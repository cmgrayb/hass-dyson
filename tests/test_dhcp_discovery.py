"""Tests for the DHCP discovery config flow step.

Covers ``DysonConfigFlow.async_step_dhcp``, which enriches an already-configured
device's registry ``connections`` with its MAC address and records the DHCP-learned
IP, without ever creating a new config entry. Matching tries the Dyson
``{product_type}_{serial}`` DHCP hostname first, falling back to the discovery IP
when the hostname is missing or unrecognized (e.g. router/device-tracker-sourced
discovery events that don't carry the native DHCP hostname).
"""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from custom_components.hass_dyson.config_flow import DysonConfigFlow
from custom_components.hass_dyson.const import (
    CONF_DHCP_HOST,
    CONF_HOSTNAME,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)

SERIAL = "TEST123456"
MAC = "C8:FF:77:11:22:33"


def _discovery_info(
    hostname: str, mac: str = MAC, ip: str = "192.168.1.50"
) -> DhcpServiceInfo:
    return DhcpServiceInfo(ip=ip, hostname=hostname, macaddress=mac)


@pytest.fixture
def mock_config_entry():
    """Config entry already configured for the target serial."""
    entry = MagicMock()
    entry.entry_id = "existing_entry_id"
    entry.data = {CONF_SERIAL_NUMBER: SERIAL}
    return entry


@pytest.fixture
def config_flow(mock_hass, mock_config_entry):
    """DysonConfigFlow instance with one existing config entry for SERIAL."""
    flow = DysonConfigFlow()
    flow.hass = mock_hass
    flow.hass.config_entries.async_entries.return_value = [mock_config_entry]
    return flow


