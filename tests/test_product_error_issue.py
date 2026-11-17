"""Test the repair issue for failed self-checks in CURRENT-FAULTS (#553)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from custom_components.hass_dyson.const import DEVICE_CATEGORY_EC, DOMAIN
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

COORDINATOR = "custom_components.hass_dyson.coordinator"
ISSUE_ID = "product_error_entry123"


def _coordinator(errors, category=DEVICE_CATEGORY_EC) -> DysonDataUpdateCoordinator:
    """Return a coordinator whose device reports the given failing checks."""
    coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
    coordinator.hass = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "entry123"
    coordinator.config_entry.title = "Living room"
    coordinator._device_category = [category]
    coordinator.device = MagicMock()
    coordinator.device.product_errors = errors
    return coordinator


@pytest.fixture
def issues():
    """Patch the issue registry helpers used by the coordinator."""
    with (
        patch(f"{COORDINATOR}.ir.async_create_issue") as create,
        patch(f"{COORDINATOR}.ir.async_delete_issue") as delete,
    ):
        yield create, delete


def test_failing_checks_raise_an_issue(issues) -> None:
    """A failing check raises a warning that names the failing keys."""
    create, delete = issues
    coordinator = _coordinator({"iuw0": "FAIL", "prot": "FAIL"})

    coordinator._async_update_product_error_issue()

    delete.assert_not_called()
    create.assert_called_once()
    args, kwargs = create.call_args
    assert args[1:] == (DOMAIN, ISSUE_ID)
    assert kwargs["is_fixable"] is False
    assert kwargs["translation_key"] == "product_error"
    assert kwargs["translation_placeholders"] == {
        "device_name": "Living room",
        "errors": "iuw0: FAIL, prot: FAIL",
    }


def test_passing_checks_clear_the_issue(issues) -> None:
    """Once every check passes again the issue is removed."""
    create, delete = issues
    coordinator = _coordinator({})

    coordinator._async_update_product_error_issue()

    create.assert_not_called()
    delete.assert_called_once_with(coordinator.hass, DOMAIN, ISSUE_ID)


def test_no_faults_message_yet_changes_nothing(issues) -> None:
    """Before the first CURRENT-FAULTS message nothing is raised or cleared."""
    create, delete = issues

    _coordinator(None)._async_update_product_error_issue()

    create.assert_not_called()
    delete.assert_not_called()


@pytest.mark.parametrize("category", ["robot", "vacuum", "light"])
def test_only_for_ec_devices(issues, category) -> None:
    """Other device categories have their own fault entities."""
    create, delete = issues

    _coordinator({"prot": "FAIL"}, category)._async_update_product_error_issue()

    create.assert_not_called()
    delete.assert_not_called()


def test_no_device_changes_nothing(issues) -> None:
    """Without a device there is nothing to report."""
    create, delete = issues
    coordinator = _coordinator({"prot": "FAIL"})
    coordinator.device = None

    coordinator._async_update_product_error_issue()

    create.assert_not_called()
    delete.assert_not_called()


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_issue_is_translated(language) -> None:
    """Every language has the issue with both placeholders."""
    path = (
        Path(__file__).parent.parent
        / "custom_components/hass_dyson/translations"
        / f"{language}.json"
    )
    issue = json.loads(path.read_text(encoding="utf-8"))["issues"]["product_error"]
    assert "{device_name}" in issue["title"]
    assert "{device_name}" in issue["description"]
    assert "{errors}" in issue["description"]
