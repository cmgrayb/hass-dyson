# TODO List

## Recent Changes

- ✅ **Firmware Update Sensors and Controls**: For Cloud-discovered devices, support a configuration switch for auto-update per device, as well as a sensor to notify when a firmware update is available. Both of these are exposed as part of the device response from libdyson-rest.
  - ✅ **Firmware Update Available Binary Sensor**: Shows when updates are available
  - ✅ **Firmware Auto-Update Switch**: Toggle auto-update setting per device
  - ✅ **Cloud-only feature**: Only works with cloud-discovered devices

## Medium Priority

### Carbon Filter Support

- **Identify formaldehyde capability name**: Currently commented out pending real device testing
- **Add carbon filter sensors**: Life and type sensors for formaldehyde-capable devices
- **Files to update**: `sensor.py` - uncomment and implement carbon filter sensors

### Robot Device Support

- **Add battery sensor**: For robot/vacuum devices
- **Implement robot-specific entities**: Based on device category filtering
- **Files to update**: `sensor.py`, potentially new platform files

### Humidity Support

- **Identify humidifier capability name**: Currently commented out pending real device testing
- **Add humidity sensor**: For humidifier-capable devices
- **Files to update**: `sensor.py` - uncomment and implement humidity sensor

### Firmware Update Available Sensor

- ⚠️ **API Integration**: Update Available Sensor ready for implementation when libdyson-rest provides a working API endpoint
- **Home Assistant UpdateEntity Support**: Continue driving toward supporting Home Assistant's built-in UpdateEntity system

## Low Priority

### Testing

- ✅ **Expand code coverage**: **72% coverage achieved (was 36%)**
  - ✅ **Perfect Coverage (100%)**: `const.py`, `entity.py`, `button.py`
  - ✅ **Excellent Coverage (90%+)**: `climate.py` (98%), `binary_sensor.py` (96%), `services.py` (95%), `number.py` (90%)
  - ✅ **Strong Coverage (80%+)**: `fan.py` (86%), `sensor.py` (84%), `switch.py` (81%), `select.py` (80%), `device_utils.py` (78%)
  - ✅ **Good Coverage (70%+)**: `__init__.py` (71%)
  - 🔧 **Infrastructure modules**: **Significantly improved!** `config_flow.py` (61%), `device.py` (56%), `coordinator.py` (41%)
- ✅ **Test suite stability**: **732 passing tests** with clean execution (fixed zeroconf patching and async mock issues)
- ✅ **Integration tests**: Comprehensive integration test scenarios added and validated
- ✅ **MQTT API v2 Migration**: Upgraded from paho-mqtt v1 to v2 with performance improvements and thread-safe async operations
- ✅ **RuntimeWarnings**: Reduced to minimal async mock warnings in test environment only
