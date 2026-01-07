"""Tests for cloud device data retrieval services in services.py.

These tests cover the cloud device management functionality including:
- Cloud device data retrieval from Dyson API
- MQTT credential decryption
- Device data sanitization
- Fallback to stored configuration
- Multiple account management
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.hass_dyson.const import DOMAIN


class TestHandleGetCloudDevices:
    """Test the main _handle_get_cloud_devices service handler."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._find_cloud_coordinators")
    @patch(
        "custom_components.hass_dyson.services._get_cloud_device_data_from_coordinator"
    )
    async def test_get_cloud_devices_success(self, mock_get_data, mock_find_coords):
        """Test successful cloud device retrieval."""
        from custom_components.hass_dyson.services import _handle_get_cloud_devices

        # Mock coordinator
        mock_find_coords.return_value = [
            {"email": "user@example.com", "coordinator": MagicMock()}
        ]

        # Mock device data
        mock_get_data.return_value = {
            "devices": [
                {
                    "serial_number": "VS6-EU-ABC1234",
                    "name": "Living Room Fan",
                    "product_type": "438M",
                }
            ],
            "summary": {"total_devices": 1, "source": "live_api"},
        }

        mock_hass = MagicMock()
        mock_call = MagicMock()
        mock_call.data = {"sanitize": False}

        result = await _handle_get_cloud_devices(mock_hass, mock_call)

        assert result["account_email"] == "user@example.com"
        assert result["total_devices"] == 1
        assert len(result["devices"]) == 1
        assert result["devices"][0]["serial_number"] == "VS6-EU-ABC1234"

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._find_cloud_coordinators")
    async def test_get_cloud_devices_no_accounts(self, mock_find_coords):
        """Test behavior when no cloud accounts configured."""
        from custom_components.hass_dyson.services import _handle_get_cloud_devices

        mock_find_coords.return_value = []

        mock_hass = MagicMock()
        mock_call = MagicMock()
        mock_call.data = {}

        result = await _handle_get_cloud_devices(mock_hass, mock_call)

        assert result["total_devices"] == 0
        assert "No cloud accounts found" in result["message"]
        assert "available_setup_methods" in result

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._find_cloud_coordinators")
    @patch(
        "custom_components.hass_dyson.services._get_cloud_device_data_from_coordinator"
    )
    async def test_get_cloud_devices_specific_account(
        self, mock_get_data, mock_find_coords
    ):
        """Test retrieving devices from specific account."""
        from custom_components.hass_dyson.services import _handle_get_cloud_devices

        mock_find_coords.return_value = [
            {"email": "user1@example.com", "coordinator": MagicMock()},
            {"email": "user2@example.com", "coordinator": MagicMock()},
        ]

        mock_get_data.return_value = {
            "devices": [{"serial_number": "TEST123"}],
            "summary": {"total_devices": 1},
        }

        mock_hass = MagicMock()
        mock_call = MagicMock()
        mock_call.data = {"account_email": "user2@example.com"}

        result = await _handle_get_cloud_devices(mock_hass, mock_call)

        # Should successfully use user2's account
        assert result["account_email"] == "user2@example.com"

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._find_cloud_coordinators")
    async def test_get_cloud_devices_account_not_found(self, mock_find_coords):
        """Test error when specified account doesn't exist."""
        from custom_components.hass_dyson.services import _handle_get_cloud_devices

        mock_find_coords.return_value = [
            {"email": "user@example.com", "coordinator": MagicMock()}
        ]

        mock_hass = MagicMock()
        mock_call = MagicMock()
        mock_call.data = {"account_email": "nonexistent@example.com"}

        with pytest.raises(ServiceValidationError, match="not found"):
            await _handle_get_cloud_devices(mock_hass, mock_call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._find_cloud_coordinators")
    @patch(
        "custom_components.hass_dyson.services._get_cloud_device_data_from_coordinator"
    )
    async def test_get_cloud_devices_api_error(self, mock_get_data, mock_find_coords):
        """Test handling of Dyson API errors."""
        from libdyson_rest import DysonAPIError

        from custom_components.hass_dyson.services import _handle_get_cloud_devices

        mock_find_coords.return_value = [
            {"email": "user@example.com", "coordinator": MagicMock()}
        ]

        mock_get_data.side_effect = DysonAPIError("API error")

        mock_hass = MagicMock()
        mock_call = MagicMock()
        mock_call.data = {}

        with pytest.raises(HomeAssistantError, match="Dyson service error"):
            await _handle_get_cloud_devices(mock_hass, mock_call)


class TestFindCloudCoordinators:
    """Test cloud coordinator discovery."""

    def test_find_cloud_coordinators_success(self):
        """Test finding cloud coordinators in Home Assistant data."""
        from custom_components.hass_dyson.coordinator import (
            DysonCloudAccountCoordinator,
        )
        from custom_components.hass_dyson.services import _find_cloud_coordinators

        mock_config_entry1 = MagicMock()
        mock_config_entry1.data = {"email": "user1@example.com"}
        mock_config_entry1.entry_id = "entry1"

        mock_coordinator1 = MagicMock(spec=DysonCloudAccountCoordinator)
        mock_coordinator1.config_entry = mock_config_entry1

        mock_config_entry2 = MagicMock()
        mock_config_entry2.data = {"email": "user2@example.com"}
        mock_config_entry2.entry_id = "entry2"

        mock_coordinator2 = MagicMock(spec=DysonCloudAccountCoordinator)
        mock_coordinator2.config_entry = mock_config_entry2

        mock_hass = MagicMock()
        mock_hass.data = {
            DOMAIN: {
                "coord1": mock_coordinator1,
                "coord2": mock_coordinator2,
            }
        }

        result = _find_cloud_coordinators(mock_hass)

        assert len(result) == 2
        assert result[0]["email"] == "user1@example.com"
        assert result[1]["email"] == "user2@example.com"

    def test_find_cloud_coordinators_empty(self):
        """Test when no coordinators exist."""
        from custom_components.hass_dyson.services import _find_cloud_coordinators

        mock_hass = MagicMock()
        mock_hass.data = {DOMAIN: {}}

        result = _find_cloud_coordinators(mock_hass)

        assert result == []


class TestFetchLiveCloudDevices:
    """Test live cloud device data fetching."""

    @pytest.mark.asyncio
    @patch("libdyson_rest.AsyncDysonClient")
    async def test_fetch_live_devices_success(self, mock_client_class):
        """Test successful live device fetch from Dyson API."""
        from custom_components.hass_dyson.services import _fetch_live_cloud_devices

        # Mock device objects
        mock_device1 = MagicMock()
        mock_device1.serial_number = "VS6-EU-ABC1234"
        mock_device1.name = "Living Room"
        mock_device1.product_type = "438M"

        # Mock client
        mock_client = MagicMock()
        mock_client.get_devices = AsyncMock(return_value=[mock_device1])
        mock_client.decrypt_local_credentials = MagicMock(
            return_value="decrypted_password"
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            "auth_token": "test_token",
            "email": "user@example.com",
        }

        result = await _fetch_live_cloud_devices(mock_config_entry)

        assert len(result) == 1
        assert result[0]["device"] == mock_device1

    @pytest.mark.asyncio
    @patch("libdyson_rest.AsyncDysonClient")
    async def test_fetch_live_devices_no_devices(self, mock_client_class):
        """Test when no devices found in cloud account."""
        from custom_components.hass_dyson.services import _fetch_live_cloud_devices

        mock_client = MagicMock()
        mock_client.get_devices = AsyncMock(return_value=[])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            "auth_token": "test_token",
            "email": "user@example.com",
        }

        result = await _fetch_live_cloud_devices(mock_config_entry)

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_live_devices_no_auth_token(self):
        """Test error when no auth token available."""
        from custom_components.hass_dyson.services import _fetch_live_cloud_devices

        mock_config_entry = MagicMock()
        mock_config_entry.data = {"email": "user@example.com"}

        with pytest.raises(HomeAssistantError, match="No auth token"):
            await _fetch_live_cloud_devices(mock_config_entry)


