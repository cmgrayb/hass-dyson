# HASS-Dyson Sensors

## PM2.5 Sensor

### Description

The PM2.5 sensor monitors fine particulate matter with diameter ≤ 2.5 micrometers in the air, providing real-time air quality monitoring.

### Purpose

Track fine particulate matter concentration for health monitoring and air quality assessment.

### Technical Specifications

1. Entity ID: `sensor.{device_name}_pm25`
2. Unit: µg/m³ (micrograms per cubic meter)
3. Device Class: PM2.5
4. State Class: Measurement
5. Range: 0-999 µg/m³
6. Icon: mdi:air-filter
7. Availability: Devices with ExtendedAQ capability
8. Update Frequency: Real-time with device data updates

### Health Guidelines

Fine particulate matter can penetrate deep into lungs and cause health issues. Values above 25 µg/m³ are considered unhealthy for sensitive groups.

## PM10 Sensor

### Description

The PM10 sensor monitors coarse particulate matter with diameter ≤ 10 micrometers in the air, including dust, pollen, and mold spores.

### Purpose

Track coarse particulate matter concentration for comprehensive air quality monitoring.

### Technical Specifications

1. Entity ID: `sensor.{device_name}_pm10`
2. Unit: µg/m³ (micrograms per cubic meter)
3. Device Class: PM10
4. State Class: Measurement
5. Range: 0-999 µg/m³
6. Icon: mdi:air-filter
7. Availability: Devices with ExtendedAQ capability
8. Update Frequency: Real-time with device data updates

### Health Guidelines

Coarse particulate matter including dust, pollen, and mold spores. Values above 50 µg/m³ are considered unhealthy for sensitive groups.

## VOC Sensor

### Description

The VOC sensor monitors volatile organic compounds concentration in the air, detecting chemical compounds from household products and materials.

### Purpose

Monitor chemical air quality through volatile organic compound detection.

### Technical Specifications

1. Entity ID: `sensor.{device_name}_voc`
2. Unit: ppb (parts per billion)
3. Device Class: Volatile Organic Compounds Parts
4. State Class: Measurement
5. Range: 0-500 ppb
6. Icon: mdi:chemical-weapon
7. Entity Category: Diagnostic
8. Availability: Devices with VOC capability
9. Update Frequency: Real-time with device data updates

### Chemical Sources

Chemical compounds that evaporate at room temperature, including cleaning products, paints, and other household chemicals. Higher values indicate poor indoor air quality.

## NO2 Sensor

### Description

The NO2 sensor monitors nitrogen dioxide concentration in the air, detecting gases from combustion processes.

### Purpose

Monitor nitrogen dioxide levels for comprehensive gas pollution tracking.

### Technical Specifications

1. Entity ID: `sensor.{device_name}_no2`
2. Unit: ppb (parts per billion)
3. Device Class: Nitrogen Dioxide
4. State Class: Measurement
5. Range: 0-200 ppb
6. Icon: mdi:molecule
7. Entity Category: Diagnostic
8. Availability: Devices with VOC capability
9. Update Frequency: Real-time with device data updates

### Pollution Sources

Gas often produced by combustion processes. Common sources include vehicle emissions, gas stoves, and heating systems. Can cause respiratory irritation at elevated levels.

## Formaldehyde Sensor

### Description

The formaldehyde sensor monitors formaldehyde concentration in the air, detecting emissions from furniture and building materials.

### Purpose

Monitor formaldehyde levels for comprehensive chemical air quality assessment.

### Technical Specifications

1. Entity ID: `sensor.{device_name}_formaldehyde`
2. Unit: ppb (parts per billion)
3. Device Class: Volatile Organic Compounds Parts
4. State Class: Measurement
5. Range: 0-100 ppb
6. Icon: mdi:chemical-weapon
7. Entity Category: Diagnostic
8. Availability: Devices with Formaldehyde capability
9. Update Frequency: Real-time with device data updates

### Health Guidelines

Colorless gas commonly found in furniture, carpets, and building materials. Can cause eye, nose, and throat irritation. Values above 10 ppb may cause discomfort.

## Temperature Sensor

### Description

The temperature sensor measures ambient air temperature with automatic unit conversion support.

### Purpose

Monitor environmental temperature for climate control and comfort management.

### Technical Specifications

