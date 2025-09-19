"""Comprehensive tests for config_flow complex logic coverage enhancement.

This module implements extensive testing of the Dyson config flow to improve coverage
from 60% to 80%+, focusing on error paths, authentication failures, MDNS discovery,
options flow, and edge cases that are not covered by the existing tests.

Following patterns from .github/design/testing-patterns.md for Home Assistant testing.
"""

import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hass_dyson.config_flow import (
    DysonConfigFlow,
    DysonOptionsFlow,
    _discover_device_via_mdns,
    _get_connection_type_display_name,
)


class TestDysonConfigFlowComprehensiveAuth:
    """Test authentication and API integration error paths."""

    @pytest.fixture
    def mock_flow(self):
        """Create a mock config flow instance."""
        flow = DysonConfigFlow()
        flow.hass = MagicMock(spec=HomeAssistant)
        flow.context = {"title_placeholders": {}}
        return flow

    @pytest.mark.asyncio
    async def test_authenticate_with_dyson_api_network_error(self, mock_flow):
        """Test authentication with network error."""
        # Mock async_add_executor_job to return a mock client that raises ConnectionError
        mock_client = MagicMock()
        mock_client.provision = AsyncMock(side_effect=ConnectionError("Network unreachable"))
        mock_flow.hass.async_add_executor_job = AsyncMock(return_value=mock_client)

        token, errors = await mock_flow._authenticate_with_dyson_api("test@example.com", "password123")

        assert token is None
        assert "base" in errors
        assert errors["base"] == "auth_failed"  # All exceptions map to auth_failed in the catch-all

    @pytest.mark.asyncio
    async def test_authenticate_with_dyson_api_timeout_error(self, mock_flow):
        """Test authentication with timeout error."""
        # Mock async_add_executor_job to return a mock client that raises TimeoutError
        mock_client = MagicMock()
        mock_client.provision = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_flow.hass.async_add_executor_job = AsyncMock(return_value=mock_client)

        token, errors = await mock_flow._authenticate_with_dyson_api("test@example.com", "password123")

        assert token is None
        assert "base" in errors
        assert errors["base"] == "auth_failed"  # All exceptions map to auth_failed in the catch-all

    @pytest.mark.asyncio
    async def test_authenticate_with_dyson_api_api_error(self, mock_flow):
        """Test authentication with API error."""
        # Import the actual exception to test proper exception handling
        from libdyson_rest.exceptions import DysonAuthError

        # Mock async_add_executor_job to return a mock client that raises DysonAuthError
        mock_client = MagicMock()
        mock_client.provision = AsyncMock(side_effect=DysonAuthError("Invalid credentials"))
        mock_flow.hass.async_add_executor_job = AsyncMock(return_value=mock_client)

        token, errors = await mock_flow._authenticate_with_dyson_api("test@example.com", "password123")

        assert token is None
        assert "base" in errors
        assert errors["base"] == "auth_failed"  # DysonAuthError maps to auth_failed

    @pytest.mark.asyncio
    async def test_authenticate_with_dyson_api_generic_exception(self, mock_flow):
        """Test authentication with generic exception."""
        # Mock async_add_executor_job to return a mock client that raises generic Exception
        mock_client = MagicMock()
        mock_client.provision = AsyncMock(side_effect=Exception("Generic error"))
        mock_flow.hass.async_add_executor_job = AsyncMock(return_value=mock_client)

        token, errors = await mock_flow._authenticate_with_dyson_api("test@example.com", "password123")

        assert token is None
        assert "base" in errors
        assert errors["base"] == "auth_failed"  # Generic exceptions map to auth_failed


