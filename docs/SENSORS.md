# HASS-Dyson Sensors

This document describes all available sensors in the HASS-Dyson integration, their purpose, discovery methods, and technical specifications.

## Air Quality Sensors

### PM2.5 Sensor

#### Description

The PM2.5 sensor monitors fine particulate matter with diameter ≤ 2.5 micrometers in the air, providing real-time air quality monitoring for health assessment.

#### Purpose

Track fine particulate matter concentration for health monitoring and air quality assessment. Fine particles can penetrate deep into lungs and affect cardiovascular health.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_pm25`
2. Unit: µg/m³ (micrograms per cubic meter)
3. Device Class: PM2.5
4. State Class: Measurement
5. Range: 0-999 µg/m³
6. Icon: mdi:air-filter
7. Availability: Devices with ExtendedAQ capability
8. Update Frequency: Real-time with device data updates
9. MQTT Key: `pm25` in environmental-data

#### Health Guidelines

Fine particulate matter can penetrate deep into lungs and cause health issues. WHO guidelines recommend annual average < 5 µg/m³, with values above 25 µg/m³ considered unhealthy for sensitive groups.

### PM10 Sensor

#### Description

The PM10 sensor monitors coarse particulate matter with diameter ≤ 10 micrometers in the air, including dust, pollen, and mold spores.

#### Purpose

Track coarse particulate matter concentration for comprehensive air quality monitoring. Includes larger particles that affect respiratory system.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_pm10`
2. Unit: µg/m³ (micrograms per cubic meter)
3. Device Class: PM10
4. State Class: Measurement
5. Range: 0-999 µg/m³
6. Icon: mdi:air-filter
7. Availability: Devices with ExtendedAQ capability
8. Update Frequency: Real-time with device data updates
9. MQTT Key: `pm10` in environmental-data

#### Health Guidelines

Coarse particulate matter including dust, pollen, and mold spores. WHO guidelines recommend annual average < 15 µg/m³, with values above 50 µg/m³ considered unhealthy for sensitive groups.

### P25R Level Sensor

#### Description

The P25R sensor provides additional fine particulate matter readings using an alternative measurement method, offering enhanced air quality monitoring precision.

#### Purpose

Supplement PM2.5 readings with additional precision measurement data for comprehensive fine particle monitoring and device calibration.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_p25r`
2. Unit: µg/m³ (micrograms per cubic meter)
3. Device Class: None
4. State Class: Measurement
5. Range: 0-999 µg/m³
6. Icon: mdi:air-filter
7. Entity Category: Diagnostic
8. Availability: Devices with ExtendedAQ capability
9. Update Frequency: Real-time with device data updates
10. MQTT Key: `p25r` in environmental-data

#### Technical Notes

P25R readings may show slight variations from standard PM2.5 measurements due to different detection methods. Used for device calibration and enhanced measurement accuracy.

### P10R Level Sensor

#### Description

The P10R sensor provides additional coarse particulate matter readings using an alternative measurement method, offering enhanced air quality monitoring precision.

#### Purpose

Supplement PM10 readings with additional precision measurement data for comprehensive coarse particle monitoring and device calibration.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_p10r`
2. Unit: µg/m³ (micrograms per cubic meter)
3. Device Class: None
4. State Class: Measurement
5. Range: 0-999 µg/m³
6. Icon: mdi:air-filter
7. Entity Category: Diagnostic
8. Availability: Devices with ExtendedAQ capability
9. Update Frequency: Real-time with device data updates
10. MQTT Key: `p10r` in environmental-data

#### Technical Notes

P10R readings may show slight variations from standard PM10 measurements due to different detection methods. Used for device calibration and enhanced measurement accuracy.

## Gas Quality Sensors

### CO2 Sensor

#### Description

The CO2 sensor monitors carbon dioxide concentration in the air, providing crucial indoor air quality information for ventilation and health management.

#### Purpose