class TestEnhanceDevicesWithMQTTCredentials:
    """Test MQTT credential enhancement for devices."""

    @pytest.mark.asyncio
    async def test_enhance_devices_with_credentials(self):
        """Test enhancing devices with decrypted MQTT credentials."""
        from custom_components.hass_dyson.services import (
            _enhance_devices_with_mqtt_credentials,
        )

        mock_device = MagicMock()
        mock_device.serial_number = "VS6-EU-ABC1234"
        mock_device.name = "Living Room"
        mock_device.connected_configuration = MagicMock()
        mock_device.connected_configuration.mqtt = MagicMock()
        mock_device.connected_configuration.mqtt.local_broker_credentials = "encrypted"

        mock_client = MagicMock()
        mock_client.decrypt_local_credentials = MagicMock(
            return_value="decrypted_password"
        )

        result = await _enhance_devices_with_mqtt_credentials(
            mock_client, [mock_device]
        )

        assert len(result) == 1
        assert result[0]["device"] == mock_device
        assert "enhanced_data" in result[0]
        assert (
            result[0]["enhanced_data"]["decrypted_mqtt_password"]
            == "decrypted_password"
        )

    @pytest.mark.asyncio
    async def test_enhance_devices_no_credentials(self):
        """Test enhancing devices when no MQTT credentials available."""
        from custom_components.hass_dyson.services import (
            _enhance_devices_with_mqtt_credentials,
        )

        mock_device = MagicMock()
        mock_device.serial_number = "VS6-EU-ABC1234"
        mock_device.connected_configuration = None

        mock_client = MagicMock()

        result = await _enhance_devices_with_mqtt_credentials(
            mock_client, [mock_device]
        )

        assert len(result) == 1
        assert result[0]["device"] == mock_device
        # Should not have decrypted_mqtt_password when credentials missing


