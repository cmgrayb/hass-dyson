"""Test the visibility of a device that silently runs on its cloud fallback."""

import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.const import (
    CONF_DHCP_HOST,
    CONF_HOSTNAME,
    DOMAIN,
    HOST_SOURCE_CLOUD_API,
    HOST_SOURCE_CONFIGURED,
    HOST_SOURCE_DHCP,
    HOST_SOURCE_MDNS,
    HOST_SOURCE_UNKNOWN,
)
from custom_components.hass_dyson.coordinator import (
    CONFIGURED_HOST_ISSUE_DELAY,
    DysonDataUpdateCoordinator,
)
from custom_components.hass_dyson.device import DysonDevice
from custom_components.hass_dyson.sensor import DysonIpAddressSensor

COORDINATOR = "custom_components.hass_dyson.coordinator"
ISSUE_ID = "configured_host_unreachable_entry123"

# Sentinel for _coordinator(host=...), so None means "no host resolved yet"
# rather than "not given".
_USE_HOSTNAME = object()


def _coordinator(
    hostname: str = "dyson-host",
    preferred: str = "local",
    fallback: bool = True,
    host_source: str = HOST_SOURCE_CONFIGURED,
    host: str | None = _USE_HOSTNAME,
) -> DysonDataUpdateCoordinator:
    """Return a coordinator with a device in the given connection state."""
    coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
    coordinator.hass = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "entry123"
    coordinator.config_entry.title = "Bedroom purifier"
    coordinator.config_entry.data = {CONF_HOSTNAME: hostname}
    coordinator._local_fallback_since = None
    coordinator._host_source = host_source
    coordinator._serial_number = "TEST-SERIAL"
    coordinator.device = MagicMock()
    coordinator.device.preferred_connection_type = preferred
    coordinator.device.using_fallback = fallback
    coordinator.device.host = hostname if host is _USE_HOSTNAME else host
    return coordinator


@pytest.fixture
def issues():
    """Patch the issue registry helpers used by the coordinator."""
    with (
        patch(f"{COORDINATOR}.ir.async_create_issue") as create,
        patch(f"{COORDINATOR}.ir.async_delete_issue") as delete,
    ):
        yield create, delete


def test_issue_raised_after_delay(issues) -> None:
    """A configured host on cloud fallback is reported only after the delay."""
    create, delete = issues
    coordinator = _coordinator()

    with patch(f"{COORDINATOR}.time.monotonic", return_value=1000.0):
        coordinator._async_update_configured_host_issue()
    create.assert_not_called()

    with patch(
        f"{COORDINATOR}.time.monotonic",
        return_value=1000.0 + CONFIGURED_HOST_ISSUE_DELAY,
    ):
        coordinator._async_update_configured_host_issue()

    create.assert_called_once()
    args, kwargs = create.call_args
    assert args[1:] == (DOMAIN, ISSUE_ID)
    assert kwargs["translation_key"] == "configured_host_unreachable"
    assert kwargs["is_fixable"] is False
    assert kwargs["translation_placeholders"] == {
        "device_name": "Bedroom purifier",
        "hostname": "dyson-host",
    }
    delete.assert_not_called()


def test_issue_cleared_when_local_returns(issues) -> None:
    """The issue is removed and the timer reset once local works again."""
    create, delete = issues
    coordinator = _coordinator()
    coordinator._local_fallback_since = 1.0
    coordinator.device.using_fallback = False

    coordinator._async_update_configured_host_issue()

    delete.assert_called_once_with(coordinator.hass, DOMAIN, ISSUE_ID)
    create.assert_not_called()
    assert coordinator._local_fallback_since is None


def test_no_issue_when_cloud_is_preferred(issues) -> None:
    """A cloud-first device is not on an unexpected fallback, so it stays quiet."""
    create, delete = issues
    coordinator = _coordinator(preferred="cloud")

    with patch(
        f"{COORDINATOR}.time.monotonic", return_value=CONFIGURED_HOST_ISSUE_DELAY * 10
    ):
        coordinator._async_update_configured_host_issue()
        coordinator._async_update_configured_host_issue()

    create.assert_not_called()
    assert delete.call_count == 2


