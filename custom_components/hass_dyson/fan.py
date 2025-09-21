"""Fan platform for Dyson integration."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from typing import Any

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

    entities = []

    # Only add fan entity for devices that support it
    if "ec" in coordinator.device_category:  # Environment Cleaner
        entities.append(DysonFan(coordinator))

    async_add_entities(entities, True)


class DysonFan(DysonEntity, FanEntity):
    """Representation of a Dyson fan."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the fan."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_fan"
        self._attr_name = f"{coordinator.device_name}"
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.DIRECTION
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        self._attr_speed_count = 10  # Dyson supports 10 speed levels
        self._attr_percentage_step = 10  # Step size of 10%

        # Set up preset modes - Auto and Manual for all device types
        self._attr_preset_modes = ["Auto", "Manual"]

        # Initialize state attributes to ensure clean state
        self._attr_is_on = None  # Will be set properly in first coordinator update
        self._attr_percentage = 0
        self._attr_current_direction = "forward"
        self._attr_preset_mode = None
        self._attr_oscillating = False

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

        # Update preset mode based on auto mode state
        if self.coordinator.device and self.coordinator.data:
            product_state = self.coordinator.data.get("product-state", {})
            auto_mode = self.coordinator.device._get_current_value(
                product_state, "auto", "OFF"
            )
            self._attr_preset_mode = "Auto" if auto_mode == "ON" else "Manual"
        else:
            self._attr_preset_mode = None

        # Oscillation not available in our current data, set to False
        self._attr_oscillating = False

        _LOGGER.debug(
            "Fan %s final state - is_on: %s, percentage: %s",
            self.coordinator.serial_number,
            self._attr_is_on,
            self._attr_percentage,
        )

        # Force Home Assistant to update with the new state
        _LOGGER.debug(
            "Fan %s writing state to Home Assistant - is_on: %s",
            self.coordinator.serial_number,
            self._attr_is_on,
        )
        self.async_write_ha_state()

        # Additional debugging - check what HA thinks our state is after writing
        _LOGGER.debug(
            "Fan %s after state write - entity_id: %s, state: %s, is_on property: %s",
            self.coordinator.serial_number,
            self.entity_id,
            self.state,
            self.is_on,
        )

        super()._handle_coordinator_update()

    @property
    def is_on(self) -> bool:
        """Return True if the fan is on."""
        return self._attr_is_on if self._attr_is_on is not None else False

    def _start_command_pending(self, duration_seconds: float = 7.0) -> None:
        """Start ignoring coordinator updates for a specified duration."""
        self._command_pending = True
        self._command_end_time = time.time() + duration_seconds
        _LOGGER.debug(
            "Fan %s started command pending period for %.1f seconds",
            self.coordinator.serial_number,
            duration_seconds,
        )

    def _stop_command_pending(self) -> None:
        """Stop ignoring coordinator updates immediately."""
        self._command_pending = False
        self._command_end_time = None
        _LOGGER.debug(
            "Fan %s stopped command pending period", self.coordinator.serial_number
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if not self.coordinator.device:
            return

        # Turn on fan power
        await self.coordinator.device.set_fan_power(True)

        # Update state immediately for responsive UI
        self._attr_is_on = True
        self.async_write_ha_state()

        # Set fan speed if specified
        if percentage is not None:
            # Convert percentage to Dyson speed (1-10) with proper rounding
            speed = max(1, min(10, round(percentage / 10)))
            if speed == 0:  # Ensure we don't set speed to 0 when turning on
                speed = 1
            await self.coordinator.device.set_fan_speed(speed)

        # Set preset mode if specified
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)

        # Let the coordinator update naturally from MQTT messages
        # No forced refresh or immediate state writing to prevent race conditions

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        if not self.coordinator.device:
            return

        # Turn off fan power
        await self.coordinator.device.set_fan_power(False)

        # Update state immediately for responsive UI
        self._attr_is_on = False
        self.async_write_ha_state()

        # Let the coordinator update naturally from MQTT messages for final state

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

            # Let the coordinator update naturally from MQTT messages for final state

    async def async_set_direction(self, direction: str) -> None:
        """Set the fan direction."""
        if not self.coordinator.device:
            return

        # Map Home Assistant direction to Dyson direction values
        direction_value = (
            "ON" if direction == "reverse" else "OFF"
        )  # Adjust based on actual Dyson values

        try:
            # Use device method directly instead of coordinator
            await self.coordinator.device.send_command(
                "STATE-SET", {"fdir": direction_value}
            )
            _LOGGER.debug(
                "Set fan direction to %s for %s",
                direction,
                self.coordinator.serial_number,
            )

            # Force coordinator refresh to update state immediately
            await asyncio.sleep(0.5)  # Give device time to process
            await self.coordinator.async_request_refresh()

            # Force Home Assistant to update with confirmed device state
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error(
                "Failed to set fan direction for %s: %s",
                self.coordinator.serial_number,
                err,
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the fan preset mode."""
        if not self.coordinator.device:
            return

        try:
            if preset_mode == "Auto":
                await self.coordinator.device.set_auto_mode(True)
            elif preset_mode == "Manual":
                await self.coordinator.device.set_auto_mode(False)
            else:
                _LOGGER.warning("Unknown preset mode: %s", preset_mode)
                return

            _LOGGER.debug(
                "Set fan preset mode to %s for %s",
                preset_mode,
                self.coordinator.serial_number,
            )

            # Update state immediately to provide responsive UI
            self._attr_preset_mode = preset_mode
            self.async_write_ha_state()

            # Force coordinator refresh to update state immediately
            await asyncio.sleep(0.5)  # Give device time to process
            await self.coordinator.async_request_refresh()

            # Force Home Assistant to update with confirmed device state
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error(
                "Failed to set fan preset mode for %s: %s",
                self.coordinator.serial_number,
                err,
            )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:  # type: ignore[return]
        """Return fan-specific state attributes for scene support."""
        attributes = {}

        if self.coordinator.device:
            product_state = self.coordinator.data.get("product-state", {})

            # Core fan properties for scene support
            percentage: int | None = self._attr_percentage
            preset_mode: str | None = self._attr_preset_mode
            current_direction: str | None = self._attr_current_direction
            is_on: bool | None = self._attr_is_on

            attributes["fan_speed"] = percentage  # type: ignore[assignment]
            attributes["preset_mode"] = preset_mode  # type: ignore[assignment]
            attributes["direction"] = current_direction  # type: ignore[assignment]
            attributes["is_on"] = is_on  # type: ignore[assignment]

            # Device state properties
            fan_power = self.coordinator.device._get_current_value(
                product_state, "fpwr", "OFF"
            )
            fan_state = self.coordinator.device._get_current_value(
                product_state, "fnst", "OFF"
            )
            fan_speed_setting = self.coordinator.device._get_current_value(
                product_state, "fnsp", "0001"
            )
            auto_mode = self.coordinator.device._get_current_value(
                product_state, "auto", "OFF"
            )
            night_mode = self.coordinator.device._get_current_value(
                product_state, "nmod", "OFF"
            )

            attributes["fan_power"] = fan_power == "ON"
            attributes["fan_state"] = fan_state  # type: ignore[assignment]
            attributes["fan_speed_setting"] = fan_speed_setting  # type: ignore[assignment]
            attributes["auto_mode"] = auto_mode == "ON"
            attributes["night_mode"] = night_mode == "ON"

            # Oscillation information
            oson = self.coordinator.device._get_current_value(
                product_state, "oson", "OFF"
            )
            attributes["oscillation_enabled"] = oson == "ON"

            lower_data = self.coordinator.device._get_current_value(
                product_state, "osal", "0000"
            )
            upper_data = self.coordinator.device._get_current_value(
                product_state, "osau", "0350"
            )

            try:
                lower_angle = int(lower_data.lstrip("0") or "0")
                upper_angle = int(upper_data.lstrip("0") or "350")

                attributes["angle_low"] = lower_angle
                attributes["angle_high"] = upper_angle
                attributes["oscillation_span"] = upper_angle - lower_angle
            except (ValueError, TypeError):
                pass

            # Sleep timer if available
            try:
                sltm = self.coordinator.device._get_current_value(
                    product_state, "sltm", "OFF"
                )
                if sltm != "OFF":
                    attributes["sleep_timer"] = int(sltm)
                else:
                    attributes["sleep_timer"] = 0
            except (ValueError, TypeError):
                attributes["sleep_timer"] = 0

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
            _LOGGER.error(
                "Failed to set oscillation angles for %s: %s",
                self.coordinator.serial_number,
                err,
            )
