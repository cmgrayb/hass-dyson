# TODO List

## Recent Completions (v0.11.1)

### ✅ Code Coverage Improvements (COMPLETED)

**Overall Coverage: 70% (+34% improvement from 36%)**

**Perfect Coverage Modules (100%):**
- ✅ `const.py`: 100% - constants validation
- ✅ `entity.py`: 100% - base entity functionality  
- ✅ `button.py`: 100% - button platform coverage

**Excellent Coverage Modules (90%+):**
- ✅ `climate.py`: 98% - climate entity platform
- ✅ `binary_sensor.py`: 96% - binary sensor platform 
- ✅ `services.py`: 95% - service handlers and schemas
- ✅ `number.py`: 90% - number entity platform

**Strong Coverage Modules (80%+):**
- ✅ `fan.py`: 86% - fan entity platform
- ✅ `switch.py`: 84% - switch entity platform
- ✅ `select.py`: 80% - select entity platform

**Good Coverage Modules (70%+):**
- ✅ `device_utils.py`: 78% - device utility functions
- ✅ `sensor.py`: 76% - sensor platform
- ✅ `__init__.py`: 71% - integration initialization

**Core Infrastructure Modules:**
- � `config_flow.py`: 59% - UI configuration flows (complex user interaction paths)
- � `device.py`: 51% - MQTT device communication (low-level network handling)
- � `coordinator.py`: 42% - data coordination (complex async workflows)

**Test Suite Statistics:**
- ✅ **672 tests passing** (100% success rate)
- ✅ **27 test files** (cleaned up from 34 files)
- ✅ **Zero failing tests**
- ✅ **Perfect test reliability**

**Achievement: 70% coverage - excellent progress toward 80% target! 🎯**

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
