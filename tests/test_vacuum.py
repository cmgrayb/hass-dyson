"""Test vacuum platform for Dyson integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.vacuum import (
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.exceptions import HomeAssistantError

from custom_components.hass_dyson.const import (
    DEVICE_CATEGORY_ROBOT,
    DOMAIN,
    ROBOT_STATE_FAULT_CRITICAL,
    ROBOT_STATE_FULL_CLEAN_PAUSED,
    ROBOT_STATE_FULL_CLEAN_RUNNING,
    ROBOT_STATE_INACTIVE_CHARGED,
)
from custom_components.hass_dyson.vacuum import DysonVacuumEntity, async_setup_entry


@pytest.fixture
def mock_coordinator_robot():
    """Create a mock coordinator for robot vacuum."""
    coordinator = MagicMock()
    coordinator.serial_number = "ROBOT-TEST-123"
    coordinator.device_name = "Test Robot Vacuum"
    coordinator.device_category = [DEVICE_CATEGORY_ROBOT]
    coordinator.device_capabilities = ["RobotVacuum"]

    coordinator.data = {
        "product-state": {
            "state": "INACTIVE_CHARGED",
            "batteryChargeLevel": 100,
            "globalPosition": [1250, 800],
            "fullCleanType": "",
            "cleanId": "",
        }
    }

    # Mock device with robot vacuum methods
    coordinator.device = MagicMock()
    coordinator.device.robot_state = "INACTIVE_CHARGED"
    coordinator.device.robot_battery_level = 100
    coordinator.device.robot_global_position = [1250, 800]
    coordinator.device.robot_full_clean_type = ""
    coordinator.device.robot_clean_id = ""

    # Mock robot command methods
    coordinator.device.robot_pause = AsyncMock()
    coordinator.device.robot_resume = AsyncMock()
    coordinator.device.robot_abort = AsyncMock()
    coordinator.device.robot_request_state = AsyncMock()

    coordinator.async_request_refresh = AsyncMock()

    return coordinator


@pytest.fixture
def mock_coordinator_non_robot():
    """Create a mock coordinator for non-robot device."""
    coordinator = MagicMock()
    coordinator.serial_number = "FAN-TEST-123"
    coordinator.device_name = "Test Fan"
    coordinator.device_category = ["ec"]  # Environment cleaner, not robot
    coordinator.device_capabilities = ["Fan", "AutoMode"]

    return coordinator


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry_id"
    return config_entry


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": MagicMock()}}
    return hass


class TestVacuumSetup:
    """Test vacuum platform setup."""

    @pytest.mark.asyncio
    async def test_setup_robot_vacuum(
        self, mock_hass, mock_config_entry, mock_coordinator_robot
    ):
        """Test setup of robot vacuum entity."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator_robot
        add_entities = AsyncMock()

        await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        # Should create vacuum entity
        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DysonVacuumEntity)

    @pytest.mark.asyncio
    async def test_setup_non_robot_device(
        self, mock_hass, mock_config_entry, mock_coordinator_non_robot
    ):
        """Test setup skips non-robot devices."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator_non_robot
        add_entities = AsyncMock()

        await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        # Should not create vacuum entity
        add_entities.assert_not_called()


class TestDysonVacuumEntity:
    """Test DysonVacuumEntity functionality."""

    def test_init(self, mock_coordinator_robot):
        """Test vacuum entity initialization."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        assert entity._attr_unique_id == "ROBOT-TEST-123_vacuum"
        assert entity._attr_name is None  # Uses device name
        assert entity._attr_has_entity_name is True

        # Check supported features
        expected_features = (
            VacuumEntityFeature.PAUSE
            | VacuumEntityFeature.STOP
            | VacuumEntityFeature.STATE
            | VacuumEntityFeature.BATTERY
        )
        assert entity._attr_supported_features == expected_features

    def test_state_mapping(self, mock_coordinator_robot):
        """Test robot state to HA state mapping."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Test various robot states
        test_cases = [
            ("FULL_CLEAN_RUNNING", VacuumActivity.CLEANING),
            ("FULL_CLEAN_PAUSED", VacuumActivity.PAUSED),
            ("INACTIVE_CHARGED", VacuumActivity.DOCKED),
            ("MAPPING_RUNNING", VacuumActivity.IDLE),
            ("FAULT_CRITICAL", VacuumActivity.ERROR),
        ]

        for robot_state, expected_ha_state in test_cases:
            mock_coordinator_robot.device.robot_state = robot_state
            assert entity.activity == expected_ha_state

    def test_state_unavailable_device(self, mock_coordinator_robot):
        """Test state when device is unavailable."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Mock missing device
        mock_coordinator_robot.device = None
        assert entity.activity is None

        # Mock device unavailable through coordinator
        mock_coordinator_robot.device = MagicMock()
        mock_coordinator_robot.device.robot_state = "INACTIVE_CHARGED"
        with patch.object(entity.coordinator, "last_update_success", False):
            # Entity inherits available from parent, which checks coordinator
            assert entity.activity is None

    def test_state_unknown_robot_state(self, mock_coordinator_robot):
        """Test state with unknown robot state."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        mock_coordinator_robot.device.robot_state = None
        assert entity.activity is None

    def test_battery_level(self, mock_coordinator_robot):
        """Test battery level reporting."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Test normal battery level
        mock_coordinator_robot.device.robot_battery_level = 75
        assert entity.battery_level == 75

        # Test missing device
        mock_coordinator_robot.device = None
        assert entity.battery_level is None

        # Test None battery level
        mock_coordinator_robot.device = MagicMock()
        mock_coordinator_robot.device.robot_battery_level = None
        assert entity.battery_level is None

        # Test unavailable through coordinator
        mock_coordinator_robot.device.robot_battery_level = 85
        with patch.object(entity.coordinator, "last_update_success", False):
            assert entity.battery_level is None

    def test_extra_state_attributes(self, mock_coordinator_robot):
        """Test additional state attributes."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Setup mock device with all attributes
        mock_coordinator_robot.device.robot_state = "FULL_CLEAN_RUNNING"
        mock_coordinator_robot.device.robot_global_position = [1200, 850]
        mock_coordinator_robot.device.robot_full_clean_type = "immediate"
        mock_coordinator_robot.device.robot_clean_id = "clean_20251217_103245"

        attributes = entity.extra_state_attributes

        expected_attributes = {
            "raw_state": "FULL_CLEAN_RUNNING",
            "global_position": [1200, 850],
            "full_clean_type": "immediate",
            "clean_id": "clean_20251217_103245",
        }
        assert attributes == expected_attributes

    def test_extra_state_attributes_empty(self, mock_coordinator_robot):
        """Test attributes when device data is not available."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Test missing device
        mock_coordinator_robot.device = None
        assert entity.extra_state_attributes == {}

        # Test unavailable device through coordinator
        mock_coordinator_robot.device = MagicMock()
        with patch.object(entity.coordinator, "last_update_success", False):
            assert entity.extra_state_attributes == {}

    def test_extra_state_attributes_partial(self, mock_coordinator_robot):
        """Test attributes with partial data."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Setup device with only some attributes
        mock_coordinator_robot.device.robot_state = "INACTIVE_CHARGED"
        mock_coordinator_robot.device.robot_global_position = None
        mock_coordinator_robot.device.robot_full_clean_type = None
        mock_coordinator_robot.device.robot_clean_id = None

        attributes = entity.extra_state_attributes
        expected_attributes = {"raw_state": "INACTIVE_CHARGED"}
        assert attributes == expected_attributes

    @pytest.mark.asyncio
    async def test_pause(self, mock_coordinator_robot):
        """Test pause command."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        await entity.async_pause()

        mock_coordinator_robot.device.robot_pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_unavailable_device(self, mock_coordinator_robot):
        """Test pause command with unavailable device."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Mock coordinator unavailable
        with patch.object(entity.coordinator, "last_update_success", False):
            with pytest.raises(HomeAssistantError, match="Device not available"):
                await entity.async_pause()

        mock_coordinator_robot.device.robot_pause.assert_not_called()

    @pytest.mark.asyncio
    async def test_pause_missing_device(self, mock_coordinator_robot):
        """Test pause command with missing device."""
        entity = DysonVacuumEntity(mock_coordinator_robot)
        mock_coordinator_robot.device = None

        with pytest.raises(HomeAssistantError, match="Device not available"):
            await entity.async_pause()

    @pytest.mark.asyncio
    async def test_pause_command_failure(self, mock_coordinator_robot):
        """Test pause command failure handling."""
        entity = DysonVacuumEntity(mock_coordinator_robot)
        mock_coordinator_robot.device.robot_pause.side_effect = Exception("MQTT error")

        with pytest.raises(HomeAssistantError, match="Failed to pause vacuum"):
            await entity.async_pause()

    @pytest.mark.asyncio
    async def test_start_resume(self, mock_coordinator_robot):
        """Test start/resume command."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        await entity.async_start()

        mock_coordinator_robot.device.robot_resume.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_unavailable_device(self, mock_coordinator_robot):
        """Test start command with unavailable device."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Mock coordinator unavailable
        with patch.object(entity.coordinator, "last_update_success", False):
            with pytest.raises(HomeAssistantError, match="Device not available"):
                await entity.async_start()

        mock_coordinator_robot.device.robot_resume.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_command_failure(self, mock_coordinator_robot):
        """Test start command failure handling."""
        entity = DysonVacuumEntity(mock_coordinator_robot)
        mock_coordinator_robot.device.robot_resume.side_effect = Exception(
            "Connection lost"
        )

        with pytest.raises(HomeAssistantError, match="Failed to start vacuum"):
            await entity.async_start()

    @pytest.mark.asyncio
    async def test_stop(self, mock_coordinator_robot):
        """Test stop command."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        await entity.async_stop()

        mock_coordinator_robot.device.robot_abort.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_with_kwargs(self, mock_coordinator_robot):
        """Test stop command with additional kwargs."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        await entity.async_stop(some_param="value")

        mock_coordinator_robot.device.robot_abort.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_unavailable_device(self, mock_coordinator_robot):
        """Test stop command with unavailable device."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Mock coordinator unavailable
        with patch.object(entity.coordinator, "last_update_success", False):
            with pytest.raises(HomeAssistantError, match="Device not available"):
                await entity.async_stop()

        mock_coordinator_robot.device.robot_abort.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_command_failure(self, mock_coordinator_robot):
        """Test stop command failure handling."""
        entity = DysonVacuumEntity(mock_coordinator_robot)
        mock_coordinator_robot.device.robot_abort.side_effect = RuntimeError(
            "Device offline"
        )

        with pytest.raises(HomeAssistantError, match="Failed to stop vacuum"):
            await entity.async_stop()

    @pytest.mark.asyncio
    async def test_return_to_base(self, mock_coordinator_robot):
        """Test return to base command."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        await entity.async_return_to_base()

        # Should call robot_abort (same as stop)
        mock_coordinator_robot.device.robot_abort.assert_called_once()

    @pytest.mark.asyncio
    async def test_return_to_base_with_kwargs(self, mock_coordinator_robot):
        """Test return to base command with kwargs."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        await entity.async_return_to_base(param="test")

        mock_coordinator_robot.device.robot_abort.assert_called_once()

    @pytest.mark.asyncio
    async def test_return_to_base_failure(self, mock_coordinator_robot):
        """Test return to base command failure."""
        entity = DysonVacuumEntity(mock_coordinator_robot)
        mock_coordinator_robot.device.robot_abort.side_effect = Exception(
            "Network error"
        )

        with pytest.raises(HomeAssistantError, match="Failed to stop vacuum"):
            await entity.async_return_to_base()


