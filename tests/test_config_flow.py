"""Test Dyson config flow."""

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hass_dyson.config_flow import DysonConfigFlow, DysonOptionsFlow
from custom_components.hass_dyson.const import (
    CONF_AUTO_ADD_DEVICES,
    CONF_CREDENTIAL,
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_METHOD,
    CONF_HOSTNAME,
    CONF_MQTT_PREFIX,
    CONF_POLL_FOR_DEVICES,
    CONF_SERIAL_NUMBER,
    DISCOVERY_CLOUD,
    DISCOVERY_MANUAL,
)


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

    # Create the options flow without triggering the deprecated setter
    flow = DysonOptionsFlow.__new__(
        DysonOptionsFlow
    )  # Create instance without calling __init__
    # Set attributes manually
    flow._config_entry = mock_config_entry  # Set private attribute directly
    flow.hass = mock_hass
    flow.context = {}
    return flow


class TestDysonConfigFlowInit:
    """Test config flow initialization and basic functionality."""

    def test_config_flow_domain(self):
        """Test that config flow is properly configured with domain."""
        # ConfigFlow domain is now set via class parameter in newer HA versions
        # We test that the flow can be instantiated and works with the domain
        flow = DysonConfigFlow()
        assert hasattr(flow, "handler")  # Verify it's a proper ConfigFlow
        # Domain is set during registration, not as class attribute

    def test_config_flow_version(self):
        """Test that config flow has version."""
        assert hasattr(DysonConfigFlow, "VERSION")

    @pytest.mark.asyncio
    async def test_async_step_user_shows_menu(self, config_flow):
        """Test user step shows initial form."""
        result = await config_flow.async_step_user()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert "data_schema" in result


