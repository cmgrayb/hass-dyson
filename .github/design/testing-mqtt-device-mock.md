# DeviceMock and DeviceFixture Class Specification

## Overview

This document specifies the `DeviceFixture` data class and the `DeviceMock` class. Together
they form the stateful MQTT device mock used in unit and integration tests.

- `DeviceFixture` is a thin, typed wrapper around a loaded fixture JSON file.
- `DeviceMock` uses a `DeviceFixture` to maintain a mutable state dict and respond to
  commands as the real device would.

See [testing-mqtt-fixture-architecture.md](testing-mqtt-fixture-architecture.md) for context
and [testing-mqtt-fixture-schema.md](testing-mqtt-fixture-schema.md) for the fixture schema.

---

## File Locations

| Class | File |
|---|---|
| `DeviceFixture` | `tests/device_mocks/device_fixture.py` |
| `DeviceMock` | `tests/device_mocks/device_mock.py` |
| `UnsupportedFixtureVersionError` | `tests/device_mocks/device_fixture.py` |
| `CommandNotFoundError` | `tests/device_mocks/device_mock.py` |

---

## `DeviceFixture`

### Purpose

`DeviceFixture` is a dataclass that:

1. Loads a fixture JSON file from disk.
2. Validates the schema version.
3. Validates that the file is sanitized (no real serial numbers or credentials).
4. Provides typed, attribute-level access to all fixture sections.

### Class Definition

```python
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SUPPORTED_SCHEMA_VERSIONS = {1}
REAL_SERIAL_PATTERN = re.compile(r"[A-Z][A-Z0-9]{1,3}-[A-Z]{2}-[A-Z]{3}[0-9]{4}[A-Z]")
SANITIZED_SERIAL_PATTERN = re.compile(r"TEST-[A-Z0-9]+-[0-9]+[A-Z]")


class UnsupportedFixtureVersionError(Exception):
    """Raised when a fixture file has an unsupported schema_version."""


class UnsanitizedFixtureError(Exception):
    """Raised when a fixture file contains unsanitized real-world data."""


@dataclass
class CommandResponse:
    """A single command response entry from the fixture."""
    status: str  # "responded" | "no_response" | "rejected"
    delta: dict[str, str] = field(default_factory=dict)     # only when status=="responded"
    response: dict[str, Any] = field(default_factory=dict)  # only when status=="rejected"


@dataclass
class FaultCode:
    """A fault code entry from the fixture."""
    code: str
    description: str
    sample_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceFixtureMetadata:
    """Metadata section of a fixture file."""
    product_type: str
    mqtt_root_topic_level: str
    device_category: str
    device_name: str
    serial_number: str
    firmware_version: str
    capabilities: list[str]
    capture_date: str
    capture_tool_version: str
    notes: str = ""


@dataclass
class DeviceFixture:
    """Typed representation of a device fixture JSON file.

    Load via DeviceFixture.from_file(path) rather than constructing directly.
    """
    metadata: DeviceFixtureMetadata
    initial_state: dict[str, str]
    environmental_state: dict[str, str] | None
    command_responses: dict[str, dict[str, CommandResponse]]
    fault_codes: list[FaultCode]

    @classmethod
    def from_file(cls, path: Path) -> DeviceFixture:
        """Load and validate a fixture file from disk.

        Args:
            path: Absolute path to the fixture JSON file.

        Returns:
            A validated DeviceFixture instance.

        Raises:
            UnsupportedFixtureVersionError: If schema_version is not supported.
            UnsanitizedFixtureError: If the file contains real serial numbers or credentials.
            FileNotFoundError: If the file does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
            KeyError / ValueError: If required fields are missing or malformed.
        """
        ...

    @classmethod
    def from_product_type(cls, product_type: str, device_category: str) -> DeviceFixture:
        """Load a fixture by product type and category using the standard path convention.

        Resolves to: tests/fixtures/devices/{device_category}/{product_type}.json
        relative to the repository root.

        Args:
            product_type: Dyson product type code (e.g. "438").
            device_category: Device category (e.g. "ec", "robot").

        Returns:
            A validated DeviceFixture instance.
        """
        ...

    @staticmethod
    def discover_all(device_category: str) -> list[DeviceFixture]:
        """Discover and load all fixture files for a given device category.

        Scans tests/fixtures/devices/{device_category}/ for *.json files and
        loads each one. Used by the pytest fixture factory for parametrization.

        Args:
            device_category: Device category (e.g. "ec", "robot").

        Returns:
            List of DeviceFixture instances, one per file found.
            Returns empty list (not error) if directory does not exist.
        """
        ...

    def _validate_schema_version(self, raw: dict[str, Any]) -> None:
        """Validate schema_version field."""
        version = raw.get("schema_version")
        if version not in SUPPORTED_SCHEMA_VERSIONS:
            raise UnsupportedFixtureVersionError(
                f"Fixture schema version {version!r} is not supported. "
                f"Supported versions: {SUPPORTED_SCHEMA_VERSIONS}"
            )

    def _validate_sanitization(self, raw: dict[str, Any]) -> None:
        """Scan the entire document for real-looking serial numbers."""
        raw_str = json.dumps(raw)
        if REAL_SERIAL_PATTERN.search(raw_str):
            raise UnsanitizedFixtureError(
                "Fixture file appears to contain a real Dyson serial number. "
                "Run the sanitizer before committing."
            )
```