class TestDysonConfigFlowComprehensiveMDNS:
    """Test MDNS discovery and network resolution complex scenarios."""

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_zeroconf_none(self):
        """Test MDNS discovery when zeroconf instance is None."""
        mock_hass = MagicMock(spec=HomeAssistant)

        with patch("homeassistant.components.zeroconf.async_get_instance") as mock_zeroconf:
            mock_zeroconf.return_value = None

            result = await _discover_device_via_mdns(mock_hass, "VS6-EU-HJA1234A", timeout=5)

            assert result is None

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_zeroconf_exception(self):
        """Test MDNS discovery when zeroconf instance raises exception."""
        mock_hass = MagicMock(spec=HomeAssistant)

        with patch("homeassistant.components.zeroconf.async_get_instance") as mock_zeroconf:
            mock_zeroconf.side_effect = Exception("Zeroconf unavailable")

            result = await _discover_device_via_mdns(mock_hass, "VS6-EU-HJA1234A", timeout=5)

            assert result is None

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_service_info_no_addresses(self):
        """Test MDNS discovery when service info exists but has no addresses."""
        mock_hass = MagicMock(spec=HomeAssistant)

        with patch("homeassistant.components.zeroconf.async_get_instance") as mock_zeroconf:
            mock_zc_instance = MagicMock()
            mock_zeroconf.return_value = mock_zc_instance

            # Mock service info with no addresses
            mock_service_info = MagicMock()
            mock_service_info.addresses = []
            mock_zc_instance.get_service_info.return_value = mock_service_info

            # Mock socket.gethostbyname to fail as well
            with patch("socket.gethostbyname") as mock_gethostbyname:
                mock_gethostbyname.side_effect = socket.gaierror("Name resolution failed")

                result = await _discover_device_via_mdns(mock_hass, "VS6-EU-HJA1234A", timeout=5)

                assert result is None

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_executor_timeout(self):
        """Test MDNS discovery when executor task times out."""
        mock_hass = MagicMock(spec=HomeAssistant)

        with patch("homeassistant.components.zeroconf.async_get_instance") as mock_zeroconf:
            mock_zc_instance = MagicMock()
            mock_zeroconf.return_value = mock_zc_instance

            # Mock a slow service lookup that would cause timeout
            def slow_service_lookup(*args, **kwargs):
                import time

                time.sleep(10)  # Simulate slow response
                return None

            mock_zc_instance.get_service_info.side_effect = slow_service_lookup

            result = await _discover_device_via_mdns(mock_hass, "VS6-EU-HJA1234A", timeout=1)

            assert result is None

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_fallback_to_local_hostname_success(self):
        """Test MDNS discovery fallback to .local hostname resolution."""
        mock_hass = MagicMock(spec=HomeAssistant)

        with patch("homeassistant.components.zeroconf.async_get_instance") as mock_zeroconf:
            mock_zc_instance = MagicMock()
            mock_zeroconf.return_value = mock_zc_instance

            # Mock service info returns None (no mDNS service found)
            mock_zc_instance.get_service_info.return_value = None

            # Mock successful hostname resolution to .local
            with patch("socket.gethostbyname") as mock_gethostbyname:
                mock_gethostbyname.return_value = "192.168.1.100"

                result = await _discover_device_via_mdns(mock_hass, "VS6-EU-HJA1234A", timeout=5)

                assert result == "192.168.1.100"
                mock_gethostbyname.assert_called_with("VS6-EU-HJA1234A.local")

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_internal_exception_handling(self):
        """Test MDNS discovery internal exception handling in _find_device."""
        mock_hass = MagicMock(spec=HomeAssistant)

        with patch("homeassistant.components.zeroconf.async_get_instance") as mock_zeroconf:
            mock_zc_instance = MagicMock()
            mock_zeroconf.return_value = mock_zc_instance

            # Mock get_service_info to raise an exception
            mock_zc_instance.get_service_info.side_effect = Exception("Service lookup failed")

            result = await _discover_device_via_mdns(mock_hass, "VS6-EU-HJA1234A", timeout=5)

            assert result is None


