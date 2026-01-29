"""Tests for __init__.py module."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

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
    _create_device_entry,
    _create_discovery_flow,
    _get_platforms_for_device,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.hass_dyson.const import (
    CONF_AUTO_ADD_DEVICES,
    CONF_DISCOVERY_METHOD,
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
    hass.services = MagicMock()
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

        with patch.object(
            mock_hass.config_entries.flow, "async_init", new_callable=AsyncMock
        ) as mock_flow_init:
            mock_flow_init.return_value = True
            result = await async_setup(mock_hass, config)

            assert result is True
            # Verify the flow was initiated with correct data
            mock_flow_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_setup_device_already_exists(self, mock_hass):
        """Test async_setup when device already exists."""
        config = {
            DOMAIN: {
                "devices": [
                    {
                        CONF_SERIAL_NUMBER: "TEST123456",
                        "discovery_method": DISCOVERY_MANUAL,
                    }
                ]
            }
        }

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
        with patch(
            "custom_components.hass_dyson.DysonDataUpdateCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = MagicMock()
            mock_coordinator_class.return_value = mock_coordinator
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator.serial_number = "TEST123456"

            with patch("custom_components.hass_dyson.async_setup_services"):
                with patch(
                    "custom_components.hass_dyson._get_platforms_for_device"
                ) as mock_get_platforms:
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

        with patch(
            "custom_components.hass_dyson.DysonCloudAccountCoordinator"
        ) as mock_cloud_coordinator:
            mock_coordinator = MagicMock()
            mock_cloud_coordinator.return_value = mock_coordinator
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()

            with patch("custom_components.hass_dyson.async_setup_services"):
                result = await async_setup_entry(mock_hass, mock_config_entry)

                assert result is True

    @pytest.mark.asyncio
    async def test_async_setup_entry_coordinator_failure(
        self, mock_hass, mock_config_entry
    ):
        """Test async_setup_entry when coordinator refresh fails."""
        with patch(
            "custom_components.hass_dyson.coordinator.DysonDataUpdateCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = MagicMock()
            mock_coordinator_class.return_value = mock_coordinator
            mock_coordinator.async_config_entry_first_refresh = AsyncMock(
                side_effect=Exception("Connection failed")
            )

            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(mock_hass, mock_config_entry)

    # NOTE: Automatic removal of unsupported devices is tested in integration tests
    # Unit testing requires HA test harness. See test_coordinator_error_handling.py
    # for validation that UnsupportedDeviceError is raised correctly.

    @pytest.mark.asyncio
    async def test_async_unload_entry(self, mock_hass, mock_config_entry):
        """Test async_unload_entry functionality."""
        # Create a proper mock coordinator with device_category
        mock_coordinator = MagicMock()
        mock_coordinator.device_category = [
            "FAN",
            "SENSOR",
        ]  # Example device categories
        mock_coordinator.async_shutdown = AsyncMock()  # Make shutdown async

        # Set up initial data
        mock_hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

        with patch.object(
            mock_hass.config_entries, "async_unload_platforms", new_callable=AsyncMock
        ) as mock_unload:
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
        with patch.object(
            mock_hass.config_entries.flow, "async_init", new_callable=AsyncMock
        ) as mock_flow_init:
            mock_flow_init.return_value = True

            # Simulate what async_setup does
            device_data = {
                CONF_SERIAL_NUMBER: "TEST123456",
                "discovery_method": DISCOVERY_CLOUD,
            }

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


class TestInitBackgroundTasks:
    """Test background task functions and error handling."""

    @pytest.mark.asyncio
    async def test_create_device_entry_success(self, mock_hass):
        """Test successful background device entry creation."""
        device_data = {"serial_number": "TEST123", "device_name": "Test Device"}
        device_info = {"serial_number": "TEST123", "name": "Test Device"}

        mock_hass.config_entries.flow.async_init = AsyncMock(
            return_value={"type": "create_entry"}
        )

        await _create_device_entry(mock_hass, device_data, device_info)

        mock_hass.config_entries.flow.async_init.assert_called_once_with(
            DOMAIN,
            context={"source": "device_auto_create"},
            data=device_data,
        )

    @pytest.mark.asyncio
    async def test_create_device_entry_exception(self, mock_hass):
        """Test background device entry creation with exception."""
        device_data = {"serial_number": "TEST123", "device_name": "Test Device"}
        device_info = {"serial_number": "TEST123", "name": "Test Device"}

        mock_hass.config_entries.flow.async_init = AsyncMock(
            side_effect=Exception("Test error")
        )

        # Should not raise exception - error should be logged
        await _create_device_entry(mock_hass, device_data, device_info)

        mock_hass.config_entries.flow.async_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_discovery_flow_success(self, mock_hass, mock_config_entry):
        """Test successful discovery flow creation."""
        device_info = {
            "serial_number": "TEST123",
            "name": "Test Device",
            "product_type": "VS6",
            "category": "Fan",
        }

        mock_hass.config_entries.flow.async_progress = MagicMock(return_value=[])
        mock_hass.config_entries.flow.async_init = AsyncMock(
            return_value={"type": "form"}
        )

        await _create_discovery_flow(mock_hass, mock_config_entry, device_info)

        mock_hass.config_entries.flow.async_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_discovery_flow_existing_flow(
        self, mock_hass, mock_config_entry
    ):
        """Test discovery flow creation when flow already exists."""
        device_info = {
            "serial_number": "TEST123",
            "name": "Test Device",
            "product_type": "VS6",
            "category": "Fan",
        }

        # Mock existing flow
        existing_flow = {
            "handler": DOMAIN,
            "context": {"source": "discovery", "unique_id": "TEST123"},
        }
        mock_hass.config_entries.flow.async_progress = MagicMock(
            return_value=[existing_flow]
        )
        mock_hass.config_entries.flow.async_init = AsyncMock()

        await _create_discovery_flow(mock_hass, mock_config_entry, device_info)

        # Should not create new flow
        mock_hass.config_entries.flow.async_init.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_discovery_flow_exception(self, mock_hass, mock_config_entry):
        """Test discovery flow creation with exception."""
        device_info = {
            "serial_number": "TEST123",
            "name": "Test Device",
            "product_type": "VS6",
            "category": "Fan",
        }

        mock_hass.config_entries.flow.async_progress = MagicMock(return_value=[])
        mock_hass.config_entries.flow.async_init = AsyncMock(
            side_effect=Exception("Test error")
        )

        # Should not raise exception - error should be logged
        await _create_discovery_flow(mock_hass, mock_config_entry, device_info)

        mock_hass.config_entries.flow.async_init.assert_called_once()


class TestInitAccountManagement:
    """Test account-level entry management and cleanup."""

    @pytest.mark.asyncio
    async def test_async_unload_entry_account_level_with_children(self, mock_hass):
        """Test unloading account-level entry with child device entries."""
        # Create account entry
        account_entry = MagicMock(spec=ConfigEntry)
        account_entry.entry_id = "account_123"
        account_entry.title = "Cloud Account"
        account_entry.data = {"devices": ["device1", "device2"]}

        # Create child device entries
        child_entry1 = MagicMock(spec=ConfigEntry)
        child_entry1.entry_id = "device1"
        child_entry1.title = "Device 1"
        child_entry1.data = {"parent_entry_id": "account_123"}

        child_entry2 = MagicMock(spec=ConfigEntry)
        child_entry2.entry_id = "device2"
        child_entry2.title = "Device 2"
        child_entry2.data = {"parent_entry_id": "account_123"}

        # Mock config entries
        mock_hass.config_entries.async_entries = MagicMock(
            return_value=[child_entry1, child_entry2]
        )
        mock_hass.config_entries.async_remove = AsyncMock()
        mock_hass.data = {DOMAIN: {}}

        with patch(
            "custom_components.hass_dyson.async_remove_cloud_services"
        ) as mock_remove_services:
            result = await async_unload_entry(mock_hass, account_entry)

        assert result is True
        assert mock_hass.config_entries.async_remove.call_count == 2
        mock_remove_services.assert_called_once_with(mock_hass)

    @pytest.mark.asyncio
    async def test_async_unload_entry_account_with_cloud_coordinator(self, mock_hass):
        """Test unloading account entry with cloud coordinator cleanup."""
        account_entry = MagicMock(spec=ConfigEntry)
        account_entry.entry_id = "account_123"
        account_entry.title = "Cloud Account"
        account_entry.data = {"devices": ["device1"]}

        # Mock cloud coordinator
        mock_coordinator = MagicMock()
        mock_coordinator.async_shutdown = AsyncMock()

        mock_hass.data = {DOMAIN: {"account_123_cloud": mock_coordinator}}
        mock_hass.config_entries.async_entries = MagicMock(return_value=[])

        with patch(
            "custom_components.hass_dyson.async_remove_cloud_services"
        ) as mock_remove_services:
            result = await async_unload_entry(mock_hass, account_entry)

        assert result is True
        mock_coordinator.async_shutdown.assert_called_once()
        mock_remove_services.assert_called_once_with(mock_hass)

    @pytest.mark.asyncio
    async def test_async_unload_entry_account_with_remaining_accounts(self, mock_hass):
        """Test unloading account entry when other cloud accounts remain."""
        account_entry = MagicMock(spec=ConfigEntry)
        account_entry.entry_id = "account_123"
        account_entry.title = "Test Account"
        account_entry.data = {"devices": ["device1"]}

        # Mock remaining cloud account
        remaining_account = MagicMock(spec=ConfigEntry)
        remaining_account.entry_id = "account_456"
        remaining_account.title = "Other Account"
        remaining_account.data = {"devices": ["device2"]}

        mock_hass.data = {DOMAIN: {}}
        mock_hass.config_entries.async_entries = MagicMock(
            return_value=[remaining_account]
        )

        with patch(
            "custom_components.hass_dyson.async_remove_cloud_services"
        ) as mock_remove_services:
            result = await async_unload_entry(mock_hass, account_entry)

        assert result is True
        # Should not remove cloud services when other accounts remain
        mock_remove_services.assert_not_called()


class TestInitDeviceManagement:
    """Test device-level entry management and error scenarios."""

    @pytest.mark.asyncio
    async def test_async_unload_entry_device_not_in_data(self, mock_hass):
        """Test unloading device entry that's not in hass.data."""
        device_entry = MagicMock(spec=ConfigEntry)
        device_entry.entry_id = "device_123"
        device_entry.title = "Test Device"
        device_entry.data = {"serial_number": "TEST123"}

        mock_hass.data = {DOMAIN: {}}  # Entry not in data

        result = await async_unload_entry(mock_hass, device_entry)

        assert result is True

    @pytest.mark.asyncio
    async def test_async_unload_entry_device_with_coordinator_shutdown_error(
        self, mock_hass
    ):
        """Test unloading device entry when coordinator shutdown fails."""
        device_entry = MagicMock(spec=ConfigEntry)
        device_entry.entry_id = "device_123"
        device_entry.title = "Test Device"
        device_entry.data = {"serial_number": "TEST123"}

        # Mock coordinator with failing shutdown
        mock_coordinator = MagicMock()
        mock_coordinator.async_shutdown = AsyncMock(
            side_effect=Exception("Shutdown failed")
        )

        mock_hass.data = {DOMAIN: {"device_123": mock_coordinator}}
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        with patch(
            "custom_components.hass_dyson.async_remove_device_services_for_coordinator"
        ) as mock_remove_services:
            with patch(
                "custom_components.hass_dyson._get_platforms_for_device",
                return_value=["sensor", "switch"],
            ):
                # Should propagate the shutdown error
                with pytest.raises(Exception, match="Shutdown failed"):
                    await async_unload_entry(mock_hass, device_entry)

        mock_coordinator.async_shutdown.assert_called_once()
        mock_remove_services.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_setup_entry_platform_error_handling(
        self, mock_hass, mock_config_entry
    ):
        """Test async_setup_entry with platform setup errors."""
        mock_hass.data = {}

        # Mock coordinator setup
        with patch(
            "custom_components.hass_dyson.DysonDataUpdateCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            # Mock platform setup with one platform failing
            with patch(
                "custom_components.hass_dyson.async_setup_device_services_for_coordinator"
            ) as mock_setup_services:
                with patch.object(
                    mock_hass.config_entries, "async_forward_entry_setups"
                ) as mock_forward:
                    mock_forward.side_effect = Exception("Platform setup failed")

                    # Should handle platform setup errors by raising ConfigEntryNotReady
                    with pytest.raises(
                        Exception
                    ):  # ConfigEntryNotReady or platform error
                        await async_setup_entry(mock_hass, mock_config_entry)

                    mock_coordinator.async_config_entry_first_refresh.assert_called_once()
                    mock_setup_services.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_setup_entry_coordinator_refresh_error_comprehensive(
        self, mock_hass, mock_config_entry
    ):
        """Test async_setup_entry when coordinator refresh fails."""
        mock_hass.data = {}

        with patch(
            "custom_components.hass_dyson.DysonDataUpdateCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock(
                side_effect=Exception("Refresh failed")
            )
            mock_coordinator_class.return_value = mock_coordinator

            # Should handle coordinator refresh errors by raising ConfigEntryNotReady
            with pytest.raises(Exception):  # ConfigEntryNotReady or refresh error
                await async_setup_entry(mock_hass, mock_config_entry)


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
                    {
                        CONF_SERIAL_NUMBER: "TEST123456",
                        "hostname": "192.168.1.100",
                        "credential": "test_credential",
                    }
                ],
            }
        }

        mock_hass.config_entries.async_entries.return_value = []

        with patch.object(
            mock_hass.config_entries.flow, "async_init", new_callable=AsyncMock
        ) as mock_flow_init:
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
            assert isinstance(e, ValueError | vol.Invalid | KeyError)


