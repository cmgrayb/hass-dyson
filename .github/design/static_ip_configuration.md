# Static IP/Hostname Configuration

This file documents the design for allowing users to configure static IP addresses or hostnames for Dyson devices to bypass unreliable mDNS/Zeroconf network discovery.

## Problem Statement

Some home networks have unreliable mDNS/Zeroconf support due to:
- Network equipment that doesn't properly forward multicast traffic
- VLANs or network segregation that blocks mDNS traffic
- Router firmware issues that interfere with service discovery
- WiFi mesh systems that don't properly bridge mDNS
- Container networking (e.g., Docker) that isolates mDNS traffic

Users in these situations currently must use "Cloud Only" connection mode, which sacrifices local control and privacy. A static IP/hostname configuration option allows users to maintain local connectivity while bypassing mDNS discovery.

## User Stories

### Primary Use Case
**As a** user with unreliable mDNS support
**I want to** specify a static IP address or hostname for my Dyson device
**So that** I can use local connectivity without relying on mDNS discovery

### Secondary Use Cases
1. **Network Stability**: Users who want guaranteed, predictable device addressing
2. **Reserved DHCP**: Users who have configured DHCP reservations for their devices
3. **Static IP Assignment**: Users who manually configured static IPs on their Dyson devices
4. **Troubleshooting**: Users debugging connection issues by eliminating mDNS as a variable

## Design Overview

### Configuration Storage

The hostname/IP address will be stored in the config entry data under the existing `CONF_HOSTNAME` key:
- **Key**: `hostname` (already defined in const.py as `CONF_HOSTNAME`)
- **Type**: String (optional)
- **Values**: IP address (e.g., "192.168.1.100") or hostname (e.g., "dyson-fan.local" or "my-dyson")
- **Default**: Empty string (triggers automatic discovery)

### Configuration Locations

The hostname field will be added to the connection type configuration step in two flows:

#### 1. Manual Device Setup Flow
**Current State**: Already has optional hostname field on device info screen with hardcoded LOCAL_ONLY connection type
**Enhancement**: None needed - manual devices already support static IP/hostname configuration
**User Path**: Home Assistant → Settings → Devices & Services → Add Integration → Dyson → Manual Device Setup
**Note**: This flow already works as desired and requires no changes

#### 2. Cloud Device Discovery Confirmation Flow
**Current State**: No hostname field exists; connection type defaults to account setting
**Enhancement**: Add hostname field to connection type selection during cloud device discovery confirmation
**User Path**:
- **Automatic Discovery + Manual Confirmation**: Home Assistant → Notifications → Configure Dyson Integration → Connection Settings
- **Manual Cloud Account Setup**: After entering cloud credentials → Select devices → Configure device → Connection Settings

#### 3. Device Reconfiguration (Options Flow)
**Current State**: No hostname field in device options
**Enhancement**: Add hostname field to device connection reconfiguration
**User Path**: Home Assistant → Settings → Devices & Services → Dyson Integration → Configure (on device entry) → Connection Settings
**Applies To**: All device types (cloud-discovered and manually added)

### UI/UX Design

#### Field Properties
- **Label**: "IP Address or Hostname (Optional)"
- **Type**: Text input (no validation)
- **Required**: No (optional field)
- **Default**: Empty string
- **Help Text**: "Leave blank for automatic mDNS discovery. For local connections only - not used with Cloud Only mode."

#### Field Placement
- **Location**: On the connection type configuration screen
- **Position**: Below the connection type selector dropdown
- **Visibility**: Always visible (shown for all connection types)
- **Conditional Text**: When "Cloud Only" is selected, help text emphasizes field is not used for that mode

#### Form Schema Example
```python
vol.Schema({
    vol.Required("connection_type", default="local_cloud_fallback"): vol.In(
        _get_connection_type_options_detailed()
    ),
    vol.Optional(CONF_HOSTNAME, description="Leave blank for automatic discovery"): str,
})
```

### Connection Behavior

#### Hostname Resolution Priority
When establishing a local connection, the integration will use this priority order:

1. **User-provided hostname/IP** (if configured in `CONF_HOSTNAME`)
   - Use exactly as provided by user
   - Skip mDNS discovery entirely
   - Proceed directly to connection attempt

2. **mDNS discovery** (if hostname field is empty)
   - Attempt automatic discovery via `_discover_device_via_mdns()`
   - Use discovered IP if found

3. **Fallback to serial.local** (if mDNS fails and no hostname provided)
   - Use `{serial_number}.local` as last resort
   - Allows DNS-based resolution as fallback

