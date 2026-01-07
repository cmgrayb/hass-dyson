"""Test error handling coverage for DysonEntity base class.

This module provides comprehensive error path testing for the DysonEntity
base class, covering device_info property, availability logic, and thread-safe
coordinator update handling.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
from custom_components.hass_dyson.entity import DysonEntity


class TestDysonEntityDeviceInfo:
    """Test device_info property error handling."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-123"
        coordinator.device_name = "Test Device"
        coordinator.last_update_success = True
        coordinator.device = MagicMock()
        coordinator.device.is_connected = True
        coordinator.device.device_info = {
            "identifiers": {("hass_dyson", "TEST-123")},
            "name": "Test Device",
            "manufacturer": "Dyson",
            "model": "Test Model",
        }
        return coordinator

    def test_device_info_when_device_exists(self, mock_coordinator):
        """Test device_info returns device information when device exists."""
        # Arrange
        entity = DysonEntity(mock_coordinator)

        # Act
        device_info = entity.device_info

        # Assert
        assert device_info is not None
        assert device_info["name"] == "Test Device"
        assert device_info["manufacturer"] == "Dyson"

    def test_device_info_when_device_is_none(self, mock_coordinator):
        """Test device_info returns None when coordinator has no device."""
        # Arrange
        mock_coordinator.device = None
        entity = DysonEntity(mock_coordinator)

        # Act
        device_info = entity.device_info

        # Assert
        assert device_info is None

    def test_device_info_when_device_has_no_device_info(self, mock_coordinator):
        """Test device_info when device object has no device_info attribute."""
        # Arrange
        mock_coordinator.device = MagicMock()
        del mock_coordinator.device.device_info  # Remove attribute
        entity = DysonEntity(mock_coordinator)

        # Act - should raise AttributeError
        with pytest.raises(AttributeError):
            _ = entity.device_info


class TestDysonEntityAvailability:
    """Test available property error handling."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator with default available state."""
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-123"
        coordinator.last_update_success = True
        coordinator.device = MagicMock()
        coordinator.device.is_connected = True
        return coordinator

    def test_available_when_all_conditions_met(self, mock_coordinator):
        """Test entity is available when all conditions are met."""
        # Arrange
        entity = DysonEntity(mock_coordinator)

        # Act
        is_available = entity.available

        # Assert
        assert is_available is True

    def test_unavailable_when_coordinator_update_failed(self, mock_coordinator):
        """Test entity is unavailable when coordinator update failed."""
        # Arrange
        mock_coordinator.last_update_success = False
        entity = DysonEntity(mock_coordinator)

        # Act
        is_available = entity.available

        # Assert
        assert is_available is False

    def test_unavailable_when_device_is_none(self, mock_coordinator):
        """Test entity is unavailable when device is None."""
        # Arrange
        mock_coordinator.device = None
        entity = DysonEntity(mock_coordinator)

        # Act
        is_available = entity.available

        # Assert
        assert is_available is False

    def test_unavailable_when_device_not_connected(self, mock_coordinator):
        """Test entity is unavailable when device is not connected."""
        # Arrange
        mock_coordinator.device.is_connected = False
        entity = DysonEntity(mock_coordinator)

        # Act
        is_available = entity.available

        # Assert
        assert is_available is False

    def test_unavailable_when_coordinator_failed_and_device_none(
        self, mock_coordinator
    ):
        """Test entity is unavailable when both coordinator failed and device is None."""
        # Arrange
        mock_coordinator.last_update_success = False
        mock_coordinator.device = None
        entity = DysonEntity(mock_coordinator)

        # Act
        is_available = entity.available

        # Assert
        assert is_available is False

    def test_unavailable_when_all_conditions_fail(self, mock_coordinator):
        """Test entity is unavailable when all availability conditions fail."""
        # Arrange
        mock_coordinator.last_update_success = False
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.is_connected = False
        entity = DysonEntity(mock_coordinator)

        # Act
        is_available = entity.available

        # Assert
        assert is_available is False

    def test_available_property_called_multiple_times(self, mock_coordinator):
        """Test available property works correctly when called multiple times."""
        # Arrange
        entity = DysonEntity(mock_coordinator)

        # Act & Assert - should be consistent
        assert entity.available is True
        assert entity.available is True
        assert entity.available is True

        # Change state
        mock_coordinator.device.is_connected = False

        # Should now be unavailable
        assert entity.available is False
        assert entity.available is False


