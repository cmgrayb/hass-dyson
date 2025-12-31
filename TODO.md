# TO DO

## Completed Items

### Device Connectivity Filtering (December 29, 2025) ✓

**Issue**: Users were experiencing errors with non-MQTT devices in their accounts that don't support standard connectivity.

**Root Cause**: Some devices in Dyson accounts use connectivity types like `lecOnly` that are not yet supported by the integration.

**Solution**:
- Updated libdyson-rest from 0.10.0 to 0.11.0b2 (handles device discovery without errors)
- Implemented selective device filtering - **only** filters out `lecOnly` devices
- Allows devices with missing/None connectivity (most existing devices work this way)
- Added informational logging for unsupported devices with future support indication
- Enhanced error messages for cases where no supported devices are found
- Comprehensive testing for device filtering logic

**Technical Implementation**:
- **Approach**: Blacklist-based filtering instead of whitelist
- **Filtered Out**: Only devices with `connection_category == 'lecOnly'`
- **Allowed Through**: All other devices including None, 'wifiOnly', 'lecAndWifi', etc.
- **Rationale**: Most existing working devices don't have a connection_category attribute

**Files Changed**:
- requirements.txt: Updated libdyson-rest version
- pyproject.toml: Updated libdyson-rest version
- config_flow.py: Added selective device filtering logic
- Updated comprehensive tests for device filtering

**Supported Connectivity Types**:
- `None` (missing attribute): Most existing devices - **SUPPORTED**
- `wifiOnly`: WiFi-only devices - **SUPPORTED**
- `lecAndWifi`: Devices with both local electrical connection and WiFi - **SUPPORTED**
- `lecOnly`: Local electrical connection only devices - **FILTERED OUT** (planned future support)

**Testing**: All 1,501 tests pass, including new comprehensive device filtering tests.
Migrate from `pytest-homeassistant-custom-component` to pure pytest with custom fixtures.

### Background
Current plugin has issues with:
- Event loop cleanup causing test instability
- Plugin conflicts with other pytest plugins
- Version coupling requiring exact HA version matching
- Limited control over testing infrastructure
- Frequent breakage due to HA core changes

### Migration Plan
1. **Phase 1** (1-2 weeks): Create custom `conftest.py` with pure pytest fixtures
2. **Phase 2** (2-4 weeks): Migrate all test files to custom infrastructure
3. **Phase 3** (1-2 weeks): Remove plugin dependency and optimize performance

### Benefits
- Full control over testing environment
- Better performance (no plugin overhead)
- Easier debugging of test failures
- Version independence from plugin updates
- Custom mock strategies tailored to project needs

### Implementation Notes
- Follow patterns used by major HA projects (HACS, ESPHome)
- Use direct Home Assistant test utilities: `homeassistant[test]`
- Implement custom `MockConfigEntry` and essential test helpers
- Add snapshot testing with syrupy for state validation

## Add Robot Vacuum Support

**Priority**: Medium
**Estimated Effort**: 3-4 weeks

Add support for Dyson robot vacuum cleaners using API-based device identification rather than sticker-hashed connection method.

### Supported Models
Based on `.github/design/vacuums.md` documentation:
- **360 Eye** (`N223`) - First-generation robot vacuum with 360° camera navigation
- **360 Heurist** (`276`) - Advanced robot vacuum with improved navigation and zone control
- **360 Vis Nav** (`277`) - Latest model with enhanced visual navigation and mapping

### Implementation Strategy
Use robot device category from Dyson API for device identification instead of requiring sticker-hashed MQTT connection method.

### Key Features to Implement
1. **Device Discovery**: API-based robot vacuum detection and setup
2. **Basic Controls**: Start, pause, resume, abort cleaning operations
3. **Status Monitoring**: Real-time state, battery level, and position tracking
4. **Power Management**: Model-specific suction power levels
5. **Cleaning Modes**: Support for immediate, scheduled, and zone-based cleaning

### Technical Requirements
- Extend existing coordinator for robot vacuum MQTT communication
- Add vacuum platform entity with Home Assistant vacuum domain
- Implement device-specific capabilities (power levels vary by model)
- Handle robot-specific operational states (cleaning, docking, mapping, faults)
- Add position tracking and cleaning session management

### Integration Points
- Leverage existing MQTT infrastructure in coordinator
- Extend device utilities for robot-specific device information
- Add robot vacuum services for advanced controls
- Implement proper error handling for navigation and hardware faults

### Testing Strategy
- Mock robot vacuum MQTT communication patterns
- Test state transitions for cleaning, charging, and error conditions
- Validate model-specific power level controls
- Test concurrent MQTT connection limitations (1-2 clients max)
