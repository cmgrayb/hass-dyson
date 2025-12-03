# TO DO

## Testing Architecture Overhaul (Major)

**Priority**: Medium-High
**Estimated Effort**: 4-6 weeks

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

## Add Humidifier Support

Humidifier support notes may be found in .github/design/humidifier_support.md
