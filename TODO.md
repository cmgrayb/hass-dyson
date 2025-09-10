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

### Testing & Coverage Enhancement

- ✅ **Phase 1 & 2 Success**: **73% coverage achieved (from 36% baseline)** - **+37 percentage points improvement!**
  - ✅ **Perfect Coverage (100%)**: `const.py`, `entity.py`, `button.py`, `update.py`
  - ✅ **Excellent Coverage (95%+)**: `switch.py` (95%), `climate.py` (96%), `binary_sensor.py` (99%)
  - ✅ **Strong Coverage (85%+)**: `services.py` (93%), `number.py` (91%), `fan.py` (90%), `device_utils.py` (89%), `sensor.py` (87%)
  - ✅ **Good Coverage (75%+)**: `__init__.py` (78%), `select.py` (76%)
  - 🔧 **Infrastructure modules**: `config_flow.py` (58%), `device.py` (56%), `coordinator.py` (44%)

- 🎯 **Phase 3 Plan - Target: 80% Overall Coverage** (Need +215 statements)
  - **Phase 3a - High-ROI Quick Wins** (~65 statements):
    - 🎯 **sensor.py**: 87% → 95% (+48 statements) - Error handling, edge cases
    - 🎯 **fan.py**: 90% → 98% (+15 statements) - Oscillation modes, speed validation  
    - 🎯 **number.py**: 91% → 98% (+16 statements) - Range validation, error cases
    - 🎯 **device_utils.py**: 89% → 98% (+14 statements) - Config creation edge cases
  - **Phase 3b - Strategic Infrastructure** (~150 statements):
    - 🎯 **coordinator.py**: 44% → 70% (+153 statements) - Connection handling, state updates
    - 🎯 **select.py**: 76% → 85% (+26 statements) - Option validation, state changes
    - 🎯 **__init__.py**: 78% → 90% (+22 statements) - Setup error paths, service management

- ✅ **Test Infrastructure Excellence**: 
  - **893 passing tests** (100% success rate for CI/CD pipelines)
  - **Comprehensive coverage patterns** established for all module types
  - **Stable async test framework** with proper Home Assistant mocking
  - **Phase 1-2 achievements**: +44 percentage points across 4 critical modules

### Coverage Enhancement Strategic Plan

#### **Immediate Phase 3a Targets (Low Risk, High ROI)**
- **sensor.py** (87% → 95%): Focus on error handling in value conversion, missing sensor states
- **fan.py** (90% → 98%): Cover oscillation mode edge cases, speed validation errors  
- **number.py** (91% → 98%): Range boundary validation, invalid value handling
- **device_utils.py** (89% → 98%): Cloud device config creation error paths

#### **Phase 3b Infrastructure Enhancement (Moderate Risk)**
- **coordinator.py** (44% → 70%): 
  - Connection retry logic and error handling
  - State update mechanisms and data validation
  - MQTT message processing edge cases
  - Device availability detection patterns
- **select.py** (76% → 85%): Option validation, state transition error handling
- **__init__.py** (78% → 90%): Platform setup error paths, service lifecycle management

#### **Future Phases (Advanced - 85%+ Goal)**
- **config_flow.py**: UI flow comprehensive testing (authentication, discovery, validation)
- **device.py**: Advanced device state management, complex MQTT scenarios
- **coordinator.py**: Full async lifecycle, advanced error recovery patterns

#### **Implementation Methodology**
- **Proven Patterns**: Use successful Phase 1-2 enhancement techniques
- **Pipeline Safety**: Maintain 100% test pass rate for CI/CD quality gates
- **Incremental Approach**: Target 2-3 modules per phase for manageable scope
- **Coverage Analysis**: Use `--cov-report=term-missing` to identify specific missing lines
- **Test Design**: Focus on exercising code paths rather than complex behavior mocking
- **Quality Metrics**: Track both coverage percentage and test reliability

#### **Success Criteria**
- **80% Overall Coverage**: Primary target requiring +215 statements
- **95%+ High-Value Modules**: sensor.py, fan.py, number.py, device_utils.py
- **70%+ Infrastructure**: coordinator.py as foundation for advanced features
- **Zero Pipeline Impact**: Maintain perfect test success rate throughout

#### **Current Baseline (Phase 2 Complete)**
```
Total Statements: 4,379 | Missing: 1,091 | Current: 73%
Target 80%: Need +215 statements | Pipeline: 893/893 tests passing

Module Priorities by Missing Statements:
coordinator.py:  310 missing (44% coverage) - Major infrastructure target  
device.py:       339 missing (56% coverage) - Complex device management
config_flow.py:  198 missing (58% coverage) - UI flows
sensor.py:        61 missing (87% coverage) - High-ROI quick win
select.py:        60 missing (76% coverage) - Control validation  
__init__.py:      39 missing (78% coverage) - Platform setup
number.py:        21 missing (91% coverage) - Range validation
device_utils.py:  18 missing (89% coverage) - Config utilities
fan.py:           17 missing (90% coverage) - Fan control logic
```