#### Connection Testing
- **Validation**: No format validation during form submission
- **Testing**: Connection testing occurs during actual device connection (not during config flow)
- **Error Handling**: If connection fails with provided hostname, normal fallback behavior applies based on connection type
- **User Feedback**: Connection failures logged with clear indication of which hostname was attempted

#### Connection Type Interactions

| Connection Type | Hostname Usage | Behavior |
|----------------|----------------|----------|
| **Local Only** | Used for local connection | Hostname required if mDNS unreliable; connection fails if unreachable |
| **Local with Cloud Fallback** | Used for initial local connection | If hostname connection fails, fallback to cloud MQTT |
| **Cloud with Local Fallback** | Used when falling back to local | If cloud fails, attempts local connection with provided hostname |
| **Cloud Only** | Not used | Hostname ignored; only cloud MQTT used; field shown but marked as unused |

### Reconfiguration Flow

#### Viewing Current Configuration
The device reconfiguration form will display:
- Current connection type selection
- Current hostname value (if any)
- Empty field if no hostname configured (indicates automatic discovery mode)

#### Modifying Configuration
Users can:
1. **Add hostname**: Enter IP/hostname in previously empty field
2. **Change hostname**: Update existing value to new IP/hostname
3. **Remove hostname**: Clear field to return to automatic mDNS discovery
4. **Change connection type**: Update connection type independently of hostname

#### Testing Changes
After reconfiguration:
1. Config entry updated with new values
2. Device coordinator reloaded
3. New connection attempt using updated settings
4. Connection status reflected in connection status sensor
5. Errors logged if connection fails with new settings

### Implementation Details

#### Config Flow Changes

##### New Helper Function
```python
def _show_connection_type_form_with_hostname(
    step_id: str,
    current_connection_type: str,
    current_hostname: str = "",
    errors: dict[str, str] | None = None,
    description_placeholders: dict[str, str] | None = None,
) -> ConfigFlowResult:
    """Show connection type selection form with hostname field."""
    return self.async_show_form(
        step_id=step_id,
        data_schema=vol.Schema({
            vol.Required("connection_type", default=current_connection_type): vol.In(
                _get_connection_type_options_detailed()
            ),
            vol.Optional(CONF_HOSTNAME, default=current_hostname,
                        description="Leave blank for automatic discovery"): str,
        }),
        errors=errors or {},
        description_placeholders=description_placeholders or {},
    )
```

##### Modified Steps

**1. Manual Device Setup** (`async_step_manual_device`)
- **No changes needed** - already has hostname field and works correctly with LOCAL_ONLY
- Current form includes all needed fields: serial, credential, mqtt_prefix, hostname (optional)
- Connection type is hardcoded to LOCAL_ONLY which is appropriate for manual setup

**2. Cloud Discovery Confirmation** (`async_step_discovery_confirm`)
- Add connection type and hostname selection after user confirms device
- Add `async_step_discovery_connection` step
- Update flow: discovery → confirmation → connection_settings → create_entry
- Store hostname in device config alongside connection_type

**3. Device Reconfiguration** (`async_step_device_reconfigure_connection`)
- Add hostname field to existing connection type reconfiguration form
- Display current hostname value (empty if not configured)
- Allow clearing hostname by submitting empty string
- Update flow: options → reconfigure_connection (with hostname) → save & reload
- Works for all device types: cloud-discovered, manually added, and sticker/WiFi-discovered

#### Coordinator Changes

##### Hostname Resolution in `_async_setup_manual_device`
**No changes needed** - Manual devices already properly handle hostname:
- User provides hostname on device setup form
- If provided, used directly
- If empty, attempts mDNS discovery via `_resolve_device_hostname()`
- Falls back to `{serial}.local` if mDNS fails
- This existing logic is exactly what we want

##### Hostname Resolution in `_async_setup_cloud_device`
Update to check for user-provided hostname before attempting mDNS:

```python
# Get hostname for local connection
hostname = self.config_entry.data.get(CONF_HOSTNAME, "").strip()

if hostname:
    # Use user-provided hostname/IP - skip mDNS discovery
    _LOGGER.info(
        "Using configured hostname for device %s: %s",
        self.serial_number,
        hostname
    )
else:
    # Attempt mDNS discovery
    _LOGGER.debug(
        "No hostname configured, attempting mDNS discovery for device %s",
        self.serial_number
    )
    hostname = await self._discover_via_mdns()

    if not hostname:
        # Fallback to serial.local
        hostname = f"{self.serial_number}.local"
        _LOGGER.warning(
            "mDNS discovery failed, using fallback: %s", hostname
        )
```

