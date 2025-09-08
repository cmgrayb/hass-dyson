"""Test entity module for Dyson integration."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
from custom_components.hass_dyson.entity import DysonEntity


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
    coordinator.last_update_success = True
    coordinator.device = MagicMock()
    coordinator.device.is_connected = True
    coordinator.device.device_info = {
        "identifiers": {("dyson", "TEST-SERIAL-123")},
        "name": "Test Device",
        "manufacturer": "Dyson",
        "model": "Test Model",
    }
    return coordinator


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.loop = MagicMock()
    hass.async_create_task = MagicMock()
    return hass


class TestDysonEntity:
    """Test DysonEntity class."""

    def test_init(self, mock_coordinator):
        """Test entity initialization."""
        # Act
        entity = DysonEntity(mock_coordinator)

        # Assert
        assert entity.coordinator == mock_coordinator
        assert isinstance(entity, CoordinatorEntity)

    def test_device_info_with_device(self, mock_coordinator):
        """Test device_info property when device is available."""
        # Arrange
        entity = DysonEntity(mock_coordinator)

        # Act
        device_info = entity.device_info

        # Assert
        assert device_info == {
            "identifiers": {("dyson", "TEST-SERIAL-123")},
            "name": "Test Device",
            "manufacturer": "Dyson",
            "model": "Test Model",
        }

    def test_device_info_without_device(self, mock_coordinator):
        """Test device_info property when device is not available."""
        # Arrange
        mock_coordinator.device = None
        entity = DysonEntity(mock_coordinator)

        # Act
        device_info = entity.device_info

        # Assert
        assert device_info is None

    def test_available_when_connected_and_update_success(self, mock_coordinator):
        """Test available property when device is connected and update successful."""
        # Arrange
        mock_coordinator.last_update_success = True
        mock_coordinator.device.is_connected = True
        entity = DysonEntity(mock_coordinator)

        # Act
        available = entity.available

        # Assert
        assert available is True

    def test_available_when_update_failed(self, mock_coordinator):
        """Test available property when update failed."""
        # Arrange
        mock_coordinator.last_update_success = False
        mock_coordinator.device.is_connected = True
        entity = DysonEntity(mock_coordinator)

        # Act
        available = entity.available

        # Assert
        assert available is False

    def test_available_when_device_disconnected(self, mock_coordinator):
        """Test available property when device is disconnected."""
        # Arrange
        mock_coordinator.last_update_success = True
        mock_coordinator.device.is_connected = False
        entity = DysonEntity(mock_coordinator)

        # Act
        available = entity.available

        # Assert
        assert available is False

    def test_available_when_no_device(self, mock_coordinator):
        """Test available property when no device is available."""
        # Arrange
        mock_coordinator.last_update_success = True
        mock_coordinator.device = None
        entity = DysonEntity(mock_coordinator)

        # Act
        available = entity.available

        # Assert
        assert available is False

    def test_available_complex_false_conditions(self, mock_coordinator):
        """Test available property with multiple false conditions."""
        # Arrange
        mock_coordinator.last_update_success = False
        mock_coordinator.device.is_connected = False
        entity = DysonEntity(mock_coordinator)

        # Act
        available = entity.available

        # Assert
        assert available is False

    def test_handle_coordinator_update_safe_with_hass_loop(self, mock_coordinator, mock_hass):
        """Test _handle_coordinator_update_safe with hass and loop available."""
        # Arrange
        entity = DysonEntity(mock_coordinator)
        entity.hass = mock_hass

        # Act
        entity._handle_coordinator_update_safe()

        # Assert
        mock_hass.loop.call_soon_threadsafe.assert_called_once()

        # Extract the scheduled function and call it to test the inner behavior
        scheduled_func = mock_hass.loop.call_soon_threadsafe.call_args[0][0]
        scheduled_func()
        mock_hass.async_create_task.assert_called_once()

    def test_handle_coordinator_update_safe_without_hass(self, mock_coordinator):
        """Test _handle_coordinator_update_safe without hass."""
        # Arrange
        entity = DysonEntity(mock_coordinator)

        with patch.object(entity, "hass", None):
            with patch.object(CoordinatorEntity, "_handle_coordinator_update") as mock_super_update:
                # Act
                entity._handle_coordinator_update_safe()

                # Assert
                mock_super_update.assert_called_once()

    def test_handle_coordinator_update_safe_without_loop(self, mock_coordinator, mock_hass):
        """Test _handle_coordinator_update_safe with hass but no loop."""
        # Arrange
        entity = DysonEntity(mock_coordinator)
        entity.hass = mock_hass
        delattr(mock_hass, "loop")  # Remove loop attribute

        with patch.object(CoordinatorEntity, "_handle_coordinator_update") as mock_super_update:
            # Act
            entity._handle_coordinator_update_safe()

            # Assert
            mock_super_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_handle_coordinator_update(self, mock_coordinator):
        """Test _async_handle_coordinator_update method."""
        # Arrange
        entity = DysonEntity(mock_coordinator)

        with patch.object(CoordinatorEntity, "_handle_coordinator_update") as mock_super_update:
            # Act
            await entity._async_handle_coordinator_update()

            # Assert
            mock_super_update.assert_called_once()

    def test_coordinator_type_annotation(self, mock_coordinator):
        """Test that coordinator has correct type annotation."""
        # Act
        entity = DysonEntity(mock_coordinator)

        # Assert
        assert hasattr(entity, "coordinator")
        assert entity.coordinator == mock_coordinator

    def test_inherits_from_coordinator_entity(self, mock_coordinator):
        """Test that DysonEntity inherits from CoordinatorEntity."""
        # Act
        entity = DysonEntity(mock_coordinator)

        # Assert
        assert isinstance(entity, CoordinatorEntity)

    def test_device_info_changes_with_coordinator_device(self, mock_coordinator):
        """Test that device_info reflects changes in coordinator.device."""
        # Arrange
        entity = DysonEntity(mock_coordinator)

        # Test initial device info
        initial_device_info = entity.device_info
        assert initial_device_info is not None

        # Change coordinator device
        mock_coordinator.device = None

        # Test device info is now None
        updated_device_info = entity.device_info
        assert updated_device_info is None

        # Set a new device
        new_device = MagicMock()
        new_device.device_info = {"identifiers": {("dyson", "NEW-SERIAL-456")}}
        mock_coordinator.device = new_device

        # Test device info reflects new device
        new_device_info = entity.device_info
        assert new_device_info == {"identifiers": {("dyson", "NEW-SERIAL-456")}}

    def test_available_property_reflects_coordinator_state_changes(self, mock_coordinator):
        """Test that available property reflects coordinator state changes."""
        # Arrange
        entity = DysonEntity(mock_coordinator)

        # Initial state - should be available
        assert entity.available is True

        # Change update success
        mock_coordinator.last_update_success = False
        assert entity.available is False

        # Restore update success but disconnect device
        mock_coordinator.last_update_success = True
        mock_coordinator.device.is_connected = False
        assert entity.available is False

        # Restore connection
        mock_coordinator.device.is_connected = True
        assert entity.available is True

        # Remove device entirely
        mock_coordinator.device = None
        assert entity.available is False


class TestDysonEntityIntegration:
    """Test DysonEntity integration scenarios."""

    def test_entity_with_real_coordinator_behavior(self):
        """Test entity behavior with more realistic coordinator."""
        # Arrange
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.last_update_success = True
        coordinator.device = MagicMock()
        coordinator.device.is_connected = True
        coordinator.device.device_info = {
            "identifiers": {("dyson", "INTEGRATION-TEST")},
            "name": "Integration Test Device",
        }

        entity = DysonEntity(coordinator)

        # Act & Assert
        assert entity.available is True
        device_info = entity.device_info
        assert device_info is not None
        assert device_info["name"] == "Integration Test Device"
        assert entity.coordinator == coordinator

    def test_thread_safety_mechanisms(self, mock_coordinator, mock_hass):
        """Test that thread safety mechanisms work correctly."""
        # Arrange
        entity = DysonEntity(mock_coordinator)
        entity.hass = mock_hass

        # Test that call_soon_threadsafe is used when hass.loop is available
        entity._handle_coordinator_update_safe()

        # Verify thread-safe scheduling
        mock_hass.loop.call_soon_threadsafe.assert_called_once()

        # Verify the scheduled function creates an async task
        scheduled_func = mock_hass.loop.call_soon_threadsafe.call_args[0][0]
        scheduled_func()
        mock_hass.async_create_task.assert_called_once()

    def test_entity_state_consistency(self, mock_coordinator):
        """Test that entity state remains consistent across property calls."""
        # Arrange
        entity = DysonEntity(mock_coordinator)

        # Act - call properties multiple times
        available1 = entity.available
        device_info1 = entity.device_info
        available2 = entity.available
        device_info2 = entity.device_info

        # Assert - results should be consistent
        assert available1 == available2
        assert device_info1 == device_info2
