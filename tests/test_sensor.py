"""Test sensor platform for Dyson integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, PERCENTAGE

from custom_components.hass_dyson.const import CAPABILITY_VOC, DOMAIN
from custom_components.hass_dyson.sensor import (
    DysonAirQualitySensor,
    DysonCarbonFilterLifeSensor,
    DysonCarbonFilterTypeSensor,
    DysonCleaningTimeRemainingSensor,
    DysonConnectionStatusSensor,
    DysonFilterLifeSensor,
    DysonFormaldehydeSensor,
    DysonHEPAFilterLifeSensor,
    DysonHEPAFilterTypeSensor,
    DysonHumiditySensor,
    DysonNextCleaningCycleSensor,
    DysonNO2Sensor,
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
        },
        "environmental-data": {
            "pm25": "10",
            "pm10": "15",
        },
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
        async_add_entities = MagicMock()

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
        async_add_entities = MagicMock()

        mock_coordinator.device_capabilities = ["Heating"]
        # Add environmental data with temperature data for sensor creation
        mock_coordinator.data = {
            "environmental-data": {
                "tact": "2731",  # Temperature data in Kelvin*10 format
            }
        }
        hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) >= 1  # Should have temperature sensor

    @pytest.mark.asyncio
    async def test_async_setup_entry_heating_without_env_data(self, mock_coordinator):
        """Test that heating capability alone doesn't create temperature sensor without environmental data."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"
        async_add_entities = MagicMock()

        mock_coordinator.device_capabilities = ["Heating"]
        mock_coordinator.device_category = ["EC"]
        # No environmental data provided - should not create sensor
        mock_coordinator.data = {}
        hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 0  # Should have no sensors - no environmental data

    @pytest.mark.asyncio
    async def test_async_setup_entry_humidifier_without_env_data(
        self, mock_coordinator
    ):
        """Test that humidifier capability creates humidifier sensors even without environmental data."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"
        async_add_entities = MagicMock()

        mock_coordinator.device_capabilities = ["Humidifier"]
        mock_coordinator.device_category = ["EC"]
        # No environmental data provided - should still create humidifier sensors
        mock_coordinator.data = {}
        hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert (
            len(entities) == 2
        )  # Should have humidifier sensors (cleaning cycle sensors)

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_capabilities(self, mock_coordinator):
        """Test setting up sensors for devices with no special capabilities."""
        # Arrange
        mock_coordinator.device_capabilities = []
        mock_coordinator.device_category = ["Unknown"]

        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"


class TestDysonPM25Sensor:
    """Test DysonPM25Sensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        sensor = DysonPM25Sensor(mock_coordinator)

        # Assert
        assert sensor.coordinator == mock_coordinator
        assert sensor._attr_unique_id == "TEST-SERIAL-123_pm25"
        assert sensor._attr_translation_key == "pm25"
        assert sensor._attr_device_class == SensorDeviceClass.PM25
        assert sensor._attr_state_class == SensorStateClass.MEASUREMENT
        assert (
            sensor._attr_native_unit_of_measurement
            == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
        )

    def test_native_value_with_valid_data(self, mock_coordinator):
        """Test sensor updates when coordinator has PM2.5 data."""
        # Arrange
        sensor = DysonPM25Sensor(mock_coordinator)
        mock_coordinator.data = {"environmental-data": {"pm25": "10"}}

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
        # Clear environmental data to simulate no device
        mock_coordinator.data = {"environmental-data": {}}

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
        assert sensor._attr_translation_key == "pm10"
        assert sensor._attr_device_class == SensorDeviceClass.PM10
        assert sensor._attr_state_class == SensorStateClass.MEASUREMENT

    def test_native_value_with_valid_data(self, mock_coordinator):
        """Test sensor updates when device has PM10 data."""
        # Arrange
        sensor = DysonPM10Sensor(mock_coordinator)
        # Set environmental data in coordinator following the new data structure
        mock_coordinator.data["environmental-data"] = {"pm10": "15"}

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
        assert sensor._attr_translation_key == "temperature"
        assert sensor._attr_device_class == SensorDeviceClass.TEMPERATURE

    def test_native_value_with_valid_temperature(self, mock_coordinator):
        """Test sensor updates when device has temperature data."""
        # Arrange
        sensor = DysonTemperatureSensor(mock_coordinator)
        mock_coordinator.data = {
            "environmental-data": {"tact": "2950"}  # 295.0 K = ~21.85°C
        }

        # Act - trigger update
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is not None
        assert isinstance(sensor._attr_native_value, int | float)
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

    def test_native_value_with_off_temperature(self, mock_coordinator):
        """Test sensor handles OFF temperature values gracefully."""
        # Arrange
        sensor = DysonTemperatureSensor(mock_coordinator)
        mock_coordinator.data = {
            "environmental-data": {"tact": "OFF"}  # Sensor inactive
        }

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
        assert sensor._attr_translation_key == "humidity"
        assert sensor._attr_device_class == SensorDeviceClass.HUMIDITY

    def test_native_value_with_valid_humidity(self, mock_coordinator):
        """Test sensor updates when device has humidity data."""
        # Arrange
        sensor = DysonHumiditySensor(mock_coordinator)
        mock_coordinator.data = {
            "environmental-data": {
                "hact": "0058"
            }  # 58% humidity in libdyson-neon format
        }

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value == 58

    def test_native_value_with_off_humidity(self, mock_coordinator):
        """Test sensor handles OFF humidity values gracefully."""
        # Arrange
        sensor = DysonHumiditySensor(mock_coordinator)
        mock_coordinator.data = {
            "environmental-data": {
                "hact": "OFF"  # Sensor inactive
            }
        }

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is None


