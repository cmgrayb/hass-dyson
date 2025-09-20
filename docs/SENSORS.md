# Sensors

This document provides comprehensive information about all sensors available in the Dyson Home Assistant integration. Sensors are automatically configured based on your device's capabilities and provide real-time monitoring of air quality, environmental conditions, and device status.

## Overview

The integration supports multiple categories of sensors:

- **Air Quality Sensors**: PM2.5, PM10, VOC, NO2, and formaldehyde monitoring
- **Environmental Sensors**: Temperature and humidity measurement
- **Device Status Sensors**: WiFi signal strength and connection status
- **Filter Sensors**: Filter life monitoring and type identification

Sensors are automatically added based on your device's capabilities. Not all sensors are available on all devices.

## Air Quality Sensors

### PM2.5 Sensor

**Entity ID**: `sensor.{device_name}_pm25`

Monitors particulate matter with diameter ≤ 2.5 micrometers in the air.

- **Unit**: µg/m³ (micrograms per cubic meter)
- **Device Class**: PM2.5
- **State Class**: Measurement
- **Range**: 0-999 µg/m³
- **Icon**: mdi:air-filter
- **Availability**: Devices with ExtendedAQ capability
- **Update Frequency**: Real-time with device data updates

**Description**: Fine particulate matter that can penetrate deep into lungs and cause health issues. Values above 25 µg/m³ are considered unhealthy for sensitive groups.

### PM10 Sensor

**Entity ID**: `sensor.{device_name}_pm10`

Monitors particulate matter with diameter ≤ 10 micrometers in the air.

- **Unit**: µg/m³ (micrograms per cubic meter)
- **Device Class**: PM10
- **State Class**: Measurement
- **Range**: 0-999 µg/m³
- **Icon**: mdi:air-filter
- **Availability**: Devices with ExtendedAQ capability
- **Update Frequency**: Real-time with device data updates

**Description**: Coarse particulate matter including dust, pollen, and mold spores. Values above 50 µg/m³ are considered unhealthy for sensitive groups.

### VOC Sensor

**Entity ID**: `sensor.{device_name}_voc`

Monitors volatile organic compounds concentration in the air.

- **Unit**: ppb (parts per billion)
- **Device Class**: Volatile Organic Compounds Parts
- **State Class**: Measurement
- **Range**: 0-500 ppb
- **Icon**: mdi:chemical-weapon
- **Entity Category**: Diagnostic
- **Availability**: Devices with VOC capability
- **Update Frequency**: Real-time with device data updates

**Description**: Chemical compounds that evaporate at room temperature, including cleaning products, paints, and other household chemicals. Higher values indicate poor indoor air quality.

### NO2 Sensor

**Entity ID**: `sensor.{device_name}_no2`

Monitors nitrogen dioxide concentration in the air.

- **Unit**: ppb (parts per billion)
- **Device Class**: Nitrogen Dioxide
- **State Class**: Measurement
- **Range**: 0-200 ppb
- **Icon**: mdi:molecule
- **Entity Category**: Diagnostic
- **Availability**: Devices with VOC capability
- **Update Frequency**: Real-time with device data updates

**Description**: A gas often produced by combustion processes. Common sources include vehicle emissions, gas stoves, and heating systems. Can cause respiratory irritation at elevated levels.

### Formaldehyde Sensor

**Entity ID**: `sensor.{device_name}_formaldehyde`

Monitors formaldehyde concentration in the air.

- **Unit**: ppb (parts per billion)
- **Device Class**: Volatile Organic Compounds Parts
- **State Class**: Measurement
- **Range**: 0-100 ppb
- **Icon**: mdi:chemical-weapon
- **Entity Category**: Diagnostic
- **Availability**: Devices with Formaldehyde capability
- **Update Frequency**: Real-time with device data updates

**Description**: A colorless gas commonly found in furniture, carpets, and building materials. Can cause eye, nose, and throat irritation. Values above 10 ppb may cause discomfort.

## Environmental Sensors

### Temperature Sensor

**Entity ID**: `sensor.{device_name}_temperature`

Measures ambient air temperature.

- **Unit**: °C (degrees Celsius)
- **Device Class**: Temperature
- **State Class**: Measurement
- **Icon**: Default temperature icon
- **Availability**: Devices with heating capability
- **Update Frequency**: Real-time with device data updates

**Description**: Reports the current ambient temperature. The sensor automatically converts from Dyson's internal Kelvin format (multiplied by 10) to Celsius with one decimal place precision.

**Unit System Support**: Home Assistant automatically converts the temperature display between Celsius and Fahrenheit based on your system's configured unit system. The sensor always reports in Celsius natively, but will be displayed in Fahrenheit if your Home Assistant is configured to use imperial units.

**Technical Details**: Raw Dyson data is in Kelvin × 10 format. The integration performs the conversion: `(raw_value / 10) - 273.15`.

### Humidity Sensor

**Entity ID**: `sensor.{device_name}_humidity`

Measures relative humidity in the air.

- **Unit**: % (percentage)
- **Device Class**: Humidity
- **State Class**: Measurement
- **Icon**: Default humidity icon
- **Availability**: Devices with humidifier capability
- **Update Frequency**: Real-time with device data updates

**Description**: Reports the current relative humidity percentage. This sensor is currently available on humidifier-capable devices but may be expanded to other device types in future updates.

**Note**: Availability is limited while the exact humidifier capability detection is being refined.

## Device Status Sensors

### WiFi Signal Sensor

