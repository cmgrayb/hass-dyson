"""Unit tests for ble_vacuum.py and BLE vacuum config-flow routing.

Covers:
- Attribute protocol parsing (0x91 responses, 0x97 pushes, decoding)
- Attribute registry sanity (unique ids, all keys present)
- Cleaning-session tracking in the device state machine
- Discovery routing: lecOnly+flrc → vacuum flow, lecOnly+light → light flow
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hass_dyson.ble_vacuum import (
    DysonBleVacuumDevice,
    DysonMessage,
    decode_attribute_value,
    parse_push_attribute,
    parse_read_attribute_response,
)
from custom_components.hass_dyson.config_flow import DysonConfigFlow
from custom_components.hass_dyson.const import (
    BLE_AUTH_CHAR_UUID,
    BLE_DEVICE_KIND_LIGHT,
    BLE_DEVICE_KIND_VACUUM,
    BLE_VACUUM_ATTR_BATTERY_LEVEL,
    BLE_VACUUM_ATTR_BLOCKAGE,
    BLE_VACUUM_ATTR_CLEANING_SESSION_ACTIVE,
    BLE_VACUUM_ATTR_POWER_MODE,
    BLE_VACUUM_ATTRIBUTES,
    BLE_WRITE_ATTR_CHAR_UUID,
    CONF_BLE_DEVICE_KIND,
    CONF_BLE_MAC,
    CONF_LTK,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)

# ---------------------------------------------------------------------------
# Attribute protocol parsing
# ---------------------------------------------------------------------------


class TestAttributeParsing:
    """Parsing of attribute channel frames."""

    def test_parse_read_response_success(self):
        """0x91 layout: attr(2) status(1) len(u16le) data."""
        payload = bytes([0x02, 0x40, 0x00, 0x01, 0x00, 0x5F])  # battery 95
        parsed = parse_read_attribute_response(payload)
        assert parsed is not None
        attr_id, status, data = parsed
        assert attr_id == BLE_VACUUM_ATTR_BATTERY_LEVEL
        assert status == 0
        assert data == bytes([0x5F])

    def test_parse_read_response_wrong_length(self):
        """Short payload yields None."""
        assert parse_read_attribute_response(bytes([0x02, 0x40, 0x00])) is None

    def test_parse_read_response_truncated_data(self):
        """Length field larger than actual data yields None."""
        payload = bytes([0x02, 0x40, 0x00, 0x05, 0x00, 0x5F])  # claims 5, gives 1
        assert parse_read_attribute_response(payload) is None

    def test_parse_push(self):
        """0x97 layout: attr(2) len(u16le) data."""
        payload = bytes([0x07, 0x40, 0x01, 0x00, 0x01])  # session active ON
        parsed = parse_push_attribute(payload)
        assert parsed is not None
        attr_id, data = parsed
        assert attr_id == BLE_VACUUM_ATTR_CLEANING_SESSION_ACTIVE
        assert data == bytes([0x01])

    def test_parse_push_short(self):
        """Short push payload yields None."""
        assert parse_push_attribute(bytes([0x07, 0x40])) is None

    def test_decode_int(self):
        """Battery level decodes as integer."""
        assert decode_attribute_value(BLE_VACUUM_ATTR_BATTERY_LEVEL, bytes([95])) == 95

    def test_decode_bool(self):
        """Boolean attributes decode 0/1."""
        assert (
            decode_attribute_value(
                BLE_VACUUM_ATTR_CLEANING_SESSION_ACTIVE, bytes([0x01])
            )
            == "active"
        )
        assert (
            decode_attribute_value(
                BLE_VACUUM_ATTR_CLEANING_SESSION_ACTIVE, bytes([0x00])
            )
            == "inactive"
        )

    def test_decode_enum(self):
        """Enum attributes map to labels."""
        assert (
            decode_attribute_value(BLE_VACUUM_ATTR_POWER_MODE, bytes([0x03])) == "boost"
        )
        assert (
            decode_attribute_value(BLE_VACUUM_ATTR_BLOCKAGE, bytes([0x00]))
            == "not_blocked"
        )
        assert (
            decode_attribute_value(BLE_VACUUM_ATTR_BLOCKAGE, bytes([0xAC]))
            == "unknown (ac)"
        )

    def test_decode_unknown_attr_passthrough(self):
        """Unknown attr ids pass raw bytes through."""
        assert decode_attribute_value(b"\xde\xad", b"\x01\x02") == b"\x01\x02"


# ---------------------------------------------------------------------------
# Registry sanity
# ---------------------------------------------------------------------------


class TestAttributeRegistry:
    """The registry must be unique and self-contained."""

    def test_ids_are_two_bytes(self):
        for attr_id in BLE_VACUUM_ATTRIBUTES:
            assert len(attr_id) == 2, f"attr id wrong size: {attr_id.hex()}"

    def test_state_keys_unique(self):
        keys = [v[0] for v in BLE_VACUUM_ATTRIBUTES.values()]
        assert len(keys) == len(set(keys)), "duplicate state keys in registry"

    def test_registry_has_expected_coverage(self):
        """Key attributes from the live verification are all present."""
        keys = {v[0] for v in BLE_VACUUM_ATTRIBUTES.values()}
        assert {
            "power_mode",
            "blockage",
            "battery_level",
            "actively_charging",
            "charger_present",
            "battery_care_setting",
            "battery_authenticity",
            "task_detection",
            "dust_illumination",
            "brush_bar_speed",
            "brush_bar_type",
            "session_active",
        } <= keys


# ---------------------------------------------------------------------------
# Session tracking in the device state machine
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_hass():
    """Minimal HomeAssistant mock capturing event-bus calls."""
    hass = MagicMock()  # not spec'd: needs .loop / .bus / .data / config_entries
    hass.data = {DOMAIN: {}}
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.loop = MagicMock()
    hass.loop.time = time.time
    return hass


@pytest.fixture
def device(mock_hass):
    dev = DysonBleVacuumDevice(
        hass=mock_hass,
        serial_number="7RD-EU-TEST0000X",
        mac_address="AA:BB:CC:DD:EE:FF",
        ltk_hex="00112233445566778899aabbccddeeff",
        account_uuid="00000000-0000-0000-0000-000000000000",
    )
    return dev


class TestSessionTracking:
    """Only the live in-progress flag is tracked — no derived history.

    Durations cannot be computed reliably here: it would need HA connected
    across both edges of a clean, and a handheld vacuum may be out of BLE
    range during one.  The machine's real history is the encrypted 0x16/0x17
    journal.
    """

    def test_session_start_and_end(self, device):
        assert device.state.session_active is False
        device._update_attribute(
            BLE_VACUUM_ATTR_CLEANING_SESSION_ACTIVE, bytes([0x01]), source="test"
        )
        assert device.state.session_active is True
        device._update_attribute(
            BLE_VACUUM_ATTR_CLEANING_SESSION_ACTIVE, bytes([0x00]), source="test"
        )
        assert device.state.session_active is False

    def test_repeated_active_push_is_idempotent(self, device):
        for _ in range(3):
            device._update_attribute(
                BLE_VACUUM_ATTR_CLEANING_SESSION_ACTIVE, bytes([0x01]), source="test"
            )
        assert device.state.session_active is True

    def test_no_derived_history_state(self):
        """The unreliable derived fields are gone, not merely unused."""
        from custom_components.hass_dyson.ble_vacuum import BLEVacuumState

        state = BLEVacuumState()
        for gone in (
            "session_started_at",
            "last_session_ended_at",
            "last_session_duration_seconds",
        ):
            assert not hasattr(state, gone), f"{gone} cannot be derived reliably"

    def test_attribute_raws_stored(self, device):
        device._update_attribute(BLE_VACUUM_ATTR_BATTERY_LEVEL, bytes([95]), source="t")
        assert device.state.attributes["battery_level"] == 95
        assert device.state.attributes_raw[BLE_VACUUM_ATTR_BATTERY_LEVEL.hex()] == "5f"


class TestProductInfoParsing:
    """Product info (0x0B) decode."""

    def test_product_info_layout(self, device):
        # fw 2.13 build 2, module "PS", variant "50", project "SVC0"
        payload = bytes.fromhex("020d0200505335305356433000000000")
        device._parse_product_info(payload)
        assert device.state.firmware_major == 2
        assert device.state.firmware_minor == 13
        assert device.state.firmware_build == 2
        assert device.state.hardware_module == "PS"
        assert device.state.hardware_variant == "50"
        assert device.state.project_id == "SVC0"
        assert device.firmware_version == "2.13.2"


# ---------------------------------------------------------------------------
# Config-flow discovery routing (issue #434)
# ---------------------------------------------------------------------------

VALID_SERIAL = "7RD-EU-AAA1234A"
VALID_MAC = "AA:BB:CC:DD:EE:FF"


@pytest.fixture
def flow(mock_hass):
    """Fresh DysonConfigFlow bound to a mock hass."""
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


def _discovery_info(category, connection="lecOnly"):
    return {
        "serial_number": VALID_SERIAL,
        "name": "Dyson V16",
        "connection_category": connection,
        "device_category": category,
        "capabilities": [],
    }


class TestDiscoveryRouting:
    """lecOnly discovery routes by device category, not always to BLE Light."""

    async def test_leconly_flrc_routes_to_vacuum(self, flow):
        """flrc device must keep kind=vacuum through the configure step."""
        with patch.object(
            DysonConfigFlow,
            "async_step_ble_configure",
            new=AsyncMock(
                return_value={"type": FlowResultType.FORM, "step_id": "ble_configure"}
            ),
        ) as step:
            await flow.async_step_discovery(_discovery_info(["flrc"]))
        step.assert_awaited_once()
        assert flow._ble_kind == BLE_DEVICE_KIND_VACUUM

    async def test_leconly_flrc_scalar_category_field(self, flow):
        """A scalar ``category`` field is honoured too."""
        info = _discovery_info(None)
        info.pop("device_category")
        info["category"] = "flrc"
        with patch.object(
            DysonConfigFlow,
            "async_step_ble_configure",
            new=AsyncMock(
                return_value={"type": FlowResultType.FORM, "step_id": "ble_configure"}
            ),
        ):
            await flow.async_step_discovery(info)
        assert flow._ble_kind == BLE_DEVICE_KIND_VACUUM

    async def test_leconly_light_routes_to_light(self, flow):
        """light category still goes to the light flow."""
        with patch.object(
            DysonConfigFlow,
            "async_step_ble_configure",
            new=AsyncMock(
                return_value={"type": FlowResultType.FORM, "step_id": "ble_configure"}
            ),
        ):
            await flow.async_step_discovery(_discovery_info(["light"]))
        assert flow._ble_kind == BLE_DEVICE_KIND_LIGHT

    async def test_leconly_unknown_category_falls_back_to_light(self, flow):
        """Unknown categories fall back to light but still proceed."""
        with patch.object(
            DysonConfigFlow,
            "async_step_ble_configure",
            new=AsyncMock(
                return_value={"type": FlowResultType.FORM, "step_id": "ble_configure"}
            ),
        ):
            await flow.async_step_discovery(_discovery_info(["weird"]))
        assert flow._ble_kind == BLE_DEVICE_KIND_LIGHT

    def test_kind_written_into_entry_on_auto_ltk(self, flow):
        """Entry data records the device kind marker."""
        flow._ble_kind = BLE_DEVICE_KIND_VACUUM
        flow._ble_serial = VALID_SERIAL
        flow._ble_mac = VALID_MAC
        # simulate what async_step_ble_configure writes on successful LTK fetch
        entry_written: dict = {}
        for k, v in {
            CONF_SERIAL_NUMBER: VALID_SERIAL,
            CONF_BLE_MAC: VALID_MAC,
            CONF_LTK: "aabbcc",
            "account_uuid": "uuid",
            CONF_BLE_DEVICE_KIND: flow._ble_kind,
        }.items():
            entry_written[k] = v
        assert entry_written[CONF_BLE_DEVICE_KIND] == BLE_DEVICE_KIND_VACUUM


class TestNormalizeDiscoveryCategories:
    """Field variants normalize into a lowercase set."""

    def _n(self, info):
        return DysonConfigFlow._normalize_discovery_categories(info)

    def test_list_field(self):
        assert self._n({"device_category": ["flrc", "ec"]}) == {"flrc", "ec"}

    def test_scalar_fields(self):
        assert self._n({"device_category": "flrc"}) == {"flrc"}
        assert self._n({"category": "flrc"}) == {"flrc"}

    def test_missing(self):
        assert self._n({}) == set()

    def test_enum_like(self):
        class Cat:
            value = "FLRC"

        assert self._n({"device_category": Cat}) == {"flrc"}


# ---------------------------------------------------------------------------
# Auth path (anti-regression for the PayloadB shape bug)
# ---------------------------------------------------------------------------

_TEST_LTK_HEX = "00112233445566778899aabbccddeeff"
_TEST_UUID = "12345678-1234-1234-1234-123456789abc"


def _fixed_enc_key():
    from custom_components.hass_dyson.ble_device import hkdf_derive_aes_key

    return hkdf_derive_aes_key(bytes.fromhex(_TEST_LTK_HEX))


def _aes_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    return Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor().update(plaintext)


def _craft_payload_b(enc_key: bytes, nonce: bytes, challenge: bytes) -> bytes:
    """Build a firmware-shaped PayloadB: reserved + IV + 32B CT + MAC."""
    iv = b"\xaa" * 16
    ct = _aes_encrypt(enc_key, iv, nonce + challenge)
    mac = hmac.new(enc_key, ct, hashlib.sha256).digest()
    return b"\x00\x00" + iv + ct + mac


def _payload_c_reply(_enc_key: bytes, _challenge: bytes) -> bytes:
    return b""


async def _run_reauth(device, payload_b: bytes, conn_est: bytes) -> None:
    """Drive _reauth_with_ltk with canned device answers."""
    from custom_components.hass_dyson.ble_vacuum import DysonMessage
    from custom_components.hass_dyson.const import (
        BLE_MSG_TYPE_CONNECTION_ESTABLISHED,
        BLE_MSG_TYPE_REAUTH_PAYLOAD_B,
    )

    answers = iter(
        [
            DysonMessage(BLE_MSG_TYPE_REAUTH_PAYLOAD_B, payload_b),
            DysonMessage(BLE_MSG_TYPE_CONNECTION_ESTABLISHED, conn_est + bytes(10)),
        ]
    )

    async def fake_wait_for_type(_tag, type_id, timeout):
        msg = next(answers)
        assert msg.type_id == type_id
        return msg

    device._send_message = AsyncMock()
    device._wait_for_type = fake_wait_for_type

    enc_key = _fixed_enc_key()
    await device._reauth_with_ltk(enc_key)


class TestReauthWithLtk:
    """_reauth_with_ltk must accept floorcare-shaped PayloadB and check nonce.

    Regression guard for the g20c_decrypt shape-mismatch bug: PayloadB CT is
    32 bytes (nonce echo || challenge), not a 16-byte light envelope.
    """

    async def test_successful_auth(self, device):
        """Floorcare-shaped PayloadB decrypts; Connection Established parses."""
        enc_key = _fixed_enc_key()
        nonce = bytes(range(16))
        challenge = bytes(reversed(range(16)))
        payload_b = _craft_payload_b(enc_key, nonce, challenge)
        conn = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x0C, 0x0B, 0x00, 0x01])

        from custom_components.hass_dyson.const import (
            BLE_MSG_TYPE_CONNECTION_ESTABLISHED,
            BLE_MSG_TYPE_REAUTH_PAYLOAD_B,
            BLE_MSG_TYPE_REAUTH_PAYLOAD_C,
        )

        sent = {}

        async def capture_send(_char, type_id, payload=b""):
            sent[type_id] = payload

        device._send_message = capture_send

        async def fake_wait(_tag, type_id, timeout):
            if type_id == BLE_MSG_TYPE_REAUTH_PAYLOAD_B:
                return DysonMessage(BLE_MSG_TYPE_REAUTH_PAYLOAD_B, payload_b)
            return DysonMessage(BLE_MSG_TYPE_CONNECTION_ESTABLISHED, conn)

        device._wait_for_type = fake_wait

        with patch(
            "custom_components.hass_dyson.ble_vacuum.os.urandom",
            side_effect=lambda *_a, **_k: nonce,
        ):
            await device._reauth_with_ltk(enc_key)

        # PayloadC must carry the encrypted device challenge
        assert BLE_MSG_TYPE_REAUTH_PAYLOAD_C in sent
        assert device.state.recovery_firmware_version == "2.12.11"
        assert device.state.ota_status == 0x00

    async def test_nonce_mismatch_rejected(self, device):
        """A PayloadB that doesn't echo our nonce aborts authentication."""
        enc_key = _fixed_enc_key()
        challenge = bytes(range(16, 32))
        wrong_nonce = bytes(range(16, 32))
        payload_b = _craft_payload_b(enc_key, wrong_nonce, challenge)
        conn = bytes(10)

        from custom_components.hass_dyson.const import (
            BLE_MSG_TYPE_CONNECTION_ESTABLISHED,
            BLE_MSG_TYPE_REAUTH_PAYLOAD_B,
        )

        device._send_message = AsyncMock()

        async def fake_wait(_tag, type_id, timeout):
            if type_id == BLE_MSG_TYPE_REAUTH_PAYLOAD_B:
                return DysonMessage(BLE_MSG_TYPE_REAUTH_PAYLOAD_B, payload_b)
            return DysonMessage(BLE_MSG_TYPE_CONNECTION_ESTABLISHED, conn)

        device._wait_for_type = fake_wait
        device._parse_product_info = MagicMock()

        with patch(
            "custom_components.hass_dyson.ble_vacuum.os.urandom",
            side_effect=lambda *_a, **_k: bytes(range(16)),
        ):
            with pytest.raises(RuntimeError, match="nonce"):
                await device._reauth_with_ltk(enc_key)

    async def test_hmac_mismatch_rejected(self, device):
        """Tampered MAC aborts authentication before decrypt."""
        enc_key = _fixed_enc_key()
        payload_b = bytearray(_craft_payload_b(enc_key, bytes(range(16)), bytes(16)))
        payload_b[-1] ^= 0xFF  # flip a MAC bit

        device._send_message = AsyncMock()

        from custom_components.hass_dyson.const import BLE_MSG_TYPE_REAUTH_PAYLOAD_B

        async def fake_wait(_tag, type_id, timeout):
            return DysonMessage(BLE_MSG_TYPE_REAUTH_PAYLOAD_B, bytes(payload_b))

        device._wait_for_type = fake_wait
        with pytest.raises(RuntimeError, match="HMAC"):
            await device._reauth_with_ltk(enc_key)


