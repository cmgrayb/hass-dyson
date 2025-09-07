# Dyson Integration for Home Assistant

<p align="center">
  <img src="https://raw.githubusercontent.com/cmgrayb/ha-dyson-alt/main/dyson-logo-social.png" alt="Dyson Logo" width="400"/>
</p>

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
[![Community Forum][forum-shield]][forum]

A core-ready Home Assistant integration for Dyson air purifiers, heaters, humidifiers, fans, and robotic vacuums featuring real-time MQTT communication and complete platform coverage.

## ✨ Current Features

### Environmental Cleaners (Fans/Purifiers)

- **Fan Control** - Speed adjustment (1-10), on/off, night mode
- **Air Quality Monitoring** - PM2.5, PM10, real-time sensor data
- **Smart Controls** - Auto mode, oscillation
- **Status Monitoring** - Connectivity, filter life, fault detection
- **Precise Adjustments** - Timers, oscillation angles

### Advanced Configuration

- **Dynamic MQTT Prefix** - Supports all Dyson models with local MQTT broker or Cloud connection
- **Cloud Discovery** - Automatic device detection via Dyson API
- **Manual Setup** - Sticker-based configuration for local devices
- **Capability Detection** - Automatic platform setup based on device features

## 🌟 Planned Features

### Environmental Cleaners (Fans/Purifiers)

- **Heating** (HP models)
- **Climate Control** - Full HVAC interface for heating models

### Robotic Vacuums

- **Battery Sensor**

### BLE Devices

- **lec Support** - We hope to someday support Dyson "lec" or BLE devices such as lights via BLE proxy devices

## 🚀 Quick Start

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
   - **Manual Setup** - Enter device details from sticker or information gained through tooling such as libdyson-rest or opendyson

## 📱 Supported Entities

### **Fan Platform**

- Primary fan control with speed adjustment (1-10)
- Night mode for quiet operation
- Real-time status updates

### **Sensors**

- **PM2.5 Sensor** - Fine particulate matter (µg/m³)
- **PM10 Sensor** - Coarse particulate matter (µg/m³)
- **WiFi RSSI** - Connection strength monitoring
- **HEPA Filter Life** - HEPA filter remaining life (%)
- **Carbon Filter Life** - Carbon filter remaining life (%)

### **Binary Sensors**

- **Connectivity** - Online/offline status
- **Filter Replacement** - Alert when any filter needs changing
- **Individual Fault Sensors** - Dedicated sensors for each fault type:
  - **Air Quality Sensor Fault** - AQS malfunction detection
  - **Filter Fault** - General filter issues
  - **HEPA Filter Fault** - HEPA filter specific problems
  - **Carbon Filter Fault** - Carbon filter issues
  - **Motor Fault** - Fan motor problems and stalls
  - **Temperature Sensor Fault** - Temperature monitoring issues
  - **Humidity Sensor Fault** - Humidity measurement problems
  - **Power Supply Fault** - Electrical and power issues
  - **WiFi Connection Fault** - Connectivity problems
  - **System Fault** - General device malfunctions
  - **Brush Fault** - Brush blockages and wear (vacuum models)
  - **Dustbin Fault** - Bin full/missing alerts (vacuum models)

### **Controls**

- **Speed Control** - Fan Speed in 10% increments (1-10)
- **Sleep Timer** - Auto-off timer (0-540 minutes)
- **Mode Selection** - Auto/Manual operation
- **Oscillation** - Enable/disable with comprehensive angle control

## 🔧 Configuration

### Cloud Account Configuration (**Recommended**)

When selecting **Cloud Discovery**, you'll be guided through the following steps:

#### **Step 1: Account Credentials**

- **Email**: Your Dyson account email address
- **Password**: Your Dyson account password
- **Country**: Select your country (affects API region)

#### **Step 2: Device Discovery**

The integration will:

- Connect to Dyson's cloud API using your credentials
- Automatically discover all devices linked to your account
- Extract device capabilities and configuration from cloud data
- Display a list of found devices for selection

#### **What You'll See**

- **Device List**: All Dyson devices registered to your account
- **Device Info**: Model, serial number, and current online status
- **Automatic Setup**: Each device configured with appropriate sensors and controls

#### **Expected Entities Per Device**

Based on your device capabilities and category, you'll automatically get:

**All Devices (Basic Support):**

- Basic binary sensors (online/offline, night mode, auto mode)

**WiFi-Enabled Devices (EC/Robot Categories):**

- Connection status sensor (Local/Cloud/Disconnected)
- WiFi signal strength sensor (diagnostic)

