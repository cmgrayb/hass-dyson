# Setup Guide - Dyson Alternative Integration

Complete setup instructions for integrating your Dyson devices with Home Assistant.

## 🎯 Prerequisites

### **Home Assistant Requirements**
- Home Assistant Core 2023.1 or newer
- Custom components support enabled
- Network access to Dyson devices

### **Dyson Device Requirements**
- Dyson device connected to same WiFi network as Home Assistant
- Device sticker information available (for manual setup)
- OR Dyson account credentials (for cloud discovery)

## 📥 Installation Methods

### **Method 1: HACS (Recommended)**
1. Open HACS in Home Assistant
2. Go to "Integrations" 
3. Click "Custom Repositories"
4. Add URL: `https://github.com/cmgrayb/ha-dyson-alt`
5. Category: "Integration"
6. Install "Dyson Alternative"
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

## ⚙️ Configuration Options

### **Option 1: Cloud Discovery (Easy)**

**When to use**: You have Dyson account and want automatic device discovery

**Setup steps**:
1. Go to **Settings** → **Devices & Services**
2. Click **"Add Integration"**
3. Search for **"Dyson Alternative"**
4. Select **"Cloud Discovery"**
5. Enter your Dyson account email and password
6. Devices will be discovered automatically

**Pros**: Automatic setup, gets all device info from cloud
**Cons**: Requires internet, shares credentials with cloud

### **Option 2: Manual Setup (Recommended)**

**When to use**: You want local-only control or cloud discovery failed

**Required information** (from device sticker):
- **Serial Number** (e.g., `MOCK-SERIAL-TEST123`)
- **WiFi Password** (8-character string on sticker)
- **Product Type** (e.g., 438 for Pure Cool)

**Setup steps**:
1. Locate device sticker (usually on bottom or back)
2. Go to **Settings** → **Devices & Services** → **"Add Integration"**
3. Search for **"Dyson Alternative"**
4. Select **"Manual Setup"**
5. Enter required information:
   ```
   Serial Number: MOCK-SERIAL-TEST123
   WiFi Password: AAAABBBB
   Product Type: 438
   Device IP (optional): 192.168.1.161
   ```
6. Click **Submit**

### **Option 3: YAML Configuration (Advanced)**

**When to use**: You want to configure multiple devices at once

**Configuration example**:
```yaml
# configuration.yaml
hass-dyson:
  devices:
    - serial_number: "MOCK-SERIAL-TEST123"
      discovery_method: "sticker"
      hostname: "192.168.1.161"  # Optional
      credential: "AAAABBBB"     # WiFi password from sticker
      device_type: "438"
      mqtt_prefix: "438M"
      capabilities: ["Auto", "Oscillation", "Heating"]

    - serial_number: "475-US-JEN0000B"
      discovery_method: "sticker"  
      hostname: "192.168.1.162"
      credential: "CCCCDDDD"
      device_type: "475"
      mqtt_prefix: "475"
      capabilities: ["Auto", "Heating", "Scheduling"]
```

## 🏷️ Device Information Guide

### **Finding Device Information**

**Device Sticker Location**:
- **Tower models**: Bottom of device
- **Desk models**: Back/bottom of device  
- **Wall models**: Behind mounting bracket

**Sticker Information**:
```
Serial Number: MOCK-SERIAL-TEST123  ← Use this
WiFi Password: AAAABBBB         ← Use this
Model: 438                      ← Use this for device_type
```

### **MQTT Prefix by Model**
| Model | Product Name | MQTT Prefix |
|-------|-------------|-------------|
| 438 | Pure Cool | 438M |
| 475 | Hot+Cool | 475 |
| 527 | V10/V11 | 527 |
| 455 | Pure Hot+Cool | 455 |
| 469 | Pure Cool Desk | 469 |

**Auto-detection**: Integration automatically determines MQTT prefix from device type

### **Device Capabilities**
**Automatically detected** based on device type:
- **Auto Mode** - Smart air quality response
- **Oscillation** - Side-to-side movement  
- **Heating** - Hot air output (HP models)
- **Scheduling** - Timer functions
- **Fault Detection** - Error monitoring

## 🔍 Network Discovery

### **Finding Device IP Address**

**Method 1: Router Admin Panel**
1. Access your router's web interface
2. Look for "Connected Devices" or "DHCP Clients"
3. Find device with hostname starting with "Dyson"

**Method 2: Network Scanner**
```bash
# Linux/Mac
nmap -sn 192.168.1.0/24 | grep -i dyson

# Windows  
ping 192.168.1.161  # Try common IPs
```

**Method 3: Home Assistant Log**
1. Enable debug logging:
   ```yaml
   logger:
     logs:
       custom_components.hass-dyson: debug
   ```
2. Check logs for discovered devices

### **Testing Device Connection**
```bash
# Test MQTT connection (port 1883)
telnet 192.168.1.161 1883

# Test device ping
ping 192.168.1.161
```

## ✅ Verification Steps

### **1. Integration Loaded**
- Go to **Settings** → **Devices & Services**
- Verify "Dyson Alternative" appears in list
- Status should show "Configured"

### **2. Device Connected**
- Device should show as "Online" in integration
- All entities should be populated with data
- No error messages in logs

### **3. Entity Verification**
**Expected entities per device**:
- 1 Fan (primary control)
- 2-4 Sensors (PM2.5, PM10, RSSI, Filter)  
- 2-3 Binary Sensors (connectivity, filter, faults)
- 1-2 Buttons (identify, reset filter)
- 3-5 Number controls (speed, timer, angle)
- 2-4 Select controls (modes)
- 3-6 Switch controls (features)
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
- Double-check WiFi password from sticker
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

## 📞 Getting Help

### **Before Requesting Support**
1. Enable debug logging:
   ```yaml
   logger:
     logs:
       custom_components.hass-dyson: debug
   ```

2. Restart Home Assistant

3. Reproduce the issue

4. Collect relevant log entries

### **Support Channels**
- **GitHub Issues**: [Report bugs/feature requests](https://github.com/cmgrayb/ha-dyson-alt/issues)
- **Home Assistant Community**: Search for "Dyson Alternative"
- **Documentation**: This guide and README.md

### **Information to Include**
- Home Assistant version
- Integration version  
- Dyson device model
- Setup method used
- Error messages from logs
- Network configuration details

---

**Next**: Once setup is complete, see main README.md for usage examples and advanced configuration options.
