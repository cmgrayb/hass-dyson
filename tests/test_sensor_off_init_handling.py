"""Test OFF and INIT value handling for sensor platform.

Tests that sensors properly handle "OFF" values when continuous monitoring
is disabled and "INIT" values when sensors are initializing.

This addresses issue #277 where ValueError exceptions were logged when
sensors reported "OFF" or "INIT" values instead of numeric data.
"""

import logging

from custom_components.hass_dyson.sensor import (
    DysonCO2Sensor,
    DysonFormaldehydeSensor,
    DysonNO2Sensor,
    DysonP10RSensor,
    DysonP25RSensor,
    DysonParticulatesSensor,
    DysonPM10Sensor,
    DysonPM25Sensor,
    DysonVOCLinkSensor,
)


class TestSensorOFFHandling:
    """Test that all air quality sensors handle OFF value correctly."""

    def test_p25r_sensor_handles_off(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test P25R sensor handles OFF value when continuous monitoring disabled (issue #277)."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"p25r": "OFF"}}
        sensor = pure_mock_sensor_entity(DysonP25RSensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None

    def test_p10r_sensor_handles_off(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test P10R sensor handles OFF value when continuous monitoring disabled (issue #277)."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"p10r": "OFF"}}
        sensor = pure_mock_sensor_entity(DysonP10RSensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None

    def test_co2_sensor_handles_off(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test CO2 sensor handles OFF value when continuous monitoring disabled."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"co2r": "OFF"}}
        sensor = pure_mock_sensor_entity(DysonCO2Sensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None

    def test_pm25_sensor_handles_off(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test PM25 sensor handles OFF value when continuous monitoring disabled (issue #277)."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"p25r": "OFF"}}
        sensor = pure_mock_sensor_entity(DysonPM25Sensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None

    def test_pm10_sensor_handles_off(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test PM10 sensor handles OFF value when continuous monitoring disabled (issue #277)."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"p10r": "OFF"}}
        sensor = pure_mock_sensor_entity(DysonPM10Sensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None

    def test_pact_sensor_handles_off(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test Particulates sensor handles OFF value when continuous monitoring disabled."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"pact": "OFF"}}
        sensor = pure_mock_sensor_entity(DysonParticulatesSensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None

    def test_vact_sensor_handles_off(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test VOC Link sensor handles OFF value when continuous monitoring disabled."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"vact": "OFF"}}
        sensor = pure_mock_sensor_entity(DysonVOCLinkSensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None

    def test_no2_sensor_handles_off(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test NO2 sensor handles OFF value when continuous monitoring disabled."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"noxl": "OFF"}}
        sensor = pure_mock_sensor_entity(DysonNO2Sensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None

    def test_hcho_sensor_handles_off(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test Formaldehyde sensor handles OFF value when continuous monitoring disabled."""
        # Arrange
        pure_mock_coordinator.data = {
            "environmental-data": {"hchr": "OFF", "hcho": "OFF"}
        }
        sensor = pure_mock_sensor_entity(DysonFormaldehydeSensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None


class TestSensorINITHandling:
    """Test that all air quality sensors handle INIT value correctly."""

    def test_p25r_sensor_handles_init(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test P25R sensor handles INIT value when initializing (issue #277)."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"p25r": "INIT"}}
        sensor = pure_mock_sensor_entity(DysonP25RSensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None

    def test_p10r_sensor_handles_init(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test P10R sensor handles INIT value when initializing (issue #277)."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"p10r": "INIT"}}
        sensor = pure_mock_sensor_entity(DysonP10RSensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None

    def test_co2_sensor_handles_init(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test CO2 sensor handles INIT value when initializing."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"co2r": "INIT"}}
        sensor = pure_mock_sensor_entity(DysonCO2Sensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None

    def test_pm25_sensor_handles_init(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test PM25 sensor handles INIT value when initializing (issue #277)."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"p25r": "INIT"}}
        sensor = pure_mock_sensor_entity(DysonPM25Sensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None

    def test_pm10_sensor_handles_init(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test PM10 sensor handles INIT value when initializing (issue #277)."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"p10r": "INIT"}}
        sensor = pure_mock_sensor_entity(DysonPM10Sensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None

    def test_vact_sensor_handles_init(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test VOC Link sensor handles INIT value when initializing."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"vact": "INIT"}}
        sensor = pure_mock_sensor_entity(DysonVOCLinkSensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None

    def test_no2_sensor_handles_init(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test NO2 sensor handles INIT value when initializing."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"noxl": "INIT"}}
        sensor = pure_mock_sensor_entity(DysonNO2Sensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None

    def test_hcho_sensor_handles_init(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test Formaldehyde sensor handles INIT value when initializing."""
        # Arrange
        pure_mock_coordinator.data = {
            "environmental-data": {"hchr": "INIT", "hcho": "INIT"}
        }
        sensor = pure_mock_sensor_entity(DysonFormaldehydeSensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert - Should be None, not raise ValueError
        assert sensor._attr_native_value is None


class TestSensorResumeAfterOFF:
    """Test that sensors return to normal operation after reporting OFF/INIT values."""

    def test_pm25_sensor_resumes_after_off(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test PM2.5 sensor returns to normal after OFF state (issue #277)."""
        # Arrange
        sensor = pure_mock_sensor_entity(DysonPM25Sensor, pure_mock_coordinator)

        # Act - sensor is OFF
        pure_mock_coordinator.data = {"environmental-data": {"p25r": "OFF"}}
        sensor._handle_coordinator_update()
        assert sensor._attr_native_value is None

        # Act - sensor resumes with valid data
        pure_mock_coordinator.data = {"environmental-data": {"p25r": "25"}}
        sensor._handle_coordinator_update()

        # Assert - sensor shows valid data again
        assert sensor._attr_native_value == 25

    def test_pm10_sensor_resumes_after_init(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test PM10 sensor returns to normal after INIT state (issue #277)."""
        # Arrange
        sensor = pure_mock_sensor_entity(DysonPM10Sensor, pure_mock_coordinator)

        # Act - sensor is initializing
        pure_mock_coordinator.data = {"environmental-data": {"p10r": "INIT"}}
        sensor._handle_coordinator_update()
        assert sensor._attr_native_value is None

        # Act - sensor initializes with valid data
        pure_mock_coordinator.data = {"environmental-data": {"p10r": "40"}}
        sensor._handle_coordinator_update()

        # Assert - sensor shows valid data
        assert sensor._attr_native_value == 40


class TestSensorNoLogging:
    """Test that OFF and INIT do not generate warning logs (issue #277)."""

    def test_off_generates_debug_not_warning(
        self, pure_mock_coordinator, pure_mock_sensor_entity, caplog
    ):
        """Test that OFF value logs at debug level, not warning (issue #277)."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"p25r": "OFF"}}
        sensor = pure_mock_sensor_entity(DysonP25RSensor, pure_mock_coordinator)

        # Act
        with caplog.at_level(logging.DEBUG):
            sensor._handle_coordinator_update()

        # Assert - No warning messages should be logged
        warning_messages = [
            record.message for record in caplog.records if record.levelname == "WARNING"
        ]
        assert len(warning_messages) == 0

        # Assert - Debug message should mention inactive
        debug_messages = [
            record.message for record in caplog.records if record.levelname == "DEBUG"
        ]
        assert any("inactive" in msg for msg in debug_messages)

    def test_init_generates_debug_not_warning(
        self, pure_mock_coordinator, pure_mock_sensor_entity, caplog
    ):
        """Test that INIT value logs at debug level, not warning (issue #277)."""
        # Arrange
        pure_mock_coordinator.data = {"environmental-data": {"p10r": "INIT"}}
        sensor = pure_mock_sensor_entity(DysonP10RSensor, pure_mock_coordinator)

        # Act
        with caplog.at_level(logging.DEBUG):
            sensor._handle_coordinator_update()

        # Assert - No warning messages should be logged
        warning_messages = [
            record.message for record in caplog.records if record.levelname == "WARNING"
        ]
        assert len(warning_messages) == 0

        # Assert - Debug message should mention initializing
        debug_messages = [
            record.message for record in caplog.records if record.levelname == "DEBUG"
        ]
        assert any("initializing" in msg for msg in debug_messages)