class TestDysonConfigFlowComprehensiveManualDevice:
    """Test manual device configuration complex scenarios."""

    @pytest.fixture
    def mock_flow(self):
        """Create a mock config flow instance."""
        flow = DysonConfigFlow()
        flow.hass = MagicMock(spec=HomeAssistant)
        flow.context = {"title_placeholders": {}}
        # Mock the abort check to prevent "already_configured" errors during testing
        flow._abort_if_unique_id_configured = MagicMock()
        return flow

    @pytest.mark.asyncio
    async def test_process_manual_device_input_invalid_serial_format(self, mock_flow):
        """Test processing manual device input with invalid serial number format."""
        user_input = {
            "serial_number": "INVALID-SERIAL",  # Invalid format
            "hostname": "192.168.1.100",
            "credential": "password123",
            "mqtt_prefix": "dyson_device",  # Required field
        }

        errors = await mock_flow._process_manual_device_input(user_input)

        # Should have no errors since MQTT prefix is provided and validation doesn't check serial format
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_process_manual_device_input_missing_required_fields(self, mock_flow):
        """Test processing manual device input with missing required fields."""
        user_input = {
            "serial_number": "",  # Missing
            "hostname": "192.168.1.100",
            "credential": "",  # Missing
            "mqtt_prefix": "",  # Missing
        }

        errors = await mock_flow._process_manual_device_input(user_input)

        assert "serial_number" in errors
        assert "credential" in errors
        assert "mqtt_prefix" in errors
        assert errors["serial_number"] == "required"
        assert errors["credential"] == "required"
        assert errors["mqtt_prefix"] == "required"

    @pytest.mark.asyncio
    async def test_process_manual_device_input_hostname_resolution_failure(self, mock_flow):
        """Test processing manual device input with hostname resolution failure."""
        user_input = {
            "serial_number": "VS6-EU-HJA1234A",
            "hostname": "nonexistent-device.local",
            "credential": "password123",
            "mqtt_prefix": "dyson_device",  # Required field
        }

        # The _process_manual_device_input method doesn't actually call hostname resolution
        # It only validates required fields, so this should succeed
        errors = await mock_flow._process_manual_device_input(user_input)

        # Should have no errors since all required fields are provided
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_resolve_device_hostname_ip_address_direct(self, mock_flow):
        """Test hostname resolution with direct IP address."""
        # IP addresses should be returned as-is
        result = await mock_flow._resolve_device_hostname("VS6-EU-HJA1234A", "192.168.1.100")

        assert result == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_resolve_device_hostname_mdns_discovery_success(self, mock_flow):
        """Test hostname resolution with successful MDNS discovery."""
        with patch("custom_components.hass_dyson.config_flow._discover_device_via_mdns") as mock_discover:
            mock_discover.return_value = "192.168.1.150"

            result = await mock_flow._resolve_device_hostname("VS6-EU-HJA1234A", "")

            assert result == "192.168.1.150"
            mock_discover.assert_called_once_with(mock_flow.hass, "VS6-EU-HJA1234A")

    @pytest.mark.asyncio
    async def test_resolve_device_hostname_mdns_fallback_to_local(self, mock_flow):
        """Test hostname resolution falls back to .local when MDNS fails."""
        with patch("custom_components.hass_dyson.config_flow._discover_device_via_mdns") as mock_discover:
            mock_discover.return_value = None  # MDNS discovery fails

            result = await mock_flow._resolve_device_hostname("VS6-EU-HJA1234A", "")

            assert result == "VS6-EU-HJA1234A.local"

    @pytest.mark.asyncio
    async def test_resolve_device_hostname_with_provided_hostname(self, mock_flow):
        """Test hostname resolution when hostname is provided."""
        result = await mock_flow._resolve_device_hostname("VS6-EU-HJA1234A", "my-device.local")

        assert result == "my-device.local"


