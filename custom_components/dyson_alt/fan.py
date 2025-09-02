"""Fan platform for Dyson Alternative integration."""

from __future__ import annotations

import logging
from typing import Any, Optional

from homeassistant.components.fan import FanEntity, FanEntityFeature
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
    """Set up Dyson fan platform."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Only add fan entity for devices that support it
    if "ec" in coordinator.device_category:  # Environment Cleaner
        async_add_entities([DysonFan(coordinator)], True)


class DysonFan(DysonEntity, FanEntity):
    """Representation of a Dyson fan."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the fan."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_fan"
        self._attr_name = "Fan"
        self._attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.DIRECTION

        # Note: Oscillation control removed - will be handled by custom advanced oscillation entities
        # Standard Home Assistant oscillation (on/off) doesn't support Dyson's advanced oscillation features

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            return

        # Update fan state based on night mode (nmod) - this is what controls the fan
        self._attr_is_on = self.coordinator.device.night_mode

        # Update speed percentage based on fan speed (nmdv)
        fan_speed = self.coordinator.device.fan_speed
        if fan_speed > 0:
            # Convert Dyson speed (0-10) to percentage (0-100)
            self._attr_percentage = min(100, max(0, fan_speed * 10))
        else:
            self._attr_percentage = 0

        # For now, we'll use forward direction (can be enhanced later)
        self._attr_current_direction = "forward"

        # Oscillation not available in our current data, set to False
        self._attr_oscillating = False

        super()._handle_coordinator_update()

    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if not self.coordinator.device:
            return

        # Turn on night mode (this controls the fan)
        await self.coordinator.device.set_night_mode(True)

        # Set fan speed if specified
        if percentage is not None:
            # Convert percentage to Dyson speed (0-10)
            speed = max(1, min(10, int(percentage / 10)))
            await self.coordinator.device.set_fan_speed(speed)

        # Trigger coordinator update
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        if not self.coordinator.device:
            return

        # Turn off night mode (this stops the fan)
        await self.coordinator.device.set_night_mode(False)

        # Trigger coordinator update
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed percentage."""
        if not self.coordinator.device:
            return

        # Convert percentage to Dyson speed (0-10)
        speed = max(0, min(10, int(percentage / 10)))
        await self.coordinator.device.set_fan_speed(speed)

        # Trigger coordinator update
        await self.coordinator.async_request_refresh()

    async def async_set_direction(self, direction: str) -> None:
        """Set the fan direction."""
        success = await self.coordinator.async_send_command("direction", {"direction": direction})
        if not success:
            _LOGGER.error("Failed to set fan direction")
