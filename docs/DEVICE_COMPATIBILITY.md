# HASS-Dyson Device Compatibility

## Environment Cleaner (EC) Devices

### Description

Environment Cleaner devices include air purifiers, fans with filters, and heating models. These devices provide air circulation and filtration capabilities with various sensor and control options.

### Always Available Entities

All Environment Cleaner devices include these entities regardless of specific capabilities:

1. Fan Platform: Speed control (1-10), on/off, night mode, auto mode
2. Binary Sensors: Online/offline status, night mode status, auto mode status
3. WiFi Connectivity: WiFi signal strength sensor, Connection status sensor

### Capability-Dependent Entities

The following capabilities can add additional entities to Environment Cleaner devices:

| Capability | Required For | Entities Added |
|------------|--------------|----------------|
| **ExtendedAQ** | Air quality monitoring | • PM2.5 sensor<br>• PM10 sensor<br>• HEPA filter life sensor<br>• HEPA filter type sensor |
| **Scheduling** | Sleep timer functionality | • Number platform (sleep timer 15-540 minutes) |
| **AdvanceOscillationDay1** | Advanced oscillation control | • Number platform (oscillation angle range)<br>• Select platform (oscillation patterns) |
| **Heating** (name subject to change) | Heat mode devices | • Temperature sensor<br>• Climate platform<br>• Heating switch |
| **Humidifier** (name subject to change) | Humidity control devices | • Humidity sensor<br>• Humidifier platform<br>• Water tank level sensor |
| **Formaldehyde** (name subject to change) | Chemical air quality monitoring | • Formaldehyde sensor (HCHO)<br>• Carbon filter life sensor<br>• Carbon filter type sensor |
| **NO2VOC** (name subject to change) | Gas and VOC monitoring | • NO2 sensor (nitrogen dioxide)<br>• VOC sensor (volatile organic compounds)<br>• Gas filter status sensor |

### Example Device Configurations

1. Basic Fan (TP00 series): Fan + basic switches only
2. Air Purifier (TP04/TP07): Fan + ExtendedAQ sensors
3. Hot+Cool (HP04/HP07): Fan + ExtendedAQ + Heating

## Robot and Vacuum Devices

### Description

