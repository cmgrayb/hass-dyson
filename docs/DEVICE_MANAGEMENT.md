# Device Management

The integration provides comprehensive device management options through the **Configure** button in Home Assistant's Devices & Services section.

## **Account-Level Management**

- **Reload All Devices** - Refresh connection and state for all devices
- **Set Default Connection** - Configure default connection method for all devices

## **Individual Device Management**

- **Configure**: Device-specific connection settings only
- **Reload**: Native Home Assistant button (top of device page)
- **Delete**: Native Home Assistant button (device menu)

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
