"""Unit tests for ble_device.py — DysonBLEDevice and supporting utilities."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hass_dyson.ble_device import (
    DysonBLEDevice,
    DysonFragmentAssembler,
    build_reauth_payload_a,
    build_reauth_payload_c,
    fragment_dyson_message,
    g20c_encrypt,
    ha_to_raw_brightness,
    hkdf_derive_aes_key,
    kelvin_to_mired,
    mired_to_kelvin,
    raw_to_ha_brightness,
)
from custom_components.hass_dyson.const import (
    EVENT_BLE_STATE_CHANGE,
)

# ── Fragment assembler ────────────────────────────────────────────────────────


class TestDysonFragmentAssembler:
    """Tests for DysonFragmentAssembler."""

    def test_single_fragment_message(self):
        """A single fragment carries 0x80|0 as header and assembles immediately."""
        asm = DysonFragmentAssembler()
        # header=0x80 (first+only), type=0x01, payload=[0xAA, 0xBB]
        fragment = bytes([0x80, 0x01, 0xAA, 0xBB])
        msg = asm.feed(fragment)
        assert msg is not None
        assert msg.type_id == 0x01
        assert msg.payload == bytes([0xAA, 0xBB])

    def test_two_fragment_message(self):
        """Two-fragment messages are reassembled correctly."""
        asm = DysonFragmentAssembler()
        # Fragment 1: header=0x81 (first,2 total), type=0x06, data=[0x01]
        f1 = bytes([0x81, 0x06, 0x01])
        result = asm.feed(f1)
        assert result is None, "Should not return before second fragment"
        # Fragment 2: header=0x01 (index 1), data=[0x02, 0x03]
        f2 = bytes([0x01, 0x02, 0x03])
        result = asm.feed(f2)
        assert result is not None
        assert result.type_id == 0x06
        assert result.payload == bytes([0x01, 0x02, 0x03])

    def test_reset_on_new_first_fragment(self):
        """Receiving a new first fragment mid-stream resets state."""
        asm = DysonFragmentAssembler()
        # Partial 3-fragment message
        asm.feed(bytes([0x82, 0x05, 0xAA]))  # first of 3
        asm.feed(bytes([0x01, 0xBB]))  # second of 3
        # New first fragment interrupts
        result = asm.feed(bytes([0x80, 0x07, 0xCC]))
        assert result is not None
        assert result.type_id == 0x07
        assert result.payload == bytes([0xCC])

    def test_empty_fragment_returns_none(self):
        """Empty bytes yield None without raising."""
        asm = DysonFragmentAssembler()
        assert asm.feed(b"") is None

    def test_first_fragment_too_short_raises(self):
        """A 1-byte first fragment raises ValueError."""
        asm = DysonFragmentAssembler()
        with pytest.raises(ValueError):
            asm.feed(bytes([0x80]))

    def test_orphan_continuation_fragment_returns_none(self):
        """Continuation fragment without a preceding first fragment returns None."""
        asm = DysonFragmentAssembler()
        assert asm.feed(bytes([0x01, 0xAA])) is None


# ── Fragment builder ──────────────────────────────────────────────────────────


class TestFragmentDysonMessage:
    """Tests for fragment_dyson_message."""

    def test_short_payload_fits_single_fragment(self):
        """Short message produces one fragment."""
        frags = fragment_dyson_message(0x01, bytes(5), capacity=20)
        assert len(frags) == 1
        assert frags[0][0] == 0x80  # first+only; 0 more follow
        assert frags[0][1] == 0x01  # type id

    def test_long_payload_is_split(self):
        """Payload spanning 3 frames is split correctly."""
        # capacity=10 → 9 data bytes per frame
        # type+payload = 1 + 20 = 21 bytes → ceil(21/9) = 3 fragments
        frags = fragment_dyson_message(0x06, bytes(20), capacity=10)
        assert len(frags) == 3
        # First fragment header: 0x80 | (3-1) = 0x82
        assert frags[0][0] == 0x82
        # Second fragment header: index=1
        assert frags[1][0] == 0x01
        # Third fragment header: index=2
        assert frags[2][0] == 0x02

    def test_roundtrip_with_assembler(self):
        """Fragment then reassemble yields original message."""
        payload = bytes(range(50))
        frags = fragment_dyson_message(0x08, payload, capacity=20)
        asm = DysonFragmentAssembler()
        result = None
        for f in frags:
            result = asm.feed(f)
        assert result is not None
        assert result.type_id == 0x08
        assert result.payload == payload

    def test_invalid_capacity_raises(self):
        """Capacity < 2 raises ValueError."""
        with pytest.raises(ValueError, match="capacity"):
            fragment_dyson_message(0x01, b"\x00", capacity=1)


# ── Cryptography ──────────────────────────────────────────────────────────────


class TestHKDFDeriveAESKey:
    """Tests for hkdf_derive_aes_key."""

    def test_returns_sixteen_bytes(self):
        """Derived key is always 16 bytes."""
        ltk = b"\xde\xad\xbe\xef" * 8
        key = hkdf_derive_aes_key(ltk)
        assert isinstance(key, bytes)
        assert len(key) == 16

    def test_deterministic(self):
        """Same LTK always produces same key."""
        ltk = os.urandom(32)
        assert hkdf_derive_aes_key(ltk) == hkdf_derive_aes_key(ltk)

    def test_different_ltks_different_keys(self):
        """Different LTKs produce different keys."""
        key1 = hkdf_derive_aes_key(b"\x00" * 16)
        key2 = hkdf_derive_aes_key(b"\xff" * 16)
        assert key1 != key2

    def test_matches_expected_derivation(self):
        """Manual HKDF derivation matches function output."""
        from custom_components.hass_dyson.const import BLE_HKDF_INFO

        ltk = b"\x01\x02\x03\x04" * 4
        prk = hmac.new(b"", ltk, hashlib.sha256).digest()
        expected = hmac.new(prk, BLE_HKDF_INFO + b"\x01", hashlib.sha256).digest()[:16]
        assert hkdf_derive_aes_key(ltk) == expected


class TestG20CEncrypt:
    """Tests for the g20c Encrypt-then-MAC scheme."""

    def test_output_is_64_bytes(self):
        """g20c output for 16-byte plaintext is always 64 bytes."""
        key = os.urandom(16)
        pt = os.urandom(16)
        ct = g20c_encrypt(key, pt)
        assert len(ct) == 64

    def test_output_is_nondeterministic(self):
        """Two calls with the same key/plaintext produce different outputs (random IV)."""
        key = os.urandom(16)
        pt = os.urandom(16)
        assert g20c_encrypt(key, pt) != g20c_encrypt(key, pt)

    def test_structure_iv_ct_mac(self):
        """Output has correct IV(16) + CT(16) + MAC(32) structure."""
        key = os.urandom(16)
        out = g20c_encrypt(key, b"\x00" * 16)
        iv = out[:16]
        ct = out[16:32]
        mac = out[32:]
        assert len(iv) == 16
        assert len(ct) == 16
        assert len(mac) == 32
        # Verify MAC matches
        expected_mac = hmac.new(key, ct, hashlib.sha256).digest()
        assert mac == expected_mac


class TestBuildReauthPayloads:
    """Tests for PayloadA and PayloadC builders."""

    ACCOUNT_UUID = "12345678-1234-1234-1234-123456789abc"

    def test_payload_a_is_82_bytes(self):
        """PayloadA is always 82 bytes."""
        key = os.urandom(16)
        nonce = os.urandom(16)
        pa = build_reauth_payload_a(self.ACCOUNT_UUID, key, nonce)
        assert len(pa) == 82

    def test_payload_a_starts_with_uuid_and_padding(self):
        """PayloadA begins with UUID bytes followed by two zero bytes."""
        import uuid as _uuid

        key = os.urandom(16)
        nonce = os.urandom(16)
        pa = build_reauth_payload_a(self.ACCOUNT_UUID, key, nonce)
        assert pa[:16] == _uuid.UUID(self.ACCOUNT_UUID).bytes
        assert pa[16:18] == b"\x00\x00"

    def test_payload_c_is_66_bytes(self):
        """PayloadC is always 66 bytes."""
        key = os.urandom(16)
        challenge = os.urandom(16)
        pc = build_reauth_payload_c(key, challenge)
        assert len(pc) == 66

    def test_payload_c_starts_with_padding(self):
        """PayloadC starts with two zero padding bytes."""
        key = os.urandom(16)
        pc = build_reauth_payload_c(key, os.urandom(16))
        assert pc[:2] == b"\x00\x00"


# ── Scaling ───────────────────────────────────────────────────────────────────


class TestBrightnessScaling:
    """Tests for ha_to_raw_brightness / raw_to_ha_brightness."""

    @pytest.mark.parametrize(
        "ha, expected_raw",
        [
            (0, 1),  # minimum raw is always 1
            (128, 50),  # ~50 %
            (255, 100),  # 100 %
            (2, 1),  # rounds to 1
        ],
    )
    def test_ha_to_raw(self, ha, expected_raw):
        assert ha_to_raw_brightness(ha) == expected_raw

    @pytest.mark.parametrize(
        "raw, expected_ha",
        [
            (0, 0),
            (50, 128),  # approximately 128
            (100, 255),
        ],
    )
    def test_raw_to_ha(self, raw, expected_ha):
        assert abs(raw_to_ha_brightness(raw) - expected_ha) <= 1

    def test_ha_to_raw_negative_clamps(self):
        assert ha_to_raw_brightness(-5) == 1

    def test_ha_to_raw_over_255_clamps(self):
        assert ha_to_raw_brightness(300) == 100


class TestColorTempScaling:
    """Tests for kelvin_to_mired / mired_to_kelvin."""

    def test_kelvin_to_mired_2700(self):
        assert kelvin_to_mired(2700) == 370

    def test_kelvin_to_mired_6500(self):
        assert kelvin_to_mired(6500) == 154

    def test_mired_to_kelvin_clamps_low(self):
        """Very high mired (low kelvin) clamps to BLE_MIN_KELVIN."""
        from custom_components.hass_dyson.const import BLE_MIN_KELVIN

        result = mired_to_kelvin(1000)  # would be 1000 K → below min
        assert result == BLE_MIN_KELVIN

    def test_mired_to_kelvin_clamps_high(self):
        """Very low mired (high kelvin) clamps to BLE_MAX_KELVIN."""
        from custom_components.hass_dyson.const import BLE_MAX_KELVIN

        result = mired_to_kelvin(50)  # would be 20000 K → above max
        assert result == BLE_MAX_KELVIN

    def test_roundtrip_kelvin(self):
        """kelvin → mired → kelvin stays within 50 K of original."""
        for k in [2700, 3000, 4000, 5000, 6500]:
            assert abs(mired_to_kelvin(kelvin_to_mired(k)) - k) <= 50


# ── DysonBLEDevice ────────────────────────────────────────────────────────────


class TestDysonBLEDevice:
    """Tests for DysonBLEDevice methods (without real BLE hardware)."""

    SERIAL = "CD06-GB-HAA0001A"
    MAC = "AA:BB:CC:DD:EE:FF"
    LTK_HEX = "deadbeefdeadbeefdeadbeefdeadbeef"
    ACCOUNT_UUID = "12345678-1234-1234-1234-123456789abc"

    def _make_device(self, hass=None):
        """Construct a DysonBLEDevice with a mock hass."""
        if hass is None:
            hass = MagicMock()
            hass.bus = MagicMock()
            hass.bus.async_fire = MagicMock()
            hass.loop = asyncio.new_event_loop()
        return DysonBLEDevice(
            hass=hass,
            serial_number=self.SERIAL,
            mac_address=self.MAC,
            ltk_hex=self.LTK_HEX,
            account_uuid=self.ACCOUNT_UUID,
        )

    def test_init_default_state(self):
        """Device initialises with disconnected state."""
        dev = self._make_device()
        assert dev.serial_number == self.SERIAL
        assert dev.mac_address == "AA:BB:CC:DD:EE:FF"
        assert dev.state.connected is False
        assert dev.is_connected is False

    def test_is_connected_false_when_no_client(self):
        """is_connected returns False when _client is None."""
        dev = self._make_device()
        assert dev.is_connected is False

    def test_is_connected_false_when_not_authenticated(self):
        """is_connected returns False even with a mock client if not authenticated."""
        dev = self._make_device()
        client = MagicMock()
        client.is_connected = True
        dev._client = client
        dev.state.authenticated = False
        assert dev.is_connected is False

    def test_is_connected_true_when_client_authenticated(self):
        """is_connected returns True when client connected and authenticated."""
        dev = self._make_device()
        client = MagicMock()
        client.is_connected = True
        dev._client = client
        dev.state.authenticated = True
        assert dev.is_connected is True

    def test_fire_state_change_calls_bus(self):
        """_fire_state_change fires EVENT_BLE_STATE_CHANGE on the event bus."""
        hass = MagicMock()
        hass.bus = MagicMock()
        hass.bus.async_fire = MagicMock()
        dev = self._make_device(hass)
        dev._fire_state_change()
        hass.bus.async_fire.assert_called_once()
        call_args = hass.bus.async_fire.call_args
        assert call_args[0][0] == EVENT_BLE_STATE_CHANGE
        data = call_args[0][1]
        assert data["serial_number"] == self.SERIAL

    @pytest.mark.asyncio
    async def test_set_power_raises_when_not_connected(self):
        """set_power raises RuntimeError when device is not connected."""
        dev = self._make_device()
        with pytest.raises(RuntimeError):
            await dev.set_power(True)

    @pytest.mark.asyncio
    async def test_set_brightness_raises_when_not_connected(self):
        """set_brightness raises RuntimeError when device is not connected."""
        dev = self._make_device()
        with pytest.raises(RuntimeError):
            await dev.set_brightness(128)

    @pytest.mark.asyncio
    async def test_set_color_temp_kelvin_raises_when_not_connected(self):
        """set_color_temp_kelvin raises RuntimeError when device is not connected."""
        dev = self._make_device()
        with pytest.raises(RuntimeError):
            await dev.set_color_temp_kelvin(4000)

    @pytest.mark.asyncio
    async def test_set_power_writes_gatt_char(self):
        """set_power writes the correct byte to BLE_POWER_UUID."""
        from custom_components.hass_dyson.const import BLE_POWER_UUID

        dev = self._make_device()
        client = MagicMock()
        client.is_connected = True
        client.write_gatt_char = AsyncMock()
        client.read_gatt_char = AsyncMock(return_value=bytearray([0x01]))
        dev._client = client
        dev.state.authenticated = True
        dev.state.connected = True

        await dev.set_power(True)
        client.write_gatt_char.assert_any_call(BLE_POWER_UUID, b"\x01", response=False)

    @pytest.mark.asyncio
    async def test_set_power_off_writes_zero(self):
        """set_power(False) writes 0x00 to BLE_POWER_UUID."""
        from custom_components.hass_dyson.const import BLE_POWER_UUID

        dev = self._make_device()
        client = MagicMock()
        client.is_connected = True
        client.write_gatt_char = AsyncMock()
        client.read_gatt_char = AsyncMock(return_value=bytearray([0x00]))
        dev._client = client
        dev.state.authenticated = True
        dev.state.connected = True

        await dev.set_power(False)
        client.write_gatt_char.assert_any_call(BLE_POWER_UUID, b"\x00", response=False)

    @pytest.mark.asyncio
    async def test_set_brightness_writes_raw_byte(self):
        """set_brightness converts HA scale and writes to BLE_BRIGHTNESS_UUID."""
        from custom_components.hass_dyson.const import BLE_BRIGHTNESS_UUID

        dev = self._make_device()
        client = MagicMock()
        client.is_connected = True
        client.write_gatt_char = AsyncMock()
        client.read_gatt_char = AsyncMock(return_value=bytearray([75]))
        dev._client = client
        dev.state.authenticated = True
        dev.state.connected = True

        await dev.set_brightness(191)  # ~75% raw
        client.write_gatt_char.assert_any_call(
            BLE_BRIGHTNESS_UUID, bytes([75]), response=False
        )

    @pytest.mark.asyncio
    async def test_set_color_temp_kelvin_clamps_and_writes(self):
        """set_color_temp_kelvin clamps to 2700-6500 and writes little-endian."""
        from custom_components.hass_dyson.const import BLE_COLOR_TEMP_UUID

        dev = self._make_device()
        client = MagicMock()
        client.is_connected = True
        client.write_gatt_char = AsyncMock()
        client.read_gatt_char = AsyncMock(
            return_value=bytearray(b"\xa0\x0f")
        )  # 4000 K LE
        dev._client = client
        dev.state.authenticated = True
        dev.state.connected = True

        await dev.set_color_temp_kelvin(4000)
        client.write_gatt_char.assert_any_call(
            BLE_COLOR_TEMP_UUID,
            (4000).to_bytes(2, byteorder="little"),
            response=False,
        )

    @pytest.mark.asyncio
    async def test_set_color_temp_kelvin_clamps_below_min(self):
        """Values below 2700 K are clamped to 2700 K."""
        from custom_components.hass_dyson.const import (
            BLE_COLOR_TEMP_UUID,
            BLE_MIN_KELVIN,
        )

        dev = self._make_device()
        client = MagicMock()
        client.is_connected = True
        client.write_gatt_char = AsyncMock()
        client.read_gatt_char = AsyncMock(return_value=bytearray(b"\x8c\x0a"))
        dev._client = client
        dev.state.authenticated = True
        dev.state.connected = True

        await dev.set_color_temp_kelvin(1000)
        client.write_gatt_char.assert_any_call(
            BLE_COLOR_TEMP_UUID,
            BLE_MIN_KELVIN.to_bytes(2, byteorder="little"),
            response=False,
        )

    def test_on_motion_notification_sets_motion_detected(self):
        """Motion notification handler sets motion_detected appropriately."""
        hass = MagicMock()
        hass.bus.async_fire = MagicMock()
        dev = self._make_device(hass)
        # Non-zero bytes → motion detected
        dev._on_motion_notification(None, bytearray([0x01]))
        assert dev.state.motion_detected is True
        # All-zero bytes → no motion
        dev._on_motion_notification(None, bytearray([0x00]))
        assert dev.state.motion_detected is False

    def test_device_info_structure(self):
        """device_info dict has required HA device registry keys."""
        dev = self._make_device()
        info = dev.device_info
        assert "identifiers" in info
        assert "name" in info
        assert "manufacturer" in info
        assert info["manufacturer"] == "Dyson"


class TestDysonBLEDeviceReauth:
    """Tests for the LTK re-auth flow (mocked GATT)."""

    SERIAL = "CD06-GB-HAA0001A"

    @pytest.mark.asyncio
    async def test_parse_product_info_short_payload_is_safe(self):
        """Too-short product info payload does not crash."""
        hass = MagicMock()
        hass.bus.async_fire = MagicMock()
        dev = DysonBLEDevice(
            hass=hass,
            serial_number=self.SERIAL,
            mac_address="AA:BB:CC:DD:EE:FF",
            ltk_hex="deadbeefdeadbeefdeadbeefdeadbeef",
            account_uuid="12345678-1234-1234-1234-123456789abc",
        )
        dev._parse_product_info(b"\x01\x02")  # Short — should not raise
        assert dev.state.firmware_major is None

    @pytest.mark.asyncio
    async def test_parse_product_info_valid_payload(self):
        """Valid product info payload populates firmware fields."""
        hass = MagicMock()
        hass.bus.async_fire = MagicMock()
        dev = DysonBLEDevice(
            hass=hass,
            serial_number=self.SERIAL,
            mac_address="AA:BB:CC:DD:EE:FF",
            ltk_hex="deadbeefdeadbeefdeadbeefdeadbeef",
            account_uuid="12345678-1234-1234-1234-123456789abc",
        )
        payload = bytes([3, 2, 0x00, 0xFF, 0x01, 0x02, 0x03, 0x04])
        dev._parse_product_info(payload)
        assert dev.state.firmware_major == 3
        assert dev.state.firmware_minor == 2