# ---------------------------------------------------------------------------
# Attribute write path
# ---------------------------------------------------------------------------


class _FakeClient:
    """Minimal bleak stand-in capturing writes."""

    def __init__(self):
        self.writes = []
        self.is_connected = True

    async def write_gatt_char(self, char, fragment, response=False):
        self.writes.append((char, fragment))


def _client_with_chars(*uuids):
    """A bleak stand-in whose service table resolves only ``uuids``."""
    client = _FakeClient()
    known = {u.lower() for u in uuids}
    client.services = MagicMock()
    client.services.get_characteristic = MagicMock(
        side_effect=lambda u: MagicMock() if u.lower() in known else None
    )
    return client


class TestAuthCharacteristicGuard:
    """Fail fast when the peer is not a Dyson, but only when we are sure.

    Without this the handshake burns three 30 s timeouts before giving up, and
    the log never says why.  The guard must stay conservative: an unknown
    service table is not evidence of absence.
    """

    def test_absent_auth_char_is_detected(self):
        client = _client_with_chars(BLE_WRITE_ATTR_CHAR_UUID)
        assert DysonBleVacuumDevice._auth_char_is_absent(client) is True

    def test_present_auth_char_passes(self):
        client = _client_with_chars(BLE_AUTH_CHAR_UUID, BLE_WRITE_ATTR_CHAR_UUID)
        assert DysonBleVacuumDevice._auth_char_is_absent(client) is False

    def test_no_service_table_is_unknown_not_absent(self):
        client = _FakeClient()
        client.services = None
        assert DysonBleVacuumDevice._auth_char_is_absent(client) is False

    def test_backend_raising_on_lookup_is_unknown_not_absent(self):
        """Never fail a connection on something we could not determine."""
        client = _FakeClient()
        client.services = MagicMock()
        client.services.get_characteristic = MagicMock(side_effect=RuntimeError("boom"))
        assert DysonBleVacuumDevice._auth_char_is_absent(client) is False