**Air Quality Models (ExtendedAQ Capability):**

- PM2.5 air quality sensor
- PM10 air quality sensor
- HEPA filter life sensor (%)
- HEPA filter type sensor

### Future Support (Under Development):

**Heating Models (Heating Capability):**

- Temperature sensor
- Climate control platform
- Heating switch control

**Formaldehyde/VOC models (Carbon Filter Models):**

- Carbon filter sensors
- VOC sensor
- NO2 sensor
- Formaldehyde sensor

**Humidifier models:**

- Humidity sensors

**Robot Models:**

- Battery sensors

> 📖 **See [Device Compatibility Matrix](docs/DEVICE_COMPATIBILITY.md) for complete entity breakdown by device type**

**Future Support (Under Development):**

- **Carbon Filter Sensors**: Life and type monitoring (pending Formaldehyde capability identification)
- **Humidity Controls**: Sensor and controls (pending Humidifier capability identification)
- **Robot-Specific Features**: Battery monitoring, cleaning modes, dustbin status

**Troubleshooting Missing Entities:**
If expected sensors are missing, see our [Entity Troubleshooting Guide](docs/TROUBLESHOOTING_ENTITIES.md)

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
hass-dyson:
  devices:
    - serial_number: "MOCK-SERIAL-TEST123"
      discovery_method: "sticker"
      hostname: "192.168.1.100" # Optional: IP address
      credential: "your_device_password"
      device_type: "ec"
      mqtt_prefix: "438M"
      capabilities: ["AdvanceOscillationDay1", "Scheduling", "ExtendedAQ"]
```

## ⚙️ Device Management

The integration provides comprehensive device management options through the **Configure** button in Home Assistant's Devices & Services section.

### **Account-Level Management**

- **🔄 Reload All Devices** - Refresh connection and state for all devices
- **⚙️ Set Default Connection** - Configure default connection method for all devices

### **Individual Device Management**

- **⚙️ Configure**: Device-specific connection settings only
- **🔄 Reload**: Native Home Assistant button (top of device page)
- **🗑️ Delete**: Native Home Assistant button (device menu)

### **Connection Type Hierarchy**

1. **Device Override** - Takes priority if set
2. **Account Default** - Used when no device override
3. **System Default** - Final fallback (`local_cloud_fallback`)

### **How to Access**

- **Account**: Configure button on main integration entry
- **Device**: Native HA controls + Configure button for connection settings

### **Device Status Indicators**

- **✅ Active** - Device is currently set up and running
- **❌ Inactive** - Device exists in account but not currently active

> 📖 **See [DEVICE_MANAGEMENT.md](DEVICE_MANAGEMENT.md) for detailed documentation**

## 🏠 Device Support

### **Tested Models**

- ✅ **438 Series** - Pure Cool Air Purifiers (verified with real device)
- ✅ **475 Series** - Hot+Cool models (mocked)
- ✅ **527 Series** - V10/V11 models (mocked)

### **Supported Features by Model**

| Feature     | 438M | 475 | 527 | Notes           |
| ----------- | ---- | --- | --- | --------------- |
| Fan Control | ✅   | ✅  | ✅  | Speed 1-10      |
| Air Quality | ✅   | ✅  | ✅  | PM2.5, PM10     |
| Auto Mode   | ✅   | ✅  | ✅  | Smart response  |
| Oscillation | ✅   | ✅  | ❌  | Angle control   |
| Heating     | ❌   | ✅  | ❌  | HP models only  |
| Night Mode  | ✅   | ✅  | ✅  | Quiet operation |
| Scheduling  | ✅   | ✅  | ✅  | Sleep timer     |

## 🔍 Troubleshooting

### **Connection Issues**

```bash
# Check device network connectivity
ping 192.168.1.100  # Your device IP

# Verify MQTT prefix in logs
grep "MQTT prefix" /config/home-assistant.log
```

### **Device Not Found**

1. Verify device is on same network as Home Assistant
2. Check serial number from device sticker
3. Ensure device password is correct
4. Try manual IP address in hostname field

### **No Data Updates**

1. Check device MQTT topics in logs
2. Verify paho-mqtt dependency installed
3. Restart integration from UI
4. Check firewall settings for MQTT traffic

### **Debug Logging**

```yaml
# In configuration.yaml
logger:
  logs:
    custom_components.hass-dyson: debug
