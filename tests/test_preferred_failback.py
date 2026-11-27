"""Tests for preferred connection retries while fallback remains usable."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.const import (
    CONNECTION_STATUS_CLOUD,
    CONNECTION_STATUS_LOCAL,
)
from custom_components.hass_dyson.device import (
    DysonDevice,
    _PreferredConnectionCandidate,
)

DEVICE = "custom_components.hass_dyson.device"


@pytest.fixture
def device():
    """Create a connected device with an active fallback client."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *args: fn(*args))
    result = DysonDevice(
        hass,
        "TEST123",
        "device.local",
        "credential",
        cloud_host="cloud.example",
        cloud_credential="cloud-credential",
    )
    result._mqtt_client = MagicMock()
    result._connected = True
    result._using_fallback = True
    result._current_connection_type = CONNECTION_STATUS_CLOUD
    result._fallback_since = 100.0
    return result


@pytest.mark.asyncio
async def test_retry_loop_waits_one_interval_and_keeps_retrying(device):
    """No preferred retry occurs before the interval, and failures do not stop it."""
    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise asyncio.CancelledError

    device._retry_preferred_on_fallback = AsyncMock()
    with patch(f"{DEVICE}.asyncio.sleep", side_effect=sleep):
        with pytest.raises(asyncio.CancelledError):
            await device._preferred_retry_loop()
    assert sleeps == [300.0, 300.0, 300.0]
    assert device._retry_preferred_on_fallback.await_count == 2


@pytest.mark.asyncio
async def test_fallback_episode_and_retry_task_survive_reconnection(device):
    """Re-entering fallback preserves its clock and does not create a second task."""
    device.hass.async_create_background_task = asyncio.create_task
    device._fallback_since = None
    with patch(f"{DEVICE}.time.monotonic", return_value=100.0):
        device._start_preferred_retry()
        task = device._preferred_retry_task
    with patch(f"{DEVICE}.time.monotonic", return_value=500.0):
        device._start_preferred_retry()
    assert device.fallback_since == 100.0
    assert device._preferred_retry_task is task
    await device._stop_preferred_retry()
    assert task.done()


@pytest.mark.asyncio
async def test_failed_candidate_preserves_fallback_and_records_failure(device):
    """A failed candidate leaves the active client and connection undisturbed."""
    active = device._mqtt_client
    candidate = MagicMock()
    candidate._attempt_connection = AsyncMock(return_value=False)
    candidate.disconnect = AsyncMock()
    candidate.promoted = False
    candidate._local_failure_count = 1
    candidate._local_connect_block_until = 0.0
    candidate._network_attempted = True
    with (
        patch(f"{DEVICE}._PreferredConnectionCandidate", return_value=candidate),
        patch(f"{DEVICE}.time.monotonic", return_value=1000.0),
    ):
        await device._retry_preferred_on_fallback()
    candidate._attempt_connection.assert_awaited_once_with(
        "local", "device.local", "credential"
    )
    candidate.disconnect.assert_awaited_once()
    assert device._mqtt_client is active
    assert device._connected
    assert device.using_fallback
    assert device.preferred_failure_at == 1000.0
    active.disconnect.assert_not_called()


@pytest.mark.asyncio
async def test_missing_details_or_backoff_do_not_record_failure(device):
    """A skipped retry is not evidence that the preferred host failed."""
    device.credential = ""
    await device._retry_preferred_on_fallback()
    assert device.preferred_failure_at is None
    device.credential = "credential"
    with patch(f"{DEVICE}.time.time", return_value=10.0):
        device._local_connect_block_until = 11.0
        await device._retry_preferred_on_fallback()
    assert device.preferred_failure_at is None


@pytest.mark.asyncio
async def test_failure_before_network_attempt_is_not_repair_evidence(device):
    """A local configuration error is not an actual host connection failure."""
    candidate = MagicMock()
    candidate._attempt_connection = AsyncMock(return_value=False)
    candidate.disconnect = AsyncMock()
    candidate.promoted = False
    candidate._network_attempted = False
    candidate._local_failure_count = 0
    candidate._local_connect_block_until = 0.0
    with patch(f"{DEVICE}._PreferredConnectionCandidate", return_value=candidate):
        await device._retry_preferred_on_fallback()
    assert device.preferred_failure_at is None


