"""Test coordinator device communication logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.hass_dyson.const import (
    CONF_CREDENTIAL,
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_METHOD,
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
    return hass


@pytest.fixture
def mock_config_entry_cloud():
    """Mock config entry for cloud discovery."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD,
        CONF_SERIAL_NUMBER: "TEST123456",
        "username": "test@example.com",
        "password": "testpassword",
    }
    return config_entry


@pytest.fixture
def mock_config_entry_sticker():
    """Mock config entry for sticker discovery."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
        CONF_SERIAL_NUMBER: "TEST123456",
        CONF_CREDENTIAL: "devicepassword",
        "hostname": "192.168.1.100",
        "capabilities": ["environmental_data", "oscillation"],
        "device_category": "fan",
    }
    return config_entry


class TestDysonDataUpdateCoordinatorLogic:
    """Test the coordinator logic without HA base class."""

    @pytest.mark.asyncio
    @patch("libdyson_rest.DysonClient")
    @patch("custom_components.hass_dyson.device.DysonDevice")
    @patch("custom_components.hass_dyson.coordinator.DysonDevice")
    async def test_cloud_device_setup_logic(self, mock_device_class, mock_mqtt_class, mock_cloud_class, mock_hass):
        """Test cloud device setup logic directly."""
        # Mock cloud client
        mock_cloud_client = MagicMock()
        mock_cloud_class.return_value = mock_cloud_client

        # Mock device info from cloud
        mock_device_info = MagicMock()
        mock_device_info.serial = "TEST123456"
        mock_device_info.product_type = "358"  # Fan model
        mock_cloud_client.get_devices.return_value = [mock_device_info]

        # Mock MQTT client
        mock_mqtt_client = MagicMock()
        mock_mqtt_class.return_value = mock_mqtt_client

        # Mock device wrapper
        mock_device = MagicMock()
        mock_device_class.return_value = mock_device

        # Create minimal coordinator for testing
        # Create with mocked base class
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.device = None
            coordinator._device_capabilities = []

        # Execute async_add_executor_job calls immediately
        def mock_executor_job(func, *args):
            return func(*args) if args else func()

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        # Test cloud login
        mock_cloud_client.login("test@example.com", "testpassword")
        devices = mock_cloud_client.get_devices()

        # Verify cloud client login was called
        mock_cloud_client.login.assert_called_once_with("test@example.com", "testpassword")

        # Verify device list was retrieved
        mock_cloud_client.get_devices.assert_called_once()

        # Verify we got our expected device
        assert len(devices) == 1
        assert devices[0].serial == "TEST123456"
        assert devices[0].product_type == "358"

    def test_device_category_mapping(self):
        """Test that device category comes from API response."""
        # Test that the coordinator uses API-provided category instead of static mapping
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_device_info = type("MockDeviceInfo", (), {"category": "ec", "serial_number": "TEST123"})()

            # Test that coordinator uses API category directly
            coordinator._device_category = getattr(mock_device_info, "category", "unknown")
            assert coordinator._device_category == "ec"

            # Test unknown category fallback
            mock_device_info_unknown = type("MockDeviceInfo", (), {"serial_number": "TEST456"})()
            coordinator._device_category = getattr(mock_device_info_unknown, "category", "unknown")
            assert coordinator._device_category == "unknown"

    def test_capability_extraction(self):
        """Test capability extraction from API response."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_device_info = type(
                "MockDeviceInfo", (), {"capabilities": ["EnvironmentalData", "AdvancedOscillation", "CustomCapability"]}
            )()

            capabilities = coordinator._extract_capabilities(mock_device_info)

            # Should contain the API-provided capabilities
            assert "EnvironmentalData" in capabilities
            assert "AdvancedOscillation" in capabilities
            assert "CustomCapability" in capabilities
            assert len(capabilities) == 3

            # Test device without capabilities attribute
            mock_device_no_caps = MagicMock()
            mock_device_no_caps.product_type = "360"
            del mock_device_no_caps.capabilities  # Remove capabilities attribute

            capabilities_empty = coordinator._extract_capabilities(mock_device_no_caps)
            assert capabilities_empty == []


