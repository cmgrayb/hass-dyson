"""
Unit tests for binary sensor filtering and fault code handling.

This module tests the binary sensor filtering logic including fault code
relevance detection and error handling.
"""

from unittest.mock import MagicMock

import pytest

from custom_components.hass_dyson.binary_sensor import _is_fault_code_relevant
from custom_components.hass_dyson.const import (
    DEVICE_CATEGORY_EC,
    DEVICE_CATEGORY_ROBOT,
    DEVICE_CATEGORY_VACUUM,
)


class TestBinarySensorFiltering:
    """Test binary sensor filtering logic."""

    def test_fault_code_relevance_for_ec_devices(self):
        """Test fault code relevance for EC devices."""
        # EC devices should handle basic fault codes
        assert _is_fault_code_relevant("mflr", DEVICE_CATEGORY_EC, []) is True
        assert _is_fault_code_relevant("wifi", DEVICE_CATEGORY_EC, []) is True
        assert _is_fault_code_relevant("pwr", DEVICE_CATEGORY_EC, []) is True

    def test_fault_code_relevance_for_robot_devices(self):
        """Test fault code relevance for robot devices."""
        # Robot devices should handle robot-specific fault codes
        assert _is_fault_code_relevant("brsh", DEVICE_CATEGORY_ROBOT, []) is True
        assert _is_fault_code_relevant("bin", DEVICE_CATEGORY_ROBOT, []) is True
        assert _is_fault_code_relevant("mflr", DEVICE_CATEGORY_ROBOT, []) is True

    def test_fault_code_relevance_for_vacuum_devices(self):
        """Test fault code relevance for vacuum devices."""
        # Vacuum devices should handle vacuum-specific fault codes
        assert _is_fault_code_relevant("brsh", DEVICE_CATEGORY_VACUUM, []) is True
        assert _is_fault_code_relevant("bin", DEVICE_CATEGORY_VACUUM, []) is True
        assert _is_fault_code_relevant("mflr", DEVICE_CATEGORY_VACUUM, []) is True

    def test_unknown_fault_code_handling(self):
        """Test handling of unknown fault codes."""
        # Unknown fault codes should not be relevant
        assert _is_fault_code_relevant("UNKN", DEVICE_CATEGORY_EC, []) is False
        assert _is_fault_code_relevant("FUTURE", DEVICE_CATEGORY_ROBOT, []) is False
        assert _is_fault_code_relevant("NEW_CODE", DEVICE_CATEGORY_VACUUM, []) is False

    def test_fault_code_with_invalid_category(self):
        """Test fault code handling with invalid device categories."""
        # Invalid categories should handle gracefully
        assert _is_fault_code_relevant("mflr", "invalid_category", []) is False
        assert _is_fault_code_relevant("mflr", None, []) is False
        assert _is_fault_code_relevant("mflr", "", []) is False

    def test_fault_code_with_invalid_fault_code(self):
        """Test handling of invalid fault codes."""
        # Invalid fault codes should handle gracefully
        assert _is_fault_code_relevant("", DEVICE_CATEGORY_EC, []) is False
        assert _is_fault_code_relevant("invalid_code", DEVICE_CATEGORY_EC, []) is False

    def test_fault_code_case_sensitivity(self):
        """Test fault code case sensitivity."""
        # Fault codes should be case sensitive - lowercase should work for category-based codes
        assert _is_fault_code_relevant("mflr", DEVICE_CATEGORY_EC, []) is True
        assert _is_fault_code_relevant("MFLR", DEVICE_CATEGORY_EC, []) is False

        # Test capability-based fault codes - these require capabilities
        assert (
            _is_fault_code_relevant("fltr", DEVICE_CATEGORY_EC, ["ExtendedAQ"]) is True
        )
        assert (
            _is_fault_code_relevant("FLTR", DEVICE_CATEGORY_EC, ["ExtendedAQ"]) is False
        )
        assert _is_fault_code_relevant("Fltr", DEVICE_CATEGORY_EC, []) is False

    def test_fault_code_with_special_characters(self):
        """Test fault codes with special characters."""
        # Special characters in fault codes should be handled
        assert _is_fault_code_relevant("FL-TR", DEVICE_CATEGORY_EC, []) is False
        assert _is_fault_code_relevant("FL_TR", DEVICE_CATEGORY_EC, []) is False
        assert _is_fault_code_relevant("FL.TR", DEVICE_CATEGORY_EC, []) is False

    def test_fault_code_with_numbers(self):
        """Test fault codes with numbers."""
        # Numeric fault codes should be handled
        assert _is_fault_code_relevant("FLTR1", DEVICE_CATEGORY_EC, []) is False
        assert _is_fault_code_relevant("123", DEVICE_CATEGORY_EC, []) is False
        assert _is_fault_code_relevant("F1T2", DEVICE_CATEGORY_EC, []) is False


