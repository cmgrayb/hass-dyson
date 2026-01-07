"""Test error handling coverage for fan entity platform.

This module provides comprehensive error path testing for the fan entity,
covering exception handling in all async control methods.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.fan import DysonFan


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_coordinator(mock_hass):
    """Create a mock coordinator with full device setup."""
    coordinator = MagicMock()
    coordinator.hass = mock_hass
    coordinator.serial_number = "TEST-SERIAL-123"
    coordinator.device_category = "ec"

    # Mock device with all control methods
    device = MagicMock()
    device.set_fan_power = AsyncMock()
    device.set_fan_speed = AsyncMock()
    device.set_auto_mode = AsyncMock()
    device.set_direction = AsyncMock()
    device.set_heating_mode = AsyncMock()
    device.set_fan_state = AsyncMock()
    device.set_oscillation = AsyncMock()
    device.set_oscillation_angles = AsyncMock()
    device.set_target_temperature = AsyncMock()
    device.get_state_value = MagicMock(return_value="OFF")

    # Mock device properties for _handle_coordinator_update
    device.fan_power = True
    device.fan_state = "FAN"
    device.fan_speed_setting = "0005"
    device.fan_speed = 5  # For AUTO mode

    coordinator.device = device

    # Mock coordinator data with product-state
    coordinator.data = {
        "product-state": {
            "fpwr": "ON",
            "fnst": "FAN",
            "fnsp": "0005",
            "auto": "OFF",
            "fdir": "ON",  # Direction support
            "oson": "OFF",  # Oscillation support
            "nmod": "OFF",
            "osal": "0000",
            "osau": "0350",
            "sltm": "OFF",
        }
    }

    coordinator.async_request_refresh = AsyncMock()
    return coordinator


# Note: async_turn_on, async_turn_off, and async_set_percentage do not have
# try-except blocks in the actual implementation. They allow exceptions to propagate.
# Error handling tests focus on methods that actually handle errors.


class TestAsyncSetDirectionErrorHandling:
    """Test error handling in async_set_direction method."""

    @pytest.mark.asyncio
    async def test_async_set_direction_connection_error(self, mock_coordinator):
        """Test async_set_direction handles ConnectionError."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_direction.side_effect = ConnectionError(
            "Connection lost"
        )

        # Act
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await fan.async_set_direction("forward")

        # Assert - method was called, error was logged
        mock_coordinator.device.set_direction.assert_called_once_with("forward")

    @pytest.mark.asyncio
    async def test_async_set_direction_timeout_error(self, mock_coordinator):
        """Test async_set_direction handles TimeoutError."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_direction.side_effect = TimeoutError(
            "Command timeout"
        )

        # Act
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await fan.async_set_direction("reverse")

        # Assert
        mock_coordinator.device.set_direction.assert_called_once_with("reverse")

    @pytest.mark.asyncio
    async def test_async_set_direction_value_error(self, mock_coordinator):
        """Test async_set_direction handles ValueError for invalid direction."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_direction.side_effect = ValueError(
            "Invalid direction value"
        )

        # Act
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await fan.async_set_direction("invalid")

        # Assert
        mock_coordinator.device.set_direction.assert_called_once_with("invalid")

    @pytest.mark.asyncio
    async def test_async_set_direction_key_error(self, mock_coordinator):
        """Test async_set_direction handles KeyError for missing keys."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_direction.side_effect = KeyError("fdir")

        # Act
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await fan.async_set_direction("forward")

        # Assert
        mock_coordinator.device.set_direction.assert_called_once_with("forward")

    @pytest.mark.asyncio
    async def test_async_set_direction_generic_exception(self, mock_coordinator):
        """Test async_set_direction handles generic Exception."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_direction.side_effect = Exception(
            "Unexpected error"
        )

        # Act
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await fan.async_set_direction("forward")

        # Assert
        mock_coordinator.device.set_direction.assert_called_once_with("forward")