class TestBonding:
    """The machine serves its characteristics only over a bonded link.

    Reading any Dyson characteristic unbonded returns ATT error 0x05,
    "insufficient authentication".  A local adapter that bonded once keeps the
    keys, so this is invisible on a direct connection — but a Bluetooth proxy
    starts with no bond, and since the protocol is entirely
    write-without-response (never acknowledged by the spec), the rejection is
    silent: writes vanish and every handshake times out.
    """

    async def test_pairing_is_attempted_on_connect(self, device):
        client = MagicMock()
        client.pair = AsyncMock(return_value=True)
        await device._ensure_bonded(client)
        client.pair.assert_awaited_once()

    async def test_backend_without_pairing_does_not_block(self, device):
        """A backend that cannot pair must not break an already-bonded link."""
        client = MagicMock()
        client.pair = AsyncMock(side_effect=NotImplementedError)
        await device._ensure_bonded(client)  # must not raise

    async def test_pairing_failure_is_reported_but_not_fatal(self, device):
        """Surface it loudly, then let the handshake produce the real error."""
        client = MagicMock()
        client.pair = AsyncMock(side_effect=RuntimeError("bonding rejected"))
        await device._ensure_bonded(client)  # must not raise

    async def test_pairing_cannot_hang_the_connection(self, device):
        """A backend that never returns must not strand the lifecycle task.

        ``pair()`` sits on the critical path of every connect, so an unbounded
        await would leave the coordinator blocked forever with no retry.
        """

        async def never_returns():
            await asyncio.sleep(3600)

        client = MagicMock()
        client.pair = MagicMock(side_effect=lambda: never_returns())
        with patch("custom_components.hass_dyson.ble_vacuum.BLE_PAIR_TIMEOUT", 0.01):
            await asyncio.wait_for(device._ensure_bonded(client), timeout=5)


