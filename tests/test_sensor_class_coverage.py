"""Extended error coverage tests for remaining sensor classes.

This module provides comprehensive error path testing for sensor classes
not covered in test_sensor_error_coverage.py. Focus areas:
1. DysonPM25Sensor - PM2.5 with p25r/pm25 fallback logic
2. DysonPM10Sensor - PM10 with p10r/pm10 fallback logic
3. DysonNO2Sensor - NO2 with range validation
4. DysonFormaldehydeSensor - HCHO with hchr/hcho fallback and NONE handling
5. Filter life sensors - HEPA and Carbon filters
6. WiFi and connection status sensors

Target: Additional 2-3% sensor.py coverage improvement (70% -> 72-73%)
Overall target: Reach 75% total coverage
"""

from unittest.mock import Mock, patch

import pytest

from custom_components.hass_dyson.sensor import (
    DysonCarbonFilterLifeSensor,
    DysonConnectionStatusSensor,
    DysonFormaldehydeSensor,
    DysonHEPAFilterLifeSensor,
    DysonNO2Sensor,
    DysonPM10Sensor,
    DysonPM25Sensor,
    DysonWiFiSensor,
)


class TestPM25SensorErrorHandling:
    """Test error handling in DysonPM25Sensor."""

    def test_handle_coordinator_update_key_error(self):
        """Test KeyError when environmental-data is missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM25-001"
        coordinator.data = {}  # Missing environmental-data key
        coordinator.device = Mock()

        sensor = DysonPM25Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_attribute_error(self):
        """Test AttributeError when data is None."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM25-002"
        coordinator.data = None  # Will cause AttributeError on .get()
        coordinator.device = Mock()

        sensor = DysonPM25Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error_inner(self):
        """Test ValueError in inner try block (invalid format)."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM25-003"
        coordinator.data = {"environmental-data": {"p25r": "INVALID"}}
        coordinator.device = Mock()

        sensor = DysonPM25Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error_inner(self):
        """Test TypeError in inner try block (wrong type)."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM25-004"
        coordinator.data = {"environmental-data": {"p25r": ["not", "a", "number"]}}
        coordinator.device = Mock()

        sensor = DysonPM25Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_out_of_range_value(self):
        """Test PM2.5 value out of valid range."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM25-005"
        coordinator.data = {"environmental-data": {"p25r": "1500"}}  # > 999
        coordinator.device = Mock()

        sensor = DysonPM25Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_fallback_to_pm25(self):
        """Test fallback from p25r to legacy pm25 key."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM25-006"
        coordinator.data = {"environmental-data": {"pm25": "50"}}  # No p25r
        coordinator.device = Mock()

        sensor = DysonPM25Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value == 50

    def test_handle_coordinator_update_value_error_outer(self):
        """Test ValueError in outer exception handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM25-007"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=ValueError("Data error"))
        coordinator.device = Mock()

        sensor = DysonPM25Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error_outer(self):
        """Test TypeError in outer exception handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM25-008"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=TypeError("Type error"))
        coordinator.device = Mock()

        sensor = DysonPM25Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test generic Exception in outer handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM25-009"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=Exception("Unexpected error"))
        coordinator.device = Mock()

        sensor = DysonPM25Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_sync_with_current_data_no_device(self):
        """Test _sync_with_current_data when device is None."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM25-010"
        coordinator.device = None

        sensor = DysonPM25Sensor(coordinator)
        sensor._sync_with_current_data()

        # Should not raise error

    def test_sync_with_current_data_no_environmental_data_attr(self):
        """Test _sync_with_current_data when device has no _environmental_data."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM25-011"
        coordinator.device = Mock()
        # Device without _environmental_data attribute

        sensor = DysonPM25Sensor(coordinator)
        sensor._sync_with_current_data()

        # Should not raise error


