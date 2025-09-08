"""Test sensor platform for Dyson integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, PERCENTAGE

from custom_components.hass_dyson.const import DOMAIN
from custom_components.hass_dyson.sensor import (
    DysonAirQualitySensor,
    DysonFilterLifeSensor,
    DysonHumiditySensor,
    DysonPM10Sensor,
    DysonPM25Sensor,
    DysonTemperatureSensor,
    DysonWiFiSensor,
    async_setup_entry,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-SERIAL-123"
    coordinator.device_name = "Test Device"
    coordinator.device = MagicMock()
    coordinator.device_capabilities = ["ExtendedAQ", "Heating"]
    coordinator.device_category = ["EC"]
    coordinator.data = {
        "product-state": {
            "pm25": "0010",
            "pm10": "0015",
            "hmax": "0030",
            "tact": "2950",
        }
    }
    return coordinator


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test-entry-id"
    return config_entry


class TestSensorPlatformSetup:
    """Test sensor platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_extended_aq_devices(self, mock_coordinator):
        """Test setting up sensors for devices with ExtendedAQ capability."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"
        async_add_entities = AsyncMock()

        hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) >= 2  # Should have PM2.5 and PM10 at minimum

    @pytest.mark.asyncio
    async def test_async_setup_entry_heating_devices(self, mock_coordinator):
        """Test setting up sensors for devices with heating capability."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"
        async_add_entities = AsyncMock()

        mock_coordinator.device_capabilities = ["Heating"]
        hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) >= 1  # Should have temperature sensor

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_capabilities(self, mock_coordinator):
        """Test setting up sensors for devices with no special capabilities."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"
        async_add_entities = AsyncMock()

        mock_coordinator.device_capabilities = []
        mock_coordinator.device_category = []
        hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        async_add_entities.assert_called_once()


class TestDysonPM25Sensor:
    """Test DysonPM25Sensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        sensor = DysonPM25Sensor(mock_coordinator)

        # Assert
        assert sensor.coordinator == mock_coordinator
        assert sensor._attr_unique_id == "TEST-SERIAL-123_pm25"
        assert sensor._attr_name == "Test Device PM2.5"
        assert sensor._attr_device_class == SensorDeviceClass.PM25
        assert sensor._attr_state_class == SensorStateClass.MEASUREMENT
        assert sensor._attr_native_unit_of_measurement == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER

    def test_native_value_with_valid_data(self, mock_coordinator):
        """Test sensor updates when device has PM2.5 data."""
        # Arrange
        sensor = DysonPM25Sensor(mock_coordinator)
        mock_coordinator.device.pm25 = 10

        # Act - trigger update
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value == 10

    def test_native_value_with_no_device(self, mock_coordinator):
        """Test sensor when no device available."""
        # Arrange
        sensor = DysonPM25Sensor(mock_coordinator)
        mock_coordinator.device = None

        # Act - trigger update
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is None


class TestDysonPM10Sensor:
    """Test DysonPM10Sensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        sensor = DysonPM10Sensor(mock_coordinator)

        # Assert
        assert sensor.coordinator == mock_coordinator
        assert sensor._attr_unique_id == "TEST-SERIAL-123_pm10"
        assert sensor._attr_name == "Test Device PM10"
        assert sensor._attr_device_class == SensorDeviceClass.PM10
        assert sensor._attr_state_class == SensorStateClass.MEASUREMENT

    def test_native_value_with_valid_data(self, mock_coordinator):
        """Test sensor updates when device has PM10 data."""
        # Arrange
        sensor = DysonPM10Sensor(mock_coordinator)
        mock_coordinator.device.pm10 = 15

        # Act - trigger update
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value == 15


class TestDysonTemperatureSensor:
    """Test DysonTemperatureSensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        sensor = DysonTemperatureSensor(mock_coordinator)

        # Assert
        assert sensor.coordinator == mock_coordinator
        assert sensor._attr_unique_id == "TEST-SERIAL-123_temperature"
        assert sensor._attr_name == "Test Device Temperature"
        assert sensor._attr_device_class == SensorDeviceClass.TEMPERATURE

    def test_native_value_with_valid_temperature(self, mock_coordinator):
        """Test sensor updates when device has temperature data."""
        # Arrange
        sensor = DysonTemperatureSensor(mock_coordinator)
        mock_coordinator.data = {"tmp": "2950"}  # 295.0 K = ~21.85°C

        # Act - trigger update
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is not None
        assert isinstance(sensor._attr_native_value, (int, float))
        # Should be around 21.85°C (295K - 273.15)
        assert 20 < sensor._attr_native_value < 25

    def test_native_value_with_no_device(self, mock_coordinator):
        """Test sensor handles missing temperature data gracefully."""
        # Arrange
        sensor = DysonTemperatureSensor(mock_coordinator)
        mock_coordinator.data = {}  # No temperature data

        # Act - trigger update
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is None


