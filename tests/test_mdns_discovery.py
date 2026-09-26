"""Tests for mDNS discovery of devices via Home Assistant's zeroconf instance.

Covers the service-type/instance-name matching in ``_discover_device_via_mdns`` and the
``.local`` resolution done through HA's zeroconf rather than the OS resolver (some devices
answer mDNS with IP TTL 16, which systemd-resolved discards).
"""

import ipaddress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.config_flow import _discover_device_via_mdns
from custom_components.hass_dyson.const import CONF_SERIAL_NUMBER, MDNS_SERVICE_DYSON

SERIAL = "TEST123456"
ANNOUNCED_NAME = f"527_{SERIAL}.{MDNS_SERVICE_DYSON}"


def _fake_browser_class(announced_names):
    """Return a ServiceBrowser stand-in that announces the given names immediately."""

    class FakeServiceBrowser:
        def __init__(self, zc, type_, listener):
            for name in announced_names:
                listener.add_service(zc, type_, name)

        def cancel(self):
            pass

    return FakeServiceBrowser


def _fake_resolver_class(addresses):
    """Return an AddressResolver stand-in answering with the given addresses (or nothing)."""

    class FakeAddressResolver:
        def __init__(self, name):
            self.name = name

        def request(self, zc, timeout):
            return bool(addresses)

        async def async_request(self, zc, timeout):
            return bool(addresses)

        def ip_addresses_by_version(self, version):
            return [ipaddress.ip_address(a) for a in addresses]

    return FakeAddressResolver


def test_mdns_service_type_matches_device_announcement():
    """Devices announce ``_dyson_mqtt._tcp`` (underscore), not ``_dyson._mqtt._tcp``."""
    assert MDNS_SERVICE_DYSON == "_dyson_mqtt._tcp.local."


class TestDiscoverDeviceViaMdns:
    """``_discover_device_via_mdns`` finds devices by the name they actually announce."""

    @pytest.mark.asyncio
    async def test_matches_product_type_prefixed_instance_name(self, mock_hass):
        """A ``<product_type>_<serial>`` announcement is matched on the serial suffix."""
        service_info = MagicMock()
        service_info.parsed_addresses.return_value = ["192.168.1.50"]
        zc_instance = MagicMock()
        zc_instance.get_service_info.return_value = service_info

        with (
            patch(
                "homeassistant.components.zeroconf.async_get_instance",
                return_value=zc_instance,
            ),
            patch("zeroconf.ServiceBrowser", _fake_browser_class([ANNOUNCED_NAME])),
            patch("zeroconf.AddressResolver", _fake_resolver_class([])),
        ):
            result = await _discover_device_via_mdns(mock_hass, SERIAL)

        assert result == "192.168.1.50"
        zc_instance.get_service_info.assert_called_once_with(
            MDNS_SERVICE_DYSON, ANNOUNCED_NAME
        )

    @pytest.mark.asyncio
    async def test_ignores_other_devices(self, mock_hass):
        """Announcements for other serials are not looked up."""
        zc_instance = MagicMock()
        other = f"438_OTHER999999.{MDNS_SERVICE_DYSON}"

        with (
            patch(
                "homeassistant.components.zeroconf.async_get_instance",
                return_value=zc_instance,
            ),
            patch("zeroconf.ServiceBrowser", _fake_browser_class([other])),
            patch("zeroconf.AddressResolver", _fake_resolver_class([])),
        ):
            result = await _discover_device_via_mdns(mock_hass, SERIAL, timeout=1)

        assert result is None
        zc_instance.get_service_info.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_hostname_via_zeroconf(self, mock_hass):
        """With no service match, ``{serial}.local`` is resolved through HA's zeroconf."""
        zc_instance = MagicMock()

        with (
            patch(
                "homeassistant.components.zeroconf.async_get_instance",
                return_value=zc_instance,
            ),
            patch("zeroconf.ServiceBrowser", _fake_browser_class([])),
            patch("zeroconf.AddressResolver", _fake_resolver_class(["192.168.1.51"])),
        ):
            result = await _discover_device_via_mdns(mock_hass, SERIAL, timeout=1)

        assert result == "192.168.1.51"

    @pytest.mark.asyncio
    async def test_returns_none_when_nothing_answers(self, mock_hass):
        """No service match and no hostname answer gives ``None``."""
        with (
            patch(
                "homeassistant.components.zeroconf.async_get_instance",
                return_value=MagicMock(),
            ),
            patch("zeroconf.ServiceBrowser", _fake_browser_class([])),
            patch("zeroconf.AddressResolver", _fake_resolver_class([])),
        ):
            result = await _discover_device_via_mdns(mock_hass, SERIAL, timeout=1)

        assert result is None


