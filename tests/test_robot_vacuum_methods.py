"""Simple tests to exercise actual robot vacuum device methods for coverage."""

import json
from unittest.mock import Mock, patch

import pytest

from custom_components.hass_dyson.device import DysonDevice


class TestRobotVacuumActualMethods:
    """Test actual robot vacuum device methods with mocked dependencies."""

    @patch("custom_components.hass_dyson.device.time")
    def test_robot_methods_direct_property_access(self, mock_time):
        """Test robot vacuum property methods directly with minimal mocking."""
        # Mock time.time() for command timestamp
        mock_time.time.return_value = 1640995200

        # Create a DysonDevice instance with mocked Home Assistant and dependencies
        mock_hass = Mock()
        mock_hass.bus = Mock()
        mock_hass.bus.async_listen_once = Mock()

        # Create device with required parameters
        device = DysonDevice(
            hass=mock_hass,
            serial_number="VS6-EU-RJA1234A",
            host="192.168.1.100",
            credential="test_credential",
            mqtt_prefix="475",
            capabilities=["robot"],
            connection_type="local_only",
        )

        # Test robot_state property - use correct data structure
        device._state_data = {"product-state": {"state": "FULL_CLEAN_RUNNING"}}

        result = device.robot_state
        assert result == "FULL_CLEAN_RUNNING"

        # Test with no robot state
        device._state_data = {"product-state": {}}
        result = device.robot_state
        assert result is None

        # Test robot_battery_level property
        device._state_data = {"product-state": {"batteryChargeLevel": "85"}}

        result = device.robot_battery_level
        assert result == 85

        # Test with invalid battery level
        device._state_data = {"product-state": {"batteryChargeLevel": "invalid"}}

        result = device.robot_battery_level
        assert result is None

        # Test with no battery level
        device._state_data = {"product-state": {}}
        result = device.robot_battery_level
        assert result is None

        # Test robot_global_position property
        device._state_data = {"product-state": {"globalPosition": [123, 456]}}

        result = device.robot_global_position
        assert result == [123, 456]

        # Test with invalid position format
        device._state_data = {"product-state": {"globalPosition": "invalid_position"}}

        result = device.robot_global_position
        assert result is None

        # Test with no position
        device._state_data = {"product-state": {}}
        result = device.robot_global_position
        assert result is None

        # Test robot_full_clean_type property
        device._state_data = {"product-state": {"fullCleanType": "immediate"}}

        result = device.robot_full_clean_type
        assert result == "immediate"

        # Test with no clean type
        device._state_data = {"product-state": {}}
        result = device.robot_full_clean_type
        assert result is None

        # Test robot_clean_id property
        device._state_data = {"product-state": {"cleanId": "clean_123456"}}

        result = device.robot_clean_id
        assert result == "clean_123456"

        # Test with no clean ID
        device._state_data = {"product-state": {}}
        result = device.robot_clean_id
        assert result is None

    @patch("custom_components.hass_dyson.device.time")
    @pytest.mark.asyncio
    async def test_robot_command_methods(self, mock_time):
        """Test robot vacuum command methods with mocked MQTT."""
        # Mock time.time() for command timestamp
        mock_time.time.return_value = 1640995200

        # Create a DysonDevice instance with mocked Home Assistant and dependencies
        mock_hass = Mock()
        mock_hass.bus = Mock()
        mock_hass.bus.async_listen_once = Mock()

        # Create device
        device = DysonDevice(
            hass=mock_hass,
            serial_number="VS6-EU-RJA1234A",
            host="192.168.1.100",
            credential="test_credential",
            mqtt_prefix="475",
            capabilities=["robot"],
            connection_type="local_only",
        )

        # Mock MQTT client and connection
        mock_client = Mock()
        mock_client.is_connected.return_value = True
        mock_client.publish = Mock()
        device._mqtt_client = mock_client
        device._connected = True

        # Test robot_pause command
        await device.robot_pause()
        mock_client.publish.assert_called()

        # Test robot_resume command
        await device.robot_resume()
        assert mock_client.publish.call_count == 2

        # Test robot_abort command
        await device.robot_abort()
        assert mock_client.publish.call_count == 3

        # Test robot_request_state command
        await device.robot_request_state()
        assert mock_client.publish.call_count == 4

        # Test commands when device is not connected
        device._connected = False

        # Should raise RuntimeError when not connected
        with pytest.raises(RuntimeError, match="is not connected"):
            await device.robot_pause()
        assert mock_client.publish.call_count == 4

    @patch("custom_components.hass_dyson.device.time")
    @pytest.mark.asyncio
    async def test_send_robot_command_method(self, mock_time):
        """Test _send_robot_command helper method."""
        # Mock time.time()
        mock_time.time.return_value = 1640995200

        # Create device
        mock_hass = Mock()
        mock_hass.bus = Mock()
        mock_hass.bus.async_listen_once = Mock()

        device = DysonDevice(
            hass=mock_hass,
            serial_number="VS6-EU-RJA1234A",
            host="192.168.1.100",
            credential="test_credential",
            mqtt_prefix="475",
            capabilities=["robot"],
            connection_type="local_only",
        )

        # Mock MQTT client
        mock_client = Mock()
        mock_client.is_connected.return_value = True
        mock_client.publish = Mock()
        device._mqtt_client = mock_client
        device._connected = True

        # Test _send_robot_command directly (it's protected but accessible)
        # Should pass dict structure as expected by the method
        test_command = {"msg": "PAUSE", "time": "2025-12-18T22:36:02Z"}
        await device._send_robot_command(test_command)

        # Verify publish was called with correct parameters
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        assert len(call_args[0]) == 2  # topic and payload
        topic = call_args[0][0]
        payload = call_args[0][1]

        assert topic.endswith("/command")

        # Verify payload structure
        command_data = json.loads(payload)
        assert command_data["msg"] == "PAUSE"
        assert command_data["time"] == "2025-12-18T22:36:02Z"

    def test_get_command_timestamp_method(self):
        """Test _get_command_timestamp helper method."""
        # Create device
        mock_hass = Mock()
        mock_hass.bus = Mock()
        mock_hass.bus.async_listen_once = Mock()

        device = DysonDevice(
            hass=mock_hass,
            serial_number="VS6-EU-RJA1234A",
            host="192.168.1.100",
            credential="test_credential",
            mqtt_prefix="475",
            capabilities=["robot"],
            connection_type="local_only",
        )

        # Test _get_command_timestamp (it's protected but accessible)
        timestamp = device._get_command_timestamp()

        # Should return a valid ISO timestamp string
        assert isinstance(timestamp, str)
        assert "T" in timestamp
        assert timestamp.endswith("Z")
        assert len(timestamp) == 20  # YYYY-MM-DDTHH:MM:SSZ format
