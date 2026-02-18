# Device Management

The integration provides comprehensive device management options through the **Configure** button in Home Assistant's Devices & Services section.

## **Account-Level Management**

- **Reload All Devices** - Refresh connection and state for all devices
- **Set Default Connection** - Configure default connection method for all devices

## **Individual Device Management**

- **Configure**: Device-specific connection settings (connection type and static IP/hostname)
- **Reload**: Native Home Assistant button (top of device page)
- **Delete**: Native Home Assistant button (device menu)

### **Device Configuration Options**

When you click **Configure** on a device, you can modify:

#### **Connection Type**
- **Use Account Default** (cloud devices only) - Inherit from account settings
- **Local Only** - Direct local connection, maximum privacy
- **Local with Cloud Fallback** - Tries local first (recommended)
- **Cloud with Local Fallback** - More reliable connection
- **Cloud Only** - For networks without mDNS support

#### **Static IP / Hostname**
- **Current value displayed** - Shows configured IP or "(automatic discovery)"
- **Add static IP** - Enter IP address to bypass mDNS discovery
- **Change IP** - Update to new IP address or hostname
- **Clear IP** - Remove static IP to return to automatic mDNS

**When to use static IP**:
- mDNS discovery is unreliable on your network
- Device has DHCP reservation
- You prefer predictable addressing
- Troubleshooting connection issues

**Example configurations**:
```
Cloud device with static IP:
  Connection Type: Local with Cloud Fallback
  IP Address: 192.168.1.100

Manual device (already has static IP from setup):
  Connection Type: Local Only
  IP Address: 192.168.1.50 (from initial setup)

Cloud device with automatic discovery:
  Connection Type: Use Account Default
  IP Address: (leave blank)
```

## **Connection Type Hierarchy**

1. **Device Override** - Takes priority if set
2. **Account Default** - Used when no device override
3. **System Default** - Final fallback (`local_cloud_fallback`)

## **How to Access**

- **Account**: Configure button on main integration entry
- **Device**: Native HA controls + Configure button for connection settings

## **Device Status Indicators**

- **Active** - Device is currently set up and running
- **Inactive** - Device exists in account but not currently active