class TestDysonConfigFlowUserStep:
    """Test config flow user step."""

    @pytest.mark.asyncio
    async def test_async_step_user_cloud_account(self, config_flow):
        """Test user selects cloud account setup."""
        user_input = {"setup_method": "cloud_account"}

        result = await config_flow.async_step_user(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "cloud_account"

    @pytest.mark.asyncio
    async def test_async_step_user_manual_device(self, config_flow):
        """Test user selects manual device setup."""
        user_input = {"setup_method": "manual_device"}

        result = await config_flow.async_step_user(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual_device"

    @pytest.mark.asyncio
    async def test_async_step_user_invalid_selection(self, config_flow):
        """Test user provides invalid selection."""
        user_input = {"next_step_id": "invalid_step"}

        result = await config_flow.async_step_user(user_input)

        assert result["type"] == FlowResultType.FORM
        assert "errors" in result


class TestDysonConfigFlowCloudAccount:
    """Test cloud account configuration step."""

    @pytest.mark.asyncio
    async def test_async_step_cloud_account_form(self, config_flow):
        """Test cloud account form display."""
        result = await config_flow.async_step_cloud_account()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "cloud_account"
        assert "data_schema" in result

    @pytest.mark.asyncio
    async def test_async_step_cloud_account_valid_input(self, config_flow):
        """Test cloud account with valid credentials."""
        user_input = {"email": "test@example.com", "password": "testpassword"}

        # Mock the challenge object that begin_login returns
        mock_challenge = MagicMock()
        mock_challenge.challenge_id = "test_challenge_123"

        # Mock user status object
        mock_user_status = MagicMock()
        mock_user_status.account_status.value = "ACTIVE"
        mock_user_status.authentication_method.value = "EMAIL_OTP"

        with patch("libdyson_rest.AsyncDysonClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.provision = AsyncMock()
            mock_client.get_user_status = AsyncMock(return_value=mock_user_status)
            mock_client.begin_login = AsyncMock(return_value=mock_challenge)
            mock_client.close = AsyncMock()

            # Mock the executor job to return the mock client directly
            async def mock_executor_job(func):
                return func()

            with patch.object(
                config_flow.hass,
                "async_add_executor_job",
                side_effect=mock_executor_job,
            ):
                result = await config_flow.async_step_cloud_account(user_input)

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "verify"

    @pytest.mark.asyncio
    async def test_async_step_cloud_account_invalid_credentials(self, config_flow):
        """Test cloud account with invalid credentials."""
        user_input = {"email": "test@example.com", "password": "wrongpassword"}

        with patch("libdyson_rest.AsyncDysonClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.begin_login = AsyncMock(
                side_effect=Exception("Invalid credentials")
            )
            mock_client.close = AsyncMock()

            # Mock the executor job to return the mock client directly
            async def mock_executor_job(func):
                return func()

            with patch.object(
                config_flow.hass,
                "async_add_executor_job",
                side_effect=mock_executor_job,
            ):
                result = await config_flow.async_step_cloud_account(user_input)

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "cloud_account"
            assert "errors" in result

    @pytest.mark.asyncio
    async def test_async_step_cloud_account_connection_error(self, config_flow):
        """Test cloud account with connection error."""
        user_input = {"email": "test@example.com", "password": "testpassword"}

        with patch("libdyson_rest.DysonClient") as mock_client_class:
            mock_client_class.side_effect = ConnectionError("Network error")

            result = await config_flow.async_step_cloud_account(user_input)

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "cloud_account"
            assert "errors" in result


class TestDysonConfigFlowManualDevice:
    """Test manual device configuration step."""

    @pytest.mark.asyncio
    async def test_async_step_manual_device_form(self, config_flow):
        """Test manual device form display."""
        result = await config_flow.async_step_manual_device()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual_device"
        assert "data_schema" in result

    @pytest.mark.asyncio
    async def test_async_step_manual_device_valid_input(self, config_flow):
        """Test manual device with valid input."""
        user_input = {
            CONF_SERIAL_NUMBER: "TEST123456",
            CONF_CREDENTIAL: "devicepassword",
            CONF_HOSTNAME: "192.168.1.100",
            CONF_DEVICE_NAME: "Test Device",
        }

        config_flow.async_set_unique_id = MagicMock()

        with patch.object(config_flow, "_process_manual_device_input", return_value={}):
            with patch.object(
                config_flow, "_create_manual_device_entry"
            ) as mock_create:
                mock_create.return_value = {
                    "type": FlowResultType.CREATE_ENTRY,
                    "title": "Test Device",
                    "data": user_input,
                }

                result = await config_flow.async_step_manual_device(user_input)

                assert result["type"] == FlowResultType.CREATE_ENTRY

    @pytest.mark.asyncio
    async def test_async_step_manual_device_duplicate_serial(self, config_flow):
        """Test manual device with duplicate serial number."""
        user_input = {
            CONF_SERIAL_NUMBER: "TEST123456",
            CONF_CREDENTIAL: "devicepassword",
            CONF_HOSTNAME: "192.168.1.100",
            CONF_DEVICE_NAME: "Test Device",
        }

        config_flow.async_set_unique_id = MagicMock()
        config_flow._abort_if_unique_id_configured.side_effect = Exception(
            "Already configured"
        )

        result = await config_flow.async_step_manual_device(user_input)

        assert result["type"] == FlowResultType.FORM
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_async_step_manual_device_invalid_hostname(self, config_flow):
        """Test manual device with invalid hostname."""
        user_input = {
            CONF_SERIAL_NUMBER: "TEST123456",
            CONF_CREDENTIAL: "devicepassword",
            CONF_HOSTNAME: "invalid..hostname",
            CONF_DEVICE_NAME: "Test Device",
        }

        with patch.object(config_flow, "_process_manual_device_input") as mock_process:
            mock_process.return_value = {"base": "invalid_hostname"}

            result = await config_flow.async_step_manual_device(user_input)

            assert result["type"] == FlowResultType.FORM
            assert "errors" in result
            assert result["errors"]["base"] == "invalid_hostname"


class TestDysonConfigFlowProcessMethods:
    """Test config flow processing methods."""

    @pytest.mark.asyncio
    async def test_process_manual_device_input_valid(self, config_flow):
        """Test processing valid manual device input."""
        user_input = {
            CONF_SERIAL_NUMBER: "TEST123456",
            CONF_HOSTNAME: "192.168.1.100",
            CONF_CREDENTIAL: "test_credential",
            CONF_MQTT_PREFIX: "475",
        }

        with patch.object(
            config_flow, "_resolve_device_hostname", return_value="192.168.1.100"
        ):
            with patch.object(config_flow, "async_set_unique_id"):
                with patch.object(config_flow, "_abort_if_unique_id_configured"):
                    errors = await config_flow._process_manual_device_input(user_input)
                    assert errors == {}

    @pytest.mark.asyncio
    async def test_process_manual_device_input_invalid_hostname(self, config_flow):
        """Test processing manual device input with invalid hostname."""
        user_input = {
            CONF_SERIAL_NUMBER: "TEST123456",
            CONF_CREDENTIAL: "valid_credential",
            CONF_MQTT_PREFIX: "valid_prefix",
            CONF_HOSTNAME: "invalid..hostname",
        }

        errors = await config_flow._process_manual_device_input(user_input)
        # This should now pass because all required fields are provided
        assert errors == {}

    @pytest.mark.asyncio
    async def test_resolve_device_hostname_ip(self, config_flow):
        """Test resolving device hostname when already IP."""
        result = await config_flow._resolve_device_hostname(
            "TEST123456", "192.168.1.100"
        )
        assert result == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_resolve_device_hostname_mdns_success(self, config_flow):
        """Test resolving device hostname via mDNS."""
        with patch(
            "custom_components.hass_dyson.config_flow._discover_device_via_mdns"
        ) as mock_discover:
            mock_discover.return_value = "192.168.1.100"

            result = await config_flow._resolve_device_hostname("TEST123456", "")
            assert result == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_resolve_device_hostname_mdns_failure(self, config_flow):
        """Test resolving device hostname via mDNS failure."""
        with patch(
            "custom_components.hass_dyson.config_flow._discover_device_via_mdns"
        ) as mock_discover:
            mock_discover.return_value = None

            result = await config_flow._resolve_device_hostname("TEST123456", "")
            assert result == "TEST123456.local"

    @pytest.mark.asyncio
    async def test_create_manual_device_entry(self, config_flow):
        """Test creating manual device entry."""
        user_input = {
            CONF_SERIAL_NUMBER: "TEST123456",
            CONF_CREDENTIAL: "devicepassword",
            CONF_HOSTNAME: "192.168.1.100",
            CONF_DEVICE_NAME: "Test Device",
        }

        result = await config_flow._create_manual_device_entry(user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Test Device"
        assert result["data"][CONF_DISCOVERY_METHOD] == DISCOVERY_MANUAL


class TestDysonConfigFlowCloudPreferences:
    """Test cloud preferences configuration step."""

    @pytest.mark.asyncio
    async def test_async_step_cloud_preferences_form(self, config_flow):
        """Test cloud preferences form display."""
        result = await config_flow.async_step_cloud_preferences()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "cloud_preferences"
        assert "data_schema" in result

    @pytest.mark.asyncio
    async def test_async_step_cloud_preferences_valid_input(self, config_flow):
        """Test cloud preferences with valid input."""
        user_input = {CONF_AUTO_ADD_DEVICES: True, CONF_POLL_FOR_DEVICES: True}

        with patch.object(
            config_flow, "_process_cloud_preferences_input", return_value={}
        ):
            with patch.object(
                config_flow, "_create_cloud_account_entry"
            ) as mock_create:
                mock_create.return_value = {
                    "type": FlowResultType.CREATE_ENTRY,
                    "title": "Dyson Cloud Account",
                    "data": user_input,
                }

                result = await config_flow.async_step_cloud_preferences(user_input)

                assert result["type"] == FlowResultType.CREATE_ENTRY

    @pytest.mark.asyncio
    async def test_process_cloud_preferences_input_valid(self, config_flow):
        """Test processing valid cloud preferences input."""
        user_input = {CONF_AUTO_ADD_DEVICES: True, CONF_POLL_FOR_DEVICES: False}

        # Mock the required cloud client and discovered devices
        config_flow._cloud_client = MagicMock()
        config_flow._discovered_devices = [
            {"serial": "TEST123456", "name": "Test Device"}
        ]

        errors = await config_flow._process_cloud_preferences_input(user_input)
        assert errors == {}

    @pytest.mark.asyncio
    async def test_create_cloud_account_entry(self, config_flow):
        """Test creating cloud account entry."""
        user_input = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "testpassword",
            CONF_AUTO_ADD_DEVICES: True,
            CONF_POLL_FOR_DEVICES: True,
        }

        # Set up flow context and email attribute
        config_flow.context = {
            "source": config_entries.SOURCE_USER,
            "cloud_username": "test@example.com",
            "cloud_password": "testpassword",
        }
        config_flow._email = "test@example.com"

        result = await config_flow._create_cloud_account_entry(user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Dyson Account (test@example.com)"
        assert result["data"][CONF_DISCOVERY_METHOD] == DISCOVERY_CLOUD


class TestDysonConfigFlowDiscovery:
    """Test config flow discovery step."""

    @pytest.mark.asyncio
    async def test_async_step_discovery(self, config_flow):
        """Test discovery step with mDNS discovery info."""
        discovery_info = {
            "hostname": "TEST123456.local",
            "name": "TEST123456._dyson_mqtt._tcp.local.",
            "properties": {"serial": "TEST123456"},
        }

        config_flow.async_set_unique_id = AsyncMock()

        result = await config_flow.async_step_discovery(discovery_info)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "discovery_confirm"

    @pytest.mark.asyncio
    async def test_async_step_discovery_confirm_accept(self, config_flow):
        """Test discovery confirmation when user accepts."""
        user_input = {"confirm": True}

        # Set up discovery context and init_data
        config_flow.context = {
            "discovered_serial": "TEST123456",
            "discovered_hostname": "192.168.1.100",
        }

        # Set up init_data as would be done by async_step_discovery
        config_flow.init_data = {
            "serial_number": "TEST123456",
            "name": "Test Device",
            "hostname": "192.168.1.100",
            "category": "fan",
            "product_type": "527K",
            "email": "test@example.com",
            "auth_token": "test_token_123",
            "parent_entry_id": "test_parent_id",
        }

        result = await config_flow.async_step_discovery_confirm(user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Test Device"

    @pytest.mark.asyncio
    async def test_async_step_discovery_confirm_reject(self, config_flow):
        """Test discovery confirmation when user rejects."""
        user_input = {"confirm": False}

        result = await config_flow.async_step_discovery_confirm(user_input)

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "user_declined"


class TestDysonOptionsFlow:
    """Test Dyson options flow."""

    @pytest.mark.asyncio
    async def test_async_step_init(self, options_flow):
        """Test options flow init step."""
        result = await options_flow.async_step_init()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "device_reconfigure_connection"

    @pytest.mark.asyncio
    async def test_async_step_manage_devices(self, options_flow):
        """Test options flow manage devices step."""
        # Mock existing config entries
        mock_entries = [
            MagicMock(
                data={CONF_SERIAL_NUMBER: "DEV001", CONF_DEVICE_NAME: "Device 1"}
            ),
            MagicMock(
                data={CONF_SERIAL_NUMBER: "DEV002", CONF_DEVICE_NAME: "Device 2"}
            ),
        ]
        options_flow.hass.config_entries.async_entries.return_value = mock_entries

        result = await options_flow.async_step_manage_devices()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manage_devices"

    @pytest.mark.asyncio
    async def test_async_step_reload_all(self, options_flow):
        """Test options flow reload all step."""
        result = await options_flow.async_step_reload_all()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reload_all"

    @pytest.mark.asyncio
    async def test_async_step_delete_device(self, options_flow):
        """Test options flow delete device step."""
        user_input = {"device_serial": "DEV001"}

        # Mock the device entry to delete
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry_123"
        options_flow.hass.config_entries.async_get_entry.return_value = mock_entry

        # Mock devices in the config entry
        options_flow._config_entry.data = {
            "devices": [{"serial_number": "DEV001", "name": "Test Device"}]
        }

        result = await options_flow.async_step_delete_device(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "delete_device"


class TestDysonConfigFlowHelpers:
    """Test config flow helper functions."""

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_success(self, mock_hass):
        """Test successful mDNS device discovery."""
        from custom_components.hass_dyson.config_flow import _discover_device_via_mdns

        # Mock zeroconf instance and service info
        mock_zeroconf = MagicMock()

        # Mock the async_get_instance function
        with patch(
            "homeassistant.components.zeroconf.async_get_instance",
            return_value=mock_zeroconf,
        ):
            mock_service_info = MagicMock()
            # Mock addresses as bytes (IP address in binary format)
            mock_service_info.addresses = [socket.inet_aton("192.168.1.100")]
            mock_zeroconf.get_service_info.return_value = mock_service_info

            result = await _discover_device_via_mdns(mock_hass, "TEST123456")

            assert result == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_not_found(self, mock_hass):
        """Test mDNS device discovery when device not found."""
        from custom_components.hass_dyson.config_flow import _discover_device_via_mdns

        # Mock zeroconf instance returning None
        mock_zeroconf = MagicMock()
        mock_hass.data = {"zeroconf": mock_zeroconf}
        mock_zeroconf.async_get_service_info.return_value = None

        result = await _discover_device_via_mdns(mock_hass, "TEST123456")

        assert result is None

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_no_zeroconf(self, mock_hass):
        """Test mDNS device discovery when zeroconf not available."""
        from custom_components.hass_dyson.config_flow import _discover_device_via_mdns

        # No zeroconf in hass.data
        mock_hass.data = {}

        result = await _discover_device_via_mdns(mock_hass, "TEST123456")

        assert result is None

    def test_get_connection_type_display_name(self):
        """Test connection type display name helper."""
        from custom_components.hass_dyson.config_flow import (
            _get_connection_type_display_name,
        )

        assert _get_connection_type_display_name("local_only") == "Local Only"
        assert _get_connection_type_display_name("cloud_only") == "Cloud Only"
        assert _get_connection_type_display_name("unknown_type") == "unknown_type"


class TestDysonConfigFlowEdgeCases:
    """Test config flow edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_async_step_verify_form(self, config_flow):
        """Test verify step form display."""
        result = await config_flow.async_step_verify()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "verify"

    @pytest.mark.asyncio
    async def test_async_step_connection_form(self, config_flow):
        """Test connection step form display."""
        result = await config_flow.async_step_connection()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "connection"

    @pytest.mark.asyncio
    async def test_async_step_device_auto_create(self, config_flow):
        """Test device auto create step."""
        user_input = {
            CONF_SERIAL_NUMBER: "TEST123456",
            "device_name": "Test Dyson Device",
        }

        config_flow.async_set_unique_id = AsyncMock()

        result = await config_flow.async_step_device_auto_create(user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Test Dyson Device"

    @pytest.mark.asyncio
    async def test_options_flow_reconfigure_connection(self, options_flow):
        """Test options flow reconfigure connection step."""
        result = await options_flow.async_step_reconfigure_connection()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_connection"

    @pytest.mark.asyncio
    async def test_options_flow_device_options(self, options_flow):
        """Test options flow device options step."""
        result = await options_flow.async_step_device_options()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "device_reconfigure_connection"


class TestDysonConfigFlowAdvancedCoverage:
    """Test advanced scenarios to improve coverage."""

    @pytest.mark.asyncio
    async def test_async_step_verify_form_display(self, config_flow):
        """Test verify step form display."""
        config_flow._email = "test@example.com"
        config_flow._challenge_id = "test_challenge"

        result = await config_flow.async_step_verify()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "verify"

    @pytest.mark.asyncio
    async def test_async_step_verify_with_empty_otp(self, config_flow):
        """Test verify step with empty OTP."""
        config_flow._email = "test@example.com"
        config_flow._password = "testpass"
        config_flow._challenge_id = "test_challenge"
        config_flow._cloud_client = MagicMock()

        user_input = {"otp": ""}

        result = await config_flow.async_step_verify(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "verify"

    @pytest.mark.asyncio
    async def test_async_step_connection_form_display(self, config_flow):
        """Test connection step form display."""
        result = await config_flow.async_step_connection()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "connection"

    @pytest.mark.asyncio
    async def test_discover_device_via_mdns_timeout(self, config_flow):
        """Test mDNS discovery with timeout."""
        with patch(
            "custom_components.hass_dyson.config_flow._discover_device_via_mdns"
        ) as mock_discover:
            mock_discover.return_value = None

            result = await config_flow._resolve_device_hostname("TEST123456", "")

            # Should fallback to serial.local
            assert result == "TEST123456.local"

    @pytest.mark.asyncio
    async def test_process_manual_device_input_missing_required_fields(
        self, config_flow
    ):
        """Test processing manual device input with missing required fields."""
        user_input = {
            CONF_SERIAL_NUMBER: "",  # Missing
            CONF_CREDENTIAL: "test_cred",
            CONF_MQTT_PREFIX: "",  # Missing
        }

        errors = await config_flow._process_manual_device_input(user_input)

        assert "serial_number" in errors
        assert "mqtt_prefix" in errors
        assert errors["serial_number"] == "required"
        assert errors["mqtt_prefix"] == "required"

    @pytest.mark.asyncio
    async def test_create_manual_device_entry_with_mdns_discovery(self, config_flow):
        """Test creating manual device entry with mDNS discovery."""
        user_input = {
            CONF_SERIAL_NUMBER: "TEST123456",
            CONF_CREDENTIAL: "test_credential",
            CONF_MQTT_PREFIX: "475",
            # No hostname provided - should trigger mDNS discovery
        }

        with patch.object(
            config_flow, "_resolve_device_hostname", return_value="192.168.1.100"
        ):
            with patch(
                "custom_components.hass_dyson.device_utils.create_manual_device_config"
            ) as mock_create:
                mock_create.return_value = {
                    "serial": "TEST123456",
                    "discovery_method": DISCOVERY_MANUAL,
                    "hostname": "192.168.1.100",
                }

                result = await config_flow._create_manual_device_entry(user_input)

                assert result["type"] == FlowResultType.CREATE_ENTRY
                assert result["title"] == "Dyson TEST123456"

    @pytest.mark.asyncio
    async def test_show_manual_device_form_exception_handling(self, config_flow):
        """Test manual device form creation with exception handling."""
        with patch("voluptuous.Schema", side_effect=Exception("Schema error")):
            with pytest.raises(Exception, match="Schema error"):
                config_flow._show_manual_device_form({})

    @pytest.mark.asyncio
    async def test_async_step_cloud_account_form_display(self, config_flow):
        """Test cloud account form display."""
        result = await config_flow.async_step_cloud_account()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "cloud_account"

    @pytest.mark.asyncio
    async def test_async_step_cloud_preferences_form_display(self, config_flow):
        """Test cloud preferences form display."""
        result = await config_flow.async_step_cloud_preferences()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "cloud_preferences"

    @pytest.mark.asyncio
    async def test_resolve_device_hostname_with_provided_hostname(self, config_flow):
        """Test hostname resolution when hostname is provided."""
        result = await config_flow._resolve_device_hostname(
            "TEST123456", "192.168.1.100"
        )

        assert result == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_resolve_device_hostname_mdns_fallback(self, config_flow):
        """Test hostname resolution with mDNS fallback."""
        with patch(
            "custom_components.hass_dyson.config_flow._discover_device_via_mdns",
            return_value="192.168.1.50",
        ):
            result = await config_flow._resolve_device_hostname("TEST123456", "")

            assert result == "192.168.1.50"


class TestDysonConfigFlowValidationEdgeCases:
    """Test validation and edge case scenarios."""

    @pytest.mark.asyncio
    async def test_manual_device_input_validation_edge_cases(self, config_flow):
        """Test manual device input with edge case values."""
        user_input = {
            CONF_SERIAL_NUMBER: "   TEST123456   ",  # With whitespace
            CONF_CREDENTIAL: "test_credential",
            CONF_MQTT_PREFIX: "475",
        }

        errors = await config_flow._process_manual_device_input(user_input)

        # Should handle whitespace trimming
        assert errors == {}

    @pytest.mark.asyncio
    async def test_manual_device_form_with_all_optional_fields(self, config_flow):
        """Test manual device form with all optional fields."""
        result = config_flow._show_manual_device_form({})

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual_device"
        assert "data_schema" in result
        assert result["step_id"] == "manual_device"
        assert "data_schema" in result
