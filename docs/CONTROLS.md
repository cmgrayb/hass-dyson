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
2. Options: 45°, 90°, 180°, 350°, Custom
3. Purpose: Quick selection of common oscillation patterns

#### Angle Range Controls

1. **Lower Angle**: `number.{device_name}_oscillation_lower_angle` (0-350°)
2. **Upper Angle**: `number.{device_name}_oscillation_upper_angle` (0-350°)
3. **Center Angle**: `number.{device_name}_oscillation_center_angle` (0-350°)
4. **Oscillation Angle**: `number.{device_name}_oscillation_angle` (Sets custom span between low and high angle 0-350°)

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
2. Options: 15°, 40°, 70°
3. Purpose: Quick selection of common oscillation patterns with fixed 177° center

#### Angle Range Controls

1. **Lower Angle**: `number.{device_name}_oscillation_day0_lower_angle` (142-212°)
2. **Upper Angle**: `number.{device_name}_oscillation_day0_upper_angle` (142-212°)
3. **Center Angle**: `number.{device_name}_oscillation_day0_center_angle` (147-207°)
4. **Oscillation Span**: `number.{device_name}_oscillation_day0_angle_span` (10-70°)

Note: Day0 capability is limited to presets only and will always center at ~180°.  Use of the Set Oscillation Angle service is possible, but not recommended.  Instead, please use a service against the Oscillation Mode Select entity to choose the desired preset, and the Oscillation on/off service built into Home Assistant for toggle.

#### Day0 Preset Patterns

| Pattern | Description | Angle Range | Center Point |
|---------|-------------|-------------|--------------|
| **15°** | Very narrow focused area | ±7.5° from center | Current center angle (adjustable) |
| **40°** | Narrow coverage | ±20° from center | Current center angle (adjustable) |
| **70°** | Medium coverage | ±35° from center | Current center angle (adjustable) |

## Night Mode Control

### Description

Night mode optimizes device operation for sleep environments by reducing noise, display brightness, and limiting maximum fan speeds.

### Purpose

Provide quiet operation suitable for bedrooms and sleep areas while maintaining air quality.

### Technical Specifications

1. Entity ID: `switch.{device_name}_night_mode`
2. Platform: Switch
3. States: On/Off
4. Availability: All Environment Cleaner devices with "Scheduling" capability
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

## Robotic Vacuum Controls

### Description

Robotic vacuum controls provide full cleaning operation management for Dyson robot vacuum cleaners (360 Eye, 360 Heurist, 360 Vis Nav). Controls are spread across three areas of Home Assistant: the vacuum entity, per-zone buttons (Vis Nav only), and developer-targeted services.

### Purpose

Start, pause, resume, and stop cleaning operations; direct the robot to specific mapped zones; and configure per-zone cleaning strategies.

---

### Vacuum Entity (All Robot Models)

The primary robot vacuum interface is a standard Home Assistant vacuum entity. It is found in **Settings → Devices & Services → [Your Dyson Device] → Controls**, or by searching for `vacuum.{device_name}` in **Developer Tools → States**.

#### Technical Specifications

1. Entity ID: `vacuum.{device_name}`
2. Platform: Vacuum
3. Availability: All robot vacuum models (Dyson 360 Eye, 360 Heurist, 360 Vis Nav)
4. Update Frequency: Real-time via MQTT state changes

#### Supported Commands

| Command | HA Service | Behavior |
|---------|-----------|----------|
| **Start** | `vacuum.start` | Starts a new whole-home clean when docked or finished; resumes a paused clean when mid-session |
| **Pause** | `vacuum.pause` | Suspends the current cleaning operation in place |
| **Stop** | `vacuum.stop` | Aborts the current clean and sends the robot back to its dock |
| **Return to Base** | `vacuum.return_to_base` | Equivalent to Stop — sends the ABORT command and docks the robot |

> **Start vs. Resume**: The `vacuum.start` command is context-aware. When the robot is docked or has finished a previous run (`INACTIVE_CHARGED`, `INACTIVE_CHARGING`, `INACTIVE_DISCHARGING`, `FULL_CLEAN_FINISHED`, `FAULT_ON_DOCK`), it sends a fresh `START` command for a global (whole-home) clean. If the robot is currently paused mid-clean, it sends `RESUME` instead.

#### State Attributes

The vacuum entity exposes the following additional attributes:

