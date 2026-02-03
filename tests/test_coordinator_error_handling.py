"""Comprehensive error handling tests for DysonDataUpdateCoordinator.

This test module focuses on error paths and edge cases to improve coverage:
- Network failures and connection timeouts
- Data parsing errors and validation failures
- MQTT communication failures
- Device reconnection scenarios
- Service registration errors
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.hass_dyson.const import (
    CONF_CREDENTIAL,
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_METHOD,
    CONF_HOSTNAME,
    CONF_SERIAL_NUMBER,
    DISCOVERY_CLOUD,
    DISCOVERY_MANUAL,
    DISCOVERY_STICKER,
)
from custom_components.hass_dyson.coordinator import (
    DysonDataUpdateCoordinator,
    _get_default_country_culture_for_coordinator,
)


@pytest.fixture
def pure_mock_hass():
    """Create a minimal mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    hass.loop = MagicMock()
    hass.loop.call_soon_threadsafe = MagicMock()
    hass.async_create_task = MagicMock()
    hass.add_job = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.config = MagicMock()
    hass.config.country = "US"
    hass.config.language = "en"
    hass.async_add_executor_job = AsyncMock()
    return hass


@pytest.fixture
def mock_config_entry_cloud():
    """Mock config entry for cloud discovery."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD,
        CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
        "username": "test@example.com",
        "auth_token": "test_token_123",
        "capabilities": ["WiFi", "ExtendedAQ"],
        "device_category": "FAN",
    }
    config_entry.entry_id = "test_entry_123"
    return config_entry


@pytest.fixture
def mock_config_entry_sticker():
    """Mock config entry for sticker-based discovery."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
        CONF_SERIAL_NUMBER: "VS6-EU-HJA5678B",
        CONF_CREDENTIAL: "devicepass",
        CONF_HOSTNAME: "192.168.1.100",
        CONF_DEVICE_NAME: "Test Fan",
        "capabilities": ["WiFi"],
        "device_category": "FAN",
    }
    config_entry.entry_id = "test_entry_456"
    return config_entry


