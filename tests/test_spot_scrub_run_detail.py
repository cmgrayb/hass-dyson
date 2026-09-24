"""Spot+Scrub run-detail properties and sensors; no hardware or credentials."""

from unittest.mock import MagicMock

import pytest

from custom_components.hass_dyson.device import DysonDevice
from custom_components.hass_dyson.sensor import (
    DysonRobotCleanActionSensor,
    DysonRobotCleanDurationSensor,
    async_setup_entry,
)


@pytest.fixture
def device():
    """Device with no state, ready to have CURRENT-STATE fields applied."""
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


def test_duration_read_from_top_level(device):
    """Robots report cleanDuration at the top level of CURRENT-STATE."""
    device._state_data = {"cleanDuration": 1800}

    assert device.robot_clean_duration == 1800


def test_duration_read_from_product_state(device):
    """Air-treatment style payloads nest fields under product-state."""
    device._state_data = {"product-state": {"cleanDuration": 60}}

    assert device.robot_clean_duration == 60


def test_duration_zero_is_kept(device):
    """A run that has just started reports zero, which is not 'missing'."""
    device._state_data = {"cleanDuration": 0}

    assert device.robot_clean_duration == 0


@pytest.mark.parametrize("state", [{}, {"cleanDuration": "unknown"}])
def test_duration_absent_or_unparsable(device, state):
    """Missing or malformed values report nothing rather than raising."""
    device._state_data = state

    assert device.robot_clean_duration is None


def test_action_read_from_top_level(device):
    """The action is reported raw, without mapping to a display label."""
    device._state_data = {"fullCleanAction": "VACUUMING_AND_MOPPING"}

    assert device.robot_full_clean_action == "VACUUMING_AND_MOPPING"


def test_action_read_from_product_state(device):
    """Nested payloads are handled the same way as top-level ones."""
    device._state_data = {"product-state": {"fullCleanAction": "MOPPING"}}

    assert device.robot_full_clean_action == "MOPPING"


@pytest.mark.parametrize("state", [{}, {"fullCleanAction": ""}])
def test_action_absent_or_empty(device, state):
    """An absent or empty action reports nothing."""
    device._state_data = state

    assert device.robot_full_clean_action is None


def test_sensors_expose_device_values(
    pure_mock_sensor_entity, sensor_coordinator, device
):
    """Both sensors pass the device value straight through."""
    device._state_data = {
        "cleanDuration": 6240,
        "fullCleanAction": "VACUUMING_AND_MOPPING",
    }
    duration = pure_mock_sensor_entity(
        DysonRobotCleanDurationSensor, sensor_coordinator
    )
    action = pure_mock_sensor_entity(DysonRobotCleanActionSensor, sensor_coordinator)

    duration._handle_coordinator_update()
    action._handle_coordinator_update()

    assert duration.native_value == 6240
    assert action.native_value == "VACUUMING_AND_MOPPING"


def test_sensors_without_a_device(pure_mock_sensor_entity, sensor_coordinator):
    """A disconnected coordinator leaves both sensors empty, not erroring."""
    sensor_coordinator.device = None
    duration = pure_mock_sensor_entity(
        DysonRobotCleanDurationSensor, sensor_coordinator
    )
    action = pure_mock_sensor_entity(DysonRobotCleanActionSensor, sensor_coordinator)

    duration._handle_coordinator_update()
    action._handle_coordinator_update()

    assert duration.native_value is None
    assert action.native_value is None


def test_unique_ids_are_distinct(pure_mock_sensor_entity, sensor_coordinator):
    """Entity registry keys must not collide."""
    duration = pure_mock_sensor_entity(
        DysonRobotCleanDurationSensor, sensor_coordinator
    )
    action = pure_mock_sensor_entity(DysonRobotCleanActionSensor, sensor_coordinator)

    assert duration.unique_id == "TEST-SERIAL_robot_clean_duration"
    assert action.unique_id == "TEST-SERIAL_robot_clean_action"


def test_action_survives_an_unexpected_state_shape(device):
    """A payload that raises on lookup reports nothing rather than propagating."""
    broken = MagicMock()
    broken.get.side_effect = TypeError("unexpected state shape")
    device._state_data = broken

    assert device.robot_full_clean_action is None


def test_duration_survives_an_unexpected_state_shape(device):
    """Same guard on the duration property."""
    broken = MagicMock()
    broken.get.side_effect = TypeError("unexpected state shape")
    device._state_data = broken

    assert device.robot_clean_duration is None


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["RB05", "277", "527K"])
async def test_only_spot_scrub_gets_run_detail_sensors(prefix):
    """Vis Nav and the older robots do not report these fields."""
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
    assert sum(isinstance(e, DysonRobotCleanDurationSensor) for e in added) == expected
    assert sum(isinstance(e, DysonRobotCleanActionSensor) for e in added) == expected