Track CO2 levels to ensure proper ventilation and identify when fresh air circulation is needed for optimal indoor air quality and cognitive performance.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_co2`
2. Unit: ppm (parts per million)
3. Device Class: CO2
4. State Class: Measurement
5. Range: 0-5000 ppm
6. Icon: mdi:molecule-co2
7. Availability: Devices with ExtendedAQ capability (when CO2 data present)
8. Update Frequency: Real-time with device data updates
9. MQTT Key: `co2` in environmental-data

#### Health Guidelines

CO2 concentrations above 1000 ppm indicate poor ventilation. Levels above 5000 ppm can cause drowsiness and reduced cognitive function. Outdoor levels are typically 400-420 ppm.

### NO2 Sensor

#### Description

The NO2 sensor monitors nitrogen dioxide concentration in the air, detecting gases from combustion processes and outdoor pollution infiltration.

#### Purpose

Monitor nitrogen dioxide levels from vehicle emissions, gas appliances, and outdoor air pollution for comprehensive gas quality assessment.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_no2`
2. Unit: ppb (parts per billion)
3. Device Class: Nitrogen Dioxide
4. State Class: Measurement
5. Range: 0-1000 ppb
6. Icon: mdi:molecule
7. Availability: Devices with ExtendedAQ capability (when NO2 data present)
8. Update Frequency: Real-time with device data updates
9. MQTT Key: `no2` in environmental-data

#### Pollution Sources

Gas often produced by combustion processes including vehicle emissions, gas stoves, heating systems, and outdoor air pollution. Can cause respiratory irritation at elevated levels.

### HCHO (Formaldehyde) Sensor

#### Description

The HCHO sensor monitors formaldehyde concentration in the air, detecting emissions from furniture, building materials, and household products.

#### Purpose

Monitor formaldehyde levels for comprehensive chemical air quality assessment and identification of indoor pollution sources from furniture and materials.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_hcho`
2. Unit: ppb (parts per billion)
3. Device Class: None
4. State Class: Measurement
5. Range: 0-1000 ppb
6. Icon: mdi:chemical-weapon
7. Availability: Devices with ExtendedAQ capability (when HCHO data present)
8. Update Frequency: Real-time with device data updates
9. MQTT Key: `hcho` in environmental-data

#### Health Guidelines

Colorless gas commonly found in furniture, carpets, building materials, and cleaning products. Can cause eye, nose, and throat irritation. Values above 10 ppb may cause discomfort.

### VOC Sensor (Legacy)

#### Description

The VOC sensor monitors volatile organic compounds concentration in the air, detecting chemical compounds from household products and materials. This is a legacy sensor maintained for backward compatibility.

#### Purpose

Monitor chemical air quality through volatile organic compound detection on older devices without ExtendedAQ capability.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_voc`
2. Unit: ppb (parts per billion)
3. Device Class: Volatile Organic Compounds Parts
4. State Class: Measurement
5. Range: 0-500 ppb
6. Icon: mdi:chemical-weapon
7. Entity Category: Diagnostic
8. Availability: Devices with VOC capability (excluding ExtendedAQ devices)
9. Update Frequency: Real-time with device data updates

#### Legacy Support

This sensor is only created on older devices with VOC capability but without ExtendedAQ capability. ExtendedAQ devices provide more specific gas monitoring through CO2, NO2, and HCHO sensors.

## Environmental Sensors

### Temperature Sensor

#### Description

The temperature sensor measures ambient air temperature with automatic unit conversion support for climate monitoring and comfort management.

#### Purpose

