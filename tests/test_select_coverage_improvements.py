"""Additional tests to improve select.py coverage."""

from unittest.mock import Mock

import pytest

from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
from custom_components.hass_dyson.select import (
    DysonFanControlModeSelect,
    DysonHeatingModeSelect,
    DysonOscillationModeSelect,
)


class TestSelectCoverageImprovements:
    """Test class for improving select.py coverage."""

    def test_fan_control_mode_init_local_device_options(self, mock_coordinator):
        """Test FanControlModeSelect initialization for local device (no Sleep option)."""
        # Setup local device
        mock_coordinator.config_entry.data = {"connection_type": "local_only"}

        select = DysonFanControlModeSelect(mock_coordinator)

        # Should only have Auto and Manual for local devices
        assert select._attr_options == ["Auto", "Manual"]
        assert "Sleep" not in select._attr_options

    def test_fan_control_mode_init_cloud_device_options(self, mock_coordinator):
        """Test FanControlModeSelect initialization for cloud device (includes Sleep option)."""
        # Setup cloud device
        mock_coordinator.config_entry.data = {"connection_type": "cloud"}

        select = DysonFanControlModeSelect(mock_coordinator)

        # Should have Auto, Manual, and Sleep for cloud devices
        assert select._attr_options == ["Auto", "Manual", "Sleep"]

    def test_fan_control_mode_coordinator_update_sleep_mode_detection(self, mock_coordinator):
        """Test sleep mode detection for cloud devices."""
        mock_coordinator.config_entry.data = {"connection_type": "cloud"}
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "auto": "OFF",
            "nmod": "ON",  # Night mode ON = Sleep mode
        }.get(key, default)
        mock_coordinator.data = {"product-state": {}}

        select = DysonFanControlModeSelect(mock_coordinator)
        # Mock the hass attribute to avoid the RuntimeError
        select.hass = Mock()
        select.async_write_ha_state = Mock()
        select._handle_coordinator_update()

        assert select._attr_current_option == "Sleep"

    def test_oscillation_mode_detect_mode_exception_handling(self, mock_coordinator):
        """Test oscillation mode detection with invalid angle data."""
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "oson": "ON",
            "osal": "invalid",  # Invalid data should trigger exception
            "osau": "0350",
        }.get(key, default)
        mock_coordinator.data = {"product-state": {}}

        select = DysonOscillationModeSelect(mock_coordinator)

        # Should handle exception and return "Custom"
        mode = select._detect_mode_from_angles()
        assert mode == "Custom"

    def test_oscillation_mode_boundary_constraints_lower_violation(self, mock_coordinator):
        """Test oscillation angle boundary handling for lower bound violation."""
        select = DysonOscillationModeSelect(mock_coordinator)

        # Test lower boundary violation (negative lower bound)
        lower, upper = select._handle_lower_boundary_violation(90)

        assert lower == 0  # Should be constrained to minimum
        assert upper <= 350  # Should not exceed maximum

    def test_oscillation_mode_boundary_constraints_upper_violation(self, mock_coordinator):
        """Test oscillation angle boundary handling for upper bound violation."""
        select = DysonOscillationModeSelect(mock_coordinator)

        # Test upper boundary violation (> 350 degrees)
        lower, upper = select._handle_upper_boundary_violation(90)

        assert upper == 350  # Should be constrained to maximum
        assert lower >= 0  # Should not go below minimum

    def test_oscillation_mode_optimize_centering_within_bounds(self, mock_coordinator):
        """Test oscillation angle optimization within bounds."""
        select = DysonOscillationModeSelect(mock_coordinator)

        # Test centering optimization when at boundaries
        lower, upper = select._optimize_centering_within_bounds(0, 90, 90, 45)

        # Should return valid bounds
        assert 0 <= lower <= upper <= 350

    def test_oscillation_mode_coordinator_update_no_device(self, mock_coordinator):
        """Test oscillation mode update when no device is available."""
        mock_coordinator.device = None

        select = DysonOscillationModeSelect(mock_coordinator)
        # Mock the hass attribute to avoid the RuntimeError
        select.hass = Mock()
        select.async_write_ha_state = Mock()
        select._handle_coordinator_update()

        assert select._attr_current_option is None

    def test_oscillation_mode_async_select_option_off(self, mock_coordinator):
        """Test turning oscillation off."""
        select = DysonOscillationModeSelect(mock_coordinator)

        # Test turning oscillation off
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def run_test():
            await select.async_select_option("Off")
            mock_coordinator.device.set_oscillation.assert_called_once_with(False)

        loop.run_until_complete(run_test())
        loop.close()

    def test_oscillation_mode_extra_state_attributes_no_device(self, mock_coordinator):
        """Test extra state attributes when no device is available."""
        mock_coordinator.device = None

        select = DysonOscillationModeSelect(mock_coordinator)
        # Mock the hass attribute to avoid RuntimeError
        select.hass = Mock()
        attributes = select.extra_state_attributes

        assert attributes is None

    def test_oscillation_mode_extra_state_attributes_invalid_data(self, mock_coordinator):
        """Test extra state attributes with invalid angle data."""
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "oson": "OFF",
            "osal": "invalid",  # Invalid data
            "osau": "invalid",  # Invalid data
            "ancp": "invalid",  # Invalid data
        }.get(key, default)
        mock_coordinator.data = {"product-state": {}}

        select = DysonOscillationModeSelect(mock_coordinator)
        # Mock the hass attribute to avoid RuntimeError
        select.hass = Mock()
        select._attr_current_option = "Off"
        attributes = select.extra_state_attributes

        # Should handle invalid data gracefully
        assert attributes is not None
        assert attributes["oscillation_mode"] == "Off"
        assert attributes["oscillation_enabled"] is False
        # Angle attributes should be missing due to exception handling

    def test_heating_mode_coordinator_update_unknown_mode(self, mock_coordinator):
        """Test heating mode with unknown heating state."""
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "hmod": "UNKNOWN",  # Unknown heating mode
            "hsta": "OFF",
        }.get(key, default)
        mock_coordinator.data = {"product-state": {}}

        select = DysonHeatingModeSelect(mock_coordinator)
        # Mock the hass attribute to avoid the RuntimeError
        select.hass = Mock()
        select.async_write_ha_state = Mock()
        select._handle_coordinator_update()

        # Should fall back to "Auto Heat" for unknown modes
        assert select._attr_current_option == "Auto Heat"

    def test_heating_mode_coordinator_update_no_device(self, mock_coordinator):
        """Test heating mode update when no device is available."""
        mock_coordinator.device = None

        select = DysonHeatingModeSelect(mock_coordinator)
        # Mock the hass attribute to avoid the RuntimeError
        select.hass = Mock()
        select.async_write_ha_state = Mock()
        select._handle_coordinator_update()

        assert select._attr_current_option is None

    def test_heating_mode_async_select_option_exception(self, mock_coordinator):
        """Test heating mode selection with device exception."""
        mock_coordinator.device.set_heating_mode.side_effect = Exception("Device error")

        select = DysonHeatingModeSelect(mock_coordinator)

        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def run_test():
            # Should handle exception gracefully
            await select.async_select_option("Heating")
            # No assertion needed - just ensure no uncaught exception

        loop.run_until_complete(run_test())
        loop.close()

    def test_heating_mode_extra_state_attributes_no_device(self, mock_coordinator):
        """Test heating mode extra state attributes when no device is available."""
        mock_coordinator.device = None

        select = DysonHeatingModeSelect(mock_coordinator)
        # Mock the hass attribute to avoid RuntimeError
        select.hass = Mock()
        attributes = select.extra_state_attributes

        assert attributes is None

    def test_heating_mode_extra_state_attributes_with_temperature(self, mock_coordinator):
        """Test heating mode extra state attributes with temperature data."""
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "hmod": "HEAT",
            "hsta": "HEAT",
            "hmax": "3003",  # 300.3K = 27.15°C target temperature
        }.get(key, default)
        mock_coordinator.data = {"product-state": {}}

        select = DysonHeatingModeSelect(mock_coordinator)
        # Mock the hass attribute to avoid RuntimeError
        select.hass = Mock()
        select._attr_current_option = "Heating"
        attributes = select.extra_state_attributes

        assert attributes is not None
        assert attributes["heating_mode"] == "Heating"
        assert attributes["heating_enabled"] is True
        assert attributes["target_temperature"] == 27.2  # Rounded to 1 decimal

    def test_heating_mode_extra_state_attributes_invalid_temperature(self, mock_coordinator):
        """Test heating mode extra state attributes with invalid temperature data."""
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "hmod": "HEAT",
            "hsta": "OFF",
            "hmax": "invalid",  # Invalid temperature data
        }.get(key, default)
        mock_coordinator.data = {"product-state": {}}

        select = DysonHeatingModeSelect(mock_coordinator)
        # Mock the hass attribute to avoid RuntimeError
        select.hass = Mock()
        select._attr_current_option = "Heating"
        attributes = select.extra_state_attributes

        assert attributes is not None
        assert attributes["heating_mode"] == "Heating"
        assert attributes["heating_enabled"] is True  # Based on hmod being "HEAT"
        # target_temperature should be missing due to exception handling
        assert "target_temperature" not in attributes


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for testing."""
    coordinator = Mock(spec=DysonDataUpdateCoordinator)
    coordinator.device = Mock()
    coordinator.device._get_current_value = Mock()
    coordinator.device.set_oscillation = Mock()
    coordinator.device.set_heating_mode = Mock()
    coordinator.serial_number = "TEST123"
    coordinator.config_entry = Mock()
    coordinator.config_entry.data = {}
    coordinator.data = {}
    return coordinator