### Key Implementation Notes

- `from_file` must deserialize `command_responses` into `dict[str, dict[str, CommandResponse]]`
  so that `DeviceMock` receives typed objects, not raw dicts.
- The `delta` field of a `CommandResponse` with `status="no_response"` is always an empty
  dict. The `delta` field of `status="rejected"` is also always empty.
- `discover_all` is called at pytest collection time (inside `params=` of
  `pytest.fixture`). It must not raise if the directory is empty — it returns `[]`.

---

## `DeviceMock`

### Purpose

`DeviceMock` wraps a `DeviceFixture` and provides:

1. A **mutable state dict** initialised from `initial_state`.
2. A `handle_command(command_type, data)` method that mutates state using captured deltas.
3. A `get_state()` method returning the current state dict (a copy).
4. A `get_environmental_state()` method returning the environmental state.
5. An `as_mqtt_payload(msg_type)` method to produce properly-formatted MQTT message dicts
   for injection into tests.
6. A `reset()` method to restore the mock to its initial state.
7. A `patch()` context manager for use with `unittest.mock.patch`.

### Class Definition

```python
from __future__ import annotations

import copy
import json
from typing import Any
from unittest.mock import MagicMock, patch as mock_patch

from .device_fixture import CommandResponse, DeviceFixture


class CommandNotFoundError(Exception):
    """Raised when handle_command is called with a command key not in the fixture."""


class DeviceMock:
    """Stateful mock of a Dyson device based on captured fixture data.

    Maintains a mutable state dict and responds to STATE-SET commands by
    applying the pre-captured response delta from the fixture.

    Usage in tests:
        mock = DeviceMock(fixture)
        mock.handle_command("STATE-SET", {"fnsp": "0005"})
        assert mock.get_state()["fnsp"] == "0005"

    Usage as pytest fixture (see fixture_factory.py):
        def test_fan_speed(ec_device_mock):
            ec_device_mock.handle_command("STATE-SET", {"fnsp": "0005"})
            assert ec_device_mock.get_state()["fnsp"] == "0005"
    """

    def __init__(self, fixture: DeviceFixture) -> None:
        """Initialise the mock from a fixture.

        Args:
            fixture: A loaded and validated DeviceFixture instance.
        """
        self._fixture = fixture
        self._state: dict[str, str] = copy.deepcopy(fixture.initial_state)
        self._environmental_state: dict[str, str] | None = (
            copy.deepcopy(fixture.environmental_state)
            if fixture.environmental_state
            else None
        )

    # -------------------------------------------------------------------------
    # Core state access
    # -------------------------------------------------------------------------

    def get_state(self) -> dict[str, str]:
        """Return a copy of the current device state dict.

        Returns:
            A copy of the current state, keyed by Dyson state key strings.
        """
        return copy.deepcopy(self._state)

    def get_environmental_state(self) -> dict[str, str] | None:
        """Return the environmental sensor state.

        Returns:
            A copy of the environmental state dict, or None if not available.
        """
        return copy.deepcopy(self._environmental_state) if self._environmental_state else None

    def reset(self) -> None:
        """Restore the mock to its fixture initial_state.

        Use this in test teardown or between test scenarios.
        """
        self._state = copy.deepcopy(self._fixture.initial_state)

    # -------------------------------------------------------------------------
    # Command handling
    # -------------------------------------------------------------------------

    def handle_command(
        self,
        command_type: str,
        data: dict[str, str],
        *,
        strict: bool = False,
    ) -> CommandResponse:
        """Process a command against the fixture and mutate state accordingly.

        Looks up the command key (derived from data) in the fixture's
        command_responses for the given command_type. Applies the response delta
        to the current state dict if status is "responded".

        Args:
            command_type: MQTT command type, e.g. "STATE-SET".
            data: Command data dict, e.g. {"fnsp": "0005"}.
            strict: If True, raises CommandNotFoundError when the command key is
                    not in the fixture. If False (default), the command is treated
                    as "no_response" silently. Use strict=True in tests that want
                    to catch fixture coverage gaps.

        Returns:
            The CommandResponse from the fixture (status, delta, response).

        Raises:
            CommandNotFoundError: If strict=True and the command key is not found.
        """
        command_key = self._build_command_key(data)
        responses_for_type = self._fixture.command_responses.get(command_type, {})
        response = responses_for_type.get(command_key)

        if response is None:
            if strict:
                raise CommandNotFoundError(
                    f"Command key {command_key!r} not found in fixture "
                    f"{self._fixture.metadata.product_type!r} "
                    f"for command type {command_type!r}."
                )
            return CommandResponse(status="no_response")

        if response.status == "responded":
            self._state.update(response.delta)

        return response

    def _build_command_key(self, data: dict[str, str]) -> str:
        """Build the fixture lookup key from a command data dict.

        For single-key commands: returns "{key}={value}".
        For multi-key commands: returns keys sorted and joined, e.g.
          "ancp=CUST&osal=0090&osau=0350".

        Args:
            data: Command data dict.

        Returns:
            Command key string for fixture lookup.
        """
        if len(data) == 1:
            key, value = next(iter(data.items()))
            return f"{key}={value}"
        return "&".join(f"{k}={v}" for k, v in sorted(data.items()))

    # -------------------------------------------------------------------------
    # MQTT payload helpers
    # -------------------------------------------------------------------------

    def as_current_state_payload(self) -> dict[str, Any]:
        """Return the current state as a CURRENT-STATE MQTT message dict.

        Suitable for passing directly to the coordinator's MQTT message handler
        in tests that simulate receiving a status update.

        Returns:
            Dict formatted as a Dyson CURRENT-STATE MQTT payload.
        """
        return {
            "msg": "CURRENT-STATE",
            "product-state": copy.deepcopy(self._state),
        }

    def as_state_change_payload(self, delta: dict[str, str]) -> dict[str, Any]:
        """Return a STATE-CHANGE MQTT message dict for a given delta.

        The delta represents the fields that changed. Before-values are derived
        from the current state.

        Args:
            delta: Dict of state keys that changed, with their new values.

        Returns:
            Dict formatted as a Dyson STATE-CHANGE MQTT payload.
        """
        before = {k: self._state.get(k, "UNKNOWN") for k in delta}
        after = delta
        product_state = {k: [before[k], after[k]] for k in delta}
        return {
            "msg": "STATE-CHANGE",
            "product-state": product_state,
        }

    def as_environmental_payload(self) -> dict[str, Any] | None:
        """Return the environmental state as an ENVIRONMENTAL-CURRENT-SENSOR-DATA payload.

        Returns:
            Dict formatted as a Dyson environmental MQTT payload, or None if not available.
        """
        if not self._environmental_state:
            return None
        return {
            "msg": "ENVIRONMENTAL-CURRENT-SENSOR-DATA",
            "data": copy.deepcopy(self._environmental_state),
        }

    # -------------------------------------------------------------------------
    # Convenience properties
    # -------------------------------------------------------------------------

    @property
    def product_type(self) -> str:
        """Device product type code."""
        return self._fixture.metadata.product_type

    @property
    def serial_number(self) -> str:
        """Sanitized serial number from the fixture."""
        return self._fixture.metadata.serial_number

    @property
    def capabilities(self) -> list[str]:
        """Device capabilities list from the fixture."""
        return self._fixture.metadata.capabilities

    @property
    def device_category(self) -> str:
        """Device category from the fixture."""
        return self._fixture.metadata.device_category

    @property
    def fixture(self) -> DeviceFixture:
        """The underlying DeviceFixture."""
        return self._fixture

    # -------------------------------------------------------------------------
    # Mock integration helpers
    # -------------------------------------------------------------------------

    def build_coordinator_mock(self) -> MagicMock:
        """Build a MagicMock coordinator pre-populated with this device's state.

        Returns a MagicMock configured so that coordinator.device.state returns
        this mock's current state dict, and coordinator.serial_number returns
        the fixture serial number.

        This is the primary integration point between DeviceMock and the existing
        coordinator-based test patterns.

        Returns:
            A MagicMock that mimics DysonDataUpdateCoordinator with device state
            sourced from this DeviceMock.

        Example:
            coordinator = device_mock.build_coordinator_mock()
            entity = MyFanEntity(coordinator)
            assert entity.is_on == (device_mock.get_state()["fpwr"] == "ON")
        """
        from unittest.mock import MagicMock
        coordinator = MagicMock()
        coordinator.serial_number = self.serial_number
        coordinator.device = MagicMock()
        coordinator.device.state = self.get_state()
        coordinator.device.environmental_state = self.get_environmental_state()
        coordinator.data = self.get_state()
        # Capabilities
        coordinator.capabilities = self.capabilities
        return coordinator
```

