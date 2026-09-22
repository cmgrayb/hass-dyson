"""Spot+Scrub numeric fault handling; shapes taken from public captures."""

from unittest.mock import MagicMock

import pytest

from custom_components.hass_dyson import (
    binary_sensor as binary_sensor_platform,
    sensor as sensor_platform,
)
from custom_components.hass_dyson.binary_sensor import (
    DysonRobotActionRequiredSensor,
)
from custom_components.hass_dyson.device import DysonDevice
from custom_components.hass_dyson.sensor import DysonRobotActiveFaultSensor

# Observed on an RB05: status and real problems share one list and are
# told apart only by nextActionRequired.
STATUS_FAULT = {"faultCode": "2105", "nextActionRequired": "LOG_ONLY"}
BLOCKING_FAULT = {"faultCode": "581", "nextActionRequired": "USER_CONTINUE"}
UNNAMED_FAULT = {"faultCode": "2102", "nextActionRequired": "LOG_ONLY"}


@pytest.fixture
def device():
    """Device with no state applied yet."""
    return DysonDevice(
        MagicMock(), "TEST-SERIAL", "192.0.2.1", "test", mqtt_prefix="RB05"
    )


@pytest.fixture
def coordinator(device):
    """Coordinator exposing the device."""
    c = MagicMock()
    c.serial_number = "TEST-SERIAL"
    c.device = device
    return c


def test_status_codes_are_not_action_required(device):
    """A LOG_ONLY code must not raise a problem."""
    device._state_data = {"activeFaults": [STATUS_FAULT]}

    assert device.robot_action_required_faults == []


def test_blocking_code_is_action_required(device):
    """Anything other than LOG_ONLY is filtered in."""
    device._state_data = {"activeFaults": [BLOCKING_FAULT, STATUS_FAULT]}

    assert device.robot_action_required_faults == [BLOCKING_FAULT]


def test_healthy_robot_reports_empty_not_none(device):
    """An empty list is an explicit all-clear, not 'unreported'."""
    device._state_data = {"activeFaults": []}

    assert device.robot_action_required_faults == []


def test_absent_list_is_unreported(device):
    """Devices that never send the field report nothing."""
    device._state_data = {}

    assert device.robot_action_required_faults is None


def test_known_code_is_named(pure_mock_sensor_entity, coordinator, device):
    """Codes on Dyson's published list are shown by name."""
    device._state_data = {"activeFaults": [BLOCKING_FAULT]}
    sensor = pure_mock_sensor_entity(DysonRobotActiveFaultSensor, coordinator)

    sensor._handle_coordinator_update()

    assert sensor.native_value == "Dock's clean water tank empty"
    assert sensor.extra_state_attributes["fault_code"] == "581"
    assert sensor.extra_state_attributes["next_action_required"] == "USER_CONTINUE"


def test_unknown_code_is_shown_raw(pure_mock_sensor_entity, coordinator, device):
    """An unlisted code is surfaced rather than guessed at."""
    device._state_data = {"activeFaults": [UNNAMED_FAULT]}
    sensor = pure_mock_sensor_entity(DysonRobotActiveFaultSensor, coordinator)

    sensor._handle_coordinator_update()

    assert sensor.native_value == "2102"


def test_no_faults_reads_none_string(pure_mock_sensor_entity, coordinator, device):
    """A healthy robot reads 'none', distinct from unknown."""
    device._state_data = {"activeFaults": []}
    sensor = pure_mock_sensor_entity(DysonRobotActiveFaultSensor, coordinator)

    sensor._handle_coordinator_update()

    assert sensor.native_value == "none"
    assert sensor.extra_state_attributes["fault_codes"] == []


def test_sensor_unreported_when_field_absent(
    pure_mock_sensor_entity, coordinator, device
):
    """No activeFaults at all leaves the sensor empty."""
    device._state_data = {}
    sensor = pure_mock_sensor_entity(DysonRobotActiveFaultSensor, coordinator)

    sensor._handle_coordinator_update()

    assert sensor.native_value is None


def test_problem_sensor_off_for_status_only(
    pure_mock_binary_sensor_entity, coordinator, device
):
    """Status codes must not leave a permanent problem state."""
    device._state_data = {"activeFaults": [STATUS_FAULT]}
    sensor = pure_mock_binary_sensor_entity(DysonRobotActionRequiredSensor, coordinator)

    sensor._handle_coordinator_update()

    assert sensor.is_on is False


def test_problem_sensor_on_and_lists_codes(
    pure_mock_binary_sensor_entity, coordinator, device
):
    """A blocking fault turns it on and names the code."""
    device._state_data = {"activeFaults": [STATUS_FAULT, BLOCKING_FAULT]}
    sensor = pure_mock_binary_sensor_entity(DysonRobotActionRequiredSensor, coordinator)

    sensor._handle_coordinator_update()

    assert sensor.is_on is True
    assert sensor.extra_state_attributes["fault_codes"] == ["581"]


def test_problem_sensor_unknown_without_a_device(
    pure_mock_binary_sensor_entity, coordinator
):
    """A disconnected coordinator reports unknown, not 'ok'."""
    coordinator.device = None
    sensor = pure_mock_binary_sensor_entity(DysonRobotActionRequiredSensor, coordinator)

    sensor._handle_coordinator_update()

    assert sensor.is_on is None


def _setup_coordinator(prefix):
    """Coordinator shaped for a robot platform setup run."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-SERIAL"
    coordinator.device.mqtt_prefix = prefix
    coordinator.device_capabilities = []
    coordinator.device_category = ["robot"]
    coordinator.config_entry.data = {}
    coordinator.data = {}
    return coordinator


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["RB05", "277"])
async def test_only_spot_scrub_gets_the_fault_sensor(prefix):
    """Other robots keep using the per-subsystem sensors."""
    coordinator = _setup_coordinator(prefix)
    entry = MagicMock(entry_id="test")
    hass = MagicMock(data={"hass_dyson": {"test": coordinator}})
    add = MagicMock()

    await sensor_platform.async_setup_entry(hass, entry, add)

    added = add.call_args.args[0]
    expected = 1 if prefix == "RB05" else 0
    assert sum(isinstance(e, DysonRobotActiveFaultSensor) for e in added) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["RB05", "277"])
async def test_only_spot_scrub_gets_the_problem_sensor(prefix):
    """The problem sensor is gated the same way."""
    coordinator = _setup_coordinator(prefix)
    entry = MagicMock(entry_id="test")
    hass = MagicMock(data={"hass_dyson": {"test": coordinator}})
    add = MagicMock()

    await binary_sensor_platform.async_setup_entry(hass, entry, add)

    added = add.call_args.args[0]
    expected = 1 if prefix == "RB05" else 0
    assert sum(isinstance(e, DysonRobotActionRequiredSensor) for e in added) == expected


def test_fault_sensor_unreported_without_a_device(pure_mock_sensor_entity, coordinator):
    """A disconnected coordinator leaves the fault sensor empty."""
    coordinator.device = None
    sensor = pure_mock_sensor_entity(DysonRobotActiveFaultSensor, coordinator)

    sensor._handle_coordinator_update()

    assert sensor.native_value is None
