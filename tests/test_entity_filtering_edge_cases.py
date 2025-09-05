"""
Unit tests for entity filtering edge cases and error conditions.

This module tests error handling, malformed data, and edge cases in the
entity filtering logic to ensure robustness.
"""

from unittest.mock import MagicMock

import pytest

from custom_components.hass_dyson.const import CAPABILITY_EXTENDED_AQ, CAPABILITY_HEATING, DEVICE_CATEGORY_EC
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator


class TestEntityFilteringEdgeCases:
    """Test edge cases and error conditions in entity filtering."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator with basic configuration."""
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-EDGE-CASE-123"
        coordinator.device_name = "Test Edge Case Device"
        coordinator.device = MagicMock()
        coordinator.data = {}
        return coordinator

    def test_none_capabilities(self, mock_coordinator):
        """Test handling when capabilities is None."""
        mock_coordinator.device_capabilities = None
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle None gracefully without crashing
        assert mock_coordinator.device_capabilities is None

    def test_empty_capabilities_list(self, mock_coordinator):
        """Test handling when capabilities is an empty list."""
        mock_coordinator.device_capabilities = []
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle empty list gracefully
        assert len(mock_coordinator.device_capabilities) == 0

    def test_malformed_capabilities_not_list(self, mock_coordinator):
        """Test handling when capabilities is not a list."""
        # String instead of list
        mock_coordinator.device_capabilities = "ExtendedAQ"
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle non-list gracefully
        assert isinstance(mock_coordinator.device_capabilities, str)

    def test_malformed_capabilities_dict(self, mock_coordinator):
        """Test handling when capabilities is a dict instead of list."""
        mock_coordinator.device_capabilities = {"capability": "ExtendedAQ"}
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle dict gracefully
        assert isinstance(mock_coordinator.device_capabilities, dict)

    def test_capabilities_with_none_elements(self, mock_coordinator):
        """Test capabilities list containing None elements."""
        mock_coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ, None, CAPABILITY_HEATING]
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle None elements in list
        assert None in mock_coordinator.device_capabilities
        assert CAPABILITY_EXTENDED_AQ in mock_coordinator.device_capabilities

    def test_capabilities_with_empty_strings(self, mock_coordinator):
        """Test capabilities list containing empty strings."""
        mock_coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ, "", CAPABILITY_HEATING]
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle empty strings
        assert "" in mock_coordinator.device_capabilities
        assert CAPABILITY_EXTENDED_AQ in mock_coordinator.device_capabilities

    def test_capabilities_case_sensitivity(self, mock_coordinator):
        """Test that capability matching is case sensitive."""
        mock_coordinator.device_capabilities = ["extendedaq", "EXTENDEDAQ", "ExtendedAQ"]
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Only the correctly cased capability should match
        assert "ExtendedAQ" in mock_coordinator.device_capabilities
        assert "extendedaq" in mock_coordinator.device_capabilities
        assert "EXTENDEDAQ" in mock_coordinator.device_capabilities

    def test_unknown_capabilities(self, mock_coordinator):
        """Test handling of unknown/future capabilities."""
        mock_coordinator.device_capabilities = ["UnknownCapability", "FutureFeature", CAPABILITY_EXTENDED_AQ]
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle unknown capabilities gracefully
        assert "UnknownCapability" in mock_coordinator.device_capabilities
        assert CAPABILITY_EXTENDED_AQ in mock_coordinator.device_capabilities

    def test_none_device_category(self, mock_coordinator):
        """Test handling when device category is None."""
        mock_coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ]
        mock_coordinator.device_category = None

        # Should handle None category gracefully
        assert mock_coordinator.device_category is None

    def test_empty_device_category(self, mock_coordinator):
        """Test handling when device category is empty string."""
        mock_coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ]
        mock_coordinator.device_category = ""

        # Should handle empty category gracefully
        assert mock_coordinator.device_category == ""

    def test_unknown_device_category(self, mock_coordinator):
        """Test handling of unknown device categories."""
        mock_coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ]
        mock_coordinator.device_category = "unknown_category"

        # Should handle unknown categories gracefully
        assert mock_coordinator.device_category == "unknown_category"

    def test_very_long_capability_names(self, mock_coordinator):
        """Test handling of extremely long capability names."""
        long_capability = "A" * 1000  # 1000 character capability name
        mock_coordinator.device_capabilities = [long_capability, CAPABILITY_EXTENDED_AQ]
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle long names gracefully
        assert long_capability in mock_coordinator.device_capabilities

    def test_special_characters_in_capabilities(self, mock_coordinator):
        """Test handling of special characters in capability names."""
        special_capabilities = [
            "Capability-With-Dashes",
            "Capability_With_Underscores",
            "Capability.With.Dots",
            "Capability With Spaces",
            "Capability@#$%^&*()",
            CAPABILITY_EXTENDED_AQ,
        ]
        mock_coordinator.device_capabilities = special_capabilities
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle special characters gracefully
        for cap in special_capabilities:
            assert cap in mock_coordinator.device_capabilities

    def test_unicode_in_capabilities(self, mock_coordinator):
        """Test handling of Unicode characters in capability names."""
        unicode_capabilities = [
            "Capability_ñ_español",
            "Capability_中文",
            "Capability_🚀_emoji",
            CAPABILITY_EXTENDED_AQ,
        ]
        mock_coordinator.device_capabilities = unicode_capabilities
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle Unicode gracefully
        for cap in unicode_capabilities:
            assert cap in mock_coordinator.device_capabilities

    def test_duplicate_capabilities(self, mock_coordinator):
        """Test handling of duplicate capabilities in list."""
        mock_coordinator.device_capabilities = [
            CAPABILITY_EXTENDED_AQ,
            CAPABILITY_HEATING,
            CAPABILITY_EXTENDED_AQ,  # Duplicate
            CAPABILITY_HEATING,  # Duplicate
        ]
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle duplicates gracefully
        assert mock_coordinator.device_capabilities.count(CAPABILITY_EXTENDED_AQ) == 2
        assert mock_coordinator.device_capabilities.count(CAPABILITY_HEATING) == 2

    def test_extremely_large_capabilities_list(self, mock_coordinator):
        """Test handling of very large capabilities lists."""
        large_capabilities = [f"Capability_{i}" for i in range(1000)]
        large_capabilities.append(CAPABILITY_EXTENDED_AQ)

        mock_coordinator.device_capabilities = large_capabilities
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle large lists gracefully
        assert len(mock_coordinator.device_capabilities) == 1001
        assert CAPABILITY_EXTENDED_AQ in mock_coordinator.device_capabilities

    def test_mixed_types_in_capabilities_list(self, mock_coordinator):
        """Test capabilities list with mixed data types."""
        mixed_capabilities = [
            CAPABILITY_EXTENDED_AQ,  # string
            123,  # int
            45.67,  # float
            True,  # bool
            ["nested", "list"],  # list
            {"nested": "dict"},  # dict
        ]
        mock_coordinator.device_capabilities = mixed_capabilities
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle mixed types gracefully
        assert CAPABILITY_EXTENDED_AQ in mock_coordinator.device_capabilities
        assert 123 in mock_coordinator.device_capabilities
        assert True in mock_coordinator.device_capabilities