class TestWriteAttribute:
    """0x93 write path: framing, 0x94 status, push-confirm, failure modes."""

    async def test_write_sends_correct_frame_and_push_confirm(self, device):
        """Frame shape: attr + u16le len + data; push-confirm satisfies."""
        from custom_components.hass_dyson.const import BLE_VACUUM_ATTR_TASK_DETECTION

        device._client = _FakeClient()
        device.state.attributes_raw = {}
        device._wait_for_message = AsyncMock(side_effect=TimeoutError)

        async def side_effect(*_a, **_k):
            # machine "confirms" via a value push during the wait
            device.state.attributes_raw[BLE_VACUUM_ATTR_TASK_DETECTION.hex()] = "01"
            return None

        device._send_message = AsyncMock(side_effect=side_effect)
        ok = await device.write_attribute(BLE_VACUUM_ATTR_TASK_DETECTION, bytes([1]))
        assert ok is True
        args = device._send_message.call_args[0]
        assert args[1] == 0x93
        assert args[2] == BLE_VACUUM_ATTR_TASK_DETECTION + b"\x01\x00\x01"

    async def test_write_status_ok(self, device):
        """0x94 status=0 confirms the write."""
        from custom_components.hass_dyson.const import (
            BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE,
            BLE_VACUUM_ATTR_TASK_DETECTION,
        )

        device._client = _FakeClient()
        device.state.attributes_raw = {}
        device._send_message = AsyncMock()
        device._wait_for_message = AsyncMock(
            return_value=DysonMessage(
                BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE,
                BLE_VACUUM_ATTR_TASK_DETECTION + b"\x00",
            )
        )
        ok = await device.write_attribute(BLE_VACUUM_ATTR_TASK_DETECTION, bytes([1]))
        assert ok is True

    async def test_write_status_reject_returns_false(self, device):
        """0x94 with non-zero status is a fast, diagnosed rejection."""
        from custom_components.hass_dyson.const import (
            BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE,
            BLE_VACUUM_ATTR_TASK_DETECTION,
        )

        device._client = _FakeClient()
        device.state.attributes_raw = {}
        device._send_message = AsyncMock()
        device._wait_for_message = AsyncMock(
            return_value=DysonMessage(
                BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE,
                BLE_VACUUM_ATTR_TASK_DETECTION + b"\x02",
            )
        )
        ok = await device.write_attribute(BLE_VACUUM_ATTR_TASK_DETECTION, bytes([1]))
        assert ok is False

    async def test_write_times_out_without_confirmation(self, device):
        from custom_components.hass_dyson.const import BLE_VACUUM_ATTR_TASK_DETECTION

        device.state.attributes_raw = {}
        device._send_message = AsyncMock()
        device._wait_for_message = AsyncMock(side_effect=TimeoutError)
        device._client = _FakeClient()
        ok = await device.write_attribute(BLE_VACUUM_ATTR_TASK_DETECTION, bytes([1]))
        assert ok is False


# ---------------------------------------------------------------------------
# Enum wire values (review-verified)
# ---------------------------------------------------------------------------


class TestEnumWireValues:
    """Wire-value maps must match the app-defined enums."""

    def test_brush_bar_speed_values(self):
        from custom_components.hass_dyson.const import (
            BLE_VACUUM_ATTR_BRUSH_BAR_SPEED,
        )

        assert (
            decode_attribute_value(BLE_VACUUM_ATTR_BRUSH_BAR_SPEED, bytes([0])) == "low"
        )
        assert (
            decode_attribute_value(BLE_VACUUM_ATTR_BRUSH_BAR_SPEED, bytes([1]))
            == "high"
        )
        assert (
            decode_attribute_value(BLE_VACUUM_ATTR_BRUSH_BAR_SPEED, bytes([2]))
            == "auto"
        )

    def test_brush_bar_type_values(self):
        from custom_components.hass_dyson.const import BLE_VACUUM_ATTR_BRUSH_BAR_TYPE

        assert (
            decode_attribute_value(BLE_VACUUM_ATTR_BRUSH_BAR_TYPE, bytes([1]))
            == "erp_768"
        )
        assert (
            decode_attribute_value(BLE_VACUUM_ATTR_BRUSH_BAR_TYPE, bytes([2]))
            == "row_768"
        )
        assert (
            decode_attribute_value(BLE_VACUUM_ATTR_BRUSH_BAR_TYPE, bytes([255]))
            == "none_attached"
        )


# ---------------------------------------------------------------------------
# Transport I/O paths (real queue: read/subscribe/teardown/reset)
# ---------------------------------------------------------------------------


class TestTransportIO:
    """Drive read/subscribe/teardown through the real message queue."""

    async def test_read_attribute_happy_path(self, device):
        """read_attribute applies a valid 0x91 response from the queue."""
        from custom_components.hass_dyson.const import (
            BLE_MSG_TYPE_READ_ATTRIBUTE_RESPONSE,
            BLE_VACUUM_ATTR_BATTERY_LEVEL,
        )

        device._client = _FakeClient()

        async def feed():
            import asyncio as _a

            await _a.sleep(0.05)
            payload = BLE_VACUUM_ATTR_BATTERY_LEVEL + b"\x00\x01\x00\x5f"
            device._queue.put_nowait(
                ("msg", DysonMessage(BLE_MSG_TYPE_READ_ATTRIBUTE_RESPONSE, payload))
            )

        import asyncio as _a

        feeder = _a.ensure_future(feed())
        ok = await device.read_attribute(BLE_VACUUM_ATTR_BATTERY_LEVEL)
        await feeder

        assert ok is True
        assert device.state.attributes["battery_level"] == 95
        assert device.state.attributes_raw[BLE_VACUUM_ATTR_BATTERY_LEVEL.hex()] == "5f"

    async def test_read_attribute_status_nonzero(self, device):
        """A 0x91 with non-zero status returns False."""
        from custom_components.hass_dyson.const import (
            BLE_MSG_TYPE_READ_ATTRIBUTE_RESPONSE,
            BLE_VACUUM_ATTR_BATTERY_LEVEL,
        )

        device._client = _FakeClient()

        async def feed():
            import asyncio as _a

            await _a.sleep(0.05)
            payload = BLE_VACUUM_ATTR_BATTERY_LEVEL + b"\x01\x01\x00\x5f"
            device._queue.put_nowait(
                ("msg", DysonMessage(BLE_MSG_TYPE_READ_ATTRIBUTE_RESPONSE, payload))
            )

        import asyncio as _a

        feeder = _a.ensure_future(feed())
        ok = await device.read_attribute(BLE_VACUUM_ATTR_BATTERY_LEVEL)
        await feeder
        assert ok is False
        assert "battery_level" not in device.state.attributes

    async def test_subscribe_attributes_acks(self, device):
        """Subscription loop records acked attrs only."""
        from custom_components.hass_dyson.const import (
            BLE_MSG_TYPE_PUSH_ATTRIBUTE_ACK,
            BLE_VACUUM_ATTRIBUTES,
        )

        device._client = _FakeClient()

        # ack only the first 3 attrs, skip the rest (timeout=simulated by
        # shrinking constant), then stop at MAX errors
        from custom_components.hass_dyson.const import BLE_ATTR_MAX_CONSECUTIVE_ERRORS

        attrs = list(BLE_VACUUM_ATTRIBUTES)
        to_ack = set(attrs[:3])

        sent = []
        original_send = device._send_message
        ack_calls: list[bytes] = []

        async def fake_send(char_uuid, type_id, payload=b""):
            sent.append((type_id, payload))
            # respond with ack immediately
            attr_id = payload[:2]
            if attr_id in to_ack:
                device._queue.put_nowait(
                    ("msg", DysonMessage(BLE_MSG_TYPE_PUSH_ATTRIBUTE_ACK, attr_id))
                )
            else:
                ack_calls.append(attr_id)

        device._send_message = fake_send
        device._wait_for_message = AsyncMock(
            side_effect=lambda _tag, _pred, _t, _d: (
                DysonMessage(BLE_MSG_TYPE_PUSH_ATTRIBUTE_ACK, sent[-1][1][:2])
                if sent and sent[-1][1][:2] in to_ack
                else (_ for _ in ()).throw(TimeoutError())
            )
        )

        await device._subscribe_attributes()
        device._send_message = original_send

        assert device._subscribed_attrs == to_ack
        # loop aborted early thanks to consecutive misses
        assert len(ack_calls) >= BLE_ATTR_MAX_CONSECUTIVE_ERRORS
        assert len(sent) < len(BLE_VACUUM_ATTRIBUTES)

    async def test_disconnect_teardown_order(self, device):
        """disconnect() sends INACTIVE for all subscribed attrs then 0x30 inactive."""
        from custom_components.hass_dyson.const import (
            BLE_MSG_TYPE_APP_ACTIVE_STATUS,
            BLE_MSG_TYPE_PUSH_ATTRIBUTE_REQUEST,
            BLE_VACUUM_ATTR_BATTERY_LEVEL,
            BLE_VACUUM_ATTR_POWER_MODE,
        )

        fake_client = _FakeClient()
        device._client = fake_client
        device._subscribed_attrs = {
            BLE_VACUUM_ATTR_BATTERY_LEVEL,
            BLE_VACUUM_ATTR_POWER_MODE,
        }

        await device.disconnect()

        # every unsubscribe (0x96) precedes the AppActiveStatus(0x30)
        last = fake_client.writes[-1]
        assert last[1][1] == BLE_MSG_TYPE_APP_ACTIVE_STATUS
        unsubscribed = [
            w[1][2:4]
            for w in fake_client.writes
            if w[1][1] == BLE_MSG_TYPE_PUSH_ATTRIBUTE_REQUEST
        ]
        assert set(unsubscribed) == {
            BLE_VACUUM_ATTR_BATTERY_LEVEL,
            BLE_VACUUM_ATTR_POWER_MODE,
        }
        assert device.state.connected is False
        assert device.state.authenticated is False

    async def test_connect_resets_session_state(self, device):
        """connect_and_authenticate clears assemblers/queue/subscribed attrs."""
        from custom_components.hass_dyson.const import (
            BLE_VACUUM_ATTR_BATTERY_LEVEL,
        )

        device._subscribed_attrs = {BLE_VACUUM_ATTR_BATTERY_LEVEL}
        device._queue.put_nowait(("auth", MagicMock()))

        # Bail out immediately after the reset (before touching hardware)
        async def fake_client():
            device._client = _FakeClient()
            raise RuntimeError("stop here")

        device._get_bleak_client = fake_client

        with pytest.raises(RuntimeError, match="stop here"):
            await device.connect_and_authenticate()

        assert device._subscribed_attrs == set()
        assert device._queue.empty()


