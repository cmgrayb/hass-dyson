"""Number platform for Dyson Alternative integration."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
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
    """Set up Dyson number platform."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Speed control for all fan devices
    entities.append(DysonFanSpeedNumber(coordinator))

    # Add timer control if device supports scheduling
    device_capabilities = coordinator.device_capabilities
    if "Scheduling" in device_capabilities:
        entities.append(DysonSleepTimerNumber(coordinator))

    # Add oscillation angle control if supported
    if "AdvanceOscillationDay1" in device_capabilities:
        entities.append(DysonOscillationAngleNumber(coordinator))

    async_add_entities(entities, True)


class DysonFanSpeedNumber(DysonEntity, NumberEntity):
    """Number entity for fan speed control."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the fan speed number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_fan_speed"
        self._attr_name = "Fan Speed"
        self._attr_icon = "mdi:fan"
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_min_value = 1
        self._attr_native_max_value = 10
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get fan speed from device state (fnsp)
            speed_data = self.coordinator.data.get("product-state", {}).get("fnsp", "0001")
            try:
                # Convert speed data to number (e.g., "0005" -> 5)
                self._attr_native_value = int(speed_data.lstrip("0") or "1")
            except (ValueError, TypeError):
                self._attr_native_value = 1
        else:
            self._attr_native_value = None
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        """Set the fan speed."""
        if not self.coordinator.device:
            return

        try:
            # Format speed as 4-digit string (e.g., 5 -> "0005")
            speed_str = f"{int(value):04d}"
            await self.coordinator.async_send_command("set_fan_speed", {"fnsp": speed_str})
            _LOGGER.debug("Set fan speed to %s for %s", speed_str, self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to set fan speed for %s: %s", self.coordinator.serial_number, err)


class DysonSleepTimerNumber(DysonEntity, NumberEntity):
    """Number entity for sleep timer control."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the sleep timer number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_sleep_timer"
        self._attr_name = "Sleep Timer"
        self._attr_icon = "mdi:timer"
        self._attr_mode = NumberMode.BOX
        self._attr_native_min_value = 0
        self._attr_native_max_value = 540  # 9 hours in minutes
        self._attr_native_step = 15  # 15-minute increments
        self._attr_native_unit_of_measurement = "min"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get sleep timer from device state (sltm)
            timer_data = self.coordinator.data.get("product-state", {}).get("sltm", "OFF")
            if timer_data == "OFF":
                self._attr_native_value = 0
            else:
                try:
                    # Convert timer data to minutes
                    self._attr_native_value = int(timer_data)
                except (ValueError, TypeError):
                    self._attr_native_value = 0
        else:
            self._attr_native_value = None
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        """Set the sleep timer."""
        if not self.coordinator.device:
            return

        try:
            timer_value = "OFF" if value == 0 else f"{int(value):04d}"
            await self.coordinator.async_send_command("set_sleep_timer", {"sltm": timer_value})
            _LOGGER.debug("Set sleep timer to %s for %s", timer_value, self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to set sleep timer for %s: %s", self.coordinator.serial_number, err)


class DysonOscillationAngleNumber(DysonEntity, NumberEntity):
    """Number entity for oscillation angle control."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the oscillation angle number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_oscillation_angle"
        self._attr_name = "Oscillation Angle"
        self._attr_icon = "mdi:rotate-3d-variant"
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_min_value = 45
        self._attr_native_max_value = 350
        self._attr_native_step = 15
        self._attr_native_unit_of_measurement = "°"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get oscillation angle from device state (ancp)
            angle_data = self.coordinator.data.get("product-state", {}).get("ancp", "0045")
            try:
                # Convert angle data to number (e.g., "0180" -> 180)
                self._attr_native_value = int(angle_data.lstrip("0") or "45")
            except (ValueError, TypeError):
                self._attr_native_value = 45
        else:
            self._attr_native_value = None
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        """Set the oscillation angle."""
        if not self.coordinator.device:
            return

        try:
            # Format angle as 4-digit string (e.g., 180 -> "0180")
            angle_str = f"{int(value):04d}"
            await self.coordinator.async_send_command("set_oscillation_angle", {"ancp": angle_str})
            _LOGGER.debug("Set oscillation angle to %s for %s", angle_str, self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to set oscillation angle for %s: %s", self.coordinator.serial_number, err)
