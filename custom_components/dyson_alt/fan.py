"""Fan platform for Dyson Alternative integration."""

from __future__ import annotations

import logging
from typing import Any, Optional

import voluptuous as vol
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity

_LOGGER = logging.getLogger(__name__)

# Service constants
ATTR_ANGLE_LOW = "angle_low"
ATTR_ANGLE_HIGH = "angle_high"

SERVICE_SET_ANGLE = "set_angle"

SET_ANGLE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ANGLE_LOW): cv.positive_int,
        vol.Required(ATTR_ANGLE_HIGH): cv.positive_int,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dyson fan platform."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Only add fan entity for devices that support it
    if "ec" in coordinator.device_category:  # Environment Cleaner
        entities.append(DysonFan(coordinator))

    async_add_entities(entities, True)

    # Register services for oscillation angle control
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_ANGLE,
        SET_ANGLE_SCHEMA,
        "async_set_angle",
    )


class DysonFan(DysonEntity, FanEntity):
    """Representation of a Dyson fan."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the fan."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_fan"
        self._attr_name = f"{coordinator.device_name}"
        self._attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.DIRECTION
        self._attr_speed_count = 10  # Dyson supports 10 speed levels
        self._attr_percentage_step = 10  # Step size of 10%

        # Note: Oscillation control removed - will be handled by custom advanced oscillation entities
        # Standard Home Assistant oscillation (on/off) doesn't support Dyson's advanced oscillation features

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            return

        # Debug logging
        fan_power = self.coordinator.device.fan_power
        fan_state = self.coordinator.device.fan_state
        fan_speed_setting = self.coordinator.device.fan_speed_setting

        _LOGGER.debug(
            "Fan %s update - fan_power: %s, fan_state: %s, fan_speed_setting: %s",
            self.coordinator.serial_number,
            fan_power,
            fan_state,
            fan_speed_setting,
        )

        # Update fan state based on fan power (fpwr) only
        # Fan should show as "on" whenever fan power is ON, regardless of fan state
        self._attr_is_on = fan_power

        # Update speed percentage based on fan speed setting (fnsp)
        if fan_speed_setting == "AUTO":
            # In auto mode, use the actual fan speed (nmdv) for display
            actual_speed = self.coordinator.device.fan_speed
            self._attr_percentage = min(100, max(0, actual_speed * 10))
        else:
            try:
                # Convert fnsp (0001-0010) to percentage (10-100%)
                speed_int = int(fan_speed_setting)
                self._attr_percentage = min(100, max(0, speed_int * 10))
            except (ValueError, TypeError):
                self._attr_percentage = 0

        # For now, we'll use forward direction (can be enhanced later)
        self._attr_current_direction = "forward"

        # Oscillation not available in our current data, set to False
        self._attr_oscillating = False

        _LOGGER.debug(
            "Fan %s final state - is_on: %s, percentage: %s",
            self.coordinator.serial_number,
            self._attr_is_on,
            self._attr_percentage,
        )

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

        # Turn on fan power
        await self.coordinator.device.set_fan_power(True)

        # Set fan speed if specified
        if percentage is not None:
            # Convert percentage to Dyson speed (1-10) with proper rounding
            speed = max(1, min(10, round(percentage / 10)))
            if speed == 0:  # Ensure we don't set speed to 0 when turning on
                speed = 1
            await self.coordinator.device.set_fan_speed(speed)

        # No need to refresh - MQTT provides real-time updates

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        if not self.coordinator.device:
            return

        # Turn off fan power
        await self.coordinator.device.set_fan_power(False)

        # No need to refresh - MQTT provides real-time updates

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed percentage."""
        if not self.coordinator.device:
            return

        if percentage == 0:
            # Turn off fan when percentage is 0
            await self.async_turn_off()
        else:
            # Convert percentage to Dyson speed (1-10) with proper rounding
            speed = max(1, min(10, round(percentage / 10)))
            await self.coordinator.device.set_fan_speed(speed)

            # No need to refresh - MQTT provides real-time updates

    async def async_set_direction(self, direction: str) -> None:
        """Set the fan direction."""
        if not self.coordinator.device:
            return

        # Map Home Assistant direction to Dyson direction values
        direction_value = "ON" if direction == "reverse" else "OFF"  # Adjust based on actual Dyson values

        try:
            # Use device method directly instead of coordinator
            await self.coordinator.device.send_command("STATE-SET", {"fdir": direction_value})
            _LOGGER.debug("Set fan direction to %s for %s", direction, self.coordinator.serial_number)

            # No need to refresh - MQTT provides real-time updates
        except Exception as err:
            _LOGGER.error("Failed to set fan direction for %s: %s", self.coordinator.serial_number, err)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return fan-specific state attributes including oscillation angles."""
        attributes = {}

        if self.coordinator.device:
            product_state = self.coordinator.data.get("product-state", {})

            # Add oscillation angle information
            lower_data = self.coordinator.device._get_current_value(product_state, "osal", "0000")
            upper_data = self.coordinator.device._get_current_value(product_state, "osau", "0350")

            try:
                lower_angle = int(lower_data.lstrip("0") or "0")
                upper_angle = int(upper_data.lstrip("0") or "350")

                attributes[ATTR_ANGLE_LOW] = lower_angle
                attributes[ATTR_ANGLE_HIGH] = upper_angle
            except (ValueError, TypeError):
                pass

        return attributes if attributes else None

    async def async_set_angle(self, angle_low: int, angle_high: int) -> None:
        """Set oscillation angle via service call."""
        if not self.coordinator.device:
            return

        try:
            _LOGGER.debug(
                "Setting oscillation angles via service - low: %s, high: %s for device %s",
                angle_low,
                angle_high,
                self.coordinator.serial_number,
            )
            await self.coordinator.device.set_oscillation_angles(angle_low, angle_high)
        except Exception as err:
            _LOGGER.error("Failed to set oscillation angles for %s: %s", self.coordinator.serial_number, err)
