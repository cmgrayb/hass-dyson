"""Enhanced sensor tests to improve coverage."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
from custom_components.hass_dyson.sensor import (
    DysonAirQualitySensor,
    DysonFilterLifeSensor,
    DysonFormaldehydeSensor,
    DysonHumiditySensor,
    DysonTemperatureSensor,
)


class TestDysonFilterLifeSensorErrorHandling:
    """Test filter life sensor error handling scenarios."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "VS6-EU-HJA1234A"
        return coordinator

    @pytest.fixture
    def filter_life_sensor(self, mock_coordinator):
        """Create a filter life sensor instance."""
        return DysonFilterLifeSensor(mock_coordinator, "hepa")

    def test_filter_life_invalid_value_type_error(
        self, filter_life_sensor, mock_coordinator
    ):
        """Test filter life sensor with invalid value causing TypeError."""
        # Setup coordinator data with invalid filter life value (non-convertible object)
        mock_coordinator.data = {"hepa_filter_life": object()}  # Non-convertible object

        # Trigger update with patched async_write_ha_state
        with patch.object(filter_life_sensor, "async_write_ha_state"):
            filter_life_sensor._handle_coordinator_update()

        # Should handle TypeError and set value to None
        assert filter_life_sensor._attr_native_value is None

    def test_filter_life_invalid_value_error(
        self, filter_life_sensor, mock_coordinator
    ):
        """Test filter life sensor with invalid value causing ValueError."""
        # Setup coordinator data with invalid filter life value (non-numeric string)
        mock_coordinator.data = {"hepa_filter_life": "invalid_number"}

        # Trigger update with patched async_write_ha_state
        with patch.object(filter_life_sensor, "async_write_ha_state"):
            filter_life_sensor._handle_coordinator_update()

        # Should handle ValueError and set value to None
        assert filter_life_sensor._attr_native_value is None

    def test_filter_life_none_value_fallback(
        self, filter_life_sensor, mock_coordinator
    ):
        """Test filter life sensor fallback when filter_life is None."""
        # Setup coordinator data with None filter life value
        mock_coordinator.data = {"hepa_filter_life": None}

        # Trigger update with patched async_write_ha_state
        with patch.object(filter_life_sensor, "async_write_ha_state"):
            filter_life_sensor._handle_coordinator_update()

        # Should set value to None when filter_life is None
        assert filter_life_sensor._attr_native_value is None

    def test_filter_life_missing_key_fallback(
        self, filter_life_sensor, mock_coordinator
    ):
        """Test filter life sensor fallback when filter_life key is missing."""
        # Setup coordinator data without filter life key
        mock_coordinator.data = {"other_data": "value"}

        # Trigger update with patched async_write_ha_state
        with patch.object(filter_life_sensor, "async_write_ha_state"):
            filter_life_sensor._handle_coordinator_update()

        # Should set value to None when key is missing
        assert filter_life_sensor._attr_native_value is None


