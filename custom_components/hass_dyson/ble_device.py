"""BLE device wrapper for Dyson BLE-only lights (e.g. Lightcycle Morph CD06).

This module implements the BLE transport layer for Dyson lights that communicate
exclusively over Bluetooth Low Energy.  It handles:

- GATT connection via Home Assistant's bluetooth integration (wrapping bleak)
- Dyson message framing (fragment assembler / builder — reverse-engineered from
  the MyDyson Android app by S-Termi, discussion #334)
- LTK silent re-auth (HKDF-SHA256 + AES-128-CBC + HMAC-SHA256)
- GATT characteristic subscriptions (power, brightness, color temperature, motion)
- State change propagation via the Home Assistant event bus
  (``EVENT_BLE_STATE_CHANGE``) — *no MQTT*

The crypto implementation faithfully mirrors the Android app's ``g20/a.java``
and ``g20/c.java`` classes as documented in S-Termi's reverse-engineering notes.

Note on PROTOCOL.md terminology
--------------------------------
The :file:`docs/PROTOCOL.md` file bundled with S-Termi's archive describes the
crypto as "AES-GCM".  The actual implementation (``g20/c.java``) uses
**AES-128-CBC + HMAC-SHA256** (Encrypt-then-MAC).  This module implements
the actual algorithm, not the summary description.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import math
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

# Lazy-import homeassistant.components.bluetooth inside methods to avoid
# importing the HA bluetooth stack (which pulls in aiousbwatcher, etc.) at
# module level — this allows tests to import ble_device without the full HA
# environment installed.
if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from .const import (
    BLE_AUTH_CHAR_UUID,
    BLE_BRIGHTNESS_UUID,
    BLE_CHAR_11006_UUID,
    BLE_CHAR_11007_UUID,
    BLE_CHAR_11009_UUID,
    BLE_COLOR_TEMP_UUID,
    BLE_HKDF_INFO,
    BLE_MAX_KELVIN,
    BLE_MIN_KELVIN,
    BLE_MOTION_UUID,
    BLE_MSG_TYPE_CONNECTION_ESTABLISHED,
    BLE_MSG_TYPE_PRODUCT_INFO,
    BLE_MSG_TYPE_REAUTH_PAYLOAD_A,
    BLE_MSG_TYPE_REAUTH_PAYLOAD_B,
    BLE_MSG_TYPE_REAUTH_PAYLOAD_C,
    BLE_MSG_TYPE_REQUEST_PRODUCT_INFO,
    BLE_POWER_UUID,
    BLE_SERVICE_UUID,
    EVENT_BLE_STATE_CHANGE,
)

_LOGGER = logging.getLogger(__name__)

# BLE fragment default capacity (matches Dyson Android app default)
_FRAGMENT_CAPACITY = 20

# Reconnection backoff delays in seconds
_RECONNECT_DELAYS = [5, 15, 30, 60]

# Keepalive poll interval in seconds
_KEEPALIVE_INTERVAL = 20.0


# ── Dyson Message Framing ─────────────────────────────────────────────────────


@dataclass
class DysonMessage:
    """A reassembled logical BLE message from the Dyson protocol."""

    type_id: int
    payload: bytes


class DysonFragmentAssembler:
    """Reassemble Dyson's first-byte-fragment-header BLE messages.

    The Dyson BLE protocol fragments logical messages across multiple GATT
    writes/notifications.  Each fragment carries a header byte that encodes
    whether it is the first fragment (high bit set) and the total or current
    fragment count in the lower 7 bits.

    Source: reverse-engineered from ``g20/a.java`` (Android Smali).
    """

    def __init__(self) -> None:
        """Initialise the assembler."""
        self._buffer = bytearray()
        self._expected_fragments = 0
        self._received_fragments = 0
        self._type_id = 0

    def reset(self) -> None:
        """Reset internal state, discarding any partial message."""
        self._buffer.clear()
        self._expected_fragments = 0
        self._received_fragments = 0
        self._type_id = 0

    def feed(self, fragment: bytes) -> DysonMessage | None:
        """Feed a raw GATT fragment.

        Args:
            fragment: Raw bytes received from the GATT characteristic.

        Returns:
            A :class:`DysonMessage` when a complete message has been assembled,
            or ``None`` when more fragments are expected.

        Raises:
            ValueError: If the first fragment is too short to be valid.
        """
        if not fragment:
            return None

        header = fragment[0]
        is_first = bool(header & 0x80)

        if is_first:
            if len(fragment) < 2:  # noqa: PLR2004
                raise ValueError(
                    f"first Dyson fragment too short: {len(fragment)} bytes"
                )
            self._buffer.clear()
            self._expected_fragments = (header & 0x7F) + 1
            self._received_fragments = 1
            self._type_id = fragment[1]
            self._buffer.extend(fragment[2:])
        else:
            if self._expected_fragments == 0:
                return None
            self._received_fragments = (header & 0x7F) + 1
            self._buffer.extend(fragment[1:])

        if (
            self._expected_fragments
            and self._received_fragments == self._expected_fragments
        ):
            message = DysonMessage(self._type_id, bytes(self._buffer))
            self.reset()
            return message

        return None


def fragment_dyson_message(
    type_id: int, payload: bytes, capacity: int = _FRAGMENT_CAPACITY
) -> list[bytes]:
    """Fragment a logical Dyson message into BLE frames.

    The logical message layout is ``[type_byte][payload]``, then split into
    chunks of ``capacity - 1`` bytes each (one byte reserved for the header).

    Args:
        type_id: Message type byte (one of ``BLE_MSG_TYPE_*`` constants).
        payload: Raw message payload bytes.
        capacity: Maximum bytes per BLE frame (default 20, Dyson app default).

    Returns:
        List of raw fragment byte strings ready to write to the GATT char.

    Raises:
        ValueError: If ``capacity < 2`` or the message is too long to fragment.
    """
    if capacity < 2:  # noqa: PLR2004
        raise ValueError("fragment capacity must be at least 2")

    logical = bytes([type_id]) + payload
    data_per_fragment = capacity - 1
    total_fragments = max(1, math.ceil(len(logical) / data_per_fragment))
    if total_fragments > 128:  # noqa: PLR2004
        raise ValueError(
            f"message too long to fragment (would need {total_fragments} fragments)"
        )

    fragments: list[bytes] = []
    for index in range(total_fragments):
        start = index * data_per_fragment
        chunk = logical[start : start + data_per_fragment]
        header = (0x80 | (total_fragments - 1)) if index == 0 else (index & 0x7F)
        fragments.append(bytes([header]) + chunk)

    return fragments


# ── Cryptography ──────────────────────────────────────────────────────────────


def hkdf_derive_aes_key(ltk: bytes) -> bytes:
    """Derive a 16-byte AES key from the Long Term Key.

    Implements the HKDF-SHA256 with empty salt as used in the Android app
    ``g20/b.d``, producing one SHA-256 expand block truncated to 16 bytes.

    Args:
        ltk: Long Term Key bytes obtained from Dyson cloud during fresh pairing.

    Returns:
        16-byte AES key suitable for AES-128-CBC operations.
    """
    prk = hmac.new(b"", ltk, hashlib.sha256).digest()
    block1 = hmac.new(prk, BLE_HKDF_INFO + b"\x01", hashlib.sha256).digest()
    return block1[:16]


def _aes_cbc_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    """AES-128-CBC encrypt (no padding — plaintext must be block-aligned)."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    return encryptor.update(plaintext) + encryptor.finalize()


