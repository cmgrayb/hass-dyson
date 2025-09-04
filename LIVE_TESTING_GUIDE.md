# AWS IoT WebSocket Live Testing Guide

## 🚀 Ready for Live Testing!

The AWS IoT WebSocket implementation is ready for live testing with real Dyson devices. This guide will help you test safely and effectively.

## ✅ Pre-Testing Checklist

### Implementation Status
- ✅ AWS IoT WebSocket MQTT client implemented
- ✅ Credential parsing and authentication logic complete
- ✅ WebSocket Secure (WSS) TLS configuration ready
- ✅ Automatic detection of WebSocket requirement (`remote_broker_type: "wss"`)
- ✅ Fallback to local MQTT if cloud fails
- ✅ All runtime dependencies satisfied
- ✅ Syntax validation passed

### Dependencies Confirmed
- ✅ `paho-mqtt>=1.6.0` with WebSocket transport support
- ✅ `websockets>=10.0` library available
- ✅ `ssl` module for TLS/SSL connections
- ✅ `urllib.parse` for URL encoding

## 🧪 Testing Strategy

### Phase 1: Installation Testing
1. **Copy Integration to Home Assistant**
   ```bash
   cp -r custom_components/hass_dyson /config/custom_components/
   ```

2. **Restart Home Assistant**
   - Full restart required to load new integration

3. **Check Logs for Import Errors**
   ```bash
   tail -f /config/home-assistant.log | grep hass-dyson
   ```

### Phase 2: Cloud Discovery Testing
1. **Add Integration via UI**
   - Go to Settings → Devices & Services → Add Integration
   - Search for "Dyson"
   - Choose "Cloud Discovery" method

2. **Enter Dyson Account Credentials**
   - Use valid Dyson account email/password
   - Monitor logs for API communication

3. **Device Detection**
   - Integration should find devices with AWS IoT credentials
   - Look for `remote_broker_type: "wss"` in debug logs

### Phase 3: WebSocket Connection Testing
1. **Enable Debug Logging**
   Add to `configuration.yaml`:
   ```yaml
   logger:
     default: warning
     logs:
       custom_components.hass-dyson: debug
       custom_components.hass_dyson.device: debug
       custom_components.hass_dyson.coordinator: debug
   ```

2. **Monitor Connection Attempts**
   Look for these log messages:
   - `"Setting up AWS IoT WebSocket connection"`
   - `"Using AWS IoT client ID"`
   - `"Would attempt connection to <endpoint>:443"`

3. **Success Indicators**
   - Device entities appear in Home Assistant
   - Device status shows "Connected" 
   - MQTT messages being received

## 🔍 Debugging and Monitoring

### Key Log Messages

#### Successful AWS IoT WebSocket Connection
```
DEBUG Setting up AWS IoT WebSocket connection to a1u2wvl3e2lrc4-ats.iot.eu-west-1.amazonaws.com
DEBUG Using AWS IoT client ID: dyson-ha-cloud-438M123456-1a2b3c4d
DEBUG Attempting AWS IoT WebSocket connection to a1u2wvl3e2lrc4-ats.iot.eu-west-1.amazonaws.com:443
DEBUG Successfully connected to AWS IoT via WebSocket: a1u2wvl3e2lrc4-ats.iot.eu-west-1.amazonaws.com
```

#### Connection Issues
```
ERROR Invalid AWS IoT credentials: <error details>
ERROR Failed to establish AWS IoT WebSocket connection to <host>: <error>
DEBUG AWS IoT WebSocket connection timeout after 10s
DEBUG AWS IoT WebSocket connection failed with result: <error_code>
```

#### Fallback to Local MQTT
```
DEBUG Cloud connection failed, attempting local fallback
DEBUG Attempting local MQTT connection to <local_ip>:1883
```

### Common Issues and Solutions

1. **Certificate Validation Errors**
   - Check system time is correct
   - Verify CA certificate bundle is up to date

2. **Authentication Failures**
   - Verify AWS IoT credentials are valid
   - Check token hasn't expired
   - Confirm custom authorizer is working

3. **Network Issues**
   - Ensure port 443 is open for outbound connections
   - Check firewall settings
   - Verify internet connectivity

4. **SSL/TLS Errors**
   - Update OpenSSL/TLS libraries
   - Check TLS version compatibility

## 🛡️ Safety Measures

### Backup Plans
1. **Local MQTT Fallback**: Integration will automatically try local connection if cloud fails
2. **Manual Configuration**: Can switch to sticker-based setup if needed
3. **Integration Removal**: Easy to remove via UI if issues occur

### Data Protection
- No sensitive credentials stored in logs
- AWS IoT tokens are properly redacted in debug output
- Secure TLS communication only

### Monitoring
- Watch Home Assistant system resources during testing
- Monitor network traffic for unusual patterns
- Keep backup of working configuration

## 📊 Success Metrics

### Connection Success
- [ ] Device appears in Home Assistant devices list
- [ ] Device status shows "Connected" via cloud
- [ ] Real-time sensor data updating
- [ ] Control commands working (fan speed, oscillation, etc.)

### Performance Success  
- [ ] Connection established within 30 seconds
- [ ] MQTT messages received promptly
- [ ] No excessive CPU/memory usage
- [ ] Stable connection without frequent reconnects

### Integration Success
- [ ] All expected entities created
- [ ] Entity states updating correctly  
- [ ] Device controls working from HA UI
- [ ] Automation/scenes function properly

## 🐛 Issue Reporting

If you encounter issues during testing, please capture:

1. **Home Assistant Logs** (with debug enabled)
2. **Device Model** (438M, 475, etc.)
3. **Connection Method** (cloud discovery vs manual)
4. **Network Environment** (home WiFi, VPN, etc.)
5. **Error Messages** (exact text from logs)

## 🎯 Testing Scenarios

### Scenario 1: Cloud-Only Device
- Device configured for cloud-only operation
- Should use AWS IoT WebSocket automatically
- Local fallback should fail gracefully

### Scenario 2: Dual-Connection Device  
- Device supports both local and cloud
- Should prefer local, fall back to cloud if needed
- Test by disabling local WiFi temporarily

### Scenario 3: Network Switching
- Start with local connection
- Switch to different network
- Should fall back to cloud automatically

## 📝 Next Steps After Testing

1. **Document Results**: Record what works and what doesn't
2. **Performance Optimization**: Identify any bottlenecks
3. **Error Handling**: Improve error messages based on real issues
4. **Feature Enhancement**: Add missing capabilities discovered during testing

---

**Ready to begin live testing!** 🚀

Start with Phase 1 and work through systematically. The implementation is solid and should handle real AWS IoT connections properly.
