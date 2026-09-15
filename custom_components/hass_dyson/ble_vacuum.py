"""BLE transport for Dyson LEC floor-care vacuums (e.g. V16 Piston Animal).

This module implements the BLE client for Dyson BLE-only vacuums (device
category ``flrc``, connection category ``lecOnly``).  It shares the auth
channel, framing and crypto with the BLE light stack in :mod:`.ble_device`,
but after authentication it talks Dyson's **binary attribute protocol** on
the messaging characteristic (``2dd10021``):

- ``0x90`` READ_ATTRIBUTE request → ``0x91`` response
- ``0x93`` WRITE_ATTRIBUTE request → ``0x94`` write-status response
- ``0x96`` PUSH-ATTRIBUTE subscribe/unsubscribe → ``0x98`` ack
- ``0x97`` PUSH_ATTRIBUTE notifications on value change
- ``0x30`` AppActiveStatus (foreground / inactive hint)

The full attribute registry was mapped from the MyDyson Android app's
connected-floorcare module and verified live on a V16 Piston Animal
(see :data:`BLE_VACUUM_ATTRIBUTES` in :mod:`.const`).

Implementation notes / pitfalls (learned on real hardware):

- The vacuum's BLE stack reboots when flooded with back-to-back writes
  (symptoms: link drop mid-session, ~10 s of ignored button presses).
  All reads/subscribes are therefore paced and ack-synchronised.
- On disconnect we must unsubscribe (``0x96`` + INACTIVE) and send
  AppActiveStatus INACTIVE, otherwise the machine can stay in a
  "foreground app attached" state for a while.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .ble_device import (
    DysonFragmentAssembler,
    DysonMessage,
    build_reauth_payload_a,
    build_reauth_payload_c,
    fragment_dyson_message,
    hkdf_derive_aes_key,
)
from .const import (
    BLE_APP_STATUS_FOREGROUND_ACTIVE,
    BLE_APP_STATUS_INACTIVE,
    BLE_ATTR_ACK_TIMEOUT,
    BLE_ATTR_MAX_CONSECUTIVE_ERRORS,
    BLE_ATTR_READ_INTERVAL,
    BLE_ATTR_SUBSCRIBE_INTERVAL,
    BLE_AUTH_CHAR_UUID,
    BLE_GAP_DEVICE_NAME_CHAR_UUID,
    BLE_MSG_TYPE_APP_ACTIVE_STATUS,
    BLE_MSG_TYPE_CONNECTION_ESTABLISHED,
    BLE_MSG_TYPE_PRODUCT_INFO,
    BLE_MSG_TYPE_PUSH_ATTRIBUTE,
    BLE_MSG_TYPE_PUSH_ATTRIBUTE_ACK,
    BLE_MSG_TYPE_PUSH_ATTRIBUTE_REQUEST,
    BLE_MSG_TYPE_READ_ATTRIBUTE_REQUEST,
    BLE_MSG_TYPE_READ_ATTRIBUTE_RESPONSE,
    BLE_MSG_TYPE_REAUTH_PAYLOAD_A,
    BLE_MSG_TYPE_REAUTH_PAYLOAD_B,
    BLE_MSG_TYPE_REAUTH_PAYLOAD_C,
    BLE_MSG_TYPE_REQUEST_PRODUCT_INFO,
    BLE_MSG_TYPE_WRITE_ATTRIBUTE_REQUEST,
    BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE,
    BLE_PAIR_TIMEOUT,
    BLE_PUSH_STATUS_ACTIVE,
    BLE_PUSH_STATUS_INACTIVE,
    BLE_RSSI_CHAR_UUID,
    BLE_VACUUM_ATTR_BATTERY_LEVEL,
    BLE_VACUUM_ATTR_CLEANING_SESSION_ACTIVE,
    BLE_VACUUM_ATTRIBUTES,
    BLE_VACUUM_LDI_AUTO_MASK,
    BLE_VACUUM_SESSION_STATES,
    BLE_WRITE_ATTR_CHAR_UUID,
    DOMAIN,
    EVENT_BLE_STATE_CHANGE,
)
from .device_utils import mask_serial

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Maximum auth handshake attempts before giving up on a connection.
_MAX_AUTH_ATTEMPTS = 3

# Payload-B minimum length (reserved 2 + IV 16 + CT 32)
_PAYLOAD_B_MIN_LEN = 50

# Attributes re-polled in the keepalive loop: the ones that change often and
# are not guaranteed to push in every firmware state.
_VOLATILE_ATTRIBUTES: tuple[bytes, ...] = (
    BLE_VACUUM_ATTR_BATTERY_LEVEL,
    BLE_VACUUM_ATTR_CLEANING_SESSION_ACTIVE,
)


# ── Crypto helpers ────────────────────────────────────────────────────────────


def _aes_cbc_decrypt_for_vacuum(key: bytes, iv: bytes, ciphertext: bytes) -> bytes:
    """AES-128-CBC decrypt (no padding — ciphertext must be block-aligned).

    Floorcare PayloadB carries a 32-byte ciphertext (two plain blocks:
    nonce echo + device challenge), unlike the light's 16-byte envelopes.
    """
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()


# ── Attribute helpers ─────────────────────────────────────────────────────────


def parse_read_attribute_response(payload: bytes) -> tuple[bytes, int, bytes] | None:
    """Parse a 0x91 READ_ATTRIBUTE response.

    Layout: ``attrId(2) | status(1) | length(u16le) | data(length)``.

    Returns:
        ``(attr_id, status, data)`` or ``None`` for malformed payloads.
    """
    if len(payload) < 5:  # noqa: PLR2004
        return None
    attr_id = payload[0:2]
    status = payload[2]
    length = payload[3] | (payload[4] << 8)
    if len(payload) < 5 + length:
        return None
    return attr_id, status, payload[5 : 5 + length]


def parse_push_attribute(payload: bytes) -> tuple[bytes, bytes] | None:
    """Parse a 0x97 PUSH_ATTRIBUTE notification.

    Layout: ``attrId(2) | length(u16le) | data(length)``.

    Returns:
        ``(attr_id, data)`` or ``None`` for malformed payloads.
    """
    if len(payload) < 4:  # noqa: PLR2004
        return None
    attr_id = payload[0:2]
    length = payload[2] | (payload[3] << 8)
    if len(payload) < 4 + length:
        return None
    return attr_id, payload[4 : 4 + length]


def decode_attribute_value(attr_id: bytes, data: bytes) -> Any:
    """Decode an attribute value to its label / int / bool per the registry.

    Args:
        attr_id: Attribute id bytes (2).
        data: Raw attribute data.

    Returns:
        A decoded value: string label for enum attributes, ``bool`` for
        boolean and bitmask attributes, ``int`` for numeric attributes, or the
        raw ``bytes`` when unknown.
    """
    entry = BLE_VACUUM_ATTRIBUTES.get(attr_id)
    if entry is None or not data:
        return data
    decoder = entry[1]
    if decoder == "bool":
        return bool(data[0])
    if decoder == "int":
        return data[0] if len(data) == 1 else int.from_bytes(data[:2], "little")
    if decoder == "ldi_auto":
        return decode_ldi_auto(data)
    if isinstance(decoder, dict):
        return decoder.get(data[0], f"unknown ({data.hex()})")
    return data


def decode_ldi_auto(data: bytes) -> bool:
    """Decode the dust-illumination capability bitmask (0x0243).

    Mirrors the MyDyson app's ``iq/b.java``: the payload is widened to four
    bytes, read little-endian, and mask-tested against ``iq.c.AUTO`` (0b111).
    Anything that does not match falls back to NOT_AUTO.

    Args:
        data: Raw attribute payload (1-4 bytes in practice).

    Returns:
        True when the AUTO dust-illumination option is available.
    """
    buf = bytes(data[:4]).ljust(4, b"\x00")
    value = int.from_bytes(buf, "little")
    return (value & BLE_VACUUM_LDI_AUTO_MASK) == BLE_VACUUM_LDI_AUTO_MASK


def _ascii_or_hex(raw: bytes) -> str:
    """Decode a short product-info field, falling back to hex.

    Dyson encodes the hardware module and variant as printable ASCII inside the
    product-info payload; anything else is returned as hex so an unexpected
    machine still yields something usable.
    """
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        return raw.hex()
    return text if text.isprintable() else raw.hex()


# ── State ─────────────────────────────────────────────────────────────────────


@dataclass
class BLEVacuumState:
    """Current state snapshot of a Dyson BLE floor-cleaner."""

    connected: bool = False
    authenticated: bool = False
    firmware_major: int | None = None
    firmware_minor: int | None = None
    firmware_build: int | None = None
    hardware_module: str | None = None
    hardware_variant: str | None = None
    project_id: str | None = None
    pending_firmware_version: str | None = None
    recovery_firmware_version: str | None = None
    ota_status: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    attributes_raw: dict[str, str] = field(default_factory=dict)
    session_active: bool = False
    last_error: str = ""


class DysonBleVacuumDevice:
    """BLE transport for a Dyson floor-cleaning vacuum (LEC attribute protocol).

    Manages the connection lifecycle: scan/connect via Home Assistant's
    bluetooth integration, silent LTK re-auth (payload A/B/C — identical to
    the BLE light), product-info parse, attribute subscription with
    ack-synchronised pacing, attribute pushes on value change, and cleaned
    tear-down on disconnect.

    Attributes:
        serial_number: Dyson device serial number.
        mac_address: BLE MAC address (``AA:BB:CC:DD:EE:FF``).
        state: Current :class:`BLEVacuumState` snapshot.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        serial_number: str,
        mac_address: str,
        ltk_hex: str,
        account_uuid: str,
        ble_proxy: str | None = None,
        state_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Initialise the BLE vacuum device wrapper.

        Args:
            state_callback: Optional direct callback invoked with each state
                snapshot.  The coordinator uses this instead of subscribing to
                the event bus, so it is not woken by every other BLE device's
                updates just to filter them out by serial.
        """
        self.hass = hass
        self._state_callback = state_callback
        self.serial_number = serial_number
        self.mac_address = mac_address.upper()
        self._ltk_hex = ltk_hex
        self._account_uuid = account_uuid
        self._ble_proxy = ble_proxy

        self.state = BLEVacuumState()
        self._client: Any | None = None
        self._auth_assembler = DysonFragmentAssembler()
        self._msg_assembler = DysonFragmentAssembler()
        self._queue: asyncio.Queue[tuple[str, DysonMessage]] = asyncio.Queue()
        self._subscribed_attrs: set[bytes] = set()
        # Attribute ids answered during the *current* session.  state.attributes
        # deliberately survives a disconnect so entities keep their last known
        # values, which means it cannot tell us whether this session produced
        # any data — hence a separate per-session set.
        self._session_attrs: set[bytes] = set()
        self._lock = asyncio.Lock()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _fire_state_change(self) -> None:
        """Publish the current state snapshot.

        Goes to two places: the owning coordinator directly (private, typed),
        and ``EVENT_BLE_STATE_CHANGE`` on the event bus, which is documented
        for user automations and so stays a public interface.
        """
        payload: dict[str, Any] = {
            "serial_number": self.serial_number,
            "connected": self.state.connected,
            "authenticated": self.state.authenticated,
            "firmware_major": self.state.firmware_major,
            "firmware_minor": self.state.firmware_minor,
            "firmware_build": self.state.firmware_build,
            "hardware_module": self.state.hardware_module,
            "hardware_variant": self.state.hardware_variant,
            "project_id": self.state.project_id,
            "firmware_version": self.firmware_version,
            "dyson_firmware_version": self.dyson_firmware_version,
            "pending_firmware_version": self.state.pending_firmware_version,
            "recovery_firmware_version": self.state.recovery_firmware_version,
            "ota_status": self.state.ota_status,
            "attributes": dict(self.state.attributes),
            "attributes_raw": dict(self.state.attributes_raw),
            "session_active": self.state.session_active,
            "last_error": self.state.last_error,
        }
        if self._state_callback is not None:
            self._state_callback(payload)
        self.hass.bus.async_fire(EVENT_BLE_STATE_CHANGE, payload)

    def _update_attribute(self, attr_id: bytes, data: bytes, *, source: str) -> None:
        """Store one attribute value (decoded + raw) and track sessions."""
        entry = BLE_VACUUM_ATTRIBUTES.get(attr_id)
        attr_hex = attr_id.hex()
        self.state.attributes_raw[attr_hex] = data.hex()

        if entry is None:
            _LOGGER.debug(
                "Unknown attribute %s on %s (from %s): %s",
                attr_hex,
                mask_serial(self.serial_number),
                source,
                data.hex(),
            )
            return

        state_key = entry[0]
        value = decode_attribute_value(attr_id, data)
        self.state.attributes[state_key] = value
        self._session_attrs.add(attr_id)
        _LOGGER.debug(
            "Attribute %s (%s) on %s = %r [%s]",
            attr_hex,
            state_key,
            mask_serial(self.serial_number),
            value,
            source,
        )

        # Track whether a clean is in progress.  Only the live flag is kept:
        # durations/history cannot be derived reliably here, because it would
        # require HA to be connected across both edges of a clean, and a
        # handheld vacuum may be out of BLE range during the clean.  The
        # machine's own per-clean history is the encrypted 0x16/0x17 journal,
        # which only Dyson can decrypt.
        if attr_id == BLE_VACUUM_ATTR_CLEANING_SESSION_ACTIVE:
            label = (
                value
                if isinstance(value, str)
                else BLE_VACUUM_SESSION_STATES.get(int(bool(value)))
            )
            active = label == BLE_VACUUM_SESSION_STATES[1]
            if active != self.state.session_active:
                _LOGGER.info(
                    "Cleaning session %s on %s",
                    "started" if active else "ended",
                    mask_serial(self.serial_number),
                )
            self.state.session_active = active

    # ── GATT notification handlers ────────────────────────────────────────────

    def _on_auth_notification(self, _characteristic: Any, data: bytearray) -> None:
        """Handle raw notification from the auth characteristic (11011)."""
        fragment = bytes(data)
        try:
            message = self._auth_assembler.feed(fragment)
        except ValueError as exc:
            _LOGGER.warning(
                "BLE auth fragment error for %s: %s",
                mask_serial(self.serial_number),
                exc,
            )
            self._auth_assembler.reset()
            return
        if message is not None:
            _LOGGER.debug(
                "BLE auth message type=0x%02X len=%d from %s",
                message.type_id,
                len(message.payload),
                mask_serial(self.serial_number),
            )
            self._queue.put_nowait(("auth", message))

    def _on_messaging_notification(self, _characteristic: Any, data: bytearray) -> None:
        """Handle raw notification from the messaging characteristic (10021)."""
        fragment = bytes(data)
        try:
            message = self._msg_assembler.feed(fragment)
        except ValueError as exc:
            _LOGGER.warning(
                "BLE messaging fragment error for %s: %s",
                mask_serial(self.serial_number),
                exc,
            )
            self._msg_assembler.reset()
            return
        if message is None:
            return

        _LOGGER.debug(
            "BLE messaging message type=0x%02X len=%d from %s",
            message.type_id,
            len(message.payload),
            mask_serial(self.serial_number),
        )

        # Pushes update state directly; anything else goes to the queue for
        # synchronous waiters (acks, read responses).
        if message.type_id == BLE_MSG_TYPE_PUSH_ATTRIBUTE:
            parsed = parse_push_attribute(message.payload)
            if parsed is None:
                _LOGGER.warning(
                    "Malformed PUSH_ATTRIBUTE from %s: %s",
                    mask_serial(self.serial_number),
                    message.payload.hex(),
                )
                return
            push_attr, push_data = parsed
            self._update_attribute(push_attr, push_data, source="push")
            self._fire_state_change()
        else:
            self._queue.put_nowait(("msg", message))

    def _on_bleak_disconnect(self, client: Any) -> None:  # noqa: ARG002
        """Handle unexpected BLE disconnect."""
        _LOGGER.info(
            "BLE vacuum %s (%s) unexpectedly disconnected",
            mask_serial(self.serial_number),
            self.mac_address,
        )
        self.state.connected = False
        self.state.authenticated = False
        # Keep session_active sticky: a BLE drop does not mean the clean
        # ended; on reconnect we re-read the attribute anyway.
        self._client = None
        self._fire_state_change()

    # ── Message plumbing ──────────────────────────────────────────────────────

    async def _wait_for_message(
        self,
        tag: str,
        predicate: Any,
        timeout: float,
        description: str,
    ) -> DysonMessage:
        """Wait for a message matching ``predicate`` from the queue.

        Args:
            tag: Channel tag ("auth" or "msg") the message must come from.
            predicate: Callable ``(DysonMessage) -> bool``.
            timeout: Max seconds to wait.
            description: Human-readable description for log/error messages.

        Raises:
            TimeoutError: On timeout.
            RuntimeError: If the link drops while waiting.
        """
        end = self.hass.loop.time() + timeout
        while True:
            remaining = end - self.hass.loop.time()
            if remaining <= 0:
                raise TimeoutError(
                    f"Timed out waiting for {description} from "
                    f"{mask_serial(self.serial_number)}"
                )
            poll_timeout = min(remaining, 1.0)
            try:
                tag_, message = await asyncio.wait_for(
                    self._queue.get(), timeout=poll_timeout
                )
            except asyncio.TimeoutError:
                if self._client is None or not getattr(
                    self._client, "is_connected", True
                ):
                    raise RuntimeError(
                        f"BLE device {mask_serial(self.serial_number)} disconnected "
                        f"while waiting for {description}"
                    ) from None
                continue
            if tag_ != tag:
                # Interesting cross-channel traffic — opportunistically keep it.
                # Product info is relevant no matter which queue it landed on.
                if message.type_id == BLE_MSG_TYPE_PRODUCT_INFO:
                    self._parse_product_info(message.payload)
                if tag_ == "msg" and message.type_id == BLE_MSG_TYPE_PUSH_ATTRIBUTE:
                    parsed = parse_push_attribute(message.payload)
                    if parsed is not None:
                        push_attr, push_data = parsed
                        self._update_attribute(push_attr, push_data, source="push")
                        self._fire_state_change()
                continue
            if predicate(message):
                return message
            _LOGGER.debug(
                "Ignoring message type=0x%02X while waiting for %s from %s",
                message.type_id,
                description,
                mask_serial(self.serial_number),
            )

    async def _wait_for_type(
        self, tag: str, type_id: int, timeout: float
    ) -> DysonMessage:
        """Wait for a message of a specific type id."""
        return await self._wait_for_message(
            tag,
            lambda m: m.type_id == type_id,
            timeout,
            f"message type 0x{type_id:02X}",
        )

    @staticmethod
    def _auth_char_is_absent(client: Any) -> bool:
        """Whether the peer demonstrably does not expose the Dyson service.

        Only ``True`` when the service table resolved and the characteristic
        genuinely is not in it.  A backend that exposes no table, or raises on
        lookup, is *unknown* rather than absent — never fail a connection on
        the strength of something we could not determine.
        """
        services = getattr(client, "services", None)
        if services is None:
            return False
        try:
            return services.get_characteristic(BLE_AUTH_CHAR_UUID) is None
        except Exception:  # noqa: BLE001 - bleak backends vary
            return False

    def _log_gatt_table(self, client: Any) -> None:
        """Record what the peer actually exposes, for connection triage.

        The service table is the first thing that differs between a direct
        adapter and a proxied connection, and a stale service cache shows up
        here as a missing or empty Dyson service.
        """
        services = getattr(client, "services", None)
        if services is None:
            _LOGGER.debug("No GATT service table available for %s", self.mac_address)
            return
        for service in services:
            for char in service.characteristics:
                _LOGGER.debug(
                    "GATT %s char %s [%s]",
                    service.uuid,
                    char.uuid,
                    ",".join(char.properties),
                )

    async def _ensure_bonded(self, client: Any) -> None:
        """Bond with the machine before touching its characteristics.

        Every Dyson characteristic sits behind ATT error 0x05 (*insufficient
        authentication*): the vacuum will only serve them over an encrypted
        link.  A local adapter that has bonded once keeps the keys, so direct
        connections appear to need no explicit step — but a Bluetooth proxy
        starts with no bond, and the rejection is invisible there, because the
        protocol only ever uses write-without-response and the spec never
        acknowledges a Write Command.  Writes simply vanish and every reply
        times out while the link itself looks healthy.

        ESPHome proxies implement pairing and keep the bond in NVS, so this is
        a one-time cost per proxy.  Best-effort: a backend that cannot pair
        (or a device already bonded) should not block the connection.
        """
        try:
            paired = await asyncio.wait_for(client.pair(), timeout=BLE_PAIR_TIMEOUT)
        except TimeoutError:
            _LOGGER.warning(
                "Pairing with BLE vacuum %s (%s) timed out after %ss — "
                "continuing, but the handshake will fail if no bond exists",
                mask_serial(self.serial_number),
                self.mac_address,
                BLE_PAIR_TIMEOUT,
            )
            return
        except NotImplementedError:
            _LOGGER.debug(
                "Bluetooth backend for %s does not implement pairing — "
                "continuing unbonded",
                self.mac_address,
            )
            return
        except Exception as exc:  # noqa: BLE001 - backends raise freely here
            _LOGGER.warning(
                "Pairing with BLE vacuum %s (%s) failed: %s — the machine only "
                "serves its characteristics over a bonded link, so the "
                "handshake will most likely time out",
                mask_serial(self.serial_number),
                self.mac_address,
                exc,
            )
            return
        # Not a success signal: an ESPHome proxy returns False here even when
        # the bond was established and the link is encrypted afterwards.  The
        # authoritative check is whether a Dyson characteristic becomes
        # readable, which the handshake exercises immediately after.
        _LOGGER.debug("Pairing with %s returned %r", self.mac_address, paired)

    async def _probe_link(self, client: Any) -> None:
        """Read a characteristic to prove the ATT layer works both ways.

        Every Dyson characteristic is write-without-response plus notify, so
        nothing in the protocol is acknowledged: a frame the transport quietly
        drops and a frame the machine ignores produce exactly the same silence,
        and notifications are the only return path.  A read is a genuine
        request/response exchange, so it separates "the link is dead" from
        "the link is fine but notifications are not arriving" — the difference
        between a transport bug and a protocol one.

        Debug-gated and best-effort: never let triage break a connection.
        """
        if not _LOGGER.isEnabledFor(logging.DEBUG):
            return
        for uuid, what in (
            (BLE_GAP_DEVICE_NAME_CHAR_UUID, "GAP device name"),
            (BLE_RSSI_CHAR_UUID, "Dyson RSSI probe"),
        ):
            try:
                value = await asyncio.wait_for(client.read_gatt_char(uuid), timeout=10)
            except Exception as exc:  # noqa: BLE001
                _LOGGER.debug("Link probe: reading %s (%s) failed: %s", what, uuid, exc)
                continue
            _LOGGER.debug(
                "Link probe: %s (%s) = %s", what, uuid, bytes(value).hex() or "empty"
            )

    async def _send_message(
        self, char_uuid: str, type_id: int, payload: bytes = b""
    ) -> None:
        """Fragment and write a logical message to the given characteristic.

        Both Dyson characteristics are write-without-response only, so nothing
        here is ever acknowledged — the spec returns no error for a Write
        Command.  A frame the machine rejects (see :meth:`_ensure_bonded`) is
        indistinguishable from one it accepted, which is why the TX log below
        exists: it is the only record that we sent anything at all.
        """
        if self._client is None:
            raise RuntimeError("BLE client not connected")
        fragments = fragment_dyson_message(type_id, payload)
        _LOGGER.debug(
            "TX msg 0x%02X to %s: %d byte(s) in %d frame(s)",
            type_id,
            char_uuid,
            len(payload),
            len(fragments),
        )
        for fragment in fragments:
            await self._client.write_gatt_char(char_uuid, fragment, response=False)

    # ── Connection / auth ─────────────────────────────────────────────────────

    async def _get_bleak_client(self) -> Any:
        """Obtain a connected (or connectable) BleakClient via HA bluetooth."""
        from bleak import BleakClient  # provided by HA core

        client = None
        try:
            from homeassistant.components import bluetooth as _bt

            connectable_info = _bt.async_last_service_info(
                self.hass, self.mac_address, connectable=True
            )
            if connectable_info is not None:
                try:
                    from bleak_retry_connector import establish_connection

                    client = await establish_connection(
                        BleakClient,
                        connectable_info.device,
                        self.serial_number,
                        disconnected_callback=self._on_bleak_disconnect,
                        max_attempts=4,
                        use_services_cache=True,
                    )
                    _LOGGER.info(
                        "BLE connection to %s established via bleak_retry_connector",
                        mask_serial(self.serial_number),
                    )
                    return client
                except ImportError:
                    _LOGGER.warning(
                        "bleak_retry_connector not available for %s — "
                        "falling back to direct BleakClient",
                        mask_serial(self.serial_number),
                    )
                    client = BleakClient(connectable_info.device)
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.warning(
                        "establish_connection() failed for %s (%s) — "
                        "falling back to direct BleakClient",
                        mask_serial(self.serial_number),
                        exc,
                    )
                    client = BleakClient(connectable_info.device)
            else:
                _LOGGER.warning(
                    "BLE vacuum %s (%s) not currently seen as connectable — "
                    "check range / ESPHome proxy 'active: true'",
                    mask_serial(self.serial_number),
                    self.mac_address,
                )
        except ImportError:
            _LOGGER.warning(
                "HA bluetooth integration unavailable for %s — "
                "falling back to raw MAC address",
                mask_serial(self.serial_number),
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning(
                "Error querying HA bluetooth integration for %s: %s",
                mask_serial(self.serial_number),
                exc,
            )
        if client is None:
            client = BleakClient(self.mac_address)
        return await self._connect_with_retries(client, attempts=3, delay=1.25)

    async def _connect_with_retries(
        self, client: Any, attempts: int = 3, delay: float = 1.25
    ) -> Any:
        """Connect a fallback BleakClient with the light stack's retry loop.

        A bare ``BleakClient(...)`` is not connected — every fallback path must
        bring the link up here, otherwise the very next GATT op explodes with
        'Not connected'.  Raises after ``attempts`` failed attempts.
        """
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                await client.connect()
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                _LOGGER.warning(
                    "BLE fallback connect attempt %d/%d failed for %s: %s: %s",
                    attempt,
                    attempts,
                    mask_serial(self.serial_number),
                    type(exc).__name__,
                    exc,
                )
                if attempt < attempts:
                    await asyncio.sleep(delay)
        if not getattr(client, "is_connected", False):
            raise RuntimeError(
                f"Failed to connect to {mask_serial(self.serial_number)} after "
                f"{attempts} attempts: {type(last_exc).__name__}: {last_exc}"
            ) from last_exc
        return client

    async def _reauth_with_ltk(self, enc_key: bytes) -> None:
        """Perform silent LTK re-authentication (payload A/B/C → 0x26)."""
        # Product info, same as the app sends before auth.
        await self._send_message(BLE_AUTH_CHAR_UUID, BLE_MSG_TYPE_REQUEST_PRODUCT_INFO)
        try:
            product_msg = await self._wait_for_type(
                "auth", BLE_MSG_TYPE_PRODUCT_INFO, timeout=5.0
            )
            self._parse_product_info(product_msg.payload)
        except TimeoutError:
            _LOGGER.debug(
                "No product info from %s (timeout); continuing with auth",
                mask_serial(self.serial_number),
            )

        payload_b_msg: DysonMessage | None = None
        for auth_attempt in range(1, _MAX_AUTH_ATTEMPTS + 1):
            nonce = os.urandom(16)
            payload_a = build_reauth_payload_a(self._account_uuid, enc_key, nonce)
            await self._send_message(
                BLE_AUTH_CHAR_UUID, BLE_MSG_TYPE_REAUTH_PAYLOAD_A, payload_a
            )
            try:
                payload_b_msg = await self._wait_for_type(
                    "auth", BLE_MSG_TYPE_REAUTH_PAYLOAD_B, timeout=30.0
                )
                break
            except TimeoutError:
                if auth_attempt < _MAX_AUTH_ATTEMPTS:
                    _LOGGER.warning(
                        "PayloadB timeout for %s (attempt %d/%d) — retrying",
                        mask_serial(self.serial_number),
                        auth_attempt,
                        _MAX_AUTH_ATTEMPTS,
                    )
                else:
                    raise

        assert payload_b_msg is not None
        # PayloadB: [0:2] reserved, [2:18] IV, [18:50] CT, [50:82] MAC (optional)
        if len(payload_b_msg.payload) < _PAYLOAD_B_MIN_LEN:
            raise RuntimeError(
                f"PayloadB from {mask_serial(self.serial_number)} too short "
                f"({len(payload_b_msg.payload)} < {_PAYLOAD_B_MIN_LEN})"
            )
        iv = payload_b_msg.payload[2:18]
        ct = payload_b_msg.payload[18:50]
        mac = payload_b_msg.payload[50:82]
        expected_mac = hmac.new(enc_key, ct, hashlib.sha256).digest()
        if len(mac) == 32 and not hmac.compare_digest(mac, expected_mac):  # noqa: PLR2004
            raise RuntimeError(
                f"PayloadB from {mask_serial(self.serial_number)} failed HMAC "
                "verification — LTK may be incorrect"
            )
        # Decrypt the 32-byte ciphertext in place (nonce_echo || challenge).
        # Note: g20c_decrypt() from the light stack cannot be reused here —
        # it expects a 16-byte-plaintext 64-byte envelope, while floorcare
        # PayloadB carries two 16-byte blocks.
        dec = _aes_cbc_decrypt_for_vacuum(enc_key, iv, ct)
        if len(dec) != 32:  # noqa: PLR2004
            raise RuntimeError(
                f"Could not decode PayloadB from {mask_serial(self.serial_number)}"
            )
        # Freshness check: the machine must echo the nonce we just sent,
        # otherwise the exchange could be replayed or the queue mixed up.
        if not hmac.compare_digest(dec[0:16], nonce):
            raise RuntimeError(
                f"PayloadB from {mask_serial(self.serial_number)} did not echo "
                "our nonce — authentication rejected"
            )
        device_challenge = dec[16:32]

        payload_c = build_reauth_payload_c(enc_key, device_challenge)
        await self._send_message(
            BLE_AUTH_CHAR_UUID, BLE_MSG_TYPE_REAUTH_PAYLOAD_C, payload_c
        )
        conn_msg = await self._wait_for_type(
            "auth", BLE_MSG_TYPE_CONNECTION_ESTABLISHED, timeout=30.0
        )
        self._parse_connection_established(conn_msg.payload)
        _LOGGER.info(
            "BLE LTK re-auth successful for %s", mask_serial(self.serial_number)
        )

    def _parse_product_info(self, payload: bytes) -> None:
        """Parse product info response (type 0x0B).

        Layout: ``fw_major(1) fw_minor(1) fw_build(u16le) | module(2) variant(2)
        | project_id(4, optional)``
        """
        if len(payload) < 8:  # noqa: PLR2004
            return
        self.state.firmware_major = payload[0]
        self.state.firmware_minor = payload[1]
        # Dyson reports build as little-endian on floorcare (newer firmware
        # trees); mirrors the MyDyson product-info parser.
        self.state.firmware_build = int.from_bytes(payload[2:4], byteorder="little")
        # Module and variant are ASCII, not opaque bytes.  Confirmed against the
        # Dyson cloud, which reports this machine as "SVC0PS.50.02.013.0002":
        # 0x5053 -> "PS" (module) and 0x3530 -> "50" (variant).
        self.state.hardware_module = _ascii_or_hex(payload[4:6])
        self.state.hardware_variant = _ascii_or_hex(payload[6:8])
        if len(payload) >= 12:  # noqa: PLR2004
            try:
                self.state.project_id = payload[8:12].decode("utf-8")
            except UnicodeDecodeError:
                self.state.project_id = payload[8:12].hex()
        _LOGGER.debug(
            "Product info for %s: fw %d.%d.%d, module %s, variant %s, project %s",
            mask_serial(self.serial_number),
            self.state.firmware_major,
            self.state.firmware_minor,
            self.state.firmware_build,
            self.state.hardware_module,
            self.state.hardware_variant,
            self.state.project_id,
        )

    def _parse_connection_established(self, payload: bytes) -> None:
        """Parse Connection Established (0x26).

        Layout: ``ota_status(1) | pending_fw(4) | recovery_fw(4) | pkg_type(1)``
        where fw = ``major(1) minor(1) build(u16le)``.
        """
        if len(payload) < 10:  # noqa: PLR2004
            return
        self.state.ota_status = payload[0]
        # pending_fw is the version the machine has staged / is offered next.
        # All-zero means "nothing pending" — the common case.
        pending_major, pending_minor = payload[1], payload[2]
        pending_build = int.from_bytes(payload[3:5], byteorder="little")
        if (pending_major, pending_minor, pending_build) == (0, 0, 0):
            self.state.pending_firmware_version = None
        else:
            self.state.pending_firmware_version = (
                f"{pending_major}.{pending_minor}.{pending_build}"
            )
        major, minor = payload[5], payload[6]
        build = int.from_bytes(payload[7:9], byteorder="little")
        self.state.recovery_firmware_version = f"{major}.{minor}.{build}"
        _LOGGER.debug(
            "Connection established for %s: ota_status=%s, pending fw=%s, recovery fw=%s",
            mask_serial(self.serial_number),
            self.state.ota_status,
            self.state.pending_firmware_version,
            self.state.recovery_firmware_version,
        )

    # ── Attribute channel ─────────────────────────────────────────────────────

    async def _subscribe_attributes(self) -> None:
        """Subscribe (0x96 + ACTIVE) to every known attribute, ack-synchronised.

        The subscription burst is paced like the MyDyson app does (~0.3-0.4 s)
        because storms of unacked writes can reboot the machine's BLE stack.
        """
        errors = 0
        for attr_id, entry in BLE_VACUUM_ATTRIBUTES.items():
            if errors >= BLE_ATTR_MAX_CONSECUTIVE_ERRORS:
                _LOGGER.warning(
                    "Stopping attribute subscription for %s after %d errors",
                    mask_serial(self.serial_number),
                    errors,
                )
                return
            state_key = entry[0]
            try:
                async with self._lock:
                    await self._send_message(
                        BLE_WRITE_ATTR_CHAR_UUID,
                        BLE_MSG_TYPE_PUSH_ATTRIBUTE_REQUEST,
                        attr_id + bytes((BLE_PUSH_STATUS_ACTIVE,)),
                    )
                    ack = await self._wait_for_message(
                        "msg",
                        lambda m, a=attr_id: (
                            m.type_id == BLE_MSG_TYPE_PUSH_ATTRIBUTE_ACK
                            and m.payload == a
                        ),
                        BLE_ATTR_ACK_TIMEOUT,
                        f"subscribe ack for attribute {attr_id.hex()}",
                    )
                    del ack
                self._subscribed_attrs.add(attr_id)
                _LOGGER.debug(
                    "Subscribed to attribute %s (%s) on %s",
                    attr_id.hex(),
                    state_key,
                    mask_serial(self.serial_number),
                )
                errors = 0
            except (TimeoutError, RuntimeError) as exc:
                errors += 1
                _LOGGER.debug(
                    "No/late ack subscribing to %s on %s: %s",
                    state_key,
                    mask_serial(self.serial_number),
                    exc,
                )
                await asyncio.sleep(1.0)
            await asyncio.sleep(BLE_ATTR_SUBSCRIBE_INTERVAL)
        _LOGGER.info(
            "Attribute subscription for %s done (%d/%d subscribed)",
            mask_serial(self.serial_number),
            len(self._subscribed_attrs),
            len(BLE_VACUUM_ATTRIBUTES),
        )

    async def read_attribute(self, attr_id: bytes) -> bool:
        """Send one READ_ATTRIBUTE (0x90) and wait for its 0x91 response.

        Returns:
            True when a response with status 0 was applied, False otherwise.
        """
        try:
            async with self._lock:
                await self._send_message(
                    BLE_WRITE_ATTR_CHAR_UUID,
                    BLE_MSG_TYPE_READ_ATTRIBUTE_REQUEST,
                    attr_id,
                )
                response = await self._wait_for_message(
                    "msg",
                    lambda m, a=attr_id: (
                        m.type_id == BLE_MSG_TYPE_READ_ATTRIBUTE_RESPONSE
                        and m.payload[:2] == a
                    ),
                    BLE_ATTR_ACK_TIMEOUT * 2,
                    f"read response for attribute {attr_id.hex()}",
                )
        except (TimeoutError, RuntimeError) as exc:
            _LOGGER.debug(
                "Read of attribute %s on %s failed: %s",
                attr_id.hex(),
                mask_serial(self.serial_number),
                exc,
            )
            return False

        parsed = parse_read_attribute_response(response.payload)
        if parsed is None:
            _LOGGER.warning(
                "Malformed read response from %s: %s",
                mask_serial(self.serial_number),
                response.payload.hex(),
            )
            return False
        _attr, status, data = parsed
        if status != 0:
            _LOGGER.debug(
                "Read attribute %s on %s returned status %d",
                attr_id.hex(),
                mask_serial(self.serial_number),
                status,
            )
            return False
        self._update_attribute(attr_id, data, source="read")
        self._fire_state_change()
        return True

    async def read_all_attributes(self) -> None:
        """Paced read of every known attribute (0x90 + response)."""
        errors = 0
        for attr_id in BLE_VACUUM_ATTRIBUTES:
            if errors >= BLE_ATTR_MAX_CONSECUTIVE_ERRORS:
                _LOGGER.warning(
                    "Aborting attribute read sweep for %s after %d errors",
                    mask_serial(self.serial_number),
                    errors,
                )
                return
            ok = await self.read_attribute(attr_id)
            if ok:
                errors = 0
            else:
                errors += 1
                await asyncio.sleep(1.0)
            await asyncio.sleep(BLE_ATTR_READ_INTERVAL)

    async def poll_state(self) -> None:
        """Keepalive poll — re-read volatile attributes only."""
        for attr_id in _VOLATILE_ATTRIBUTES:
            await self.read_attribute(attr_id)
            await asyncio.sleep(BLE_ATTR_READ_INTERVAL)

    async def write_attribute(self, attr_id: bytes, value: bytes) -> bool:
        """Write one attribute via 0x93 WRITE_ATTRIBUTE request.

        Layout: ``attrId(2) | length(u16le) | data(length)``.  The machine
        answers with a write-status response and/or a 0x97 push carrying the
        new value; the push is what updates entity state (never assumed
        optimistically).

        Writes are paced like reads — the BLE stack is fragile under write
        bursts.

        Returns:
            True when the machine *accepted* the write — either a 0x94 status
            of 0, or a 0x97 push carrying the new value.

            Acceptance is not the same as applied.  Verified on a V16: writing
            dust illumination (0x0A40) with no cleaner head attached returns
            ``0a4000`` — status 0 — while the attribute stays unchanged,
            because the LDI laser lives in the head.  Callers should treat a
            True here as "the command reached the machine", and rely on the
            attribute push for what the value actually became.
        """
        payload = attr_id + len(value).to_bytes(2, "little") + value
        try:
            async with self._lock:
                await self._send_message(
                    BLE_WRITE_ATTR_CHAR_UUID,
                    BLE_MSG_TYPE_WRITE_ATTRIBUTE_REQUEST,
                    payload,
                )
                # Two independent confirmations exist:
                # (a) the 0x94 write-status response with an explicit status byte
                #     for this attribute (fast, carries reject reasons), or
                # (b) a 0x97 push carrying the new value (updated by the
                #     notification handler into state.attributes_raw).
                status: int | None = None
                try:
                    resp = await self._wait_for_message(
                        "msg",
                        lambda m, a=attr_id: (
                            m.type_id == BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE
                            and m.payload[:2] == a
                        ),
                        BLE_ATTR_ACK_TIMEOUT * 2,
                        f"write status for attribute {attr_id.hex()}",
                    )
                    status = resp.payload[2] if len(resp.payload) >= 3 else None  # noqa: PLR2004
                    _LOGGER.debug(
                        "Write status for %s on %s: status=%s raw=%s",
                        attr_id.hex(),
                        mask_serial(self.serial_number),
                        status,
                        resp.payload.hex(),
                    )
                except TimeoutError:
                    status = None

                if status == 0:
                    if self.state.attributes_raw.get(attr_id.hex()) != value.hex():
                        # Accepted but not (yet) reflected.  Normal when the
                        # hardware the setting drives is absent — e.g. dust
                        # illumination with no cleaner head fitted.
                        _LOGGER.debug(
                            "Write of %s=%s accepted by %s but the attribute still "
                            "reads %s — the setting may not apply in this state",
                            attr_id.hex(),
                            value.hex(),
                            mask_serial(self.serial_number),
                            self.state.attributes_raw.get(attr_id.hex()),
                        )
                    return True
                if status is not None:
                    # An explicit non-zero status is the machine saying no, and
                    # it is authoritative.  Checking the current value first
                    # would report success for a rejected no-op write (observed
                    # on a V16: battery care returns 134001 even when writing
                    # the value it already holds).
                    _LOGGER.warning(
                        "Write of attribute %s=%s rejected by %s (write status %d)",
                        attr_id.hex(),
                        value.hex(),
                        mask_serial(self.serial_number),
                        status,
                    )
                    return False
                # No 0x94 arrived at all — fall back to the attribute push.
                if self.state.attributes_raw.get(attr_id.hex()) == value.hex():
                    return True
                _LOGGER.warning(
                    "Write of attribute %s=%s on %s not confirmed by the machine",
                    attr_id.hex(),
                    value.hex(),
                    mask_serial(self.serial_number),
                )
                return False
        except (TimeoutError, RuntimeError) as exc:
            _LOGGER.debug(
                "Write of attribute %s on %s failed: %s",
                attr_id.hex(),
                mask_serial(self.serial_number),
                exc,
            )
            return False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect_and_authenticate(self) -> None:
        """Connect (if needed), subscribe channels, and run LTK re-auth."""
        # Reset all session state up front — after a failed attempt the
        # assemblers, message queue and subscribed-attribute set must not
        # carry over, or a stale PayloadB can be matched against the wrong
        # nonce on the retry.
        self._auth_assembler.reset()
        self._msg_assembler.reset()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover - defensive
                break
        self._subscribed_attrs.clear()
        self._session_attrs.clear()

        if self._client is None or not getattr(self._client, "is_connected", False):
            self._client = await self._get_bleak_client()

        self._log_gatt_table(self._client)
        await self._ensure_bonded(self._client)
        await self._probe_link(self._client)
        if self._auth_char_is_absent(self._client):
            # Better to say so than to sit through three handshake timeouts:
            # the link is up but this is not a Dyson GATT table, which usually
            # means a stale service cache or a wrong MAC.
            raise RuntimeError(
                f"Auth characteristic {BLE_AUTH_CHAR_UUID} is not present on "
                f"{self.mac_address} — the connected peer does not expose the "
                "Dyson service"
            )

        await self._client.start_notify(BLE_AUTH_CHAR_UUID, self._on_auth_notification)
        _LOGGER.debug(
            "Started auth notifications for %s", mask_serial(self.serial_number)
        )

        ltk = bytes.fromhex(self._ltk_hex)
        enc_key = hkdf_derive_aes_key(ltk)
        await self._reauth_with_ltk(enc_key)

        # Messaging channel: subscription first, then AppActiveStatus, then the
        # attribute pipeline (same order the app uses).
        await self._client.start_notify(
            BLE_WRITE_ATTR_CHAR_UUID, self._on_messaging_notification
        )
        _LOGGER.debug(
            "Started messaging notifications for %s", mask_serial(self.serial_number)
        )

        await self._send_message(
            BLE_WRITE_ATTR_CHAR_UUID,
            BLE_MSG_TYPE_APP_ACTIVE_STATUS,
            bytes((BLE_APP_STATUS_FOREGROUND_ACTIVE,)),
        )
        await asyncio.sleep(0.5)

        self.state.connected = True
        self.state.authenticated = True
        self.state.last_error = ""
        self._fire_state_change()

        await self._subscribe_attributes()
        await self.read_all_attributes()
        if not self._session_attrs:
            # A session with zero usable attributes is a failed session, not a
            # ready one — marking it connected would flap the device between
            # "ready" and "offline" with every entity empty.  Treat it like any
            # other connection failure and let the lifecycle back off/retry.
            #
            # This must test what *this* session received: state.attributes
            # survives disconnects on purpose, so checking it would pass on
            # cached values from an earlier session and serve stale readings
            # as live indefinitely.
            await self.disconnect()
            raise RuntimeError(
                f"BLE vacuum {mask_serial(self.serial_number)} authenticated but "
                "answered zero attributes — treating as failed connection"
            )
        _LOGGER.info(
            "BLE vacuum %s ready (%d attribute subscriptions, %d attributes read "
            "this session)",
            mask_serial(self.serial_number),
            len(self._subscribed_attrs),
            len(self._session_attrs),
        )

    async def disconnect(self) -> None:
        """Gently tear down the attribute session and disconnect."""
        client = self._client
        self._client = None
        if client is None:
            return
        # Teardown writes are only meaningful with a live link — calling
        # write/disconnect on a never-connected client throws inside bleak.
        if not getattr(client, "is_connected", False):
            self.state.connected = False
            self.state.authenticated = False
            self._fire_state_change()
            return
        try:
            # Unsubscribe pushes the same way the app does when leaving.
            for attr_id in list(self._subscribed_attrs):
                try:
                    fragments = fragment_dyson_message(
                        BLE_MSG_TYPE_PUSH_ATTRIBUTE_REQUEST,
                        attr_id + bytes((BLE_PUSH_STATUS_INACTIVE,)),
                    )
                    for fragment in fragments:
                        await client.write_gatt_char(
                            BLE_WRITE_ATTR_CHAR_UUID, fragment, response=False
                        )
                    await asyncio.sleep(0.2)
                except Exception:  # noqa: BLE001
                    break
            fragments = fragment_dyson_message(
                BLE_MSG_TYPE_APP_ACTIVE_STATUS,
                bytes((BLE_APP_STATUS_INACTIVE,)),
            )
            for fragment in fragments:
                await client.write_gatt_char(
                    BLE_WRITE_ATTR_CHAR_UUID, fragment, response=False
                )
            await asyncio.sleep(0.5)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug(
                "Graceful teardown skipped for %s: %s",
                mask_serial(self.serial_number),
                exc,
            )
        finally:
            # This has to run even when the graceful phase above is cancelled
            # (CancelledError is a BaseException, so `except Exception` does not
            # stop it).  ``self._client`` was cleared at the top, so a second
            # disconnect() call returns immediately — if the real teardown were
            # skipped here the BLE link would simply stay up.
            try:
                await client.disconnect()
            except Exception as exc:  # noqa: BLE001
                _LOGGER.debug(
                    "Disconnect error for %s: %s", mask_serial(self.serial_number), exc
                )
            self.state.connected = False
            self.state.authenticated = False
            self._fire_state_change()

    # ── Convenience accessors for entities ────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        """Return True when connected and authenticated."""
        return (
            self.state.connected
            and self.state.authenticated
            and self._client is not None
            and getattr(self._client, "is_connected", False)
        )

    @property
    def firmware_version(self) -> str | None:
        """Return firmware version as ``major.minor.build`` when known."""
        if (
            self.state.firmware_major is None
            or self.state.firmware_minor is None
            or self.state.firmware_build is None
        ):
            return None
        return (
            f"{self.state.firmware_major}."
            f"{self.state.firmware_minor}."
            f"{self.state.firmware_build}"
        )

    @property
    def dyson_firmware_version(self) -> str | None:
        """Return the firmware in Dyson's own format, or None if incomplete.

        Reconstructs exactly what the cloud reports for this machine —
        ``SVC0PS.50.02.013.0002`` — from the BLE product-info fields, as
        ``{project}{module}.{variant}.{major:02d}.{minor:03d}.{build:04d}``.
        Verified byte-for-byte against the account API.  This is the form to
        compare against a cloud "latest version"; :attr:`firmware_version`
        stays the short human-readable one used for the device registry.
        """
        st = self.state
        if None in (st.firmware_major, st.firmware_minor, st.firmware_build):
            return None
        if not (st.project_id and st.hardware_module and st.hardware_variant):
            return None
        return (
            f"{st.project_id}{st.hardware_module}.{st.hardware_variant}."
            f"{st.firmware_major:02d}.{st.firmware_minor:03d}.{st.firmware_build:04d}"
        )

    @property
    def device_info(self):
        """Return Home Assistant device registry info for this vacuum."""
        from homeassistant.helpers.device_registry import DeviceInfo

        return DeviceInfo(
            identifiers={(DOMAIN, self.serial_number)},
            name=f"Dyson {self.serial_number}",
            manufacturer="Dyson",
            model="LEC floor-care vacuum",
            model_id=self.state.hardware_module,
            serial_number=self.serial_number,
            sw_version=self.firmware_version,
            hw_version=(
                f"{self.state.hardware_module}/{self.state.hardware_variant}"
                if self.state.hardware_module
                else None
            ),
        )
