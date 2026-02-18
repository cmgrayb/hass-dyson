# Troubleshooting

## Cloud Accounts

### "Authentication failed. Please check your email and password."

Authentication has failed to request an OTP to send for the MFA step.

- Ensure that an account already exists
- Ensure that you are using a Dyson account, and not an OAUTH account such as:
  - Google
  - Microsoft
  - Apple
  - Facebook
  - Twitter/X
  - GitHub

### "Verification failed. Please check your password and the code and try again."

This message occurs when the password and OTP sent via e-mail do not authenticate properly.

Most common solutions:
- Ensure that the OTP is recent (last few minutes)
- Check account password for errors
- Ensure that you are using a Dyson account, and not an OAUTH account such as:
  - Google
  - Microsoft
  - Apple
  - Facebook
  - Twitter/X
  - GitHub

## **Device Connection Issues**

### **Device Not Found / mDNS Issues**

**Problem**: Device not discovered automatically, "device not found" errors

**Common Causes**:
- Network doesn't support multicast DNS (mDNS)
- VLANs or network segregation blocking mDNS traffic
- WiFi mesh system not forwarding mDNS properly
- Router firmware issues with multicast traffic
- Container networking (Docker) isolating mDNS

**Solution: Use Static IP Address**

1. **Find your device's IP address**:
   ```bash
   # Check device network connectivity
   ping 192.168.1.100  # Your device IP

   # Or use network scanner
   sudo nmap -sn 192.168.1.0/24
   ```

2. **Configure static IP in integration**:
   - **For new cloud-discovered devices**: Enter IP in "Connection Configuration" step
   - **For existing devices**: Go to device Configure → enter IP in hostname field
   - **For manual setup**: Enter IP in "IP Address or Hostname" field

3. **Verify connection**:
   ```bash
   # Test MQTT port is accessible
   telnet 192.168.1.100 1883
   # or
   nc -zv 192.168.1.100 1883
   ```

**See also**: [Static IP Configuration Guide](SETUP.md#static-ip--hostname-configuration)

### **MQTT Connection Failed**

```bash
# Verify MQTT prefix in logs
grep "MQTT prefix" /config/home-assistant.log
```

## **Device Not Found**

1. Verify device is on same network as Home Assistant
2. Check serial number from device sticker
3. Ensure device password is correct
4. Try manual IP address in hostname field

## **No Data Updates**

1. Check device MQTT topics in logs
2. Verify paho-mqtt dependency installed
3. Restart integration from UI
4. Check firewall settings for MQTT traffic

## **Debug Logging**

```yaml
# In configuration.yaml
logger:
  logs:
    custom_components.hass_dyson: debug
```

## **Contact Us!**

If the above troubleshooting steps do not solve the problem you are encountering,
please check for known issues on [GitHub](https://github.com/cmgrayb/hass-dyson/issues)

If your issue is not covered by an existing report, please open a new issue to let us know!
