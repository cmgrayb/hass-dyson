# TODO List

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
- **Add unit tests**: For entity filtering logic
- **Device capability testing**: Test with real devices of different categories
- **Integration tests**: Verify correct entities are created for different device configurations

## Code Quality

### Type Safety
- **Review entity type hints**: Ensure all new entities have proper type annotations
- **Update coordinator types**: Verify device capability types are properly defined

### Error Handling
- **Capability detection errors**: Handle cases where device capabilities are malformed
- **Missing sensor data**: Graceful handling when expected sensors don't provide data