def test_candidate_promotion_and_stale_callbacks(device):
    """Only the live candidate can be promoted; retired callbacks are ignored."""
    old = device._mqtt_client
    candidate = _PreferredConnectionCandidate(device)
    new = MagicMock()
    candidate._mqtt_client = new
    candidate._on_connect(new, None, {}, 0)
    assert device._mqtt_client is old
    assert candidate.promote() is old
    assert device._mqtt_client is new
    device._on_disconnect(old, None, 1)
    assert device.is_connected
    candidate._on_disconnect(new, None, 1)
    assert not device.is_connected


@pytest.mark.asyncio
async def test_preferred_success_promotes_without_losing_fallback(device):
    """Successful handoff retires the old client only after promotion."""
    old = device._mqtt_client
    candidate = MagicMock()
    candidate._attempt_connection = AsyncMock(return_value=True)
    candidate.disconnect = AsyncMock()
    candidate._local_failure_count = 0
    candidate._local_connect_block_until = 0.0
    candidate._network_attempted = True
    new = MagicMock()

    def promote():
        assert device._mqtt_client is old
        old.disconnect.assert_not_called()
        device._mqtt_client = new
        device._using_fallback = False
        device._current_connection_type = CONNECTION_STATUS_LOCAL
        device._end_fallback_episode()
        candidate.promoted = True
        return old

    candidate.promote.side_effect = promote
    with patch(f"{DEVICE}._PreferredConnectionCandidate", return_value=candidate):
        await device._retry_preferred_on_fallback()
    assert device._mqtt_client is new
    assert device.connection_status == CONNECTION_STATUS_LOCAL
    assert device.fallback_since is None
    assert not device.using_fallback
    old.disconnect.assert_called_once()
    candidate.disconnect.assert_not_awaited()


@pytest.mark.asyncio
async def test_real_candidate_handshake_promotes_after_connack(device):
    """The actual MQTT attempt keeps fallback until the candidate receives CONNACK."""
    old = device._mqtt_client
    new = MagicMock()

    def connect(*args):
        assert device._mqtt_client is old
        assert device.is_connected
        return 0

    new.connect.side_effect = connect
    new.loop_start.side_effect = lambda: new.on_connect(new, None, {}, 0)
    with patch(f"{DEVICE}.mqtt.Client", return_value=new):
        await device._retry_preferred_on_fallback()
    assert device._mqtt_client is new
    assert device.connection_status == CONNECTION_STATUS_LOCAL
    old.disconnect.assert_called_once()
    assert new.subscribe.called


@pytest.mark.asyncio
async def test_real_candidate_failure_keeps_cloud_connected(device):
    """A failed socket attempt closes only its candidate client."""
    old = device._mqtt_client
    new = MagicMock()
    new.connect.side_effect = OSError("unreachable")
    with patch(f"{DEVICE}.mqtt.Client", return_value=new):
        await device._retry_preferred_on_fallback()
    assert device._mqtt_client is old
    assert device.is_connected
    assert device.using_fallback
    assert device.preferred_failure_at is not None
    old.disconnect.assert_not_called()
    new.disconnect.assert_called()


@pytest.mark.asyncio
async def test_cancelled_retry_waits_for_candidate_cleanup(device):
    """Cancellation must not leave a still-running MQTT connection attempt behind."""
    started = asyncio.Event()
    finish = asyncio.Event()
    candidate = MagicMock()
    candidate.promoted = False
    candidate.disconnect = AsyncMock()

    async def attempt(*args):
        started.set()
        await finish.wait()
        return False

    candidate._attempt_connection = AsyncMock(side_effect=attempt)
    with patch(f"{DEVICE}._PreferredConnectionCandidate", return_value=candidate):
        task = asyncio.create_task(device._retry_preferred_on_fallback())
        await started.wait()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    candidate.disconnect.assert_awaited_once()
    assert device.preferred_failure_at is None
    assert device.is_connected


@pytest.mark.asyncio
async def test_cloud_preferred_is_retried(device):
    """Cloud-first configurations use the same timed fallback mechanism."""
    device._preferred_connection_type = "cloud"
    device._current_connection_type = CONNECTION_STATUS_LOCAL
    candidate = MagicMock()
    candidate._attempt_connection = AsyncMock(return_value=False)
    candidate.disconnect = AsyncMock()
    candidate.promoted = False
    candidate._local_failure_count = 0
    candidate._local_connect_block_until = 0.0
    with patch(f"{DEVICE}._PreferredConnectionCandidate", return_value=candidate):
        await device._retry_preferred_on_fallback()
    candidate._attempt_connection.assert_awaited_once_with(
        "cloud", "cloud.example", "cloud-credential"
    )
