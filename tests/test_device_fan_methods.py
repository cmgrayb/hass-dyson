"""Tests for fan control device methods in DysonDevice."""

from unittest.mock import AsyncMock

import pytest

from custom_components.hass_dyson.device import DysonDevice


class TestDysonDeviceFanMethods:
    """Test fan-related device methods."""

    @pytest.mark.asyncio
    async def test_set_direction_forward(self):
        """Test setting fan direction to forward."""
        # Setup
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        # Execute
        await device.set_direction("forward")

        # Verify
        device.send_command.assert_called_once_with("STATE-SET", {"fdir": "ON"})

    @pytest.mark.asyncio
    async def test_set_direction_reverse(self):
        """Test setting fan direction to reverse."""
        # Setup
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        # Execute
        await device.set_direction("reverse")

        # Verify
        device.send_command.assert_called_once_with("STATE-SET", {"fdir": "OFF"})

    @pytest.mark.asyncio
    async def test_set_heating_mode_heat(self):
        """Test setting heating mode to HEAT."""
        # Setup
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        # Execute
        await device.set_heating_mode("HEAT")

        # Verify
        device.send_command.assert_called_once_with("STATE-SET", {"hmod": "HEAT"})

    @pytest.mark.asyncio
    async def test_set_heating_mode_off(self):
        """Test setting heating mode to OFF."""
        # Setup
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        # Execute
        await device.set_heating_mode("OFF")

        # Verify
        device.send_command.assert_called_once_with("STATE-SET", {"hmod": "OFF"})

    @pytest.mark.asyncio
    async def test_set_fan_state_off(self):
        """Test setting fan state to OFF."""
        # Setup
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        # Execute
        await device.set_fan_state("OFF")

        # Verify
        device.send_command.assert_called_once_with("STATE-SET", {"fnst": "OFF"})

    @pytest.mark.asyncio
    async def test_set_fan_state_fan(self):
        """Test setting fan state to FAN."""
        # Setup
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        # Execute
        await device.set_fan_state("FAN")

        # Verify
        device.send_command.assert_called_once_with("STATE-SET", {"fnst": "FAN"})

    @pytest.mark.asyncio
    async def test_set_direction_exception_handling(self):
        """Test exception handling in set_direction method."""
        # Setup
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock(side_effect=Exception("MQTT error"))

        # Execute & Verify
        with pytest.raises(Exception, match="MQTT error"):
            await device.set_direction("forward")

    @pytest.mark.asyncio
    async def test_set_heating_mode_exception_handling(self):
        """Test exception handling in set_heating_mode method."""
        # Setup
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock(side_effect=Exception("MQTT error"))

        # Execute & Verify
        with pytest.raises(Exception, match="MQTT error"):
            await device.set_heating_mode("HEAT")

    @pytest.mark.asyncio
    async def test_set_fan_state_exception_handling(self):
        """Test exception handling in set_fan_state method."""
        # Setup
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock(side_effect=Exception("MQTT error"))

        # Execute & Verify
        with pytest.raises(Exception, match="MQTT error"):
            await device.set_fan_state("OFF")

    @pytest.mark.asyncio
    async def test_direction_command_formatting(self):
        """Test that direction commands are formatted correctly."""
        # Setup
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        # Test various direction inputs
        test_cases = [
            ("forward", "ON"),
            ("reverse", "OFF"),
            ("Forward", "ON"),  # Case handling
            ("Reverse", "OFF"),
            ("FORWARD", "ON"),
            ("REVERSE", "OFF"),
        ]

        for direction, expected_value in test_cases:
            device.send_command.reset_mock()
            await device.set_direction(direction)
            device.send_command.assert_called_once_with(
                "STATE-SET", {"fdir": expected_value}
            )

    @pytest.mark.asyncio
    async def test_heating_mode_command_formatting(self):
        """Test that heating mode commands are formatted correctly."""
        # Setup
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        # Test various heating mode inputs
        test_modes = ["HEAT", "OFF", "AUTO"]

        for mode in test_modes:
            device.send_command.reset_mock()
            await device.set_heating_mode(mode)
            device.send_command.assert_called_once_with("STATE-SET", {"hmod": mode})

    @pytest.mark.asyncio
    async def test_fan_state_command_formatting(self):
        """Test that fan state commands are formatted correctly."""
        # Setup
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        # Test various fan state inputs
        test_states = ["OFF", "FAN", "AUTO"]

        for state in test_states:
            device.send_command.reset_mock()
            await device.set_fan_state(state)
            device.send_command.assert_called_once_with("STATE-SET", {"fnst": state})