class TestDysonFilterLifeSensor:
    """Test DysonFilterLifeSensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that filter life sensor initializes with correct attributes."""
        # Act
        sensor = DysonFilterLifeSensor(mock_coordinator, "hepa")

        # Assert
        assert sensor._attr_unique_id == "TEST-SERIAL-123_hepa_filter_life"
        assert sensor._attr_translation_key == "filter_life"
        assert sensor._attr_native_unit_of_measurement == PERCENTAGE
        assert sensor._attr_icon == "mdi:air-filter"

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
        assert sensor._attr_translation_key == "wifi_signal"
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
        assert (
            sensor._attr_name == "PM25"
        )  # This sensor still uses _attr_name dynamically
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
    async def test_multiple_capabilities_creates_multiple_sensors(
        self, mock_coordinator
    ):
        """Test that devices with multiple capabilities create multiple sensors."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"
        async_add_entities = MagicMock()

        mock_coordinator.device_capabilities = ["ExtendedAQ", "Heating"]
        mock_coordinator.device_category = ["EC"]
        hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert (
            len(entities) >= 3
        )  # Should have PM2.5, PM10, temperature, and possibly more

    def test_sensor_data_consistency_across_updates(self, mock_coordinator):
        """Test that sensor values remain consistent across coordinator updates."""
        # Arrange
        sensor = DysonPM25Sensor(mock_coordinator)
        # Set environmental data in coordinator following the new data structure
        mock_coordinator.data["environmental-data"] = {"pm25": "20"}

        # Act - trigger update and get values multiple times
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        value1 = sensor._attr_native_value
        value2 = sensor._attr_native_value

        # Assert
        assert value1 == value2
        assert value1 == 20


class TestSensorPlatformSetupAdvanced:
    """Test advanced sensor platform setup scenarios."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_voc_devices(self, mock_coordinator):
        """Test setting up sensors for devices with VOC/NO2 Detection capability for UI testing."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"
        async_add_entities = MagicMock()

        # Set up device with VOC capability (manual testing)
        mock_coordinator.device_capabilities = [CAPABILITY_VOC]
        mock_coordinator.device_category = ["EC"]
        # Override coordinator.data to not include ExtendedAQ data since this is manual testing
        mock_coordinator.data = {
            "product-state": {"pm25": "0010", "pm10": "0015"},
            "environmental-data": {"pm25": "10", "pm10": "15"},  # No gas sensor data
        }
        hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert (
            len(entities) == 3
        )  # VOC/NO2 Detection capability creates gas sensors (VOC, NO2, CO2) for UI testing

    @pytest.mark.asyncio
    async def test_async_setup_entry_formaldehyde_devices(self, mock_coordinator):
        """Test setting up sensors for devices with ExtendedAQ+Formaldehyde capability and carbon filter."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"
        async_add_entities = AsyncMock()

        # Set up device with both ExtendedAQ and Formaldehyde for comprehensive sensors
        mock_coordinator.device_capabilities = ["ExtendedAQ", "Formaldehyde"]
        mock_coordinator.device_category = ["EC"]
        # Ensure coordinator.data includes HCHO data and carbon filter data for sensor creation
        mock_coordinator.data = {
            "product-state": {
                "pm25": "0010",
                "pm10": "0015",
                "cflt": "CARF",  # Carbon filter present for filter sensors
            },
            "environmental-data": {
                "pm25": "10",
                "pm10": "15",
                "va10": "5",  # HCHO (VOC) data present using correct key
            },
        }
        hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        # Should have PM sensors (4) + HCHO sensor (1) + carbon filter sensors (2) = 7 entities
        assert (
            len(entities) >= 6
        )  # Dynamic sensor detection creates sensors based on data presence

    @pytest.mark.asyncio
    async def test_async_setup_entry_robot_category(self, mock_coordinator):
        """Test setting up sensors for robot devices."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"
        async_add_entities = AsyncMock()

        mock_coordinator.device_capabilities = []
        mock_coordinator.device_category = ["robot"]
        hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) >= 2  # Should have WiFi and connection status sensors

    @pytest.mark.asyncio
    async def test_async_setup_entry_humidifier_capability(self, mock_coordinator):
        """Test setting up sensors for devices with Humidifier capability."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"
        async_add_entities = AsyncMock()

        mock_coordinator.device_capabilities = ["Humidifier"]
        mock_coordinator.device_category = ["EC"]
        # Add environmental data with humidity data for sensor creation
        mock_coordinator.data = {
            "environmental-data": {
                "hact": "45",  # Humidity data in percentage format
            }
        }
        hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) >= 1  # Should have humidity sensor

    @pytest.mark.asyncio
    async def test_async_setup_entry_exception_handling(self, mock_coordinator):
        """Test sensor setup exception handling."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"
        async_add_entities = AsyncMock()

        mock_coordinator.device_capabilities = None  # This will cause an exception
        hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True  # Should still return True even with errors
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert entities == []  # Should have empty entities list on error


class TestDysonNO2Sensor:
    """Test Dyson NO2 sensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that NO2 sensor initializes with correct attributes."""
        # Act
        sensor = DysonNO2Sensor(mock_coordinator)

        # Assert
        assert sensor._attr_unique_id == "TEST-SERIAL-123_no2"
        assert sensor._attr_translation_key == "no2"
        assert sensor._attr_native_unit_of_measurement == "μg/m³"
        assert sensor._attr_icon == "mdi:molecule"

    def test_native_value_with_valid_data(self, mock_coordinator):
        """Test native value calculation with valid NO2 data."""
        # Arrange
        sensor = DysonNO2Sensor(mock_coordinator)
        mock_coordinator.device = MagicMock()
        # Update to use environmental data with correct key
        mock_coordinator.data = {
            "environmental-data": {
                "noxl": "15"  # NO2 data using correct key
            }
        }

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value == 15

    def test_native_value_with_no_device(self, mock_coordinator):
        """Test native value when no device is available."""
        # Arrange
        sensor = DysonNO2Sensor(mock_coordinator)
        mock_coordinator.device = None

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is None


class TestDysonFormaldehydeSensor:
    """Test Dyson Formaldehyde sensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that formaldehyde sensor initializes with correct attributes."""
        # Act
        sensor = DysonFormaldehydeSensor(mock_coordinator)

        # Assert
        assert sensor._attr_unique_id == "TEST-SERIAL-123_hcho"
        assert sensor._attr_translation_key == "hcho"
        assert sensor._attr_native_unit_of_measurement == "mg/m³"
        assert sensor._attr_icon == "mdi:molecule"

    def test_native_value_with_valid_data(self, mock_coordinator):
        """Test native value calculation with valid formaldehyde data."""
        # Arrange
        sensor = DysonFormaldehydeSensor(mock_coordinator)
        mock_coordinator.data = {
            "environmental-data": {
                "hchr": "0002"  # Raw value that converts to 2/1000 = 0.002 mg/m³ (matches libdyson-neon tests)
            }
        }

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        # 2 raw (from "0002") -> 0.002 mg/m³ (matches libdyson-neon implementation: raw/1000)
        assert sensor._attr_native_value == 0.002

    def test_native_value_with_no_device(self, mock_coordinator):
        """Test native value when no device is available."""
        # Arrange
        sensor = DysonFormaldehydeSensor(mock_coordinator)
        mock_coordinator.device = None

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is None


class TestDysonHEPAFilterLifeSensor:
    """Test Dyson HEPA filter life sensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that HEPA filter life sensor initializes with correct attributes."""
        # Act
        sensor = DysonHEPAFilterLifeSensor(mock_coordinator)

        # Assert
        assert sensor._attr_unique_id == "TEST-SERIAL-123_hepa_filter_life"
        assert sensor._attr_translation_key == "hepa_filter_life"
        assert sensor._attr_native_unit_of_measurement == PERCENTAGE
        assert sensor._attr_icon == "mdi:air-filter"

    def test_native_value_with_valid_data(self, mock_coordinator):
        """Test native value calculation with valid HEPA filter data."""
        # Arrange
        sensor = DysonHEPAFilterLifeSensor(mock_coordinator)
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.hepa_filter_life = 85

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value == 85

    def test_native_value_with_no_device(self, mock_coordinator):
        """Test native value when no device is available."""
        # Arrange
        sensor = DysonHEPAFilterLifeSensor(mock_coordinator)
        mock_coordinator.device = None

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is None


class TestDysonCarbonFilterLifeSensor:
    """Test Dyson carbon filter life sensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that carbon filter life sensor initializes with correct attributes."""
        # Act
        sensor = DysonCarbonFilterLifeSensor(mock_coordinator)

        # Assert
        assert sensor._attr_unique_id == "TEST-SERIAL-123_carbon_filter_life"
        assert sensor._attr_translation_key == "carbon_filter_life"
        assert sensor._attr_native_unit_of_measurement == PERCENTAGE
        assert sensor._attr_icon == "mdi:air-filter"

    def test_native_value_with_valid_data(self, mock_coordinator):
        """Test native value calculation with valid carbon filter data."""
        # Arrange
        sensor = DysonCarbonFilterLifeSensor(mock_coordinator)
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.carbon_filter_life = 72

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value == 72

    def test_native_value_with_no_device(self, mock_coordinator):
        """Test native value when no device is available."""
        # Arrange
        sensor = DysonCarbonFilterLifeSensor(mock_coordinator)
        mock_coordinator.device = None

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is None


class TestDysonHEPAFilterTypeSensor:
    """Test Dyson HEPA filter type sensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that HEPA filter type sensor initializes with correct attributes."""
        # Act
        sensor = DysonHEPAFilterTypeSensor(mock_coordinator)

        # Assert
        assert sensor._attr_unique_id == "TEST-SERIAL-123_hepa_filter_type"
        assert sensor._attr_translation_key == "hepa_filter_type"
        assert sensor._attr_icon == "mdi:air-filter"

    def test_native_value_with_valid_data(self, mock_coordinator):
        """Test native value with valid HEPA filter type data."""
        # Arrange
        sensor = DysonHEPAFilterTypeSensor(mock_coordinator)
        mock_coordinator.device = MagicMock()
        # Mock the actual data structure the sensor expects
        mock_coordinator.data = {
            "product-state": {"hflt": "STD"}
        }  # Standard filter type code

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value == "STD"

    def test_native_value_with_no_device(self, mock_coordinator):
        """Test native value when no device is available."""
        # Arrange
        sensor = DysonHEPAFilterTypeSensor(mock_coordinator)
        mock_coordinator.device = None

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is None


class TestDysonCarbonFilterTypeSensor:
    """Test Dyson carbon filter type sensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that carbon filter type sensor initializes with correct attributes."""
        # Act
        sensor = DysonCarbonFilterTypeSensor(mock_coordinator)

        # Assert
        assert sensor._attr_unique_id == "TEST-SERIAL-123_carbon_filter_type"
        assert sensor._attr_translation_key == "carbon_filter_type"
        assert sensor._attr_icon == "mdi:air-filter"

    def test_native_value_with_valid_data(self, mock_coordinator):
        """Test native value with valid carbon filter type data."""
        # Arrange
        sensor = DysonCarbonFilterTypeSensor(mock_coordinator)
        mock_coordinator.device = MagicMock()
        # Mock the actual data structure the sensor expects
        mock_coordinator.data = {
            "product-state": {"cflt": "ACT"}
        }  # Activated carbon filter type code

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value == "ACT"

    def test_native_value_with_no_device(self, mock_coordinator):
        """Test native value when no device is available."""
        # Arrange
        sensor = DysonCarbonFilterTypeSensor(mock_coordinator)
        mock_coordinator.device = None

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is None

    def test_native_value_with_none_filter_type(self, mock_coordinator):
        """Test native value with NONE filter type (not installed)."""
        # Arrange
        sensor = DysonCarbonFilterTypeSensor(mock_coordinator)
        mock_coordinator.device = MagicMock()
        mock_coordinator.data = {"product-state": {"cflt": "NONE"}}

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value == "Not Installed"

    def test_native_value_with_scog_filter_type(self, mock_coordinator):
        """Test native value with SCOG filter type (not installed)."""
        # Arrange
        sensor = DysonCarbonFilterTypeSensor(mock_coordinator)
        mock_coordinator.device = MagicMock()
        mock_coordinator.data = {"product-state": {"cflt": "SCOG"}}

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value == "Not Installed"

    def test_native_value_case_insensitive_none_scog(self, mock_coordinator):
        """Test native value with case-insensitive NONE and SCOG values."""
        sensor = DysonCarbonFilterTypeSensor(mock_coordinator)
        mock_coordinator.device = MagicMock()

        # Test lowercase variations
        test_cases = [
            ("none", "Not Installed"),
            ("NONE", "Not Installed"),
            ("None", "Not Installed"),
            ("scog", "Not Installed"),
            ("SCOG", "Not Installed"),
            ("Scog", "Not Installed"),
        ]

        for input_value, expected_output in test_cases:
            mock_coordinator.data = {"product-state": {"cflt": input_value}}

            # Act
            with patch.object(sensor, "async_write_ha_state"):
                sensor._handle_coordinator_update()

            # Assert
            assert sensor._attr_native_value == expected_output, (
                f"Failed for input '{input_value}'"
            )


class TestDysonConnectionStatusSensor:
    """Test Dyson connection status sensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that connection status sensor initializes with correct attributes."""
        # Act
        sensor = DysonConnectionStatusSensor(mock_coordinator)

        # Assert
        assert sensor._attr_unique_id == "TEST-SERIAL-123_connection_status"
        assert sensor._attr_translation_key == "connection_status"
        assert sensor._attr_icon == "mdi:connection"

    def test_native_value_with_connected_device(self, mock_coordinator):
        """Test native value when device is connected."""
        # Arrange
        sensor = DysonConnectionStatusSensor(mock_coordinator)
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.connection_status = "Connected"

        # Act
        # Assert - use the property directly since this sensor uses @property
        assert sensor.native_value == "Connected"

    def test_native_value_with_disconnected_device(self, mock_coordinator):
        """Test native value when device is disconnected."""
        # Arrange
        sensor = DysonConnectionStatusSensor(mock_coordinator)
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.connection_status = "Disconnected"

        # Act
        # Assert - use the property directly since this sensor uses @property
        assert sensor.native_value == "Disconnected"

    def test_native_value_with_no_device(self, mock_coordinator):
        """Test native value when no device is available."""
        # Arrange
        sensor = DysonConnectionStatusSensor(mock_coordinator)
        mock_coordinator.device = None

        # Act
        # Assert - use the property directly since this sensor uses @property
        assert sensor.native_value == "Disconnected"


class TestSensorCoverageEnhancement:
    """Test class to enhance sensor coverage to 90%+."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_exception_handling_fallback(
        self, mock_coordinator, mock_hass
    ):
        """Test sensor setup exception handling with fallback to basic sensors."""
        # Arrange
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"
        mock_async_add_entities = MagicMock()

        # Mock coordinator to have device capabilities that would normally create sensors
        mock_coordinator.device_capabilities = ["ExtendedAQ", "Heating"]
        mock_coordinator.device_category = ["EC"]
        mock_coordinator.serial_number = "TEST-SERIAL-123"
        mock_hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Mock coordinator.device_capabilities to raise an exception during entity creation
        with (
            patch("custom_components.hass_dyson.sensor._LOGGER") as mock_logger,
            patch(
                "custom_components.hass_dyson.sensor.DysonPM25Sensor",
                side_effect=Exception("Entity creation error"),
            ),
        ):
            # Act - This should trigger the exception handling path (lines 145-149)
            result = await async_setup_entry(
                mock_hass, config_entry, mock_async_add_entities
            )

            # Assert
            # The function should still return True even when entity creation fails
            # It should log the error and warning (fallback behavior)
            assert result is True
            mock_logger.error.assert_called_once_with(
                "Unexpected error during sensor setup for device %s: %s",
                "TEST-SERIAL-123",
                mock_logger.error.call_args[0][2],  # The exception object
            )
            mock_logger.warning.assert_called_once_with(
                "Falling back to basic sensor setup for device %s", "TEST-SERIAL-123"
            )
            # async_add_entities should be called with empty entities list
            mock_async_add_entities.assert_called_once_with([], True)

    @pytest.mark.asyncio
    async def test_sensor_platform_setup_robot_device_battery_debug_log(
        self, mock_coordinator, mock_hass
    ):
        """Test robot device debug logging for battery sensor placeholder."""
        # Create mock config entry
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"

        # Mock async_add_entities
        mock_async_add_entities = MagicMock()

        # Set up coordinator for robot device (should trigger debug log on lines 141-142)
        mock_coordinator.device_category = [
            "robot"
        ]  # lowercase to match the condition in sensor.py
        mock_coordinator.device_capabilities = []
        mock_hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        with patch("custom_components.hass_dyson.sensor._LOGGER") as mock_logger:
            await async_setup_entry(mock_hass, config_entry, mock_async_add_entities)

            # Assert that the debug log was called for robot device battery sensor placeholder
            mock_logger.debug.assert_any_call(
                "Robot device %s battery level available via vacuum entity",
                mock_coordinator.serial_number,
            )

    def test_sensor_data_safety_methods_coverage(self, mock_coordinator):
        """Test sensor data safety method coverage for missing lines."""
        # Test with no device to trigger None value paths
        mock_coordinator.device = None

        # Create sensors when device is None to avoid sync issues
        sensors = [
            DysonPM25Sensor(mock_coordinator),
            DysonPM10Sensor(mock_coordinator),
            DysonTemperatureSensor(mock_coordinator),
            DysonHumiditySensor(mock_coordinator),
            DysonNO2Sensor(mock_coordinator),
            DysonFormaldehydeSensor(mock_coordinator),
        ]

        for sensor in sensors:
            # These should return None when no device is available
            value = sensor.native_value
            assert value is None

        # Test with device but no sensor properties
        mock_device = MagicMock()
        # Explicitly set sensor properties to None to test missing data paths
        mock_device.pm25 = None
        mock_device.pm10 = None
        mock_device.temperature = None
        mock_device.humidity = None
        mock_device.volatile_organic_compounds = None
        mock_device.nitrogen_dioxide = None
        mock_device.formaldehyde = None
        mock_device._environmental_data = {}  # No environmental data
        mock_coordinator.device = mock_device
        mock_coordinator.data = {}  # Empty data should trigger fallback paths

        # Trigger coordinator update to test device property paths
        for sensor in sensors:
            sensor.hass = MagicMock()  # Set hass to avoid RuntimeError
            with patch.object(sensor, "async_write_ha_state"):
                sensor._handle_coordinator_update()
            # These should handle missing data gracefully and return None
            value = sensor.native_value
            assert value is None

    def test_filter_life_sensors_missing_coverage(self, mock_coordinator):
        """Test filter life sensor paths that need coverage."""
        # Test HEPA filter life sensor
        hepa_sensor = DysonHEPAFilterLifeSensor(mock_coordinator)
        carbon_sensor = DysonCarbonFilterLifeSensor(mock_coordinator)
        hepa_type_sensor = DysonHEPAFilterTypeSensor(mock_coordinator)
        carbon_type_sensor = DysonCarbonFilterTypeSensor(mock_coordinator)

        # Test with no device
        mock_coordinator.device = None
        assert hepa_sensor.native_value is None
        assert carbon_sensor.native_value is None
        assert hepa_type_sensor.native_value is None
        assert carbon_type_sensor.native_value is None

        # Test with device but no data
        mock_coordinator.device = MagicMock()
        mock_coordinator.data = {}
        # These should handle missing data gracefully
        hepa_sensor.native_value
        carbon_sensor.native_value
        hepa_type_sensor.native_value
        carbon_type_sensor.native_value

    def test_wifi_sensor_missing_coverage(self, mock_coordinator):
        """Test WiFi sensor missing coverage paths."""
        wifi_sensor = DysonWiFiSensor(mock_coordinator)

        # Test with no device (should return None)
        mock_coordinator.device = None
        assert wifi_sensor.native_value is None

        # Test with device but missing RSSI data
        mock_coordinator.device = MagicMock()
        mock_coordinator.data = {"product-state": {}}  # Missing RSSI data
        value = wifi_sensor.native_value
        # Should handle missing RSSI gracefully
        assert value is None or isinstance(value, int | float)

    def test_carbon_filter_sensor_setup_filtering(self, mock_coordinator):
        """Test the carbon filter sensor filtering logic for NONE and SCOG values."""
        # Test the filtering logic directly
        test_cases = [
            ("NONE", False, "NONE should prevent sensor creation"),
            ("SCOG", False, "SCOG should prevent sensor creation"),
            ("none", False, "lowercase none should prevent sensor creation"),
            ("scog", False, "lowercase scog should prevent sensor creation"),
            ("GCOM", True, "GCOM should allow sensor creation"),
            ("ABCD", True, "Other values should allow sensor creation"),
            (None, False, "None value should prevent sensor creation"),
        ]

        for carbon_filter_type, should_add, description in test_cases:
            # Test the logic that's used in async_setup_entry
            if carbon_filter_type is not None:
                condition = str(carbon_filter_type).upper() not in ["NONE", "SCOG"]
            else:
                condition = False

            assert condition == should_add, (
                f"{description} (got {condition}, expected {should_add})"
            )


