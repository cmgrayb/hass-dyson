"""Comprehensive coordinator tests to improve coverage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.hass_dyson.const import (
    CONF_CREDENTIAL,
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_METHOD,
    CONF_HOSTNAME,
    CONF_MQTT_PREFIX,
    CONF_SERIAL_NUMBER,
    DISCOVERY_CLOUD,
    DISCOVERY_MANUAL,
    DISCOVERY_STICKER,
)
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator


@pytest.fixture
def mock_hass():
    """Mock Home Assistant."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.bus.async_fire = MagicMock()
    hass.loop.call_soon_threadsafe = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    return hass


@pytest.fixture
def mock_config_entry_cloud():
    """Mock cloud config entry."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD,
        CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
        "username": "test@example.com",
        "auth_token": "test_auth_token_123",
    }
    config_entry.entry_id = "test_entry_123"
    return config_entry


@pytest.fixture
def mock_config_entry_manual():
    """Mock manual config entry."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_DISCOVERY_METHOD: DISCOVERY_MANUAL,
        CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
        CONF_HOSTNAME: "192.168.1.100",
        CONF_CREDENTIAL: "device_password",
        CONF_MQTT_PREFIX: "438/VS6-EU-HJA1234A",
        CONF_DEVICE_NAME: "Living Room Fan",
        "device_type": "438",
        "device_category": ["ec"],
        "capabilities": ["environmental_data", "oscillation"],
    }
    return config_entry


@pytest.fixture
def mock_config_entry_sticker():
    """Mock sticker config entry."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
        CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
    }
    return config_entry


class TestDysonDataUpdateCoordinatorBasicProperties:
    """Test coordinator basic properties and initialization."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_hass, mock_config_entry_cloud):
        """Test coordinator initialization."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        assert coordinator.config_entry == mock_config_entry_cloud
        assert coordinator.device is None
        assert coordinator.device_capabilities == []
        assert coordinator.device_category == []
        assert coordinator.device_type == ""
        assert coordinator.firmware_version == "Unknown"
        assert coordinator.firmware_auto_update_enabled is False
        assert coordinator.firmware_latest_version is None
        assert coordinator.firmware_update_in_progress is False

    @pytest.mark.asyncio
    async def test_serial_number_from_config(self, mock_hass, mock_config_entry_cloud):
        """Test serial number property from config entry."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        assert coordinator.serial_number == "VS6-EU-HJA1234A"

    @pytest.mark.asyncio
    async def test_serial_number_fallback(self, mock_hass):
        """Test serial number fallback behavior."""
        config_entry = MagicMock()
        config_entry.data = {CONF_SERIAL_NUMBER: "FALLBACK123"}

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.config_entry = config_entry

        assert coordinator.serial_number == "FALLBACK123"

    @pytest.mark.asyncio
    async def test_device_name_from_config(self, mock_hass, mock_config_entry_manual):
        """Test device name from config entry."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_manual)

        assert coordinator.device_name == "Living Room Fan"

    @pytest.mark.asyncio
    async def test_device_name_fallback(self, mock_hass, mock_config_entry_cloud):
        """Test device name fallback to serial number."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        assert coordinator.device_name == "Dyson VS6-EU-HJA1234A"

    @pytest.mark.asyncio
    async def test_firmware_auto_update_enabled_property(self, mock_hass, mock_config_entry_cloud):
        """Test firmware auto update enabled property."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
            coordinator._firmware_auto_update_enabled = True

        assert coordinator.firmware_auto_update_enabled is True


class TestDysonDataUpdateCoordinatorConnectionType:
    """Test connection type logic."""

    @pytest.mark.asyncio
    async def test_get_effective_connection_type_device_specific(self, mock_hass, mock_config_entry_cloud):
        """Test getting device-specific connection type."""
        mock_config_entry_cloud.data["connection_type"] = "cloud_only"

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        connection_type = coordinator._get_effective_connection_type()
        assert connection_type == "cloud_only"

    @pytest.mark.asyncio
    async def test_get_effective_connection_type_from_parent(self, mock_hass, mock_config_entry_cloud):
        """Test getting connection type from parent account entry."""
        mock_config_entry_cloud.data["parent_entry_id"] = "parent_123"

        # Mock parent account entry
        parent_entry = MagicMock()
        parent_entry.entry_id = "parent_123"
        parent_entry.data = {"connection_type": "local_cloud_fallback"}

        mock_hass.config_entries.async_entries.return_value = [parent_entry]

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        connection_type = coordinator._get_effective_connection_type()
        assert connection_type == "local_cloud_fallback"

    @pytest.mark.asyncio
    async def test_get_effective_connection_type_default(self, mock_hass, mock_config_entry_cloud):
        """Test default connection type fallback."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        connection_type = coordinator._get_effective_connection_type()
        assert connection_type == "local_cloud_fallback"

    @pytest.mark.asyncio
    async def test_get_effective_connection_type_exception_handling(self, mock_hass, mock_config_entry_cloud):
        """Test exception handling in connection type retrieval."""
        mock_config_entry_cloud.data["parent_entry_id"] = "parent_123"
        mock_hass.config_entries.async_entries.side_effect = Exception("Config error")

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        connection_type = coordinator._get_effective_connection_type()
        assert connection_type == "local_cloud_fallback"


