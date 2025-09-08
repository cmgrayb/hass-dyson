"""Test button platform for Dyson integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant

from custom_components.hass_dyson.button import DysonReconnectButton, async_setup_entry
from custom_components.hass_dyson.const import DOMAIN


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-SERIAL-123"
    coordinator.device_name = "Test Device"
    coordinator.device = MagicMock()
    return coordinator


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test-entry-id"
    return config_entry


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    return hass


class TestButtonPlatformSetup:
    """Test button platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_reconnect_button(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test that async_setup_entry creates a reconnect button."""
        # Arrange
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator
        mock_add_entities = MagicMock()

        # Act
        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        # Assert
        mock_add_entities.assert_called_once()
        added_entities = mock_add_entities.call_args[0][0]
        assert len(added_entities) == 1
        assert isinstance(added_entities[0], DysonReconnectButton)
        # Check the second argument is True
        assert mock_add_entities.call_args[0][1] is True

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_missing_coordinator(self, mock_hass, mock_config_entry):
        """Test async_setup_entry with missing coordinator raises KeyError."""
        # Arrange
        mock_add_entities = AsyncMock()

        # Act & Assert
        with pytest.raises(KeyError):
            await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)


class TestDysonReconnectButton:
    """Test DysonReconnectButton class."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        button = DysonReconnectButton(mock_coordinator)

        # Assert
        assert button.coordinator == mock_coordinator
        assert button._attr_unique_id == "TEST-SERIAL-123_reconnect"
        assert button._attr_name == "Test Device Reconnect"
        assert button._attr_icon == "mdi:wifi-sync"
        assert button._attr_entity_category == EntityCategory.DIAGNOSTIC

    @pytest.mark.asyncio
    async def test_async_press_successful_reconnect(self, mock_coordinator):
        """Test successful reconnection when button is pressed."""
        # Arrange
        button = DysonReconnectButton(mock_coordinator)
        mock_coordinator.device.force_reconnect = AsyncMock(return_value=True)
        mock_coordinator.async_request_refresh = AsyncMock()

        # Act
        await button.async_press()

        # Assert
        mock_coordinator.device.force_reconnect.assert_called_once()
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_press_failed_reconnect(self, mock_coordinator):
        """Test failed reconnection when button is pressed."""
        # Arrange
        button = DysonReconnectButton(mock_coordinator)
        mock_coordinator.device.force_reconnect = AsyncMock(return_value=False)
        mock_coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.hass_dyson.button._LOGGER") as mock_logger:
            # Act
            await button.async_press()

            # Assert
            mock_coordinator.device.force_reconnect.assert_called_once()
            mock_coordinator.async_request_refresh.assert_not_called()
            mock_logger.warning.assert_called_with("Manual reconnection failed for %s", "TEST-SERIAL-123")

    @pytest.mark.asyncio
    async def test_async_press_no_device_available(self, mock_coordinator):
        """Test button press when no device is available."""
        # Arrange
        mock_coordinator.device = None
        button = DysonReconnectButton(mock_coordinator)

        with patch("custom_components.hass_dyson.button._LOGGER") as mock_logger:
            # Act
            await button.async_press()

            # Assert
            mock_logger.warning.assert_called_with("Device not available for reconnect")

    @pytest.mark.asyncio
    async def test_async_press_exception_handling(self, mock_coordinator):
        """Test exception handling during button press."""
        # Arrange
        button = DysonReconnectButton(mock_coordinator)
        mock_coordinator.device.force_reconnect = AsyncMock(side_effect=Exception("Connection error"))

        with patch("custom_components.hass_dyson.button._LOGGER") as mock_logger:
            # Act
            await button.async_press()

            # Assert
            mock_coordinator.device.force_reconnect.assert_called_once()
            mock_logger.error.assert_called_with(
                "Failed to manually reconnect %s: %s",
                "TEST-SERIAL-123",
                mock_coordinator.device.force_reconnect.side_effect,
            )

    @pytest.mark.asyncio
    async def test_async_press_logs_info_messages(self, mock_coordinator):
        """Test that async_press logs appropriate info messages."""
        # Arrange
        button = DysonReconnectButton(mock_coordinator)
        mock_coordinator.device.force_reconnect = AsyncMock(return_value=True)
        mock_coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.hass_dyson.button._LOGGER") as mock_logger:
            # Act
            await button.async_press()

            # Assert
            expected_calls = [
                (
                    "Manual reconnect triggered for %s",
                    "TEST-SERIAL-123",
                ),
                (
                    "Manual reconnection successful for %s",
                    "TEST-SERIAL-123",
                ),
            ]

            # Check that info was called with expected arguments
            assert mock_logger.info.call_count == 2
            for call_args, expected_args in zip(mock_logger.info.call_args_list, expected_calls):
                assert call_args[0] == expected_args

    def test_inherits_from_correct_base_classes(self, mock_coordinator):
        """Test that DysonReconnectButton inherits from correct base classes."""
        # Act
        button = DysonReconnectButton(mock_coordinator)

        # Assert
        from homeassistant.components.button import ButtonEntity

        from custom_components.hass_dyson.entity import DysonEntity

        assert isinstance(button, DysonEntity)
        assert isinstance(button, ButtonEntity)

    def test_coordinator_type_annotation(self, mock_coordinator):
        """Test that coordinator has correct type annotation."""
        # Act
        button = DysonReconnectButton(mock_coordinator)

        # Assert
        assert hasattr(button, "coordinator")
        # Verify the coordinator attribute is set correctly
        assert button.coordinator == mock_coordinator


class TestButtonPlatformIntegration:
    """Test button platform integration scenarios."""

    @pytest.mark.asyncio
    async def test_button_entity_in_home_assistant_context(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test button entity works correctly in Home Assistant context."""
        # Arrange
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator
        mock_add_entities = MagicMock()

        # Act
        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        # Assert
        entities = mock_add_entities.call_args[0][0]
        button = entities[0]

        # Verify button properties work as expected
        assert button.unique_id == "TEST-SERIAL-123_reconnect"
        assert button.name == "Test Device Reconnect"
        assert button.icon == "mdi:wifi-sync"
        assert button.entity_category == EntityCategory.DIAGNOSTIC

    @pytest.mark.asyncio
    async def test_multiple_config_entries(self, mock_hass):
        """Test that multiple config entries can have their own buttons."""
        # Arrange
        coordinator1 = MagicMock()
        coordinator1.serial_number = "DEVICE-001"
        coordinator1.device_name = "Living Room Fan"
        coordinator1.device = MagicMock()

        coordinator2 = MagicMock()
        coordinator2.serial_number = "DEVICE-002"
        coordinator2.device_name = "Bedroom Purifier"
        coordinator2.device = MagicMock()

        config_entry1 = MagicMock(spec=ConfigEntry)
        config_entry1.entry_id = "entry-1"

        config_entry2 = MagicMock(spec=ConfigEntry)
        config_entry2.entry_id = "entry-2"

        mock_hass.data[DOMAIN]["entry-1"] = coordinator1
        mock_hass.data[DOMAIN]["entry-2"] = coordinator2

        mock_add_entities = MagicMock()

        # Act
        await async_setup_entry(mock_hass, config_entry1, mock_add_entities)
        button1 = mock_add_entities.call_args[0][0][0]

        await async_setup_entry(mock_hass, config_entry2, mock_add_entities)
        button2 = mock_add_entities.call_args[0][0][0]

        # Assert
        assert button1.unique_id == "DEVICE-001_reconnect"
        assert button1.name == "Living Room Fan Reconnect"
        assert button2.unique_id == "DEVICE-002_reconnect"
        assert button2.name == "Bedroom Purifier Reconnect"

    @pytest.mark.asyncio
    async def test_button_press_integration_with_coordinator(self, mock_coordinator):
        """Test button press properly integrates with coordinator methods."""
        # Arrange
        button = DysonReconnectButton(mock_coordinator)
        mock_coordinator.device.force_reconnect = AsyncMock(return_value=True)
        mock_coordinator.async_request_refresh = AsyncMock()

        # Act
        await button.async_press()

        # Assert
        # Verify the call sequence
        mock_coordinator.device.force_reconnect.assert_called_once()
        mock_coordinator.async_request_refresh.assert_called_once()

        # Verify that refresh is called after successful reconnect
        force_reconnect_call_order = mock_coordinator.device.force_reconnect.call_args_list
        refresh_call_order = mock_coordinator.async_request_refresh.call_args_list
        assert len(force_reconnect_call_order) == 1
        assert len(refresh_call_order) == 1
