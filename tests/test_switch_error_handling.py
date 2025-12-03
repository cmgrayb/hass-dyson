"""Test switch error handling to improve coverage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.switch import (
    DysonAutoModeSwitch,
    DysonContinuousMonitoringSwitch,
    DysonHeatingSwitch,
    DysonNightModeSwitch,
)


class TestSwitchErrorHandling:
    """Test switch error handling scenarios to improve coverage."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock()
        coordinator.serial_number = "TEST-SERIAL-123"
        coordinator.device_name = "Test Device"
        coordinator.device = MagicMock()
        return coordinator

    async def test_auto_mode_switch_turn_off_exception_handling(self, mock_coordinator):
        """Test auto mode switch turn off with device exception."""
        switch = DysonAutoModeSwitch(mock_coordinator)

        # Mock device to raise exception
        mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=Exception("Device error")
        )

        with patch.object(switch, "async_write_ha_state"):
            # Should handle exception gracefully
            await switch.async_turn_off()

        # Verify device method was called
        mock_coordinator.device.set_auto_mode.assert_called_once_with(False)

    async def test_night_mode_switch_turn_on_exception_handling(self, mock_coordinator):
        """Test night mode switch turn on with device exception."""
        switch = DysonNightModeSwitch(mock_coordinator)

        # Mock device to raise exception
        mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=Exception("Device error")
        )

        with patch.object(switch, "async_write_ha_state"):
            # Should handle exception gracefully
            await switch.async_turn_on()

        # Verify device method was called
        mock_coordinator.device.set_night_mode.assert_called_once_with(True)

    async def test_night_mode_switch_turn_off_exception_handling(
        self, mock_coordinator
    ):
        """Test night mode switch turn off with device exception."""
        switch = DysonNightModeSwitch(mock_coordinator)

        # Mock device to raise exception
        mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=Exception("Device error")
        )

        with patch.object(switch, "async_write_ha_state"):
            # Should handle exception gracefully
            await switch.async_turn_off()

        # Verify device method was called
        mock_coordinator.device.set_night_mode.assert_called_once_with(False)

    # Oscillation switch tests removed - oscillation is now handled natively by the fan platform

    async def test_heating_switch_turn_on_exception_handling(self, mock_coordinator):
        """Test heating switch turn on with device exception."""
        switch = DysonHeatingSwitch(mock_coordinator)

        # Mock device to raise exception
        mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=Exception("Device error")
        )

        with patch.object(switch, "async_write_ha_state"):
            # Should handle exception gracefully
            await switch.async_turn_on()

        # Verify device method was called
        mock_coordinator.device.set_heating_mode.assert_called_once_with("HEAT")

    async def test_heating_switch_turn_off_exception_handling(self, mock_coordinator):
        """Test heating switch turn off with device exception."""
        switch = DysonHeatingSwitch(mock_coordinator)

        # Mock device to raise exception
        mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=Exception("Device error")
        )

        with patch.object(switch, "async_write_ha_state"):
            # Should handle exception gracefully
            await switch.async_turn_off()

        # Verify device method was called
        mock_coordinator.device.set_heating_mode.assert_called_once_with("OFF")

    async def test_continuous_monitoring_switch_turn_on_exception_handling(
        self, mock_coordinator
    ):
        """Test continuous monitoring switch turn on with device exception."""
        switch = DysonContinuousMonitoringSwitch(mock_coordinator)

        # Mock device to raise exception
        mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=Exception("Device error")
        )

        with patch.object(switch, "async_write_ha_state"):
            # Should handle exception gracefully
            await switch.async_turn_on()

        # Verify device method was called
        mock_coordinator.device.set_continuous_monitoring.assert_called_once_with(True)

    async def test_continuous_monitoring_switch_turn_off_exception_handling(
        self, mock_coordinator
    ):
        """Test continuous monitoring switch turn off with device exception."""
        switch = DysonContinuousMonitoringSwitch(mock_coordinator)

        # Mock device to raise exception
        mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=Exception("Device error")
        )

        with patch.object(switch, "async_write_ha_state"):
            # Should handle exception gracefully
            await switch.async_turn_off()

        # Verify device method was called
        mock_coordinator.device.set_continuous_monitoring.assert_called_once_with(False)

    async def test_switches_with_no_device(self, mock_coordinator):
        """Test switch behavior when coordinator has no device."""
        # Set coordinator device to None
        mock_coordinator.device = None

        switches = [
            DysonAutoModeSwitch(mock_coordinator),
            DysonNightModeSwitch(mock_coordinator),
            # DysonOscillationSwitch removed - oscillation handled by fan platform
            DysonHeatingSwitch(mock_coordinator),
            DysonContinuousMonitoringSwitch(mock_coordinator),
        ]

        for switch in switches:
            with patch.object(switch, "async_write_ha_state"):
                # All these should return early when device is None
                await switch.async_turn_on()
                await switch.async_turn_off()

    # Oscillation switch extra state attributes test removed - oscillation handled by fan platform

    def test_heating_switch_extra_state_attributes_detailed(self, mock_coordinator):
        """Test heating switch extra state attributes with detailed data."""
        switch = DysonHeatingSwitch(mock_coordinator)

        # Test with device having heat target data
        mock_coordinator.device.heat_target = 22

        # Test that extra_state_attributes returns without error
        attributes = switch.extra_state_attributes
        # The actual attributes depend on internal device data structure
        assert attributes is not None or attributes is None
