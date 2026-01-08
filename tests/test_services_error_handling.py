"""Comprehensive service error handling and validation tests for services.py.

Tests focus on:
- Parameter validation (range, type, required fields)
- Error handling (device not found, command failures, connection errors)
- Edge cases (boundary values, missing data, invalid states)
- Service registration and availability
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.hass_dyson.services import (
    SERVICE_RESET_FILTER_SCHEMA,
    SERVICE_SET_OSCILLATION_ANGLES_SCHEMA,
    SERVICE_SET_SLEEP_TIMER_SCHEMA,
    _convert_to_string,
    _decrypt_device_mqtt_credentials,
)


class TestServiceSchemaValidation:
    """Test service schema validation for parameter types and ranges."""

    def test_sleep_timer_invalid_minutes_type(self):
        """Test sleep timer schema rejects non-integer minutes."""
        schema = SERVICE_SET_SLEEP_TIMER_SCHEMA

        with pytest.raises(vol.Invalid):
            schema({"device_id": "test_device", "minutes": "not_a_number"})

        with pytest.raises(vol.Invalid):
            schema({"device_id": "test_device", "minutes": 12.5})

    def test_sleep_timer_out_of_range_minutes(self):
        """Test sleep timer schema rejects out-of-range minutes."""
        schema = SERVICE_SET_SLEEP_TIMER_SCHEMA

        # Below minimum (15)
        with pytest.raises(vol.Invalid):
            schema({"device_id": "test_device", "minutes": 10})

        # Above maximum (540)
        with pytest.raises(vol.Invalid):
            schema({"device_id": "test_device", "minutes": 600})

    def test_sleep_timer_missing_required_field(self):
        """Test sleep timer schema rejects missing device_id."""
        schema = SERVICE_SET_SLEEP_TIMER_SCHEMA

        with pytest.raises(vol.Invalid):
            schema({"minutes": 60})

    def test_oscillation_angles_invalid_types(self):
        """Test oscillation angles schema rejects invalid types."""
        schema = SERVICE_SET_OSCILLATION_ANGLES_SCHEMA

        with pytest.raises(vol.Invalid):
            schema(
                {
                    "device_id": "test",
                    "oscillation_angle_low": "not_int",
                    "oscillation_angle_high": 90,
                }
            )

        with pytest.raises(vol.Invalid):
            schema(
                {
                    "device_id": "test",
                    "oscillation_angle_low": 5,
                    "oscillation_angle_high": "not_int",
                }
            )

    def test_oscillation_angles_out_of_range(self):
        """Test oscillation angles schema rejects out-of-range values."""
        schema = SERVICE_SET_OSCILLATION_ANGLES_SCHEMA

        # Below minimum (5)
        with pytest.raises(vol.Invalid):
            schema(
                {
                    "device_id": "test",
                    "oscillation_angle_low": 0,
                    "oscillation_angle_high": 90,
                }
            )

        # Above maximum (355)
        with pytest.raises(vol.Invalid):
            schema(
                {
                    "device_id": "test",
                    "oscillation_angle_low": 5,
                    "oscillation_angle_high": 360,
                }
            )

    def test_reset_filter_invalid_filter_type(self):
        """Test reset filter schema accepts valid filter types."""
        schema = SERVICE_RESET_FILTER_SCHEMA

        # Valid types should work
        valid_data = schema({"device_id": "test", "filter_type": "hepa"})
        assert valid_data["filter_type"] == "hepa"

        valid_data = schema({"device_id": "test", "filter_type": "carbon"})
        assert valid_data["filter_type"] == "carbon"

    # Removed: schedule_operation service was experimental and removed
    #
    # def test_schedule_operation_missing_required_params(self):
    #     \"\"\"Test schedule operation requires both days and time.\"\"\"
    #     ...

    # Removed: schedule_operation service was experimental and removed
    #
    # def test_schedule_operation_invalid_time_format(self):
    #     \"\"\"Test schedule operation rejects invalid time format.\"\"\"
    #     ...


class TestServiceParameterValidation:
    """Test service call parameter validation and error handling."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_set_sleep_timer_device_not_found(self, mock_get_coord):
        """Test sleep timer service with non-existent device."""
        from homeassistant.exceptions import ServiceValidationError

        from custom_components.hass_dyson.services import _handle_set_sleep_timer

        mock_get_coord.return_value = None
        mock_hass = MagicMock()
        mock_call = MagicMock()
        mock_call.data = {"device_id": "nonexistent_device", "minutes": 60}

        # Should raise ServiceValidationError when device not found
        with pytest.raises(ServiceValidationError, match="not found or not available"):
            await _handle_set_sleep_timer(mock_hass, mock_call)

        # Verify coordinator was checked
        mock_get_coord.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_cancel_sleep_timer_device_not_found(self, mock_get_coord):
        """Test cancel sleep timer with non-existent device."""
        from homeassistant.exceptions import ServiceValidationError

        from custom_components.hass_dyson.services import _handle_cancel_sleep_timer

        mock_get_coord.return_value = None
        mock_hass = MagicMock()
        mock_call = MagicMock()
        mock_call.data = {"device_id": "nonexistent_device"}

        with pytest.raises(ServiceValidationError, match="not found or not available"):
            await _handle_cancel_sleep_timer(mock_hass, mock_call)

        mock_get_coord.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_reset_filter_device_not_found(self, mock_get_coord):
        """Test reset filter with non-existent device."""
        from homeassistant.exceptions import ServiceValidationError

        from custom_components.hass_dyson.services import _handle_reset_filter

        mock_get_coord.return_value = None
        mock_hass = MagicMock()
        mock_call = MagicMock()
        mock_call.data = {"device_id": "nonexistent_device", "filter_type": "hepa"}

        with pytest.raises(ServiceValidationError, match="not found or not available"):
            await _handle_reset_filter(mock_hass, mock_call)

        mock_get_coord.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_set_oscillation_angles_device_not_found(self, mock_get_coord):
        """Test set oscillation angles with non-existent device."""
        from homeassistant.exceptions import ServiceValidationError

        from custom_components.hass_dyson.services import _handle_set_oscillation_angles

        mock_get_coord.return_value = None
        mock_hass = MagicMock()
        mock_call = MagicMock()
        mock_call.data = {
            "device_id": "nonexistent_device",
            "lower_angle": 5,
            "upper_angle": 180,
        }

        with pytest.raises(ServiceValidationError, match="not found or not available"):
            await _handle_set_oscillation_angles(mock_hass, mock_call)

        mock_get_coord.assert_called_once()


