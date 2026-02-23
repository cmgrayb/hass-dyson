"""Test fan platform for Dyson integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.fan import FanEntityFeature
from homeassistant.config_entries import ConfigEntry

from custom_components.hass_dyson.const import DOMAIN
from custom_components.hass_dyson.fan import DysonFan, async_setup_entry


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
            "fdir": "ON",  # Fan direction - include to enable direction support
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
    coordinator.device.set_direction = AsyncMock()
    coordinator.device.set_heating_mode = AsyncMock()
    coordinator.device.set_fan_state = AsyncMock()
    coordinator.device.send_command = AsyncMock()
    coordinator.device.get_state_value = MagicMock(return_value="OFF")
    coordinator.async_request_refresh = AsyncMock()
    coordinator.device_capabilities = []  # Add device capabilities mock

    return coordinator


@pytest.fixture
def mock_coordinator_no_direction():
    """Create a mock coordinator without direction support."""
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
            # No "fdir" key - direction not supported
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
    coordinator.device.set_direction = AsyncMock()
    coordinator.device.set_heating_mode = AsyncMock()
    coordinator.device.set_fan_state = AsyncMock()
    coordinator.device.send_command = AsyncMock()
    coordinator.device.get_state_value = MagicMock(return_value="OFF")
    coordinator.async_request_refresh = AsyncMock()
    coordinator.device_capabilities = []  # Add device capabilities mock

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
        async_add_entities = MagicMock()

        hass.data = {DOMAIN: {"test_entry": mock_coordinator}}
        mock_coordinator.device_category = "ec"  # Environment Cleaner

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
        async_add_entities = MagicMock()

        hass.data = {DOMAIN: {"test_entry": mock_coordinator}}
        mock_coordinator.device_category = "robot"  # Not EC

        # Act
        await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 0


class TestDysonFan:
    """Test DysonFan entity."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        fan = DysonFan(mock_coordinator)

        # Assert
        assert fan.coordinator == mock_coordinator
        assert fan._attr_unique_id == "TEST-SERIAL-123_fan"
        assert fan._attr_name is None  # Uses device name from device_info
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

    def test_init_sets_attributes_correctly_no_direction_support(
        self, mock_coordinator_no_direction
    ):
        """Test that __init__ sets attributes correctly when direction is not supported."""
        # Act
        fan = DysonFan(mock_coordinator_no_direction)

        # Assert - should not include DIRECTION feature
        expected_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        assert fan._attr_supported_features == expected_features
        assert not fan._direction_supported

    def test_handle_coordinator_update_fan_on(self, mock_coordinator):
        """Test _handle_coordinator_update when fan is on."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.fan_power = True
        mock_coordinator.device.fan_state = "FAN"
        mock_coordinator.device.fan_speed_setting = "0005"
        # Mock different values for different keys

        def mockget_state_value(data, key, default):
            if key == "auto":
                return "OFF"  # Manual mode
            elif key == "fdir":
                return "OFF"  # Reverse direction
            return default

        mock_coordinator.device.get_state_value.side_effect = mockget_state_value

        # Act
        with patch.object(fan, "async_write_ha_state"):
            fan._handle_coordinator_update()

        # Assert
        assert fan._attr_is_on is True
        assert fan._attr_percentage == 50  # 5 * 10
        assert (
            fan._attr_current_direction == "reverse"
        )  # fdir=OFF means reverse direction

    def test_handle_coordinator_update_fan_on_forward_direction(self, mock_coordinator):
        """Test _handle_coordinator_update when fan is on with forward direction."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.fan_power = True
        mock_coordinator.device.fan_state = "FAN"
        mock_coordinator.device.fan_speed_setting = "0005"
        mock_coordinator.device.auto_mode = False  # Manual mode

        def mockget_state_value(data, key, default):
            if key == "fdir":
                return "ON"  # Forward direction
            return default

        mock_coordinator.device.get_state_value.side_effect = mockget_state_value

        # Act
        with patch.object(fan, "async_write_ha_state"):
            fan._handle_coordinator_update()

        # Assert
        assert fan._attr_is_on is True
        assert fan._attr_percentage == 50  # 5 * 10
        assert (
            fan._attr_current_direction == "forward"
        )  # fdir=ON means forward direction
        assert fan._attr_preset_mode == "Manual"
        assert fan._attr_oscillating is False

    def test_handle_coordinator_update_fan_auto_mode_via_fmod(self, mock_coordinator):
        """Test fan in auto mode via fmod key (TP02/HP02 Link devices)."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.fan_power = True
        mock_coordinator.device.fan_state = "FAN"
        mock_coordinator.device.fan_speed_setting = "AUTO"
        mock_coordinator.device.auto_mode = True  # Auto mode via fmod="AUTO"

        # Act
        with patch.object(fan, "async_write_ha_state"):
            fan._handle_coordinator_update()

        # Assert
        assert fan._attr_is_on is True
        assert fan._attr_preset_mode == "Auto"

    def test_handle_coordinator_update_fan_auto_mode_via_auto_key(
        self, mock_coordinator
    ):
        """Test fan in auto mode via auto key (non-TP02 devices)."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.fan_power = True
        mock_coordinator.device.fan_state = "FAN"
        mock_coordinator.device.fan_speed_setting = "AUTO"
        mock_coordinator.device.auto_mode = True  # Auto mode via auto key

        # Act
        with patch.object(fan, "async_write_ha_state"):
            fan._handle_coordinator_update()

        # Assert
        assert fan._attr_is_on is True
        assert fan._attr_preset_mode == "Auto"

    def test_handle_coordinator_update_fan_manual_mode(self, mock_coordinator):
        """Test fan in manual mode (both fmod and auto indicate manual)."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.fan_power = True
        mock_coordinator.device.fan_state = "FAN"
        mock_coordinator.device.fan_speed_setting = "0005"
        mock_coordinator.device.auto_mode = False  # Manual mode

        # Act
        with patch.object(fan, "async_write_ha_state"):
            fan._handle_coordinator_update()

        # Assert
        assert fan._attr_is_on is True
        assert fan._attr_preset_mode == "Manual"

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
        mock_coordinator.device.get_state_value.return_value = "ON"  # Auto mode

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
        mock_coordinator.device.set_fan_speed.assert_called_once_with(
            8
        )  # 75 -> speed 8
        assert fan._attr_is_on is True

    @pytest.mark.asyncio
    async def test_async_turn_on_with_preset_mode(self, mock_coordinator):
        """Test async_turn_on with preset mode setting."""
        # Arrange
        fan = DysonFan(mock_coordinator)

        # Act
        with (
            patch.object(fan, "async_write_ha_state"),
            patch.object(
                fan, "async_set_preset_mode", new_callable=AsyncMock
            ) as mock_set_preset,
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
        mock_coordinator.device.set_fan_speed.assert_called_once_with(
            6
        )  # 60 -> speed 6

    @pytest.mark.asyncio
    async def test_async_set_percentage_zero(self, mock_coordinator):
        """Test async_set_percentage with zero (turn off)."""
        # Arrange
        fan = DysonFan(mock_coordinator)

        # Act
        with patch.object(
            fan, "async_turn_off", new_callable=AsyncMock
        ) as mock_turn_off:
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
        with (
            patch.object(fan, "async_write_ha_state"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await fan.async_set_direction("forward")

        # Assert
        mock_coordinator.device.set_direction.assert_called_once_with("forward")
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_direction_reverse(self, mock_coordinator):
        """Test async_set_direction with reverse direction."""
        # Arrange
        fan = DysonFan(mock_coordinator)

        # Act
        with (
            patch.object(fan, "async_write_ha_state"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await fan.async_set_direction("reverse")

        # Assert
        mock_coordinator.device.set_direction.assert_called_once_with("reverse")

    @pytest.mark.asyncio
    async def test_async_set_direction_error_handling(self, mock_coordinator):
        """Test async_set_direction error handling."""
        # Arrange
        fan = DysonFan(mock_coordinator)
        mock_coordinator.device.set_direction.side_effect = Exception("Test error")

        # Act - should not raise exception
        await fan.async_set_direction("forward")

        # Assert
        mock_coordinator.device.set_direction.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_direction_forward_no_support(
        self, mock_coordinator_no_direction
    ):
        """Test async_set_direction with forward direction when direction is not supported."""
        # Arrange
        fan = DysonFan(mock_coordinator_no_direction)

        # Act
        with (
            patch.object(fan, "async_write_ha_state"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await fan.async_set_direction("forward")

        # Assert - should not send command when direction not supported
        mock_coordinator_no_direction.device.set_direction.assert_not_called()

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
        """Test that fan entity supports all expected features when direction is supported."""
        # Arrange & Act
        fan = DysonFan(mock_coordinator)

        # Assert - with direction support (fdir key present)
        expected_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.DIRECTION
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        assert fan._attr_supported_features == expected_features

    def test_fan_features_without_direction_support(
        self, mock_coordinator_no_direction
    ):
        """Test that fan entity does not include direction feature when not supported."""
        # Arrange & Act
        fan = DysonFan(mock_coordinator_no_direction)

        # Assert - without direction support (no fdir key)
        expected_features = (
            FanEntityFeature.SET_SPEED
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


class TestFanCoverageEnhancement:
    """Test class to enhance fan coverage to 90%+."""

    def test_handle_coordinator_update_no_device_no_data_preset_mode(
        self, mock_coordinator
    ):
        """Test coordinator update when no device and no data (line 141)."""
        # Arrange - remove device and data
        mock_coordinator.device = None
        mock_coordinator.data = None
        fan = DysonFan(mock_coordinator)

        # Act - this should trigger line 141 (_attr_preset_mode = None)
        with patch.object(fan, "_handle_coordinator_update_safe"):
            fan._handle_coordinator_update()

        # Assert
        assert fan._attr_preset_mode is None

    def test_start_command_pending_debug_logging(self, mock_coordinator):
        """Test _start_command_pending debug logging (lines 177-179)."""
        fan = DysonFan(mock_coordinator)

        with patch("custom_components.hass_dyson.fan._LOGGER") as mock_logger:
            # Act - this should trigger debug logging on lines 177-179
            fan._start_command_pending(5.0)

            # Assert - verify debug logging was called
            mock_logger.debug.assert_called_with(
                "Fan %s started command pending period for %.1f seconds",
                "TEST-SERIAL-123",
                5.0,
            )
            assert fan._command_pending is True

    def test_stop_command_pending_debug_logging(self, mock_coordinator):
        """Test _stop_command_pending debug logging (lines 185-187)."""
        fan = DysonFan(mock_coordinator)

        with patch("custom_components.hass_dyson.fan._LOGGER") as mock_logger:
            # Act - this should trigger debug logging on lines 185-187
            fan._stop_command_pending()

            # Assert - verify debug logging was called
            mock_logger.debug.assert_called_with(
                "Fan %s stopped command pending period", "TEST-SERIAL-123"
            )
            assert fan._command_pending is False
            assert fan._command_end_time is None

    def test_extra_state_attributes_missing_coverage(self, mock_coordinator):
        """Test extra_state_attributes missing coverage paths."""
        fan = DysonFan(mock_coordinator)

        # Test with no device (should return None - line 358)
        mock_coordinator.device = None
        attributes = fan.extra_state_attributes
        assert attributes is None

    def test_command_pending_logic_coverage(self, mock_coordinator):
        """Test command pending logic edge cases - debug logging coverage."""
        fan = DysonFan(mock_coordinator)

        # Initialize command pending attributes by starting a command pending period
        fan._start_command_pending()

        # Test command pending attributes are properly set
        assert fan._command_pending is True
        assert fan._command_end_time is not None

        # Test command pending stop functionality
        fan._stop_command_pending()
        assert fan._command_pending is False
        assert fan._command_end_time is None

    @pytest.mark.asyncio
    async def test_async_set_percentage_command_pending_integration(
        self, mock_coordinator
    ):
        """Test async_set_percentage with percentage conversion (lines 241-246)."""
        fan = DysonFan(mock_coordinator)
        fan.hass = MagicMock()  # Set hass to avoid RuntimeError

        # Act - test percentage conversion and device method call
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_set_percentage(75)

        # Assert - verify device set_fan_speed was called with correct conversion
        mock_coordinator.device.set_fan_speed.assert_called_once_with(
            8
        )  # 75% -> speed 8

    def test_supported_features_property_coverage(self, mock_coordinator):
        """Test supported_features property coverage."""
        fan = DysonFan(mock_coordinator)

        # Test that supported features includes expected features (based on __init__)
        features = fan.supported_features
        expected_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.DIRECTION  # Included because mock has fdir key
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        assert features == expected_features

    @pytest.mark.asyncio
    async def test_async_set_direction_error_handling_coverage(self, mock_coordinator):
        """Test async_set_direction error handling coverage (lines 356-358)."""
        fan = DysonFan(mock_coordinator)
        # Ensure direction is supported
        assert fan._direction_supported

        # Test with device command failure
        mock_coordinator.device.send_command.side_effect = Exception("Command failed")

        with patch("custom_components.hass_dyson.fan._LOGGER") as mock_logger:
            await fan.async_set_direction("forward")

            # Should log error when command fails
            assert mock_logger.error.called

    def test_extra_state_attributes_comprehensive_coverage(self, mock_coordinator):
        """Test extra_state_attributes comprehensive coverage (lines 364-376)."""
        fan = DysonFan(mock_coordinator)

        # Set up coordinator data for comprehensive attribute testing
        mock_coordinator.data = {
            "product-state": {
                "fpwr": "ON",
                "fnst": "FAN",
                "fnsp": "0007",
                "auto": "ON",
            }
        }

        attributes = fan.extra_state_attributes

        # Should include fan state attributes for scene support
        assert attributes is not None
        # Check for actual attributes that exist in the implementation
        expected_keys = [
            "fan_speed",
            "preset_mode",
            "direction",
            "is_on",
            "fan_power",
            "fan_state",
            "fan_speed_setting",
            "auto_mode",
            "night_mode",
            "oscillation_enabled",
            "sleep_timer",
        ]
        for key in expected_keys:
            assert key in attributes

    def test_init_with_oscillation_support(self, mock_coordinator):
        """Test that __init__ adds oscillation support when device reports oson state."""
        # Arrange - Add oson to device state to indicate oscillation support
        mock_coordinator.data = {
            "product-state": {
                "fpwr": "ON",
                "fnst": "FAN",
                "fnsp": "0005",
                "auto": "OFF",
                "fdir": "ON",  # Direction support
                "oson": "OFF",  # Device supports oscillation
            }
        }

        # Act
        fan = DysonFan(mock_coordinator)

        # Assert - Should include OSCILLATE and DIRECTION features
        expected_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.DIRECTION
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.OSCILLATE
        )
        assert fan._attr_supported_features == expected_features

    def test_init_without_oscillation_support(self, mock_coordinator):
        """Test that __init__ does not add oscillation support when device lacks oson state."""
        # Arrange - No oson in device state (no oscillation support)
        mock_coordinator.data = {
            "product-state": {
                "fpwr": "ON",
                "fnst": "FAN",
                "fnsp": "0005",
                "auto": "OFF",
                # No "oson" key = no oscillation support
                # No "fdir" key = no direction support
            }
        }

        # Act
        fan = DysonFan(mock_coordinator)

        # Assert - Should not include OSCILLATE or DIRECTION features
        expected_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        assert fan._attr_supported_features == expected_features
        assert not (fan._attr_supported_features & FanEntityFeature.OSCILLATE)

    def test_handle_coordinator_update_with_oscillation_support(self, mock_coordinator):
        """Test coordinator update with oscillation support updates oscillation state."""
        # Arrange - Device with oscillation support
        mock_coordinator.data = {
            "product-state": {
                "fpwr": "ON",
                "fnst": "FAN",
                "fnsp": "0005",
                "auto": "OFF",
                "oson": "ON",  # Oscillation is ON
            }
        }
        fan = DysonFan(mock_coordinator)

        # Mock device method calls
        def mockget_state_value(state, key, default):
            return state.get(key, default)

        mock_coordinator.device.get_state_value.side_effect = mockget_state_value

        # Act
        with patch.object(fan, "async_write_ha_state"):
            fan._handle_coordinator_update()

        # Assert
        assert fan._attr_oscillating is True

    def test_handle_coordinator_update_breeze_mode_oscillating(self, mock_coordinator):
        """Test that ancp=BRZE reports oscillating=True in the firmware-settled Breeze state.

        The Dyson firmware intentionally settles at ancp=BRZE, oson=OFF,
        oscs=OFF when Breeze is running.  _attr_oscillating must be True.
        """
        mock_coordinator.data = {
            "product-state": {
                "fpwr": "ON",
                "fnst": "FAN",
                "fnsp": "0005",
                "auto": "OFF",
                "oson": "OFF",  # firmware-settled state — Breeze manages its own oscillation
                "ancp": "BRZE",
            }
        }
        fan = DysonFan(mock_coordinator)

        def mockget_state_value(state, key, default):
            return state.get(key, default)

        mock_coordinator.device.get_state_value.side_effect = mockget_state_value

        with patch.object(fan, "async_write_ha_state"):
            fan._handle_coordinator_update()

        assert fan._attr_oscillating is True

    def test_handle_coordinator_update_without_oscillation_support(
        self, mock_coordinator
    ):
        """Test coordinator update without oscillation support sets oscillation to False."""
        # Arrange - Device without oscillation support (no oson in state)
        mock_coordinator.data = {
            "product-state": {
                "fpwr": "ON",
                "fnst": "FAN",
                "fnsp": "0005",
                "auto": "OFF",
                # No "oson" key = no oscillation support
            }
        }
        fan = DysonFan(mock_coordinator)

        # Act
        with patch.object(fan, "async_write_ha_state"):
            fan._handle_coordinator_update()

        # Assert
        assert fan._attr_oscillating is False

    @pytest.mark.asyncio
    async def test_async_oscillate_turn_on_success(self, mock_coordinator):
        """Test successful oscillation turn on via native fan service."""
        # Arrange - Device with oscillation support
        mock_coordinator.data = {
            "product-state": {
                "fpwr": "ON",
                "oson": "OFF",  # Device supports oscillation
            }
        }
        mock_coordinator.device.set_oscillation = AsyncMock()
        fan = DysonFan(mock_coordinator)

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_oscillate(True)

        # Assert
        mock_coordinator.device.set_oscillation.assert_called_once_with(True)
        assert fan._attr_oscillating is True

    @pytest.mark.asyncio
    async def test_async_oscillate_turn_off_success(self, mock_coordinator):
        """Test successful oscillation turn off via native fan service."""
        # Arrange - Device with oscillation support, not in Breeze mode
        mock_coordinator.data = {
            "product-state": {
                "fpwr": "ON",
                "oson": "ON",  # Device supports oscillation
            }
        }
        mock_coordinator.device.set_oscillation = AsyncMock()
        fan = DysonFan(mock_coordinator)

        # Act
        with patch.object(fan, "async_write_ha_state"):
            await fan.async_oscillate(False)

        # Assert
        mock_coordinator.device.set_oscillation.assert_called_once_with(False)
        assert fan._attr_oscillating is False

    @pytest.mark.asyncio
    async def test_async_oscillate_turn_off_from_breeze(self, mock_coordinator):
        """Test that turning off oscillation in Breeze passes osal/osau angles.

        set_oscillation_off_from_breeze() must receive the current osal/osau
        so it can restore the correct ancp preset rather than always using CUST.
        """
        mock_coordinator.data = {
            "product-state": {
                "fpwr": "ON",
                "oson": "OFF",  # Breeze settled state
                "ancp": "BRZE",
                "osal": "0157",
                "osau": "0202",
            }
        }
        mock_coordinator.device.set_oscillation_off_from_breeze = AsyncMock()
        mock_coordinator.device.set_oscillation = AsyncMock()

        def mockget(state, key, default):
            return state.get(key, default)

        mock_coordinator.device.get_state_value.side_effect = mockget
        fan = DysonFan(mock_coordinator)

        with patch.object(fan, "async_write_ha_state"):
            await fan.async_oscillate(False)

        mock_coordinator.device.set_oscillation_off_from_breeze.assert_called_once_with(
            157, 202
        )
        mock_coordinator.device.set_oscillation.assert_not_called()
        assert fan._attr_oscillating is False

    @pytest.mark.asyncio
    async def test_async_oscillate_without_support_logs_warning(self, mock_coordinator):
        """Test oscillation control without support logs warning."""
        # Arrange - Device without oscillation support (no oson in state)
        mock_coordinator.data = {
            "product-state": {
                "fpwr": "ON",
                # No "oson" key = no oscillation support
            }
        }
        fan = DysonFan(mock_coordinator)

        with patch("custom_components.hass_dyson.fan._LOGGER") as mock_logger:
            # Act
            await fan.async_oscillate(True)

            # Assert
            mock_logger.warning.assert_called_once_with(
                "Device %s does not support oscillation control",
                mock_coordinator.serial_number,
            )

    @pytest.mark.asyncio
    async def test_async_oscillate_no_device(self, mock_coordinator):
        """Test oscillation control with no device returns early."""
        # Arrange
        mock_coordinator.device = None
        mock_coordinator.data = {
            "product-state": {
                "oson": "OFF",  # Would support oscillation if device existed
            }
        }
        fan = DysonFan(mock_coordinator)

        # Act & Assert - should not raise exception
        await fan.async_oscillate(True)

    @pytest.mark.asyncio
    async def test_async_oscillate_exception_handling(self, mock_coordinator):
        """Test oscillation control exception handling."""
        # Arrange - Device with oscillation support
        mock_coordinator.data = {
            "product-state": {
                "oson": "OFF",  # Device supports oscillation
            }
        }
        mock_coordinator.device.set_oscillation = AsyncMock(
            side_effect=Exception("Device error")
        )
        fan = DysonFan(mock_coordinator)

        with patch("custom_components.hass_dyson.fan._LOGGER") as mock_logger:
            # Act
            await fan.async_oscillate(True)

            # Assert - Updated to match improved exception handling
            mock_logger.error.assert_called_once_with(
                "Unexpected error setting oscillation to %s for %s: %s",
                True,  # oscillating parameter
                mock_coordinator.serial_number,
                mock_logger.error.call_args[0][3],  # The exception object
            )
