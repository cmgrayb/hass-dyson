"""Test sensor.py missing coverage areas."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.hass_dyson.sensor import (
    DysonP10RSensor,
    DysonP25RSensor,
    DysonTemperatureSensor,
    DysonVOCSensor,
)


class TestSensorMissingCoverage:
    """Test previously uncovered sensor.py code paths."""

    def test_p25r_sensor_no_coordinator_data(self, mock_coordinator):
        """Test P25R sensor with no coordinator data."""
        sensor = DysonP25RSensor(mock_coordinator)
        sensor.coordinator.data = None

        # Mock the parent update to avoid HA entity method calls
        with patch(
            "custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update"
        ):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_p25r_sensor_no_environmental_data(self, mock_coordinator):
        """Test P25R sensor with no environmental data."""
        sensor = DysonP25RSensor(mock_coordinator)
        sensor.coordinator.data = {}

        # Mock the parent update to avoid HA entity method calls
        with patch(
            "custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update"
        ):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_p25r_sensor_invalid_range_low(self, mock_coordinator):
        """Test P25R sensor with value below valid range."""
        sensor = DysonP25RSensor(mock_coordinator)
        sensor.coordinator.data = {"environmental-data": {"p25r": "-1"}}

        # Mock the parent update to avoid HA entity method calls
        with patch(
            "custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update"
        ):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_p25r_sensor_invalid_range_high(self, mock_coordinator):
        """Test P25R sensor with value above valid range."""
        sensor = DysonP25RSensor(mock_coordinator)
        sensor.coordinator.data = {"environmental-data": {"p25r": "1000"}}

        # Mock the parent update to avoid HA entity method calls
        with patch(
            "custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update"
        ):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_p25r_sensor_invalid_format(self, mock_coordinator):
        """Test P25R sensor with invalid format."""
        sensor = DysonP25RSensor(mock_coordinator)
        sensor.coordinator.data = {"environmental-data": {"p25r": "invalid"}}

        # Mock the parent update to avoid HA entity method calls
        with patch(
            "custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update"
        ):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_p25r_sensor_type_error(self, mock_coordinator):
        """Test P25R sensor with type that can't be converted."""
        sensor = DysonP25RSensor(mock_coordinator)
        sensor.coordinator.data = {
            "environmental-data": {"p25r": ["not", "a", "number"]}
        }

        # Mock the parent update to avoid HA entity method calls
        with patch(
            "custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update"
        ):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_p25r_sensor_key_error(self, mock_coordinator):
        """Test P25R sensor with KeyError."""
        sensor = DysonP25RSensor(mock_coordinator)

        # Set up data missing the environmental-data key to trigger KeyError
        sensor.coordinator.data = {
            "invalid-key": {}  # Missing environmental-data key
        }

        with patch(
            "custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update"
        ):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_p25r_sensor_attribute_error(self, mock_coordinator):
        """Test P25R sensor with AttributeError."""
        sensor = DysonP25RSensor(mock_coordinator)
        # Set coordinator data to None to trigger AttributeError
        sensor.coordinator.data = None

        # This will cause an AttributeError when trying to call .get() on None
        with patch.object(sensor.coordinator, "data", None):
            with patch(
                "custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update"
            ):
                sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_p25r_sensor_general_exception(self, mock_coordinator):
        """Test P25R sensor with exception during data processing."""
        sensor = DysonP25RSensor(mock_coordinator)

        # Use None data to trigger exception during processing
        sensor.coordinator.data = None

        # Mock to avoid HA entity methods
        with patch(
            "custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update"
        ):
            # This should trigger the general exception handling in the sensor
            sensor._handle_coordinator_update()

        # After exception, value should be None due to exception handling
        assert sensor._attr_native_value is None

    def test_p10r_sensor_no_data(self, mock_coordinator):
        """Test P10R sensor with no data."""
        sensor = DysonP10RSensor(mock_coordinator)
        sensor.coordinator.data = {}

        with patch(
            "custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update"
        ):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_p10r_sensor_invalid_format(self, mock_coordinator):
        """Test P10R sensor with invalid format."""
        sensor = DysonP10RSensor(mock_coordinator)
        sensor.coordinator.data = {"environmental-data": {"p10r": "not_a_number"}}

        with patch(
            "custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update"
        ):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_voc_sensor_no_data(self, mock_coordinator):
        """Test VOC sensor with no data."""
        sensor = DysonVOCSensor(mock_coordinator)
        sensor.coordinator.data = {}

        with patch(
            "custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update"
        ):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_voc_sensor_invalid_format(self, mock_coordinator):
        """Test VOC sensor with invalid format."""
        sensor = DysonVOCSensor(mock_coordinator)
        sensor.coordinator.data = {"environmental-data": {"va10": "invalid"}}

        with patch(
            "custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update"
        ):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_temperature_sensor_no_data(self, mock_coordinator):
        """Test temperature sensor with no data."""
        sensor = DysonTemperatureSensor(mock_coordinator)
        sensor.coordinator.data = {}

        with patch(
            "custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update"
        ):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_temperature_sensor_invalid_range(self, mock_coordinator):
        """Test temperature sensor with invalid format to trigger ValueError."""
        sensor = DysonTemperatureSensor(mock_coordinator)
        sensor.coordinator.data = {
            "environmental-data": {
                "tact": "invalid_temp"
            }  # Invalid format causes ValueError
        }

        with patch(
            "custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update"
        ):
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None
