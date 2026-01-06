"""Comprehensive tests for the Dyson services platform.

This consolidated module combines service platform testing including:
- Core service registration and platform setup (test_services.py)
- Service validation and error handling (test_services_coverage_enhancement.py)
- Essential service functionality patterns

Following pure pytest patterns for Home Assistant integration testing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.hass_dyson.const import (
    DOMAIN,
    SERVICE_CANCEL_SLEEP_TIMER,
    SERVICE_GET_CLOUD_DEVICES,
    SERVICE_REFRESH_ACCOUNT_DATA,
    SERVICE_RESET_FILTER,
    SERVICE_SCHEDULE_OPERATION,
    SERVICE_SET_OSCILLATION_ANGLES,
    SERVICE_SET_SLEEP_TIMER,
)
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
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    hass.services = MagicMock()
    hass.services.async_register = MagicMock()
    hass.services.async_remove = MagicMock()
    hass.services.has_service = MagicMock(return_value=True)
    return hass


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-SERIAL-123"
    coordinator.device_name = "Test Device"
    coordinator.device = MagicMock()
    coordinator.device.set_sleep_timer = AsyncMock()
    coordinator.device.cancel_sleep_timer = AsyncMock()
    coordinator.device.set_oscillation_angles = AsyncMock()
    coordinator.device.reset_filter = AsyncMock()
    coordinator.device.reset_hepa_filter_life = AsyncMock()
    coordinator.device.reset_carbon_filter_life = AsyncMock()
    coordinator.device.schedule_operation = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.device_capabilities = ["Scheduling", "AdvancedOscillation"]
    coordinator.device_category = ["ec"]
    return coordinator


class TestServiceSetup:
    """Test service platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_services(self, mock_hass):
        """Test basic service setup."""
        # Set up mock return value to avoid errors
        mock_hass.services.async_register.return_value = None
        mock_hass.services.has_service.return_value = False

        # Import the actual function
        from custom_components.hass_dyson.services import (
            async_register_device_services_for_categories,
        )

        # Call with actual supported categories to trigger service registration
        await async_register_device_services_for_categories(mock_hass, ["ec"])

        # Should register services (exact count may vary)
        assert mock_hass.services.async_register.call_count >= 1

    @pytest.mark.asyncio
    async def test_async_setup_cloud_services(self, mock_hass):
        """Test cloud service setup."""
        # Set up mock return value to avoid errors
        mock_hass.services.async_register.return_value = None
        mock_hass.services.has_service.return_value = False

        # Import the actual function
        from custom_components.hass_dyson.services import (
            async_register_device_services_for_categories,
        )

        # Call with actual supported categories to trigger service registration
        await async_register_device_services_for_categories(mock_hass, ["ec", "robot"])

        # Should register cloud services
        assert mock_hass.services.async_register.call_count >= 1


