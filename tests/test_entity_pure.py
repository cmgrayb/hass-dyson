"""Test entity module for Dyson integration using pure pytest (Phase 1 Migration).

This consolidates entity base class tests and migrates to pure pytest infrastructure.
"""

from unittest.mock import MagicMock

import pytest
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.hass_dyson.entity import DysonEntity


class TestDysonEntityPurePytest:
    """Test DysonEntity class using pure pytest fixtures."""

    def test_entity_initialization(self, pure_mock_coordinator):
        """Test entity initialization with coordinator."""
        # Act
        entity = DysonEntity(pure_mock_coordinator)

        # Assert
        assert entity.coordinator == pure_mock_coordinator
        assert isinstance(entity, CoordinatorEntity)

    def test_device_info_with_device(self, pure_mock_coordinator):
        """Test device_info property when device is available."""
        # Arrange
        expected_device_info = {
            "identifiers": {("dyson", "TEST-DEVICE-001")},
            "name": "Living Room Fan",
            "manufacturer": "Dyson",
            "model": "DP04",
            "sw_version": "1.0.0",
        }
        pure_mock_coordinator.device.device_info = expected_device_info
        entity = DysonEntity(pure_mock_coordinator)

        # Act
        device_info = entity.device_info

        # Assert
        assert device_info == expected_device_info

    def test_device_info_without_device(self, pure_mock_coordinator):
        """Test device_info property when device is not available."""
        # Arrange
        pure_mock_coordinator.device = None
        entity = DysonEntity(pure_mock_coordinator)

        # Act
        device_info = entity.device_info

        # Assert
        assert device_info is None

    def test_available_when_connected_and_update_success(self, pure_mock_coordinator):
        """Test available property when device is connected and update successful."""
        # Arrange
        pure_mock_coordinator.last_update_success = True
        pure_mock_coordinator.device.is_connected = True
        entity = DysonEntity(pure_mock_coordinator)

        # Act
        available = entity.available

        # Assert
        assert available is True

    def test_available_when_update_failed(self, pure_mock_coordinator):
        """Test available property when update failed."""
        # Arrange
        pure_mock_coordinator.last_update_success = False
        pure_mock_coordinator.device.is_connected = True
        entity = DysonEntity(pure_mock_coordinator)

        # Act
        available = entity.available

        # Assert
        assert available is False

    def test_available_when_device_disconnected(self, pure_mock_coordinator):
        """Test available property when device is disconnected."""
        # Arrange
        pure_mock_coordinator.last_update_success = True
        pure_mock_coordinator.device.is_connected = False
        entity = DysonEntity(pure_mock_coordinator)

        # Act
        available = entity.available

        # Assert
        assert available is False

    def test_available_when_no_device(self, pure_mock_coordinator):
        """Test available property when coordinator has no device."""
        # Arrange
        pure_mock_coordinator.device = None
        entity = DysonEntity(pure_mock_coordinator)

        # Act
        available = entity.available

        # Assert
        assert available is False

    def test_entity_attributes_inherited_from_coordinator_entity(
        self, pure_mock_coordinator
    ):
        """Test that DysonEntity properly inherits CoordinatorEntity attributes."""
        # Act
        entity = DysonEntity(pure_mock_coordinator)

        # Assert - Check that it has expected CoordinatorEntity attributes
        assert hasattr(entity, "coordinator")
        assert hasattr(entity, "available")
        assert hasattr(
            entity, "should_poll"
        )  # Should be False for coordinator entities
        assert entity.should_poll is False

    def test_coordinator_type_consistency(self, pure_mock_coordinator):
        """Test that coordinator reference is consistent."""
        # Act
        entity = DysonEntity(pure_mock_coordinator)

        # Assert
        assert entity.coordinator is pure_mock_coordinator
        assert isinstance(entity, CoordinatorEntity)

    def test_device_info_dynamic_changes(self, pure_mock_coordinator):
        """Test that device_info reflects dynamic changes in coordinator device."""
        # Arrange
        entity = DysonEntity(pure_mock_coordinator)

        # Test with initial device
        initial_device_info = entity.device_info
        assert initial_device_info is not None

        # Change coordinator device to None
        pure_mock_coordinator.device = None
        assert entity.device_info is None

        # Restore device with different info
        new_device = MagicMock()
        new_device.device_info = {"identifiers": {("dyson", "NEW-DEVICE-123")}}
        pure_mock_coordinator.device = new_device

        assert entity.device_info == {"identifiers": {("dyson", "NEW-DEVICE-123")}}

    def test_available_state_combinations(self, pure_mock_coordinator):
        """Test available property with various state combinations."""
        entity = DysonEntity(pure_mock_coordinator)

        # Test all True conditions
        pure_mock_coordinator.last_update_success = True
        pure_mock_coordinator.device.is_connected = True
        assert entity.available is True

        # Test update failed
        pure_mock_coordinator.last_update_success = False
        assert entity.available is False

        # Test device disconnected
        pure_mock_coordinator.last_update_success = True
        pure_mock_coordinator.device.is_connected = False
        assert entity.available is False

        # Test both failed
        pure_mock_coordinator.last_update_success = False
        pure_mock_coordinator.device.is_connected = False
        assert entity.available is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
