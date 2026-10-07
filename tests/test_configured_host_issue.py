"""Test the repair issue raised when a configured host stops answering."""

import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.const import CONF_HOSTNAME, DOMAIN
from custom_components.hass_dyson.coordinator import (
    CONFIGURED_HOST_ISSUE_DELAY,
    DysonDataUpdateCoordinator,
)
from custom_components.hass_dyson.device import DysonDevice

COORDINATOR = "custom_components.hass_dyson.coordinator"
ISSUE_ID = "configured_host_unreachable_entry123"


def _coordinator(
    hostname: str = "dyson-host", preferred: str = "local", fallback: bool = True
) -> DysonDataUpdateCoordinator:
    """Return a coordinator with a device in the given connection state."""
    coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
    coordinator.hass = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "entry123"
    coordinator.config_entry.title = "Bedroom purifier"
    coordinator.config_entry.data = {CONF_HOSTNAME: hostname}
    coordinator._local_fallback_since = None
    coordinator.device = MagicMock()
    coordinator.device.preferred_connection_type = preferred
    coordinator.device.using_fallback = fallback
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


@pytest.mark.parametrize(
    ("hostname", "preferred"),
    [
        pytest.param("", "local", id="no_configured_host"),
        pytest.param("dyson-host", "cloud", id="cloud_preferred"),
    ],
)
def test_no_issue_when_fallback_is_expected(
    issues, hostname: str, preferred: str
) -> None:
    """Discovery-only devices and cloud-first devices never raise the issue."""
    create, delete = issues
    coordinator = _coordinator(hostname=hostname, preferred=preferred)

    with patch(
        f"{COORDINATOR}.time.monotonic", return_value=CONFIGURED_HOST_ISSUE_DELAY * 10
    ):
        coordinator._async_update_configured_host_issue()
        coordinator._async_update_configured_host_issue()

    create.assert_not_called()
    assert delete.call_count == 2


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


def test_issue_translation_placeholders() -> None:
    """The English issue text exists and uses exactly the placeholders passed."""
    path = (
        Path(__file__).parent.parent
        / "custom_components/hass_dyson/translations/en.json"
    )
    issue = json.loads(path.read_text(encoding="utf-8"))["issues"][
        "configured_host_unreachable"
    ]

    text = issue["title"] + issue["description"]
    assert "{device_name}" in issue["title"]
    assert "{hostname}" in issue["description"]
    assert set(re.findall(r"{(\w+)}", text)) == {
        "device_name",
        "hostname",
    }
