"""Test services module for Dyson integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.service import SupportsResponse

from custom_components.hass_dyson.const import (
    DOMAIN,
    SERVICE_GET_CLOUD_DEVICES,
    SERVICE_REFRESH_ACCOUNT_DATA,
)
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
from custom_components.hass_dyson.services import (
    SERVICE_CANCEL_SLEEP_TIMER_SCHEMA,
    SERVICE_GET_CLOUD_DEVICES_SCHEMA,
    SERVICE_REFRESH_ACCOUNT_DATA_SCHEMA,
    SERVICE_RESET_FILTER_SCHEMA,
    SERVICE_SCHEDULE_OPERATION_SCHEMA,
    SERVICE_SET_OSCILLATION_ANGLES_SCHEMA,
    SERVICE_SET_SLEEP_TIMER_SCHEMA,
    _find_cloud_coordinators,
    _get_coordinator_from_device_id,
    _handle_cancel_sleep_timer,
    _handle_get_cloud_devices,
    _handle_reset_filter,
    _handle_schedule_operation,
    _handle_set_oscillation_angles,
    _handle_set_sleep_timer,
    async_handle_refresh_account_data,
    async_remove_services,
    async_setup_cloud_services,
    async_setup_services,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    hass.services = MagicMock()
    # async_register and async_remove return None, not coroutines
    hass.services.async_register = MagicMock()
    hass.services.async_remove = MagicMock()
    hass.services.has_service = MagicMock(return_value=True)
    return hass


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
    coordinator.serial_number = "TEST-SERIAL-123"
    coordinator.device = MagicMock()
    coordinator.device.set_sleep_timer = AsyncMock()
    coordinator.device.set_oscillation_angles = AsyncMock()
    coordinator.device.reset_hepa_filter_life = AsyncMock()
    coordinator.device.reset_carbon_filter_life = AsyncMock()
    coordinator.async_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def mock_device_registry():
    """Create a mock device registry."""
    device_registry = MagicMock()
    return device_registry


class TestServiceSchemas:
    """Test service schema validation."""

    def test_set_sleep_timer_schema_valid(self):
        """Test valid sleep timer schema."""
        valid_data = {"device_id": "test-device", "minutes": 30}
        result = SERVICE_SET_SLEEP_TIMER_SCHEMA(valid_data)
        assert result == valid_data

    def test_set_sleep_timer_schema_invalid_minutes(self):
        """Test invalid minutes in sleep timer schema."""
        invalid_data = {"device_id": "test-device", "minutes": 9999}
        with pytest.raises(vol.Invalid):
            SERVICE_SET_SLEEP_TIMER_SCHEMA(invalid_data)

    def test_cancel_sleep_timer_schema_valid(self):
        """Test valid cancel sleep timer schema."""
        valid_data = {"device_id": "test-device"}
        result = SERVICE_CANCEL_SLEEP_TIMER_SCHEMA(valid_data)
        assert result == valid_data

    def test_schedule_operation_schema_valid(self):
        """Test valid schedule operation schema."""
        valid_data = {
            "device_id": "test-device",
            "operation": "turn_on",
            "schedule_time": "2023-01-01T12:00:00Z",
            "parameters": "{}",
        }
        result = SERVICE_SCHEDULE_OPERATION_SCHEMA(valid_data)
        assert result == valid_data

    def test_schedule_operation_schema_invalid_operation(self):
        """Test invalid operation in schedule schema."""
        invalid_data = {
            "device_id": "test-device",
            "operation": "invalid_op",
            "schedule_time": "2023-01-01T12:00:00Z",
        }
        with pytest.raises(vol.Invalid):
            SERVICE_SCHEDULE_OPERATION_SCHEMA(invalid_data)

    def test_set_oscillation_angles_schema_valid(self):
        """Test valid oscillation angles schema."""
        valid_data = {"device_id": "test-device", "lower_angle": 45, "upper_angle": 315}
        result = SERVICE_SET_OSCILLATION_ANGLES_SCHEMA(valid_data)
        assert result == valid_data

    def test_set_oscillation_angles_schema_invalid_range(self):
        """Test invalid angle range in oscillation schema."""
        invalid_data = {
            "device_id": "test-device",
            "lower_angle": 45,
            "upper_angle": 500,
        }
        with pytest.raises(vol.Invalid):
            SERVICE_SET_OSCILLATION_ANGLES_SCHEMA(invalid_data)

    def test_fetch_account_data_schema_valid(self):
        """Test valid fetch account data schema."""
        valid_data = {"device_id": "test-device"}
        result = SERVICE_REFRESH_ACCOUNT_DATA_SCHEMA(valid_data)
        assert result == valid_data

    def test_fetch_account_data_schema_no_device(self):
        """Test fetch account data schema without device_id."""
        valid_data = {}
        result = SERVICE_REFRESH_ACCOUNT_DATA_SCHEMA(valid_data)
        assert result == valid_data

    def test_reset_filter_schema_valid(self):
        """Test valid reset filter schema."""
        valid_data = {"device_id": "test-device", "filter_type": "hepa"}
        result = SERVICE_RESET_FILTER_SCHEMA(valid_data)
        assert result == valid_data

    def test_reset_filter_schema_invalid_type(self):
        """Test invalid filter type in reset filter schema."""
        invalid_data = {"device_id": "test-device", "filter_type": "invalid_filter"}
        with pytest.raises(vol.Invalid):
            SERVICE_RESET_FILTER_SCHEMA(invalid_data)


class TestSetSleepTimer:
    """Test set sleep timer service handler."""

    @pytest.mark.asyncio
    async def test_handle_set_sleep_timer_success(self, mock_hass, mock_coordinator):
        """Test successful sleep timer setting."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device", "minutes": 30}

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ) as mock_get_coord:
            # Act
            await _handle_set_sleep_timer(mock_hass, call)

            # Assert
            mock_get_coord.assert_called_once_with(mock_hass, "test-device")
            mock_coordinator.device.set_sleep_timer.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_handle_set_sleep_timer_device_not_found(self, mock_hass):
        """Test sleep timer setting with device not found."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device", "minutes": 30}

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=None,
        ):
            # Act & Assert
            with pytest.raises(
                ServiceValidationError, match="Device test-device not found"
            ):
                await _handle_set_sleep_timer(mock_hass, call)

    @pytest.mark.asyncio
    async def test_handle_set_sleep_timer_no_device(self, mock_hass, mock_coordinator):
        """Test sleep timer setting with coordinator but no device."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device", "minutes": 30}
        mock_coordinator.device = None

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act & Assert
            with pytest.raises(
                ServiceValidationError, match="Device test-device not found"
            ):
                await _handle_set_sleep_timer(mock_hass, call)

    @pytest.mark.asyncio
    async def test_handle_set_sleep_timer_device_error(
        self, mock_hass, mock_coordinator
    ):
        """Test sleep timer setting with device error."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device", "minutes": 30}
        mock_coordinator.device.set_sleep_timer.side_effect = Exception("Device error")

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act & Assert
            with pytest.raises(HomeAssistantError, match="Failed to set sleep timer"):
                await _handle_set_sleep_timer(mock_hass, call)


class TestCancelSleepTimer:
    """Test cancel sleep timer service handler."""

    @pytest.mark.asyncio
    async def test_handle_cancel_sleep_timer_success(self, mock_hass, mock_coordinator):
        """Test successful sleep timer cancellation."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device"}

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act
            await _handle_cancel_sleep_timer(mock_hass, call)

            # Assert
            mock_coordinator.device.set_sleep_timer.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_handle_cancel_sleep_timer_device_error(
        self, mock_hass, mock_coordinator
    ):
        """Test sleep timer cancellation with device error."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device"}
        mock_coordinator.device.set_sleep_timer.side_effect = Exception("Device error")

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act & Assert
            with pytest.raises(
                HomeAssistantError, match="Failed to cancel sleep timer"
            ):
                await _handle_cancel_sleep_timer(mock_hass, call)


class TestScheduleOperation:
    """Test schedule operation service handler."""

    @pytest.mark.asyncio
    async def test_handle_schedule_operation_success(self, mock_hass, mock_coordinator):
        """Test successful operation scheduling."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {
            "device_id": "test-device",
            "operation": "turn_on",
            "schedule_time": "2023-01-01T12:00:00Z",
            "parameters": '{"speed": 5}',
        }

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ) as mock_get_coord:
            with patch("custom_components.hass_dyson.services._LOGGER") as mock_logger:
                # Act
                await _handle_schedule_operation(mock_hass, call)

                # Assert
                mock_get_coord.assert_called_once_with(mock_hass, "test-device")
                mock_logger.warning.assert_called_once()
                # Check that the warning was called with the expected format string and arguments
                call_args = mock_logger.warning.call_args[0]
                assert (
                    call_args[0]
                    == "Scheduled operation '%s' for device %s at %s with parameters %s - Note: Scheduling is experimental and not yet fully implemented"
                )
                assert call_args[1] == "turn_on"

    @pytest.mark.asyncio
    async def test_handle_schedule_operation_no_parameters(
        self, mock_hass, mock_coordinator
    ):
        """Test operation scheduling without parameters."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {
            "device_id": "test-device",
            "operation": "turn_off",
            "schedule_time": "2023-01-01T12:00:00Z",
        }

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            with patch("custom_components.hass_dyson.services._LOGGER") as mock_logger:
                # Act
                await _handle_schedule_operation(mock_hass, call)

                # Assert
                mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_schedule_operation_invalid_time(
        self, mock_hass, mock_coordinator
    ):
        """Test operation scheduling with invalid time format."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {
            "device_id": "test-device",
            "operation": "turn_on",
            "schedule_time": "invalid-time",
        }

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act & Assert
            with pytest.raises(ServiceValidationError, match="Invalid schedule time"):
                await _handle_schedule_operation(mock_hass, call)

    @pytest.mark.asyncio
    async def test_handle_schedule_operation_invalid_json(
        self, mock_hass, mock_coordinator
    ):
        """Test operation scheduling with invalid JSON parameters."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {
            "device_id": "test-device",
            "operation": "turn_on",
            "schedule_time": "2023-01-01T12:00:00Z",
            "parameters": "invalid-json",
        }

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act & Assert
            with pytest.raises(ServiceValidationError, match="Invalid schedule time"):
                await _handle_schedule_operation(mock_hass, call)


class TestSetOscillationAngles:
    """Test set oscillation angles service handler."""

    @pytest.mark.asyncio
    async def test_handle_set_oscillation_angles_success(
        self, mock_hass, mock_coordinator
    ):
        """Test successful oscillation angles setting."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device", "lower_angle": 45, "upper_angle": 315}

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act
            await _handle_set_oscillation_angles(mock_hass, call)

            # Assert
            mock_coordinator.device.set_oscillation_angles.assert_called_once_with(
                45, 315
            )

    @pytest.mark.asyncio
    async def test_handle_set_oscillation_angles_invalid_range(
        self, mock_hass, mock_coordinator
    ):
        """Test oscillation angles setting with invalid angle range."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device", "lower_angle": 200, "upper_angle": 100}

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act & Assert
            with pytest.raises(
                ServiceValidationError,
                match="Lower angle must be less than upper angle",
            ):
                await _handle_set_oscillation_angles(mock_hass, call)

    @pytest.mark.asyncio
    async def test_handle_set_oscillation_angles_device_error(
        self, mock_hass, mock_coordinator
    ):
        """Test oscillation angles setting with device error."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device", "lower_angle": 45, "upper_angle": 315}
        mock_coordinator.device.set_oscillation_angles.side_effect = Exception(
            "Device error"
        )

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act & Assert
            with pytest.raises(
                HomeAssistantError, match="Failed to set oscillation angles"
            ):
                await _handle_set_oscillation_angles(mock_hass, call)


