# API Reference - Dyson Integration

Complete reference for developers and advanced users working with the Dyson integration.

## 🏗️ Architecture Overview

### **Integration Structure**
```
ConfigFlow → Coordinator → Device → MQTT Client → Physical Device
     ↓           ↓          ↓           ↓              ↓
Setup Flow → Data Updates → Commands → Network → Device Response
```

### **Component Hierarchy**
```python
DysonAltIntegration
├── DysonCoordinator           # Data coordination
├── DysonDevice                # MQTT device wrapper  
├── Platform Entities:
│   ├── DysonFan              # Primary fan control
│   ├── DysonSensor           # Air quality sensors
│   ├── DysonBinarySensor     # Status sensors
│   ├── DysonButton           # Action buttons
│   ├── DysonNumberEntity     # Numeric controls
│   ├── DysonSelectEntity     # Mode selectors
│   ├── DysonSwitchEntity     # Feature toggles
│   └── DysonClimateEntity    # HVAC control
```

## 📡 MQTT Communication

### **Message Format**
```json
{
  "msg": "CURRENT-STATE",
  "time": "2025-01-08T10:30:45.000Z",
  "data": {
    "fmod": "FAN",     // Fan mode
    "fnsp": "0004",    // Fan speed (0001-0010) or "AUTO"
    "oson": "ON",      // Oscillation
    "osau": "0167",    // Oscillation upper angle  
    "osal": "0090",    // Oscillation lower angle
    "sltm": "0015",    // Sleep timer
    "rhtm": "ON",      // Continuous Monitoring
    "auto": "ON",      // Auto mode
    "hflr": "0072",    // HEPA filter life (percentage)
    "cflr": "0085",    // Carbon filter life (percentage) 
    "pm25": "0009",    // PM2.5 (µg/m³)
    "pm10": "0012",    // PM10 (µg/m³)
    "rssi": "-029"     // WiFi signal (dBm)
  }
}
```

### **MQTT Topics**
```
# Status messages (from device)
{mqtt_prefix}/{serial}/status/current
{mqtt_prefix}/{serial}/status/faults

# Commands (to device)  
{mqtt_prefix}/{serial}/command
```

### **Command Examples**
```python
# Set fan speed to 5
await coordinator.async_send_command({
    "msg": "STATE-SET",
    "data": {"fnsp": "0005"}
})

# Enable oscillation
await coordinator.async_send_command({
    "msg": "STATE-SET", 
    "data": {"oson": "ON"}
})

# Set sleep timer to 30 minutes
await coordinator.async_send_command({
    "msg": "STATE-SET",
    "data": {"sltm": "0030"}
})
```

## 🔧 Core Classes

### **DysonCoordinator**
```python
class DysonCoordinator(DataUpdateCoordinator):
    """Manages data updates and command sending for Dyson devices."""
    
    def __init__(self, hass, device_wrapper):
        """Initialize coordinator with device wrapper."""
        
    async def _async_update_data(self):
        """Fetch latest data from device."""
        
    async def async_send_command(self, command: dict):
        """Send command to device via MQTT."""
        
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for entity registry."""
```

### **DysonDevice** 
```python
class DysonDevice:
    """Wrapper for paho-mqtt device communication."""
    
    def __init__(self, serial: str, credential: str, device_type: str):
        """Initialize with device credentials."""
        
    async def async_connect(self) -> bool:
        """Establish MQTT connection to device."""
        
    async def async_send_command(self, command: dict):
        """Send command to device."""
        
    @property
    def current_state(self) -> dict:
        """Get latest device state data."""
        
    @property
    def is_connected(self) -> bool:
        """Check if device is currently connected."""
```

### **Base Entity Classes**
```python
class DysonEntity(CoordinatorEntity):
    """Base class for all Dyson entities."""
    
    def __init__(self, coordinator, device_name: str):
        """Initialize with coordinator reference."""
        
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        
    def _handle_coordinator_update(self):
        """Handle data updates from coordinator."""

class DysonFanEntity(DysonEntity, FanEntity):
    """Fan entity with speed control and modes."""
    
class DysonSensorEntity(DysonEntity, SensorEntity):
    """Sensor entity for air quality data."""
    
# ... other entity base classes
```

## 🎛️ Platform Entities

