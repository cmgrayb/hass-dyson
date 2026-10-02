"""Sanitized RB05 protocol and entity tests; no hardware or credentials."""

import asyncio
import copy
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.hass_dyson.device import DysonDevice
from custom_components.hass_dyson.select import async_setup_entry
from custom_components.hass_dyson.spot_scrub import (
    MODE_CODES,
    mode_payload,
    read_preferences,
)
from custom_components.hass_dyson.spot_scrub_select import (
    DysonSpotScrubCleaningModeSelect,
)


@pytest.fixture
def preferences():
    """Response layout with synthetic room IDs and labels."""
    return {
        "prefer_on": 1,
        "room": [
            [1, "Room A", 2, 0, 0, 1, 0, 0, 1, 0, 1, 0],
            [2, '{"type":"hallway","name":"Room B"}', 2, 3, 0, 99, 0, 0, 0, 0, 2, 0],
        ],
        "uv_switch": [[1, 0], [2, 0]],
    }


@pytest.mark.parametrize("option,code", MODE_CODES.items())
def test_payload_preserves_settings(preferences, option, code):
    """Only the documented mode and response-only fields are transformed."""
    original = copy.deepcopy(preferences)
    payload = mode_payload(123, preferences, option)
    assert preferences == original
    assert payload["map_id"] == 123
    assert payload["uv_switch"] == preferences["uv_switch"]
    for before, after in zip(preferences["room"], payload["room_preference"]):
        assert len(after) == 11
        assert after[0] == before[0]
        assert after[2] == 0
        assert after[3] == code
        assert after[4:] == before[4:11]
    assert payload["room_preference"][1][1] == "Room B"


@pytest.mark.parametrize(
    "change", ["empty", "short", "tail", "flag", "uv", "duplicate", "label"]
)
def test_unknown_layout_rejected(preferences, change):
    """Never guess a new firmware layout or missing settings."""
    if change == "empty":
        preferences["room"] = []
    if change == "short":
        preferences["room"][0].pop()
    if change == "tail":
        preferences["room"][0][11] = 1
    if change == "flag":
        preferences["prefer_on"] = 0
    if change == "uv":
        preferences.pop("uv_switch")
    if change == "duplicate":
        preferences["room"][1][0] = 1
    if change == "label":
        preferences["room"][1][1] = '{"type":"hallway"}'
    with pytest.raises(ValueError):
        mode_payload(123, preferences, "mop_only")


@pytest.mark.asyncio
async def test_ambiguous_map():
    """Refuse multiple current maps instead of changing the wrong map."""
    device = MagicMock()
    device.send_jdm_command = AsyncMock(
        return_value={"map_list": [{"id": 1, "cur": True}, {"id": 2, "cur": True}]}
    )
    with pytest.raises(ValueError):
        await read_preferences(device)
    device.send_jdm_command.assert_awaited_once()


@pytest.fixture
def device():
    """Real device transport with a mocked publisher."""
    hass = MagicMock()
    dev = DysonDevice(hass, "TEST-SERIAL", "192.0.2.1", "test", mqtt_prefix="RB05")
    dev._connected = True
    dev._mqtt_client = MagicMock()

    async def execute(func, *args):
        return func(*args)

    hass.async_add_executor_job = execute
    return dev


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [0, 1])
async def test_request_matches_reply_and_preserves_callbacks(device, code):
    """Echoes/wrong IDs are ignored; callbacks survive after completion."""
    observer = MagicMock()
    device.add_message_callback(observer)

    def publish(topic, payload):
        request = json.loads(payload)
        response = dict(request, code=code, data={"result": 0})
        device._notify_callbacks(topic, response)  # command echo, not status
        device._notify_callbacks(
            topic.replace("command", "status"), dict(response, msgId="wrong")
        )
        device._notify_callbacks(topic.replace("command", "status"), response)
        return MagicMock(rc=0)

    device._mqtt_client.publish.side_effect = publish
    if code:
        with pytest.raises(RuntimeError):
            await device.send_jdm_command("service.get_preference", {})
    else:
        assert await device.send_jdm_command("service.get_preference", {}) == {
            "result": 0
        }
    assert device._message_callbacks == [observer]
    assert observer.call_count == 3