class TestServiceCommandExecution:
    """Test service command execution and device interaction."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_set_sleep_timer_command_failure(self, mock_get_coord):
        """Test sleep timer handles device command failure."""
        from homeassistant.exceptions import HomeAssistantError

        from custom_components.hass_dyson.services import _handle_set_sleep_timer

        mock_coordinator = MagicMock()
        mock_coordinator.serial_number = "TEST123"
        mock_device = MagicMock()
        mock_device.set_sleep_timer = AsyncMock(
            side_effect=RuntimeError("Command failed")
        )
        mock_coordinator.device = mock_device
        mock_coordinator.async_request_refresh = AsyncMock()
        mock_get_coord.return_value = mock_coordinator

        mock_hass = MagicMock()
        mock_call = MagicMock()
        mock_call.data = {"device_id": "test_device", "minutes": 60}

        # Should raise HomeAssistantError
        with pytest.raises(HomeAssistantError, match="Failed to set sleep timer"):
            await _handle_set_sleep_timer(mock_hass, mock_call)

        mock_device.set_sleep_timer.assert_called_once_with(60)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_cancel_sleep_timer_command_failure(self, mock_get_coord):
        """Test cancel sleep timer handles device command failure."""
        from homeassistant.exceptions import HomeAssistantError

        from custom_components.hass_dyson.services import _handle_cancel_sleep_timer

        mock_coordinator = MagicMock()
        mock_coordinator.serial_number = "TEST123"
        mock_device = MagicMock()
        mock_device.set_sleep_timer = AsyncMock(
            side_effect=RuntimeError("Command failed")
        )
        mock_coordinator.device = mock_device
        mock_coordinator.async_request_refresh = AsyncMock()
        mock_get_coord.return_value = mock_coordinator

        mock_hass = MagicMock()
        mock_call = MagicMock()
        mock_call.data = {"device_id": "test_device"}

        with pytest.raises(HomeAssistantError, match="Failed to cancel sleep timer"):
            await _handle_cancel_sleep_timer(mock_hass, mock_call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_reset_filter_hepa_command(self, mock_get_coord):
        """Test reset filter HEPA command execution."""
        from custom_components.hass_dyson.services import _handle_reset_filter

        mock_coordinator = MagicMock()
        mock_coordinator.serial_number = "TEST123"
        mock_device = MagicMock()
        mock_device.reset_hepa_filter_life = AsyncMock()
        mock_coordinator.device = mock_device
        mock_get_coord.return_value = mock_coordinator

        mock_hass = MagicMock()
        mock_call = MagicMock()
        mock_call.data = {"device_id": "test_device", "filter_type": "hepa"}

        await _handle_reset_filter(mock_hass, mock_call)

        mock_device.reset_hepa_filter_life.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_reset_filter_carbon_command(self, mock_get_coord):
        """Test reset filter carbon command execution."""
        from custom_components.hass_dyson.services import _handle_reset_filter

        mock_coordinator = MagicMock()
        mock_coordinator.serial_number = "TEST123"
        mock_device = MagicMock()
        mock_device.reset_carbon_filter_life = AsyncMock()
        mock_coordinator.device = mock_device
        mock_get_coord.return_value = mock_coordinator

        mock_hass = MagicMock()
        mock_call = MagicMock()
        mock_call.data = {"device_id": "test_device", "filter_type": "carbon"}

        await _handle_reset_filter(mock_hass, mock_call)

        mock_device.reset_carbon_filter_life.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_reset_filter_command_failure(self, mock_get_coord):
        """Test reset filter handles command failure."""
        from homeassistant.exceptions import HomeAssistantError

        from custom_components.hass_dyson.services import _handle_reset_filter

        mock_coordinator = MagicMock()
        mock_coordinator.serial_number = "TEST123"
        mock_device = MagicMock()
        mock_device.reset_hepa_filter_life = AsyncMock(
            side_effect=RuntimeError("Command failed")
        )
        mock_coordinator.device = mock_device
        mock_get_coord.return_value = mock_coordinator

        mock_hass = MagicMock()
        mock_call = MagicMock()
        mock_call.data = {"device_id": "test_device", "filter_type": "hepa"}

        # Should raise HomeAssistantError
        with pytest.raises(HomeAssistantError, match="Failed to reset hepa filter"):
            await _handle_reset_filter(mock_hass, mock_call)

        mock_device.reset_hepa_filter_life.assert_called_once()


class TestUtilityFunctions:
    """Test utility functions for data conversion and processing."""

    def test_convert_to_string_with_value_attribute(self):
        """Test _convert_to_string handles objects with value attribute."""

        class MockEnum:
            def __init__(self, value):
                self.value = value

        obj = MockEnum("test_value")
        result = _convert_to_string(obj)
        assert result == "test_value"

    def test_convert_to_string_without_value_attribute(self):
        """Test _convert_to_string handles regular objects."""
        result = _convert_to_string("simple_string")
        assert result == "simple_string"

        result = _convert_to_string(42)
        assert result == "42"

        result = _convert_to_string(None)
        assert result == "None"

    def test_decrypt_mqtt_credentials_missing_connected_config(self):
        """Test MQTT credential decryption with missing connected_configuration."""
        mock_cloud_client = MagicMock()
        mock_device = MagicMock()
        mock_device.connected_configuration = None
        mock_device.serial_number = "TEST123"

        result = _decrypt_device_mqtt_credentials(mock_cloud_client, mock_device)

        assert result == ""

    def test_decrypt_mqtt_credentials_missing_mqtt_obj(self):
        """Test MQTT credential decryption with missing mqtt object."""
        mock_cloud_client = MagicMock()
        mock_device = MagicMock()
        mock_connected_config = MagicMock()
        mock_connected_config.mqtt = None
        mock_device.connected_configuration = mock_connected_config
        mock_device.serial_number = "TEST123"

        result = _decrypt_device_mqtt_credentials(mock_cloud_client, mock_device)

        assert result == ""

    def test_decrypt_mqtt_credentials_missing_credentials(self):
        """Test MQTT credential decryption with missing local_broker_credentials."""
        mock_cloud_client = MagicMock()
        mock_device = MagicMock()
        mock_connected_config = MagicMock()
        mock_mqtt_obj = MagicMock()
        mock_mqtt_obj.local_broker_credentials = ""
        mock_connected_config.mqtt = mock_mqtt_obj
        mock_device.connected_configuration = mock_connected_config
        mock_device.serial_number = "TEST123"

        result = _decrypt_device_mqtt_credentials(mock_cloud_client, mock_device)

        assert result == ""

    def test_decrypt_mqtt_credentials_decrypt_error(self):
        """Test MQTT credential decryption handles decryption errors."""
        mock_cloud_client = MagicMock()
        mock_cloud_client.decrypt_local_credentials = MagicMock(
            side_effect=ValueError("Decryption failed")
        )

        mock_device = MagicMock()
        mock_connected_config = MagicMock()
        mock_mqtt_obj = MagicMock()
        mock_mqtt_obj.local_broker_credentials = "encrypted_data"
        mock_connected_config.mqtt = mock_mqtt_obj
        mock_device.connected_configuration = mock_connected_config
        mock_device.serial_number = "TEST123"

        result = _decrypt_device_mqtt_credentials(mock_cloud_client, mock_device)

        assert result == ""

    def test_decrypt_mqtt_credentials_attribute_error(self):
        """Test MQTT credential decryption handles attribute errors."""
        mock_cloud_client = MagicMock()
        # decrypt_local_credentials raises AttributeError
        mock_cloud_client.decrypt_local_credentials = MagicMock(
            side_effect=AttributeError("Missing attribute")
        )

        mock_device = MagicMock()
        mock_connected_config = MagicMock()
        mock_mqtt_obj = MagicMock()
        mock_mqtt_obj.local_broker_credentials = "encrypted_data"
        mock_connected_config.mqtt = mock_mqtt_obj
        mock_device.connected_configuration = mock_connected_config
        mock_device.serial_number = "TEST123"

        result = _decrypt_device_mqtt_credentials(mock_cloud_client, mock_device)

        assert result == ""

    def test_decrypt_mqtt_credentials_unexpected_error(self):
        """Test MQTT credential decryption handles unexpected errors."""
        mock_cloud_client = MagicMock()
        mock_cloud_client.decrypt_local_credentials = MagicMock(
            side_effect=RuntimeError("Unexpected error")
        )

        mock_device = MagicMock()
        mock_connected_config = MagicMock()
        mock_mqtt_obj = MagicMock()
        mock_mqtt_obj.local_broker_credentials = "encrypted_data"
        mock_connected_config.mqtt = mock_mqtt_obj
        mock_device.connected_configuration = mock_connected_config
        mock_device.serial_number = "TEST123"

        result = _decrypt_device_mqtt_credentials(mock_cloud_client, mock_device)

        assert result == ""


class TestServiceRegistration:
    """Test service registration and availability logic."""

    @pytest.mark.asyncio
    @patch(
        "custom_components.hass_dyson.services._get_device_categories_for_coordinator"
    )
    async def test_register_services_for_ec_category(self, mock_get_categories):
        """Test service registration for ec (Environment Cleaner) category."""
        from custom_components.hass_dyson.services import (
            async_register_device_services_for_coordinator,
        )

        mock_get_categories.return_value = ["ec"]

        mock_hass = MagicMock()
        mock_hass.services = MagicMock()
        mock_hass.services.has_service = MagicMock(return_value=False)
        mock_hass.services.async_register = (
            MagicMock()
        )  # Synchronous mock for compatibility

        mock_coordinator = MagicMock()
        mock_coordinator.device_capabilities = []  # No capabilities, fall back to categories

        await async_register_device_services_for_coordinator(
            mock_hass, mock_coordinator
        )

        # Verify services were registered (has_service was called)
        assert mock_hass.services.has_service.called

    @pytest.mark.asyncio
    async def test_register_cloud_services_idempotent(self):
        """Test cloud services registration is idempotent."""
        from custom_components.hass_dyson.services import async_setup_cloud_services

        mock_hass = MagicMock()
        mock_hass.services = MagicMock()
        mock_hass.services.has_service = MagicMock(return_value=True)
        mock_hass.services.async_register = MagicMock()

        # Call twice
        await async_setup_cloud_services(mock_hass)
        await async_setup_cloud_services(mock_hass)

        # Should check if service exists each time
        assert mock_hass.services.has_service.called
        mock_hass.services.async_register = AsyncMock()

        # Should not register if services already exist
        await async_setup_cloud_services(mock_hass)

        # Verify no registration occurred
        mock_hass.services.async_register.assert_not_called()
