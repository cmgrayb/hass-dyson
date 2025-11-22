"""Number platform for Dyson integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

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

    entities: list[NumberEntity] = []

    # Add timer control if device supports scheduling
    device_capabilities = coordinator.device_capabilities
    if "Scheduling" in device_capabilities:
        entities.append(DysonSleepTimerNumber(coordinator))

    # Add oscillation angle control if supported
    _LOGGER.debug(
        "Device capabilities for %s: %s", coordinator.serial_number, device_capabilities
    )

    # Check if device has oscillation capability
    if "AdvanceOscillationDay1" in device_capabilities:
        _LOGGER.info(
            "Adding oscillation angle controls for %s", coordinator.serial_number
        )
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
        self._attr_translation_key = "sleep_timer"
        self._attr_icon = "mdi:timer"
        self._attr_mode = NumberMode.BOX
        self._attr_native_min_value = 0
        self._attr_native_max_value = 540  # 9 hours in minutes
        self._attr_native_step = 15  # 15-minute increments
        self._attr_native_unit_of_measurement = "min"
        self._timer_polling_task: asyncio.Task | None = None

    async def async_added_to_hass(self) -> None:
        """Entity added to hass."""
        await super().async_added_to_hass()
        # Start minimal polling when timer is active (vendor app behavior)
        self._start_timer_polling_if_needed()

    async def async_will_remove_from_hass(self) -> None:
        """Entity will be removed from hass."""
        if hasattr(self, "_timer_polling_task") and self._timer_polling_task:
            self._timer_polling_task.cancel()
        await super().async_will_remove_from_hass()

    def _start_timer_polling_if_needed(self) -> None:
        """Start polling only when timer is active, like vendor app."""
        if self._timer_polling_task and not self._timer_polling_task.done():
            return  # Already running

        # Check if timer is currently active
        if self.coordinator.device:
            product_state = self.coordinator.data.get("product-state", {})
            timer_data = self.coordinator.device._get_current_value(
                product_state, "sltm", "OFF"
            )
            if timer_data != "OFF":
                try:
                    timer_value = int(timer_data)
                    if timer_value > 0:
                        _LOGGER.debug(
                            "Starting timer polling for active timer (%s min) on %s",
                            timer_value,
                            self.coordinator.serial_number,
                        )
                        self._timer_polling_task = asyncio.create_task(
                            self._poll_timer_updates()
                        )
                except (ValueError, TypeError):
                    pass

    async def _poll_timer_updates(self) -> None:
        """Poll for timer updates when timer is active (vendor app behavior)."""
        try:
            # Device reports whole minutes rounded down, so timing is unpredictable
            # Use more frequent polling initially to catch minute transitions reliably
            await self._do_frequent_initial_polling()

            # Then continue with regular 60-second intervals
            await self._do_regular_polling()
        except asyncio.CancelledError:
            _LOGGER.debug(
                "Timer polling cancelled for %s", self.coordinator.serial_number
            )
        except asyncio.CancelledError:
            _LOGGER.debug(
                "Timer polling task cancelled for %s", self.coordinator.serial_number
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.warning(
                "Communication error during timer polling for %s: %s",
                self.coordinator.serial_number,
                err
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error in timer polling for %s: %s",
                self.coordinator.serial_number,
                err
            )

    async def _do_frequent_initial_polling(self) -> None:
        """Do frequent polling for first few minutes to catch transitions."""
        # Poll every 30 seconds for the first 3 minutes to catch transitions
        for i in range(6):  # 6 polls over 3 minutes
            await asyncio.sleep(30)

            if not await self._poll_timer_once(f"initial poll {i + 1}/6"):
                return

    async def _do_regular_polling(self) -> None:
        """Continue with regular 60-second polling intervals."""
        while True:
            await asyncio.sleep(60)  # Wait 1 minute

            if not await self._poll_timer_once("regular poll"):
                return

    async def _poll_timer_once(self, poll_type: str) -> bool:
        """Poll timer once and return False if timer is off or device unavailable."""
        if not (self.coordinator.device and self.coordinator.device.is_connected):
            return False

        product_state = self.coordinator.data.get("product-state", {})
        timer_data = self.coordinator.device._get_current_value(
            product_state, "sltm", "OFF"
        )

        if timer_data == "OFF" or timer_data == "0":
            _LOGGER.debug(
                "Timer finished or turned off for %s", self.coordinator.serial_number
            )
            return False

        _LOGGER.debug(
            "Timer %s for %s: %s min",
            poll_type,
            self.coordinator.serial_number,
            timer_data,
        )
        await self.coordinator.device._request_current_state()
        return True

    def _stop_timer_polling(self) -> None:
        """Stop timer polling task."""
        if self._timer_polling_task and not self._timer_polling_task.done():
            self._timer_polling_task.cancel()
            self._timer_polling_task = None
            _LOGGER.debug(
                "Stopped sleep timer polling for %s", self.coordinator.serial_number
            )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "Sleep timer entity _handle_coordinator_update called for %s",
            self.coordinator.serial_number,
        )
        if self.coordinator.device:
            # Get sleep timer from device state (sltm)
            product_state = self.coordinator.data.get("product-state", {})
            try:
                timer_data = self.coordinator.device._get_current_value(
                    product_state, "sltm", "OFF"
                )
                if timer_data == "OFF":
                    device_value = 0
                else:
                    try:
                        # Convert timer data to minutes
                        device_value = int(timer_data)
                    except (ValueError, TypeError):
                        device_value = 0

                _LOGGER.debug(
                    "TIMER DEBUG: Updating sleep timer entity from %s to %s for %s (coordinator update)",
                    self._attr_native_value,
                    device_value,
                    self.coordinator.serial_number,
                )
                self._attr_native_value = device_value

                # Start polling if timer is now active (handles vendor app timer changes)
                if device_value > 0:
                    self._start_timer_polling_if_needed()
                else:
                    self._stop_timer_polling()

            except (KeyError, AttributeError) as err:
                _LOGGER.debug(
                    "Sleep timer data not available for %s: %s",
                    self.coordinator.serial_number,
                    err,
                )
                self._attr_native_value = 0
            except (ValueError, TypeError) as err:
                _LOGGER.warning(
                    "Invalid sleep timer data format for %s: %s",
                    self.coordinator.serial_number,
                    err,
                )
                self._attr_native_value = 0
            except Exception as err:
                _LOGGER.error(
                    "Unexpected error processing sleep timer update for %s: %s",
                    self.coordinator.serial_number,
                    err,
                )
                self._attr_native_value = 0
        else:
            self._attr_native_value = None
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        """Set the sleep timer."""
        if not self.coordinator.device:
            return

        try:
            minutes = int(value)
            _LOGGER.debug(
                "Setting sleep timer to %s minutes for %s",
                minutes,
                self.coordinator.serial_number,
            )

            # Send the command to the device
            await self.coordinator.device.set_sleep_timer(minutes)

            if minutes > 0:
                # Wait for device to process the command, then poll to get actual value
                _LOGGER.debug(
                    "Sleep timer set, waiting 15s then polling for actual device value"
                )
                await asyncio.sleep(15)

                # Force a poll to get the device's actual timer value
                await self.coordinator.device._request_current_state()

                # Wait a bit more for the coordinator update, then start polling
                await asyncio.sleep(5)
                self._start_timer_polling_if_needed()
            else:
                # Timer turned off, stop polling and set to 0
                self._stop_timer_polling()
                self._attr_native_value = 0
                self.async_write_ha_state()

        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting sleep timer to %s minutes for %s: %s",
                int(value),
                self.coordinator.serial_number,
                err,
            )
        except ValueError as err:
            _LOGGER.error(
                "Invalid sleep timer value %s for %s: %s",
                value,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting sleep timer to %s minutes for %s: %s",
                int(value),
                self.coordinator.serial_number,
                err,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:  # type: ignore[return]
        """Return sleep timer state attributes for scene support."""
        if not self.coordinator.device:
            return None

        attributes = {}
        product_state = self.coordinator.data.get("product-state", {})

        # Sleep timer state for scene support
        native_value: float | None = self._attr_native_value
        attributes["sleep_timer_minutes"] = native_value  # type: ignore[assignment]

        # Raw device state
        sltm = self.coordinator.device._get_current_value(product_state, "sltm", "OFF")
        attributes["sleep_timer_raw"] = sltm  # type: ignore[assignment]
        attributes["sleep_timer_enabled"] = sltm != "OFF"

        return attributes


class DysonOscillationLowerAngleNumber(DysonEntity, NumberEntity):
    """Number entity for oscillation lower angle control."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the oscillation lower angle number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_oscillation_lower_angle"
        self._attr_translation_key = "oscillation_low_angle"
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
            angle_data = self.coordinator.device._get_current_value(
                product_state, "osal", "0000"
            )
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
            upper_angle_data = self.coordinator.data.get("product-state", {}).get(
                "osau", "0350"
            )
            upper_angle = int(upper_angle_data.lstrip("0") or "350")

            # Ensure lower angle is less than upper angle
            lower_angle = min(int(value), upper_angle - 5)

            # Use device method directly
            await self.coordinator.device.set_oscillation_angles(
                lower_angle, upper_angle
            )
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug(
                "Set oscillation lower angle to %s for %s",
                lower_angle,
                self.coordinator.serial_number,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting oscillation lower angle to %s for %s: %s",
                value,
                self.coordinator.serial_number,
                err,
            )
        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "Device data unavailable for oscillation lower angle on %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid oscillation lower angle value %s for %s: %s",
                value,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting oscillation lower angle to %s for %s: %s",
                value,
                self.coordinator.serial_number,
                err,
            )