@pytest.mark.parametrize(
    "host_source",
    [HOST_SOURCE_CLOUD_API, HOST_SOURCE_DHCP, HOST_SOURCE_MDNS, HOST_SOURCE_UNKNOWN],
)
def test_discovered_host_also_reported(issues, host_source: str) -> None:
    """A discovered address that stops answering is as silent as a static one.

    Nothing was typed into the connection options, so the remedy differs and the
    wording differs with it, but the device is still stuck on the cloud.
    """
    create, _ = issues
    coordinator = _coordinator(
        hostname="", host_source=host_source, host="TEST-SERIAL.local"
    )

    with patch(f"{COORDINATOR}.time.monotonic", return_value=1000.0):
        coordinator._async_update_configured_host_issue()
    create.assert_not_called()

    with patch(
        f"{COORDINATOR}.time.monotonic",
        return_value=1000.0 + CONFIGURED_HOST_ISSUE_DELAY,
    ):
        coordinator._async_update_configured_host_issue()

    create.assert_called_once()
    args, kwargs = create.call_args
    assert args[1:] == (DOMAIN, ISSUE_ID)
    assert kwargs["translation_key"] == "discovered_host_unreachable"
    assert kwargs["translation_placeholders"] == {
        "device_name": "Bedroom purifier",
        "hostname": "TEST-SERIAL.local",
    }


async def test_shutdown_removes_issue(issues) -> None:
    """Unloading the device entry removes its issue."""
    _, delete = issues
    coordinator = _coordinator()
    coordinator._serial_number = "TEST-SERIAL"
    device = coordinator.device
    device.disconnect = AsyncMock()

    await coordinator.async_shutdown()

    device.disconnect.assert_awaited_once()
    delete.assert_called_with(coordinator.hass, DOMAIN, ISSUE_ID)


def test_device_exposes_fallback_state() -> None:
    """The device reports its preferred connection and whether it fell back."""
    device = DysonDevice.__new__(DysonDevice)
    device._preferred_connection_type = "local"
    device._using_fallback = True

    assert device.preferred_connection_type == "local"
    assert device.using_fallback is True


@pytest.mark.parametrize(
    "key", ["configured_host_unreachable", "discovered_host_unreachable"]
)
def test_issue_translation_placeholders(key: str) -> None:
    """The English issue text exists and uses exactly the placeholders passed."""
    path = (
        Path(__file__).parent.parent
        / "custom_components/hass_dyson/translations/en.json"
    )
    issue = json.loads(path.read_text(encoding="utf-8"))["issues"][key]

    text = issue["title"] + issue["description"]
    assert "{device_name}" in issue["title"]
    assert "{hostname}" in issue["description"]
    assert set(re.findall(r"{(\w+)}", text)) == {
        "device_name",
        "hostname",
    }


@pytest.mark.parametrize(
    ("data", "api_hostname", "expected_source", "expected_host"),
    [
        pytest.param(
            {CONF_HOSTNAME: "192.168.1.10"},
            "ignored.local",
            HOST_SOURCE_CONFIGURED,
            "192.168.1.10",
            id="configured_wins",
        ),
        pytest.param(
            {CONF_HOSTNAME: ""},
            "TEST-SERIAL.local",
            HOST_SOURCE_CLOUD_API,
            "TEST-SERIAL.local",
            id="cloud_api",
        ),
        pytest.param(
            {CONF_HOSTNAME: "", CONF_DHCP_HOST: "192.168.1.11"},
            None,
            HOST_SOURCE_DHCP,
            "192.168.1.11",
            id="dhcp",
        ),
        pytest.param(
            {CONF_HOSTNAME: ""},
            None,
            HOST_SOURCE_MDNS,
            "TEST-SERIAL.local",
            id="mdns_fallback",
        ),
    ],
)
def test_host_source_follows_the_branch_taken(
    data: dict, api_hostname: str | None, expected_source: str, expected_host: str
) -> None:
    """Each priority level in _get_device_host records where the host came from."""
    coordinator = _coordinator()
    coordinator.config_entry.data = data
    coordinator._host_source = HOST_SOURCE_UNKNOWN
    device_info = MagicMock()
    device_info.hostname = api_hostname

    assert coordinator._get_device_host(device_info) == expected_host
    assert coordinator.host_source == expected_source


@pytest.mark.parametrize(
    ("host", "host_source", "is_ip", "is_configured"),
    [
        pytest.param(
            "192.168.1.10", HOST_SOURCE_CONFIGURED, True, True, id="static_ip"
        ),
        pytest.param(
            "TEST-SERIAL.local", HOST_SOURCE_MDNS, False, False, id="unresolved_mdns"
        ),
        pytest.param(None, HOST_SOURCE_UNKNOWN, False, False, id="no_host_yet"),
    ],
)
def test_ip_sensor_reports_host_provenance(
    host: str | None, host_source: str, is_ip: bool, is_configured: bool
) -> None:
    """The IP sensor says where its value came from and whether it is an address.

    A name that nothing resolves reads exactly like a working value in the
    state alone, which is the case this entity is meant to diagnose.
    """
    coordinator = _coordinator(host_source=host_source, host=host)
    sensor = DysonIpAddressSensor.__new__(DysonIpAddressSensor)
    sensor.coordinator = coordinator

    assert sensor.native_value == host
    assert sensor.extra_state_attributes == {
        "host_source": host_source,
        "is_ip_address": is_ip,
        "is_configured": is_configured,
    }