### **Fan Platform (`fan.py`)**
```python
class DysonFan(DysonFanEntity):
    """Primary fan control entity."""
    
    @property
    def is_on(self) -> bool:
        """Return if fan is on."""
        return self.coordinator.data.get("fmod") != "OFF"
        
    @property  
    def percentage(self) -> int:
        """Return fan speed percentage (0-100)."""
        
    async def async_turn_on(self, percentage=None, **kwargs):
        """Turn on fan with optional speed."""
        
    async def async_turn_off(self, **kwargs):
        """Turn off fan."""
```

### **Sensor Platform (`sensor.py`)**
```python
class DysonPM25Sensor(DysonSensorEntity):
    """PM2.5 air quality sensor."""
    
    @property
    def native_value(self) -> int:
        """Return PM2.5 value in µg/m³."""
        pm25_raw = self.coordinator.data.get("pm25", "0000")
        return int(pm25_raw) if pm25_raw.isdigit() else None
        
    @property
    def device_class(self) -> SensorDeviceClass:
        """Return PM2.5 device class."""
        return SensorDeviceClass.PM25
```

### **Number Platform (`number.py`)**
```python
class DysonFanSpeedNumber(DysonNumberEntity):
    """Fan speed numeric control (1-10)."""
    
    @property
    def native_min_value(self) -> float:
        return 1.0
        
    @property 
    def native_max_value(self) -> float:
        return 10.0
        
    async def async_set_native_value(self, value: float):
        """Set fan speed."""
        speed_str = f"{int(value):04d}"
        await self.coordinator.async_send_command({
            "msg": "STATE-SET",
            "data": {"fnsp": speed_str}
        })
```

### **Select Platform (`select.py`)**
```python
class DysonAirQualityModeSelect(DysonSelectEntity):
    """Air quality mode selection."""
    
    @property
    def options(self) -> list[str]:
        """Return available mode options."""
        return ["Auto", "Manual", "Sleep"]
        
    @property
    def current_option(self) -> str:
        """Return current mode."""
        
    async def async_select_option(self, option: str):
        """Set air quality mode."""
```

## 🔌 Configuration Flow

### **ConfigFlow Class**
```python
class DysonAltConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Dyson integration."""
    
    async def async_step_user(self, user_input=None):
        """Handle initial setup method selection."""
        
    async def async_step_cloud_discovery(self, user_input=None):
        """Handle cloud-based device discovery."""
        
    async def async_step_manual_setup(self, user_input=None): 
        """Handle manual device setup with sticker info."""
        
    async def async_validate_device_connection(self, device_config):
        """Test device connection before saving."""
```

### **Setup Schemas**
```python
CLOUD_DISCOVERY_SCHEMA = vol.Schema({
    vol.Required("email"): str,
    vol.Required("password"): str,
})

MANUAL_SETUP_SCHEMA = vol.Schema({
    vol.Required("serial_number"): str,
    vol.Required("credential"): str,
    vol.Required("device_type"): vol.In(["438", "475", "527", "455", "469"]),
    vol.Optional("hostname"): str,
})
```

## 📊 Data Structures

### **Device State Data**
```python
DEVICE_STATE = {
    # Fan control
    "fmod": "FAN",        # Fan mode (OFF/FAN/AUTO)  
    "fnsp": "0005",       # Fan speed (0001-0010)
    "fnst": "FAN",        # Fan state
    
    # Oscillation
    "oson": "ON",         # Oscillation on/off
    "osau": "BRZE",       # Oscillation angle (BRZE/0045-0350)
    "ancp": "0180",       # Angle position
    
    # Auto mode & scheduling
    "rhtm": "ON",         # Auto mode (rhythm)
    "sltm": "STET",       # Sleep timer (STET/0001-0540)
    "nmod": "OFF",        # Night mode
    
    # Air quality
    "pm25": "0009",       # PM2.5 µg/m³
    "pm10": "0012",       # PM10 µg/m³  
    "vact": "0004",       # VOC
    "pact": "0002",       # Particulate count
    
    # Device status
    "rssi": "-029",       # WiFi signal dBm
    "hflr": "0072",       # HEPA filter life (percentage)
    "cflr": "0085",       # Carbon filter life (percentage)
    "ercd": "NONE",       # Error code
    "wacd": "NONE",       # Warning code
    
    # Heating (HP models)
    "hmod": "HEAT",       # Heating mode
    "hmax": "2980",       # Max heating (Kelvin)
    "tilt": "OK",         # Tilt status
}
```

