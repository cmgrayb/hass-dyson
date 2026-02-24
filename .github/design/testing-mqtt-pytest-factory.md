# pytest Fixture Factory and Parametrization Specification

## Overview

This document specifies the pytest fixture factory that makes `DeviceMock` instances
available to test functions. The factory auto-discovers fixture files by device category
and parametrizes tests across all available device types automatically.

See [testing-mqtt-fixture-architecture.md](testing-mqtt-fixture-architecture.md) for context
and [testing-mqtt-device-mock.md](testing-mqtt-device-mock.md) for the `DeviceMock` class spec.

---

## Design Goals

1. **Zero-boilerplate scaling**: When a new fixture file is added to
   `tests/fixtures/devices/{category}/`, tests parametrized over that category automatically
   run against the new device with no changes to test code.
2. **Fixture isolation**: Each test function receives a fresh `DeviceMock` instance with
   state reset to `initial_state`. State mutations from one test do not affect another.
3. **Readable test IDs**: pytest test IDs include the product type, e.g.
   `test_fan_turns_on[438]` and `test_fan_turns_on[527]`.
4. **Compatibility with existing patterns**: The `DeviceMock` integrates with existing
   coordinator mock patterns via `build_coordinator_mock()`.

---

## File Location

```
tests/device_mocks/fixture_factory.py
```

This module defines all category-scoped pytest fixtures and is imported by
`tests/conftest.py` via a plugin import.

---

## Fixture Factory Implementation

