"""Tests for the Dyson firmware update functionality."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components.update import UpdateEntityFeature
from homeassistant.core import HomeAssistant

from custom_components.hass_dyson.const import DISCOVERY_CLOUD, DISCOVERY_MANUAL, DOMAIN
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
from custom_components.hass_dyson.update import DysonFirmwareUpdateEntity, async_setup_entry


class TestDysonFirmwareUpdateEntity:
    """Test the DysonFirmwareUpdateEntity class."""

    @pytest.fixture
    def mock_config_entry(self) -> Mock:
        """Create a mock config entry."""
        config_entry = Mock()
        config_entry.data = {"discovery_method": DISCOVERY_CLOUD, "serial_number": "TEST-SERIAL-123"}
        return config_entry

    @pytest.fixture
    def update_entity(self, mock_coordinator, mock_config_entry) -> DysonFirmwareUpdateEntity:
        """Create a firmware update entity."""
        return DysonFirmwareUpdateEntity(mock_coordinator)

    def test_entity_properties(self, update_entity, mock_coordinator):
        """Test entity properties."""
        # Test basic properties
        assert update_entity.name == "Test Dyson Firmware Update"
        assert update_entity.unique_id == "TEST-SERIAL-123_firmware_update"  # Updated to match centralized fixture
        assert update_entity.device_class == "firmware"

        # Test version properties
        assert update_entity.installed_version == "1.0.0"
        assert update_entity.latest_version == "1.0.1"
        assert update_entity.in_progress is False

        # Test supported features
        assert update_entity.supported_features == UpdateEntityFeature.INSTALL

    def test_entity_properties_no_update_available(self, update_entity, mock_coordinator):
        """Test entity properties when no update is available."""
        mock_coordinator.firmware_latest_version = "1.0.0"  # Same as installed

        assert update_entity.installed_version == "1.0.0"
        assert update_entity.latest_version == "1.0.0"

    def test_entity_properties_update_in_progress(self, update_entity, mock_coordinator):
        """Test entity properties when update is in progress."""
        mock_coordinator.firmware_update_in_progress = True

        assert update_entity.in_progress is True

    @pytest.mark.asyncio
    async def test_async_install_success(self, update_entity, mock_coordinator):
        """Test successful firmware update installation."""
        mock_coordinator.async_install_firmware_update = AsyncMock(return_value=True)

        await update_entity.async_install(version="1.0.1", backup=False)

        mock_coordinator.async_install_firmware_update.assert_called_once_with("1.0.1")

    @pytest.mark.asyncio
    async def test_async_install_failure(self, update_entity, mock_coordinator):
        """Test firmware update installation failure."""
        mock_coordinator.async_install_firmware_update = AsyncMock(return_value=False)

        # The method doesn't raise - it just logs and returns
        result = await update_entity.async_install(version="1.0.1", backup=False)
        assert result is None  # Method doesn't return anything

    @pytest.mark.asyncio
    async def test_async_install_exception(self, update_entity, mock_coordinator):
        """Test firmware update installation with exception."""
        mock_coordinator.async_install_firmware_update = AsyncMock(side_effect=Exception("API Error"))

        # The method doesn't raise - it catches exceptions and logs them
        result = await update_entity.async_install(version="1.0.1", backup=False)
        assert result is None  # Method doesn't return anything

    def test_available_cloud_device(self, update_entity, mock_coordinator):
        """Test entity availability for cloud devices."""
        mock_coordinator.config_entry.data = {"discovery_method": DISCOVERY_CLOUD}
        mock_coordinator.device.is_connected = True

        assert update_entity.available is True

    def test_available_manual_device(self, update_entity, mock_coordinator):
        """Test entity availability for manual devices."""
        mock_coordinator.config_entry.data = {"discovery_method": DISCOVERY_MANUAL}
        mock_coordinator.device.is_connected = False

        assert update_entity.available is False

    def test_device_info(self, update_entity, mock_coordinator):
        """Test device info properties."""
        # Mock the device_info property to return a dict
        mock_coordinator.device.device_info = {
            "identifiers": {("hass_dyson", "TEST-SERIAL-123")},
            "name": "Test Dyson",
            "manufacturer": "Dyson",
        }

        device_info = update_entity.device_info

        assert device_info["identifiers"] == {("hass_dyson", "TEST-SERIAL-123")}
        assert device_info["name"] == "Test Dyson"
        assert device_info["manufacturer"] == "Dyson"


class TestFirmwareUpdatePlatformSetup:
    """Test the firmware update platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_cloud_device(self):
        """Test platform setup for cloud devices."""
        hass = Mock(spec=HomeAssistant)
        config_entry = Mock()
        config_entry.entry_id = "test_entry_id"
        config_entry.data = {"discovery_method": DISCOVERY_CLOUD}

        mock_coordinator = Mock(spec=DysonDataUpdateCoordinator)

        # Mock hass.data structure
        hass.data = {DOMAIN: {"test_entry_id": mock_coordinator}}

        async_add_entities = AsyncMock()

        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # async_setup_entry returns None, not True
        assert result is None
        async_add_entities.assert_called_once()  # Check that the entity was created
        call_args = async_add_entities.call_args[0][0]
        assert len(call_args) == 1
        assert isinstance(call_args[0], DysonFirmwareUpdateEntity)

    @pytest.mark.asyncio
    async def test_async_setup_entry_manual_device(self):
        """Test platform setup for manual devices (should not create entities)."""
        hass = Mock(spec=HomeAssistant)
        config_entry = Mock()
        config_entry.entry_id = "test_entry_id"
        config_entry.data = {"discovery_method": DISCOVERY_MANUAL}

        mock_coordinator = Mock(spec=DysonDataUpdateCoordinator)
        hass.data = {DOMAIN: {"test_entry_id": mock_coordinator}}

        async_add_entities = AsyncMock()

        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # async_setup_entry returns None, not True
        assert result is None
        async_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_coordinator(self):
        """Test platform setup when coordinator is not available."""
        hass = Mock(spec=HomeAssistant)
        config_entry = Mock()
        config_entry.entry_id = "test_entry_id"
        config_entry.data = {"discovery_method": DISCOVERY_CLOUD}

        # No coordinator in hass.data
        hass.data = {"hass_dyson": {}}

        async_add_entities = AsyncMock()

        with pytest.raises(KeyError):
            await async_setup_entry(hass, config_entry, async_add_entities)


