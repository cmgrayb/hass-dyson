"""Switch platform for Dyson Alternative integration."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
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
    """Set up Dyson switch platform."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Basic switches for all devices
    entities.append(DysonNightModeSwitch(coordinator))

    # Only add auto mode switch for cloud devices (not manual local-only devices)
    connection_type = config_entry.data.get("connection_type", "unknown")
    if connection_type != "local_only":
        entities.append(DysonAutoModeSwitch(coordinator))

    # Add additional switches based on capabilities
    device_capabilities = coordinator.device_capabilities

    # Oscillation switch disabled - use "Oscillation Mode" select entity instead
    # if "AdvanceOscillationDay1" in device_capabilities:
    #     entities.append(DysonOscillationSwitch(coordinator))

    if "Heating" in device_capabilities:
        entities.append(DysonHeatingSwitch(coordinator))

    if "ContinuousMonitoring" in device_capabilities:
        entities.append(DysonContinuousMonitoringSwitch(coordinator))

    async_add_entities(entities, True)


class DysonAutoModeSwitch(DysonEntity, SwitchEntity):
    """Switch for auto mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the auto mode switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_auto_mode"
        self._attr_name = "Auto Mode"
        self._attr_icon = "mdi:auto-mode"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get auto mode from device state (auto)
            product_state = self.coordinator.data.get("product-state", {})
            auto_mode = self.coordinator.device._get_current_value(product_state, "auto", "OFF")
            self._attr_is_on = auto_mode == "ON"
        else:
            self._attr_is_on = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on auto mode."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_auto_mode(True)
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug("Turned on auto mode for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn on auto mode for %s: %s", self.coordinator.serial_number, err)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off auto mode."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_auto_mode(False)
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug("Turned off auto mode for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn off auto mode for %s: %s", self.coordinator.serial_number, err)


class DysonNightModeSwitch(DysonEntity, SwitchEntity):
    """Switch for night mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the night mode switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_night_mode"
        self._attr_name = "Night Mode"
        self._attr_icon = "mdi:weather-night"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get night mode from device state (nmod)
            product_state = self.coordinator.data.get("product-state", {})
            night_mode = self.coordinator.device._get_current_value(product_state, "nmod", "OFF")
            self._attr_is_on = night_mode == "ON"
        else:
            self._attr_is_on = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on night mode."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_night_mode(True)
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug("Turned on night mode for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn on night mode for %s: %s", self.coordinator.serial_number, err)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off night mode."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_night_mode(False)
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug("Turned off night mode for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn off night mode for %s: %s", self.coordinator.serial_number, err)


class DysonOscillationSwitch(DysonEntity, SwitchEntity):
    """Switch for oscillation."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the oscillation switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_oscillation"
        self._attr_name = "Oscillation"
        self._attr_icon = "mdi:rotate-3d-variant"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get oscillation from device state (oson)
            product_state = self.coordinator.data.get("product-state", {})
            oson = self.coordinator.device._get_current_value(product_state, "oson", "OFF")
            self._attr_is_on = oson == "ON"
        else:
            self._attr_is_on = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on oscillation."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_oscillation(True)
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug("Turned on oscillation for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn on oscillation for %s: %s", self.coordinator.serial_number, err)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off oscillation."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_oscillation(False)
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug("Turned off oscillation for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn off oscillation for %s: %s", self.coordinator.serial_number, err)


class DysonHeatingSwitch(DysonEntity, SwitchEntity):
    """Switch for heating mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the heating switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_heating"
        self._attr_name = "Heating"
        self._attr_icon = "mdi:radiator"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get heating from device state (hmod)
            product_state = self.coordinator.data.get("product-state", {})
            hmod = self.coordinator.device._get_current_value(product_state, "hmod", "OFF")
            self._attr_is_on = hmod != "OFF"
        else:
            self._attr_is_on = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on heating."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.async_send_command("set_heating", {"hmod": "HEAT"})
            _LOGGER.debug("Turned on heating for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn on heating for %s: %s", self.coordinator.serial_number, err)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off heating."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.async_send_command("set_heating", {"hmod": "OFF"})
            _LOGGER.debug("Turned off heating for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn off heating for %s: %s", self.coordinator.serial_number, err)


class DysonContinuousMonitoringSwitch(DysonEntity, SwitchEntity):
    """Switch for continuous monitoring."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the continuous monitoring switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_continuous_monitoring"
        self._attr_name = "Continuous Monitoring"
        self._attr_icon = "mdi:monitor-eye"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get monitoring from device state (rhtm)
            product_state = self.coordinator.data.get("product-state", {})
            rhtm = self.coordinator.device._get_current_value(product_state, "rhtm", "OFF")
            self._attr_is_on = rhtm == "ON"
        else:
            self._attr_is_on = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on continuous monitoring."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.async_send_command("set_monitoring", {"rhtm": "ON"})
            _LOGGER.debug("Turned on continuous monitoring for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn on continuous monitoring for %s: %s", self.coordinator.serial_number, err)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off continuous monitoring."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.async_send_command("set_monitoring", {"rhtm": "OFF"})
            _LOGGER.debug("Turned off continuous monitoring for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn off continuous monitoring for %s: %s", self.coordinator.serial_number, err)
