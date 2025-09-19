"""Simple coordinator tests focusing on uncovered methods."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.hass_dyson.const import CONF_SERIAL_NUMBER, MQTT_CMD_REQUEST_CURRENT_STATE
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator


@pytest.fixture
def mock_hass():
    """Mock Home Assistant with necessary components."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.bus.async_fire = MagicMock()
    hass.loop.call_soon_threadsafe = MagicMock()
    hass.async_create_task = MagicMock()
    hass.add_job = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Mock config entry with necessary data."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
    }
    return config_entry


class TestDysonDataUpdateCoordinatorMethodsSimple:
    """Test simple coordinator methods without complex initialization."""

    @pytest.mark.asyncio
    async def test_extract_capabilities_basic(self, mock_hass, mock_config_entry):
        """Test basic capabilities extraction."""
        # Use proper patching pattern from our testing guide
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        # Mock a device info object with proper capabilities structure
        mock_device_info = MagicMock()
        mock_device_info.capabilities = ["environmental_data", "oscillation", "air_quality"]

        # Test the actual capability extraction method
        result = coordinator._extract_capabilities(mock_device_info)

        # Should return a list of detected capabilities
        assert isinstance(result, list)
        expected_capabilities = ["environmental_data", "oscillation", "air_quality"]
        for cap in expected_capabilities:
            assert cap in result

    @pytest.mark.asyncio
    async def test_extract_capabilities_no_environmental_data(self, mock_hass, mock_config_entry):
        """Test capabilities extraction when no environmental data."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_device_info = MagicMock()
        # Mock the capabilities attribute that the implementation actually checks
        mock_device_info.capabilities = ["oscillation", "heating"]

        result = coordinator._extract_capabilities(mock_device_info)

        assert isinstance(result, list)
        assert "environmental_data" not in result
        assert "oscillation" in result
        assert "heating" in result
        assert "air_quality" not in result

    @pytest.mark.asyncio
    async def test_extract_capabilities_missing_attributes(self, mock_hass, mock_config_entry):
        """Test capabilities extraction with missing attributes."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry

        mock_device_info = MagicMock()
        # Remove attributes to simulate missing capabilities
        del mock_device_info.environmental_data
        del mock_device_info.oscillation

        result = coordinator._extract_capabilities(mock_device_info)

        # Should return empty list when attributes are missing
        assert result == []

    @pytest.mark.asyncio
    async def test_get_effective_connection_type_with_parent(self, mock_hass, mock_config_entry):
        """Test effective connection type with parent account entry."""
        # Setup config entry with parent_entry_id
        mock_config_entry.data = {CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A", "parent_entry_id": "parent-account-123"}

        # Mock the parent account entry
        mock_account_entry = MagicMock()
        mock_account_entry.entry_id = "parent-account-123"
        mock_account_entry.data = {"connection_type": "cloud_only"}

        # Mock the config entries async_entries method to return the parent entry
        mock_hass.config_entries = MagicMock()
        mock_hass.config_entries.async_entries.return_value = [mock_account_entry]

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry

            result = coordinator._get_effective_connection_type()

            # Should use the parent account connection type
            assert result == "cloud_only"

    @pytest.mark.asyncio
    async def test_get_effective_connection_type_device_specific(self, mock_hass):
        """Test effective connection type with device-specific setting."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
            "connection_type": "local_only",
        }

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = config_entry

        result = coordinator._get_effective_connection_type()

        # Should use device-specific connection type
        assert result == "local_only"

    @pytest.mark.asyncio
    async def test_get_effective_connection_type_default(self, mock_hass, mock_config_entry):
        """Test effective connection type with default fallback."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry

        # Mock no parent account entries
        mock_hass.config_entries = MagicMock()
        mock_hass.config_entries.async_entries_for_config_entry_id.return_value = []

        result = coordinator._get_effective_connection_type()

        # Should fall back to default
        assert result == "local_cloud_fallback"

    @pytest.mark.asyncio
    async def test_get_mqtt_password_variations(self, mock_hass, mock_config_entry):
        """Test MQTT password extraction from various fields."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry

        # Test with password field
        mock_mqtt_obj = MagicMock()
        mock_mqtt_obj.password = "test_password"
        mock_mqtt_obj.decoded_password = ""
        mock_mqtt_obj.local_password = ""
        mock_mqtt_obj.device_password = ""

        result = coordinator._get_mqtt_password(None, mock_mqtt_obj)
        assert result == "test_password"

        # Test with decoded_password field
        mock_mqtt_obj.password = ""
        mock_mqtt_obj.decoded_password = "decoded_password"
        result = coordinator._get_mqtt_password(None, mock_mqtt_obj)
        assert result == "decoded_password"

        # Test with local_password field
        mock_mqtt_obj.decoded_password = ""
        mock_mqtt_obj.local_password = "local_password"
        result = coordinator._get_mqtt_password(None, mock_mqtt_obj)
        assert result == "local_password"

        # Test with device_password field
        mock_mqtt_obj.local_password = ""
        mock_mqtt_obj.device_password = "device_password"
        result = coordinator._get_mqtt_password(None, mock_mqtt_obj)
        assert result == "device_password"

    @pytest.mark.asyncio
    async def test_get_mqtt_password_with_decryption(self, mock_hass, mock_config_entry):
        """Test MQTT password with decryption."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry

        mock_cloud_client = MagicMock()
        mock_mqtt_obj = MagicMock()
        mock_mqtt_obj.password = ""
        mock_mqtt_obj.decoded_password = ""
        mock_mqtt_obj.local_password = ""
        mock_mqtt_obj.device_password = ""
        mock_mqtt_obj.local_broker_credentials = "encrypted_credentials"

        # Mock successful decryption
        with patch.object(coordinator, "_decrypt_mqtt_credentials") as mock_decrypt:
            mock_decrypt.return_value = "decrypted_password"

            result = coordinator._get_mqtt_password(mock_cloud_client, mock_mqtt_obj)

            assert result == "decrypted_password"
            mock_decrypt.assert_called_once_with(mock_cloud_client, mock_mqtt_obj)

    @pytest.mark.asyncio
    async def test_schedule_fallback_update_success(self, mock_hass, mock_config_entry):
        """Test successful fallback update scheduling."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry
            coordinator.async_update_listeners = MagicMock()

            # Mock the loop.call_soon_threadsafe method
            mock_hass.loop = MagicMock()
            mock_hass.loop.call_soon_threadsafe = MagicMock()

        coordinator._schedule_fallback_update()

        # Should schedule the listener update through call_soon_threadsafe
        mock_hass.loop.call_soon_threadsafe.assert_called_once_with(coordinator.async_update_listeners)

    @pytest.mark.asyncio
    async def test_schedule_fallback_update_exception(self, mock_hass, mock_config_entry):
        """Test fallback update with exception."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry
            coordinator.async_update_listeners = MagicMock()

            # Mock the loop.call_soon_threadsafe method to raise exception
            mock_hass.loop = MagicMock()
            mock_hass.loop.call_soon_threadsafe = MagicMock(side_effect=Exception("Test exception"))

        # Should handle exception gracefully
        coordinator._schedule_fallback_update()

        # Should still attempt the call
        mock_hass.loop.call_soon_threadsafe.assert_called_once_with(coordinator.async_update_listeners)


class TestDysonDataUpdateCoordinatorDeviceSetupSimple:
    """Test device setup methods with minimal mocking."""

    @pytest.mark.asyncio
    async def test_on_message_update_with_state_topic(self, mock_hass, mock_config_entry):
        """Test message update callback with state topic."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry

        # Mock the state change handler
        with patch.object(coordinator, "_handle_state_change_message") as mock_handler:
            # Pass the correct message format that triggers state change handling
            coordinator._on_message_update("DYSON/STATE-CHANGE", {"msg": "STATE-CHANGE"})

            # Should call the state change handler
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_update_non_state_topic(self, mock_hass, mock_config_entry):
        """Test message update callback with non-state topic."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry

        # Mock the state change handler
        with patch.object(coordinator, "_handle_state_change_message") as mock_handler:
            coordinator._on_message_update("DYSON/ENVIRONMENT", {"pm25": 10})

            # Should not call the state change handler for non-state topics
            mock_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_schedule_coordinator_data_update_calls_hass(self, mock_hass, mock_config_entry):
        """Test that scheduling coordinator data update calls hass methods."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry

        coordinator._schedule_coordinator_data_update()

        # Should call hass.loop.call_soon_threadsafe
        mock_hass.loop.call_soon_threadsafe.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_coordinator_update_task_calls_hass(self, mock_hass, mock_config_entry):
        """Test that creating coordinator update task calls hass methods."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry

        coordinator._create_coordinator_update_task()

        # Should call hass.async_create_task
        mock_hass.async_create_task.assert_called_once()


class TestDysonDataUpdateCoordinatorAsyncUpdateData:
    """Test the complex _async_update_data method."""

    @pytest.mark.asyncio
    async def test_async_update_data_device_connected_success(self, mock_hass, mock_config_entry):
        """Test async update with connected device returning state."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry

        # Create a mock device that is connected
        mock_device = MagicMock()
        mock_device.is_connected = True
        mock_device.get_state = AsyncMock(return_value={"fan": {"speed": 5}})
        coordinator.device = mock_device

        # Test the actual async update method
        result = await coordinator._async_update_data()

        # Should return the device state
        assert result == {"fan": {"speed": 5}}
        mock_device.get_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_data_device_disconnected_reconnect_success(self, mock_hass, mock_config_entry):
        """Test async update with disconnected device that reconnects successfully."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry

        mock_device = MagicMock()
        mock_device.is_connected = False
        mock_device.connect = AsyncMock(return_value=True)
        mock_device.send_command = AsyncMock()
        mock_device.get_state = AsyncMock(return_value={"fan": {"speed": 3}})
        coordinator.device = mock_device

        result = await coordinator._async_update_data()

        # Should reconnect, send current state command, and return state
        assert result == {"fan": {"speed": 3}}
        mock_device.connect.assert_called_once()
        mock_device.send_command.assert_called_once_with(MQTT_CMD_REQUEST_CURRENT_STATE)
        mock_device.get_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_data_device_disconnected_reconnect_failure(self, mock_hass, mock_config_entry):
        """Test async update with disconnected device that fails to reconnect."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry

        mock_device = MagicMock()
        mock_device.is_connected = False
        mock_device.connect = AsyncMock(return_value=False)
        coordinator.device = mock_device

        # Should raise UpdateFailed when reconnection fails
        with pytest.raises(UpdateFailed, match="Failed to reconnect to device"):
            await coordinator._async_update_data()

        mock_device.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_data_no_device(self, mock_hass, mock_config_entry):
        """Test async update with no device initialized."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry
        coordinator.device = None

        # Should raise UpdateFailed when no device
        with pytest.raises(UpdateFailed, match="Device not initialized"):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_async_update_data_send_command_exception_continues(self, mock_hass, mock_config_entry):
        """Test async update continues even if send command fails."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            # Set required attributes manually after patching parent __init__
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry

        mock_device = MagicMock()
        mock_device.is_connected = False
        mock_device.connect = AsyncMock(return_value=True)
        mock_device.send_command = AsyncMock(side_effect=Exception("Command failed"))
        mock_device.get_state = AsyncMock(return_value={"fan": {"speed": 1}})
        coordinator.device = mock_device

        # Should continue and return state even if send_command fails
        result = await coordinator._async_update_data()

        assert result == {"fan": {"speed": 1}}
        mock_device.connect.assert_called_once()
        mock_device.send_command.assert_called_once_with(MQTT_CMD_REQUEST_CURRENT_STATE)
        mock_device.get_state.assert_called_once()