#### Device Class Changes

The `DysonDevice` class in `device.py` requires no changes. It already accepts hostname as a parameter and uses it for connection attempts.

### Testing Strategy

#### Unit Tests

**Test Coverage Required**:
1. **Form Display (Cloud Discovery)**
   - Hostname field appears on cloud device connection type form
   - Default value is empty string
   - Help text correctly displayed
   - Field shown for all connection types

2. **Configuration Storage (Cloud Devices)**
   - Hostname saved to config entry when provided during cloud discovery
   - Empty string stored when field left blank
   - Hostname retrieved correctly during device setup

3. **Hostname Resolution Logic (Cloud Devices)**
   - User-provided hostname used when configured
   - mDNS discovery skipped when hostname provided
   - mDNS discovery attempted when hostname empty
   - Fallback to serial.local when mDNS fails and no hostname

4. **Manual Device Hostname (Existing Behavior)**
   - Manual device hostname field works as expected (no regression)
   - Manual devices continue using LOCAL_ONLY connection type
   - Manual device hostname resolution logic unchanged

5. **Reconfiguration**
   - Current hostname displayed in reconfiguration form
   - Hostname can be added to existing config (cloud and manual devices)
   - Hostname can be removed (set to empty)
   - Hostname can be changed to new value
   - Works for all device types

6. **Connection Type Interactions (Cloud Devices)**
   - Local Only uses hostname correctly
   - Cloud fallback works with hostname
   - Cloud Only ignores hostname appropriately

#### Integration Tests

**Test Scenarios**:
1. **Manual Device with Static IP (Verify Existing Behavior)**
   - Add manual device with IP address
   - Verify connection uses provided IP
   - Verify no mDNS discovery attempted
   - Verify no regressions in existing manual device flow

2. **Cloud Device with Static IP**
   - Add cloud device with discovered info
   - Configure static IP during connection setup step
   - Verify local connection uses static IP
   - Verify mDNS discovery bypassed

3. **Cloud Device without Static IP**
   - Add cloud device with discovered info
   - Leave hostname field empty during connection setup
   - Verify mDNS discovery attempted
   - Verify fallback behavior works

4. **Reconfiguration with Hostname Change (Cloud Device)**
   - Add cloud device without hostname (mDNS mode)
   - Reconfigure to add static IP
   - Verify new connection uses static IP

5. **Reconfiguration Removing Hostname (Cloud Device)**
   - Add cloud device with static IP
   - Reconfigure to remove IP (clear field)
   - Verify connection switches to mDNS discovery

6. **Connection Type Changes with Hostname**
   - Configure cloud device with hostname and Local Only
   - Change to Cloud with Local Fallback
   - Verify hostname still used for local connection attempts

#### Manual Testing Checklist

- [ ] Manual device setup continues to work as expected (no regression)
- [ ] Manual device hostname field functions correctly (existing behavior)
- [ ] Cloud discovery confirmation shows hostname field on connection screen
- [ ] Cloud device connection setup includes hostname option
- [ ] Device reconfiguration shows hostname field with current value (all device types)
- [ ] Empty hostname field triggers mDNS discovery
- [ ] Provided hostname bypasses mDNS discovery
- [ ] Invalid hostname logs clear error message
- [ ] Cloud Only mode shows but ignores hostname
- [ ] Reconfiguration clears hostname when field emptied
- [ ] Connection status sensor reflects correct connection method
- [ ] Device connectivity works with static IP when mDNS disabled
- [ ] Manual devices continue using LOCAL_ONLY (no connection type UI for manual)

### User Documentation Updates

#### Files to Update

1. **docs/SETUP.md**
   - Add section on static IP configuration
   - Document when to use hostname override
   - Provide examples of valid hostname formats

2. **docs/TROUBLESHOOTING.md**
   - Add troubleshooting steps for mDNS issues
   - Document hostname override as solution
   - Explain how to find device IP address

3. **docs/DEVICE_MANAGEMENT.md**
   - Document reconfiguration of hostname
   - Explain switching between mDNS and static IP
   - Describe connection testing after changes

4. **README.md**
   - Add mention of static IP support in features list

#### Documentation Content Guidelines

**When to Use Static IP**:
- mDNS discovery consistently fails
- Device has DHCP reservation or static IP
- Network segregation blocks mDNS
- Prefer predictable device addressing

**How to Find Device IP**:
- Check router's DHCP client list
- Use Dyson mobile app (if available)
- Use network scanning tools
- Check Home Assistant network device discovery

