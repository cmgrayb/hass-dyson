# Entity Availability Troubleshooting Guide

This guide helps resolve common issues with missing or unexpected entities in the Dyson Home Assistant integration.

## Quick Diagnosis

### 🔍 **Step 1: Check Your Device Configuration**

1. **Navigate to**: Settings → Devices & Services → Dyson Integration
2. **Find your device** in the device list
3. **Click on the device** to see its configuration
4. **Note**: Device category and capabilities listed

### 🔍 **Step 2: Expected vs Actual Entities**

Compare what you see with the [Device Compatibility Matrix](DEVICE_COMPATIBILITY.md) for your device type.

## Common Issues & Solutions

### ❌ Missing Air Quality Sensors (PM2.5, PM10)

#### **Symptoms**
- No PM2.5 or PM10 sensors in entity list
- Air quality data not available
- HEPA filter sensors missing

#### **Cause**
Device lacks `ExtendedAQ` capability

#### **Solutions**

**For Cloud-Discovered Devices:**
1. **Wait for sync**: Allow 5-10 minutes for full device discovery
2. **Check device model**: Verify your device actually supports air quality monitoring
   - ✅ Supported: TP04, TP07, HP04, HP07, DP04 series
   - ❌ Not supported: TP00, AM07, basic fan models
3. **Reload integration**: Settings → Devices & Services → Dyson → ⋯ → Reload

**For Manually Configured Devices:**
1. **Reconfigure device**: Settings → Devices & Services → Dyson → Configure
2. **Select ExtendedAQ capability** during setup
3. **Save configuration** and restart Home Assistant

### ❌ Missing WiFi Monitoring (Signal Strength, Connection Status)

#### **Symptoms**
- No WiFi signal strength sensor
- No connection status sensor
- Can't monitor device connectivity

#### **Cause**
Device category not set to "ec" (Environment Cleaner) or "robot"

#### **Solutions**

**For Cloud-Discovered Devices:**
1. **Verify device type**: Check if device is actually WiFi-enabled
   - ✅ WiFi devices: Most TP/HP/DP series, robot vacuums
   - ❌ Non-WiFi: Corded devices, some older models
2. **Check category detection**: May need manual override

**For Manually Configured Devices:**
1. **Update device category**: 
   - Go to device configuration
   - Set category to "Environment Cleaner" for air purifiers/fans
   - Set category to "Robot" for robot vacuums
2. **Save and restart** Home Assistant

### ❌ Missing Temperature Sensor/Climate Control

#### **Symptoms**
- No temperature sensor
- No climate platform for heating control
- Heat mode controls missing

#### **Cause**
Device lacks `Heating` capability

#### **Solutions**

**Verify Device Support:**
- ✅ Heating models: HP04, HP07, AM09 (Hot+Cool series)
- ❌ Cooling only: TP04, TP07, most Pure Cool models

**For Supported Devices:**
1. **Cloud setup**: Capability should be auto-detected
2. **Manual setup**: Ensure "Heating" capability is selected
3. **Reconfigure** if needed

### ❌ Missing Filter Sensors

#### **Symptoms**
- No HEPA filter life sensor
- No filter type information
- Filter replacement alerts missing

#### **Cause**
Usually tied to `ExtendedAQ` capability

#### **Solutions**
1. **Follow air quality sensor troubleshooting** above
2. **Verify device has replaceable filters**
3. **Check device documentation** for filter support

### ⚠️ Unexpected Sensors Appearing

#### **Symptoms**
- Sensors showing for features your device doesn't have
- Error states in entity list
- Sensors always showing "unavailable"

#### **Cause**
Incorrect capability or category configuration

#### **Solutions**
1. **Remove excess capabilities** from manual configuration
2. **Verify device specifications** against selected capabilities
3. **Reconfigure with conservative settings**

## Advanced Troubleshooting

### 🔧 **Check Integration Logs**

1. **Enable debug logging**:
   ```yaml
   # Add to configuration.yaml
   logger:
     logs:
       custom_components.hass_dyson: debug
   ```

2. **Restart Home Assistant**

3. **Check logs**: Settings → System → Logs → Filter by "hass_dyson"

4. **Look for**:
   - Capability detection messages
   - Entity creation logs
   - Connection status updates

### 🔧 **Verify Device Communication**

**MQTT Connection Check:**
1. Check connection status sensor (if available)
2. Look for "Local" or "Cloud" status (not "Disconnected")
3. Verify device responds to fan speed changes

**Network Diagnostics:**
1. Ensure device is on same network as Home Assistant
2. Check firewall settings for MQTT (port 1883)
3. Verify cloud connectivity if using cloud mode

### 🔧 **Reset and Reconfigure**

**Complete Reset (Last Resort):**
1. **Remove integration**: Settings → Devices & Services → Dyson → Delete
2. **Clear cached data**: Restart Home Assistant
3. **Re-add integration** with careful capability selection
4. **Document working configuration** for future reference

## Device-Specific Notes

### **TP04/TP07 Pure Cool Series**
- ✅ Should have: ExtendedAQ, WiFi monitoring, filter sensors
- ❌ Should not have: Heating/temperature control
- 🔧 Common issue: Sometimes detected without ExtendedAQ

### **HP04/HP07 Hot+Cool Series**
- ✅ Should have: ExtendedAQ, Heating, WiFi monitoring, all sensors
- ❌ Should not have: Humidifier capabilities
- 🔧 Common issue: Temperature sensor may need manual capability addition

### **Robot Vacuums (360 Eye, etc.)**
- ✅ Should have: WiFi monitoring, vacuum platform
- ❌ Should not have: Air quality sensors (unless hybrid model)
- 🔧 Common issue: May be detected as wrong category

### **Basic Fan Models (TP00, AM series)**
- ✅ Should have: Basic fan controls only
- ❌ Should not have: Air quality, WiFi, or advanced sensors
- 🔧 Common issue: Over-configuration with unsupported capabilities

## Getting Help

### **Before Reporting Issues**
1. ✅ Check this troubleshooting guide
2. ✅ Verify device model capabilities
3. ✅ Try reconfiguration with correct settings
4. ✅ Enable debug logging and check for errors

### **When Reporting Issues**
Include:
- **Device model** (exact model number)
- **Configuration method** (cloud discovery vs manual)
- **Selected capabilities** and device category
- **Expected vs actual entities**
- **Relevant log entries** (with debug enabled)
- **Home Assistant version** and integration version

### **Useful Commands**
```bash
# Check entity registry
ha core logs --follow | grep hass_dyson

# List all entities for device
grep "dyson" /config/.storage/core.entity_registry

# Check device registry
grep "dyson" /config/.storage/core.device_registry
```

## Prevention Tips

### **Best Practices**
1. **Research first**: Check device specifications before configuration
2. **Start conservative**: Begin with basic capabilities, add as needed
3. **Document configuration**: Note working setups for similar devices
4. **Test incrementally**: Add one capability at a time
5. **Monitor logs**: Watch for errors during entity creation

### **Configuration Validation**
- ✅ ExtendedAQ only for devices with air quality sensors
- ✅ Heating only for Hot+Cool models
- ✅ WiFi monitoring only for connected devices
- ✅ Device category matches actual device type
- ✅ Manual configuration matches device specifications
