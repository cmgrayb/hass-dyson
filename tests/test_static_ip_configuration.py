"""Tests for static IP/hostname configuration feature."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from custom_components.hass_dyson.config_flow import DysonConfigFlow
from custom_components.hass_dyson.const import CONF_HOSTNAME, CONF_SERIAL_NUMBER, DOMAIN


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    hass.config_entries = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    return hass


@pytest.fixture
def mock_discovery_info():
    """Create mock discovery info for a cloud device."""
    return {
        "serial_number": "VS6-EU-HJA1234A",
        "name": "Dyson Test Fan",
        "product_type": "438",
        "category": "ec",
        "email": "test@example.com",
        "auth_token": "test_token_123",
        "parent_entry_id": "parent_entry_123",
    }


class TestCloudDeviceDiscoveryWithHostname:
    """Test cloud device discovery flow with hostname configuration."""

    @pytest.mark.asyncio
    async def test_discovery_connection_step_shows_hostname_field(
        self, mock_hass, mock_discovery_info
    ):
        """Test that discovery connection step shows hostname field."""
        flow = DysonConfigFlow()
        flow.hass = mock_hass
        flow.init_data = mock_discovery_info

        # Get the discovery connection form
        result = await flow.async_step_discovery_connection()

        # Verify form is shown with correct step_id
        assert result["type"] == "form"
        assert result["step_id"] == "discovery_connection"

        # Verify data schema includes hostname field
        schema_keys = list(result["data_schema"].schema.keys())
        assert any("connection_type" in str(key) for key in schema_keys)
        assert any(CONF_HOSTNAME in str(key) for key in schema_keys)

    @pytest.mark.asyncio
    async def test_discovery_with_static_ip_creates_device_with_hostname(
        self, mock_hass, mock_discovery_info
    ):
        """Test that providing static IP during discovery saves it to config."""
        flow = DysonConfigFlow()
        flow.hass = mock_hass
        flow.init_data = mock_discovery_info

        # Simulate user providing static IP
        user_input = {
            "connection_type": "local_cloud_fallback",
            CONF_HOSTNAME: "192.168.1.100",
        }

        with patch(
            "custom_components.hass_dyson.device_utils.create_cloud_device_config"
        ) as mock_create_config:
            mock_create_config.return_value = {
                CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
                CONF_HOSTNAME: "192.168.1.100",
                "connection_type": "local_cloud_fallback",
            }

            result = await flow.async_step_discovery_connection(user_input)

            # Verify create_cloud_device_config was called with hostname
            mock_create_config.assert_called_once()
            call_kwargs = mock_create_config.call_args.kwargs
            assert call_kwargs["hostname"] == "192.168.1.100"
            assert call_kwargs["connection_type"] == "local_cloud_fallback"

            # Verify entry is created
            assert result["type"] == "create_entry"

    @pytest.mark.asyncio
    async def test_discovery_without_hostname_creates_device_with_none(
        self, mock_hass, mock_discovery_info
    ):
        """Test that leaving hostname empty passes None to config creation."""
        flow = DysonConfigFlow()
        flow.hass = mock_hass
        flow.init_data = mock_discovery_info

        # Simulate user leaving hostname blank
        user_input = {
            "connection_type": "local_cloud_fallback",
            CONF_HOSTNAME: "",  # Empty string
        }

        with patch(
            "custom_components.hass_dyson.device_utils.create_cloud_device_config"
        ) as mock_create_config:
            mock_create_config.return_value = {
                CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
                "connection_type": "local_cloud_fallback",
            }

            result = await flow.async_step_discovery_connection(user_input)

            # Verify create_cloud_device_config was called with None hostname
            mock_create_config.assert_called_once()
            call_kwargs = mock_create_config.call_args.kwargs
            assert call_kwargs["hostname"] is None

            # Verify entry is created
            assert result["type"] == "create_entry"

    @pytest.mark.asyncio
    async def test_discovery_confirm_redirects_to_connection_step(
        self, mock_hass, mock_discovery_info
    ):
        """Test that discovery confirmation redirects to connection configuration."""
        flow = DysonConfigFlow()
        flow.hass = mock_hass
        flow.init_data = mock_discovery_info

        # Simulate user confirming device
        user_input = {"confirm": True}

        with patch.object(
            flow, "async_step_discovery_connection", return_value=MagicMock()
        ) as mock_connection_step:
            await flow.async_step_discovery_confirm(user_input)

            # Verify we're redirected to connection configuration
            mock_connection_step.assert_called_once()


class TestDeviceReconfigurationWithHostname:
    """Test device reconfiguration flow with hostname field."""

    @pytest.fixture
    def mock_config_entry_cloud(self):
        """Create a mock config entry for a cloud device."""
        entry = MagicMock(spec=config_entries.ConfigEntry)
        entry.entry_id = "test_entry_123"
        entry.data = {
            CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
            "connection_type": "local_cloud_fallback",
            "parent_entry_id": "parent_123",
        }
        return entry

    @pytest.fixture
    def mock_config_entry_manual(self):
        """Create a mock config entry for a manual device."""
        entry = MagicMock(spec=config_entries.ConfigEntry)
        entry.entry_id = "manual_entry_123"
        entry.data = {
            CONF_SERIAL_NUMBER: "VS6-EU-HJA5678B",
            CONF_HOSTNAME: "192.168.1.50",
            "connection_type": "local_only",
        }
        return entry

    @pytest.mark.asyncio
    async def test_reconfiguration_shows_hostname_field(
        self, mock_hass, mock_config_entry_cloud
    ):
        """Test that reconfiguration form includes hostname field."""
        from custom_components.hass_dyson.config_flow import DysonOptionsFlow

        flow = DysonOptionsFlow(mock_config_entry_cloud)
        flow.hass = mock_hass

        # Get the reconfiguration form
        result = await flow.async_step_device_reconfigure_connection()

        # Verify form is shown
        assert result["type"] == "form"
        assert result["step_id"] == "device_reconfigure_connection"

        # Verify data schema includes hostname field
        schema_keys = list(result["data_schema"].schema.keys())
        assert any(CONF_HOSTNAME in str(key) for key in schema_keys)

    @pytest.mark.asyncio
    async def test_reconfiguration_shows_current_hostname(
        self, mock_hass, mock_config_entry_manual
    ):
        """Test that reconfiguration form displays current hostname value."""
        from custom_components.hass_dyson.config_flow import DysonOptionsFlow

        flow = DysonOptionsFlow(mock_config_entry_manual)
        flow.hass = mock_hass

        # Get the reconfiguration form
        result = await flow.async_step_device_reconfigure_connection()

        # Verify form shows current hostname as default
        schema = result["data_schema"].schema
        hostname_field = next(
            (key for key in schema.keys() if CONF_HOSTNAME in str(key)), None
        )
        assert hostname_field is not None
        assert hostname_field.default() == "192.168.1.50"

    @pytest.mark.asyncio
    async def test_reconfiguration_saves_new_hostname(
        self, mock_hass, mock_config_entry_cloud
    ):
        """Test that reconfiguration saves updated hostname."""
        from custom_components.hass_dyson.config_flow import DysonOptionsFlow

        flow = DysonOptionsFlow(mock_config_entry_cloud)
        flow.hass = mock_hass

        # Mock the config entry update method
        mock_hass.config_entries.async_update_entry = MagicMock()
        mock_hass.config_entries.async_reload = AsyncMock()

        # Simulate user adding hostname
        user_input = {
            "connection_type": "local_cloud_fallback",
            CONF_HOSTNAME: "192.168.1.200",
        }

        result = await flow.async_step_device_reconfigure_connection(user_input)

        # Verify config entry was updated with hostname
        mock_hass.config_entries.async_update_entry.assert_called_once()
        call_args = mock_hass.config_entries.async_update_entry.call_args
        updated_data = call_args.kwargs["data"]
        assert updated_data[CONF_HOSTNAME] == "192.168.1.200"

        # Verify reload was triggered
        mock_hass.config_entries.async_reload.assert_called_once()

        # Verify success
        assert result["type"] == "create_entry"

    @pytest.mark.asyncio
    async def test_reconfiguration_removes_hostname_when_cleared(
        self, mock_hass, mock_config_entry_manual
    ):
        """Test that clearing hostname field removes it from config."""
        from custom_components.hass_dyson.config_flow import DysonOptionsFlow

        flow = DysonOptionsFlow(mock_config_entry_manual)
        flow.hass = mock_hass

        # Mock the config entry update method
        mock_hass.config_entries.async_update_entry = MagicMock()
        mock_hass.config_entries.async_reload = AsyncMock()

        # Simulate user clearing hostname
        user_input = {
            "connection_type": "local_only",
            CONF_HOSTNAME: "",  # Empty string to clear
        }

        result = await flow.async_step_device_reconfigure_connection(user_input)

        # Verify config entry was updated without hostname
        mock_hass.config_entries.async_update_entry.assert_called_once()
        call_args = mock_hass.config_entries.async_update_entry.call_args
        updated_data = call_args.kwargs["data"]
        assert CONF_HOSTNAME not in updated_data

        # Verify reload was triggered
        mock_hass.config_entries.async_reload.assert_called_once()

        # Verify success
        assert result["type"] == "create_entry"


class TestCoordinatorHostnameResolution:
    """Test coordinator hostname resolution logic."""

    @pytest.mark.asyncio
    async def test_uses_configured_hostname_first(self):
        """Test that configured hostname takes priority over API hostname."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

        mock_hass = MagicMock()
        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
            CONF_HOSTNAME: "192.168.1.100",  # User-configured
        }

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry
            # serial_number is a @property that reads from config_entry.data

            # Mock device_info with different hostname from API
            mock_device_info = MagicMock()
            mock_device_info.hostname = "10.0.0.50"  # API hostname

            # Test _get_device_host method
            hostname = coordinator._get_device_host(mock_device_info)

            # Should use configured hostname, not API hostname
            assert hostname == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_uses_api_hostname_when_no_configured_hostname(self):
        """Test that API hostname is used when no user-configured hostname."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

        mock_hass = MagicMock()
        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
            # No CONF_HOSTNAME configured
        }

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry
            # serial_number is a @property that reads from config_entry.data

            # Mock device_info with API hostname
            mock_device_info = MagicMock()
            mock_device_info.hostname = "10.0.0.50"

            # Test _get_device_host method
            hostname = coordinator._get_device_host(mock_device_info)

            # Should use API hostname
            assert hostname == "10.0.0.50"

    @pytest.mark.asyncio
    async def test_falls_back_to_serial_local_when_no_hostname(self):
        """Test fallback to {serial}.local when no hostname configured or from API."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

        mock_hass = MagicMock()
        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
            # No CONF_HOSTNAME configured
        }

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry
            # serial_number is a @property that reads from config_entry.data

            # Mock device_info without hostname
            mock_device_info = MagicMock()
            mock_device_info.hostname = None

            # Test _get_device_host method
            hostname = coordinator._get_device_host(mock_device_info)

            # Should fall back to {serial}.local
            assert hostname == "VS6-EU-HJA1234A.local"


class TestDeviceUtilsHostnameSupport:
    """Test device utils hostname parameter support."""

    def test_create_cloud_device_config_accepts_hostname(self):
        """Test that create_cloud_device_config accepts hostname parameter."""
        from custom_components.hass_dyson.device_utils import create_cloud_device_config

        device_info = {
            "name": "Test Fan",
            "product_type": "438",
            "category": "ec",
        }

        config = create_cloud_device_config(
            serial_number="VS6-EU-HJA1234A",
            username="test@example.com",
            device_info=device_info,
            hostname="192.168.1.100",
        )

        # Verify hostname is included in config
        assert config[CONF_HOSTNAME] == "192.168.1.100"

    def test_create_cloud_device_config_omits_none_hostname(self):
        """Test that None hostname is omitted from config."""
        from custom_components.hass_dyson.device_utils import create_cloud_device_config

        device_info = {
            "name": "Test Fan",
            "product_type": "438",
            "category": "ec",
        }

        config = create_cloud_device_config(
            serial_number="VS6-EU-HJA1234A",
            username="test@example.com",
            device_info=device_info,
            hostname=None,
        )

        # Verify hostname is not included when None
        assert CONF_HOSTNAME not in config
