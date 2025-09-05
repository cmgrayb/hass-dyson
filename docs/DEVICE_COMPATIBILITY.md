# Device Compatibility Matrix

This document provides a comprehensive overview of which entities are available for different Dyson device types and configurations.

## Entity Availability by Device Type

### 🌪️ Environment Cleaner (EC) Devices
*Air purifiers, fans with filters, heating models*

#### Always Available
- **Fan Platform**: Speed control (1-10), on/off, night mode, auto mode
- **Binary Sensors**: 
  - Online/offline status
  - Night mode status  
  - Auto mode status
- **Button Platform**: Reset filter button
- **Number Platform**: Sleep timer (15-540 minutes)
- **Select Platform**: Fan speed selection
- **Switch Platform**: Oscillation control

#### Capability-Dependent Entities

| Capability | Required For | Entities Added |
|------------|--------------|----------------|
| **ExtendedAQ** | Air quality monitoring | • PM2.5 sensor<br>• PM10 sensor<br>• HEPA filter life sensor<br>• HEPA filter type sensor |
| **Heating** | Heat mode devices | • Temperature sensor<br>• Climate platform<br>• Heating switch |
| **WiFi Connectivity** | ec/robot categories | • WiFi signal strength sensor<br>• Connection status sensor |

#### Example Configurations
- **Basic Fan (TP00 series)**: Fan + basic switches only
- **Air Purifier (TP04/TP07)**: Fan + ExtendedAQ sensors + WiFi monitoring  
- **Hot+Cool (HP04/HP07)**: Fan + ExtendedAQ + Heating + WiFi monitoring

### 🤖 Robot/Vacuum Devices
*Self-piloting cleaning devices, robot vacuums*

#### Always Available
- **Vacuum Platform**: Start/stop, pause, dock, status
- **Binary Sensors**: 
  - Online/offline status
  - Charging status
  - Docked status

#### Capability-Dependent Entities

| Capability | Required For | Entities Added |
|------------|--------------|----------------|
| **WiFi Connectivity** | robot category | • WiFi signal strength sensor<br>• Connection status sensor |
| **ExtendedAQ** | Air quality models | • PM2.5 sensor<br>• PM10 sensor<br>• HEPA filter sensors |

#### Future Support (Planned)
- **Battery sensor**: Battery level monitoring
- **Robot-specific controls**: Cleaning patterns, suction modes

### 🧹 Vacuum Cleaner Devices
*Traditional suction cleaning devices*

#### Currently Supported
- **Basic vacuum controls**: Start/stop functionality
- **Status monitoring**: Online/offline status

#### Future Support (Planned)
- **Suction control**: Variable suction power
- **Brush monitoring**: Brush status and maintenance

### 🧽 Floor Cleaner (FLRC) Devices  
*Mopping and floor cleaning devices*

#### Currently Supported
- **Basic cleaner controls**: Start/stop functionality
- **Status monitoring**: Online/offline status

#### Future Support (Planned)
- **Water tank monitoring**: Tank level and status
- **Cleaning modes**: Different floor cleaning patterns

## Capability Reference

### ExtendedAQ (Extended Air Quality)
**Provides**: Continuous air quality monitoring with particle sensors
- **PM2.5 Sensor**: Fine particulate matter (μg/m³)
- **PM10 Sensor**: Coarse particulate matter (μg/m³)  
- **HEPA Filter Life**: Remaining filter life (%)
- **HEPA Filter Type**: Installed filter model/type

### Heating
**Provides**: Temperature control and climate functionality
- **Temperature Sensor**: Current ambient temperature (°C)
- **Climate Platform**: Full HVAC interface with heat mode
- **Heating Switch**: Toggle heat mode on/off

### WiFi Connectivity (Device Category Based)
**Available for**: ec (Environment Cleaner) and robot device categories
- **WiFi Signal Strength**: Signal strength in dBm
- **Connection Status**: Current connection state (Local/Cloud/Disconnected)

