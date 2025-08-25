"""Test basic functionality without Home Assistant dependencies."""

import sys
from pathlib import Path

# Add the custom_components directory to the path
custom_components_path = Path(__file__).parent.parent / "custom_components"
sys.path.insert(0, str(custom_components_path))


def test_const_import():
    """Test that we can import constants."""
    # Import const.py directly without going through __init__.py
    from dyson_alt.const import DEFAULT_TIMEOUT, DOMAIN

    assert DOMAIN == "dyson_alt"
    assert DEFAULT_TIMEOUT == 10


def test_development_tools():
    """Test that development tools are working."""
    # This test passes if we can run it, indicating pytest is working
    assert True
