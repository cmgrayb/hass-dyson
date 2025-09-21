"""Comprehensive config flow coverage enhancement tests.

This module focuses on improving config_flow.py coverage from 69% to 80%+ by testing
error handling scenarios, validation edge cases, and missing code paths.
"""

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hass_dyson.config_flow import (
    DysonConfigFlow,
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
    CONF_MQTT_PREFIX,
    CONF_SERIAL_NUMBER,
)


class TestConfigFlowErrorHandling:
    """Test error handling scenarios in config flow."""

    @pytest.fixture
    def mock_flow(self):
        """Create a mock config flow instance."""
        flow = DysonConfigFlow()
        flow.hass = MagicMock(spec=HomeAssistant)
        flow.context = {"title_placeholders": {}}
        return flow

    @pytest.mark.asyncio
    async def test_async_step_user_invalid_setup_method(self, mock_flow):
        """Test user step with invalid setup method."""
        user_input = {"setup_method": "invalid_method"}

        result = await mock_flow.async_step_user(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_setup_method"

    @pytest.mark.asyncio
    async def test_async_step_user_form_creation_exception(self, mock_flow):
        """Test exception during form creation in user step."""
        with patch("voluptuous.Schema", side_effect=Exception("Schema error")):
            with pytest.raises(Exception, match="Schema error"):
                await mock_flow.async_step_user(None)

    @pytest.mark.asyncio
    async def test_authenticate_with_dyson_api_missing_challenge_id(self, mock_flow):
        """Test authentication when challenge is missing challenge_id."""
        mock_cloud_client = AsyncMock()
        mock_challenge = MagicMock()
        mock_challenge.challenge_id = None
        mock_cloud_client.request_login_code = AsyncMock(return_value=mock_challenge)

        with patch("libdyson_rest.AsyncDysonClient", return_value=mock_cloud_client):
            challenge_id, errors = await mock_flow._authenticate_with_dyson_api(
                "test@test.com", "password123"
            )

        assert challenge_id is None
        assert errors["base"] == "auth_failed"

    @pytest.mark.asyncio
    async def test_authenticate_with_dyson_api_none_challenge(self, mock_flow):
        """Test authentication when challenge itself is None."""
        mock_cloud_client = AsyncMock()
        mock_cloud_client.provision = AsyncMock()
        mock_cloud_client.get_user_status = AsyncMock()
        mock_cloud_client.begin_login = AsyncMock(return_value=None)

        # Mock hass.async_add_executor_job to return our mock client
        mock_flow.hass.async_add_executor_job = AsyncMock(
            return_value=mock_cloud_client
        )

        with patch("libdyson_rest.AsyncDysonClient", return_value=mock_cloud_client):
            challenge_id, errors = await mock_flow._authenticate_with_dyson_api(
                "test@test.com", "password"
            )

        assert challenge_id is None
        assert errors["base"] == "connection_failed"

    @pytest.mark.asyncio
    async def test_create_cloud_account_form_exception(self, mock_flow):
        """Test exception during cloud account form creation."""
        with patch("voluptuous.Schema", side_effect=Exception("Form error")):
            with pytest.raises(Exception, match="Form error"):
                mock_flow._create_cloud_account_form({})

    @pytest.mark.asyncio
    async def test_async_step_cloud_account_missing_credentials(self, mock_flow):
        """Test cloud account step with missing credentials."""
        user_input = {"email": "", "password": "password"}

        result = await mock_flow.async_step_cloud_account(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "auth_failed"

    @pytest.mark.asyncio
    async def test_async_step_cloud_account_empty_password(self, mock_flow):
        """Test cloud account step with empty password."""
        user_input = {"email": "test@test.com", "password": ""}

        result = await mock_flow.async_step_cloud_account(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "auth_failed"

    @pytest.mark.asyncio
    async def test_process_manual_device_input_missing_fields(self, mock_flow):
        """Test manual device processing with missing required fields."""
        user_input = {
            CONF_SERIAL_NUMBER: "",
            CONF_CREDENTIAL: "credential",
            CONF_MQTT_PREFIX: "prefix",
        }

        errors = await mock_flow._process_manual_device_input(user_input)

        assert errors[CONF_SERIAL_NUMBER] == "required"

    @pytest.mark.asyncio
    async def test_process_manual_device_input_duplicate_device(self, mock_flow):
        """Test manual device processing with duplicate device."""
        user_input = {
            CONF_SERIAL_NUMBER: "TEST123",
            CONF_CREDENTIAL: "credential",
            CONF_MQTT_PREFIX: "prefix",
        }

        mock_flow.async_set_unique_id = AsyncMock()
        mock_flow._abort_if_unique_id_configured = MagicMock(
            side_effect=Exception("Already configured")
        )

        errors = await mock_flow._process_manual_device_input(user_input)

        assert errors["base"] == "manual_setup_failed"

    @pytest.mark.asyncio
    async def test_resolve_device_hostname_mdns_failure(self, mock_flow):
        """Test hostname resolution when mDNS discovery fails."""
        with patch(
            "custom_components.hass_dyson.config_flow._discover_device_via_mdns",
            return_value=None,
        ):
            hostname = await mock_flow._resolve_device_hostname("TEST123", "")

        assert hostname == "TEST123.local"

    @pytest.mark.asyncio
    async def test_resolve_device_hostname_provided_hostname(self, mock_flow):
        """Test hostname resolution with provided hostname."""
        hostname = await mock_flow._resolve_device_hostname("TEST123", "192.168.1.100")

        assert hostname == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_show_manual_device_form_exception(self, mock_flow):
        """Test exception during manual device form creation."""
        with patch("voluptuous.Schema", side_effect=Exception("Schema error")):
            with pytest.raises(Exception, match="Schema error"):
                mock_flow._show_manual_device_form({})

    @pytest.mark.asyncio
    async def test_async_step_verify_missing_cloud_client(self, mock_flow):
        """Test verify step with missing cloud client."""
        mock_flow._cloud_client = None
        mock_flow._challenge_id = "challenge123"

        user_input = {"verification_code": "123456"}
        result = await mock_flow.async_step_verify(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "verification_failed"

    @pytest.mark.asyncio
    async def test_async_step_verify_missing_challenge_id(self, mock_flow):
        """Test verify step with missing challenge ID."""
        mock_flow._cloud_client = MagicMock()
        mock_flow._challenge_id = None

        user_input = {"verification_code": "123456"}
        result = await mock_flow.async_step_verify(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "verification_failed"

    @pytest.mark.asyncio
    async def test_async_step_verify_missing_email_or_password(self, mock_flow):
        """Test verify step with missing email or password."""
        mock_flow._cloud_client = MagicMock()
        mock_flow._challenge_id = "challenge123"
        mock_flow._email = ""  # Missing email
        mock_flow._password = "password"

        user_input = {"verification_code": "123456"}
        result = await mock_flow.async_step_verify(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "verification_failed"

    @pytest.mark.asyncio
    async def test_async_step_verify_401_error(self, mock_flow):
        """Test verify step with 401 authentication error."""
        mock_cloud_client = AsyncMock()
        mock_cloud_client.complete_login = AsyncMock(
            side_effect=Exception("401 Unauthorized")
        )

        mock_flow._cloud_client = mock_cloud_client
        mock_flow._challenge_id = "challenge123"
        mock_flow._email = "test@test.com"
        mock_flow._password = "password"

        user_input = {"verification_code": "123456"}
        result = await mock_flow.async_step_verify(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "auth_failed"

    @pytest.mark.asyncio
    async def test_async_step_verify_form_creation_exception(self, mock_flow):
        """Test exception during verification form creation."""
        with patch("voluptuous.Schema", side_effect=Exception("Form error")):
            with pytest.raises(Exception, match="Form error"):
                await mock_flow.async_step_verify(None)

    @pytest.mark.asyncio
    async def test_async_step_connection_missing_cloud_client(self, mock_flow):
        """Test connection step with missing cloud client."""
        mock_flow._cloud_client = None

        user_input = {"connection_type": "local_cloud_fallback"}
        result = await mock_flow.async_step_connection(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "connection_failed"

    @pytest.mark.asyncio
    async def test_async_step_connection_device_discovery_api_format_error(
        self, mock_flow
    ):
        """Test connection step with API format error."""
        mock_cloud_client = AsyncMock()
        mock_cloud_client.get_devices = AsyncMock(
            side_effect=Exception("Missing required field: productType")
        )

        mock_flow._cloud_client = mock_cloud_client

        user_input = {"connection_type": "local_cloud_fallback"}
        result = await mock_flow.async_step_connection(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "api_format_changed"

    @pytest.mark.asyncio
    async def test_async_step_connection_device_discovery_json_validation_error(
        self, mock_flow
    ):
        """Test connection step with JSON validation error."""
        mock_cloud_client = AsyncMock()
        mock_cloud_client.get_devices = AsyncMock(
            side_effect=Exception("JSONValidationError: Invalid format")
        )

        mock_flow._cloud_client = mock_cloud_client

        user_input = {"connection_type": "local_cloud_fallback"}
        result = await mock_flow.async_step_connection(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "api_validation_failed"

    @pytest.mark.asyncio
    async def test_async_step_connection_no_devices_found(self, mock_flow):
        """Test connection step when no devices found."""
        mock_cloud_client = AsyncMock()
        mock_cloud_client.get_devices = AsyncMock(return_value=[])

        mock_flow._cloud_client = mock_cloud_client

        user_input = {"connection_type": "local_cloud_fallback"}
        result = await mock_flow.async_step_connection(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "no_devices"

    @pytest.mark.asyncio
    async def test_async_step_connection_form_creation_exception(self, mock_flow):
        """Test exception during connection form creation."""
        with patch("voluptuous.Schema", side_effect=Exception("Form error")):
            with pytest.raises(Exception, match="Form error"):
                await mock_flow.async_step_connection(None)


class TestMDNSDiscoveryErrorHandling:
    """Test mDNS discovery error handling."""

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_no_zeroconf_instance(self):
        """Test mDNS discovery when zeroconf instance is unavailable."""
        mock_hass = MagicMock()

        with patch(
            "homeassistant.components.zeroconf.async_get_instance", return_value=None
        ):
            result = await _discover_device_via_mdns(mock_hass, "TEST123")

        assert result is None

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_no_services_found(self):
        """Test mDNS discovery when no services found."""
        mock_hass = MagicMock()
        mock_zeroconf = MagicMock()
        mock_zeroconf.get_service_info = MagicMock(return_value=None)

        with patch(
            "homeassistant.components.zeroconf.async_get_instance",
            return_value=mock_zeroconf,
        ):
            with patch(
                "socket.gethostbyname",
                side_effect=socket.gaierror("Name resolution failed"),
            ):
                result = await _discover_device_via_mdns(mock_hass, "TEST123")

        assert result is None

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_timeout(self):
        """Test mDNS discovery timeout."""
        mock_hass = MagicMock()

        def slow_function():
            import time

            time.sleep(2)  # Simulate slow operation
            return None

        with patch(
            "homeassistant.components.zeroconf.async_get_instance",
            return_value=MagicMock(),
        ):
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(
                    side_effect=slow_function
                )
                result = await _discover_device_via_mdns(
                    mock_hass, "TEST123", timeout=1
                )

        assert result is None

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_zeroconf_exception(self):
        """Test mDNS discovery with zeroconf exception."""
        mock_hass = MagicMock()

        with patch(
            "homeassistant.components.zeroconf.async_get_instance",
            side_effect=Exception("Zeroconf error"),
        ):
            result = await _discover_device_via_mdns(mock_hass, "TEST123")

        assert result is None

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_service_info_no_addresses(self):
        """Test mDNS discovery when service info has no addresses."""
        mock_hass = MagicMock()
        mock_zeroconf = MagicMock()
        mock_service_info = MagicMock()
        mock_service_info.addresses = []
        mock_zeroconf.get_service_info = MagicMock(return_value=mock_service_info)

        with patch(
            "homeassistant.components.zeroconf.async_get_instance",
            return_value=mock_zeroconf,
        ):
            with patch(
                "socket.gethostbyname",
                side_effect=socket.gaierror("Name resolution failed"),
            ):
                result = await _discover_device_via_mdns(mock_hass, "TEST123")

        assert result is None


class TestUtilityFunctionsCoverage:
    """Test utility functions for complete coverage."""

    def test_get_connection_type_display_name_unknown(self):
        """Test display name for unknown connection type."""
        result = _get_connection_type_display_name("unknown_type")
        assert result == "unknown_type"

    def test_get_setup_method_options(self):
        """Test setup method options."""
        options = _get_setup_method_options()
        assert "cloud_account" in options
        assert "manual_device" in options

    def test_get_connection_type_options(self):
        """Test connection type options."""
        options = _get_connection_type_options()
        assert "local_only" in options
        assert "cloud_only" in options

    def test_get_connection_type_options_detailed(self):
        """Test detailed connection type options."""
        options = _get_connection_type_options_detailed()
        assert "local_only" in options
        assert "Maximum Privacy" in options["local_only"]

    def test_get_management_actions(self):
        """Test management actions options."""
        actions = _get_management_actions()
        assert "reload_all" in actions
        assert "reconfigure_connection" in actions

    def test_get_device_connection_options(self):
        """Test device connection options."""
        options = _get_device_connection_options("local_cloud_fallback")
        assert "use_account_default" in options
        assert "local_only" in options


class TestCleanupAndErrorRecovery:
    """Test cleanup and error recovery scenarios."""

    @pytest.fixture
    def mock_flow(self):
        """Create a mock config flow instance."""
        flow = DysonConfigFlow()
        flow.hass = MagicMock(spec=HomeAssistant)
        flow.context = {"title_placeholders": {}}
        return flow

    @pytest.mark.asyncio
    async def test_cleanup_cloud_client_success(self, mock_flow):
        """Test successful cloud client cleanup."""
        mock_cloud_client = AsyncMock()
        mock_cloud_client.close = AsyncMock()
        mock_flow._cloud_client = mock_cloud_client

        await mock_flow._cleanup_cloud_client()

        assert mock_flow._cloud_client is None
        mock_cloud_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_cloud_client_no_client(self, mock_flow):
        """Test cleanup when no cloud client exists."""
        mock_flow._cloud_client = None

        await mock_flow._cleanup_cloud_client()

        assert mock_flow._cloud_client is None

    @pytest.mark.asyncio
    async def test_cleanup_cloud_client_close_failure(self, mock_flow):
        """Test cleanup when client close fails."""
        mock_cloud_client = AsyncMock()
        mock_cloud_client.close = AsyncMock(side_effect=Exception("Close failed"))
        mock_flow._cloud_client = mock_cloud_client

        await mock_flow._cleanup_cloud_client()

        assert mock_flow._cloud_client is None


class TestConfigFlowAuthenticationScenarios:
    """Test various authentication scenarios and error paths."""

    @pytest.fixture
    def mock_flow(self):
        """Create a mock config flow instance."""
        flow = DysonConfigFlow()
        flow.hass = MagicMock(spec=HomeAssistant)
        flow.context = {"title_placeholders": {}}
        return flow

    @pytest.mark.asyncio
    async def test_authenticate_with_dyson_api_auth_error(self, mock_flow):
        """Test authentication with DysonAuthError."""
        with patch("libdyson_rest.AsyncDysonClient") as mock_client_class:
            mock_cloud_client = AsyncMock()
            mock_client_class.return_value = mock_cloud_client

            # Create a mock exception for DysonAuthError
            class DysonAuthError(Exception):
                pass

            mock_cloud_client.request_login_code = AsyncMock(
                side_effect=DysonAuthError("Auth failed")
            )

            # Mock the exception in the config flow
            with patch("libdyson_rest.exceptions.DysonAuthError", DysonAuthError):
                challenge_id, errors = await mock_flow._authenticate_with_dyson_api(
                    "test@test.com", "password"
                )

        assert challenge_id is None
        assert errors["base"] == "auth_failed"

    @pytest.mark.asyncio
    async def test_authenticate_with_dyson_api_connection_error(self, mock_flow):
        """Test authentication with DysonConnectionError."""
        mock_cloud_client = AsyncMock()
        mock_cloud_client.provision = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        # Mock hass.async_add_executor_job to return our mock client
        mock_flow.hass.async_add_executor_job = AsyncMock(
            return_value=mock_cloud_client
        )

        # Import and use real exceptions
        from libdyson_rest.exceptions import DysonConnectionError

        with patch("libdyson_rest.AsyncDysonClient", return_value=mock_cloud_client):
            with patch.object(
                mock_cloud_client,
                "provision",
                side_effect=DysonConnectionError("Connection failed"),
            ):
                challenge_id, errors = await mock_flow._authenticate_with_dyson_api(
                    "test@test.com", "password"
                )

        assert challenge_id is None
        assert errors["base"] == "connection_failed"

    @pytest.mark.asyncio
    async def test_authenticate_with_dyson_api_api_error(self, mock_flow):
        """Test authentication with DysonAPIError."""
        mock_cloud_client = AsyncMock()
        mock_cloud_client.provision = AsyncMock()
        mock_cloud_client.get_user_status = AsyncMock()
        mock_cloud_client.begin_login = AsyncMock()

        # Mock hass.async_add_executor_job to return our mock client
        mock_flow.hass.async_add_executor_job = AsyncMock(
            return_value=mock_cloud_client
        )

        # Import and use real exceptions
        from libdyson_rest.exceptions import DysonAPIError

        with patch("libdyson_rest.AsyncDysonClient", return_value=mock_cloud_client):
            with patch.object(
                mock_cloud_client,
                "begin_login",
                side_effect=DysonAPIError("API failed"),
            ):
                challenge_id, errors = await mock_flow._authenticate_with_dyson_api(
                    "test@test.com", "password"
                )

        assert challenge_id is None
        assert errors["base"] == "cloud_api_error"

    @pytest.mark.asyncio
    async def test_authenticate_with_dyson_api_generic_exception(self, mock_flow):
        """Test authentication with generic exception."""
        with patch("libdyson_rest.AsyncDysonClient") as mock_client_class:
            mock_cloud_client = AsyncMock()
            mock_client_class.return_value = mock_cloud_client
            mock_cloud_client.request_login_code = AsyncMock(
                side_effect=Exception("Generic error")
            )

            challenge_id, errors = await mock_flow._authenticate_with_dyson_api(
                "test@test.com", "password"
            )

        assert challenge_id is None
        assert errors["base"] == "auth_failed"
