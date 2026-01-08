"""Comprehensive error handling tests for sensor entity module.

This test module targets uncovered exception handlers in sensor.py to improve
code coverage from 54% baseline. Focus areas:
1. KeyError/AttributeError when accessing missing data keys
2. ValueError/TypeError in data type conversions
3. Generic Exception handling
4. Invalid value ranges and validation
5. Missing environmental/product data

Target: +3-4% overall coverage improvement (large module with 820 statements)
"""

from unittest.mock import Mock, patch

from custom_components.hass_dyson.sensor import (
    DysonAirQualitySensor,
    DysonCO2Sensor,
    DysonFilterLifeSensor,
    DysonHumiditySensor,
    DysonP10RSensor,
    DysonP25RSensor,
    DysonTemperatureSensor,
    DysonVOCSensor,
)


class TestP25RSensorErrorHandling:
    """Test error handling in DysonP25RSensor."""

    def test_handle_coordinator_update_key_error(self):
        """Test KeyError when environmental-data is missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P25R-001"
        coordinator.data = {}  # Missing environmental-data key
        coordinator.device = Mock()

        sensor = DysonP25RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Should handle gracefully
        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_attribute_error(self):
        """Test AttributeError when data structure is unexpected."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P25R-002"
        coordinator.data = None  # Will cause AttributeError on .get()
        coordinator.device = Mock()

        sensor = DysonP25RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error_inner(self):
        """Test ValueError in inner try block (invalid format)."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P25R-003"
        coordinator.data = {"environmental-data": {"p25r": "INVALID"}}
        coordinator.device = Mock()

        sensor = DysonP25RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Should log warning and set None
        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error_inner(self):
        """Test TypeError in inner try block (wrong type)."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P25R-004"
        coordinator.data = {"environmental-data": {"p25r": ["not", "a", "number"]}}
        coordinator.device = Mock()

        sensor = DysonP25RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error_outer(self):
        """Test ValueError in outer exception handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P25R-005"
        coordinator.data = Mock()
        # Make data.get() raise ValueError
        coordinator.data.get = Mock(side_effect=ValueError("Data conversion error"))
        coordinator.device = Mock()

        sensor = DysonP25RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error_outer(self):
        """Test TypeError in outer exception handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P25R-006"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=TypeError("Type mismatch"))
        coordinator.device = Mock()

        sensor = DysonP25RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test generic Exception in outer handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P25R-007"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=RuntimeError("Unexpected error"))
        coordinator.device = Mock()

        sensor = DysonP25RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None


class TestP10RSensorErrorHandling:
    """Test error handling in DysonP10RSensor."""

    def test_handle_coordinator_update_key_error(self):
        """Test KeyError when p10r data is missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P10R-001"
        coordinator.data = {"environmental-data": {}}  # Missing p10r key
        coordinator.device = Mock()

        sensor = DysonP10RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_attribute_error(self):
        """Test AttributeError in data access."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P10R-002"
        coordinator.data = None
        coordinator.device = Mock()

        sensor = DysonP10RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error_conversion(self):
        """Test ValueError in p10r value conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P10R-003"
        coordinator.data = {"environmental-data": {"p10r": "NOT_A_NUMBER"}}
        coordinator.device = Mock()

        sensor = DysonP10RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error_conversion(self):
        """Test TypeError in p10r value conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P10R-004"
        coordinator.data = {"environmental-data": {"p10r": {"invalid": "type"}}}
        coordinator.device = Mock()

        sensor = DysonP10RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test generic Exception in P10R sensor."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P10R-005"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=OSError("Disk error"))
        coordinator.device = Mock()

        sensor = DysonP10RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None


class TestCO2SensorErrorHandling:
    """Test error handling in DysonCO2Sensor."""

    def test_handle_coordinator_update_key_error(self):
        """Test KeyError when co2r data is missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CO2-001"
        coordinator.data = {"environmental-data": {}}
        coordinator.device = Mock()

        sensor = DysonCO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_attribute_error(self):
        """Test AttributeError in CO2 data access."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CO2-002"
        coordinator.data = None
        coordinator.device = Mock()

        sensor = DysonCO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error_conversion(self):
        """Test ValueError in CO2 value conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CO2-003"
        coordinator.data = {"environmental-data": {"co2r": "INVALID_CO2"}}
        coordinator.device = Mock()

        sensor = DysonCO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error_conversion(self):
        """Test TypeError in CO2 value conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CO2-004"
        coordinator.data = {"environmental-data": {"co2r": [123]}}
        coordinator.device = Mock()

        sensor = DysonCO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test generic Exception in CO2 sensor."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CO2-005"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=MemoryError("Out of memory"))
        coordinator.device = Mock()

        sensor = DysonCO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None


