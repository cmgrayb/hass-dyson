"""Climate platform for Dyson integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
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
    """Set up Dyson climate platform."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Add climate entity for devices with heating or humidifier capability
    device_capabilities = coordinator.device_capabilities
    if "Heating" in device_capabilities or "Humidifier" in device_capabilities:
        entities.append(DysonClimateEntity(coordinator))

    async_add_entities(entities, True)


class DysonClimateEntity(DysonEntity, ClimateEntity):  # type: ignore[misc]
    """Climate entity for Dyson heating devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_climate"
        self._attr_name = None  # Use device name from device_info
        self._attr_icon = "mdi:thermostat"

        # Check device capabilities for feature support
        device_capabilities = coordinator.device_capabilities
        has_heating = "Heating" in device_capabilities
        has_humidifier = "Humidifier" in device_capabilities

        # Climate features
        supported_features = (
            ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        )

        if has_heating:
            supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

        if has_humidifier:
            supported_features |= ClimateEntityFeature.TARGET_HUMIDITY

        self._attr_supported_features = supported_features

        # Temperature settings
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_min_temp = 1
        self._attr_max_temp = 37
        self._attr_target_temperature_step = 1

        # Humidity settings
        self._attr_min_humidity = 30
        self._attr_max_humidity = 50  # Based on humt range 0030-0050
        self._attr_target_humidity_step = 1

        # HVAC modes based on device capabilities
        hvac_modes = [HVACMode.OFF, HVACMode.FAN_ONLY]

        if has_heating:
            hvac_modes.append(HVACMode.HEAT)

        if has_humidifier:
            hvac_modes.append(HVACMode.DRY)  # Use DRY mode for humidification

        self._attr_hvac_modes = hvac_modes

        # Initialize HVAC mode to OFF (will be updated in _handle_coordinator_update)
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_hvac_action = HVACAction.OFF

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            return

        device_data = self.coordinator.data.get("product-state", {})

        self._update_temperatures(device_data)
        self._update_humidity(device_data)
        self._update_hvac_mode(device_data)
        self._update_hvac_action(device_data)

        super()._handle_coordinator_update()

    def _update_temperatures(self, device_data: dict[str, Any]) -> None:
        """Update current and target temperatures from device data."""
        if not self.coordinator.device:
            return

        # Current temperature
        current_temp = self.coordinator.device.get_state_value(
            device_data, "tmp", "0000"
        )
        try:
            temp_kelvin = int(current_temp) / 10  # Device reports in 0.1K increments
            # Only set temperature if we have a valid reading (not default 0000)
            if current_temp != "0000" and temp_kelvin > 0:
                self._attr_current_temperature = (
                    temp_kelvin - 273.15
                )  # Convert to Celsius
            else:
                self._attr_current_temperature = (
                    None  # No temperature sensor or invalid reading
                )
        except (ValueError, TypeError):
            self._attr_current_temperature = None

        # Target temperature
        target_temp = self.coordinator.device.get_state_value(
            device_data, "hmax", "0000"
        )
        try:
            temp_kelvin = int(target_temp) / 10
            # Only set target temperature if we have a valid reading
            if target_temp != "0000" and temp_kelvin > 0:
                self._attr_target_temperature = temp_kelvin - 273.15
            else:
                self._attr_target_temperature = 20  # Default to 20°C
        except (ValueError, TypeError):
            self._attr_target_temperature = 20  # Default to 20°C

    def _update_humidity(self, device_data: dict[str, Any]) -> None:
        """Update current and target humidity from device data."""
        if (
            not self.coordinator.device
            or "Humidifier" not in self.coordinator.device_capabilities
        ):
            return

        # Current humidity (if available)
        current_humidity = self.coordinator.device.get_state_value(
            device_data, "humi", "0000"
        )
        try:
            humidity_percent = int(current_humidity)
            # Only set humidity if we have a valid reading (not default 0000)
            if current_humidity != "0000" and humidity_percent > 0:
                self._attr_current_humidity = humidity_percent
            else:
                self._attr_current_humidity = (
                    None  # No humidity sensor or invalid reading
                )
        except (ValueError, TypeError):
            self._attr_current_humidity = None

        # Target humidity
        target_humidity = self.coordinator.device.get_state_value(
            device_data, "humt", "0040"
        )
        try:
            humidity_percent = int(target_humidity)
            # Only set target humidity if we have a valid reading
            if target_humidity != "0000" and humidity_percent > 0:
                self._attr_target_humidity = humidity_percent
            else:
                self._attr_target_humidity = 40  # Default to 40%
        except (ValueError, TypeError):
            self._attr_target_humidity = 40  # Default to 40%

    def _update_hvac_mode(self, device_data: dict[str, Any]) -> None:
        """Update HVAC mode from device data."""
        if not self.coordinator.device:
            return

        device_capabilities = self.coordinator.device_capabilities
        # Use device fan_power property which handles fpwr/fnst fallback properly
        fan_power_state = self.coordinator.device.fan_power
        fan_power = "ON" if fan_power_state else "OFF"

        # Check heating mode if device supports heating
        heating_mode = "OFF"
        if "Heating" in device_capabilities:
            heating_mode = self.coordinator.device.get_state_value(
                device_data, "hmod", "OFF"
            )

        # Check humidifier modes if device supports humidification
        humidity_enabled = "OFF"
        humidity_auto = "OFF"
        if "Humidifier" in device_capabilities:
            humidity_enabled = self.coordinator.device.get_state_value(
                device_data, "hume", "OFF"
            )
            humidity_auto = self.coordinator.device.get_state_value(
                device_data, "haut", "OFF"
            )

        # Only set to OFF if we're certain the fan power is actually OFF
        if fan_power == "OFF":
            self._attr_hvac_mode = HVACMode.OFF
        elif heating_mode == "HEAT":
            self._attr_hvac_mode = HVACMode.HEAT
        elif humidity_enabled == "HUMD" or humidity_auto == "ON":
            self._attr_hvac_mode = HVACMode.DRY  # Use DRY mode for humidification
        elif fan_power == "ON":
            # Fan is on - determine the specific mode based on heating state
            if heating_mode == "OFF":
                self._attr_hvac_mode = HVACMode.FAN_ONLY
            else:
                # Fan is on but heating mode is unclear - default to FAN_ONLY to avoid OFF
                _LOGGER.debug(
                    "Climate %s: Fan power ON but heating mode unclear (%s), defaulting to FAN_ONLY",
                    self.coordinator.serial_number,
                    heating_mode,
                )
                self._attr_hvac_mode = HVACMode.FAN_ONLY
        else:
            # State is unclear - preserve current mode to avoid flickering
            _LOGGER.debug(
                "Climate %s: Device state unclear (fpwr=%s, hmod=%s), preserving current HVAC mode (%s)",
                self.coordinator.serial_number,
                fan_power,
                heating_mode,
                self._attr_hvac_mode,
            )
            # Don't change self._attr_hvac_mode - keep existing state

    def _update_hvac_action(self, device_data: dict[str, Any]) -> None:
        """Update HVAC action based on current heating/cooling/humidifying status."""
        if not self.coordinator.device:
            return

        device_capabilities = self.coordinator.device_capabilities

        # Check device status
        heating_status = self.coordinator.device.get_state_value(
            device_data, "hsta", "OFF"
        )
        # Use device fan_power property which handles fpwr/fnst fallback properly
        fan_power_state = self.coordinator.device.fan_power
        fan_power = "ON" if fan_power_state else "OFF"
        hvac_mode = getattr(self, "_attr_hvac_mode", HVACMode.OFF)

        # Check humidifier status if supported
        humidity_enabled = "OFF"
        humidity_auto = "OFF"
        if "Humidifier" in device_capabilities:
            humidity_enabled = self.coordinator.device.get_state_value(
                device_data, "hume", "OFF"
            )
            humidity_auto = self.coordinator.device.get_state_value(
                device_data, "haut", "OFF"
            )

        if hvac_mode == HVACMode.OFF:
            self._attr_hvac_action = HVACAction.OFF
        elif heating_status == "HEAT":
            self._attr_hvac_action = HVACAction.HEATING
        elif hvac_mode == HVACMode.DRY and (
            humidity_enabled == "HUMD" or humidity_auto == "ON"
        ):
            # Device is in humidification mode - use drying action as closest match
            self._attr_hvac_action = HVACAction.DRYING
        elif hvac_mode == HVACMode.FAN_ONLY and fan_power == "ON":
            # Device is in fan-only mode with fan running
            self._attr_hvac_action = HVACAction.FAN
        else:
            # Device is on but not actively heating, cooling, or humidifying
            self._attr_hvac_action = HVACAction.IDLE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode - Heat, Fan Only, Dry (humidifier), or Off."""
        if not self.coordinator.device:
            return

        device_capabilities = self.coordinator.device_capabilities

        try:
            if hvac_mode == HVACMode.OFF:
                # Turn off fan power and all modes
                command_data = {"fpwr": "OFF"}
                if "Heating" in device_capabilities:
                    command_data["hmod"] = "OFF"
                if "Humidifier" in device_capabilities:
                    command_data["hume"] = "OFF"
                    command_data["haut"] = "OFF"
                await self.coordinator.device.send_command("STATE-SET", command_data)

            elif hvac_mode == HVACMode.HEAT and "Heating" in device_capabilities:
                # Enable heating mode
                command_data = {"fpwr": "ON", "hmod": "HEAT"}
                if "Humidifier" in device_capabilities:
                    command_data["hume"] = "OFF"
                    command_data["haut"] = "OFF"
                await self.coordinator.device.send_command("STATE-SET", command_data)

            elif hvac_mode == HVACMode.FAN_ONLY:
                # Enable fan only (no heat or humidification)
                command_data = {"fpwr": "ON"}
                if "Heating" in device_capabilities:
                    command_data["hmod"] = "OFF"
                if "Humidifier" in device_capabilities:
                    command_data["hume"] = "OFF"
                    command_data["haut"] = "OFF"
                await self.coordinator.device.send_command("STATE-SET", command_data)

            elif hvac_mode == HVACMode.DRY and "Humidifier" in device_capabilities:
                # Enable humidification mode (manual on, auto off)
                command_data = {"fpwr": "ON", "hume": "HUMD", "haut": "OFF"}
                if "Heating" in device_capabilities:
                    command_data["hmod"] = "OFF"
                await self.coordinator.device.send_command("STATE-SET", command_data)

            else:
                supported_modes = [mode.value for mode in self._attr_hvac_modes]
                _LOGGER.warning(
                    "Unsupported HVAC mode '%s' for %s. Supported modes: %s.",
                    hvac_mode,
                    self.coordinator.serial_number,
                    supported_modes,
                )
                return

            # Update local state immediately for responsive UI
            self._attr_hvac_mode = hvac_mode
            self.async_write_ha_state()

            _LOGGER.debug(
                "Set HVAC mode to %s for %s", hvac_mode, self.coordinator.serial_number
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting HVAC mode '%s' for %s: %s",
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
                "Unexpected error setting HVAC mode '%s' for %s: %s",
                hvac_mode,
                self.coordinator.serial_number,
                err,
            )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if not self.coordinator.device:
            return

        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        try:
            # Call the device method directly
            await self.coordinator.device.set_target_temperature(temperature)

            # Update local state immediately for responsive UI
            self._attr_target_temperature = temperature
            self.async_write_ha_state()

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

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        if (
            not self.coordinator.device
            or "Humidifier" not in self.coordinator.device_capabilities
        ):
            return

        try:
            # Convert humidity percentage to device format (4-digit string)
            humidity_value = f"{humidity:04d}"
            await self.coordinator.device.send_command(
                "STATE-SET", {"humt": humidity_value}
            )

            # Update local state immediately for responsive UI
            self._attr_target_humidity = int(humidity)
            self.async_write_ha_state()

            _LOGGER.debug(
                "Set target humidity to %s%% for %s",
                humidity,
                self.coordinator.serial_number,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting humidity to %s%% for %s: %s",
                humidity,
                self.coordinator.serial_number,
                err,
            )
        except ValueError as err:
            _LOGGER.error(
                "Invalid humidity value %s%% for %s: %s",
                humidity,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting humidity to %s%% for %s: %s",
                humidity,
                self.coordinator.serial_number,
                err,
            )

    async def async_turn_on(self) -> None:
        """Turn the entity on - defaults to heating mode if available, otherwise humidifier mode."""
        device_capabilities = self.coordinator.device_capabilities

        if "Heating" in device_capabilities:
            await self.async_set_hvac_mode(HVACMode.HEAT)
        elif "Humidifier" in device_capabilities:
            await self.async_set_hvac_mode(HVACMode.DRY)
        else:
            _LOGGER.warning(
                "No supported climate modes available for %s",
                self.coordinator.serial_number,
            )

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return climate-specific state attributes for scene support."""
        if not self.coordinator.device:
            return None

        attributes = {}
        product_state = self.coordinator.data.get("product-state", {})

        # Core climate properties for scene support
        target_temp: float | None = self._attr_target_temperature
        hvac_mode: HVACMode | None = self._attr_hvac_mode

        attributes["target_temperature"] = target_temp  # type: ignore[assignment]
        attributes["hvac_mode"] = hvac_mode  # type: ignore[assignment]

        # Device state properties for climate control
        fan_power = self.coordinator.device.get_state_value(
            product_state, "fpwr", "OFF"
        )

        device_capabilities = self.coordinator.device_capabilities

        # Heating attributes (if supported)
        if "Heating" in device_capabilities:
            heating_mode = self.coordinator.device.get_state_value(
                product_state, "hmod", "OFF"
            )
            heating_status = self.coordinator.device.get_state_value(
                product_state, "hsta", "OFF"
            )
            attributes["heating_mode"] = heating_mode  # type: ignore[assignment]
            attributes["heating_status"] = heating_status  # type: ignore[assignment]

        # Humidity attributes (if supported)
        if "Humidifier" in device_capabilities:
            humidity_enabled = self.coordinator.device.get_state_value(
                product_state, "hume", "OFF"
            )
            humidity_auto = self.coordinator.device.get_state_value(
                product_state, "haut", "OFF"
            )
            current_humidity = self.coordinator.device.get_state_value(
                product_state, "humi", "0000"
            )

            attributes["humidity_enabled"] = humidity_enabled  # type: ignore[assignment]
            attributes["humidity_auto"] = humidity_auto  # type: ignore[assignment]
            attributes["current_humidity_raw"] = current_humidity  # type: ignore[assignment]

        attributes["fan_power"] = fan_power  # type: ignore[assignment]

        # Target temperature in Kelvin for device commands
        if target_temp is not None:
            temp_kelvin: int = int((target_temp + 273.15) * 10)
            kelvin_str: str = f"{temp_kelvin:04d}"
            attributes["target_temperature_kelvin"] = kelvin_str  # type: ignore[assignment]

        # Target humidity for device commands
        target_humidity = self._attr_target_humidity
        if target_humidity is not None and "Humidifier" in device_capabilities:
            humidity_int = int(target_humidity)
            humidity_str: str = f"{humidity_int:04d}"
            attributes["target_humidity"] = humidity_int  # type: ignore[assignment]
            attributes["target_humidity_formatted"] = humidity_str  # type: ignore[assignment]

        return attributes
