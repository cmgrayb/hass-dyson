"""Spot+Scrub (JDM) cleaning schedules kept on the robot.

The RB05 and RB07 store schedules ("orders") on the robot. MyDyson writes
them over MQTT with ``service.add_order`` (create, edit and switching on or
off all re-send the full order with the same id) and ``service.del_order``
{id}. ``service.get_order`` {} only returns a summary, ``order_data_lite``
{total, enable, md5, timestamp}; there is no full read over MQTT.

So Home Assistant keeps its own copy of the orders in a ``Store``. It learns
orders it writes itself and every order the app writes while HA is connected
(the robot echoes all ``command/jdm`` traffic to subscribers). Changes made
while HA was offline are detected from the summary: when the robot's total
or checksum stops matching HA's copy, the schedules are flagged out of sync
until the order is re-sent (switching it off and on again in MyDyson does
that).

Captured from MyDyson (RB05 2026-11-12, RB07 2026-11-10):
``{"id": 7171834, "enable": 1, "day": 64, "hour": 10, "minute": 0,
"repeat": 1, "map_id": ..., "room_count": 7, "time_zone": 39600,
"prefer_type": 1, "is_global": 0, "areas": [], "room_preference": [...],
"uv_switch": [...]}``. ``day`` is a bitmask; Sunday = 64 was observed, the
other bits (Monday = 1 ... Saturday = 32) are inferred. ``time_zone`` is the
UTC offset in seconds. Switching an order off sent ``uv_switch`` all zero.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import random
import time
import weakref
from collections.abc import Callable, Iterable
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .device_utils import mask_serial
from .spot_scrub import read_preferences, resolve_room_settings, room_settings_payload

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
POLL_INTERVAL = timedelta(minutes=10)
PENDING_TTL = 60.0

ADD_ORDER = "service.add_order"
DEL_ORDER = "service.del_order"
GET_ORDER = "service.get_order"

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_BITS = {day: 1 << index for index, day in enumerate(DAYS)}

# Key order of MyDyson's add_order params.
ORDER_KEYS = (
    "id",
    "enable",
    "day",
    "hour",
    "minute",
    "repeat",
    "map_id",
    "room_count",
    "time_zone",
    "prefer_type",
    "is_global",
    "areas",
    "room_preference",
    "uv_switch",
)


class ScheduleNotFoundError(ValueError):
    """The schedule id is not in Home Assistant's copy of the robot's orders."""


def days_to_mask(days: Iterable[str]) -> int:
    """Return the robot's day bitmask for day names (mon ... sun)."""
    mask = 0
    for day in days:
        key = str(day).strip().lower()[:3]
        if key not in DAY_BITS:
            raise ValueError(f"Unknown day: {day}")
        mask |= DAY_BITS[key]
    if not mask:
        raise ValueError("At least one day is required")
    return mask


def mask_to_days(mask: int) -> list[str]:
    """Return day names for a bitmask, Monday first."""
    return [day for day in DAYS if mask & DAY_BITS[day]]


def validate_order(params: Any) -> dict[str, Any]:
    """Return the order if its scheduling fields have the captured shape."""
    if not isinstance(params, dict):
        raise ValueError("Order is not a mapping")
    for key, low, high in (
        ("id", 0, 2**63),
        ("enable", 0, 1),
        ("day", 1, 127),
        ("hour", 0, 23),
        ("minute", 0, 59),
    ):
        value = params.get(key)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"Unrecognized order field {key}: {value!r}")
    return params


def room_names(order: dict[str, Any]) -> list[str]:
    """Room names in an order's room plan, in the order MyDyson lists them."""
    rows = order.get("room_preference")
    if not isinstance(rows, list):
        return []
    return [row[1] for row in rows if isinstance(row, list) and len(row) > 1 and row[1]]


def describe_order(order: dict[str, Any]) -> dict[str, Any]:
    """A readable summary of one order for attributes and service responses."""
    return {
        "schedule_id": order["id"],
        "enabled": order["enable"] == 1,
        "days": mask_to_days(order["day"]),
        "time": f"{order['hour']:02d}:{order['minute']:02d}",
        "repeat": order.get("repeat") == 1,
        "rooms": room_names(order),
    }