class TestPM10SensorErrorHandling:
    """Test error handling in DysonPM10Sensor."""

    def test_handle_coordinator_update_key_error(self):
        """Test KeyError when environmental-data is missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM10-001"
        coordinator.data = {}
        coordinator.device = Mock()

        sensor = DysonPM10Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error_inner(self):
        """Test ValueError in inner try block."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM10-002"
        coordinator.data = {"environmental-data": {"p10r": "INVALID"}}
        coordinator.device = Mock()

        sensor = DysonPM10Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_out_of_range_value(self):
        """Test PM10 value out of valid range."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM10-003"
        coordinator.data = {"environmental-data": {"p10r": "2000"}}  # > 999
        coordinator.device = Mock()

        sensor = DysonPM10Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_fallback_to_pm10(self):
        """Test fallback from p10r to legacy pm10 key."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM10-004"
        coordinator.data = {"environmental-data": {"pm10": "75"}}  # No p10r
        coordinator.device = Mock()

        sensor = DysonPM10Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value == 75

    def test_handle_coordinator_update_generic_exception(self):
        """Test generic Exception in outer handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM10-005"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=Exception("Unexpected"))
        coordinator.device = Mock()

        sensor = DysonPM10Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_sync_with_current_data_no_device(self):
        """Test _sync_with_current_data when device is None."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-PM10-006"
        coordinator.device = None

        sensor = DysonPM10Sensor(coordinator)
        sensor._sync_with_current_data()

        # Should not raise error


class TestNO2SensorErrorHandling:
    """Test error handling in DysonNO2Sensor."""

    def test_handle_coordinator_update_key_error(self):
        """Test KeyError when environmental-data is missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-NO2-001"
        coordinator.data = {}
        coordinator.device = Mock()

        sensor = DysonNO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_attribute_error(self):
        """Test AttributeError when data is None."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-NO2-002"
        coordinator.data = None
        coordinator.device = Mock()

        sensor = DysonNO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error_inner(self):
        """Test ValueError in inner try block."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-NO2-003"
        coordinator.data = {"environmental-data": {"noxl": "INVALID"}}
        coordinator.device = Mock()

        sensor = DysonNO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error_inner(self):
        """Test TypeError in inner try block."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-NO2-004"
        coordinator.data = {"environmental-data": {"noxl": {"not": "number"}}}
        coordinator.device = Mock()

        sensor = DysonNO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_out_of_range_value(self):
        """Test NO2 value out of valid range."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-NO2-005"
        coordinator.data = {"environmental-data": {"noxl": "250"}}  # > 200
        coordinator.device = Mock()

        sensor = DysonNO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error_outer(self):
        """Test ValueError in outer exception handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-NO2-006"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=ValueError("Data error"))
        coordinator.device = Mock()

        sensor = DysonNO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test generic Exception in outer handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-NO2-007"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=Exception("Unexpected"))
        coordinator.device = Mock()

        sensor = DysonNO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None


class TestFormaldehydeSensorErrorHandling:
    """Test error handling in DysonFormaldehydeSensor."""

    def test_handle_coordinator_update_key_error(self):
        """Test KeyError when environmental-data is missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HCHO-001"
        coordinator.data = {}
        coordinator.device = Mock()

        sensor = DysonFormaldehydeSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_hchr_none_value(self):
        """Test hchr with 'NONE' value (should be treated as unavailable)."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HCHO-002"
        coordinator.data = {"environmental-data": {"hchr": "NONE"}}
        coordinator.device = Mock()

        sensor = DysonFormaldehydeSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_hcho_none_value(self):
        """Test hcho with 'NONE' value (should be treated as unavailable)."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HCHO-003"
        coordinator.data = {"environmental-data": {"hcho": "NONE"}}
        coordinator.device = Mock()

        sensor = DysonFormaldehydeSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_hchr_preferred_over_hcho(self):
        """Test hchr is used when both hchr and hcho are present."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HCHO-004"
        coordinator.data = {"environmental-data": {"hchr": "5", "hcho": "10"}}
        coordinator.device = Mock()

        sensor = DysonFormaldehydeSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Should use hchr value (5), not hcho value (10)
        assert sensor._attr_native_value == 0.005  # 5/1000

    def test_handle_coordinator_update_fallback_to_hcho(self):
        """Test fallback to hcho when hchr is not available."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HCHO-005"
        coordinator.data = {"environmental-data": {"hcho": "8"}}  # No hchr
        coordinator.device = Mock()

        sensor = DysonFormaldehydeSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value == 0.008  # 8/1000

    def test_handle_coordinator_update_value_error_inner(self):
        """Test ValueError in inner try block."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HCHO-006"
        coordinator.data = {"environmental-data": {"hchr": "INVALID"}}
        coordinator.device = Mock()

        sensor = DysonFormaldehydeSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_out_of_range_value(self):
        """Test HCHO value out of valid range."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HCHO-007"
        coordinator.data = {"environmental-data": {"hchr": "15000"}}  # > 9999
        coordinator.device = Mock()

        sensor = DysonFormaldehydeSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test generic Exception in outer handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HCHO-008"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=Exception("Unexpected"))
        coordinator.device = Mock()

        sensor = DysonFormaldehydeSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None


class TestHEPAFilterLifeSensorErrorHandling:
    """Test error handling in DysonHEPAFilterLifeSensor."""

    def test_handle_coordinator_update_key_error(self):
        """Test KeyError when product-state is missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HEPA-001"
        coordinator.data = {}
        coordinator.device = Mock()

        sensor = DysonHEPAFilterLifeSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_attribute_error(self):
        """Test AttributeError when data is None."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HEPA-002"
        coordinator.data = None
        coordinator.device = Mock()

        sensor = DysonHEPAFilterLifeSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error(self):
        """Test ValueError when filter life value is invalid."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HEPA-003"
        coordinator.data = {"product-state": {"hflr": "INVALID"}}
        coordinator.device = Mock()

        sensor = DysonHEPAFilterLifeSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test generic Exception handling."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HEPA-004"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=Exception("Unexpected"))
        coordinator.device = Mock()

        sensor = DysonHEPAFilterLifeSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None


