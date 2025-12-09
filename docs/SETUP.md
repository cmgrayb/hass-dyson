# Setup Guide - Dyson Integration

Complete setup instructions for integrating your Dyson devices with Home Assistant.

## Prerequisites

### **Home Assistant Requirements**
- Home Assistant Core 2025.12 or newer
- Custom components support enabled
- Network access to Dyson devices

### **Dyson Device Requirements**
- Dyson device connected to same network via WiFi as Home Assistant
- Dyson account credentials (for cloud discovery)
- OR Device sticker information available (for manual setup) on some older devices

## Installation Methods

### **Method 1: HACS (Recommended)**
1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click "Custom Repositories"
4. Add URL: `https://github.com/cmgrayb/ha-dyson-alt`
5. Category: "Integration"
6. Install "Dyson"
7. Restart Home Assistant

### **Method 2: Manual Installation**
1. Download integration files:
   ```bash
   git clone https://github.com/cmgrayb/ha-dyson-alt.git
   ```

2. Copy to Home Assistant:
   ```bash
   # Copy integration folder
   cp -r ha-dyson-alt/custom_components/hass_dyson /config/custom_components/
   ```

3. Restart Home Assistant

### **Method 3: Direct Download**
1. Download latest release from GitHub
2. Extract `custom_components/hass_dyson` folder
3. Place in `/config/custom_components/hass_dyson`
4. Restart Home Assistant

## Configuration Options

### **Option 1: Cloud Discovery (Easy)**

**When to use**:
- You have a Dyson account
   - You want automatic or semi-automatic device discovery
   - You need to query the API for device information for manual device configuration
   - You need to query the API for device information for a feature request or bug report

**Setup steps**:
1. Go to **Settings** → **Devices & Services**
2. Click **"Add Integration"**
3. Search for **"Dyson"**
4. Select **"Cloud Discovery"**
5. Enter your Dyson account email and password
6. Check your e-mail for the one time password - don't forget to check your junk filter!
7. Enter the one time password
8. Choose how you would like to interact with the cloud:
   1. `Poll for new devices`
      - When selected, the cloud account will inform Home Assistant of discovered devices
   2. `Automatically add discovered devices`
      - When selected, the cloud account will add all devices discovered by `Poll for new devices` using the information from the API without prompting the user for additional information
      - When deselected, the cloud account will prompt the user to configure all devices discovered by `Poll for new devices` using Home Assistant native "Add" prompt.
    3. If neither of the above is selected, the Cloud Account will only be used for Home Assistant Actions such as `Get Cloud Devices`.

**Pros**: Automatic setup, gets all device info from cloud
**Cons**: Requires internet, shares credentials with cloud

### **Option 2: Manual Setup (Advanced)**

**When to use**:
   - You want local-only control of your devices
   - You do NOT want Home Assistant to support firmware version or update functions

**Required information**:
- **Serial Number** (e.g., `MOCK-SERIAL-TEST123`)
- **Device Password** (8-character string on sticker)
- **Device MQTT Prefix** (e.g., 438, 438K, 527E, 358M)

**How to retrieve the required information**
- Option 1: Home Assistant Action
  - Follow the instructions above for setting up a Cloud connection
  - Uncheck all discovery boxes
  - Run Get Cloud Devices Action in Home Assistant with Sanitize OFF

- Option 2: Sticker
  - Older Dyson devices may have a sticker on them with the connection information

