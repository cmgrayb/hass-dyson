# Troubleshooting

## Cloud Accounts

### "Failed to find account {email} on {api_fqdn}"

The integration could not locate your account on the Dyson API endpoint determined by your country/region.

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

### **Device Silently Running on the Cloud Connection**

**Problem**: Everything looks healthy. The device is discovered, all its entities
exist, none of them is unavailable and there is no error in the log, yet local
control is gone: commands take seconds instead of being instant, and the device
stops responding at all when the internet does.

**How this happens**: a device set to prefer a local connection falls back to
the cloud when the local MQTT connection cannot be established, which is the
right behaviour, but it is not an error, so nothing in the UI announces it. The
address that failed may come from four different places, in this priority order:

1. a static IP or hostname entered in the device's connection options
2. the hostname reported by the cloud API
3. an IP learned from DHCP discovery
4. `{serial}.local`, resolved over mDNS

Only the first is something you typed. The other three are discovered, and each
has its own way of going stale: a device that moves to a new DHCP lease, a
network that filters mDNS, a hostname the cloud never updated.

**How to tell**:

- **Repairs** raises a warning after the fallback has lasted ten minutes, and
  the wording differs depending on whether the failing address was configured or
  discovered. It clears itself once the device connects locally again.
- The **Connection Status** sensor reads `Cloud` instead of `Local`.
- The **IP Address** sensor shows the address actually in use, and its
  attributes say where that address came from. `host_source` is one of
  `configured`, `cloud_api`, `dhcp` or `mdns`, and `is_ip_address` is false
  while the value is still a name waiting to be resolved. An unresolvable
  `{serial}.local` reads like a perfectly good value in the state alone, which
  is exactly what makes this failure quiet.

**Solution**: set the device's IP address in its connection options, which
bypasses discovery entirely, or fix mDNS on the network as described in the
section above. Reserve the address on the DHCP server so it survives a lease
renewal.

### **Device Registry Missing MAC Address / Not Linking to Router-Reported Device**

**Problem**: The device page shows an empty `connections` field, so it never merges
with the same physical device tracked by a router-backed integration (TP-Link,
UniFi, Fritz!Box, etc.).

**How this works**: The integration relies on Home Assistant's built-in `dhcp`
discovery component to observe a Dyson device's MAC address on the network and
populate the device registry automatically — no cooperation from the device
itself is required.

**Common Causes**:
- **Docker container networking**: if Home Assistant runs in a container on an
  isolated bridge network (the default for `docker-compose`), it has no L2
  visibility into the physical LAN and can never observe the device's DHCP or
  ARP traffic. Requires `network_mode: host` (Linux only) or a `macvlan`
  network attached to the physical LAN interface.
- **DHCP lease not yet renewed and no active scan**: HA performs an active
  network scan at startup in addition to passive sniffing, but this still
  requires L2 visibility as above.
- **Device's WiFi module uses an OUI not yet recognized**: the integration
  matches DHCP traffic against a known list of Dyson MAC prefixes; devices
  using a newer/unlisted WiFi module won't be discovered until that OUI is
  added.

**Solution**:
- Ensure Home Assistant itself (not just this integration) has real network
  visibility to the device's LAN segment (host networking or macvlan for
  containerized installs).
- Enable debug logging for `homeassistant.components.dhcp` and
  `custom_components.hass_dyson.config_flow` to confirm discovery events are
  received.

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