1. Entity ID: `sensor.{device_name}_temperature`
2. Unit: °C (degrees Celsius)
3. Device Class: Temperature
4. State Class: Measurement
5. Icon: Default temperature icon
6. Availability: Devices with heating capability
7. Update Frequency: Real-time with device data updates

### Unit System Support

Home Assistant automatically converts temperature display between Celsius and Fahrenheit based on system configuration. The sensor reports in Celsius natively but displays in Fahrenheit for imperial unit systems.

### Data Conversion

Raw Dyson data is in Kelvin × 10 format. The integration performs conversion: `(raw_value / 10) - 273.15`.

## Humidity Sensor

### Description

The humidity sensor measures relative humidity in the air for environmental monitoring.

### Purpose

Monitor humidity levels for comfort and health management.

### Technical Specifications

1. Entity ID: `sensor.{device_name}_humidity`
2. Unit: % (percentage)
3. Device Class: Humidity
4. State Class: Measurement
5. Icon: Default humidity icon
6. Availability: Devices with humidifier capability
7. Update Frequency: Real-time with device data updates

### Availability Notes

Currently available on humidifier-capable devices but may be expanded to other device types in future updates. Availability is limited while exact humidifier capability detection is being refined.

## WiFi Signal Sensor

### Description

The WiFi signal sensor monitors the device's wireless network signal strength for connectivity assessment.

### Purpose

Monitor network connectivity strength for troubleshooting and performance optimization.

### Technical Specifications

1. Entity ID: `sensor.{device_name}_wifi`
2. Unit: dBm (decibels relative to milliwatt)
3. Device Class: Signal Strength
4. State Class: Measurement
5. Icon: mdi:wifi
6. Entity Category: Diagnostic
7. Availability: EC and robot category devices
8. Update Frequency: Real-time with device data updates

### Signal Strength Guidelines

Signal strength values closer to 0 indicate stronger signals. Examples: -30 dBm is excellent, -70 dBm is good, -90 dBm is poor.

## Connection Status Sensor

### Description

The connection status sensor shows the current connectivity state of the device to cloud services.

### Purpose

Monitor device connectivity for troubleshooting network and service issues.

### Technical Specifications

1. Entity ID: `sensor.{device_name}_connection_status`
2. Unit: None (text status)
3. Device Class: None
4. State Class: None
5. Icon: mdi:connection
6. Entity Category: Diagnostic
7. Availability: EC and robot category devices
8. Update Frequency: Real-time with connection changes

### Status Values

Reports whether the device is "Connected" or "Disconnected" from the cloud service. Useful for monitoring device connectivity issues.

## HEPA Filter Life Sensor

### Description

The HEPA filter life sensor monitors the remaining operational life of the HEPA filter as a percentage.

### Purpose

Track filter replacement timing for optimal air filtration performance.

### Technical Specifications

1. Entity ID: `sensor.{device_name}_hepa_filter_life`
2. Unit: % (percentage)
3. Device Class: None
4. State Class: Measurement
5. Range: 0-100%
6. Icon: mdi:air-filter
7. Availability: Devices with ExtendedAQ capability
8. Update Frequency: Real-time with device data updates

### Maintenance Guidelines

Shows percentage of filter life remaining. When this reaches 0%, filter replacement is required. Device typically alerts users when filter life is low.

## HEPA Filter Type Sensor

### Description

The HEPA filter type sensor displays the specific model of HEPA filter currently installed in the device.

### Purpose

Track filter compatibility and ensure correct replacement filter selection.

### Technical Specifications

1. Entity ID: `sensor.{device_name}_hepa_filter_type`
2. Unit: None (text description)
3. Device Class: None
4. State Class: None
5. Icon: mdi:air-filter
6. Entity Category: Diagnostic
7. Availability: Devices with ExtendedAQ capability
8. Update Frequency: On receipt of status update from device

### Filter Status Values

Shows specific HEPA filter model installed. Returns "Not Installed" if no filter is detected. Useful for tracking filter replacements and ensuring correct filter types.

## Carbon Filter Life Sensor

### Description

The carbon filter life sensor monitors the remaining operational life of the carbon filter for odor and gas absorption.

### Purpose

Track carbon filter replacement timing for optimal chemical filtration performance.

### Technical Specifications

