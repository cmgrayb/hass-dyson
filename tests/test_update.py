"""Tests for the Dyson update platform."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components.update import UpdateDeviceClass, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.hass_dyson.const import (
    CONF_DISCOVERY_METHOD,
    DISCOVERY_CLOUD,
    DOMAIN,
)
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
from custom_components.hass_dyson.update import (
    DysonFirmwareUpdateEntity,
    async_setup_entry,
)


class TestUpdatePlatformSetup:
    """Test the update platform setup."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock HomeAssistant instance."""
        hass = Mock(spec=HomeAssistant)
        hass.data = {DOMAIN: {}}
        return hass

    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry."""
        config_entry = Mock(spec=ConfigEntry)
        config_entry.entry_id = "test_entry_id"
        config_entry.data = {
            CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD,
            "serial": "ABC123",
            "device_name": "Test Device",
        }
        return config_entry

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "ABC123"
        coordinator.device_name = "Test Device"
        coordinator.device = Mock()
        coordinator.device.is_connected = True
        coordinator.last_update_success = True
        return coordinator

    @pytest.fixture
    def mock_add_entities(self):
        """Create a mock add_entities function."""
        return Mock(spec=AddEntitiesCallback)

    @pytest.mark.asyncio
    async def test_async_setup_entry_cloud_device(
        self, mock_hass, mock_config_entry, mock_coordinator, mock_add_entities
    ):
        """Test setting up update entity for cloud device."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DysonFirmwareUpdateEntity)

    @pytest.mark.asyncio
    async def test_async_setup_entry_manual_device(
        self, mock_hass, mock_config_entry, mock_coordinator, mock_add_entities
    ):
        """Test setting up update entity for manual device - should not create entity."""
        mock_config_entry.data[CONF_DISCOVERY_METHOD] = "manual"
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        # Manual devices don't get firmware update entities
        mock_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_coordinator(
        self, mock_hass, mock_config_entry, mock_add_entities
    ):
        """Test setup when coordinator is missing."""
        # No coordinator in hass.data - this will cause KeyError

        with pytest.raises(KeyError):
            await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)