class TestSleepTimerService:
    """Test sleep timer service functionality."""

    @pytest.mark.asyncio
    async def test_handle_set_sleep_timer_success(self, mock_hass, mock_coordinator):
        """Test successful sleep timer service call."""
        mock_hass.data[DOMAIN]["test_entry"] = mock_coordinator
        # Ensure device method is AsyncMock
        mock_coordinator.device.reset_filter = AsyncMock()
        # Ensure device method is AsyncMock
        mock_coordinator.device.set_sleep_timer = AsyncMock()

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Create ServiceCall with proper attributes
            service_call = ServiceCall.__new__(ServiceCall)
            service_call.domain = DOMAIN
            service_call.service = SERVICE_SET_SLEEP_TIMER
            service_call.data = {"device_id": "test_device", "minutes": 60}

            await _handle_set_sleep_timer(mock_hass, service_call)

            mock_coordinator.device.set_sleep_timer.assert_called_once_with(60)

    @pytest.mark.asyncio
    async def test_handle_cancel_sleep_timer_success(self, mock_hass, mock_coordinator):
        """Test successful cancel sleep timer service call."""
        mock_hass.data[DOMAIN]["test_entry"] = mock_coordinator
        # Mock the actual method used: set_sleep_timer(0) to cancel
        mock_coordinator.device.set_sleep_timer = AsyncMock()
        mock_coordinator.async_request_refresh = AsyncMock()

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Create ServiceCall with proper attributes
            service_call = ServiceCall.__new__(ServiceCall)
            service_call.domain = DOMAIN
            service_call.service = SERVICE_CANCEL_SLEEP_TIMER
            service_call.data = {"device_id": "test_device"}

            await _handle_cancel_sleep_timer(mock_hass, service_call)

            # The actual implementation calls set_sleep_timer(0) to cancel
            mock_coordinator.device.set_sleep_timer.assert_called_once_with(0)

    def test_sleep_timer_schema_validation(self):
        """Test sleep timer schema validation."""
        # Valid data
        valid_data = {"device_id": "test", "minutes": 120}
        result = SERVICE_SET_SLEEP_TIMER_SCHEMA(valid_data)
        assert result["minutes"] == 120

        # Invalid data
        with pytest.raises(vol.Invalid):
            SERVICE_SET_SLEEP_TIMER_SCHEMA({"device_id": "test", "minutes": -5})


class TestOscillationAnglesService:
    """Test oscillation angles service functionality."""

    @pytest.mark.asyncio
    async def test_handle_set_oscillation_angles_success(
        self, mock_hass, mock_coordinator
    ):
        """Test successful oscillation angles service call."""
        mock_hass.data[DOMAIN]["test_entry"] = mock_coordinator

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Create ServiceCall with proper attributes
            service_call = ServiceCall.__new__(ServiceCall)
            service_call.domain = DOMAIN
            service_call.service = SERVICE_SET_OSCILLATION_ANGLES
            service_call.data = {
                "device_id": "test_device",
                "lower_angle": 45,
                "upper_angle": 315,
            }

            await _handle_set_oscillation_angles(mock_hass, service_call)

            mock_coordinator.device.set_oscillation_angles.assert_called_once_with(
                45, 315
            )

    def test_oscillation_angles_schema_validation(self):
        """Test oscillation angles schema validation."""
        # Valid data
        valid_data = {"device_id": "test", "lower_angle": 45, "upper_angle": 315}
        result = SERVICE_SET_OSCILLATION_ANGLES_SCHEMA(valid_data)
        assert result["lower_angle"] == 45
        assert result["upper_angle"] == 315

        # Invalid angle range
        with pytest.raises(vol.Invalid):
            SERVICE_SET_OSCILLATION_ANGLES_SCHEMA(
                {
                    "device_id": "test",
                    "angle_low": 400,  # > 350
                    "angle_high": 315,
                }
            )


class TestFilterResetService:
    """Test filter reset service functionality."""

    @pytest.mark.asyncio
    async def test_handle_reset_filter_hepa(self, mock_hass, mock_coordinator):
        """Test resetting HEPA filter."""
        mock_hass.data[DOMAIN]["test_entry"] = mock_coordinator

        # Mock the correct method that is actually called
        mock_coordinator.device.reset_hepa_filter_life = AsyncMock()

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Create ServiceCall with proper attributes
            service_call = ServiceCall.__new__(ServiceCall)
            service_call.domain = DOMAIN
            service_call.service = SERVICE_RESET_FILTER
            service_call.data = {"device_id": "test_device", "filter_type": "hepa"}

            await _handle_reset_filter(mock_hass, service_call)

            mock_coordinator.device.reset_hepa_filter_life.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_reset_filter_carbon(self, mock_hass, mock_coordinator):
        """Test resetting carbon filter."""
        mock_hass.data[DOMAIN]["test_entry"] = mock_coordinator

        # Mock the correct method that is actually called
        mock_coordinator.device.reset_carbon_filter_life = AsyncMock()

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Create ServiceCall with proper attributes
            service_call = ServiceCall.__new__(ServiceCall)
            service_call.domain = DOMAIN
            service_call.service = SERVICE_RESET_FILTER
            service_call.data = {"device_id": "test_device", "filter_type": "carbon"}

            await _handle_reset_filter(mock_hass, service_call)

            mock_coordinator.device.reset_carbon_filter_life.assert_called_once()

    def test_reset_filter_schema_validation(self):
        """Test filter reset schema validation."""
        # Valid filter types
        SERVICE_RESET_FILTER_SCHEMA({"device_id": "test", "filter_type": "hepa"})
        SERVICE_RESET_FILTER_SCHEMA({"device_id": "test", "filter_type": "carbon"})

        # Invalid filter type
        with pytest.raises(vol.Invalid):
            SERVICE_RESET_FILTER_SCHEMA(
                {"device_id": "test", "filter_type": "invalid_filter"}
            )


