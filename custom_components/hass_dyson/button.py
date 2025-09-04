"""Button platform for Dyson integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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

    # Add reconnect button (safe utility button)
    entities.append(DysonReconnectButton(coordinator))

    # Filter reset buttons removed - users can use services/actions instead
    # This prevents accidental filter life resets by inexperienced users

    async_add_entities(entities, True)


class DysonReconnectButton(DysonEntity, ButtonEntity):
    """Button to trigger intelligent reconnection to device."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the reconnect button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_reconnect"
        self._attr_name = f"{coordinator.device_name} Reconnect"
        self._attr_icon = "mdi:wifi-sync"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

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