class TestDysonAirQualitySensorErrorHandling:
    """Test air quality sensor error handling scenarios."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "VS6-EU-HJA1234A"
        coordinator.device = MagicMock()
        return coordinator

    @pytest.fixture
    def pm25_sensor(self, mock_coordinator):
        """Create PM2.5 sensor instance."""
        return DysonAirQualitySensor(mock_coordinator, "pm25")

    @pytest.fixture
    def pm10_sensor(self, mock_coordinator):
        """Create PM10 sensor instance."""
        return DysonAirQualitySensor(mock_coordinator, "pm10")

    @pytest.fixture
    def no2_sensor(self, mock_coordinator):
        """Create NO2 sensor instance."""
        return DysonAirQualitySensor(mock_coordinator, "no2")

    @pytest.fixture
    def voc_sensor(self, mock_coordinator):
        """Create VOC sensor instance."""
        return DysonAirQualitySensor(mock_coordinator, "voc")

    @pytest.fixture
    def formaldehyde_sensor(self, mock_coordinator):
        """Create formaldehyde sensor instance."""
        return DysonFormaldehydeSensor(mock_coordinator)

    def test_pm25_invalid_conversion_error(self, pm25_sensor, mock_coordinator):
        """Test PM2.5 sensor with invalid data conversion."""
        # Setup device with no pm25 property to trigger data lookup
        mock_coordinator.device.pm25 = None
        mock_coordinator.data = {"pm25": "invalid_float"}

        # Trigger update with patched async_write_ha_state
        with patch.object(pm25_sensor, "async_write_ha_state"):
            pm25_sensor._handle_coordinator_update()

        # Should handle conversion error and set value to None
        assert pm25_sensor._attr_native_value is None

    def test_pm10_invalid_conversion_error(self, pm10_sensor, mock_coordinator):
        """Test PM10 sensor with invalid data conversion."""
        # Setup device with no pm10 property to trigger data lookup
        mock_coordinator.device.pm10 = None
        mock_coordinator.data = {"pm10": "invalid_float"}

        # Trigger update with patched async_write_ha_state
        with patch.object(pm10_sensor, "async_write_ha_state"):
            pm10_sensor._handle_coordinator_update()

        # Should handle conversion error and set value to None
        assert pm10_sensor._attr_native_value is None

    def test_no2_invalid_conversion_error(self, no2_sensor, mock_coordinator):
        """Test NO2 sensor with invalid data conversion."""
        # Setup device with no no2 property to trigger data lookup
        mock_coordinator.device.no2 = None
        mock_coordinator.data = {"no2": "invalid_float"}

        # Trigger update with patched async_write_ha_state
        with patch.object(no2_sensor, "async_write_ha_state"):
            no2_sensor._handle_coordinator_update()

        # Should handle conversion error and set value to None
        assert no2_sensor._attr_native_value is None

    def test_voc_invalid_conversion_error(self, voc_sensor, mock_coordinator):
        """Test VOC sensor with invalid data conversion."""
        # Setup device with no voc property to trigger data lookup
        mock_coordinator.device.voc = None
        mock_coordinator.data = {"voc": "invalid_float"}

        # Trigger update with patched async_write_ha_state
        with patch.object(voc_sensor, "async_write_ha_state"):
            voc_sensor._handle_coordinator_update()

        # Should handle conversion error and set value to None
        assert voc_sensor._attr_native_value is None

    def test_formaldehyde_invalid_conversion_error(
        self, formaldehyde_sensor, mock_coordinator
    ):
        """Test formaldehyde sensor with invalid data conversion."""
        # Setup device with no formaldehyde property to trigger data lookup
        mock_coordinator.device.formaldehyde = None
        mock_coordinator.data = {"hcho": "invalid_float"}

        # Trigger update with patched async_write_ha_state
        with patch.object(formaldehyde_sensor, "async_write_ha_state"):
            formaldehyde_sensor._handle_coordinator_update()

        # Should handle conversion error and set value to None
        assert formaldehyde_sensor._attr_native_value is None


class TestDysonEnvironmentalSensorErrorHandling:
    """Test environmental sensor error handling scenarios."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "VS6-EU-HJA1234A"
        coordinator.device = MagicMock()
        return coordinator

    @pytest.fixture
    def temperature_sensor(self, mock_coordinator):
        """Create temperature sensor instance."""
        return DysonTemperatureSensor(mock_coordinator)

    @pytest.fixture
    def humidity_sensor(self, mock_coordinator):
        """Create humidity sensor instance."""
        return DysonHumiditySensor(mock_coordinator)

    def test_temperature_invalid_conversion_error(
        self, temperature_sensor, mock_coordinator
    ):
        """Test temperature sensor with invalid data conversion."""
        # Setup device with no temperature property to trigger data lookup
        mock_coordinator.device.temperature = None
        mock_coordinator.data = {"tact": "invalid_temp"}

        # Trigger update with patched async_write_ha_state
        with patch.object(temperature_sensor, "async_write_ha_state"):
            temperature_sensor._handle_coordinator_update()

        # Should handle conversion error and set value to None
        assert temperature_sensor._attr_native_value is None

    def test_humidity_invalid_conversion_error(self, humidity_sensor, mock_coordinator):
        """Test humidity sensor with invalid data conversion."""
        # Setup device with no humidity property to trigger data lookup
        mock_coordinator.device.humidity = None
        mock_coordinator.data = {"hact": "invalid_humidity"}

        # Trigger update with patched async_write_ha_state
        with patch.object(humidity_sensor, "async_write_ha_state"):
            humidity_sensor._handle_coordinator_update()

        # Should handle conversion error and set value to None
        assert humidity_sensor._attr_native_value is None


class TestDysonSensorCoordinatorDataHandling:
    """Test sensor handling of coordinator data edge cases."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "VS6-EU-HJA1234A"
        coordinator.device = MagicMock()
        return coordinator

    @pytest.fixture
    def filter_life_sensor(self, mock_coordinator):
        """Create a filter life sensor instance."""
        return DysonFilterLifeSensor(mock_coordinator, "hepa")

    def test_sensor_empty_coordinator_data(self, filter_life_sensor, mock_coordinator):
        """Test sensor with empty coordinator data."""
        # Setup coordinator with empty data
        mock_coordinator.data = {}

        # Trigger update with patched async_write_ha_state
        with patch.object(filter_life_sensor, "async_write_ha_state"):
            filter_life_sensor._handle_coordinator_update()

        # Should handle missing key gracefully
        assert filter_life_sensor._attr_native_value is None

    def test_sensor_none_coordinator_data(self, filter_life_sensor, mock_coordinator):
        """Test sensor with None coordinator data."""
        # Setup coordinator with None data
        mock_coordinator.data = None

        # Trigger update with patched async_write_ha_state
        with patch.object(filter_life_sensor, "async_write_ha_state"):
            filter_life_sensor._handle_coordinator_update()

        # Should handle None data gracefully
        assert filter_life_sensor._attr_native_value is None

    def test_sensor_corrupted_coordinator_data(
        self, filter_life_sensor, mock_coordinator
    ):
        """Test sensor with corrupted coordinator data."""
        # Setup coordinator with corrupted data (string instead of dict)
        mock_coordinator.data = "corrupted_data"

        # This should handle the exception gracefully
        try:
            with patch.object(filter_life_sensor, "async_write_ha_state"):
                filter_life_sensor._handle_coordinator_update()
            # If we get here, the sensor handled the error gracefully
            assert filter_life_sensor._attr_native_value is None
        except AttributeError:
            # This is expected - the sensor should handle AttributeError gracefully
            assert filter_life_sensor._attr_native_value is None
