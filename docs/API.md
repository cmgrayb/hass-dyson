# API Documentation

This document provides comprehensive API documentation for the Dyson Home Assistant integration, including code examples and usage patterns for developers.

## Table of Contents

- [Integration Setup](#integration-setup)
- [Device Management](#device-management)
- [Entity System](#entity-system)
- [Service Registration](#service-registration)
- [Data Coordination](#data-coordination)
- [MQTT Communication](#mqtt-communication)
- [Error Handling](#error-handling)

## Integration Setup

### Basic Integration Initialization

```python
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from custom_components.hass_dyson import async_setup_entry

async def setup_dyson_integration(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up the Dyson integration from a config entry.

    This function initializes the integration, creates the data coordinator,
    establishes device connections, and registers services.
    """
    result = await async_setup_entry(hass, entry)
    return result
```

### Configuration Entry Data Structure

```python
# Example config entry data for cloud discovery
cloud_config = {
    "discovery_method": "cloud",
    "email": "user@example.com",
    "password": "encrypted_password",
    "country": "US",
    "auto_add_devices": True,
    "enable_polling": True
}

# Example config entry data for manual setup
manual_config = {
    "discovery_method": "sticker",
    "serial_number": "VS6-EU-HJA1234A",
    "credential": "device_password_from_sticker",
    "device_type": "ec",
    "mqtt_prefix": "438M",
    "hostname": "192.168.1.100",  # Optional
    "capabilities": ["AdvanceOscillationDay1", "Scheduling", "ExtendedAQ"]
}
```

## Device Management

### DysonDevice Class

The `DysonDevice` class handles direct MQTT communication with Dyson devices.

```python
from custom_components.hass_dyson.device import DysonDevice

# Initialize device connection
device = DysonDevice(
    serial_number="VS6-EU-HJA1234A",
    credential="device_password",
    device_type="ec"
)

# Connect to device
success = await device.connect()
if success:
    print("Device connected successfully")
else:
    print("Failed to connect to device")

# Check connection status
if device.is_connected:
    print("Device is online")

# Send commands to device
await device.set_fan_speed(5)
await device.set_oscillation(True)
await device.set_night_mode(True)
```

### Device Control Methods

```python
# Fan control
await device.set_fan_speed(7)  # Speed 1-10
await device.set_fan_on_off(True)  # Turn fan on/off
await device.set_oscillation(True)  # Enable oscillation
await device.set_night_mode(True)  # Enable night mode

# Climate control (for heating models)
await device.set_target_temperature(22.5)  # Set target temperature
await device.set_heater_mode("HEAT")  # Enable heating
await device.set_fan_direction("FRONT")  # Set airflow direction

# Air quality and monitoring
current_state = device.get_current_state()
pm25_level = current_state.get("pm25", 0)
temperature = current_state.get("temperature", 0)
```

### Device State Properties

```python
# Access device state information
print(f"Fan speed: {device.fan_speed}")
print(f"Temperature: {device.temperature}°C")
print(f"Humidity: {device.humidity}%")
print(f"PM2.5: {device.pm25} μg/m³")
print(f"Filter life: {device.filter_life}%")
print(f"Connection status: {device.connection_status}")
```

## Entity System

### DysonEntity Base Class

All Dyson entities inherit from `DysonEntity`, which provides common functionality.

```python
from custom_components.hass_dyson.entity import DysonEntity

class CustomDysonEntity(DysonEntity):
    """Custom entity implementation example."""

    def __init__(self, coordinator, entity_description):
        super().__init__(coordinator, entity_description)

    @property
    def native_value(self):
        """Return the current value."""
        return self.coordinator.data.get("custom_value")

    async def async_update(self):
        """Update entity state from coordinator."""
        await self.coordinator.async_request_refresh()
```

### Fan Entity Implementation

```python
from custom_components.hass_dyson.fan import DysonFan

# Fan entity with climate integration
class DysonFanEntity(DysonFan):
    """Example of fan entity with heating support."""

    @property
    def supported_features(self):
        """Return supported features."""
        features = FanEntityFeature.SET_SPEED | FanEntityFeature.OSCILLATE
        if self.coordinator.device_capabilities.get("Heating"):
            features |= FanEntityFeature.DIRECTION
        return features

    async def async_set_percentage(self, percentage: int):
        """Set fan speed by percentage."""
        speed = max(1, min(10, int(percentage / 10)))
        await self.coordinator.device.set_fan_speed(speed)

    async def async_oscillate(self, oscillating: bool):
        """Set oscillation."""
        await self.coordinator.device.set_oscillation(oscillating)
```

### Sensor Entity Implementation

```python
from custom_components.hass_dyson.sensor import DysonP25RSensor

# Air quality sensor example
class AirQualitySensor(DysonP25RSensor):
    """PM2.5 air quality sensor."""

    @property
    def native_value(self):
        """Return PM2.5 value."""
        return self.coordinator.data.get("pm25", 0)

    @property
    def native_unit_of_measurement(self):
        """Return unit of measurement."""
        return "μg/m³"

    @property
    def device_class(self):
        """Return device class."""
        return SensorDeviceClass.PM25
```

## Service Registration

### Dynamic Service Registration

```python
from custom_components.hass_dyson.services import (
    async_register_device_services,
    async_unregister_device_services
)

# Register services for a device
await async_register_device_services(
    hass=hass,
    serial_number="VS6-EU-HJA1234A",
    capabilities=["AdvanceOscillationDay1", "Scheduling", "ExtendedAQ"]
)

# Unregister services when device is removed
await async_unregister_device_services(
    hass=hass,
    serial_number="VS6-EU-HJA1234A"
)
```

### Service Handler Implementation

```python
from custom_components.hass_dyson.services import async_set_sleep_timer

# Call service handler directly
await async_set_sleep_timer(
    hass=hass,
    call_data={
        "serial_number": "VS6-EU-HJA1234A",
        "minutes": 60
    }
)

# Service schema example
SLEEP_TIMER_SCHEMA = vol.Schema({
    vol.Required("serial_number"): cv.string,
    vol.Required("minutes"): vol.All(vol.Coerce(int), vol.Range(min=0, max=540))
})
```

### Available Services by Capability

```python
# Basic services (all devices)
services_basic = [
    "set_fan_speed",
    "set_oscillation",
    "set_night_mode"
]

# Advanced oscillation services
if "AdvanceOscillationDay1" in capabilities:
    services_advanced = [
        "set_oscillation_angle",
        "set_continuous_monitoring"
    ]

# Scheduling services
if "Scheduling" in capabilities:
    services_scheduling = [
        "set_sleep_timer"
    ]

# Heating services
if "Heating" in capabilities:
    services_heating = [
        "set_target_temperature",
        "set_fan_direction"
    ]
```

## Data Coordination

### DysonDataUpdateCoordinator

The coordinator manages data updates and device communication.

```python
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

# Initialize coordinator
coordinator = DysonDataUpdateCoordinator(hass, config_entry)

# Access device capabilities
capabilities = coordinator.device_capabilities
print(f"Device supports: {capabilities}")

# Get device category and firmware info
category = coordinator.device_category  # e.g., "EC" for air purifiers
firmware = coordinator.firmware_version
print(f"Device: {category}, Firmware: {firmware}")

# Trigger data refresh
await coordinator.async_request_refresh()

# Access coordinated data
data = coordinator.data
temperature = data.get("temperature", 0)
pm25 = data.get("pm25", 0)
```

### Coordinator Properties and Methods

```python
# Device information properties
print(f"Serial: {coordinator.serial_number}")
print(f"Model: {coordinator.device_model}")
print(f"Category: {coordinator.device_category}")
print(f"Capabilities: {coordinator.device_capabilities}")

# Connection and status
print(f"Connected: {coordinator.device.is_connected}")
print(f"Connection type: {coordinator.connection_status}")
print(f"WiFi strength: {coordinator.wifi_rssi}")

# Firmware and filters
print(f"Firmware: {coordinator.firmware_version}")
print(f"Auto update: {coordinator.auto_update_enabled}")
print(f"New version: {coordinator.new_version_available}")
print(f"Filter life: {coordinator.filter_life_hepa}%")
```

## MQTT Communication

### Device Connection Management

```python
# Connect with error handling
try:
    success = await device.connect()
    if success:
        print("Connected via MQTT")
    else:
        print("Connection failed")
except Exception as e:
    print(f"Connection error: {e}")

# Send MQTT command
try:
    await device.send_command({
        "msg": "STATE-SET",
        "data": {
            "fspd": "0005",  # Fan speed 5
            "oson": "ON",    # Oscillation on
            "nmod": "ON"     # Night mode on
        }
    })
except Exception as e:
    print(f"Command failed: {e}")
```

### Message Format Examples

```python
# Fan control message
fan_command = {
    "msg": "STATE-SET",
    "time": "2025-01-01T12:00:00.000Z",
    "data": {
        "fspd": "0007",  # Fan speed (1-10, formatted as 4-digit string)
        "fpwr": "ON",    # Fan power (ON/OFF)
        "oson": "OFF",   # Oscillation (ON/OFF)
        "nmod": "ON"     # Night mode (ON/OFF)
    }
}

# Climate control message (heating models)
climate_command = {
    "msg": "STATE-SET",
    "time": "2025-01-01T12:00:00.000Z",
    "data": {
        "hmod": "HEAT",  # Heat mode (HEAT/OFF)
        "hmax": "2950",  # Target temperature (Kelvin * 10)
        "fdir": "ON"     # Fan direction (ON=front, OFF=back)
    }
}
```

## Error Handling

### Exception Types and Handling

```python
from custom_components.hass_dyson.exceptions import (
    DysonConnectionError,
    DysonCommandError,
    DysonAuthenticationError
)

# Connection error handling
try:
    await device.connect()
except DysonConnectionError as e:
    print(f"Connection failed: {e}")
    # Implement retry logic

except DysonAuthenticationError as e:
    print(f"Authentication failed: {e}")
    # Check credentials

# Command error handling
try:
    await device.set_fan_speed(5)
except DysonCommandError as e:
    print(f"Command failed: {e}")
    # Handle command failure

except Exception as e:
    print(f"Unexpected error: {e}")
    # General error handling
```

### Retry and Recovery Patterns

```python
import asyncio
from typing import Callable, Any

async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    backoff_factor: float = 1.0
) -> Any:
    """Retry function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            wait_time = backoff_factor * (2 ** attempt)
            await asyncio.sleep(wait_time)

# Usage example
result = await retry_with_backoff(
    lambda: device.connect(),
    max_retries=3,
    backoff_factor=2.0
)
```

### Logging Best Practices

```python
import logging

_LOGGER = logging.getLogger(__name__)

# Connection logging
try:
    await device.connect()
    _LOGGER.info("Device %s connected successfully", device.serial_number)
except Exception as e:
    _LOGGER.error("Failed to connect to device %s: %s", device.serial_number, e)

# Command logging
try:
    await device.set_fan_speed(speed)
    _LOGGER.debug("Set fan speed to %s for device %s", speed, device.serial_number)
except Exception as e:
    _LOGGER.warning("Failed to set fan speed for device %s: %s", device.serial_number, e)

# State logging
_LOGGER.debug(
    "Device %s state: temp=%s°C, pm25=%s μg/m³, connected=%s",
    device.serial_number,
    device.temperature,
    device.pm25,
    device.is_connected
)
```

## Integration Examples

### Complete Setup Example

```python
async def setup_complete_integration():
    """Complete example of setting up Dyson integration."""

    # 1. Create config entry
    config_entry = ConfigEntry(
        version=1,
        domain="hass_dyson",
        title="Dyson Device",
        data={
            "discovery_method": "cloud",
            "email": "user@example.com",
            "password": "password",
            "country": "US"
        }
    )

    # 2. Set up integration
    success = await async_setup_entry(hass, config_entry)
    if not success:
        return False

    # 3. Access coordinator
    coordinator = hass.data["hass_dyson"][config_entry.entry_id]

    # 4. Control device
    await coordinator.device.set_fan_speed(7)
    await coordinator.device.set_oscillation(True)

    # 5. Access sensor data
    data = coordinator.data
    print(f"PM2.5: {data.get('pm25')} μg/m³")
    print(f"Temperature: {data.get('temperature')}°C")

    return True
```

### Automation Integration Example

```python
# Home Assistant automation using Dyson services
automation_config = {
    "trigger": {
        "platform": "numeric_state",
        "entity_id": "sensor.dyson_pm25",
        "above": 50
    },
    "action": [
        {
            "service": "hass_dyson.set_fan_speed",
            "data": {
                "serial_number": "VS6-EU-HJA1234A",
                "speed": 8
            }
        },
        {
            "service": "hass_dyson.set_oscillation",
            "data": {
                "serial_number": "VS6-EU-HJA1234A",
                "oscillation": True
            }
        }
    ]
}
```

This API documentation provides comprehensive examples for developers working with the Dyson Home Assistant integration. For additional information, see the other documentation files in the `docs/` directory.