class TestCoordinatorResolveLocalHost:
    """``_async_resolve_local_host`` resolves ``.local`` names via HA's zeroconf."""

    def _coordinator(self):
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

        mock_hass = MagicMock()
        mock_config_entry = MagicMock()
        mock_config_entry.data = {CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A"}
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
        coordinator.hass = mock_hass
        coordinator.config_entry = mock_config_entry
        return coordinator

    @pytest.mark.asyncio
    async def test_resolves_to_ip(self):
        """An mDNS answer replaces the hostname with the address."""
        coordinator = self._coordinator()
        aiozc = MagicMock()

        with (
            patch(
                "homeassistant.components.zeroconf.async_get_async_instance",
                AsyncMock(return_value=aiozc),
            ),
            patch("zeroconf.AddressResolver", _fake_resolver_class(["192.168.1.52"])),
        ):
            host = await coordinator._async_resolve_local_host("VS6-EU-HJA1234A.local")

        assert host == "192.168.1.52"

    @pytest.mark.asyncio
    async def test_keeps_hostname_when_nothing_answers(self):
        """No answer leaves the hostname unchanged (previous behaviour)."""
        coordinator = self._coordinator()

        with (
            patch(
                "homeassistant.components.zeroconf.async_get_async_instance",
                AsyncMock(return_value=MagicMock()),
            ),
            patch("zeroconf.AddressResolver", _fake_resolver_class([])),
        ):
            host = await coordinator._async_resolve_local_host("VS6-EU-HJA1234A.local")

        assert host == "VS6-EU-HJA1234A.local"

    @pytest.mark.asyncio
    async def test_keeps_hostname_on_error(self):
        """A zeroconf failure is logged and the hostname is kept."""
        coordinator = self._coordinator()

        with patch(
            "homeassistant.components.zeroconf.async_get_async_instance",
            AsyncMock(side_effect=RuntimeError("zeroconf unavailable")),
        ):
            host = await coordinator._async_resolve_local_host("VS6-EU-HJA1234A.local")

        assert host == "VS6-EU-HJA1234A.local"


class TestCreateCloudDeviceHost:
    """Cloud-created devices resolve a ``.local`` fallback host before connecting."""

    def _coordinator(self):
        coordinator = TestCoordinatorResolveLocalHost()._coordinator()
        coordinator._firmware_version = "Unknown"
        coordinator._device_capabilities = []
        coordinator._device_category = ["ec"]
        return coordinator

    async def _run(self, coordinator, host_from_config):
        device = MagicMock()
        device.connect = AsyncMock(return_value=True)

        with (
            patch.object(
                coordinator, "_get_device_host", return_value=host_from_config
            ),
            patch.object(
                coordinator,
                "_async_resolve_local_host",
                AsyncMock(return_value="192.168.1.53"),
            ) as resolve,
            patch.object(coordinator, "_get_mqtt_prefix", return_value="438"),
            patch.object(
                coordinator,
                "_get_effective_connection_type",
                return_value="local_cloud_fallback",
            ),
            patch.object(
                coordinator, "_refine_capabilities_from_device_state", AsyncMock()
            ),
            patch(
                "custom_components.hass_dyson.coordinator.ha_instance_id.async_get",
                AsyncMock(return_value="ha-uuid"),
            ),
            patch(
                "custom_components.hass_dyson.device.DysonDevice", return_value=device
            ) as device_cls,
        ):
            await coordinator._create_cloud_device(
                MagicMock(), {"mqtt_password": "secret"}, {}
            )

        return resolve, device_cls

    @pytest.mark.asyncio
    async def test_local_fallback_host_is_resolved(self):
        """``{serial}.local`` goes through mDNS resolution and the address is used."""
        coordinator = self._coordinator()

        resolve, device_cls = await self._run(coordinator, "VS6-EU-HJA1234A.local")

        resolve.assert_awaited_once_with("VS6-EU-HJA1234A.local")
        assert device_cls.call_args.args[2] == "192.168.1.53"

    @pytest.mark.asyncio
    async def test_configured_address_is_used_as_is(self):
        """A configured IP or hostname is passed through without mDNS resolution."""
        coordinator = self._coordinator()

        resolve, device_cls = await self._run(coordinator, "192.168.1.100")

        resolve.assert_not_awaited()
        assert device_cls.call_args.args[2] == "192.168.1.100"
