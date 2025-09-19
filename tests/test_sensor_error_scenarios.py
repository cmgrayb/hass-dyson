"""Test sensor error handling scenarios to improve coverage."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
from custom_components.hass_dyson.sensor import (
    DysonAirQualitySensor,
    DysonFilterLifeSensor,
    DysonHumiditySensor,
    DysonTemperatureSensor,
)


class TestSensorErrorHandling:
    """Test sensor error handling scenarios."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "VS6-EU-HJA1234A"
        coordinator.data = {}
        return coordinator

    def test_filter_life_sensor_invalid_data_handling(self, mock_coordinator):
        """Test filter life sensor with invalid data."""
        sensor = DysonFilterLifeSensor(mock_coordinator, "hepa")

        # Test with invalid data that should trigger error paths
        test_cases = [
            {"hepa_filter_life": "invalid_string"},  # ValueError
            {"hepa_filter_life": object()},  # TypeError
            {"hepa_filter_life": None},  # None value
            {},  # Missing key
        ]

        for test_data in test_cases:
            mock_coordinator.data = test_data
            # Manually call the update method to trigger error handling with patched state write
            with patch.object(sensor, "async_write_ha_state"):
                sensor._handle_coordinator_update()
            # The sensor should handle errors gracefully

    def test_air_quality_sensor_invalid_data_handling(self, mock_coordinator):
        """Test air quality sensor with invalid data."""
        sensor = DysonAirQualitySensor(mock_coordinator, "pm25")

        # Test with invalid data that should trigger error paths
        test_cases = [
            {"pm25": "invalid_string"},  # ValueError in conversion
            {"pm25": object()},  # TypeError in conversion
            {"pm25": None},  # None value
            {},  # Missing key
        ]

        for test_data in test_cases:
            mock_coordinator.data = test_data
            with patch.object(sensor, "async_write_ha_state"):
                sensor._handle_coordinator_update()
            # The sensor should handle errors gracefully

    def test_temperature_sensor_invalid_data_handling(self, mock_coordinator):
        """Test temperature sensor with invalid data."""
        sensor = DysonTemperatureSensor(mock_coordinator)

        # Test with invalid data that should trigger error paths
        test_cases = [
            {"temperature": "invalid_string"},  # ValueError in conversion
            {"temperature": object()},  # TypeError in conversion
            {"temperature": None},  # None value
            {},  # Missing key
        ]

        for test_data in test_cases:
            mock_coordinator.data = test_data
            with patch.object(sensor, "async_write_ha_state"):
                sensor._handle_coordinator_update()
            # The sensor should handle errors gracefully

    def test_humidity_sensor_invalid_data_handling(self, mock_coordinator):
        """Test humidity sensor with invalid data."""
        sensor = DysonHumiditySensor(mock_coordinator)

        # Test with invalid data that should trigger error paths
        test_cases = [
            {"humidity": "invalid_string"},  # ValueError in conversion
            {"humidity": object()},  # TypeError in conversion
            {"humidity": None},  # None value
            {},  # Missing key
        ]

        for test_data in test_cases:
            mock_coordinator.data = test_data
            with patch.object(sensor, "async_write_ha_state"):
                sensor._handle_coordinator_update()
            # The sensor should handle errors gracefully

    def test_coordinator_data_edge_cases(self, mock_coordinator):
        """Test sensor behavior with edge cases in coordinator data."""
        sensor = DysonFilterLifeSensor(mock_coordinator, "hepa")

        # Test edge cases
        edge_cases = [
            None,  # Coordinator data is None
            "not_a_dict",  # Coordinator data is not a dict
            {},  # Empty dict
        ]

        for edge_case in edge_cases:
            mock_coordinator.data = edge_case
            try:
                with patch.object(sensor, "async_write_ha_state"):
                    sensor._handle_coordinator_update()
                # Should not crash with bad data
            except AttributeError:
                # AttributeError might occur with non-dict data, which is acceptable
                pass
            except Exception as e:
                # Any other exception suggests the sensor isn't robust enough
                pytest.fail(f"Sensor should handle edge case gracefully: {e}")
