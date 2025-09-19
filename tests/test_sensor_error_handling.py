"""Test sensor error handling to improve coverage."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.hass_dyson.sensor import (
    DysonAirQualitySensor,
    DysonFilterLifeSensor,
    DysonHumiditySensor,
    DysonTemperatureSensor,
)


class TestSensorErrorHandling:
    """Test sensor error handling scenarios to improve coverage."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock()
        coordinator.serial_number = "TEST-SERIAL-123"
        coordinator.device_name = "Test Device"
        coordinator.device = MagicMock()
        return coordinator

    def test_filter_life_sensor_invalid_data_conversion(self, mock_coordinator):
        """Test filter life sensor with data that causes conversion errors."""
        sensor = DysonFilterLifeSensor(mock_coordinator, "hepa")

        # Test ValueError case - string that can't be converted to int
        mock_coordinator.data = {"hepa_filter_life": "invalid_number"}
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
        assert sensor._attr_native_value is None

        # Test TypeError case - object that can't be converted
        mock_coordinator.data = {"hepa_filter_life": object()}
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
        assert sensor._attr_native_value is None

    def test_air_quality_sensor_pm25_invalid_conversion(self, mock_coordinator):
        """Test PM2.5 air quality sensor with invalid data conversion."""
        sensor = DysonAirQualitySensor(mock_coordinator, "pm25")

        # Test with invalid string that should cause ValueError
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.pm25 = None  # This triggers the data lookup
        mock_coordinator.data = {"pm25": "invalid_float"}

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
        assert sensor._attr_native_value is None

    def test_air_quality_sensor_no2_invalid_conversion(self, mock_coordinator):
        """Test NO2 air quality sensor with invalid data conversion."""
        sensor = DysonAirQualitySensor(mock_coordinator, "no2")

        # Test with invalid data
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.no2 = None
        mock_coordinator.data = {"no2": "not_a_number"}

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
        assert sensor._attr_native_value is None

    def test_temperature_sensor_invalid_conversion(self, mock_coordinator):
        """Test temperature sensor with invalid data conversion."""
        sensor = DysonTemperatureSensor(mock_coordinator)

        # Test with device returning None (triggers data lookup)
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.temperature = None
        mock_coordinator.data = {"temperature": "invalid_temp"}

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
        assert sensor._attr_native_value is None

    def test_humidity_sensor_invalid_conversion(self, mock_coordinator):
        """Test humidity sensor with invalid data conversion."""
        sensor = DysonHumiditySensor(mock_coordinator)

        # Test with device returning None (triggers data lookup)
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.humidity = None
        mock_coordinator.data = {"hact": "invalid_humidity"}

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
        assert sensor._attr_native_value is None
