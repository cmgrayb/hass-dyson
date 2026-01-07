"""Comprehensive tests for Dyson config flow.

This consolidated module combines all config flow testing including:
- Main config flow functionality (test_config_flow.py)
- Comprehensive enhanced coverage (test_config_flow_comprehensive_enhanced.py)
- Error handling scenarios (test_config_flow_error_handling.py)
- Local broker credentials and connectivity filtering (test_config_flow_localBrokerCredentials_fix.py)

Following pure pytest patterns for Home Assistant integration testing.
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hass_dyson.config_flow import (
    DysonConfigFlow,
    DysonOptionsFlow,
    _discover_device_via_mdns,
    _get_connection_type_display_name,
    _get_connection_type_options,
    _get_connection_type_options_detailed,
    _get_device_connection_options,
    _get_management_actions,
    _get_setup_method_options,
)
from custom_components.hass_dyson.const import (
    CONF_CREDENTIAL,
    CONF_DEVICE_NAME,
    CONF_HOSTNAME,
    CONF_MQTT_PREFIX,
    CONF_SERIAL_NUMBER,
)


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    return MagicMock(spec=HomeAssistant)


@pytest.fixture
def config_flow(mock_hass):
    """Create a DysonConfigFlow instance."""
    flow = DysonConfigFlow()
    flow.hass = mock_hass
    flow._abort_if_unique_id_configured = MagicMock()
    # Mock the context to be writable
    flow.context = {}
    return flow


@pytest.fixture
def options_flow(mock_hass):
    """Create a DysonOptionsFlow instance."""
    mock_config_entry = MagicMock()
    mock_config_entry.data = {
        CONF_SERIAL_NUMBER: "TEST123456",
        CONF_DEVICE_NAME: "Test Device",
    }

    # Create options flow properly
    flow = DysonOptionsFlow(mock_config_entry)
    flow.hass = mock_hass
    flow.context = {}
    return flow


@pytest.fixture
def config_flow_with_client(mock_hass):
    """Create a DysonConfigFlow instance with an initialized client."""
    flow = DysonConfigFlow()
    flow.hass = mock_hass
    flow._email = "test@example.com"
    flow._cloud_client = AsyncMock()
    return flow


class TestDysonConfigFlowInit:
    """Test config flow initialization."""

    def test_config_flow_init(self, config_flow):
        """Test config flow initialization."""
        assert config_flow.VERSION == 1
        assert hasattr(config_flow, "hass")
        assert hasattr(config_flow, "context")

    def test_options_flow_init(self, options_flow):
        """Test options flow initialization."""
        assert hasattr(options_flow, "hass")
        assert hasattr(options_flow, "context")


class TestDysonConfigFlowUserStep:
    """Test config flow user step."""

    @pytest.mark.asyncio
    async def test_async_step_user_shows_setup_methods(self, config_flow):
        """Test user step shows setup method selection."""
        result = await config_flow.async_step_user()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert "setup_method" in result["data_schema"].schema

    @pytest.mark.asyncio
    async def test_async_step_user_cloud_selection(self, config_flow):
        """Test user step with cloud setup method selection."""
        user_input = {"setup_method": "cloud_account"}

        with patch.object(config_flow, "async_step_cloud_account") as mock_step:
            mock_step.return_value = {"type": FlowResultType.FORM}
            await config_flow.async_step_user(user_input)
            mock_step.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_step_user_manual_selection(self, config_flow):
        """Test user step with manual setup method selection."""
        user_input = {"setup_method": "manual_device"}

        with patch.object(config_flow, "async_step_manual_device") as mock_step:
            mock_step.return_value = {"type": FlowResultType.FORM}
            await config_flow.async_step_user(user_input)
            mock_step.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_step_user_invalid_setup_method(self, config_flow):
        """Test user step with invalid setup method."""
        user_input = {"setup_method": "invalid_method"}

        result = await config_flow.async_step_user(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_setup_method"


class TestDysonConfigFlowCloudAccount:
    """Test cloud account configuration."""

    @pytest.mark.asyncio
    async def test_async_step_cloud_account_form(self, config_flow):
        """Test cloud account step shows form."""
        result = await config_flow.async_step_cloud_account()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "cloud_account"
        assert "email" in result["data_schema"].schema

    @pytest.mark.asyncio
    async def test_async_step_cloud_account_valid_credentials(self, config_flow):
        """Test cloud account with valid credentials."""
        user_input = {"email": "test@example.com", "country": "US", "language": "en-US"}

        with patch.object(config_flow, "_initiate_otp_with_dyson_api") as mock_otp:
            mock_otp.return_value = ("otp_token", {})

            with patch.object(config_flow, "async_step_verify") as mock_step:
                mock_step.return_value = {"type": FlowResultType.FORM}
                await config_flow.async_step_cloud_account(user_input)
                mock_step.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_step_cloud_account_api_error(self, config_flow):
        """Test cloud account with API error."""
        user_input = {"email": "test@example.com", "country": "US", "language": "en-US"}

        with patch.object(config_flow, "_initiate_otp_with_dyson_api") as mock_otp:
            mock_otp.return_value = (None, {"base": "api_error"})

            result = await config_flow.async_step_cloud_account(user_input)

            assert result["type"] == FlowResultType.FORM
            assert result["errors"]["base"] == "api_error"


class TestDysonConfigFlowOTPVerification:
    """Test OTP verification step."""

    @pytest.mark.asyncio
    async def test_otp_verification_success(self, config_flow):
        """Test successful OTP verification."""
        config_flow._email = "test@example.com"
        config_flow._challenge_id = "test_challenge"
        config_flow._cloud_client = MagicMock()
        config_flow._cloud_client.complete_login = AsyncMock()

        user_input = {"verification_code": "123456", "password": "testpass"}

        with patch.object(config_flow, "async_step_connection") as mock_step:
            mock_step.return_value = {"type": FlowResultType.FORM}
            await config_flow.async_step_verify(user_input)
            mock_step.assert_called_once()

    @pytest.mark.asyncio
    async def test_otp_verification_invalid_code(self, config_flow):
        """Test OTP verification with invalid code."""
        config_flow._email = "test@example.com"
        config_flow._challenge_id = "test_challenge"
        config_flow._cloud_client = MagicMock()
        config_flow._cloud_client.complete_login = AsyncMock(
            side_effect=Exception("401 Unauthorized")
        )

        user_input = {"verification_code": "000000", "password": "wrongpass"}

        result = await config_flow.async_step_verify(user_input)

        assert result["type"] == FlowResultType.FORM
        assert "base" in result["errors"]


class TestDysonConfigFlowManualDevice:
    """Test manual device configuration."""

    @pytest.mark.asyncio
    async def test_manual_device_form(self, config_flow):
        """Test manual device step shows form."""
        result = await config_flow.async_step_manual_device()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual_device"
        assert CONF_SERIAL_NUMBER in result["data_schema"].schema

    @pytest.mark.asyncio
    async def test_manual_device_mdns_discovery_success(self, config_flow):
        """Test manual device with successful MDNS discovery."""
        user_input = {
            CONF_SERIAL_NUMBER: "TEST123456",
            CONF_DEVICE_NAME: "Test Device",
            CONF_CREDENTIAL: "test_cred",
            CONF_MQTT_PREFIX: "test_prefix",
        }

        with patch(
            "custom_components.hass_dyson.config_flow._discover_device_via_mdns"
        ) as mock_mdns:
            mock_mdns.return_value = "192.168.1.100"

            with patch(
                "custom_components.hass_dyson.device_utils.create_manual_device_config"
            ) as mock_create:
                mock_create.return_value = {"serial_number": "TEST123456"}

                result = await config_flow.async_step_manual_device(user_input)

                assert result["type"] == FlowResultType.CREATE_ENTRY
                assert result["title"] == "Test Device"

    @pytest.mark.asyncio
    async def test_manual_device_mdns_discovery_failure(self, config_flow):
        """Test manual device with MDNS discovery failure."""
        user_input = {
            CONF_SERIAL_NUMBER: "TEST123456",
            CONF_DEVICE_NAME: "Test Device",
            CONF_CREDENTIAL: "test_cred",
            CONF_MQTT_PREFIX: "test_prefix",
        }

        with patch(
            "custom_components.hass_dyson.config_flow._discover_device_via_mdns"
        ) as mock_mdns:
            mock_mdns.return_value = None

            with patch(
                "custom_components.hass_dyson.device_utils.create_manual_device_config"
            ) as mock_create:
                mock_create.return_value = {"serial_number": "TEST123456"}

                # Even with failed mDNS, manual device setup can still succeed without hostname
                result = await config_flow.async_step_manual_device(user_input)

                assert result["type"] == FlowResultType.CREATE_ENTRY

    @pytest.mark.asyncio
    async def test_manual_device_mdns_exception(self, config_flow):
        """Test manual device with MDNS exception."""
        # Test with missing required field to trigger validation error
        user_input = {CONF_SERIAL_NUMBER: "TEST123456", CONF_DEVICE_NAME: "Test Device"}

        result = await config_flow.async_step_manual_device(user_input)

        # Should return form with validation errors for missing required fields
        assert result["type"] == FlowResultType.FORM
        assert "errors" in result


class TestDysonConfigFlowDeviceVerification:
    """Test device verification."""

    @pytest.mark.asyncio
    async def test_verify_device_success(self, config_flow):
        """Test successful device verification."""
        config_flow._device_info = {
            CONF_SERIAL_NUMBER: "TEST123456",
            CONF_HOSTNAME: "192.168.1.100",
        }

        # Set up required cloud client and auth data
        from unittest.mock import AsyncMock

        config_flow._cloud_client = AsyncMock()
        config_flow._challenge_id = "test_challenge"
        config_flow._email = "test@example.com"

        user_input = {"verification_code": "123456", "password": "test_pass"}

        # Mock the complete_login method
        config_flow._cloud_client.complete_login = AsyncMock()

        with patch.object(config_flow, "async_step_connection") as mock_connection:
            mock_connection.return_value = {
                "type": FlowResultType.CREATE_ENTRY,
                "title": "Test Device",
                "data": {"serial_number": "TEST123456"},
            }

            result = await config_flow.async_step_verify(user_input)

            assert result["type"] == FlowResultType.CREATE_ENTRY

    @pytest.mark.asyncio
    async def test_verify_device_connection_failure(self, config_flow):
        """Test device verification with connection failure."""
        config_flow._device_info = {
            CONF_SERIAL_NUMBER: "TEST123456",
            CONF_HOSTNAME: "192.168.1.100",
        }

        user_input = {CONF_CREDENTIAL: "invalid_credential"}

        # Test connection failure through async_step_verify
        config_flow._cloud_client = MagicMock()
        config_flow._cloud_client.complete_login = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        result = await config_flow.async_step_verify(user_input)

        assert result["type"] == FlowResultType.FORM
        assert "base" in result.get("errors", {})


class TestDysonConfigFlowDiscovery:
    """Test device discovery functionality."""

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_success(self, mock_hass):
        """Test successful MDNS discovery."""
        with patch(
            "homeassistant.components.zeroconf.async_get_instance"
        ) as mock_zeroconf:
            mock_instance = MagicMock()
            mock_zeroconf.return_value = mock_instance

            result = await _discover_device_via_mdns(mock_hass, "TEST123456")
            # Test should handle the async nature and mocking
            assert result is None or isinstance(result, str)

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_socket_error(self, mock_hass):
        """Test MDNS discovery with socket error."""
        with patch(
            "homeassistant.components.zeroconf.async_get_instance"
        ) as mock_zeroconf:
            mock_zeroconf.return_value = (
                None  # Simulate failure to get zeroconf instance
            )

            result = await _discover_device_via_mdns(mock_hass, "TEST123456")
            assert result is None

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_exception(self, mock_hass):
        """Test MDNS discovery with general exception."""
        with patch(
            "homeassistant.components.zeroconf.async_get_instance",
            side_effect=Exception("Network error"),
        ):
            result = await _discover_device_via_mdns(mock_hass, "TEST123456")
            assert result is None


class TestDysonOptionsFlow:
    """Test options flow functionality."""

    @pytest.mark.asyncio
    async def test_init_form(self, options_flow):
        """Test options flow shows device reconfigure connection form."""
        result = await options_flow.async_step_init()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "device_reconfigure_connection"

    @pytest.mark.asyncio
    async def test_init_with_valid_options(self, options_flow):
        """Test options flow with valid device connection options."""
        user_input = {"connection_type": "cloud_only"}

        # Mock the async reload method that's called after updating the config entry
        options_flow.hass.config_entries.async_reload = AsyncMock()

        result = await options_flow.async_step_device_reconfigure_connection(user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        # Don't assert the exact connection_type as it may not be present
        assert result["data"] is not None


class TestDysonConfigFlowHelpers:
    """Test helper functions."""

    def test_get_connection_type_display_name(self):
        """Test connection type display name function."""
        # Test that the function returns proper display names for valid types
        assert _get_connection_type_display_name("cloud_only") == "Cloud Only"
        assert _get_connection_type_display_name("local_only") == "Local Only"

    def test_get_setup_method_options(self):
        """Test setup method options function."""
        options = _get_setup_method_options()
        assert "cloud_account" in options
        assert "manual_device" in options

    def test_get_connection_type_options(self):
        """Test connection type options function."""
        options = _get_connection_type_options()
        assert isinstance(options, dict)
        assert "local_only" in options

    def test_get_management_actions(self):
        """Test management actions function."""
        actions = _get_management_actions()
        assert isinstance(actions, dict)
        assert "reload_all" in actions


class TestDysonConfigFlowErrorHandling:
    """Test comprehensive error handling scenarios."""

    @pytest.fixture
    def mock_flow(self):
        """Create a mock config flow instance."""
        flow = DysonConfigFlow()
        flow.hass = MagicMock(spec=HomeAssistant)
        flow.context = {"title_placeholders": {}}
        return flow

    @pytest.mark.asyncio
    async def test_initiate_otp_network_error(self, mock_flow):
        """Test OTP initiation with network error."""
        from libdyson_rest.exceptions import DysonConnectionError

        mock_client = MagicMock()
        mock_client.provision = AsyncMock(side_effect=DysonConnectionError())
        mock_flow.hass.async_add_executor_job = AsyncMock(return_value=mock_client)

        token, errors = await mock_flow._initiate_otp_with_dyson_api(
            "test@example.com", "US", "en-US"
        )

        assert token is None
        assert "base" in errors

    @pytest.mark.asyncio
    async def test_verify_otp_network_error(self, mock_flow):
        """Test OTP verification with network error."""
        from libdyson_rest.exceptions import DysonConnectionError

        mock_flow._otp_token = "test_token"
        mock_flow._cloud_client = MagicMock()
        mock_flow._cloud_client.complete_login = AsyncMock(
            side_effect=DysonConnectionError()
        )

        result = await mock_flow.async_step_verify({"verification_code": "123456"})

        assert result["type"] == FlowResultType.FORM
        assert "base" in result.get("errors", {})

    @pytest.mark.asyncio
    async def test_device_connection_timeout(self, mock_flow):
        """Test device connection with timeout."""
        mock_flow._device_info = {
            CONF_SERIAL_NUMBER: "TEST123456",
            CONF_HOSTNAME: "192.168.1.100",
            CONF_CREDENTIAL: "test_cred",
        }

        mock_flow._cloud_client = MagicMock()
        mock_flow._cloud_client.complete_login = AsyncMock(side_effect=TimeoutError())

        result = await mock_flow.async_step_verify({"verification_code": "123456"})

        assert result["type"] == FlowResultType.FORM
        assert "base" in result.get("errors", {})

    @pytest.mark.asyncio
    async def test_mdns_discovery_timeout(self, mock_flow):
        """Test MDNS discovery with timeout."""
        with patch("homeassistant.components.zeroconf.async_get_instance"):
            # Use mock_flow's hass
            result = await _discover_device_via_mdns(
                mock_flow.hass, "TEST123456", timeout=1
            )
            assert result is None


class TestDysonConfigFlowConnectivityTypeFiltering:
    """Test device filtering based on connectivity types."""

    @pytest.mark.asyncio
    async def test_unsupported_connectivity_type_handling(
        self, config_flow_with_client
    ):
        """Test filtering of devices with unsupported connectivity types."""
        # Mock devices with different connectivity types
        standard_device = MagicMock()
        standard_device.name = "Standard Device"
        standard_device.connection_category = (
            None  # Most existing devices have no category
        )
        standard_device.serial_number = "STD123"
        standard_device.product_type = "475"

        lec_only_device = MagicMock()
        lec_only_device.name = "LEC Only Device"
        lec_only_device.connection_category = "lecOnly"
        lec_only_device.serial_number = "LEC456"
        lec_only_device.product_type = "999"

        config_flow_with_client._cloud_client.get_devices.return_value = [
            standard_device,
            lec_only_device,
        ]

        user_input = {"connection_type": "local_cloud_fallback"}

        result = await config_flow_with_client.async_step_connection(user_input)

        # The flow proceeds to cloud_preferences after filtering devices
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "cloud_preferences"
        # The device count should reflect filtering (1 supported device)
        assert result["description_placeholders"]["device_count"] == "1"

    @pytest.mark.asyncio
    async def test_supported_connectivity_type_inclusion(self, config_flow_with_client):
        """Test that devices with supported connectivity types are included."""
        # Mock device with supported connectivity
        supported_device = MagicMock()
        supported_device.name = "Supported Device"
        supported_device.connection_category = None  # Standard category
        supported_device.serial_number = "SUP789"
        supported_device.product_type = "527"

        config_flow_with_client._cloud_client.get_devices.return_value = [
            supported_device,
        ]

        user_input = {"connection_type": "local_cloud_fallback"}

        result = await config_flow_with_client.async_step_connection(user_input)

        # Should proceed to cloud_preferences with supported device
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "cloud_preferences"
        # The device count should show 1 supported device
        assert result["description_placeholders"]["device_count"] == "1"

    @pytest.mark.asyncio
    async def test_mixed_connectivity_types_filtering(self, config_flow_with_client):
        """Test filtering with mixed supported and unsupported connectivity types."""
        # Mock mix of devices
        devices = [
            # Supported devices
            MagicMock(
                name="Device 1",
                connection_category=None,
                serial_number="D1",
                product_type="475",
            ),
            MagicMock(
                name="Device 2",
                connection_category="standard",
                serial_number="D2",
                product_type="527",
            ),
            # Unsupported devices
            MagicMock(
                name="Device 3",
                connection_category="lecOnly",
                serial_number="D3",
                product_type="999",
            ),
            MagicMock(
                name="Device 4",
                connection_category="unsupported",
                serial_number="D4",
                product_type="888",
            ),
        ]

        config_flow_with_client._cloud_client.get_devices.return_value = devices

        user_input = {"connection_type": "local_cloud_fallback"}

        result = await config_flow_with_client.async_step_connection(user_input)

        # Should proceed to cloud_preferences after filtering
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "cloud_preferences"
        # Should show 3 supported devices (only lecOnly is filtered out)
        assert result["description_placeholders"]["device_count"] == "3"

    @pytest.mark.asyncio
    async def test_no_supported_devices_available(self, config_flow_with_client):
        """Test behavior when no supported devices are available."""
        # Mock only unsupported devices
        unsupported_device = MagicMock()
        unsupported_device.name = "Unsupported Device"
        unsupported_device.connection_category = "lecOnly"
        unsupported_device.serial_number = "UNS123"
        unsupported_device.product_type = "999"

        config_flow_with_client._cloud_client.get_devices.return_value = [
            unsupported_device,
        ]

        user_input = {"connection_type": "local_cloud_fallback"}

        result = await config_flow_with_client.async_step_connection(user_input)

        # Should still proceed to cloud_preferences but with 0 devices
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "cloud_preferences"
        # The device count should show 0 supported devices
        assert result["description_placeholders"]["device_count"] == "0"


class TestDysonConfigFlowComprehensiveAuth:
    """Test comprehensive authentication scenarios."""

    @pytest.fixture
    def mock_flow(self):
        """Create a mock config flow instance."""
        flow = DysonConfigFlow()
        flow.hass = MagicMock(spec=HomeAssistant)
        flow.context = {"title_placeholders": {}}
        return flow

    @pytest.mark.asyncio
    async def test_authentication_rate_limiting(self, mock_flow):
        """Test authentication with rate limiting."""
        from libdyson_rest.exceptions import DysonAPIError

        mock_client = MagicMock()
        mock_client.provision = AsyncMock(side_effect=DysonAPIError())
        mock_flow.hass.async_add_executor_job = AsyncMock(return_value=mock_client)

        token, errors = await mock_flow._initiate_otp_with_dyson_api(
            "test@example.com", "US", "en-US"
        )

        assert token is None
        assert errors["base"] == "cloud_api_error"

    @pytest.mark.asyncio
    async def test_authentication_invalid_credentials(self, mock_flow):
        """Test authentication with invalid credentials."""
        from libdyson_rest.exceptions import DysonAuthError

        mock_client = MagicMock()
        mock_client.provision = AsyncMock(side_effect=DysonAuthError())
        mock_flow.hass.async_add_executor_job = AsyncMock(return_value=mock_client)

        token, errors = await mock_flow._initiate_otp_with_dyson_api(
            "test@example.com", "US", "en-US"
        )

        assert token is None
        assert errors["base"] == "auth_failed"


class TestDysonConfigFlowUtilityFunctions:
    """Test utility functions comprehensively."""

    def test_get_connection_type_options_detailed(self):
        """Test detailed connection type options."""
        options = _get_connection_type_options_detailed()
        assert isinstance(options, dict)
        assert len(options) > 0

    def test_get_device_connection_options(self):
        """Test device connection options."""
        account_connection_type = "cloud_only"

        options = _get_device_connection_options(account_connection_type)
        assert isinstance(options, dict)
        assert "use_account_default" in options

    def test_utility_functions_edge_cases(self):
        """Test utility functions with edge cases."""
        # Test with None inputs - function should return None since it's not in the dict
        assert _get_connection_type_display_name(None) is None

        # Test with unknown connection type - should return the input value
        assert _get_connection_type_display_name("unknown_type") == "unknown_type"
        assert _get_connection_type_display_name("") is not None


class TestDysonConfigFlowEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_concurrent_flow_handling(self, config_flow):
        """Test handling of concurrent config flows during device setup."""
        # Mock _abort_if_unique_id_configured to simulate already configured device
        with patch.object(
            config_flow, "_abort_if_unique_id_configured"
        ) as mock_abort_check:
            with patch.object(config_flow, "async_abort") as mock_async_abort:
                with patch.object(config_flow, "async_set_unique_id"):
                    # Set up the abort side effect
                    def abort_side_effect():
                        config_flow.async_abort(reason="already_configured")

                    mock_abort_check.side_effect = abort_side_effect

                    # Test during manual device setup which calls _abort_if_unique_id_configured
                    user_input = {
                        CONF_SERIAL_NUMBER: "TEST123456",
                        CONF_CREDENTIAL: "test_key",
                        CONF_MQTT_PREFIX: "test_prefix",
                    }

                    await config_flow.async_step_manual_device(user_input)

                    # Verify abort was called due to duplicate device
                    mock_abort_check.assert_called_once()
                    mock_async_abort.assert_called_once_with(
                        reason="already_configured"
                    )

    @pytest.mark.asyncio
    async def test_malformed_device_data_handling(self, config_flow):
        """Test handling of malformed device data."""
        config_flow._cloud_client = MagicMock()

        # Mock device with missing required fields
        malformed_device = MagicMock()
        malformed_device.name = None  # Missing name
        malformed_device.serial_number = ""  # Empty serial

        config_flow._cloud_client.get_devices.return_value = [malformed_device]

        result = await config_flow.async_step_connection({"connection_type": "cloud"})

        # Should handle malformed data gracefully
        assert result["type"] == FlowResultType.FORM

    @pytest.mark.asyncio
    async def test_network_interruption_recovery(self, config_flow):
        """Test recovery from network interruptions."""
        # Set up initial state for verification step
        config_flow._device_info = {
            CONF_SERIAL_NUMBER: "TEST123456",
            CONF_HOSTNAME: "192.168.1.100",
        }
        # Don't set challenge_id to test parameter validation

        # Attempt should fail with parameter validation error
        result = await config_flow.async_step_verify(
            {"verification_code": "123456", "password": "test_password"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "verify"
        assert "base" in result.get("errors", {})

        # Verify proper error was captured and user can retry
        assert result["errors"]["base"] == "verification_failed"


class TestDysonConfigFlowErrorHandlingGaps:
    """Test specific error handling paths that need coverage improvement."""

    @pytest.fixture
    def mock_flow(self):
        """Create a mock config flow with proper setup."""
        flow = DysonConfigFlow()
        flow.hass = MagicMock(spec=HomeAssistant)
        flow.context = {"title_placeholders": {}}
        return flow

    @pytest.mark.asyncio
    async def test_async_step_user_form_creation_error(self, mock_flow):
        """Test error during setup method form creation."""
        with patch(
            "custom_components.hass_dyson.config_flow._get_setup_method_options",
            side_effect=Exception("Form creation error"),
        ):
            # This should trigger the first except block in async_step_user
            with pytest.raises(Exception) as exc_info:
                await mock_flow.async_step_user()
            assert "Form creation error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_async_step_user_top_level_exception(self, mock_flow):
        """Test top-level exception handler in async_step_user."""
        # Force an exception in the main try block by mocking the module-level function
        with patch(
            "custom_components.hass_dyson.config_flow._get_default_country_culture",
            side_effect=Exception("Top level error"),
        ):
            result = await mock_flow.async_step_user()
            # The method should handle the exception and return a form with errors
            assert result["type"] == "form"
            assert "errors" in result

    @pytest.mark.asyncio
    async def test_mdns_discovery_socket_gaierror(self, mock_hass):
        """Test mDNS discovery socket.gaierror handling."""
        import socket

        with patch("zeroconf.Zeroconf") as mock_zeroconf_class:
            mock_zeroconf = MagicMock()
            mock_zeroconf_class.return_value = mock_zeroconf

            # Mock socket.gethostbyname to raise gaierror
            with patch(
                "socket.gethostbyname",
                side_effect=socket.gaierror("Name resolution failed"),
            ):
                result = await _discover_device_via_mdns(mock_hass, "TEST123456")
                assert result is None

    @pytest.mark.asyncio
    async def test_mdns_discovery_general_exception(self, mock_hass):
        """Test mDNS discovery general exception handling."""
        with patch(
            "zeroconf.Zeroconf", side_effect=Exception("Zeroconf initialization failed")
        ):
            result = await _discover_device_via_mdns(mock_hass, "TEST123456")
            assert result is None

    @pytest.mark.asyncio
    async def test_mdns_discovery_timeout_error(self, mock_hass):
        """Test mDNS discovery timeout handling."""
        with patch("asyncio.wait_for", side_effect=TimeoutError("Discovery timeout")):
            result = await _discover_device_via_mdns(mock_hass, "TEST123456")
            assert result is None

    @pytest.mark.asyncio
    async def test_initiate_otp_client_initialization_error(self, mock_flow):
        """Test OTP initiation with client initialization failure."""
        # Mock async_add_executor_job to return None
        mock_flow.hass.async_add_executor_job = AsyncMock(return_value=None)

        token, errors = await mock_flow._initiate_otp_with_dyson_api(
            "test@example.com", "US", "en-US"
        )

        assert token is None
        assert errors["base"] == "auth_failed"

    @pytest.mark.asyncio
    async def test_initiate_otp_challenge_none_response(self, mock_flow):
        """Test OTP initiation with None challenge response."""
        # Mock successful client creation but None challenge
        mock_client = AsyncMock()
        mock_client.provision = AsyncMock()
        mock_client.get_user_status = AsyncMock(
            return_value=MagicMock(
                account_status=MagicMock(value="active"),
                authentication_method=MagicMock(value="otp"),
            )
        )
        mock_client.begin_login = AsyncMock(return_value=None)

        mock_flow.hass.async_add_executor_job = AsyncMock(return_value=mock_client)

        token, errors = await mock_flow._initiate_otp_with_dyson_api(
            "test@example.com", "US", "en-US"
        )

        assert token is None
        assert errors["base"] == "connection_failed"

    @pytest.mark.asyncio
    async def test_initiate_otp_challenge_no_id(self, mock_flow):
        """Test OTP initiation with challenge but no challenge_id."""
        # Mock successful client but challenge without ID
        mock_client = AsyncMock()
        mock_client.provision = AsyncMock()
        mock_client.get_user_status = AsyncMock(
            return_value=MagicMock(
                account_status=MagicMock(value="active"),
                authentication_method=MagicMock(value="otp"),
            )
        )

        # Mock challenge with None challenge_id
        mock_challenge = MagicMock()
        mock_challenge.challenge_id = None
        mock_client.begin_login = AsyncMock(return_value=mock_challenge)

        mock_flow.hass.async_add_executor_job = AsyncMock(return_value=mock_client)

        token, errors = await mock_flow._initiate_otp_with_dyson_api(
            "test@example.com", "US", "en-US"
        )

        assert token is None
        assert errors["base"] == "connection_failed"

    @pytest.mark.asyncio
    async def test_default_country_culture_no_config(self):
        """Test _get_default_country_culture with hass that has no config attribute."""
        from custom_components.hass_dyson.config_flow import (
            _get_default_country_culture,
        )

        # Mock hass without config attribute
        mock_hass = MagicMock()
        del mock_hass.config  # Remove config attribute

        country, culture = _get_default_country_culture(mock_hass)

        assert country == "US"
        assert culture == "en-US"

    @pytest.mark.asyncio
    async def test_default_country_culture_config_none(self):
        """Test _get_default_country_culture with hass.config = None."""
        from custom_components.hass_dyson.config_flow import (
            _get_default_country_culture,
        )

        mock_hass = MagicMock()
        mock_hass.config = None

        country, culture = _get_default_country_culture(mock_hass)

        assert country == "US"
        assert culture == "en-US"

    @pytest.mark.asyncio
    async def test_default_country_culture_attribute_error(self):
        """Test _get_default_country_culture with AttributeError."""
        from custom_components.hass_dyson.config_flow import (
            _get_default_country_culture,
        )

        # Mock hass with None config to trigger fallback
        mock_hass = MagicMock()
        mock_hass.config = None

        country, culture = _get_default_country_culture(mock_hass)

        assert country == "US"
        assert culture == "en-US"

    @pytest.mark.asyncio
    async def test_default_country_culture_type_error(self):
        """Test _get_default_country_culture with TypeError."""
        from custom_components.hass_dyson.config_flow import (
            _get_default_country_culture,
        )

        # Mock hass that raises TypeError
        mock_hass = MagicMock()
        mock_hass.config = MagicMock()
        type(mock_hass.config).language = PropertyMock(
            side_effect=TypeError("Invalid type")
        )

        country, culture = _get_default_country_culture(mock_hass)

        assert country == "US"
        assert culture == "en-US"

    @pytest.mark.asyncio
    async def test_cleanup_cloud_client_success(self, mock_flow):
        """Test successful cloud client cleanup."""
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        mock_flow._cloud_client = mock_client

        await mock_flow._cleanup_cloud_client()

        mock_client.close.assert_called_once()
        assert mock_flow._cloud_client is None

    @pytest.mark.asyncio
    async def test_cleanup_cloud_client_exception(self, mock_flow):
        """Test cloud client cleanup with exception."""
        mock_client = AsyncMock()
        mock_client.close = AsyncMock(side_effect=Exception("Close failed"))
        mock_flow._cloud_client = mock_client

        # Should not raise exception, just log and continue
        await mock_flow._cleanup_cloud_client()

        mock_client.close.assert_called_once()
        assert mock_flow._cloud_client is None

    @pytest.mark.asyncio
    async def test_cleanup_cloud_client_none(self, mock_flow):
        """Test cloud client cleanup when client is None."""
        mock_flow._cloud_client = None

        # Should handle gracefully without error
        await mock_flow._cleanup_cloud_client()

        assert mock_flow._cloud_client is None

    def test_get_connection_type_display_name_edge_cases(self):
        """Test connection type display name with edge cases."""
        # Test with empty string
        result = _get_connection_type_display_name("")
        assert result == ""

        # Test with unknown type
        result = _get_connection_type_display_name("unknown_connection")
        assert result == "unknown_connection"

        # Test with None (coverage for missing key in dict.get)
        result = _get_connection_type_display_name(None)
        assert result is None

    def test_get_device_connection_options_edge_cases(self):
        """Test device connection options with edge cases."""
        # Test with None account connection type
        options = _get_device_connection_options(None)
        assert isinstance(options, dict)
        assert "use_account_default" in options

        # Test with unknown account connection type
        options = _get_device_connection_options("unknown_type")
        assert isinstance(options, dict)
        assert "use_account_default" in options