**Hostname Formats**:
- IPv4 address: `192.168.1.100`
- Hostname: `dyson-fan`
- FQDN: `dyson-fan.local` or `dyson-fan.mydomain.com`
- Do not include http:// or any URL scheme

### Future Enhancements

#### Nice-to-Have Features (Not in Initial Implementation)
1. **IP Address Validation**: Add optional format validation for IP addresses (not hostnames)
2. **Connection Testing Button**: Add "Test Connection" button in config flow to verify before saving
3. **Auto-discover Current IP**: Button to run one-time mDNS discovery and populate field
4. **Multiple IP Fallbacks**: Allow specifying multiple IPs to try in sequence
5. **Hostname Resolution Test**: Show resolved IP from hostname during configuration

#### Backward Compatibility
- Existing devices without hostname continue using mDNS discovery
- No migration needed - hostname is optional field
- Empty hostname field maintains current behavior
- Existing manual devices already use hostname if configured

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Device Configuration                     │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Connection Type Selection Step                        │ │
│  │                                                         │ │
│  │  [X] Connection Type: [Local with Cloud Fallback ▼]   │ │
│  │                                                         │ │
│  │  IP Address or Hostname (Optional):                    │ │
│  │  [ 192.168.1.100                    ]                 │ │
│  │                                                         │ │
│  │  ℹ️  Leave blank for automatic mDNS discovery          │ │
│  │     For local connections only                         │ │
│  │                                                         │ │
│  │              [Cancel]  [Next]                          │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│                            ↓                                 │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Device Setup Logic                                     │ │
│  │                                                         │ │
│  │  if hostname_configured:                               │ │
│  │      use_hostname()                                    │ │
│  │  else:                                                  │ │
│  │      try_mdns_discovery()                              │ │
│  │      if not found:                                      │ │
│  │          use_serial_local_fallback()                   │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│                            ↓                                 │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Connection Attempt                                     │ │
│  │                                                         │ │
│  │  Based on Connection Type:                             │ │
│  │  • Local Only → hostname (fails if unreachable)        │ │
│  │  • Local+Cloud → hostname then cloud MQTT              │ │
│  │  • Cloud+Local → cloud MQTT then hostname              │ │
│  │  • Cloud Only → cloud MQTT (hostname ignored)          │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Checklist

### Phase 1: Core Implementation
- [ ] Add connection type selection step to cloud device discovery flow
- [ ] Add hostname field to cloud discovery connection type screen
- [ ] Add hostname field to device reconfiguration screen (all device types)
- [ ] Update coordinator hostname resolution logic for cloud devices
- [ ] Store hostname in config entry data for cloud-discovered devices
- [ ] Log hostname usage in connection attempts
- [ ] Verify manual device flow unchanged (no regression)

### Phase 2: Testing
- [ ] Write unit tests for cloud discovery form display
- [ ] Write unit tests for hostname resolution logic (cloud devices)
- [ ] Write unit tests for reconfiguration (all device types)
- [ ] Write regression tests for manual device flow
- [ ] Write integration tests for cloud device with hostname
- [ ] Write integration tests for hostname reconfiguration
- [ ] Manual testing with real devices

### Phase 3: Documentation
- [ ] Update SETUP.md with static IP configuration
- [ ] Update TROUBLESHOOTING.md with mDNS solutions
- [ ] Update DEVICE_MANAGEMENT.md with reconfiguration steps
- [ ] Update README.md with feature mention
- [ ] Add inline code comments for hostname resolution
- [ ] Create user-facing configuration examples

### Phase 4: Review & Polish
- [ ] Code review for implementation
- [ ] UX review for form layouts
- [ ] Documentation review for clarity
- [ ] Test all connection type combinations
- [ ] Verify backward compatibility
- [ ] Check error messages are user-friendly

## Success Criteria

The feature will be considered successful when:

1. **Functionality**
   - Users can configure static IP/hostname in all three flows
   - Hostname correctly bypasses mDNS discovery when provided
   - Empty hostname correctly triggers mDNS discovery
   - Hostname can be added, changed, and removed via reconfiguration
   - Connection fallback behavior works correctly with hostname

2. **Usability**
   - Forms are intuitive and well-labeled
   - Help text clearly explains when to use the field
   - Error messages provide actionable guidance
   - Documentation provides clear examples

3. **Reliability**
   - All automated tests pass
   - Manual testing confirms expected behavior
   - No regressions in existing functionality
   - Backward compatibility maintained

4. **User Satisfaction**
   - Users with mDNS issues can successfully connect devices
   - Feature solves the reported problem
   - No additional complexity for users who don't need it