```python
"""pytest fixture factory for DeviceMock instances.

Provides auto-parametrized fixtures for each device category. Tests that
need device-type-specific mocks should use the category fixtures defined here.

Fixtures provided:
    ec_device_mock      — parametrized over all ec fixtures
    robot_device_mock   — parametrized over all robot fixtures
    vacuum_device_mock  — parametrized over all vacuum fixtures
    flrc_device_mock    — parametrized over all flrc fixtures
    any_device_mock     — parametrized over ALL fixtures across all categories

Usage:
    def test_something(ec_device_mock: DeviceMock) -> None:
        ec_device_mock.handle_command("STATE-SET", {"fpwr": "OFF"})
        assert ec_device_mock.get_state()["fpwr"] == "OFF"
"""

from __future__ import annotations

import pytest

from .device_fixture import DeviceFixture
from .device_mock import DeviceMock

from custom_components.hass_dyson.const import (
    DEVICE_CATEGORY_EC,
    DEVICE_CATEGORY_FLRC,
    DEVICE_CATEGORY_ROBOT,
    DEVICE_CATEGORY_VACUUM,
)


def _make_device_mock_params(device_category: str) -> list[pytest.param]:
    """Discover fixture files for a category and return pytest params.

    Each param wraps a DeviceFixture and uses the product_type as the test ID.

    Args:
        device_category: One of "ec", "robot", "vacuum", "flrc".

    Returns:
        List of pytest.param objects. Empty list if no fixtures found.
    """
    fixtures = DeviceFixture.discover_all(device_category)
    return [
        pytest.param(fixture, id=fixture.metadata.product_type)
        for fixture in fixtures
    ]


# ---------------------------------------------------------------------------
# ec device mock
# ---------------------------------------------------------------------------

@pytest.fixture(
    params=_make_device_mock_params(DEVICE_CATEGORY_EC),
    scope="function",
)
def ec_device_mock(request: pytest.FixtureRequest) -> DeviceMock:
    """Parametrized DeviceMock for ec (fan/purifier) device types.

    Automatically parametrized over all fixture files in
    tests/fixtures/devices/ec/. Each test function receives a fresh
    DeviceMock instance with state reset to the fixture's initial_state.

    Args:
        request: pytest fixture request providing the parametrized value.

    Returns:
        A DeviceMock instance for the current ec device type.

    Example:
        def test_fan_power_off(ec_device_mock: DeviceMock) -> None:
            ec_device_mock.handle_command("STATE-SET", {"fpwr": "OFF"})
            assert ec_device_mock.get_state()["fpwr"] == "OFF"
    """
    fixture: DeviceFixture = request.param
    mock = DeviceMock(fixture)
    yield mock
    mock.reset()


# ---------------------------------------------------------------------------
# robot device mock
# ---------------------------------------------------------------------------

@pytest.fixture(
    params=_make_device_mock_params(DEVICE_CATEGORY_ROBOT),
    scope="function",
)
def robot_device_mock(request: pytest.FixtureRequest) -> DeviceMock:
    """Parametrized DeviceMock for robot vacuum device types.

    Automatically parametrized over all fixture files in
    tests/fixtures/devices/robot/.

    Args:
        request: pytest fixture request providing the parametrized value.

    Returns:
        A DeviceMock instance for the current robot device type.
    """
    fixture: DeviceFixture = request.param
    mock = DeviceMock(fixture)
    yield mock
    mock.reset()


# ---------------------------------------------------------------------------
# vacuum device mock
# ---------------------------------------------------------------------------

@pytest.fixture(
    params=_make_device_mock_params(DEVICE_CATEGORY_VACUUM),
    scope="function",
)
def vacuum_device_mock(request: pytest.FixtureRequest) -> DeviceMock:
    """Parametrized DeviceMock for vacuum device types.

    Automatically parametrized over all fixture files in
    tests/fixtures/devices/vacuum/.

    Args:
        request: pytest fixture request providing the parametrized value.

    Returns:
        A DeviceMock instance for the current vacuum device type.
    """
    fixture: DeviceFixture = request.param
    mock = DeviceMock(fixture)
    yield mock
    mock.reset()


# ---------------------------------------------------------------------------
# flrc device mock
# ---------------------------------------------------------------------------

@pytest.fixture(
    params=_make_device_mock_params(DEVICE_CATEGORY_FLRC),
    scope="function",
)
def flrc_device_mock(request: pytest.FixtureRequest) -> DeviceMock:
    """Parametrized DeviceMock for floor cleaner device types.

    Automatically parametrized over all fixture files in
    tests/fixtures/devices/flrc/.

    Args:
        request: pytest fixture request providing the parametrized value.

    Returns:
        A DeviceMock instance for the current flrc device type.
    """
    fixture: DeviceFixture = request.param
    mock = DeviceMock(fixture)
    yield mock
    mock.reset()


# ---------------------------------------------------------------------------
# Cross-category fixture
# ---------------------------------------------------------------------------

def _make_all_device_mock_params() -> list[pytest.param]:
    """Return params for all fixtures across all categories."""
    all_params = []
    for category in [
        DEVICE_CATEGORY_EC,
        DEVICE_CATEGORY_ROBOT,
        DEVICE_CATEGORY_VACUUM,
        DEVICE_CATEGORY_FLRC,
    ]:
        fixtures = DeviceFixture.discover_all(category)
        for fixture in fixtures:
            all_params.append(
                pytest.param(
                    fixture,
                    id=f"{fixture.metadata.device_category}-{fixture.metadata.product_type}",
                )
            )
    return all_params


@pytest.fixture(
    params=_make_all_device_mock_params(),
    scope="function",
)
def any_device_mock(request: pytest.FixtureRequest) -> DeviceMock:
    """Parametrized DeviceMock for ALL device types across all categories.

    Use this only for tests that apply universally to every device type
    (e.g. basic MQTT connectivity, coordinator setup, config entry loading).
    For category-specific tests, prefer ec_device_mock, robot_device_mock, etc.

    Args:
        request: pytest fixture request providing the parametrized value.

    Returns:
        A DeviceMock instance for each device type in every category.
    """
    fixture: DeviceFixture = request.param
    mock = DeviceMock(fixture)
    yield mock
    mock.reset()
```

---

## conftest.py Integration

Add the following import to `tests/conftest.py` to make all fixtures available globally:

```python
# In tests/conftest.py — add near the top after existing imports
from tests.device_mocks.fixture_factory import (  # noqa: F401
    any_device_mock,
    ec_device_mock,
    flrc_device_mock,
    robot_device_mock,
    vacuum_device_mock,
)
```

Alternatively, if `tests/device_mocks/` is registered as a pytest plugin directory in
`pyproject.toml`, the fixtures are auto-discovered without an explicit import:

```toml
# pyproject.toml
[tool.pytest.ini_options]
# ...existing config...
testpaths = ["tests"]
```

The explicit import in `conftest.py` is simpler and preferred.

---

## Canonical Test Patterns

### Pattern 1: Test parametrized over all ec device types

```python
# tests/test_fan.py

import pytest
from tests.device_mocks.device_mock import DeviceMock


def test_fan_power_off(ec_device_mock: DeviceMock) -> None:
    """Verify fan turns off correctly across all ec device types."""
    ec_device_mock.handle_command("STATE-SET", {"fpwr": "OFF"})
    state = ec_device_mock.get_state()
    assert state["fpwr"] == "OFF"
```

This test runs once per fixture file in `tests/fixtures/devices/ec/`. With four fixtures,
pytest reports:

```
test_fan_power_off[438] PASSED
test_fan_power_off[527] PASSED
test_fan_power_off[475] PASSED
test_fan_power_off[527E] PASSED
```

---

### Pattern 2: Test parametrized over ec devices, using coordinator mock

```python
# tests/test_fan.py

from unittest.mock import MagicMock
import pytest
from tests.device_mocks.device_mock import DeviceMock
from custom_components.hass_dyson.fan import DysonFanEntity


def test_fan_entity_state_reflects_device(ec_device_mock: DeviceMock) -> None:
    """Verify the fan entity correctly reads power state from the coordinator."""
    coordinator = ec_device_mock.build_coordinator_mock()
    entity = DysonFanEntity(coordinator)

    # Initial state from fixture
    initial_power = ec_device_mock.get_state()["fpwr"]
    assert entity.is_on == (initial_power == "ON")

    # Simulate device state change
    ec_device_mock.handle_command("STATE-SET", {"fpwr": "OFF"})
    coordinator.device.state = ec_device_mock.get_state()

    assert not entity.is_on
```

---

### Pattern 3: Test a capability-specific feature only on supporting devices

```python
# tests/test_humidifier.py

import pytest
from tests.device_mocks.device_mock import DeviceMock


@pytest.mark.parametrize(
    "ec_device_mock",
    [
        # Override the auto-parametrization to filter capabilities
        # Use indirect=True to pass through the fixture factory
    ],
    indirect=True,
)
def test_humidity_target_only_on_humidifiers(ec_device_mock: DeviceMock) -> None:
    """Verify humidity target is only settable on devices with Humidifier capability."""
    if "Humidifier" not in ec_device_mock.capabilities:
        pytest.skip(f"{ec_device_mock.product_type} does not have Humidifier capability")

    ec_device_mock.handle_command("STATE-SET", {"humt": "0040"})
    assert ec_device_mock.get_state()["humt"] == "0040"
```

**Preferred alternative** — use a dedicated fixture that filters at parametrization time:

```python
# tests/device_mocks/fixture_factory.py — add alongside existing fixtures

@pytest.fixture(
    params=[
        pytest.param(f, id=f.metadata.product_type)
        for f in DeviceFixture.discover_all(DEVICE_CATEGORY_EC)
        if "Humidifier" in f.metadata.capabilities
    ],
    scope="function",
)
def humidifier_device_mock(request: pytest.FixtureRequest) -> DeviceMock:
    """DeviceMock parametrized over ec devices with Humidifier capability only."""
    fixture: DeviceFixture = request.param
    mock = DeviceMock(fixture)
    yield mock
    mock.reset()
```

This approach is cleaner — tests that use `humidifier_device_mock` never run on
non-humidifier devices and do not appear as skipped in the test output.

---

