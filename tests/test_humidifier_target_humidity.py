"""Tests for humidifier_target_humidity in device_utils."""

import pytest

from custom_components.hass_dyson.device_utils import humidifier_target_humidity


@pytest.mark.parametrize(
    ("product_state", "expected"),
    [
        ({"haut": "ON", "rect": "0045", "humt": "0040"}, 45),
        ({"haut": "OFF", "rect": "0045", "humt": "0040"}, 40),
        ({"haut": "ON", "rect": "0000", "humt": "0050"}, 50),
        ({"haut": "ON", "rect": "OFF", "humt": "0030"}, 30),
        ({"haut": "ON", "rect": None, "humt": "0060"}, 60),
        ({"humt": "0000"}, None),
        ({"humt": "abcd"}, None),
        ({}, None),
    ],
)
def test_humidifier_target_humidity(product_state, expected):
    """Auto mode reads rect, manual mode humt; invalid values are skipped."""
    assert humidifier_target_humidity(product_state) == expected