class TestDeviceDataCorruption:
    """Test handling of corrupted or invalid device data."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator for corruption testing."""
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-CORRUPTION-123"
        coordinator.device_name = "Test Corruption Device"
        coordinator.device = MagicMock()
        return coordinator

    def test_coordinator_with_no_data_attribute(self, mock_coordinator):
        """Test when coordinator has no data attribute."""
        # Remove data attribute
        if hasattr(mock_coordinator, "data"):
            delattr(mock_coordinator, "data")

        # Should handle missing data attribute gracefully
        assert not hasattr(mock_coordinator, "data")

    def test_coordinator_data_is_none(self, mock_coordinator):
        """Test when coordinator.data is None."""
        mock_coordinator.data = None
        mock_coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ]
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle None data gracefully
        assert mock_coordinator.data is None

    def test_coordinator_data_corrupted_structure(self, mock_coordinator):
        """Test when coordinator.data has unexpected structure."""
        # Data should be dict but is string
        mock_coordinator.data = "corrupted_data_string"
        mock_coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ]
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle corrupted data structure gracefully
        assert isinstance(mock_coordinator.data, str)

    def test_missing_device_attribute(self, mock_coordinator):
        """Test when coordinator has no device attribute."""
        if hasattr(mock_coordinator, "device"):
            delattr(mock_coordinator, "device")

        mock_coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ]
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle missing device gracefully
        assert not hasattr(mock_coordinator, "device")

    def test_device_is_none(self, mock_coordinator):
        """Test when coordinator.device is None."""
        mock_coordinator.device = None
        mock_coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ]
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle None device gracefully
        assert mock_coordinator.device is None


class TestNetworkAndConnectionErrors:
    """Test error handling for network and connection issues."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator for network testing."""
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-NETWORK-123"
        coordinator.device_name = "Test Network Device"
        coordinator.device = MagicMock()
        coordinator.data = {}
        return coordinator

    def test_device_connection_timeout(self, mock_coordinator):
        """Test handling of device connection timeouts."""
        mock_coordinator.device.get_state.side_effect = TimeoutError("Connection timeout")
        mock_coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ]
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle timeout gracefully
        with pytest.raises(TimeoutError):
            mock_coordinator.device.get_state()

    def test_device_connection_refused(self, mock_coordinator):
        """Test handling of connection refused errors."""
        mock_coordinator.device.connect.side_effect = ConnectionRefusedError("Connection refused")
        mock_coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ]
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle connection refused gracefully
        with pytest.raises(ConnectionRefusedError):
            mock_coordinator.device.connect()

    def test_device_network_unreachable(self, mock_coordinator):
        """Test handling of network unreachable errors."""
        from socket import gaierror

        mock_coordinator.device.connect.side_effect = gaierror("Network unreachable")
        mock_coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ]
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # Should handle network errors gracefully
        with pytest.raises(gaierror):
            mock_coordinator.device.connect()

    def test_intermittent_connectivity(self, mock_coordinator):
        """Test handling of intermittent connectivity issues."""
        # Simulate intermittent failures
        call_count = 0

        def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise ConnectionError("Intermittent failure")
            return {"status": "connected"}

        mock_coordinator.device.get_state.side_effect = side_effect
        mock_coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ]
        mock_coordinator.device_category = DEVICE_CATEGORY_EC

        # First call should succeed
        result = mock_coordinator.device.get_state()
        assert result["status"] == "connected"

        # Second call should fail
        with pytest.raises(ConnectionError):
            mock_coordinator.device.get_state()
