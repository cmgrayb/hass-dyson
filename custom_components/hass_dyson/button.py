"""Button platform for Dyson integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from libdyson_rest.models import PersistentMapMeta, ZoneMeta

from .const import DEVICE_CATEGORY_ROBOT, DOMAIN
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity

_LOGGER = logging.getLogger(__name__)


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

    entities: list[ButtonEntity] = [DysonReconnectButton(coordinator)]

    # Robot vacuums (Vis Nav): auto-discover per-zone clean buttons from the
    # persistent-map metadata fetched from the Dyson cloud.
    is_robot = any(
        cat == DEVICE_CATEGORY_ROBOT for cat in (coordinator.device_category or [])
    )
    has_token = bool(coordinator.config_entry.data.get("auth_token"))
    if is_robot and has_token:
        # Lazy import to avoid a setup-time circular dependency with services.py.
        from .services import _fetch_persistent_map_metadata

        try:
            maps = await _fetch_persistent_map_metadata(coordinator)
        except Exception as err:  # noqa: BLE001 — never block setup over zone discovery
            _LOGGER.warning(
                "Could not fetch persistent map for %s; skipping zone buttons: %s",
                coordinator.serial_number,
                err,
            )
            maps = []

        # Most robots have a single persistent map; iterate to handle multi-map setups.
        seen_zone_ids: set[str] = set()
        for pmap in maps:
            for zone in pmap.zones:
                zone_id = zone.id
                if not zone_id or zone_id in seen_zone_ids:
                    continue
                seen_zone_ids.add(zone_id)
                entities.append(DysonZoneCleanButton(coordinator, pmap, zone))

        if seen_zone_ids:
            entities.append(DysonRefreshZonesButton(coordinator))
            _LOGGER.info(
                "Created %d per-zone clean buttons for %s",
                len(seen_zone_ids),
                coordinator.serial_number,
            )

    # Add Find+Follow scan button for devices that report the 'soon' state key.
    # Always visible (regardless of switch state) when the device supports F+F.
    ff_product_state: dict = {}
    if coordinator.data:
        raw_ps = coordinator.data.get("product-state", {})
        if isinstance(raw_ps, dict):
            ff_product_state = raw_ps
    if "soon" in ff_product_state:
        entities.append(DysonFindFollowScanButton(coordinator))

    async_add_entities(entities, True)


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

    One entity per zone in the persistent map. Tapping sends a START MQTT
    command with cleaningMode='zoneConfigured' targeting just that zone.
    """

    coordinator: DysonDataUpdateCoordinator

    def __init__(
        self,
        coordinator: DysonDataUpdateCoordinator,
        pmap: PersistentMapMeta,
        zone: ZoneMeta,
    ) -> None:
        super().__init__(coordinator)
        self._pmap_id: str = pmap.id
        self._zone_id: str = zone.id
        self._zone_name: str = str(zone.name or f"Zone {self._zone_id}")
        # unique_id uses zone_id (stable in MyDyson app even if user renames the zone)
        self._attr_unique_id = f"{coordinator.serial_number}_clean_zone_{self._zone_id}"
        self._attr_name = f"Clean {self._zone_name}"
        self._attr_icon = _icon_for_zone(zone.icon)

    async def async_press(self) -> None:
        if not self.coordinator.device:
            raise HomeAssistantError(
                f"Device {self.coordinator.serial_number} not available"
            )
        cleaning_programme = {
            "persistentMapId": self._pmap_id,
            "orderedZones": [],
            "unorderedZones": [self._zone_id],
        }
        _LOGGER.info(
            "Zone-clean button pressed: %s → zone %s (%s)",
            self.coordinator.serial_number,
            self._zone_id,
            self._zone_name,
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
    """Force re-fetch of the persistent map metadata from the Dyson cloud.

    Invalidates the in-process cache used by the start_zone_clean service and
    zone-clean buttons. To pick up newly added/renamed zones in the HA UI,
    restart Home Assistant after pressing this button (entities are only
    created at integration setup).
    """

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_refresh_zones"
        self._attr_name = "Refresh Zone List"
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        from .services import _fetch_persistent_map_metadata, _persistent_map_cache

        _persistent_map_cache.invalidate(self.coordinator.serial_number)
        try:
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


class DysonFindFollowScanButton(DysonEntity, ButtonEntity):
    """Button to trigger an immediate Find+Follow person scan.

    Sending ``soon=SCAN`` causes the device camera to immediately sweep for
    people.  The device automatically returns to Find+Follow ON state after
    the scan completes, even if Find+Follow was OFF before the scan.
    """

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the Find+Follow scan button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_find_follow_scan"
        self._attr_translation_key = "find_follow_scan"
        self._attr_icon = "mdi:radar"

    async def async_press(self) -> None:
        """Trigger an immediate Find+Follow person scan."""
        if not self.coordinator.device:
            _LOGGER.warning(
                "Device not available for Find+Follow scan on %s",
                self.coordinator.serial_number,
            )
            return
        try:
            await self.coordinator.device.set_find_follow("SCAN")
            _LOGGER.debug(
                "Triggered Find+Follow scan for %s",
                self.coordinator.serial_number,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error triggering Find+Follow scan for %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error triggering Find+Follow scan for %s: %s",
                self.coordinator.serial_number,
                err,
            )