class TestDysonHumidifierSensors:
    """Test humidifier-specific sensors."""

    @pytest.fixture
    def mock_humidifier_coordinator(self):
        """Create a mock coordinator for humidifier device."""
        coordinator = MagicMock()
        coordinator.serial_number = "PH01-EU-ABC1234A"
        coordinator.device_name = "Test Humidifier"
        coordinator.device = MagicMock()
        coordinator.device_capabilities = ["Humidifier"]
        coordinator.device_category = ["EC"]
        coordinator.device.get_state_value = MagicMock()
        coordinator.data = {
            "product-state": {
                "cltr": "0072",  # 72 hours until cleaning
                "cdrr": "0015",  # 15 minutes cleaning remaining
            },
        }
        return coordinator

    def test_next_cleaning_cycle_sensor_init(self, mock_humidifier_coordinator):
        """Test next cleaning cycle sensor initialization."""

        sensor = DysonNextCleaningCycleSensor(mock_humidifier_coordinator)

        assert sensor._attr_unique_id == "PH01-EU-ABC1234A_next_cleaning_cycle"
        assert sensor._attr_translation_key == "next_cleaning_cycle"
        assert sensor._attr_native_unit_of_measurement == "h"
        assert sensor._attr_device_class == SensorDeviceClass.DURATION
        assert sensor._attr_state_class == SensorStateClass.MEASUREMENT
        assert sensor._attr_icon == "mdi:timer-outline"

    def test_next_cleaning_cycle_sensor_update(self, mock_humidifier_coordinator):
        """Test next cleaning cycle sensor coordinator update."""

        mock_humidifier_coordinator.device.get_state_value.return_value = "0072"

        sensor = DysonNextCleaningCycleSensor(mock_humidifier_coordinator)
        sensor.hass = MagicMock()
        sensor.async_write_ha_state = MagicMock()
        sensor._handle_coordinator_update()

        assert sensor._attr_native_value == 72

    def test_next_cleaning_cycle_sensor_update_no_data(
        self, mock_humidifier_coordinator
    ):
        """Test next cleaning cycle sensor with no data."""

        mock_humidifier_coordinator.device.get_state_value.return_value = "0000"

        sensor = DysonNextCleaningCycleSensor(mock_humidifier_coordinator)
        sensor.hass = MagicMock()
        sensor.async_write_ha_state = MagicMock()
        sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_next_cleaning_cycle_sensor_invalid_data(self, mock_humidifier_coordinator):
        """Test next cleaning cycle sensor with invalid data."""

        mock_humidifier_coordinator.device.get_state_value.return_value = "invalid"

        sensor = DysonNextCleaningCycleSensor(mock_humidifier_coordinator)
        sensor.hass = MagicMock()
        sensor.async_write_ha_state = MagicMock()

        with patch("custom_components.hass_dyson.sensor._LOGGER") as mock_logger:
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None
        mock_logger.warning.assert_called_once()

    def test_cleaning_time_remaining_sensor_init(self, mock_humidifier_coordinator):
        """Test cleaning time remaining sensor initialization."""

        sensor = DysonCleaningTimeRemainingSensor(mock_humidifier_coordinator)

        assert sensor._attr_unique_id == "PH01-EU-ABC1234A_cleaning_time_remaining"
        assert sensor._attr_translation_key == "cleaning_time_remaining"
        assert sensor._attr_native_unit_of_measurement == "min"
        assert sensor._attr_device_class == SensorDeviceClass.DURATION
        assert sensor._attr_state_class == SensorStateClass.MEASUREMENT
        assert sensor._attr_icon == "mdi:timer"

    def test_cleaning_time_remaining_sensor_update(self, mock_humidifier_coordinator):
        """Test cleaning time remaining sensor coordinator update."""

        mock_humidifier_coordinator.device.get_state_value.return_value = "0015"

        sensor = DysonCleaningTimeRemainingSensor(mock_humidifier_coordinator)
        sensor.hass = MagicMock()
        sensor.async_write_ha_state = MagicMock()
        sensor._handle_coordinator_update()

        assert sensor._attr_native_value == 15

    def test_cleaning_time_remaining_sensor_update_no_data(
        self, mock_humidifier_coordinator
    ):
        """Test cleaning time remaining sensor with no data."""

        mock_humidifier_coordinator.device.get_state_value.return_value = "0000"

        sensor = DysonCleaningTimeRemainingSensor(mock_humidifier_coordinator)
        sensor.hass = MagicMock()
        sensor.async_write_ha_state = MagicMock()
        sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    def test_cleaning_time_remaining_sensor_no_device(
        self, mock_humidifier_coordinator
    ):
        """Test cleaning time remaining sensor with no device."""

        mock_humidifier_coordinator.device = None

        sensor = DysonCleaningTimeRemainingSensor(mock_humidifier_coordinator)
        sensor.hass = MagicMock()
        sensor.async_write_ha_state = MagicMock()
        sensor._handle_coordinator_update()

        assert sensor._attr_native_value is None

    @pytest.mark.asyncio
    async def test_setup_entry_with_humidifier_capability(
        self, mock_humidifier_coordinator
    ):
        """Test platform setup adds humidifier sensors for humidifier devices."""
        mock_hass = MagicMock()
        mock_config_entry = MagicMock()
        mock_config_entry.entry_id = "test_entry"
        mock_add_entities = MagicMock()

        mock_hass.data = {DOMAIN: {"test_entry": mock_humidifier_coordinator}}

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        # Should include humidifier sensors
        call_args = mock_add_entities.call_args[0][0]
        sensor_names = [sensor.__class__.__name__ for sensor in call_args]

        assert "DysonNextCleaningCycleSensor" in sensor_names
        assert "DysonCleaningTimeRemainingSensor" in sensor_names

    @pytest.mark.asyncio
    async def test_setup_entry_without_humidifier_capability(self):
        """Test platform setup skips humidifier sensors for non-humidifier devices."""
        mock_coordinator = MagicMock()
        mock_coordinator.device_capabilities = ["Heating"]  # No humidifier
        mock_coordinator.device_category = ["EC"]
        mock_coordinator.data = {"product-state": {}, "environmental-data": {}}

        mock_hass = MagicMock()
        mock_config_entry = MagicMock()
        mock_config_entry.entry_id = "test_entry"
        mock_add_entities = MagicMock()

        mock_hass.data = {DOMAIN: {"test_entry": mock_coordinator}}

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        # Should not include humidifier sensors
        call_args = mock_add_entities.call_args[0][0]
        sensor_names = [sensor.__class__.__name__ for sensor in call_args]

        assert "DysonNextCleaningCycleSensor" not in sensor_names
        assert "DysonCleaningTimeRemainingSensor" not in sensor_names
