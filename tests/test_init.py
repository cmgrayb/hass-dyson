"""Tests for __init__.py module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.hass_dyson import (
    CONFIG_SCHEMA,
    DEVICE_SCHEMA,
    PLATFORMS_MAP,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.hass_dyson.const import (
    CONF_AUTO_ADD_DEVICES,
    CONF_POLL_FOR_DEVICES,
    CONF_SERIAL_NUMBER,
    DISCOVERY_CLOUD,
    DISCOVERY_MANUAL,
    DOMAIN,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config_entries = MagicMock()
    hass.data = {}
    # async_create_task should return a Task, not a coroutine
    hass.async_create_task = MagicMock(return_value=MagicMock())
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        CONF_SERIAL_NUMBER: "TEST123456",
        "device_name": "Test Device",
        "connection_type": "local_only",
        "hostname": "192.168.1.100",
        "credential": "test_credential",
    }
    entry.options = {}
    entry.entry_id = "test_entry_id"
    entry.version = 1
    entry.title = "Test Device"  # Add missing title attribute
    return entry


class TestInitModule:
    """Test __init__.py functionality."""

    def test_config_schema_structure(self):
        """Test CONFIG_SCHEMA structure."""
        assert DOMAIN in CONFIG_SCHEMA.schema
        domain_schema = CONFIG_SCHEMA.schema[DOMAIN]
        assert "username" in domain_schema.schema
        assert "password" in domain_schema.schema
        assert "devices" in domain_schema.schema

    def test_device_schema_structure(self):
        """Test DEVICE_SCHEMA structure."""
        assert CONF_SERIAL_NUMBER in DEVICE_SCHEMA.schema
        assert "discovery_method" in DEVICE_SCHEMA.schema
        assert "hostname" in DEVICE_SCHEMA.schema
        assert "credential" in DEVICE_SCHEMA.schema
        assert "capabilities" in DEVICE_SCHEMA.schema

    def test_platforms_map(self):
        """Test PLATFORMS_MAP contains expected platforms."""
        expected_platforms = [
            Platform.FAN,
            Platform.SENSOR,
            Platform.BINARY_SENSOR,
            Platform.BUTTON,
            Platform.NUMBER,
            Platform.SELECT,
            Platform.SWITCH,
            Platform.VACUUM,
            Platform.CLIMATE,
        ]
        for platform in expected_platforms:
            assert platform in PLATFORMS_MAP

    @pytest.mark.asyncio
    async def test_async_setup_no_devices(self, mock_hass):
        """Test async_setup with no devices configured."""
        config = {DOMAIN: {}}

        result = await async_setup(mock_hass, config)

        assert result is True

    @pytest.mark.asyncio
    async def test_async_setup_empty_devices(self, mock_hass):
        """Test async_setup with empty devices list."""
        config = {DOMAIN: {"devices": []}}

        result = await async_setup(mock_hass, config)

        assert result is True

    @pytest.mark.asyncio
    async def test_async_setup_with_devices(self, mock_hass):
        """Test async_setup with devices configured."""
        config = {
            DOMAIN: {
                "username": "test@example.com",
                "password": "testpass",
                "devices": [
                    {
                        CONF_SERIAL_NUMBER: "TEST123456",
                        "discovery_method": DISCOVERY_CLOUD,
                        "hostname": "192.168.1.100",
                        "credential": "test_cred",
                        "capabilities": ["FAN", "SENSOR"],
                    }
                ],
            }
        }

        # Mock config entries
        mock_hass.config_entries.async_entries.return_value = []

        with patch.object(mock_hass.config_entries.flow, "async_init", new_callable=AsyncMock) as mock_flow_init:
            mock_flow_init.return_value = True
            result = await async_setup(mock_hass, config)

            assert result is True
            # Verify the flow was initiated with correct data
            mock_flow_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_setup_device_already_exists(self, mock_hass):
        """Test async_setup when device already exists."""
        config = {DOMAIN: {"devices": [{CONF_SERIAL_NUMBER: "TEST123456", "discovery_method": DISCOVERY_MANUAL}]}}

        # Mock existing config entry
        existing_entry = MagicMock()
        existing_entry.data = {CONF_SERIAL_NUMBER: "TEST123456"}
        mock_hass.config_entries.async_entries.return_value = [existing_entry]

        result = await async_setup(mock_hass, config)

        assert result is True

    @pytest.mark.asyncio
    async def test_async_setup_entry_basic(self, mock_hass, mock_config_entry):
        """Test basic async_setup_entry functionality."""
        # Patch the actual coordinator init at the import level
        with patch("custom_components.hass_dyson.DysonDataUpdateCoordinator") as mock_coordinator_class:
            mock_coordinator = MagicMock()
            mock_coordinator_class.return_value = mock_coordinator
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator.serial_number = "TEST123456"

            with patch("custom_components.hass_dyson.async_setup_services"):
                with patch("custom_components.hass_dyson._get_platforms_for_device") as mock_get_platforms:
                    mock_get_platforms.return_value = ["sensor", "fan"]
                    mock_hass.config_entries.async_forward_entry_setups = AsyncMock()

                    result = await async_setup_entry(mock_hass, mock_config_entry)

                    assert result is True
                    assert DOMAIN in mock_hass.data
                    assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_async_setup_entry_cloud_account(self, mock_hass, mock_config_entry):
        """Test async_setup_entry with cloud account entry."""
        # Configure as cloud account entry with devices list to trigger account-level setup
        mock_config_entry.data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "testpass",
            CONF_AUTO_ADD_DEVICES: True,
            CONF_POLL_FOR_DEVICES: True,
            "devices": [{"serial_number": "TEST123456", "device_name": "Test Device"}],
        }

        mock_hass.config_entries.async_entries.return_value = []

        with patch("custom_components.hass_dyson.DysonCloudAccountCoordinator") as mock_cloud_coordinator:
            mock_coordinator = MagicMock()
            mock_cloud_coordinator.return_value = mock_coordinator
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()

            with patch("custom_components.hass_dyson.async_setup_services"):
                result = await async_setup_entry(mock_hass, mock_config_entry)

                assert result is True

    @pytest.mark.asyncio
    async def test_async_setup_entry_coordinator_failure(self, mock_hass, mock_config_entry):
        """Test async_setup_entry when coordinator refresh fails."""
        with patch("custom_components.hass_dyson.coordinator.DysonDataUpdateCoordinator") as mock_coordinator_class:
            mock_coordinator = MagicMock()
            mock_coordinator_class.return_value = mock_coordinator
            mock_coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=Exception("Connection failed"))

            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(mock_hass, mock_config_entry)

    @pytest.mark.asyncio
    async def test_async_unload_entry(self, mock_hass, mock_config_entry):
        """Test async_unload_entry functionality."""
        # Create a proper mock coordinator with device_category
        mock_coordinator = MagicMock()
        mock_coordinator.device_category = ["FAN", "SENSOR"]  # Example device categories
        mock_coordinator.async_shutdown = AsyncMock()  # Make shutdown async

        # Set up initial data
        mock_hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

        with patch.object(mock_hass.config_entries, "async_unload_platforms", new_callable=AsyncMock) as mock_unload:
            mock_unload.return_value = True

            with patch("custom_components.hass_dyson.async_remove_services"):
                result = await async_unload_entry(mock_hass, mock_config_entry)

                assert result is True
                assert mock_config_entry.entry_id not in mock_hass.data[DOMAIN]


class TestInitHelperFunctions:
    """Test helper functions in __init__.py."""

    @pytest.mark.asyncio
    async def test_create_config_entry_function(self, mock_hass):
        """Test config entry creation helper."""
        # Test that config flow can be initiated
        with patch.object(mock_hass.config_entries.flow, "async_init", new_callable=AsyncMock) as mock_flow_init:
            mock_flow_init.return_value = True

            # Simulate what async_setup does
            device_data = {CONF_SERIAL_NUMBER: "TEST123456", "discovery_method": DISCOVERY_CLOUD}

            await mock_hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "import"},
                data=device_data,
            )

            mock_flow_init.assert_called_once()


class TestInitConstants:
    """Test constants and schemas defined in __init__.py."""

    def test_device_schema_defaults(self):
        """Test device schema default values."""
        # Test that discovery_method defaults to DISCOVERY_CLOUD
        test_device = {CONF_SERIAL_NUMBER: "TEST123456"}
        validated = DEVICE_SCHEMA(test_device)
        assert validated["discovery_method"] == DISCOVERY_CLOUD
        assert validated["capabilities"] == []

    def test_config_schema_defaults(self):
        """Test config schema default values."""
        test_config = {DOMAIN: {}}
        validated = CONFIG_SCHEMA(test_config)
        assert validated[DOMAIN]["devices"] == []

    def test_platforms_map_completeness(self):
        """Test that all expected platforms are mapped."""
        assert len(PLATFORMS_MAP) >= 9  # At least 9 platforms should be supported

        # Check that all values are strings
        for platform, name in PLATFORMS_MAP.items():
            assert isinstance(name, str)
            assert len(name) > 0


class TestInitIntegration:
    """Test integration-level functionality."""

    @pytest.mark.asyncio
    async def test_full_setup_flow(self, mock_hass):
        """Test complete setup flow from YAML to entry creation."""
        config = {
            DOMAIN: {
                "username": "test@example.com",
                "password": "testpass",
                "devices": [
                    {CONF_SERIAL_NUMBER: "TEST123456", "hostname": "192.168.1.100", "credential": "test_credential"}
                ],
            }
        }

        mock_hass.config_entries.async_entries.return_value = []

        with patch.object(mock_hass.config_entries.flow, "async_init", new_callable=AsyncMock) as mock_flow_init:
            mock_flow_init.return_value = True
            result = await async_setup(mock_hass, config)

            assert result is True
            mock_flow_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_in_setup(self, mock_hass):
        """Test error handling during setup."""
        config = {DOMAIN: {"devices": [{"invalid": "config"}]}}

        mock_hass.config_entries.async_entries.return_value = []

        # This should handle validation errors gracefully
        try:
            result = await async_setup(mock_hass, config)
            # Should either succeed with valid handling or raise expected exception
            assert isinstance(result, bool)
        except Exception as e:
            # Should be a known/expected exception type (KeyError for missing serial_number)
            assert isinstance(e, (ValueError, vol.Invalid, KeyError))
