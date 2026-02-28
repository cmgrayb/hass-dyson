"""Comprehensive error handling tests for select entity module.

This test module targets uncovered exception handlers in select.py to improve
code coverage from 53% baseline. Focus areas:
1. async_select_option error paths (ConnectionError, TimeoutError, ValueError, Exception)
2. _handle_coordinator_update parsing errors (ValueError, TypeError)
3. Device state retrieval failures
4. Attribute calculation exceptions

Target: +5-7% coverage improvement
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.hass_dyson.select import (
    DysonFanControlModeSelect,
    DysonHeatingModeSelect,
    DysonOscillationModeDay0Select,
    DysonOscillationModeSelect,
    DysonRobotPower360EyeSelect,
    DysonRobotPowerGenericSelect,
    DysonRobotPowerHeuristSelect,
    DysonRobotPowerVisNavSelect,
    DysonWaterHardnessSelect,
)


class TestFanControlModeSelectErrorHandling:
    """Test error handling in DysonFanControlModeSelect."""

    @pytest.mark.asyncio
    async def test_async_select_option_connection_error_auto_mode(self):
        """Test ConnectionError handling when setting auto mode."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-SERIAL-123"
        coordinator.device = Mock()
        coordinator.device.set_auto_mode = AsyncMock(
            side_effect=ConnectionError("Connection lost")
        )
        coordinator.config_entry = Mock()
        coordinator.config_entry.data = {"connection_type": "cloud"}

        select = DysonFanControlModeSelect(coordinator)

        # Should not raise, error logged
        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Auto")

    @pytest.mark.asyncio
    async def test_async_select_option_timeout_error_sleep_mode(self):
        """Test TimeoutError handling when setting sleep mode."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-SERIAL-123"
        coordinator.device = Mock()
        coordinator.device.set_night_mode = AsyncMock(
            side_effect=TimeoutError("Request timeout")
        )
        coordinator.device.set_auto_mode = AsyncMock()
        coordinator.config_entry = Mock()
        coordinator.config_entry.data = {"connection_type": "cloud"}

        select = DysonFanControlModeSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Sleep")

    @pytest.mark.asyncio
    async def test_async_select_option_value_error_manual_mode(self):
        """Test ValueError handling when setting manual mode."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-SERIAL-123"
        coordinator.device = Mock()
        coordinator.device.set_auto_mode = AsyncMock(
            side_effect=ValueError("Invalid mode value")
        )
        coordinator.config_entry = Mock()
        coordinator.config_entry.data = {"connection_type": "local_only"}

        select = DysonFanControlModeSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Manual")

    @pytest.mark.asyncio
    async def test_async_select_option_generic_exception(self):
        """Test generic Exception handling in async_select_option."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-SERIAL-123"
        coordinator.device = Mock()
        coordinator.device.set_auto_mode = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )
        coordinator.config_entry = Mock()
        coordinator.config_entry.data = {"connection_type": "cloud"}

        select = DysonFanControlModeSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Auto")

    def test_handle_coordinator_update_no_device(self):
        """Test _handle_coordinator_update when device is None."""
        coordinator = Mock()
        coordinator.device = None
        coordinator.data = {}
        coordinator.config_entry = Mock()
        coordinator.config_entry.data = {"connection_type": "cloud"}

        select = DysonFanControlModeSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            select._handle_coordinator_update()

        assert select._attr_current_option is None


class TestOscillationModeSelectErrorHandling:
    """Test error handling in DysonOscillationModeSelect."""

    @pytest.mark.asyncio
    async def test_async_select_option_connection_error_45_degree(self):
        """Test ConnectionError when selecting 45° preset mode."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-SERIAL-456"
        coordinator.device = Mock()
        coordinator.device_capabilities = ["AdvanceOscillationDay1"]
        coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ConnectionError("Device unreachable")
        )
        coordinator.device.get_state_value.return_value = "0175"
        coordinator.data = {"product-state": {}}

        select = DysonOscillationModeSelect(coordinator)
        select._attr_current_option = "Off"

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("45°")

    @pytest.mark.asyncio
    async def test_async_select_option_timeout_error_90_degree(self):
        """Test TimeoutError when selecting 90° preset mode."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-SERIAL-456"
        coordinator.device = Mock()
        coordinator.device_capabilities = ["AdvanceOscillationDay1"]
        coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=TimeoutError("Operation timeout")
        )
        coordinator.device.get_state_value.return_value = "0175"
        coordinator.data = {"product-state": {}}

        select = DysonOscillationModeSelect(coordinator)
        select._attr_current_option = "90°"

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("90°")

    @pytest.mark.asyncio
    async def test_async_select_option_value_error_180_degree(self):
        """Test ValueError when selecting 180° preset mode."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-SERIAL-456"
        coordinator.device = Mock()
        coordinator.device_capabilities = ["AdvanceOscillationDay1"]
        coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ValueError("Invalid angle range")
        )
        coordinator.device.get_state_value.return_value = "0175"
        coordinator.data = {"product-state": {}}

        select = DysonOscillationModeSelect(coordinator)
        select._attr_current_option = "180°"

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("180°")

    @pytest.mark.asyncio
    async def test_async_select_option_generic_exception_350_degree(self):
        """Test generic Exception when selecting 350° mode."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-SERIAL-456"
        coordinator.device = Mock()
        coordinator.device_capabilities = ["AdvanceOscillationDay1"]
        coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=AttributeError("Missing device attribute")
        )
        coordinator.device.get_state_value.return_value = "0175"
        coordinator.data = {"product-state": {}}

        select = DysonOscillationModeSelect(coordinator)
        select._attr_current_option = "90°"

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("350°")

    @pytest.mark.asyncio
    async def test_async_select_option_off_mode_connection_error(self):
        """Test ConnectionError when turning off oscillation."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-SERIAL-456"
        coordinator.device = Mock()
        coordinator.device_capabilities = ["AdvanceOscillationDay1"]
        coordinator.device.set_oscillation = AsyncMock(
            side_effect=ConnectionError("Device disconnected")
        )

        select = DysonOscillationModeSelect(coordinator)
        select._attr_current_option = "45°"

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Off")

    @pytest.mark.asyncio
    async def test_async_select_option_custom_mode_error(self):
        """Test error handling when selecting Custom mode."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-SERIAL-456"
        coordinator.device = Mock()
        coordinator.device_capabilities = ["AdvanceOscillationDay1"]
        coordinator.device.set_oscillation = AsyncMock(
            side_effect=TimeoutError("Custom mode timeout")
        )

        select = DysonOscillationModeSelect(coordinator)
        select._attr_current_option = "90°"

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Custom")

    def test_calculate_sweep_midpoint_value_error(self):
        """Test _calculate_sweep_midpoint returns 175 when osal/osau cannot be parsed."""
        coordinator = Mock()
        coordinator.device = Mock()
        coordinator.device_capabilities = ["AdvanceOscillationDay1"]
        coordinator.device.get_state_value = Mock(side_effect=["INVALID", "INVALID"])
        coordinator.data = {"product-state": {}}

        select = DysonOscillationModeSelect(coordinator)

        midpoint = select._calculate_sweep_midpoint()
        assert midpoint == 175

    def test_calculate_sweep_midpoint_empty_strings(self):
        """Test _calculate_sweep_midpoint returns 175 when osal/osau are empty strings."""
        coordinator = Mock()
        coordinator.device = Mock()
        coordinator.device_capabilities = ["AdvanceOscillationDay1"]
        coordinator.device.get_state_value = Mock(side_effect=["", ""])
        coordinator.data = {"product-state": {}}

        select = DysonOscillationModeSelect(coordinator)

        midpoint = select._calculate_sweep_midpoint()
        assert midpoint == 175

    def test_detect_mode_from_angles_value_error(self):
        """Test _detect_mode_from_angles with ValueError in parsing."""
        coordinator = Mock()
        coordinator.device = Mock()
        coordinator.device_capabilities = ["AdvanceOscillationDay1"]
        # ancp, oson, osal, osau — ancp is checked first (not BRZE so falls through)
        coordinator.device.get_state_value = Mock(
            side_effect=["", "ON", "INVALID", "BAD"]
        )
        coordinator.data = {"product-state": {}}

        select = DysonOscillationModeSelect(coordinator)

        mode = select._detect_mode_from_angles()
        assert mode == "Custom"

    def test_detect_mode_from_angles_type_error(self):
        """Test _detect_mode_from_angles with non-matching angles."""
        coordinator = Mock()
        coordinator.device = Mock()
        coordinator.device_capabilities = ["AdvanceOscillationDay1"]
        # ancp, oson, osal, osau — ancp first; span of 20 → Custom
        coordinator.device.get_state_value = Mock(
            side_effect=["", "ON", "0100", "0120"]
        )
        coordinator.data = {"product-state": {}}

        select = DysonOscillationModeSelect(coordinator)

        # Span of 20 doesn't match any preset (45°, 90°, 180°, 350°), returns "Custom"
        mode = select._detect_mode_from_angles()
        assert mode == "Custom"

    def test_extra_state_attributes_value_error(self):
        """Test extra_state_attributes with ValueError in angle parsing."""
        coordinator = Mock()
        coordinator.device = Mock()
        coordinator.device_capabilities = ["AdvanceOscillationDay1"]
        # oson, ancp (early), osal, osau — osal=INVALID triggers ValueError
        coordinator.device.get_state_value = Mock(
            side_effect=["ON", "", "INVALID", "0350"]
        )
        coordinator.data = {"product-state": {}}

        select = DysonOscillationModeSelect(coordinator)
        select._attr_current_option = "90°"

        attrs = select.extra_state_attributes

        # Should handle error gracefully without angle attributes
        assert attrs is not None
        assert "oscillation_mode" in attrs
        assert attrs["oscillation_enabled"] is True

    def test_extra_state_attributes_type_error(self):
        """Test extra_state_attributes with TypeError in calculations."""
        coordinator = Mock()
        coordinator.device = Mock()
        coordinator.device_capabilities = ["AdvanceOscillationDay1"]
        # oson, ancp (early), osal, osau — empty strings cause int() to use fallback defaults
        coordinator.device.get_state_value = Mock(side_effect=["ON", "", "", ""])
        coordinator.data = {"product-state": {}}

        select = DysonOscillationModeSelect(coordinator)
        select._attr_current_option = "180°"

        attrs = select.extra_state_attributes

        assert attrs is not None
        assert "oscillation_mode" in attrs


class TestOscillationModeDay0SelectErrorHandling:
    """Test error handling in DysonOscillationModeDay0Select."""

    @pytest.mark.asyncio
    async def test_async_select_option_connection_error(self):
        """Test ConnectionError in Day0 oscillation select."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-DAY0-789"
        coordinator.device = Mock()
        coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ConnectionError("Day0 device offline")
        )
        coordinator.data = {"product-state": {}}

        select = DysonOscillationModeDay0Select(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("45°")

    @pytest.mark.asyncio
    async def test_async_select_option_timeout_error(self):
        """Test TimeoutError in Day0 oscillation select."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-DAY0-789"
        coordinator.device = Mock()
        coordinator.device.set_oscillation = AsyncMock(
            side_effect=TimeoutError("Day0 command timeout")
        )

        select = DysonOscillationModeDay0Select(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Off")

    @pytest.mark.asyncio
    async def test_async_select_option_value_error(self):
        """Test ValueError in Day0 oscillation select."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-DAY0-789"
        coordinator.device = Mock()
        coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ValueError("Invalid Day0 angle")
        )
        coordinator.data = {"product-state": {}}

        select = DysonOscillationModeDay0Select(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("90°")

    @pytest.mark.asyncio
    async def test_async_select_option_generic_exception(self):
        """Test generic Exception in Day0 oscillation select."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-DAY0-789"
        coordinator.device = Mock()
        coordinator.device.set_oscillation = AsyncMock(
            side_effect=KeyError("Missing Day0 state key")
        )

        select = DysonOscillationModeDay0Select(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Custom")

    def test_extra_state_attributes_value_error(self):
        """Test extra_state_attributes with ValueError in Day0 parsing."""
        coordinator = Mock()
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(
            side_effect=["ON", "INVALID", "INVALID"]
        )
        coordinator.data = {"product-state": {}}

        select = DysonOscillationModeDay0Select(coordinator)

        attrs = select.extra_state_attributes

        # Should handle parsing error gracefully
        assert attrs is not None


class TestHeatingModeSelectErrorHandling:
    """Test error handling in DysonHeatingModeSelect."""

    @pytest.mark.asyncio
    async def test_async_select_option_connection_error_heating_on(self):
        """Test ConnectionError when enabling heating."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HEAT-111"
        coordinator.device = Mock()
        coordinator.device.set_heat_mode = AsyncMock(
            side_effect=ConnectionError("Heater connection lost")
        )

        select = DysonHeatingModeSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Heating On")

    @pytest.mark.asyncio
    async def test_async_select_option_timeout_error_heating_off(self):
        """Test TimeoutError when disabling heating."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HEAT-111"
        coordinator.device = Mock()
        coordinator.device.set_heat_mode = AsyncMock(
            side_effect=TimeoutError("Heater timeout")
        )

        select = DysonHeatingModeSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Heating Off")

    @pytest.mark.asyncio
    async def test_async_select_option_value_error(self):
        """Test ValueError in heating mode selection."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HEAT-111"
        coordinator.device = Mock()
        coordinator.device.set_heat_mode = AsyncMock(
            side_effect=ValueError("Invalid heating mode")
        )

        select = DysonHeatingModeSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Heating On")

    @pytest.mark.asyncio
    async def test_async_select_option_generic_exception(self):
        """Test generic Exception in heating mode selection."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HEAT-111"
        coordinator.device = Mock()
        coordinator.device.set_heat_mode = AsyncMock(
            side_effect=OSError("System error in heater")
        )

        select = DysonHeatingModeSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Heating Off")


class TestWaterHardnessSelectErrorHandling:
    """Test error handling in DysonWaterHardnessSelect."""

    @pytest.mark.asyncio
    async def test_async_select_option_connection_error_soft(self):
        """Test ConnectionError when setting water hardness to soft."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HUMID-222"
        coordinator.device = Mock()
        coordinator.device.set_water_hardness = AsyncMock(
            side_effect=ConnectionError("Humidifier offline")
        )

        select = DysonWaterHardnessSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Soft")

    @pytest.mark.asyncio
    async def test_async_select_option_timeout_error_medium(self):
        """Test TimeoutError when setting water hardness to medium."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HUMID-222"
        coordinator.device = Mock()
        coordinator.device.set_water_hardness = AsyncMock(
            side_effect=TimeoutError("Hardness adjustment timeout")
        )

        select = DysonWaterHardnessSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Medium")

    @pytest.mark.asyncio
    async def test_async_select_option_value_error_hard(self):
        """Test ValueError when setting water hardness to hard."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HUMID-222"
        coordinator.device = Mock()
        coordinator.device.set_water_hardness = AsyncMock(
            side_effect=ValueError("Invalid hardness level")
        )

        select = DysonWaterHardnessSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Hard")

    @pytest.mark.asyncio
    async def test_async_select_option_generic_exception(self):
        """Test generic Exception in water hardness selection."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HUMID-222"
        coordinator.device = Mock()
        coordinator.device.set_water_hardness = AsyncMock(
            side_effect=RuntimeError("Humidifier malfunction")
        )

        select = DysonWaterHardnessSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Medium")


class TestRobotPower360EyeSelectErrorHandling:
    """Test error handling in DysonRobotPower360EyeSelect."""

    @pytest.mark.asyncio
    async def test_async_select_option_connection_error_quiet(self):
        """Test ConnectionError when setting robot power to quiet."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-360-333"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=ConnectionError("Robot offline")
        )

        select = DysonRobotPower360EyeSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Quiet")

    @pytest.mark.asyncio
    async def test_async_select_option_timeout_error_max(self):
        """Test TimeoutError when setting robot power to max."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-360-333"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=TimeoutError("Power mode timeout")
        )

        select = DysonRobotPower360EyeSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Max")

    @pytest.mark.asyncio
    async def test_async_select_option_value_error(self):
        """Test ValueError in 360 Eye power selection."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-360-333"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=ValueError("Invalid 360 Eye power mode")
        )

        select = DysonRobotPower360EyeSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Quiet")

    @pytest.mark.asyncio
    async def test_async_select_option_generic_exception(self):
        """Test generic Exception in 360 Eye power selection."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-360-333"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=OSError("Robot hardware error")
        )

        select = DysonRobotPower360EyeSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Max")


class TestRobotPowerHeuristSelectErrorHandling:
    """Test error handling in DysonRobotPowerHeuristSelect."""

    @pytest.mark.asyncio
    async def test_async_select_option_connection_error_quiet(self):
        """Test ConnectionError when setting Heurist power to quiet."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-HEUR-444"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=ConnectionError("Heurist disconnected")
        )

        select = DysonRobotPowerHeuristSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Quiet")

    @pytest.mark.asyncio
    async def test_async_select_option_timeout_error_high(self):
        """Test TimeoutError when setting Heurist power to high."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-HEUR-444"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=TimeoutError("Heurist command timeout")
        )

        select = DysonRobotPowerHeuristSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("High")

    @pytest.mark.asyncio
    async def test_async_select_option_value_error(self):
        """Test ValueError in Heurist power selection."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-HEUR-444"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=ValueError("Invalid Heurist power")
        )

        select = DysonRobotPowerHeuristSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Medium")

    @pytest.mark.asyncio
    async def test_async_select_option_generic_exception(self):
        """Test generic Exception in Heurist power selection."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-HEUR-444"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=TypeError("Heurist type mismatch")
        )

        select = DysonRobotPowerHeuristSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Quiet")


class TestRobotPowerVisNavSelectErrorHandling:
    """Test error handling in DysonRobotPowerVisNavSelect."""

    @pytest.mark.asyncio
    async def test_async_select_option_connection_error_quiet(self):
        """Test ConnectionError when setting Vis Nav power to quiet."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-VIS-555"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=ConnectionError("Vis Nav unreachable")
        )

        select = DysonRobotPowerVisNavSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Quiet")

    @pytest.mark.asyncio
    async def test_async_select_option_timeout_error_boost(self):
        """Test TimeoutError when setting Vis Nav power to boost."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-VIS-555"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=TimeoutError("Vis Nav boost timeout")
        )

        select = DysonRobotPowerVisNavSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Boost")

    @pytest.mark.asyncio
    async def test_async_select_option_value_error(self):
        """Test ValueError in Vis Nav power selection."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-VIS-555"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=ValueError("Invalid Vis Nav power level")
        )

        select = DysonRobotPowerVisNavSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Medium")

    @pytest.mark.asyncio
    async def test_async_select_option_generic_exception(self):
        """Test generic Exception in Vis Nav power selection."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-VIS-555"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=AttributeError("Vis Nav missing attribute")
        )

        select = DysonRobotPowerVisNavSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Quiet")


class TestRobotPowerGenericSelectErrorHandling:
    """Test error handling in DysonRobotPowerGenericSelect."""

    @pytest.mark.asyncio
    async def test_async_select_option_connection_error_auto(self):
        """Test ConnectionError when setting generic robot power to auto."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-GEN-666"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=ConnectionError("Generic robot offline")
        )

        select = DysonRobotPowerGenericSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Auto")

    @pytest.mark.asyncio
    async def test_async_select_option_timeout_error_quiet(self):
        """Test TimeoutError when setting generic robot power to quiet."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-GEN-666"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=TimeoutError("Generic robot timeout")
        )

        select = DysonRobotPowerGenericSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Quiet")

    @pytest.mark.asyncio
    async def test_async_select_option_value_error(self):
        """Test ValueError in generic robot power selection."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-GEN-666"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=ValueError("Invalid generic power mode")
        )

        select = DysonRobotPowerGenericSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Max")

    @pytest.mark.asyncio
    async def test_async_select_option_generic_exception(self):
        """Test generic Exception in generic robot power selection."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-ROBOT-GEN-666"
        coordinator.device = Mock()
        coordinator.device.set_power_mode = AsyncMock(
            side_effect=KeyError("Generic robot missing key")
        )

        select = DysonRobotPowerGenericSelect(coordinator)

        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("Auto")