class TestDysonDataUpdateCoordinatorDeviceSetup:
    """Test device setup methods."""

    @pytest.mark.asyncio
    async def test_async_setup_device_cloud(self, mock_hass, mock_config_entry_cloud):
        """Test async setup device with cloud discovery."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        with patch.object(coordinator, "_async_setup_cloud_device") as mock_setup_cloud:
            await coordinator._async_setup_device()
            mock_setup_cloud.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_setup_device_manual(self, mock_hass, mock_config_entry_manual):
        """Test async setup device with manual discovery."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_manual)

        with patch.object(coordinator, "_async_setup_manual_device") as mock_setup_manual:
            await coordinator._async_setup_device()
            mock_setup_manual.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_setup_device_sticker_raises_error(self, mock_hass, mock_config_entry_sticker):
        """Test async setup device with sticker discovery raises error."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_sticker)

        with pytest.raises(UpdateFailed, match="Sticker discovery method temporarily disabled"):
            await coordinator._async_setup_device()

    @pytest.mark.asyncio
    async def test_async_setup_device_unknown_method(self, mock_hass):
        """Test async setup device with unknown discovery method."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_DISCOVERY_METHOD: "unknown_method",
            CONF_SERIAL_NUMBER: "TEST-SERIAL-123",  # Add required serial number
        }

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.config_entry = config_entry

        with pytest.raises(UpdateFailed, match="Unknown discovery method: unknown_method"):
            await coordinator._async_setup_device()


