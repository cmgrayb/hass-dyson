# Testing Guide for Dyson Integration

This guide covers **real-world testing** with actual Dyson devices to validate the integration's functionality.

> **Note**: For development testing patterns, unit testing, and mock setups, see the [Testing Patterns Documentation](.github/design/testing-patterns.md).

## Real-World Testing with Physical Devices

## Prerequisites
1. **Dyson Device**: A physical Dyson device (fan, purifier, etc.)
2. **Network Access**: Device must be on same network as Home Assistant
3. **Device Info**: Serial number and either:
   - Dyson account credentials (for cloud discovery), OR  
   - Device IP address + credential from sticker (for manual setup)

## Testing Approach 1: Cloud Discovery (Recommended)

### Step 1: Gather Information
- [ ] Dyson account email and password
- [ ] Device serial number (from device sticker or Dyson app)
- [ ] Confirm device is registered in your Dyson account

### Step 2: Update Configuration
Edit `docker/config/configuration.yaml`:
```yaml
hass-dyson:
  username: "your_real_email@dyson.com"
  password: "your_real_password"
  devices:
    - serial_number: "YOUR-DEVICE-SERIAL"
      discovery_method: "cloud"
```

### Step 3: Test Authentication
```bash
# Clear any existing config entries
python reset-config.py

# Restart container
./docker-dev.sh restart

# Monitor logs
./docker-dev.sh logs --tail=50 -f
```

### Expected Results
- [ ] **Authentication Success**: No "429 Too Many Requests" or credential errors
- [ ] **Device Discovery**: Integration finds your device in cloud account
- [ ] **MQTT Connection**: Device connects via MQTT
- [ ] **Entity Creation**: Sensors, fans, etc. appear in Home Assistant

## Testing Approach 2: Manual Device Setup

### Step 1: Gather Information
- [ ] Device serial number (from sticker)
- [ ] Device IP address (from router or network scan)
- [ ] Device credential (from sticker - usually starts with password-like string)
- [ ] Device capabilities (check device model documentation)

### Step 2: Update Configuration
Edit `docker/config/configuration.yaml`:
```yaml
hass-dyson:
  devices:
    - serial_number: "YOUR-DEVICE-SERIAL"
      discovery_method: "sticker"
      hostname: "192.168.1.XXX"  # Your device IP
      credential: "CREDENTIAL_FROM_STICKER"
      capabilities:
        - "EnvironmentalData"      # Most devices have this
        - "AdvanceOscillationDay1" # Common for fans
```

### Step 3: Test Direct Connection
```bash
# Clear any existing config entries
python reset-config.py

# Restart container
./docker-dev.sh restart

# Monitor logs
./docker-dev.sh logs --tail=50 -f
```

## Troubleshooting Guide

### Common Issues & Solutions

#### Authentication Issues
- **Error**: `Email and password are required`
  - **Solution**: Check YAML syntax, ensure credentials are properly quoted
  
- **Error**: `429 Too Many Requests`  
  - **Solution**: Wait 5-10 minutes, Dyson API has rate limits
  
- **Error**: `Invalid credentials`
  - **Solution**: Verify email/password work in Dyson mobile app

#### Device Discovery Issues
- **Error**: `Device not found in cloud account`
  - **Solution**: 
    1. Check serial number is correct
    2. Ensure device is registered in your Dyson account
    3. Try removing and re-adding device in Dyson app

#### Connection Issues  
- **Error**: `Connection timeout` or `MQTT connection failed`
  - **Solution**:
    1. Check device IP address is reachable: `ping 192.168.1.XXX`
    2. Ensure device and Home Assistant are on same network
    3. Check firewall settings

#### Import/Library Issues
- **Error**: `Cannot import name 'DysonClient'`
  - **Solution**: Library version mismatch, restart container: `./docker-dev.sh restart`

## Validation Checklist

Once integration loads successfully, verify:

### Device Entities
- [ ] **Fan entity**: `fan.device_name` appears in Home Assistant
- [ ] **Sensor entities**: Temperature, humidity, air quality sensors
- [ ] **Button entities**: Oscillation, night mode controls
- [ ] **Switch entities**: Various device-specific switches

### Device Controls
- [ ] **Turn on/off**: Fan power control works
- [ ] **Speed control**: Fan speed adjustment works  
- [ ] **Oscillation**: Oscillation toggle works
- [ ] **Night mode**: Night mode toggle works

### Data Updates
- [ ] **Real-time updates**: Sensors update when device conditions change
- [ ] **Status sync**: Device status matches what's shown in Dyson app
- [ ] **Command response**: Device responds to Home Assistant commands

## Advanced Testing

### Performance Testing  
```bash
# Monitor integration performance
./docker-dev.sh logs --tail=100 | grep -E "(hass-dyson|ERROR|WARNING)"

# Check memory/CPU usage in container
./docker-dev.sh shell
top -p $(pgrep python)
```

### Network Testing
```bash
# Check MQTT traffic (if using manual setup)
./docker-dev.sh shell
tcpdump -i any port 1883

# Test device connectivity
ping YOUR_DEVICE_IP
telnet YOUR_DEVICE_IP 1883
```

### Integration Testing
- [ ] **Home Assistant restart**: Integration survives HA restart
- [ ] **Device restart**: Integration reconnects after device power cycle  
- [ ] **Network issues**: Integration handles network interruptions gracefully

## Success Criteria

The integration is working correctly when:
1. ✅ **No authentication errors** in logs
2. ✅ **Device entities appear** in Home Assistant UI
3. ✅ **Controls work** - can turn device on/off, change settings
4. ✅ **Sensors update** - real-time data from device
5. ✅ **No recurring errors** in logs after initial setup

## Next Steps After Successful Testing

1. **Document your configuration** for future reference
2. **Test edge cases** (device offline, network issues)
3. **Consider security** (credential storage, network access)
4. **Optimize polling intervals** if needed
5. **Set up automations** using the new device entities

## Getting Help

If you encounter issues:
1. **Check logs first**: Most issues show clear error messages
2. **Verify network connectivity**: Ping device, check firewall
3. **Test with Dyson app**: Ensure device works normally outside Home Assistant
4. **Review configuration**: YAML syntax, serial numbers, credentials
5. **Rate limiting**: Wait if you see 429 errors from API calls
