"""Characterize the existing light lifecycle before extending its settings."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.ble_device import DysonBLEDevice, DysonMessage
from custom_components.hass_dyson.const import (
    BLE_AUTH_CHAR_UUID,
    BLE_BRIGHTNESS_LUMENS_UUID,
    BLE_COLOR_TEMP_UUID,
    BLE_POWER_UUID,
)


@pytest.fixture
async def device():
    """Use a real device wrapper with a fully local fake GATT client."""
    hass = MagicMock()
    hass.loop = asyncio.get_running_loop()
    result = DysonBLEDevice(
        hass,
        "TEST-LAMP",
        "AA:BB:CC:DD:EE:FF",
        bytes(range(16)).hex(),
        "12345678-1234-5678-1234-567812345678",
    )
    client = MagicMock()
    client.is_connected = True
    client.start_notify = AsyncMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    values = {
        BLE_POWER_UUID: b"\1",
        BLE_BRIGHTNESS_LUMENS_UUID: (400).to_bytes(2, "little"),
        BLE_COLOR_TEMP_UUID: (3300).to_bytes(2, "little"),
    }
    client.read_gatt_char = AsyncMock(side_effect=lambda uuid: values[uuid])
    result._get_bleak_client = AsyncMock(return_value=client)
    result._reauth_with_ltk = AsyncMock()
    result.lighting.start = MagicMock()
    return result, client


@pytest.mark.asyncio
async def test_existing_connection_sets_up_core_state_before_optional_settings(device):
    """The light remains usable without waiting for optional attribute reads."""
    lamp, client = device
    await lamp.connect_and_authenticate()
    assert lamp.is_connected
    assert lamp.state.power is True
    assert lamp.state.brightness_raw == 400
    assert lamp.state.color_temp_kelvin == 3300
    assert lamp.state.motion_detected is None
    lamp.lighting.start.assert_called_once_with()
    await lamp.disconnect()
    client.disconnect.assert_awaited_once_with()
    assert not lamp.is_connected


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["subscription", "auth"])
async def test_failed_handshake_closes_gatt_without_starting_settings(device, stage):
    """Subscription failures and bad authentication must not leak a connection."""
    lamp, client = device
    if stage == "subscription":
        client.start_notify.side_effect = RuntimeError("synthetic subscription failure")
    else:
        lamp._reauth_with_ltk.side_effect = RuntimeError("synthetic auth failure")
    with pytest.raises(RuntimeError):
        await lamp.connect_and_authenticate()
    assert lamp._client is None
    assert not lamp.is_connected
    lamp.lighting.start.assert_not_called()
    client.disconnect.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_gatt_read_or_optional_notification_failure_preserves_basic_connection(
    device,
):
    """A proxy read error or unsupported optional notify is not an auth failure."""
    lamp, client = device
    client.read_gatt_char.side_effect = RuntimeError("synthetic read failure")

    async def subscribe(uuid, callback):
        if uuid != BLE_AUTH_CHAR_UUID:
            raise RuntimeError("synthetic optional subscription failure")

    client.start_notify.side_effect = subscribe
    await lamp.connect_and_authenticate()
    assert lamp.is_connected
    assert lamp.state.power is None
    await lamp.disconnect()


@pytest.mark.asyncio
async def test_raw_client_retries_are_bounded(device):
    """A non-HA fallback cannot loop forever or start settings without auth."""
    lamp, client = device
    client.is_connected = False
    client.connect.side_effect = RuntimeError("synthetic offline client")
    with patch(
        "custom_components.hass_dyson.ble_device.asyncio.sleep", new=AsyncMock()
    ):
        with pytest.raises(RuntimeError, match="after 4 attempts"):
            await lamp.connect_and_authenticate()
    assert client.connect.await_count == 4
    lamp.lighting.start.assert_not_called()


@pytest.mark.asyncio
async def test_raw_client_success_after_one_retry(device):
    """Existing retry behaviour is retained on adapters without cached clients."""
    lamp, client = device
    client.is_connected = False
    attempts = 0

    async def connect():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("synthetic transient failure")
        client.is_connected = True

    client.connect.side_effect = connect
    with patch(
        "custom_components.hass_dyson.ble_device.asyncio.sleep", new=AsyncMock()
    ):
        await lamp.connect_and_authenticate()
    assert lamp.is_connected and attempts == 2
    await lamp.disconnect()


@pytest.mark.asyncio
async def test_auth_wait_consumes_unsolicited_messages_and_cleans_up_on_timeout(device):
    """Use the actual bounded queue waiter and do not orphan get() tasks."""
    lamp, client = device
    lamp._client = client
    lamp._message_queue.put_nowait(DysonMessage(0x0B, bytes(16)))
    lamp._message_queue.put_nowait(DysonMessage(0x26, b"done"))
    assert (await lamp._wait_for_type(0x26, timeout=0.1)).payload == b"done"
    with pytest.raises(TimeoutError):
        await lamp._wait_for_type(0x26, timeout=0.001)


def test_runtime_sensor_notifications_never_claim_raw_measurements():
    """The physical enable flags are exact one-byte Booleans, not lux/PIR data."""
    lamp = DysonBLEDevice(
        MagicMock(),
        "TEST-LAMP",
        "AA:BB:CC:DD:EE:FF",
        bytes(16).hex(),
        "12345678-1234-5678-1234-567812345678",
    )
    lamp._on_runtime_notification("11006")(None, bytearray(b"\1"))
    lamp._on_runtime_notification("11007")(None, bytearray(b"\0"))
    assert lamp.state.auto_brightness is True
    assert lamp.state.movement_sensor is False
    assert lamp.state.motion_detected is None
    lamp._on_runtime_notification("11007")(None, bytearray(b"\xff"))
    assert lamp.state.movement_sensor is None
