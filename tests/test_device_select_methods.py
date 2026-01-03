"""Test suite for Dyson device select control methods.

This module provides comprehensive testing for the select-related device control
methods that centralize MQTT commands in the device layer. Tests cover water
hardness control for humidifiers and robot vacuum power level control.

Test Coverage:
- Water hardness setting with validation
- Robot power level setting for different models (360 Eye, Heurist, Vis Nav, Generic)
- Error handling for invalid parameters
- MQTT command formatting verification
- Exception handling for device communication failures

The tests ensure proper encapsulation of select controls in device methods
rather than having direct MQTT commands scattered throughout select entities.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hass_dyson.device import DysonDevice


class TestDysonDeviceSelectMethods:
    """Test select-related device control methods."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.loop = MagicMock()
        hass.async_add_executor_job = AsyncMock()
        return hass

    @pytest.fixture
    def mock_device(self, mock_hass):
        """Create mock Dyson device."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST-DEVICE-123",
            host="192.168.1.100",
            credential="test_credential",
        )

        # Mock the MQTT client and connection
        device._mqtt_client = MagicMock()
        device._connected = True
        device.send_command = AsyncMock()
        device._send_robot_command = AsyncMock()
        device._get_command_timestamp = MagicMock(
            return_value="2024-01-01T12:00:00.000Z"
        )

        return device

    @pytest.mark.asyncio
    async def test_set_water_hardness_soft(self, mock_device):
        """Test setting water hardness to soft."""
        await mock_device.set_water_hardness("soft")

        mock_device.send_command.assert_called_once_with("STATE-SET", {"wath": "0675"})

    @pytest.mark.asyncio
    async def test_set_water_hardness_medium(self, mock_device):
        """Test setting water hardness to medium."""
        await mock_device.set_water_hardness("medium")

        mock_device.send_command.assert_called_once_with("STATE-SET", {"wath": "1350"})

    @pytest.mark.asyncio
    async def test_set_water_hardness_hard(self, mock_device):
        """Test setting water hardness to hard."""
        await mock_device.set_water_hardness("hard")

        mock_device.send_command.assert_called_once_with("STATE-SET", {"wath": "2025"})

    @pytest.mark.asyncio
    async def test_set_water_hardness_invalid_value(self, mock_device):
        """Test setting water hardness with invalid value raises ValueError."""
        with pytest.raises(ValueError, match="Invalid water hardness: invalid"):
            await mock_device.set_water_hardness("invalid")

        # Ensure send_command was not called
        mock_device.send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_water_hardness_case_sensitivity(self, mock_device):
        """Test that water hardness setting is case sensitive."""
        with pytest.raises(ValueError, match="Invalid water hardness: Soft"):
            await mock_device.set_water_hardness("Soft")

    @pytest.mark.asyncio
    async def test_set_robot_power_360eye(self, mock_device):
        """Test setting robot power for 360 Eye model."""
        await mock_device.set_robot_power("halfPower", "360eye")

        expected_command = {
            "msg": "STATE-SET",
            "time": "2024-01-01T12:00:00.000Z",
            "data": {"fPwr": "halfPower"},
        }

        mock_device._send_robot_command.assert_called_once_with(expected_command)

    @pytest.mark.asyncio
    async def test_set_robot_power_heurist(self, mock_device):
        """Test setting robot power for Heurist model."""
        await mock_device.set_robot_power("2", "heurist")

        expected_command = {
            "msg": "STATE-SET",
            "time": "2024-01-01T12:00:00.000Z",
            "data": {"fPwr": 2},
        }

        mock_device._send_robot_command.assert_called_once_with(expected_command)

    @pytest.mark.asyncio
    async def test_set_robot_power_vis_nav(self, mock_device):
        """Test setting robot power for Vis Nav model."""
        await mock_device.set_robot_power("3", "vis_nav")

        expected_command = {
            "msg": "STATE-SET",
            "time": "2024-01-01T12:00:00.000Z",
            "data": {"fPwr": 3},
        }

        mock_device._send_robot_command.assert_called_once_with(expected_command)

    @pytest.mark.asyncio
    async def test_set_robot_power_generic(self, mock_device):
        """Test setting robot power for generic model."""
        await mock_device.set_robot_power("1", "generic")

        expected_command = {
            "msg": "STATE-SET",
            "time": "2024-01-01T12:00:00.000Z",
            "data": {"fPwr": 1},
        }

        mock_device._send_robot_command.assert_called_once_with(expected_command)

    @pytest.mark.asyncio
    async def test_set_robot_power_default_generic(self, mock_device):
        """Test setting robot power with default model type (generic)."""
        await mock_device.set_robot_power("4")

        expected_command = {
            "msg": "STATE-SET",
            "time": "2024-01-01T12:00:00.000Z",
            "data": {"fPwr": 4},
        }

        mock_device._send_robot_command.assert_called_once_with(expected_command)

    @pytest.mark.asyncio
    async def test_set_robot_power_360eye_string_power(self, mock_device):
        """Test that 360 Eye model preserves string power values."""
        await mock_device.set_robot_power("fullPower", "360eye")

        expected_command = {
            "msg": "STATE-SET",
            "time": "2024-01-01T12:00:00.000Z",
            "data": {"fPwr": "fullPower"},
        }

        mock_device._send_robot_command.assert_called_once_with(expected_command)

    @pytest.mark.asyncio
    async def test_set_robot_power_numeric_models_convert_to_int(self, mock_device):
        """Test that numeric models convert power values to integers."""
        # Test all numeric models
        for model_type in ["heurist", "vis_nav", "generic"]:
            mock_device._send_robot_command.reset_mock()

            await mock_device.set_robot_power("3", model_type)

            expected_command = {
                "msg": "STATE-SET",
                "time": "2024-01-01T12:00:00.000Z",
                "data": {"fPwr": 3},
            }

            mock_device._send_robot_command.assert_called_once_with(expected_command)

    @pytest.mark.asyncio
    async def test_set_water_hardness_exception_handling(self, mock_device):
        """Test water hardness exception handling."""
        mock_device.send_command.side_effect = ConnectionError("Connection failed")

        with pytest.raises(ConnectionError):
            await mock_device.set_water_hardness("medium")

    @pytest.mark.asyncio
    async def test_set_robot_power_exception_handling(self, mock_device):
        """Test robot power exception handling."""
        mock_device._send_robot_command.side_effect = TimeoutError("Timeout")

        with pytest.raises(TimeoutError):
            await mock_device.set_robot_power("2", "heurist")

    @pytest.mark.asyncio
    async def test_water_hardness_value_mapping(self, mock_device):
        """Test complete water hardness value mapping."""
        hardness_tests = [
            ("soft", "0675"),
            ("medium", "1350"),
            ("hard", "2025"),
        ]

        for hardness, expected_value in hardness_tests:
            mock_device.send_command.reset_mock()

            await mock_device.set_water_hardness(hardness)

            mock_device.send_command.assert_called_once_with(
                "STATE-SET", {"wath": expected_value}
            )

    @pytest.mark.asyncio
    async def test_robot_power_command_structure(self, mock_device):
        """Test robot power command structure is consistent."""
        power_value = "2"
        model_type = "heurist"

        await mock_device.set_robot_power(power_value, model_type)

        # Verify command structure
        call_args = mock_device._send_robot_command.call_args[0][0]

        assert call_args["msg"] == "STATE-SET"
        assert "time" in call_args
        assert call_args["data"]["fPwr"] == 2
        assert isinstance(call_args["time"], str)

    @pytest.mark.asyncio
    async def test_robot_power_timestamp_generation(self, mock_device):
        """Test robot power command includes proper timestamp."""
        await mock_device.set_robot_power("1", "generic")

        # Verify timestamp was requested
        mock_device._get_command_timestamp.assert_called_once()

        # Verify timestamp is included in command
        call_args = mock_device._send_robot_command.call_args[0][0]
        assert call_args["time"] == "2024-01-01T12:00:00.000Z"

    @pytest.mark.asyncio
    async def test_request_current_faults_success(self, mock_device):
        """Test requesting current faults from device."""
        # Mock the private _request_current_faults method
        mock_device._request_current_faults = AsyncMock()

        await mock_device.request_current_faults()

        # Verify the private method was called
        mock_device._request_current_faults.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_current_faults_device_not_connected(self, mock_device):
        """Test request_current_faults raises error when device not connected."""
        mock_device._connected = False

        with pytest.raises(
            RuntimeError, match="Device TEST-DEVICE-123 is not connected"
        ):
            await mock_device.request_current_faults()

    @pytest.mark.asyncio
    async def test_request_current_faults_exception_handling(self, mock_device):
        """Test request_current_faults exception handling."""
        mock_device._request_current_faults = AsyncMock(
            side_effect=ConnectionError("Connection lost")
        )

        with pytest.raises(ConnectionError):
            await mock_device.request_current_faults()