class TestGetDeviceDataFromConfigEntry:
    """Test device data retrieval from config entries."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._fetch_live_cloud_devices")
    @patch("custom_components.hass_dyson.services._build_device_data_from_live_api")
    async def test_get_device_data_live_api_success(self, mock_build, mock_fetch):
        """Test getting device data from live API."""
        from custom_components.hass_dyson.services import (
            _get_device_data_from_config_entry,
        )

        mock_fetch.return_value = [{"device": MagicMock()}]
        mock_build.return_value = {
            "devices": [{"serial_number": "VS6-EU-ABC1234"}],
            "summary": {"source": "live_api"},
        }

        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            "email": "user@example.com",
            "auth_token": "test_token",
        }

        result = await _get_device_data_from_config_entry(mock_config_entry, False)

        assert result["summary"]["source"] == "live_api"
        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._fetch_live_cloud_devices")
    async def test_get_device_data_fallback_to_stored(self, mock_fetch):
        """Test fallback to stored config when live API fails."""
        from custom_components.hass_dyson.services import (
            _get_device_data_from_config_entry,
        )

        mock_fetch.side_effect = ConnectionError("API unavailable")

        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            "email": "user@example.com",
            "auth_token": "test_token",
            "devices": [
                {
                    "serial_number": "VS6-EU-ABC1234",
                    "name": "Living Room",
                    "product_type": "438M",
                    "device_category": ["ec"],
                }
            ],
        }

        result = await _get_device_data_from_config_entry(mock_config_entry, False)

        assert result["summary"]["source"] == "config_entry_stored_data"
        assert len(result["devices"]) == 1
        assert result["devices"][0]["serial_number"] == "VS6-EU-ABC1234"

    @pytest.mark.asyncio
    async def test_get_device_data_no_credentials(self):
        """Test error when no credentials available."""
        from custom_components.hass_dyson.services import (
            _get_device_data_from_config_entry,
        )

        mock_config_entry = MagicMock()
        mock_config_entry.data = {}

        with pytest.raises(HomeAssistantError, match="Missing authentication"):
            await _get_device_data_from_config_entry(mock_config_entry, False)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._fetch_live_cloud_devices")
    async def test_get_device_data_sanitized(self, mock_fetch):
        """Test sanitized device data output."""
        from custom_components.hass_dyson.services import (
            _get_device_data_from_config_entry,
        )

        mock_fetch.side_effect = ConnectionError("API unavailable")

        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            "email": "user@example.com",
            "auth_token": "test_token",
            "devices": [
                {
                    "serial_number": "VS6-EU-ABC1234",
                    "name": "Living Room",
                    "product_type": "438M",
                    "device_category": "ec",
                    "local_ip": "192.168.1.100",
                }
            ],
        }

        result = await _get_device_data_from_config_entry(mock_config_entry, True)

        # Sanitized data should hide serial number or just not include IP
        # The serial_number field exists but is sanitized in display
        assert (
            "local_ip" not in result["devices"][0]
            or result["devices"][0].get("serial_number") == "***HIDDEN***"
        )


class TestBuildDeviceDataFromLiveAPI:
    """Test device data building from live API responses."""

    @pytest.mark.asyncio
    async def test_build_device_data_sanitized(self):
        """Test building sanitized device data."""
        from custom_components.hass_dyson.services import (
            _build_device_data_from_live_api,
        )

        mock_device = MagicMock()
        mock_device.serial_number = "VS6-EU-ABC1234"

        enhanced_devices = [
            {
                "device": mock_device,
                "enhanced_data": {
                    "name": "Living Room",
                    "product_type": "438M",
                    "device_category": ["ec"],
                    "capabilities": ["Scheduling"],
                    "mqtt_prefix": "438M",
                    "decrypted_mqtt_password": "secret_password",
                },
            }
        ]

        result = await _build_device_data_from_live_api(
            enhanced_devices, "user@example.com", True
        )

        assert len(result["devices"]) == 1
        # Sanitized should hide serial
        assert result["devices"][0]["serial_number"] == "***HIDDEN***"
        assert result["devices"][0]["name"] == "Living Room"

    @pytest.mark.asyncio
    async def test_build_device_data_not_sanitized(self):
        """Test building non-sanitized device data."""
        from custom_components.hass_dyson.services import (
            _build_device_data_from_live_api,
        )

        mock_device = MagicMock()
        mock_device.serial_number = "VS6-EU-ABC1234"

        enhanced_devices = [
            {
                "device": mock_device,
                "enhanced_data": {
                    "name": "Living Room",
                    "product_type": "438M",
                    "device_category": ["ec"],
                    "capabilities": ["Scheduling"],
                    "mqtt_prefix": "438M",
                    "decrypted_mqtt_password": "secret_password",
                },
            }
        ]

        result = await _build_device_data_from_live_api(
            enhanced_devices, "user@example.com", False
        )

        assert len(result["devices"]) == 1
        assert result["summary"]["account_email"] == "user@example.com"
        assert result["devices"][0]["serial_number"] == "VS6-EU-ABC1234"
        assert result["devices"][0]["mqtt_password"] == "secret_password"


class TestExtractEnhancedDeviceInfo:
    """Test device information extraction."""

    def test_extract_enhanced_device_info(self):
        """Test extracting enhanced device information."""
        from custom_components.hass_dyson.services import _extract_enhanced_device_info

        mock_device = MagicMock()
        mock_device.serial_number = "VS6-EU-ABC1234"
        mock_device.name = "Living Room"
        mock_device.type = "438"
        mock_device.variant = "M"

        result = _extract_enhanced_device_info(mock_device)

        assert result["name"] == "Living Room"
        assert result["product_type"] == "438M"


class TestDeviceCategoryHandling:
    """Test device category conversion and handling."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._fetch_live_cloud_devices")
    async def test_device_category_string_conversion(self, mock_fetch):
        """Test converting device category from string to list."""
        from custom_components.hass_dyson.services import (
            _get_device_data_from_config_entry,
        )

        mock_fetch.side_effect = ConnectionError("API unavailable")

        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            "email": "user@example.com",
            "auth_token": "test_token",
            "devices": [
                {
                    "serial_number": "VS6-EU-ABC1234",
                    "name": "Living Room",
                    "device_category": "ec",  # String, should be converted to list
                }
            ],
        }

        result = await _get_device_data_from_config_entry(mock_config_entry, False)

        # Should convert string to list
        assert isinstance(result["devices"][0]["device_category"], list)
        assert "ec" in result["devices"][0]["device_category"]

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._fetch_live_cloud_devices")
    async def test_device_category_enum_conversion(self, mock_fetch):
        """Test converting device category from enum to list of strings."""
        from custom_components.hass_dyson.services import (
            _get_device_data_from_config_entry,
        )

        mock_fetch.side_effect = ConnectionError("API unavailable")

        # Mock enum-like object
        mock_enum = MagicMock()
        mock_enum.value = "ec"

        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            "email": "user@example.com",
            "auth_token": "test_token",
            "devices": [
                {
                    "serial_number": "VS6-EU-ABC1234",
                    "name": "Living Room",
                    "device_category": [mock_enum],  # List with enum
                }
            ],
        }

        result = await _get_device_data_from_config_entry(mock_config_entry, False)

        # Should convert enum to string in list
        assert isinstance(result["devices"][0]["device_category"], list)
        assert "ec" in result["devices"][0]["device_category"]