class TestDysonHumiditySensor:
    """Test DysonHumiditySensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        sensor = DysonHumiditySensor(mock_coordinator)

        # Assert
        assert sensor.coordinator == mock_coordinator
        assert sensor._attr_unique_id == "TEST-SERIAL-123_humidity"
        assert sensor._attr_name == "Humidity"
        assert sensor._attr_device_class == SensorDeviceClass.HUMIDITY

    def test_native_value_with_valid_humidity(self, mock_coordinator):
        """Test sensor updates when device has humidity data."""
        # Arrange
        sensor = DysonHumiditySensor(mock_coordinator)
        mock_coordinator.data = {"hact": "030"}  # 30% humidity

        # Act - trigger update with mocked device_utils
        with (
            patch.object(sensor, "async_write_ha_state"),
            patch("custom_components.hass_dyson.device_utils.get_sensor_data_safe", return_value="030"),
            patch("custom_components.hass_dyson.device_utils.convert_sensor_value_safe", return_value=30),
        ):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value == 30


class TestDysonFilterLifeSensor:
    """Test DysonFilterLifeSensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        sensor = DysonFilterLifeSensor(mock_coordinator, "hepa")

        # Assert
        assert sensor.coordinator == mock_coordinator
        assert sensor._attr_unique_id == "TEST-SERIAL-123_hepa_filter_life"
        assert sensor._attr_name == "Test Device HEPA Filter Life"
        assert sensor._attr_native_unit_of_measurement == PERCENTAGE

    def test_native_value_with_valid_filter_life(self, mock_coordinator):
        """Test sensor updates when device has filter life data."""
        # Arrange
        sensor = DysonFilterLifeSensor(mock_coordinator, "hepa")
        mock_coordinator.data = {"hepa_filter_life": 85}

        # Act - trigger update
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value == 85

    def test_native_value_with_no_device(self, mock_coordinator):
        """Test sensor handles missing filter life data gracefully."""
        # Arrange
        sensor = DysonFilterLifeSensor(mock_coordinator, "hepa")
        mock_coordinator.data = {}  # No filter life data

        # Act - trigger update
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is None


class TestDysonWiFiSensor:
    """Test DysonWiFiSensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        sensor = DysonWiFiSensor(mock_coordinator)

        # Assert
        assert sensor.coordinator == mock_coordinator
        assert sensor._attr_unique_id == "TEST-SERIAL-123_wifi"
        assert sensor._attr_name == "Test Device WiFi Signal"
        assert sensor._attr_device_class == SensorDeviceClass.SIGNAL_STRENGTH

    def test_native_value_with_valid_rssi(self, mock_coordinator):
        """Test native_value with valid WiFi RSSI data."""
        # Arrange
        sensor = DysonWiFiSensor(mock_coordinator)
        mock_coordinator.device.rssi = -50

        # Act & trigger update
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value == -50

    def test_native_value_with_no_device(self, mock_coordinator):
        """Test native_value when no device available."""
        # Arrange
        sensor = DysonWiFiSensor(mock_coordinator)
        mock_coordinator.device = None

        # Act & trigger update
        sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is None


class TestDysonAirQualitySensor:
    """Test DysonAirQualitySensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        sensor = DysonAirQualitySensor(mock_coordinator, "pm25")

        # Assert
        assert sensor.coordinator == mock_coordinator
        assert sensor._attr_unique_id == "TEST-SERIAL-123_pm25"
        assert sensor._attr_name == "PM25"
        assert sensor._attr_device_class == SensorDeviceClass.PM25
        assert sensor.sensor_type == "pm25"

    def test_native_value_calculation_pm25(self, mock_coordinator):
        """Test native_value for PM2.5 sensor type."""
        # Arrange
        sensor = DysonAirQualitySensor(mock_coordinator, "pm25")
        mock_coordinator.data = {"pm25": "0020"}  # 20 µg/m³

        # Act & trigger update
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is not None

    def test_native_value_with_no_data(self, mock_coordinator):
        """Test native_value when data is not available."""
        # Arrange
        sensor = DysonAirQualitySensor(mock_coordinator, "pm25")
        mock_coordinator.data = None

        # Act & trigger update
        sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is None


class TestSensorIntegration:
    """Test sensor integration scenarios."""

    def test_all_sensor_types_inherit_correctly(self, mock_coordinator):
        """Test that all sensor types inherit from the correct base classes."""
        # Act & Assert
        sensors = [
            DysonPM25Sensor(mock_coordinator),
            DysonPM10Sensor(mock_coordinator),
            DysonTemperatureSensor(mock_coordinator),
            DysonHumiditySensor(mock_coordinator),
            DysonFilterLifeSensor(mock_coordinator, "hepa"),
            DysonWiFiSensor(mock_coordinator),
            DysonAirQualitySensor(mock_coordinator, "pm25"),
        ]

        for sensor in sensors:
            assert isinstance(sensor, SensorEntity)

    @pytest.mark.asyncio
    async def test_multiple_capabilities_creates_multiple_sensors(self, mock_coordinator):
        """Test that devices with multiple capabilities create multiple sensors."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"
        async_add_entities = AsyncMock()

        mock_coordinator.device_capabilities = ["ExtendedAQ", "Heating"]
        mock_coordinator.device_category = ["EC"]
        hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) >= 3  # Should have PM2.5, PM10, temperature, and possibly more

    def test_sensor_data_consistency_across_updates(self, mock_coordinator):
        """Test that sensor values remain consistent across coordinator updates."""
        # Arrange
        sensor = DysonPM25Sensor(mock_coordinator)
        mock_coordinator.device.pm25 = 20

        # Act - trigger update and get values multiple times
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        value1 = sensor._attr_native_value
        value2 = sensor._attr_native_value

        # Assert
        assert value1 == value2
        assert value1 == 20
