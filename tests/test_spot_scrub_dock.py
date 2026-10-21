"""Spot+Scrub dock state and dock work timer; no hardware or credentials."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.hass_dyson.device import DysonDevice
from custom_components.hass_dyson.sensor import (
    DysonRobotDockStateSensor,
    DysonRobotDockTimerEndSensor,
    async_setup_entry,
)

TOPIC = "RB05/TEST-SERIAL/status"

# prop.post as sent by an RB05 while the dock dried the mop roller
DRYING_POST = {
    "msgId": "1",
    "method": "prop.post",
    "params": {"work_time": {"type": 3, "total": 14400, "surplus": 4080}},
}


@pytest.fixture
def device():
    """Device with no state, ready to have messages applied."""
    return DysonDevice(
        MagicMock(), "TEST-SERIAL", "192.0.2.1", "test", mqtt_prefix="RB05"
    )


@pytest.fixture
def sensor_coordinator(device):
    """Coordinator exposing the device the sensors read from."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-SERIAL"
    coordinator.device = device
    return coordinator


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"dockState": "DRYING_MOP"}, "DRYING_MOP"),
        ({"product-state": {"dockState": "DRYING_MOP"}}, "DRYING_MOP"),
        ({}, None),
        ({"dockState": ""}, None),
    ],
)
def test_dock_state_is_read_raw(device, state, expected):
    """dockState is passed through from either level; absent or empty is None."""
    device._state_data = state

    assert device.robot_dock_state == expected


def test_prop_post_work_time_sets_timer_end(device):
    """The end time is the arrival time plus the remaining seconds."""
    with patch("custom_components.hass_dyson.device.time.time", return_value=1000.0):
        device._process_message_data(DRYING_POST, TOPIC)

    with patch(
        "custom_components.hass_dyson.device.dt_util.utcnow",
        return_value=dt_util.utc_from_timestamp(1000.0),
    ):
        assert device.robot_dock_timer_end == dt_util.utc_from_timestamp(5080.0)


def test_prop_post_still_reaches_callbacks(device):
    """Handling the timer does not swallow the message for other consumers."""
    received = []
    device.add_message_callback(lambda topic, data: received.append(data))

    device._process_message_data(DRYING_POST, TOPIC)

    assert received == [DRYING_POST]


def test_timer_end_is_none_once_passed(device):
    """A timer whose end has passed is not reported as still running."""
    device._dock_timer_end = 0.0

    assert device.robot_dock_timer_end is None


@pytest.mark.parametrize(
    "params",
    [None, {"work_time": "x"}, {"work_time": {"type": 3}}, {"other_prop": 1}],
)
def test_malformed_or_unrelated_prop_post_is_ignored(device, params):
    """Unknown or malformed properties leave the timer untouched."""
    device._process_message_data({"method": "prop.post", "params": params}, TOPIC)

    assert device.robot_dock_timer_end is None


def test_sensors_expose_device_values(
    pure_mock_sensor_entity, sensor_coordinator, device
):
    """The dock state passes through; the timer sensor shows the end time."""
    device._state_data = {"dockState": "DRYING_MOP"}
    now = dt_util.utcnow()
    device._dock_timer_end = now.timestamp() + 4080
    state = pure_mock_sensor_entity(DysonRobotDockStateSensor, sensor_coordinator)
    timer = pure_mock_sensor_entity(DysonRobotDockTimerEndSensor, sensor_coordinator)

    state._handle_coordinator_update()
    timer._handle_coordinator_update()

    assert state.native_value == "DRYING_MOP"
    assert abs(timer.native_value - (now + timedelta(seconds=4080))) < timedelta(
        seconds=1
    )


def test_sensors_without_a_device(pure_mock_sensor_entity, sensor_coordinator):
    """A disconnected coordinator leaves both sensors empty, not erroring."""
    sensor_coordinator.device = None
    state = pure_mock_sensor_entity(DysonRobotDockStateSensor, sensor_coordinator)
    timer = pure_mock_sensor_entity(DysonRobotDockTimerEndSensor, sensor_coordinator)

    state._handle_coordinator_update()
    timer._handle_coordinator_update()

    assert state.native_value is None
    assert timer.native_value is None


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["RB05", "277", "527K"])
async def test_only_spot_scrub_gets_dock_sensors(prefix):
    """Vis Nav and the older robots have no washing dock."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-SERIAL"
    coordinator.device.mqtt_prefix = prefix
    coordinator.device_capabilities = []
    coordinator.device_category = ["robot"]
    coordinator.data = {}
    coordinator.config_entry.data = {}
    entry = MagicMock(entry_id="test")
    hass = MagicMock(data={"hass_dyson": {"test": coordinator}})
    add = MagicMock()

    await async_setup_entry(hass, entry, add)

    added = add.call_args.args[0]
    expected = 1 if prefix == "RB05" else 0
    assert sum(isinstance(e, DysonRobotDockStateSensor) for e in added) == expected
    assert sum(isinstance(e, DysonRobotDockTimerEndSensor) for e in added) == expected
