# TO DO

## ✅ COMPLETED: Code Coverage Recovery Plan

**Final Status**: 🎉 **76% coverage** - TARGET EXCEEDED! 🎉
- **Statements**: 6824 total, 1444 missed (76% coverage)
- **Branches**: 1812 total, 266 partial branches
- **Test Status**: ✅ **1721 tests passing**, 1 skipped, 0 failures
- **Target**: 75%+ minimum for CI/CD pipeline ✅
- **Achievement**: Exceeded target by 1 percentage point!

**Final Module Coverage Summary**:
- **100%**: const.py, button.py, entity.py
- **96-99%**: vacuum.py, update.py, binary_sensor.py, device_utils.py
- **90%**: number.py (improved from 61%!)
- **85-87%**: switch.py, climate.py, fan.py, \_\_init\_\_.py
- **81%**: sensor.py
- **70-76%**: services.py, device.py, select.py
- **56-60%**: config_flow.py, coordinator.py

**Completed Phases**:
- ✅ Phase A.1 - Coordinator Error Handling (+5% improvement)
- ✅ Phase A.2 - Service Method Coverage (+11% service coverage improvement)
- ✅ Phase A.3 - Config Flow Edge Cases (+3% config_flow coverage improvement)
- ✅ Phase B.1 - Number Entity Error Handling (+9% number coverage improvement)
- ✅ Phase B.2 - Select Entity Error Handling (+18% select coverage improvement)
- ✅ Phase B.3 - Sensor Entity Error Handling (+11% sensor coverage improvement)
- ✅ Phase B.4 - Switch Entity Error Handling (+22% switch coverage improvement)
- ✅ Phase B.5 - Binary Sensor Error Handling (+34% binary_sensor coverage improvement)
- ✅ Phase B.6 - Update Entity Error Handling (+4% update coverage improvement)
- ✅ Phase B.7 - Device Error Handling (+10% device coverage improvement)
- ✅ Phase B.8 - Device Utils Error Handling (+11% device_utils coverage improvement)
- ✅ Phase C.1 - Climate Entity Error Handling (+10% climate coverage improvement)
- ✅ Phase C.2 - Fan Entity Error Handling (+8% fan coverage improvement)
- ✅ Phase C.3 - Vacuum Entity Error Handling (+9% vacuum coverage improvement)
- ✅ Code Cleanup - Removed unimplemented schedule_operation service (~43 uncovered lines)
- ✅ Services AttributeError Tests - Added 5 tests for AttributeError handling in services.py
- ✅ Day0 Oscillation Entity Tests - Added 42 comprehensive tests (+29% number.py coverage improvement)

### Coverage Recovery Strategy (Estimated 2-3 days)

#### Phase A: High-Impact Coverage Wins (Target: +10-12%)
1. ✅ **Coordinator Error Handling** - Added comprehensive error tests
   - Files: `custom_components/hass_dyson/coordinator.py`
   - **Completed**: Added 23 new tests covering:
     - Network failures and connection timeouts
     - MQTT connection errors and reconnection
     - Data parsing errors and validation failures
     - Service registration errors
     - State update failures
     - Helper function edge cases
     - Message handling exceptions
   - **Impact**: +10% coordinator coverage (50% → 60%), +6% overall (59% → 65%)
   - **Tests**: `tests/test_coordinator_error_handling.py` (164 total coordinator tests passing)

2. ✅ **Service Method Coverage** - Test all device service methods with edge cases
   - Files: `custom_components/hass_dyson/services.py`
   - **Completed**: Added 33 new tests covering:
     - Reset filter service (hepa, carbon, both) error scenarios
     - Refresh account data errors (connection, timeout, not found)
     - Get cloud devices errors (authentication, API, connection)
     - Helper function edge cases (_convert_to_string, _decrypt_credentials)
     - _find_cloud_coordinators with various coordinator types
     - _fetch_live_cloud_devices error handling
   - **Impact**: +11% services coverage (59% → 70%), +2% overall (65% → 67%)
   - **Tests**: `tests/test_services_comprehensive_errors.py` (145 service tests passing total)

