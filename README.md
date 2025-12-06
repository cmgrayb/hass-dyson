# Dyson Integration for Home Assistant

<p align="center">
  <img src="https://raw.githubusercontent.com/cmgrayb/hass-dyson/main/image_assets/logo.png" alt="Dyson Logo" width="400"/>
</p>


<!-- Badge Links -->

[releases-shield]: https://img.shields.io/github/release/cmgrayb/hass-dyson.svg?style=for-the-badge
[releases]: https://github.com/cmgrayb/hass-dyson/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/cmgrayb/hass-dyson.svg?style=for-the-badge
[commits]: https://github.com/cmgrayb/hass-dyson/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/cmgrayb/hass-dyson.svg?style=for-the-badge

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
[![Community Forum][forum-shield]][forum]

A core-ready Home Assistant integration for Dyson air purifiers, heaters, humidifiers, fans, and robotic vacuums featuring real-time MQTT communication and complete platform coverage.

## Current Features

### All Supported Devices

- **Cloud Discovery** - Automatic device detection via Dyson API
- **Manual Setup** - Sticker-based or network-isolated configuration for local devices
- **Capability Based Detection** - Automatic platform setup based on device features

### Environmental Cleaners (Fans/Purifiers)

- **Fan Control** - Speed adjustment (1-10), on/off, night mode
- **Air Quality Monitoring** - PM2.5, PM10, real-time sensor data
- **Smart Controls** - Auto mode, oscillation
- **Status Monitoring** - Connectivity, filter life, fault detection, firmware version
- **Precise Adjustments** - Timers, oscillation angles
- **Heating Support** - Climate Control with Heater mode, Heater Thermostat, and Fan Direction

## Planned Features

### Environmental Cleaners (Fans/Purifiers)

- **Humidifier Support** (e.g. PH models) - All functions should currently work except for humidification controls
- **Climate Control** - Climate Control with Humidistat
- **TBD** - Any features found which can be supported, will be

### Robotic Vacuums

- **Battery Sensor** - Monitor your 360 robotic vacuum's battery
- **TBD** - Any features found which can be supported, will be

### BLE Devices

- **lec Support** - We hope to someday support Dyson "lec" or BLE devices such as lights via BLE proxy devices

## Quick Start

### Installation

1. **Add Custom Repository to HACS**

   - Open **HACS** in Home Assistant
   - Go to **Settings** (three dots menu)
   - Select **Custom repositories**
   - Add repository URL: `https://github.com/cmgrayb/hass-dyson`
   - Select category: **Integration**
   - Click **Add**

2. **Install Integration**
   - Search for "**Dyson**" in HACS
   - Click **Download**
   - Restart Home Assistant

### Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "**Dyson**"
3. Choose setup method:
   - **Cloud Discovery** - Enter Dyson account credentials
   - **Manual Setup** - Enter device details from sticker or information gained through the Get Cloud Devices Action, or external tooling such as libdyson-rest or opendyson

## Configuration

### Cloud Account Configuration (**Recommended**)

When selecting **Cloud Discovery**, you'll be guided through the following steps:

#### **Step 1: Account Credentials**

- **Email**: Your Dyson account email address
- **Password**: Your Dyson account password
- **Country**: Verify your country and culture (affects API region and localization)

#### **Step 2: Device Discovery**

The integration will:

- Connect to Dyson's cloud API using your credentials
- Prompt the user for configuration preferences
- Extract device capabilities and configuration from cloud data
- If configured to do so (default), automatically discover and add all supportable devices linked to your account
- Alternatively, prompt to add a list of found devices for selection
- If polling and auto-add are both deselected, the cloud account may be used for fetching account and device data via Home Assistant Actions only.  For more information, see: [Actions](docs/ACTIONS.md)

#### **What You'll See**

- **Device List**: All Dyson devices registered to your account
- **Device Info**: Model, serial number, and current online status
- **Automatic Setup**: Each device configured with appropriate sensors and controls

#### **Expected Entities Per Device**

Based on your device capabilities and category, you'll automatically get:

**All Devices (Basic Support):**

- Basic binary sensors (online/offline, faults)

**WiFi-Enabled Devices (EC/Robot Categories):**