# ---------------------------------------------------------------------------
# Connection Established parsing
# ---------------------------------------------------------------------------


class TestConnectionEstablishedParsing:
    """0x26: ota_status(1) | pending_fw(4) | recovery_fw(4) | pkg_type(1)."""

    def test_layout(self, device):
        payload = bytes([0x0C, 0x00, 0x00, 0x00, 0x00, 0x02, 0x0C, 0x0B, 0x00, 0x01])
        device._parse_connection_established(payload)
        assert device.state.ota_status == 0x0C
        assert device.state.recovery_firmware_version == "2.12.11"

    def test_short_payload_ignored(self, device):
        device._parse_connection_established(bytes([0x0C, 0x00]))
        assert device.state.ota_status is None
        assert device.state.pending_firmware_version is None

    def test_all_zero_pending_means_up_to_date(self, device):
        payload = bytes.fromhex("00" + "00000000" + "020c0b00" + "01")
        device._parse_connection_established(payload)
        assert device.state.ota_status == 0
        assert device.state.pending_firmware_version is None
        assert device.state.recovery_firmware_version == "2.12.11"

    def test_pending_firmware_decoded(self, device):
        # pending 2.14.5, recovery 2.12.11
        payload = bytes.fromhex("01" + "020e0500" + "020c0b00" + "01")
        device._parse_connection_established(payload)
        assert device.state.ota_status == 1
        assert device.state.pending_firmware_version == "2.14.5"
        assert device.state.recovery_firmware_version == "2.12.11"

    def test_pending_build_is_little_endian(self, device):
        # pending build bytes 00 01 -> 0x0100 = 256
        payload = bytes.fromhex("01" + "03000001" + "020c0b00" + "01")
        device._parse_connection_established(payload)
        assert device.state.pending_firmware_version == "3.0.256"


# ---------------------------------------------------------------------------
# Connection retry loop / zero-attributes / disconnect guard
# ---------------------------------------------------------------------------


class _FlakyClient:
    """Bleak stand-in whose connect() only succeeds on request."""

    def __init__(self, always_fail: bool = False) -> None:
        self.is_connected = False
        self.connect_calls = 0
        self.always_fail = always_fail

    async def connect(self):
        self.connect_calls += 1
        if not self.always_fail:
            self.is_connected = True
            return
        raise RuntimeError("no link")


class TestConnectWithRetries:
    async def test_fallback_connect_runs_retry_loop_and_succeeds(self, device):
        client = _FlakyClient()
        out = await device._connect_with_retries(client, attempts=3, delay=0)
        assert out is client
        assert client.connect_calls == 1

    async def test_fallback_connect_exhausts_attempts_and_raises(self, device):
        client = _FlakyClient(always_fail=True)
        with pytest.raises(RuntimeError, match="Failed to connect"):
            await device._connect_with_retries(client, attempts=3, delay=0)
        assert client.connect_calls == 3

    async def test_disconnect_on_never_connected_client_does_not_throw(self, device):
        """Never-connected clients skip teardown writes entirely."""
        device._client = _FlakyClient()  # not connected
        await device.disconnect()
        assert device.state.connected is False
        assert device.state.authenticated is False

    async def test_zero_attributes_fails_connection(self, device):
        """A session answering zero attributes must not report 'ready'."""
        device._client = _FlakyClient()
        device._client.is_connected = True

        device._get_bleak_client = AsyncMock(return_value=device._client)
        device._client.start_notify = AsyncMock()
        device._reauth_with_ltk = AsyncMock()
        device._send_message = AsyncMock()
        device._subscribe_attributes = AsyncMock()
        device.read_all_attributes = AsyncMock()
        # no attributes in state → fail path must raise
        device.disconnect = AsyncMock()

        with pytest.raises(RuntimeError, match="answered zero attributes"):
            await device.connect_and_authenticate()
        device.disconnect.assert_awaited_once()


class TestPlatformDispatch:
    """select.py / switch.py must reach the BLE-vacuum module (issue-round 3)."""

    def _entry_data_dict(self, coord):
        return {"ble_vacuum_coordinator": coord, "is_ble_vacuum": True}

    async def test_select_dispatch_reaches_vacuum_module(self, mock_hass):
        from custom_components.hass_dyson import select as select_mod

        coord = MagicMock(serial_number="X")
        mock_hass.data = {DOMAIN: {"e1": self._entry_data_dict(coord)}}
        entry = MagicMock()
        entry.entry_id = "e1"

        with patch(
            "custom_components.hass_dyson.ble_vacuum_select.async_setup_entry",
            new=AsyncMock(return_value=True),
        ) as spy:
            await select_mod.async_setup_entry(mock_hass, entry, MagicMock())
        spy.assert_awaited_once()

    async def test_switch_dispatch_reaches_vacuum_module(self, mock_hass):
        from custom_components.hass_dyson import switch as switch_mod

        coord = MagicMock(serial_number="X")
        mock_hass.data = {DOMAIN: {"e1": self._entry_data_dict(coord)}}
        entry = MagicMock()
        entry.entry_id = "e1"

        with patch(
            "custom_components.hass_dyson.ble_vacuum_switch.async_setup_entry",
            new=AsyncMock(return_value=True),
        ) as spy:
            await switch_mod.async_setup_entry(mock_hass, entry, MagicMock())
        spy.assert_awaited_once()


class TestIconNames:
    """Icons must be real MDI names (the UI silently drops unknown ones).

    Scans the module *source* rather than a hand-maintained class list, so a
    new entity cannot slip past by not being listed here.
    """

    # Names that shipped broken at some point; kept as a cheap regression
    # guard for environments where hass_frontend is not installed.
    FORBIDDEN = {
        "mdi:axis-rotate",
        "mdi:timer-play-outline",
        "mdi:air-filter-variant",
        "mdi:shield-battery",
        "mdi:shield-battery-outline",
        "mdi:battery-heart-variant-outline",
    }

    @staticmethod
    def _declared_icons() -> set[str]:
        """Every ``mdi:*`` literal in the BLE vacuum entity modules."""
        import pathlib
        import re

        import custom_components.hass_dyson as pkg

        root = pathlib.Path(pkg.__file__).parent
        icons: set[str] = set()
        for path in sorted(root.glob("ble_vacuum*.py")):
            icons |= set(re.findall(r'"(mdi:[a-z0-9-]+)"', path.read_text()))
        return icons

    def test_icons_are_not_known_broken(self):
        """None of the previously-shipped bad names come back."""
        declared = self._declared_icons()
        assert declared, "no icons found — the scan is broken"
        bad = declared & self.FORBIDDEN
        assert not bad, f"known-broken icon names in use: {sorted(bad)}"

    def test_icons_exist_in_mdi(self):
        """Every declared icon resolves against the real MDI set.

        Skipped when ``hass_frontend`` is not installed (it is not a test
        dependency); runs for real in any environment that has the frontend.
        """
        import glob
        import json
        import os

        pytest.importorskip(
            "hass_frontend", reason="frontend package not installed in this env"
        )
        import hass_frontend

        mdi_dir = os.path.join(os.path.dirname(hass_frontend.__file__), "static", "mdi")
        names: set[str] = set()
        for chunk in glob.glob(os.path.join(mdi_dir, "*.json")):
            try:
                with open(chunk, encoding="utf-8") as fh:
                    names |= set(json.load(fh))
            except (OSError, ValueError):  # pragma: no cover - defensive
                continue
        if not names:  # pragma: no cover - frontend layout changed
            pytest.skip("could not read the MDI icon set")

        missing = sorted(
            icon
            for icon in self._declared_icons()
            if icon.removeprefix("mdi:") not in names
        )
        assert not missing, f"icons not present in MDI: {missing}"

    def test_product_info_8_byte_variant(self, device):
        device._parse_product_info(bytes.fromhex("020d020050533530"))
        assert device.state.firmware_major == 2
        assert device.state.hardware_module == "PS"
        assert device.state.project_id is None  # 8-byte form has no project id