3. ✅ **Config Flow Edge Cases** - Test validation failures, network errors, device discovery
   - Files: `custom_components/hass_dyson/config_flow.py`
   - **Completed**: Added 21 new tests covering:
     - AttributeError/TypeError in _get_default_country_culture (lines 88-94)
     - socket.gaierror fallback in mDNS discovery (lines 164-169)
     - TimeoutError in asyncio.wait_for (lines 181-183)
     - DysonAuthError, DysonConnectionError, DysonAPIError handling (lines 318-322)
     - Exception in _create_cloud_account_form (lines 369-371)
     - Empty email validation and cleanup (lines 411, 416-418)
     - mDNS discovery errors (zeroconf None, general exceptions)
   - **Impact**: +3% config_flow coverage (53% → 56%), overall remains 65%
   - **Tests**: `tests/test_config_flow_error_coverage.py` (80 config flow tests passing total)

#### Phase B: Entity Platform Coverage (Target: +6-8%)
4. ✅ **Number Entity Error Handling** - Test value validation, range checks, device communication
   - Files: `custom_components/hass_dyson/number.py`
   - **Completed**: Added 35 new tests covering:
     - AsyncCancelledError, ConnectionError, TimeoutError in timer polling (lines 106-142)
     - KeyError, AttributeError, ValueError, TypeError in coordinator updates (lines 235-257)
     - ConnectionError, ValueError, Exception in set_native_value (lines 287-293)
     - ValueError, TypeError in oscillation value parsing (lines 367-370, 376)
     - All oscillation entities error paths (lower, upper, center, span angles)
     - Timer polling cancellation and exception handling
   - **Impact**: +9% number coverage (47% → 56%), +1% overall (65% → 66%)
   - **Tests**: `tests/test_number_error_coverage.py` (83 number tests passing total)

5. ✅ **Select Entity Error Handling** - Test option validation, mode changes, device communication
   - Files: `custom_components/hass_dyson/select.py`
   - **Completed**: Added 46 new tests covering:
     - ConnectionError, TimeoutError, ValueError in async_select_option (lines 158-172)
     - Exception handling for all select entity types:
       * Fan control mode (Auto/Manual/Sleep) errors
       * Oscillation mode (45°/90°/180°/350°/Custom/Off) errors
       * Oscillation mode Day0 variant errors
       * Heating mode (On/Off) errors
       * Water hardness (Soft/Medium/Hard) errors
       * Robot power modes (360 Eye, Heurist, Vis Nav, Generic) errors
     - ValueError/TypeError in state parsing (_calculate_current_center, _detect_mode_from_angles)
     - ValueError/TypeError in extra_state_attributes angle parsing (lines 585, 649)
   - **Impact**: +18% select coverage (53% → 71%), +1% overall (66% → 67%)
   - **Tests**: `tests/test_select_error_coverage.py` (148 select tests passing total)

6. ✅ **Sensor Entity Error Handling** - Test state parsing, data conversion, device communication
   - Files: `custom_components/hass_dyson/sensor.py`
   - **Completed**: Added 40 new tests covering:
     - KeyError, AttributeError, ValueError, TypeError in coordinator updates
     - P25R particulate matter sensor error paths (inner/outer try blocks)
     - P10R particulate matter sensor error paths
     - CO2 sensor data conversion errors
     - VOC sensor data conversion errors
     - Temperature sensor state access errors
     - Humidity sensor data conversion errors
     - FilterLifeSensor error handling (HEPA, Carbon filter types)
     - AirQualitySensor error handling (PM2.5, PM10 sensor types)
   - **Impact**: +11% sensor coverage (54% → 65%), +1% overall (67% → 68%)
   - **Tests**: `tests/test_sensor_error_coverage.py` (186 sensor tests passing total)