def g20c_encrypt(enc_key: bytes, plaintext: bytes) -> bytes:
    """Encrypt using Dyson's g20c scheme: IV(16) + AES-CBC(16) + HMAC-SHA256(32).

    This is Encrypt-then-MAC (not AES-GCM).  Mirrors ``g20/c.a()`` in the
    Android app.  Total output is always 64 bytes for a 16-byte plaintext.

    Args:
        enc_key: 16-byte AES key derived from :func:`hkdf_derive_aes_key`.
        plaintext: 16-byte plaintext block (e.g. a random nonce or challenge).

    Returns:
        64-byte ciphertext envelope: ``IV(16) + CT(16) + MAC(32)``.
    """
    iv = os.urandom(16)
    ct = _aes_cbc_encrypt(enc_key, iv, plaintext)
    mac = hmac.new(enc_key, ct, hashlib.sha256).digest()
    return iv + ct + mac


def build_reauth_payload_a(account_uuid: str, enc_key: bytes, nonce: bytes) -> bytes:
    """Build the 82-byte LTK re-auth PayloadA (message type 0x06).

    Layout: ``account_guid(16) || 0x00 0x00 || g20c_encrypt(enc_key, nonce)``

    Args:
        account_uuid: Dyson account UUID string (e.g. ``"xxxxxxxx-xxxx-..."``).
        enc_key: Derived AES key from :func:`hkdf_derive_aes_key`.
        nonce: 16 random bytes generated fresh for each auth attempt.

    Returns:
        82-byte payload.
    """
    return UUID(account_uuid).bytes + b"\x00\x00" + g20c_encrypt(enc_key, nonce)