class TestVacuumEntityIntegration:
    """Test vacuum entity integration scenarios."""

    def test_availability_logic(self, mock_coordinator_robot):
        """Test entity availability logic."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Mock the parent availability property
        with patch("custom_components.hass_dyson.vacuum.DysonEntity.available", True):
            # Device present and coordinator available
            assert entity.available is True

        with patch("custom_components.hass_dyson.vacuum.DysonEntity.available", False):
            # Coordinator not available
            assert entity.available is False

    @pytest.mark.asyncio
    async def test_state_updates(self, mock_coordinator_robot):
        """Test entity responds to state updates."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Initial state
        mock_coordinator_robot.device.robot_state = ROBOT_STATE_INACTIVE_CHARGED
        assert entity.activity == VacuumActivity.DOCKED

        # State change to cleaning
        mock_coordinator_robot.device.robot_state = ROBOT_STATE_FULL_CLEAN_RUNNING
        assert entity.activity == VacuumActivity.CLEANING

        # State change to paused
        mock_coordinator_robot.device.robot_state = ROBOT_STATE_FULL_CLEAN_PAUSED
        assert entity.activity == VacuumActivity.PAUSED

        # State change to error
        mock_coordinator_robot.device.robot_state = ROBOT_STATE_FAULT_CRITICAL
        assert entity.activity == VacuumActivity.ERROR

    def test_battery_updates(self, mock_coordinator_robot):
        """Test entity responds to battery level updates."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Test different battery levels
        for level in [100, 75, 50, 25, 10, 0]:
            mock_coordinator_robot.device.robot_battery_level = level
            assert entity.battery_level == level

    def test_position_tracking(self, mock_coordinator_robot):
        """Test position tracking in attributes."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Test position updates
        positions = [
            [1000, 500],
            [1100, 600],
            [1200, 700],
        ]

        for position in positions:
            mock_coordinator_robot.device.robot_global_position = position
            attributes = entity.extra_state_attributes
            assert attributes.get("global_position") == position

    def test_cleaning_session_tracking(self, mock_coordinator_robot):
        """Test cleaning session information tracking."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Test cleaning session updates
        mock_coordinator_robot.device.robot_full_clean_type = "immediate"
        mock_coordinator_robot.device.robot_clean_id = "session_123"

        attributes = entity.extra_state_attributes
        assert attributes.get("full_clean_type") == "immediate"
        assert attributes.get("clean_id") == "session_123"

        # Test session cleared
        mock_coordinator_robot.device.robot_full_clean_type = None
        mock_coordinator_robot.device.robot_clean_id = None

        attributes = entity.extra_state_attributes
        assert "full_clean_type" not in attributes
        assert "clean_id" not in attributes


class TestVacuumEntityErrorHandling:
    """Test vacuum entity error handling scenarios."""

    @pytest.mark.asyncio
    async def test_command_timeout_handling(self, mock_coordinator_robot):
        """Test handling of command timeouts."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        mock_coordinator_robot.device.robot_pause.side_effect = TimeoutError(
            "Command timeout"
        )

        with pytest.raises(HomeAssistantError, match="Failed to pause vacuum"):
            await entity.async_pause()

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, mock_coordinator_robot):
        """Test handling of connection errors."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        mock_coordinator_robot.device.robot_resume.side_effect = ConnectionError(
            "Lost connection"
        )

        with pytest.raises(HomeAssistantError, match="Failed to start vacuum"):
            await entity.async_start()

    def test_invalid_state_handling(self, mock_coordinator_robot):
        """Test handling of invalid robot states."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Test unknown state
        mock_coordinator_robot.device.robot_state = "UNKNOWN_STATE"
        assert entity.activity == VacuumActivity.IDLE  # Default fallback

        # Test empty state
        mock_coordinator_robot.device.robot_state = ""
        assert entity.activity == VacuumActivity.IDLE

    def test_invalid_battery_handling(self, mock_coordinator_robot):
        """Test handling of invalid battery values."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Test negative battery
        mock_coordinator_robot.device.robot_battery_level = -5
        assert (
            entity.battery_level == -5
        )  # Should pass through, let HA handle validation

        # Test over 100 battery
        mock_coordinator_robot.device.robot_battery_level = 120
        assert entity.battery_level == 120  # Should pass through

    def test_device_state_corruption(self, mock_coordinator_robot):
        """Test handling of corrupted device state."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Test when device properties return None
        mock_coordinator_robot.device.robot_state = None

        # Entity should handle gracefully and return None/empty
        assert entity.activity is None

    @pytest.mark.asyncio
    async def test_partial_device_functionality(self, mock_coordinator_robot):
        """Test entity behavior when device has partial functionality."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Remove some methods to simulate partial functionality
        del mock_coordinator_robot.device.robot_pause

        # Entity should still work for other operations
        assert entity.battery_level == 100
        assert entity.activity == VacuumActivity.DOCKED

        # But missing methods should raise HomeAssistantError (wrapped AttributeError)
        with pytest.raises(HomeAssistantError, match="Failed to pause vacuum"):
            await entity.async_pause()