---

## Command Key Resolution

The `_build_command_key` method determines how `handle_command(data)` maps to an entry in
the fixture's `command_responses`. The rules are:

| Scenario | Example `data` | Resulting key |
|---|---|---|
| Single field | `{"fnsp": "0005"}` | `"fnsp=0005"` |
| Multi-field (alphabetical) | `{"osau": "0350", "osal": "0090"}` | `"osal=0090&osau=0350"` |

Multi-field keys are stored in the fixture in alphabetical order. The capture service must
write them in the same order. The mock must resolve them in the same order.

---

## State Mutation Semantics

When `handle_command` receives a `responded` `CommandResponse`:

```python
# Before: self._state = {"fpwr": "ON", "fnsp": "0003", "fmod": "FAN", "auto": "OFF"}
# Command: handle_command("STATE-SET", {"fnsp": "AUTO"})
# Fixture delta: {"fnsp": "AUTO", "fmod": "AUTO", "auto": "ON"}
# After: self._state = {"fpwr": "ON", "fnsp": "AUTO", "fmod": "AUTO", "auto": "ON"}
```

Key properties:
- Only the keys in the delta are updated. Other state keys are unchanged.
- The delta is applied with `dict.update()` — it is a merge, not a replacement.
- This mirrors how real Dyson STATE-CHANGE messages work.

