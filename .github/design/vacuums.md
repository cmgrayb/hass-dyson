# Dyson Robot Vacuum Communication Protocol

## Overview

This document describes the communication protocols, device capabilities, and control mechanisms for Dyson robot vacuum cleaners. It focuses on how these devices operate, communicate over networks, and respond to commands, providing the technical foundation for developing integrations and control systems.

## Supported Vacuum Models

| Model | Device Type | Key Features | Device Category | Capabilities |
|-------|-------------|--------------|-----------------|---------------|
| **360 Eye** | `N223` | First-generation robot vacuum with 360° camera navigation | `robot` | Basic navigation |
| **360 Heurist** | `276` | Advanced robot vacuum with improved navigation and zone control | `robot` | Heat, Advanced navigation |
| **360 Vis Nav** | `277` | Latest model with enhanced visual navigation and mapping | `robot` | Mapping, Restrictions, DirectedCleaning, ChangeWifi, CleaningStrategies, ActiveFaults, DustDetection, OutOfBoxState |

### Device Capabilities by Model

#### 360 Vis Nav (Model 277) Confirmed Capabilities
The 360 Vis Nav robot vacuum supports the following advanced features:
- **Mapping**: Create and maintain floor plan maps
- **Restrictions**: Define no-go zones and virtual barriers
- **DirectedCleaning**: Target specific areas or rooms for cleaning
- **ChangeWifi**: Modify WiFi network settings remotely
- **CleaningStrategies**: Multiple cleaning patterns and methodologies
- **ActiveFaults**: Real-time fault detection and reporting
- **DustDetection**: Intelligent dust level sensing for adaptive cleaning
- **OutOfBoxState**: Initial setup and first-time configuration support

## Device Network Architecture

### Network Discovery
Dyson vacuums announce themselves on local networks using **mDNS/Zeroconf** protocols:

- **360 Eye Model**: Advertises service `_360eye_mqtt._tcp.local.`
- **Other Models**: Advertise service `_dyson_mqtt._tcp.local.`

### Device Identification
Each device broadcasts a unique identifier in its mDNS service name:
- **360 Eye**: Format `{prefix}-{serial}._{service}`
- **Other Models**: Format `DYSON_{serial}_{device_type}._{service}`

### Network Communication Stack
```
Application Layer    │ JSON Command/Status Messages
Transport Layer      │ MQTT v3.1 over TCP
Network Layer        │ IP (Local Network)
Discovery Layer      │ mDNS/Zeroconf Service Advertisement
```

## MQTT Communication Protocol

### Device MQTT Broker
Each Dyson vacuum runs an embedded MQTT broker that accepts connections on the standard MQTT port (1883). The device acts as both publisher (sending status updates) and subscriber (receiving commands).  The MQTT broker appears to be similar to or the same as
the MQTT broker used by fans.  Re-use any existing functions already present whenever possible to avoid repetitive code.

### Topic Structure
```
{device_type}/{serial_number}/status    # Device → Client (status updates and faults)
{device_type}/{serial_number}/command   # Client → Device (control commands)
```

**Examples:**
- `N223/ABC-DE-12345678/status` (360 Eye status)
- `276/XYZ-AB-87654321/command` (360 Heurist commands)

### Message Protocol
All MQTT messages use JSON payloads with mandatory timestamp fields:

```json
{
  "msg": "MESSAGE_TYPE",
  "time": "2025-12-17T10:30:15Z",
  "data": { /* message-specific payload */ }
}
```

### Authentication & Security
- **Connection**: MQTT v3.1 with username/password authentication
- **Username**: Device serial number (e.g., `ABC-DE-12345678`)
- **Password**: SHA-512 hash of WiFi setup password, base64 encoded
- **Network**: Local network only - devices do not accept external connections
- **Encryption**: Plain TCP (relies on local network security)

## Device Operational States

### Primary Operating Modes

#### Active Cleaning States
- `FULL_CLEAN_RUNNING` - Robot actively cleaning entire accessible area
- `FULL_CLEAN_PAUSED` - Cleaning suspended, awaiting resume command
- `FULL_CLEAN_FINISHED` - Cleaning cycle completed, returning to dock
- `FULL_CLEAN_DISCOVERING` - Initial room scanning before cleaning
- `FULL_CLEAN_TRAVERSING` - Moving between cleaning areas

#### Mapping and Navigation
- `MAPPING_RUNNING` - Creating or updating floor plan map
- `MAPPING_PAUSED` - Mapping process suspended
- `MAPPING_FINISHED` - Map creation completed

#### Dock and Charging States
- `INACTIVE_CHARGED` - Fully charged and ready for operation
- `INACTIVE_CHARGING` - Actively charging at dock
- `INACTIVE_DISCHARGING` - On dock but not charging
- `FULL_CLEAN_CHARGING` - Interrupted cleaning to recharge
- `MAPPING_CHARGING` - Interrupted mapping to recharge