Robot and Vacuum devices include self-piloting cleaning devices and robot vacuums that provide automated cleaning functionality.
Robot and Vacuum devices are currently only partially supported.  If you have one of these devices and would like us to support it, please help us out!  Issue [#41](https://github.com/cmgrayb/hass-dyson/issues/41)

### Always Available Entities

All Robot and Vacuum devices include these entities:

1. Vacuum Platform: Start/stop, pause, dock, status
2. Binary Sensors: Online/offline status, charging status, docked status

### Capability-Dependent Entities

The following capabilities can add additional entities to Robot and Vacuum devices:

| Capability | Required For | Entities Added |
|------------|--------------|----------------|
| Robot and Vacuum Capabilities not yet known| | |

### Planned Future Support

The following features are planned for future releases:

1. Battery sensor: Battery level monitoring
2. Robot-specific controls: Cleaning patterns, etc.

## Vacuum Cleaner Devices

### Description

Traditional suction cleaning devices that provide manual cleaning functionality.
This device type appears in the Dyson API but no released product is known to be compatible.
If you have a device of this type that can be controlled through the app, let us know!  We'd be happy to add support for it if possible.  [Issues Page](https://github.com/cmgrayb/hass-dyson/issues)

### Currently Supported Entities

1. Status monitoring: Online/offline status

### Planned Future Support

The following features are planned for future releases:

1. TBD

## Floor Cleaner (FLRC) Devices

### Description

Mopping and floor cleaning devices that provide wet cleaning functionality for hard surfaces.
This device type appears in the Dyson API but no released product is known to be compatible.
If you have a device of this type that can be controlled through the app, let us know!  We'd be happy to add support for it if possible.  [Issues Page](https://github.com/cmgrayb/hass-dyson/issues)

### Currently Supported Entities

1. Basic cleaner controls: Start/stop functionality
2. Status monitoring: Online/offline status

### Planned Future Support

The following features are planned for future releases:

1. TBD

## Device Capabilities Reference

## ExtendedAQ Capability

### Description

Extended Air Quality capability provides continuous air quality monitoring with particle sensors.

### Purpose

Monitor indoor air quality through particulate matter detection and filter status tracking.

### Entities Provided

1. PM2.5 Sensor: Fine particulate matter measurement (μg/m³)
2. PM10 Sensor: Coarse particulate matter measurement (μg/m³)
3. HEPA Filter Life: Remaining filter life percentage (%)
4. HEPA Filter Type: Installed filter model/type information

## Heating Capability

### Description

Heating capability provides temperature control and climate functionality for devices with heating elements.
This capability is currently experimental.  If you can have one of these devices and can help us with the information we need to complete the capability, let us know!  Issue [#46](https://github.com/cmgrayb/hass-dyson/issues/46)

### Purpose

Enable temperature control and climate management through integrated heating systems.

### Device Architecture

Heating devices are **Environment Cleaners** (`ec`) with the `Heating` capability. They are not a separate device category.

### Entities Provided

1. **Fan Entity**: Main device control (speed, oscillation, preset modes)
2. **Climate Entity**: Dedicated heating/temperature control interface
   - HVAC modes: Off, Fan Only, Heat, Auto
   - Target temperature setting (1-37°C)
   - Current temperature display
3. **Temperature Sensor**: Current ambient temperature measurement (°C)

### Important Notes

- **No separate heating switch**: Heating is controlled through the climate entity's HVAC modes
- **No separate heating mode select**: Heating modes are part of the climate entity interface
- **Clear separation**: Fan entity controls air circulation, climate entity controls temperature

## WiFi Connectivity Capability

### Description

WiFi Connectivity capability provides network monitoring for devices that connect via WiFi networks.

### Purpose

Monitor network connection status and signal strength for troubleshooting and performance optimization.

### Device Category Requirements

Available for devices in the following categories:

1. Environment Cleaner (ec) devices
2. Robot devices

### Entities Provided

1. WiFi Signal Strength: Signal strength measurement in dBm
2. Connection Status: Current connection state (Local/Cloud/Disconnected)

## Future Capabilities Under Investigation

## Formaldehyde Capability

### Description

Formaldehyde capability would provide chemical air quality monitoring for volatile organic compounds.
This capability is currently experimental.  If you can have one of these devices and can help us with the information we need to complete the capability, let us know! Issue [#40](https://github.com/cmgrayb/hass-dyson/issues/40)

### Planned Entities

1. Carbon Filter Life: Remaining carbon filter life percentage (%)
2. Carbon Filter Type: Installed carbon filter model information
3. Formaldehyde Sensor: HCHO level detection and measurement

## Humidifier Capability

### Description

Humidifier capability provides humidity control functionality for devices with humidification systems.
This capability is currently experimental.  If you can have one of these devices and can help us with the information we need to complete the capability, let us know! Issue [#39](https://github.com/cmgrayb/hass-dyson/issues/39)

### Planned Entities

1. Humidity Sensor: Current relative humidity measurement (%)
2. Humidifier Controls: Humidity target and operational mode settings

## Device Configuration Examples

## Dyson Pure Cool TP04 Configuration

### Description

Configuration example for Dyson Pure Cool TP04 with ExtendedAQ.

### Available Platforms

1. fan: Speed control, auto mode, night mode
2. sensor: PM2.5, PM10, HEPA filter life/type, WiFi signal, connection status
3. binary_sensor: Online status, night mode status, auto mode status
4. action: Reset filter functionality
5. number: Sleep timer control
7. select: Oscillation control

## Dyson Pure Hot+Cool HP07 Configuration

### Description

Configuration example for Dyson Pure Hot+Cool HP07 with ExtendedAQ, and Heating.

### Available Platforms

1. fan: Speed control, preset modes (auto, manual, sleep)
2. climate: Heating control, temperature management
3. sensor: PM2.5, PM10, temperature, HEPA filters, WiFi, connection status
4. binary_sensor: Online status, night mode status, heating status
5. number: Sleep timer control, oscillation angle controls
6. select: Fan control mode, oscillation patterns, heating mode
7. switch: Night mode, heating control, continuous monitoring

## Dyson V15 Robot Vacuum Configuration

### Description

Configuration example for Dyson V15 Robot Vacuum with Robot and WiFi capabilities.

### Available Platforms

1. vacuum: Start, stop, dock, status control
2. sensor: WiFi signal strength, connection status
3. binary_sensor: Online status, charging status, docked status

### Planned Future Additions

1. battery sensor: Battery level monitoring
2. cleaning modes: Advanced cleaning pattern controls

## Basic Fan Model Configuration

### Description

Configuration example for basic fan models without special capabilities.

### Available Platforms

1. fan: Speed control functionality only
2. binary_sensor: Online status monitoring
3. number: Sleep timer control
4. select: Fan control mode

## Troubleshooting Entity Availability

## Missing Air Quality Sensors

### Description

Issue where PM2.5/PM10 sensors are not appearing in the device entity list.

### Purpose

Resolve missing air quality monitoring entities for devices that should support them.

### Troubleshooting Steps

1. Verify device model supports air quality monitoring capabilities
2. Check device configuration includes ExtendedAQ capability setting
3. For manual setup, ensure ExtendedAQ is selected in device capabilities

## Missing WiFi Monitoring

### Description

Issue where WiFi signal strength or connection status sensors are missing from the device.

### Purpose

Resolve missing network monitoring entities for WiFi-connected devices.

### Troubleshooting Steps

1. Verify device category is set to "ec" (Environment Cleaner) or "robot"
2. For manual setup, select correct device category during configuration
3. Note: Non-WiFi devices (corded vacuums) do not support WiFi monitoring

## Missing Temperature Controls

### Description

Issue where temperature sensor or climate platform entities are not available.

### Purpose

Resolve missing temperature control entities for heating-capable devices.

### Troubleshooting Steps

1. Verify device model supports heating functionality (HP series devices)
2. Check device configuration includes Heating capability setting
3. For manual setup, ensure Heating is selected in device capabilities
4. For persistent issues, report via Issue [#46](https://github.com/cmgrayb/hass-dyson/issues/46)

## Unexpected Sensors Appearing

### Description

Issue where sensors appear for features that the device does not actually support.

### Purpose

Resolve incorrect sensor entities appearing due to misconfiguration.

### Troubleshooting Steps

1. Review device capabilities in integration setup configuration
2. Remove unsupported capabilities from manual device configuration
3. Reconfigure integration with correct device category and capabilities

## Configuration Best Practices

## Cloud Discovery Configuration

### Description

Best practices for devices discovered automatically through Dyson cloud account integration.

### Configuration Guidelines

1. Automatic Detection: Capabilities and categories are automatically detected from Dyson API
2. Verification Process: Check entity list matches expected device features after discovery
3. Troubleshooting Approach: Wait for full device synchronization before reporting issues

## Manual Setup Configuration

### Description

Best practices for manually configured devices without cloud account integration.

### Configuration Guidelines

1. Research Phase: Verify device model capabilities before starting configuration
2. Conservative Approach: Start with basic capabilities, add additional features as needed
3. Documentation Reference: Consult device manual or Dyson specifications for supported features

## Integration Health Monitoring

### Description

Best practices for monitoring and maintaining integration health over time.

1. Connection Monitoring: Check connection status sensor for connectivity issues
2. Filter Maintenance: Watch filter life sensors for replacement scheduling
3. Performance Optimization: Use air quality sensors for automation triggers
