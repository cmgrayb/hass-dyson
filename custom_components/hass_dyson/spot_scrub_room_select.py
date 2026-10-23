"""Per-room Spot+Scrub settings as select entities.

One shared store per robot reads the room preferences every 60 seconds (so
changes made in MyDyson appear in Home Assistant) and serialises writes. Each
room gets a select for its cleaning mode, vacuum power, hydration and wash
repetitions. Rooms are discovered from the first successful read.
"""

from __future__ import annotations

import asyncio
import logging
import weakref
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity
from .spot_scrub import (
    IDLE_STATES,
    ROOM_SETTINGS,
    decode_room_settings,
    read_preferences,
    room_name,
    room_settings_payload,
    settings_match,
)

_LOGGER = logging.getLogger(__name__)

REFRESH_INTERVAL = timedelta(seconds=60)

SETTING_LABELS = {
    "cleaning_mode": "cleaning mode",
    "vacuum_power": "vacuum power",
    "hydration": "hydration",
    "wash_repetitions": "wash repetitions",
}


class SpotScrubNotIdleError(Exception):
    """The robot is not docked or finished, so preferences are not written."""


class SpotScrubInvalidRequestError(ValueError):
    """A requested room, setting or value does not exist on this robot."""


class SpotScrubRoomStore:
    """Shared, serialised access to one robot's room preferences."""

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        self.coordinator = coordinator
        self.preferences: dict[str, Any] | None = None
        self._lock = asyncio.Lock()
        self._listeners: list[Callable[[], None]] = []
        self._unsub_timer: Callable[[], None] | None = None

    @property
    def rows(self) -> dict[int, list[Any]]:
        """Current room rows by room id (empty until a read succeeds)."""
        return {row[0]: row for row in (self.preferences or {}).get("room", [])}

    @callback
    def publish(self, preferences: dict[str, Any] | None) -> None:
        """Store a confirmed read and notify listening entities."""
        self.preferences = preferences
        for listener in list(self._listeners):
            listener()

    @callback
    def async_add_listener(
        self, hass: HomeAssistant, listener: Callable[[], None]
    ) -> Callable[[], None]:
        """Listen for updates; the refresh timer runs while anyone listens."""
        self._listeners.append(listener)
        if self._unsub_timer is None:
            self._unsub_timer = async_track_time_interval(
                hass, self._async_timer, REFRESH_INTERVAL
            )

        @callback
        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)
            if not self._listeners and self._unsub_timer is not None:
                self._unsub_timer()
                self._unsub_timer = None

        return remove

    async def _async_timer(self, _now: Any) -> None:
        await self.async_refresh()

    async def async_refresh(self) -> None:
        """Read the robot without changing anything."""
        async with self._lock:
            try:
                _, preferences = await read_preferences(self.coordinator.device)
            except (RuntimeError, ValueError, TimeoutError, AttributeError) as err:
                _LOGGER.debug("Unable to read Spot+Scrub room preferences: %s", err)
                preferences = None
        self.publish(preferences)

    async def async_apply(
        self,
        resolve: Callable[[dict[str, Any]], dict[int, dict[str, Any]]],
    ) -> dict[int, dict[str, Any]]:
        """Write resolved room settings while idle and confirm them by read-back.

        ``resolve`` turns the freshly read preferences into {room_id: settings};
        raising ValueError there rejects the request before anything is sent.
        """
        async with self._lock:
            device = self.coordinator.device
            if device is None or getattr(device, "robot_state", None) not in (
                IDLE_STATES
            ):
                raise SpotScrubNotIdleError
            map_id, preferences = await read_preferences(device)
            try:
                changes = resolve(preferences)
            except ValueError as err:
                raise SpotScrubInvalidRequestError(str(err)) from err
            payload = room_settings_payload(map_id, preferences, changes)
            await device.send_jdm_command("service.set_preference", payload)
            confirmed_map, confirmed = await read_preferences(device)
            actual = {row[0]: row for row in confirmed["room"]}
            if confirmed_map != map_id or any(
                room_id not in actual or not settings_match(actual[room_id], settings)
                for room_id, settings in changes.items()
            ):
                self.preferences = confirmed
                raise ValueError("Robot did not confirm the requested room settings")
        self.publish(confirmed)
        return changes


