"""Regression tests for the recovered lighting protocol (synthetic data only)."""

from datetime import date

import pytest

from custom_components.hass_dyson.ble_light_protocol import (
    decode_away_date,
    decode_birth_year,
    encode_away_date,
    encode_birth_year,
    encode_dst,
    encode_timezone,
    parse_attribute_message,
)


@pytest.mark.parametrize(
    "opcode,body,expected",
    [
        (0x91, bytes.fromhex("132000010001"), (0x2013, 0, b"\x01")),
        (0x91, bytes.fromhex("1320020000"), (0x2013, 2, b"")),
        (0x97, bytes.fromhex("1320010001"), (0x2013, 0, b"\x01")),
        (0x94, bytes.fromhex("132001"), (0x2013, 1, b"")),
        (0x98, bytes.fromhex("1320"), (0x2013, 0, b"")),
    ],
)
def test_attribute_messages(opcode, body, expected):
    assert parse_attribute_message(opcode, body) == expected


@pytest.mark.parametrize(
    "opcode,body",
    [
        (0x91, b"\x13"),
        (0x91, bytes.fromhex("132000020001")),
        (0x97, bytes.fromhex("1320")),
        (0x94, bytes.fromhex("13200000")),
        (0x98, bytes.fromhex("132000")),
    ],
)
def test_truncated_or_overlong_responses(opcode, body):
    with pytest.raises(ValueError):
        parse_attribute_message(opcode, body)


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (19800, "9a99a940"),
        (20700, "6666ae40"),
        (-12600, "333353c0"),
        (0, "00000000"),
    ],
)
def test_timezone_is_hhmm_float_not_decimal_hours(seconds, expected):
    assert encode_timezone(seconds).hex() == expected


def test_away_date_is_decimal_ddmmyyyy_not_unix():
    value = date(2026, 11, 1)
    encoded = encode_away_date(value)
    assert int.from_bytes(encoded, "little") == 1112026
    assert decode_away_date(encoded) == value
    assert decode_away_date(bytes(4)) is None
    assert decode_away_date(b"\xff" * 4) is None


def test_dst_cloud_fields_are_bit_packed_not_copied():
    cloud = bytes([3, 2, 25, 1, 2, 60, 10, 4, 31, 7, 3])
    assert encode_dst(cloud) == bytes.fromhex("2319023c4a1f0317")
    assert encode_dst(bytes(11)) == bytes(8)
    with pytest.raises(ValueError):
        encode_dst(bytes(8))
    with pytest.raises(ValueError):
        encode_dst(bytes([255]) * 11)


def test_sensitive_state_has_independent_key_and_verified_mac():
    key = bytes(range(16))
    encoded = encode_birth_year(1990, key)
    assert len(encoded) == 64
    assert decode_birth_year(encoded, key) == 1990
    assert decode_birth_year(encoded, bytes(16)) is None
    corrupted = encoded[:20] + bytes([encoded[20] ^ 1]) + encoded[21:]
    assert decode_birth_year(corrupted, key) is None
    assert decode_birth_year(encoded[:-1], key) is None
    assert encode_birth_year(1990, key) != encoded


@pytest.mark.parametrize("year", [0, 1899, 9999])
def test_invalid_birth_year_is_rejected(year):
    with pytest.raises(ValueError):
        encode_birth_year(year, bytes(16))