| Attribute | Description |
|-----------|-------------|
| `raw_state` | The underlying Dyson robot state string (e.g., `FULL_CLEAN_RUNNING`) |
| `global_position` | Current `[x, y]` coordinates when available during cleaning |
| `full_clean_type` | Clean trigger type (`immediate`, `scheduled`, `manual`) |
| `clean_id` | Unique identifier for the current cleaning session |

---

### Standard HA Area-Based Zone Cleaning — `vacuum.clean_area` (HA 2026.3+, Vis Nav Only)

Home Assistant 2026.3 introduced a **standard `vacuum.clean_area` action** that maps vacuum-specific segments to native Home Assistant areas. The Dyson 360 Vis Nav supports this standard interface, enabling voice assistant commands such as "Hey Google, clean the kitchen" and consistent cross-brand automation syntax.

> **Prerequisites**: A Dyson cloud account (`auth_token`) must be configured, and the robot must have a completed persistent map. This is the **recommended** approach for new automations.

#### One-Time Setup: Map Dyson Zones to HA Areas

Before using `vacuum.clean_area`, link your Dyson zone names to Home Assistant areas once:

1. Go to **Settings → Devices & Services → Entities**.
2. Search for your Vis Nav vacuum entity (e.g., `vacuum.dyson_360_vis_nav`).
3. Click the entity, then select the **cogwheel** (⚙) icon.
4. Select **Map vacuum segments to areas**.
   - The dialog shows Dyson zones on the left and HA areas on the right.
   - If the option does not appear, verify the cloud account is configured and a map exists.
5. For each Dyson zone, select the corresponding HA area.
6. Click **Save**.

> If zones in the MyDyson app change (rooms added or removed), Home Assistant will surface a **repair issue** prompting you to re-configure the mapping.

#### Using `vacuum.clean_area` in Automations

```yaml
service: vacuum.clean_area
target:
  entity_id: vacuum.dyson_360_vis_nav
data:
  cleaning_area_id:
    - kitchen
    - living_room
```

The `cleaning_area_id` values are **HA area slugs** (as shown in **Settings → Areas**), not Dyson zone names. Multiple areas can be cleaned in a single action call.

---

### Zone Clean Buttons (Dyson 360 Vis Nav Only)

For Vis Nav owners who have completed an initial mapping run, the integration automatically creates one **button entity per mapped room**. These are found in **Settings → Devices & Services → [Your Dyson Device] → Controls**.

> **Prerequisites**: A Dyson cloud account (`auth_token`) must be configured, and the robot must have a saved persistent map from at least one completed mapping or cleaning run.

#### Per-Zone Clean Buttons

| Entity ID | Name | Behavior |
|-----------|------|----------|
| `button.{device_name}_clean_{zone_name}` | Clean {Zone Name} | Immediately starts a zone-specific clean targeting that room only |

- Each button corresponds to a mapped room in the Dyson app (e.g., **Clean Living Room**, **Clean Bedroom**).
- Pressing the button sends a `zoneConfigured` START command — the robot will clean only the selected zone.
- Zone icons in the HA UI reflect the room type set in the MyDyson app.

#### Refresh Zone List Button (Diagnostic)

| Entity ID | Name | Purpose |
|-----------|------|---------|
| `button.{device_name}_refresh_zones` | Refresh Zone List | Re-fetches the persistent map and zone list from the Dyson cloud |

- This button is in the **Diagnostic** entity category; enable it via **Settings → Devices & Services → [Device] → Entities → Show disabled entities**.
- Use it after adding or renaming rooms in the MyDyson app, then **restart Home Assistant** to surface any newly created zone buttons.
- Zone metadata is otherwise cached for 1 hour.

---

### Services (Automations and Scripts)

The following services are available under the `hass_dyson` domain for use in automations, scripts, and **Developer Tools → Services**. They are registered for all robot vacuum models unless noted.

#### `hass_dyson.start_zone_clean` (Vis Nav Only)

Start a zone-specific clean targeting one or more named rooms. Zones can be identified by display name (as shown in the MyDyson app) or by their internal zone ID.

| Field | Required | Description |
|-------|----------|-------------|
| `device_id` | Yes | The Home Assistant device ID of the Dyson robot vacuum |
| `zones` | Yes | List of zone names or IDs to clean (e.g., `["Living room", "Hallway"]`) |

**Example automation:**

```yaml
service: hass_dyson.start_zone_clean
data:
  device_id: "abc123def456"
  zones:
    - "Living room"
    - "Hallway"
```