Monitor environmental temperature for climate control, comfort management, and integration with heating systems.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_temperature`
2. Unit: °C (degrees Celsius)
3. Device Class: Temperature
4. State Class: Measurement
5. Icon: Default temperature icon
6. Availability: Devices with Heating capability OR EnvironmentalData capability
7. Update Frequency: Real-time with device data updates
8. MQTT Key: `tact` in environmental-data

#### Unit System Support

Home Assistant automatically converts temperature display between Celsius and Fahrenheit based on system configuration. The sensor reports in Celsius natively but displays in Fahrenheit for imperial unit systems.

#### Data Conversion

Raw Dyson data is in Kelvin × 10 format. The integration performs conversion: `(raw_value / 10) - 273.15`. For example, a value of "2950" converts to 21.85°C.

#### Discovery Logic

Temperature sensors are created when devices have either:
- Heating capability (for heater fans and heating-capable devices)
- EnvironmentalData capability (indicating environmental sensor support)

### Humidity Sensor

#### Description

The humidity sensor measures relative humidity in the air for environmental monitoring and comfort management.

#### Purpose

Monitor humidity levels for comfort, health management, and integration with humidifier systems.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_humidity`
2. Unit: % (percentage)
3. Device Class: Humidity
4. State Class: Measurement
5. Icon: Default humidity icon
6. Availability: Devices with Humidifier capability OR EnvironmentalData capability
7. Update Frequency: Real-time with device data updates
8. MQTT Key: `hact` in environmental-data

#### Discovery Logic

Humidity sensors are created when devices have either:
- Humidifier capability (for humidifier devices, determined by PH product type)
- EnvironmentalData capability (indicating environmental sensor support)

#### Data Format

Humidity values are reported as percentages from 0-100%. For example, a value of "0045" represents 45% relative humidity.

## Connectivity Sensors

### WiFi Signal Sensor

#### Description

The WiFi signal sensor monitors the device's wireless network signal strength for connectivity assessment and network troubleshooting.

#### Purpose

Monitor network connectivity strength for troubleshooting performance issues and optimizing device placement for better connectivity.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_wifi`
2. Unit: dBm (decibels relative to milliwatt)
3. Device Class: Signal Strength
4. State Class: Measurement
5. Icon: mdi:wifi
6. Entity Category: Diagnostic
7. Availability: EC (Environment Cleaner) and robot category devices
8. Update Frequency: Real-time with device data updates

#### Signal Strength Guidelines

Signal strength values closer to 0 indicate stronger signals:
- -30 dBm: Excellent signal
- -50 dBm: Very good signal
- -70 dBm: Good signal
- -80 dBm: Fair signal
- -90 dBm: Poor signal

#### Device Categories

Only available on devices with WiFi connectivity monitoring:
- EC (Environment Cleaner): Fan and filter devices with network capabilities
- Robot: Robotic vacuum cleaners with WiFi connectivity

### Connection Status Sensor

#### Description

The connection status sensor shows the current connectivity state of the device to Dyson cloud services for remote monitoring and control.

#### Purpose

Monitor device connectivity for troubleshooting network and cloud service issues, ensuring remote control functionality is available.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_connection_status`
2. Unit: None (text status)
3. Device Class: None
4. State Class: None
5. Icon: mdi:connection
6. Entity Category: Diagnostic
7. Availability: EC (Environment Cleaner) and robot category devices
8. Update Frequency: Real-time with connection changes

#### Status Values

Reports current connectivity state:
- "Connected": Device is online and communicating with cloud services
- "Disconnected": Device is offline or cannot reach cloud services

#### Troubleshooting

Use this sensor to identify connectivity issues that may affect remote control functionality or cloud-based features like scheduling and mobile app access.

## Filter Monitoring Sensors

### HEPA Filter Life Sensor

#### Description

The HEPA filter life sensor monitors the remaining operational life of the HEPA filter as a percentage, enabling proactive maintenance scheduling.

#### Purpose

Track filter replacement timing for optimal air filtration performance and ensure continuous air quality improvement.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_hepa_filter_life`
2. Unit: % (percentage)
3. Device Class: None
4. State Class: Measurement
5. Range: 0-100%
6. Icon: mdi:air-filter
7. Availability: Devices with ExtendedAQ capability
8. Update Frequency: Real-time with device data updates

#### Maintenance Guidelines

Shows percentage of filter life remaining based on usage time and air quality conditions. When this reaches 0%, filter replacement is required. Device typically alerts users when filter life drops below 10%.

#### Performance Impact

HEPA filters lose efficiency as they collect particles. Regular monitoring ensures optimal PM2.5 and PM10 filtration performance.

### HEPA Filter Type Sensor

#### Description

The HEPA filter type sensor displays the specific model of HEPA filter currently installed in the device for compatibility tracking.

#### Purpose

Track filter compatibility and ensure correct replacement filter selection for optimal performance and warranty compliance.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_hepa_filter_type`
2. Unit: None (text description)
3. Device Class: None
4. State Class: None
5. Icon: mdi:air-filter
6. Entity Category: Diagnostic
7. Availability: Devices with ExtendedAQ capability
8. Update Frequency: On receipt of status update from device