class TestDysonFirmwareUpdateEntity:
    """Test the DysonFirmwareUpdateEntity."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "ABC123"
        coordinator.device_name = "Test Device"
        coordinator.device = Mock()
        coordinator.device.is_connected = True
        coordinator.last_update_success = True
        # Add firmware properties
        coordinator.firmware_version = "21.08.01"
        coordinator.firmware_latest_version = "21.09.01"
        coordinator.firmware_update_in_progress = False
        coordinator.firmware_auto_update_enabled = False
        # Add firmware update methods
        coordinator.async_install_firmware_update = AsyncMock()
        return coordinator

    @pytest.fixture
    def update_entity(self, mock_coordinator):
        """Create a DysonFirmwareUpdateEntity."""
        return DysonFirmwareUpdateEntity(mock_coordinator)

    def test_entity_properties(self, update_entity, mock_coordinator):
        """Test basic entity properties."""
        assert (
            update_entity.unique_id
            == f"{mock_coordinator.serial_number}_firmware_update"
        )
        assert update_entity._attr_translation_key == "firmware_update"
        assert update_entity.device_class == UpdateDeviceClass.FIRMWARE
        assert update_entity.supported_features == UpdateEntityFeature.INSTALL

    def test_entity_properties_with_update_available(
        self, update_entity, mock_coordinator
    ):
        """Test entity properties when update is available."""
        assert update_entity.installed_version == "21.08.01"
        assert update_entity.latest_version == "21.09.01"
        assert (
            update_entity.release_summary == "Firmware update from 21.08.01 to 21.09.01"
        )
        assert update_entity.in_progress is False
        assert update_entity.auto_update is False
        assert update_entity.title == "Dyson Device Firmware"

    def test_entity_properties_no_update_available(
        self, update_entity, mock_coordinator
    ):
        """Test entity properties when no update is available."""
        mock_coordinator.firmware_version = "21.09.01"
        mock_coordinator.firmware_latest_version = "21.09.01"

        assert update_entity.installed_version == "21.09.01"
        assert update_entity.latest_version == "21.09.01"
        assert update_entity.release_summary is None

    def test_entity_properties_unknown_version(self, update_entity, mock_coordinator):
        """Test entity properties when version is unknown."""
        mock_coordinator.firmware_version = "Unknown"

        assert update_entity.installed_version is None

    @pytest.mark.asyncio
    async def test_async_install_success(self, update_entity, mock_coordinator):
        """Test successful firmware installation."""
        mock_coordinator.async_install_firmware_update.return_value = True

        await update_entity.async_install(version=None, backup=False)

        mock_coordinator.async_install_firmware_update.assert_called_once_with(
            "21.09.01"
        )

    @pytest.mark.asyncio
    async def test_async_install_no_device(self, update_entity, mock_coordinator):
        """Test firmware installation when no device available."""
        mock_coordinator.device = None

        # Should return without error when no device
        await update_entity.async_install(version=None, backup=False)

        mock_coordinator.async_install_firmware_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_install_no_version(self, update_entity, mock_coordinator):
        """Test firmware installation when no version available."""
        mock_coordinator.firmware_latest_version = None

        # Should return without error when no version
        await update_entity.async_install(version=None, backup=False)

        mock_coordinator.async_install_firmware_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_install_specific_version(
        self, update_entity, mock_coordinator
    ):
        """Test firmware installation with specific version."""
        mock_coordinator.async_install_firmware_update.return_value = True

        await update_entity.async_install(version="21.10.01", backup=False)

        mock_coordinator.async_install_firmware_update.assert_called_once_with(
            "21.10.01"
        )

    @pytest.mark.asyncio
    async def test_async_install_failure(self, update_entity, mock_coordinator):
        """Test firmware installation failure."""
        mock_coordinator.async_install_firmware_update.return_value = False

        # The entity doesn't raise exceptions, just logs errors
        await update_entity.async_install(version=None, backup=False)

        mock_coordinator.async_install_firmware_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_install_exception(self, update_entity, mock_coordinator):
        """Test firmware installation with exception."""
        mock_coordinator.async_install_firmware_update.side_effect = Exception(
            "Test error"
        )

        # The entity catches exceptions and logs them
        await update_entity.async_install(version=None, backup=False)

        mock_coordinator.async_install_firmware_update.assert_called_once()

    def test_icon_property(self, update_entity):
        """Test icon property."""
        # The icon is set in __init__
        assert update_entity.icon == "mdi:cellphone-arrow-down"


class TestUpdateEntityIntegration:
    """Integration tests for the update entity."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator with realistic data."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "ABC123"
        coordinator.device_name = "Test Device"
        coordinator.device = Mock()
        coordinator.device.is_connected = True
        coordinator.last_update_success = True
        coordinator.async_install_firmware_update = AsyncMock()

        # Firmware properties
        coordinator.firmware_version = "21.08.01"
        coordinator.firmware_latest_version = "21.09.01"
        coordinator.firmware_update_in_progress = False
        coordinator.firmware_auto_update_enabled = False

        return coordinator

    def test_firmware_update_entity_full_integration(self, mock_coordinator):
        """Test firmware update entity with full coordinator integration."""
        entity = DysonFirmwareUpdateEntity(mock_coordinator)

        # Test all properties
        assert entity.unique_id == "ABC123_firmware_update"
        assert entity._attr_translation_key == "firmware_update"
        assert entity.device_class == UpdateDeviceClass.FIRMWARE
        assert entity.supported_features == UpdateEntityFeature.INSTALL
        assert entity.installed_version == "21.08.01"
        assert entity.latest_version == "21.09.01"
        assert entity.release_summary == "Firmware update from 21.08.01 to 21.09.01"

    @pytest.mark.asyncio
    async def test_firmware_installation_workflow(self, mock_coordinator):
        """Test complete firmware installation workflow."""
        entity = DysonFirmwareUpdateEntity(mock_coordinator)

        # Simulate successful installation
        mock_coordinator.async_install_firmware_update.return_value = True

        # Should not raise exception
        await entity.async_install(version=None, backup=False)

        mock_coordinator.async_install_firmware_update.assert_called_once()

    def test_entity_state_changes_with_coordinator_updates(self, mock_coordinator):
        """Test that entity state changes when coordinator updates."""
        entity = DysonFirmwareUpdateEntity(mock_coordinator)

        # Initially has update available
        assert entity.latest_version == "21.09.01"
        assert entity.installed_version == "21.08.01"

        # Simulate firmware update completion
        mock_coordinator.firmware_version = "21.09.01"
        mock_coordinator.firmware_latest_version = "21.09.01"

        # Now should show no update available
        assert entity.latest_version == "21.09.01"
        assert entity.installed_version == "21.09.01"
        assert entity.release_summary is None


