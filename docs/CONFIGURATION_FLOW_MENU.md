# Configuration Flow Menu Enhancement

## Overview

This enhancement adds a menu to the beginning of the Dyson integration's configuration flow, allowing users to choose between two setup methods:

1. **Dyson Cloud Account (Recommended)** - The existing cloud-based setup flow
2. **Manual Device Setup** - A new manual setup option for direct device configuration

## Changes Made

### 1. Configuration Flow (`config_flow.py`)

#### New `async_step_user` Method
- **Purpose**: Initial setup method selection menu
- **Options**: Cloud Account or Manual Device
- **Flow**: Routes users to appropriate setup path based on selection

#### Renamed `async_step_cloud_account` Method  
- **Previously**: `async_step_user`
- **Purpose**: Handle cloud account authentication (existing functionality)
- **Flow**: Email/Password → Verification → Connection Type → Device Discovery

#### New `async_step_manual_device` Method
- **Purpose**: Manual device configuration
- **Required Fields**:
  - Device Serial Number
  - Device Password
- **Optional Fields**:
  - Device IP Address (hostname)
  - Device Name
- **Default Settings**:
  - Connection Type: `local_only` (for privacy)
  - Discovery Method: `manual`

### 2. Translation Updates (`translations/en.json`)

#### New Translation Keys
```json
{
  "config": {
    "step": {
      "user": {
        "title": "Dyson Integration Setup",
        "description": "Choose how you would like to set up your Dyson devices.",
        "data": {
          "setup_method": "Setup Method"
        }
      },
      "manual_device": {
        "title": "Manual Device Setup",
        "description": "Enter your device information manually. You can find the serial number and device password on a sticker on your device.",
        "data": {
          "serial_number": "Device Serial Number",
          "credential": "Device Password",
          "hostname": "Device IP Address (Optional)",
          "device_name": "Device Name (Optional)"
        }
      }
    },
    "error": {
      "manual_setup_failed": "Manual setup failed. Please check your device information.",
      "invalid_setup_method": "Invalid setup method selected.",
      "required": "This field is required."
    }
  }
}
```

### 3. Updated Imports
- Added required constants from `const.py`:
  - `CONF_CREDENTIAL`
  - `CONF_HOSTNAME` 
  - `CONF_DISCOVERY_METHOD`
  - `CONF_CONNECTION_TYPE`
  - `CONNECTION_TYPE_LOCAL_ONLY`
  - `DISCOVERY_MANUAL`

## User Experience

### Setup Flow Diagram
```
Integration Setup
       ↓
   [User Menu]
   ┌─────────────────────────────────┐
   │ ☁️  Dyson Cloud Account        │
   │    (Recommended)                │
   │                                 │
   │ 🔧 Manual Device Setup         │
   └─────────────────────────────────┘
       ↓                    ↓
[Cloud Flow]        [Manual Flow]
Email/Password      Serial/Password
     ↓                    ↓
Verification        Device Created
     ↓
Connection Type
     ↓
Device Discovery

```

### Manual Setup Benefits
- **Privacy**: Uses `local_only` connection by default
- **No Cloud Required**: Works without internet access after setup
- **Direct Control**: Bypass cloud authentication for individual devices
- **Flexibility**: Optional IP address for static network configurations

## Technical Details

### Configuration Data Structure (Manual)
```python
{
    "serial_number": "123-AB-CD456789",
    "credential": "MyDevicePassword123",
    "discovery_method": "manual",
    "connection_type": "local_only",
    "device_name": "Living Room Air Purifier",
    "hostname": "192.168.1.100"  # Optional
}
```

### Error Handling
- **Validation**: Required fields are checked before submission
- **Uniqueness**: Prevents duplicate device entries by serial number
- **Graceful Failures**: Provides clear error messages for troubleshooting

## Compatibility

- **Backward Compatible**: Existing cloud-based setup remains unchanged
- **Home Assistant Core**: Compatible with HA config flow standards
- **Integration Options**: Both manual and cloud devices can coexist

## Future Enhancements

Potential improvements could include:
- Auto-discovery of local devices on network
- QR code scanning for device credentials
- Bulk device import from configuration files
- Connection type selection during manual setup