#### Filter Status Values

Shows specific HEPA filter model installed:
- Filter model number (e.g., "970013-03")
- "Not Installed" if no filter is detected
- "Unknown" if type cannot be determined

Useful for ordering correct replacement filters and ensuring compatibility.

### Carbon Filter Life Sensor

#### Description

The carbon filter life sensor monitors the remaining operational life of the carbon filter for odor and gas absorption, ensuring effective chemical filtration.

#### Purpose

Track carbon filter replacement timing for optimal chemical filtration performance and odor control.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_carbon_filter_life`
2. Unit: % (percentage)
3. Device Class: None
4. State Class: Measurement
5. Range: 0-100%
6. Icon: mdi:air-filter
7. Availability: Devices with carbon filter detected in device state
8. Update Frequency: Real-time with device data updates

#### Maintenance Guidelines

Shows percentage of carbon filter life remaining. Carbon filters absorb odors, formaldehyde, and other gases. When this reaches 0%, filter replacement is required for continued chemical filtration.

#### Discovery Logic

Carbon filter sensors are only created when the device reports a carbon filter type other than "NONE" in its device state (`cflt` field).

### Carbon Filter Type Sensor

#### Description

The carbon filter type sensor displays the specific model of carbon filter currently installed in the device for replacement tracking.

#### Purpose

Track carbon filter compatibility and ensure correct replacement filter selection for optimal chemical filtration performance.

#### Technical Specifications

1. Entity ID: `sensor.{device_name}_carbon_filter_type`
2. Unit: None (text description)
3. Device Class: None
4. State Class: None
5. Icon: mdi:air-filter
6. Entity Category: Diagnostic
7. Availability: Devices with carbon filter detected in device state
8. Update Frequency: On receipt of status update from device

#### Filter Status Values

Shows specific carbon filter model installed:
- Filter model number (e.g., "970532-01")
- "Not Installed" if no filter is detected
- "Unknown" if the type cannot be determined

#### Discovery Logic

Carbon filter type sensors are only created when the device reports a carbon filter type other than "NONE" in its device state (`cflt` field).

## Sensor Discovery and Capability Requirements

### Dynamic Sensor Discovery

The HASS-Dyson integration uses dynamic sensor discovery based on device capabilities and real-time data presence, ensuring that only supported sensors are created for each device model.

#### Discovery Process

1. **Capability Detection**: Device capabilities are read from the Dyson cloud API or manually configured
2. **Data Validation**: Environmental data presence is checked to confirm sensor support
3. **Entity Creation**: Only supported sensors with available data are created as Home Assistant entities

### Air Quality Sensors

#### ExtendedAQ Capability

ExtendedAQ is the primary capability for modern air quality monitoring and includes support for:

| Sensor | Always Created | Data Key | Discovery Method |
|--------|---------------|----------|------------------|
| PM2.5 | Yes | `pm25` | Always present on ExtendedAQ devices |
| PM10 | Yes | `pm10` | Always present on ExtendedAQ devices |
| P25R | Yes | `p25r` | Always present on ExtendedAQ devices |
| P10R | Yes | `p10r` | Always present on ExtendedAQ devices |
| CO2 | Dynamic | `co2` | Created only when CO2 data is present |
| NO2 | Dynamic | `no2` | Created only when NO2 data is present |
| HCHO | Dynamic | `hcho` | Created only when HCHO data is present |

#### Legacy VOC Support

For backward compatibility, the VOC sensor is maintained:

| Sensor | Capability | Availability |
|--------|------------|--------------|
| VOC | VOC capability | Only on devices WITHOUT ExtendedAQ |

**Note**: Devices with ExtendedAQ capability provide more specific gas monitoring through CO2, NO2, and HCHO sensors instead of the generic VOC sensor.

### Environmental Sensors

Environmental sensors use capability-based discovery with fallback support:

| Sensor | Primary Capability | Fallback Capability | Compatible Devices |
|--------|-------------------|-------------------|-------------------|
| Temperature | EnvironmentalData | Heating | Environmental monitoring devices, heater fans |
| Humidity | EnvironmentalData | Humidifier | Environmental monitoring devices, humidifier devices |

#### Capability Detection Methods

- **EnvironmentalData**: Detected from device capability list in cloud API
- **Heating**: Virtual capability assigned to HP (Heater/Purifier) model devices
- **Humidifier**: Virtual capability assigned to PH (Purifier/Humidifier) model devices

### Connectivity Sensors

Network and connectivity sensors are available based on device category:

| Sensor | Device Categories | Purpose |
|--------|------------------|---------|
| WiFi Signal | EC, Robot | Monitor network signal strength |
| Connection Status | EC, Robot | Monitor cloud connectivity |

#### Device Categories

- **EC (Environment Cleaner)**: Fan and filter devices with network capabilities
- **Robot**: Robotic vacuum cleaners with WiFi connectivity

### Filter Monitoring Sensors

Filter sensors use different discovery methods based on filter type:

#### HEPA Filter Sensors

| Sensor | Capability | Always Available |
|--------|------------|------------------|
| HEPA Filter Life | ExtendedAQ | Yes |
| HEPA Filter Type | ExtendedAQ | Yes |

#### Carbon Filter Sensors

| Sensor | Discovery Method | Availability |
|--------|-----------------|--------------|
| Carbon Filter Life | Device State Check | Only when `cflt` ≠ "NONE" |
| Carbon Filter Type | Device State Check | Only when `cflt` ≠ "NONE" |

**Note**: Carbon filter sensors are created dynamically based on the presence of carbon filter data (`cflt` field) in device state, not capability-based.

## Technical Implementation Details

### MQTT Communication

All sensor data is retrieved through MQTT messages from Dyson devices or their cloud connection, depending on configuration.

#### Environmental Data Request

Sensors request current environmental data using:
```json
{"msg":"REQUEST-PRODUCT-ENVIRONMENT-CURRENT-SENSOR-DATA"}
```

Device responds on `status/current` topic with:
```json
{
  "msg":"ENVIRONMENTAL-CURRENT-SENSOR-DATA",
  "time":"2025-11-17T17:22:40.000Z",
  "data":{
    "pm25":"0012",
    "pm10":"0018", 
    "p25r":"0010",
    "p10r":"0016",
    "co2":"0450",
    "no2":"0025",
    "hcho":"0008",
    "tact":"2950",
    "hact":"0045"
  }
}
```

#### Data Key Mapping

| Sensor | MQTT Key | Data Format | Conversion |
|--------|----------|-------------|------------|
| PM2.5 | `pm25` | Integer (µg/m³) | Direct value |
| PM10 | `pm10` | Integer (µg/m³) | Direct value |
| P25R | `p25r` | Integer (µg/m³) | Direct value |
| P10R | `p10r` | Integer (µg/m³) | Direct value |
| CO2 | `co2` | Integer (ppm) | Direct value |
| NO2 | `no2` | Integer (ppb) | Direct value |
| HCHO | `hcho` | Integer (ppb) | Direct value |
| Temperature | `tact` | Kelvin × 10 | `(value / 10) - 273.15` |
| Humidity | `hact` | Percentage | Direct value |

### Data Validation

All sensors include comprehensive validation to ensure data integrity and reliability.

#### Validation Rules

1. **Air Quality Sensors**: Reject values outside expected ranges to prevent sensor errors
   - PM2.5/PM10: 0-999 µg/m³
   - P25R/P10R: 0-999 µg/m³
   - CO2: 0-5000 ppm
   - NO2: 0-1000 ppb
   - HCHO: 0-1000 ppb

2. **Environmental Sensors**: Include unit conversion and decimal precision handling
   - Temperature: Kelvin × 10 format conversion with range validation
   - Humidity: 0-100% range validation

3. **Filter Sensors**: Validate percentage values (0-100%) and handle missing filter scenarios

#### Data Type Conversion

All sensor values are converted to appropriate Python data types with error handling:
```python
try:
    new_value = int(raw_value)
    if not (min_range <= new_value <= max_range):
        _LOGGER.warning("Invalid value: %s", new_value)
        new_value = None