- Option 3: Third Party Tools
  - There are several third party tools which can retrieve the information such as option 1 for those uncomfortable with cloud account creation
    - libdyson-rest
      - Use the troubleshoot_account.py script in [cmgrayb/libdyson-rest](https://github.com/cmgrayb/libdyson-rest) to perform the action outside of Home Assistant
    - opendyson
      - Use [opendyson](https://github.com/libdyson-wg/opendyson) to retrieve the connection information

**Setup steps**:
1. Locate device sticker (usually on bottom or back)
2. Go to **Settings** → **Devices & Services** → **"Add Integration"**
3. Search for **"Dyson"**
4. Select **"Manual Setup"**
5. Enter required information:
   ```
   Serial Number: MOCK-SERIAL-TEST123
   Device Password: AAAABBBB
   Product Type: 438
   Device IP (optional): 192.168.1.100
   Device Name: Home Assistant name for the device
   Device Category:
      - `ec` for Environment Cleaners (air purifiers, fans with filters, heaters, and humidifiers)
      - `robot` for Robot Vacuums (self-piloting cleaning devices - limited support)
      - `vacuum` for Vacuum Cleaners (suction cleaning devices - limited support)
      - `flrc` for Floor Cleaners (mopping and floor cleaning devices - limited support)
   Device Capabilities (select all that apply):
      - `AdvanceOscillationDay1` for wide angle oscillation control (0-350 degrees)
      - `Scheduling` for timer and schedule controls (1-480 minutes)
      - `EnvironmentalData` for continuous monitoring and background data
      - `ExtendedAQ` for PM2.5/PM10 sensors and HEPA filter monitoring
      - `Heating` for heat mode, temperature control, and climate entity
      - `VOC` for chemical detection (VOC and NO2 sensors)
      - `Formaldehyde` for formaldehyde sensor and carbon filter monitoring
      - `Humidifier` for humidity control and humidity sensor
      - `ChangeWifi` for WiFi management and signal strength monitoring
   ```
6. Click **Submit**

### **Option 3: YAML Configuration (Advanced, Not Recommended)**

**When to use**: You want to pre-configure manual devices, such as in a testing lab

**Configuration example**:
```yaml
# configuration.yaml
hass-dyson:
  devices:
    - serial_number: "MOCK-SERIAL-TEST123"
      discovery_method: "sticker"
      hostname: "192.168.1.100"  # Optional
      credential: "AAAABBBB"     # Device password from sticker
      device_type: "438"
      device_category: "ec"      # Environment Cleaner
      mqtt_prefix: "438M"
      capabilities: ["AdvanceOscillationDay1", "ExtendedAQ", "Heating"]

    - serial_number: "475-US-JEN0000B"
      discovery_method: "sticker"
      hostname: "192.168.1.101"
      credential: "CCCCDDDD"
      device_type: "475"
      device_category: "ec"      # Environment Cleaner
      mqtt_prefix: "475"
      capabilities: ["VOC", "Heating", "Scheduling", "EnvironmentalData"]

    - serial_number: "527-US-ABC1234D"
      discovery_method: "sticker"
      hostname: "192.168.1.102"
      credential: "GGGGHHHHH"
      device_type: "527"
      device_category: "ec"      # Humidifier
      mqtt_prefix: "527"
      capabilities: ["Humidifier", "ExtendedAQ", "EnvironmentalData"]

    - serial_number: "RBV-001-US"
      discovery_method: "sticker"
      hostname: "192.168.1.103"
      credential: "EEEEFFFF"
      device_type: "360"
      device_category: "robot"   # Robot Vacuum
      mqtt_prefix: "360"
      capabilities: ["Scheduling", "ChangeWifi"]
```

## Device Information Guide

### **Finding Device Information**

**Device Sticker Location**:
- **Tower models**: Bottom of device
- **Desk models**: Back/bottom of device
- **Wall models**: Behind mounting bracket

**Sticker Information**:
```
Serial Number: MOCK-SERIAL-TEST123  ← Use this for device serial number
Device Password: AAAABBBB         ← Use this for device password
Model: 438                      ← Use this for device_type and MQTT prefix
```

**Auto-detection**: Integration automatically determines MQTT prefix from device type

### **Device Capabilities**
**Capabilities determine which features and sensors are available for your device. If using cloud discovery they are automatically detected, but for manual setup you will need to specify them.**

**Available Capabilities:**

- **`AdvanceOscillationDay1`** (Advanced Oscillation)
  - Wide angle oscillation control (0-350 degrees)
  - Precise angle adjustment via number controls
  - Upper and lower oscillation boundary settings
  - Enables: Advanced oscillation controls, angle sensors

- **`AdvanceOscillationDay0`** (Simplified Advanced Oscillation)
  - Fixed center point oscillation control (177° center)
  - Preset angle patterns: 15°, 40°, 70°, Custom
  - Simplified controls without center angle adjustment
  - Enables: Day0 oscillation select, lower/upper angle controls, span control

- **`Scheduling`** (Timer & Schedule Controls)
  - Sleep timer functionality (1-480 minutes)
  - Scheduled operation modes
  - Delayed start/stop functions
  - Enables: Timer controls, schedule selects

- **`EnvironmentalData`** (Continuous Monitoring)
  - Real-time environmental data collection
  - Background sensor monitoring
  - Automatic data reporting
  - Enables: Continuous monitoring switch

- **`ExtendedAQ`** (Extended Air Quality)
  - PM2.5 and PM10 particulate matter sensors
  - HEPA filter life monitoring and alerts
  - Advanced air quality metrics
  - Filter replacement tracking
  - Enables: PM2.5/PM10 sensors, HEPA filter sensors

- **`Heating`** (Heat Mode)
  - VIRTUAL CAPABILITY - This capability is not returned by the Dyson API and is made avaialable for manual device setup only
  - Hot air output functionality
  - Target temperature control (1-37°C)
  - Current temperature sensing
  - Heat mode selection
  - Enables: Climate entity, heating controls

- **`VOC`** (Chemical Detection)
  - VIRTUAL CAPABILITY - This capability is not returned by the Dyson API and is made avaialable for manual device setup only
  - Volatile Organic Compounds sensing
  - Nitrogen Dioxide (NO2/NOx) detection
  - Carbon Dioxide (CO2) detection
  - Chemical air quality monitoring
  - Real-time gas detection
  - Enables: VOC sensor, NO2 sensor

- **`Formaldehyde`** (Formaldehyde Detection)
  - VIRTUAL CAPABILITY - This capability is not returned by the Dyson API and is made avaialable for manual device setup only
  - Formaldehyde (HCHO) concentration monitoring
  - Enables: Formaldehyde sensor

- **`Humidifier`** (Humidity Control)
  - VIRTUAL CAPABILITY - This capability is not returned by the Dyson API and is made avaialable for manual device setup only
  - Air humidification functionality
  - Relative humidity sensing
  - Moisture level control
  - Water tank monitoring
  - Enables: Humidity sensor, humidifier controls

**Capability Detection:**
- **Cloud devices**: Capabilities automatically detected from Dyson API
- **Manual devices**: Must be specified during setup based on device features
- **Auto-detection**: Integration determines available controls based on capabilities

**Common Capability Combinations by Device Type:**

| Device Type | Typical Capabilities | Description |
|-------------|---------------------|-------------|
| **Air Purifier** | `ExtendedAQ`, `VOC`, `EnvironmentalData` | Basic air purification with sensors |
| **Heated Fan** | `ExtendedAQ`, `Heating`, `AdvanceOscillationDay1` | Air purifier with heating and oscillation |
| **Premium Model** | `ExtendedAQ`, `VOC`, `Formaldehyde`, `Heating`, `AdvanceOscillationDay1`, `Scheduling` | Full-featured device with all sensors |
| **Humidifier** | `Humidifier`, `ExtendedAQ`, `EnvironmentalData` | Humidification with air quality monitoring |
| **Robot Vacuum** | `Scheduling`, `ChangeWifi` | Basic vacuum with scheduling |
| **Basic Fan** | `AdvanceOscillationDay1`, `Scheduling` | Simple fan with timer and oscillation |

**Note**: Check your device's specifications or use cloud discovery to determine exact capabilities.

### **Device Categories**
**Choose the correct category for your device**:

- **`ec` (Environment Cleaner)** - Most common category
  - Air purifiers (Pure Cool, Pure Hot+Cool)
  - Fans with filters (Pure Cool Link, Cool)
  - Heater fans (Hot, Hot+Cool)
  - Humidifiers (Air Multiplier with humidification)
  - Examples: All tower fans, desk fans, and air treatment devices

- **`robot` (Robot Vacuum)** - Limited support
  - Self-piloting vacuum cleaners
  - 360 Eye series
  - Examples: 360 Eye, 360 Heurist
  - Note: Basic functionality only, help needed for full implementation

- **`vacuum` (Vacuum Cleaner)** - Limited support
  - Traditional handheld/stick vacuum cleaners
  - Cordless vacuum models
  - Examples: V6, V7, V8, V10, V11, V15 series
  - Note: Limited connectivity, most models not WiFi-enabled

- **`flrc` (Floor Cleaner)** - Limited support
  - Mopping and wet cleaning devices
  - Floor washing machines
  - Examples: V15s Detect Submarine (if it exists)
  - Note: Experimental support, few models available

## 🔍 Network Discovery

### **Finding Device IP Address**

**Method 1: mDNS Discovery (Automatic Discovery)**
1. This is the default discovery method when no IP address or hostname is entered

**Method 2: Router Admin Panel**
1. Access your router's web interface
2. Look for "Connected Devices" or "DHCP Clients"
3. Find device with hostname starting with "Dyson"

**Method 3: Network Scanner**
```bash
# Linux/Mac
nmap -sn 192.168.1.0/24 | grep -i dyson

# Windows
ping 192.168.1.100  # Try common IPs
```

### **Testing Device Connection**
```bash
# Test MQTT connection (port 1883)
# This command should result in an empty window without error if successful
telnet 192.168.1.100 1883

# Test device ping
ping 192.168.1.100
```

## ✅ Verification Steps

### **1. Integration Loaded**
- Go to **Settings** → **Devices & Services**
- Verify "Dyson" appears in list
- Status should show "Configured"

### **2. Device Connected**
- Device should show as "Online" in integration
- All entities should be populated with data
- No error messages in logs

### **3. Entity Verification**
**Expected entities varies by device category and capabilities**:
- 1 Fan (primary control with preset modes)
- 2-4 Sensors (PM2.5, PM10, RSSI, Filter)
- 2-3 Binary Sensors (connectivity, filter, faults)
- 1 Button (identify device)
- 3-5 Number controls (sleep timer, oscillation angles)
- 2-4 Select controls (fan mode, oscillation patterns, heating mode)
- 2-4 Switch controls (night mode, heating, continuous monitoring)
- 0-1 Climate (heating models only)

### **4. Functionality Test**
- Try turning fan on/off
- Adjust fan speed
- Check sensor readings update
- Test mode changes

## 🛠️ Troubleshooting Setup

### **Cloud Discovery Issues**
**Problem**: "Login failed" or "No devices found"
**Solutions**:
- Verify Dyson account email/password
- Ensure devices registered in Dyson app
- Try logging out/in from Dyson mobile app
- Check internet connectivity

**Problem**: "Connection timeout"
**Solutions**:
- Check Home Assistant internet access
- Verify firewall allows HTTPS traffic
- Try setup during off-peak hours

### **Manual Setup Issues**
**Problem**: "Device not found"
**Solutions**:
- Verify device IP address
- Check device is on same network
- Ensure device is powered on
- Try without specifying IP (use auto-discovery)

**Problem**: "Authentication failed"
**Solutions**:
- Double-check device password from sticker
- Ensure correct serial number format
- Verify device type matches model

**Problem**: "MQTT connection failed"
**Solutions**:
- Check device MQTT port (1883) not blocked
- Verify network allows device communication
- Try restarting device (power cycle)

### **Configuration Errors**
**Problem**: Integration won't load
**Solutions**:
- Check Home Assistant logs for errors
- Verify all required fields completed
- Ensure serial number format correct
- Try removing and re-adding integration

**Problem**: No entities created
**Solutions**:
- Verify device type detection
- Check capabilities auto-detection
- Enable debug logging to see discovery process
- Restart Home Assistant after setup

### **Network Issues**
**Problem**: Intermittent disconnection
**Solutions**:
- Check WiFi signal strength to device
- Verify router stability
- Consider static IP assignment
- Check for network congestion

**Problem**: Slow response times
**Solutions**:
- Move device closer to WiFi access point
- Check network bandwidth usage
- Verify Home Assistant system resources
- Consider ethernet connection if possible

## Getting Help

### **Before Requesting Support**
1. Enable debug logging:
   ```yaml
   logger:
       custom_components.dyson: debug
       libdyson_rest: debug
   ```

2. Restart Home Assistant

3. Reproduce the issue

4. Collect relevant log entries

### **Support Channels**
- **GitHub Issues**: [Report bugs/feature requests](https://github.com/cmgrayb/hass-dyson/issues)
- **Home Assistant Community**: Search for "Dyson"
- **Documentation**: This guide and README.md

### **Information to Include**
- Home Assistant version
- Integration version
- **Output from Get Cloud Devices in Sanitize mode**
- Setup method used
- Error messages from logs
- Network configuration details

---

**Next**: Once setup is complete, see main README.md for usage examples and advanced configuration options.