class TestDysonDataUpdateCoordinatorCloudAuth:
    """Test cloud authentication methods."""

    @pytest.mark.asyncio
    async def test_authenticate_cloud_client_with_auth_token(self, mock_hass, mock_config_entry_cloud):
        """Test cloud authentication with auth token."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_cloud

        mock_client = MagicMock()

        with patch("libdyson_rest.AsyncDysonClient") as mock_client_class:
            mock_client_class.return_value = mock_client
            mock_hass.async_add_executor_job.return_value = mock_client

            result = await coordinator._authenticate_cloud_client()

            assert result == mock_client
            mock_hass.async_add_executor_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_cloud_client_with_username_password(self, mock_hass):
        """Test cloud authentication with username and password."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
            "username": "test@example.com",
            "password": "testpass123",
        }

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = config_entry

        mock_client = MagicMock()
        mock_challenge = MagicMock()
        mock_challenge.challenge_id = "test_challenge_123"
        mock_user_status = MagicMock()
        mock_user_status.account_status.value = "active"

        mock_client.provision = AsyncMock()
        mock_client.get_user_status = AsyncMock(return_value=mock_user_status)
        mock_client.begin_login = AsyncMock(return_value=mock_challenge)
        mock_client.complete_login = AsyncMock()
        mock_client.close = AsyncMock()

        with patch("libdyson_rest.AsyncDysonClient") as mock_client_class:
            mock_client_class.return_value = mock_client
            mock_hass.async_add_executor_job.return_value = mock_client

            result = await coordinator._authenticate_cloud_client()

            assert result == mock_client
            mock_client.provision.assert_called_once()
            mock_client.get_user_status.assert_called_once()
            mock_client.begin_login.assert_called_once()
            mock_client.complete_login.assert_called_once_with(
                "test_challenge_123", "", "test@example.com", "testpass123"
            )

    @pytest.mark.asyncio
    async def test_authenticate_cloud_client_missing_credentials(self, mock_hass):
        """Test cloud authentication with missing credentials."""
        config_entry = MagicMock()
        config_entry.data = {CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A"}

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = config_entry

        with pytest.raises(UpdateFailed, match="Missing cloud credentials"):
            await coordinator._authenticate_cloud_client()

    @pytest.mark.asyncio
    async def test_authenticate_cloud_client_auth_failure(self, mock_hass):
        """Test cloud authentication failure handling."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
            "username": "test@example.com",
            "password": "wrong_password",
        }

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = config_entry

        mock_client = MagicMock()
        mock_client.provision = AsyncMock(side_effect=Exception("Auth failed"))
        mock_client.close = AsyncMock()

        with patch("libdyson_rest.AsyncDysonClient") as mock_client_class:
            mock_client_class.return_value = mock_client
            mock_hass.async_add_executor_job.return_value = mock_client

            with pytest.raises(UpdateFailed, match="Cloud authentication failed"):
                await coordinator._authenticate_cloud_client()

            mock_client.close.assert_called_once()


class TestDysonDataUpdateCoordinatorCloudDeviceDiscovery:
    """Test cloud device discovery methods."""

    @pytest.mark.asyncio
    async def test_find_cloud_device_success(self, mock_hass, mock_config_entry_cloud):
        """Test successful cloud device discovery."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        mock_device_info = MagicMock()
        mock_device_info.serial_number = "VS6-EU-HJA1234A"

        mock_other_device = MagicMock()
        mock_other_device.serial_number = "OTHER123"

        mock_cloud_client = MagicMock()
        mock_cloud_client.get_devices = AsyncMock(return_value=[mock_other_device, mock_device_info])

        result = await coordinator._find_cloud_device(mock_cloud_client)

        assert result == mock_device_info

    @pytest.mark.asyncio
    async def test_find_cloud_device_not_found(self, mock_hass, mock_config_entry_cloud):
        """Test cloud device not found."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        mock_other_device = MagicMock()
        mock_other_device.serial_number = "OTHER123"

        mock_cloud_client = MagicMock()
        mock_cloud_client.get_devices = AsyncMock(return_value=[mock_other_device])

        with pytest.raises(UpdateFailed, match="Device VS6-EU-HJA1234A not found in cloud account"):
            await coordinator._find_cloud_device(mock_cloud_client)


class TestDysonDataUpdateCoordinatorManualSetup:
    """Test manual device setup methods."""

    @pytest.mark.asyncio
    async def test_async_setup_manual_device_success(self, mock_hass, mock_config_entry_manual):
        """Test successful manual device setup."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_manual)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_manual
            # Initialize device attributes
            coordinator._device_type = ""
            coordinator._device_category = []
            coordinator._device_capabilities = []
            coordinator.device = None

        mock_device = MagicMock()
        mock_device.connect = AsyncMock(return_value=True)
        mock_device.set_firmware_version = MagicMock()
        mock_device.add_environmental_callback = MagicMock()
        mock_device.add_message_callback = MagicMock()

        with patch("custom_components.hass_dyson.coordinator.DysonDevice") as mock_device_class:
            mock_device_class.return_value = mock_device

            await coordinator._async_setup_manual_device()

            assert coordinator.device == mock_device
            assert coordinator.device_type == "438"
            assert coordinator.device_category == ["ec"]
            assert coordinator.device_capabilities == ["environmental_data", "oscillation"]

            mock_device.connect.assert_called_once()
            mock_device.set_firmware_version.assert_called_once_with("Unknown")
            mock_device.add_environmental_callback.assert_called_once()
            mock_device.add_message_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_setup_manual_device_missing_hostname(self, mock_hass):
        """Test manual device setup with missing hostname."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_DISCOVERY_METHOD: DISCOVERY_MANUAL,
            CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
            CONF_CREDENTIAL: "device_password",
            CONF_MQTT_PREFIX: "438/VS6-EU-HJA1234A",
        }

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, config_entry)

        with pytest.raises(UpdateFailed, match="Manual device setup requires hostname"):
            await coordinator._async_setup_manual_device()

    @pytest.mark.asyncio
    async def test_async_setup_manual_device_connection_failure(self, mock_hass, mock_config_entry_manual):
        """Test manual device setup with connection failure."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_manual)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_manual

        mock_device = MagicMock()
        mock_device.connect = AsyncMock(return_value=False)

        with patch("custom_components.hass_dyson.device.DysonDevice") as mock_device_class:
            mock_device_class.return_value = mock_device

            with pytest.raises(UpdateFailed, match="Failed to connect to manual device VS6-EU-HJA1234A"):
                await coordinator._async_setup_manual_device()


class TestDysonDataUpdateCoordinatorCallbacks:
    """Test coordinator callback methods."""

    @pytest.mark.asyncio
    async def test_on_environmental_update(self, mock_hass, mock_config_entry_cloud):
        """Test environmental update callback."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_cloud

        mock_device = MagicMock()
        mock_device._environmental_data = {"pm25": 10, "pm10": 15}
        coordinator.device = mock_device

        coordinator._on_environmental_update()

        # Should not raise any errors and complete successfully

    @pytest.mark.asyncio
    async def test_on_environmental_update_no_device(self, mock_hass, mock_config_entry_cloud):
        """Test environmental update callback with no device."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_cloud

        coordinator.device = None
        coordinator._on_environmental_update()

        # Should not raise any errors and complete successfully

    @pytest.mark.asyncio
    async def test_schedule_listener_update(self, mock_hass, mock_config_entry_cloud):
        """Test schedule listener update method."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_cloud
            coordinator.async_update_listeners = MagicMock()

        coordinator._schedule_listener_update()

        mock_hass.loop.call_soon_threadsafe.assert_called_once_with(coordinator.async_update_listeners)


class TestDysonDataUpdateCoordinatorFirstRefresh:
    """Test first refresh and setup methods."""

    @pytest.mark.asyncio
    async def test_async_config_entry_first_refresh_success(self, mock_hass, mock_config_entry_cloud):
        """Test successful first refresh."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        with patch.object(coordinator, "_async_setup_device") as mock_setup_device:
            with patch(
                "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.async_config_entry_first_refresh"
            ) as mock_super_refresh:
                mock_setup_device.return_value = None
                mock_super_refresh.return_value = None

                await coordinator.async_config_entry_first_refresh()

                mock_setup_device.assert_called_once()
                mock_super_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_config_entry_first_refresh_failure(self, mock_hass, mock_config_entry_cloud):
        """Test first refresh failure."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        with patch.object(coordinator, "_async_setup_device") as mock_setup_device:
            mock_setup_device.side_effect = Exception("Setup failed")

            with pytest.raises(Exception, match="Setup failed"):
                await coordinator.async_config_entry_first_refresh()


class TestDysonDataUpdateCoordinatorUpdate:
    """Test coordinator update methods."""

    @pytest.mark.asyncio
    async def test_update_coordinator_data_success(self, mock_hass, mock_config_entry_cloud):
        """Test successful coordinator data update."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_cloud
            coordinator._listeners = {}

        mock_device = MagicMock()
        mock_device.get_state = AsyncMock(return_value={"mock": "data"})
        coordinator.device = mock_device

        result = await coordinator._async_update_data()

        assert result == {"mock": "data"}

    @pytest.mark.asyncio
    async def test_update_coordinator_data_no_device(self, mock_hass, mock_config_entry_cloud):
        """Test coordinator data update with no device."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_cloud
            coordinator._listeners = {}

        coordinator.device = None

        # Should raise UpdateFailed when no device
        with pytest.raises(UpdateFailed, match="Device not initialized"):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_update_coordinator_data_exception(self, mock_hass, mock_config_entry_cloud):
        """Test coordinator data update with exception."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_cloud
            coordinator._listeners = {}

        mock_device = MagicMock()
        mock_device.get_state = AsyncMock(side_effect=Exception("Device error"))
        mock_device.is_connected = True  # Ensure we skip reconnection logic
        coordinator.device = mock_device

        with pytest.raises(UpdateFailed, match="Error communicating with device"):
            await coordinator._async_update_data()


class TestDysonDataUpdateCoordinatorMessageHandling:
    """Test message handling methods."""

    @pytest.mark.asyncio
    async def test_on_message_update_state_change(self, mock_hass, mock_config_entry_cloud):
        """Test message update for state change."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
            coordinator._schedule_listener_update = MagicMock()

        coordinator._on_message_update("test/topic", {"msg": "STATE-CHANGE", "data": "test"})

        coordinator._schedule_listener_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_update_non_state_change(self, mock_hass, mock_config_entry_cloud):
        """Test message update for non-state change."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
            coordinator._schedule_listener_update = MagicMock()

        coordinator._on_message_update("test/topic", {"msg": "ENVIRONMENTAL-CURRENT-SENSOR-DATA", "data": "test"})

        coordinator._schedule_listener_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_state_change_message_success(self, mock_hass, mock_config_entry_cloud):
        """Test successful state change message handling."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        mock_device = MagicMock()
        coordinator.device = mock_device

        coordinator._handle_state_change_message()

        # Should complete without errors

    @pytest.mark.asyncio
    async def test_handle_state_change_message_no_device(self, mock_hass, mock_config_entry_cloud):
        """Test state change message handling with no device."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        coordinator.device = None
        coordinator._handle_state_change_message()

        # Should complete without errors

    @pytest.mark.asyncio
    async def test_handle_state_change_message_exception(self, mock_hass, mock_config_entry_cloud):
        """Test state change message handling with exception."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        mock_device = MagicMock()
        mock_device.handle_state_change.side_effect = Exception("Device error")
        coordinator.device = mock_device

        # Should not raise exception but handle it gracefully
        coordinator._handle_state_change_message()


class TestDysonDataUpdateCoordinatorScheduling:
    """Test coordinator scheduling methods."""

    @pytest.mark.asyncio
    async def test_schedule_coordinator_data_update(self, mock_hass, mock_config_entry_cloud):
        """Test scheduling coordinator data update."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_cloud

            # Mock the loop.call_soon_threadsafe method
            mock_hass.loop = MagicMock()
            mock_hass.loop.call_soon_threadsafe = MagicMock()

        coordinator._schedule_coordinator_data_update()

        # Verify that call_soon_threadsafe was called with the correct method
        mock_hass.loop.call_soon_threadsafe.assert_called_once_with(coordinator._create_coordinator_update_task)

    @pytest.mark.asyncio
    async def test_create_coordinator_update_task(self, mock_hass, mock_config_entry_cloud):
        """Test creating coordinator update task."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_cloud

            # Mock async_create_task method
            mock_hass.async_create_task = MagicMock()

        coordinator._create_coordinator_update_task()

        # Verify that async_create_task was called
        mock_hass.async_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_fallback_update(self, mock_hass, mock_config_entry_cloud):
        """Test scheduling fallback update."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        with patch("asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None
            coordinator._schedule_fallback_update()
            # Should complete without errors

    @pytest.mark.asyncio
    async def test_schedule_fallback_update_exception(self, mock_hass, mock_config_entry_cloud):
        """Test fallback update with exception."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)

        with patch("asyncio.sleep") as mock_sleep:
            mock_sleep.side_effect = Exception("Sleep error")
            coordinator._schedule_fallback_update()
            # Should handle exception gracefully
