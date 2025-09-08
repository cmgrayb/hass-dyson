"""Test fan platform for Dyson integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.fan import FanEntityFeature
from homeassistant.config_entries import ConfigEntry

from custom_components.hass_dyson.const import DOMAIN
from custom_components.hass_dyson.fan import SERVICE_SET_ANGLE, SET_ANGLE_SCHEMA, DysonFan, async_setup_entry


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-SERIAL-123"
    coordinator.device_name = "Test Device"
    coordinator.device_category = "ec"  # Environment Cleaner
    coordinator.data = {
        "product-state": {
            "fpwr": "ON",  # Fan power
            "fnst": "FAN",  # Fan state
            "fnsp": "0005",  # Fan speed
            "auto": "OFF",  # Auto mode
        }
    }

    # Mock device with all required methods
    coordinator.device = MagicMock()
    coordinator.device.fan_power = True
    coordinator.device.fan_state = "FAN"
    coordinator.device.fan_speed_setting = "0005"
    coordinator.device.fan_speed = 5
    coordinator.device.set_fan_power = AsyncMock()
    coordinator.device.set_fan_speed = AsyncMock()
    coordinator.device.set_auto_mode = AsyncMock()
    coordinator.device.send_command = AsyncMock()
    coordinator.device._get_current_value = MagicMock(return_value="OFF")
    coordinator.async_request_refresh = AsyncMock()

    return coordinator


class TestFanPlatformSetup:
    """Test fan platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_fan_for_ec_device(self, mock_coordinator):
        """Test that async_setup_entry creates fan entity for EC devices."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.entry_id = "test_entry"
        async_add_entities = AsyncMock()

        hass.data = {DOMAIN: {"test_entry": mock_coordinator}}
        mock_coordinator.device_category = "ec"  # Environment Cleaner

        # Mock the entity platform to avoid RuntimeError
        with patch("custom_components.hass_dyson.fan.entity_platform.async_get_current_platform") as mock_platform:
            mock_platform_instance = MagicMock()
            mock_platform.return_value = mock_platform_instance

            # Act
            await async_setup_entry(hass, config_entry, async_add_entities)

            # Assert
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]
            assert len(entities) == 1
            assert isinstance(entities[0], DysonFan)

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_fan_for_non_ec_device(self, mock_coordinator):
        """Test that async_setup_entry doesn't create fan for non-EC devices."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.entry_id = "test_entry"
        async_add_entities = AsyncMock()

        hass.data = {DOMAIN: {"test_entry": mock_coordinator}}
        mock_coordinator.device_category = "robot"  # Not EC

        # Mock the entity platform to avoid RuntimeError
        with patch("custom_components.hass_dyson.fan.entity_platform.async_get_current_platform") as mock_platform:
            mock_platform_instance = MagicMock()
            mock_platform.return_value = mock_platform_instance

            # Act
            await async_setup_entry(hass, config_entry, async_add_entities)

            # Assert
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]
            assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_async_setup_entry_registers_set_angle_service(self, mock_coordinator):
        """Test that async_setup_entry registers the set_angle service."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.entry_id = "test_entry"
        async_add_entities = AsyncMock()

        hass.data = {DOMAIN: {"test_entry": mock_coordinator}}
        mock_coordinator.device_category = "ec"

        with patch("custom_components.hass_dyson.fan.entity_platform.async_get_current_platform") as mock_platform:
            mock_platform_instance = MagicMock()
            mock_platform.return_value = mock_platform_instance

            # Act
            await async_setup_entry(hass, config_entry, async_add_entities)

            # Assert
            mock_platform_instance.async_register_entity_service.assert_called_once_with(
                SERVICE_SET_ANGLE,
                SET_ANGLE_SCHEMA,
                "async_set_angle",
            )


class TestDysonFan:
    """Test DysonFan entity."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        fan = DysonFan(mock_coordinator)

        # Assert
        assert fan.coordinator == mock_coordinator
        assert fan._attr_unique_id == "TEST-SERIAL-123_fan"
        assert fan._attr_name == "Test Device"
        assert fan._attr_supported_features == (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.DIRECTION
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        assert fan._attr_speed_count == 10
        assert fan._attr_percentage_step == 10
        assert fan._attr_preset_modes == ["Auto", "Manual"]
        assert fan._attr_is_on is None
        assert fan._attr_percentage == 0
        assert fan._attr_current_direction == "forward"
        assert fan._attr_preset_mode is None
        assert fan._attr_oscillating is False

    def test_handle_coordinator_update_fan_on(self, mock_coordinator):
        """Test _handle_coordinator_update when fan is on."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.fan_power = True
        mock_coordinator.device.fan_state = "FAN"
        mock_coordinator.device.fan_speed_setting = "0005"
        mock_coordinator.device._get_current_value.return_value = "OFF"  # Manual mode

        # Act
        with patch.object(fan, "async_write_ha_state"):
            fan._handle_coordinator_update()

        # Assert
        assert fan._attr_is_on is True
        assert fan._attr_percentage == 50  # 5 * 10
        assert fan._attr_current_direction == "forward"
        assert fan._attr_preset_mode == "Manual"
        assert fan._attr_oscillating is False

    def test_handle_coordinator_update_fan_off(self, mock_coordinator):
        """Test _handle_coordinator_update when fan is off."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.fan_power = False
        mock_coordinator.device.fan_state = "OFF"
        mock_coordinator.device.fan_speed_setting = "0000"

        # Act
        with patch.object(fan, "async_write_ha_state"):
            fan._handle_coordinator_update()

        # Assert
        assert fan._attr_is_on is False
        assert fan._attr_percentage == 0

    def test_handle_coordinator_update_auto_mode(self, mock_coordinator):
        """Test _handle_coordinator_update with auto mode."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.fan_power = True
        mock_coordinator.device.fan_speed_setting = "AUTO"
        mock_coordinator.device.fan_speed = 7  # Actual speed
        mock_coordinator.device._get_current_value.return_value = "ON"  # Auto mode

        # Act
        with patch.object(fan, "async_write_ha_state"):
            fan._handle_coordinator_update()

        # Assert
        assert fan._attr_is_on is True
        assert fan._attr_percentage == 70  # 7 * 10
        assert fan._attr_preset_mode == "Auto"

    def test_handle_coordinator_update_invalid_speed(self, mock_coordinator):
        """Test _handle_coordinator_update with invalid speed setting."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.fan_power = True
        mock_coordinator.device.fan_speed_setting = "INVALID"

        # Act
        with patch.object(fan, "async_write_ha_state"):
            fan._handle_coordinator_update()

        # Assert
        assert fan._attr_percentage == 0

    def test_handle_coordinator_update_no_device(self, mock_coordinator):
        """Test _handle_coordinator_update when no device available."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device = None

        # Act
        fan._handle_coordinator_update()

        # Assert - should return early without errors

    def test_is_on_property(self, mock_coordinator):
        """Test is_on property."""
        # Arrange
        fan = DysonFan(mock_coordinator)

        # Test when _attr_is_on is True
        fan._attr_is_on = True
        assert fan.is_on is True

        # Test when _attr_is_on is False
        fan._attr_is_on = False
        assert fan.is_on is False

        # Test when _attr_is_on is None
        fan._attr_is_on = None
        assert fan.is_on is False

    @pytest.mark.asyncio
    async def test_async_turn_on_basic(self, mock_coordinator):
        """Test async_turn_on with basic call."""
        # Arrange
        fan = DysonFan(mock_coordinator)

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_turn_on()

        # Assert
        mock_coordinator.device.set_fan_power.assert_called_once_with(True)
        assert fan._attr_is_on is True

    @pytest.mark.asyncio
    async def test_async_turn_on_with_percentage(self, mock_coordinator):
        """Test async_turn_on with percentage setting."""
        # Arrange
        fan = DysonFan(mock_coordinator)

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_turn_on(percentage=75)

        # Assert
        mock_coordinator.device.set_fan_power.assert_called_once_with(True)
        mock_coordinator.device.set_fan_speed.assert_called_once_with(8)  # 75 -> speed 8
        assert fan._attr_is_on is True

    @pytest.mark.asyncio
    async def test_async_turn_on_with_preset_mode(self, mock_coordinator):
        """Test async_turn_on with preset mode setting."""
        # Arrange
        fan = DysonFan(mock_coordinator)

        # Act
        with (
            patch.object(fan, "async_write_ha_state"),
            patch.object(fan, "async_set_preset_mode", new_callable=AsyncMock) as mock_set_preset,
        ):
            await fan.async_turn_on(preset_mode="Auto")

        # Assert
        mock_coordinator.device.set_fan_power.assert_called_once_with(True)
        mock_set_preset.assert_called_once_with("Auto")

    @pytest.mark.asyncio
    async def test_async_turn_on_no_device(self, mock_coordinator):
        """Test async_turn_on when no device available."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device = None

        # Act
        await fan.async_turn_on()

        # Assert - should return without error, no calls made

    @pytest.mark.asyncio
    async def test_async_turn_off(self, mock_coordinator):
        """Test async_turn_off."""
        # Arrange
        fan = DysonFan(mock_coordinator)

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_turn_off()

        # Assert
        mock_coordinator.device.set_fan_power.assert_called_once_with(False)
        assert fan._attr_is_on is False

    @pytest.mark.asyncio
    async def test_async_turn_off_no_device(self, mock_coordinator):
        """Test async_turn_off when no device available."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device = None

        # Act
        await fan.async_turn_off()

        # Assert - should return without error, no calls made

    @pytest.mark.asyncio
    async def test_async_set_percentage(self, mock_coordinator):
        """Test async_set_percentage with valid percentage."""
        # Arrange
        fan = DysonFan(mock_coordinator)

        # Act
        await fan.async_set_percentage(60)

        # Assert
        mock_coordinator.device.set_fan_speed.assert_called_once_with(6)  # 60 -> speed 6

    @pytest.mark.asyncio
    async def test_async_set_percentage_zero(self, mock_coordinator):
        """Test async_set_percentage with zero (turn off)."""
        # Arrange
        fan = DysonFan(mock_coordinator)

        # Act
        with patch.object(fan, "async_turn_off", new_callable=AsyncMock) as mock_turn_off:
            await fan.async_set_percentage(0)

        # Assert
        mock_turn_off.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_percentage_no_device(self, mock_coordinator):
        """Test async_set_percentage when no device available."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device = None

        # Act
        await fan.async_set_percentage(50)

        # Assert - should return without error, no calls made

    @pytest.mark.asyncio
    async def test_async_set_direction_forward(self, mock_coordinator):
        """Test async_set_direction with forward direction."""
        # Arrange
        fan = DysonFan(mock_coordinator)

        # Act
        with patch.object(fan, "async_write_ha_state"), patch("asyncio.sleep", new_callable=AsyncMock):
            await fan.async_set_direction("forward")

        # Assert
        mock_coordinator.device.send_command.assert_called_once_with("STATE-SET", {"fdir": "OFF"})
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_direction_reverse(self, mock_coordinator):
        """Test async_set_direction with reverse direction."""
        # Arrange
        fan = DysonFan(mock_coordinator)

        # Act
        with patch.object(fan, "async_write_ha_state"), patch("asyncio.sleep", new_callable=AsyncMock):
            await fan.async_set_direction("reverse")

        # Assert
        mock_coordinator.device.send_command.assert_called_once_with("STATE-SET", {"fdir": "ON"})

    @pytest.mark.asyncio
    async def test_async_set_direction_error_handling(self, mock_coordinator):
        """Test async_set_direction error handling."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.send_command.side_effect = Exception("Test error")

        # Act - should not raise exception
        await fan.async_set_direction("forward")

        # Assert
        mock_coordinator.device.send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_auto(self, mock_coordinator):
        """Test async_set_preset_mode with Auto mode."""
        # Arrange
        fan = DysonFan(mock_coordinator)

        # Act
        await fan.async_set_preset_mode("Auto")

        # Assert
        mock_coordinator.device.set_auto_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_manual(self, mock_coordinator):
        """Test async_set_preset_mode with Manual mode."""
        # Arrange
        fan = DysonFan(mock_coordinator)

        # Act
        await fan.async_set_preset_mode("Manual")

        # Assert
        mock_coordinator.device.set_auto_mode.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_no_device(self, mock_coordinator):
        """Test async_set_preset_mode when no device available."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device = None

        # Act
        await fan.async_set_preset_mode("Auto")

        # Assert - should return without error, no calls made


class TestFanIntegration:
    """Test fan integration scenarios."""

    def test_all_fan_features_supported(self, mock_coordinator):
        """Test that fan entity supports all expected features."""
        # Arrange & Act
        fan = DysonFan(mock_coordinator)

        # Assert
        expected_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.DIRECTION
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        assert fan._attr_supported_features == expected_features

    def test_fan_inherits_from_correct_base_classes(self, mock_coordinator):
        """Test that DysonFan inherits from correct base classes."""
        # Arrange & Act
        fan = DysonFan(mock_coordinator)

        # Assert
        from homeassistant.components.fan import FanEntity

        from custom_components.hass_dyson.entity import DysonEntity

        assert isinstance(fan, DysonEntity)
        assert isinstance(fan, FanEntity)

    def test_coordinator_type_annotation(self, mock_coordinator):
        """Test that coordinator type annotation is correct."""
        # Arrange & Act
        fan = DysonFan(mock_coordinator)

        # Assert
        # Check that the coordinator is properly assigned
        assert fan.coordinator == mock_coordinator
        # Check that the class has the coordinator attribute
        assert hasattr(fan, "coordinator")
        # Note: Runtime type checking would require more complex inspection

    @pytest.mark.asyncio
    async def test_fan_state_consistency_across_updates(self, mock_coordinator):
        """Test that fan state remains consistent across coordinator updates."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.fan_power = True
        mock_coordinator.device.fan_speed_setting = "0007"

        # Act - trigger multiple updates
        with patch.object(fan, "async_write_ha_state"):
            fan._handle_coordinator_update()
            initial_state = fan._attr_is_on
            initial_percentage = fan._attr_percentage

            fan._handle_coordinator_update()
            final_state = fan._attr_is_on
            final_percentage = fan._attr_percentage

        # Assert
        assert initial_state == final_state
        assert initial_percentage == final_percentage
        assert final_percentage == 70  # 7 * 10
