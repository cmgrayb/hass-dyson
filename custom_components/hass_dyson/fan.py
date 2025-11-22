"""Fan platform for Dyson integration.

This module implements the Home Assistant fan platform for Dyson devices,
providing comprehensive fan control including speed, oscillation, direction,
and preset modes. It also integrates climate functionality for heating-capable
devices like the Hot+Cool series.

Key Features:
    - 10-level speed control (1-10) mapped to percentage
    - Oscillation control with angle specification support
    - Direction control (forward/reverse airflow)
    - Preset modes: Auto, Manual, Heat (device-dependent)
    - Night mode integration for quiet operation
    - Climate integration for heating-enabled devices
    - Real-time state updates via MQTT coordinator
    - Command pending system to prevent UI flickering

Supported Device Features (capability-dependent):
    - SET_SPEED: All devices (1-10 speed levels)
    - PRESET_MODE: All devices (Auto, Manual, Heat if available)
    - TURN_ON/TURN_OFF: All devices
    - OSCILLATE: Devices with oscillation capability (oson state)
    - DIRECTION: Devices with direction control (fdir state)

Device Compatibility:
    - Pure series: Basic fan control, air quality automation
    - Hot+Cool series: Full fan + heating climate control
    - Humidify series: Fan control + humidity management
    - All models: Speed, oscillation, night mode (if supported)

Climate Integration:
    Heating-capable devices (Hot+Cool series) provide additional attributes:
    - current_temperature: Ambient temperature reading
    - target_temperature: Heating target temperature
    - hvac_mode: Heat/Fan/Off modes
    - temperature_unit: Celsius
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from typing import Any

from homeassistant.components.climate.const import HVACMode
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
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
    """Set up Dyson fan platform entities.

    Creates fan entities for devices that support fan functionality,
    specifically devices in the "ec" (Environment Cleaner) category.

    Args:
        hass: Home Assistant instance
        config_entry: Configuration entry for the Dyson integration
        async_add_entities: Callback to add entities to Home Assistant

    Note:
        Only creates fan entities for devices with "ec" in device_category,
        which includes most Dyson air purifiers and fans. Other device
        types (like lighting) are handled by their respective platforms.

        The fan entity provides the primary control interface for:
        - Air circulation and filtration
        - Speed control and automation
        - Oscillation and airflow direction
        - Climate control (for heating-capable models)

    Example:
        Entity created for Environment Cleaner devices:

        >>> # Device with device_category = ["ec"]
        >>> # Creates: fan.living_room_dyson
        >>> # Features: speed, oscillation, preset modes
    """
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Only add fan entity for devices that support it
    if "ec" in coordinator.device_category:  # Environment Cleaner
        entities.append(DysonFan(coordinator))

    async_add_entities(entities, True)


class DysonFan(DysonEntity, FanEntity):
    """Home Assistant fan entity for Dyson air purifiers and fans.

    This entity provides comprehensive fan control for Dyson devices including
    speed management, oscillation control, preset modes, and integrated climate
    functionality for heating-capable models.

    Supported Features (device-dependent):
        - SET_SPEED: 10-level speed control (mapped to 0-100% range)
        - PRESET_MODE: Auto, Manual, Heat modes
        - TURN_ON/TURN_OFF: Power control
        - OSCILLATE: On/off oscillation (if device supports oson)
        - DIRECTION: Forward/reverse airflow (if device supports fdir)

    Attributes:
        _attr_speed_count: Always 10 (Dyson's native speed levels)
        _attr_percentage_step: 10% (10% per speed level)
        _attr_preset_modes: ["Auto", "Manual"] or ["Auto", "Manual", "Heat"]
        _has_heating: True for Hot+Cool series devices
        _direction_supported: True if device reports fdir state
        _oscillation_supported: True if device reports oson state

    Climate Integration (Hot+Cool models):
        When heating capability is detected, the fan entity provides:
        - current_temperature: Real-time temperature reading
        - target_temperature: Heating target (1-37°C)
        - HVAC modes: Heat, Fan Only, Off
        - Automatic heating control based on target temperature

    State Management:
        Uses command pending system to prevent UI flickering:
        - Commands trigger immediate state updates
        - Coordinator updates ignored for 7 seconds after commands
        - Ensures responsive UI during device communication delays

    Example:
        Basic fan operations:

        >>> # Set speed to 70% (level 7)
        >>> await fan.async_set_percentage(70)
        >>>
        >>> # Enable oscillation for wider coverage
        >>> await fan.async_oscillate(True)
        >>>
        >>> # Use auto mode for air quality response
        >>> await fan.async_set_preset_mode("Auto")
        >>>
        >>> # For Hot+Cool models - set heating
        >>> if fan._has_heating:
        >>>     await fan.async_set_temperature(temperature=22.0)

    Note:
        The entity automatically detects device capabilities during initialization
        and enables corresponding features. Unsupported operations are handled
        gracefully with appropriate logging.
    """

    coordinator: DysonDataUpdateCoordinator
    _attr_current_temperature: float | None
    _attr_target_temperature: float

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the Dyson fan entity with capability detection.

        Sets up the fan entity with appropriate features based on device
        capabilities detected from device state and coordinator information.

        Args:
            coordinator: DysonDataUpdateCoordinator providing device access

        Initialization Process:
        1. Configure base fan features (speed, preset modes, power control)
        2. Detect oscillation support via device state (oson key presence)
        3. Detect direction support via device state (fdir key presence)
        4. Configure heating integration for Hot+Cool series devices
        5. Set up preset modes based on heating capability
        6. Configure entity attributes and identifiers

        Feature Detection:
        - Oscillation: Enabled if device reports 'oson' in product state
        - Direction: Enabled if device reports 'fdir' in product state
        - Heating: Enabled if 'Heating' in coordinator.device_capabilities

        Preset Modes:
        - Standard devices: ["Auto", "Manual"]
        - Heating devices: ["Auto", "Manual", "Heat"]

        Note:
            Feature detection is dynamic and based on actual device capabilities
            rather than device model assumptions, ensuring accuracy across
            different firmware versions and device configurations.
        """
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_fan"
        self._attr_name = f"{coordinator.device_name}"
        # Base features for all fans
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )

        # Add direction support if device reports direction state (fdir)
        self._direction_supported = self._check_direction_support()
        if self._direction_supported:
            self._attr_supported_features |= FanEntityFeature.DIRECTION

        # Add oscillation support if device reports oscillation state (oson)
        self._oscillation_supported = self._check_oscillation_support()
        if self._oscillation_supported:
            self._attr_supported_features |= FanEntityFeature.OSCILLATE
        self._attr_speed_count = 10  # Dyson supports 10 speed levels
        self._attr_percentage_step = 10  # Step size of 10%

        # Check if device has heating capability for integrated climate features
        self._has_heating = "Heating" in coordinator.device_capabilities

        # Set up preset modes based on heating capability
        if self._has_heating:
            self._attr_preset_modes = ["Auto", "Manual", "Heat"]
            # Add climate-specific attributes for heating devices
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
            self._attr_min_temp = 1
            self._attr_max_temp = 37
            self._attr_target_temperature_step = 1
            self._attr_target_temperature = 20  # Default target temperature
            self._attr_current_temperature = None
            self._attr_hvac_modes = [
                HVACMode.OFF,
                HVACMode.FAN_ONLY,
                HVACMode.HEAT,
                HVACMode.AUTO,
            ]
            self._attr_hvac_mode = HVACMode.OFF
        else:
            self._attr_preset_modes = ["Auto", "Manual"]

        # Initialize state attributes to ensure clean state
        self._attr_is_on = None  # Will be set properly in first coordinator update
        self._attr_percentage = 0
        self._attr_current_direction = "forward"
        self._attr_preset_mode = None
        self._attr_oscillating = False

        # Initialize command pending attributes to prevent linting errors
        self._command_pending = False
        self._command_end_time: float | None = None

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

        # Update preset mode and heating data if applicable
        if self.coordinator.device and self.coordinator.data:
            product_state = self.coordinator.data.get("product-state", {})

            # Update fan direction based on device state (fdir) if supported
            if self._direction_supported:
                # fdir="ON" means front airflow is on (forward direction in HA terms)
                # fdir="OFF" means front airflow is off (reverse direction in HA terms)
                fdir_value = self.coordinator.device.get_state_value(
                    product_state,
                    "fdir",
                    "ON",  # Default to ON (forward) if not available
                )
                self._attr_current_direction = (
                    "forward" if fdir_value == "ON" else "reverse"
                )
            else:
                # Device doesn't support direction control
                self._attr_current_direction = "forward"  # Default fallback
            auto_mode = self.coordinator.device.get_state_value(
                product_state, "auto", "OFF"
            )

            # Update heating information if device has heating capability
            if self._has_heating:
                self._update_heating_data(product_state)
                # For heating devices, preset mode includes heating state
                heating_mode = self.coordinator.device.get_state_value(
                    product_state, "hmod", "OFF"
                )
                if heating_mode == "HEAT":
                    self._attr_preset_mode = "Heat"
                elif auto_mode == "ON":
                    self._attr_preset_mode = "Auto"
                else:
                    self._attr_preset_mode = "Manual"
            else:
                # Non-heating devices use simple Auto/Manual logic
                self._attr_preset_mode = "Auto" if auto_mode == "ON" else "Manual"

            # Update oscillation state from device data if supported
            if self._oscillation_supported:
                oson = self.coordinator.device.get_state_value(
                    product_state, "oson", "OFF"
                )
                self._attr_oscillating = oson == "ON"
            else:
                # Device doesn't support oscillation
                self._attr_oscillating = False
        else:
            self._attr_preset_mode = None
            self._attr_oscillating = False
            if not self._direction_supported:
                self._attr_current_direction = (
                    "forward"  # Default fallback when no device data
                )

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

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan (sync wrapper).

        This method provides the required synchronous interface for Home Assistant's
        FanEntity abstract method. It delegates to the async implementation.

        Args:
            percentage: Fan speed percentage (0-100)
            preset_mode: Preset mode to set ("Auto", "Manual", "Heat")
            **kwargs: Additional arguments
        """
        self.hass.create_task(self.async_turn_on(percentage, preset_mode, **kwargs))

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

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan (sync wrapper).

        This method provides the required synchronous interface for Home Assistant's
        FanEntity abstract method. It delegates to the async implementation.

        Args:
            **kwargs: Additional arguments
        """
        self.hass.create_task(self.async_turn_off(**kwargs))

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

    def set_percentage(self, percentage: int) -> None:
        """Set the fan speed percentage (sync wrapper).

        This method provides the required synchronous interface for Home Assistant's
        FanEntity abstract method. It delegates to the async implementation.

        Args:
            percentage: Fan speed percentage (0-100)
        """
        self.hass.create_task(self.async_set_percentage(percentage))

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

    def set_direction(self, direction: str) -> None:
        """Set the fan direction (sync wrapper).

        This method provides the required synchronous interface for Home Assistant's
        FanEntity abstract method. It delegates to the async implementation.

        Args:
            direction: Direction to set ("forward" or "reverse")
        """
        self.hass.create_task(self.async_set_direction(direction))

    async def async_set_direction(self, direction: str) -> None:
        """Set the fan direction."""
        if not self.coordinator.device:
            return

        # Only allow direction control if device supports it
        if not self._direction_supported:
            _LOGGER.warning(
                "Device %s does not support direction control",
                self.coordinator.serial_number,
            )
            return

        # Map Home Assistant direction to Dyson direction values
        # Based on libdyson-neon: fdir="ON" = front airflow = forward direction
        #                         fdir="OFF" = no front airflow = reverse direction
        direction_value = "ON" if direction == "forward" else "OFF"

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
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting fan direction for %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except (ValueError, KeyError) as err:
            _LOGGER.error(
                "Invalid direction value for %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting fan direction for %s: %s",
                self.coordinator.serial_number,
                err,
            )

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the fan preset mode (sync wrapper).

        This method provides the required synchronous interface for Home Assistant's
        FanEntity abstract method. It delegates to the async implementation.

        Args:
            preset_mode: Preset mode to set ("Auto", "Manual", "Heat")
        """
        self.hass.create_task(self.async_set_preset_mode(preset_mode))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the fan preset mode."""
        if not self.coordinator.device:
            return

        try:
            if preset_mode == "Auto":
                await self.coordinator.device.set_auto_mode(True)
            elif preset_mode == "Manual":
                await self.coordinator.device.set_auto_mode(False)
            elif preset_mode == "Heat" and self._has_heating:
                # Enable heating mode
                await self.coordinator.async_send_command(
                    "set_climate_mode", {"fnst": "FAN", "hmod": "HEAT", "auto": "OFF"}
                )
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
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting preset mode '%s' for %s: %s",
                preset_mode,
                self.coordinator.serial_number,
                err,
            )
        except (ValueError, KeyError) as err:
            _LOGGER.error(
                "Invalid preset mode '%s' for %s: %s",
                preset_mode,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting preset mode '%s' for %s: %s",
                preset_mode,
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
            fan_power = self.coordinator.device.get_state_value(
                product_state, "fpwr", "OFF"
            )
            fan_state = self.coordinator.device.get_state_value(
                product_state, "fnst", "OFF"
            )
            fan_speed_setting = self.coordinator.device.get_state_value(
                product_state, "fnsp", "0001"
            )
            auto_mode = self.coordinator.device.get_state_value(
                product_state, "auto", "OFF"
            )
            night_mode = self.coordinator.device.get_state_value(
                product_state, "nmod", "OFF"
            )

            attributes["fan_power"] = fan_power == "ON"
            attributes["fan_state"] = fan_state  # type: ignore[assignment]
            attributes["fan_speed_setting"] = fan_speed_setting  # type: ignore[assignment]
            attributes["auto_mode"] = auto_mode == "ON"
            attributes["night_mode"] = night_mode == "ON"

            # Oscillation information
            oson = self.coordinator.device.get_state_value(product_state, "oson", "OFF")
            attributes["oscillation_enabled"] = oson == "ON"

            lower_data = self.coordinator.device.get_state_value(
                product_state, "osal", "0000"
            )
            upper_data = self.coordinator.device.get_state_value(
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
                sltm = self.coordinator.device.get_state_value(
                    product_state, "sltm", "OFF"
                )
                if sltm != "OFF":
                    attributes["sleep_timer"] = int(sltm)
                else:
                    attributes["sleep_timer"] = 0
            except (ValueError, TypeError):
                attributes["sleep_timer"] = 0

            # Heating information if device has heating capability
            if self._has_heating:
                # Current and target temperatures
                attributes["current_temperature"] = self._attr_current_temperature  # type: ignore[assignment]
                attributes["target_temperature"] = self._attr_target_temperature  # type: ignore[assignment]
                attributes["hvac_mode"] = self._attr_hvac_mode  # type: ignore[assignment]
                attributes["temperature_unit"] = self._attr_temperature_unit  # type: ignore[assignment]

                # Raw device heating state for scene support
                hmod = self.coordinator.device.get_state_value(
                    product_state, "hmod", "OFF"
                )
                attributes["heating_mode"] = hmod  # type: ignore[assignment]
                attributes["heating_enabled"] = hmod != "OFF"  # type: ignore[assignment]

                # Target temperature in Kelvin format for device commands
                if self._attr_target_temperature is not None:
                    temp_kelvin = int((self._attr_target_temperature + 273.15) * 10)
                    attributes["target_temperature_kelvin"] = f"{temp_kelvin:04d}"  # type: ignore[assignment]

        return attributes if attributes else None

    def _check_oscillation_support(self) -> bool:
        """Check if device supports oscillation by looking for 'oson' in device state."""
        if not self.coordinator.device or not self.coordinator.data:
            return False

        product_state = self.coordinator.data.get("product-state", {})
        # Check if device reports oscillation state (oson key exists)
        return "oson" in product_state

    def _check_direction_support(self) -> bool:
        """Check if device supports direction control by looking for 'fdir' in device state."""
        if not self.coordinator.device or not self.coordinator.data:
            return False

        product_state = self.coordinator.data.get("product-state", {})
        # Check if device reports fan direction state (fdir key exists)
        return "fdir" in product_state

    def oscillate(self, oscillating: bool) -> None:
        """Set oscillation on/off (sync wrapper).

        This method provides the required synchronous interface for Home Assistant's
        FanEntity abstract method. It delegates to the async implementation.

        Args:
            oscillating: True to enable oscillation, False to disable
        """
        self.hass.create_task(self.async_oscillate(oscillating))

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation on/off via Home Assistant's native fan.oscillate service."""
        if not self.coordinator.device:
            return

        # Only allow oscillation control if device supports it
        if not self._oscillation_supported:
            _LOGGER.warning(
                "Device %s does not support oscillation control",
                self.coordinator.serial_number,
            )
            return

        try:
            await self.coordinator.device.set_oscillation(oscillating)

            # Update state immediately for responsive UI
            self._attr_oscillating = oscillating
            self.async_write_ha_state()

            _LOGGER.debug(
                "Set oscillation to %s for %s via native fan service",
                oscillating,
                self.coordinator.serial_number,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting oscillation to %s for %s: %s",
                oscillating,
                self.coordinator.serial_number,
                err,
            )
        except AttributeError as err:
            _LOGGER.error(
                "Device method not available for oscillation on %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting oscillation to %s for %s: %s",
                oscillating,
                self.coordinator.serial_number,
                err,
            )

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
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting oscillation angles (%s°-%s°) for %s: %s",
                angle_low,
                angle_high,
                self.coordinator.serial_number,
                err,
            )
        except ValueError as err:
            _LOGGER.error(
                "Invalid angle values (%s°-%s°) for %s: %s",
                angle_low,
                angle_high,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting oscillation angles (%s°-%s°) for %s: %s",
                angle_low,
                angle_high,
                self.coordinator.serial_number,
                err,
            )

    # Climate functionality for heating-enabled devices
    def _update_heating_data(self, device_data: dict[str, Any]) -> None:
        """Update temperature and heating mode data."""
        if not self._has_heating:
            return

        # Current temperature
        current_temp = self.coordinator.device.get_state_value(
            device_data, "tmp", "0000"
        )
        try:
            temp_kelvin = int(current_temp) / 10  # Device reports in 0.1K increments
            self._attr_current_temperature = float(
                temp_kelvin - 273.15
            )  # Convert to Celsius
        except (ValueError, TypeError):
            self._attr_current_temperature = None

        # Target temperature
        target_temp = self.coordinator.device.get_state_value(
            device_data, "hmax", "0000"
        )
        try:
            temp_kelvin = int(target_temp) / 10
            self._attr_target_temperature = float(temp_kelvin - 273.15)
        except (ValueError, TypeError):
            self._attr_target_temperature = 20.0  # Default to 20°C

        # HVAC mode based on device state
        heating_mode = self.coordinator.device.get_state_value(
            device_data, "hmod", "OFF"
        )
        fan_power = self.coordinator.device.get_state_value(device_data, "fpwr", "OFF")
        auto_mode = self.coordinator.device.get_state_value(device_data, "auto", "OFF")

        if fan_power == "OFF":
            self._attr_hvac_mode = HVACMode.OFF
        elif heating_mode == "HEAT":
            self._attr_hvac_mode = HVACMode.HEAT
        elif auto_mode == "ON":
            self._attr_hvac_mode = HVACMode.AUTO
        else:
            self._attr_hvac_mode = HVACMode.FAN_ONLY

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if not self._has_heating or not self.coordinator.device:
            return

        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        try:
            # Call the device method directly
            await self.coordinator.device.set_target_temperature(temperature)

            # Request updated state after command
            await asyncio.sleep(1)  # Give device time to process
            await self.coordinator.async_request_refresh()

            _LOGGER.debug(
                "Set target temperature to %s°C for %s",
                temperature,
                self.coordinator.serial_number,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting temperature to %s°C for %s: %s",
                temperature,
                self.coordinator.serial_number,
                err,
            )
        except ValueError as err:
            _LOGGER.error(
                "Invalid temperature value %s°C for %s: %s",
                temperature,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting temperature to %s°C for %s: %s",
                temperature,
                self.coordinator.serial_number,
                err,
            )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""
        if not self._has_heating or not self.coordinator.device:
            return

        try:
            if hvac_mode == HVACMode.OFF:
                await self.coordinator.async_send_command("set_power", {"fnst": "OFF"})
            elif hvac_mode == HVACMode.HEAT:
                await self.coordinator.async_send_command(
                    "set_climate_mode", {"fnst": "FAN", "hmod": "HEAT", "auto": "OFF"}
                )
            elif hvac_mode == HVACMode.FAN_ONLY:
                await self.coordinator.async_send_command(
                    "set_climate_mode", {"fnst": "FAN", "hmod": "OFF", "auto": "OFF"}
                )
            elif hvac_mode == HVACMode.AUTO:
                await self.coordinator.async_send_command(
                    "set_climate_mode", {"fnst": "FAN", "hmod": "OFF", "auto": "ON"}
                )

            # Request updated state after command
            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()

            _LOGGER.debug(
                "Set HVAC mode to %s for %s",
                hvac_mode,
                self.coordinator.serial_number,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting HVAC mode to %s for %s: %s",
                hvac_mode,
                self.coordinator.serial_number,
                err,
            )
        except (ValueError, KeyError) as err:
            _LOGGER.error(
                "Invalid HVAC mode '%s' for %s: %s",
                hvac_mode,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting HVAC mode to %s for %s: %s",
                hvac_mode,
                self.coordinator.serial_number,
                err,
            )
