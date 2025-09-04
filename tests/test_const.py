"""Test constants."""

from custom_components.hass_dyson.const import DEFAULT_TIMEOUT, DOMAIN


def test_domain():
    """Test domain constant."""
    assert DOMAIN == "hass-dyson"


def test_default_timeout():
    """Test default timeout constant."""
    assert DEFAULT_TIMEOUT == 10
