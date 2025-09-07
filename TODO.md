# TODO List

## Recent Completions (v0.11.0)

### ✅ Scene Support (COMPLETED)

- **Complete scene support**: All settable device properties now exposed as `extra_state_attributes` across all entity platforms
- **Comprehensive coverage**: Fan, climate, switch, select, and number entities all expose device state for scene capture
- **Device control methods**: All major device properties (fan speed, oscillation, heating, timers) can be set and restored via scenes
- **Testing validation**: 9 test classes with comprehensive scene support validation
- **Documentation**: Complete implementation guide in `docs/SCENE_SUPPORT_IMPLEMENTATION.md`

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

- **Expand code coverage**: Target 80% coverage for custom_components files
- **Integration tests**: Add more integration test scenarios