class TestCoordinatorFirmwareMethods:
    """Test firmware-related methods in the coordinator."""

    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry for cloud device."""
        config_entry = Mock()
        config_entry.data = {
            "discovery_method": DISCOVERY_CLOUD,
            "serial_number": "TEST-SERIAL-123",
            "auth_token": "test_token",
            "username": "test@example.com",
        }
        return config_entry

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = Mock(spec=HomeAssistant)
        hass.async_add_executor_job = AsyncMock()
        return hass

    @pytest.fixture
    def coordinator(self, mock_hass, mock_config_entry):
        """Create a coordinator instance."""
        coord = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
        coord.hass = mock_hass
        coord.config_entry = mock_config_entry
        coord._device_type = "438"
        coord._firmware_version = "1.0.0"
        coord._firmware_latest_version = None
        coord._firmware_update_in_progress = False
        coord.device = Mock()
        coord.device.send_command = AsyncMock(return_value=True)
        coord.async_update_listeners = Mock()
        return coord

    @pytest.mark.asyncio
    async def test_async_check_firmware_update_available(self, coordinator, mock_hass):
        """Test checking for firmware updates when update is available."""
        # Mock the cloud client and pending release
        mock_client = AsyncMock()
        mock_pending_release = Mock()
        mock_pending_release.version = "1.0.1"

        mock_client.get_pending_release = AsyncMock(return_value=mock_pending_release)
        mock_client.close = AsyncMock()

        with patch.object(coordinator, "_authenticate_cloud_client") as mock_auth:
            mock_auth.return_value = mock_client

            result = await coordinator.async_check_firmware_update()

            assert result is True
            assert coordinator._firmware_latest_version == "1.0.1"
            coordinator.async_update_listeners.assert_called_once()
            mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_check_firmware_update_none_available(self, coordinator, mock_hass):
        """Test checking for firmware updates when no update is available."""
        mock_client = AsyncMock()

        mock_client.get_pending_release = AsyncMock(return_value=None)
        mock_client.close = AsyncMock()

        with patch.object(coordinator, "_authenticate_cloud_client") as mock_auth:
            mock_auth.return_value = mock_client

            result = await coordinator.async_check_firmware_update()

            assert result is False
            assert coordinator._firmware_latest_version == "1.0.0"  # Same as current
            mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_check_firmware_update_manual_device(self, coordinator):
        """Test firmware update check for manual devices (should return False)."""
        coordinator.config_entry.data["discovery_method"] = DISCOVERY_MANUAL

        result = await coordinator.async_check_firmware_update()

        assert result is False

    @pytest.mark.asyncio
    async def test_async_check_firmware_update_exception(self, coordinator, mock_hass):
        """Test firmware update check with exception."""
        mock_client = Mock()

        mock_hass.async_add_executor_job.side_effect = Exception("API Error")

        with patch.object(coordinator, "_authenticate_cloud_client") as mock_auth:
            mock_auth.return_value = mock_client

            result = await coordinator.async_check_firmware_update()

            assert result is False
            assert coordinator._firmware_latest_version == "1.0.0"  # Falls back to current

    @pytest.mark.asyncio
    async def test_async_install_firmware_update_success(self, coordinator):
        """Test successful firmware update installation."""
        version = "1.0.1"

        result = await coordinator.async_install_firmware_update(version)

        assert result is True

        # Verify MQTT command was sent
        call_args = coordinator.device.send_command.call_args
        assert call_args[0][0] == "SOFTWARE-UPGRADE"

        command_data = call_args[0][1]
        assert command_data["msg"] == "SOFTWARE-UPGRADE"
        assert command_data["version"] == version
        assert command_data["url"] == f"http://ota-firmware.cp.dyson.com/438/M__SC04.WF02/{version}/manifest.bin"

        # Verify time format (should be ISO format with Z suffix)
        assert "time" in command_data
        import re

        time_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z$"
        assert re.match(time_pattern, command_data["time"])  # Verify progress tracking
        assert coordinator._firmware_update_in_progress is True  # Remains True until device reports completion

    @pytest.mark.asyncio
    async def test_async_install_firmware_update_no_device(self, coordinator):
        """Test firmware update installation with no device connection."""
        coordinator.device = None

        result = await coordinator.async_install_firmware_update("1.0.1")

        assert result is False

    @pytest.mark.asyncio
    async def test_async_install_firmware_update_command_failure(self, coordinator):
        """Test firmware update installation when MQTT command fails."""
        coordinator.device.send_command = AsyncMock(side_effect=Exception("MQTT send failed"))

        result = await coordinator.async_install_firmware_update("1.0.1")

        assert result is False
        assert coordinator._firmware_update_in_progress is False

    @pytest.mark.asyncio
    async def test_async_install_firmware_update_exception(self, coordinator):
        """Test firmware update installation with exception."""
        coordinator.device.send_command = AsyncMock(side_effect=Exception("MQTT Error"))

        result = await coordinator.async_install_firmware_update("1.0.1")

        assert result is False
        assert coordinator._firmware_update_in_progress is False

    def test_extract_device_type_from_product_type(self, coordinator):
        """Test device type extraction from product_type field."""
        device_info = Mock()
        device_info.product_type = "438"
        device_info.type = None

        coordinator._extract_device_type(device_info)

        assert coordinator._device_type == "438"

    def test_extract_device_type_from_type_field(self, coordinator):
        """Test device type extraction from type field."""
        device_info = Mock()
        device_info.product_type = None
        device_info.type = "469"

        coordinator._extract_device_type(device_info)

        assert coordinator._device_type == "469"

    def test_extract_device_type_missing_both_fields(self, coordinator):
        """Test device type extraction when both fields are missing."""
        device_info = Mock()
        device_info.product_type = None
        device_info.type = None

        with pytest.raises(ValueError) as exc_info:
            coordinator._extract_device_type(device_info)

        assert "Device type not available" in str(exc_info.value)
        assert "TEST-SERIAL-123" in str(exc_info.value)

    def test_firmware_properties(self, coordinator):
        """Test firmware-related properties."""
        coordinator._firmware_version = "1.0.0"
        coordinator._firmware_latest_version = "1.0.1"
        coordinator._firmware_update_in_progress = True

        assert coordinator.firmware_version == "1.0.0"
        assert coordinator.firmware_latest_version == "1.0.1"
        assert coordinator.firmware_update_in_progress is True

    def test_device_type_property(self, coordinator):
        """Test device type property."""
        coordinator._device_type = "438"

        assert coordinator.device_type == "438"
