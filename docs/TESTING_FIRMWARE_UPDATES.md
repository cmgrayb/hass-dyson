# Firmware Update Testing Guide

## Prerequisites

1. **Updated Dependencies**: The integration now uses `libdyson-rest==0.6.0b1` which includes firmware update support.

2. **Environment Setup**: 
   ```bash
   # If testing with real credentials
   export DYSON_EMAIL="your.email@example.com" 
   export DYSON_PASSWORD="your_dyson_password"
   export DYSON_DEVICE_SERIAL="9RJ-US-UAA8845A"  # Your device serial
   ```

## Testing Steps

### 1. Library Verification
Run the included test script to verify the library is working:
```bash
python test_firmware_update.py
```

Expected output:
```
✅ get_pending_release method is available
📋 Method signature: get_pending_release(serial_number: str) -> libdyson_rest.models.device.PendingRelease
```

### 2. Integration Testing
```bash
# Test basic imports
python -c "
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
from custom_components.hass_dyson.update import DysonFirmwareUpdateEntity
print('✅ Integration compatible with libdyson-rest 0.6.0b1')
"

# Run unit tests
python -m pytest tests/test_basic.py -v
python -m pytest tests/test_coordinator.py::TestDysonDataUpdateCoordinatorInit::test_properties -v
```

### 3. Manual Testing with Home Assistant

#### Setup Steps:
1. Copy the `custom_components/hass_dyson` folder to your Home Assistant `custom_components` directory
2. Ensure you have `libdyson-rest==0.6.0b1` installed in your HA environment
3. Add a Dyson device via cloud discovery
4. The update platform should automatically be available

#### Expected Entities:
- **Update Entity**: `update.dyson_[serial]_firmware` 
- **Properties**:
  - `installed_version`: Current firmware version from device
  - `latest_version`: Available firmware version (if any)
  - `in_progress`: Whether update is currently running
  - `supported_features`: `INSTALL` if cloud device

#### Testing Firmware Updates:
1. **Check for Updates**: The coordinator automatically checks for firmware updates during setup
2. **Manual Check**: Call the service or use the `async_check_firmware_update()` method
3. **Install Update**: Use the update entity's install button or call `async_install_firmware_update()`

### 4. MQTT Command Verification

When a firmware update is triggered, you should see an MQTT command like:
```json
{
  "msg": "SOFTWARE-UPGRADE",
  "time": "2025-09-09T19:52:58.573Z", 
  "version": "438MPF.00.01.007.0002",
  "url": "http://ota-firmware.cp.dyson.com/438/M__SC04.WF02/438MPF.00.01.007.0002/manifest.bin"
}
```

The device type (e.g., `438`) is now dynamically extracted from the API response.

### 5. Device Type Extraction Testing

The integration now requires the device type to be available from the API. Test edge cases:

#### For Cloud Devices:
- Device type extracted from `product_type` or `type` field
- If neither available, setup should fail with clear error message

#### For Manual Devices:
- Device type must be provided in config entry
- No fallback to default values

### 6. Error Scenarios to Test

1. **Missing Device Type**: Should raise `ValueError` with clear message
2. **API Unavailable**: Should gracefully handle `DysonAPIError`
3. **No Updates Available**: Should log appropriately and set latest_version = installed_version
4. **MQTT Command Failure**: Should mark update as failed and log error

## Expected Behavior

### Successful Firmware Update Flow:
1. Device setup extracts correct device type from API
2. Initial firmware check during coordinator setup
3. Update entity shows available firmware if any
4. User triggers update via UI
5. MQTT SOFTWARE-UPGRADE command sent with correct URL
6. Device begins firmware update process
7. Update entity shows "in_progress" state

### Error Handling:
- Clear error messages for missing device types
- Graceful handling of API errors
- Proper logging for debugging
- No crashes during error scenarios

## Rollback Instructions

If issues occur, you can rollback:
```bash
pip install libdyson-rest==0.5.0
# Remove the update.py platform registration from __init__.py
# Remove firmware-related properties from coordinator.py
```

## Monitoring and Debugging

Enable debug logging in Home Assistant:
```yaml
logger:
  logs:
    custom_components.hass_dyson: debug
    libdyson_rest: debug
```

Check logs for:
- Device type extraction messages
- Firmware update check results  
- MQTT command success/failure
- Error handling scenarios