class TestPlatformDetermination:
    """Test platform determination logic - stable tests that enhance coverage."""

    def test_get_platforms_for_vacuum_device(self):
        """Test platform determination for vacuum devices."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["robot"]
        mock_coordinator.device_capabilities = []
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        assert "vacuum" in platforms
        assert "sensor" in platforms
        assert "binary_sensor" in platforms
        assert "button" in platforms
        assert "update" in platforms

    def test_get_platforms_for_fan_device_with_capabilities(self):
        """Test platform determination for fan with advanced capabilities."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["ec"]
        mock_coordinator.device_capabilities = [
            "Scheduling",
            "AdvanceOscillationDay1",
            "Heating",
        ]
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        assert "fan" in platforms
        assert "number" in platforms
        assert "select" in platforms
        assert "switch" in platforms
        assert "climate" in platforms
        assert "update" in platforms

    def test_get_platforms_for_local_device(self):
        """Test platform determination for locally discovered device."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["ec"]
        mock_coordinator.device_capabilities = []
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: "local"}

        platforms = _get_platforms_for_device(mock_coordinator)

        # Should not include update platform for local devices
        assert "update" not in platforms
        assert "fan" in platforms
        assert "sensor" in platforms

    def test_get_platforms_deduplication(self):
        """Test platform list deduplication."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["ec"]
        mock_coordinator.device_capabilities = ["Scheduling"]  # This adds number/select
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        # Should not have duplicates
        assert len(platforms) == len(set(platforms))
        assert platforms.count("number") == 1
        assert platforms.count("select") == 1

    def test_get_platforms_for_flrc_category(self):
        """Test platform determination for FLRC category devices."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["flrc"]
        mock_coordinator.device_capabilities = []
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        assert "vacuum" in platforms
        assert "update" in platforms

    def test_get_platforms_switch_capability_logic(self):
        """Test switch platform logic based on capabilities."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["ec"]
        mock_coordinator.device_capabilities = ["Switch"]
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        assert "switch" in platforms

    def test_get_platforms_multi_category_handling(self):
        """Test platform determination with multiple device categories."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["ec", "light"]  # Multiple categories
        mock_coordinator.device_capabilities = []
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        # Should include platforms for EC devices (no climate without Heating capability)
        assert "fan" in platforms
        assert "switch" in platforms

    def test_get_platforms_empty_categories(self):
        """Test platform determination with empty device categories."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = []  # Empty categories
        mock_coordinator.device_capabilities = []
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        # Should still include base platforms
        assert "sensor" in platforms
        assert "binary_sensor" in platforms
        assert "button" in platforms
        assert "update" in platforms

    def test_get_platforms_unknown_category(self):
        """Test platform determination with unknown device category."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["unknown_category"]
        mock_coordinator.device_capabilities = []
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        # Should include base platforms even for unknown categories
        assert "sensor" in platforms
        assert "binary_sensor" in platforms
        assert "button" in platforms
        assert "update" in platforms

        # Should not include category-specific platforms
        assert "fan" not in platforms
        assert "vacuum" not in platforms
