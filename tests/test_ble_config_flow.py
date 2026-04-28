"""Tests for the BLE pairing config flow steps.

Covers:
- async_step_ble_discover  — BLE scan and device selection
- async_step_ble_configure — serial/MAC entry, account-assisted LTK fetch
- _fetch_ltk_from_account  — cloud LTK retrieval helper
- _cloud_fetch_ltk         — blocking HTTP helper
- async_step_ble_light     — manual LTK fallback (with pre-fill from state)
"""

import sys
import urllib.error
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hass_dyson.config_flow import DysonConfigFlow
from custom_components.hass_dyson.const import (
    CONF_BLE_MAC,
    CONF_BLE_PROXY,
    CONF_LTK,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_SERIAL = "CD06-EU-AAA1234A"
VALID_MAC = "AA:BB:CC:DD:EE:FF"
VALID_LTK = "deadbeef01020304"
VALID_AUTH_TOKEN = "fake-bearer-token"


@pytest.fixture
def mock_hass():
    """Return a minimal mock HomeAssistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    hass.config_entries = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    hass.async_add_executor_job = AsyncMock()
    return hass


@pytest.fixture
def flow(mock_hass):
    """Return a fresh DysonConfigFlow bound to mock_hass."""
    f = DysonConfigFlow()
    f.hass = mock_hass
    f.context = {}
    f.async_set_unique_id = AsyncMock()
    f._abort_if_unique_id_configured = MagicMock()
    f.async_show_form = MagicMock(side_effect=lambda **kwargs: kwargs)
    f.async_create_entry = MagicMock(
        side_effect=lambda **kwargs: {"type": FlowResultType.CREATE_ENTRY, **kwargs}
    )
    return f


# ---------------------------------------------------------------------------
# Helper to inject a fake bluetooth module into sys.modules
# ---------------------------------------------------------------------------


DYSON_BLE_SERVICE_UUID = "2dd10010-1c37-452d-8979-d1b4a787d0a4"


def _mock_bluetooth_module(service_infos):
    """Return a fake homeassistant.components.bluetooth module mock."""
    mock_bt = MagicMock()
    mock_bt.async_discovered_service_info.return_value = service_infos
    return mock_bt


# ---------------------------------------------------------------------------
# Tests for async_step_ble_discover
# ---------------------------------------------------------------------------


class TestBleDiscover:
    """Tests for async_step_ble_discover."""

    @pytest.mark.asyncio
    async def test_no_ble_devices_skips_to_configure(self, flow):
        """When BLE scan finds nothing, go directly to async_step_ble_configure."""
        mock_bt = _mock_bluetooth_module([])
        with patch.dict(sys.modules, {"homeassistant.components.bluetooth": mock_bt}):
            with patch.object(
                flow,
                "async_step_ble_configure",
                new=AsyncMock(return_value={"type": "form"}),
            ) as mock_cfg:
                await flow.async_step_ble_discover()
                mock_cfg.assert_called_once()

    @pytest.mark.asyncio
    async def test_ble_import_error_skips_to_configure(self, flow):
        """If the bluetooth integration raises during import, skip to configure."""
        # Remove any cached bluetooth module so the import fails naturally
        with patch.dict(sys.modules, {"homeassistant.components.bluetooth": None}):
            with patch.object(
                flow,
                "async_step_ble_configure",
                new=AsyncMock(return_value={"type": "form"}),
            ) as mock_cfg:
                await flow.async_step_ble_discover()
                mock_cfg.assert_called_once()

    @pytest.mark.asyncio
    async def test_devices_found_shows_form(self, flow):
        """When BLE devices are found, the discover form is shown."""
        mock_si = MagicMock()
        mock_si.address = VALID_MAC
        mock_si.name = "Dyson Lightcycle"
        mock_si.service_uuids = [DYSON_BLE_SERVICE_UUID]

        mock_bt = _mock_bluetooth_module([mock_si])
        with patch.dict(sys.modules, {"homeassistant.components.bluetooth": mock_bt}):
            result = await flow.async_step_ble_discover()

        assert result["step_id"] == "ble_discover"
        assert result["description_placeholders"]["device_count"] == "1"

    @pytest.mark.asyncio
    async def test_user_selects_device(self, flow):
        """Selecting a device from the list stores the MAC and calls configure."""
        mock_si = MagicMock()
        mock_si.address = VALID_MAC
        mock_si.name = "Dyson"
        mock_si.service_uuids = [DYSON_BLE_SERVICE_UUID]

        mock_bt = _mock_bluetooth_module([mock_si])
        with patch.dict(sys.modules, {"homeassistant.components.bluetooth": mock_bt}):
            with patch.object(
                flow,
                "async_step_ble_configure",
                new=AsyncMock(return_value={"type": "form"}),
            ) as mock_cfg:
                await flow.async_step_ble_discover(user_input={"ble_device": VALID_MAC})
                assert flow._ble_mac == VALID_MAC
                mock_cfg.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_selects_manual(self, flow):
        """Choosing 'manual' does not set _ble_mac and calls configure."""
        mock_si = MagicMock()
        mock_si.address = VALID_MAC
        mock_si.name = "Dyson"
        mock_si.service_uuids = [DYSON_BLE_SERVICE_UUID]

        mock_bt = _mock_bluetooth_module([mock_si])
        with patch.dict(sys.modules, {"homeassistant.components.bluetooth": mock_bt}):
            with patch.object(
                flow,
                "async_step_ble_configure",
                new=AsyncMock(return_value={"type": "form"}),
            ) as mock_cfg:
                await flow.async_step_ble_discover(user_input={"ble_device": "manual"})
                assert flow._ble_mac is None
                mock_cfg.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_dyson_devices_excluded(self, flow):
        """Devices that do not advertise the Dyson service UUID are ignored."""
        other_si = MagicMock()
        other_si.address = "11:22:33:44:55:66"
        other_si.name = "Other BLE"
        other_si.service_uuids = ["0000180f-0000-1000-8000-00805f9b34fb"]

        mock_bt = _mock_bluetooth_module([other_si])
        with patch.dict(sys.modules, {"homeassistant.components.bluetooth": mock_bt}):
            with patch.object(
                flow,
                "async_step_ble_configure",
                new=AsyncMock(return_value={"type": "form"}),
            ) as mock_cfg:
                await flow.async_step_ble_discover()
                # No Dyson devices → skips directly to configure
                mock_cfg.assert_called_once()
        assert flow._ble_found_devices == []


# ---------------------------------------------------------------------------
# Tests for async_step_ble_configure
# ---------------------------------------------------------------------------


class TestBleConfigure:
    """Tests for async_step_ble_configure."""

    @pytest.mark.asyncio
    async def test_shows_form_without_user_input(self, flow):
        """No user_input shows the configure form."""
        result = await flow.async_step_ble_configure()
        assert result["step_id"] == "ble_configure"

    @pytest.mark.asyncio
    async def test_prefills_mac_from_state(self, flow):
        """MAC is pre-filled when _ble_mac is already set."""
        flow._ble_mac = VALID_MAC
        await flow.async_step_ble_configure()
        # Verify the form call includes the default for CONF_BLE_MAC
        call_kwargs = flow.async_show_form.call_args[1]
        schema = call_kwargs["data_schema"]
        # The schema's markers should include CONF_BLE_MAC with default VALID_MAC
        key_defaults = {
            str(k): k.default() if callable(k.default) else k.default
            for k in schema.schema
            if hasattr(k, "default")
        }
        assert key_defaults.get("ble_mac") == VALID_MAC

    @pytest.mark.asyncio
    async def test_missing_serial_shows_error(self, flow):
        """Empty serial produces a 'required' error."""
        result = await flow.async_step_ble_configure(
            user_input={CONF_SERIAL_NUMBER: "", CONF_BLE_MAC: VALID_MAC}
        )
        assert result["errors"][CONF_SERIAL_NUMBER] == "required"

    @pytest.mark.asyncio
    async def test_invalid_mac_shows_error(self, flow):
        """Bad MAC address produces an 'invalid_mac_address' error."""
        result = await flow.async_step_ble_configure(
            user_input={CONF_SERIAL_NUMBER: VALID_SERIAL, CONF_BLE_MAC: "not-a-mac"}
        )
        assert result["errors"][CONF_BLE_MAC] == "invalid_mac_address"

    @pytest.mark.asyncio
    async def test_already_configured_serial_shows_error(self, flow):
        """Serial that is already configured produces an error."""
        flow._abort_if_unique_id_configured.side_effect = Exception(
            "already configured"
        )
        result = await flow.async_step_ble_configure(
            user_input={CONF_SERIAL_NUMBER: VALID_SERIAL, CONF_BLE_MAC: VALID_MAC}
        )
        assert result["errors"][CONF_SERIAL_NUMBER] == "already_configured"

    @pytest.mark.asyncio
    async def test_ltk_auto_fetch_success_creates_entry(self, flow):
        """When LTK is auto-fetched the entry is created immediately."""
        with patch.object(
            flow, "_fetch_ltk_from_account", new=AsyncMock(return_value=(VALID_LTK, ""))
        ):
            result = await flow.async_step_ble_configure(
                user_input={CONF_SERIAL_NUMBER: VALID_SERIAL, CONF_BLE_MAC: VALID_MAC}
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_LTK] == VALID_LTK
        assert result["data"][CONF_SERIAL_NUMBER] == VALID_SERIAL
        assert result["data"][CONF_BLE_MAC] == VALID_MAC

    @pytest.mark.asyncio
    async def test_ltk_auto_fetch_success_with_proxy(self, flow):
        """BLE proxy is included in config if provided."""
        with patch.object(
            flow, "_fetch_ltk_from_account", new=AsyncMock(return_value=(VALID_LTK, ""))
        ):
            result = await flow.async_step_ble_configure(
                user_input={
                    CONF_SERIAL_NUMBER: VALID_SERIAL,
                    CONF_BLE_MAC: VALID_MAC,
                    CONF_BLE_PROXY: "192.168.1.50",
                }
            )

        assert result["data"][CONF_BLE_PROXY] == "192.168.1.50"

    @pytest.mark.asyncio
    async def test_ltk_auto_fetch_none_falls_back_to_manual(self, flow):
        """When LTK fetch returns None, flow falls back to ble_light step."""
        with patch.object(
            flow, "_fetch_ltk_from_account", new=AsyncMock(return_value=None)
        ):
            with patch.object(
                flow,
                "async_step_ble_light",
                new=AsyncMock(return_value={"type": "form"}),
            ) as mock_manual:
                await flow.async_step_ble_configure(
                    user_input={
                        CONF_SERIAL_NUMBER: VALID_SERIAL,
                        CONF_BLE_MAC: VALID_MAC,
                    }
                )
                mock_manual.assert_called_once()

    @pytest.mark.asyncio
    async def test_serial_and_mac_stored_before_ltk_fetch(self, flow):
        """_ble_serial and _ble_mac are stored before LTK fetch so the fallback can pre-fill."""
        with patch.object(
            flow, "_fetch_ltk_from_account", new=AsyncMock(return_value=None)
        ):
            with patch.object(
                flow, "async_step_ble_light", new=AsyncMock(return_value={})
            ):
                await flow.async_step_ble_configure(
                    user_input={
                        CONF_SERIAL_NUMBER: VALID_SERIAL,
                        CONF_BLE_MAC: VALID_MAC,
                    }
                )

        assert flow._ble_serial == VALID_SERIAL
        assert flow._ble_mac == VALID_MAC


# ---------------------------------------------------------------------------
# Tests for _fetch_ltk_from_account
# ---------------------------------------------------------------------------


class TestFetchLtkFromAccount:
    """Tests for the _fetch_ltk_from_account helper."""

    @pytest.mark.asyncio
    async def test_no_cloud_entries_returns_none(self, flow):
        """When no cloud account entries exist the helper returns None."""
        flow.hass.config_entries.async_entries.return_value = []
        result = await flow._fetch_ltk_from_account(VALID_SERIAL)
        assert result is None

    @pytest.mark.asyncio
    async def test_cloud_entry_without_token_skipped(self, flow):
        """An entry lacking auth_token is skipped."""
        entry = MagicMock()
        entry.data = {}  # no auth_token
        flow.hass.config_entries.async_entries.return_value = [entry]
        result = await flow._fetch_ltk_from_account(VALID_SERIAL)
        assert result is None
        # async_add_executor_job should not have been called
        flow.hass.async_add_executor_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_cloud_entry_with_token_returns_ltk(self, flow):
        """Entry with auth_token causes executor LTK fetch, returning result."""
        entry = MagicMock()
        entry.data = {"auth_token": VALID_AUTH_TOKEN}
        flow.hass.config_entries.async_entries.return_value = [entry]
        flow.hass.async_add_executor_job = AsyncMock(return_value=VALID_LTK)

        result = await flow._fetch_ltk_from_account(VALID_SERIAL)
        assert result == (VALID_LTK, "")

    @pytest.mark.asyncio
    async def test_first_successful_entry_returned(self, flow):
        """The LTK from the first entry that succeeds is returned immediately."""
        entry1 = MagicMock()
        entry1.data = {"auth_token": "token1"}
        entry2 = MagicMock()
        entry2.data = {"auth_token": "token2"}
        flow.hass.config_entries.async_entries.return_value = [entry1, entry2]

        call_count = 0

        async def fake_executor(func, *args):
            nonlocal call_count
            call_count += 1
            return VALID_LTK  # succeed on first try

        flow.hass.async_add_executor_job = fake_executor

        result = await flow._fetch_ltk_from_account(VALID_SERIAL)
        assert result == (VALID_LTK, "")
        assert call_count == 1  # returned after first entry

    @pytest.mark.asyncio
    async def test_executor_returns_none_tries_next_entry(self, flow):
        """None from one entry causes the next entry to be tried."""
        entry1 = MagicMock()
        entry1.data = {"auth_token": "token1"}
        entry2 = MagicMock()
        entry2.data = {"auth_token": "token2"}
        flow.hass.config_entries.async_entries.return_value = [entry1, entry2]

        results = [None, VALID_LTK]
        idx = 0

        async def fake_executor(func, *args):
            nonlocal idx
            val = results[idx]
            idx += 1
            return val

        flow.hass.async_add_executor_job = fake_executor

        result = await flow._fetch_ltk_from_account(VALID_SERIAL)
        assert result == (VALID_LTK, "")


# ---------------------------------------------------------------------------
# Tests for _cloud_fetch_ltk
# ---------------------------------------------------------------------------


class TestCloudFetchLtk:
    """Tests for the synchronous _cloud_fetch_ltk helper."""

    def test_successful_fetch_returns_ltk(self, flow):
        """A successful HTTP response with 'ltk' key returns the LTK string."""
        import json

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ltk": VALID_LTK}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = flow._cloud_fetch_ltk(VALID_SERIAL, VALID_AUTH_TOKEN)

        assert result == VALID_LTK

    def test_http_error_tries_next_url(self, flow):
        """HTTP errors cause the next base URL to be tried; returns LTK from last."""
        import json

        success_response = MagicMock()
        success_response.read.return_value = json.dumps({"ltk": VALID_LTK}).encode()
        success_response.__enter__ = lambda s: s
        success_response.__exit__ = MagicMock(return_value=False)

        call_count = 0

        def fake_urlopen(req, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
            return success_response

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = flow._cloud_fetch_ltk(VALID_SERIAL, VALID_AUTH_TOKEN)

        assert result == VALID_LTK
        assert call_count == 2

    def test_all_urls_fail_returns_none(self, flow):
        """If all base URLs raise errors the helper returns None."""
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(None, 500, "Server Error", {}, None),
        ):
            result = flow._cloud_fetch_ltk(VALID_SERIAL, VALID_AUTH_TOKEN)

        assert result is None

    def test_missing_ltk_key_returns_none(self, flow):
        """A response that does not contain 'ltk' returns None."""
        import json

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"error": "not found"}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = flow._cloud_fetch_ltk(VALID_SERIAL, VALID_AUTH_TOKEN)

        assert result is None

    def test_non_string_ltk_returns_none(self, flow):
        """A non-string 'ltk' value in the response returns None."""
        import json

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ltk": 12345}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = flow._cloud_fetch_ltk(VALID_SERIAL, VALID_AUTH_TOKEN)

        assert result is None

    def test_uses_correct_auth_headers(self, flow):
        """The request must include the correct Authorization and auth-code headers."""
        import json

        captured_requests = []
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ltk": VALID_LTK}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        def capture(req, **kwargs):
            captured_requests.append(req)
            return mock_response

        with patch("urllib.request.urlopen", side_effect=capture):
            flow._cloud_fetch_ltk(VALID_SERIAL, VALID_AUTH_TOKEN)

        assert captured_requests, "urlopen was not called"
        req = captured_requests[0]
        assert req.get_header("Authorization") == f"Bearer {VALID_AUTH_TOKEN}"
        assert req.get_header("X-dyson-apiauthcode") == "80541406"


# ---------------------------------------------------------------------------
# Tests for async_step_ble_light (manual LTK entry + pre-fill)
# ---------------------------------------------------------------------------


class TestBleLightStep:
    """Tests for async_step_ble_light."""

    @pytest.mark.asyncio
    async def test_shows_form_without_input(self, flow):
        """No user_input renders the ble_light form."""
        result = await flow.async_step_ble_light()
        assert result["step_id"] == "ble_light"

    @pytest.mark.asyncio
    async def test_prefills_serial_and_mac_from_state(self, flow):
        """Previously stored _ble_serial and _ble_mac appear as defaults."""
        flow._ble_mac = VALID_MAC
        flow._ble_serial = VALID_SERIAL
        await flow.async_step_ble_light()
        schema = flow.async_show_form.call_args[1]["data_schema"]
        key_defaults = {
            str(k): k.default() if callable(k.default) else k.default
            for k in schema.schema
            if hasattr(k, "default")
        }
        assert key_defaults.get("serial_number") == VALID_SERIAL
        assert key_defaults.get("ble_mac") == VALID_MAC

    @pytest.mark.asyncio
    async def test_valid_input_creates_entry(self, flow):
        """Valid serial, MAC, and LTK result in a config entry being created."""
        user_input = {
            CONF_SERIAL_NUMBER: VALID_SERIAL,
            CONF_BLE_MAC: VALID_MAC,
            CONF_LTK: VALID_LTK,
        }
        result = await flow.async_step_ble_light(user_input)
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_LTK] == VALID_LTK

    @pytest.mark.asyncio
    async def test_missing_serial_shows_error(self, flow):
        """Empty serial number shows a 'required' error."""
        user_input = {
            CONF_SERIAL_NUMBER: "",
            CONF_BLE_MAC: VALID_MAC,
            CONF_LTK: VALID_LTK,
        }
        result = await flow.async_step_ble_light(user_input)
        assert result["errors"][CONF_SERIAL_NUMBER] == "required"

    @pytest.mark.asyncio
    async def test_invalid_mac_shows_error(self, flow):
        """Invalid MAC address shows error."""
        user_input = {
            CONF_SERIAL_NUMBER: VALID_SERIAL,
            CONF_BLE_MAC: "bad_mac",
            CONF_LTK: VALID_LTK,
        }
        result = await flow.async_step_ble_light(user_input)
        assert result["errors"][CONF_BLE_MAC] == "invalid_mac_address"

    @pytest.mark.asyncio
    async def test_invalid_ltk_hex_shows_error(self, flow):
        """Non-hex LTK shows an 'invalid_ltk' error."""
        user_input = {
            CONF_SERIAL_NUMBER: VALID_SERIAL,
            CONF_BLE_MAC: VALID_MAC,
            CONF_LTK: "not-hex!",
        }
        result = await flow.async_step_ble_light(user_input)
        assert result["errors"][CONF_LTK] == "invalid_ltk"

    @pytest.mark.asyncio
    async def test_odd_length_ltk_shows_error(self, flow):
        """LTK hex string with odd length shows an 'invalid_ltk' error."""
        user_input = {
            CONF_SERIAL_NUMBER: VALID_SERIAL,
            CONF_BLE_MAC: VALID_MAC,
            CONF_LTK: "abc",  # odd length
        }
        result = await flow.async_step_ble_light(user_input)
        assert result["errors"][CONF_LTK] == "invalid_ltk"

    @pytest.mark.asyncio
    async def test_existing_serial_shows_error(self, flow):
        """Serial already in HA shows 'already_configured'."""
        flow._abort_if_unique_id_configured.side_effect = Exception("dupe")
        user_input = {
            CONF_SERIAL_NUMBER: VALID_SERIAL,
            CONF_BLE_MAC: VALID_MAC,
            CONF_LTK: VALID_LTK,
        }
        result = await flow.async_step_ble_light(user_input)
        assert result["errors"][CONF_SERIAL_NUMBER] == "already_configured"

    @pytest.mark.asyncio
    async def test_proxy_included_when_provided(self, flow):
        """CONF_BLE_PROXY is stored when the user supplies a proxy host."""
        user_input = {
            CONF_SERIAL_NUMBER: VALID_SERIAL,
            CONF_BLE_MAC: VALID_MAC,
            CONF_LTK: VALID_LTK,
            CONF_BLE_PROXY: "  192.168.2.10  ",
        }
        result = await flow.async_step_ble_light(user_input)
        assert result["data"][CONF_BLE_PROXY] == "192.168.2.10"
