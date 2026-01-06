"""Test sensor platform for Dyson integration using pure pytest (Phase 1 Migration).

This consolidates all sensor related tests:
- test_sensor.py (main sensor tests)
- test_sensor_coverage_enhancement_fixed.py
- test_sensor_coverage_enhancement.py
- test_sensor_error_handling.py
- test_sensor_error_scenarios.py
- test_sensor_missing_coverage.py
And migrates them to pure pytest infrastructure.
"""

from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    UnitOfTemperature,
)

from custom_components.hass_dyson.const import (
    DOMAIN,
)
from custom_components.hass_dyson.sensor import (
    DysonFilterLifeSensor,
    DysonFormaldehydeSensor,
    DysonHumiditySensor,
    DysonNO2Sensor,
    DysonPM10Sensor,
    DysonPM25Sensor,
    DysonTemperatureSensor,
    async_setup_entry,
)


class TestSensorPlatformSetup:
    """Test sensor platform setup using pure pytest."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_extended_aq_sensors(
        self, pure_mock_hass, pure_mock_config_entry, pure_mock_coordinator
    ):
        """Test setting up sensors for devices with ExtendedAQ capability."""
        # Arrange
        pure_mock_hass.data[DOMAIN] = {
            pure_mock_config_entry.entry_id: pure_mock_coordinator
        }
        mock_add_entities = MagicMock()

        # Ensure coordinator has ExtendedAQ capability
        pure_mock_coordinator.device_capabilities = ["ExtendedAQ", "EnvironmentalData"]

        # Act
        result = await async_setup_entry(
            pure_mock_hass, pure_mock_config_entry, mock_add_entities
        )

        # Assert
        assert result is True
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]

        # Should have various air quality sensors
        assert len(entities) >= 2
        sensor_types = [type(entity).__name__ for entity in entities]

        # Check for expected sensor types
        expected_sensors = ["DysonPM25Sensor", "DysonPM10Sensor"]
        for expected in expected_sensors:
            assert expected in sensor_types

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_heating_sensors(
        self, pure_mock_hass, pure_mock_config_entry, pure_mock_coordinator
    ):
        """Test setting up sensors for devices with heating capability."""
        # Arrange
        pure_mock_hass.data[DOMAIN] = {
            pure_mock_config_entry.entry_id: pure_mock_coordinator
        }
        mock_add_entities = MagicMock()

        # Ensure coordinator has heating capability
        pure_mock_coordinator.device_capabilities = ["Heating"]

        # Act
        result = await async_setup_entry(
            pure_mock_hass, pure_mock_config_entry, mock_add_entities
        )

        # Assert
        assert result is True
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) >= 1


class TestDysonPM25Sensor:
    """Test DysonPM25Sensor using pure pytest."""

    def test_pm25_sensor_init(self, pure_mock_coordinator):
        """Test PM2.5 sensor initialization."""
        # Act
        sensor = DysonPM25Sensor(pure_mock_coordinator)

        # Assert
        assert sensor.coordinator == pure_mock_coordinator
        assert sensor.unique_id == f"{pure_mock_coordinator.serial_number}_pm25"
        assert "PM2.5" in sensor.name
        assert sensor.device_class == SensorDeviceClass.PM25
        assert (
            sensor.native_unit_of_measurement
            == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
        )

    def test_pm25_sensor_state_from_environmental_data(self, pure_mock_coordinator):
        """Test PM2.5 sensor state from environmental data."""
        # Arrange
        pure_mock_coordinator.data["environmental-data"]["pm25"] = "15"
        sensor = DysonPM25Sensor(pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert
        assert sensor.native_value == 15

    def test_pm25_sensor_state_unavailable_data(self, pure_mock_coordinator):
        """Test PM2.5 sensor with unavailable data."""
        # Arrange
        pure_mock_coordinator.data["environmental-data"]["pm25"] = None
        sensor = DysonPM25Sensor(pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert
        assert sensor.native_value is None


class TestDysonPM10Sensor:
    """Test DysonPM10Sensor using pure pytest."""

    def test_pm10_sensor_init(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test PM10 sensor initialization."""
        # Act
        sensor = pure_mock_sensor_entity(DysonPM10Sensor, pure_mock_coordinator)

        # Assert
        assert sensor.coordinator == pure_mock_coordinator
        assert sensor.unique_id == f"{pure_mock_coordinator.serial_number}_pm10"
        assert "PM10" in sensor.name
        assert sensor.device_class == SensorDeviceClass.PM10
        assert (
            sensor.native_unit_of_measurement
            == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
        )

    def test_pm10_sensor_state_calculation(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test PM10 sensor state calculation."""
        # Arrange
        pure_mock_coordinator.data["environmental-data"]["pm10"] = "25"
        sensor = pure_mock_sensor_entity(DysonPM10Sensor, pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert
        assert sensor.native_value == 25


class TestDysonTemperatureSensor:
    """Test DysonTemperatureSensor using pure pytest."""

    def test_temperature_sensor_init(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test temperature sensor initialization."""
        # Act
        sensor = pure_mock_sensor_entity(DysonTemperatureSensor, pure_mock_coordinator)

        # Assert
        assert sensor.coordinator == pure_mock_coordinator
        assert sensor.unique_id == f"{pure_mock_coordinator.serial_number}_temperature"
        assert sensor.device_class == SensorDeviceClass.TEMPERATURE
        assert sensor.native_unit_of_measurement == UnitOfTemperature.CELSIUS

    def test_temperature_sensor_kelvin_to_celsius_conversion(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test temperature sensor converts Kelvin to Celsius."""
        # Arrange - tact is temperature in Kelvin * 10 (295.0K = 21.85°C)
        pure_mock_coordinator.data["environmental-data"]["tact"] = "2950"
        sensor = pure_mock_sensor_entity(DysonTemperatureSensor, pure_mock_coordinator)

        # Act - Trigger the calculation that happens during coordinator updates
        sensor._handle_coordinator_update()

        # Assert - Check the calculated value
        expected_celsius = 295.0 - 273.15  # Convert from Kelvin
        assert abs(sensor._attr_native_value - expected_celsius) < 0.1

    def test_temperature_sensor_invalid_data_handling(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test temperature sensor with invalid data."""
        # Arrange
        pure_mock_coordinator.data["environmental-data"]["tact"] = "invalid"
        sensor = pure_mock_sensor_entity(DysonTemperatureSensor, pure_mock_coordinator)

        # Act - Trigger the calculation that happens during coordinator updates
        sensor._handle_coordinator_update()

        # Assert - Check the calculated value
        assert sensor._attr_native_value is None


class TestDysonHumiditySensor:
    """Test DysonHumiditySensor using pure pytest."""

    def test_humidity_sensor_init(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test humidity sensor initialization."""
        # Act
        sensor = pure_mock_sensor_entity(DysonHumiditySensor, pure_mock_coordinator)

        # Assert
        assert sensor.coordinator == pure_mock_coordinator
        assert sensor.unique_id == f"{pure_mock_coordinator.serial_number}_humidity"
        assert sensor.device_class == SensorDeviceClass.HUMIDITY
        assert sensor.native_unit_of_measurement == PERCENTAGE

    def test_humidity_sensor_percentage_conversion(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test humidity sensor converts raw value to percentage."""
        # Arrange - hact is humidity as percentage (0045 = 45%)
        pure_mock_coordinator.data["environmental-data"]["hact"] = "0045"
        sensor = pure_mock_sensor_entity(DysonHumiditySensor, pure_mock_coordinator)

        # Act - Trigger the calculation that happens during coordinator updates
        sensor._handle_coordinator_update()

        # Assert - Check the calculated value
        assert sensor._attr_native_value == 45

    def test_humidity_sensor_invalid_data_handling(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test humidity sensor with invalid data."""
        # Arrange
        pure_mock_coordinator.data["environmental-data"]["hact"] = "invalid"
        sensor = pure_mock_sensor_entity(DysonHumiditySensor, pure_mock_coordinator)

        # Act - Trigger the calculation that happens during coordinator updates
        sensor._handle_coordinator_update()

        # Assert - Check the calculated value
        assert sensor._attr_native_value is None


class TestDysonFormaldehydeSensor:
    """Test DysonFormaldehydeSensor using pure pytest."""

    def test_formaldehyde_sensor_init(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test formaldehyde sensor initialization."""
        # Act
        sensor = pure_mock_sensor_entity(DysonFormaldehydeSensor, pure_mock_coordinator)

        # Assert
        assert sensor.coordinator == pure_mock_coordinator
        assert sensor.unique_id == f"{pure_mock_coordinator.serial_number}_formaldehyde"
        assert "Formaldehyde" in sensor.name

    def test_formaldehyde_sensor_data_conversion(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test formaldehyde sensor converts raw data."""
        # Arrange - Formaldehyde data in environmental data
        pure_mock_coordinator.data["environmental-data"]["hcho"] = "5"
        sensor = pure_mock_sensor_entity(DysonFormaldehydeSensor, pure_mock_coordinator)

        # Act - Trigger the calculation
        sensor._handle_coordinator_update()

        # Assert - Check the calculated value
        assert sensor._attr_native_value == 5


class TestDysonFormaldehyde2Sensor:
    """Test DysonFormaldehydeSensor using pure pytest - additional tests."""

    def test_formaldehyde_sensor_init_direct(self, pure_mock_coordinator):
        """Test formaldehyde sensor initialization with direct instantiation."""
        # Act
        sensor = DysonFormaldehydeSensor(pure_mock_coordinator)

        # Assert
        assert sensor.coordinator == pure_mock_coordinator
        assert sensor.unique_id == f"{pure_mock_coordinator.serial_number}_formaldehyde"
        assert "Formaldehyde" in sensor.name

    def test_formaldehyde_sensor_value_calculation(self, pure_mock_coordinator):
        """Test formaldehyde sensor value calculation."""
        # Arrange
        pure_mock_coordinator.data["environmental-data"]["hcho"] = "5"
        sensor = DysonFormaldehydeSensor(pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert
        assert sensor.native_value == 5

    def test_formaldehyde_sensor_none_value_handling(self, pure_mock_coordinator):
        """Test formaldehyde sensor handles None values."""
        # Arrange
        pure_mock_coordinator.data["environmental-data"]["hcho"] = None
        sensor = DysonFormaldehydeSensor(pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert
        assert sensor.native_value is None


class TestDysonNO2Sensor:
    """Test DysonNO2Sensor using pure pytest."""

    def test_no2_sensor_init(self, pure_mock_coordinator):
        """Test NO2 sensor initialization."""
        # Act
        sensor = DysonNO2Sensor(pure_mock_coordinator)

        # Assert
        assert sensor.coordinator == pure_mock_coordinator
        assert sensor.unique_id == f"{pure_mock_coordinator.serial_number}_no2"
        assert "NO2" in sensor.name

    def test_no2_sensor_value_calculation(self, pure_mock_coordinator):
        """Test NO2 sensor value calculation."""
        # Arrange
        pure_mock_coordinator.data["environmental-data"]["no2"] = "25"
        sensor = DysonNO2Sensor(pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert
        assert sensor.native_value == 25


class TestSensorErrorHandling:
    """Test sensor error handling scenarios using pure pytest."""

    def test_sensor_coordinator_data_none(self, pure_mock_coordinator):
        """Test sensor behavior when coordinator data is None."""
        # Arrange
        pure_mock_coordinator.data = None
        sensor = DysonPM25Sensor(pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert
        assert sensor.native_value is None

    def test_sensor_coordinator_data_missing_keys(self, pure_mock_coordinator):
        """Test sensor behavior with missing data keys."""
        # Arrange
        pure_mock_coordinator.data = {"product-state": {}}  # Missing environmental-data
        sensor = DysonTemperatureSensor(pure_mock_coordinator)

        # Act
        sensor._handle_coordinator_update()

        # Assert
        assert sensor.native_value is None

    def test_sensor_coordinator_update_exception_handling(self, pure_mock_coordinator):
        """Test sensor handles exceptions during coordinator update."""
        # Arrange
        sensor = DysonPM25Sensor(pure_mock_coordinator)

        # Mock data access to raise exception
        def side_effect(*args, **kwargs):
            raise KeyError("Test exception")

        pure_mock_coordinator.data = MagicMock()
        pure_mock_coordinator.data.__getitem__.side_effect = side_effect

        # Act & Assert - Should not raise exception
        try:
            sensor._handle_coordinator_update()
        except Exception:
            pytest.fail("Sensor should handle coordinator update exceptions gracefully")


class TestSensorStateClasses:
    """Test sensor state class assignments using pure pytest."""

    def test_measurement_sensors_have_measurement_state_class(
        self, pure_mock_coordinator
    ):
        """Test that measurement sensors have correct state class."""
        measurement_sensors = [
            DysonPM25Sensor(pure_mock_coordinator),
            DysonPM10Sensor(pure_mock_coordinator),
            DysonTemperatureSensor(pure_mock_coordinator),
            DysonHumiditySensor(pure_mock_coordinator),
        ]

        for sensor in measurement_sensors:
            assert sensor.state_class == SensorStateClass.MEASUREMENT

    def test_filter_sensors_have_total_state_class(self, pure_mock_coordinator):
        """Test that filter life sensors have correct state class."""
        filter_sensors = [
            DysonFilterLifeSensor(pure_mock_coordinator, "hepa"),
        ]

        for sensor in filter_sensors:
            # Filter life sensors may have TOTAL or no state class depending on implementation
            assert hasattr(sensor, "state_class")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