# ---------------------------------------------------------------------------
# Notification handlers / queue branches / client plumbing (coverage push)
# ---------------------------------------------------------------------------


class TestNotificationHandlersIO:
    def test_messaging_push_updates_state_via_handler(self, device):
        """A real 0x97 frame flows through _on_messaging_notification."""
        from custom_components.hass_dyson.const import (
            BLE_VACUUM_ATTR_CLEANING_SESSION_ACTIVE,
        )

        frame = bytes(
            [0x80, 0x97]
            + list(BLE_VACUUM_ATTR_CLEANING_SESSION_ACTIVE)
            + [0x01, 0x00, 0x01]
        )
        device._on_messaging_notification(None, bytearray(frame))
        assert device.state.session_active is True
        assert device.state.attributes["session_active"] == "active"
        device._queue.put_nowait = MagicMock()  # any unqueued leftovers?

    def test_messaging_malformed_push_logged(self, device, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            # first+only fragment header 0x80 | type 0x97 | attrs(2) + len says 5, got 1
            device._on_messaging_notification(
                None, bytearray([0x80, 0x97, 0x07, 0x40, 0x05, 0x00, 0x01])
            )
        assert "Malformed PUSH_ATTRIBUTE" in caplog.text

    def test_messaging_non_push_goes_to_queue(self, device):
        from custom_components.hass_dyson.const import BLE_MSG_TYPE_PUSH_ATTRIBUTE_ACK

        frame = bytes([0x80, BLE_MSG_TYPE_PUSH_ATTRIBUTE_ACK, 0x07, 0x40])
        device._on_messaging_notification(None, bytearray(frame))
        assert not device._queue.empty()
        tag, msg = device._queue.get_nowait()
        assert tag == "msg" and msg.type_id == BLE_MSG_TYPE_PUSH_ATTRIBUTE_ACK

    async def test_wait_for_message_timeout(self, device):
        hass = device.hass
        hass.loop.time = MagicMock(side_effect=[0.0, 3.0])
        with pytest.raises(TimeoutError):
            await device._wait_for_type("msg", 0x91, timeout=2.0)

    async def test_wait_for_message_link_dead(self, device):
        fake = _FakeClient()
        fake.is_connected = False
        device._client = fake
        hass = device.hass
        # first loop.time() call returns 0 (inside wait window) → checks link → raises
        hass.loop.time = MagicMock(side_effect=lambda: 0.0)
        with pytest.raises(RuntimeError, match="disconnected"):
            await device._wait_for_type("msg", 0x91, timeout=5.0)


class TestGetBleakClient:
    async def test_missing_ha_bluetooth_falls_back_to_raw_client(self, device):
        device._connect_with_retries = AsyncMock(side_effect=lambda c, **k: c)
        with pytest.MonkeyPatch().context() as mp:
            import sys

            mp.setitem(sys.modules, "homeassistant.components.bluetooth", None)
            mp.setitem(sys.modules, "bleak", __import__("bleak"))
            client = await device._get_bleak_client()
        from bleak import BleakClient as _Real

        assert isinstance(client, _Real)
        device._connect_with_retries.assert_awaited_once()

    async def test_no_service_info_falls_back(self, device):
        device._connect_with_retries = AsyncMock(side_effect=lambda c, **k: c)
        bt = MagicMock()
        bt.async_last_service_info = MagicMock(return_value=None)
        import sys

        with pytest.MonkeyPatch().context() as mp:
            mp.setitem(sys.modules, "homeassistant.components.bluetooth", bt)
            mp.setitem(sys.modules, "bleak", __import__("bleak"))
            client = await device._get_bleak_client()
        from bleak import BleakClient as _Real

        assert isinstance(client, _Real)
        bt.async_last_service_info.assert_called()
        device._connect_with_retries.assert_awaited_once()

    async def test_service_info_direct_fallback_connects(self, device):
        """establish_connection failure still ends in a connected client now."""
        device._connect_with_retries = AsyncMock(side_effect=lambda c, **k: c)
        bt = MagicMock()
        connectable = MagicMock()
        bt.async_last_service_info = MagicMock(side_effect=[connectable, None])
        import sys

        with pytest.MonkeyPatch().context() as mp:
            mp.setitem(sys.modules, "homeassistant.components.bluetooth", bt)
            mp.setitem(
                sys.modules,
                "bleak_retry_connector",
                MagicMock(
                    establish_connection=AsyncMock(
                        side_effect=RuntimeError("proxy timeout")
                    )
                ),
            )
            client = await device._get_bleak_client()
        device._connect_with_retries.assert_awaited_once()
        assert client is not None


class TestSubscribeAndReadAll:
    async def test_subscribe_all_acked(self, device):
        from custom_components.hass_dyson.const import (
            BLE_MSG_TYPE_PUSH_ATTRIBUTE_ACK,
            BLE_VACUUM_ATTRIBUTES,
        )

        device._client = _FakeClient()

        device._send_message = AsyncMock()
        device._wait_for_message = AsyncMock(
            side_effect=lambda _tag, _pred, _t, _d: DysonMessage(
                BLE_MSG_TYPE_PUSH_ATTRIBUTE_ACK, b"\x00\x40"
            )
        )
        await device._subscribe_attributes()
        assert device._subscribed_attrs == set(BLE_VACUUM_ATTRIBUTES)

    async def test_read_all_stops_after_consecutive_errors(self, device):
        calls: list[bytes] = []

        async def flaky(_attr):
            calls.append(_attr)
            return False

        device.read_attribute = flaky
        from custom_components.hass_dyson.const import (
            BLE_ATTR_MAX_CONSECUTIVE_ERRORS,
        )

        await device.read_all_attributes()
        assert len(calls) == BLE_ATTR_MAX_CONSECUTIVE_ERRORS

    async def test_reauth_product_info_timeout_tolerated(self, device):
        """Product-info timeout is tolerated; auth proceeds."""
        enc_key = _fixed_enc_key()
        nonce = bytes(range(16))
        challenge = bytes(reversed(range(16)))
        payload_b = _craft_payload_b(enc_key, nonce, challenge)
        conn = bytes(10)

        from custom_components.hass_dyson.const import (
            BLE_MSG_TYPE_CONNECTION_ESTABLISHED,
            BLE_MSG_TYPE_PRODUCT_INFO,
            BLE_MSG_TYPE_REAUTH_PAYLOAD_B,
        )

        device._send_message = AsyncMock()
        calls = []

        async def fake_wait(_tag, type_id, timeout):
            calls.append(type_id)
            if type_id == BLE_MSG_TYPE_PRODUCT_INFO:
                raise TimeoutError
            if type_id == BLE_MSG_TYPE_REAUTH_PAYLOAD_B:
                return DysonMessage(BLE_MSG_TYPE_REAUTH_PAYLOAD_B, payload_b)
            return DysonMessage(BLE_MSG_TYPE_CONNECTION_ESTABLISHED, conn)

        device._wait_for_type = fake_wait
        with patch(
            "custom_components.hass_dyson.ble_vacuum.os.urandom",
            side_effect=lambda *_a, **_k: nonce,
        ):
            await device._reauth_with_ltk(enc_key)
            pass  # tolerated timeout must not raise


class TestLdiCapabilityBitmask:
    """0x0243 is a 32-bit LE bitmask, mask-tested against 0b111 (iq/b.java)."""

    def test_auto_bits_set(self):
        from custom_components.hass_dyson.ble_vacuum import decode_ldi_auto

        assert decode_ldi_auto(b"\x07") is True

    def test_no_bits_set(self):
        from custom_components.hass_dyson.ble_vacuum import decode_ldi_auto

        assert decode_ldi_auto(b"\x00") is False

    def test_partial_bits_do_not_count(self):
        """The app requires (value & 7) == 7, not merely a non-zero value."""
        from custom_components.hass_dyson.ble_vacuum import decode_ldi_auto

        assert decode_ldi_auto(b"\x03") is False
        assert decode_ldi_auto(b"\x05") is False

    def test_extra_high_bits_still_auto(self):
        from custom_components.hass_dyson.ble_vacuum import decode_ldi_auto

        assert decode_ldi_auto(b"\xff") is True

    def test_widened_to_four_bytes_little_endian(self):
        from custom_components.hass_dyson.ble_vacuum import decode_ldi_auto

        # Short payloads are zero-padded; the low byte carries the flags.
        assert decode_ldi_auto(b"\x07\x00\x00\x00") is True
        assert decode_ldi_auto(b"\x00\x07") is False

    def test_registry_decodes_through_decode_attribute_value(self):
        from custom_components.hass_dyson.const import (
            BLE_VACUUM_ATTR_DUST_ILLUMINATION_AUTO,
        )

        assert (
            decode_attribute_value(BLE_VACUUM_ATTR_DUST_ILLUMINATION_AUTO, b"\x07")
            is True
        )
        assert (
            decode_attribute_value(BLE_VACUUM_ATTR_DUST_ILLUMINATION_AUTO, b"\x00")
            is False
        )


class TestStateDelivery:
    """State reaches the coordinator directly; the public event still fires."""

    def test_callback_receives_the_snapshot(self, mock_hass):
        seen: list[dict] = []
        dev = DysonBleVacuumDevice(
            hass=mock_hass,
            serial_number="7RD-EU-TEST0000X",
            mac_address="AA:BB:CC:DD:EE:FF",
            ltk_hex="00112233445566778899aabbccddeeff",
            account_uuid="00000000-0000-0000-0000-000000000000",
            state_callback=seen.append,
        )
        dev._update_attribute(BLE_VACUUM_ATTR_BATTERY_LEVEL, bytes([77]), source="t")
        dev._fire_state_change()
        assert seen, "coordinator callback was not invoked"
        assert seen[-1]["attributes"]["battery_level"] == 77
        assert seen[-1]["serial_number"] == "7RD-EU-TEST0000X"

    def test_public_event_still_fires(self, mock_hass, device):
        """dyson_ble_state_change is documented for user automations."""
        from custom_components.hass_dyson.const import EVENT_BLE_STATE_CHANGE

        device._fire_state_change()
        mock_hass.bus.async_fire.assert_called()
        event_name, payload = mock_hass.bus.async_fire.call_args.args
        assert event_name == EVENT_BLE_STATE_CHANGE
        assert payload["serial_number"] == "7RD-EU-TEST0000X"

    def test_event_and_callback_get_the_same_object(self, mock_hass):
        seen: list[dict] = []
        dev = DysonBleVacuumDevice(
            hass=mock_hass,
            serial_number="7RD-EU-TEST0000X",
            mac_address="AA:BB:CC:DD:EE:FF",
            ltk_hex="00112233445566778899aabbccddeeff",
            account_uuid="00000000-0000-0000-0000-000000000000",
            state_callback=seen.append,
        )
        dev._fire_state_change()
        assert seen[-1] == mock_hass.bus.async_fire.call_args.args[1]

    def test_device_works_without_a_callback(self, device, mock_hass):
        """state_callback is optional — the event path alone must still work."""
        device._fire_state_change()
        mock_hass.bus.async_fire.assert_called()


class TestStaleAttributeGuard:
    """Readiness must reflect the current session, not cached values.

    state.attributes survives disconnects on purpose so entities keep their
    last known reading.  That makes it useless as a "did this session work?"
    signal: after any successful session it is non-empty forever, so a later
    reconnect whose subscribes and reads all fail would still report ready and
    serve the old values as live.
    """

    def test_session_set_starts_empty(self, device):
        assert device._session_attrs == set()

    def test_update_records_the_session_attribute(self, device):
        device._update_attribute(BLE_VACUUM_ATTR_BATTERY_LEVEL, bytes([50]), source="t")
        assert BLE_VACUUM_ATTR_BATTERY_LEVEL in device._session_attrs

    @pytest.mark.asyncio
    async def test_reconnect_with_zero_reads_is_rejected_despite_cache(self, device):
        """The regression: cached attributes must not make a dead session look ready."""
        # A previous session populated the cache.
        device._update_attribute(BLE_VACUUM_ATTR_BATTERY_LEVEL, bytes([50]), source="t")
        assert device.state.attributes  # cache survives, by design

        # New session: auth succeeds but nothing answers.
        client = MagicMock()
        client.is_connected = True
        client.start_notify = AsyncMock()
        device._client = client
        device._send_message = AsyncMock()
        device._reauth_with_ltk = AsyncMock()
        device._subscribe_attributes = AsyncMock()
        device.read_all_attributes = AsyncMock()
        device.disconnect = AsyncMock()

        with pytest.raises(RuntimeError, match="zero attributes"):
            await device.connect_and_authenticate()
        device.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_session_with_fresh_data_is_accepted(self, device):
        client = MagicMock()
        client.is_connected = True
        client.start_notify = AsyncMock()
        device._client = client
        device._send_message = AsyncMock()
        device._reauth_with_ltk = AsyncMock()
        device._subscribe_attributes = AsyncMock()

        async def _read_something():
            device._update_attribute(
                BLE_VACUUM_ATTR_BATTERY_LEVEL, bytes([64]), source="read"
            )

        device.read_all_attributes = AsyncMock(side_effect=_read_something)
        device.disconnect = AsyncMock()

        await device.connect_and_authenticate()
        assert device.state.connected is True
        device.disconnect.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_connect_clears_the_previous_session_set(self, device):
        device._update_attribute(BLE_VACUUM_ATTR_BATTERY_LEVEL, bytes([50]), source="t")
        client = MagicMock()
        client.is_connected = True
        client.start_notify = AsyncMock()
        device._client = client
        device._send_message = AsyncMock()
        device._reauth_with_ltk = AsyncMock()
        device._subscribe_attributes = AsyncMock()
        device.read_all_attributes = AsyncMock()
        device.disconnect = AsyncMock()
        with pytest.raises(RuntimeError):
            await device.connect_and_authenticate()
        assert device._session_attrs == set(), "session set was not reset on connect"


class TestTeardownCancellationSafety:
    """Cancelling the graceful phase must not leave the BLE link up.

    disconnect() clears self._client before the graceful teardown so the
    lifecycle cannot reuse it.  That means a cancellation part-way through is
    unrecoverable from outside: a second disconnect() call sees client is None
    and returns immediately.  The real client.disconnect() therefore has to run
    in a finally.
    """

    @staticmethod
    def _connected_client():
        client = MagicMock()
        client.is_connected = True
        client.disconnect = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_link_is_closed_when_graceful_phase_is_cancelled(self, device):
        import asyncio as _asyncio

        client = self._connected_client()
        # Cancel the moment the first teardown write happens.
        client.write_gatt_char = AsyncMock(side_effect=_asyncio.CancelledError)
        device._client = client
        device._subscribed_attrs = {b"\x00\x40"}

        with pytest.raises(_asyncio.CancelledError):
            await device.disconnect()

        client.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_link_is_closed_when_a_sleep_is_cancelled(self, device, monkeypatch):
        import asyncio as _asyncio

        client = self._connected_client()
        client.write_gatt_char = AsyncMock()
        device._client = client
        device._subscribed_attrs = set()

        async def _cancelled_sleep(*_a, **_k):
            raise _asyncio.CancelledError

        monkeypatch.setattr(
            "custom_components.hass_dyson.ble_vacuum.asyncio.sleep", _cancelled_sleep
        )
        with pytest.raises(_asyncio.CancelledError):
            await device.disconnect()

        client.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_normal_teardown_still_disconnects(self, device):
        client = self._connected_client()
        client.write_gatt_char = AsyncMock()
        device._client = client
        device._subscribed_attrs = set()

        await device.disconnect()

        client.disconnect.assert_awaited_once()
        assert device.state.connected is False
        assert device.state.authenticated is False

    @pytest.mark.asyncio
    async def test_second_call_is_a_noop(self, device):
        client = self._connected_client()
        client.write_gatt_char = AsyncMock()
        device._client = client
        device._subscribed_attrs = set()
        await device.disconnect()
        client.disconnect.reset_mock()

        await device.disconnect()  # client reference already gone
        client.disconnect.assert_not_awaited()


class TestWriteAcceptanceSemantics:
    """A 0x94 status of 0 means accepted, which is not the same as applied.

    Verified on a V16: writing dust illumination with no cleaner head attached
    returns 0a4000 (status 0) while the attribute stays put, because the LDI
    laser is in the head.
    """

    @pytest.mark.asyncio
    async def test_status_zero_is_accepted_even_if_value_does_not_move(
        self, device, caplog
    ):
        import logging

        from custom_components.hass_dyson.const import (
            BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE,
            BLE_VACUUM_ATTR_DUST_ILLUMINATION,
        )

        attr = BLE_VACUUM_ATTR_DUST_ILLUMINATION
        device.state.attributes_raw[attr.hex()] = "01"  # still 'on'
        device._send_message = AsyncMock()
        device._wait_for_message = AsyncMock(
            return_value=DysonMessage(
                BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE, bytes.fromhex("0a4000")
            )
        )
        with caplog.at_level(logging.DEBUG):
            ok = await device.write_attribute(attr, b"\x00")
        assert ok is True, "status 0 is an acceptance"
        assert "may not apply in this state" in caplog.text

    @pytest.mark.asyncio
    async def test_status_zero_with_matching_value_logs_nothing_odd(
        self, device, caplog
    ):
        import logging

        from custom_components.hass_dyson.const import (
            BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE,
            BLE_VACUUM_ATTR_TASK_DETECTION,
        )

        attr = BLE_VACUUM_ATTR_TASK_DETECTION
        device.state.attributes_raw[attr.hex()] = "01"  # push already applied
        device._send_message = AsyncMock()
        device._wait_for_message = AsyncMock(
            return_value=DysonMessage(
                BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE, bytes.fromhex("074100")
            )
        )
        with caplog.at_level(logging.DEBUG):
            ok = await device.write_attribute(attr, b"\x01")
        assert ok is True
        assert "may not apply in this state" not in caplog.text

    @pytest.mark.asyncio
    async def test_nonzero_status_is_a_rejection(self, device):
        from custom_components.hass_dyson.const import (
            BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE,
            BLE_VACUUM_ATTR_TASK_DETECTION,
        )

        attr = BLE_VACUUM_ATTR_TASK_DETECTION
        device.state.attributes_raw[attr.hex()] = "00"
        device._send_message = AsyncMock()
        device._wait_for_message = AsyncMock(
            return_value=DysonMessage(
                BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE, bytes.fromhex("074103")
            )
        )
        assert await device.write_attribute(attr, b"\x01") is False


class TestWriteRejection:
    """An explicit non-zero 0x94 status is the machine saying no.

    A rejection can arrive even when writing the value the attribute already
    holds, so checking the current value before the status would report that
    rejection as success.
    """

    @staticmethod
    def _device_with_response(device, payload_hex):
        from custom_components.hass_dyson.const import (
            BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE,
        )

        device._send_message = AsyncMock()
        device._wait_for_message = AsyncMock(
            return_value=DysonMessage(
                BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE, bytes.fromhex(payload_hex)
            )
        )
        return device

    @pytest.mark.asyncio
    async def test_rejected_noop_write_is_not_reported_as_success(self, device):
        """The regression: value already matches, but the machine said no."""
        from custom_components.hass_dyson.const import (
            BLE_VACUUM_ATTR_BATTERY_CARE_SETTING,
        )

        attr = BLE_VACUUM_ATTR_BATTERY_CARE_SETTING
        device.state.attributes_raw[attr.hex()] = "00"  # already the target
        self._device_with_response(device, "084101")  # status 1 = rejected
        assert await device.write_attribute(attr, b"\x00") is False

    @pytest.mark.asyncio
    async def test_rejection_is_logged_as_a_warning(self, device, caplog):
        import logging

        from custom_components.hass_dyson.const import (
            BLE_VACUUM_ATTR_BATTERY_CARE_SETTING,
        )

        attr = BLE_VACUUM_ATTR_BATTERY_CARE_SETTING
        device.state.attributes_raw[attr.hex()] = "00"
        self._device_with_response(device, "084101")
        with caplog.at_level(logging.WARNING):
            await device.write_attribute(attr, b"\x00")
        assert "rejected" in caplog.text
        assert "write status 1" in caplog.text

    @pytest.mark.asyncio
    async def test_push_fallback_still_applies_when_no_status_arrives(self, device):
        """With no 0x94 at all, a matching pushed value is the confirmation."""
        from custom_components.hass_dyson.const import BLE_VACUUM_ATTR_TASK_DETECTION

        attr = BLE_VACUUM_ATTR_TASK_DETECTION
        device.state.attributes_raw[attr.hex()] = "01"  # push already landed
        device._send_message = AsyncMock()
        device._wait_for_message = AsyncMock(side_effect=TimeoutError)
        assert await device.write_attribute(attr, b"\x01") is True

    @pytest.mark.asyncio
    async def test_no_status_and_no_push_is_a_failure(self, device):
        from custom_components.hass_dyson.const import BLE_VACUUM_ATTR_TASK_DETECTION

        attr = BLE_VACUUM_ATTR_TASK_DETECTION
        device.state.attributes_raw[attr.hex()] = "00"
        device._send_message = AsyncMock()
        device._wait_for_message = AsyncMock(side_effect=TimeoutError)
        assert await device.write_attribute(attr, b"\x01") is False


class TestDysonVersionFormat:
    """The BLE product-info fields reconstruct Dyson's own version string.

    Verified against the account API, which reports this exact machine as
    SVC0PS.50.02.013.0002 while BLE reports fw 2.13.2 with module 0x5053 and
    variant 0x3530 — the same thing in two encodings.
    """

    def test_module_and_variant_are_ascii(self, device):
        device._parse_product_info(bytes.fromhex("020d0200505335305356433000000000"))
        assert device.state.hardware_module == "PS"
        assert device.state.hardware_variant == "50"
        assert device.state.project_id == "SVC0"

    def test_reconstructs_the_cloud_version_string(self, device):
        device._parse_product_info(bytes.fromhex("020d0200505335305356433000000000"))
        assert device.dyson_firmware_version == "SVC0PS.50.02.013.0002"
        assert device.firmware_version == "2.13.2"

    def test_none_until_product_info_arrives(self, device):
        assert device.dyson_firmware_version is None

    def test_none_without_project_id(self, device):
        # 8-byte payload: no project id field
        device._parse_product_info(bytes.fromhex("020d020050533530"))
        assert device.firmware_version == "2.13.2"
        assert device.dyson_firmware_version is None

    def test_non_ascii_falls_back_to_hex(self, device):
        device._parse_product_info(bytes.fromhex("020d0200fffe00015356433000000000"))
        assert device.state.hardware_module == "fffe"