class DysonOscillationUpperAngleNumber(DysonEntity, NumberEntity):
    """Number entity for oscillation upper angle control."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the oscillation upper angle number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_oscillation_upper_angle"
        self._attr_translation_key = "oscillation_high_angle"
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
            angle_data = self.coordinator.device._get_current_value(
                product_state, "osau", "0350"
            )
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
            lower_angle_data = self.coordinator.data.get("product-state", {}).get(
                "osal", "0000"
            )
            lower_angle = int(lower_angle_data.lstrip("0") or "0")

            # Ensure upper angle is greater than lower angle
            upper_angle = max(int(value), lower_angle + 5)

            # Use device method directly
            await self.coordinator.device.set_oscillation_angles(
                lower_angle, upper_angle
            )
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug(
                "Set oscillation upper angle to %s for %s",
                upper_angle,
                self.coordinator.serial_number,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting oscillation upper angle to %s for %s: %s",
                value,
                self.coordinator.serial_number,
                err,
            )
        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "Device data unavailable for oscillation upper angle on %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid oscillation upper angle value %s for %s: %s",
                value,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting oscillation upper angle to %s for %s: %s",
                value,
                self.coordinator.serial_number,
                err,
            )


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
            lower_data = self.coordinator.device._get_current_value(
                product_state, "osal", "0000"
            )
            upper_data = self.coordinator.device._get_current_value(
                product_state, "osau", "0350"
            )
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
            lower_data = self.coordinator.device._get_current_value(
                product_state, "osal", "0000"
            )
            upper_data = self.coordinator.device._get_current_value(
                product_state, "osau", "0350"
            )
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
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting oscillation center angle to %s for %s: %s",
                value,
                self.coordinator.serial_number,
                err,
            )
        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "Device data unavailable for oscillation center angle on %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid oscillation center angle value %s for %s: %s",
                value,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting oscillation center angle to %s for %s: %s",
                value,
                self.coordinator.serial_number,
                err,
            )


class DysonOscillationAngleSpanNumber(DysonEntity, NumberEntity):
    """Number entity for oscillation angle span control."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the oscillation angle span number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_oscillation_angle_span"
        self._attr_name = "Oscillation Angle"
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
            lower_data = self.coordinator.device._get_current_value(
                product_state, "osal", "0000"
            )
            upper_data = self.coordinator.device._get_current_value(
                product_state, "osau", "0350"
            )
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
            lower_data = self.coordinator.device._get_current_value(
                product_state, "osal", "0000"
            )
            upper_data = self.coordinator.device._get_current_value(
                product_state, "osau", "0350"
            )
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
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting oscillation angle span to %s for %s: %s",
                value,
                self.coordinator.serial_number,
                err,
            )
        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "Device data unavailable for oscillation angle span on %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid oscillation angle span value %s for %s: %s",
                value,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting oscillation angle span to %s for %s: %s",
                value,
                self.coordinator.serial_number,
                err,
            )
