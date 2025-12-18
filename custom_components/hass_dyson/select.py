"""Select platform for Dyson integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_CATEGORY_ROBOT,
    DOMAIN,
    ROBOT_POWER_OPTIONS_360_EYE,
    ROBOT_POWER_OPTIONS_HEURIST,
    ROBOT_POWER_OPTIONS_VIS_NAV,
)
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

    entities: list[SelectEntity] = []

    # Fan control mode moved to fan platform preset modes

    # Add additional selects based on capabilities
    device_capabilities = coordinator.device_capabilities

    # Only show oscillation mode select for devices with advanced oscillation capability
    if "AdvanceOscillationDay1" in device_capabilities:
        entities.append(DysonOscillationModeSelect(coordinator))
    elif "AdvanceOscillationDay0" in device_capabilities:
        entities.append(DysonOscillationModeDay0Select(coordinator))

    # Add water hardness select for humidifier devices
    if "Humidifier" in device_capabilities:
        entities.append(DysonWaterHardnessSelect(coordinator))

    # Add robot vacuum power level selects based on device category and capabilities
    device_categories = getattr(coordinator, "device_category", [])
    if isinstance(device_categories, list) and any(
        cat == DEVICE_CATEGORY_ROBOT for cat in device_categories
    ):
        # Determine which power level select to show based on capabilities
        # Since we don't have specific capability names yet, we'll need to detect
        # based on other device information. For now, create placeholder logic.

        # TODO: Replace with actual capability detection once we know the capability names
        # For now, we'll create all three and let them determine their own availability

        if "RobotPower360Eye" in device_capabilities:
            entities.append(DysonRobotPower360EyeSelect(coordinator))
        elif "RobotPowerHeurist" in device_capabilities:
            entities.append(DysonRobotPowerHeuristSelect(coordinator))
        elif "RobotPowerVisNav" in device_capabilities:
            entities.append(DysonRobotPowerVisNavSelect(coordinator))
        else:
            # Default fallback - create a generic robot power select
            # This will need to be refined once we have real device data
            _LOGGER.debug(
                "Robot device %s has unknown power capabilities, using generic power select",
                coordinator.serial_number,
            )
            entities.append(DysonRobotPowerGenericSelect(coordinator))

    # Note: Heating mode control is now integrated into the fan entity's preset modes
    # No separate heating mode select needed

    async_add_entities(entities, True)


class DysonFanControlModeSelect(DysonEntity, SelectEntity):
    """Select entity for fan control mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the fan control mode select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_fan_control_mode"
        self._attr_translation_key = "fan_control_mode"
        self._attr_icon = "mdi:fan-auto"

        # For manual devices, only show Auto and Manual (no Sleep)
        connection_type = coordinator.config_entry.data.get(
            "connection_type", "unknown"
        )
        if connection_type == "local_only":
            self._attr_options = ["Auto", "Manual"]
        else:
            self._attr_options = ["Auto", "Manual", "Sleep"]

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            product_state = self.coordinator.data.get("product-state", {})

            # Get air quality mode from device state (auto mode)
            auto_mode = self.coordinator.device.get_state_value(
                product_state, "auto", "OFF"
            )
            night_mode = self.coordinator.device.get_state_value(
                product_state, "nmod", "OFF"
            )

            # For manual devices, Sleep mode is handled by Night Mode switch
            connection_type = self.coordinator.config_entry.data.get(
                "connection_type", "unknown"
            )
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
            _LOGGER.debug(
                "Set air quality mode to %s for %s",
                option,
                self.coordinator.serial_number,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting air quality mode to '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )
        except ValueError as err:
            _LOGGER.error(
                "Invalid air quality mode '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting air quality mode to '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )


class DysonOscillationModeSelect(DysonEntity, SelectEntity):
    """Select entity for oscillation mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the oscillation mode select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_oscillation_mode"
        self._attr_translation_key = "oscillation_mode"
        self._attr_icon = "mdi:rotate-3d-variant"
        self._attr_options = ["Off", "45°", "90°", "180°", "350°", "Custom"]
        # Hybrid approach: event-driven + state-based center preservation
        self._saved_center_angle: int | None = None
        self._last_known_mode: str | None = (
            None  # Track transitions for event-driven logic
        )
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
            lower_data = self.coordinator.device.get_state_value(
                product_state, "osal", "0000"
            )
            upper_data = self.coordinator.device.get_state_value(
                product_state, "osau", "0350"
            )
            lower_angle = int(lower_data.lstrip("0") or "0")
            upper_angle = int(upper_data.lstrip("0") or "350")
            return (lower_angle + upper_angle) // 2
        except (ValueError, TypeError):
            # Fallback to ancp if available
            try:
                angle_data = self.coordinator.device.get_state_value(
                    product_state, "ancp", "0175"
                )
                return int(angle_data.lstrip("0") or "175")
            except (ValueError, TypeError):
                return 175  # Ultimate fallback

    def _detect_mode_from_angles(self) -> str:
        """Detect current oscillation mode from device angles."""
        if not self.coordinator.device:
            return "Off"

        product_state = self.coordinator.data.get("product-state", {})
        oson = self.coordinator.device.get_state_value(product_state, "oson", "OFF")

        if oson == "OFF":
            return "Off"

        try:
            lower_data = self.coordinator.device.get_state_value(
                product_state, "osal", "0000"
            )
            upper_data = self.coordinator.device.get_state_value(
                product_state, "osau", "0350"
            )
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
            and self._saved_center_angle
            is None  # Only save if we haven't already saved
        )

    def _should_restore_center_on_state_change(self, new_mode: str) -> bool:
        """Check if we should restore center due to external state change from 350° mode."""
        return (
            self._last_known_mode == "350°"
            and new_mode != "350°"
            and new_mode != "Off"
            and self._saved_center_angle is not None
        )

    def _calculate_angles_for_preset(
        self, preset_angle: int, current_center: int = 175
    ) -> tuple[int, int]:
        """Calculate lower and upper angles for a preset mode, with center point as authoritative."""
        if preset_angle == 350:
            # Full range oscillation
            return 0, 350

        # Calculate initial angles from center point
        lower, upper = self._calculate_initial_angles(preset_angle, current_center)

        # Apply boundary constraints
        return self._apply_boundary_constraints(
            lower, upper, preset_angle, current_center
        )

    def _calculate_initial_angles(
        self, preset_angle: int, current_center: int
    ) -> tuple[int, int]:
        """Calculate initial lower and upper angles from center point."""
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

        return lower, upper

    def _apply_boundary_constraints(
        self, lower: int, upper: int, preset_angle: int, current_center: int
    ) -> tuple[int, int]:
        """Apply boundary constraints to angle range."""
        # Handle boundary constraints - center point wins
        if lower < 0:
            lower, upper = self._handle_lower_boundary_violation(preset_angle)
        elif upper > 350:
            lower, upper = self._handle_upper_boundary_violation(preset_angle)

        # Final verification and centering within constraints
        return self._optimize_centering_within_bounds(
            lower, upper, preset_angle, current_center
        )

    def _handle_lower_boundary_violation(self, preset_angle: int) -> tuple[int, int]:
        """Handle case where lower bound is violated."""
        # Shift entire range right to fit bounds
        lower = 0
        upper = min(350, preset_angle)  # Ensure we don't exceed bounds
        # If we can't fit the full span, compress symmetrically around center
        if upper > 350:
            upper = 350
            lower = max(0, 350 - preset_angle)
        return lower, upper

    def _handle_upper_boundary_violation(self, preset_angle: int) -> tuple[int, int]:
        """Handle case where upper bound is violated."""
        # Shift entire range left to fit bounds
        upper = 350
        lower = max(0, 350 - preset_angle)
        return lower, upper

    def _optimize_centering_within_bounds(
        self, lower: int, upper: int, preset_angle: int, current_center: int
    ) -> tuple[int, int]:
        """Optimize centering within boundary constraints."""
        # Final verification: if we had to compress due to bounds,
        # ensure we're still as centered as possible within constraints
        if lower == 0 or upper == 350:
            # We hit a boundary - calculate best centered position within constraints
            available_span = upper - lower
            if available_span >= preset_angle:
                # We have room to center better
                lower, upper = self._recenter_within_available_space(
                    lower, upper, current_center
                )

        return int(lower), int(upper)

    def _recenter_within_available_space(
        self, lower: int, upper: int, current_center: int
    ) -> tuple[int, int]:
        """Recenter the angle range within available space."""
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

        return lower, upper

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
                center_to_use = (
                    self._calculate_current_center()
                )  # Default: current center

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
                lower_angle, upper_angle = self._calculate_angles_for_preset(
                    preset_angle, center_to_use
                )
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
            await self.coordinator.device.set_oscillation_angles(
                lower_angle, upper_angle
            )

            _LOGGER.debug(
                "Set oscillation mode to %s (lower: %s, upper: %s) for %s",
                option,
                lower_angle,
                upper_angle,
                self.coordinator.serial_number,
            )

        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting oscillation mode to '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )
        except ValueError as err:
            _LOGGER.error(
                "Invalid oscillation mode '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting oscillation mode to '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return oscillation mode state attributes for scene support."""
        if not self.coordinator.device:
            return None

        attributes = {}
        product_state = self.coordinator.data.get("product-state", {})

        # Current oscillation mode for scene support
        attributes["oscillation_mode"] = self._attr_current_option

        # Oscillation state details
        oson = self.coordinator.device.get_state_value(product_state, "oson", "OFF")
        oscillation_enabled: bool = oson == "ON"
        attributes["oscillation_enabled"] = oscillation_enabled  # type: ignore[assignment]

        # Current angle configuration
        try:
            lower_data = self.coordinator.device.get_state_value(
                product_state, "osal", "0000"
            )
            upper_data = self.coordinator.device.get_state_value(
                product_state, "osau", "0350"
            )
            center_data = self.coordinator.device.get_state_value(
                product_state, "ancp", "0175"
            )

            lower_angle: int = int(lower_data.lstrip("0") or "0")
            upper_angle: int = int(upper_data.lstrip("0") or "350")
            center_angle: int = int(center_data.lstrip("0") or "175")
            span: int = upper_angle - lower_angle

            attributes["oscillation_angle_low"] = lower_angle  # type: ignore[assignment]
            attributes["oscillation_angle_high"] = upper_angle  # type: ignore[assignment]
            attributes["oscillation_center"] = center_angle  # type: ignore[assignment]
            attributes["oscillation_span"] = span  # type: ignore[assignment]
        except (ValueError, TypeError):
            pass

        return attributes


class DysonOscillationModeDay0Select(DysonEntity, SelectEntity):
    """Select entity for oscillation mode (AdvanceOscillationDay0 capability)."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the oscillation mode select for Day0."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_oscillation_mode"
        self._attr_translation_key = "oscillation"
        self._attr_icon = "mdi:rotate-3d-variant"
        # Simplified to just the three working preset options
        self._attr_options = ["Off", "15°", "40°", "70°"]
        # Fixed center angle for Day0 - middle of allowed range (142°-212°)
        self._center_angle = 177

    def _detect_mode_from_angles(self) -> str:
        """Detect current oscillation mode from device ANCP value."""
        if not self.coordinator.device:
            return "Off"

        product_state = self.coordinator.data.get("product-state", {})
        oson = self.coordinator.device.get_state_value(product_state, "oson", "OFF")

        if oson == "OFF":
            return "Off"

        try:
            # Day0 devices use ancp (angle center point) to indicate the preset mode
            ancp_data = self.coordinator.device.get_state_value(
                product_state, "ancp", "0040"
            )
            ancp_value = int(ancp_data.lstrip("0") or "40")

            # Map ancp values to preset modes
            if ancp_value == 15:
                detected_mode = "15°"
            elif ancp_value == 40:
                detected_mode = "40°"
            elif ancp_value == 70:
                detected_mode = "70°"
            else:
                # Default to closest preset
                if ancp_value < 27:
                    detected_mode = "15°"
                elif ancp_value < 55:
                    detected_mode = "40°"
                else:
                    detected_mode = "70°"

            _LOGGER.debug(
                "Day0: Detected mode from ancp=%s -> '%s' for %s",
                ancp_value,
                detected_mode,
                self.coordinator.serial_number,
            )

            return detected_mode
        except (ValueError, TypeError):
            return "Off"

    def _get_day0_angles_and_ancp(self, preset_angle: int) -> tuple[int, int, int]:
        """Get fixed angles and ancp value for Day0 preset mode."""
        # Day0 devices use fixed physical angles but variable ancp
        # Based on MQTT trace: osal=157, osau=197, ancp=preset_value
        lower_angle = 157
        upper_angle = 197
        ancp_value = preset_angle

        _LOGGER.debug(
            "Day0: Fixed angles for %s° preset: %s°-%s° with ancp=%s for %s",
            preset_angle,
            lower_angle,
            upper_angle,
            ancp_value,
            self.coordinator.serial_number,
        )

        return lower_angle, upper_angle, ancp_value

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            detected_mode = self._detect_mode_from_angles()
            self._attr_current_option = detected_mode
        else:
            self._attr_current_option = None

        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Select the oscillation mode for Day0."""
        if not self.coordinator.device:
            return

        try:
            if option == "Off":
                await self.coordinator.device.set_oscillation(False)
                _LOGGER.debug(
                    "Day0: Turned off oscillation for %s",
                    self.coordinator.serial_number,
                )
                return

            # Get Day0 angles and ancp for the selected preset
            preset_angle = int(option.replace("°", ""))
            lower_angle, upper_angle, ancp_value = self._get_day0_angles_and_ancp(
                preset_angle
            )

            _LOGGER.debug(
                "Day0: Setting %s° mode for %s -> fixed angles %s°-%s° with ancp=%s",
                preset_angle,
                self.coordinator.serial_number,
                lower_angle,
                upper_angle,
                ancp_value,
            )

            # Apply the fixed angles and ancp using Day0-specific method
            await self.coordinator.device.set_oscillation_angles_day0(
                lower_angle, upper_angle, ancp_value
            )

            _LOGGER.debug(
                "Day0: Successfully set %s° oscillation mode for %s",
                preset_angle,
                self.coordinator.serial_number,
            )

        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting Day0 oscillation mode to '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )
        except ValueError as err:
            _LOGGER.error(
                "Invalid Day0 oscillation mode '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting Day0 oscillation mode to '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return oscillation mode state attributes for scene support."""
        if not self.coordinator.device:
            return None

        attributes = {}
        product_state = self.coordinator.data.get("product-state", {})

        # Current oscillation mode for scene support
        attributes["oscillation_mode"] = self._attr_current_option

        # Oscillation state details
        oson = self.coordinator.device.get_state_value(product_state, "oson", "OFF")
        oscillation_enabled: bool = oson == "ON"
        attributes["oscillation_enabled"] = oscillation_enabled  # type: ignore[assignment]

        # Current angle configuration
        try:
            lower_data = self.coordinator.device.get_state_value(
                product_state, "osal", "0000"
            )
            upper_data = self.coordinator.device.get_state_value(
                product_state, "osau", "0350"
            )

            lower_angle: int = int(lower_data.lstrip("0") or "0")
            upper_angle: int = int(upper_data.lstrip("0") or "350")
            span: int = upper_angle - lower_angle

            attributes["oscillation_angle_low"] = lower_angle  # type: ignore[assignment]
            attributes["oscillation_angle_high"] = upper_angle  # type: ignore[assignment]
            attributes["oscillation_center"] = self._center_angle  # type: ignore[assignment]
            attributes["oscillation_span"] = span  # type: ignore[assignment]
            attributes["oscillation_day0_mode"] = True  # type: ignore[assignment]
        except (ValueError, TypeError):
            pass

        return attributes


class DysonHeatingModeSelect(DysonEntity, SelectEntity):
    """Select entity for heating mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the heating mode select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_heating_mode"
        self._attr_translation_key = "heating_mode"
        self._attr_icon = "mdi:radiator"
        self._attr_options = ["Off", "Heating", "Auto Heat"]

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get heating mode from device state (hmod)
            product_state = self.coordinator.data.get("product-state", {})
            hmod = self.coordinator.device.get_state_value(product_state, "hmod", "OFF")
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
            _LOGGER.debug(
                "Set heating mode to %s for %s", option, self.coordinator.serial_number
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting heating mode to '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )
        except ValueError as err:
            _LOGGER.error(
                "Invalid heating mode '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting heating mode to '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return heating mode state attributes for scene support."""
        if not self.coordinator.device:
            return None

        attributes = {}
        product_state = self.coordinator.data.get("product-state", {})

        # Current heating mode for scene support
        attributes["heating_mode"] = self._attr_current_option

        # Device heating state details
        hmod = self.coordinator.device.get_state_value(product_state, "hmod", "OFF")
        attributes["heating_mode_raw"] = hmod
        heating_enabled: bool = hmod != "OFF"
        attributes["heating_enabled"] = heating_enabled  # type: ignore[assignment]

        # Include target temperature if available
        try:
            hmax = self.coordinator.device.get_state_value(
                product_state, "hmax", "2980"
            )
            temp_kelvin: float = int(hmax) / 10  # Device reports in 0.1K increments
            target_celsius: float = temp_kelvin - 273.15
            attributes["target_temperature"] = round(target_celsius, 1)  # type: ignore[assignment]
            attributes["target_temperature_kelvin"] = hmax
        except (ValueError, TypeError):
            pass

        return attributes


class DysonWaterHardnessSelect(DysonEntity, SelectEntity):
    """Select entity for water hardness setting on humidifier devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the water hardness select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_water_hardness"
        self._attr_translation_key = "water_hardness"
        self._attr_icon = "mdi:water-percent"
        self._attr_options = ["Soft", "Medium", "Hard"]

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            product_state = self.coordinator.data.get("product-state", {})

            # Get water hardness from device state
            water_hardness = self.coordinator.device.get_state_value(
                product_state,
                "wath",
                "1350",  # Default to Medium
            )

            # Map device values to display names
            if water_hardness == "2025":
                self._attr_current_option = "Soft"
            elif water_hardness == "1350":
                self._attr_current_option = "Medium"
            elif water_hardness == "0675":
                self._attr_current_option = "Hard"
            else:
                _LOGGER.warning(
                    "Unknown water hardness value '%s' for %s, defaulting to Medium",
                    water_hardness,
                    self.coordinator.serial_number,
                )
                self._attr_current_option = "Medium"
        else:
            self._attr_current_option = None

        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Select new water hardness option."""
        if not self.coordinator.device:
            return

        # Map display names to device values
        value_map = {
            "Soft": "2025",
            "Medium": "1350",
            "Hard": "0675",
        }

        if option not in value_map:
            _LOGGER.error(
                "Invalid water hardness option '%s' for %s. Valid options: %s",
                option,
                self.coordinator.serial_number,
                list(value_map.keys()),
            )
            return

        try:
            await self.coordinator.device.send_command(
                "STATE-SET", {"wath": value_map[option]}
            )

            # Update local state immediately for responsive UI
            self._attr_current_option = option
            self.async_write_ha_state()

            _LOGGER.debug(
                "Set water hardness to '%s' for %s",
                option,
                self.coordinator.serial_number,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting water hardness to '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )
        except ValueError as err:
            _LOGGER.error(
                "Invalid water hardness option '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting water hardness to '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return water hardness state attributes for scene support."""
        if not self.coordinator.device:
            return None

        attributes = {}
        product_state = self.coordinator.data.get("product-state", {})

        # Current water hardness for scene support
        attributes["water_hardness"] = self._attr_current_option

        # Raw device value
        wath = self.coordinator.device.get_state_value(product_state, "wath", "1350")
        attributes["water_hardness_raw"] = wath

        return attributes


class DysonRobotPower360EyeSelect(DysonEntity, SelectEntity):
    """Select entity for Dyson 360 Eye robot vacuum power level."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the 360 Eye robot power select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_robot_power_360_eye"
        self._attr_translation_key = "robot_power_360_eye"
        self._attr_name = "Power Level"
        self._attr_icon = "mdi:vacuum"
        self._attr_options = list(ROBOT_POWER_OPTIONS_360_EYE.values())
        self._attr_current_option = None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_current_option = None
            return

        # Get current robot power level from device state
        # TODO: Implement when we know the exact state field name
        # For now, default to the first option
        self._attr_current_option = list(ROBOT_POWER_OPTIONS_360_EYE.values())[0]
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected robot power level."""
        if not self.coordinator.device:
            _LOGGER.error("Device not available for power level change")
            return

        # Find the command value for the selected option
        command_value = None
        for cmd_val, display_name in ROBOT_POWER_OPTIONS_360_EYE.items():
            if display_name == option:
                command_value = cmd_val
                break

        if command_value is None:
            _LOGGER.error("Unknown power level option: %s", option)
            return

        try:
            _LOGGER.info(
                "Setting 360 Eye robot power to '%s' (%s) for %s",
                option,
                command_value,
                self.coordinator.serial_number,
            )

            # TODO: Implement robot power level command once we know the exact format
            # await self.coordinator.device.set_robot_power_level(command_value)

            # Update local state immediately for responsive UI
            self._attr_current_option = option
            self.async_write_ha_state()

            _LOGGER.debug(
                "Set 360 Eye robot power to '%s' for %s",
                option,
                self.coordinator.serial_number,
            )
        except Exception as err:
            _LOGGER.error(
                "Error setting 360 Eye robot power to '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )


class DysonRobotPowerHeuristSelect(DysonEntity, SelectEntity):
    """Select entity for Dyson 360 Heurist robot vacuum power level."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the 360 Heurist robot power select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_robot_power_heurist"
        self._attr_translation_key = "robot_power_heurist"
        self._attr_name = "Power Level"
        self._attr_icon = "mdi:vacuum"
        self._attr_options = list(ROBOT_POWER_OPTIONS_HEURIST.values())
        self._attr_current_option = None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_current_option = None
            return

        # Get current robot power level from device state
        # TODO: Implement when we know the exact state field name
        # For now, default to the first option
        self._attr_current_option = list(ROBOT_POWER_OPTIONS_HEURIST.values())[0]
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected robot power level."""
        if not self.coordinator.device:
            _LOGGER.error("Device not available for power level change")
            return

        # Find the command value for the selected option
        command_value = None
        for cmd_val, display_name in ROBOT_POWER_OPTIONS_HEURIST.items():
            if display_name == option:
                command_value = cmd_val
                break

        if command_value is None:
            _LOGGER.error("Unknown power level option: %s", option)
            return

        try:
            _LOGGER.info(
                "Setting 360 Heurist robot power to '%s' (%s) for %s",
                option,
                command_value,
                self.coordinator.serial_number,
            )

            # TODO: Implement robot power level command once we know the exact format
            # await self.coordinator.device.set_robot_power_level(command_value)

            # Update local state immediately for responsive UI
            self._attr_current_option = option
            self.async_write_ha_state()

            _LOGGER.debug(
                "Set 360 Heurist robot power to '%s' for %s",
                option,
                self.coordinator.serial_number,
            )
        except Exception as err:
            _LOGGER.error(
                "Error setting 360 Heurist robot power to '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )


class DysonRobotPowerVisNavSelect(DysonEntity, SelectEntity):
    """Select entity for Dyson 360 Vis Nav robot vacuum power level."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the 360 Vis Nav robot power select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_robot_power_vis_nav"
        self._attr_translation_key = "robot_power_vis_nav"
        self._attr_name = "Power Level"
        self._attr_icon = "mdi:vacuum"
        self._attr_options = list(ROBOT_POWER_OPTIONS_VIS_NAV.values())
        self._attr_current_option = None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_current_option = None
            return

        # Get current robot power level from device state
        # TODO: Implement when we know the exact state field name
        # For now, default to the first option
        self._attr_current_option = list(ROBOT_POWER_OPTIONS_VIS_NAV.values())[0]
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected robot power level."""
        if not self.coordinator.device:
            _LOGGER.error("Device not available for power level change")
            return

        # Find the command value for the selected option
        command_value = None
        for cmd_val, display_name in ROBOT_POWER_OPTIONS_VIS_NAV.items():
            if display_name == option:
                command_value = cmd_val
                break

        if command_value is None:
            _LOGGER.error("Unknown power level option: %s", option)
            return

        try:
            _LOGGER.info(
                "Setting 360 Vis Nav robot power to '%s' (%s) for %s",
                option,
                command_value,
                self.coordinator.serial_number,
            )

            # TODO: Implement robot power level command once we know the exact format
            # await self.coordinator.device.set_robot_power_level(command_value)

            # Update local state immediately for responsive UI
            self._attr_current_option = option
            self.async_write_ha_state()

            _LOGGER.debug(
                "Set 360 Vis Nav robot power to '%s' for %s",
                option,
                self.coordinator.serial_number,
            )
        except Exception as err:
            _LOGGER.error(
                "Error setting 360 Vis Nav robot power to '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )


class DysonRobotPowerGenericSelect(DysonEntity, SelectEntity):
    """Generic select entity for robot vacuum power level (fallback)."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the generic robot power select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_robot_power_generic"
        self._attr_translation_key = "robot_power_generic"
        self._attr_name = "Power Level"
        self._attr_icon = "mdi:vacuum"
        # Default to Heurist-style options as a reasonable fallback
        self._attr_options = list(ROBOT_POWER_OPTIONS_HEURIST.values())
        self._attr_current_option = None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_current_option = None
            return

        # Get current robot power level from device state
        # TODO: Implement when we know the exact state field name
        # For now, default to the first option
        self._attr_current_option = list(ROBOT_POWER_OPTIONS_HEURIST.values())[0]
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected robot power level."""
        if not self.coordinator.device:
            _LOGGER.error("Device not available for power level change")
            return

        # Find the command value for the selected option
        command_value = None
        for cmd_val, display_name in ROBOT_POWER_OPTIONS_HEURIST.items():
            if display_name == option:
                command_value = cmd_val
                break

        if command_value is None:
            _LOGGER.error("Unknown power level option: %s", option)
            return

        try:
            _LOGGER.info(
                "Setting generic robot power to '%s' (%s) for %s",
                option,
                command_value,
                self.coordinator.serial_number,
            )

            # TODO: Implement robot power level command once we know the exact format
            # await self.coordinator.device.set_robot_power_level(command_value)

            # Update local state immediately for responsive UI
            self._attr_current_option = option
            self.async_write_ha_state()

            _LOGGER.debug(
                "Set generic robot power to '%s' for %s",
                option,
                self.coordinator.serial_number,
            )
        except Exception as err:
            _LOGGER.error(
                "Error setting generic robot power to '%s' for %s: %s",
                option,
                self.coordinator.serial_number,
                err,
            )
