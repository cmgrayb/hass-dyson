"""Exercise real fragment/attribute code with a completely synthetic BLE lamp."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.ble_device import (
    DysonBLEDevice,
    DysonFragmentAssembler,
    fragment_dyson_message,
)
from custom_components.hass_dyson.ble_light_attributes import BLELightAttributeError
from custom_components.hass_dyson.ble_light_protocol import (
    MODE_ATTRIBUTES,
    LightAttribute,
    encode_birth_year,
)
from custom_components.hass_dyson.const import BLE_WRITE_ATTR_CHAR_UUID


@pytest.fixture
def lamp():
    """Run the production codec against a local request/response simulator."""
    device = DysonBLEDevice(
        MagicMock(),
        "TEST-LAMP",
        "AA:BB:CC:DD:EE:FF",
        bytes(range(16)).hex(),
        "12345678-1234-5678-1234-567812345678",
    )
    client = MagicMock()
    client.is_connected = True
    client.services.get_characteristic.return_value.properties = [
        "write-without-response"
    ]
    client.start_notify = AsyncMock()
    client.read_gatt_char = AsyncMock(return_value=b"\0")
    client.disconnect = AsyncMock()
    device._client = client
    device.state.connected = device.state.authenticated = True
    settings = device.lighting
    settings._ready = True
    values = dict.fromkeys(MODE_ATTRIBUTES.values(), b"\0")
    rejected = set()
    assembler = DysonFragmentAssembler()

    async def write(uuid, payload, **kwargs):
        if uuid != BLE_WRITE_ATTR_CHAR_UUID:
            return
        message = assembler.feed(bytes(payload))
        if message is None or message.type_id in (0x30, 0x80):
            return
        attr = int.from_bytes(message.payload[:2], "little")
        attr_bytes = attr.to_bytes(2, "little")
        if message.type_id == 0x93:
            values[attr] = message.payload[4:]
            opcode, body = 0x94, attr_bytes + b"\0"
        elif message.type_id == 0x90:
            value = values.get(attr, b"\0")
            if attr in rejected:
                opcode, body = 0x91, attr_bytes + b"\2\0\0"
            else:
                opcode, body = (
                    0x91,
                    attr_bytes + b"\0" + len(value).to_bytes(2, "little") + value,
                )
        elif message.type_id == 0x96:
            opcode, body = 0x98, attr_bytes
        else:
            raise AssertionError("Unexpected simulated opcode")
        for frame in fragment_dyson_message(opcode, body):
            settings._on_message(None, bytearray(frame))

    client.write_gatt_char = AsyncMock(side_effect=write)
    return device, settings, client, values, rejected


@pytest.mark.asyncio
async def test_setting_write_is_confirmed_and_event_is_json_safe(lamp):
    """No raw bytes, keys or sensitive attribute dictionary enter HA events."""
    device, settings, _, values, _ = lamp
    await settings.set_attribute(LightAttribute.AWAY_MODE, b"\1")
    assert settings.attributes[LightAttribute.AWAY_MODE] == b"\1"
    assert values[LightAttribute.AWAY_MODE] == b"\1"
    payload = device.hass.bus.async_fire.call_args.args[1]
    json.dumps(payload)
    assert "attributes" not in payload
    assert "ltk" not in payload
    assert "birth_year" not in payload


@pytest.mark.asyncio
async def test_readback_mismatch_is_not_reported_as_success(lamp):
    """A positive write ACK alone must not make a setting look applied."""
    _, settings, _, _, _ = lamp
    with patch.object(settings, "_read", new=AsyncMock(return_value=b"\0")):
        with pytest.raises(BLELightAttributeError, match="readback mismatch"):
            await settings.set_attribute(LightAttribute.AWAY_MODE, b"\1")


@pytest.mark.asyncio
async def test_rejected_attribute_does_not_pollute_cache(lamp):
    """A nonzero read status is a per-feature error, not a valid empty value."""
    _, settings, _, _, rejected = lamp
    rejected.add(LightAttribute.AWAY_MODE)
    with pytest.raises(BLELightAttributeError, match="rejected"):
        await settings._read(LightAttribute.AWAY_MODE)
    assert LightAttribute.AWAY_MODE not in settings.attributes


@pytest.mark.asyncio
async def test_timeout_disables_uncorrelated_channel_until_reconnect(lamp):
    """Late replies must not confirm an unrelated retry on the same session."""
    _, settings, client, _, _ = lamp
    client.write_gatt_char.side_effect = None
    with patch(
        "custom_components.hass_dyson.ble_light_attributes._REQUEST_TIMEOUT", 0.001
    ):
        with pytest.raises(BLELightAttributeError, match="timed out"):
            await settings._read(LightAttribute.AWAY_MODE)
    assert not settings.available
    assert not settings._pending
    with pytest.raises(BLELightAttributeError, match="unavailable"):
        await settings._read(LightAttribute.AWAY_MODE)
    settings.reset()
    assert not settings._timed_out


@pytest.mark.asyncio
async def test_cancellation_removes_pending_request(lamp):
    """Caller cancellation propagates and does not leave a future behind."""
    _, settings, client, _, _ = lamp
    client.write_gatt_char.side_effect = None
    task = asyncio.create_task(settings._read(LightAttribute.AWAY_MODE))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not settings._pending


@pytest.mark.asyncio
async def test_disconnection_fails_waiters_and_clears_sensitive_cache(lamp):
    """A new session must never reuse previous settings or queued replies."""
    _, settings, client, _, _ = lamp
    settings.attributes[LightAttribute.YEAR_OF_BIRTH] = bytes(64)
    client.write_gatt_char.side_effect = None
    task = asyncio.create_task(settings._read(LightAttribute.AWAY_MODE))
    await asyncio.sleep(0)
    settings.reset()
    with pytest.raises(BLELightAttributeError, match="disconnected"):
        await task
    assert settings.attributes == {}


def test_pushed_daylight_change_updates_existing_switch(lamp):
    """Physical changes use the original daylight-mode state and entity ID."""
    device, settings, _, _, _ = lamp
    for frame in fragment_dyson_message(0x97, bytes.fromhex("1320010001")):
        settings._on_message(None, bytearray(frame))
    assert device.state.daylight_mode is True
    assert settings.attributes[LightAttribute.DAYLIGHT_MODE] == b"\1"


@pytest.mark.parametrize("frame", [b"\x80", b"\x80\x91\x13", b"\x80\x94\x13\x20\0\0"])
def test_malformed_reply_is_ignored(lamp, frame):
    """A bad notification cannot become a valid optional setting."""
    _, settings, _, _, _ = lamp
    settings._on_message(None, bytearray(frame))
    assert settings.attributes == {}


@pytest.mark.asyncio
async def test_sensor_enablement_requires_readback(lamp):
    """Sensor settings remain distinct from measured movement or lux."""
    device, settings, client, _, _ = lamp
    client.read_gatt_char.return_value = b"\1"
    await settings.set_sensor("movement_sensor", True)
    assert device.state.movement_sensor is True
    assert device.state.motion_detected is None
    client.read_gatt_char.return_value = b"\0"
    with pytest.raises(BLELightAttributeError, match="readback mismatch"):
        await settings.set_sensor("auto_brightness", True)
    assert device.state.auto_brightness is None


@pytest.mark.asyncio
@pytest.mark.parametrize("sensor,enabled", [("lux", True), ("movement_sensor", 1)])
async def test_invalid_sensor_request_never_writes(lamp, sensor, enabled):
    """Validate control names and Boolean values before device access."""
    _, settings, client, _, _ = lamp
    with pytest.raises(ValueError):
        await settings.set_sensor(sensor, enabled)
    client.write_gatt_char.assert_not_awaited()


@pytest.mark.asyncio
async def test_modes_and_reset_use_native_attributes(lamp):
    """Manual mode clears all native modes; resets preserve the unset sentinel."""
    _, settings, _, values, _ = lamp
    await settings.set_mode("study")
    assert values[LightAttribute.STUDY_MODE] == b"\1"
    await settings.set_mode("manual")
    assert all(values[attr] == b"\0" for attr in MODE_ATTRIBUTES.values())
    await settings.reset_daylight_times()
    assert values[LightAttribute.SUNRISE_TIME] == b"\xff\xff"
    with pytest.raises(ValueError):
        await settings.set_mode("invented")


@pytest.mark.asyncio
async def test_birth_year_is_encrypted_and_only_decoded_on_demand(lamp):
    """Use a synthetic key; do not store the year or key on the event bus."""
    device, settings, _, values, _ = lamp
    await settings.set_birth_year(1990)
    assert len(values[LightAttribute.YEAR_OF_BIRTH]) == 64
    assert settings.birth_year == 1990
    settings.attributes[LightAttribute.YEAR_OF_BIRTH] = encode_birth_year(
        1990, bytes(16)
    )
    assert settings.birth_year is None
    device._ltk_hex = "invalid"
    assert settings.birth_year is None


@pytest.mark.asyncio
async def test_background_worker_and_disconnect_are_owned(lamp):
    """Discovery releases the command lock and cleanly exits on unload."""
    device, settings, client, _, _ = lamp
    settings.start()
    task = settings._task
    for _ in range(20):
        await asyncio.sleep(0)
        if settings._subscriptions:
            break
    assert settings.available
    assert settings._subscriptions
    await device.disconnect()
    assert task.done()
    assert settings._task is None
    assert settings.attributes == {}
    client.disconnect.assert_awaited_once()


def test_fragment_gap_discards_message_without_contaminating_next(lamp):
    """Reuse the project's fragment codec, including strict fragment ordering."""
    assembler = DysonFragmentAssembler()
    frames = fragment_dyson_message(0x97, bytes(82))
    assert assembler.feed(frames[0]) is None
    assert assembler.feed(frames[2]) is None
    assert assembler.feed(frames[3]) is None
    assert assembler.feed(b"\x80\x94\x13\x20\0").payload == b"\x13\x20\0"