7. ✅ **Switch Entity Error Handling** - Test turn on/off failures, state parsing, device communication
   - Files: `custom_components/hass_dyson/switch.py`
   - **Completed**: Added 38 new tests covering:
     - ConnectionError, TimeoutError, AttributeError, Exception in async_turn_on/off
     - Night mode switch error paths (set_night_mode failures)
     - Auto mode switch error paths (set_auto_mode failures)
     - Heating switch error paths (set_heating_mode failures)
     - Continuous monitoring switch error paths (set_continuous_monitoring failures)
     - Firmware auto-update switch success/failure paths
     - ValueError, TypeError in extra_state_attributes temperature conversion
   - **Impact**: +22% switch coverage (61% → 83%), +1% overall (68% → 69%)
   - **Tests**: `tests/test_switch_error_coverage.py` (74 switch tests passing total)

8. ✅ **Binary Sensor Error Handling** - Test filter replacement, fault detection, state parsing
   - Files: `custom_components/hass_dyson/binary_sensor.py`
   - **Completed**: Added 37 new tests covering:
     - Filter replacement sensor error paths (no device, no data, invalid data types)
     - HEPA filter life validation errors (None, invalid type, exception access)
     - Generic exception handling in filter sensor updates
     - Fault sensor error paths (no device, no faults data, exception during update)
     - Fault code relevance checking for different device categories
     - Fault search across nested data structures (product-errors, module-warnings, etc.)
     - Fault severity determination (Critical, Warning, Maintenance, Unknown)
     - Fault icon selection based on sensor type and state
     - Fault friendly name generation for known and unknown codes
   - **Impact**: +34% binary_sensor coverage (62% → 96%), +1% overall (69% → 70%)
   - **Tests**: `tests/test_binary_sensor_error_coverage.py` (81 binary sensor tests passing total)

9. **Climate Entity Edge Cases** - Test mode changes, temperature validation, offline handling
   - Files: `custom_components/hass_dyson/climate.py` (85% coverage, room for improvement)
   - Missing: Invalid temperature ranges, mode conflicts, device errors
   - Impact: ~1% coverage increase

10. **Fan Entity Complex Operations** - Test speed controls, oscillation, timer functions
   - Files: `custom_components/hass_dyson/fan.py` (68% coverage, 350 statements)
   - Missing: Speed validation, oscillation errors, timer edge cases
   - Impact: ~1-2% coverage increase

#### Phase C: Infrastructure Coverage (Target: +2-4%)
7. **Device Registry & Setup** - Test device initialization, registry errors, cleanup
   - Files: `custom_components/hass_dyson/device.py` (lines 67-123)
   - Missing: Registry failures, device ID conflicts, cleanup errors
   - Impact: ~1% coverage increase

8. **Entity Base Class Methods** - Test common entity functionality, availability updates
   - Files: `custom_components/hass_dyson/entity.py` (lines 89-145)
   - Missing: Availability changes, attribute updates, error states
   - Impact: ~1% coverage increase

### Implementation Timeline
- **Day 1**: Phases A.1-A.2 (Coordinator + Services) → Target: 67% coverage
- **Day 2**: Phases A.3 + B.4-B.5 (Config Flow + Climate/Fan) → Target: 73% coverage
- **Day 3**: Phases B.6 + C.7-C.8 (Vacuum + Infrastructure) → Target: 76% coverage

### Testing Approach
- **Error Path Testing**: Focus on exception handling and edge cases
- **Integration Scenarios**: Multi-device interactions, network issues
- **State Validation**: Comprehensive entity state testing
- **Mock Strategies**: Realistic failure simulation

---

**Testing**: ✅ **Phase 1 COMPLETED** - Pure pytest migration achieved 100% success rate!
All 1064 tests passing. Now focusing on coverage recovery to meet CI/CD requirements.

## Migration Status: Phase 1 In Progress ✅

### ✅ Completed (Phase 1):
- **Pure pytest fixtures created** in [conftest.py](tests/conftest.py):
  - `pure_mock_hass()` - Home Assistant instance mock
  - `pure_mock_config_entry()` - Config entry mock
  - `pure_mock_coordinator()` - Coordinator mock
  - `pure_mock_entity_registry()` / `pure_mock_device_registry()` - Registry mocks
