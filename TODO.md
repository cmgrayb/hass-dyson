# TODO List

## High Priority

- ✅ **Firmware Update Sensors and Controls**: For Cloud-discovered devices, support a configuration switch for auto-update per device, as well as a sensor to notify when a firmware update is available. Both of these are exposed as part of the device response from libdyson-rest.
  - ✅ **Firmware Update Available Binary Sensor**: Shows when updates are available
  - ✅ **Firmware Auto-Update Switch**: Toggle auto-update setting per device
  - ✅ **Cloud-only feature**: Only works with cloud-discovered devices
  - ⚠️ **API Integration**: Update Available Sensor ready for implementation when libdyson-rest provides a working API endpoint

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

## Low Priority

### Testing

- ✅ **Expand code coverage**: **70% coverage achieved (was 36%)**
  - ✅ **Perfect Coverage (100%)**: `const.py`, `entity.py`, `button.py`
  - ✅ **Excellent Coverage (90%+)**: `climate.py` (98%), `binary_sensor.py` (96%), `services.py` (95%), `number.py` (90%)
  - ✅ **Strong Coverage (80%+)**: `fan.py` (86%), `switch.py` (84%), `select.py` (80%)
  - ✅ **Good Coverage (70%+)**: `device_utils.py` (78%), `sensor.py` (76%), `__init__.py` (71%)
  - 🔧 **Infrastructure modules**: `config_flow.py` (59%), `device.py` (51%), `coordinator.py` (42%) - complex network/async code
- ✅ **Integration tests**: Comprehensive integration test scenarios added and validated