class TestAsyncSetPresetModeErrorHandling:
    """Test error handling in async_set_preset_mode method."""

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_auto_connection_error(self, mock_coordinator):
        """Test async_set_preset_mode Auto handles ConnectionError."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_auto_mode.side_effect = ConnectionError(
            "Connection lost"
        )

        # Act
        with (
            patch.object(fan, "async_write_ha_state"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await fan.async_set_preset_mode("Auto")

        # Assert
        mock_coordinator.device.set_auto_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_manual_timeout_error(self, mock_coordinator):
        """Test async_set_preset_mode Manual handles TimeoutError."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_auto_mode.side_effect = TimeoutError(
            "Command timeout"
        )

        # Act
        with (
            patch.object(fan, "async_write_ha_state"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await fan.async_set_preset_mode("Manual")

        # Assert
        mock_coordinator.device.set_auto_mode.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_heat_connection_error(self, mock_coordinator):
        """Test async_set_preset_mode Heat handles ConnectionError."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        fan._has_heating = True
        mock_coordinator.device.set_heating_mode.side_effect = ConnectionError(
            "Connection lost"
        )

        # Act
        with (
            patch.object(fan, "async_write_ha_state"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await fan.async_set_preset_mode("Heat")

        # Assert
        mock_coordinator.device.set_heating_mode.assert_called_once_with("HEAT")

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_value_error(self, mock_coordinator):
        """Test async_set_preset_mode handles ValueError."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_auto_mode.side_effect = ValueError("Invalid mode")

        # Act
        with (
            patch.object(fan, "async_write_ha_state"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await fan.async_set_preset_mode("Auto")

        # Assert
        mock_coordinator.device.set_auto_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_key_error(self, mock_coordinator):
        """Test async_set_preset_mode handles KeyError."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_auto_mode.side_effect = KeyError("auto")

        # Act
        with (
            patch.object(fan, "async_write_ha_state"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await fan.async_set_preset_mode("Auto")

        # Assert
        mock_coordinator.device.set_auto_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_generic_exception(self, mock_coordinator):
        """Test async_set_preset_mode handles generic Exception."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_auto_mode.side_effect = Exception(
            "Unexpected error"
        )

        # Act
        with (
            patch.object(fan, "async_write_ha_state"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await fan.async_set_preset_mode("Auto")

        # Assert
        mock_coordinator.device.set_auto_mode.assert_called_once_with(True)


class TestAsyncOscillateErrorHandling:
    """Test error handling in async_oscillate method."""

    @pytest.mark.asyncio
    async def test_async_oscillate_connection_error(self, mock_coordinator):
        """Test async_oscillate handles ConnectionError."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_oscillation.side_effect = ConnectionError(
            "Connection lost"
        )

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_oscillate(True)

        # Assert
        mock_coordinator.device.set_oscillation.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_async_oscillate_timeout_error(self, mock_coordinator):
        """Test async_oscillate handles TimeoutError."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_oscillation.side_effect = TimeoutError(
            "Command timeout"
        )

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_oscillate(False)

        # Assert
        mock_coordinator.device.set_oscillation.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_async_oscillate_attribute_error(self, mock_coordinator):
        """Test async_oscillate handles AttributeError."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_oscillation.side_effect = AttributeError(
            "Method not available"
        )

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_oscillate(True)

        # Assert
        mock_coordinator.device.set_oscillation.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_async_oscillate_generic_exception(self, mock_coordinator):
        """Test async_oscillate handles generic Exception."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_oscillation.side_effect = Exception(
            "Unexpected error"
        )

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_oscillate(True)

        # Assert
        mock_coordinator.device.set_oscillation.assert_called_once_with(True)


class TestAsyncSetAngleErrorHandling:
    """Test error handling in async_set_angle method."""

    @pytest.mark.asyncio
    async def test_async_set_angle_connection_error(self, mock_coordinator):
        """Test async_set_angle handles ConnectionError."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_oscillation_angles.side_effect = ConnectionError(
            "Connection lost"
        )

        # Act - should not raise
        await fan.async_set_angle(45, 315)

        # Assert
        mock_coordinator.device.set_oscillation_angles.assert_called_once_with(45, 315)

    @pytest.mark.asyncio
    async def test_async_set_angle_timeout_error(self, mock_coordinator):
        """Test async_set_angle handles TimeoutError."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_oscillation_angles.side_effect = TimeoutError(
            "Command timeout"
        )

        # Act
        await fan.async_set_angle(90, 270)

        # Assert
        mock_coordinator.device.set_oscillation_angles.assert_called_once_with(90, 270)

    @pytest.mark.asyncio
    async def test_async_set_angle_value_error(self, mock_coordinator):
        """Test async_set_angle handles ValueError for invalid angles."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_oscillation_angles.side_effect = ValueError(
            "Invalid angle range"
        )

        # Act
        await fan.async_set_angle(350, 10)

        # Assert
        mock_coordinator.device.set_oscillation_angles.assert_called_once_with(350, 10)

    @pytest.mark.asyncio
    async def test_async_set_angle_generic_exception(self, mock_coordinator):
        """Test async_set_angle handles generic Exception."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_oscillation_angles.side_effect = Exception(
            "Unexpected error"
        )

        # Act
        await fan.async_set_angle(0, 180)

        # Assert
        mock_coordinator.device.set_oscillation_angles.assert_called_once_with(0, 180)


class TestAsyncSetTemperatureErrorHandling:
    """Test error handling in async_set_temperature method for heating devices."""

    @pytest.mark.asyncio
    async def test_async_set_temperature_connection_error(self, mock_coordinator):
        """Test async_set_temperature handles ConnectionError."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        fan._has_heating = True
        mock_coordinator.device.set_target_temperature.side_effect = ConnectionError(
            "Connection lost"
        )

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_set_temperature(temperature=22.0)

        # Assert
        mock_coordinator.device.set_target_temperature.assert_called_once_with(22.0)

    @pytest.mark.asyncio
    async def test_async_set_temperature_timeout_error(self, mock_coordinator):
        """Test async_set_temperature handles TimeoutError."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        fan._has_heating = True
        mock_coordinator.device.set_target_temperature.side_effect = TimeoutError(
            "Command timeout"
        )

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_set_temperature(temperature=24.5)

        # Assert
        mock_coordinator.device.set_target_temperature.assert_called_once_with(24.5)

    @pytest.mark.asyncio
    async def test_async_set_temperature_value_error(self, mock_coordinator):
        """Test async_set_temperature handles ValueError for invalid temperature."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        fan._has_heating = True
        mock_coordinator.device.set_target_temperature.side_effect = ValueError(
            "Temperature out of range"
        )

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_set_temperature(temperature=50.0)

        # Assert
        mock_coordinator.device.set_target_temperature.assert_called_once_with(50.0)

    @pytest.mark.asyncio
    async def test_async_set_temperature_generic_exception(self, mock_coordinator):
        """Test async_set_temperature handles generic Exception."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        fan._has_heating = True
        mock_coordinator.device.set_target_temperature.side_effect = Exception(
            "Unexpected error"
        )

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_set_temperature(temperature=20.0)

        # Assert
        mock_coordinator.device.set_target_temperature.assert_called_once_with(20.0)


class TestAsyncSetHvacModeErrorHandling:
    """Test error handling in async_set_hvac_mode method for heating devices."""

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_off_connection_error(self, mock_coordinator):
        """Test async_set_hvac_mode OFF handles ConnectionError."""
        # Arrange
        from homeassistant.components.climate import HVACMode

        fan = DysonFan(mock_coordinator)
        fan._has_heating = True
        mock_coordinator.device.set_fan_state.side_effect = ConnectionError(
            "Connection lost"
        )

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_set_hvac_mode(HVACMode.OFF)

        # Assert
        mock_coordinator.device.set_fan_state.assert_called_once_with("OFF")

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_heat_timeout_error(self, mock_coordinator):
        """Test async_set_hvac_mode HEAT handles TimeoutError."""
        # Arrange
        from homeassistant.components.climate import HVACMode

        fan = DysonFan(mock_coordinator)
        fan._has_heating = True
        mock_coordinator.device.set_heating_mode.side_effect = TimeoutError(
            "Command timeout"
        )

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_set_hvac_mode(HVACMode.HEAT)

        # Assert
        mock_coordinator.device.set_heating_mode.assert_called_once_with("HEAT")

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_fan_only_value_error(self, mock_coordinator):
        """Test async_set_hvac_mode FAN_ONLY handles ValueError."""
        # Arrange
        from homeassistant.components.climate import HVACMode

        fan = DysonFan(mock_coordinator)
        fan._has_heating = True
        mock_coordinator.device.set_fan_state.side_effect = ValueError(
            "Invalid fan state"
        )

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_set_hvac_mode(HVACMode.FAN_ONLY)

        # Assert
        mock_coordinator.device.set_fan_state.assert_called_once_with("FAN")

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_auto_key_error(self, mock_coordinator):
        """Test async_set_hvac_mode AUTO handles KeyError."""
        # Arrange
        from homeassistant.components.climate import HVACMode

        fan = DysonFan(mock_coordinator)
        fan._has_heating = True
        mock_coordinator.device.set_auto_mode.side_effect = KeyError("auto")

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_set_hvac_mode(HVACMode.AUTO)

        # Assert
        mock_coordinator.device.set_auto_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_generic_exception(self, mock_coordinator):
        """Test async_set_hvac_mode handles generic Exception."""
        # Arrange
        from homeassistant.components.climate import HVACMode

        fan = DysonFan(mock_coordinator)
        fan._has_heating = True
        mock_coordinator.device.set_heating_mode.side_effect = Exception(
            "Unexpected error"
        )

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_set_hvac_mode(HVACMode.HEAT)

        # Assert
        mock_coordinator.device.set_heating_mode.assert_called_once_with("HEAT")


class TestHandleCoordinatorUpdateErrorHandling:
    """Test error handling in _handle_coordinator_update method."""

    def test_handle_coordinator_update_invalid_speed_value_error(
        self, mock_coordinator
    ):
        """Test _handle_coordinator_update handles ValueError for invalid speed."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        # Mock the device property to return invalid value
        mock_coordinator.device.fan_speed_setting = "INVALID"

        # Act - should not raise
        with patch.object(fan, "async_write_ha_state"):
            fan._handle_coordinator_update()

        # Assert - percentage should default to 0
        assert fan._attr_percentage == 0

    def test_handle_coordinator_update_speed_type_error(self, mock_coordinator):
        """Test _handle_coordinator_update handles TypeError for non-string speed."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        # Mock the device property to return None
        mock_coordinator.device.fan_speed_setting = None

        # Act
        with patch.object(fan, "async_write_ha_state"):
            fan._handle_coordinator_update()

        # Assert - percentage should default to 0
        assert fan._attr_percentage == 0


class TestExtraStateAttributesErrorHandling:
    """Test error handling in extra_state_attributes property."""

    def test_extra_state_attributes_invalid_angle_value_error(self, mock_coordinator):
        """Test extra_state_attributes handles ValueError for invalid angles."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.data["product-state"]["osal"] = "INVALID"
        mock_coordinator.data["product-state"]["osau"] = "0350"

        # Act - should not raise
        attributes = fan.extra_state_attributes

        # Assert - angle attributes should not be present
        assert "angle_low" not in attributes
        assert "angle_high" not in attributes
        assert "oscillation_span" not in attributes

    def test_extra_state_attributes_angle_type_error(self, mock_coordinator):
        """Test extra_state_attributes handles TypeError for None angles."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.data["product-state"]["osal"] = None
        mock_coordinator.data["product-state"]["osau"] = None

        # Act
        attributes = fan.extra_state_attributes

        # Assert - angle attributes should not be present
        assert "angle_low" not in attributes
        assert "angle_high" not in attributes

    def test_extra_state_attributes_invalid_sleep_timer_value_error(
        self, mock_coordinator
    ):
        """Test extra_state_attributes handles ValueError for invalid sleep timer."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.data["product-state"]["sltm"] = "INVALID"

        # Act
        attributes = fan.extra_state_attributes

        # Assert - sleep_timer should default to 0
        assert attributes["sleep_timer"] == 0

    def test_extra_state_attributes_sleep_timer_type_error(self, mock_coordinator):
        """Test extra_state_attributes handles TypeError for None sleep timer."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.data["product-state"]["sltm"] = None

        # Act
        attributes = fan.extra_state_attributes

        # Assert - sleep_timer should default to 0
        assert attributes["sleep_timer"] == 0


class TestUpdateHeatingDataErrorHandling:
    """Test error handling in _update_heating_data method."""

    def test_update_heating_data_invalid_current_temp_value_error(
        self, mock_coordinator
    ):
        """Test _update_heating_data handles ValueError for invalid current temperature."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        fan._has_heating = True
        product_state = {"tmp": "INVALID", "hmax": "2931", "hmod": "HEAT", "fpwr": "ON"}

        # Act - should not raise
        fan._update_heating_data(product_state)

        # Assert - current_temperature should be None
        assert fan._attr_current_temperature is None

    def test_update_heating_data_current_temp_type_error(self, mock_coordinator):
        """Test _update_heating_data handles TypeError for None current temperature."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        fan._has_heating = True
        product_state = {"tmp": None, "hmax": "2931", "hmod": "HEAT", "fpwr": "ON"}

        # Act
        fan._update_heating_data(product_state)

        # Assert - current_temperature should be None
        assert fan._attr_current_temperature is None

    def test_update_heating_data_invalid_target_temp_value_error(
        self, mock_coordinator
    ):
        """Test _update_heating_data handles ValueError for invalid target temperature."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        fan._has_heating = True
        product_state = {"tmp": "2981", "hmax": "INVALID", "hmod": "HEAT", "fpwr": "ON"}

        # Act
        fan._update_heating_data(product_state)

        # Assert - target_temperature should default to 20.0°C
        assert fan._attr_target_temperature == 20.0

    def test_update_heating_data_target_temp_type_error(self, mock_coordinator):
        """Test _update_heating_data handles TypeError for None target temperature."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        fan._has_heating = True
        product_state = {"tmp": "2981", "hmax": None, "hmod": "HEAT", "fpwr": "ON"}

        # Act
        fan._update_heating_data(product_state)

        # Assert - target_temperature should default to 20.0°C
        assert fan._attr_target_temperature == 20.0
