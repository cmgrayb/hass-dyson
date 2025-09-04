"""Test basic functionality without Home Assistant dependencies."""

import sys
from pathlib import Path

# Add the custom_components directory to the path
custom_components_path = Path(__file__).parent.parent / "custom_components"
sys.path.insert(0, str(custom_components_path))


def test_const_import():
    """Test that we can import constants."""
    # Import const.py directly without going through __init__.py
    from hass_dyson.const import (
        CONF_AUTO_ADD_DEVICES,
        CONF_POLL_FOR_DEVICES,
        DEFAULT_AUTO_ADD_DEVICES,
        DEFAULT_POLL_FOR_DEVICES,
        DEFAULT_TIMEOUT,
        DOMAIN,
    )

    assert DOMAIN == "hass-dyson"
    assert DEFAULT_TIMEOUT == 10
    assert CONF_POLL_FOR_DEVICES == "poll_for_devices"
    assert CONF_AUTO_ADD_DEVICES == "auto_add_devices"
    assert DEFAULT_POLL_FOR_DEVICES is True
    assert DEFAULT_AUTO_ADD_DEVICES is True


def test_development_tools():
    """Test that development tools are working."""
    # This test passes if we can run it, indicating pytest is working
    assert True
