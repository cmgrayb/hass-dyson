"""Test device humidifier control methods."""

from unittest.mock import AsyncMock

import pytest

from custom_components.hass_dyson.device import DysonDevice


class TestDysonDeviceHumidifierMethods:
    """Test humidifier control methods in DysonDevice."""

    @pytest.mark.asyncio
    async def test_set_humidifier_mode_enabled(self):
        """Test setting humidifier mode to enabled."""
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        await device.set_humidifier_mode(True)

        device.send_command.assert_called_once_with(
            "STATE-SET", {"hume": "HUMD", "haut": "OFF"}
        )

    @pytest.mark.asyncio
    async def test_set_humidifier_mode_disabled(self):
        """Test setting humidifier mode to disabled."""
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        await device.set_humidifier_mode(False)

        device.send_command.assert_called_once_with(
            "STATE-SET", {"hume": "OFF", "haut": "OFF"}
        )

    @pytest.mark.asyncio
    async def test_set_humidifier_mode_with_auto(self):
        """Test setting humidifier mode to enabled with auto mode."""
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        await device.set_humidifier_mode(True, auto_mode=True)

        device.send_command.assert_called_once_with(
            "STATE-SET", {"hume": "HUMD", "haut": "ON"}
        )

    @pytest.mark.asyncio
    async def test_set_humidifier_mode_disabled_ignores_auto(self):
        """Test setting humidifier mode to disabled ignores auto_mode parameter."""
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        await device.set_humidifier_mode(False, auto_mode=True)

        device.send_command.assert_called_once_with(
            "STATE-SET", {"hume": "OFF", "haut": "OFF"}
        )

    @pytest.mark.asyncio
    async def test_set_target_humidity_valid_range(self):
        """Test setting target humidity within valid range."""
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        await device.set_target_humidity(40)

        device.send_command.assert_called_once_with("STATE-SET", {"humt": "0040"})

    @pytest.mark.asyncio
    async def test_set_target_humidity_minimum(self):
        """Test setting target humidity to minimum value."""
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        await device.set_target_humidity(30)

        device.send_command.assert_called_once_with("STATE-SET", {"humt": "0030"})

    @pytest.mark.asyncio
    async def test_set_target_humidity_maximum(self):
        """Test setting target humidity to maximum value."""
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        await device.set_target_humidity(50)

        device.send_command.assert_called_once_with("STATE-SET", {"humt": "0050"})

    @pytest.mark.asyncio
    async def test_set_target_humidity_below_minimum(self):
        """Test setting target humidity below minimum raises ValueError."""
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        with pytest.raises(
            ValueError, match="Target humidity must be between 30% and 50%"
        ):
            await device.set_target_humidity(29)

        device.send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_target_humidity_above_maximum(self):
        """Test setting target humidity above maximum raises ValueError."""
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        with pytest.raises(
            ValueError, match="Target humidity must be between 30% and 50%"
        ):
            await device.set_target_humidity(51)

        device.send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_target_humidity_formatting(self):
        """Test target humidity is formatted correctly as 4-digit string."""
        device = DysonDevice(
            "TEST-SERIAL", "127.0.0.1", 1883, "test_username", "test_password"
        )
        device.send_command = AsyncMock()

        # Test single digit
        await device.set_target_humidity(35)
        device.send_command.assert_called_with("STATE-SET", {"humt": "0035"})

        # Reset mock
        device.send_command.reset_mock()

        # Test double digit
        await device.set_target_humidity(45)
        device.send_command.assert_called_with("STATE-SET", {"humt": "0045"})