@pytest.mark.asyncio
@pytest.mark.parametrize("readable", [True, False])
async def test_existing_daylight_switch_keeps_legacy_fallback(lamp, readable):
    """An optional attribute service must not break older daylight devices."""
    device, settings, client, _, _ = lamp
    if readable:
        settings.attributes[LightAttribute.DAYLIGHT_MODE] = b"\0"
    with patch.object(settings, "set_attribute", new=AsyncMock()) as writer:
        await device.set_daylight_mode(True)
    if readable:
        writer.assert_awaited_once_with(LightAttribute.DAYLIGHT_MODE, b"\1")
    else:
        writer.assert_not_awaited()
        client.write_gatt_char.assert_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,value", [("set_brightness", 160), ("set_color_temp_kelvin", 4500)]
)
async def test_manual_slider_confirms_native_daylight_is_disabled(lamp, method, value):
    """A physical/native daylight mode must not survive a manual adjustment."""
    device, settings, _, values, _ = lamp
    values[LightAttribute.DAYLIGHT_MODE] = b"\1"
    settings.attributes[LightAttribute.DAYLIGHT_MODE] = b"\1"
    device.state.daylight_mode = True
    await getattr(device, method)(value)
    assert values[LightAttribute.DAYLIGHT_MODE] == b"\0"
    assert settings.attributes[LightAttribute.DAYLIGHT_MODE] == b"\0"
    assert device.state.daylight_mode is False


