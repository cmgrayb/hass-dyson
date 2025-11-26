"""
Streamlined coverage enhancement tests for __init__.py module.

This file focuses on the stable, working tests that provide reliable coverage
enhancement for __init__.py, specifically targeting platform determination logic
which covers critical missing lines and helps push overall coverage toward 75%.
"""

from unittest.mock import Mock

from custom_components.hass_dyson import _get_platforms_for_device
from custom_components.hass_dyson.const import CONF_DISCOVERY_METHOD, DISCOVERY_CLOUD


class TestPlatformDetermination:
    """Test platform determination logic - stable tests that enhance coverage."""

    def test_get_platforms_for_vacuum_device(self):
        """Test platform determination for vacuum devices."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["robot"]
        mock_coordinator.device_capabilities = []
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        assert "vacuum" in platforms
        assert "sensor" in platforms
        assert "binary_sensor" in platforms
        assert "button" in platforms
        assert "update" in platforms

    def test_get_platforms_for_fan_device_with_capabilities(self):
        """Test platform determination for fan with advanced capabilities."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["ec"]
        mock_coordinator.device_capabilities = [
            "Scheduling",
            "AdvanceOscillationDay1",
            "Heating",
        ]
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        assert "fan" in platforms
        assert "number" in platforms
        assert "select" in platforms
        assert "switch" in platforms
        assert "climate" in platforms
        assert "update" in platforms

    def test_get_platforms_for_local_device(self):
        """Test platform determination for locally discovered device."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["ec"]
        mock_coordinator.device_capabilities = []
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: "local"}

        platforms = _get_platforms_for_device(mock_coordinator)

        # Should not include update platform for local devices
        assert "update" not in platforms
        assert "fan" in platforms
        assert "sensor" in platforms

    def test_get_platforms_deduplication(self):
        """Test platform list deduplication."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["ec"]
        mock_coordinator.device_capabilities = ["Scheduling"]  # This adds number/select
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        # Should not have duplicates
        assert len(platforms) == len(set(platforms))
        assert platforms.count("number") == 1
        assert platforms.count("select") == 1

    def test_get_platforms_for_flrc_category(self):
        """Test platform determination for FLRC category devices."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["flrc"]
        mock_coordinator.device_capabilities = []
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        assert "vacuum" in platforms
        assert "update" in platforms

    def test_get_platforms_switch_capability_logic(self):
        """Test switch platform logic based on capabilities."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["ec"]
        mock_coordinator.device_capabilities = ["Switch"]
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        assert "switch" in platforms

    def test_get_platforms_multi_category_handling(self):
        """Test platform determination with multiple device categories."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["ec", "light"]  # Multiple categories
        mock_coordinator.device_capabilities = []
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        # Should include platforms for EC devices (no climate without Heating capability)
        assert "fan" in platforms
        assert "switch" in platforms

    def test_get_platforms_empty_categories(self):
        """Test platform determination with empty device categories."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = []  # Empty categories
        mock_coordinator.device_capabilities = []
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        # Should still include base platforms
        assert "sensor" in platforms
        assert "binary_sensor" in platforms
        assert "button" in platforms
        assert "update" in platforms

    def test_get_platforms_unknown_category(self):
        """Test platform determination with unknown device category."""
        mock_coordinator = Mock()
        mock_coordinator.device_category = ["unknown_category"]
        mock_coordinator.device_capabilities = []
        mock_coordinator.config_entry.data = {CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD}

        platforms = _get_platforms_for_device(mock_coordinator)

        # Should include base platforms even for unknown categories
        assert "sensor" in platforms
        assert "binary_sensor" in platforms
        assert "button" in platforms
        assert "update" in platforms

        # Should not include category-specific platforms
        assert "fan" not in platforms
        assert "vacuum" not in platforms
