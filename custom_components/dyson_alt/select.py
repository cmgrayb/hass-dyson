"""Select platform for Dyson Alternative integration."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
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
    """Set up Dyson select platform."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Air quality mode selection for all devices
    entities.append(DysonAirQualityModeSelect(coordinator))

    # Add additional selects based on capabilities
    device_capabilities = coordinator.device_capabilities

    if "AdvanceOscillationDay1" in device_capabilities:
        entities.append(DysonOscillationModeSelect(coordinator))

    if "Heating" in device_capabilities:
        entities.append(DysonHeatingModeSelect(coordinator))

    async_add_entities(entities, True)


class DysonAirQualityModeSelect(DysonEntity, SelectEntity):
    """Select entity for air quality mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the air quality mode select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_air_quality_mode"
        self._attr_name = "Air Quality Mode"
        self._attr_icon = "mdi:air-filter"
        self._attr_options = ["Auto", "Manual", "Sleep"]

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get air quality mode from device state (auto mode)
            auto_mode = self.coordinator.data.get("product-state", {}).get("auto", "OFF")
            night_mode = self.coordinator.data.get("product-state", {}).get("nmod", "OFF")

            if night_mode == "ON":
                self._attr_current_option = "Sleep"
            elif auto_mode == "ON":
                self._attr_current_option = "Auto"
            else:
                self._attr_current_option = "Manual"
        else:
            self._attr_current_option = None
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Select the air quality mode."""
        if not self.coordinator.device:
            return

        try:
            if option == "Auto":
                await self.coordinator.async_send_command("set_mode", {"auto": "ON", "nmod": "OFF"})
            elif option == "Sleep":
                await self.coordinator.async_send_command("set_mode", {"auto": "OFF", "nmod": "ON"})
            else:  # Manual
                await self.coordinator.async_send_command("set_mode", {"auto": "OFF", "nmod": "OFF"})
            _LOGGER.debug("Set air quality mode to %s for %s", option, self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to set air quality mode for %s: %s", self.coordinator.serial_number, err)


class DysonOscillationModeSelect(DysonEntity, SelectEntity):
    """Select entity for oscillation mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the oscillation mode select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_oscillation_mode"
        self._attr_name = "Oscillation Mode"
        self._attr_icon = "mdi:rotate-3d-variant"
        self._attr_options = ["Off", "45°", "90°", "180°", "350°"]

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get oscillation state from device (oson/oscs)
            oson = self.coordinator.data.get("product-state", {}).get("oson", "OFF")
            if oson == "OFF":
                self._attr_current_option = "Off"
            else:
                # Get oscillation angle
                angle_data = self.coordinator.data.get("product-state", {}).get("ancp", "0045")
                try:
                    angle = int(angle_data.lstrip("0") or "45")
                    if angle <= 45:
                        self._attr_current_option = "45°"
                    elif angle <= 90:
                        self._attr_current_option = "90°"
                    elif angle <= 180:
                        self._attr_current_option = "180°"
                    else:
                        self._attr_current_option = "350°"
                except (ValueError, TypeError):
                    self._attr_current_option = "45°"
        else:
            self._attr_current_option = None
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Select the oscillation mode."""
        if not self.coordinator.device:
            return

        try:
            if option == "Off":
                await self.coordinator.async_send_command("set_oscillation", {"oson": "OFF"})
            else:
                # Extract angle from option (e.g., "180°" -> "0180")
                angle = int(option.replace("°", ""))
                angle_str = f"{angle:04d}"
                await self.coordinator.async_send_command("set_oscillation", {"oson": "ON", "ancp": angle_str})
            _LOGGER.debug("Set oscillation mode to %s for %s", option, self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to set oscillation mode for %s: %s", self.coordinator.serial_number, err)


class DysonHeatingModeSelect(DysonEntity, SelectEntity):
    """Select entity for heating mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the heating mode select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_heating_mode"
        self._attr_name = "Heating Mode"
        self._attr_icon = "mdi:radiator"
        self._attr_options = ["Off", "Heating", "Auto Heat"]

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get heating mode from device state (hmod)
            hmod = self.coordinator.data.get("product-state", {}).get("hmod", "OFF")
            if hmod == "OFF":
                self._attr_current_option = "Off"
            elif hmod == "HEAT":
                self._attr_current_option = "Heating"
            else:
                self._attr_current_option = "Auto Heat"
        else:
            self._attr_current_option = None
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Select the heating mode."""
        if not self.coordinator.device:
            return

        try:
            if option == "Off":
                mode_value = "OFF"
            elif option == "Heating":
                mode_value = "HEAT"
            else:  # Auto Heat
                mode_value = "AUTO"

            await self.coordinator.async_send_command("set_heating", {"hmod": mode_value})
            _LOGGER.debug("Set heating mode to %s for %s", option, self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to set heating mode for %s: %s", self.coordinator.serial_number, err)
