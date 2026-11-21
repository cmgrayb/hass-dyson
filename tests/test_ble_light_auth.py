"""Authenticate fresh synthetic sessions and reject truncated or replayed proofs."""

import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.ble_device import (
    DysonBLEDevice,
    DysonMessage,
    _aes_cbc_encrypt,
    hkdf_derive_aes_key,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault", [None, "truncated", "overlong", "bad_mac", "wrong_echo", "bad_status"]
)
async def test_reauth_requires_complete_mac_and_current_nonce(fault, caplog):
    """Known-answer simulation exercises the real proof-verification path."""
    ltk = bytes(range(16))
    key = hkdf_derive_aes_key(ltk)
    nonce = b"n" * 16
    echo = b"x" * 16 if fault == "wrong_echo" else nonce
    iv = bytes(16)
    ciphertext = _aes_cbc_encrypt(key, iv, echo + b"d" * 16)
    mac = hmac.new(key, ciphertext, hashlib.sha256).digest()
    body = b"\0\0" + iv + ciphertext + mac
    if fault == "truncated":
        body = body[:50]
    elif fault == "overlong":
        body += b"\0"
    elif fault == "bad_mac":
        body = body[:-1] + bytes((body[-1] ^ 1,))
    elif fault == "bad_status":
        body = b"\1" + body[1:]
    device = DysonBLEDevice(
        MagicMock(),
        "TEST-LAMP",
        "AA:BB:CC:DD:EE:FF",
        ltk.hex(),
        "12345678-1234-5678-1234-567812345678",
    )
    device._send_message = AsyncMock()
    device._wait_for_type = AsyncMock(
        side_effect=[
            DysonMessage(0x0B, bytes(16)),
            DysonMessage(0x07, body),
            DysonMessage(0x26, bytes(10)),
        ]
    )
    with patch(
        "custom_components.hass_dyson.ble_device.os.urandom", return_value=nonce
    ):
        if fault is not None:
            with pytest.raises(RuntimeError, match="authentication"):
                await device._reauth_with_ltk()
            assert all(
                call.args[0] != 0x08 for call in device._send_message.call_args_list
            )
        else:
            await device._reauth_with_ltk()
            assert [call.args[0] for call in device._send_message.call_args_list] == [
                0x0A,
                0x06,
                0x08,
            ]
    assert ltk.hex() not in caplog.text
    assert (b"d" * 16).hex() not in caplog.text
