"""Button platform for Dyson integration."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from libdyson_rest.models import PersistentMapMeta, ZoneMeta

from .const import DEVICE_CATEGORY_ROBOT, DOMAIN, ROBOT_MSG_MAP_MANIFEST_UPDATED
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity

_LOGGER = logging.getLogger(__name__)

# Retry schedule (seconds) for zone-button discovery when the cloud fetch
# fails during setup.  After the schedule is exhausted the Refresh Zone List
# button remains available for manual recovery.
ZONE_DISCOVERY_RETRY_DELAYS: tuple[float, ...] = (60.0, 300.0, 900.0)

# Coalescing delay (seconds) between the robot's PERSISTENT-MAP-MANIFEST-
# UPDATED broadcast and the metadata re-fetch it triggers — the broadcast
# can repeat, and device message callbacks may deliver a message twice.
MANIFEST_REFRESH_DEBOUNCE: float = 5.0


def _async_migrate_zone_button_unique_ids(
    hass: HomeAssistant,
    coordinator: DysonDataUpdateCoordinator,
    maps: list[PersistentMapMeta],
) -> None:
    """Migrate pre-multi-map zone-button unique_ids to the map-qualified form.

    The old ``{serial}_clean_zone_{zone_id}`` unique_id is ambiguous across
    maps (zone ids restart from 1 per map). The old dedupe created each
    button for the first map in API order carrying that zone id, so the
    first map claiming an old unique_id here reproduces exactly which map
    the entity belonged to — existing entities keep their entity_id and
    history.
    """
    ent_reg = er.async_get(hass)
    serial = coordinator.serial_number
    claimed_old_ids: set[str] = set()
    for pmap in maps:
        for zone in pmap.zones:
            if not zone.id:
                continue
            old_unique_id = f"{serial}_clean_zone_{zone.id}"
            if old_unique_id in claimed_old_ids:
                continue
            entity_id = ent_reg.async_get_entity_id("button", DOMAIN, old_unique_id)
            if entity_id is None:
                continue
            # The first map (in API order) carrying this zone id owns the old
            # entity — even when the migration below is skipped, a later map
            # with a colliding zone id must not claim it.
            claimed_old_ids.add(old_unique_id)
            new_unique_id = f"{serial}_clean_zone_{pmap.id}_{zone.id}"
            if ent_reg.async_get_entity_id("button", DOMAIN, new_unique_id):
                _LOGGER.debug(
                    "Zone button %s already exists; leaving %s unmigrated",
                    new_unique_id,
                    old_unique_id,
                )
                continue
            ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)
            _LOGGER.info(
                "Migrated zone button %s unique_id: %s → %s",
                entity_id,
                old_unique_id,
                new_unique_id,
            )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dyson button platform."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    # BLE devices manage their own reconnection — MQTT reconnect button not applicable
    if isinstance(entry_data, dict) and entry_data.get("is_ble"):
        return
    coordinator: DysonDataUpdateCoordinator = entry_data

    # Robot vacuums (Vis Nav): auto-discover per-zone clean buttons from the
    # persistent-map metadata fetched from the Dyson cloud.
    is_robot = any(
        cat == DEVICE_CATEGORY_ROBOT for cat in (coordinator.device_category or [])
    )
    has_token = bool(coordinator.config_entry.data.get("auth_token"))

    if not (is_robot and has_token):
        async_add_entities([DysonReconnectButton(coordinator)], True)
        return

    known_zone_buttons: dict[tuple[str, str], DysonZoneCleanButton] = {}

    async def _async_discover_zone_buttons() -> int:
        """Fetch map metadata; add, update, and retire zone buttons to match.

        Existing buttons pick up zone/map renames, icon changes, and a fresh
        zonesDefinitionLastUpdatedDate snapshot; buttons whose zone vanished
        from the manifest are retired (unavailable).

        Returns the number of buttons added; raises if the cloud fetch fails.
        """
        # Lazy import to avoid a setup-time circular dependency with services.py.
        from .services import _fetch_persistent_map_metadata

        maps = await _fetch_persistent_map_metadata(coordinator)

        _async_migrate_zone_button_unique_ids(hass, coordinator, maps)

        # Zone ids restart from 1 on every map, so dedupe on (map, zone) —
        # a bare-zone-id key would silently drop every later map's buttons.
        qualify_names = len(maps) > 1
        new_buttons: list[ButtonEntity] = []
        fresh_keys: set[tuple[str, str]] = set()
        for pmap in maps:
            for zone in pmap.zones:
                if not zone.id:
                    continue
                key = (pmap.id, zone.id)
                fresh_keys.add(key)
                existing = known_zone_buttons.get(key)
                if existing is not None:
                    existing.async_update_zone_meta(
                        pmap, zone, qualify_name=qualify_names
                    )
                    continue
                button = DysonZoneCleanButton(
                    coordinator, pmap, zone, qualify_name=qualify_names
                )
                known_zone_buttons[key] = button
                new_buttons.append(button)

        # A zone deleted in the MyDyson app leaves a button whose START the
        # robot would mishandle (per-zone commands degrade silently) — retire
        # it. An empty maps list means a failed read, not an empty home:
        # never retire on it.
        if maps:
            for key, button in known_zone_buttons.items():
                if key not in fresh_keys:
                    button.async_mark_zone_deleted()

        if new_buttons:
            async_add_entities(new_buttons, True)
            _LOGGER.info(
                "Created %d per-zone clean buttons for %s",
                len(new_buttons),
                coordinator.serial_number,
            )
        return len(new_buttons)

    # The reconnect and refresh buttons are created unconditionally so a
    # failed cloud fetch never removes the manual recovery path.
    async_add_entities(
        [
            DysonReconnectButton(coordinator),
            DysonRefreshZonesButton(coordinator, _async_discover_zone_buttons),
        ],
        True,
    )

    # React to the robot's own manifest broadcast: within ~1 minute of a zone
    # edit in the MyDyson app (or its post-clean map update) the robot
    # publishes PERSISTENT-MAP-MANIFEST-UPDATED, so the buttons follow
    # app-side changes without a manual refresh or restart.
    manifest_refresh_unsub: CALLBACK_TYPE | None = None
    manifest_listener_removed = False

    async def _async_manifest_refresh(_now) -> None:
        nonlocal manifest_refresh_unsub
        manifest_refresh_unsub = None
        from .services import _persistent_map_cache

        _persistent_map_cache.invalidate(coordinator.serial_number)
        try:
            await _async_discover_zone_buttons()
        except Exception as err:  # noqa: BLE001 — the next broadcast retries
            _LOGGER.debug(
                "Manifest-triggered zone refresh failed for %s: %s",
                coordinator.serial_number,
                err,
            )

    def _schedule_manifest_refresh() -> None:
        nonlocal manifest_refresh_unsub
        # A broadcast can be in flight (queued via call_soon_threadsafe)
        # when the entry unloads — never re-arm after teardown.
        if manifest_listener_removed:
            return
        if manifest_refresh_unsub is not None:
            manifest_refresh_unsub()
        manifest_refresh_unsub = async_call_later(
            hass, MANIFEST_REFRESH_DEBOUNCE, _async_manifest_refresh
        )

    def _on_device_message(topic: str, data: dict[str, Any]) -> None:
        # Fires on paho's network thread — hop to the event loop.
        if data.get("msg") != ROBOT_MSG_MAP_MANIFEST_UPDATED:
            return
        hass.loop.call_soon_threadsafe(_schedule_manifest_refresh)

    device = coordinator.device
    if device is not None:
        device.add_message_callback(_on_device_message)

        def _remove_manifest_listener() -> None:
            nonlocal manifest_listener_removed
            manifest_listener_removed = True
            device.remove_message_callback(_on_device_message)
            if manifest_refresh_unsub is not None:
                manifest_refresh_unsub()

        config_entry.async_on_unload(_remove_manifest_listener)

    try:
        await _async_discover_zone_buttons()
    except Exception as err:  # noqa: BLE001 — never block setup over zone discovery
        _LOGGER.warning(
            "Could not fetch persistent map for %s; retrying zone-button"
            " discovery in the background: %s",
            coordinator.serial_number,
            err,
        )
    else:
        return

    # Retry on a backoff schedule so the buttons reappear without a Home
    # Assistant restart once the cloud recovers.
    retry_delays = iter(ZONE_DISCOVERY_RETRY_DELAYS)
    cancel_retry: CALLBACK_TYPE | None = None

    async def _async_retry(_now) -> None:
        nonlocal cancel_retry
        cancel_retry = None
        try:
            await _async_discover_zone_buttons()
        except Exception as err:  # noqa: BLE001 — keep retrying on the schedule
            _LOGGER.debug(
                "Zone-button discovery retry failed for %s: %s",
                coordinator.serial_number,
                err,
            )
            _schedule_retry()

    def _schedule_retry() -> None:
        nonlocal cancel_retry
        delay = next(retry_delays, None)
        if delay is None:
            _LOGGER.warning(
                "Zone-button discovery for %s did not succeed after %d retries;"
                " press the Refresh Zone List button to retry",
                coordinator.serial_number,
                len(ZONE_DISCOVERY_RETRY_DELAYS),
            )
            return
        cancel_retry = async_call_later(hass, delay, _async_retry)

    def _cancel_pending_retry() -> None:
        if cancel_retry is not None:
            cancel_retry()

    config_entry.async_on_unload(_cancel_pending_retry)
    _schedule_retry()


class DysonReconnectButton(DysonEntity, ButtonEntity):
    """Button to trigger intelligent reconnection to device."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the reconnect button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_reconnect"
        self._attr_name = "Reconnect"
        self._attr_icon = "mdi:wifi-sync"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Handle the button press to trigger intelligent reconnection."""
        if not self.coordinator.device:
            _LOGGER.warning("Device not available for reconnect")
            return

        try:
            _LOGGER.info(
                "Manual reconnect triggered for %s", self.coordinator.serial_number
            )
            success = await self.coordinator.device.force_reconnect()
            if success:
                _LOGGER.info(
                    "Manual reconnection successful for %s",
                    self.coordinator.serial_number,
                )
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.warning(
                    "Manual reconnection failed for %s", self.coordinator.serial_number
                )
        except Exception as err:
            _LOGGER.error(
                "Failed to manually reconnect %s: %s",
                self.coordinator.serial_number,
                err,
            )


class DysonZoneCleanButton(DysonEntity, ButtonEntity):
    """Per-zone 'Clean this room' button (Vis Nav).

    One entity per zone per persistent map. Tapping sends a START MQTT
    command with cleaningMode='zoneConfigured' targeting just that zone.
    """

    coordinator: DysonDataUpdateCoordinator

    def __init__(
        self,
        coordinator: DysonDataUpdateCoordinator,
        pmap: PersistentMapMeta,
        zone: ZoneMeta,
        qualify_name: bool = False,
    ) -> None:
        super().__init__(coordinator)
        self._pmap_id: str = pmap.id
        self._zone_id: str = zone.id
        self._zone_deleted: bool = False
        # unique_id is map-qualified — zone ids restart from 1 on every map.
        # Both components are stable in MyDyson even if the user renames them.
        self._attr_unique_id = (
            f"{coordinator.serial_number}_clean_zone_{self._pmap_id}_{self._zone_id}"
        )
        self._apply_zone_meta(pmap, zone, qualify_name)

    def _apply_zone_meta(
        self, pmap: PersistentMapMeta, zone: ZoneMeta, qualify_name: bool
    ) -> None:
        """Snapshot the map/zone fields the entity presents and sends."""
        self._pmap_name = str(pmap.name or pmap.id)
        self._pmap_zdlud: str | None = pmap.zones_definition_last_updated_date
        self._zone_name = str(zone.name or f"Zone {self._zone_id}")
        self._attr_name = (
            f"Clean {self._zone_name} ({self._pmap_name})"
            if qualify_name
            else f"Clean {self._zone_name}"
        )
        self._attr_icon = _icon_for_zone(zone.icon)

    @callback
    def async_update_zone_meta(
        self, pmap: PersistentMapMeta, zone: ZoneMeta, qualify_name: bool
    ) -> None:
        """Refresh the construction-time snapshots after a metadata re-fetch.

        Propagates zone/map renames and icon changes to the live entity and
        the registry, resurfaces a button whose zone reappeared, and renews
        the zonesDefinitionLastUpdatedDate snapshot sent with every START —
        the device mishandles zone commands carrying a stale one.
        """
        old_name, old_icon = self._attr_name, self._attr_icon
        was_deleted = self._zone_deleted
        self._zone_deleted = False
        self._apply_zone_meta(pmap, zone, qualify_name)
        if self.hass is None or self.entity_id is None:
            return
        if self._attr_name != old_name and self.registry_entry is not None:
            # Keep the registry's suggested name in sync — a user's manual
            # rename (the registry ``name`` field) still wins over this.
            er.async_get(self.hass).async_update_entity(
                self.entity_id, original_name=self._attr_name
            )
        if self._attr_name != old_name or self._attr_icon != old_icon or was_deleted:
            _LOGGER.info(
                "Zone button %s updated: %r → %r",
                self.entity_id,
                old_name,
                self._attr_name,
            )
            self.async_write_ha_state()

    @callback
    def async_mark_zone_deleted(self) -> None:
        """Retire the button after its zone vanished from the map manifest."""
        if self._zone_deleted:
            return
        self._zone_deleted = True
        _LOGGER.info(
            "Zone %s (%s) no longer exists on map %s; disabling its clean button",
            self._zone_id,
            self._zone_name,
            self._pmap_name,
        )
        if self.hass is not None and self.entity_id is not None:
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Unavailable while the robot is known to be on a different map.

        The signal is the robot's MQTT-reported map (announced during every
        clean), falling back to the cloud isCurrentMap flag. When neither is
        available (e.g. a freshly restarted Vis Nav on its dock — the v1 API
        omits isCurrentMap) every zone button stays available. A button whose
        zone was deleted in the MyDyson app is always unavailable.
        """
        if self._zone_deleted:
            return False
        if not super().available:
            return False
        from .services import _effective_current_map, _persistent_map_cache

        maps = _persistent_map_cache.get_stale(self.coordinator.serial_number) or []
        current = _effective_current_map(maps, self.coordinator)
        return current is None or current.id == self._pmap_id

    async def async_press(self) -> None:
        if self._zone_deleted:
            raise HomeAssistantError(
                f"Zone {self._zone_name!r} was removed from map "
                f"{self._pmap_name!r} in the MyDyson app; this button no "
                "longer has a zone to clean"
            )
        if not self.coordinator.device:
            raise HomeAssistantError(
                f"Device {self.coordinator.serial_number} not available"
            )
        # Guard against a stale UI: the robot can only clean the map it is on.
        from .services import _effective_current_map, _persistent_map_cache

        maps = _persistent_map_cache.get_stale(self.coordinator.serial_number) or []
        current = _effective_current_map(maps, self.coordinator)
        if current is not None and current.id != self._pmap_id:
            raise HomeAssistantError(
                f"The robot is currently using map {current.name or current.id!r}; "
                f"{self._zone_name!r} is on map {self._pmap_name!r}. Move the robot "
                "to that map and refresh the zone list, then retry."
            )
        cleaning_programme = {
            "persistentMapId": self._pmap_id,
            "orderedZones": [],
            "unorderedZones": [self._zone_id],
        }
        # Without zonesDefinitionLastUpdatedDate the device silently
        # downgrades the START to a global (whole-house) clean.
        if self._pmap_zdlud:
            cleaning_programme["zonesDefinitionLastUpdatedDate"] = self._pmap_zdlud
        _LOGGER.info(
            "Zone-clean button pressed: %s → zone %s (%s, map %s)",
            self.coordinator.serial_number,
            self._zone_id,
            self._zone_name,
            self._pmap_name,
        )
        try:
            await self.coordinator.device.robot_start_clean(
                cleaning_mode="zoneConfigured",
                full_clean_type="immediate",
                cleaning_programme=cleaning_programme,
            )
        except Exception as err:
            raise HomeAssistantError(
                f"Failed to start clean of {self._zone_name}: {err}"
            ) from err


