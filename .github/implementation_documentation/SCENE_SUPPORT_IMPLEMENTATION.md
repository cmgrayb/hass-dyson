# Scene Support Implementation Summary

## Overview

Implemented comprehensive scene support for the Dyson Home Assistant integration by exposing all settable device properties as `extra_state_attributes` across all entity platforms. This enables Home Assistant scenes to capture and restore the complete device state.

## Implementation Details

### Core Scene Support Principle

Every entity that controls a settable device property now exposes those properties in `extra_state_attributes`, making them available for scene capture and restoration. This follows Home Assistant's scene documentation which states that all entity state and attributes are captured.

### Entities Enhanced with Scene Support

#### 1. Fan Entity (`fan.py`)

**Enhanced `extra_state_attributes`:**

- `fan_speed` - Current speed percentage (0-100)
- `preset_mode` - Auto/Manual mode
- `direction` - Fan direction (forward/reverse)
- `is_on` - Fan power state
- `fan_power` - Raw device power state (ON/OFF)
- `fan_state` - Raw device fan state (OFF/FAN)
- `fan_speed_setting` - Raw device speed setting (0001-0010/AUTO)
- `auto_mode` - Auto mode enabled (boolean)
- `night_mode` - Night mode enabled (boolean)
- `oscillation_enabled` - Oscillation on/off
- `angle_low` - Lower oscillation angle
- `angle_high` - Upper oscillation angle
- `oscillation_span` - Calculated angle span
- `sleep_timer` - Sleep timer in minutes (0 if off)

#### 2. Climate Entity (`climate.py`)

**Enhanced `extra_state_attributes`:**

- `target_temperature` - Target temperature in Celsius
- `hvac_mode` - Current HVAC mode (heat/auto/fan_only/off)
- `fan_mode` - Fan speed mode (1-10/Auto)
- `heating_mode` - Raw device heating mode (OFF/HEAT/AUTO)
- `auto_mode` - Auto mode enabled (boolean)
- `fan_speed` - Raw device fan speed setting
- `fan_power` - Fan power state (boolean)
- `target_temperature_kelvin` - Device-format temperature for commands

#### 3. Switch Entities (`switch.py`)

**Oscillation Switch:**

- `oscillation_enabled` - Oscillation state (boolean)
- `oscillation_angle_low` - Lower oscillation angle
- `oscillation_angle_high` - Upper oscillation angle

**Heating Switch:**

- `heating_mode` - Raw device heating mode (OFF/HEAT/AUTO)
- `heating_enabled` - Heating enabled (boolean)
- `target_temperature` - Target temperature in Celsius
- `target_temperature_kelvin` - Device-format temperature

**Continuous Monitoring Switch:**

- `continuous_monitoring` - Monitoring enabled (boolean)
- `monitoring_mode` - Raw device monitoring mode (ON/OFF)

#### 4. Select Entities (`select.py`)

**Oscillation Mode Select:**

- `oscillation_mode` - Current mode (Off/Narrow/Wide/Custom)
- `oscillation_enabled` - Oscillation state (boolean)
- `oscillation_angle_low` - Lower oscillation angle
- `oscillation_angle_high` - Upper oscillation angle
- `oscillation_center` - Center angle point
- `oscillation_span` - Calculated angle span

**Heating Mode Select:**

- `heating_mode` - Current heating mode (Off/Heating/Auto Heat)
- `heating_mode_raw` - Raw device heating mode (OFF/HEAT/AUTO)
- `heating_enabled` - Heating enabled (boolean)
- `target_temperature` - Target temperature in Celsius
- `target_temperature_kelvin` - Device-format temperature

#### 5. Number Entity (`number.py`)

**Sleep Timer Number:**

- `sleep_timer_minutes` - Timer value in minutes
- `sleep_timer_raw` - Raw device timer value
- `sleep_timer_enabled` - Timer enabled (boolean)

### Device Control Methods Available

The following device control methods are available for scene restoration:

- `set_fan_power(enabled: bool)`
- `set_fan_speed(speed: int)` (1-10)
- `set_auto_mode(enabled: bool)`
- `set_night_mode(enabled: bool)`
- `set_oscillation(enabled: bool)`
- `set_oscillation_angles(lower: int, upper: int)`
- `set_heating_mode(mode: str)` (OFF/HEAT/AUTO)
- `set_sleep_timer(minutes: int)`

## Scene Usage Examples

### Creating a Scene

When a user creates a scene in Home Assistant, all the `extra_state_attributes` from each entity are automatically captured:

```yaml
# Example captured scene state
- entity_id: fan.dyson_living_room
  state: "on"
  attributes:
    fan_speed: 50
    preset_mode: "Manual"
    auto_mode: false
    night_mode: true
    oscillation_enabled: true
    angle_low: 45
    angle_high: 315
    sleep_timer: 120

- entity_id: climate.dyson_living_room
  state: "heat"
  attributes:
    target_temperature: 22.0
    hvac_mode: "heat"
    fan_mode: "5"
    heating_mode: "HEAT"
```

### Scene Restoration

When the scene is activated, Home Assistant can use the entity's service calls to restore all the captured state:

```python
# Restoration calls made by Home Assistant
await fan.async_turn_on(percentage=50)
await fan.async_set_preset_mode("Manual")
await device.set_night_mode(True)
await device.set_oscillation_angles(45, 315)
await device.set_sleep_timer(120)

await climate.async_set_hvac_mode("heat")
await climate.async_set_temperature(temperature=22.0)
await climate.async_set_fan_mode("5")
```

## Comprehensive Device State Coverage

### All Major Settable Properties Exposed

The implementation ensures all major device control properties are exposed somewhere in the entity ecosystem:

| Device Property       | Exposed In                       | Control Method             |
| --------------------- | -------------------------------- | -------------------------- |
| Fan Power             | Fan entity                       | `set_fan_power()`          |
| Fan Speed             | Fan, Climate entities            | `set_fan_speed()`          |
| Auto Mode             | Fan, Climate entities            | `set_auto_mode()`          |
| Night Mode            | Fan entity                       | `set_night_mode()`         |
| Oscillation           | Fan, Switch, Select entities     | `set_oscillation()`        |
| Oscillation Angles    | Fan, Switch, Select entities     | `set_oscillation_angles()` |
| Heating Mode          | Climate, Switch, Select entities | `set_heating_mode()`       |
| Target Temperature    | Climate, Switch, Select entities | `async_set_temperature()`  |
| Sleep Timer           | Fan, Number entities             | `set_sleep_timer()`        |
| Continuous Monitoring | Switch entity                    | Device command             |

### Data Consistency

- All temperature values are exposed in both Celsius (for user readability) and Kelvin format (for device commands)
- Oscillation information is consistently exposed across fan, switch, and select entities
- Raw device values are preserved alongside processed values for debugging and advanced use cases

## Testing

Comprehensive test suite validates scene support:

- **9 test classes** covering all entity types
- **Individual entity scene support tests** - verify each entity exposes correct attributes
- **Integration test** - verifies all essential device properties are covered somewhere
- **State consistency tests** - ensure multiple entities exposing same data stay consistent

Key test validations:

- All major settable device properties are exposed as scene attributes
- Temperature conversions are correct (Celsius ↔ Kelvin)
- Boolean state conversions work properly (ON/OFF ↔ true/false)
- Raw device values are preserved alongside processed values
- No critical scene properties are missing

## Benefits

1. **Complete Scene Support**: Users can create comprehensive scenes that capture all device settings
2. **State Transparency**: All device state is visible in entity attributes for debugging and automation
3. **Flexible Automation**: Automations can access detailed device state information
4. **Consistent Experience**: Scene capture/restore works seamlessly with Dyson devices
5. **Future-Proof**: New device properties can easily be added to the scene support framework

## Usage for Users

Users can now:

1. **Create scenes** that capture complete Dyson device state (fan speed, oscillation angles, heating settings, timers, etc.)
2. **Restore scenes** to exactly recreate device conditions
3. **Use in automations** - access detailed device state through entity attributes
4. **Debug device issues** - all raw device values are visible in entity attributes

The implementation provides comprehensive scene support while maintaining backward compatibility and not affecting existing entity functionality.
