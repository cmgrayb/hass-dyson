"""Climate platform for Dyson integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
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

    # Only add climate entity for devices with heating capability
    device_capabilities = coordinator.device_capabilities
    if "Heating" in device_capabilities:
        entities.append(DysonClimateEntity(coordinator))

    async_add_entities(entities, True)


class DysonClimateEntity(DysonEntity, ClimateEntity):  # type: ignore[misc]
    """Climate entity for Dyson heating devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_climate"
        self._attr_translation_key = "heating_controls"
        self._attr_icon = "mdi:thermostat"

        # Climate features
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        # Temperature settings
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_min_temp = 1
        self._attr_max_temp = 37
        self._attr_target_temperature_step = 1

        # HVAC modes
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.HEAT,
            HVACMode.FAN_ONLY,
            HVACMode.AUTO,
        ]

        # Initialize HVAC mode to OFF (will be updated in _handle_coordinator_update)
        self._attr_hvac_mode = HVACMode.OFF

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            return

        device_data = self.coordinator.data.get("product-state", {})

        self._update_temperatures(device_data)
        self._update_hvac_mode(device_data)

        super()._handle_coordinator_update()

    def _update_temperatures(self, device_data: dict[str, Any]) -> None:
        """Update current and target temperatures from device data."""
        if not self.coordinator.device:
            return

        # Current temperature
        current_temp = self.coordinator.device._get_current_value(
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
        target_temp = self.coordinator.device._get_current_value(
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

    def _update_hvac_mode(self, device_data: dict[str, Any]) -> None:
        """Update HVAC mode from device data."""
        if not self.coordinator.device:
            return

        fan_power = self.coordinator.device._get_current_value(
            device_data, "fnst", "OFF"
        )
        heating_mode = self.coordinator.device._get_current_value(
            device_data, "hmod", "OFF"
        )
        auto_mode = self.coordinator.device._get_current_value(
            device_data, "auto", "OFF"
        )

        if fan_power == "OFF":
            self._attr_hvac_mode = HVACMode.OFF
        elif heating_mode == "HEAT":
            self._attr_hvac_mode = HVACMode.HEAT
        elif auto_mode == "ON":
            self._attr_hvac_mode = HVACMode.AUTO
        else:
            self._attr_hvac_mode = HVACMode.FAN_ONLY

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if not self.coordinator.device:
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
                    "set_climate_mode", {"fnst": "FAN", "auto": "ON"}
                )

            _LOGGER.debug(
                "Set HVAC mode to %s for %s", hvac_mode, self.coordinator.serial_number
            )
        except Exception as err:
            _LOGGER.error(
                "Failed to set HVAC mode for %s: %s",
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

            # Request updated state after command
            await asyncio.sleep(1)  # Give device time to process
            await self.coordinator.async_request_refresh()

            _LOGGER.debug(
                "Set target temperature to %s°C for %s",
                temperature,
                self.coordinator.serial_number,
            )
        except Exception as err:
            _LOGGER.error(
                "Failed to set target temperature for %s: %s",
                self.coordinator.serial_number,
                err,
            )

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    @property
    def extra_state_attributes(self):
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

        # Device state properties that can be controlled
        heating_mode = self.coordinator.device._get_current_value(
            product_state, "hmod", "OFF"
        )
        auto_mode = self.coordinator.device._get_current_value(
            product_state, "auto", "OFF"
        )
        fan_power = self.coordinator.device._get_current_value(
            product_state, "fnst", "OFF"
        )

        attributes["heating_mode"] = heating_mode  # type: ignore[assignment]
        attributes["auto_mode"] = auto_mode == "ON"
        attributes["fan_power"] = fan_power == "FAN"

        # Target temperature in Kelvin for device commands
        if target_temp is not None:
            temp_kelvin: int = int((target_temp + 273.15) * 10)
            kelvin_str: str = f"{temp_kelvin:04d}"
            attributes["target_temperature_kelvin"] = kelvin_str  # type: ignore[assignment]

        return attributes