- Zone names are matched case-insensitively.
- If any zone name cannot be resolved, the service raises an error and lists the known zone names.
- Persistent map metadata is fetched from the Dyson cloud and cached for 1 hour.

#### `hass_dyson.set_zone_behaviour` (Vis Nav Only)

Override the cleaning strategy for a specific zone. This setting is persisted to the Dyson cloud and applies to all subsequent cleans — equivalent to changing a zone's behaviour in the MyDyson app.

| Field | Required | Description |
|-------|----------|-------------|
| `device_id` | Yes | The Home Assistant device ID of the Dyson robot vacuum |
| `zone` | Yes | Zone name or ID (e.g., `"Living room"` or `"4"`) |
| `cleaning_strategy` | Yes | One of: `auto`, `quick`, `quiet`, `boost` |

**Cleaning strategy options:**

| Strategy | Description |
|----------|-------------|
| `auto` | Device selects speed automatically based on surface type |
| `quick` | Lower suction, faster pass |
| `quiet` | Reduced noise, lower power |
| `boost` | Maximum suction power |

**Example automation:**

```yaml
service: hass_dyson.set_zone_behaviour
data:
  device_id: "abc123def456"
  zone: "Bedroom"
  cleaning_strategy: "quiet"
```

---

### Where to Find Each Control

| Control Type | Location in Home Assistant | Models | Notes |
|---|---|---|---|
| Vacuum entity (start/pause/stop) | Settings → Devices → [Device] → Controls | All robot models | Standard HA vacuum controls |
| **`vacuum.clean_area` action** | Automations → Add action → Vacuum: Clean area | 360 Vis Nav only | **Recommended** — uses HA areas; voice assistant compatible |
| Per-zone clean buttons | Settings → Devices → [Device] → Controls | 360 Vis Nav only | Alternative; no area mapping required |
| Refresh Zone List button | Settings → Devices → [Device] → Entities (diagnostic) | 360 Vis Nav only | Forces cloud re-fetch of zone metadata |
| `hass_dyson.start_zone_clean` service | Developer Tools → Services | 360 Vis Nav only | Alternative; uses Dyson zone names directly |
| `hass_dyson.set_zone_behaviour` service | Developer Tools → Services | 360 Vis Nav only | Sets per-zone cleaning strategy |

---

### Usage Notes

- Zone-based cleaning (all methods) requires a completed persistent map and a configured Dyson cloud account.
- **`vacuum.clean_area` is the recommended approach** for new automations — it integrates with HA areas and unlocks voice assistant support.
- Per-zone buttons and `hass_dyson.start_zone_clean` remain available as alternatives and do not require configuring HA area mappings.
- If the **"Map vacuum segments to areas"** option is missing from entity settings, verify the cloud account is active and a mapping run has completed.
- If zones change in the MyDyson app (rooms added, removed, or renamed), a **repair issue** will appear in Home Assistant prompting you to re-configure the area mapping.
- If no zone buttons appear after setup, press **Refresh Zone List** and then restart Home Assistant.
- The `vacuum.start` command always initiates a **whole-home** (`global`) clean. Use `vacuum.clean_area`, zone buttons, or `start_zone_clean` to target specific rooms.
- Power level (Quiet / High / Max on Heurist; Auto / Quick / Quiet / Boost on Vis Nav) is controlled via the dedicated power-level select entity, not through vacuum commands.

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
4. **Climate Integration**: Create a template climate entity for fan-only devices to automatically run your fan on a thermostat for cooling

## Troubleshooting

### Common Issues

1. **Timer Display Delays**: Normal behavior due to MQTT limitations - actual timing is accurate
2. **Oscillation Not Responding**: Check device positioning and ensure clear movement path
3. **Auto Mode Not Activating**: Verify air quality sensors are functional and clean
4. **Night Mode Not Quiet Enough**: Check fan speed limits and consider manual speed override

### Connection Issues

1. **Controls Not Responding**:
    a. Check WiFi connectivity and MQTT connection status
    b. Try setting a static IP or DNS entry by reconfiguring the device to bypass local mDNS issues
2. **Delayed Updates**: Normal for some settings and devices - allow up to 30 seconds for state changes
3. **Missing Controls**: If manually created, verify device capabilities and configuration; if created from cloud account, please open an issue

For additional troubleshooting, see the main integration documentation and device compatibility guide.
