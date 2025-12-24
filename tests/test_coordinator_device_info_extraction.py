"""Extended coordinator tests for device info extraction and MQTT methods."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.hass_dyson.const import (
    CONF_SERIAL_NUMBER,
    MQTT_CMD_REQUEST_CURRENT_STATE,
)
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator


@pytest.fixture
def mock_hass():
    """Mock Home Assistant."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.bus.async_fire = MagicMock()
    hass.loop.call_soon_threadsafe = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
    }
    return config_entry


class TestDysonDataUpdateCoordinatorDeviceInfoExtraction:
    """Test device info extraction methods."""

    @pytest.mark.asyncio
    async def test_extract_device_type_with_product_type(
        self, mock_hass, mock_config_entry
    ):
        """Test extracting device type from product_type field."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_device_info = MagicMock()
        mock_device_info.product_type = "438"
        mock_device_info.type = None

        coordinator._extract_device_type(mock_device_info)

        assert coordinator.device_type == "438"

    @pytest.mark.asyncio
    async def test_extract_device_type_with_type_field(
        self, mock_hass, mock_config_entry
    ):
        """Test extracting device type from type field."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_device_info = MagicMock()
        mock_device_info.product_type = None
        mock_device_info.type = "358"

        coordinator._extract_device_type(mock_device_info)

        assert coordinator.device_type == "358"

    @pytest.mark.asyncio
    async def test_extract_device_type_missing_both_fields(
        self, mock_hass, mock_config_entry
    ):
        """Test extracting device type when both fields are missing."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_device_info = MagicMock()
        mock_device_info.product_type = None
        mock_device_info.type = None

        with pytest.raises(ValueError, match="Device type not available"):
            coordinator._extract_device_type(mock_device_info)

    @pytest.mark.asyncio
    async def test_extract_device_category_from_config(self, mock_hass):
        """Test extracting device category from config entry."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
            "device_category": "robot",
        }

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, config_entry)

        mock_device_info = MagicMock()
        mock_device_info.category = "ec"

        with patch(
            "custom_components.hass_dyson.device_utils.normalize_device_category"
        ) as mock_normalize:
            mock_normalize.return_value = ["robot"]
            coordinator._extract_device_category(mock_device_info)

            assert coordinator.device_category == ["robot"]
            mock_normalize.assert_called_once_with("robot")

    @pytest.mark.asyncio
    async def test_extract_device_category_from_api(self, mock_hass, mock_config_entry):
        """Test extracting device category from API response."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_device_info = MagicMock()
        mock_device_info.category = "ec"

        with patch(
            "custom_components.hass_dyson.device_utils.normalize_device_category"
        ) as mock_normalize:
            mock_normalize.return_value = ["ec"]
            coordinator._extract_device_category(mock_device_info)

            assert coordinator.device_category == ["ec"]
            mock_normalize.assert_called_once_with("ec")

    @pytest.mark.asyncio
    async def test_extract_device_capabilities_from_config(self, mock_hass):
        """Test extracting device capabilities from config entry."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
            "capabilities": ["oscillation", "heating"],
        }

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, config_entry)

        mock_device_info = MagicMock()

        with patch(
            "custom_components.hass_dyson.device_utils.normalize_capabilities"
        ) as mock_normalize:
            mock_normalize.return_value = ["oscillation", "heating"]
            coordinator._extract_device_capabilities(mock_device_info)

            assert coordinator.device_capabilities == ["oscillation", "heating"]
            mock_normalize.assert_called_once_with(["oscillation", "heating"])

    @pytest.mark.asyncio
    async def test_extract_device_capabilities_from_api(
        self, mock_hass, mock_config_entry
    ):
        """Test extracting device capabilities from API response."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_device_info = MagicMock()

        with patch.object(coordinator, "_extract_capabilities") as mock_extract_caps:
            with patch(
                "custom_components.hass_dyson.device_utils.normalize_capabilities"
            ) as mock_normalize:
                mock_extract_caps.return_value = ["environmental_data", "air_quality"]
                mock_normalize.return_value = ["environmental_data", "air_quality"]

                coordinator._extract_device_capabilities(mock_device_info)

                assert coordinator.device_capabilities == [
                    "environmental_data",
                    "air_quality",
                ]
                mock_extract_caps.assert_called_once_with(mock_device_info)
                mock_normalize.assert_called_once_with(
                    ["environmental_data", "air_quality"]
                )

    @pytest.mark.asyncio
    async def test_extract_device_capabilities_api_exception(
        self, mock_hass, mock_config_entry
    ):
        """Test handling exception during API capability extraction."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_device_info = MagicMock()

        with patch.object(coordinator, "_extract_capabilities") as mock_extract_caps:
            mock_extract_caps.side_effect = Exception("API error")

            coordinator._extract_device_capabilities(mock_device_info)

            assert coordinator.device_capabilities == []

    @pytest.mark.asyncio
    async def test_extract_device_capabilities_critical_exception(
        self, mock_hass, mock_config_entry
    ):
        """Test handling critical exception during capability extraction."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_device_info = MagicMock()

        with patch(
            "custom_components.hass_dyson.device_utils.normalize_capabilities"
        ) as mock_normalize:
            mock_normalize.side_effect = Exception("Critical error")

            coordinator._extract_device_capabilities(mock_device_info)

            assert coordinator.device_capabilities == []


class TestDysonDataUpdateCoordinatorMQTTCredentials:
    """Test MQTT credential extraction methods."""

    @pytest.mark.asyncio
    async def test_get_mqtt_object_success(self, mock_hass, mock_config_entry):
        """Test successful MQTT object extraction."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_mqtt_obj = MagicMock()
        mock_connected_config = MagicMock()
        mock_connected_config.mqtt = mock_mqtt_obj

        mock_device_info = MagicMock()
        mock_device_info.connected_configuration = mock_connected_config

        result = coordinator._get_mqtt_object(mock_device_info)

        assert result == mock_mqtt_obj

    @pytest.mark.asyncio
    async def test_get_mqtt_object_no_connected_config(
        self, mock_hass, mock_config_entry
    ):
        """Test MQTT object extraction with no connected configuration."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_device_info = MagicMock()
        mock_device_info.connected_configuration = None

        result = coordinator._get_mqtt_object(mock_device_info)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_mqtt_username_with_username_field(
        self, mock_hass, mock_config_entry
    ):
        """Test MQTT username extraction with username field."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_mqtt_obj = MagicMock()
        mock_mqtt_obj.username = "mqtt_user_123"
        mock_mqtt_obj.local_username = ""
        mock_mqtt_obj.broker_username = ""

        result = coordinator._get_mqtt_username(mock_mqtt_obj)

        assert result == "mqtt_user_123"

    @pytest.mark.asyncio
    async def test_get_mqtt_username_fallback_to_serial(
        self, mock_hass, mock_config_entry
    ):
        """Test MQTT username fallback to serial number."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_mqtt_obj = MagicMock()
        mock_mqtt_obj.username = ""
        mock_mqtt_obj.local_username = ""
        mock_mqtt_obj.broker_username = ""

        result = coordinator._get_mqtt_username(mock_mqtt_obj)

        assert result == "VS6-EU-HJA1234A"

    @pytest.mark.asyncio
    async def test_get_plain_password_with_password_field(
        self, mock_hass, mock_config_entry
    ):
        """Test plain password extraction with password field."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_mqtt_obj = MagicMock()
        mock_mqtt_obj.password = "plain_password_123"
        mock_mqtt_obj.decoded_password = ""
        mock_mqtt_obj.local_password = ""
        mock_mqtt_obj.device_password = ""

        result = coordinator._get_plain_password(mock_mqtt_obj)

        assert result == "plain_password_123"

    @pytest.mark.asyncio
    async def test_get_plain_password_no_password(self, mock_hass, mock_config_entry):
        """Test plain password extraction with no password fields."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_mqtt_obj = MagicMock()
        mock_mqtt_obj.password = ""
        mock_mqtt_obj.decoded_password = ""
        mock_mqtt_obj.local_password = ""
        mock_mqtt_obj.device_password = ""

        result = coordinator._get_plain_password(mock_mqtt_obj)

        assert result == ""

    @pytest.mark.asyncio
    async def test_decrypt_mqtt_credentials_success(self, mock_hass, mock_config_entry):
        """Test successful MQTT credentials decryption."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_cloud_client = MagicMock()
        mock_cloud_client.decrypt_local_credentials.return_value = "decrypted_password"

        mock_mqtt_obj = MagicMock()
        mock_mqtt_obj.local_broker_credentials = "encrypted_credentials"

        result = coordinator._decrypt_mqtt_credentials(mock_cloud_client, mock_mqtt_obj)

        assert result == "decrypted_password"
        mock_cloud_client.decrypt_local_credentials.assert_called_once_with(
            "encrypted_credentials", "VS6-EU-HJA1234A"
        )

    @pytest.mark.asyncio
    async def test_decrypt_mqtt_credentials_no_credentials(
        self, mock_hass, mock_config_entry
    ):
        """Test MQTT credentials decryption with no credentials."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_cloud_client = MagicMock()
        mock_mqtt_obj = MagicMock()
        mock_mqtt_obj.local_broker_credentials = ""

        result = coordinator._decrypt_mqtt_credentials(mock_cloud_client, mock_mqtt_obj)

        assert result == ""

    @pytest.mark.asyncio
    async def test_decrypt_mqtt_credentials_exception(
        self, mock_hass, mock_config_entry
    ):
        """Test MQTT credentials decryption with exception."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_cloud_client = MagicMock()
        mock_cloud_client.decrypt_local_credentials.side_effect = Exception(
            "Decryption failed"
        )

        mock_mqtt_obj = MagicMock()
        mock_mqtt_obj.local_broker_credentials = "encrypted_credentials"

        result = coordinator._decrypt_mqtt_credentials(mock_cloud_client, mock_mqtt_obj)

        assert result == "encrypted_credentials"  # Fallback to encrypted

    @pytest.mark.asyncio
    async def test_extract_mqtt_credentials_success(self, mock_hass, mock_config_entry):
        """Test successful MQTT credentials extraction."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_cloud_client = MagicMock()
        mock_device_info = MagicMock()

        with patch.object(coordinator, "_get_mqtt_object") as mock_get_mqtt_obj:
            with patch.object(coordinator, "_get_mqtt_username") as mock_get_username:
                with patch.object(
                    coordinator, "_get_mqtt_password"
                ) as mock_get_password:
                    mock_mqtt_obj = MagicMock()
                    mock_get_mqtt_obj.return_value = mock_mqtt_obj
                    mock_get_username.return_value = "test_user"
                    mock_get_password.return_value = "test_password"

                    result = await coordinator._extract_mqtt_credentials(
                        mock_cloud_client, mock_device_info
                    )

                    assert result == {
                        "mqtt_username": "test_user",
                        "mqtt_password": "test_password",
                    }

    @pytest.mark.asyncio
    async def test_extract_mqtt_credentials_empty_password(
        self, mock_hass, mock_config_entry
    ):
        """Test MQTT credentials extraction with empty password."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_cloud_client = MagicMock()
        mock_device_info = MagicMock()

        with patch.object(coordinator, "_get_mqtt_object") as mock_get_mqtt_obj:
            with patch.object(coordinator, "_get_mqtt_username") as mock_get_username:
                with patch.object(
                    coordinator, "_get_mqtt_password"
                ) as mock_get_password:
                    mock_mqtt_obj = MagicMock()
                    mock_get_mqtt_obj.return_value = mock_mqtt_obj
                    mock_get_username.return_value = "test_user"
                    mock_get_password.return_value = ""

                    with pytest.raises(
                        UpdateFailed, match="MQTT password cannot be empty"
                    ):
                        await coordinator._extract_mqtt_credentials(
                            mock_cloud_client, mock_device_info
                        )