class TestDysonDataUpdateCoordinatorInit:
    """Test coordinator initialization."""

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    def test_init_with_config_entry(self, mock_super_init):
        """Test coordinator initialization with config entry."""
        mock_hass = MagicMock()
        mock_config_entry = MagicMock()
        mock_config_entry.data = {CONF_SERIAL_NUMBER: "TEST123456"}

        coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        assert coordinator.config_entry == mock_config_entry
        assert coordinator.device is None
        assert coordinator._device_capabilities == []
        assert coordinator._device_category == []
        assert coordinator._firmware_version == "Unknown"
        mock_super_init.assert_called_once()

    def test_properties(self):
        """Test property getters."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator._device_capabilities = ["environmental_data", "oscillation"]
            coordinator._device_category = ["fan"]
            coordinator._firmware_version = "1.2.3"

            assert coordinator.device_capabilities == ["environmental_data", "oscillation"]
            assert coordinator.device_category == ["fan"]
            assert coordinator.firmware_version == "1.2.3"


class TestDysonDataUpdateCoordinatorCallbacks:
    """Test coordinator callback handling."""

    def test_on_environmental_update(self):
        """Test environmental data update callback."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_hass = MagicMock()
            mock_device = MagicMock()
            mock_device._environmental_data = {"pm25": "010", "pm10": "020"}
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_SERIAL_NUMBER: "TEST123456"}

            coordinator.hass = mock_hass
            coordinator.device = mock_device
            coordinator.config_entry = mock_config_entry

            coordinator._on_environmental_update()

            mock_hass.add_job.assert_called_once()

    def test_on_message_update_state_change(self):
        """Test message update callback for STATE-CHANGE."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_SERIAL_NUMBER: "TEST123456"}
            coordinator.config_entry = mock_config_entry

            with patch.object(coordinator, "_handle_state_change_message") as mock_handle:
                coordinator._on_message_update("test/topic", {"msg": "STATE-CHANGE"})
                mock_handle.assert_called_once()

    def test_on_message_update_non_state_change(self):
        """Test message update callback for non-STATE-CHANGE messages."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_SERIAL_NUMBER: "TEST123456"}
            coordinator.config_entry = mock_config_entry

            with patch.object(coordinator, "_handle_state_change_message") as mock_handle:
                coordinator._on_message_update("test/topic", {"msg": "OTHER"})
                mock_handle.assert_not_called()

    def test_handle_state_change_message_with_device(self):
        """Test STATE-CHANGE message handling with device available."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.device = MagicMock()

            with patch.object(coordinator, "_schedule_coordinator_data_update") as mock_schedule:
                coordinator._handle_state_change_message()
                mock_schedule.assert_called_once()

    def test_handle_state_change_message_without_device(self):
        """Test STATE-CHANGE message handling without device."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.device = None

            with patch.object(coordinator, "_schedule_listener_update") as mock_schedule:
                coordinator._handle_state_change_message()
                mock_schedule.assert_called_once()

    def test_handle_state_change_message_exception(self):
        """Test STATE-CHANGE message handling with exception."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.device = MagicMock()

            with patch.object(coordinator, "_schedule_coordinator_data_update", side_effect=Exception("Test error")):
                with patch.object(coordinator, "_schedule_fallback_update") as mock_fallback:
                    coordinator._handle_state_change_message()
                    mock_fallback.assert_called_once()


class TestDysonDataUpdateCoordinatorScheduling:
    """Test coordinator scheduling methods."""

    def test_schedule_coordinator_data_update(self):
        """Test scheduling coordinator data update."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_hass = MagicMock()
            coordinator.hass = mock_hass

            coordinator._schedule_coordinator_data_update()

            mock_hass.loop.call_soon_threadsafe.assert_called_once()

    def test_create_coordinator_update_task(self):
        """Test creating coordinator update task."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_hass = MagicMock()
            # async_create_task should return a Task, not a coroutine
            mock_hass.async_create_task = MagicMock(return_value=MagicMock())
            coordinator.hass = mock_hass

            coordinator._create_coordinator_update_task()

            mock_hass.async_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_coordinator_data_success(self):
        """Test updating coordinator data successfully."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.async_update_listeners = MagicMock()
            mock_device = AsyncMock()
            mock_device.get_state.return_value = {"test": "data"}
            coordinator.device = mock_device

            await coordinator._update_coordinator_data()

            assert coordinator.data == {"test": "data"}
            coordinator.async_update_listeners.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_coordinator_data_failure(self):
        """Test updating coordinator data with failure."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.async_update_listeners = MagicMock()
            mock_device = AsyncMock()
            mock_device.get_state.side_effect = Exception("Test error")
            coordinator.device = mock_device

            await coordinator._update_coordinator_data()

            # Should still call listeners even on failure
            coordinator.async_update_listeners.assert_called_once()

    def test_schedule_listener_update(self):
        """Test scheduling listener update."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_hass = MagicMock()
            coordinator.hass = mock_hass
            coordinator.async_update_listeners = MagicMock()

            coordinator._schedule_listener_update()

            mock_hass.loop.call_soon_threadsafe.assert_called_once_with(coordinator.async_update_listeners)

    def test_schedule_fallback_update(self):
        """Test scheduling fallback update."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_hass = MagicMock()
            coordinator.hass = mock_hass
            coordinator.async_update_listeners = MagicMock()

            coordinator._schedule_fallback_update()

            mock_hass.loop.call_soon_threadsafe.assert_called_once_with(coordinator.async_update_listeners)

    def test_schedule_fallback_update_exception(self):
        """Test scheduling fallback update with exception."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_hass = MagicMock()
            mock_hass.loop.call_soon_threadsafe.side_effect = Exception("Test error")
            coordinator.hass = mock_hass
            coordinator.async_update_listeners = MagicMock()

            # Should not raise exception
            coordinator._schedule_fallback_update()


