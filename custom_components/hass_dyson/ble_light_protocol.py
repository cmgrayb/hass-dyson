"""Dyson lighting attribute framing and value encodings."""

from __future__ import annotations

import hashlib
import hmac
import math
import os
import struct
from datetime import date
from enum import IntEnum

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class LightAttribute(IntEnum):
    """Lighting attributes carried by the authenticated message channel."""

    LATITUDE = 0x2003
    LONGITUDE = 0x2004
    TIMEZONE = 0x2005
    WAKE_UP_BRIGHTNESS = 0x2006
    WAKE_UP_PERIOD = 0x2007
    BOOST_MODE = 0x2009
    DAYLIGHT_MODE = 0x2013
    SUNRISE_TIME = 0x2014
    SUNSET_TIME = 0x2015
    BASELINE_BRIGHTNESS = 0x2017
    BASELINE_COLOUR_TEMPERATURE = 0x2018
    YEAR_OF_BIRTH = 0x201A
    AGE_ADJUST_MODE = 0x201B
    DND_MODE = 0x201C
    DAYLIGHT_SAVING_ADJUSTMENT = 0x201D
    STUDY_MODE = 0x201E
    RELAX_MODE = 0x201F
    PRECISION_MODE = 0x2021
    DND_START_TIME = 0x2023
    DND_END_TIME = 0x2024
    AGE_TIMESTAMP = 0x2025
    AWAY_MODE = 0x2026
    AWAY_MODE_START_DATE = 0x2028
    PERSONAL_DAYLIGHT_MODE = 0x2029
    LAST_FAULT = 0x2030
    PENULTIMATE_FAULT = 0x2031
    WAKE_UP_SCHEDULE_TOGGLE = 0x2032


MODE_ATTRIBUTES = {
    "daylight": LightAttribute.DAYLIGHT_MODE,
    "study": LightAttribute.STUDY_MODE,
    "relax": LightAttribute.RELAX_MODE,
    "precision": LightAttribute.PRECISION_MODE,
}

READABLE_ATTRIBUTES = (
    *MODE_ATTRIBUTES.values(),
    LightAttribute.DND_MODE,
    LightAttribute.AWAY_MODE,
    LightAttribute.AGE_ADJUST_MODE,
    LightAttribute.PERSONAL_DAYLIGHT_MODE,
    LightAttribute.WAKE_UP_SCHEDULE_TOGGLE,
    LightAttribute.BASELINE_BRIGHTNESS,
    LightAttribute.BASELINE_COLOUR_TEMPERATURE,
    LightAttribute.WAKE_UP_BRIGHTNESS,
    LightAttribute.SUNRISE_TIME,
    LightAttribute.SUNSET_TIME,
    LightAttribute.DND_START_TIME,
    LightAttribute.DND_END_TIME,
    LightAttribute.AWAY_MODE_START_DATE,
    LightAttribute.YEAR_OF_BIRTH,
    LightAttribute.LATITUDE,
    LightAttribute.LONGITUDE,
    LightAttribute.TIMEZONE,
)


def parse_attribute_message(opcode: int, body: bytes) -> tuple[int, int, bytes]:
    """Validate a read/write/subscription response or pushed attribute value."""
    if len(body) < 2:
        raise ValueError("Truncated attribute ID")
    attribute = int.from_bytes(body[:2], "little")
    if opcode == 0x98 and len(body) == 2:
        return attribute, 0, b""
    if opcode == 0x94 and len(body) == 3:
        return attribute, body[2], b""
    if opcode not in (0x91, 0x97):
        raise ValueError("Invalid attribute response")
    offset = 3 if opcode == 0x91 else 2
    if len(body) < offset + 2:
        raise ValueError("Truncated attribute length")
    status = body[2] if opcode == 0x91 else 0
    length = int.from_bytes(body[offset : offset + 2], "little")
    value = body[offset + 2 :]
    if length != len(value):
        raise ValueError("Attribute length mismatch")
    return attribute, status, value


def encode_timezone(offset_seconds: int) -> bytes:
    """Encode the app's HH.MM-style timezone float, including negative offsets."""
    if not -86400 < offset_seconds < 86400:
        raise ValueError("Invalid timezone offset")
    hours = offset_seconds / 3600
    whole = math.trunc(hours)
    return struct.pack("<f", whole + (hours - whole) * 0.6)


def encode_dst(fields: bytes) -> bytes:
    """Pack eleven cloud fields into the app's eight-byte DST rule record."""
    if len(fields) != 11 or any(fields[index] > 15 for index in (0, 1, 3, 6, 7, 9)):
        raise ValueError("Invalid DST rule fields")
    return bytes(
        (
            fields[0] | (fields[1] << 4),
            fields[2],
            fields[4],
            fields[5],
            fields[6] | (fields[7] << 4),
            fields[8],
            fields[10],
            fields[9] | (fields[3] << 4),
        )
    )


def encode_away_date(value: date) -> bytes:
    """Encode the native numeric DDMMYYYY representation, not a timestamp."""
    return int(value.strftime("%d%m%Y")).to_bytes(4, "little")


def decode_away_date(value: bytes) -> date | None:
    """Decode a valid native date; treat unset or malformed values as unknown."""
    if len(value) != 4 or value == b"\0" * 4:
        return None
    text = f"{int.from_bytes(value, 'little'):08d}"
    try:
        return date(int(text[4:]), int(text[2:4]), int(text[:2]))
    except ValueError:
        return None


def _sensitive_key(raw_ltk: bytes) -> bytes:
    if len(raw_ltk) != 16:
        raise ValueError("Invalid LTK length")
    return HKDF(
        algorithm=hashes.SHA256(), length=16, salt=b"", info=b"SENSITIVE_STATE\0"
    ).derive(raw_ltk)


def encode_birth_year(year: int, raw_ltk: bytes) -> bytes:
    """Protect year of birth using a distinct key context from BLE auth."""
    if not 1900 <= year <= date.today().year:
        raise ValueError("Invalid year of birth")
    key = _sensitive_key(raw_ltk)
    iv = os.urandom(16)
    plaintext = year.to_bytes(2, "little") + bytes(14)
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    return iv + ciphertext + hmac.new(key, ciphertext, hashlib.sha256).digest()


def decode_birth_year(value: bytes, raw_ltk: bytes) -> int | None:
    """Verify sensitive-state data before returning a plausible birth year."""
    if len(value) != 64:
        return None
    key = _sensitive_key(raw_ltk)
    iv, ciphertext, mac = value[:16], value[16:32], value[32:]
    if not hmac.compare_digest(hmac.new(key, ciphertext, hashlib.sha256).digest(), mac):
        return None
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    year = int.from_bytes(plaintext[:2], "little")
    if plaintext[2:] != bytes(14) or not 1900 <= year <= date.today().year:
        return None
    return year
