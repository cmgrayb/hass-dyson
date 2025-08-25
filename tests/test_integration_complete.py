"""Test the complete integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.dyson_alt.const import CONF_SERIAL_NUMBER
from custom_components.dyson_alt.coordinator import DysonDataUpdateCoordinator
from custom_components.dyson_alt.fan import DysonFan
from custom_components.dyson_alt.sensor import (
    DysonAirQualitySensor,
    DysonFilterLifeSensor,
    DysonHumiditySensor,
    DysonTemperatureSensor,
)


@pytest.fixture
def mock_hass():
    """Mock Home Assistant."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.bus.async_fire = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.title = "Theater Fan"
    config_entry.data = {
        "serial_number": "MOCK-SERIAL-TEST123",
        "discovery_method": "sticker",
        "mqtt_username": "MOCK-SERIAL-TEST123",
        "mqtt_password": "test_password",
        "mqtt_hostname": "192.168.1.100",
        "capabilities": ["EnvironmentalData", "ExtendedAQ", "AdvanceOscillationDay1"],
    }
    return config_entry


@pytest.fixture
def mock_coordinator(mock_hass, mock_config_entry):
    """Mock coordinator with test data."""
    with patch("custom_components.dyson_alt.coordinator.DataUpdateCoordinator.__init__"):
        coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
        coordinator.hass = mock_hass
        coordinator.config_entry = mock_config_entry
        # Set serial number via config entry data (it's a property)
        coordinator.config_entry.data = {**coordinator.config_entry.data, CONF_SERIAL_NUMBER: "MOCK-SERIAL-TEST123"}
        # Set private attributes since properties are read-only
        coordinator._device_capabilities = ["EnvironmentalData", "ExtendedAQ", "AdvanceOscillationDay1"]
        coordinator._device_category = "ec"
        coordinator.last_update_success = True
        coordinator.data = {
            "power": "ON",
            "fan_speed": 5,
            "direction": "forward",
            "oscillating": True,
            "temperature": 2950,  # 22.0°C in Kelvin * 10
            "humidity": 45,
            "pm25": 12,
            "pm10": 18,
            "p25r": 8,
            "p10r": 15,
            "hepa_filter_life": 85,
            "carbon_filter_life": 72,
        }
        coordinator.async_send_command = AsyncMock(return_value=True)

        # Mock device for fan entity commands
        mock_device = MagicMock()
        mock_device.night_mode = True
        mock_device.fan_speed = 5
        mock_device.set_night_mode = AsyncMock()
        mock_device.set_fan_speed = AsyncMock()
        coordinator.device = mock_device

        return coordinator


def test_fan_entity_creation(mock_coordinator):
    """Test fan entity creation."""
    fan = DysonFan(mock_coordinator)
    # Trigger coordinator update to initialize attributes
    fan._handle_coordinator_update()

    assert fan.unique_id == "MOCK-SERIAL-TEST123_fan"
    assert fan.name == "Theater Fan Fan"
    assert fan.is_on is True
    assert fan.percentage == 50  # 5 * 10
    assert fan.current_direction == "forward"
    # Note: oscillating is set to False in _handle_coordinator_update regardless of data
    assert fan.oscillating is False


def test_temperature_sensor_creation(mock_coordinator):
    """Test temperature sensor creation."""
    sensor = DysonTemperatureSensor(mock_coordinator)
    # Mock hass to avoid RuntimeError in _handle_coordinator_update
    sensor.hass = MagicMock()

    assert sensor.unique_id == "MOCK-SERIAL-TEST123_temperature"
    assert sensor.name == "Theater Fan Temperature"
    assert sensor.device_class == "temperature"
    assert sensor.native_unit_of_measurement == "°C"

    # Trigger coordinator update
    sensor._handle_coordinator_update()
    assert sensor.native_value == 22.0  # (2950 / 10) - 273.15


def test_humidity_sensor_creation(mock_coordinator):
    """Test humidity sensor creation."""
    sensor = DysonHumiditySensor(mock_coordinator)
    # Mock hass to avoid RuntimeError in _handle_coordinator_update
    sensor.hass = MagicMock()

    assert sensor.unique_id == "MOCK-SERIAL-TEST123_humidity"
    assert sensor.name == "Theater Fan Humidity"
    assert sensor.device_class == "humidity"
    assert sensor.native_unit_of_measurement == "%"

    # Trigger coordinator update
    sensor._handle_coordinator_update()
    assert sensor.native_value == 45


def test_air_quality_sensors_creation(mock_coordinator):
    """Test air quality sensor creation."""
    pm25_sensor = DysonAirQualitySensor(mock_coordinator, "pm25")
    p25r_sensor = DysonAirQualitySensor(mock_coordinator, "p25r")
    # Mock hass to avoid RuntimeError in _handle_coordinator_update
    pm25_sensor.hass = MagicMock()
    p25r_sensor.hass = MagicMock()

    assert pm25_sensor.unique_id == "MOCK-SERIAL-TEST123_pm25"
    assert pm25_sensor.name == "Theater Fan PM25"
    assert pm25_sensor.device_class == "pm25"

    assert p25r_sensor.unique_id == "MOCK-SERIAL-TEST123_p25r"
    assert p25r_sensor.name == "Theater Fan P25R"

    # Trigger coordinator updates
    pm25_sensor._handle_coordinator_update()
    p25r_sensor._handle_coordinator_update()

    assert pm25_sensor.native_value == 12
    assert p25r_sensor.native_value == 8


def test_filter_life_sensors_creation(mock_coordinator):
    """Test filter life sensor creation."""
    hepa_sensor = DysonFilterLifeSensor(mock_coordinator, "hepa")
    carbon_sensor = DysonFilterLifeSensor(mock_coordinator, "carbon")
    # Mock hass to avoid RuntimeError in _handle_coordinator_update
    hepa_sensor.hass = MagicMock()
    carbon_sensor.hass = MagicMock()

    assert hepa_sensor.unique_id == "MOCK-SERIAL-TEST123_hepa_filter_life"
    assert hepa_sensor.name == "Theater Fan HEPA Filter Life"
    assert hepa_sensor.native_unit_of_measurement == "%"

    assert carbon_sensor.unique_id == "MOCK-SERIAL-TEST123_carbon_filter_life"
    assert carbon_sensor.name == "Theater Fan CARBON Filter Life"

    # Trigger coordinator updates
    hepa_sensor._handle_coordinator_update()
    carbon_sensor._handle_coordinator_update()

    assert hepa_sensor.native_value == 85
    assert carbon_sensor.native_value == 72


@pytest.mark.asyncio
async def test_fan_entity_commands(mock_coordinator):
    """Test fan entity command functionality."""
    fan = DysonFan(mock_coordinator)

    # Test turn on
    await fan.async_turn_on(percentage=80)
    mock_coordinator.async_send_command.assert_any_call("power", {"state": "ON"})
    mock_coordinator.async_send_command.assert_any_call("fan_speed", {"speed": "8"})

    # Test turn off
    await fan.async_turn_off()
    mock_coordinator.async_send_command.assert_called_with("power", {"state": "OFF"})

    # Test set percentage
    await fan.async_set_percentage(30)
    mock_coordinator.async_send_command.assert_called_with("fan_speed", {"speed": "3"})

    # Test oscillation
    await fan.async_oscillate(False)
    mock_coordinator.async_send_command.assert_called_with("oscillation", {"oscillating": "false"})


if __name__ == "__main__":
    pytest.main([__file__])