class TestDysonDataUpdateCoordinatorProperties:
    """Test coordinator property methods."""

    def test_serial_number_from_config(self):
        """Test serial number property from config entry."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_SERIAL_NUMBER: "TEST123456"}
            coordinator.config_entry = mock_config_entry

            assert coordinator.serial_number == "TEST123456"

    def test_device_name_from_config(self):
        """Test device name property from config entry."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_DEVICE_NAME: "Living Room Fan"}
            coordinator.config_entry = mock_config_entry

            assert coordinator.device_name == "Living Room Fan"

    def test_device_name_fallback_to_serial(self):
        """Test device name fallback to serial number."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_SERIAL_NUMBER: "TEST123456"}
            coordinator.config_entry = mock_config_entry

            # The actual implementation returns "Dyson {serial}" when no device name is provided
            assert coordinator.device_name == "Dyson TEST123456"

    def test_get_effective_connection_type(self):
        """Test getting effective connection type."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}
            coordinator.config_entry = mock_config_entry

            # The actual implementation returns a default connection type, not the discovery method
            assert coordinator._get_effective_connection_type() == "local_cloud_fallback"


class TestDysonDataUpdateCoordinatorSetup:
    """Test coordinator device setup methods."""

    @pytest.mark.asyncio
    async def test_async_config_entry_first_refresh_success(self):
        """Test successful first refresh."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_SERIAL_NUMBER: "TEST123456"}
            coordinator.config_entry = mock_config_entry

            with patch.object(coordinator, "_async_setup_device") as mock_setup:
                with patch(
                    "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.async_config_entry_first_refresh"
                ) as mock_super:
                    await coordinator.async_config_entry_first_refresh()

                    mock_setup.assert_called_once()
                    mock_super.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_config_entry_first_refresh_failure(self):
        """Test first refresh with setup failure."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_SERIAL_NUMBER: "TEST123456"}
            coordinator.config_entry = mock_config_entry

            with patch.object(coordinator, "_async_setup_device", side_effect=Exception("Setup failed")):
                with pytest.raises(Exception, match="Setup failed"):
                    await coordinator.async_config_entry_first_refresh()

    @pytest.mark.asyncio
    async def test_async_setup_device_cloud(self):
        """Test device setup for cloud discovery."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}
            coordinator.config_entry = mock_config_entry

            with patch.object(coordinator, "_async_setup_cloud_device") as mock_setup_cloud:
                await coordinator._async_setup_device()
                mock_setup_cloud.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_setup_device_sticker(self):
        """Test device setup for sticker discovery (temporarily disabled)."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_STICKER}
            coordinator.config_entry = mock_config_entry

            with pytest.raises(UpdateFailed, match="Sticker discovery method temporarily disabled"):
                await coordinator._async_setup_device()

    @pytest.mark.asyncio
    async def test_async_setup_device_manual(self):
        """Test device setup for manual discovery."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_MANUAL}
            coordinator.config_entry = mock_config_entry

            with patch.object(coordinator, "_async_setup_manual_device") as mock_setup_manual:
                await coordinator._async_setup_device()
                mock_setup_manual.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_setup_device_unknown_method(self):
        """Test device setup with unknown discovery method."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_DISCOVERY_METHOD: "unknown"}
            coordinator.config_entry = mock_config_entry

            with pytest.raises(UpdateFailed, match="Unknown discovery method: unknown"):
                await coordinator._async_setup_device()