#### Error and Fault Conditions
- `FAULT_CRITICAL` - Hardware failure requiring service
- `FAULT_USER_RECOVERABLE` - Issue requiring user intervention (e.g., obstruction)
- `FAULT_LOST` - Navigation failure, robot cannot determine position
- `FAULT_ON_DOCK` - Charging dock malfunction
- `FAULT_RETURN_TO_DOCK` - Unable to return to charging station

### Device Status Information

The device continuously reports its status via MQTT, including:

| Field | Type | Description |
|-------|------|-------------|
| `state` | String | Current operational state from above list |
| `newstate` | String | Alternative state field (model dependent) |
| `batteryChargeLevel` | Integer | Battery percentage (0-100) |
| `globalPosition` | Array[Int, Int] | Current coordinates [x, y] in device units |
| `fullCleanType` | String | Type of cleaning operation in progress |
| `cleanId` | String | Unique identifier for current cleaning session |

## Device-Specific Capabilities

### Suction Power Control

Each model supports different power level commands:

#### 360 Eye Robot
- `halfPower` - Quiet operation mode (extended battery life)
- `fullPower` - Maximum suction for deep cleaning

#### 360 Heurist Robot
- `1` - Quiet mode (lowest noise, longest battery)
- `2` - High mode (balanced performance)
- `3` - Maximum mode (strongest suction)

#### 360 Vis Nav Robot
- `1` - Auto mode (intelligent power adjustment)
- `2` - Quick mode (fast cleaning cycle)
- `3` - Quiet mode (minimal noise operation)
- `4` - Boost mode (maximum suction power)

### Cleaning Operation Types

The devices recognize different cleaning contexts:

#### Cleaning Trigger Types
- `immediate` - User-initiated cleaning via app or button
- `manual` - Direct user control and navigation
- `scheduled` - Automated cleaning based on programmed schedule

#### Cleaning Area Modes
- `global` - Clean entire mapped area systematically
- `zoneConfigured` - Clean specific user-defined zones only

## Device Control Commands

### Basic Operation Control
Send these commands to `{device_type}/{serial}/command` topic:

| Command | JSON Message | Device Response |
|---------|--------------|-----------------|
| **PAUSE** | `{"msg": "PAUSE", "time": "ISO8601"}` | Suspends current operation |
| **RESUME** | `{"msg": "RESUME", "time": "ISO8601"}` | Continues paused operation |
| **ABORT** | `{"msg": "ABORT", "time": "ISO8601"}` | Stops and cancels current task |

### Status Request
```json
{
  "msg": "REQUEST-CURRENT-STATE",
  "time": "2025-12-17T10:30:15Z"
}
```

The device responds immediately with complete status on the status topic.

## Communication Examples

### Device Discovery Process
1. **mDNS Service Lookup**: Scan for `_dyson_mqtt._tcp.local.` or `_360eye_mqtt._tcp.local.`
2. **Extract Device Info**: Parse service name to get serial number and device type
3. **Resolve IP Address**: Use mDNS to get device IP address
4. **MQTT Connection**: Connect to device IP on port 1883

### MQTT Connection Sequence
```
1. TCP Connect to {device_ip}:1883
2. MQTT CONNECT with username={serial}, password={hashed_wifi_password}
3. SUBSCRIBE to {device_type}/{serial}/status
4. PUBLISH to {device_type}/{serial}/command for control
```

### Status Message Examples

**Initial Status Response:**
```json
{
  "msg": "CURRENT-STATE",
  "time": "2025-12-17T10:30:15Z",
  "state": "INACTIVE_CHARGED",
  "batteryChargeLevel": 100,
  "globalPosition": [1250, 800],
  "fullCleanType": "",
  "cleanId": ""
}
```

**Cleaning Status Update:**
```json
{
  "msg": "STATE-CHANGE",
  "time": "2025-12-17T10:32:45Z",
  "state": "FULL_CLEAN_RUNNING",
  "batteryChargeLevel": 95,
  "globalPosition": [1180, 750],
  "fullCleanType": "immediate",
  "cleanId": "clean_20251217_103245"
}
```

### Command Examples

**Pause Cleaning:**
```json
{
  "msg": "PAUSE",
  "time": "2025-12-17T10:35:00Z"
}
```

**Resume Cleaning:**
```json
{
  "msg": "RESUME",
  "time": "2025-12-17T10:37:30Z"
}
```

**Cancel Operation:**
```json
{
  "msg": "ABORT",
  "time": "2025-12-17T10:40:00Z"
}
```

## Device Behavior and Error Conditions

### Connection Error Responses
When MQTT connections fail, devices respond with specific MQTT return codes:

| Return Code | Meaning | Likely Cause |
|-------------|---------|--------------|
| `0` | Connection Accepted | Successful authentication |
| `1` | Bad Username/Password | Invalid serial or WiFi password hash |
| `2` | Identifier Rejected | Client ID conflicts |
| `3` | Server Unavailable | Device MQTT broker offline |
| `5` | Not Authorized | Device-specific authorization failure |
| `7` | Connection Refused | Device type mismatch or firmware issue |

### Device Limitations
- **Concurrent Connections**: Most devices allow only 1-2 simultaneous MQTT clients
- **Command Rate**: Commands should be spaced at least 1-2 seconds apart
- **Network Requirements**: Devices must be on same local network subnet
- **Battery Behavior**: Low battery may cause delayed responses or disconnections

### Fault State Recovery
When devices enter fault states, they typically require:
- **User Recovery Faults**: Physical intervention (remove obstruction, empty bin)
- **Navigation Faults**: Manual repositioning or restarting cleaning cycle
- **Critical Faults**: Device restart or service contact

## Security and Network Architecture

### Authentication Mechanism
```
WiFi Password → SHA-512 Hash → Base64 Encode → MQTT Password
```

The device stores the hash of the original WiFi setup password. Clients must:
1. Obtain the original WiFi password (from setup process or user)
2. Calculate SHA-512 hash of the password string
3. Base64 encode the hash for MQTT authentication

### Network Security Model
- **Local Network Only**: Devices reject connections from external networks
- **No Encryption**: MQTT traffic is unencrypted (relies on WiFi security)
- **Access Control**: Authentication prevents unauthorized device control
- **Service Isolation**: Each device runs independent MQTT broker

### Discovery Security
- **mDNS Exposure**: Device presence visible to entire local network
- **Serial Exposure**: Device serial numbers visible in service advertisements
- **No Authentication**: mDNS discovery requires no credentials

## Integration Guidelines

### Client Implementation Requirements
To successfully communicate with Dyson vacuums, clients must:

1. **Implement mDNS Discovery**: Scan for appropriate service types
2. **Handle MQTT v3.1**: Use proper MQTT client library with authentication
3. **Process JSON Messages**: Parse device status and format commands correctly
4. **Manage Credentials**: Securely hash and store WiFi passwords
5. **Handle Timeouts**: Implement appropriate timeout and retry logic

### Message Processing Requirements
- **Timestamp Validation**: All messages must include valid ISO8601 timestamps
- **State Validation**: Verify device states before sending commands
- **Error Handling**: Process MQTT return codes and device fault states
- **Connection Management**: Handle disconnections and reconnection logic

### Testing and Validation
- **Network Isolation**: Test behavior when devices are unreachable
- **Authentication Failure**: Verify proper handling of invalid credentials
- **State Conflicts**: Test command rejection during inappropriate states
- **Concurrent Access**: Validate behavior with multiple clients

## Device Capabilities and Limitations

### Supported Operations
✅ **Basic Control**: Start, pause, resume, abort cleaning
✅ **Status Monitoring**: Real-time state and battery information
✅ **Position Tracking**: Global coordinates during operation
✅ **Power Management**: Model-specific suction power levels
✅ **Network Discovery**: Automatic device identification

### Current Limitations
❌ **Zone Configuration**: Cannot define custom cleaning zones via MQTT; likely requires Dyson cloud services
❌ **Schedule Management**: No interface for setting cleaning schedules; likely requires Dyson cloud services
❌ **Map Access**: Floor maps not accessible through MQTT interface; likely requires Dyson cloud services
❌ **Firmware Updates**: No remote firmware update capability known at this time
❌ **Cloud Connectivity**: Devices can operate independently of Dyson cloud services

### Future Protocol Extensions
These capabilities may be available in newer firmware or future models:
- **Advanced Navigation**: Specific room targeting and zone definitions
- **Cleaning Preferences**: Customizable cleaning patterns and intensity
- **Maintenance Alerts**: Proactive notifications for filter replacement
- **Performance Analytics**: Historical cleaning data and efficiency metrics

## Technical Reference

### Standard MQTT Topics
```
# Status Publishing (Device → Client)
{device_type}/{serial}/status

# Command Subscription (Client → Device)
{device_type}/{serial}/command
```

### Message Types
- `CURRENT-STATE` - Complete device status response
- `STATE-CHANGE` - Incremental status update
- `REQUEST-CURRENT-STATE` - Status information request
- `PAUSE` / `RESUME` / `ABORT` - Operation control commands

### Device Type Identifiers
- `N223` - Dyson 360 Eye (first generation)
- `276` - Dyson 360 Heurist (advanced navigation)
- `277` - Dyson 360 Vis Nav (visual navigation)

---

*This protocol documentation is based on analysis of Dyson robot vacuum firmware as of December 2025. Device behavior may vary between firmware versions and models.*
