# MQTT Device Mock Migration Path

## Overview

This document describes the phased migration from the current ad-hoc inline mock patterns
to the new `DeviceMock` fixture-based architecture. Migration is **not required** and is
**not blocking**. The new architecture is additive — existing tests continue to work
unchanged. Migration is recommended when a test is being modified anyway, or when
a test is identified as a candidate for device-type parametrization.

See [testing-mqtt-fixture-architecture.md](testing-mqtt-fixture-architecture.md) for the
overall architecture and constraints.

---

## Principles

1. **Do not break existing tests.** All 1721+ existing tests must continue to pass after
   each migration step.
2. **Migrate opportunistically.** Migrate a test only when it is being modified for another
   reason, or when it is explicitly identified as a migration candidate.
3. **Maintain 75% coverage minimum.** Coverage must not drop below 75% at any point during
   migration.
4. **New tests use the new pattern.** Any test written after the `DeviceMock` infrastructure
   is in place should use `DeviceMock` unless there is a specific reason not to.
5. **Do not delete inline mocks prematurely.** Keep them until the migrated test has been
   running successfully for at least one CI cycle.

---

## Phase 0: Infrastructure (Prerequisite)

Before any migration can occur, the following must be in place:

| Task | Location | Status on start |
|---|---|---|
| `tests/device_mocks/device_fixture.py` | New file | Not yet created |
| `tests/device_mocks/device_mock.py` | New file | Not yet created |
| `tests/device_mocks/fixture_factory.py` | New file | Not yet created |
| `tests/device_mocks/sanitizer.py` | New file | Not yet created |
| `tests/device_mocks/__init__.py` | New file | Not yet created |
| `tests/device_mocks/test_device_fixture.py` | New file | Not yet created |
| `tests/device_mocks/test_device_mock.py` | New file | Not yet created |
| `tests/fixtures/devices/ec/` | New directory | Not yet created |
| Import in `tests/conftest.py` | Modification | Not yet done |
| At least one fixture file in `tests/fixtures/devices/ec/` | New JSON file | Not yet created |

Phase 0 is complete when:
- All infrastructure files exist
- `DeviceMock` and `DeviceFixture` unit tests pass
- At least one representative fixture file exists (e.g. `438.json`)
- `ec_device_mock` is available as a pytest fixture
- A smoke test in `tests/test_basic.py` demonstrates the pattern works end-to-end

---

## Phase 1: New Tests Use the New Pattern

**No migration of existing tests.** All new tests written after Phase 0 completion follow
the `DeviceMock` pattern. Developers writing new tests are directed to the new pattern via
updated documentation in `testing-patterns.md`.

Specifically:
- New entity platform tests use `ec_device_mock` or category-specific fixtures
- New coordinator tests use `ec_device_mock.build_coordinator_mock()`
- New service tests that exercise MQTT behavior use `DeviceMock.as_current_state_payload()`

No existing test files are modified in Phase 1.

---

## Phase 2: Opportunistic Migration of High-Value Tests

During normal development, when a test file is being modified for any reason, consider
migrating it to the `DeviceMock` pattern if:

- The test contains inline mock state dicts with Dyson state keys
- The test would benefit from parametrization over multiple device types
- The test is testing behavior that varies by device capability

**Migration is optional per test file.** Do not migrate a test file just to migrate it.

### Identifying Migration Candidates

The following test files contain the highest concentration of inline state dicts and are
the best candidates for migration when they need modification:

| Test File | Reason for Priority |
|---|---|
| `tests/test_fan.py` | Large number of state-key-based assertions |
| `tests/test_climate.py` | Capability-dependent tests (Heating guard) |
| `tests/test_humidifier.py` | Capability-dependent tests (Humidifier guard) |
| `tests/test_sensor.py` | Environmental state key tests |
| `tests/test_select.py` | Oscillation mode tests |
| `tests/test_number.py` | Oscillation angle tests |
| `tests/test_switch.py` | Simple on/off state tests |
| `tests/test_binary_sensor.py` | Fault code tests |

---

## Phase 3: Systematic Migration of Duplicate Tests (Future)

After Phase 2 has been running for a sufficient period, consider a systematic pass to
consolidate the many small test files that exist to cover edge cases of individual modules.
The current codebase has test files like:
- `test_fan_error_coverage.py`
- `test_sensor_aqi.py`
- `test_sensor_error_coverage.py`
- `test_sensor_class_coverage.py`

Many of these exist because the previous approach to coverage improvement was to add new
small test files. Phase 3 consolidates these into parametrized tests that cover the same
cases via fixture variation.

**Phase 3 is explicitly out of scope for the initial implementation.** It is recorded here
for planning purposes only.

---

## How to Migrate a Single Test

### Before (existing inline mock pattern)