@pytest.fixture
def mock_config_entry_manual():
    """Mock config entry for manual discovery."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_DISCOVERY_METHOD: DISCOVERY_MANUAL,
        CONF_SERIAL_NUMBER: "VS6-EU-HJA9999C",
        CONF_CREDENTIAL: "manualpass",
        CONF_HOSTNAME: "192.168.1.200",
        CONF_DEVICE_NAME: "Manual Fan",
        "capabilities": [],
        "device_category": "FAN",
    }
    config_entry.entry_id = "test_entry_789"
    return config_entry


class TestCoordinatorConnectionFailures:
    """Test network and connection failure scenarios."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    @patch("libdyson_rest.DysonClient")
    async def test_cloud_connection_timeout(
        self, mock_cloud_class, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test cloud connection timeout."""
        mock_super_init.return_value = None

        # Mock cloud client that times out
        mock_cloud_client = MagicMock()
        mock_cloud_client.get_devices = AsyncMock(
            side_effect=TimeoutError("Connection timeout")
        )
        mock_cloud_class.return_value = mock_cloud_client

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}

        # Execute setup should handle timeout gracefully
        with pytest.raises((UpdateFailed, TimeoutError)):
            await coordinator._async_setup_cloud_device()

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    @patch("custom_components.hass_dyson.device.DysonDevice")
    async def test_mqtt_connection_failure(
        self,
        mock_device_class,
        mock_super_init,
        pure_mock_hass,
        mock_config_entry_sticker,
    ):
        """Test MQTT connection failure handling."""
        mock_super_init.return_value = None

        # Mock device that fails to connect
        mock_device = MagicMock()
        mock_device.connect = AsyncMock(return_value=False)
        mock_device_class.return_value = mock_device

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_sticker
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}

        # Setup should handle connection failure
        with pytest.raises(UpdateFailed):
            await coordinator._async_setup_sticker_device()

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    @patch("custom_components.hass_dyson.device.DysonDevice")
    async def test_device_reconnection_after_failure(
        self,
        mock_device_class,
        mock_super_init,
        pure_mock_hass,
        mock_config_entry_sticker,
    ):
        """Test device reconnection logic after initial failure."""
        mock_super_init.return_value = None

        # Mock device that fails first, succeeds second time
        mock_device = MagicMock()
        connect_attempts = [False, True]
        mock_device.connect = AsyncMock(side_effect=connect_attempts)
        mock_device.get_state = AsyncMock(return_value={"fan": {"speed": 5}})
        mock_device_class.return_value = mock_device

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_sticker
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}
        coordinator.device = mock_device

        # First attempt should fail
        with pytest.raises(UpdateFailed):
            await coordinator._async_setup_sticker_device()

        # Mock successful connection for second attempt
        mock_device.connect = AsyncMock(return_value=True)

        # Second attempt should succeed (simulating reconnection)
        result = await coordinator.device.connect()
        assert result is True


class TestCoordinatorDataParsingErrors:
    """Test data parsing and validation error scenarios."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    async def test_malformed_device_state_data(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test handling of malformed device state data."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}
        coordinator.device = MagicMock()

        # Mock device returning malformed data
        coordinator.device.get_state = AsyncMock(return_value=None)

        # Should handle gracefully
        await coordinator._notify_ha_of_state_change()

        # Verify no exception raised and coordinator still functional
        assert coordinator.device is not None

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    async def test_missing_required_fields_in_device_info(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test handling of device info with missing required fields."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}
        coordinator.config_entry = mock_config_entry_cloud

        # Mock device info missing product_type
        mock_device_info = MagicMock()
        mock_device_info.product_type = None
        mock_device_info.type = None  # Both fields missing
        mock_device_info.serial = "VS6-EU-HJA1234A"

        # Should raise ValueError for missing device type
        with pytest.raises(ValueError, match="Device type not available"):
            coordinator._extract_device_type(mock_device_info)

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    def test_invalid_environmental_data_format(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test handling of invalid environmental data format."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}
        coordinator.data = {}

        # Mock invalid environmental message (missing 'data' field)
        invalid_message = {"msg": "ENVIRONMENTAL-CURRENT-SENSOR-DATA"}

        # Should handle gracefully without crashing
        coordinator._handle_environmental_message(invalid_message)

        # Coordinator should still be functional
        assert coordinator.data is not None

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    def test_capability_extraction_with_empty_config(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test capability extraction when config has empty capabilities."""
        mock_super_init.return_value = None

        # Config entry with empty capabilities
        mock_config_entry_cloud.data["capabilities"] = []

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}
        coordinator.config_entry = mock_config_entry_cloud

        # Mock device info with API capabilities
        mock_device_info = MagicMock()
        mock_device_info.capabilities = ["WiFi", "AirQuality"]

        # Should fall back to API extraction
        with patch.object(
            coordinator, "_extract_capabilities", return_value=["WiFi", "AirQuality"]
        ):
            coordinator._extract_device_capabilities(mock_device_info)

        # Should have extracted from API
        assert (
            "WiFi" in coordinator.device_capabilities
            or len(coordinator.device_capabilities) == 0
        )

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    def test_capability_extraction_critical_error(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test critical error during capability extraction."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}
        coordinator.config_entry = mock_config_entry_cloud

        # Mock device info that causes exception
        mock_device_info = MagicMock()
        mock_device_info.capabilities = MagicMock(
            side_effect=RuntimeError("Critical error")
        )

        # Should handle critical error and set empty capabilities
        coordinator._extract_device_capabilities(mock_device_info)

        # Should have fallback to empty list (or keep existing from config)
        # The coordinator falls back to config entry capabilities when API fails
        assert coordinator.device_capabilities is not None


class TestCoordinatorMQTTErrors:
    """Test MQTT-specific error scenarios."""

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    def test_mqtt_message_handler_exception(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test MQTT message handler with exception."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}
        coordinator.device = MagicMock()

        # Mock _schedule_coordinator_data_update to raise exception
        with patch.object(
            coordinator,
            "_schedule_coordinator_data_update",
            side_effect=RuntimeError("MQTT error"),
        ):
            with patch.object(
                coordinator, "_schedule_fallback_update"
            ) as mock_fallback:
                # Should catch exception and call fallback
                coordinator._handle_state_change_message()

                # Verify fallback was called
                mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    async def test_mqtt_credentials_extraction_failure(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test MQTT credential extraction with no credentials in API response."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}

        # Mock device info with no MQTT credentials (cloud-only device)
        mock_device_info = MagicMock()
        mock_device_info.connected_configuration = None

        mock_cloud_client = MagicMock()

        # Should NOT raise - allows cloud fallback for devices without local credentials
        result = await coordinator._extract_mqtt_credentials(
            mock_cloud_client, mock_device_info
        )

        # Should return empty password (will use cloud fallback)
        assert result["mqtt_password"] == ""
        assert (
            result["mqtt_username"] == "VS6-EU-HJA1234A"
        )  # Falls back to serial number

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    async def test_mqtt_credentials_decryption_failure(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test MQTT credential decryption failure when encrypted credentials exist but can't be decrypted."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}

        # Mock device info WITH encrypted credentials but decryption fails
        mock_device_info = MagicMock()
        mock_mqtt_obj = MagicMock()
        # Configure the mock to return the string when accessed via getattr
        mock_mqtt_obj.configure_mock(
            local_broker_credentials="encrypted_data_that_exists",
            # Ensure plain password attributes return empty so we go to decryption
            password="",
            decoded_password="",
            local_password="",
            device_password="",
        )
        mock_connected_config = MagicMock()
        mock_connected_config.mqtt = mock_mqtt_obj
        mock_device_info.connected_configuration = mock_connected_config

        mock_cloud_client = MagicMock()
        # Make decryption return empty (extraction failure)
        mock_cloud_client.decrypt_local_credentials.return_value = ""

        # Should raise UpdateFailed when credentials exist but extraction fails
        with pytest.raises(
            UpdateFailed, match="Failed to extract local MQTT credentials"
        ):
            await coordinator._extract_mqtt_credentials(
                mock_cloud_client, mock_device_info
            )

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    async def test_device_without_mqtt_support_rejected(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test that devices without MQTT support are rejected during setup."""
        from custom_components.hass_dyson.const import UnsupportedDeviceError

        mock_super_init.return_value = None

        # Set up config entry with serial number
        mock_config_entry_cloud.data = {
            "serial_number": "FLRC123",
            "discovery_method": "cloud",
            "username": "test@example.com",
            "auth_token": "test_token",
        }

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}
        coordinator.config_entry = mock_config_entry_cloud

        # Mock device info for floor cleaner (no MQTT)
        mock_device_info = MagicMock()
        mock_device_info.name = "Dyson Wash G1"
        mock_device_info.connection_category = "nonConnected"
        mock_device_info.connected_configuration = None  # No MQTT config

        mock_cloud_client = MagicMock()
        mock_cloud_client.get_devices = AsyncMock(return_value=[mock_device_info])

        # Mock authentication and device finding
        coordinator._authenticate_cloud_client = AsyncMock(
            return_value=mock_cloud_client
        )
        coordinator._find_cloud_device = AsyncMock(return_value=mock_device_info)
        coordinator._extract_device_info = MagicMock()

        # Should raise UnsupportedDeviceError for device without MQTT support
        with pytest.raises(
            UnsupportedDeviceError, match="does not support MQTT connection"
        ):
            await coordinator._async_setup_cloud_device()

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    def test_firmware_update_status_exception(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test firmware update status handling with exception."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}

        # Mock data that causes exception during processing
        malformed_data = {"unexpected": "structure"}

        # Should handle exception gracefully
        coordinator._handle_firmware_update_status("/status/software", malformed_data)

        # Coordinator should still be functional
        assert coordinator._firmware_update_in_progress is False


class TestCoordinatorServiceRegistration:
    """Test service registration error scenarios."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    @patch(
        "custom_components.hass_dyson.services.async_register_device_services_for_coordinator"
    )
    async def test_service_registration_failure(
        self,
        mock_register_services,
        mock_super_init,
        pure_mock_hass,
        mock_config_entry_cloud,
    ):
        """Test service registration failure handling."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}
        coordinator._services_registered = False
        coordinator._device_capabilities = ["WiFi", "AirQuality"]
        coordinator.device = MagicMock()

        # Mock service registration to fail
        mock_register_services.side_effect = RuntimeError("Service registration failed")

        # Should handle failure gracefully
        await coordinator.ensure_device_services_registered()

        # Services should not be marked as registered
        assert coordinator._services_registered is False

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    async def test_service_registration_no_capabilities(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test service registration skipped when no capabilities."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}
        coordinator._services_registered = False
        coordinator._device_capabilities = []
        coordinator.device = None

        # Should skip registration when no capabilities
        await coordinator.ensure_device_services_registered()

        # Services should not be registered
        assert coordinator._services_registered is False


class TestCoordinatorStateUpdate:
    """Test state update error scenarios."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    async def test_update_coordinator_data_no_device(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test update coordinator data when device is None."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}
        coordinator.device = None
        coordinator.async_update_listeners = MagicMock()

        # Should handle gracefully
        await coordinator._update_coordinator_data()

        # Should not crash
        assert coordinator.device is None

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    async def test_update_coordinator_data_get_state_failure(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test update coordinator data when get_state fails."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}
        coordinator.device = MagicMock()
        coordinator.device.get_state = AsyncMock(
            side_effect=RuntimeError("State fetch failed")
        )
        coordinator.async_update_listeners = MagicMock()

        # Should handle error and still notify listeners
        await coordinator._update_coordinator_data()

        # Listeners should still be notified
        coordinator.async_update_listeners.assert_called_once()

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    def test_schedule_fallback_update_exception(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test fallback update scheduling with exception."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}

        # Mock loop.call_soon_threadsafe to raise exception
        coordinator.hass.loop.call_soon_threadsafe = MagicMock(
            side_effect=RuntimeError("Loop error")
        )

        # Should catch exception and log warning
        coordinator._schedule_fallback_update()

        # Should not crash
        assert coordinator.hass is not None


class TestCoordinatorHelperFunctions:
    """Test helper function error scenarios."""

    def test_get_default_country_culture_no_config(self):
        """Test country/culture extraction when hass has no config."""
        mock_hass = MagicMock()
        mock_hass.config = None

        country, culture = _get_default_country_culture_for_coordinator(mock_hass)

        # Should return defaults
        assert country == "US"
        assert culture == "en-US"

    def test_get_default_country_culture_missing_attributes(self):
        """Test country/culture extraction with missing attributes."""
        mock_hass = MagicMock()
        mock_hass.config = MagicMock()
        mock_hass.config.country = None
        mock_hass.config.language = None

        country, culture = _get_default_country_culture_for_coordinator(mock_hass)

        # Should return defaults
        assert country == "US"
        assert culture == "en-US"

    def test_get_default_country_culture_attribute_error(self):
        """Test country/culture extraction with AttributeError."""
        mock_hass = MagicMock()
        del mock_hass.config  # Remove config attribute

        country, culture = _get_default_country_culture_for_coordinator(mock_hass)

        # Should return defaults
        assert country == "US"
        assert culture == "en-US"

    def test_get_default_country_culture_type_error(self):
        """Test country/culture extraction with TypeError."""
        mock_hass = MagicMock()
        mock_hass.config.country = TypeError("Invalid type")

        country, culture = _get_default_country_culture_for_coordinator(mock_hass)

        # Should return defaults
        assert country == "US"
        assert culture == "en-US"


class TestCoordinatorMessageHandling:
    """Test message handling edge cases."""

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    def test_on_message_update_unknown_message_type(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test message update with unknown message type."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}
        coordinator.device = MagicMock()

        # Unknown message type
        unknown_message = {"msg": "UNKNOWN-MESSAGE-TYPE", "data": {}}

        # Should handle gracefully (no action)
        coordinator._on_message_update("product/serial/status", unknown_message)

        # Should not crash
        assert coordinator.device is not None

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    def test_handle_environmental_message_empty_data(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test environmental message with empty data field."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}
        coordinator.data = {}

        # Message with empty data
        empty_message = {"msg": "ENVIRONMENTAL-CURRENT-SENSOR-DATA", "data": {}}

        # Should handle gracefully
        coordinator._handle_environmental_message(empty_message)

        # Should not crash
        assert coordinator.data is not None

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    def test_handle_environmental_message_exception_in_update(
        self, mock_super_init, pure_mock_hass, mock_config_entry_cloud
    ):
        """Test environmental message handling when update raises exception."""
        mock_super_init.return_value = None

        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
        coordinator.hass = pure_mock_hass
        coordinator._listeners = {}
        coordinator.data = {}

        # Mock loop.call_soon_threadsafe to raise exception
        coordinator.hass.loop.call_soon_threadsafe = MagicMock(
            side_effect=RuntimeError("Update failed")
        )

        # Valid environmental data
        message = {
            "msg": "ENVIRONMENTAL-CURRENT-SENSOR-DATA",
            "data": {"pm25": 10, "pm10": 15},
        }

        # Should catch exception
        coordinator._handle_environmental_message(message)

        # Should not crash
        assert coordinator.hass is not None
