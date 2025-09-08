"""Test sensor platform for Dyson integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, PERCENTAGE

from custom_components.hass_dyson.const import DOMAIN
from custom_components.hass_dyson.sensor import (
    DysonAirQualitySensor,
    DysonCarbonFilterLifeSensor,
    DysonCarbonFilterTypeSensor,
    DysonConnectionStatusSensor,
    DysonFilterLifeSensor,
    DysonFormaldehydeSensor,
    DysonHEPAFilterLifeSensor,
    DysonHEPAFilterTypeSensor,
    DysonHumiditySensor,
    DysonNO2Sensor,
    DysonPM10Sensor,
    DysonPM25Sensor,
    DysonTemperatureSensor,
    DysonVOCSensor,
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


class TestSensorPlatformSetupAdvanced:
    """Test advanced sensor platform setup scenarios."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_voc_devices(self, mock_coordinator):
        """Test setting up sensors for devices with VOC capability."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"
        async_add_entities = MagicMock()

        mock_coordinator.device_capabilities = ["VOC"]
        mock_coordinator.device_category = ["EC"]
        hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) >= 2  # Should have VOC and NO2 sensors

    @pytest.mark.asyncio
    async def test_async_setup_entry_formaldehyde_devices(self, mock_coordinator):
        """Test setting up sensors for devices with Formaldehyde capability."""
        # Arrange
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"
        async_add_entities = AsyncMock()

        mock_coordinator.device_capabilities = ["Formaldehyde"]
        mock_coordinator.device_category = ["EC"]
        hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) >= 3  # Should have formaldehyde sensor and carbon filter sensors

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


class TestDysonVOCSensor:
    """Test Dyson VOC sensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that VOC sensor initializes with correct attributes."""
        # Act
        sensor = DysonVOCSensor(mock_coordinator)

        # Assert
        assert sensor._attr_unique_id == "TEST-SERIAL-123_voc"
        assert sensor._attr_name == "Test Device VOC"
        assert sensor._attr_native_unit_of_measurement == "ppb"
        assert sensor._attr_icon == "mdi:chemical-weapon"

    def test_native_value_with_valid_data(self, mock_coordinator):
        """Test native value calculation with valid VOC data."""
        # Arrange
        sensor = DysonVOCSensor(mock_coordinator)
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.voc = 25

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value == 25

    def test_native_value_with_no_device(self, mock_coordinator):
        """Test native value when no device is available."""
        # Arrange
        sensor = DysonVOCSensor(mock_coordinator)
        mock_coordinator.device = None

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value is None


class TestDysonNO2Sensor:
    """Test Dyson NO2 sensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that NO2 sensor initializes with correct attributes."""
        # Act
        sensor = DysonNO2Sensor(mock_coordinator)

        # Assert
        assert sensor._attr_unique_id == "TEST-SERIAL-123_no2"
        assert sensor._attr_name == "Test Device NO2"
        assert sensor._attr_native_unit_of_measurement == "ppb"
        assert sensor._attr_icon == "mdi:molecule"

    def test_native_value_with_valid_data(self, mock_coordinator):
        """Test native value calculation with valid NO2 data."""
        # Arrange
        sensor = DysonNO2Sensor(mock_coordinator)
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.no2 = 15

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
        assert sensor._attr_unique_id == "TEST-SERIAL-123_formaldehyde"
        assert sensor._attr_name == "Test Device Formaldehyde"
        assert sensor._attr_native_unit_of_measurement == "ppb"
        assert sensor._attr_icon == "mdi:chemical-weapon"

    def test_native_value_with_valid_data(self, mock_coordinator):
        """Test native value calculation with valid formaldehyde data."""
        # Arrange
        sensor = DysonFormaldehydeSensor(mock_coordinator)
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.formaldehyde = 8

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        assert sensor._attr_native_value == 8

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
        assert sensor._attr_name == "Test Device HEPA Filter Life"
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
        assert sensor._attr_name == "Carbon Filter Life"
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
        assert sensor._attr_name == "Test Device HEPA Filter Type"
        assert sensor._attr_icon == "mdi:air-filter"

    def test_native_value_with_valid_data(self, mock_coordinator):
        """Test native value with valid HEPA filter type data."""
        # Arrange
        sensor = DysonHEPAFilterTypeSensor(mock_coordinator)
        mock_coordinator.device = MagicMock()
        # Mock the actual data structure the sensor expects
        mock_coordinator.data = {"product-state": {"hflt": "STD"}}  # Standard filter type code

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
        assert sensor._attr_name == "Carbon Filter Type"
        assert sensor._attr_icon == "mdi:air-filter"

    def test_native_value_with_valid_data(self, mock_coordinator):
        """Test native value with valid carbon filter type data."""
        # Arrange
        sensor = DysonCarbonFilterTypeSensor(mock_coordinator)
        mock_coordinator.device = MagicMock()
        # Mock the actual data structure the sensor expects
        mock_coordinator.data = {"product-state": {"cflt": "ACT"}}  # Activated carbon filter type code

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


class TestDysonConnectionStatusSensor:
    """Test Dyson connection status sensor."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that connection status sensor initializes with correct attributes."""
        # Act
        sensor = DysonConnectionStatusSensor(mock_coordinator)

        # Assert
        assert sensor._attr_unique_id == "TEST-SERIAL-123_connection_status"
        assert sensor._attr_name == "Test Device Connection Status"
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