_STORES: weakref.WeakKeyDictionary[Any, SpotScrubRoomStore] = (
    weakref.WeakKeyDictionary()
)


def get_room_store(coordinator: DysonDataUpdateCoordinator) -> SpotScrubRoomStore:
    """Return the one store for this robot."""
    store = _STORES.get(coordinator)
    if store is None:
        store = _STORES[coordinator] = SpotScrubRoomStore(coordinator)
    return store


def _option_to_str(setting: str, option: Any) -> str:
    return f"{option}x" if setting == "wash_repetitions" else str(option)


def _str_to_option(setting: str, value: str) -> Any:
    if setting == "wash_repetitions":
        return int(value.rstrip("x"))
    return value


class DysonSpotScrubRoomSettingSelect(DysonEntity, SelectEntity):
    """One setting of one room, kept in sync with the robot."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: DysonDataUpdateCoordinator,
        store: SpotScrubRoomStore,
        room_id: int,
        name: str,
        setting: str,
    ) -> None:
        """Initialize a select for one room setting."""
        super().__init__(coordinator)
        self._store = store
        self._room_id = room_id
        self._setting = setting
        self._attr_unique_id = f"{coordinator.serial_number}_room_{room_id}_{setting}"
        self._attr_name = f"{name} {SETTING_LABELS[setting]}"
        self._attr_icon = "mdi:floor-plan"
        self._attr_options = [
            _option_to_str(setting, option) for option in ROOM_SETTINGS[setting][1]
        ]

    @property
    def available(self) -> bool:
        """Available while the robot's preferences include this room."""
        return super().available and self._room_id in self._store.rows

    @property
    def current_option(self) -> str | None:
        """The robot's current value, or None for an undecoded code."""
        row = self._store.rows.get(self._room_id)
        if row is None:
            return None
        option = decode_room_settings(row)[self._setting]
        return None if option is None else _option_to_str(self._setting, option)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Identify the room for automations."""
        return {"room_id": self._room_id}

    async def async_added_to_hass(self) -> None:
        """Follow the shared store."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._store.async_add_listener(self.hass, self.async_write_ha_state)
        )

    async def async_select_option(self, option: str) -> None:
        """Write this one setting, leaving everything else unchanged."""
        if option not in self.options:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="spot_scrub_invalid_mode"
            )
        value = _str_to_option(self._setting, option)
        try:
            await self._store.async_apply(
                lambda _prefs: {self._room_id: {self._setting: value}}
            )
        except SpotScrubNotIdleError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="spot_scrub_not_idle"
            ) from err
        except (RuntimeError, ValueError, TimeoutError) as err:
            _LOGGER.debug("Spot+Scrub room setting change failed: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="spot_scrub_request_failed",
            ) from err
        finally:
            self.async_write_ha_state()


async def async_setup_room_selects(
    hass: HomeAssistant,
    coordinator: DysonDataUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add room selects once rooms are known, and for rooms added later."""
    store = get_room_store(coordinator)
    added: set[int] = set()

    @callback
    def add_new_rooms() -> None:
        new = [row for room_id, row in store.rows.items() if room_id not in added]
        if not new:
            return
        entities = []
        for row in new:
            added.add(row[0])
            try:
                name = room_name(row)
            except ValueError:
                name = f"Room {row[0]}"
            entities.extend(
                DysonSpotScrubRoomSettingSelect(
                    coordinator, store, row[0], name, setting
                )
                for setting in ROOM_SETTINGS
            )
        async_add_entities(entities)

    # Keep discovering for the life of the entry; the store's timer runs while
    # this listener is registered.
    remove = store.async_add_listener(hass, add_new_rooms)
    entry = getattr(coordinator, "config_entry", None)
    if entry is not None and hasattr(entry, "async_on_unload"):
        entry.async_on_unload(remove)
    hass.async_create_task(store.async_refresh())