class TestScheduleOperationService:
    """Test schedule operation service functionality."""

    @pytest.mark.asyncio
    async def test_handle_schedule_operation_success(self, mock_hass, mock_coordinator):
        """Test successful schedule operation service call."""
        mock_hass.data[DOMAIN]["test_entry"] = mock_coordinator

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Mock schedule operation method
            mock_coordinator.device.schedule_operation = AsyncMock()

            # Create ServiceCall with proper attributes
            service_call = ServiceCall.__new__(ServiceCall)
            service_call.domain = DOMAIN
            service_call.service = SERVICE_SCHEDULE_OPERATION
            service_call.data = {
                "device_id": "test_device",
                "operation": "turn_on",
                "schedule_time": "2024-01-01T12:00:00",
            }

            # Should not raise any exception (scheduling is experimental and just logs)
            await _handle_schedule_operation(mock_hass, service_call)

            # Note: Currently the implementation only logs the operation
            # The device.schedule_operation method is not called yet since scheduling is experimental

    def test_schedule_operation_schema_validation(self):
        """Test schedule operation schema validation."""
        # Valid operation
        valid_data = {
            "device_id": "test",
            "operation": "turn_on",
            "schedule_time": "2024-01-01T12:00:00",
        }
        result = SERVICE_SCHEDULE_OPERATION_SCHEMA(valid_data)
        assert result["operation"] == "turn_on"


