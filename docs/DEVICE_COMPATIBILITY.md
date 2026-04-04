# HASS-Dyson Device Compatibility

## Integration Goal

Please note that the goal of this integration is to be as compatible and future-proof
as possible.  We expect that once a classification or type of device is supported,
essentially all devices of that classification or type are supported until found to be
lacking in some way.

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
| **ExtendedAQ** | Full air quality monitoring | • PM2.5 sensor<br>• PM10 sensor<br>• VOC sensor (volatile organic compounds)<br>• NOx sensor (nitrogen oxides)<br>• CO2 sensor (carbon dioxide)<br>• Formaldehyde sensor (HCHO)<br>• HEPA filter life sensor<br>• HEPA filter type sensor<br>• Carbon filter life sensor<br>• Carbon filter type sensor |
| **Scheduling** | Sleep timer functionality | • Number platform (sleep timer 15-540 minutes) |
| **AdvanceOscillationDay0** | Basic oscillation control | • Select platform (oscillation patterns) |
| **AdvanceOscillationDay1** | Advanced oscillation control | • Number platform (oscillation angle range)<br>• Select platform (oscillation patterns) |
| **Heating** (auto-detected) | Heat mode devices | • Temperature sensor<br>• Climate platform<br>• Heating switch |
| **Humidifier** (auto-detected) | Humidity control devices | • Humidity sensor<br>• Humidifier platform<br>• Water tank level sensor |

### Example Device Configurations

1. Basic Fan (AM00 series): Fan + AdvanceOscillationDay0
2. Air Purifier (TP00 series): Fan + AdvanceOscillationDay1 + ExtendedAQ
3. Hot+Cool (HP00 series): Fan + AdvanceOscillationDay1 + ExtendedAQ
4. Humidifier (PH00 series): Fan + AdvanceOscillationDay1 + ExtendedAQ
5. Big and Quiet (BP00 series): Fan + AdvanceOscillationDay1 + ExtendedAQ

## Robot and Vacuum Devices

### Description

Robot and Vacuum devices include self-piloting cleaning devices and robot vacuums that provide automated cleaning functionality.
Robot and Vacuum devices are currently only partially supported.  If you have one of these devices and would like us to support it, please help us out!  Issue [#41](https://github.com/cmgrayb/hass-dyson/issues/41)

### Always Available Entities

All Robot and Vacuum devices include these entities:

1. Vacuum Platform: Stop, pause, dock, status
2. Binary Sensors: Online/offline status, charging status, docked status
3. Battery sensor: Battery level monitoring

### Capability-Dependent Entities

The following capabilities can add additional entities to Robot and Vacuum devices:

| Capability | Required For | Entities Added |
|------------|--------------|----------------|
| Robot and Vacuum Capabilities not yet known| | |

### Planned Future Support

The following features are planned for future releases:

1. Robot-specific controls: Clean by area or all areas

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

Extended Air Quality capability provides comprehensive air quality monitoring covering particulate matter, gaseous pollutants, and filter status tracking. All sensors listed below are provided automatically when the device reports this capability — no separate capability selection is required.

### Purpose

Monitor indoor air quality through particulate matter, gaseous pollutants, chemical detection, and filter status tracking.

### Entities Provided

1. PM2.5 Sensor: Fine particulate matter measurement (μg/m³)
2. PM10 Sensor: Coarse particulate matter measurement (μg/m³)
3. VOC Sensor: Volatile organic compounds index
4. NOx Sensor: Nitrogen oxides index
5. CO2 Sensor: Carbon dioxide level (ppm) — where supported by device hardware
6. Formaldehyde Sensor: HCHO level detection (mg/m³) — where supported by device hardware
7. HEPA Filter Life: Remaining HEPA filter life percentage (%)
8. HEPA Filter Type: Installed HEPA filter model/type information
9. Carbon Filter Life: Remaining carbon filter life percentage (%)
10. Carbon Filter Type: Installed carbon filter model/type information

### Notes

- All entities under ExtendedAQ are detected and enabled automatically from the cloud API response or device MQTT data.
- Sensors for CO2 and Formaldehyde are only present if the physical device hardware supports those measurements; the integration does not require a separate capability flag for them.

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

## Humidifier Capability

### Description

Humidifier capability provides humidity control functionality for devices with humidification systems. This capability is auto-detected and fully supported.

### Entities Provided

1. Humidity Sensor: Current relative humidity measurement (%)
2. Humidifier Platform: Humidity target setting and operational mode controls
3. Water Tank Level Sensor: Remaining water level status

## Device Configuration Examples

## Dyson Pure Cool TP04 Configuration

### Description

Configuration example for Dyson Pure Cool TP04 with ExtendedAQ.

### Available Platforms

1. fan: Speed control, auto mode, night mode
2. sensor: PM2.5, PM10, VOC, NOx, HEPA filter life/type, carbon filter life/type, WiFi signal, connection status
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
3. sensor: PM2.5, PM10, VOC, NOx, HEPA filter life/type, carbon filter life/type, temperature, WiFi signal, connection status
4. binary_sensor: Online status, night mode status, heating status
5. number: Sleep timer control, oscillation angle controls
6. select: Fan control mode, oscillation patterns, heating mode
7. switch: Night mode, heating control, continuous monitoring

## Dyson VisNav Robot Vacuum Configuration

### Description

Configuration example for Dyson VisNav Robot Vacuum with Robot and WiFi capabilities.

### Available Platforms

1. vacuum: Stop, dock, status control
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
4. For persistent issues, please open an [issue](https://github.com/cmgrayb/hass-dyson/issues)

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