@pytest.mark.asyncio
async def test_timeout_and_late_reply(device):
    """Timed out requests remove callbacks and late replies are harmless."""
    device._mqtt_client.publish.return_value = MagicMock(rc=0)
    with pytest.raises(TimeoutError):
        await device.send_jdm_command("service.get_preference", {}, timeout=0.001)
    assert device._message_callbacks == []
    request = json.loads(device._mqtt_client.publish.call_args.args[1])
    device._notify_callbacks("RB05/TEST-SERIAL/status/jdm", dict(request, code=0))


@pytest.mark.asyncio
async def test_cancellation(device):
    """Cancelled requests do not retain callbacks."""
    device._mqtt_client.publish.return_value = MagicMock(rc=0)
    task = asyncio.create_task(device.send_jdm_command("service.get_preference", {}))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert device._message_callbacks == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["disconnected", "wrong_model", "publish"])
async def test_transport_failures(device, failure):
    """Fail without leaking callbacks or publishing to other Dyson models."""
    if failure == "disconnected":
        device._connected = False
    if failure == "wrong_model":
        device.mqtt_prefix = "277"
    device._mqtt_client.publish.return_value = MagicMock(rc=1)
    with pytest.raises((RuntimeError, ValueError)):
        await device.send_jdm_command("service.get_preference", {})
    assert device._message_callbacks == []
    if failure != "publish":
        device._mqtt_client.publish.assert_not_called()


@pytest.fixture
def selector(preferences):
    """Native selector with a simulated preference server."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-SERIAL"
    coordinator.device.robot_state = "INACTIVE_CHARGING"
    entity = DysonSpotScrubCleaningModeSelect(coordinator)
    entity.async_write_ha_state = MagicMock()
    state = copy.deepcopy(preferences)

    async def request(method, params):
        if method == "service.get_map_list":
            return {"map_list": [{"id": 123, "cur": True}]}
        if method == "service.get_preference":
            return copy.deepcopy(state)
        assert method == "service.set_preference"
        state["room"] = [row + [0] for row in params["room_preference"]]
        return {"result": 0}

    coordinator.device.send_jdm_command = AsyncMock(side_effect=request)
    return entity


@pytest.mark.asyncio
@pytest.mark.parametrize("option", MODE_CODES)
async def test_select_and_readback(selector, option):
    """A mode is shown only after successful readback; no START is sent."""
    await selector.async_select_option(option)
    assert selector.current_option == option
    assert not selector.extra_state_attributes["mixed_modes"]
    calls = selector.coordinator.device.send_jdm_command.await_args_list
    assert [c.args[0] for c in calls] == [
        "service.get_map_list",
        "service.get_preference",
        "service.set_preference",
        "service.get_map_list",
        "service.get_preference",
    ]


@pytest.mark.asyncio
async def test_mixed_modes_and_read_failure(selector):
    """Mixed room preferences are not misrepresented as a single mode."""
    await selector.async_update()
    assert selector.current_option is None
    assert selector.extra_state_attributes["mixed_modes"]
    selector.coordinator.device.send_jdm_command.side_effect = TimeoutError()
    await selector.async_update()
    assert not selector.available


@pytest.mark.asyncio
async def test_moving_guard(selector):
    """An active clean cannot have its preferences changed."""
    selector.coordinator.device.robot_state = "FULL_CLEAN_RUNNING"
    with pytest.raises(HomeAssistantError):
        await selector.async_select_option("mop_only")
    selector.coordinator.device.send_jdm_command.assert_not_called()


@pytest.mark.asyncio
async def test_readback_mismatch(selector, preferences):
    """An acknowledged but ineffective write is an error, not success."""
    selector.coordinator.device.send_jdm_command.side_effect = [
        {"map_list": [{"id": 123, "cur": True}]},
        preferences,
        {"result": 0},
        {"map_list": [{"id": 123, "cur": True}]},
        preferences,
    ]
    with pytest.raises(HomeAssistantError):
        await selector.async_select_option("mop_only")
    assert not selector.available


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["RB05", "277", "527K"])
async def test_only_rb05_gets_selector(prefix):
    """Vis Nav and air purifiers are not given this control."""
    coordinator = MagicMock()
    coordinator.device.mqtt_prefix = prefix
    coordinator.device_capabilities = []
    coordinator.device_category = []
    entry = MagicMock(entry_id="test")
    hass = MagicMock(data={"hass_dyson": {"test": coordinator}})
    add = MagicMock()
    await async_setup_entry(hass, entry, add)
    assert sum(
        isinstance(e, DysonSpotScrubCleaningModeSelect) for e in add.call_args.args[0]
    ) == (prefix == "RB05")