class TestDysonEntityCoordinatorUpdateThreadSafety:
    """Test _handle_coordinator_update_safe thread safety."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-123"
        coordinator.last_update_success = True
        coordinator.device = MagicMock()
        coordinator.device.is_connected = True
        return coordinator

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.loop = MagicMock()
        hass.loop.call_soon_threadsafe = MagicMock()
        hass.async_create_task = MagicMock()
        return hass

    def test_handle_coordinator_update_safe_with_hass_and_loop(
        self, mock_coordinator, mock_hass
    ):
        """Test update handling uses call_soon_threadsafe when hass and loop available."""
        # Arrange
        entity = DysonEntity(mock_coordinator)
        entity.hass = mock_hass

        # Act
        entity._handle_coordinator_update_safe()

        # Assert
        mock_hass.loop.call_soon_threadsafe.assert_called_once()

    def test_handle_coordinator_update_safe_without_hass(self, mock_coordinator):
        """Test update handling falls back to super() when hass is not available."""
        # Arrange
        entity = DysonEntity(mock_coordinator)
        entity.hass = None

        # Mock the parent _handle_coordinator_update
        with patch.object(
            DysonEntity.__bases__[0], "_handle_coordinator_update"
        ) as mock_parent:
            # Act
            entity._handle_coordinator_update_safe()

            # Assert
            mock_parent.assert_called_once()

    def test_handle_coordinator_update_safe_without_loop_attribute(
        self, mock_coordinator, mock_hass
    ):
        """Test update handling falls back when hass has no loop attribute."""
        # Arrange
        entity = DysonEntity(mock_coordinator)
        entity.hass = mock_hass
        del mock_hass.loop  # Remove loop attribute

        # Mock the parent _handle_coordinator_update
        with patch.object(
            DysonEntity.__bases__[0], "_handle_coordinator_update"
        ) as mock_parent:
            # Act
            entity._handle_coordinator_update_safe()

            # Assert
            mock_parent.assert_called_once()

    def test_handle_coordinator_update_safe_schedules_async_update(
        self, mock_coordinator, mock_hass
    ):
        """Test that safe update handler schedules the async update task."""
        # Arrange
        entity = DysonEntity(mock_coordinator)
        entity.hass = mock_hass

        # Capture the callback passed to call_soon_threadsafe
        callback_ref = None

        def capture_callback(callback):
            nonlocal callback_ref
            callback_ref = callback

        mock_hass.loop.call_soon_threadsafe.side_effect = capture_callback

        # Act
        entity._handle_coordinator_update_safe()

        # Assert - callback was captured
        assert callback_ref is not None

        # Execute the callback
        callback_ref()

        # Verify async_create_task was called
        mock_hass.async_create_task.assert_called_once()


class TestDysonEntityAsyncHandleCoordinatorUpdate:
    """Test _async_handle_coordinator_update error handling."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-123"
        coordinator.last_update_success = True
        coordinator.device = MagicMock()
        coordinator.device.is_connected = True
        return coordinator

    @pytest.mark.asyncio
    async def test_async_handle_coordinator_update_calls_parent(self, mock_coordinator):
        """Test async update handler calls parent implementation."""
        # Arrange
        entity = DysonEntity(mock_coordinator)

        # Mock the parent _handle_coordinator_update
        with patch.object(
            DysonEntity.__bases__[0], "_handle_coordinator_update"
        ) as mock_parent:
            # Act
            await entity._async_handle_coordinator_update()

            # Assert
            mock_parent.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_handle_coordinator_update_multiple_calls(
        self, mock_coordinator
    ):
        """Test async update handler works correctly with multiple calls."""
        # Arrange
        entity = DysonEntity(mock_coordinator)

        # Mock the parent _handle_coordinator_update
        with patch.object(
            DysonEntity.__bases__[0], "_handle_coordinator_update"
        ) as mock_parent:
            # Act - call multiple times
            await entity._async_handle_coordinator_update()
            await entity._async_handle_coordinator_update()
            await entity._async_handle_coordinator_update()

            # Assert - should be called three times
            assert mock_parent.call_count == 3


class TestDysonEntityInitialization:
    """Test DysonEntity initialization."""

    def test_entity_initialization_sets_attributes(self):
        """Test entity initialization sets required attributes."""
        # Arrange
        mock_coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coordinator.serial_number = "TEST-123"

        # Act
        entity = DysonEntity(mock_coordinator)

        # Assert
        assert entity.coordinator == mock_coordinator
        assert entity._attr_has_entity_name is True

    def test_entity_initialization_with_different_coordinators(self):
        """Test entity can be initialized with different coordinators."""
        # Arrange
        coordinator1 = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator1.serial_number = "DEVICE-001"

        coordinator2 = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator2.serial_number = "DEVICE-002"

        # Act
        entity1 = DysonEntity(coordinator1)
        entity2 = DysonEntity(coordinator2)

        # Assert
        assert entity1.coordinator.serial_number == "DEVICE-001"
        assert entity2.coordinator.serial_number == "DEVICE-002"
        assert entity1.coordinator != entity2.coordinator


class TestDysonEntityEdgeCases:
    """Test edge cases and unusual scenarios."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-123"
        coordinator.last_update_success = True
        coordinator.device = MagicMock()
        coordinator.device.is_connected = True
        return coordinator

    def test_available_when_device_has_no_is_connected_attribute(
        self, mock_coordinator
    ):
        """Test availability check when device has no is_connected attribute."""
        # Arrange
        mock_coordinator.device = MagicMock()
        del mock_coordinator.device.is_connected
        entity = DysonEntity(mock_coordinator)

        # Act & Assert - should raise AttributeError
        with pytest.raises(AttributeError):
            _ = entity.available

    def test_device_info_property_multiple_accesses(self, mock_coordinator):
        """Test device_info property returns consistent results on multiple accesses."""
        # Arrange
        entity = DysonEntity(mock_coordinator)

        # Act
        info1 = entity.device_info
        info2 = entity.device_info
        info3 = entity.device_info

        # Assert - should return same reference
        assert info1 is info2
        assert info2 is info3

    def test_entity_with_coordinator_having_minimal_attributes(self):
        """Test entity works with coordinator having only required attributes."""
        # Arrange - minimal coordinator
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "MIN-TEST"
        coordinator.last_update_success = False
        coordinator.device = None

        # Act
        entity = DysonEntity(coordinator)

        # Assert
        assert entity.available is False
        assert entity.device_info is None

    @pytest.mark.asyncio
    async def test_async_update_handler_exception_propagation(self, mock_coordinator):
        """Test async update handler propagates exceptions from parent."""
        # Arrange
        entity = DysonEntity(mock_coordinator)

        # Mock parent to raise exception
        with patch.object(
            DysonEntity.__bases__[0], "_handle_coordinator_update"
        ) as mock_parent:
            mock_parent.side_effect = RuntimeError("Update failed")

            # Act & Assert - exception should propagate
            with pytest.raises(RuntimeError, match="Update failed"):
                await entity._async_handle_coordinator_update()