except (ValueError, TypeError):
    _LOGGER.warning("Invalid format: %s", raw_value)
    new_value = None
```

### Error Handling

Robust error handling ensures graceful degradation when sensor data is unavailable.

#### Error Handling Strategies

1. **Missing Data**: Sensors report `None` (unavailable) when device data is missing
2. **Invalid Values**: Out-of-range or malformed data is rejected with debug logging
3. **Device Disconnection**: Sensors gracefully handle temporary device disconnections
4. **Type Errors**: Malformed data types are caught and logged without crashing

#### Fallback Behavior

When sensor data is unavailable:
- Entity state becomes `unavailable` in Home Assistant
- Previous valid values are retained until new data arrives
- Debug logging provides troubleshooting information
- No exceptions are raised to prevent integration failure

### Update Frequency

Different sensor types update at different frequencies based on data importance and change patterns.

#### Update Patterns

1. **Real-time Sensors**: Air quality, environmental, and WiFi sensors update with each device data refresh (typically every 30-60 seconds)
2. **Status Sensors**: Connection status updates immediately when status changes
3. **Filter Sensors**: Update with device data but change infrequently (only when filters are replaced or maintenance performed)

#### Coordinator Integration

All sensors use the `DysonDataUpdateCoordinator` for efficient data management:
- Single MQTT connection per device
- Coordinated updates for all entities
- Automatic retry on connection failure
- Debounced updates to prevent excessive API calls

### Entity Organization

Sensors are categorized to control visibility and organization in Home Assistant interfaces.

#### Entity Categories

1. **Primary Sensors**: Air quality and environmental sensors (no category - visible by default)
   - PM2.5, PM10, CO2, Temperature, Humidity

2. **Diagnostic Sensors**: Device status and technical sensors (`EntityCategory.DIAGNOSTIC`)
   - P25R, P10R, NO2, HCHO, WiFi Signal, Connection Status, Filter Types

#### Visibility Control

- Primary sensors appear in main Home Assistant sensor lists
- Diagnostic sensors may be hidden by default but accessible in device details
- Use entity category settings to control sensor visibility based on monitoring preferences
- Filter sensors appear in maintenance dashboards

### Device Class Support

Sensors use appropriate Home Assistant device classes for proper integration:

| Sensor | Device Class | Benefits |
|--------|-------------|----------|
| PM2.5 | `SensorDeviceClass.PM25` | Proper unit handling, dashboard integration |
| PM10 | `SensorDeviceClass.PM10` | Proper unit handling, dashboard integration |
| CO2 | `SensorDeviceClass.CO2` | Proper unit handling, air quality tracking |
| NO2 | `SensorDeviceClass.NITROGEN_DIOXIDE` | Proper unit handling, pollution tracking |
| Temperature | `SensorDeviceClass.TEMPERATURE` | Automatic unit conversion, climate integration |
| Humidity | `SensorDeviceClass.HUMIDITY` | Climate integration, comfort tracking |
| WiFi | `SensorDeviceClass.SIGNAL_STRENGTH` | Network monitoring, connectivity tracking |

Device classes ensure proper handling by Home Assistant core systems, including automatic unit conversions, dashboard presentations, and integration with other climate and air quality systems.