@pytest.mark.asyncio
async def test_delayed_attribute_readback_retries_reads_not_writes(lamp):
    """A successful BLE ACK can precede application on the main lamp MCU."""
    _, settings, _, _, _ = lamp
    with (
        patch.object(settings, "_request", new=AsyncMock(return_value=b"")) as request,
        patch.object(
            settings, "_read", new=AsyncMock(side_effect=[b"\0", b"\1"])
        ) as read,
    ):
        await settings._write(LightAttribute.AWAY_MODE, b"\1")
    assert request.await_count == 1
    assert read.await_count == 2


@pytest.mark.asyncio
async def test_delayed_sensor_readback_does_not_repeat_the_toggle(lamp):
    """Wait for a confirmed flag without resending the user's command."""
    device, settings, client, _, _ = lamp
    client.read_gatt_char.side_effect = [b"\0", b"\0", b"\1"]
    await settings.set_sensor("auto_brightness", True)
    assert client.write_gatt_char.await_count == 1
    assert client.read_gatt_char.await_count == 3
    assert device.state.auto_brightness is True


@pytest.mark.asyncio
@pytest.mark.parametrize("daylight_capable", [True, False])
@pytest.mark.parametrize(
    "first,second",
    [
        (("set_brightness", 102), ("set_color_temp_kelvin", 3300)),
        (("set_power", True), ("set_color_temp_kelvin", 3300)),
        (("set_brightness", 102), ("set_power", False)),
    ],
)
async def test_morph_commands_share_pacing_without_delaying_legacy_lamps(
    lamp, daylight_capable, first, second
):
    """A combined scene must not drop its second unacknowledged light write."""
    device, _, _, _, _ = lamp
    device._daylight_capable = daylight_capable
    device._manual_mode_valid_until = float("inf")
    with (
        patch(
            "custom_components.hass_dyson.ble_device.asyncio.get_running_loop"
        ) as get_loop,
        patch(
            "custom_components.hass_dyson.ble_device.asyncio.sleep", new=AsyncMock()
        ) as sleep,
    ):
        get_loop.return_value.time.return_value = 10.0
        await getattr(device, first[0])(first[1])
        await getattr(device, second[0])(second[1])
    if daylight_capable:
        sleep.assert_awaited_once_with(0.25)
    else:
        sleep.assert_not_awaited()


