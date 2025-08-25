"""Switch platform for Dyson Alternative integration."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DysonDataUpdateCoordinator

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
    entities.extend(
        [
            DysonAutoModeSwitch(coordinator),
            DysonNightModeSwitch(coordinator),
        ]
    )

    # Add additional switches based on capabilities
    device_capabilities = coordinator.device_capabilities

    if "AdvanceOscillationDay1" in device_capabilities:
        entities.append(DysonOscillationSwitch(coordinator))

    if "Heating" in device_capabilities:
        entities.append(DysonHeatingSwitch(coordinator))

    if "ContinuousMonitoring" in device_capabilities:
        entities.append(DysonContinuousMonitoringSwitch(coordinator))

    async_add_entities(entities, True)


class DysonAutoModeSwitch(CoordinatorEntity, SwitchEntity):
    """Switch for auto mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the auto mode switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_auto_mode"
        self._attr_name = f"{coordinator.config_entry.title} Auto Mode"
        self._attr_icon = "mdi:auto-mode"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get auto mode from device state (auto)
            auto_mode = self.coordinator.data.get("product-state", {}).get("auto", "OFF")
            self._attr_is_on = auto_mode == "ON"
        else:
            self._attr_is_on = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on auto mode."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.async_send_command("set_auto_mode", {"auto": "ON"})
            _LOGGER.debug("Turned on auto mode for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn on auto mode for %s: %s", self.coordinator.serial_number, err)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off auto mode."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.async_send_command("set_auto_mode", {"auto": "OFF"})
            _LOGGER.debug("Turned off auto mode for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn off auto mode for %s: %s", self.coordinator.serial_number, err)


class DysonNightModeSwitch(CoordinatorEntity, SwitchEntity):
    """Switch for night mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the night mode switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_night_mode"
        self._attr_name = f"{coordinator.config_entry.title} Night Mode"
        self._attr_icon = "mdi:weather-night"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get night mode from device state (nmod)
            night_mode = self.coordinator.data.get("product-state", {}).get("nmod", "OFF")
            self._attr_is_on = night_mode == "ON"
        else:
            self._attr_is_on = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on night mode."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.async_send_command("set_night_mode", {"nmod": "ON"})
            _LOGGER.debug("Turned on night mode for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn on night mode for %s: %s", self.coordinator.serial_number, err)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off night mode."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.async_send_command("set_night_mode", {"nmod": "OFF"})
            _LOGGER.debug("Turned off night mode for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn off night mode for %s: %s", self.coordinator.serial_number, err)


class DysonOscillationSwitch(CoordinatorEntity, SwitchEntity):
    """Switch for oscillation."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the oscillation switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_oscillation"
        self._attr_name = f"{coordinator.config_entry.title} Oscillation"
        self._attr_icon = "mdi:rotate-3d-variant"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get oscillation from device state (oson)
            oson = self.coordinator.data.get("product-state", {}).get("oson", "OFF")
            self._attr_is_on = oson == "ON"
        else:
            self._attr_is_on = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on oscillation."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.async_send_command("set_oscillation", {"oson": "ON"})
            _LOGGER.debug("Turned on oscillation for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn on oscillation for %s: %s", self.coordinator.serial_number, err)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off oscillation."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.async_send_command("set_oscillation", {"oson": "OFF"})
            _LOGGER.debug("Turned off oscillation for %s", self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to turn off oscillation for %s: %s", self.coordinator.serial_number, err)


class DysonHeatingSwitch(CoordinatorEntity, SwitchEntity):
    """Switch for heating mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the heating switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_heating"
        self._attr_name = f"{coordinator.config_entry.title} Heating"
        self._attr_icon = "mdi:radiator"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get heating from device state (hmod)
            hmod = self.coordinator.data.get("product-state", {}).get("hmod", "OFF")
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


class DysonContinuousMonitoringSwitch(CoordinatorEntity, SwitchEntity):
    """Switch for continuous monitoring."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the continuous monitoring switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_continuous_monitoring"
        self._attr_name = f"{coordinator.config_entry.title} Continuous Monitoring"
        self._attr_icon = "mdi:monitor-eye"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get monitoring from device state (rhtm)
            rhtm = self.coordinator.data.get("product-state", {}).get("rhtm", "OFF")
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
