# TO DO

## 🎯 PRIORITY: Code Coverage Recovery Plan

**Current Status**: 59% coverage (down from 77% baseline)
**Target**: 75%+ minimum for CI/CD pipeline
**Gap**: Need to recover 16+ percentage points

### Coverage Recovery Strategy (Estimated 2-3 days)

#### Phase A: High-Impact Coverage Wins (Target: +10-12%)
1. **Coordinator Error Handling** - Add tests for network failures, reconnection logic, data parsing errors
   - Files: `custom_components/hass_dyson/coordinator.py` (lines 45-89, 120-156)
   - Impact: ~4% coverage increase

2. **Service Method Coverage** - Test all device service methods with edge cases
   - Files: `custom_components/hass_dyson/services.py` (lines 78-145)
   - Missing: Error handling, invalid parameters, device offline scenarios
   - Impact: ~3% coverage increase

3. **Config Flow Edge Cases** - Test validation failures, network errors, device discovery
   - Files: `custom_components/hass_dyson/config_flow.py` (lines 89-134, 167-203)
   - Missing: API failures, duplicate entries, timeout scenarios
   - Impact: ~3% coverage increase

#### Phase B: Entity Platform Coverage (Target: +6-8%)
4. **Climate Entity Edge Cases** - Test mode changes, temperature validation, offline handling
   - Files: `custom_components/hass_dyson/climate.py` (lines 156-234)
   - Missing: Invalid temperature ranges, mode conflicts, device errors
   - Impact: ~2% coverage increase

5. **Fan Entity Complex Operations** - Test speed controls, oscillation, timer functions
   - Files: `custom_components/hass_dyson/fan.py` (lines 123-189, 234-267)
   - Missing: Speed validation, oscillation errors, timer edge cases
   - Impact: ~2% coverage increase

6. **Vacuum Entity Advanced Features** - Test cleaning modes, navigation, error recovery
   - Files: `custom_components/hass_dyson/vacuum.py` (lines 178-245, 289-334)
   - Missing: Navigation failures, cleaning mode errors, battery scenarios
   - Impact: ~2% coverage increase

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

### Phase 3 Planning (1-2 weeks):
- Remove `pytest-homeassistant-custom-component==0.13.302` dependency
- Clean up [conftest.py](tests/conftest.py) - Remove plugin compatibility patches
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