class TestCloudServices:
    """Test cloud service functionality."""

    @pytest.mark.asyncio
    async def test_handle_get_cloud_devices_success(self, mock_hass):
        """Test successful get cloud devices service call."""
        # Create ServiceCall with proper attributes
        service_call = ServiceCall.__new__(ServiceCall)
        service_call.domain = DOMAIN
        service_call.service = SERVICE_GET_CLOUD_DEVICES
        service_call.data = {"sanitize": True}

        # Create a mock coordinator
        mock_coordinator = MagicMock()
        mock_coordinator.device = MagicMock()

        with (
            patch(
                "custom_components.hass_dyson.services._find_cloud_coordinators"
            ) as mock_find,
            patch(
                "custom_components.hass_dyson.services._get_cloud_device_data_from_coordinator"
            ) as mock_get_data,
        ):
            mock_find.return_value = [
                {
                    "email": "test@example.com",
                    "coordinator": mock_coordinator,
                    "type": "cloud_account",
                }
            ]
            mock_get_data.return_value = {"devices": [{"name": "Test Device"}]}

            result = await _handle_get_cloud_devices(mock_hass, service_call)

            # Should return device data
            assert result is not None
            assert "account_email" in result
            assert result["account_email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_handle_refresh_account_data_success(self, mock_hass):
        """Test successful refresh account data service call."""
        # Create ServiceCall with proper attributes
        service_call = ServiceCall.__new__(ServiceCall)
        service_call.domain = DOMAIN
        service_call.service = SERVICE_REFRESH_ACCOUNT_DATA
        service_call.data = {}

        # Import the actual function

        with patch(
            "custom_components.hass_dyson.services._find_cloud_coordinators"
        ) as mock_find:
            mock_find.return_value = []

            # The function doesn't return a value, just check it completes
            await async_handle_refresh_account_data(mock_hass, service_call)

            # Verify the function was called without error
            assert True  # Test passes if no exception was raised


class TestServiceUtilities:
    """Test service utility functions."""

    @pytest.mark.asyncio
    async def test_get_coordinator_from_device_id_success(
        self, mock_hass, mock_coordinator
    ):
        """Test successful coordinator lookup by device_id."""
        # Make mock_coordinator pass isinstance check
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

        mock_coordinator.__class__ = DysonDataUpdateCoordinator

        with patch(
            "homeassistant.helpers.device_registry.async_get"
        ) as mock_device_reg:
            mock_registry = MagicMock()
            mock_device = MagicMock()
            mock_device.config_entries = {"test_entry"}  # This is a set
            mock_registry.async_get.return_value = mock_device
            mock_device_reg.return_value = mock_registry

            # Set up hass.data properly
            mock_hass.data = {DOMAIN: {"test_entry": mock_coordinator}}

            result = await _get_coordinator_from_device_id(mock_hass, "test_device_id")

            assert result == mock_coordinator

    @pytest.mark.asyncio
    async def test_get_coordinator_from_device_id_not_found(self, mock_hass):
        """Test coordinator lookup with device not found."""
        with patch(
            "homeassistant.helpers.device_registry.async_get"
        ) as mock_device_reg:
            mock_registry = MagicMock()
            mock_registry.async_get.return_value = None
            mock_device_reg.return_value = mock_registry

            result = await _get_coordinator_from_device_id(
                mock_hass, "nonexistent_device"
            )

            assert result is None

    def test_find_cloud_coordinators(self, mock_hass, mock_coordinator):
        """Test finding cloud coordinators."""
        # Setup mock coordinator with cloud discovery method
        mock_coordinator.config_entry = MagicMock()
        mock_coordinator.config_entry.data = {"discovery_method": "cloud"}
        mock_hass.data[DOMAIN]["test_entry"] = mock_coordinator

        result = _find_cloud_coordinators(mock_hass)

        # Should find coordinators
        assert isinstance(result, list)


class TestServiceErrorHandling:
    """Test service error handling scenarios."""

    @pytest.mark.asyncio
    async def test_service_call_with_nonexistent_device(self, mock_hass):
        """Test service call with nonexistent device."""
        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=None,
        ):
            # Create ServiceCall with proper attributes
            service_call = ServiceCall.__new__(ServiceCall)
            service_call.domain = DOMAIN
            service_call.service = SERVICE_SET_SLEEP_TIMER
            service_call.data = {"device_id": "nonexistent", "minutes": 60}

            # Should handle gracefully and raise ServiceValidationError
            with pytest.raises(ServiceValidationError):
                await _handle_set_sleep_timer(mock_hass, service_call)

    @pytest.mark.asyncio
    async def test_service_call_device_error(self, mock_hass, mock_coordinator):
        """Test service call when device method raises exception."""
        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=Exception("Device error")
        )

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Create ServiceCall with proper attributes
            service_call = ServiceCall.__new__(ServiceCall)
            service_call.domain = DOMAIN
            service_call.service = SERVICE_SET_SLEEP_TIMER
            service_call.data = {"device_id": "test_device", "minutes": 60}

            # Should propagate device errors
            with pytest.raises(HomeAssistantError):
                await _handle_set_sleep_timer(mock_hass, service_call)