class TestUpdateEntityCoverageEnhancement:
    """Additional tests to improve coverage of missed lines."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "ABC123"
        coordinator.device_name = "Test Device"
        coordinator.device = Mock()
        coordinator.device.is_connected = True
        coordinator.last_update_success = True
        coordinator.firmware_version = "21.08.01"
        coordinator.firmware_latest_version = "21.09.01"
        coordinator.firmware_update_in_progress = False
        coordinator.firmware_auto_update_enabled = True
        coordinator.async_install_firmware_update = AsyncMock()
        return coordinator

    @pytest.fixture
    def update_entity(self, mock_coordinator):
        """Create a DysonFirmwareUpdateEntity."""
        return DysonFirmwareUpdateEntity(mock_coordinator)

    def test_auto_update_property(self, update_entity, mock_coordinator):
        """Test auto_update property."""
        assert update_entity.auto_update is True

    def test_in_progress_property(self, update_entity, mock_coordinator):
        """Test in_progress property."""
        mock_coordinator.firmware_update_in_progress = True
        assert update_entity.in_progress is True

    def test_title_property(self, update_entity):
        """Test title property."""
        assert update_entity.title == "Dyson Device Firmware"

    def test_release_summary_no_difference(self, update_entity, mock_coordinator):
        """Test release_summary when versions are the same."""
        mock_coordinator.firmware_version = "21.09.01"
        mock_coordinator.firmware_latest_version = "21.09.01"

        assert update_entity.release_summary is None

    def test_release_summary_with_none_versions(self, update_entity, mock_coordinator):
        """Test release_summary when versions are None."""
        mock_coordinator.firmware_version = None
        mock_coordinator.firmware_latest_version = None

        assert update_entity.release_summary is None

    @pytest.mark.asyncio
    async def test_install_logs_info_messages(self, update_entity, mock_coordinator):
        """Test that install method logs appropriate messages."""
        mock_coordinator.async_install_firmware_update.return_value = True

        with patch("custom_components.hass_dyson.update._LOGGER") as mock_logger:
            await update_entity.async_install(version="21.10.01", backup=False)

            # Should log info about starting and success
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_install_logs_error_on_failure(self, update_entity, mock_coordinator):
        """Test that install method logs errors on failure."""
        mock_coordinator.async_install_firmware_update.return_value = False

        with patch("custom_components.hass_dyson.update._LOGGER") as mock_logger:
            await update_entity.async_install(version="21.10.01", backup=False)

            # Should log error about failure
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_install_logs_error_on_exception(
        self, update_entity, mock_coordinator
    ):
        """Test that install method logs errors on exception."""
        mock_coordinator.async_install_firmware_update.side_effect = Exception(
            "Test error"
        )

        with patch("custom_components.hass_dyson.update._LOGGER") as mock_logger:
            await update_entity.async_install(version="21.10.01", backup=False)

            # Should log error about exception
            mock_logger.error.assert_called()

    def test_handle_coordinator_update_logs_debug(self, update_entity):
        """Test that coordinator update handler logs debug information."""
        with patch("custom_components.hass_dyson.update._LOGGER") as mock_logger:
            with patch.object(
                type(update_entity).__bases__[0], "_handle_coordinator_update"
            ):
                update_entity._handle_coordinator_update()

                # Should log debug information
                mock_logger.debug.assert_called()