class TestCarbonFilterLifeSensorErrorHandling:
    """Test error handling in DysonCarbonFilterLifeSensor."""

    def test_handle_coordinator_update_key_error(self):
        """Test KeyError when product-state is missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CARBON-001"
        coordinator.data = {}
        coordinator.device = Mock()

        sensor = DysonCarbonFilterLifeSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error(self):
        """Test ValueError when filter life value is invalid."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CARBON-002"
        coordinator.data = {"product-state": {"cflr": "INVALID"}}
        coordinator.device = Mock()

        sensor = DysonCarbonFilterLifeSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test generic Exception handling."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CARBON-003"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=Exception("Unexpected"))
        coordinator.device = Mock()

        sensor = DysonCarbonFilterLifeSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None


class TestWiFiSensorErrorHandling:
    """Test error handling in DysonWiFiSensor."""

    def test_handle_coordinator_update_no_device(self):
        """Test when coordinator has no device."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-WIFI-001"
        coordinator.device = None

        sensor = DysonWiFiSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_with_rssi_value(self):
        """Test successful rssi value retrieval from device."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-WIFI-002"
        coordinator.device = Mock()
        coordinator.device.rssi = -45  # Valid WiFi signal strength

        sensor = DysonWiFiSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Implementation directly assigns device.rssi without error handling
        assert sensor._attr_native_value == -45

    def test_handle_coordinator_update_rssi_property_exception(self):
        """Test when rssi property raises exception."""
        from unittest.mock import PropertyMock

        coordinator = Mock()
        coordinator.serial_number = "TEST-WIFI-003"
        coordinator.device = Mock()

        # Make rssi property raise exception
        type(coordinator.device).rssi = PropertyMock(
            side_effect=Exception("Device error")
        )

        sensor = DysonWiFiSensor(coordinator)

        # Implementation doesn't catch exceptions, so it should raise
        with pytest.raises(Exception, match="Device error"):
            with patch.object(sensor, "async_write_ha_state"):
                sensor._handle_coordinator_update()


class TestConnectionStatusSensorErrorHandling:
    """Test error handling in DysonConnectionStatusSensor."""

    def test_handle_coordinator_update_no_device(self):
        """Test when coordinator has no device."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CONN-001"
        coordinator.device = None

        sensor = DysonConnectionStatusSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Should handle gracefully

    def test_handle_coordinator_update_device_no_is_connected_attr(self):
        """Test when device has no is_connected attribute."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CONN-002"
        coordinator.device = Mock(spec=[])  # No attributes

        sensor = DysonConnectionStatusSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            # Should handle AttributeError gracefully
            sensor._handle_coordinator_update()

    def test_handle_coordinator_update_generic_exception(self):
        """Test generic Exception handling."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CONN-003"
        coordinator.device = Mock()
        # Make is_connected property raise exception
        type(coordinator.device).is_connected = property(
            lambda self: (_ for _ in ()).throw(Exception("Unexpected"))
        )

        sensor = DysonConnectionStatusSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Should handle gracefully