### **Device Configuration**
```python
DEVICE_CONFIG = {
    "serial_number": "MOCK-SERIAL-TEST123",
    "discovery_method": "sticker",  # or "cloud"
    "hostname": "192.168.1.161",    # optional
    "credential": "AAAABBBB",       # Device password
    "device_type": "438",           # product type
    "mqtt_prefix": "438M",          # auto-determined
    "capabilities": [               # auto-detected
        "Auto", "Oscillation", "Scheduling", "Fault"
    ]
}
```

## 🎨 Entity Customization

### **Custom Entity Icons**
```python
ENTITY_ICONS = {
    "pm25": "mdi:air-filter",
    "pm10": "mdi:air-filter", 
    "filter_life": "mdi:air-filter-outline",
    "rssi": "mdi:wifi-strength-2",
    "connectivity": "mdi:wifi",
    "fault": "mdi:alert-circle",
    "oscillation": "mdi:rotate-360",
    "heating": "mdi:radiator",
    "night_mode": "mdi:weather-night",
}
```

### **State Classes**
```python
# For cumulative sensors
STATE_CLASS_TOTAL_INCREASING = "total_increasing"

# For measurement sensors  
STATE_CLASS_MEASUREMENT = "measurement"

# For state sensors
STATE_CLASS_NONE = None
```

### **Device Classes** 
```python
# Air quality sensors
SensorDeviceClass.PM25
SensorDeviceClass.PM10
SensorDeviceClass.SIGNAL_STRENGTH

# Binary sensors
BinarySensorDeviceClass.CONNECTIVITY
BinarySensorDeviceClass.PROBLEM

# Climate entities
ClimateDeviceClass.THERMOSTAT
```

## 🔍 Debugging & Logging

### **Enable Debug Logging**
```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.hass-dyson: debug
    libdyson_rest: debug
```

### **Log Categories**
```python
# Component logging
_LOGGER = logging.getLogger(__name__)

# Usage in code
_LOGGER.debug("Device state updated: %s", state_data)
_LOGGER.info("Device connected: %s", self.device.serial)
_LOGGER.warning("Connection lost, retrying...")
_LOGGER.error("Failed to send command: %s", error)
```

### **Common Debug Patterns**
```python
# Log MQTT message details
_LOGGER.debug("Received MQTT message: topic=%s, payload=%s", 
              topic, payload)

# Log state transitions
_LOGGER.debug("Fan state changed: %s -> %s", 
              old_state, new_state)

# Log command sending
_LOGGER.debug("Sending command to %s: %s", 
              self.device.serial, command)
```

## 🧪 Testing Patterns

### **Mocking Device Communication**
```python
from unittest.mock import Mock, patch

@patch('custom_components.hass_dyson.device.DysonDevice')
async def test_fan_speed_control(mock_device):
    """Test fan speed adjustment."""
    mock_device.current_state = {"fnsp": "0005"}
    
    # Test entity creation
    coordinator = DysonCoordinator(hass, mock_device)
    fan = DysonFan(coordinator, "Test Fan")
    
    # Test speed setting
    await fan.async_set_percentage(80)
    
    # Verify command sent
    mock_device.async_send_command.assert_called_with({
        "msg": "STATE-SET",
        "data": {"fnsp": "0008"}
    })
```

### **Integration Testing**
```python
async def test_device_discovery():
    """Test device discovery process."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "serial_number": "MOCK-SERIAL-TEST123",
            "credential": "AAAABBBB",
            "device_type": "438"
        }
    )
    
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Verify entities created
    state = hass.states.get("fan.dyson_test_fan")
    assert state is not None
    assert state.state == "off"
```

## 📚 Extension Points

### **Adding New Sensors**
```python
class DysonCustomSensor(DysonSensorEntity):
    """Custom sensor implementation."""
    
    @property
    def name(self) -> str:
        return f"{self._device_name} Custom Sensor"
        
    @property
    def native_value(self):
        """Extract custom value from device state."""
        return self.coordinator.data.get("custom_field")
        
    @property
    def native_unit_of_measurement(self) -> str:
        return "custom_unit"
```

### **Custom Platform Registration**
```python
# In platform file (e.g., sensor.py)
SENSORS = [
    DysonPM25Sensor,
    DysonPM10Sensor,
    DysonRSSISensor,
    DysonCustomSensor,  # Add here
]

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensors from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    for sensor_class in SENSORS:
        if sensor_class.should_create(coordinator.device):
            entities.append(sensor_class(coordinator, entry.title))
            
    async_add_entities(entities)
```

---

**Note**: This API is subject to change as the integration evolves. Check the latest code for authoritative implementation details.