def _uv_off(uv: list[Any]) -> list[list[Any]]:
    return [[item[0], 0] for item in uv if isinstance(item, list) and item]


def _uv_is_off(uv: Any) -> bool:
    return not isinstance(uv, list) or all(
        isinstance(item, list) and len(item) == 2 and item[1] == 0 for item in uv
    )


def current_utc_offset() -> int:
    """The HA time zone's current UTC offset in seconds, as MyDyson sends it."""
    offset = dt_util.now().utcoffset()
    return int(offset.total_seconds()) if offset else 0


class SpotScrubScheduleManager:
    """Home Assistant's copy of one robot's schedules, kept in step over MQTT."""

    def __init__(self, hass: HomeAssistant, coordinator: Any) -> None:
        self.hass = hass
        self.coordinator = coordinator
        serial = coordinator.serial_number
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.jdm_schedules.{serial}"
        )
        self.orders: dict[int, dict[str, Any]] = {}
        # Last switched-on UV rows per order, so switching on from HA can
        # restore what switching off cleared.
        self._uv_on: dict[int, list[Any]] = {}
        self.robot_summary: dict[str, Any] | None = None
        self.summary_checked: str | None = None
        self.in_sync: bool | None = None
        self._synced_md5: str | None = None
        self._expect_baseline = False
        self._pending: dict[str, tuple[str, Any, float]] = {}
        self._lock = asyncio.Lock()
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[Callable[[], None]] = []
        self._device: Any = None
        self._loaded = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def issue_id(self) -> str:
        """Repair issue id for this robot."""
        return f"jdm_schedules_out_of_sync_{self.coordinator.serial_number}"

    async def async_load(self) -> None:
        """Load the stored copy once."""
        if self._loaded:
            return
        self._loaded = True
        data = await self._store.async_load() or {}
        for raw in data.get("orders", []):
            try:
                order = validate_order(raw)
            except ValueError:
                continue
            self.orders[order["id"]] = order
        self._uv_on = {
            int(key): value
            for key, value in data.get("uv_on", {}).items()
            if str(key).isdigit()
        }
        self.robot_summary = data.get("robot_summary")
        self.summary_checked = data.get("summary_checked")
        self._synced_md5 = data.get("synced_md5")
        self.in_sync = data.get("in_sync")

    def _data_to_save(self) -> dict[str, Any]:
        return {
            "orders": [self.orders[key] for key in sorted(self.orders)],
            "uv_on": {str(key): value for key, value in self._uv_on.items()},
            "robot_summary": self.robot_summary,
            "summary_checked": self.summary_checked,
            "synced_md5": self._synced_md5,
            "in_sync": self.in_sync,
        }

    @callback
    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._data_to_save, 1)

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Listen for changes; MQTT tracking and polling run while anyone listens."""
        self._listeners.append(listener)
        if not self._unsubs:
            self._start()

        @callback
        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)
            if not self._listeners:
                self._stop()

        return remove

    def _start(self) -> None:
        device = self.coordinator.device
        if device is not None:
            self._device = device
            device.add_message_callback(self._on_message)
            self._unsubs.append(
                lambda: device.remove_message_callback(self._on_message)
            )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._async_poll_timer, POLL_INTERVAL)
        )
        self.hass.async_create_background_task(
            self.async_poll(), f"{DOMAIN} schedule summary"
        )

    def _stop(self) -> None:
        while self._unsubs:
            self._unsubs.pop()()
        self._device = None

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    # ------------------------------------------------------------------
    # MQTT tracking
    # ------------------------------------------------------------------

    def _on_message(self, topic: str, data: dict[str, Any]) -> None:
        """Paho-thread callback: hand JDM order traffic to the HA loop."""
        if not topic.endswith(("/command/jdm", "/status/jdm")):
            return
        method = data.get("method")
        if method not in (ADD_ORDER, DEL_ORDER, GET_ORDER):
            return
        self.hass.loop.call_soon_threadsafe(
            self._handle_message, topic, copy.deepcopy(data)
        )

    @callback
    def _handle_message(self, topic: str, data: dict[str, Any]) -> None:
        method = data.get("method")
        msg_id = str(data.get("msgId"))
        now = time.monotonic()
        for key, (_, _, sent) in list(self._pending.items()):
            if now - sent > PENDING_TTL:
                del self._pending[key]
        if topic.endswith("/command/jdm"):
            if method in (ADD_ORDER, DEL_ORDER):
                self._pending[msg_id] = (method, data.get("params"), now)
            return
        reply = data.get("data")
        if data.get("code") != 0 or not isinstance(reply, dict):
            self._pending.pop(msg_id, None)
            return
        if method == GET_ORDER:
            self._apply_summary(reply.get("order_data_lite"))
            return
        pending = self._pending.pop(msg_id, None)
        if pending is None or reply.get("result", 0) != 0:
            return
        sent_method, params, _ = pending
        try:
            if sent_method == ADD_ORDER:
                self._apply_add(params)
            elif isinstance(params, dict) and type(params.get("id")) is int:
                self._apply_delete(params["id"])
        except ValueError as err:
            _LOGGER.debug("Ignoring unrecognized order: %s", err)

    @callback
    def _apply_add(self, params: Any) -> None:
        order = validate_order(copy.deepcopy(params))
        if self.orders.get(order["id"]) == order:
            return
        self.orders[order["id"]] = order
        if order["enable"] == 1 and not _uv_is_off(order.get("uv_switch")):
            self._uv_on[order["id"]] = copy.deepcopy(order["uv_switch"])
        self._expect_baseline = True
        self._schedule_save()
        self._notify()

    @callback
    def _apply_delete(self, order_id: int) -> None:
        self._uv_on.pop(order_id, None)
        if self.orders.pop(order_id, None) is None:
            return
        self._expect_baseline = True
        self._schedule_save()
        self._notify()

    @callback
    def _apply_summary(self, lite: Any) -> None:
        if not isinstance(lite, dict) or type(lite.get("total")) is not int:
            return
        self.robot_summary = {
            key: lite.get(key) for key in ("total", "enable", "md5", "timestamp")
        }
        self.summary_checked = dt_util.utcnow().isoformat()
        md5 = lite.get("md5")
        if lite["total"] != len(self.orders):
            in_sync = False
        elif self._expect_baseline or self._synced_md5 is None:
            # The robot's list now matches a change HA saw (or HA's first
            # look): remember its checksum as the in-step value.
            self._synced_md5 = md5
            self._expect_baseline = False
            in_sync = True
        else:
            in_sync = md5 == self._synced_md5
        self._set_in_sync(in_sync)
        self._schedule_save()
        self._notify()

    @callback
    def _set_in_sync(self, in_sync: bool) -> None:
        changed = in_sync != self.in_sync
        self.in_sync = in_sync
        if in_sync:
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
            return
        if changed:
            _LOGGER.warning(
                "Schedules on %s no longer match Home Assistant's copy",
                mask_serial(self.coordinator.serial_number),
            )
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self.issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="jdm_schedules_out_of_sync",
            translation_placeholders={
                "device_name": str(self.coordinator.device_name),
                "robot_total": str((self.robot_summary or {}).get("total")),
                "known_total": str(len(self.orders)),
            },
        )

    async def _async_poll_timer(self, _now: Any) -> None:
        await self.async_poll()

    async def async_poll(self) -> None:
        """Ask the robot for its order summary (the reply is applied as it passes)."""
        await self.async_load()
        device = self.coordinator.device
        if device is None:
            return
        try:
            reply = await device.send_jdm_command(GET_ORDER, {})
        except (RuntimeError, ValueError, TimeoutError) as err:
            _LOGGER.debug("Unable to read Spot+Scrub schedule summary: %s", err)
            return
        self._apply_summary(reply.get("order_data_lite"))

    # ------------------------------------------------------------------
    # Writes from Home Assistant
    # ------------------------------------------------------------------

    def _new_id(self) -> int:
        while True:
            order_id = random.randint(1_000_000, 2**31 - 1)
            if order_id not in self.orders:
                return order_id

    async def async_set_schedule(
        self,
        schedule_id: int | None = None,
        *,
        days: Iterable[str] | None = None,
        hour: int | None = None,
        minute: int | None = None,
        enabled: bool | None = None,
        room_modes: dict[Any, Any] | None = None,
    ) -> dict[str, Any]:
        """Create (no id) or change a schedule on the robot; returns the order."""
        await self.async_load()
        async with self._lock:
            device = self.coordinator.device
            if device is None:
                raise RuntimeError("Spot+Scrub is disconnected")
            existing = None
            if schedule_id is not None:
                existing = self.orders.get(schedule_id)
                if existing is None:
                    raise ScheduleNotFoundError(f"Unknown schedule: {schedule_id}")
            elif days is None or hour is None or minute is None:
                raise ValueError("A new schedule needs days and a time")

            order: dict[str, Any] = copy.deepcopy(existing) if existing else {}
            order_id = existing["id"] if existing else self._new_id()
            uv_on = copy.deepcopy(self._uv_on.get(order_id))
            if existing is None or room_modes:
                map_id, preferences = await read_preferences(device)
                changes = (
                    resolve_room_settings(preferences, room_modes) if room_modes else {}
                )
                plan = room_settings_payload(map_id, preferences, changes)
                order.update(
                    map_id=plan["map_id"],
                    room_count=len(plan["room_preference"]),
                    prefer_type=plan["prefer_type"],
                    room_preference=plan["room_preference"],
                    uv_switch=plan["uv_switch"],
                )
                uv_on = copy.deepcopy(plan["uv_switch"])

            enable = (
                (1 if enabled else 0)
                if enabled is not None
                else (existing["enable"] if existing else 1)
            )
            uv = order.get("uv_switch", [])
            if enable:
                if _uv_is_off(uv) and uv_on is None:
                    _, preferences = await read_preferences(device)
                    rows = room_settings_payload(0, preferences, {})["uv_switch"]
                    by_room = {item[0]: item for item in rows}
                    uv_on = [copy.deepcopy(by_room.get(item[0], item)) for item in uv]
                if _uv_is_off(uv) and uv_on is not None:
                    uv = uv_on
            else:
                uv = _uv_off(uv)

            order.update(
                id=order_id,
                enable=enable,
                day=days_to_mask(days) if days is not None else order["day"],
                hour=hour if hour is not None else order["hour"],
                minute=minute if minute is not None else order["minute"],
                time_zone=current_utc_offset(),
                uv_switch=uv,
            )
            order.setdefault("repeat", 1)
            order.setdefault("is_global", 0)
            order.setdefault("areas", [])
            params = {key: order[key] for key in ORDER_KEYS if key in order}
            params.update({k: v for k, v in order.items() if k not in params})
            validate_order(params)
            await device.send_jdm_command(ADD_ORDER, params)
            if uv_on is not None and not _uv_is_off(uv_on):
                self._uv_on[order_id] = uv_on
            self._apply_add(params)
        await self.async_poll()
        return params

    async def async_delete_schedule(self, schedule_id: int) -> None:
        """Delete a schedule from the robot."""
        await self.async_load()
        async with self._lock:
            device = self.coordinator.device
            if device is None:
                raise RuntimeError("Spot+Scrub is disconnected")
            if schedule_id not in self.orders:
                raise ScheduleNotFoundError(f"Unknown schedule: {schedule_id}")
            try:
                await device.send_jdm_command(DEL_ORDER, {"id": schedule_id})
            except RuntimeError as err:
                if "rejected" not in str(err):
                    raise
                # Already gone from the robot (deleted while HA was not
                # watching): drop HA's stale copy too.
                _LOGGER.debug("Robot has no schedule %s: %s", schedule_id, err)
            self._apply_delete(schedule_id)
        await self.async_poll()


_MANAGERS: weakref.WeakKeyDictionary[Any, SpotScrubScheduleManager] = (
    weakref.WeakKeyDictionary()
)


def get_schedule_manager(
    hass: HomeAssistant, coordinator: Any
) -> SpotScrubScheduleManager:
    """Return the one schedule manager for this robot."""
    manager = _MANAGERS.get(coordinator)
    if manager is None:
        manager = _MANAGERS[coordinator] = SpotScrubScheduleManager(hass, coordinator)
    return manager