class DysonRefreshZonesButton(DysonEntity, ButtonEntity):
    """Re-fetch the persistent map metadata from the Dyson cloud.

    Invalidates the in-process cache used by the start_zone_clean service and
    zone-clean buttons, then reconciles the buttons with the fresh manifest:
    new zones gain buttons, renamed zones/maps pick up their new names in
    place (unique_id is the map + zone id, so the entity survives), and
    deleted zones have their buttons retired.  The same reconciliation runs
    automatically when the robot broadcasts PERSISTENT-MAP-MANIFEST-UPDATED.
    """

    coordinator: DysonDataUpdateCoordinator

    def __init__(
        self,
        coordinator: DysonDataUpdateCoordinator,
        discover_zone_buttons: Callable[[], Awaitable[int]] | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._discover_zone_buttons = discover_zone_buttons
        self._attr_unique_id = f"{coordinator.serial_number}_refresh_zones"
        self._attr_name = "Refresh Zone List"
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        from .services import _fetch_persistent_map_metadata, _persistent_map_cache

        _persistent_map_cache.invalidate(self.coordinator.serial_number)
        try:
            if self._discover_zone_buttons is not None:
                added = await self._discover_zone_buttons()
                _LOGGER.info(
                    "Refreshed persistent map for %s: %d new zone button(s) added",
                    self.coordinator.serial_number,
                    added,
                )
                return
            maps = await _fetch_persistent_map_metadata(self.coordinator)
            _LOGGER.info(
                "Refreshed persistent map for %s: %d map(s), %d zone(s) total. "
                "Restart HA to surface any newly-added zones as buttons.",
                self.coordinator.serial_number,
                len(maps),
                sum(len(m.zones) for m in maps),
            )
        except Exception as err:
            raise HomeAssistantError(
                f"Failed to refresh zones for {self.coordinator.serial_number}: {err}"
            ) from err


# Map persistent-map zone icon names (as returned by Dyson cloud) to MDI icons.
_ZONE_ICON_MAP: dict[str, str] = {
    "hallway": "mdi:floor-plan",
    "living_room": "mdi:sofa",
    "bedroom": "mdi:bed-outline",
    "main_bedroom": "mdi:bed",
    "bathroom": "mdi:shower",
    "toilet": "mdi:toilet",
    "kitchen": "mdi:silverware-fork-knife",
    "dining_room": "mdi:silverware",
    "work": "mdi:desk",
    "office": "mdi:desk",
    "garage": "mdi:garage",
    "custom": "mdi:floor-plan",
}


def _icon_for_zone(icon_key: str | None) -> str:
    """Return an MDI icon for a Dyson zone icon key (falls back to a generic icon)."""
    if not icon_key:
        return "mdi:vacuum"
    return _ZONE_ICON_MAP.get(str(icon_key), "mdi:vacuum")