```python
# tests/test_fan.py  — existing pattern

from unittest.mock import MagicMock
import pytest

def test_fan_auto_mode_enables_auto_flag():
    """Verify that setting AUTO speed sets the auto flag."""
    coordinator = MagicMock()
    coordinator.device.state = {
        "fpwr": "ON",
        "fnsp": "0003",
        "fmod": "FAN",
        "auto": "OFF",
    }
    entity = DysonFanEntity(coordinator)
    # Simulate command
    coordinator.device.state["fnsp"] = "AUTO"
    coordinator.device.state["fmod"] = "AUTO"
    coordinator.device.state["auto"] = "ON"
    assert entity.percentage_step is not None
```

### After (DeviceMock pattern)

```python
# tests/test_fan.py  — migrated pattern

from tests.device_mocks.device_mock import DeviceMock
import pytest


def test_fan_auto_mode_enables_auto_flag(ec_device_mock: DeviceMock) -> None:
    """Verify that setting AUTO speed sets the auto flag across all ec devices.

    The fixture captures the real device behavior: the device sets fmod=AUTO
    and auto=ON when fnsp is set to AUTO. This dependent state change is
    verified here without needing to know the dependency in test code.
    """
    response = ec_device_mock.handle_command("STATE-SET", {"fnsp": "AUTO"})
    state = ec_device_mock.get_state()

    if response.status == "no_response":
        pytest.skip(
            f"{ec_device_mock.product_type} does not respond to AUTO speed command"
        )

    assert state["fnsp"] == "AUTO"
    # Dependent state changes come from the fixture delta — no hand-coding required
    if "fmod" in response.delta:
        assert state["fmod"] == "AUTO"
    if "auto" in response.delta:
        assert state["auto"] == "ON"
```

### Key differences

| Aspect | Before | After |
|---|---|---|
| Device coverage | Single hard-coded state dict | All ec device types via parametrize |
| Dependent state logic | Hand-coded in test | Captured in fixture, applied automatically |
| Command sending | Direct dict mutation | `handle_command()` with response status check |
| `no_response` handling | Not tested | `pytest.skip` with clear reason |
| Test ID | Single entry | One entry per device type: `[438]`, `[527]`, etc. |

---

## Capability Guard Migration Pattern

Certain tests currently guard assertions with `if product_type == "527":` or similar.
After migration, use capability checks from the fixture:

### Before

```python
def test_humidifier_target(coordinator):
    """Only test PH01 humidifier."""
    if coordinator.device_type != "527":
        return
    # ...
```

### After

```python
def test_humidifier_target(ec_device_mock: DeviceMock) -> None:
    """Test humidity target on all devices that support it."""
    if "Humidifier" not in ec_device_mock.capabilities:
        pytest.skip(f"{ec_device_mock.product_type} lacks Humidifier capability")
    # ...
```

Or use the dedicated capability-filtered fixture (preferred):

```python
def test_humidifier_target(humidifier_device_mock: DeviceMock) -> None:
    """Test humidity target — fixture only includes Humidifier-capable devices."""
    # No skip needed — fixture_factory.py handles the filter
    ec_device_mock.handle_command("STATE-SET", {"humt": "0040"})
    assert ec_device_mock.get_state()["humt"] == "0040"
```

---

## Rollback Plan

If the `DeviceMock` infrastructure introduces test failures or coverage regressions, the
rollback procedure is:

1. Remove the fixture factory import from `tests/conftest.py`.
2. Remove `tests/device_mocks/` directory.
3. Remove `tests/fixtures/devices/` directory.
4. All existing tests continue to pass unchanged — the new infrastructure is isolated.

The capture service in the integration source is independent of the test infrastructure and
does not need to be reverted unless desired.

---

## Checklist: Is a Test Ready to Migrate?

Use this checklist before migrating any individual test:

- [ ] The test currently passes
- [ ] A `DeviceFixture` file exists for the relevant device category
- [ ] The state keys used in the test inline dict are present in the fixture's `initial_state`
- [ ] The commands simulated in the test are present in the fixture's `command_responses`
- [ ] The migrated test has been run locally and passes for all parametrized device types
- [ ] Coverage has not dropped after migration
- [ ] The original inline mock version has been removed (not left as dead code)

---

## Documentation Updates Required at Each Phase

| Phase | Documentation to Update |
|---|---|
| Phase 0 complete | `testing-patterns.md` — add `DeviceMock` as preferred new-test pattern |
| Phase 0 complete | `copilot-instructions.md` (`.github/`) — update Testing Strategy section |
| Phase 1 | No documentation changes required |
| Phase 2 | Update `testing-patterns.md` with any patterns discovered during migration |
| Phase 3 | Update this document to reflect completed migration status |
