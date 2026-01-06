"""Test button platform for Dyson integration using pure pytest (Phase 1 Migration).

This migrates button platform tests to pure pytest infrastructure.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import EntityCategory

from custom_components.hass_dyson.button import DysonReconnectButton, async_setup_entry
from custom_components.hass_dyson.const import DOMAIN


class TestButtonPlatformSetup:
    """Test button platform setup using pure pytest."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_reconnect_button(
        self, pure_mock_hass, pure_mock_config_entry, pure_mock_coordinator
    ):
        """Test that async_setup_entry creates a reconnect button."""
        # Arrange
        pure_mock_hass.data[DOMAIN][pure_mock_config_entry.entry_id] = (
            pure_mock_coordinator
        )
        mock_add_entities = MagicMock()

        # Act
        await async_setup_entry(
            pure_mock_hass, pure_mock_config_entry, mock_add_entities
        )

        # Assert
        mock_add_entities.assert_called_once()
        added_entities = mock_add_entities.call_args[0][0]
        assert len(added_entities) == 1
        assert isinstance(added_entities[0], DysonReconnectButton)
        # Check the second argument is True
        assert mock_add_entities.call_args[0][1] is True

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_missing_coordinator(
        self, pure_mock_hass, pure_mock_config_entry
    ):
        """Test async_setup_entry with missing coordinator raises KeyError."""
        # Arrange
        mock_add_entities = AsyncMock()

        # Act & Assert
        with pytest.raises(KeyError):
            await async_setup_entry(
                pure_mock_hass, pure_mock_config_entry, mock_add_entities
            )


class TestDysonReconnectButton:
    """Test DysonReconnectButton class using pure pytest."""

    def test_init_sets_attributes_correctly(self, pure_mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        button = DysonReconnectButton(pure_mock_coordinator)

        # Assert
        assert button.coordinator == pure_mock_coordinator
        assert (
            button._attr_unique_id == f"{pure_mock_coordinator.serial_number}_reconnect"
        )
        assert button._attr_name == "Reconnect"
        assert button._attr_icon == "mdi:wifi-sync"
        assert button._attr_entity_category == EntityCategory.DIAGNOSTIC

    @pytest.mark.asyncio
    async def test_async_press_successful_reconnect(self, pure_mock_coordinator):
        """Test successful reconnection when button is pressed."""
        # Arrange
        button = DysonReconnectButton(pure_mock_coordinator)
        pure_mock_coordinator.device.force_reconnect = AsyncMock(return_value=True)
        pure_mock_coordinator.async_request_refresh = AsyncMock()

        # Act
        await button.async_press()

        # Assert
        pure_mock_coordinator.device.force_reconnect.assert_called_once()
        pure_mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_press_failed_reconnect(self, pure_mock_coordinator):
        """Test reconnection failure when button is pressed."""
        # Arrange
        button = DysonReconnectButton(pure_mock_coordinator)
        pure_mock_coordinator.device.force_reconnect = AsyncMock(return_value=False)
        pure_mock_coordinator.async_request_refresh = AsyncMock()

        # Act
        await button.async_press()

        # Assert
        pure_mock_coordinator.device.force_reconnect.assert_called_once()
        # When reconnect fails, refresh is NOT called according to implementation
        pure_mock_coordinator.async_request_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_press_exception_handling(self, pure_mock_coordinator):
        """Test exception handling when reconnection raises an exception."""
        # Arrange
        button = DysonReconnectButton(pure_mock_coordinator)
        pure_mock_coordinator.device.force_reconnect = AsyncMock(
            side_effect=Exception("Connection error")
        )
        pure_mock_coordinator.async_request_refresh = AsyncMock()

        # Act & Assert
        # Button should handle exceptions gracefully
        try:
            await button.async_press()
        except Exception:
            pytest.fail("Button should handle exceptions gracefully")

    def test_button_entity_properties(self, pure_mock_coordinator):
        """Test button entity properties are set correctly."""
        # Act
        button = DysonReconnectButton(pure_mock_coordinator)

        # Assert
        assert button.entity_category == EntityCategory.DIAGNOSTIC
        assert button.unique_id == f"{pure_mock_coordinator.serial_number}_reconnect"
        assert button.name == "Reconnect"
        assert button.icon == "mdi:wifi-sync"

    def test_button_inherits_from_coordinator_entity(self, pure_mock_coordinator):
        """Test that button inherits from DysonEntity (CoordinatorEntity)."""
        # Act
        button = DysonReconnectButton(pure_mock_coordinator)

        # Assert
        assert hasattr(button, "coordinator")
        assert hasattr(button, "available")
        assert button.coordinator == pure_mock_coordinator

    @pytest.mark.asyncio
    async def test_button_press_respects_device_availability(
        self, pure_mock_coordinator
    ):
        """Test that button press behavior respects device availability."""
        # Arrange
        button = DysonReconnectButton(pure_mock_coordinator)
        pure_mock_coordinator.device.force_reconnect = AsyncMock(return_value=True)
        pure_mock_coordinator.async_request_refresh = AsyncMock()

        # Test when device is available
        pure_mock_coordinator.last_update_success = True
        pure_mock_coordinator.device.is_connected = True

        # Act
        await button.async_press()

        # Assert
        pure_mock_coordinator.device.force_reconnect.assert_called_once()
        pure_mock_coordinator.async_request_refresh.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