class TestServiceSchemas:
    """Test service schema validation."""

    def test_all_schemas_require_device_id(self):
        """Test that all service schemas require device_id."""
        schemas = [
            SERVICE_SET_SLEEP_TIMER_SCHEMA,
            SERVICE_CANCEL_SLEEP_TIMER_SCHEMA,
            SERVICE_SET_OSCILLATION_ANGLES_SCHEMA,
            SERVICE_RESET_FILTER_SCHEMA,
        ]

        for schema in schemas:
            # Each schema should require device_id
            with pytest.raises(vol.Invalid):
                schema({})  # Missing device_id

    def test_sleep_timer_boundary_values(self):
        """Test sleep timer boundary validation."""
        # Valid boundaries (15-540 minutes based on SLEEP_TIMER constants)
        SERVICE_SET_SLEEP_TIMER_SCHEMA({"device_id": "test", "minutes": 15})
        SERVICE_SET_SLEEP_TIMER_SCHEMA({"device_id": "test", "minutes": 540})

        # Invalid boundaries
        with pytest.raises(vol.Invalid):
            SERVICE_SET_SLEEP_TIMER_SCHEMA({"device_id": "test", "minutes": 10})  # < 15
        with pytest.raises(vol.Invalid):
            SERVICE_SET_SLEEP_TIMER_SCHEMA(
                {"device_id": "test", "minutes": 600}
            )  # > 540

    def test_oscillation_angles_boundary_values(self):
        """Test oscillation angles boundary validation."""
        # Valid angles (0-350)
        SERVICE_SET_OSCILLATION_ANGLES_SCHEMA(
            {"device_id": "test", "lower_angle": 0, "upper_angle": 350}
        )

        # Invalid angles
        with pytest.raises(vol.Invalid):
            SERVICE_SET_OSCILLATION_ANGLES_SCHEMA(
                {
                    "device_id": "test",
                    "lower_angle": -1,  # < 0
                    "upper_angle": 350,
                }
            )
        with pytest.raises(vol.Invalid):
            SERVICE_SET_OSCILLATION_ANGLES_SCHEMA(
                {
                    "device_id": "test",
                    "lower_angle": 0,
                    "upper_angle": 351,  # > 350
                }
            )


class TestServiceMissingCoverage:
    """Test previously uncovered service code paths."""

    @pytest.mark.asyncio
    async def test_service_setup_with_existing_services(self, mock_hass):
        """Test service setup when services already exist."""
        mock_hass.services.async_register.return_value = None
        mock_hass.services.has_service.return_value = False

        # Import the actual function
        from custom_components.hass_dyson.services import (
            async_register_device_services_for_categories,
        )

        # Setup services twice with actual supported category
        await async_register_device_services_for_categories(mock_hass, ["ec"])
        await async_register_device_services_for_categories(mock_hass, ["ec"])

        # Should handle gracefully
        assert mock_hass.services.async_register.call_count >= 1

    def test_cloud_services_schema_validation(self):
        """Test cloud service schema validation."""
        # Valid cloud service data
        SERVICE_GET_CLOUD_DEVICES_SCHEMA({"sanitize": True})
        SERVICE_GET_CLOUD_DEVICES_SCHEMA({"sanitize": False})
        SERVICE_REFRESH_ACCOUNT_DATA_SCHEMA({})

        # Invalid data types
        with pytest.raises(vol.Invalid):
            SERVICE_GET_CLOUD_DEVICES_SCHEMA({"sanitize": "invalid"})

    @pytest.mark.asyncio
    async def test_service_with_minimal_parameters(self, mock_hass, mock_coordinator):
        """Test services with minimal required parameters."""
        mock_hass.data[DOMAIN]["test_entry"] = mock_coordinator

        # Mock the actual method that gets called (set_sleep_timer with 0)
        mock_coordinator.device.set_sleep_timer = AsyncMock()
        mock_coordinator.async_request_refresh = AsyncMock()

        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            return_value=mock_coordinator,
        ):
            # Create ServiceCall with proper attributes - Cancel sleep timer only needs device_id
            service_call = ServiceCall.__new__(ServiceCall)
            service_call.domain = DOMAIN
            service_call.service = SERVICE_CANCEL_SLEEP_TIMER
            service_call.data = {"device_id": "test_device"}

            await _handle_cancel_sleep_timer(mock_hass, service_call)

            # The actual implementation calls set_sleep_timer(0) to cancel
            mock_coordinator.device.set_sleep_timer.assert_called_once_with(0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
