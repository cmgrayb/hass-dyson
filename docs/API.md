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

# Air quality and monitoring using public interface
current_state = device.state
pm25_level = device.get_state_value(current_state, "pm25", "0")
temperature = device.get_state_value(current_state, "tact", "0")

# Environmental data access
env_data = device.get_environmental_data()
pm25_level = env_data.get("pm25", 0)
pm10_level = env_data.get("pm10", 0)
humidity = env_data.get("hact", 0)
temperature = env_data.get("tact", 0)
```

### Device State Properties

```python
# Access device state information using public interface
state_data = device.state
env_data = device.get_environmental_data()

print(f"Fan speed: {device.get_state_value(state_data, 'fnsp', '0')}")
print(f"Temperature: {env_data.get('tact', 0)}°C")
print(f"Humidity: {env_data.get('hact', 0)}%")
print(f"PM2.5: {env_data.get('pm25', 0)} μg/m³")
print(f"PM10: {env_data.get('pm10', 0)} μg/m³")
print(f"VOC: {env_data.get('va10', 0)}")
print(f"NO2: {env_data.get('noxl', 0)}")
print(f"Connection status: {device.connection_status}")

# Alternative direct property access (if available)
print(f"Fan power: {device.get_state_value(state_data, 'fpwr', 'OFF')}")
print(f"Oscillation: {device.get_state_value(state_data, 'oson', 'OFF')}")
print(f"Night mode: {device.get_state_value(state_data, 'nmod', 'OFF')}")
print(f"Auto mode: {device.get_state_value(state_data, 'auto', 'OFF')}")
```

### Public Interface Methods

The `DysonDevice` class provides public interface methods for safe access to device data:

```python
# get_state_value() - Safe access to device state values
def get_state_value(data: dict[str, Any], key: str, default: str = "OFF") -> str:
    """
    Get current value from device data with proper encapsulation.

    Args:
        data: Device state data dictionary (from device.state)
        key: The state key to retrieve (e.g., 'fnsp', 'fpwr', 'oson')
        default: Default value if key is not found (default: "OFF")

    Returns:
        String representation of the state value

    Note:
        Values are normalized at message processing time:
        - CURRENT-STATE messages: already strings
        - STATE-CHANGE messages: [previous, current] arrays converted to current string
        - ENVIRONMENTAL-CURRENT-SENSOR-DATA messages: already strings
        - Fault messages: already strings
    """

# Example usage of get_state_value()
state_data = device.state
fan_speed = device.get_state_value(state_data, "fnsp", "0")  # Fan speed
fan_power = device.get_state_value(state_data, "fpwr", "OFF")  # Fan power
oscillation = device.get_state_value(state_data, "oson", "OFF")  # Oscillation
night_mode = device.get_state_value(state_data, "nmod", "OFF")  # Night mode
auto_mode = device.get_state_value(state_data, "auto", "OFF")  # Auto mode

# Heating-specific state values (for compatible models)
heating_mode = device.get_state_value(state_data, "hmod", "OFF")  # Heating mode
target_temp = device.get_state_value(state_data, "hmax", "0")  # Target temperature
```

```python
# get_environmental_data() - Safe access to environmental sensor data
def get_environmental_data() -> dict[str, Any]:
    """
    Get environmental data from the device with proper encapsulation.

    Returns:
        Dictionary containing environmental data with keys:
        - pm25: PM2.5 particle concentration (μg/m³)
        - pm10: PM10 particle concentration (μg/m³)
        - va10: Volatile organic compounds (VOC index)
        - noxl: Nitrogen dioxide levels (ppb)
        - hchr: Formaldehyde concentration (μg/m³)
        - hact: Humidity percentage (%)
        - tact: Temperature readings (°C * 10)

    Note:
        Returns a copy of the internal environmental data to prevent
        external modifications. Use this method instead of accessing
        internal attributes directly.
    """

# Example usage of get_environmental_data()
env_data = device.get_environmental_data()