```

## 📚 Documentation

### **Comprehensive Guides**

- **[Device Compatibility Matrix](docs/DEVICE_COMPATIBILITY.md)** - Complete breakdown of which entities are available for each device type and capability
- **[Entity Troubleshooting Guide](docs/TROUBLESHOOTING_ENTITIES.md)** - Resolve missing or unexpected sensors and controls
- **[API Documentation](docs/API.md)** - Technical details about the Dyson API integration
- **[Security Guide](docs/SECURITY.md)** - Security considerations and best practices
- **[Live Testing Guide](docs/LIVE_TESTING_GUIDE.md)** - How to test with real Dyson devices

### **Quick References**

- **[Setup Guide](docs/SETUP.md)** - Detailed installation and configuration instructions
- **[Testing Guide](docs/TESTING_GUIDE.md)** - How to run tests and validate functionality
- **[Implementation Summary](docs/IMPLEMENTATION_SUMMARY.md)** - Technical architecture overview

## 🛠️ Development

### **Quick Start with DevContainer**

The easiest way to get started with development is using the provided devcontainer:

1. **Prerequisites**: Install VS Code with the "Dev Containers" extension
2. **Open Project**: Open the repository in VS Code
3. **Reopen in Container**: Press `Ctrl+Shift+P` → "Dev Containers: Reopen in Container"
4. **Start Developing**: All dependencies, tools, and Home Assistant are pre-installed!

The devcontainer includes:

- **Home Assistant Core** with all dependencies
- **Development Tools**: Black, Flake8, isort, mypy, pytest
- **MQTT Broker**: Local Mosquitto for testing
- **VS Code Extensions**: Python tools and GitHub Copilot
- **Pre-configured Settings**: Optimized for HA development

See [`.devcontainer/README.md`](.devcontainer/README.md) for detailed documentation.

### **Manual Development Setup**

If you prefer local development:

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install development dependencies
pip install -r requirements-dev.txt
pip install -e .

# Install Home Assistant for testing
pip install homeassistant
```

### **Architecture**

```
Config Flow → Coordinator → Device Wrapper → MQTT Client
     ↓            ↓              ↓
Platform Setup → Data Updates → Real Device
```

### **Project Structure**

```
custom_components/hass_dyson/
├── __init__.py          # Integration setup
├── config_flow.py       # Setup wizard
├── coordinator.py       # Data coordination
├── device.py           # MQTT device wrapper
├── const.py            # Constants
├── manifest.json       # Metadata
├── fan.py              # Fan platform
├── sensor.py           # Sensor platform
├── binary_sensor.py    # Binary sensor platform
├── button.py           # Button platform
├── number.py           # Number platform
├── select.py           # Select platform
├── switch.py           # Switch platform
└── climate.py          # Climate platform
```

### **Contributing**

1. Fork the repository
2. **Recommended**: Use the devcontainer for consistent development environment
   - Open in VS Code with Dev Containers extension
   - All tools and dependencies are pre-configured
3. Create feature branch (`git checkout -b feature/amazing-feature`)
4. Make your changes following the code quality standards:

   ```bash
   # Format code
   python -m black .

   # Lint code
   python -m flake8 .

   # Sort imports
   python -m isort .

   # Run tests
   python -m pytest
   ```

5. Commit changes (`git commit -am 'Add amazing feature'`)
6. Push branch (`git push origin feature/amazing-feature`)
7. Open Pull Request

## 📋 Requirements

- **Home Assistant** 2025.8+
- **Python** 3.11+
- **Dependencies** (auto-installed):
  - `libdyson-rest>=0.4.1`
  - `paho-mqtt>=2.1.0`
  - `cryptography>=3.4.0`

## 🙏 Acknowledgments

- **libshenxn** - For getting the Dyson community started with the original libdyson
- **dotvezz** - For maintaining the libdyson-wg working group, ha-dyson, and opendyson, the inspiration for this integration
- **libdyson-wg** - For maintaining excellent documentation and tooling without which this integration would not have been possible
- **paho-mqtt** - Reliable MQTT communication library
- **Home Assistant** - Amazing home automation platform
- **Dyson** - For making great products worth putting in the work for

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<!-- Badge Links -->

[releases-shield]: https://img.shields.io/github/release/cmgrayb/ha-dyson-alt.svg?style=for-the-badge
[releases]: https://github.com/cmgrayb/ha-dyson-alt/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/cmgrayb/ha-dyson-alt.svg?style=for-the-badge
[commits]: https://github.com/cmgrayb/ha-dyson-alt/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/cmgrayb/ha-dyson-alt.svg?style=for-the-badge

---

**⚠️ Disclaimer**: This is an unofficial integration not affiliated with Dyson Ltd. Use at your own risk.