---

## `as_state_change_payload` Detail

The `STATE-CHANGE` MQTT message format uses before/after pairs:

```json
{
  "msg": "STATE-CHANGE",
  "product-state": {
    "fnsp": ["0003", "AUTO"],
    "fmod": ["FAN",  "AUTO"],
    "auto": ["OFF",  "ON"]
  }
}
```

`as_state_change_payload(delta)` produces this format. The before-values are taken from the
mock's state **at the time of the call** (before the delta is applied). Tests that need to
simulate a STATE-CHANGE message arriving from the device should call
`as_state_change_payload` before calling `handle_command`, or use the `CommandResponse.delta`
directly to construct the payload.

---

## Error Handling

| Condition | Default behavior (`strict=False`) | Strict behavior (`strict=True`) |
|---|---|---|
| Command key not in fixture | Returns `CommandResponse(status="no_response")` | Raises `CommandNotFoundError` |
| Command type not in fixture | Returns `CommandResponse(status="no_response")` | Raises `CommandNotFoundError` |
| `no_response` status | State unchanged, returns the `CommandResponse` | Same |
| `rejected` status | State unchanged, returns the `CommandResponse` | Same |

---

## Testing the DeviceMock Itself

`DeviceMock` and `DeviceFixture` must have their own unit tests in
`tests/device_mocks/test_device_mock.py` and `tests/device_mocks/test_device_fixture.py`.
These tests use an in-memory fixture dict (not a file on disk) to avoid coupling to any
specific fixture file.

Required test coverage:

- `DeviceFixture.from_file` raises `UnsupportedFixtureVersionError` for unknown versions
- `DeviceFixture.from_file` raises `UnsanitizedFixtureError` for real serial numbers
- `DeviceFixture.discover_all` returns empty list for missing directory
- `DeviceFixture.discover_all` returns one fixture per `.json` file found
- `DeviceMock.handle_command` applies full delta for `responded` status
- `DeviceMock.handle_command` does not mutate state for `no_response`
- `DeviceMock.handle_command` does not mutate state for `rejected`
- `DeviceMock.handle_command` raises `CommandNotFoundError` when `strict=True`
- `DeviceMock.reset` restores state to `initial_state`
- `DeviceMock.as_current_state_payload` returns correct MQTT format
- `DeviceMock.as_state_change_payload` returns correct before/after format
- `DeviceMock.build_coordinator_mock` returns a mock with correct state dict
- Multi-field command key resolution is alphabetically sorted