# Air quality measurements
pm25 = env_data.get("pm25", 0)  # PM2.5 concentration
pm10 = env_data.get("pm10", 0)  # PM10 concentration
voc = env_data.get("va10", 0)   # Volatile organic compounds
no2 = env_data.get("noxl", 0)   # Nitrogen dioxide
formaldehyde = env_data.get("hchr", 0)  # Formaldehyde

# Environmental conditions
humidity = env_data.get("hact", 0)  # Humidity percentage
temperature = env_data.get("tact", 0) / 10  # Temperature (convert from °C * 10)

print(f"Air Quality - PM2.5: {pm25}μg/m³, PM10: {pm10}μg/m³, VOC: {voc}")
print(f"Environment - Temp: {temperature}°C, Humidity: {humidity}%")
```

### Data Access Best Practices

```python
# ✅ RECOMMENDED: Use public interface methods
state_data = device.state
env_data = device.get_environmental_data()

fan_speed = device.get_state_value(state_data, "fnsp", "0")
pm25_level = env_data.get("pm25", 0)

# ❌ AVOID: Direct access to private attributes
# fan_speed = device._current_state.get("fnsp", "0")  # Don't do this
# pm25_level = device._environmental_data.get("pm25", 0)  # Don't do this

# ✅ RECOMMENDED: Safe data retrieval with defaults
temperature = env_data.get("tact", 0)  # Returns 0 if not available
humidity = env_data.get("hact", 0)     # Returns 0 if not available

# ✅ RECOMMENDED: Type conversion with error handling
try:
    temp_celsius = int(env_data.get("tact", 0)) / 10
    humidity_percent = int(env_data.get("hact", 0))
except (ValueError, TypeError):
    temp_celsius = 0.0
    humidity_percent = 0
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
        """Return the current value using public interface."""
        if not self.coordinator.device:
            return None
        state_data = self.coordinator.device.state
        return self.coordinator.device.get_state_value(state_data, "custom_key", "0")

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
        """Return PM2.5 value using public interface."""
        if not self.coordinator.device:
            return 0
        env_data = self.coordinator.device.get_environmental_data()
        return env_data.get("pm25", 0)

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
from homeassistant.helpers.service import ServiceCall

service_call = ServiceCall(
    domain="hass_dyson",
    service="set_sleep_timer",
    data={
        "device_id": "VS6-EU-HJA1234A",
        "minutes": 60
    }
)

await async_set_sleep_timer(hass, service_call)

# Service schema example
SERVICE_SET_SLEEP_TIMER_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,  # Home Assistant device registry ID
    vol.Required("minutes"): vol.All(
        vol.Coerce(int), vol.Range(min=15, max=540)  # 15 minutes to 9 hours
    )
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

## API Design and Encapsulation

### Encapsulation Principles

The Dyson integration follows strict encapsulation principles to ensure maintainability and prevent accidental misuse:

```python
# ✅ CORRECT: Use public interface methods
device = coordinator.device
if device:
    # Get state data safely
    state_data = device.state
    env_data = device.get_environmental_data()

    # Access values through public methods
    fan_speed = device.get_state_value(state_data, "fnsp", "0")
    pm25 = env_data.get("pm25", 0)

# ❌ INCORRECT: Direct access to private members
# fan_speed = device._current_state.get("fnsp", "0")  # Breaks encapsulation
# pm25 = device._environmental_data.get("pm25", 0)   # Breaks encapsulation
```

### Public vs Private Interface

**Public Interface (Safe to Use):**
- `device.state` - Current device state dictionary
- `device.get_state_value(data, key, default)` - Safe state value retrieval
- `device.get_environmental_data()` - Environmental sensor data
- `device.send_command(command, data)` - Device command execution
- `device.connect()` / `device.disconnect()` - Connection management
- `device.is_connected` - Connection status property

**Private Interface (Do Not Use):**
- `device._current_state` - Internal state storage
- `device._environmental_data` - Internal environmental data
- `device._mqtt_client` - Internal MQTT client
- `device._connected` - Internal connection flag
- `device._callbacks` - Internal callback management

### Migration from Legacy Code

If you have existing code using private members, migrate as follows:

```python
# OLD (deprecated):
fan_speed = device._current_state.get("fnsp", "0")
pm25 = device._environmental_data.get("pm25", 0)

# NEW (recommended):
state_data = device.state
env_data = device.get_environmental_data()
fan_speed = device.get_state_value(state_data, "fnsp", "0")
pm25 = env_data.get("pm25", 0)
```

### Type Safety and Error Handling

```python
from typing import Optional

def get_device_temperature(coordinator) -> Optional[float]:
    """Get device temperature with proper error handling."""
    if not coordinator.device:
        return None

    try:
        env_data = coordinator.device.get_environmental_data()
        temp_raw = env_data.get("tact", 0)
        return float(temp_raw) / 10  # Convert from °C * 10
    except (ValueError, TypeError, ZeroDivisionError):
        return None

def get_device_fan_speed(coordinator) -> Optional[int]:
    """Get device fan speed with proper error handling."""
    if not coordinator.device:
        return None

    try:
        state_data = coordinator.device.state
        speed_str = coordinator.device.get_state_value(state_data, "fnsp", "0")
        return int(speed_str)
    except (ValueError, TypeError):
        return None
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

    # 5. Access sensor data using public interface
    if coordinator.device:
        env_data = coordinator.device.get_environmental_data()
        state_data = coordinator.device.state
        print(f"PM2.5: {env_data.get('pm25', 0)} μg/m³")
        print(f"Temperature: {env_data.get('tact', 0) / 10}°C")
        print(f"Fan speed: {coordinator.device.get_state_value(state_data, 'fnsp', '0')}")

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
            "service": "hass_dyson.set_sleep_timer",
            "data": {
                "device_id": "dyson_vs6_eu_hja1234a",
                "minutes": 60
            }
        },
        {
            "service": "fan.set_percentage",
            "target": {
                "entity_id": "fan.dyson_purifier"
            },
            "data": {
                "percentage": 80
            }
        }
    ]
}
```

## API Changelog and Updates

### v0.19.0 - Enhanced Encapsulation and Public Interfaces

**New Public Interface Methods:**
- `DysonDevice.get_state_value(data, key, default)` - Safe state value retrieval
- `DysonDevice.get_environmental_data()` - Environmental sensor data access

**Improved Encapsulation:**
- All external access to device data now uses public interface methods
- Private member access (`_current_state`, `_environmental_data`) is deprecated
- Enhanced type safety and error handling throughout the API

**Migration Required:**
If you're upgrading from previous versions, update your code to use the new public interface:

```python
# OLD (v0.18.x and earlier):
pm25 = device._environmental_data.get("pm25", 0)
fan_speed = device._current_state.get("fnsp", "0")

# NEW (v0.19.0+):
env_data = device.get_environmental_data()
state_data = device.state
pm25 = env_data.get("pm25", 0)
fan_speed = device.get_state_value(state_data, "fnsp", "0")
```

**Service Updates:**
- All services now use `device_id` parameter (Home Assistant device registry ID)
- Enhanced error handling and validation for all service calls
- Improved service schemas with proper range validation

### Compatibility Notes

- **Backward Compatibility**: Existing integrations will continue to work but should migrate to the new public interface
- **Performance**: New public interface methods provide better performance through optimized data access
- **Type Safety**: Enhanced type hints and validation throughout the API
- **Documentation**: All examples updated to reflect current best practices

### Future API Evolution

The public interface methods are designed to be stable and will maintain backward compatibility. Future enhancements will focus on:
- Additional environmental sensor support
- Extended device capability detection
- Enhanced error reporting and diagnostics
- Performance optimizations

---

This API documentation provides comprehensive examples for developers working with the Dyson Home Assistant integration. For additional information, see the other documentation files in the `docs/` directory.

**Related Documentation:**
- [Setup Guide](SETUP.md) - Integration installation and configuration
- [Device Compatibility](DEVICE_COMPATIBILITY.md) - Supported device models
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
- [Developer's Guide](DEVELOPERS_GUIDE.md) - Development environment setup