- Connection status sensor (Local/Cloud/Disconnected)
- Reconnect button to attempt to re-establish preferred connectivity
- WiFi signal strength sensor (diagnostic)
- Temperature sensor
- Humidity sensor
- Carbon filter sensors
- HEPA filter sensors

**Air Quality Models (ExtendedAQ Capability):**

- PM2.5 air quality sensor
- PM10 air quality sensor
- HEPA filter life sensor (%)
- HEPA filter type sensor
- Carbon filter life sensor (%)
- Carbon filter type sensor
- VOC sensor
- NO2/NOx sensor
- CO2 sensor
- HCHO/Formaldehyde sensor

**Heating Models (Heating Capability):**

- Climate control platform
- Heating controls

### Future Support (Under Development):

**Humidifier models (Humidifier Capability):**

- Climate control platform
- Humidifier controls

**Robot Models:**

- Battery sensors
- Cleaning modes
- Dustbin status

> **See [Device Compatibility Matrix](docs/DEVICE_COMPATIBILITY.md) for complete entity breakdown by device type**

#### **Setup Time**

- **Initial connection**: 10-30 seconds
- **Device discovery**: 5-15 seconds per device
- **Entity creation**: Values may take a minute or two to show up after new device creation or boot

#### **Troubleshooting Cloud Setup**

- **Invalid credentials**: Verify email/password and account region
- **No devices found**: Ensure devices are registered in Dyson app
- **Connection timeout**: Check internet connection and Dyson API status
- **Partial device data**: Some devices may need additional setup time

### Manual/Sticker Setup (Advanced Use Case such as isolated network)

**Please note: some sensors (like Firmware version) will not work without access to the Cloud API**

Required information from device sticker, libdyson-rest, or opendyson:

- **Serial Number** (e.g., MOCK-SERIAL-TEST123)
- **Device Password** (from sticker)
- **MQTT Prefix** (e.g., 438M for Pure Cool models)
- **Device Type** (e.g., EC for air purifiers)

### YAML Configuration (Optional, **Not** Recommended)

```yaml
hass_dyson:
  devices:
    - serial_number: "MOCK-SERIAL-TEST123"
      discovery_method: "sticker"
      hostname: "192.168.1.100" # Optional: IP address
      credential: "your_device_password"
      device_type: "ec"
      mqtt_prefix: "438M"
      capabilities: ["AdvanceOscillationDay1", "Scheduling", "ExtendedAQ"]
```

## Documentation

### **Additional Information**

- **[Actions](docs/ACTIONS.md)** - Information on included Home Assistant Actions
- **[Controls](docs/CONTROLS.md)** - Information on included controls for devices
- **[Device Compatibility Matrix](docs/DEVICE_COMPATIBILITY.md)** - Complete breakdown of which entities are available for each device type and capability
- **[Device Management](docs/DEVICE_MANAGEMENT.md)** - Information on device discovery and configuration
- **[Entities](docs/ENTITIES.md)** - Information on entities to expect for a given device type
- **[Sensors](docs/SENSORS.md)** - Information on included sensors for devices
- **[Supported Devices](docs/SUPPORTED_DEVICES.md)** - Information on devices tested and known to be supported

### **Quick References**

- **[Setup Guide](docs/SETUP.md)** - Detailed installation and configuration instructions
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Troubleshooting Guide

### **For Developers**

- **[API Documentation](docs/API.md)** - Comprehensive API documentation with code examples and usage patterns for developers
- **[Developers Guide](docs/DEVELOPERS_GUIDE.md)** - See something you can help with?  This is where to start!

## Requirements

- **Home Assistant** 2025.12+
- **Python** 3.11+
- **Dependencies** (auto-installed):
  - `libdyson-rest>=0.8.2`
  - `paho-mqtt>=2.1.0`
  - `cryptography>=3.4.0`

## Acknowledgments

- **libshenxn** - For getting the Dyson community started with the original libdyson
- **dotvezz** - For maintaining the libdyson-wg working group, ha-dyson, and opendyson, the inspiration for this integration
- **libdyson-wg** - For maintaining excellent documentation and tooling without which this integration would not have been possible
- **paho-mqtt** - Reliable MQTT communication library
- **Home Assistant** - Amazing home automation platform
- **Dyson** - For making great products worth putting in the work for

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**⚠️ Disclaimer**: This is an unofficial integration not affiliated with Dyson Ltd. Use at your own risk.
