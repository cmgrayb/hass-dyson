# TODO List

## Recent Completions (v0.10.0)

### ✅ Type Safety Improvements (COMPLETED)

- **MyPy Strictness**: Successfully re-enabled ALL strict error codes in pyproject.toml
  - ✅ var-annotated: Fixed variable annotations across all platforms
  - ✅ no-untyped-def: Added function signatures throughout codebase
  - ✅ assignment: Resolved type assignment issues
  - ✅ arg-type: Fixed argument type mismatches
  - ✅ union-attr: Handled Union type attribute access
  - ✅ no-any-return: Eliminated Any return types
  - ✅ no-untyped-call: Added proper function call typing
  - ✅ type-arg: Fixed generic type arguments
  - ✅ unreachable: Removed unreachable code paths
  - ✅ attr-defined: Fixed attribute definition issues
- **Enterprise-level type safety**: Full mypy strict mode compliance achieved

### ✅ Testing Infrastructure (COMPLETED)

- **Comprehensive test suite**: 148 tests covering all major functionality
- **Test coverage**: 25% baseline established with room for improvement
- **Edge case testing**: Extensive binary sensor, entity filtering, and integration scenarios
- **Real device validation**: Tests using actual Dyson device data

### ✅ Dependency Management (COMPLETED)

- **libdyson-rest upgrade**: Successfully upgraded from v0.4.1 → v0.5.0 (production)
- **Enhanced type support**: New version provides comprehensive type annotations
- **Package metadata cleanup**: Removed stale .egg-info directories
- **Version consistency**: All files now reference libdyson-rest==0.5.0

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
- **Performance testing**: Validate performance under load

### Error Handling

- **Capability detection errors**: Handle cases where device capabilities are malformed
- **Missing sensor data**: Graceful handling when expected sensors don't provide data
