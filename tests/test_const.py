"""Test constants using pure pytest (migrated from pytest-homeassistant-custom-component)."""

from custom_components.hass_dyson.const import DEFAULT_TIMEOUT, DOMAIN


class TestDysonConstants:
    """Test constants using pure pytest approach."""

    def test_domain_constant(self):
        """Test domain constant is correctly defined."""
        assert DOMAIN == "hass_dyson"
        assert isinstance(DOMAIN, str)

    def test_default_timeout_constant(self):
        """Test default timeout constant is reasonable value."""
        assert DEFAULT_TIMEOUT == 10
        assert isinstance(DEFAULT_TIMEOUT, int)
        assert DEFAULT_TIMEOUT > 0  # Should be positive

    def test_domain_follows_ha_naming_conventions(self):
        """Test that domain follows Home Assistant naming conventions."""
        # Domain should be lowercase
        assert DOMAIN.islower()
        # Domain should not contain spaces
        assert " " not in DOMAIN
        # Domain should use underscores, not hyphens for Python module compatibility
        assert "-" not in DOMAIN or "_" in DOMAIN