class TestDysonDataUpdateCoordinatorUpdate:
    """Test coordinator data update methods."""

    @pytest.mark.asyncio
    async def test_async_update_data_no_device(self, mock_hass, mock_config_entry):
        """Test async update data with no device."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        coordinator.device = None

        with pytest.raises(UpdateFailed, match="Device not initialized"):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_async_update_data_device_connected(
        self, mock_hass, mock_config_entry
    ):
        """Test async update data with connected device."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_device = MagicMock()
        mock_device.is_connected = True
        mock_device.get_state = AsyncMock(return_value={"state": "connected"})
        coordinator.device = mock_device

        result = await coordinator._async_update_data()

        assert result == {"state": "connected", "environmental-data": {}}
        mock_device.get_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_data_device_reconnection_success(
        self, mock_hass, mock_config_entry
    ):
        """Test async update data with successful reconnection."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_device = MagicMock()
        mock_device.is_connected = False
        mock_device.connect = AsyncMock(return_value=True)
        mock_device.send_command = AsyncMock()
        mock_device.get_state = AsyncMock(return_value={"state": "reconnected"})
        coordinator.device = mock_device

        result = await coordinator._async_update_data()

        assert result == {"state": "reconnected", "environmental-data": {}}
        mock_device.connect.assert_called_once()
        # Should call both current state and fault requests (new fault polling feature)
        assert mock_device.send_command.call_count == 2
        expected_calls = [
            call(MQTT_CMD_REQUEST_CURRENT_STATE),
            call("REQUEST-CURRENT-FAULTS"),
        ]
        mock_device.send_command.assert_has_calls(expected_calls, any_order=True)
        mock_device.get_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_data_device_reconnection_failure(
        self, mock_hass, mock_config_entry
    ):
        """Test async update data with failed reconnection."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_device = MagicMock()
        mock_device.is_connected = False
        mock_device.connect = AsyncMock(return_value=False)
        coordinator.device = mock_device

        with pytest.raises(UpdateFailed, match="Failed to reconnect to device"):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_async_update_data_send_command_exception(
        self, mock_hass, mock_config_entry
    ):
        """Test async update data with send command exception."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_device = MagicMock()
        mock_device.is_connected = False
        mock_device.connect = AsyncMock(return_value=True)
        mock_device.send_command = AsyncMock(side_effect=Exception("Command failed"))
        mock_device.get_state = AsyncMock(return_value={"state": "reconnected"})
        coordinator.device = mock_device

        result = await coordinator._async_update_data()

        # Should still complete successfully even with command exception
        assert result == {"state": "reconnected", "environmental-data": {}}

    @pytest.mark.asyncio
    async def test_update_coordinator_data_success(self, mock_hass, mock_config_entry):
        """Test successful coordinator data update."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            coordinator.async_update_listeners = MagicMock()

        mock_device = MagicMock()
        mock_device.get_state = AsyncMock(return_value={"fresh": "state"})
        coordinator.device = mock_device

        await coordinator._update_coordinator_data()

        assert coordinator.data == {"fresh": "state"}
        coordinator.async_update_listeners.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_coordinator_data_exception(
        self, mock_hass, mock_config_entry
    ):
        """Test coordinator data update with exception."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            coordinator.async_update_listeners = MagicMock()

        mock_device = MagicMock()
        mock_device.get_state = AsyncMock(side_effect=Exception("Device error"))
        coordinator.device = mock_device

        await coordinator._update_coordinator_data()

        # Should still call listeners even with exception
        coordinator.async_update_listeners.assert_called_once()


class TestDysonDataUpdateCoordinatorDebugMethods:
    """Test debug and logging methods."""

    @pytest.mark.asyncio
    async def test_debug_connected_configuration_with_config(
        self, mock_hass, mock_config_entry
    ):
        """Test debug connected configuration with configuration."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        # Use simpler mock setup to avoid complex nesting
        mock_connected_config = MagicMock()
        mock_connected_config.configure_mock(**{"test": "value"})

        mock_device_info = MagicMock()
        mock_device_info.configure_mock(connected_configuration=mock_connected_config)

        with patch.object(coordinator, "_debug_mqtt_object") as mock_debug_mqtt:
            coordinator._debug_connected_configuration(mock_device_info)
            mock_debug_mqtt.assert_called_once_with(mock_connected_config)

    @pytest.mark.asyncio
    async def test_debug_connected_configuration_none(
        self, mock_hass, mock_config_entry
    ):
        """Test debug connected configuration with None."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_device_info = MagicMock()
        mock_device_info.configure_mock(connected_configuration=None)

        # Should not raise any errors
        coordinator._debug_connected_configuration(mock_device_info)

    @pytest.mark.asyncio
    async def test_debug_mqtt_object_with_mqtt(self, mock_hass, mock_config_entry):
        """Test debug MQTT object with MQTT object."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        # Use simpler mock setup to avoid complex nesting
        mock_mqtt_obj = MagicMock()
        mock_mqtt_obj.configure_mock(
            **{"password": "test_password", "decoded_password": "decoded_password"}
        )

        mock_connected_config = MagicMock()
        mock_connected_config.configure_mock(mqtt=mock_mqtt_obj)

        # Should not raise any errors
        coordinator._debug_mqtt_object(mock_connected_config)

    @pytest.mark.asyncio
    async def test_debug_mqtt_object_none(self, mock_hass, mock_config_entry):
        """Test debug MQTT object with None."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        mock_connected_config = MagicMock()
        mock_connected_config.mqtt = None

        # Should not raise any errors
        coordinator._debug_mqtt_object(mock_connected_config)

    @pytest.mark.asyncio
    async def test_log_mqtt_credentials(self, mock_hass, mock_config_entry):
        """Test MQTT credentials logging."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        # Should not raise any errors
        coordinator._log_mqtt_credentials("test_user", "test_password_1234567890_long")

    @pytest.mark.asyncio
    async def test_log_mqtt_credentials_short_password(
        self, mock_hass, mock_config_entry
    ):
        """Test MQTT credentials logging with short password."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)

        # Should not raise any errors
        coordinator._log_mqtt_credentials("test_user", "short")
