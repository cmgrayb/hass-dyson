"""Additional sensor class error coverage tests to reach 75% target.

Tests for P10R, CO2, and VOC sensor error handling paths.
Target: Additional 1-2% overall coverage improvement (74% -> 75%+).
"""

from unittest.mock import Mock, patch

from custom_components.hass_dyson.sensor import (
    DysonCO2Sensor,
    DysonP10RSensor,
    DysonVOCSensor,
)


class TestP10RSensorErrorHandling:
    """Tests for DysonP10RSensor error handling in _handle_coordinator_update."""

    def test_handle_coordinator_update_key_error(self):
        """Test P10R sensor handling KeyError when environmental-data missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P10R-001"
        coordinator.data = {}  # No environmental-data key
        coordinator.device = Mock()

        sensor = DysonP10RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_attribute_error(self):
        """Test P10R sensor handling AttributeError when data is None."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P10R-002"
        coordinator.data = None
        coordinator.device = Mock()

        sensor = DysonP10RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error_inner(self):
        """Test P10R sensor handling ValueError in inner conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P10R-003"
        coordinator.data = {"environmental-data": {"p10r": "INVALID"}}
        coordinator.device = Mock()

        sensor = DysonP10RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error_inner(self):
        """Test P10R sensor handling TypeError in inner conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P10R-004"
        coordinator.data = {"environmental-data": {"p10r": ["list", "not", "int"]}}
        coordinator.device = Mock()

        sensor = DysonP10RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_out_of_range_value(self):
        """Test P10R value out of valid range (0-999)."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P10R-005"
        coordinator.data = {"environmental-data": {"p10r": "2000"}}  # > 999
        coordinator.device = Mock()

        sensor = DysonP10RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error_outer(self):
        """Test P10R sensor handling ValueError in outer handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P10R-006"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=ValueError("Data error"))
        coordinator.device = Mock()

        sensor = DysonP10RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error_outer(self):
        """Test P10R sensor handling TypeError in outer handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P10R-007"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=TypeError("Type error"))
        coordinator.device = Mock()

        sensor = DysonP10RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test P10R sensor handling generic Exception."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P10R-008"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=Exception("Unexpected"))
        coordinator.device = Mock()

        sensor = DysonP10RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_valid_value(self):
        """Test P10R sensor successfully processing valid value."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-P10R-009"
        coordinator.data = {"environmental-data": {"p10r": "75"}}
        coordinator.device = Mock()

        sensor = DysonP10RSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value == 75


class TestCO2SensorErrorHandling:
    """Tests for DysonCO2Sensor error handling in _handle_coordinator_update."""

    def test_handle_coordinator_update_key_error(self):
        """Test CO2 sensor handling KeyError when environmental-data missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CO2-001"
        coordinator.data = {}  # No environmental-data key
        coordinator.device = Mock()

        sensor = DysonCO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_attribute_error(self):
        """Test CO2 sensor handling AttributeError when data is None."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CO2-002"
        coordinator.data = None
        coordinator.device = Mock()

        sensor = DysonCO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error_inner(self):
        """Test CO2 sensor handling ValueError in inner conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CO2-003"
        coordinator.data = {"environmental-data": {"co2r": "INVALID"}}
        coordinator.device = Mock()

        sensor = DysonCO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error_inner(self):
        """Test CO2 sensor handling TypeError in inner conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CO2-004"
        coordinator.data = {"environmental-data": {"co2r": ["list", "not", "int"]}}
        coordinator.device = Mock()

        sensor = DysonCO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_out_of_range_value(self):
        """Test CO2 value out of valid range (0-5000)."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CO2-005"
        coordinator.data = {"environmental-data": {"co2r": "10000"}}  # > 5000
        coordinator.device = Mock()

        sensor = DysonCO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error_outer(self):
        """Test CO2 sensor handling ValueError in outer handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CO2-006"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=ValueError("Data error"))
        coordinator.device = Mock()

        sensor = DysonCO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error_outer(self):
        """Test CO2 sensor handling TypeError in outer handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CO2-007"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=TypeError("Type error"))
        coordinator.device = Mock()

        sensor = DysonCO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test CO2 sensor handling generic Exception."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CO2-008"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=Exception("Unexpected"))
        coordinator.device = Mock()

        sensor = DysonCO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_valid_value(self):
        """Test CO2 sensor successfully processing valid value."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-CO2-009"
        coordinator.data = {"environmental-data": {"co2r": "450"}}
        coordinator.device = Mock()

        sensor = DysonCO2Sensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value == 450


class TestVOCSensorErrorHandling:
    """Tests for DysonVOCSensor error handling in _handle_coordinator_update."""

    def test_handle_coordinator_update_key_error(self):
        """Test VOC sensor handling KeyError when environmental-data missing."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-VOC-001"
        coordinator.data = {}  # No environmental-data key
        coordinator.device = Mock()

        sensor = DysonVOCSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_attribute_error(self):
        """Test VOC sensor handling AttributeError when data is None."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-VOC-002"
        coordinator.data = None
        coordinator.device = Mock()

        sensor = DysonVOCSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error_inner(self):
        """Test VOC sensor handling ValueError in inner conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-VOC-003"
        coordinator.data = {"environmental-data": {"va10": "INVALID"}}
        coordinator.device = Mock()

        sensor = DysonVOCSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error_inner(self):
        """Test VOC sensor handling TypeError in inner conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-VOC-004"
        coordinator.data = {"environmental-data": {"va10": ["list", "not", "int"]}}
        coordinator.device = Mock()

        sensor = DysonVOCSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_out_of_range_value(self):
        """Test VOC value out of valid range (0-9999)."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-VOC-005"
        coordinator.data = {"environmental-data": {"va10": "15000"}}  # > 9999
        coordinator.device = Mock()

        sensor = DysonVOCSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_value_error_outer(self):
        """Test VOC sensor handling ValueError in outer handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-VOC-006"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=ValueError("Data error"))
        coordinator.device = Mock()

        sensor = DysonVOCSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_type_error_outer(self):
        """Test VOC sensor handling TypeError in outer handler."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-VOC-007"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=TypeError("Type error"))
        coordinator.device = Mock()

        sensor = DysonVOCSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_generic_exception(self):
        """Test VOC sensor handling generic Exception."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-VOC-008"
        coordinator.data = Mock()
        coordinator.data.get = Mock(side_effect=Exception("Unexpected"))
        coordinator.device = Mock()

        sensor = DysonVOCSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_handle_coordinator_update_valid_value(self):
        """Test VOC sensor successfully processing valid value with conversion."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-VOC-009"
        coordinator.data = {"environmental-data": {"va10": "2500"}}  # Raw value
        coordinator.device = Mock()

        sensor = DysonVOCSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # VOC conversion: 2500 / 1000.0 = 2.5 mg/m³
        assert sensor._attr_native_value == 2.5

    def test_handle_coordinator_update_valid_value_conversion_rounding(self):
        """Test VOC conversion with proper rounding to 3 decimal places."""
        coordinator = Mock()
        coordinator.serial_number = "TEST-VOC-010"
        coordinator.data = {"environmental-data": {"va10": "1234"}}  # Raw value
        coordinator.device = Mock()

        sensor = DysonVOCSensor(coordinator)

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # VOC conversion: 1234 / 1000.0 = 1.234 mg/m³
        assert sensor._attr_native_value == 1.234