class TestVOCSensorErrorHandling:
    """Test error handling in DysonVOCSensor."""

    def test_handle_coordinator_update_key_error(self):
        """Test KeyError when vocr data is missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-VOC-001"
        coordinator.data = {"environmental-data": {}}
        coordinator.device = Mock()

        sensor = DysonVOCSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_attribute_error(self):
        """Test AttributeError in VOC data access."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-VOC-002"
        coordinator.data = None
        coordinator.device = Mock()

        sensor = DysonVOCSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error_conversion(self):
        """Test ValueError in VOC value conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-VOC-003"
        coordinator.data = {"environmental-data": {"vocr": "INVALID_VOC"}}
        coordinator.device = Mock()

        sensor = DysonVOCSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error_conversion(self):
        """Test TypeError in VOC value conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-VOC-004"
        coordinator.data = {"environmental-data": {"vocr": None}}
        coordinator.device = Mock()

        sensor = DysonVOCSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            # This will actually succeed with None, but we're testing the path
            sensor._handle_coordinator_update()

        # vocr being None means it stays None (no conversion attempted)
        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test generic Exception in VOC sensor."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-VOC-005"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=OSError("System error"))
        coordinator.device = Mock()

        sensor = DysonVOCSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None


class TestTemperatureSensorErrorHandling:
    """Test error handling in DysonTemperatureSensor."""

    def test_handle_coordinator_update_key_error(self):
        """Test KeyError when temperature data is missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-TEMP-001"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(side_effect=KeyError("tact"))
        coordinator.data = {"product-state": {}}

        sensor = DysonTemperatureSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Should handle and set to None
        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_attribute_error(self):
        """Test AttributeError in temperature sensor."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-TEMP-002"
        coordinator.device = None  # Will cause AttributeError
        coordinator.data = {}

        sensor = DysonTemperatureSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error(self):
        """Test ValueError in temperature conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-TEMP-003"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(return_value="INVALID")
        coordinator.data = {"product-state": {}}

        sensor = DysonTemperatureSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error(self):
        """Test TypeError in temperature conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-TEMP-004"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(return_value=["not", "temperature"])
        coordinator.data = {"product-state": {}}

        sensor = DysonTemperatureSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test generic Exception in temperature sensor."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-TEMP-005"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(
            side_effect=RuntimeError("Device error")
        )
        coordinator.data = {"product-state": {}}

        sensor = DysonTemperatureSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None


class TestHumiditySensorErrorHandling:
    """Test error handling in DysonHumiditySensor."""

    def test_handle_coordinator_update_key_error(self):
        """Test KeyError when humidity data is missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HUM-001"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(side_effect=KeyError("hact"))
        coordinator.data = {"product-state": {}}

        sensor = DysonHumiditySensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_attribute_error(self):
        """Test AttributeError in humidity sensor."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HUM-002"
        coordinator.device = None
        coordinator.data = {}

        sensor = DysonHumiditySensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error(self):
        """Test ValueError in humidity conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HUM-003"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(return_value="NOT_A_NUMBER")
        coordinator.data = {"product-state": {}}

        sensor = DysonHumiditySensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error(self):
        """Test TypeError in humidity conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HUM-004"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(return_value={"invalid": "type"})
        coordinator.data = {"product-state": {}}

        sensor = DysonHumiditySensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test generic Exception in humidity sensor."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-HUM-005"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(side_effect=OSError("I/O error"))
        coordinator.data = {"product-state": {}}

        sensor = DysonHumiditySensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None


class TestFilterLifeSensorErrorHandling:
    """Test error handling in DysonFilterLifeSensor."""

    def test_handle_coordinator_update_key_error(self):
        """Test KeyError when filter life data is missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-FILTER-001"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(side_effect=KeyError("filf"))
        coordinator.data = {"product-state": {}}

        sensor = DysonFilterLifeSensor(coordinator, "hepa")

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_attribute_error(self):
        """Test AttributeError in filter life sensor."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-FILTER-002"
        coordinator.device = None
        coordinator.data = {}

        sensor = DysonFilterLifeSensor(coordinator, "carbon")

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error(self):
        """Test ValueError in filter life conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-FILTER-003"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(return_value="INVALID_HOURS")
        coordinator.data = {"product-state": {}}

        sensor = DysonFilterLifeSensor(coordinator, "hepa")

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test generic Exception in filter life sensor."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-FILTER-004"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(
            side_effect=RuntimeError("Filter error")
        )
        coordinator.data = {"product-state": {}}

        sensor = DysonFilterLifeSensor(coordinator, "carbon")

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None


class TestAirQualitySensorErrorHandling:
    """Test error handling in DysonAirQualitySensor."""

    def test_handle_coordinator_update_key_error(self):
        """Test KeyError when air quality data is missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-AQ-001"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(side_effect=KeyError("pact"))
        coordinator.data = {"product-state": {}}

        sensor = DysonAirQualitySensor(coordinator, "pm25")

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_attribute_error(self):
        """Test AttributeError in air quality sensor."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-AQ-002"
        coordinator.device = None
        coordinator.data = {}

        sensor = DysonAirQualitySensor(coordinator, "pm10")

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error(self):
        """Test ValueError in air quality conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-AQ-003"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(return_value="BAD_QUALITY")
        coordinator.data = {"product-state": {}}

        sensor = DysonAirQualitySensor(coordinator, "pm25")

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test generic Exception in air quality sensor."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-AQ-004"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(
            side_effect=MemoryError("Memory issue")
        )
        coordinator.data = {"product-state": {}}

        sensor = DysonAirQualitySensor(coordinator, "pm10")

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None