@pytest.mark.parametrize("kelvin", [0, 2699, 6501, 65535])
def test_invalid_temperature_notifications_preserve_last_valid_value(lamp, kelvin):
    """Power-off/transitional sentinels must not expose an invalid HA Kelvin."""
    device, _, _, _, _ = lamp
    device.state.color_temp_kelvin = 3300
    device._on_color_temp_notification(None, bytearray(kelvin.to_bytes(2, "little")))
    assert device.state.color_temp_kelvin == 3300


@pytest.mark.asyncio
async def test_zero_initial_temperature_does_not_replace_known_temperature(lamp):
    """An off lamp can return zero rather than its remembered setpoint."""
    device, _, client, _, _ = lamp
    device.state.color_temp_kelvin = 3300
    client.read_gatt_char.return_value = b"\0\0"
    await device._read_initial_state()
    assert device.state.color_temp_kelvin == 3300


@pytest.mark.asyncio
async def test_attribute_writes_share_light_pacing_but_reads_do_not(lamp):
    """Switching from a slider to native settings uses the same MCU budget."""
    device, settings, _, _, _ = lamp
    with patch.object(device, "_wait_for_light_write", new=AsyncMock()) as pace:
        await settings._write(LightAttribute.AWAY_MODE, b"\1")
        pace.assert_awaited_once()
        assert device._last_light_write is not None
        await settings._read(LightAttribute.AWAY_MODE)
        pace.assert_awaited_once()


@pytest.mark.asyncio
async def test_sensor_switches_reuse_the_paced_light_write_path(lamp):
    """A sensor command immediately after a scene must not be dropped."""
    device, settings, client, _, _ = lamp
    client.read_gatt_char.return_value = b"\1"
    with patch.object(device, "_wait_for_light_write", new=AsyncMock()) as pace:
        await settings.set_sensor("auto_brightness", True)
        pace.assert_awaited_once()
    assert device._last_light_write is not None
