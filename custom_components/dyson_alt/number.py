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

    # Add timer control if device supports scheduling
    device_capabilities = coordinator.device_capabilities
    if "Scheduling" in device_capabilities:
        entities.append(DysonSleepTimerNumber(coordinator))

    # Add oscillation angle control if supported - temporarily enable for all devices for testing
    device_capabilities = coordinator.device_capabilities
    _LOGGER.debug("Device capabilities for %s: %s", coordinator.serial_number, device_capabilities)

    # Check if device has oscillation capability or is an environment cleaner - temporarily allow all
    has_oscillation = "AdvanceOscillationDay1" in device_capabilities
    is_environment_cleaner = any("ec" in cat.lower() for cat in coordinator.device_category)

    # Temporarily enable for all devices for testing
    if has_oscillation or is_environment_cleaner or True:
        _LOGGER.info("Adding oscillation angle controls for %s", coordinator.serial_number)
        entities.append(DysonOscillationLowerAngleNumber(coordinator))
        entities.append(DysonOscillationUpperAngleNumber(coordinator))
        entities.append(DysonOscillationCenterAngleNumber(coordinator))
        entities.append(DysonOscillationAngleSpanNumber(coordinator))

    async_add_entities(entities, True)


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
            product_state = self.coordinator.data.get("product-state", {})
            timer_data = self.coordinator.device._get_current_value(product_state, "sltm", "OFF")
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
        self._handle_coordinator_update_safe()

    async def async_set_native_value(self, value: float) -> None:
        """Set the sleep timer."""
        if not self.coordinator.device:
            return

        try:
            # Use device method directly
            minutes = int(value)
            await self.coordinator.device.set_sleep_timer(int(value))
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug("Set sleep timer to %s minutes for %s", minutes, self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to set sleep timer for %s: %s", self.coordinator.serial_number, err)


class DysonOscillationLowerAngleNumber(DysonEntity, NumberEntity):
    """Number entity for oscillation lower angle control."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the oscillation lower angle number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_oscillation_lower_angle"
        self._attr_name = "Oscillation Low Angle"
        self._attr_icon = "mdi:rotate-left"
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_min_value = 0
        self._attr_native_max_value = 350
        self._attr_native_step = 5
        self._attr_native_unit_of_measurement = "°"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get lower oscillation angle from device state (osal)
            product_state = self.coordinator.data.get("product-state", {})
            angle_data = self.coordinator.device._get_current_value(product_state, "osal", "0000")
            try:
                # Convert angle data to number (e.g., "0090" -> 90)
                self._attr_native_value = int(angle_data.lstrip("0") or "0")
            except (ValueError, TypeError):
                self._attr_native_value = 0
        else:
            self._attr_native_value = None
        self._handle_coordinator_update_safe()

    async def async_set_native_value(self, value: float) -> None:
        """Set the oscillation lower angle."""
        if not self.coordinator.device:
            return

        try:
            # Get current upper angle to ensure lower < upper
            upper_angle_data = self.coordinator.data.get("product-state", {}).get("osau", "0350")
            upper_angle = int(upper_angle_data.lstrip("0") or "350")

            # Ensure lower angle is less than upper angle
            lower_angle = min(int(value), upper_angle - 5)

            # Use device method directly
            await self.coordinator.device.set_oscillation_angles(lower_angle, upper_angle)
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug("Set oscillation lower angle to %s for %s", lower_angle, self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to set oscillation lower angle for %s: %s", self.coordinator.serial_number, err)


class DysonOscillationUpperAngleNumber(DysonEntity, NumberEntity):
    """Number entity for oscillation upper angle control."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the oscillation upper angle number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_oscillation_upper_angle"
        self._attr_name = "Oscillation High Angle"
        self._attr_icon = "mdi:rotate-right"
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_min_value = 0
        self._attr_native_max_value = 350
        self._attr_native_step = 5
        self._attr_native_unit_of_measurement = "°"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get upper oscillation angle from device state (osau)
            product_state = self.coordinator.data.get("product-state", {})
            angle_data = self.coordinator.device._get_current_value(product_state, "osau", "0350")
            try:
                # Convert angle data to number (e.g., "0350" -> 350)
                self._attr_native_value = int(angle_data.lstrip("0") or "350")
            except (ValueError, TypeError):
                self._attr_native_value = 350
        else:
            self._attr_native_value = None
        self._handle_coordinator_update_safe()

    async def async_set_native_value(self, value: float) -> None:
        """Set the oscillation upper angle."""
        if not self.coordinator.device:
            return

        try:
            # Get current lower angle to ensure lower < upper
            lower_angle_data = self.coordinator.data.get("product-state", {}).get("osal", "0000")
            lower_angle = int(lower_angle_data.lstrip("0") or "0")

            # Ensure upper angle is greater than lower angle
            upper_angle = max(int(value), lower_angle + 5)

            # Use device method directly
            await self.coordinator.device.set_oscillation_angles(lower_angle, upper_angle)
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug("Set oscillation upper angle to %s for %s", upper_angle, self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to set oscillation upper angle for %s: %s", self.coordinator.serial_number, err)


class DysonOscillationCenterAngleNumber(DysonEntity, NumberEntity):
    """Number entity for oscillation center angle control."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the oscillation center angle number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_oscillation_center_angle"
        self._attr_name = "Oscillation Center Angle"
        self._attr_icon = "mdi:crosshairs"
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_min_value = 0
        self._attr_native_max_value = 350
        self._attr_native_step = 5
        self._attr_native_unit_of_measurement = "°"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Calculate center angle from lower and upper angles
            product_state = self.coordinator.data.get("product-state", {})
            lower_data = self.coordinator.device._get_current_value(product_state, "osal", "0000")
            upper_data = self.coordinator.device._get_current_value(product_state, "osau", "0350")
            try:
                lower_angle = int(lower_data.lstrip("0") or "0")
                upper_angle = int(upper_data.lstrip("0") or "350")
                # Center is the median between lower and upper
                self._attr_native_value = (lower_angle + upper_angle) // 2
            except (ValueError, TypeError):
                self._attr_native_value = 175  # Default center
        else:
            self._attr_native_value = None
        self._handle_coordinator_update_safe()

    async def async_set_native_value(self, value: float) -> None:
        """Set the oscillation center angle - adjusts lower and upper to maintain current span."""
        if not self.coordinator.device:
            return

        try:
            # Get current span (upper - lower)
            product_state = self.coordinator.data.get("product-state", {})
            lower_data = self.coordinator.device._get_current_value(product_state, "osal", "0000")
            upper_data = self.coordinator.device._get_current_value(product_state, "osau", "0350")
            lower_angle = int(lower_data.lstrip("0") or "0")
            upper_angle = int(upper_data.lstrip("0") or "350")
            current_span = upper_angle - lower_angle

            # Calculate new lower and upper angles centered on the target
            center_angle = int(value)
            half_span = current_span // 2
            new_lower = max(0, center_angle - half_span)
            new_upper = min(350, center_angle + half_span)

            # Adjust if we hit boundaries
            if new_lower == 0:
                new_upper = min(350, current_span)
            elif new_upper == 350:
                new_lower = max(0, 350 - current_span)

            # Use device method directly
            await self.coordinator.device.set_oscillation_angles(new_lower, new_upper)
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug(
                "Set oscillation center angle to %s (lower: %s, upper: %s) for %s",
                center_angle,
                new_lower,
                new_upper,
                self.coordinator.serial_number,
            )
        except Exception as err:
            _LOGGER.error("Failed to set oscillation center angle for %s: %s", self.coordinator.serial_number, err)


class DysonOscillationAngleSpanNumber(DysonEntity, NumberEntity):
    """Number entity for oscillation angle span control."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the oscillation angle span number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_oscillation_angle_span"
        self._attr_name = "Oscillation Angle Span"
        self._attr_icon = "mdi:angle-acute"
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_min_value = 10
        self._attr_native_max_value = 350
        self._attr_native_step = 5
        self._attr_native_unit_of_measurement = "°"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Calculate span from lower and upper angles
            product_state = self.coordinator.data.get("product-state", {})
            lower_data = self.coordinator.device._get_current_value(product_state, "osal", "0000")
            upper_data = self.coordinator.device._get_current_value(product_state, "osau", "0350")
            try:
                lower_angle = int(lower_data.lstrip("0") or "0")
                upper_angle = int(upper_data.lstrip("0") or "350")
                # Span is the difference between upper and lower
                self._attr_native_value = upper_angle - lower_angle
            except (ValueError, TypeError):
                self._attr_native_value = 350  # Default full span
        else:
            self._attr_native_value = None
        self._handle_coordinator_update_safe()

    async def async_set_native_value(self, value: float) -> None:
        """Set the oscillation angle span - adjusts lower and upper to maintain current center."""
        if not self.coordinator.device:
            return

        try:
            # Get current center angle
            product_state = self.coordinator.data.get("product-state", {})
            lower_data = self.coordinator.device._get_current_value(product_state, "osal", "0000")
            upper_data = self.coordinator.device._get_current_value(product_state, "osau", "0350")
            lower_angle = int(lower_data.lstrip("0") or "0")
            upper_angle = int(upper_data.lstrip("0") or "350")
            current_center = (lower_angle + upper_angle) // 2

            # Calculate new lower and upper angles with the desired span
            new_span = int(value)
            half_span = new_span // 2
            new_lower = max(0, current_center - half_span)
            new_upper = min(350, current_center + half_span)

            # Adjust if we hit boundaries
            if new_lower == 0:
                new_upper = min(350, new_span)
            elif new_upper == 350:
                new_lower = max(0, 350 - new_span)

            # Use device method directly
            await self.coordinator.device.set_oscillation_angles(new_lower, new_upper)
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug(
                "Set oscillation angle span to %s (lower: %s, upper: %s) for %s",
                new_span,
                new_lower,
                new_upper,
                self.coordinator.serial_number,
            )
        except Exception as err:
            _LOGGER.error("Failed to set oscillation angle span for %s: %s", self.coordinator.serial_number, err)


# Keep the original single angle class for backward compatibility
class DysonOscillationAngleNumber(DysonEntity, NumberEntity):
    """Number entity for oscillation angle control."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the oscillation angle number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_oscillation_angle"
        self._attr_name = "Oscillation Custom Angle"
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
            product_state = self.coordinator.data.get("product-state", {})
            angle_data = self.coordinator.device._get_current_value(product_state, "ancp", "0045")
            try:
                # Convert angle data to number (e.g., "0180" -> 180)
                self._attr_native_value = int(angle_data.lstrip("0") or "45")
            except (ValueError, TypeError):
                self._attr_native_value = 45
        else:
            self._attr_native_value = None
        self._handle_coordinator_update_safe()

    async def async_set_native_value(self, value: float) -> None:
        """Set the oscillation angle."""
        if not self.coordinator.device:
            return

        try:
            # Use device method with angle parameter
            await self.coordinator.device.set_oscillation(True, int(value))
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug("Set oscillation angle to %s for %s", int(value), self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to set oscillation angle for %s: %s", self.coordinator.serial_number, err)