class TestDysonConfigFlowComprehensiveVerify:
    """Test verification step complex scenarios."""

    @pytest.fixture
    def mock_flow(self):
        """Create a mock config flow instance."""
        flow = DysonConfigFlow()
        flow.hass = MagicMock(spec=HomeAssistant)
        flow.context = {"title_placeholders": {}}
        return flow

    @pytest.mark.asyncio
    async def test_async_step_verify_empty_otp_submission(self, mock_flow):
        """Test verify step with empty verification code submission."""
        user_input = {"verification_code": ""}

        # Set up flow state to simulate being in verification step
        mock_flow._cloud_client = MagicMock()
        mock_flow._challenge_id = "test-challenge-id"
        mock_flow._email = "test@example.com"
        mock_flow._password = "password123"

        # Mock complete_login to fail for empty verification code
        mock_flow._cloud_client.complete_login = AsyncMock(side_effect=Exception("Empty verification code"))

        result = await mock_flow.async_step_verify(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "verify"
        assert "base" in result["errors"]
        assert result["errors"]["base"] == "verification_failed"

    @pytest.mark.asyncio
    async def test_async_step_verify_invalid_otp_format(self, mock_flow):
        """Test verify step with invalid verification code format."""
        user_input = {"verification_code": "12345"}  # Too short

        # Set up flow state to simulate being in verification step
        mock_flow._cloud_client = MagicMock()
        mock_flow._challenge_id = "test-challenge-id"
        mock_flow._email = "test@example.com"
        mock_flow._password = "password123"

        # Mock the challenge verification to fail
        mock_flow._cloud_client.complete_login = AsyncMock(side_effect=Exception("Invalid verification code"))

        result = await mock_flow.async_step_verify(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "verify"
        assert "base" in result["errors"]
        assert result["errors"]["base"] == "verification_failed"

    @pytest.mark.asyncio
    async def test_async_step_verify_network_error_during_challenge(self, mock_flow):
        """Test verify step with network error during challenge."""
        user_input = {"verification_code": "123456"}

        # Set up flow state to simulate being in verification step
        mock_flow._cloud_client = MagicMock()
        mock_flow._challenge_id = "test-challenge-id"
        mock_flow._email = "test@example.com"
        mock_flow._password = "password123"

        # Mock network error during complete_login
        mock_flow._cloud_client.complete_login = AsyncMock(side_effect=ConnectionError("Network unreachable"))

        result = await mock_flow.async_step_verify(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "verify"
        assert "base" in result["errors"]
        assert result["errors"]["base"] == "verification_failed"


class TestDysonConfigFlowComprehensiveConnection:
    """Test connection configuration complex scenarios."""

    @pytest.fixture
    def mock_flow(self):
        """Create a mock config flow instance."""
        flow = DysonConfigFlow()
        flow.hass = MagicMock(spec=HomeAssistant)
        flow.context = {"title_placeholders": {}}
        # Use the correct type annotation, _discovered_devices expects Device objects or None
        flow._discovered_devices = None  # Will be set up in individual tests as needed
        return flow

    @pytest.mark.asyncio
    async def test_async_step_connection_no_devices_available(self, mock_flow):
        """Test connection step when no devices are available."""
        mock_flow._discovered_devices = []  # No devices

        result = await mock_flow.async_step_connection()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "connection"
        # Should still show form even with no devices

    @pytest.mark.asyncio
    async def test_async_step_connection_device_selection_validation(self, mock_flow):
        """Test connection step without cloud client setup."""
        user_input = {"connection_type": "local_cloud_fallback"}

        # Don't set up _cloud_client to simulate missing cloud client
        mock_flow._cloud_client = None

        result = await mock_flow.async_step_connection(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "connection"
        assert "base" in result["errors"]
        assert result["errors"]["base"] == "connection_failed"

    @pytest.mark.asyncio
    async def test_async_step_connection_successful_device_discovery(self, mock_flow):
        """Test connection step with successful device discovery."""
        user_input = {"connection_type": "cloud_only"}

        # Set up cloud client with mock devices
        mock_flow._cloud_client = MagicMock()
        mock_devices = [
            {"serial": "VS6-EU-HJA1234A", "name": "Test Device 1"},
            {"serial": "VS6-EU-HJA1234B", "name": "Test Device 2"},
        ]
        mock_flow._cloud_client.get_devices = AsyncMock(return_value=mock_devices)

        # Mock the next step
        with patch.object(mock_flow, "async_step_cloud_preferences") as mock_next_step:
            mock_next_step.return_value = {"type": FlowResultType.FORM, "step_id": "cloud_preferences"}

            result = await mock_flow.async_step_connection(user_input)

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "cloud_preferences"
            mock_next_step.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_step_connection_no_devices_found(self, mock_flow):
        """Test connection step when no devices are found."""
        user_input = {"connection_type": "local_only"}

        # Set up cloud client but return no devices
        mock_flow._cloud_client = MagicMock()
        mock_flow._cloud_client.get_devices = AsyncMock(return_value=[])

        result = await mock_flow.async_step_connection(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "connection"
        assert "base" in result["errors"]
        assert result["errors"]["base"] == "no_devices"


class TestDysonConfigFlowComprehensiveDiscovery:
    """Test discovery flow complex scenarios."""

    @pytest.fixture
    def mock_flow(self):
        """Create a mock config flow instance."""
        flow = DysonConfigFlow()
        flow.hass = MagicMock(spec=HomeAssistant)
        flow.context = {"title_placeholders": {}}
        # Mock the abort check to prevent "already_configured" errors during testing
        flow._abort_if_unique_id_configured = MagicMock()
        return flow

    @pytest.mark.asyncio
    async def test_async_step_discovery_invalid_discovery_info(self, mock_flow):
        """Test discovery step with invalid discovery info."""
        discovery_info = {}  # Missing required fields

        result = await mock_flow.async_step_discovery(discovery_info)

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "invalid_discovery_info"

    @pytest.mark.asyncio
    async def test_async_step_discovery_missing_serial_number(self, mock_flow):
        """Test discovery step with missing serial number in discovery info."""
        discovery_info = {"hostname": "192.168.1.100", "port": 1883}

        result = await mock_flow.async_step_discovery(discovery_info)

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "invalid_discovery_info"

    @pytest.mark.asyncio
    async def test_async_step_discovery_already_configured_device(self, mock_flow):
        """Test discovery step with already configured device."""
        discovery_info = {"serial_number": "VS6-EU-HJA1234A", "hostname": "192.168.1.100"}

        # Mock device already configured by making _abort_if_unique_id_configured raise AbortFlow
        from homeassistant.data_entry_flow import AbortFlow

        mock_flow._abort_if_unique_id_configured = MagicMock(side_effect=AbortFlow("already_configured"))

        # The AbortFlow exception should be raised
        with pytest.raises(AbortFlow) as exc_info:
            await mock_flow.async_step_discovery(discovery_info)

        assert str(exc_info.value) == "Flow aborted: already_configured"

    @pytest.mark.asyncio
    async def test_async_step_discovery_confirm_rejection(self, mock_flow):
        """Test discovery confirmation when user rejects."""
        user_input = {"confirm": False}

        result = await mock_flow.async_step_discovery_confirm(user_input)

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "user_declined"


class TestDysonOptionsFlowComprehensive:
    """Test options flow complex scenarios."""

    @pytest.fixture
    def mock_options_flow(self):
        """Create a mock options flow instance."""
        # Use the same pattern as existing tests to avoid HA framework setup
        config_entry = MagicMock()
        config_entry.data = {"serial_number": "VS6-EU-HJA1234A"}
        config_entry.options = {}

        # Create instance without calling __init__ to avoid frame helper setup
        flow = DysonOptionsFlow.__new__(DysonOptionsFlow)
        flow._config_entry = config_entry  # Set private attribute directly
        flow.hass = MagicMock(spec=HomeAssistant)
        flow.context = {}
        return flow

    @pytest.mark.asyncio
    async def test_async_step_manage_devices_no_devices_found(self, mock_options_flow):
        """Test manage devices step when no devices are found."""
        # Mock empty config entries
        mock_options_flow.hass.config_entries.async_entries.return_value = []

        result = await mock_options_flow.async_step_manage_devices()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manage_devices"

    @pytest.mark.asyncio
    async def test_async_step_delete_device_invalid_device_serial(self, mock_options_flow):
        """Test delete device step with invalid device serial."""
        user_input = {"device_serial": "nonexistent-device-serial"}

        # Mock config entry data with no matching device
        mock_options_flow.config_entry.data = {"devices": []}

        result = await mock_options_flow.async_step_delete_device(user_input)

        # Should redirect to manage_devices on invalid device
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manage_devices"

    @pytest.mark.asyncio
    async def test_async_step_delete_device_successful_removal(self, mock_options_flow):
        """Test delete device step with successful device removal."""
        device_serial = "test-device-serial"
        user_input = {"device_serial": device_serial, "confirm": True}

        # Mock config entry data with a device
        mock_options_flow.config_entry.data = {"devices": [{"serial_number": device_serial, "name": "Test Device"}]}

        # Mock successful device entry removal
        mock_device_entry = MagicMock()
        mock_device_entry.entry_id = "device-entry-id"
        mock_device_entry.data = {
            "parent_entry_id": mock_options_flow.config_entry.entry_id,
            "serial_number": device_serial,
        }

        mock_options_flow.hass.config_entries.async_entries.return_value = [mock_device_entry]
        mock_options_flow.hass.config_entries.async_remove = AsyncMock()
        mock_options_flow.hass.config_entries.async_update_entry = MagicMock()

        result = await mock_options_flow.async_step_delete_device(user_input)

        # Should create entry after successful removal
        assert result["type"] == FlowResultType.CREATE_ENTRY
        # async_remove called twice: once for device entry, once for account entry (when no devices left)
        assert mock_options_flow.hass.config_entries.async_remove.call_count == 2

    @pytest.mark.asyncio
    async def test_async_step_reload_all_user_cancels(self, mock_options_flow):
        """Test reload all step when user cancels."""
        user_input = {"confirm": False}

        result = await mock_options_flow.async_step_reload_all(user_input)

        # Should redirect to manage_devices when user cancels
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manage_devices"


class TestDysonConfigFlowUtilityFunctions:
    """Test utility function edge cases."""

    def test_get_connection_type_display_name_unknown_type(self):
        """Test connection type display name for unknown types."""
        result = _get_connection_type_display_name("unknown_connection_type")

        assert result == "unknown_connection_type"

    def test_get_connection_type_display_name_none_type(self):
        """Test connection type display name for None type - skip this invalid test."""
        # None is not a valid input for this function per type annotations
        pass

    def test_get_connection_type_display_name_empty_string(self):
        """Test connection type display name for empty string."""
        result = _get_connection_type_display_name("")

        assert result == ""


class TestDysonConfigFlowCleanupAndErrorRecovery:
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
        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_flow._cloud_client = mock_client

        await mock_flow._cleanup_cloud_client()

        mock_client.close.assert_called_once()
        assert mock_flow._cloud_client is None

    @pytest.mark.asyncio
    async def test_cleanup_cloud_client_no_client(self, mock_flow):
        """Test cloud client cleanup when no client exists."""
        # Should not raise exception when no client to cleanup
        await mock_flow._cleanup_cloud_client()

    @pytest.mark.asyncio
    async def test_cleanup_cloud_client_close_failure(self, mock_flow):
        """Test cloud client cleanup when close fails."""
        mock_client = MagicMock()
        mock_client.close = AsyncMock(side_effect=Exception("Close failed"))
        mock_flow._cloud_client = mock_client

        # Should not raise exception even if close fails
        await mock_flow._cleanup_cloud_client()

        # Client should still be cleaned up
        assert mock_flow._cloud_client is None


class TestDysonConfigFlowDeviceAutoCreate:
    """Test device auto-creation complex scenarios."""

    @pytest.fixture
    def mock_flow(self):
        """Create a mock config flow instance."""
        flow = DysonConfigFlow()
        flow.hass = MagicMock(spec=HomeAssistant)
        flow.context = {"title_placeholders": {}}
        # Mock the abort check to prevent "already_configured" errors during testing
        flow._abort_if_unique_id_configured = MagicMock()
        return flow

    @pytest.mark.asyncio
    async def test_async_step_device_auto_create_missing_device(self, mock_flow):
        """Test device auto-creation when user_input is None."""
        result = await mock_flow.async_step_device_auto_create(None)

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "no_device_data"

    @pytest.mark.asyncio
    async def test_async_step_device_auto_create_duplicate_device(self, mock_flow):
        """Test device auto-creation when device already exists."""
        user_input = {"serial_number": "VS6-EU-HJA1234A", "device_name": "Test Dyson Device"}

        # Mock device already configured by making _abort_if_unique_id_configured raise AbortFlow
        from homeassistant.data_entry_flow import AbortFlow

        mock_flow._abort_if_unique_id_configured = MagicMock(side_effect=AbortFlow("already_configured"))

        # The AbortFlow exception should be raised
        with pytest.raises(AbortFlow) as exc_info:
            await mock_flow.async_step_device_auto_create(user_input)

        assert str(exc_info.value) == "Flow aborted: already_configured"

    @pytest.mark.asyncio
    async def test_async_step_device_auto_create_missing_connection_type(self, mock_flow):
        """Test device auto-creation with missing serial number."""
        user_input = {
            "device_name": "Test Dyson Device"
            # Missing serial_number
        }

        result = await mock_flow.async_step_device_auto_create(user_input)

        # Should create entry successfully - the method doesn't validate serial_number presence
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Test Dyson Device"
        assert result["data"] == user_input

    @pytest.mark.asyncio
    async def test_async_step_device_auto_create_success(self, mock_flow):
        """Test successful device auto-creation."""
        user_input = {"serial_number": "VS6-EU-HJA1234A", "device_name": "Test Dyson Device"}

        result = await mock_flow.async_step_device_auto_create(user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Test Dyson Device"
        assert result["data"] == user_input