class TestAsyncStepDhcp:
    """``async_step_dhcp`` enriches an existing entry and never creates a new one."""

    @pytest.mark.asyncio
    async def test_matching_serial_updates_registry_and_aborts(
        self, config_flow, mock_config_entry
    ):
        """A hostname matching an existing serial merges the MAC and stores the IP."""
        mock_device = MagicMock()
        mock_device.id = "device_id_1"
        mock_device.connections = set()
        mock_registry = MagicMock()
        mock_registry.async_get_device_by_identifier.return_value = mock_device

        with patch(
            "homeassistant.helpers.device_registry.async_get",
            return_value=mock_registry,
        ):
            result = await config_flow.async_step_dhcp(_discovery_info(f"527_{SERIAL}"))

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"
        mock_registry.async_update_device.assert_called_once()
        _, kwargs = mock_registry.async_update_device.call_args
        assert kwargs["new_connections"] == {("mac", "c8:ff:77:11:22:33")}
        config_flow.hass.config_entries.async_update_entry.assert_called_once()
        _, update_kwargs = config_flow.hass.config_entries.async_update_entry.call_args
        assert update_kwargs["data"][CONF_DHCP_HOST] == "192.168.1.50"
        config_flow.hass.config_entries.async_schedule_reload.assert_called_once_with(
            mock_config_entry.entry_id
        )

    @pytest.mark.asyncio
    async def test_no_matching_serial_aborts_without_registry_write(self, config_flow):
        """A hostname whose serial doesn't match any entry aborts silently."""
        result = await config_flow.async_step_dhcp(_discovery_info("527_UNKNOWN000000"))

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "no_matching_device"
        config_flow.hass.config_entries.async_update_entry.assert_not_called()

    @pytest.mark.asyncio
    async def test_blank_hostname_falls_back_to_no_matching_device(self, config_flow):
        """A blank/malformed hostname with no IP match aborts with no_matching_device."""
        result = await config_flow.async_step_dhcp(
            _discovery_info("not-a-dyson-hostname")
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "no_matching_device"

    @pytest.mark.asyncio
    async def test_blank_hostname_matches_via_static_hostname_ip(
        self, config_flow, mock_config_entry
    ):
        """A blank hostname still matches when the discovery IP is the configured static IP."""
        mock_config_entry.data = {
            CONF_SERIAL_NUMBER: SERIAL,
            CONF_HOSTNAME: "192.168.1.50",
        }
        mock_device = MagicMock()
        mock_device.id = "device_id_1"
        mock_device.connections = set()
        mock_registry = MagicMock()
        mock_registry.async_get_device_by_identifier.return_value = mock_device

        with patch(
            "homeassistant.helpers.device_registry.async_get",
            return_value=mock_registry,
        ):
            result = await config_flow.async_step_dhcp(
                _discovery_info("", ip="192.168.1.50")
            )

        assert result["reason"] == "already_configured"
        mock_registry.async_update_device.assert_called_once()

    @pytest.mark.asyncio
    async def test_blank_hostname_matches_via_live_coordinator_host(
        self, config_flow, mock_config_entry
    ):
        """A blank hostname still matches via the entry's currently-connected host."""
        mock_config_entry.entry_id = "live_entry_id"
        mock_config_entry.data = {CONF_SERIAL_NUMBER: SERIAL}
        mock_coordinator = MagicMock()
        mock_coordinator.device.host = "192.168.1.75"
        config_flow.hass.data[DOMAIN] = {"live_entry_id": mock_coordinator}
        mock_registry = MagicMock()
        mock_registry.async_get_device_by_identifier.return_value = None

        with patch(
            "homeassistant.helpers.device_registry.async_get",
            return_value=mock_registry,
        ):
            result = await config_flow.async_step_dhcp(
                _discovery_info("router-reported-name", ip="192.168.1.75")
            )

        assert result["reason"] == "already_configured"

    @pytest.mark.asyncio
    async def test_existing_mac_connection_skips_registry_write(
        self, config_flow, mock_config_entry
    ):
        """No registry write occurs when the MAC connection is already recorded."""
        mock_device = MagicMock()
        mock_device.id = "device_id_1"
        mock_device.connections = {("mac", "c8:ff:77:11:22:33")}
        mock_registry = MagicMock()
        mock_registry.async_get_device_by_identifier.return_value = mock_device

        with patch(
            "homeassistant.helpers.device_registry.async_get",
            return_value=mock_registry,
        ):
            result = await config_flow.async_step_dhcp(_discovery_info(f"527_{SERIAL}"))

        assert result["reason"] == "already_configured"
        mock_registry.async_update_device.assert_not_called()

    @pytest.mark.asyncio
    async def test_unchanged_dhcp_host_skips_entry_update(
        self, config_flow, mock_config_entry
    ):
        """No config entry write occurs when the IP hasn't changed since last discovery."""
        mock_config_entry.data = {
            CONF_SERIAL_NUMBER: SERIAL,
            CONF_DHCP_HOST: "192.168.1.50",
        }
        mock_registry = MagicMock()
        mock_registry.async_get_device_by_identifier.return_value = None

        with patch(
            "homeassistant.helpers.device_registry.async_get",
            return_value=mock_registry,
        ):
            result = await config_flow.async_step_dhcp(_discovery_info(f"527_{SERIAL}"))

        assert result["reason"] == "already_configured"
        config_flow.hass.config_entries.async_update_entry.assert_not_called()
        config_flow.hass.config_entries.async_schedule_reload.assert_not_called()

    @pytest.mark.asyncio
    async def test_static_hostname_override_skips_reload(
        self, config_flow, mock_config_entry
    ):
        """A configured static hostname always wins, so no reload is scheduled."""
        mock_config_entry.data = {
            CONF_SERIAL_NUMBER: SERIAL,
            CONF_HOSTNAME: "my-dyson.example.com",
        }
        mock_registry = MagicMock()
        mock_registry.async_get_device_by_identifier.return_value = None

        with patch(
            "homeassistant.helpers.device_registry.async_get",
            return_value=mock_registry,
        ):
            result = await config_flow.async_step_dhcp(_discovery_info(f"527_{SERIAL}"))

        assert result["reason"] == "already_configured"
        config_flow.hass.config_entries.async_update_entry.assert_called_once()
        config_flow.hass.config_entries.async_schedule_reload.assert_not_called()