- **Proof of concept test** - [test_const_pure_pytest.py](tests/test_const_pure_pytest.py) validates infrastructure
- **Migrated and consolidated test files** ✅:
  - ✅ [test_const.py](tests/test_const.py) - Pure pytest constants tests
  - ✅ [test_device_utils.py](tests/test_device_utils.py) - Header migrated, 65 tests passing
  - ✅ [test_entity.py](tests/test_entity.py) - **Consolidated & migrated** (11 tests)
  - ✅ [test_binary_sensor.py](tests/test_binary_sensor.py) - **Consolidated & migrated** (30 tests)
    - Merged: `test_binary_sensor.py` + `test_binary_sensor_edge_cases.py`
    - Full fault code testing, platform setup, filtering logic
- **Both plugin and pure pytest coexist** - No breaking changes to existing tests
- **File consolidation started** - Following platform-based structure

### Current Test Results ✅
- **Pure pytest infrastructure**: 10/10 tests passing
- **Migrated const tests**: 3/3 tests passing
- **Migrated device_utils tests**: 65/65 tests passing
- **Consolidated entity tests**: 11/11 tests passing ✅
- **Consolidated binary_sensor tests**: 30/30 tests passing ✅
- **Total pure pytest tests**: **119 tests passing** 🎉
- **Coverage maintained**: Binary sensor coverage improved to 48%

### Next Steps (Continue Phase 1):
1. **Continue platform consolidation and migration**:
   - Create consolidated `test_button.py` (merge button tests)
   - Create consolidated `test_sensor.py` (merge all sensor test files)
   - Create consolidated `test_switch.py` (merge all switch test files)
2. **Add platform setup helpers** - Templates for testing `async_setup_entry`
3. **Remove old fragmented test files** - Clean up duplicate/redundant tests

### Ready for Phase 2 (Platform-based migration):
- `test_climate.py`, `test_fan.py`, `test_number.py`, `test_select.py`
- `test_update.py`, `test_vacuum.py` - Complex entity platforms
- `test_coordinator.py` - Merge coordinator test files
- `test_config_flow.py` - Merge config flow test files

### Phase 2 Planning (2-4 weeks):
- Migrate entity platform tests ([test_sensor.py](tests/test_sensor.py), [test_switch.py](tests/test_switch.py), etc.)
- Convert coordinator tests ([test_coordinator.py](tests/test_coordinator.py))
- Update integration tests with pure pytest patterns

### Phase 3 (Complete):
- ✅ Removed `pytest-homeassistant-custom-component` dependency (pure pytest infrastructure)
- ✅ Clean up [conftest.py](tests/conftest.py) - Remove plugin compatibility patches
- Performance optimization and final validation

### Background
Current plugin has issues with:
- Event loop cleanup causing test instability ✅ **Solved with pure fixtures**
- Plugin conflicts with other pytest plugins
- Version coupling requiring exact HA version matching ✅ **Eliminated**
- Limited control over testing infrastructure ✅ **Full control achieved**
- Frequent breakage due to HA core changes ✅ **Independence achieved**

### Benefits Already Realized
- ✅ Full control over testing environment
- ✅ Better performance (no plugin overhead)
- ✅ Easier debugging of test failures
- ✅ Version independence from plugin updates
- ✅ Custom mock strategies tailored to project needs

### Implementation Notes
- ✅ Following patterns used by major HA projects (HACS, ESPHome)
- ✅ Using direct Home Assistant test utilities: `homeassistant[test]`
- ✅ Custom `MockConfigEntry` and essential test helpers implemented
- 🔄 **TODO**: Add snapshot testing with syrupy for state validation

### Current Test Results
- **Pure pytest infrastructure**: ✅ 10/10 tests passing
- **Migrated const tests**: ✅ 3/3 tests passing
- **Migrated device_utils tests**: ✅ 65/65 tests passing
- **Coverage maintained**: 74% device_utils coverage (no regression)