1. Entity ID: `sensor.{device_name}_carbon_filter_life`
2. Unit: % (percentage)
3. Device Class: None
4. State Class: Measurement
5. Range: 0-100%
6. Icon: mdi:air-filter
7. Availability: Devices with Formaldehyde capability
8. Update Frequency: Real-time with device data updates

### Maintenance Guidelines

Shows percentage of carbon filter life remaining. Carbon filters absorb odors and gases. When this reaches 0%, filter replacement is required.

### Availability Notes

Currently only available on devices with confirmed formaldehyde sensing capability.

## Carbon Filter Type Sensor

### Description

The carbon filter type sensor displays the specific model of carbon filter currently installed in the device.

### Purpose

Track carbon filter compatibility and ensure correct replacement filter selection.

### Technical Specifications

1. Entity ID: `sensor.{device_name}_carbon_filter_type`
2. Unit: None (text description)
3. Device Class: None
4. State Class: None
5. Icon: mdi:air-filter
6. Entity Category: Diagnostic
7. Availability: Devices with Formaldehyde capability
8. Update Frequency: On receipt of status update from device

### Filter Status Values

Shows specific carbon filter model installed. Returns "Not Installed" if no filter is detected, or "Unknown" if the type cannot be determined.

### Availability Notes

Currently only available on devices with confirmed formaldehyde sensing capability.

## Device Capability Requirements

## Air Quality Sensors

### Description

Air quality sensors require specific device capabilities to function properly.

### Capability Requirements

| Sensor Category | Required Capability | Compatible Devices |
|----------------|-------------------|-------------------|
| PM2.5 & PM10 | ExtendedAQ | Air purifiers with advanced air quality monitoring |
| VOC & NO2 | VOC | Air purifiers with chemical detection |
| Formaldehyde | Formaldehyde | Air purifiers with formaldehyde sensing |

## Environmental Sensors

### Description

Environmental sensors provide temperature and humidity monitoring based on device capabilities.

### Capability Requirements

| Sensor Category | Required Capability | Compatible Devices |
|----------------|-------------------|-------------------|
| Temperature | Heating | Heater fans and heating-capable devices |
| Humidity | Humidifier | Humidifier devices |

## Device Status Sensors

### Description

Device status sensors monitor connectivity and operational status.

### Capability Requirements

| Sensor Category | Required Capability | Compatible Devices |
|----------------|-------------------|-------------------|
| WiFi Status | EC or Robot category | Connected devices with WiFi monitoring |

## Filter Monitoring Sensors

### Description

Filter sensors track filter life and type information for maintenance scheduling.

### Capability Requirements

| Sensor Category | Required Capability | Compatible Devices |
|----------------|-------------------|-------------------|
| HEPA Filters | ExtendedAQ | Air purifiers with replaceable HEPA filters |
| Carbon Filters | Formaldehyde | Air purifiers with carbon filtration |

## Technical Implementation Details

## Data Validation

### Description

All sensors include comprehensive validation to ensure data integrity and reliability.

### Validation Rules

1. Air Quality Sensors: Reject values outside expected ranges to prevent sensor errors
2. Environmental Sensors: Include unit conversion and decimal precision handling
3. Filter Sensors: Validate percentage values (0-100%) and handle missing filter scenarios

## Error Handling

### Description

Robust error handling ensures graceful degradation when sensor data is unavailable.

### Error Handling Strategies

1. Missing Data: Sensors report `None` (unavailable) when device data is missing
2. Invalid Values: Out-of-range or malformed data is rejected with debug logging
3. Device Disconnection: Sensors gracefully handle temporary device disconnections

## Update Frequency

### Description

Different sensor types update at different frequencies based on data importance and change patterns.

### Update Patterns

1. Real-time Sensors: Air quality, environmental, and WiFi sensors update with each device data refresh
2. Status Sensors: Connection status updates immediately when status changes
3. Filter Sensors: Update with device data but change infrequently (only when filters are replaced)

## Sensor Categories

### Description

Sensors are categorized to control visibility and organization in Home Assistant interfaces.

### Category Types

1. Primary Sensors: Air quality and environmental sensors appear in main sensor lists
2. Diagnostic Sensors: Device status and filter type sensors are categorized as diagnostic and may be hidden by default

### Visibility Control

Use entity category settings to control sensor visibility based on monitoring preferences and interface requirements.
