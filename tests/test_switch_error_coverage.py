"""Error coverage tests for switch platform.

This module focuses on testing error handling paths in switch entities
to improve code coverage for switch.py module.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.switch import (
    DysonAutoModeSwitch,
    DysonContinuousMonitoringSwitch,
    DysonFirmwareAutoUpdateSwitch,
    DysonHeatingSwitch,
    DysonNightModeSwitch,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for switch tests."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-SERIAL-123"
    coordinator.device = MagicMock()
    coordinator.data = {"product-state": {}}
    coordinator.device_capabilities = []
    coordinator.firmware_auto_update_enabled = False
    coordinator.firmware_version = "1.0.0"
    coordinator.async_set_firmware_auto_update = AsyncMock(return_value=True)
    return coordinator


class TestNightModeSwitchErrorHandling:
    """Test error handling in night mode switch."""

    @pytest.mark.asyncio
    async def test_turn_on_connection_error(self, mock_coordinator):
        """Test night mode turn on with ConnectionError."""
        switch = DysonNightModeSwitch(mock_coordinator)
        mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        # Patch async_write_ha_state to avoid entity platform requirements
        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_night_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_on_timeout_error(self, mock_coordinator):
        """Test night mode turn on with TimeoutError."""
        switch = DysonNightModeSwitch(mock_coordinator)
        mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=TimeoutError("Request timeout")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_night_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_on_attribute_error(self, mock_coordinator):
        """Test night mode turn on with AttributeError."""
        switch = DysonNightModeSwitch(mock_coordinator)
        mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=AttributeError("Method not available")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_night_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_on_generic_exception(self, mock_coordinator):
        """Test night mode turn on with generic Exception."""
        switch = DysonNightModeSwitch(mock_coordinator)
        mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_night_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_off_connection_error(self, mock_coordinator):
        """Test night mode turn off with ConnectionError."""
        switch = DysonNightModeSwitch(mock_coordinator)
        mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_night_mode.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_turn_off_timeout_error(self, mock_coordinator):
        """Test night mode turn off with TimeoutError."""
        switch = DysonNightModeSwitch(mock_coordinator)
        mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=TimeoutError("Request timeout")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_night_mode.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_turn_off_attribute_error(self, mock_coordinator):
        """Test night mode turn off with AttributeError."""
        switch = DysonNightModeSwitch(mock_coordinator)
        mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=AttributeError("Method not available")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_night_mode.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_turn_off_generic_exception(self, mock_coordinator):
        """Test night mode turn off with generic Exception."""
        switch = DysonNightModeSwitch(mock_coordinator)
        mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_night_mode.assert_called_once_with(False)


class TestAutoModeSwitchErrorHandling:
    """Test error handling in auto mode switch."""

    @pytest.mark.asyncio
    async def test_turn_on_connection_error(self, mock_coordinator):
        """Test auto mode turn on with ConnectionError."""
        switch = DysonAutoModeSwitch(mock_coordinator)
        mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_auto_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_on_timeout_error(self, mock_coordinator):
        """Test auto mode turn on with TimeoutError."""
        switch = DysonAutoModeSwitch(mock_coordinator)
        mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=TimeoutError("Request timeout")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_auto_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_on_attribute_error(self, mock_coordinator):
        """Test auto mode turn on with AttributeError."""
        switch = DysonAutoModeSwitch(mock_coordinator)
        mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=AttributeError("Method not available")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_auto_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_on_generic_exception(self, mock_coordinator):
        """Test auto mode turn on with generic Exception."""
        switch = DysonAutoModeSwitch(mock_coordinator)
        mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_auto_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_off_connection_error(self, mock_coordinator):
        """Test auto mode turn off with ConnectionError."""
        switch = DysonAutoModeSwitch(mock_coordinator)
        mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_auto_mode.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_turn_off_timeout_error(self, mock_coordinator):
        """Test auto mode turn off with TimeoutError."""
        switch = DysonAutoModeSwitch(mock_coordinator)
        mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=TimeoutError("Request timeout")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_auto_mode.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_turn_off_attribute_error(self, mock_coordinator):
        """Test auto mode turn off with AttributeError."""
        switch = DysonAutoModeSwitch(mock_coordinator)
        mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=AttributeError("Method not available")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_auto_mode.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_turn_off_generic_exception(self, mock_coordinator):
        """Test auto mode turn off with generic Exception."""
        switch = DysonAutoModeSwitch(mock_coordinator)
        mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_auto_mode.assert_called_once_with(False)


class TestHeatingSwitchErrorHandling:
    """Test error handling in heating switch."""

    @pytest.mark.asyncio
    async def test_turn_on_connection_error(self, mock_coordinator):
        """Test heating turn on with ConnectionError."""
        switch = DysonHeatingSwitch(mock_coordinator)
        mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_heating_mode.assert_called_once_with("HEAT")

    @pytest.mark.asyncio
    async def test_turn_on_timeout_error(self, mock_coordinator):
        """Test heating turn on with TimeoutError."""
        switch = DysonHeatingSwitch(mock_coordinator)
        mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=TimeoutError("Request timeout")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_heating_mode.assert_called_once_with("HEAT")

    @pytest.mark.asyncio
    async def test_turn_on_attribute_error(self, mock_coordinator):
        """Test heating turn on with AttributeError."""
        switch = DysonHeatingSwitch(mock_coordinator)
        mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=AttributeError("Method not available")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_heating_mode.assert_called_once_with("HEAT")

    @pytest.mark.asyncio
    async def test_turn_on_generic_exception(self, mock_coordinator):
        """Test heating turn on with generic Exception."""
        switch = DysonHeatingSwitch(mock_coordinator)
        mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_heating_mode.assert_called_once_with("HEAT")

    @pytest.mark.asyncio
    async def test_turn_off_connection_error(self, mock_coordinator):
        """Test heating turn off with ConnectionError."""
        switch = DysonHeatingSwitch(mock_coordinator)
        mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_heating_mode.assert_called_once_with("OFF")

    @pytest.mark.asyncio
    async def test_turn_off_timeout_error(self, mock_coordinator):
        """Test heating turn off with TimeoutError."""
        switch = DysonHeatingSwitch(mock_coordinator)
        mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=TimeoutError("Request timeout")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_heating_mode.assert_called_once_with("OFF")

    @pytest.mark.asyncio
    async def test_turn_off_attribute_error(self, mock_coordinator):
        """Test heating turn off with AttributeError."""
        switch = DysonHeatingSwitch(mock_coordinator)
        mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=AttributeError("Method not available")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_heating_mode.assert_called_once_with("OFF")

    @pytest.mark.asyncio
    async def test_turn_off_generic_exception(self, mock_coordinator):
        """Test heating turn off with generic Exception."""
        switch = DysonHeatingSwitch(mock_coordinator)
        mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_heating_mode.assert_called_once_with("OFF")

    def test_extra_state_attributes_value_error_temperature(self, mock_coordinator):
        """Test heating extra_state_attributes with ValueError in temperature conversion."""
        switch = DysonHeatingSwitch(mock_coordinator)
        mock_coordinator.device.get_state_value = MagicMock(
            side_effect=["HEAT", "invalid_temp"]
        )

        with patch.object(switch, "async_write_ha_state"):
            attrs = switch.extra_state_attributes

        assert attrs is not None
        assert attrs["heating_mode"] == "HEAT"
        assert attrs["heating_enabled"] is True
        # Temperature attributes should not be present due to ValueError
        assert "target_temperature" not in attrs
        assert "target_temperature_kelvin" not in attrs

    def test_extra_state_attributes_type_error_temperature(self, mock_coordinator):
        """Test heating extra_state_attributes with TypeError in temperature conversion."""
        switch = DysonHeatingSwitch(mock_coordinator)
        mock_coordinator.device.get_state_value = MagicMock(side_effect=["HEAT", None])

        with patch.object(switch, "async_write_ha_state"):
            attrs = switch.extra_state_attributes

        assert attrs is not None
        assert attrs["heating_mode"] == "HEAT"
        # Temperature attributes should not be present due to TypeError
        assert "target_temperature" not in attrs


class TestContinuousMonitoringSwitchErrorHandling:
    """Test error handling in continuous monitoring switch."""

    @pytest.mark.asyncio
    async def test_turn_on_connection_error(self, mock_coordinator):
        """Test continuous monitoring turn on with ConnectionError."""
        switch = DysonContinuousMonitoringSwitch(mock_coordinator)
        mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_continuous_monitoring.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_on_timeout_error(self, mock_coordinator):
        """Test continuous monitoring turn on with TimeoutError."""
        switch = DysonContinuousMonitoringSwitch(mock_coordinator)
        mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=TimeoutError("Request timeout")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_continuous_monitoring.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_on_attribute_error(self, mock_coordinator):
        """Test continuous monitoring turn on with AttributeError."""
        switch = DysonContinuousMonitoringSwitch(mock_coordinator)
        mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=AttributeError("Method not available")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_continuous_monitoring.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_on_generic_exception(self, mock_coordinator):
        """Test continuous monitoring turn on with generic Exception."""
        switch = DysonContinuousMonitoringSwitch(mock_coordinator)
        mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.device.set_continuous_monitoring.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_off_connection_error(self, mock_coordinator):
        """Test continuous monitoring turn off with ConnectionError."""
        switch = DysonContinuousMonitoringSwitch(mock_coordinator)
        mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_continuous_monitoring.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_turn_off_timeout_error(self, mock_coordinator):
        """Test continuous monitoring turn off with TimeoutError."""
        switch = DysonContinuousMonitoringSwitch(mock_coordinator)
        mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=TimeoutError("Request timeout")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_continuous_monitoring.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_turn_off_attribute_error(self, mock_coordinator):
        """Test continuous monitoring turn off with AttributeError."""
        switch = DysonContinuousMonitoringSwitch(mock_coordinator)
        mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=AttributeError("Method not available")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_continuous_monitoring.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_turn_off_generic_exception(self, mock_coordinator):
        """Test continuous monitoring turn off with generic Exception."""
        switch = DysonContinuousMonitoringSwitch(mock_coordinator)
        mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.device.set_continuous_monitoring.assert_called_once_with(False)


class TestFirmwareAutoUpdateSwitchErrorHandling:
    """Test error handling in firmware auto-update switch."""

    @pytest.mark.asyncio
    async def test_turn_on_success(self, mock_coordinator):
        """Test firmware auto-update turn on success."""
        switch = DysonFirmwareAutoUpdateSwitch(mock_coordinator)
        mock_coordinator.async_set_firmware_auto_update = AsyncMock(return_value=True)

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.async_set_firmware_auto_update.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_on_failure(self, mock_coordinator):
        """Test firmware auto-update turn on failure."""
        switch = DysonFirmwareAutoUpdateSwitch(mock_coordinator)
        mock_coordinator.async_set_firmware_auto_update = AsyncMock(return_value=False)

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()

        mock_coordinator.async_set_firmware_auto_update.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_off_success(self, mock_coordinator):
        """Test firmware auto-update turn off success."""
        switch = DysonFirmwareAutoUpdateSwitch(mock_coordinator)
        mock_coordinator.async_set_firmware_auto_update = AsyncMock(return_value=True)

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.async_set_firmware_auto_update.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_turn_off_failure(self, mock_coordinator):
        """Test firmware auto-update turn off failure."""
        switch = DysonFirmwareAutoUpdateSwitch(mock_coordinator)
        mock_coordinator.async_set_firmware_auto_update = AsyncMock(return_value=False)

        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()

        mock_coordinator.async_set_firmware_auto_update.assert_called_once_with(False)
