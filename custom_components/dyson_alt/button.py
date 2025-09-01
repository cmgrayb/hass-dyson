"""Button platform for Dyson Alternative integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dyson button platform."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Basic buttons for all devices
    entities.extend(
        [
            DysonResetHEPAFilterButton(coordinator),
            DysonResetCarbonFilterButton(coordinator),
            DysonReconnectButton(coordinator),
        ]
    )

    async_add_entities(entities, True)


class DysonResetHEPAFilterButton(DysonEntity, ButtonEntity):
    """Button to reset HEPA filter life counter."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the reset HEPA filter button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_reset_hepa_filter"
        self._attr_name = "Reset HEPA Filter"
        self._attr_icon = "mdi:air-filter"

    async def async_press(self) -> None:
        """Handle the button press."""
        if not self.coordinator.device:
            _LOGGER.warning("Device not available for HEPA filter reset")
            return

        try:
            await self.coordinator.device.reset_hepa_filter_life()
            _LOGGER.info("HEPA filter reset command sent to %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to reset HEPA filter for %s: %s", self.coordinator.serial_number, err)


class DysonResetCarbonFilterButton(DysonEntity, ButtonEntity):
    """Button to reset carbon filter life counter."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the reset carbon filter button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_reset_carbon_filter"
        self._attr_name = "Reset Carbon Filter"
        self._attr_icon = "mdi:air-filter"

    async def async_press(self) -> None:
        """Handle the button press."""
        if not self.coordinator.device:
            _LOGGER.warning("Device not available for carbon filter reset")
            return

        try:
            await self.coordinator.device.reset_carbon_filter_life()
            _LOGGER.info("Carbon filter reset command sent to %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to reset carbon filter for %s: %s", self.coordinator.serial_number, err)


class DysonReconnectButton(DysonEntity, ButtonEntity):
    """Button to trigger intelligent reconnection to device."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the reconnect button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_reconnect"
        self._attr_name = "Reconnect"
        self._attr_icon = "mdi:wifi-sync"

    async def async_press(self) -> None:
        """Handle the button press to trigger intelligent reconnection."""
        if not self.coordinator.device:
            _LOGGER.warning("Device not available for reconnect")
            return

        try:
            _LOGGER.info("Manual reconnect triggered for %s", self.coordinator.serial_number)

            # Use the device's force_reconnect method for clean reconnection logic
            success = await self.coordinator.device.force_reconnect()

            if success:
                _LOGGER.info("Manual reconnection successful for %s", self.coordinator.serial_number)
                # Trigger a coordinator update to refresh all entities
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.warning("Manual reconnection failed for %s", self.coordinator.serial_number)

        except Exception as err:
            _LOGGER.error("Failed to manually reconnect %s: %s", self.coordinator.serial_number, err)