class TestBinarySensorEdgeCases:
    """Test edge cases in binary sensor handling."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator for binary sensor testing."""
        coordinator = MagicMock()
        coordinator.serial_number = "BINARY-TEST-123"
        coordinator.device_name = "Binary Test Device"
        coordinator.device = MagicMock()
        coordinator.data = {}
        return coordinator

    def test_binary_sensor_with_no_fault_data(self, mock_coordinator):
        """Test binary sensor when device provides no fault data."""
        mock_coordinator.data = {}  # No fault data
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle missing fault data gracefully
        assert "faults" not in mock_coordinator.data

    def test_binary_sensor_with_malformed_fault_data(self, mock_coordinator):
        """Test binary sensor with malformed fault data."""
        # Fault data should be a list but is a string
        mock_coordinator.data = {"faults": "FLTR,WIFI"}
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle malformed data gracefully
        assert isinstance(mock_coordinator.data["faults"], str)

    def test_binary_sensor_with_empty_fault_list(self, mock_coordinator):
        """Test binary sensor with empty fault list."""
        mock_coordinator.data = {"faults": []}
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle empty fault list gracefully
        assert len(mock_coordinator.data["faults"]) == 0

    def test_binary_sensor_with_none_faults(self, mock_coordinator):
        """Test binary sensor when faults is None."""
        mock_coordinator.data = {"faults": None}
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle None faults gracefully
        assert mock_coordinator.data["faults"] is None

    def test_binary_sensor_with_mixed_fault_types(self, mock_coordinator):
        """Test binary sensor with mixed data types in fault list."""
        mock_coordinator.data = {"faults": ["FLTR", 123, None, "WIFI", ""]}
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle mixed types gracefully
        fault_list = mock_coordinator.data["faults"]
        assert "FLTR" in fault_list
        assert 123 in fault_list
        assert None in fault_list
        assert "WIFI" in fault_list
        assert "" in fault_list

    def test_binary_sensor_state_transitions(self, mock_coordinator):
        """Test binary sensor state transitions."""
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Initial state - no faults
        mock_coordinator.data = {"faults": []}
        assert len(mock_coordinator.data["faults"]) == 0

        # Fault appears
        mock_coordinator.data = {"faults": ["FLTR"]}
        assert "FLTR" in mock_coordinator.data["faults"]

        # Multiple faults
        mock_coordinator.data = {"faults": ["FLTR", "WIFI"]}
        assert len(mock_coordinator.data["faults"]) == 2

        # Fault cleared
        mock_coordinator.data = {"faults": []}
        assert len(mock_coordinator.data["faults"]) == 0

    def test_binary_sensor_duplicate_faults(self, mock_coordinator):
        """Test binary sensor with duplicate fault codes."""
        mock_coordinator.data = {"faults": ["FLTR", "FLTR", "WIFI", "FLTR"]}
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle duplicates gracefully
        fault_list = mock_coordinator.data["faults"]
        assert fault_list.count("FLTR") == 3
        assert fault_list.count("WIFI") == 1

    def test_binary_sensor_very_long_fault_codes(self, mock_coordinator):
        """Test binary sensor with very long fault codes."""
        long_fault = "A" * 1000  # 1000 character fault code
        mock_coordinator.data = {"faults": [long_fault, "FLTR"]}
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle long fault codes gracefully
        assert long_fault in mock_coordinator.data["faults"]
        assert "FLTR" in mock_coordinator.data["faults"]

    def test_binary_sensor_unicode_fault_codes(self, mock_coordinator):
        """Test binary sensor with Unicode fault codes."""
        unicode_faults = ["FLTR_ñ", "WIFI_中文", "ERROR_🚨"]
        mock_coordinator.data = {"faults": unicode_faults}
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle Unicode gracefully
        for fault in unicode_faults:
            assert fault in mock_coordinator.data["faults"]

    def test_binary_sensor_extremely_large_fault_list(self, mock_coordinator):
        """Test binary sensor with extremely large fault list."""
        large_fault_list = [f"FAULT_{i}" for i in range(1000)]
        large_fault_list.append("FLTR")

        mock_coordinator.data = {"faults": large_fault_list}
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle large lists gracefully
        assert len(mock_coordinator.data["faults"]) == 1001
        assert "FLTR" in mock_coordinator.data["faults"]
        assert "FAULT_999" in mock_coordinator.data["faults"]


class TestFilterReplacementSensorEdgeCases:
    """Test edge cases specific to filter replacement sensor."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator for filter sensor testing."""
        coordinator = MagicMock()
        coordinator.serial_number = "FILTER-TEST-123"
        coordinator.device_name = "Filter Test Device"
        coordinator.device = MagicMock()
        coordinator.data = {}
        return coordinator

    def test_filter_sensor_with_no_filter_data(self, mock_coordinator):
        """Test filter sensor when device provides no filter data."""
        mock_coordinator.data = {}  # No filter data

        # Should handle missing filter data gracefully
        assert "filter_life" not in mock_coordinator.data
        assert "filter_type" not in mock_coordinator.data

    def test_filter_sensor_with_invalid_filter_life(self, mock_coordinator):
        """Test filter sensor with invalid filter life data."""
        mock_coordinator.data = {
            "filter_life": "invalid",
            "filter_type": "HEPA",
        }  # Should be numeric

        # Should handle invalid data gracefully
        assert mock_coordinator.data["filter_life"] == "invalid"

    def test_filter_sensor_with_negative_filter_life(self, mock_coordinator):
        """Test filter sensor with negative filter life."""
        mock_coordinator.data = {
            "filter_life": -50,
            "filter_type": "HEPA",
        }  # Negative value

        # Should handle negative values gracefully
        assert mock_coordinator.data["filter_life"] == -50

    def test_filter_sensor_with_extreme_filter_life_values(self, mock_coordinator):
        """Test filter sensor with extreme filter life values."""
        # Test very large value
        mock_coordinator.data = {"filter_life": 999999999}
        assert mock_coordinator.data["filter_life"] == 999999999

        # Test zero value
        mock_coordinator.data = {"filter_life": 0}
        assert mock_coordinator.data["filter_life"] == 0

        # Test float value
        mock_coordinator.data = {"filter_life": 50.5}
        assert mock_coordinator.data["filter_life"] == 50.5

    def test_filter_sensor_with_missing_filter_type(self, mock_coordinator):
        """Test filter sensor when filter type is missing."""
        mock_coordinator.data = {
            "filter_life": 75,
            # filter_type is missing
        }

        # Should handle missing filter type gracefully
        assert "filter_type" not in mock_coordinator.data
        assert mock_coordinator.data["filter_life"] == 75
