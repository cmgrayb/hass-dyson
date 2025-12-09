# HASS-Dyson Controls

## Fan Control

### Description

The fan control provides primary speed and mode management for all Dyson devices with fan capabilities. This is the main interface for controlling air circulation and filtration.

### Purpose

Control fan speed, power state, and operational modes for optimal air circulation and air quality management.

### Technical Specifications

1. Entity ID: `fan.{device_name}`
2. Platform: Fan
3. Speed Range: 1-10 (mapped from device's internal speed settings)
4. Features: On/off, Speed control, Preset modes
5. Preset Modes: Auto, Manual, Sleep (device-dependent)
6. Availability: All Environment Cleaner devices
7. Update Frequency: Real-time with device state changes

### Preset Modes

| Mode | Description | Device Behavior |
|------|-------------|-----------------|
| **Auto** | Automatic speed adjustment | Device adjusts fan speed based on air quality sensors |
| **Manual** | Fixed speed control | Fan runs at user-selected speed (1-10) |

### Usage Notes

- Speed settings are automatically converted between Home Assistant's 1-10 scale and the device's internal speed representation
- Preset mode availability depends on device capabilities and connection type
- Sleep mode may not be available on all device models or connection types

## Sleep Timer

### Description

The sleep timer allows setting a countdown timer for automatic device shutdown, providing energy savings and sleep comfort.

### Purpose

Schedule automatic device shutdown after a specified time period, commonly used for nighttime operation.

### Technical Specifications

1. Entity ID: `number.{device_name}_sleep_timer`
2. Platform: Number
3. Range: 0-540 minutes (9 hours)
4. Step: 15 minutes
5. Unit: Minutes
6. Mode: Number input
7. Availability: Devices with Scheduling capability
8. Update Frequency: Real-time countdown with minute precision

### Timer Behavior

The sleep timer operates with the following characteristics:

- **Setting Accuracy**: Timer is set precisely to the specified minute value
- **Display Accuracy**: Updates show whole minutes remaining (rounded down)
- **Update Timing**: Initial updates within 30 seconds, then every 60 seconds
- **Countdown Precision**: Due to Dyson MQTT limitations, displayed time may vary by up to 30 seconds from actual remaining time

### Usage Examples

| Set Value | Behavior |
|-----------|----------|
| **0** | Timer off - device runs continuously |
| **15** | Device shuts off after 15 minutes |
| **60** | Device shuts off after 1 hour |
| **540** | Device shuts off after 9 hours (maximum) |

### Important Limitations

**Timer Display Accuracy**: Due to limitations in Dyson's MQTT implementation, the displayed countdown may vary by up to 30 seconds from the actual remaining time. The timer will be set accurately, but the real-time display updates are limited by the device's reporting frequency and whole-minute precision.

## Oscillation Control

### Description

Oscillation controls manage the horizontal movement patterns of the device's airflow, providing customizable air distribution across different areas.

### Purpose

Direct airflow to specific areas or create sweeping air circulation patterns for optimal room coverage.

### Advanced Oscillation (AdvanceOscillationDay1 Capability)

Devices with advanced oscillation capability provide additional precise controls:

#### Oscillation Mode Select

1. Entity ID: `select.{device_name}_oscillation_mode`
2. Options: Off, 45°, 90°, 180°, 350°, Custom
3. Purpose: Quick selection of common oscillation patterns

#### Angle Range Controls

1. **Lower Angle**: `number.{device_name}_oscillation_lower_angle` (0-355°)
2. **Upper Angle**: `number.{device_name}_oscillation_upper_angle` (5-360°)
3. **Center Angle**: `number.{device_name}_oscillation_center_angle` (0-359°)
4. **Oscillation Angle**: `number.{device_name}_oscillation_angle` (Sets custom span between low and high angle 5-360°)

#### Preset Patterns

| Pattern | Description | Angle Range |
|---------|-------------|-------------|
| **45°** | Narrow focused area | ±22.5° from center |
| **90°** | Quarter circle coverage | ±45° from center |
| **180°** | Half circle coverage | ±90° from center |
| **350°** | Nearly full circle | 5° gap for motor positioning |
| **Custom** | User-defined range | Manual lower/upper angles |

### Advanced Oscillation Day0 (AdvanceOscillationDay0 Capability)

Devices with the AdvanceOscillationDay0 capability provide a simplified oscillation control with a fixed center point:

#### Oscillation Mode Select

1. Entity ID: `select.{device_name}_oscillation_mode_day0`
2. Options: Off, 15°, 40°, 70°, Custom
3. Purpose: Quick selection of common oscillation patterns with fixed 177° center

#### Angle Range Controls

1. **Lower Angle**: `number.{device_name}_oscillation_day0_lower_angle` (142-212°)
2. **Upper Angle**: `number.{device_name}_oscillation_day0_upper_angle` (142-212°)
3. **Center Angle**: `number.{device_name}_oscillation_day0_center_angle` (147-207°)
4. **Oscillation Span**: `number.{device_name}_oscillation_day0_angle_span` (10-70°)

Note: Day0 capability allows flexible custom ranges within 142°-212° physical limits. The center angle control lets you position preset modes (15°, 40°, 70°) anywhere within the valid range, while custom mode allows complete manual control.

#### Day0 Preset Patterns

| Pattern | Description | Angle Range | Center Point |
|---------|-------------|-------------|--------------|
| **15°** | Very narrow focused area | ±7.5° from center | Current center angle (adjustable) |
| **40°** | Narrow coverage | ±20° from center | Current center angle (adjustable) |
| **70°** | Medium coverage | ±35° from center | Current center angle (adjustable) |
| **Custom** | User-defined range | Any range within 142°-212° | Flexible manual control |

**Example**: With center set to 160°, the 40° preset creates 140°-180° range. With center at 200°, it creates 180°-212° range (clamped to physical limits).

## Night Mode Control

### Description

Night mode optimizes device operation for sleep environments by reducing noise, display brightness, and limiting maximum fan speeds.

### Purpose

Provide quiet operation suitable for bedrooms and sleep areas while maintaining air quality.

### Technical Specifications

1. Entity ID: `switch.{device_name}_night_mode`
2. Platform: Switch
3. States: On/Off
4. Availability: All Environment Cleaner devices
5. Update Frequency: Real-time with device state changes

### Night Mode Effects

When enabled, night mode typically:

- **Reduces Fan Speed**: Limits maximum speed for quieter operation
- **Dims Display**: Reduces or turns off LED display brightness
- **Quieter Operation**: Prioritizes noise reduction over maximum airflow
- **Maintains Functionality**: Air quality monitoring and basic filtration continue

### Interaction with Other Controls

- **Auto Mode**: Night mode can work alongside auto mode with reduced speed limits
- **Manual Speed**: Speed adjustments are constrained to night mode limits
- **Timer**: Sleep timer functions normally in night mode

## Continuous Monitoring

### Description

Continuous monitoring controls whether the device maintains sensor operation and data collection when the fan is turned off.

### Purpose

Enable environmental monitoring and data collection even when active air circulation is not needed.

### Technical Specifications

1. Entity ID: `switch.{device_name}_continuous_monitoring`
2. Platform: Switch
3. States: On/Off
4. Availability: All Environment Cleaner devices with sensors
5. Update Frequency: Real-time with device state changes

### Behavior

- **On**: Sensors remain active when fan is off, continuing air quality monitoring
- **Off**: Sensors may enter power-saving mode when fan is off

Note: Changing the switch value affects historical data availability for air quality trends

### Power Consumption

Enabling continuous monitoring will slightly increase power consumption when the fan is off, but provides continuous environmental data for monitoring and automation.

## Heating Controls (HP Models)

### Description

Heating controls are available on Heat + Cool (HP) models and provide temperature regulation capabilities.

### Purpose

Provide heating functionality and temperature control for year-round climate management.

### Heating Mode Switch

#### Technical Specifications

1. Entity ID: `switch.{device_name}_heating`
2. Platform: Switch
3. States: On/Off
4. Availability: Devices with Heating capability
5. Update Frequency: Real-time with device state changes

#### Behavior

- **On**: Enables heating element and heating functionality
- **Off**: Disables heating, device operates as fan/purifier only

### Climate Control

#### Technical Specifications

1. Entity ID: `climate.{device_name}`
2. Platform: Climate
3. HVAC Modes: Off, Fan Only, Heat, Auto
4. Temperature Range: Device-dependent (typically 1-37°C)
5. Availability: Devices with Heating capability

#### Features

- **Target Temperature**: Set desired room temperature
- **Current Temperature**: Real-time room temperature reading
- **HVAC Modes**: Full climate control interface
- **Fan Speed**: Integrated with main fan control

### Heating Mode Select

#### Technical Specifications

1. Entity ID: `select.{device_name}_heating_mode`
2. Options: Off, Heating, Auto Heat
3. Purpose: Quick heating mode selection without full climate interface

## Usage Best Practices

### Energy Efficiency

1. **Use Auto Mode**: Let the device adjust speed based on air quality
2. **Set Sleep Timers**: Avoid running unnecessarily when air quality is good
3. **Night Mode**: Use for bedroom operation to balance performance and noise
4. **Continuous Monitoring**: Consider power consumption vs. data and automatic air cleaning needs

### Air Quality Optimization

1. **Monitor Sensor Data**: Use PM2.5/PM10 readings to understand air quality patterns
2. **Oscillation Patterns**: Adjust to direct clean air where needed most
3. **Filter Maintenance**: Replace filters promptly when alerts appear
4. **Strategic Placement**: Position device for optimal room coverage with oscillation

### Automation Suggestions

1. **Schedule Operation**: Use timers and schedules for different daily periods
2. **Scene Integration**: Include in bedtime, morning, and away scenes
3. **Weather Integration**: Adjust settings based on outdoor air quality or pollen forecasts

## Troubleshooting

### Common Issues

1. **Timer Display Delays**: Normal behavior due to MQTT limitations - actual timing is accurate
2. **Oscillation Not Responding**: Check device positioning and ensure clear movement path
3. **Auto Mode Not Activating**: Verify air quality sensors are functional and clean
4. **Night Mode Not Quiet Enough**: Check fan speed limits and consider manual speed override

### Connection Issues

1. **Controls Not Responding**: Check WiFi connectivity and MQTT connection status
2. **Delayed Updates**: Normal for some settings - allow up to 30 seconds for state changes
3. **Missing Controls**: Verify device capabilities and integration configuration

For additional troubleshooting, see the main integration documentation and device compatibility guide.