**Entity ID**: `sensor.{device_name}_wifi`

Monitors the device's WiFi signal strength.

- **Unit**: dBm (decibels relative to milliwatt)
- **Device Class**: Signal Strength
- **State Class**: Measurement
- **Icon**: mdi:wifi
- **Entity Category**: Diagnostic
- **Availability**: EC and robot category devices
- **Update Frequency**: Real-time with device data updates

**Description**: Reports the WiFi signal strength in dBm. Values closer to 0 indicate stronger signals (e.g., -30 dBm is excellent, -70 dBm is good, -90 dBm is poor).

### Connection Status Sensor

**Entity ID**: `sensor.{device_name}_connection_status`

Shows the current connection status of the device.

- **Unit**: None (text status)
- **Device Class**: None
- **State Class**: None
- **Icon**: mdi:connection
- **Entity Category**: Diagnostic
- **Availability**: EC and robot category devices
- **Update Frequency**: Real-time with connection changes

**Description**: Reports whether the device is "Connected" or "Disconnected" from the cloud service. Useful for monitoring device connectivity issues.

## Filter Sensors

### HEPA Filter Life Sensor

**Entity ID**: `sensor.{device_name}_hepa_filter_life`

Monitors the remaining life of the HEPA filter.

- **Unit**: % (percentage)
- **Device Class**: None
- **State Class**: Measurement
- **Range**: 0-100%
- **Icon**: mdi:air-filter
- **Availability**: Devices with ExtendedAQ capability
- **Update Frequency**: Real-time with device data updates

**Description**: Shows the percentage of filter life remaining. When this reaches 0%, the filter needs replacement. The device typically alerts users when filter life is low.

### HEPA Filter Type Sensor

**Entity ID**: `sensor.{device_name}_hepa_filter_type`

Displays the type of HEPA filter installed.

- **Unit**: None (text description)
- **Device Class**: None
- **State Class**: None
- **Icon**: mdi:air-filter
- **Entity Category**: Diagnostic
- **Availability**: Devices with ExtendedAQ capability
- **Update Frequency**: On receipt of status update from device

**Description**: Shows the specific HEPA filter model installed. Returns "Not Installed" if no filter is detected. Useful for tracking filter replacements and ensuring correct filter types.

### Carbon Filter Life Sensor

**Entity ID**: `sensor.{device_name}_carbon_filter_life`

Monitors the remaining life of the carbon filter.

- **Unit**: % (percentage)
- **Device Class**: None
- **State Class**: Measurement
- **Range**: 0-100%
- **Icon**: mdi:air-filter
- **Availability**: Devices with Formaldehyde capability
- **Update Frequency**: Real-time with device data updates

**Description**: Shows the percentage of carbon filter life remaining. Carbon filters absorb odors and gases. When this reaches 0%, the filter needs replacement.

**Note**: Currently only available on devices with confirmed formaldehyde sensing capability.

### Carbon Filter Type Sensor

**Entity ID**: `sensor.{device_name}_carbon_filter_type`

Displays the type of carbon filter installed.

- **Unit**: None (text description)
- **Device Class**: None
- **State Class**: None
- **Icon**: mdi:air-filter
- **Entity Category**: Diagnostic
- **Availability**: Devices with Formaldehyde capability
- **Update Frequency**: On receipt of status update from device

**Description**: Shows the specific carbon filter model installed. Returns "Not Installed" if no filter is detected, or "Unknown" if the type cannot be determined.

**Note**: Currently only available on devices with confirmed formaldehyde sensing capability.

## Device Capability Matrix

| Sensor Category | Required Capability | Compatible Devices |
|----------------|-------------------|-------------------|
| PM2.5 & PM10 | ExtendedAQ | Air purifiers with advanced air quality monitoring |
| VOC & NO2 | VOC | Air purifiers with chemical detection |
| Formaldehyde | Formaldehyde | Air purifiers with formaldehyde sensing |
| Temperature | Heating | Heater fans and heating-capable devices |
| Humidity | Humidifier | Humidifier devices |
| WiFi Status | EC or Robot category | Connected devices with WiFi monitoring |
| HEPA Filters | ExtendedAQ | Air purifiers with replaceable HEPA filters |
| Carbon Filters | Formaldehyde | Air purifiers with carbon filtration |

## Technical Notes

### Data Validation

All sensors include validation to ensure reported values are within reasonable ranges:

- **Air Quality Sensors**: Reject values outside expected ranges to prevent sensor errors
- **Environmental Sensors**: Include unit conversion and decimal precision handling
- **Filter Sensors**: Validate percentage values (0-100%) and handle missing filter scenarios

### Error Handling

- **Missing Data**: Sensors report `None` (unavailable) when device data is missing
- **Invalid Values**: Out-of-range or malformed data is rejected with debug logging
- **Device Disconnection**: Sensors gracefully handle temporary device disconnections

### Update Frequency

- **Real-time Sensors**: Air quality, environmental, and WiFi sensors update with each device data refresh
- **Status Sensors**: Connection status updates immediately when status changes
- **Filter Sensors**: Update with device data but change infrequently (only when filters are replaced)

### Diagnostic vs. Primary Sensors

- **Primary Sensors**: Air quality and environmental sensors appear in main sensor lists
- **Diagnostic Sensors**: Device status and filter type sensors are categorized as diagnostic and may be hidden by default in some Home Assistant interfaces

Use the entity category settings to control sensor visibility based on your monitoring preferences.