### Pattern 4: Simulate receiving an MQTT message

```python
# tests/test_coordinator.py

from unittest.mock import patch, MagicMock
import pytest
from tests.device_mocks.device_mock import DeviceMock
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator


@pytest.mark.asyncio
async def test_coordinator_updates_on_state_change(
    ec_device_mock: DeviceMock,
    mock_hass: MagicMock,
    mock_config_entry: MagicMock,
) -> None:
    """Verify the coordinator updates listeners when a STATE-CHANGE arrives."""
    # Get the simulated state change payload
    ec_device_mock.handle_command("STATE-SET", {"fpwr": "OFF"})
    payload = ec_device_mock.as_state_change_payload({"fpwr": "OFF"})

    with patch("...DataUpdateCoordinator.__init__"):
        coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
        coordinator.hass = mock_hass
        coordinator._listeners = {}
        coordinator.async_update_listeners = MagicMock()

        # Inject the payload as if it arrived from MQTT
        coordinator._handle_mqtt_message(json.dumps(payload))

        coordinator.async_update_listeners.assert_called_once()
```

---

### Pattern 5: Strict mode to catch fixture gaps

```python
def test_all_ec_commands_covered(ec_device_mock: DeviceMock) -> None:
    """Verify the fixture has responses for all core commands.

    Uses strict=True to catch any commands the fixture is missing entries for.
    This helps identify when const.py gains new state keys that need capturing.
    """
    from custom_components.hass_dyson.const import (
        STATE_KEY_POWER, STATE_KEY_FAN_SPEED, STATE_KEY_NIGHT_MODE
    )
    from tests.device_mocks.device_mock import CommandNotFoundError

    core_commands = [
        ("STATE-SET", {STATE_KEY_POWER: "OFF"}),
        ("STATE-SET", {STATE_KEY_FAN_SPEED: "0005"}),
        ("STATE-SET", {STATE_KEY_NIGHT_MODE: "ON"}),
    ]
    for command_type, data in core_commands:
        try:
            ec_device_mock.handle_command(command_type, data, strict=True)
        except CommandNotFoundError as e:
            pytest.fail(f"Fixture {ec_device_mock.product_type!r} is missing: {e}")
        ec_device_mock.reset()
```

---

## Fixture Parametrization Rules

| When no fixture files exist for a category | The fixture parameter list is empty. Tests using that fixture are collected but immediately skipped with a clear message: `"No fixture files found for category 'ec'"`. |
|---|---|
| When fixture files are added | Tests are automatically collected on the next run. No changes to test code required. |
| Fixture scope | Always `"function"` — each test gets a fresh, reset mock. |
| Fixture teardown | `mock.reset()` is called in the `yield` fixture's teardown. |

---

## `__init__.py` for the `device_mocks` Package

```python
# tests/device_mocks/__init__.py
"""Device mock package for MQTT fixture-based testing.

Provides DeviceFixture, DeviceMock, and pytest fixture factories
for parametrized device type testing.
"""

from .device_fixture import DeviceFixture, UnsupportedFixtureVersionError, UnsanitizedFixtureError
from .device_mock import DeviceMock, CommandNotFoundError

__all__ = [
    "DeviceFixture",
    "DeviceMock",
    "UnsupportedFixtureVersionError",
    "UnsanitizedFixtureError",
    "CommandNotFoundError",
]
```

---

## pyproject.toml — No Changes Required

The fixture factory does not require changes to `pyproject.toml` provided it is imported
from `tests/conftest.py`. The existing pytest configuration in `pyproject.toml` is
sufficient.

---

## Coverage Implications

Tests written using the `ec_device_mock` fixture will cover branches in fan, climate,
humidifier, sensor, switch, select, number, binary_sensor, and button platform code that
depend on state key values. The parametrization over multiple device types exercises
capability-guard branches that are currently under-covered by single-device inline mocks.

Expected coverage impact: **+3–7%** depending on how many fixture files are available at
any given time.
