"""Entities for Spot+Scrub (JDM) schedules kept on the robot.

- calendar: enabled schedules as weekly events (replaces the cloud
  ``unifiedscheduler`` calendar, which returns 404 for these robots);
- sensor: number of schedules, with every schedule and the robot's summary
  as attributes, including whether HA's copy is in step;
- switch: one per schedule, to switch it on or off.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity
from .spot_scrub_schedule import (
    DAYS,
    SpotScrubScheduleManager,
    describe_order,
    get_schedule_manager,
    mask_to_days,
)

EVENT_LENGTH = timedelta(hours=1)
_DAY_LABELS = dict(zip(DAYS, ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")))


def schedule_label(order: dict[str, Any]) -> str:
    """Short label such as ``10:00 Mon, Wed``."""
    days = mask_to_days(order["day"])
    label = (
        "Every day" if len(days) == 7 else ", ".join(_DAY_LABELS[day] for day in days)
    )
    return f"{order['hour']:02d}:{order['minute']:02d} {label}"


def expand_orders(
    orders: list[dict[str, Any]],
    range_start: datetime,
    range_end: datetime,
    device_name: str,
    local_tz: Any = None,
) -> list[CalendarEvent]:
    """Weekly events for enabled orders that overlap the range."""
    tz = local_tz or dt_util.get_default_time_zone()
    events: list[CalendarEvent] = []
    for order in orders:
        if order["enable"] != 1:
            continue
        weekdays = {DAYS.index(day) for day in mask_to_days(order["day"])}
        rooms = describe_order(order)["rooms"]
        description = "\n".join(
            [
                f"Schedule {order['id']}",
                f"Rooms: {', '.join(rooms) if rooms else 'unknown'}",
            ]
        )
        current = range_start.astimezone(tz).date() - timedelta(days=1)
        last = range_end.astimezone(tz).date()
        while current <= last:
            if current.weekday() in weekdays:
                start = datetime.combine(
                    current, time(order["hour"], order["minute"]), tzinfo=tz
                )
                end = start + EVENT_LENGTH
                if end > range_start and start < range_end:
                    events.append(
                        CalendarEvent(
                            summary=f"{device_name}: room clean",
                            start=start,
                            end=end,
                            description=description,
                            uid=f"{order['id']}-{current.isoformat()}",
                        )
                    )
            current += timedelta(days=1)
    events.sort(key=lambda event: event.start)
    return events


class _ScheduleEntity(DysonEntity):
    """Base: follows the schedule manager."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(
        self,
        coordinator: DysonDataUpdateCoordinator,
        manager: SpotScrubScheduleManager,
    ) -> None:
        super().__init__(coordinator)
        self._manager = manager

    async def async_added_to_hass(self) -> None:
        """Register with the manager."""
        await super().async_added_to_hass()
        await self._manager.async_load()
        self.async_on_remove(self._manager.async_add_listener(self._schedules_changed))

    @callback
    def _schedules_changed(self) -> None:
        self.async_write_ha_state()


class DysonJdmScheduleCalendar(_ScheduleEntity, CalendarEntity):
    """Enabled robot schedules as weekly calendar events."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, manager) -> None:
        """Keep the cloud calendar's unique id so the entity id stays the same."""
        super().__init__(coordinator, manager)
        self._attr_unique_id = f"{coordinator.serial_number}_schedule_calendar"
        self._attr_translation_key = "schedule"

    def _events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        return expand_orders(
            list(self._manager.orders.values()),
            start,
            end,
            str(self.coordinator.device_name),
        )

    @property
    def event(self) -> CalendarEvent | None:
        """The current or next schedule run."""
        now = dt_util.now()
        events = [e for e in self._events(now, now + timedelta(days=8)) if e.end > now]
        return events[0] if events else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Schedule runs in the requested range."""
        return self._events(start_date, end_date)


class DysonJdmSchedulesSensor(_ScheduleEntity, SensorEntity):
    """Number of schedules on the robot, as Home Assistant knows them."""

    _attr_icon = "mdi:calendar-multiple"

    def __init__(self, coordinator, manager) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, manager)
        self._attr_unique_id = f"{coordinator.serial_number}_jdm_schedules"
        self._attr_translation_key = "jdm_schedules"

    @property
    def native_value(self) -> int:
        """Known schedules."""
        return len(self._manager.orders)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Each schedule and the robot's own summary."""
        summary = self._manager.robot_summary or {}
        return {
            "schedules": [
                describe_order(order)
                for order in sorted(
                    self._manager.orders.values(),
                    key=lambda o: (o["hour"], o["minute"], o["id"]),
                )
            ],
            "in_sync": self._manager.in_sync,
            "robot_total": summary.get("total"),
            "robot_enabled": summary.get("enable"),
            "robot_checksum": summary.get("md5"),
            "last_checked": self._manager.summary_checked,
        }


class DysonJdmScheduleSwitch(_ScheduleEntity, SwitchEntity):
    """Switch one robot schedule on or off."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, manager, schedule_id: int) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, manager)
        self._schedule_id = schedule_id
        self._attr_unique_id = f"{coordinator.serial_number}_jdm_schedule_{schedule_id}"

    @property
    def _order(self) -> dict[str, Any] | None:
        return self._manager.orders.get(self._schedule_id)

    @property
    def name(self) -> str:
        """Name from the schedule's time and days."""
        order = self._order
        return f"Schedule {schedule_label(order)}" if order else "Schedule"

    @property
    def is_on(self) -> bool | None:
        """Whether the schedule is enabled."""
        order = self._order
        return order["enable"] == 1 if order else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The schedule's details."""
        order = self._order
        return describe_order(order) if order else {}

    @callback
    def _schedules_changed(self) -> None:
        if self._order is None:
            # Deleted on the robot (from HA or MyDyson): remove this entity.
            registry = er.async_get(self.hass)
            if registry.async_get(self.entity_id):
                registry.async_remove(self.entity_id)
            else:
                self.hass.async_create_task(self.async_remove())
            return
        self.async_write_ha_state()

    async def _async_set(self, enabled: bool) -> None:
        try:
            await self._manager.async_set_schedule(self._schedule_id, enabled=enabled)
        except (RuntimeError, ValueError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="jdm_schedule_failed"
            ) from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the schedule."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the schedule."""
        await self._async_set(False)


async def async_setup_schedule_switches(
    hass: HomeAssistant,
    coordinator: DysonDataUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
    on_unload: Any,
) -> None:
    """Add a switch per schedule now and whenever a new one appears."""
    manager = get_schedule_manager(hass, coordinator)
    await manager.async_load()
    known: set[int] = set()

    # Drop switches of schedules deleted while Home Assistant was not running.
    registry = er.async_get(hass)
    prefix = f"{coordinator.serial_number}_jdm_schedule_"
    for entry in er.async_entries_for_config_entry(
        registry, coordinator.config_entry.entry_id
    ):
        suffix = entry.unique_id.removeprefix(prefix)
        if (
            entry.domain == "switch"
            and entry.unique_id.startswith(prefix)
            and (not suffix.isdigit() or int(suffix) not in manager.orders)
        ):
            registry.async_remove(entry.entity_id)

    @callback
    def add_new() -> None:
        new = [order_id for order_id in manager.orders if order_id not in known]
        known.intersection_update(manager.orders)
        if new:
            known.update(new)
            async_add_entities(
                [
                    DysonJdmScheduleSwitch(coordinator, manager, order_id)
                    for order_id in new
                ]
            )

    add_new()
    on_unload(manager.async_add_listener(add_new))
