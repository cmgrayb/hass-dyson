"""Test constants."""

from custom_components.dyson_alt.const import DEFAULT_TIMEOUT, DOMAIN


def test_domain():
    """Test domain constant."""
    assert DOMAIN == "dyson_alt"


def test_default_timeout():
    """Test default timeout constant."""
    assert DEFAULT_TIMEOUT == 10
