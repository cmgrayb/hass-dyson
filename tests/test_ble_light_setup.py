"""Cloud login/OTP stay upstream; test lamp discovery with synthetic accounts."""

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hass_dyson.ble_light_cloud import DysonBLELightCloudError
from custom_components.hass_dyson.config_flow import DysonConfigFlow

SERIAL = "TEST-LAMP"
UUID = "12345678-1234-5678-1234-567812345678"
LTK = bytes(range(16)).hex().upper()


@pytest.fixture
def setup():
    """No real cloud, Bluetooth stack or HA storage is used in this flow."""
    flow = DysonConfigFlow()
    flow.hass = MagicMock()
    flow.context = {}
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    flow.async_create_entry = MagicMock(
        side_effect=lambda **kw: {"type": FlowResultType.CREATE_ENTRY, **kw}
    )
    flow.async_show_form = MagicMock(
        side_effect=lambda **kw: {"type": FlowResultType.FORM, **kw}
    )
    owner = SimpleNamespace(
        entry_id="owner",
        data={
            "auth_token": "synthetic-owner-token",
            "account_uuid": UUID,
            "country": "DE",
        },
    )
    other = SimpleNamespace(
        entry_id="other",
        data={
            "auth_token": "synthetic-other-token",
            "account_uuid": UUID,
            "country": "US",
        },
    )
    flow.hass.config_entries.async_entries.return_value = [other, owner]
    cloud = SimpleNamespace(fetch_ltk=AsyncMock(return_value=LTK))
    bluetooth = MagicMock()
    bluetooth.async_discovered_service_info.return_value = [
        SimpleNamespace(name=SERIAL, address="AA:BB:CC:DD:EE:FF")
    ]
    with (
        patch(
            "custom_components.hass_dyson.ble_light_cloud.DysonBLELightCloudClient",
            return_value=cloud,
        ) as factory,
        patch(
            "homeassistant.helpers.httpx_client.get_async_client",
            return_value="managed",
        ),
        patch.dict(sys.modules, {"homeassistant.components.bluetooth": bluetooth}),
    ):
        yield flow, owner, other, cloud, factory


@pytest.mark.asyncio
async def test_account_auto_add_creates_owned_lamp_without_key_entry(setup):
    """Use the account's room title but preserve the serial-based device name."""
    flow, _, _, cloud, factory = setup
    result = await flow.async_step_discovery(
        {
            "serial_number": SERIAL,
            "name": "Office",
            "category": "light",
            "connection_category": "lecOnly",
            "parent_entry_id": "owner",
            "product_type": "552",
            "country": "DE",
            "ble_auto_add": True,
            "capabilities": ["Daylight"],
        }
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Office"
    assert result["data"]["device_name"] == f"Dyson {SERIAL}"
    assert result["data"]["parent_entry_id"] == "owner"
    assert result["data"]["account_uuid"] == UUID
    assert result["data"]["ltk"] == LTK
    assert result["data"]["capabilities"] == ["Daylight"]
    assert result["data"]["product_type"] == "552"
    assert "auth_token" not in result["data"]
    factory.assert_called_once_with("synthetic-owner-token", "DE", client="managed")
    cloud.fetch_ltk.assert_awaited_once_with(SERIAL)


@pytest.mark.asyncio
async def test_parent_account_failure_never_uses_an_unrelated_account(setup):
    """Avoid pairing one account's lamp with another account's UUID/key."""
    flow, _, _, cloud, factory = setup
    flow.init_data = {"parent_entry_id": "owner"}
    cloud.fetch_ltk.side_effect = DysonBLELightCloudError("Cloud unavailable")
    assert await flow._fetch_ltk_from_account(SERIAL) is None
    factory.assert_called_once_with("synthetic-owner-token", "DE", client="managed")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "account_uuid", [None, "invalid", "00000000-0000-0000-0000-000000000000"]
)
async def test_invalid_account_uuid_never_fetches_key(setup, account_uuid):
    """Never knowingly create an entry that can only fail authentication."""
    flow, owner, _, cloud, _ = setup
    owner.data["account_uuid"] = account_uuid
    flow.init_data = {"parent_entry_id": "owner"}
    assert await flow._fetch_ltk_from_account(SERIAL) is None
    cloud.fetch_ltk.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_discovery_still_requires_user_confirmation(setup):
    """Respect disabled auto-add and leave non-lamp flows untouched."""
    flow, _, _, cloud, _ = setup
    result = await flow.async_step_discovery(
        {
            "serial_number": SERIAL,
            "category": "light",
            "connection_category": "lecOnly",
            "parent_entry_id": "owner",
            "ble_auto_add": False,
        }
    )
    assert result["step_id"] == "ble_configure"
    cloud.fetch_ltk.assert_not_awaited()