class TestFetchAccountData:
    """Test fetch account data service handler."""

    @pytest.mark.asyncio
    async def test_handle_fetch_account_data_specific_device(
        self, mock_hass, mock_coordinator
    ):
        """Test fetching account data for specific device."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device"}

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act
            await async_handle_refresh_account_data(mock_hass, call)

            # Assert
            mock_coordinator.async_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_fetch_account_data_all_devices(self, mock_hass):
        """Test fetching account data for all devices."""
        # Arrange
        mock_coordinator1 = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coordinator1.serial_number = "DEVICE-001"
        mock_coordinator1.async_refresh = AsyncMock()

        mock_coordinator2 = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coordinator2.serial_number = "DEVICE-002"
        mock_coordinator2.async_refresh = AsyncMock()

        mock_hass.data[DOMAIN] = {
            "entry1": mock_coordinator1,
            "entry2": mock_coordinator2,
            "entry3": "not_a_coordinator",  # Should be ignored
        }

        call = MagicMock(spec=ServiceCall)
        call.data = {}

        # Act
        await async_handle_refresh_account_data(mock_hass, call)

        # Assert
        mock_coordinator1.async_refresh.assert_called_once()
        mock_coordinator2.async_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_fetch_account_data_device_not_found(self, mock_hass):
        """Test fetching account data for non-existent device."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device"}

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=None,
        ):
            # Act & Assert
            with pytest.raises(
                ServiceValidationError, match="Device test-device not found"
            ):
                await async_handle_refresh_account_data(mock_hass, call)

    @pytest.mark.asyncio
    async def test_handle_fetch_account_data_device_error(
        self, mock_hass, mock_coordinator
    ):
        """Test fetching account data with device error."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device"}
        mock_coordinator.async_refresh.side_effect = Exception("Refresh error")

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act & Assert
            with pytest.raises(
                HomeAssistantError, match="Failed to refresh account data"
            ):
                await async_handle_refresh_account_data(mock_hass, call)

    @pytest.mark.asyncio
    async def test_handle_fetch_account_data_all_devices_with_errors(self, mock_hass):
        """Test fetching account data for all devices with some errors."""
        # Arrange
        mock_coordinator1 = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coordinator1.serial_number = "DEVICE-001"
        mock_coordinator1.async_refresh = AsyncMock()

        mock_coordinator2 = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coordinator2.serial_number = "DEVICE-002"
        mock_coordinator2.async_refresh = AsyncMock(
            side_effect=Exception("Device error")
        )

        mock_hass.data[DOMAIN] = {
            "entry1": mock_coordinator1,
            "entry2": mock_coordinator2,
        }

        call = MagicMock(spec=ServiceCall)
        call.data = {}

        with patch("custom_components.hass_dyson.services._LOGGER") as mock_logger:
            # Act
            await async_handle_refresh_account_data(mock_hass, call)

            # Assert
            mock_coordinator1.async_refresh.assert_called_once()
            mock_coordinator2.async_refresh.assert_called_once()
            mock_logger.error.assert_called_once()


class TestResetFilter:
    """Test reset filter service handler."""

    @pytest.mark.asyncio
    async def test_handle_reset_filter_hepa(self, mock_hass, mock_coordinator):
        """Test HEPA filter reset."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device", "filter_type": "hepa"}

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act
            await _handle_reset_filter(mock_hass, call)

            # Assert
            mock_coordinator.device.reset_hepa_filter_life.assert_called_once()
            mock_coordinator.device.reset_carbon_filter_life.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_reset_filter_carbon(self, mock_hass, mock_coordinator):
        """Test carbon filter reset."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device", "filter_type": "carbon"}

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act
            await _handle_reset_filter(mock_hass, call)

            # Assert
            mock_coordinator.device.reset_carbon_filter_life.assert_called_once()
            mock_coordinator.device.reset_hepa_filter_life.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_reset_filter_both(self, mock_hass, mock_coordinator):
        """Test both filters reset."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device", "filter_type": "both"}

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act
            await _handle_reset_filter(mock_hass, call)

            # Assert
            mock_coordinator.device.reset_hepa_filter_life.assert_called_once()
            mock_coordinator.device.reset_carbon_filter_life.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_reset_filter_device_error(self, mock_hass, mock_coordinator):
        """Test filter reset with device error."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device", "filter_type": "hepa"}
        mock_coordinator.device.reset_hepa_filter_life.side_effect = Exception(
            "Device error"
        )

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act & Assert
            with pytest.raises(HomeAssistantError, match="Failed to reset hepa filter"):
                await _handle_reset_filter(mock_hass, call)


class TestServiceManagement:
    """Test service setup and removal."""

    @pytest.mark.asyncio
    async def test_async_setup_services(self, mock_hass):
        """Test service setup."""
        # Configure mock to show services are not yet registered
        mock_hass.services.has_service = MagicMock(return_value=False)

        # Act
        await async_setup_services(mock_hass)

        # Assert
        # Should register 2 cloud services when no devices are configured
        assert mock_hass.services.async_register.call_count == 2

        # Verify cloud services are registered
        registered_services = [
            call[0][1] for call in mock_hass.services.async_register.call_args_list
        ]
        assert "get_cloud_devices" in registered_services
        assert "refresh_account_data" in registered_services

    @pytest.mark.asyncio
    async def test_async_remove_services(self, mock_hass):
        """Test service removal."""
        # Act
        await async_remove_services(mock_hass)

        # Assert
        # Should check for and remove 7 services (including get_cloud_devices)
        assert mock_hass.services.has_service.call_count == 7
        assert mock_hass.services.async_remove.call_count == 7

    @pytest.mark.asyncio
    async def test_async_setup_cloud_services_registration_details(self, mock_hass):
        """Test detailed cloud services registration behavior."""
        # Configure mock to show services are not yet registered
        mock_hass.services.has_service = MagicMock(return_value=False)

        # Act
        await async_setup_cloud_services(mock_hass)

        # Assert
        # Should register 2 cloud services
        assert mock_hass.services.async_register.call_count == 2

        # Get all the registration calls
        calls = mock_hass.services.async_register.call_args_list

        # First call should be get_cloud_devices with supports_response
        first_call = calls[0]
        assert first_call[0][0] == DOMAIN  # domain
        assert first_call[0][1] == SERVICE_GET_CLOUD_DEVICES  # service name
        assert first_call[1]["supports_response"] == SupportsResponse.OPTIONAL

        # Second call should be refresh_account_data without supports_response
        second_call = calls[1]
        assert second_call[0][0] == DOMAIN  # domain
        assert second_call[0][1] == SERVICE_REFRESH_ACCOUNT_DATA  # service name
        assert (
            "supports_response" not in second_call[1]
        )  # No supports_response for this service


class TestGetCoordinatorFromDeviceId:
    """Test _get_coordinator_from_device_id helper function."""

    @pytest.mark.asyncio
    async def test_get_coordinator_success(self, mock_hass, mock_coordinator):
        """Test successful coordinator retrieval."""
        # Arrange
        device_id = "test-device-id"
        device_entry = MagicMock()
        device_entry.config_entries = {"config-entry-1"}
        mock_hass.data[DOMAIN]["config-entry-1"] = mock_coordinator

        with patch("custom_components.hass_dyson.services.dr.async_get") as mock_dr_get:
            mock_device_registry = MagicMock()
            mock_device_registry.async_get.return_value = device_entry
            mock_dr_get.return_value = mock_device_registry

            # Act
            result = await _get_coordinator_from_device_id(mock_hass, device_id)

            # Assert
            assert result == mock_coordinator
            mock_dr_get.assert_called_once_with(mock_hass)
            mock_device_registry.async_get.assert_called_once_with(device_id)

    @pytest.mark.asyncio
    async def test_get_coordinator_device_not_found(self, mock_hass):
        """Test coordinator retrieval with device not found."""
        # Arrange
        device_id = "test-device-id"

        with patch("custom_components.hass_dyson.services.dr.async_get") as mock_dr_get:
            mock_device_registry = MagicMock()
            mock_device_registry.async_get.return_value = None
            mock_dr_get.return_value = mock_device_registry

            # Act
            result = await _get_coordinator_from_device_id(mock_hass, device_id)

            # Assert
            assert result is None

    @pytest.mark.asyncio
    async def test_get_coordinator_no_matching_config_entry(self, mock_hass):
        """Test coordinator retrieval with no matching config entry."""
        # Arrange
        device_id = "test-device-id"
        device_entry = MagicMock()
        device_entry.config_entries = {"config-entry-1"}
        mock_hass.data[DOMAIN] = {}  # No coordinators

        with patch("custom_components.hass_dyson.services.dr.async_get") as mock_dr_get:
            mock_device_registry = MagicMock()
            mock_device_registry.async_get.return_value = device_entry
            mock_dr_get.return_value = mock_device_registry

            # Act
            result = await _get_coordinator_from_device_id(mock_hass, device_id)

            # Assert
            assert result is None

    @pytest.mark.asyncio
    async def test_get_coordinator_wrong_type(self, mock_hass):
        """Test coordinator retrieval with wrong coordinator type."""
        # Arrange
        device_id = "test-device-id"
        device_entry = MagicMock()
        device_entry.config_entries = {"config-entry-1"}
        mock_hass.data[DOMAIN]["config-entry-1"] = "not_a_coordinator"

        with patch("custom_components.hass_dyson.services.dr.async_get") as mock_dr_get:
            mock_device_registry = MagicMock()
            mock_device_registry.async_get.return_value = device_entry
            mock_dr_get.return_value = mock_device_registry

            # Act
            result = await _get_coordinator_from_device_id(mock_hass, device_id)

            # Assert
            assert result is None


class TestServicesCoverage:
    """Additional tests to improve services coverage."""

    @pytest.mark.asyncio
    async def test_cancel_sleep_timer_with_logging(self, mock_hass, mock_coordinator):
        """Test cancel sleep timer success with logging verification."""
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device"}

        with (
            patch(
                "custom_components.hass_dyson.services._get_coordinator_from_device_id",
                return_value=mock_coordinator,
            ),
            patch("custom_components.hass_dyson.services._LOGGER") as mock_logger,
        ):
            await _handle_cancel_sleep_timer(mock_hass, call)

            # Verify the success logging (line 90)
            mock_logger.info.assert_called_once_with(
                "Cancelled sleep timer for device %s", mock_coordinator.serial_number
            )

    @pytest.mark.asyncio
    async def test_set_oscillation_angles_with_logging(
        self, mock_hass, mock_coordinator
    ):
        """Test set oscillation angles success with logging verification."""
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device", "lower_angle": 30, "upper_angle": 90}

        with (
            patch(
                "custom_components.hass_dyson.services._get_coordinator_from_device_id",
                return_value=mock_coordinator,
            ),
            patch("custom_components.hass_dyson.services._LOGGER") as mock_logger,
        ):
            await _handle_set_oscillation_angles(mock_hass, call)

            # Verify the success logging (line 149)
            mock_logger.info.assert_called_once_with(
                "Set oscillation angles %d°-%d° for device %s",
                30,
                90,
                mock_coordinator.serial_number,
            )

    @pytest.mark.asyncio
    async def test_fetch_account_data_with_device_error_logging(
        self, mock_hass, mock_coordinator
    ):
        """Test fetch account data with device error to cover error logging."""
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device"}

        # Make the device fetch fail
        mock_coordinator.async_refresh.side_effect = Exception("Network error")

        with (
            patch(
                "custom_components.hass_dyson.services._get_coordinator_from_device_id",
                return_value=mock_coordinator,
            ),
            patch("custom_components.hass_dyson.services._LOGGER") as mock_logger,
        ):
            with pytest.raises(HomeAssistantError):
                await async_handle_refresh_account_data(mock_hass, call)

            # Verify error logging (line 202)
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_async_remove_services_no_services_registered(self, mock_hass):
        """Test remove services when no services are registered."""
        # Mock that services don't exist
        mock_hass.services.has_service.return_value = False

        # This should not call async_remove since services don't exist
        await async_remove_services(mock_hass)

        # Verify no removal calls were made
        mock_hass.services.async_remove.assert_not_called()


class TestCloudDevicesService:
    """Test cloud devices service functionality."""

    def test_get_cloud_devices_schema_valid_with_account(self):
        """Test valid schema with account email."""
        data = {"account_email": "test@example.com", "sanitize": True}
        validated_data = SERVICE_GET_CLOUD_DEVICES_SCHEMA(data)
        assert validated_data["account_email"] == "test@example.com"
        assert validated_data["sanitize"] is True

    def test_get_cloud_devices_schema_valid_no_account(self):
        """Test valid schema without account email."""
        data = {"sanitize": False}
        validated_data = SERVICE_GET_CLOUD_DEVICES_SCHEMA(data)
        assert "account_email" not in validated_data
        assert validated_data["sanitize"] is False

    def test_get_cloud_devices_schema_default_sanitize(self):
        """Test schema with default sanitize value."""
        data = {}
        validated_data = SERVICE_GET_CLOUD_DEVICES_SCHEMA(data)
        # Schema provides default value for sanitize
        assert validated_data["sanitize"] is False

    @pytest.mark.asyncio
    async def test_find_cloud_coordinators_success(self, mock_hass):
        """Test finding cloud coordinators successfully."""
        # Create mock coordinators
        cloud_coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        cloud_coordinator.config_entry = MagicMock()
        cloud_coordinator.config_entry.data = {
            "discovery_method": "cloud",
            "username": "test@example.com",
        }
        cloud_coordinator.config_entry.entry_id = "entry1"
        cloud_coordinator.device = MagicMock()

        local_coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        local_coordinator.config_entry = MagicMock()
        local_coordinator.config_entry.data = {
            "discovery_method": "manual",
            "username": "local@example.com",
        }

        mock_hass.data = {
            DOMAIN: {
                "entry1": cloud_coordinator,
                "entry2": local_coordinator,
                "non_coordinator": "not_a_coordinator",
            }
        }

        coordinators = _find_cloud_coordinators(mock_hass)

        assert len(coordinators) == 1
        assert coordinators[0]["email"] == "test@example.com"
        assert coordinators[0]["coordinator"] == cloud_coordinator

    @pytest.mark.asyncio
    async def test_find_cloud_coordinators_no_cloud_accounts(self, mock_hass):
        """Test finding cloud coordinators when none exist."""
        mock_hass.data = {DOMAIN: {}}

        coordinators = _find_cloud_coordinators(mock_hass)

        assert len(coordinators) == 0

    @pytest.mark.asyncio
    async def test_handle_get_cloud_devices_success_sanitized(self, mock_hass):
        """Test successful cloud devices retrieval with sanitization."""
        # Create mock coordinator with proper attributes
        mock_coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coordinator.serial_number = "TEST-123"
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.mqtt_prefix = "475"
        mock_coordinator.device.credential = "test-password"
        mock_coordinator._device_capabilities = ["Heating", "VOC"]
        mock_coordinator._device_category = ["ec"]
        mock_coordinator._device_type = "438M"

        call = MagicMock(spec=ServiceCall)
        call.data = {"account_email": "test@example.com", "sanitize": True}

        with patch(
            "custom_components.hass_dyson.services._find_cloud_coordinators",
            return_value=[
                {
                    "email": "test@example.com",
                    "coordinator": mock_coordinator,
                    "config_entry_id": "entry1",
                }
            ],
        ):
            result = await _handle_get_cloud_devices(mock_hass, call)

        assert result["account_email"] == "test@example.com"
        assert result["total_devices"] == 1
        assert result["sanitized"] is True
        assert len(result["devices"]) == 1

        device = result["devices"][0]
        assert device["model"] == "438M"
        assert device["mqtt_topic"] == "475/TEST-123"
        assert device["device_category"] == "ec"
        assert device["device_connection_category"] == "connected"
        assert device["device_capabilities"] == ["Heating", "VOC"]

    @pytest.mark.asyncio
    async def test_handle_get_cloud_devices_success_detailed(self, mock_hass):
        """Test successful cloud devices retrieval with detailed info."""
        mock_coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coordinator.serial_number = "TEST-123"
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.mqtt_prefix = "475"
        mock_coordinator.device.credential = "test-password"
        mock_coordinator._device_capabilities = ["Heating", "VOC"]
        mock_coordinator._device_category = ["ec"]
        mock_coordinator._device_type = "438M"

        call = MagicMock(spec=ServiceCall)
        call.data = {"account_email": "test@example.com", "sanitize": False}

        with patch(
            "custom_components.hass_dyson.services._find_cloud_coordinators",
            return_value=[
                {
                    "email": "test@example.com",
                    "coordinator": mock_coordinator,
                    "config_entry_id": "entry1",
                }
            ],
        ):
            result = await _handle_get_cloud_devices(mock_hass, call)

        assert result["account_email"] == "test@example.com"
        assert result["total_devices"] == 1
        assert result["sanitized"] is False
        assert "summary" in result

        device = result["devices"][0]
        assert "basic_info" in device
        assert "setup_info" in device
        assert device["basic_info"]["serial_number"] == "TEST-123"
        assert device["setup_info"]["local_mqtt_config"]["password"] == "test-password"

    @pytest.mark.asyncio
    async def test_handle_get_cloud_devices_no_cloud_accounts(self, mock_hass):
        """Test helpful response when no cloud accounts found."""
        call = MagicMock(spec=ServiceCall)
        call.data = {"sanitize": False}

        with patch(
            "custom_components.hass_dyson.services._find_cloud_coordinators",
            return_value=[],
        ):
            result = await _handle_get_cloud_devices(mock_hass, call)

        assert (
            result["message"]
            == "No cloud accounts found. Please configure a cloud account first."
        )
        assert result["total_devices"] == 0
        assert result["devices"] == []
        assert "available_setup_methods" in result
        assert result["sanitized"] is False

    @pytest.mark.asyncio
    async def test_handle_get_cloud_devices_account_not_found(self, mock_hass):
        """Test error when specified account not found."""
        mock_coordinator = MagicMock(spec=DysonDataUpdateCoordinator)

        call = MagicMock(spec=ServiceCall)
        call.data = {"account_email": "notfound@example.com", "sanitize": False}

        with patch(
            "custom_components.hass_dyson.services._find_cloud_coordinators",
            return_value=[
                {
                    "email": "test@example.com",
                    "coordinator": mock_coordinator,
                    "config_entry_id": "entry1",
                }
            ],
        ):
            with pytest.raises(ServiceValidationError) as exc_info:
                await _handle_get_cloud_devices(mock_hass, call)

        assert "Account 'notfound@example.com' not found" in str(exc_info.value)
        assert "test@example.com" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handle_get_cloud_devices_use_first_account(self, mock_hass):
        """Test using first account when none specified."""
        mock_coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coordinator.serial_number = "TEST-123"
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.mqtt_prefix = "475"
        mock_coordinator._device_capabilities = []
        mock_coordinator._device_category = ["ec"]
        mock_coordinator._device_type = "438M"

        call = MagicMock(spec=ServiceCall)
        call.data = {"sanitize": True}  # No account_email specified

        with patch(
            "custom_components.hass_dyson.services._find_cloud_coordinators",
            return_value=[
                {
                    "email": "first@example.com",
                    "coordinator": mock_coordinator,
                    "config_entry_id": "entry1",
                },
                {
                    "email": "second@example.com",
                    "coordinator": MagicMock(),
                    "config_entry_id": "entry2",
                },
            ],
        ):
            result = await _handle_get_cloud_devices(mock_hass, call)

        # Should use first account
        assert result["account_email"] == "first@example.com"

    @pytest.mark.asyncio
    async def test_handle_get_cloud_devices_coordinator_error(self, mock_hass):
        """Test error when device coordinator has no device available."""
        mock_coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coordinator.device = None  # No device available

        call = MagicMock(spec=ServiceCall)
        call.data = {"account_email": "test@example.com", "sanitize": False}

        with patch(
            "custom_components.hass_dyson.services._find_cloud_coordinators",
            return_value=[
                {
                    "email": "test@example.com",
                    "coordinator": mock_coordinator,
                    "config_entry_id": "entry1",
                    "type": "device",  # Specify this is a device coordinator
                }
            ],
        ):
            with pytest.raises(HomeAssistantError) as exc_info:
                await _handle_get_cloud_devices(mock_hass, call)

        assert "Device coordinator has no device" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handle_get_cloud_devices_live_api_success(self, mock_hass):
        """Test successful cloud devices retrieval using live API."""
        # Mock config entry with auth token but no active coordinator
        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            "email": "test@example.com",
            "auth_token": "test-auth-token",
            "devices": [{"serial_number": "OLD-123", "name": "Old Device"}],
        }

        call = MagicMock(spec=ServiceCall)
        call.data = {"account_email": "test@example.com", "sanitize": False}

        # Mock live device from API based on real Dyson device structure
        mock_live_device = MagicMock()
        mock_live_device.serial_number = "LIVE-456"
        mock_live_device.name = "Live API Device"
        mock_live_device.category = "ec"
        mock_live_device.type = "438"
        mock_live_device.variant = "M"
        mock_live_device.model = "TP11"
        mock_live_device.connection_category = "lecAndWifi"

        # Mock connected_configuration structure
        mock_firmware = MagicMock()
        mock_firmware.version = "438MPF.00.01.007.0002"
        mock_firmware.capabilities = [
            "AdvanceOscillationDay1",
            "Scheduling",
            "EnvironmentalData",
        ]

        mock_mqtt = MagicMock()
        mock_mqtt.mqtt_root_topic_level = "438M"

        mock_connected_config = MagicMock()
        mock_connected_config.firmware = mock_firmware
        mock_connected_config.mqtt = mock_mqtt

        mock_live_device.connected_configuration = mock_connected_config

        with (
            patch(
                "custom_components.hass_dyson.services._find_cloud_coordinators",
                return_value=[
                    {
                        "email": "test@example.com",
                        "coordinator": None,
                        "config_entry_id": "entry1",
                        "config_entry": mock_config_entry,
                        "type": "config_entry",
                    }
                ],
            ),
            patch(
                "custom_components.hass_dyson.services._fetch_live_cloud_devices",
                return_value=[
                    {
                        "device": mock_live_device,
                        "enhanced_data": {
                            "name": "Live API Device",
                            "product_type": "438M",
                            "device_category": ["ec"],
                            "capabilities": [
                                "AdvanceOscillationDay1",
                                "Scheduling",
                                "EnvironmentalData",
                            ],
                            "mqtt_prefix": "438M",
                            "model": "TP11",
                            "firmware_version": "438MPF.00.01.007.0002",
                            "connection_category": "lecAndWifi",
                            "decrypted_mqtt_password": "decrypted_password_123",
                        },
                    }
                ],
            ),
        ):
            result = await _handle_get_cloud_devices(mock_hass, call)

        # Verify response structure
        assert result["account_email"] == "test@example.com"
        assert result["total_devices"] == 1
        assert result["sanitized"] is False
        assert len(result["devices"]) == 1

        # Verify device data from live API with enhanced extraction
        device = result["devices"][0]
        assert device["serial_number"] == "LIVE-456"
        assert device["name"] == "Live API Device"
        assert device["product_type"] == "438M"  # Constructed from type + variant
        assert device["device_category"] == ["ec"]  # Derived from category
        assert device["capabilities"] == [
            "AdvanceOscillationDay1",
            "Scheduling",
            "EnvironmentalData",
        ]
        assert (
            device["mqtt_prefix"] == "438M"
        )  # From connected_configuration.mqtt.mqtt_root_topic_level
        assert device["model"] == "TP11"
        assert device["firmware_version"] == "438MPF.00.01.007.0002"
        assert device["connection_category"] == "lecAndWifi"
        assert device["setup_status"] == "live_cloud_api"
        # Verify category is no longer in output
        assert "category" not in device
        # Verify MQTT password is included with new name
        assert device["mqtt_password"] == "decrypted_password_123"

    @pytest.mark.asyncio
    async def test_handle_get_cloud_devices_live_api_fallback(self, mock_hass):
        """Test fallback to stored data when live API fails."""
        # Mock config entry with stored devices
        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            "email": "test@example.com",
            "auth_token": "test-auth-token",
            "devices": [
                {
                    "serial_number": "STORED-789",
                    "name": "Stored Device",
                    "product_type": "stored_type",
                }
            ],
        }

        call = MagicMock(spec=ServiceCall)
        call.data = {"account_email": "test@example.com", "sanitize": False}

        with (
            patch(
                "custom_components.hass_dyson.services._find_cloud_coordinators",
                return_value=[
                    {
                        "email": "test@example.com",
                        "coordinator": None,
                        "config_entry_id": "entry1",
                        "config_entry": mock_config_entry,
                        "type": "config_entry",
                    }
                ],
            ),
            patch(
                "custom_components.hass_dyson.services._fetch_live_cloud_devices",
                side_effect=Exception("API connection failed"),
            ),
        ):
            result = await _handle_get_cloud_devices(mock_hass, call)

        # Verify response uses fallback data
        assert result["account_email"] == "test@example.com"
        assert result["total_devices"] == 1
        assert len(result["devices"]) == 1

        # Verify device data from stored config (fallback)
        device = result["devices"][0]
        assert device["serial_number"] == "STORED-789"
        assert device["name"] == "Stored Device"
        assert device["product_type"] == "stored_type"
        assert device["setup_status"] == "stored_in_config"

    @pytest.mark.asyncio
    async def test_device_category_normalization(self, mock_hass):
        """Test that device_category is always normalized to list of strings."""
        # Mock config entry with devices having different device_category formats
        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            "email": "test@example.com",
            "auth_token": "test-auth-token",
            "devices": [
                {"serial_number": "DEV1", "device_category": "ec"},  # string
                {"serial_number": "DEV2", "device_category": ["fan", "heater"]},  # list
                {"serial_number": "DEV3", "device_category": None},  # None
                {"serial_number": "DEV4"},  # missing
            ],
        }

        call = MagicMock(spec=ServiceCall)
        call.data = {"account_email": "test@example.com", "sanitize": False}

        with (
            patch(
                "custom_components.hass_dyson.services._find_cloud_coordinators",
                return_value=[
                    {
                        "email": "test@example.com",
                        "coordinator": None,
                        "config_entry_id": "entry1",
                        "config_entry": mock_config_entry,
                        "type": "config_entry",
                    }
                ],
            ),
            patch(
                "custom_components.hass_dyson.services._fetch_live_cloud_devices",
                side_effect=Exception(
                    "API unavailable"
                ),  # Force fallback to stored data
            ),
        ):
            result = await _handle_get_cloud_devices(mock_hass, call)

        # Verify all device_category fields are normalized to list of strings
        devices = result["devices"]
        assert len(devices) == 4

        assert devices[0]["device_category"] == ["ec"]  # string -> list
        assert devices[1]["device_category"] == ["fan", "heater"]  # list preserved
        assert devices[2]["device_category"] == []  # None -> empty list
        assert devices[3]["device_category"] == []  # missing -> empty list

    @pytest.mark.asyncio
    async def test_device_category_enum_conversion(self, mock_hass):
        """Test that device_category enum values are properly converted to strings."""
        from enum import Enum

        # Create a mock enum like Dyson's DeviceCategory
        class MockDeviceCategory(Enum):
            ENVIRONMENT_CLEANER = "ec"
            FAN = "fan"

        # Mock config entry with devices having enum device_category values
        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            "email": "test@example.com",
            "auth_token": "test-auth-token",
            "devices": [
                {
                    "serial_number": "DEV1",
                    "device_category": MockDeviceCategory.ENVIRONMENT_CLEANER,
                },  # single enum
                {
                    "serial_number": "DEV2",
                    "device_category": [
                        MockDeviceCategory.FAN,
                        MockDeviceCategory.ENVIRONMENT_CLEANER,
                    ],
                },  # list of enums
            ],
        }

        call = MagicMock(spec=ServiceCall)
        call.data = {"account_email": "test@example.com", "sanitize": False}

        # Mock _find_cloud_coordinators to return config entry
        with patch(
            "custom_components.hass_dyson.services._find_cloud_coordinators"
        ) as mock_find:
            mock_find.return_value = [
                {
                    "config_entry": mock_config_entry,
                    "coordinator": None,
                    "email": "test@example.com",
                    "type": "config_entry",
                }
            ]

            # Call service with sanitize=False to get full details
            result = await _handle_get_cloud_devices(mock_hass, call)

            devices = result["devices"]
            assert len(devices) == 2

            # Verify enum values are converted to their string values, not representations
            assert devices[0]["device_category"] == [
                "ec"
            ]  # MockDeviceCategory.ENVIRONMENT_CLEANER.value
            assert devices[1]["device_category"] == [
                "fan",
                "ec",
            ]  # List of enum values converted to strings

    @pytest.mark.asyncio
    async def test_sanitized_output_includes_required_fields(self, mock_hass):
        """Test that sanitized output includes all required fields from design document."""
        # Mock config entry with auth token but no active coordinator
        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            "email": "test@example.com",
            "auth_token": "test-auth-token",
            "devices": [{"serial_number": "TEST-123", "name": "Test Device"}],
        }

        call = MagicMock(spec=ServiceCall)
        call.data = {"account_email": "test@example.com", "sanitize": True}

        # Mock live device from API with all fields
        mock_live_device = MagicMock()
        mock_live_device.serial_number = "TEST-123"
        mock_live_device.name = "Test Device"
        mock_live_device.category = "ec"
        mock_live_device.type = "438"
        mock_live_device.variant = "M"
        mock_live_device.model = "TP11"
        mock_live_device.connection_category = "lecAndWifi"

        # Mock connected_configuration structure
        mock_firmware = MagicMock()
        mock_firmware.capabilities = ["Scheduling", "EnvironmentalData"]

        mock_mqtt = MagicMock()
        mock_mqtt.mqtt_root_topic_level = "438M"

        mock_connected_config = MagicMock()
        mock_connected_config.firmware = mock_firmware
        mock_connected_config.mqtt = mock_mqtt

        mock_live_device.connected_configuration = mock_connected_config

        with (
            patch(
                "custom_components.hass_dyson.services._find_cloud_coordinators",
                return_value=[
                    {
                        "email": "test@example.com",
                        "coordinator": None,
                        "config_entry_id": "entry1",
                        "config_entry": mock_config_entry,
                        "type": "config_entry",
                    }
                ],
            ),
            patch(
                "custom_components.hass_dyson.services._fetch_live_cloud_devices",
                return_value=[
                    {
                        "device": mock_live_device,
                        "enhanced_data": {
                            "name": "Test Device",
                            "product_type": "438M",
                            "device_category": ["ec"],
                            "capabilities": ["Scheduling", "EnvironmentalData"],
                            "mqtt_prefix": "438M",
                            "model": "TP11",
                            "firmware_version": "438MPF.00.01.007.0002",
                            "connection_category": "lecAndWifi",
                            "decrypted_mqtt_password": "decrypted_password_123",
                        },
                    }
                ],
            ),
        ):
            result = await _handle_get_cloud_devices(mock_hass, call)

        # Verify sanitized output includes all required fields from design document
        device = result["devices"][0]
        assert device["serial_number"] == "***HIDDEN***"  # Sanitized
        assert device["model"] == "TP11"  # Model
        assert device["mqtt_prefix"] == "438M"  # MQTT Topic
        assert device["device_category"] == ["ec"]  # Device Category
        assert (
            device["connection_category"] == "lecAndWifi"
        )  # Device Connection Category
        assert device["capabilities"] == [
            "Scheduling",
            "EnvironmentalData",
        ]  # Device Capabilities

        # Verify no sensitive fields are included
        assert "mqtt_password" not in device  # Should not be in sanitized output
        assert "firmware_version" not in device


class TestDecryptDeviceMqttCredentials:
    """Test _decrypt_device_mqtt_credentials helper function."""

    def test_decrypt_device_mqtt_credentials_success(self):
        """Test successful MQTT credentials decryption."""
        from custom_components.hass_dyson.services import (
            _decrypt_device_mqtt_credentials,
        )

        # Arrange
        mock_cloud_client = MagicMock()
        mock_cloud_client.decrypt_local_credentials.return_value = (
            "decrypted_password_123"
        )

        mock_device = MagicMock()
        mock_device.serial_number = "TEST-SERIAL-123"

        # Create nested mock structure for connected_configuration.mqtt.local_broker_credentials
        mock_mqtt = MagicMock()
        mock_mqtt.local_broker_credentials = "encrypted_credentials_data"

        mock_connected_config = MagicMock()
        mock_connected_config.mqtt = mock_mqtt

        mock_device.connected_configuration = mock_connected_config

        # Act
        result = _decrypt_device_mqtt_credentials(mock_cloud_client, mock_device)

        # Assert
        assert result == "decrypted_password_123"
        mock_cloud_client.decrypt_local_credentials.assert_called_once_with(
            "encrypted_credentials_data", "TEST-SERIAL-123"
        )

    def test_decrypt_device_mqtt_credentials_no_connected_config(self):
        """Test MQTT credentials decryption with no connected configuration."""
        from custom_components.hass_dyson.services import (
            _decrypt_device_mqtt_credentials,
        )

        # Arrange
        mock_cloud_client = MagicMock()
        mock_device = MagicMock()
        mock_device.connected_configuration = None

        # Act
        result = _decrypt_device_mqtt_credentials(mock_cloud_client, mock_device)

        # Assert
        assert result == ""
        mock_cloud_client.decrypt_local_credentials.assert_not_called()

    def test_decrypt_device_mqtt_credentials_no_mqtt_config(self):
        """Test MQTT credentials decryption with no MQTT configuration."""
        from custom_components.hass_dyson.services import (
            _decrypt_device_mqtt_credentials,
        )

        # Arrange
        mock_cloud_client = MagicMock()
        mock_device = MagicMock()
        mock_device.serial_number = "TEST-SERIAL-123"

        mock_connected_config = MagicMock()
        mock_connected_config.mqtt = None
        mock_device.connected_configuration = mock_connected_config

        # Act
        result = _decrypt_device_mqtt_credentials(mock_cloud_client, mock_device)

        # Assert
        assert result == ""
        mock_cloud_client.decrypt_local_credentials.assert_not_called()

    def test_decrypt_device_mqtt_credentials_no_credentials(self):
        """Test MQTT credentials decryption with no encrypted credentials."""
        from custom_components.hass_dyson.services import (
            _decrypt_device_mqtt_credentials,
        )

        # Arrange
        mock_cloud_client = MagicMock()
        mock_device = MagicMock()
        mock_device.serial_number = "TEST-SERIAL-123"

        mock_mqtt = MagicMock()
        mock_mqtt.local_broker_credentials = ""

        mock_connected_config = MagicMock()
        mock_connected_config.mqtt = mock_mqtt
        mock_device.connected_configuration = mock_connected_config

        # Act
        result = _decrypt_device_mqtt_credentials(mock_cloud_client, mock_device)

        # Assert
        assert result == ""
        mock_cloud_client.decrypt_local_credentials.assert_not_called()

    def test_decrypt_device_mqtt_credentials_exception_handling(self):
        """Test MQTT credentials decryption with exception."""
        from custom_components.hass_dyson.services import (
            _decrypt_device_mqtt_credentials,
        )

        # Arrange
        mock_cloud_client = MagicMock()
        mock_cloud_client.decrypt_local_credentials.side_effect = Exception(
            "Decryption error"
        )

        mock_device = MagicMock()
        mock_device.serial_number = "TEST-SERIAL-123"

        mock_mqtt = MagicMock()
        mock_mqtt.local_broker_credentials = "encrypted_credentials_data"

        mock_connected_config = MagicMock()
        mock_connected_config.mqtt = mock_mqtt
        mock_device.connected_configuration = mock_connected_config

        # Act
        result = _decrypt_device_mqtt_credentials(mock_cloud_client, mock_device)

        # Assert
        assert result == ""
        mock_cloud_client.decrypt_local_credentials.assert_called_once_with(
            "encrypted_credentials_data", "TEST-SERIAL-123"
        )


class TestConvertToString:
    """Test _convert_to_string helper function."""

    def test_convert_to_string_with_enum(self):
        """Test _convert_to_string with an enum-like object."""
        from custom_components.hass_dyson.services import _convert_to_string

        # Arrange
        mock_enum = MagicMock()
        mock_enum.value = "enum_value_123"

        # Act
        result = _convert_to_string(mock_enum)

        # Assert
        assert result == "enum_value_123"

    def test_convert_to_string_with_regular_object(self):
        """Test _convert_to_string with a regular object."""
        from custom_components.hass_dyson.services import _convert_to_string

        # Arrange
        test_object = "simple_string"

        # Act
        result = _convert_to_string(test_object)

        # Assert
        assert result == "simple_string"

    def test_convert_to_string_with_number(self):
        """Test _convert_to_string with a number."""
        from custom_components.hass_dyson.services import _convert_to_string

        # Act
        result = _convert_to_string(42)

        # Assert
        assert result == "42"


class TestCancelSleepTimerErrorHandling:
    """Test error handling in cancel sleep timer service."""

    @pytest.mark.asyncio
    async def test_cancel_sleep_timer_device_not_found(self, mock_hass):
        """Test cancel sleep timer with device not found."""
        # Arrange
        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id"
        ) as mock_get_coord:
            mock_get_coord.return_value = None

            call_data = {"device_id": "nonexistent"}
            mock_call = MagicMock(spec=ServiceCall)
            mock_call.data = call_data

            # Act & Assert
            with pytest.raises(
                ServiceValidationError, match="Device nonexistent not found"
            ):
                await _handle_cancel_sleep_timer(mock_hass, mock_call)

    @pytest.mark.asyncio
    async def test_cancel_sleep_timer_device_error(self, mock_hass, mock_coordinator):
        """Test cancel sleep timer with device communication error."""
        # Arrange
        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=Exception("Device error")
        )

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id"
        ) as mock_get_coord:
            mock_get_coord.return_value = mock_coordinator

            call_data = {"device_id": "test-id"}
            mock_call = MagicMock(spec=ServiceCall)
            mock_call.data = call_data

            # Act & Assert
            with pytest.raises(
                HomeAssistantError, match="Failed to cancel sleep timer"
            ):
                await _handle_cancel_sleep_timer(mock_hass, mock_call)


class TestScheduleOperationErrorHandling:
    """Test error handling in schedule operation service."""

    @pytest.mark.asyncio
    async def test_schedule_operation_device_not_found(self, mock_hass):
        """Test schedule operation with device not found."""
        # Arrange
        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id"
        ) as mock_get_coord:
            mock_get_coord.return_value = None

            call_data = {
                "device_id": "nonexistent",
                "operation": "start",
                "schedule_time": "2025-01-01T12:00:00Z",
            }
            mock_call = MagicMock(spec=ServiceCall)
            mock_call.data = call_data

            # Act & Assert
            with pytest.raises(
                ServiceValidationError, match="Device nonexistent not found"
            ):
                await _handle_schedule_operation(mock_hass, mock_call)

    @pytest.mark.asyncio
    async def test_schedule_operation_invalid_time_format(
        self, mock_hass, mock_coordinator
    ):
        """Test schedule operation with invalid time format."""
        # Arrange
        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id"
        ) as mock_get_coord:
            mock_get_coord.return_value = mock_coordinator

            call_data = {
                "device_id": "test-id",
                "operation": "start",
                "schedule_time": "invalid-time-format",
            }
            mock_call = MagicMock(spec=ServiceCall)
            mock_call.data = call_data

            # Act & Assert
            with pytest.raises(
                ServiceValidationError,
                match="Invalid schedule time or parameters format",
            ):
                await _handle_schedule_operation(mock_hass, mock_call)


class TestSetOscillationAnglesErrorHandling:
    """Test error handling in set oscillation angles service."""

    @pytest.mark.asyncio
    async def test_set_oscillation_angles_invalid_range(self, mock_hass):
        """Test set oscillation angles with invalid angle range."""
        # Arrange
        call_data = {
            "device_id": "test-id",
            "lower_angle": 45,
            "upper_angle": 30,  # upper angle less than lower angle
        }
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = call_data

        # Act & Assert
        with pytest.raises(
            ServiceValidationError, match="Lower angle must be less than upper angle"
        ):
            await _handle_set_oscillation_angles(mock_hass, mock_call)

    @pytest.mark.asyncio
    async def test_set_oscillation_angles_device_not_found(self, mock_hass):
        """Test set oscillation angles with device not found."""
        # Arrange
        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id"
        ) as mock_get_coord:
            mock_get_coord.return_value = None

            call_data = {
                "device_id": "nonexistent",
                "lower_angle": 10,
                "upper_angle": 30,
            }
            mock_call = MagicMock(spec=ServiceCall)
            mock_call.data = call_data

            # Act & Assert
            with pytest.raises(
                ServiceValidationError, match="Device nonexistent not found"
            ):
                await _handle_set_oscillation_angles(mock_hass, mock_call)


class TestResetFilterErrorHandling:
    """Test error handling in reset filter service."""

    @pytest.mark.asyncio
    async def test_reset_filter_device_not_found(self, mock_hass):
        """Test reset filter with device not found."""
        # Arrange
        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id"
        ) as mock_get_coord:
            mock_get_coord.return_value = None

            call_data = {"device_id": "nonexistent", "filter_type": "hepa"}
            mock_call = MagicMock(spec=ServiceCall)
            mock_call.data = call_data

            # Act & Assert
            with pytest.raises(
                ServiceValidationError, match="Device nonexistent not found"
            ):
                await _handle_reset_filter(mock_hass, mock_call)


class TestSetSleepTimerErrorHandling:
    """Test error handling in set sleep timer service."""

    @pytest.mark.asyncio
    async def test_set_sleep_timer_device_not_found(self, mock_hass):
        """Test set sleep timer with device not found."""
        # Arrange
        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id"
        ) as mock_get_coord:
            mock_get_coord.return_value = None

            call_data = {"device_id": "nonexistent", "minutes": 60}
            mock_call = MagicMock(spec=ServiceCall)
            mock_call.data = call_data

            # Act & Assert
            with pytest.raises(
                ServiceValidationError, match="Device nonexistent not found"
            ):
                await _handle_set_sleep_timer(mock_hass, mock_call)

    @pytest.mark.asyncio
    async def test_set_sleep_timer_device_error(self, mock_hass, mock_coordinator):
        """Test set sleep timer with device communication error."""
        # Arrange
        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=Exception("Device error")
        )

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id"
        ) as mock_get_coord:
            mock_get_coord.return_value = mock_coordinator

            call_data = {"device_id": "test-id", "minutes": 60}
            mock_call = MagicMock(spec=ServiceCall)
            mock_call.data = call_data

            # Act & Assert
            with pytest.raises(HomeAssistantError, match="Failed to set sleep timer"):
                await _handle_set_sleep_timer(mock_hass, mock_call)


class TestResetFilterAdvancedErrorHandling:
    """Test error handling in reset filter service."""

    @pytest.mark.asyncio
    async def test_reset_filter_device_error(self, mock_hass, mock_coordinator):
        """Test reset filter with device communication error."""
        # Arrange
        mock_coordinator.device.reset_hepa_filter_life = AsyncMock(
            side_effect=Exception("Device error")
        )

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id"
        ) as mock_get_coord:
            mock_get_coord.return_value = mock_coordinator

            call_data = {"device_id": "test-id", "filter_type": "hepa"}
            mock_call = MagicMock(spec=ServiceCall)
            mock_call.data = call_data

            # Act & Assert
            with pytest.raises(HomeAssistantError, match="Failed to reset hepa filter"):
                await _handle_reset_filter(mock_hass, mock_call)

    @pytest.mark.asyncio
    async def test_reset_filter_carbon_success(self, mock_hass, mock_coordinator):
        """Test reset carbon filter success."""
        # Arrange
        mock_coordinator.device.reset_carbon_filter_life = AsyncMock()

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id"
        ) as mock_get_coord:
            mock_get_coord.return_value = mock_coordinator

            call_data = {"device_id": "test-id", "filter_type": "carbon"}
            mock_call = MagicMock(spec=ServiceCall)
            mock_call.data = call_data

            # Act
            await _handle_reset_filter(mock_hass, mock_call)

            # Assert
            mock_coordinator.device.reset_carbon_filter_life.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_filter_both_success(self, mock_hass, mock_coordinator):
        """Test reset both filters success."""
        # Arrange
        mock_coordinator.device.reset_hepa_filter_life = AsyncMock()
        mock_coordinator.device.reset_carbon_filter_life = AsyncMock()

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id"
        ) as mock_get_coord:
            mock_get_coord.return_value = mock_coordinator

            call_data = {"device_id": "test-id", "filter_type": "both"}
            mock_call = MagicMock(spec=ServiceCall)
            mock_call.data = call_data

            # Act
            await _handle_reset_filter(mock_hass, mock_call)

            # Assert
            mock_coordinator.device.reset_hepa_filter_life.assert_called_once()
            mock_coordinator.device.reset_carbon_filter_life.assert_called_once()


class TestSetOscillationAnglesDeviceError:
    """Test device communication error in set oscillation angles."""

    @pytest.mark.asyncio
    async def test_set_oscillation_angles_device_error(
        self, mock_hass, mock_coordinator
    ):
        """Test set oscillation angles with device communication error."""
        # Arrange
        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=Exception("Device error")
        )

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id"
        ) as mock_get_coord:
            mock_get_coord.return_value = mock_coordinator

            call_data = {"device_id": "test-id", "lower_angle": 10, "upper_angle": 30}
            mock_call = MagicMock(spec=ServiceCall)
            mock_call.data = call_data

            # Act & Assert
            with pytest.raises(
                HomeAssistantError, match="Failed to set oscillation angles"
            ):
                await _handle_set_oscillation_angles(mock_hass, mock_call)
