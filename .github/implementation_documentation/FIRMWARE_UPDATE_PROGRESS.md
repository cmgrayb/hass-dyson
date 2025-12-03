# Dyson Firmware Update Progress Tracking

## Overview

The Dyson integration uses a two-phase approach for firmware updates:

1. **Trigger**: Cloud API call using `trigger_firmware_update()`
2. **Progress Monitoring**: MQTT status messages (partially implemented)

## Implementation Status

### ✅ Completed
- Cloud API trigger via `libdyson-rest==0.9.0b1`
- Basic progress tracking with `_firmware_update_in_progress` flag
- Update entity with proper installation workflow
- Only cloud-discovered devices can receive updates

### 🔄 Pending Implementation
- MQTT progress message parsing (missing JSON key)

## MQTT Progress Messages

### Topic Structure
```
{mqtt_root}/{serial_number}/status/software
```

**Example**: `438M/9RJ-US-UAANNNNA/status/software`

### Known Status Values
From observed firmware update process:

| Status | Meaning | Action Required |
|--------|---------|-----------------|
| `"acknowledged"` | Download started | Keep `_firmware_update_in_progress = True` |
| `"downloaded"` | Installation started | Keep `_firmware_update_in_progress = True` |
| *Unknown* | Update completed | Set `_firmware_update_in_progress = False` |
| *Unknown* | Update failed | Set `_firmware_update_in_progress = False` |

### Missing Information
- **JSON Key**: The key that contains the status values (e.g., `"status"`, `"state"`, `"update_status"`)
- **Completion Values**: Status values for successful completion
- **Failure Values**: Status values for update failures
- **Full Message Structure**: Complete JSON structure of status messages

### Expected Message Format
```json
{
  "unknown_key": "acknowledged|downloaded|completed|failed",
  "timestamp": "2025-01-01T12:00:00Z",
  "version": "438MPF.00.01.004.0001",
  "other_fields": "..."
}
```

## Implementation Plan

### Phase 1: Data Collection ✅
- [x] Implement cloud API trigger
- [x] Add MQTT message handler framework
- [x] Document known information

### Phase 2: Progress Monitoring (Pending)
- [ ] Capture complete MQTT message during next firmware update
- [ ] Identify missing JSON key
- [ ] Implement status parsing in `_handle_firmware_update_status()`
- [ ] Test with real firmware update

### Phase 3: Enhancement (Future)
- [ ] Add progress percentage if available
- [ ] Add estimated completion time
- [ ] Add detailed error reporting
- [ ] Add update success confirmation

## Code Locations

### Primary Implementation
- `custom_components/hass_dyson/coordinator.py`
  - `async_install_firmware_update()`: Cloud API trigger
  - `_handle_firmware_update_status()`: MQTT message handler (placeholder)
  - `firmware_update_in_progress`: Property for current status

### Update Entity
- `custom_components/hass_dyson/update.py`
  - `DysonFirmwareUpdateEntity`: Home Assistant update entity
  - `async_install()`: User-facing update method

## Testing Strategy

### Manual Testing
1. Wait for firmware update availability
2. Enable debug logging for MQTT messages
3. Trigger update via Home Assistant
4. Capture complete MQTT messages
5. Extract missing JSON key
6. Implement parsing logic

### Debug Logging
```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.hass_dyson.coordinator: debug
    custom_components.hass_dyson.update: debug
```

## Security Considerations

- Firmware updates only available for cloud-discovered devices
- No direct MQTT command injection (read-only status monitoring)
- Progress status doesn't contain sensitive information
- Update trigger requires valid cloud authentication

## Error Handling

- Network failures during status monitoring
- Invalid/malformed status messages  
- Update timeouts (device restart scenarios)
- Cloud API failures vs. MQTT status conflicts

---

**Last Updated**: November 19, 2025
**Status**: Awaiting next firmware update for data collection
**Next Action**: Capture complete MQTT message structure
