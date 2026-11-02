"""Saved location synchronization stays optional, bounded and account-scoped."""

import asyncio
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.hass_dyson.ble_light_cloud import DysonBLELightCloudError
from custom_components.hass_dyson.ble_light_location import BLELightLocation
from custom_components.hass_dyson.ble_light_protocol import LightAttribute


def saved_location():
    """Synthetic coordinates and settings, unrelated to any actual lamp."""
    return {
        "latitude": 0.0,
        "longitude": 0.0,
        "timezone": "UTC",
        "dst": bytes(11).hex(),
    }


@pytest.fixture
def sync():
    """Mock only HA storage and external transports."""
    coordinator = SimpleNamespace(
        hass=MagicMock(),
        serial_number="TEST-LAMP",
        _config_entry=SimpleNamespace(
            data={"auth_token": "synthetic-token", "country": "US"}
        ),
        ble_device=SimpleNamespace(
            is_connected=True,
            lighting=SimpleNamespace(available=True, set_attributes=AsyncMock()),
        ),
    )
    return BLELightLocation(coordinator), coordinator


@pytest.mark.asyncio
async def test_cached_location_is_usable_offline(sync):
    """A cached location does not require a token or internet connection."""
    helper, coord = sync
    coord._config_entry.data = {"ble_light_location": saved_location()}
    with patch(
        "custom_components.hass_dyson.ble_light_location.DysonBLELightCloudClient"
    ) as cloud:
        await helper.sync(use_cache=True)
    cloud.assert_not_called()
    values = coord.ble_device.lighting.set_attributes.call_args.args[0]
    assert values[LightAttribute.LATITUDE] == struct.pack("<d", 0.0)
    assert values[LightAttribute.TIMEZONE] == struct.pack("<f", 0.0)
    assert values[LightAttribute.DAYLIGHT_SAVING_ADJUSTMENT] == bytes(8)
    coord.hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_cloud_location_uses_managed_client_and_caches_only_after_apply(sync):
    """Reads are cloud-only; the app account's saved location is never changed."""
    helper, coord = sync
    cloud = SimpleNamespace(
        fetch_location=AsyncMock(return_value={"latitude": 0.0, "longitude": 0.0}),
        fetch_timezone=AsyncMock(return_value="UTC"),
        fetch_dst=AsyncMock(return_value=bytes(11)),
    )
    with (
        patch(
            "custom_components.hass_dyson.ble_light_location.DysonBLELightCloudClient",
            return_value=cloud,
        ),
        patch(
            "custom_components.hass_dyson.ble_light_location.get_async_client",
            return_value="managed",
        ),
    ):
        await helper.sync()
    coord.ble_device.lighting.set_attributes.assert_awaited_once()
    data = coord.hass.config_entries.async_update_entry.call_args.kwargs["data"]
    assert data["ble_light_location"] == saved_location()


@pytest.mark.asyncio
async def test_partial_cloud_failure_never_writes_or_caches(sync):
    """Do not partially apply location if timezone or DST cannot be fetched."""
    helper, coord = sync
    cloud = SimpleNamespace(
        fetch_location=AsyncMock(return_value=saved_location()),
        fetch_timezone=AsyncMock(
            side_effect=DysonBLELightCloudError("Cloud unavailable")
        ),
    )
    with (
        patch(
            "custom_components.hass_dyson.ble_light_location.DysonBLELightCloudClient",
            return_value=cloud,
        ),
        patch("custom_components.hass_dyson.ble_light_location.get_async_client"),
    ):
        with pytest.raises(HomeAssistantError, match="Cloud unavailable"):
            await helper.sync()
    coord.ble_device.lighting.set_attributes.assert_not_awaited()
    coord.hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"latitude": True},
        {"latitude": 91},
        {"longitude": float("nan")},
        {"timezone": "not-a-zone"},
        {"dst": "00"},
    ],
)
async def test_invalid_cached_location_never_touches_lamp(sync, changes):
    """Validate every field before writing even the first coordinate."""
    helper, coord = sync
    coord._config_entry.data["ble_light_location"] = {**saved_location(), **changes}
    with pytest.raises(HomeAssistantError, match="Invalid saved"):
        await helper.sync(use_cache=True)
    coord.ble_device.lighting.set_attributes.assert_not_awaited()


@pytest.mark.asyncio
async def test_current_parent_credentials_take_precedence(sync):
    """Use the linked parent only, never another configured Dyson account."""
    helper, coord = sync
    coord._config_entry.data["parent_entry_id"] = "owner"
    parent = SimpleNamespace(
        data={"auth_token": "refreshed-synthetic-token", "country": "DE"}
    )
    coord.hass.config_entries.async_get_entry.return_value = parent
    assert helper._account_value("auth_token") == "refreshed-synthetic-token"
    coord.hass.config_entries.async_get_entry.assert_called_once_with("owner")


@pytest.mark.asyncio
async def test_optional_restore_failure_and_shutdown_are_quiet(sync):
    """No background cloud failure bubbles into the BLE reconnect loop."""
    helper, _ = sync
    helper.sync = AsyncMock(side_effect=HomeAssistantError("offline"))
    await helper._restore()
    blocker = asyncio.Event()
    helper._restore = AsyncMock(side_effect=blocker.wait)
    helper.start()
    task = helper._task
    helper.start()
    assert helper._task is task
    await asyncio.sleep(0)
    await helper.close()
    assert task.done() and helper._task is None
