"""Comprehensive error handling tests for services module to improve coverage.

Focuses on error paths, edge cases, and exception handling for:
- Reset filter service (hepa, carbon, both)
- Refresh account data service
- Get cloud devices service
- Helper functions and validation
- Service registration and unregistration
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from libdyson_rest import DysonAPIError, DysonAuthError, DysonConnectionError

from custom_components.hass_dyson.const import (
    CONF_DISCOVERY_METHOD,
    DISCOVERY_CLOUD,
    DOMAIN,
)
from custom_components.hass_dyson.services import (
    _convert_to_string,
    _decrypt_device_mqtt_credentials,
    _find_cloud_coordinators,
    async_handle_refresh_account_data,
)


@pytest.fixture
def pure_mock_hass():
    """Create a minimal mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    hass.config_entries = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    return hass


@pytest.fixture
def mock_service_call():
    """Create a mock service call."""
    call = MagicMock()
    call.data = {}
    return call


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.device = MagicMock()
    coordinator.serial_number = "VS6-EU-HJA1234A"
    coordinator.async_refresh = AsyncMock()
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {
        CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD,
        CONF_USERNAME: "test@example.com",
        "email": "test@example.com",
    }
    coordinator.config_entry.entry_id = "test_entry_123"
    return coordinator


class TestResetFilterService:
    """Test reset filter service error scenarios."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_reset_filter_device_not_found(
        self, mock_get_coord, pure_mock_hass, mock_service_call
    ):
        """Test reset filter when device not found."""
        from custom_components.hass_dyson.services import _handle_reset_filter

        mock_get_coord.return_value = None
        mock_service_call.data = {"device_id": "test_device", "filter_type": "hepa"}

        with pytest.raises(ServiceValidationError, match="not found or not available"):
            await _handle_reset_filter(pure_mock_hass, mock_service_call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_reset_filter_no_device_object(
        self, mock_get_coord, pure_mock_hass, mock_service_call, mock_coordinator
    ):
        """Test reset filter when coordinator has no device."""
        from custom_components.hass_dyson.services import _handle_reset_filter

        mock_coordinator.device = None
        mock_get_coord.return_value = mock_coordinator
        mock_service_call.data = {"device_id": "test_device", "filter_type": "hepa"}

        with pytest.raises(ServiceValidationError, match="not found or not available"):
            await _handle_reset_filter(pure_mock_hass, mock_service_call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_reset_hepa_filter_connection_error(
        self, mock_get_coord, pure_mock_hass, mock_service_call, mock_coordinator
    ):
        """Test reset HEPA filter with connection error."""
        from custom_components.hass_dyson.services import _handle_reset_filter

        mock_coordinator.device.reset_hepa_filter_life = AsyncMock(
            side_effect=ConnectionError("Network error")
        )
        mock_get_coord.return_value = mock_coordinator
        mock_service_call.data = {"device_id": "test_device", "filter_type": "hepa"}

        with pytest.raises(HomeAssistantError, match="Device communication failed"):
            await _handle_reset_filter(pure_mock_hass, mock_service_call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_reset_carbon_filter_attribute_error(
        self, mock_get_coord, pure_mock_hass, mock_service_call, mock_coordinator
    ):
        """Test reset carbon filter when method not supported."""
        from custom_components.hass_dyson.services import _handle_reset_filter

        mock_coordinator.device.reset_carbon_filter_life = AsyncMock(
            side_effect=AttributeError("Method not available")
        )
        mock_get_coord.return_value = mock_coordinator
        mock_service_call.data = {"device_id": "test_device", "filter_type": "carbon"}

        with pytest.raises(HomeAssistantError, match="not supported"):
            await _handle_reset_filter(pure_mock_hass, mock_service_call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_reset_both_filters_timeout(
        self, mock_get_coord, pure_mock_hass, mock_service_call, mock_coordinator
    ):
        """Test reset both filters with timeout error."""
        from custom_components.hass_dyson.services import _handle_reset_filter

        mock_coordinator.device.reset_hepa_filter_life = AsyncMock(
            side_effect=TimeoutError("Request timeout")
        )
        mock_coordinator.device.reset_carbon_filter_life = AsyncMock()
        mock_get_coord.return_value = mock_coordinator
        mock_service_call.data = {"device_id": "test_device", "filter_type": "both"}

        with pytest.raises(HomeAssistantError, match="Device communication failed"):
            await _handle_reset_filter(pure_mock_hass, mock_service_call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_reset_filter_unexpected_exception(
        self, mock_get_coord, pure_mock_hass, mock_service_call, mock_coordinator
    ):
        """Test reset filter with unexpected exception."""
        from custom_components.hass_dyson.services import _handle_reset_filter

        mock_coordinator.device.reset_hepa_filter_life = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )
        mock_get_coord.return_value = mock_coordinator
        mock_service_call.data = {"device_id": "test_device", "filter_type": "hepa"}

        with pytest.raises(HomeAssistantError, match="Failed to reset hepa filter"):
            await _handle_reset_filter(pure_mock_hass, mock_service_call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_reset_both_filters_success(
        self, mock_get_coord, pure_mock_hass, mock_service_call, mock_coordinator
    ):
        """Test successful reset of both filters."""
        from custom_components.hass_dyson.services import _handle_reset_filter

        mock_coordinator.device.reset_hepa_filter_life = AsyncMock()
        mock_coordinator.device.reset_carbon_filter_life = AsyncMock()
        mock_get_coord.return_value = mock_coordinator
        mock_service_call.data = {"device_id": "test_device", "filter_type": "both"}

        await _handle_reset_filter(pure_mock_hass, mock_service_call)

        # Both methods should be called
        mock_coordinator.device.reset_hepa_filter_life.assert_called_once()
        mock_coordinator.device.reset_carbon_filter_life.assert_called_once()


class TestRefreshAccountDataService:
    """Test refresh account data service error scenarios."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_refresh_specific_device_not_found(
        self, mock_get_coord, pure_mock_hass, mock_service_call
    ):
        """Test refresh with device ID but device not found."""
        mock_get_coord.return_value = None
        mock_service_call.data = {"device_id": "nonexistent_device"}

        with pytest.raises(ServiceValidationError, match="not found"):
            await async_handle_refresh_account_data(pure_mock_hass, mock_service_call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_refresh_specific_device_connection_error(
        self, mock_get_coord, pure_mock_hass, mock_service_call, mock_coordinator
    ):
        """Test refresh specific device with connection error."""
        mock_coordinator.async_refresh = AsyncMock(
            side_effect=ConnectionError("Network failed")
        )
        mock_get_coord.return_value = mock_coordinator
        mock_service_call.data = {"device_id": "test_device"}

        with pytest.raises(HomeAssistantError, match="Device communication failed"):
            await async_handle_refresh_account_data(pure_mock_hass, mock_service_call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_refresh_specific_device_timeout(
        self, mock_get_coord, pure_mock_hass, mock_service_call, mock_coordinator
    ):
        """Test refresh specific device with timeout."""
        mock_coordinator.async_refresh = AsyncMock(side_effect=TimeoutError("Timeout"))
        mock_get_coord.return_value = mock_coordinator
        mock_service_call.data = {"device_id": "test_device"}

        with pytest.raises(HomeAssistantError, match="Device communication failed"):
            await async_handle_refresh_account_data(pure_mock_hass, mock_service_call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_refresh_specific_device_unexpected_error(
        self, mock_get_coord, pure_mock_hass, mock_service_call, mock_coordinator
    ):
        """Test refresh specific device with unexpected error."""
        mock_coordinator.async_refresh = AsyncMock(
            side_effect=RuntimeError("Unexpected")
        )
        mock_get_coord.return_value = mock_coordinator
        mock_service_call.data = {"device_id": "test_device"}

        with pytest.raises(HomeAssistantError, match="Failed to refresh account data"):
            await async_handle_refresh_account_data(pure_mock_hass, mock_service_call)

    @pytest.mark.asyncio
    async def test_refresh_all_devices_connection_error(
        self, pure_mock_hass, mock_service_call
    ):
        """Test refresh all devices with one device having connection error."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

        # Create coordinators
        coordinator1 = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator1.serial_number = "VS6-EU-HJA1234A"
        coordinator1.async_refresh = AsyncMock()

        coordinator2 = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator2.serial_number = "VS6-EU-HJA5678B"
        coordinator2.async_refresh = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        pure_mock_hass.data[DOMAIN] = {
            "coord1": coordinator1,
            "coord2": coordinator2,
        }
        mock_service_call.data = {}  # No device_id means refresh all

        # Should not raise error, just log warning for failed device
        await async_handle_refresh_account_data(pure_mock_hass, mock_service_call)

        # Both coordinators should be called
        coordinator1.async_refresh.assert_called_once()
        coordinator2.async_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_all_devices_unexpected_error(
        self, pure_mock_hass, mock_service_call
    ):
        """Test refresh all devices with unexpected error."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

        coordinator1 = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator1.serial_number = "VS6-EU-HJA1234A"
        coordinator1.async_refresh = AsyncMock(side_effect=RuntimeError("Unexpected"))

        pure_mock_hass.data[DOMAIN] = {"coord1": coordinator1}
        mock_service_call.data = {}

        # Should not raise error for unexpected errors in batch refresh
        await async_handle_refresh_account_data(pure_mock_hass, mock_service_call)

        coordinator1.async_refresh.assert_called_once()


class TestGetCloudDevicesService:
    """Test get cloud devices service error scenarios."""

    @pytest.mark.asyncio
    async def test_get_cloud_devices_no_coordinators(
        self, pure_mock_hass, mock_service_call
    ):
        """Test get cloud devices when no cloud coordinators exist."""
        from custom_components.hass_dyson.services import _handle_get_cloud_devices

        pure_mock_hass.data[DOMAIN] = {}
        mock_service_call.data = {}

        # Returns helpful message instead of raising error
        result = await _handle_get_cloud_devices(pure_mock_hass, mock_service_call)

        assert result["total_devices"] == 0
        assert result["devices"] == []
        assert "No cloud accounts found" in result["message"]

    @pytest.mark.asyncio
    async def test_get_cloud_devices_account_not_found(
        self, pure_mock_hass, mock_service_call, mock_coordinator
    ):
        """Test get cloud devices with non-existent account email."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
        from custom_components.hass_dyson.services import _handle_get_cloud_devices

        pure_mock_hass.data[DOMAIN] = {"coord1": mock_coordinator}
        mock_service_call.data = {"account_email": "nonexistent@example.com"}

        with patch.object(mock_coordinator, "__class__", DysonDataUpdateCoordinator):
            with pytest.raises(
                HomeAssistantError, match="not found"
            ):  # Match actual error message
                await _handle_get_cloud_devices(pure_mock_hass, mock_service_call)

    @pytest.mark.asyncio
    @patch(
        "custom_components.hass_dyson.services._get_cloud_device_data_from_coordinator"
    )
    async def test_get_cloud_devices_dyson_auth_error(
        self, mock_get_data, pure_mock_hass, mock_service_call, mock_coordinator
    ):
        """Test get cloud devices with Dyson authentication error."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
        from custom_components.hass_dyson.services import _handle_get_cloud_devices

        mock_get_data.side_effect = DysonAuthError("Auth failed")
        pure_mock_hass.data[DOMAIN] = {"coord1": mock_coordinator}
        mock_service_call.data = {}

        with patch.object(mock_coordinator, "__class__", DysonDataUpdateCoordinator):
            with pytest.raises(HomeAssistantError, match="Dyson service error"):
                await _handle_get_cloud_devices(pure_mock_hass, mock_service_call)

    @pytest.mark.asyncio
    @patch(
        "custom_components.hass_dyson.services._get_cloud_device_data_from_coordinator"
    )
    async def test_get_cloud_devices_connection_error(
        self, mock_get_data, pure_mock_hass, mock_service_call, mock_coordinator
    ):
        """Test get cloud devices with connection error."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
        from custom_components.hass_dyson.services import _handle_get_cloud_devices

        mock_get_data.side_effect = DysonConnectionError("Connection failed")
        pure_mock_hass.data[DOMAIN] = {"coord1": mock_coordinator}
        mock_service_call.data = {}

        with patch.object(mock_coordinator, "__class__", DysonDataUpdateCoordinator):
            with pytest.raises(HomeAssistantError, match="Dyson service error"):
                await _handle_get_cloud_devices(pure_mock_hass, mock_service_call)

    @pytest.mark.asyncio
    @patch(
        "custom_components.hass_dyson.services._get_cloud_device_data_from_coordinator"
    )
    async def test_get_cloud_devices_api_error(
        self, mock_get_data, pure_mock_hass, mock_service_call, mock_coordinator
    ):
        """Test get cloud devices with API error."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
        from custom_components.hass_dyson.services import _handle_get_cloud_devices

        mock_get_data.side_effect = DysonAPIError("API error")
        pure_mock_hass.data[DOMAIN] = {"coord1": mock_coordinator}
        mock_service_call.data = {}

        with patch.object(mock_coordinator, "__class__", DysonDataUpdateCoordinator):
            with pytest.raises(HomeAssistantError, match="Dyson service error"):
                await _handle_get_cloud_devices(pure_mock_hass, mock_service_call)

    @pytest.mark.asyncio
    @patch(
        "custom_components.hass_dyson.services._get_cloud_device_data_from_coordinator"
    )
    async def test_get_cloud_devices_unexpected_error(
        self, mock_get_data, pure_mock_hass, mock_service_call, mock_coordinator
    ):
        """Test get cloud devices with unexpected error."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
        from custom_components.hass_dyson.services import _handle_get_cloud_devices

        mock_get_data.side_effect = RuntimeError("Unexpected")
        pure_mock_hass.data[DOMAIN] = {"coord1": mock_coordinator}
        mock_service_call.data = {}

        with patch.object(mock_coordinator, "__class__", DysonDataUpdateCoordinator):
            with pytest.raises(HomeAssistantError, match="Unexpected error"):
                await _handle_get_cloud_devices(pure_mock_hass, mock_service_call)


class TestHelperFunctions:
    """Test helper function error scenarios."""

    def test_convert_to_string_with_value_attribute(self):
        """Test _convert_to_string with object having value attribute."""
        mock_enum = MagicMock()
        mock_enum.value = "ACTIVE"

        result = _convert_to_string(mock_enum)
        assert result == "ACTIVE"

    def test_convert_to_string_without_value_attribute(self):
        """Test _convert_to_string with regular object."""
        result = _convert_to_string("plain_string")
        assert result == "plain_string"

        result = _convert_to_string(42)
        assert result == "42"

    def test_decrypt_credentials_no_connected_config(self):
        """Test credential decryption with no connected configuration."""
        mock_device = MagicMock()
        mock_device.connected_configuration = None
        mock_device.serial_number = "TEST123"

        mock_client = MagicMock()

        result = _decrypt_device_mqtt_credentials(mock_client, mock_device)
        assert result == ""

    def test_decrypt_credentials_no_mqtt_object(self):
        """Test credential decryption with no MQTT object."""
        mock_device = MagicMock()
        mock_config = MagicMock()
        mock_config.mqtt = None
        mock_device.connected_configuration = mock_config
        mock_device.serial_number = "TEST123"

        mock_client = MagicMock()

        result = _decrypt_device_mqtt_credentials(mock_client, mock_device)
        assert result == ""

    def test_decrypt_credentials_no_encrypted_data(self):
        """Test credential decryption with no encrypted credentials."""
        mock_device = MagicMock()
        mock_mqtt = MagicMock()
        mock_mqtt.local_broker_credentials = ""
        mock_config = MagicMock()
        mock_config.mqtt = mock_mqtt
        mock_device.connected_configuration = mock_config
        mock_device.serial_number = "TEST123"

        mock_client = MagicMock()

        result = _decrypt_device_mqtt_credentials(mock_client, mock_device)
        assert result == ""

    def test_decrypt_credentials_value_error(self):
        """Test credential decryption with ValueError."""
        mock_device = MagicMock()
        mock_mqtt = MagicMock()
        mock_mqtt.local_broker_credentials = "invalid_format"
        mock_config = MagicMock()
        mock_config.mqtt = mock_mqtt
        mock_device.connected_configuration = mock_config
        mock_device.serial_number = "TEST123"

        mock_client = MagicMock()
        mock_client.decrypt_local_credentials = MagicMock(
            side_effect=ValueError("Invalid format")
        )

        result = _decrypt_device_mqtt_credentials(mock_client, mock_device)
        assert result == ""

    def test_decrypt_credentials_key_error(self):
        """Test credential decryption with KeyError."""
        mock_device = MagicMock()
        mock_mqtt = MagicMock()
        mock_mqtt.local_broker_credentials = "encrypted_data"
        mock_config = MagicMock()
        mock_config.mqtt = mock_mqtt
        mock_device.connected_configuration = mock_config
        mock_device.serial_number = "TEST123"

        mock_client = MagicMock()
        mock_client.decrypt_local_credentials = MagicMock(
            side_effect=KeyError("Missing key")
        )

        result = _decrypt_device_mqtt_credentials(mock_client, mock_device)
        assert result == ""

    def test_decrypt_credentials_unexpected_error(self):
        """Test credential decryption with unexpected error."""
        mock_device = MagicMock()
        mock_mqtt = MagicMock()
        mock_mqtt.local_broker_credentials = "encrypted_data"
        mock_config = MagicMock()
        mock_config.mqtt = mock_mqtt
        mock_device.connected_configuration = mock_config
        mock_device.serial_number = "TEST123"

        mock_client = MagicMock()
        mock_client.decrypt_local_credentials = MagicMock(
            side_effect=RuntimeError("Unexpected error")
        )

        result = _decrypt_device_mqtt_credentials(mock_client, mock_device)
        assert result == ""


class TestFindCloudCoordinators:
    """Test _find_cloud_coordinators function."""

    def test_find_cloud_coordinators_empty_domain(self, pure_mock_hass):
        """Test finding coordinators with empty domain data."""
        pure_mock_hass.data = {}

        result = _find_cloud_coordinators(pure_mock_hass)
        assert result == []

    def test_find_cloud_coordinators_cloud_account_type(
        self, pure_mock_hass, mock_coordinator
    ):
        """Test finding cloud account coordinators."""
        from custom_components.hass_dyson.coordinator import (
            DysonCloudAccountCoordinator,
        )

        # Create a cloud account coordinator mock
        cloud_coord = MagicMock(spec=DysonCloudAccountCoordinator)
        cloud_coord.config_entry = MagicMock()
        cloud_coord.config_entry.data = {"email": "cloud@example.com"}
        cloud_coord.config_entry.entry_id = "cloud_entry_123"

        pure_mock_hass.data[DOMAIN] = {"cloud_coord": cloud_coord}

        result = _find_cloud_coordinators(pure_mock_hass)

        assert len(result) == 1
        assert result[0]["email"] == "cloud@example.com"
        assert result[0]["type"] == "cloud_account"

    def test_find_cloud_coordinators_device_with_cloud_discovery(
        self, pure_mock_hass, mock_coordinator
    ):
        """Test finding device coordinators with cloud discovery."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

        mock_coordinator.config_entry.data[CONF_DISCOVERY_METHOD] = DISCOVERY_CLOUD
        mock_coordinator.config_entry.data["email"] = "device@example.com"
        mock_coordinator.device = MagicMock()

        pure_mock_hass.data[DOMAIN] = {"device_coord": mock_coordinator}

        with patch.object(mock_coordinator, "__class__", DysonDataUpdateCoordinator):
            result = _find_cloud_coordinators(pure_mock_hass)

        assert len(result) == 1
        assert result[0]["email"] == "device@example.com"
        assert result[0]["type"] == "device"

    def test_find_cloud_coordinators_from_config_entries(self, pure_mock_hass):
        """Test finding coordinators from config entries when no active coordinators."""
        pure_mock_hass.data[DOMAIN] = {}

        mock_entry = MagicMock()
        mock_entry.data = {
            "email": "entry@example.com",
            "auth_token": "token123",
            "devices": ["device1", "device2"],
        }
        mock_entry.entry_id = "entry_123"

        pure_mock_hass.config_entries.async_entries = MagicMock(
            return_value=[mock_entry]
        )

        result = _find_cloud_coordinators(pure_mock_hass)

        assert len(result) == 1
        assert result[0]["email"] == "entry@example.com"
        assert result[0]["type"] == "config_entry"
        assert result[0]["config_entry"] == mock_entry


class TestFetchLiveCloudDevices:
    """Test _fetch_live_cloud_devices function."""

    @pytest.mark.asyncio
    async def test_fetch_live_devices_no_auth_token(self):
        """Test fetching live devices without auth token."""
        from custom_components.hass_dyson.services import _fetch_live_cloud_devices

        mock_config_entry = MagicMock()
        mock_config_entry.data = {"email": "test@example.com", "auth_token": None}

        with pytest.raises(HomeAssistantError, match="No auth token available"):
            await _fetch_live_cloud_devices(mock_config_entry)

    @pytest.mark.asyncio
    @patch("libdyson_rest.AsyncDysonClient")
    async def test_fetch_live_devices_empty_result(self, mock_client_class):
        """Test fetching live devices with empty result."""
        from custom_components.hass_dyson.services import _fetch_live_cloud_devices

        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            "email": "test@example.com",
            "auth_token": "token123",
        }

        # Mock client to return empty device list
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=[])
        mock_client_class.return_value = mock_client

        result = await _fetch_live_cloud_devices(mock_config_entry)

        assert result == []