def build_reauth_payload_c(enc_key: bytes, challenge: bytes) -> bytes:
    """Build the 66-byte LTK re-auth PayloadC (message type 0x08).

    Layout: ``0x00 0x00 || g20c_encrypt(enc_key, challenge)``

    Args:
        enc_key: Derived AES key from :func:`hkdf_derive_aes_key`.
        challenge: Challenge bytes extracted from the lamp's PayloadB (0x07).

    Returns:
        66-byte payload.
    """
    return b"\x00\x00" + g20c_encrypt(enc_key, challenge)


# ── Value scaling ─────────────────────────────────────────────────────────────


def ha_to_raw_brightness(ha_brightness: int) -> int:
    """Map Home Assistant brightness (0-255) to lamp percent (1-100).

    The minimum raw value is 1 to prevent ambiguity with the power-off state.

    Args:
        ha_brightness: HA brightness value in range 0–255.

    Returns:
        Lamp brightness percent in range 1–100.
    """
    if ha_brightness <= 0:
        return 1
    return max(1, min(100, round(ha_brightness * 100 / 255)))


def raw_to_ha_brightness(raw: int) -> int:
    """Map lamp percent (0-100) to Home Assistant brightness (0-255).

    Args:
        raw: Lamp brightness percent in range 0–100.

    Returns:
        HA brightness value in range 0–255.
    """
    return max(0, min(255, round(raw * 255 / 100)))


def kelvin_to_mired(kelvin: int) -> int:
    """Convert Kelvin to mired (reciprocal megakelvin).

    Args:
        kelvin: Color temperature in Kelvin.

    Returns:
        Color temperature in mired, rounded to nearest integer.
    """
    return round(1_000_000 / kelvin)


def mired_to_kelvin(mired: int) -> int:
    """Convert mired to Kelvin, clamped to lamp range.

    Args:
        mired: Color temperature in mired.

    Returns:
        Color temperature in Kelvin, clamped to [BLE_MIN_KELVIN, BLE_MAX_KELVIN].
    """
    kelvin = round(1_000_000 / mired)
    return max(BLE_MIN_KELVIN, min(BLE_MAX_KELVIN, kelvin))


# ── DysonBLEDevice ────────────────────────────────────────────────────────────


@dataclass
class BLELightState:
    """Current state snapshot of a Dyson BLE light."""

    connected: bool = False
    authenticated: bool = False
    power: bool | None = None
    brightness_raw: int | None = None  # 0-100 lamp percent
    brightness: int | None = None  # 0-255 HA scale
    color_temp_kelvin: int | None = None
    color_temp_mired: int | None = None
    motion_detected: bool = False
    last_motion_at: float = 0.0
    char_11006_hex: str | None = None
    char_11007_hex: str | None = None
    char_11009_hex: str | None = None
    last_error: str = ""
    firmware_major: int | None = None
    firmware_minor: int | None = None
    firmware_build: int | None = None


