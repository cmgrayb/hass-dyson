"""Test services module for Dyson integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.hass_dyson.const import DOMAIN
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
from custom_components.hass_dyson.services import (
    SERVICE_CANCEL_SLEEP_TIMER_SCHEMA,
    SERVICE_FETCH_ACCOUNT_DATA_SCHEMA,
    SERVICE_RESET_FILTER_SCHEMA,
    SERVICE_SCHEDULE_OPERATION_SCHEMA,
    SERVICE_SET_OSCILLATION_ANGLES_SCHEMA,
    SERVICE_SET_SLEEP_TIMER_SCHEMA,
    _get_coordinator_from_device_id,
    _handle_cancel_sleep_timer,
    _handle_fetch_account_data,
    _handle_reset_filter,
    _handle_schedule_operation,
    _handle_set_oscillation_angles,
    _handle_set_sleep_timer,
    async_remove_services,
    async_setup_services,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    hass.services = MagicMock()
    hass.services.async_register = AsyncMock()
    hass.services.async_remove = AsyncMock()
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
        invalid_data = {"device_id": "test-device", "lower_angle": 45, "upper_angle": 500}
        with pytest.raises(vol.Invalid):
            SERVICE_SET_OSCILLATION_ANGLES_SCHEMA(invalid_data)

    def test_fetch_account_data_schema_valid(self):
        """Test valid fetch account data schema."""
        valid_data = {"device_id": "test-device"}
        result = SERVICE_FETCH_ACCOUNT_DATA_SCHEMA(valid_data)
        assert result == valid_data

    def test_fetch_account_data_schema_no_device(self):
        """Test fetch account data schema without device_id."""
        valid_data = {}
        result = SERVICE_FETCH_ACCOUNT_DATA_SCHEMA(valid_data)
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
            with pytest.raises(ServiceValidationError, match="Device test-device not found"):
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
            with pytest.raises(ServiceValidationError, match="Device test-device not found"):
                await _handle_set_sleep_timer(mock_hass, call)

    @pytest.mark.asyncio
    async def test_handle_set_sleep_timer_device_error(self, mock_hass, mock_coordinator):
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
    async def test_handle_cancel_sleep_timer_device_error(self, mock_hass, mock_coordinator):
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
            with pytest.raises(HomeAssistantError, match="Failed to cancel sleep timer"):
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
    async def test_handle_schedule_operation_no_parameters(self, mock_hass, mock_coordinator):
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
    async def test_handle_schedule_operation_invalid_time(self, mock_hass, mock_coordinator):
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
    async def test_handle_schedule_operation_invalid_json(self, mock_hass, mock_coordinator):
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
    async def test_handle_set_oscillation_angles_success(self, mock_hass, mock_coordinator):
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
            mock_coordinator.device.set_oscillation_angles.assert_called_once_with(45, 315)

    @pytest.mark.asyncio
    async def test_handle_set_oscillation_angles_invalid_range(self, mock_hass, mock_coordinator):
        """Test oscillation angles setting with invalid angle range."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device", "lower_angle": 200, "upper_angle": 100}

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act & Assert
            with pytest.raises(ServiceValidationError, match="Lower angle must be less than upper angle"):
                await _handle_set_oscillation_angles(mock_hass, call)

    @pytest.mark.asyncio
    async def test_handle_set_oscillation_angles_device_error(self, mock_hass, mock_coordinator):
        """Test oscillation angles setting with device error."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device", "lower_angle": 45, "upper_angle": 315}
        mock_coordinator.device.set_oscillation_angles.side_effect = Exception("Device error")

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act & Assert
            with pytest.raises(HomeAssistantError, match="Failed to set oscillation angles"):
                await _handle_set_oscillation_angles(mock_hass, call)


class TestFetchAccountData:
    """Test fetch account data service handler."""

    @pytest.mark.asyncio
    async def test_handle_fetch_account_data_specific_device(self, mock_hass, mock_coordinator):
        """Test fetching account data for specific device."""
        # Arrange
        call = MagicMock(spec=ServiceCall)
        call.data = {"device_id": "test-device"}

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Act
            await _handle_fetch_account_data(mock_hass, call)

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
        await _handle_fetch_account_data(mock_hass, call)

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
            with pytest.raises(ServiceValidationError, match="Device test-device not found"):
                await _handle_fetch_account_data(mock_hass, call)

    @pytest.mark.asyncio
    async def test_handle_fetch_account_data_device_error(self, mock_hass, mock_coordinator):
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
            with pytest.raises(HomeAssistantError, match="Failed to refresh account data"):
                await _handle_fetch_account_data(mock_hass, call)

    @pytest.mark.asyncio
    async def test_handle_fetch_account_data_all_devices_with_errors(self, mock_hass):
        """Test fetching account data for all devices with some errors."""
        # Arrange
        mock_coordinator1 = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coordinator1.serial_number = "DEVICE-001"
        mock_coordinator1.async_refresh = AsyncMock()

        mock_coordinator2 = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coordinator2.serial_number = "DEVICE-002"
        mock_coordinator2.async_refresh = AsyncMock(side_effect=Exception("Device error"))

        mock_hass.data[DOMAIN] = {
            "entry1": mock_coordinator1,
            "entry2": mock_coordinator2,
        }

        call = MagicMock(spec=ServiceCall)
        call.data = {}

        with patch("custom_components.hass_dyson.services._LOGGER") as mock_logger:
            # Act
            await _handle_fetch_account_data(mock_hass, call)

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
        mock_coordinator.device.reset_hepa_filter_life.side_effect = Exception("Device error")

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
        # Act
        await async_setup_services(mock_hass)

        # Assert
        # Should register 6 services
        assert mock_hass.services.async_register.call_count == 6

        # Verify all services are registered
        expected_services = [
            "set_sleep_timer",
            "cancel_sleep_timer",
            "schedule_operation",
            "set_oscillation_angles",
            "fetch_account_data",
            "reset_filter",
        ]

        registered_services = [call[0][1] for call in mock_hass.services.async_register.call_args_list]

        for service in expected_services:
            assert service in registered_services

    @pytest.mark.asyncio
    async def test_async_remove_services(self, mock_hass):
        """Test service removal."""
        # Act
        await async_remove_services(mock_hass)

        # Assert
        # Should check for and remove 6 services
        assert mock_hass.services.has_service.call_count == 6
        assert mock_hass.services.async_remove.call_count == 6


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