### Future Capabilities

#### Formaldehyde (Under Investigation)
**Would provide**: Chemical air quality monitoring
- **Carbon Filter Life**: Remaining carbon filter life (%)
- **Carbon Filter Type**: Installed carbon filter model
- **Formaldehyde Sensor**: HCHO level detection

#### Humidifier (Under Investigation)  
**Would provide**: Humidity control functionality
- **Humidity Sensor**: Current relative humidity (%)
- **Humidifier Controls**: Humidity target and mode

## Device Configuration Examples

### Dyson Pure Cool TP04 (ExtendedAQ + WiFi)
```yaml
Platforms:
  - fan (speed, auto, night mode)
  - sensor (PM2.5, PM10, HEPA filter life/type, WiFi signal, connection status)
  - binary_sensor (online, night mode, auto mode)
  - button (reset filter)
  - number (sleep timer)
  - select (fan speed)
  - switch (oscillation)
```

### Dyson Pure Hot+Cool HP07 (ExtendedAQ + Heating + WiFi)
```yaml
Platforms:
  - fan (speed, auto, night mode)
  - climate (heating, temperature control)
  - sensor (PM2.5, PM10, temperature, HEPA filters, WiFi, connection)
  - binary_sensor (online, night mode, auto mode, heating)
  - button (reset filter)
  - number (sleep timer)
  - select (fan speed)
  - switch (oscillation, heating)
```

### Dyson V15 Robot Vacuum (Robot + WiFi)
```yaml
Platforms:
  - vacuum (start, stop, dock, status)
  - sensor (WiFi signal, connection status)
  - binary_sensor (online, charging, docked)
  # Future: battery sensor, cleaning modes
```

### Basic Fan Model (No Special Capabilities)
```yaml
Platforms:
  - fan (speed control only)
  - binary_sensor (online status)
  - button (basic controls)
  - number (sleep timer)
  - select (fan speed)
  - switch (oscillation)
  # No air quality sensors, no WiFi monitoring
```

## Troubleshooting Entity Availability

### Missing Air Quality Sensors
**Problem**: PM2.5/PM10 sensors not appearing
**Cause**: Device lacks ExtendedAQ capability
**Solution**: 
1. Verify device model supports air quality monitoring
2. Check device configuration includes ExtendedAQ capability
3. For manual setup, ensure ExtendedAQ is selected in capabilities

### Missing WiFi Monitoring
**Problem**: WiFi signal strength or connection status sensors missing
**Cause**: Device category not set to "ec" or "robot"
**Solution**:
1. Verify device category in integration configuration
2. For manual setup, select correct device category (Environment Cleaner or Robot)
3. Non-WiFi devices (like corded vacuums) don't support WiFi monitoring

### Missing Temperature Controls
**Problem**: No temperature sensor or climate platform
**Cause**: Device lacks Heating capability
**Solution**:
1. Verify device model supports heating (HP series, etc.)
2. Check device configuration includes Heating capability
3. For manual setup, ensure Heating is selected in capabilities

### Unexpected Sensors Appearing
**Problem**: Sensors showing for unsupported features
**Cause**: Incorrect capability or category configuration
**Solution**:
1. Review device capabilities in integration setup
2. Remove unsupported capabilities from manual configuration
3. Reconfigure integration with correct device category

## Configuration Best Practices

### For Cloud Discovery
- **Automatic**: Capabilities and categories detected from Dyson API
- **Verification**: Check entity list matches expected device features
- **Troubleshooting**: Wait for full device sync before reporting issues

### For Manual Setup
- **Research**: Verify device model capabilities before configuration
- **Conservative**: Start with basic capabilities, add features as needed
- **Documentation**: Refer to device manual or Dyson specs for supported features

### For Integration Health
- **Monitor**: Check connection status sensor for connectivity issues
- **Maintenance**: Watch filter life sensors for replacement scheduling
- **Performance**: Use air quality sensors for automation triggers