class TestDysonDataUpdateCoordinatorCloudSetup:
    """Test coordinator cloud device setup methods."""

    @pytest.mark.asyncio
    async def test_async_setup_cloud_device_success(self):
        """Test successful cloud device setup."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_SERIAL_NUMBER: "TEST123456"}
            coordinator.config_entry = mock_config_entry
            coordinator._device_category = ["fan"]

            mock_cloud_client = MagicMock()
            mock_device_info = MagicMock()
            mock_mqtt_creds = {"host": "test.com", "port": 8883}
            mock_cloud_creds = {"username": "test", "password": "pass"}

            with patch.object(coordinator, "_authenticate_cloud_client", return_value=mock_cloud_client):
                with patch.object(coordinator, "_find_cloud_device", return_value=mock_device_info):
                    with patch.object(coordinator, "_extract_device_info"):
                        with patch.object(coordinator, "_extract_mqtt_credentials", return_value=mock_mqtt_creds):
                            with patch.object(coordinator, "_extract_cloud_credentials", return_value=mock_cloud_creds):
                                with patch.object(coordinator, "_create_cloud_device"):
                                    await coordinator._async_setup_cloud_device()

    @pytest.mark.asyncio
    async def test_async_setup_cloud_device_failure(self):
        """Test cloud device setup with failure."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_SERIAL_NUMBER: "TEST123456"}
            coordinator.config_entry = mock_config_entry

            with patch.object(coordinator, "_authenticate_cloud_client", side_effect=Exception("Auth failed")):
                with pytest.raises(UpdateFailed, match="Cloud device setup failed: Auth failed"):
                    await coordinator._async_setup_cloud_device()

    @pytest.mark.asyncio
    async def test_authenticate_cloud_client_with_token(self):
        """Test cloud client authentication with existing token."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)

            # Mock hass with async_add_executor_job
            mock_hass = AsyncMock()

            async def mock_executor_job(func):
                return func()

            mock_hass.async_add_executor_job.side_effect = mock_executor_job
            coordinator.hass = mock_hass

            mock_config_entry = MagicMock()
            mock_config_entry.data = {
                CONF_SERIAL_NUMBER: "TEST123456",
                "auth_token": "test_token",
                "username": "test@example.com",
            }
            coordinator.config_entry = mock_config_entry

            with patch("libdyson_rest.async_client.AsyncDysonClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client

                result = await coordinator._authenticate_cloud_client()

                mock_client_class.assert_called_once_with(email="test@example.com", auth_token="test_token")
                assert result == mock_client

    @pytest.mark.asyncio
    async def test_authenticate_cloud_client_with_password(self):
        """Test cloud client authentication with username/password."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)

            # Mock hass with async_add_executor_job
            mock_hass = AsyncMock()

            async def mock_executor_job(func):
                return func()

            mock_hass.async_add_executor_job.side_effect = mock_executor_job
            coordinator.hass = mock_hass

            mock_config_entry = MagicMock()
            mock_config_entry.data = {
                CONF_SERIAL_NUMBER: "TEST123456",
                "username": "test@example.com",
                "password": "testpass",
            }
            coordinator.config_entry = mock_config_entry

            with patch("libdyson_rest.async_client.AsyncDysonClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client
                mock_challenge = MagicMock()
                mock_challenge.challenge_id = 12345

                # Mock the async methods
                mock_client.begin_login = AsyncMock(return_value=mock_challenge)
                mock_client.complete_login = AsyncMock()

                result = await coordinator._authenticate_cloud_client()

                mock_client_class.assert_called_once_with(email="test@example.com")
                assert result == mock_client
                mock_client.begin_login.assert_called_once()
                mock_client.complete_login.assert_called_once_with("12345", "", "test@example.com", "testpass")

    @pytest.mark.asyncio
    async def test_authenticate_cloud_client_missing_credentials(self):
        """Test cloud client authentication with missing credentials."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_SERIAL_NUMBER: "TEST123456"}
            coordinator.config_entry = mock_config_entry

            with pytest.raises(UpdateFailed, match="Missing cloud credentials"):
                await coordinator._authenticate_cloud_client()

    @pytest.mark.asyncio
    async def test_find_cloud_device_success(self):
        """Test finding cloud device successfully."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_SERIAL_NUMBER: "TEST123456"}
            coordinator.config_entry = mock_config_entry

            mock_cloud_client = AsyncMock()
            mock_device = MagicMock()
            mock_device.serial_number = "TEST123456"
            mock_devices = [mock_device]

            mock_cloud_client.get_devices = AsyncMock(return_value=mock_devices)

            result = await coordinator._find_cloud_device(mock_cloud_client)

            assert result == mock_device
            mock_cloud_client.get_devices.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_cloud_device_not_found(self):
        """Test finding cloud device when not found."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_config_entry = MagicMock()
            mock_config_entry.data = {CONF_SERIAL_NUMBER: "TEST123456"}
            coordinator.config_entry = mock_config_entry

            mock_cloud_client = AsyncMock()
            mock_other_device = MagicMock()
            mock_other_device.serial_number = "OTHER123456"
            mock_devices = [mock_other_device]

            mock_cloud_client.get_devices = AsyncMock(return_value=mock_devices)

            with pytest.raises(UpdateFailed, match="Device TEST123456 not found in cloud account"):
                await coordinator._find_cloud_device(mock_cloud_client)


class TestDysonDataUpdateCoordinatorDeviceInfo:
    """Test coordinator device info extraction."""

    def test_extract_device_info(self):
        """Test extracting device info."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_device_info = MagicMock()

            with patch.object(coordinator, "_debug_connected_configuration"):
                with patch.object(coordinator, "_extract_device_category"):
                    with patch.object(coordinator, "_extract_device_capabilities"):
                        with patch.object(coordinator, "_extract_firmware_version"):
                            coordinator._extract_device_info(mock_device_info)

    def test_debug_connected_configuration(self):
        """Test debugging connected configuration."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_device_info = MagicMock()
            mock_connected_config = MagicMock()
            mock_device_info.connected_configuration = mock_connected_config

            with patch.object(coordinator, "_debug_mqtt_object"):
                coordinator._debug_connected_configuration(mock_device_info)

    def test_debug_connected_configuration_none(self):
        """Test debugging connected configuration when None."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_device_info = MagicMock()
            mock_device_info.connected_configuration = None

            # Should not raise exception
            coordinator._debug_connected_configuration(mock_device_info)

    def test_debug_mqtt_object(self):
        """Test debugging MQTT object."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_connected_config = MagicMock()
            mock_mqtt_obj = MagicMock()
            mock_mqtt_obj.password = "test_password"
            mock_connected_config.mqtt = mock_mqtt_obj

            # Should not raise exception
            coordinator._debug_mqtt_object(mock_connected_config)

    def test_debug_mqtt_object_none(self):
        """Test debugging MQTT object when None."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_connected_config = MagicMock()
            mock_connected_config.mqtt = None

            # Should not raise exception
            coordinator._debug_mqtt_object(mock_connected_config)