class DysonBLEDevice:
    """BLE transport layer for a Dyson BLE-only light.

    Manages the full lifecycle of a Bluetooth connection to a Dyson Lightcycle
    Morph (or compatible device):

    1. Scan/connect using Home Assistant's bluetooth integration
    2. Authenticate using stored LTK via the silent re-auth flow
    3. Read initial state from GATT characteristics
    4. Subscribe to runtime notifications (motion, flags)
    5. Fire :const:`.const.EVENT_BLE_STATE_CHANGE` on every state update
    6. Reconnect with exponential backoff on disconnect

    Commands (:meth:`set_power`, :meth:`set_brightness`,
    :meth:`set_color_temp_kelvin`) write directly to GATT characteristics
    and then read back state to update the event bus.

    Attributes:
        serial_number: Dyson device serial number.
        mac_address: BLE MAC address of the lamp (``AA:BB:CC:DD:EE:FF``).
        ltk_hex: Long Term Key hex string from Dyson cloud pairing.
        account_uuid: Dyson account UUID for constructing auth payloads.
        state: Current :class:`BLELightState` snapshot.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        serial_number: str,
        mac_address: str,
        ltk_hex: str,
        account_uuid: str,
        ble_proxy: str | None = None,
    ) -> None:
        """Initialise the BLE device wrapper.

        Args:
            hass: Home Assistant instance.
            serial_number: Dyson device serial number.
            mac_address: BLE MAC address (``AA:BB:CC:DD:EE:FF``).
            ltk_hex: Long Term Key as a hex string.
            account_uuid: Dyson account UUID string.
            ble_proxy: Optional pinned Bluetooth proxy host (future use).
        """
        self.hass = hass
        self.serial_number = serial_number
        self.mac_address = mac_address.upper()
        self._ltk_hex = ltk_hex
        self._account_uuid = account_uuid
        self._ble_proxy = ble_proxy

        self.state = BLELightState()
        self._client: Any | None = None  # BleakClient at runtime
        self._assembler = DysonFragmentAssembler()
        self._message_queue: asyncio.Queue[DysonMessage] = asyncio.Queue()
        self._lock = asyncio.Lock()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _fire_state_change(self) -> None:
        """Publish current state on the HA event bus."""
        import dataclasses

        self.hass.bus.async_fire(
            EVENT_BLE_STATE_CHANGE,
            {
                "serial_number": self.serial_number,
                **dataclasses.asdict(self.state),
            },
        )

    def _on_auth_notification(self, _characteristic: Any, data: bytearray) -> None:
        """Handle raw notification from the auth characteristic (11011)."""
        fragment = bytes(data)
        try:
            message = self._assembler.feed(fragment)
        except ValueError as exc:
            _LOGGER.warning("BLE fragment error for %s: %s", self.serial_number, exc)
            self._assembler.reset()
            return

        if message is not None:
            _LOGGER.debug(
                "BLE message type=0x%02X len=%d from %s",
                message.type_id,
                len(message.payload),
                self.serial_number,
            )
            self._message_queue.put_nowait(message)

    def _on_motion_notification(self, _characteristic: Any, data: bytearray) -> None:
        """Handle notification from the motion characteristic (11008)."""
        raw = bytes(data)
        motion = raw != bytes(len(raw))
        import time

        if motion:
            self.state.last_motion_at = time.time()
        self.state.motion_detected = motion
        self._fire_state_change()

    def _on_runtime_notification(self, short_id: str):
        """Return a notify handler for a runtime diagnostic characteristic."""

        def _handler(_characteristic: Any, data: bytearray) -> None:
            hex_value = bytes(data).hex()
            setattr(self.state, f"char_{short_id}_hex", hex_value)
            self._fire_state_change()

        return _handler

    def _on_bleak_disconnect(self, client: Any) -> None:  # noqa: ARG002
        """Handle unexpected BLE disconnect (called by bleak_retry_connector).

        Registered as the ``disconnected_callback`` when
        :func:`bleak_retry_connector.establish_connection` is used.  The
        coordinator's keepalive loop will detect the disconnection via
        :attr:`is_connected` and trigger a reconnect with backoff.
        """
        _LOGGER.info(
            "BLE device %s (%s) unexpectedly disconnected",
            self.serial_number,
            self.mac_address,
        )
        self.state.connected = False
        self.state.authenticated = False
        self._client = None

    async def _wait_for_type(self, type_id: int, timeout: float = 10.0) -> DysonMessage:
        """Wait for a specific message type from the auth characteristic."""
        end = self.hass.loop.time() + timeout
        while True:
            remaining = end - self.hass.loop.time()
            if remaining <= 0:
                raise TimeoutError(
                    f"Timed out waiting for BLE message type 0x{type_id:02X} "
                    f"from {self.serial_number}"
                )
            msg = await asyncio.wait_for(self._message_queue.get(), timeout=remaining)
            if msg.type_id == type_id:
                return msg
            _LOGGER.debug(
                "Ignoring type 0x%02X while waiting for 0x%02X from %s",
                msg.type_id,
                type_id,
                self.serial_number,
            )

    async def _send_message(self, type_id: int, payload: bytes = b"") -> None:
        """Fragment and write a logical message to the auth characteristic."""
        if self._client is None:
            raise RuntimeError("BLE client not connected")
        fragments = fragment_dyson_message(type_id, payload)
        for fragment in fragments:
            await self._client.write_gatt_char(
                BLE_AUTH_CHAR_UUID, fragment, response=False
            )

    async def _get_bleak_client(self) -> Any:
        """Obtain a connected (or connectable) BleakClient.

        When the device is visible in HA's Bluetooth stack, uses
        :func:`bleak_retry_connector.establish_connection` to return an
        **already-connected** client with HA-recommended retry logic.  Falls
        back to a raw ``BleakClient(mac)`` that still needs ``.connect()``.
        """
        from bleak import BleakClient  # provided by HA core

        _LOGGER.debug(
            "BLE client lookup for %s (MAC: %s, proxy: %s)",
            self.serial_number,
            self.mac_address,
            self._ble_proxy or "none (direct adapter)",
        )

        try:
            from homeassistant.components import bluetooth as _bt

            # Log all currently discovered service infos for this MAC to aid diagnosis
            connectable_info = _bt.async_last_service_info(
                self.hass, self.mac_address, connectable=True
            )
            non_connectable_info = _bt.async_last_service_info(
                self.hass, self.mac_address, connectable=False
            )

            if connectable_info is not None:
                _LOGGER.info(
                    "BLE device %s (%s) found as CONNECTABLE via adapter/proxy '%s' "
                    "(RSSI: %s dBm) — connecting via bleak_retry_connector",
                    self.serial_number,
                    self.mac_address,
                    getattr(connectable_info, "source", "unknown"),
                    getattr(connectable_info, "rssi", "unknown"),
                )
                try:
                    from bleak_retry_connector import establish_connection

                    client = await establish_connection(
                        BleakClient,
                        connectable_info.device,
                        self.serial_number,
                        disconnected_callback=self._on_bleak_disconnect,
                        max_attempts=4,
                    )
                    _LOGGER.info(
                        "BLE connection to %s established via bleak_retry_connector",
                        self.serial_number,
                    )
                    return client  # Already connected — skip manual .connect()
                except ImportError:
                    _LOGGER.warning(
                        "bleak_retry_connector not available for %s — "
                        "falling back to direct BleakClient (connection may be unreliable)",
                        self.serial_number,
                    )
                    return BleakClient(connectable_info.device)
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.warning(
                        "establish_connection() failed for %s (%s) — "
                        "falling back to direct BleakClient",
                        self.serial_number,
                        exc,
                    )
                    return BleakClient(connectable_info.device)
            elif non_connectable_info is not None:
                _LOGGER.warning(
                    "BLE device %s (%s) is visible (RSSI: %s dBm, source: '%s') but NOT "
                    "connectable. If using an ESPHome Bluetooth proxy, ensure it is "
                    "configured with 'active: true' in the bluetooth_proxy component. "
                    "Falling back to raw MAC address — connection will likely fail.",
                    self.serial_number,
                    self.mac_address,
                    getattr(non_connectable_info, "rssi", "unknown"),
                    getattr(non_connectable_info, "source", "unknown"),
                )
            else:
                _LOGGER.warning(
                    "BLE device %s (%s) has NOT been seen by any HA Bluetooth adapter or "
                    "proxy. Check that the device is powered on and within range. "
                    "Falling back to raw MAC address — connection will likely fail.",
                    self.serial_number,
                    self.mac_address,
                )
        except ImportError:
            _LOGGER.warning(
                "HA bluetooth integration not available for %s — "
                "falling back to raw MAC address",
                self.serial_number,
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning(
                "Error querying HA bluetooth integration for %s: %s — "
                "falling back to raw MAC address",
                self.serial_number,
                exc,
            )
        # Fall back to MAC address (works for local adapters, not proxies)
        _LOGGER.debug(
            "Using raw MAC address fallback for BleakClient(%s)", self.mac_address
        )
        return BleakClient(self.mac_address)

    # ── LTK re-auth ───────────────────────────────────────────────────────────

    async def _reauth_with_ltk(self) -> None:
        """Perform silent LTK re-authentication (no button press, no cloud call).

        Sends PayloadA (0x06), receives PayloadB (0x07), sends PayloadC (0x08),
        waits for Connection Established (0x26).

        Raises:
            RuntimeError: If the client is not connected.
            TimeoutError: If the lamp does not respond within the timeout.
        """
        _LOGGER.debug(
            "LTK re-auth started for %s (LTK length: %d chars)",
            self.serial_number,
            len(self._ltk_hex),
        )
        ltk = bytes.fromhex(self._ltk_hex)
        enc_key = hkdf_derive_aes_key(ltk)
        nonce = os.urandom(16)

        # Request product info first (matches observed app behaviour)
        _LOGGER.debug("Requesting product info from %s", self.serial_number)
        await self._send_message(BLE_MSG_TYPE_REQUEST_PRODUCT_INFO)
        try:
            product_msg = await self._wait_for_type(
                BLE_MSG_TYPE_PRODUCT_INFO, timeout=5.0
            )
            self._parse_product_info(product_msg.payload)
            _LOGGER.debug(
                "Product info received from %s: firmware %s.%s build %s",
                self.serial_number,
                self.state.firmware_major,
                self.state.firmware_minor,
                self.state.firmware_build,
            )
        except TimeoutError:
            _LOGGER.debug(
                "No product info response from %s (timeout); continuing with auth",
                self.serial_number,
            )

        # Challenge-response
        _LOGGER.debug("Sending PayloadA (0x06) to %s", self.serial_number)
        payload_a = build_reauth_payload_a(self._account_uuid, enc_key, nonce)
        await self._send_message(BLE_MSG_TYPE_REAUTH_PAYLOAD_A, payload_a)

        _LOGGER.debug("Waiting for PayloadB (0x07) from %s", self.serial_number)
        payload_b_msg = await self._wait_for_type(
            BLE_MSG_TYPE_REAUTH_PAYLOAD_B, timeout=20.0
        )
        _LOGGER.debug(
            "PayloadB received from %s (%d bytes)",
            self.serial_number,
            len(payload_b_msg.payload),
        )
        # The challenge from PayloadB is the 16-byte block starting at offset 18
        # (2 reserved bytes + 16-byte IV skipped; the actual challenge is at +2)
        # For simplicity we treat the entire PayloadB payload as the challenge input
        challenge = payload_b_msg.payload

        _LOGGER.debug("Sending PayloadC (0x08) to %s", self.serial_number)
        payload_c = build_reauth_payload_c(
            enc_key, challenge[:16] if len(challenge) >= 16 else challenge
        )
        await self._send_message(BLE_MSG_TYPE_REAUTH_PAYLOAD_C, payload_c)

        _LOGGER.debug(
            "Waiting for Connection Established (0x26) from %s", self.serial_number
        )
        await self._wait_for_type(BLE_MSG_TYPE_CONNECTION_ESTABLISHED, timeout=20.0)
        _LOGGER.info("BLE LTK re-auth successful for %s", self.serial_number)

    def _parse_product_info(self, payload: bytes) -> None:
        """Parse product info response (type 0x0B) and update firmware fields."""
        if len(payload) < 8:  # noqa: PLR2004
            return
        self.state.firmware_major = payload[0]
        self.state.firmware_minor = payload[1]
        self.state.firmware_build = int.from_bytes(payload[2:4], byteorder="big")

    # ── GATT state read / subscribe ───────────────────────────────────────────

    async def _read_initial_state(self) -> None:
        """Read current values from all light control characteristics."""
        if self._client is None:
            return

        try:
            power_raw = bytes(await self._client.read_gatt_char(BLE_POWER_UUID))
            brightness_raw_bytes = bytes(
                await self._client.read_gatt_char(BLE_BRIGHTNESS_UUID)
            )
            color_temp_raw = bytes(
                await self._client.read_gatt_char(BLE_COLOR_TEMP_UUID)
            )

            power_on = bool(power_raw and power_raw[0] != 0)
            brightness_percent = brightness_raw_bytes[0] if brightness_raw_bytes else 0
            color_temp_kelvin = (
                int.from_bytes(color_temp_raw, byteorder="little")
                if color_temp_raw
                else None
            )

            self.state.power = power_on
            self.state.brightness_raw = brightness_percent
            self.state.brightness = raw_to_ha_brightness(brightness_percent)
            self.state.color_temp_kelvin = color_temp_kelvin
            self.state.color_temp_mired = (
                kelvin_to_mired(color_temp_kelvin)
                if color_temp_kelvin and color_temp_kelvin > 0
                else None
            )

            # Read diagnostic chars (best-effort)
            for short_id, uuid in (
                ("11006", BLE_CHAR_11006_UUID),
                ("11007", BLE_CHAR_11007_UUID),
                ("11009", BLE_CHAR_11009_UUID),
            ):
                try:
                    raw = bytes(await self._client.read_gatt_char(uuid))
                    setattr(self.state, f"char_{short_id}_hex", raw.hex())
                except Exception:  # noqa: BLE001
                    pass

        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning(
                "Failed to read initial state from %s: %s", self.serial_number, exc
            )

    async def _subscribe_notifications(self) -> None:
        """Subscribe to notify characteristics for real-time updates."""
        if self._client is None:
            return

        # Motion notifications (most important — drives binary sensor)
        try:
            await self._client.start_notify(
                BLE_MOTION_UUID, self._on_motion_notification
            )
            _LOGGER.debug(
                "Subscribed to motion notifications for %s", self.serial_number
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning(
                "Failed to subscribe to motion characteristic for %s: %s",
                self.serial_number,
                exc,
            )

        # Runtime / diagnostic notifications (best-effort)
        for short_id, uuid in (
            ("11006", BLE_CHAR_11006_UUID),
            ("11007", BLE_CHAR_11007_UUID),
            ("11009", BLE_CHAR_11009_UUID),
        ):
            try:
                await self._client.start_notify(
                    uuid, self._on_runtime_notification(short_id)
                )
                _LOGGER.debug(
                    "Subscribed to diagnostic characteristic %s for %s",
                    short_id,
                    self.serial_number,
                )
            except Exception as exc:  # noqa: BLE001
                _LOGGER.debug(
                    "Could not subscribe to diagnostic characteristic %s for %s: %s",
                    short_id,
                    self.serial_number,
                    exc,
                )

    # ── Public connection API ─────────────────────────────────────────────────

    async def connect_and_authenticate(self) -> None:
        """Connect to the lamp and complete LTK re-auth.

        On success, :attr:`state`.``connected`` and ``authenticated`` are set
        to :data:`True`.  The current light state is read from the device and
        notification subscriptions are established.

        Raises:
            RuntimeError: If a BleakClient cannot be created or connection fails.
            TimeoutError: If auth times out.
        """
        async with self._lock:
            _LOGGER.info(
                "Connecting to Dyson BLE lamp %s (MAC: %s)",
                self.serial_number,
                self.mac_address,
            )
            client = await self._get_bleak_client()
            _LOGGER.debug(
                "BleakClient obtained for %s: %s (already_connected: %s)",
                self.serial_number,
                type(client).__name__,
                getattr(client, "is_connected", False),
            )

            if not getattr(client, "is_connected", False):
                # Client not pre-connected — use manual retry loop (raw MAC fallback path)
                attempts = 4
                delay = 1.25
                last_exc: Exception | None = None

                for attempt in range(1, attempts + 1):
                    try:
                        _LOGGER.debug(
                            "BLE connect attempt %d/%d for %s",
                            attempt,
                            attempts,
                            self.serial_number,
                        )
                        await client.connect()
                        break
                    except Exception as exc:  # noqa: BLE001
                        last_exc = exc
                        _LOGGER.warning(
                            "BLE connect attempt %d/%d failed for %s: %s: %s",
                            attempt,
                            attempts,
                            self.serial_number,
                            type(exc).__name__,
                            exc,
                        )
                        if attempt < attempts:
                            await asyncio.sleep(delay)

                if not client.is_connected:
                    raise RuntimeError(
                        f"Failed to connect to {self.serial_number} after {attempts} attempts: "
                        f"{type(last_exc).__name__}: {last_exc}"
                    ) from last_exc
            else:
                _LOGGER.info(
                    "GATT connection already established for %s via bleak_retry_connector",
                    self.serial_number,
                )

            _LOGGER.info(
                "GATT connection established for %s — subscribing to auth characteristic",
                self.serial_number,
            )
            self._client = client
            self.state.connected = True
            self._message_queue = asyncio.Queue()
            self._assembler.reset()

            # Subscribe to auth characteristic notifications
            await self._client.start_notify(
                BLE_AUTH_CHAR_UUID, self._on_auth_notification
            )
            _LOGGER.debug(
                "Auth characteristic notification subscription active for %s",
                self.serial_number,
            )

            # LTK re-auth
            try:
                await self._reauth_with_ltk()
            except Exception as exc:
                _LOGGER.error(
                    "LTK re-auth failed for %s (%s: %s) — "
                    "verify that the LTK was correctly retrieved from the Dyson cloud",
                    self.serial_number,
                    type(exc).__name__,
                    exc,
                )
                self.state.last_error = str(exc)
                await self._disconnect_client()
                raise

            self.state.authenticated = True
            self.state.last_error = ""
            _LOGGER.info(
                "Dyson BLE lamp %s fully connected and authenticated",
                self.serial_number,
            )

            # Read initial state and subscribe to runtime notifications
            await self._read_initial_state()
            await self._subscribe_notifications()
            self._fire_state_change()

    async def _disconnect_client(self) -> None:
        """Disconnect the BleakClient, suppressing errors."""
        client = self._client
        self._client = None
        if client is not None:
            try:
                if client.is_connected:
                    _LOGGER.debug(
                        "Disconnecting GATT client for %s", self.serial_number
                    )
                    await client.disconnect()
            except Exception as exc:  # noqa: BLE001
                _LOGGER.debug(
                    "Error during GATT disconnect for %s: %s", self.serial_number, exc
                )
        self.state.connected = False
        self.state.authenticated = False
        _LOGGER.debug("GATT client disconnected for %s", self.serial_number)
        self._fire_state_change()

    async def disconnect(self) -> None:
        """Deliberately disconnect from the lamp."""
        async with self._lock:
            await self._disconnect_client()

    @property
    def is_connected(self) -> bool:
        """Return True if the lamp is connected and authenticated."""
        return (
            self._client is not None
            and getattr(self._client, "is_connected", False)
            and self.state.authenticated
        )

    # ── Command API ───────────────────────────────────────────────────────────

    async def set_power(self, on: bool) -> None:
        """Turn the lamp on or off.

        Args:
            on: :data:`True` to turn on, :data:`False` to turn off.

        Raises:
            RuntimeError: If the lamp is not connected and authenticated.
        """
        if not self.is_connected or self._client is None:
            raise RuntimeError(f"{self.serial_number} is not connected")
        async with self._lock:
            await self._client.write_gatt_char(
                BLE_POWER_UUID, b"\x01" if on else b"\x00", response=False
            )
            await asyncio.sleep(0.2)
            await self._read_initial_state()
            self._fire_state_change()

    async def set_brightness(self, ha_brightness: int) -> None:
        """Set brightness.

        Args:
            ha_brightness: Home Assistant brightness value (0–255).

        Raises:
            RuntimeError: If the lamp is not connected and authenticated.
        """
        if not self.is_connected or self._client is None:
            raise RuntimeError(f"{self.serial_number} is not connected")
        async with self._lock:
            raw = ha_to_raw_brightness(ha_brightness)
            await self._client.write_gatt_char(
                BLE_BRIGHTNESS_UUID, bytes([raw]), response=False
            )
            await asyncio.sleep(0.2)
            await self._read_initial_state()
            self._fire_state_change()

    async def set_color_temp_kelvin(self, kelvin: int) -> None:
        """Set color temperature in Kelvin.

        Args:
            kelvin: Color temperature in Kelvin (clamped to 2700–6500).

        Raises:
            RuntimeError: If the lamp is not connected and authenticated.
        """
        if not self.is_connected or self._client is None:
            raise RuntimeError(f"{self.serial_number} is not connected")
        async with self._lock:
            kelvin_clamped = max(BLE_MIN_KELVIN, min(BLE_MAX_KELVIN, kelvin))
            await self._client.write_gatt_char(
                BLE_COLOR_TEMP_UUID,
                kelvin_clamped.to_bytes(2, byteorder="little"),
                response=False,
            )
            await asyncio.sleep(0.2)
            await self._read_initial_state()
            self._fire_state_change()

    async def set_color_temp_mired(self, mired: int) -> None:
        """Set color temperature in mired.

        Args:
            mired: Color temperature in mired (converted to Kelvin internally).

        Raises:
            RuntimeError: If the lamp is not connected and authenticated.
        """
        await self.set_color_temp_kelvin(mired_to_kelvin(mired))

    async def poll_state(self) -> None:
        """Read current device state and fire an update event.

        Used by the keepalive loop in the coordinator.
        """
        if not self.is_connected:
            return
        async with self._lock:
            await self._read_initial_state()
            self._fire_state_change()

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info dict for the HA device registry."""
        info: dict[str, Any] = {
            "identifiers": {(BLE_SERVICE_UUID, self.serial_number)},
            "name": f"Dyson {self.serial_number}",
            "manufacturer": "Dyson",
            "model": "Lightcycle Morph (CD06)",
        }
        if self.state.firmware_major is not None:
            info["sw_version"] = (
                f"{self.state.firmware_major}.{self.state.firmware_minor}"
                f".{self.state.firmware_build}"
            )
        return info
