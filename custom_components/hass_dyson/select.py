"""Select platform for Dyson integration."""

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

    # Fan control mode moved to fan platform preset modes

    # Add additional selects based on capabilities - temporarily enable all for testing
    device_capabilities = coordinator.device_capabilities

    # Temporarily enable oscillation for all devices for testing
    if "AdvanceOscillationDay1" in device_capabilities or True:
        entities.append(DysonOscillationModeSelect(coordinator))

    if "Heating" in device_capabilities:
        entities.append(DysonHeatingModeSelect(coordinator))

    async_add_entities(entities, True)


class DysonFanControlModeSelect(DysonEntity, SelectEntity):
    """Select entity for fan control mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the fan control mode select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_fan_control_mode"
        self._attr_name = f"{coordinator.device_name} Fan Control Mode"
        self._attr_icon = "mdi:fan-auto"

        # For manual devices, only show Auto and Manual (no Sleep)
        connection_type = coordinator.config_entry.data.get("connection_type", "unknown")
        if connection_type == "local_only":
            self._attr_options = ["Auto", "Manual"]
        else:
            self._attr_options = ["Auto", "Manual", "Sleep"]

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            product_state = self.coordinator.data.get("product-state", {})

            # Get air quality mode from device state (auto mode)
            auto_mode = self.coordinator.device._get_current_value(product_state, "auto", "OFF")
            night_mode = self.coordinator.device._get_current_value(product_state, "nmod", "OFF")

            # For manual devices, Sleep mode is handled by Night Mode switch
            connection_type = self.coordinator.config_entry.data.get("connection_type", "unknown")
            if connection_type == "local_only":
                if auto_mode == "ON":
                    self._attr_current_option = "Auto"
                else:
                    self._attr_current_option = "Manual"
            else:
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
                await self.coordinator.device.set_auto_mode(True)
            elif option == "Sleep":
                # Only for cloud devices
                await self.coordinator.device.set_night_mode(True)
                await self.coordinator.device.set_auto_mode(False)
            else:  # Manual
                await self.coordinator.device.set_auto_mode(False)

            # No need to refresh - MQTT provides real-time updates
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
        self._attr_name = f"{coordinator.device_name} Oscillation"  # Renamed from "Oscillation Mode"
        self._attr_icon = "mdi:rotate-3d-variant"
        self._attr_options = ["Off", "45°", "90°", "180°", "350°", "Custom"]
        # Hybrid approach: event-driven + state-based center preservation
        self._saved_center_angle = None
        self._last_known_mode = None  # Track transitions for event-driven logic
        # Store preferred center points for each preset mode
        self._preferred_centers = {
            "45°": 175,  # Default centers
            "90°": 175,
            "180°": 175,
        }
        # Track the last known non-350° mode for center restoration
        self._last_preset_mode = None

    def _calculate_current_center(self) -> int:
        """Calculate current center point from device state."""
        if not self.coordinator.device:
            return 175  # Default center

        product_state = self.coordinator.data.get("product-state", {})

        try:
            # Try to get lower/upper angles first
            lower_data = self.coordinator.device._get_current_value(product_state, "osal", "0000")
            upper_data = self.coordinator.device._get_current_value(product_state, "osau", "0350")
            lower_angle = int(lower_data.lstrip("0") or "0")
            upper_angle = int(upper_data.lstrip("0") or "350")
            return (lower_angle + upper_angle) // 2
        except (ValueError, TypeError):
            # Fallback to ancp if available
            try:
                angle_data = self.coordinator.device._get_current_value(product_state, "ancp", "0175")
                return int(angle_data.lstrip("0") or "175")
            except (ValueError, TypeError):
                return 175  # Ultimate fallback

    def _detect_mode_from_angles(self) -> str:
        """Detect current oscillation mode from device angles."""
        if not self.coordinator.device:
            return "Off"

        product_state = self.coordinator.data.get("product-state", {})
        oson = self.coordinator.device._get_current_value(product_state, "oson", "OFF")

        if oson == "OFF":
            return "Off"

        try:
            lower_data = self.coordinator.device._get_current_value(product_state, "osal", "0000")
            upper_data = self.coordinator.device._get_current_value(product_state, "osau", "0350")
            lower_angle = int(lower_data.lstrip("0") or "0")
            upper_angle = int(upper_data.lstrip("0") or "350")
            angle_span = upper_angle - lower_angle

            # Check for preset matches with tolerance
            # 350° mode is detected by near-maximum span (340-350°) regardless of exact position
            if angle_span >= 340 and angle_span <= 350:
                return "350°"
            elif abs(angle_span - 180) <= 5:
                return "180°"
            elif abs(angle_span - 90) <= 5:
                return "90°"
            elif abs(angle_span - 45) <= 5:
                return "45°"
            else:
                return "Custom"
        except (ValueError, TypeError):
            return "Custom"

    def _should_save_center_on_state_change(self, new_mode: str) -> bool:
        """Check if we should save center due to external state change to 350° mode."""
        return (
            new_mode == "350°"
            and self._last_known_mode != "350°"
            and self._last_known_mode is not None
            and self._saved_center_angle is None  # Only save if we haven't already saved
        )

    def _should_restore_center_on_state_change(self, new_mode: str) -> bool:
        """Check if we should restore center due to external state change from 350° mode."""
        return (
            self._last_known_mode == "350°"
            and new_mode != "350°"
            and new_mode != "Off"
            and self._saved_center_angle is not None
        )

    def _calculate_angles_for_preset(self, preset_angle: int, current_center: int = 175) -> tuple[int, int]:
        """Calculate lower and upper angles for a preset mode, with center point as authoritative."""
        if preset_angle == 350:
            # Full range oscillation
            return 0, 350

        # Center point is authoritative - calculate angles to preserve it exactly
        half_span = preset_angle / 2.0  # Use float division for precision

        # Calculate ideal lower and upper angles
        ideal_lower = current_center - half_span
        ideal_upper = current_center + half_span

        # Round to integers while preserving the center as much as possible
        lower = int(round(ideal_lower))
        upper = int(round(ideal_upper))

        # Ensure the span is exactly the preset angle
        actual_span = upper - lower
        if actual_span != preset_angle:
            # Adjust upper to get exact span while keeping center as close as possible
            upper = lower + preset_angle

        # Handle boundary constraints - center point wins
        if lower < 0:
            # Shift entire range right to fit bounds
            shift = -lower
            lower = 0
            upper = min(350, preset_angle)  # Ensure we don't exceed bounds
            # If we can't fit the full span, compress symmetrically around center
            if upper > 350:
                upper = 350
                lower = max(0, 350 - preset_angle)
        elif upper > 350:
            # Shift entire range left to fit bounds
            upper = 350
            lower = max(0, 350 - preset_angle)

        # Final verification: if we had to compress due to bounds,
        # ensure we're still as centered as possible within constraints
        if lower == 0 or upper == 350:
            # We hit a boundary - calculate best centered position within constraints
            available_span = upper - lower
            if available_span < preset_angle:
                # We had to compress the span due to boundary limits
                # Keep the result as calculated above
                pass
            else:
                # We have room to center better
                actual_center = (lower + upper) / 2.0
                if actual_center != current_center:
                    # Try to shift to get closer to target center
                    center_diff = current_center - actual_center
                    max_shift_left = lower
                    max_shift_right = 350 - upper

                    if center_diff > 0 and max_shift_right > 0:
                        # Need to shift right
                        shift = min(center_diff, max_shift_right)
                        lower += int(shift)
                        upper += int(shift)
                    elif center_diff < 0 and max_shift_left > 0:
                        # Need to shift left
                        shift = min(-center_diff, max_shift_left)
                        lower -= int(shift)
                        upper -= int(shift)

        return int(lower), int(upper)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator with hybrid center preservation."""
        if not self.coordinator.device:
            self._attr_current_option = None
            super()._handle_coordinator_update()
            return

        # Detect current mode from device state
        detected_mode = self._detect_mode_from_angles()

        # Hybrid approach: Handle state-based center preservation for external changes
        if self._should_save_center_on_state_change(detected_mode):
            current_center = self._calculate_current_center()
            self._saved_center_angle = current_center
            _LOGGER.info(
                "STATE-BASED: SAVING center angle %s on external change to 350° mode (from %s)",
                current_center,
                self._last_known_mode,
            )
        elif self._should_restore_center_on_state_change(detected_mode):
            _LOGGER.info(
                "STATE-BASED: External change detected from 350° mode to %s with saved center %s",
                detected_mode,
                self._saved_center_angle,
            )
            # Note: We don't automatically restore here - we just log it
            # The user would need to use the entity to get the restoration behavior

        # Update the current option
        self._attr_current_option = detected_mode

        # Track mode changes for next iteration
        self._last_known_mode = detected_mode

        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Select the oscillation mode with event-driven center preservation."""
        if not self.coordinator.device:
            return

        try:
            if option == "Off":
                await self.coordinator.device.set_oscillation(False)
                return

            if option == "Custom":
                # For Custom, just turn on oscillation with current angle settings
                await self.coordinator.device.set_oscillation(True)
                return

            # EVENT-DRIVEN: Handle center preservation for entity-driven changes
            current_mode = self._attr_current_option or "Off"

            # Save center point when entering 350° mode via entity
            if option == "350°" and current_mode != "350°":
                current_center = self._calculate_current_center()
                self._saved_center_angle = current_center
                _LOGGER.info(
                    "EVENT-DRIVEN: SAVING center angle %s when selecting 350° mode (from %s)",
                    current_center,
                    current_mode,
                )

            # Calculate angles for the selected preset
            preset_angle = int(option.replace("°", ""))

            if preset_angle == 350:
                # Full range oscillation
                lower_angle, upper_angle = 0, 350
            else:
                # Determine center to use for angle calculation
                center_to_use = self._calculate_current_center()  # Default: current center

                # EVENT-DRIVEN: Restore center when leaving 350° mode via entity
                if current_mode == "350°" and self._saved_center_angle is not None:
                    center_to_use = self._saved_center_angle
                    _LOGGER.info(
                        "EVENT-DRIVEN: RESTORING saved center angle %s when leaving 350° mode (target: %s°)",
                        center_to_use,
                        preset_angle,
                    )
                    self._saved_center_angle = None  # Clear after use
                else:
                    _LOGGER.info(
                        "EVENT-DRIVEN: Using current center angle %s for preset %s° (from %s)",
                        center_to_use,
                        preset_angle,
                        current_mode,
                    )

                # Calculate coordinated angles
                lower_angle, upper_angle = self._calculate_angles_for_preset(preset_angle, center_to_use)
                calculated_center = (lower_angle + upper_angle) / 2.0
                _LOGGER.info(
                    "Calculated angles for %s°: lower=%s, upper=%s, resulting_center=%.1f (target_center=%s, diff=%.1f)",
                    preset_angle,
                    lower_angle,
                    upper_angle,
                    calculated_center,
                    center_to_use,
                    calculated_center - center_to_use,
                )

            # Apply the calculated angles
            await self.coordinator.device.set_oscillation_angles(lower_angle, upper_angle)

            _LOGGER.debug(
                "Set oscillation mode to %s (lower: %s, upper: %s) for %s",
                option,
                lower_angle,
                upper_angle,
                self.coordinator.serial_number,
            )

        except Exception as err:
            _LOGGER.error("Failed to set oscillation mode for %s: %s", self.coordinator.serial_number, err)


class DysonHeatingModeSelect(DysonEntity, SelectEntity):
    """Select entity for heating mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the heating mode select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_heating_mode"
        self._attr_name = f"{coordinator.device_name} Heating Mode"
        self._attr_icon = "mdi:radiator"
        self._attr_options = ["Off", "Heating", "Auto Heat"]

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get heating mode from device state (hmod)
            product_state = self.coordinator.data.get("product-state", {})
            hmod = self.coordinator.device._get_current_value(product_state, "hmod", "OFF")
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

            await self.coordinator.device.set_heating_mode(mode_value)
            _LOGGER.debug("Set heating mode to %s for %s", option, self.coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to set heating mode for %s: %s", self.coordinator.serial_number, err)
