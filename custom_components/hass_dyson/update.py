"""Update platform for Dyson devices."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity, UpdateEntityFeature
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DISCOVERY_METHOD, DISCOVERY_CLOUD, DOMAIN
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dyson update entities."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Only add update entity for cloud-discovered devices
    if config_entry.data.get(CONF_DISCOVERY_METHOD) == DISCOVERY_CLOUD:
        entities = [DysonFirmwareUpdateEntity(coordinator)]
        async_add_entities(entities)
        _LOGGER.debug("Added firmware update entity for cloud device %s", coordinator.serial_number)
    else:
        _LOGGER.debug("Skipped firmware update entity for non-cloud device %s", coordinator.serial_number)


class DysonFirmwareUpdateEntity(DysonEntity, UpdateEntity):
    """Update entity for Dyson firmware updates."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the firmware update entity."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_firmware_update"
        self._attr_name = f"{coordinator.device_name} Firmware Update"
        self._attr_icon = "mdi:cellphone-arrow-down"

    @property
    def installed_version(self) -> str | None:
        """Return the currently installed firmware version."""
        return self.coordinator.firmware_version if self.coordinator.firmware_version != "Unknown" else None

    @property
    def latest_version(self) -> str | None:
        """Return the latest available firmware version."""
        return self.coordinator.firmware_latest_version

    @property
    def in_progress(self) -> bool | None:
        """Return True if firmware update is in progress."""
        return self.coordinator.firmware_update_in_progress

    @property
    def auto_update(self) -> bool:
        """Return True if auto-update is enabled."""
        return self.coordinator.firmware_auto_update_enabled

    @property
    def title(self) -> str:
        """Return the title of the software."""
        return "Dyson Device Firmware"

    @property
    def release_summary(self) -> str | None:
        """Return a summary of the release."""
        current = self.installed_version
        latest = self.latest_version
        if latest and current and latest != current:
            return f"Firmware update from {current} to {latest}"
        return None

    async def async_install(self, version: str | None = None, backup: bool = False, **kwargs: Any) -> None:
        """Install firmware update."""
        if not self.coordinator.device:
            _LOGGER.error("No device available for firmware update")
            return

        try:
            # Use the latest version if no specific version requested
            target_version = version or self.latest_version
            if not target_version:
                _LOGGER.error("No firmware version available for installation")
                return

            _LOGGER.info(
                "Starting firmware update for %s to version %s", self.coordinator.serial_number, target_version
            )  # Trigger the firmware update via coordinator
            success = await self.coordinator.async_install_firmware_update(target_version)

            if success:
                _LOGGER.info("Firmware update initiated successfully for %s", self.coordinator.serial_number)
            else:
                _LOGGER.error("Failed to initiate firmware update for %s", self.coordinator.serial_number)

        except Exception as err:
            _LOGGER.error("Error installing firmware update for %s: %s", self.coordinator.serial_number, err)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "Firmware update entity updated for %s: current=%s, latest=%s, in_progress=%s",
            self.coordinator.serial_number,
            self.installed_version,
            self.latest_version,
            self.in_progress,
        )
        super()._handle_coordinator_update()
