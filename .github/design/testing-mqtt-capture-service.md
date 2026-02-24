# MQTT Device Capture Service Specification

## Overview

This document specifies the Home Assistant Action (service call) that captures real device
MQTT behavior into fixture files. The fixture files are then sanitized and committed to the
repository for use in tests.

The capture service is a **developer/advanced-user tool**, not a routine operational
feature. It is expected to be used infrequently — primarily when a new device type is added
to the integration or when a firmware update may have changed device behavior.

See [testing-mqtt-fixture-architecture.md](testing-mqtt-fixture-architecture.md) for context
and [testing-mqtt-fixture-schema.md](testing-mqtt-fixture-schema.md) for the output schema.

---

## User-Facing Documentation Requirements

The capture service must include prominent documentation warning users that:

1. **The device will change states** over the course of the capture. All supported
   configuration options will be cycled through (enabled, disabled, set to various values).
2. **The device will be restored** to its state at the time the action was started, to the
   best of the integration's ability.
3. **Restoration is best-effort only.** If the capture is interrupted (HA restart, network
   failure, power loss), the device may be left in a non-default state that the user must
   manually correct.
4. **This action is not intended for regular use.** It should only be run by developers or
   users who are contributing to the integration.
5. **The device must be connected** (local MQTT or cloud MQTT) for the capture to succeed.
   The service uses the device's existing connection — no separate connection is opened.
   Cloud-connected devices are supported, but captures may be slower due to network latency
   and are subject to AWS IoT publish rate limits (see Cloud Connection Caveats below).

---

## HA Action Definition

### Service Name

```yaml
hass_dyson.capture_device_fixture
```

### Service Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `serial_number` | `string` | Yes | Serial number of the device to capture |
| `command_timeout` | `integer` | No | Seconds to wait for a device response per command. Default: `5` |
| `include_probe_commands` | `boolean` | No | Whether to send probe commands beyond the known set for the device category. Default: `true` |
| `output_path` | `string` | No | Path relative to `/config/` to write the fixture file. Default: `dyson_fixtures/` |
| `command_delay` | `number` | No | Minimum seconds between commands. Default: `0.5`. Increase to `2.0` or more if the device is connected via cloud MQTT to avoid AWS IoT rate limiting. |

### Example Service Call (YAML)

```yaml
service: hass_dyson.capture_device_fixture
data:
  serial_number: VS6-EU-HJA1234A
  command_timeout: 5
  include_probe_commands: true
```

---

## Cloud Connection Caveats

The capture service works with both local MQTT and cloud AWS IoT WebSocket connections
because `DysonDevice` handles both transports transparently using the same paho-mqtt client
and identical MQTT message formats (STATE-SET, STATE-CHANGE, topics).

When the device is connected via cloud MQTT, the following applies:

| Concern | Impact | Mitigation |
|---|---|---|
| Round-trip latency | ~200–500ms added per command vs local LAN | `command_timeout` default of `5s` remains sufficient; increase if needed |
| AWS IoT publish rate limiting | Rapid commands may be throttled, causing spurious `no_response` results | Use `command_delay=2.0` or higher when on cloud connection |
| Credential expiry | Cloud credentials have a TTL; a long session may expire mid-capture | The existing coordinator reconnection logic handles re-authentication; if capture fails mid-way, commands from that point are recorded as `no_response` |

The service determines the active connection type from `coordinator.device.connection_status`
and logs it at `INFO` level at the start of the capture. If cloud-connected, it also logs
a recommendation to increase `command_delay`.

---

## Capture Sequence

The capture service executes the following sequence. Each step is logged at `INFO` level.
Failures at any step are logged at `WARNING` or `ERROR` and do not abort the sequence unless
the device becomes unreachable.

```
1.  Resolve device from serial number
2.  Verify device is connected (local or cloud MQTT). Log connection type at INFO level.
    If cloud-connected and command_delay < 1.0, log a WARNING recommending command_delay >= 2.0.
3.  Request and record CURRENT-STATE → stored as restore_state and initial_state
4.  Request and record ENVIRONMENTAL-CURRENT-SENSOR-DATA → stored as environmental_state
5.  Request and record CURRENT-FAULTS → stored for fault_codes seed
6.  Build command list for device category (see Command Sets below)
7.  For each command in list:
    a. Log command being sent
    b. Publish STATE-SET command via MQTT
    c. Wait up to command_timeout seconds for STATE-CHANGE response
    d. Record response with status: responded / no_response / rejected
    e. Re-request CURRENT-STATE to ensure mock initial_state is coherent after restore
8.  Restore device to restore_state captured in step 3
    a. Publish STATE-SET with the full restore_state dict
    b. Wait for STATE-CHANGE confirmation (up to command_timeout * 2 seconds)
    c. Log success or failure of restore
9.  Assemble fixture JSON document
10. Apply sanitization (see Sanitization section)
11. Write fixture to output_path/{product_type}.json
12. Fire hass_dyson_fixture_captured event with output path for user notification
```

---

## Command Sets

### How the Command Set is Built

1. **Base set**: The integration's known state keys for the device category (see below).
2. **Capability filter** (Option A, primary): Commands that are only valid for specific
   capabilities are included only if the device has that capability.
3. **Probe set** (Option B fallback): If `include_probe_commands=true`, additional commands
   from the full `ec` universe that are not in the base set are appended. The device's
   response (or silence) determines whether they are relevant.

### ec Command Set

The `ec` command set covers all known state keys in `const.py` plus probe keys observed in
community research. Each command is sent as a single-key `STATE-SET` message.

#### Core Commands (all ec devices)

| Command Key | Values Sent | Capability Guard |
|---|---|---|
| `fpwr` | `ON`, `OFF` | None |
| `fnsp` | `0001`, `0005`, `0010`, `AUTO` | None |
| `nmod` | `ON`, `OFF` | None |
| `oson` | `ON`, `OFF` | None |
| `rhtm` | `ON`, `OFF` | None |
| `fdir` | `ON`, `OFF` | None |
| `sltm` | `0030`, `OFF` | None |

#### Oscillation Commands

| Command Key | Values Sent | Capability Guard |
|---|---|---|
| `ancp` | `BRZE` | `AdvanceOscillationDay1` **and** `Humidifier` |
| `ancp` | `0045`, `0090`, `0180`, `0315` | `AdvanceOscillationDay1` |
| `ancp` | `0015`, `0040`, `0070` | `AdvanceOscillationDay0` |
| `osau` | `0090`, `0180`, `0350` | `AdvanceOscillationDay1` |
| `osal` | `0090`, `0180`, `0090` | `AdvanceOscillationDay1` |

#### Heating Commands

| Command Key | Values Sent | Capability Guard |
|---|---|---|
| `hmod` | `HEAT`, `OFF` | `Heating` |
| `ffoc` | `ON`, `OFF` | `Heating` |
| `tilt` | `ON`, `OFF` | `Heating` |
| `ract` | `ON`, `OFF` | `Heating` |
| `htemp` | `2940`, `2980`, `3000` | `Heating` |

#### Humidifier Commands

| Command Key | Values Sent | Capability Guard |
|---|---|---|
| `hume` | `HUMD`, `OFF` | `Humidifier` |
| `haut` | `ON`, `OFF` | `Humidifier` |
| `humt` | `0030`, `0040`, `0050` | `Humidifier` |
| `wath` | `2025`, `1350`, `0675` | `Humidifier` |

#### Probe Commands (sent when `include_probe_commands=true`)

These are commands observed in community research or other Dyson device generations that
may or may not be supported by a given device. Failures and non-responses are recorded as
fixture data, documenting what the device does NOT support.

| Command Key | Values Sent | Notes |
|---|---|---|
| `bril` | `0000`, `0050`, `0100` | Brightness (lighting devices) |
| `colu` | `2700`, `5000`, `6500` | Color temperature |
| `cfad` | `ON`, `OFF` | Carbon filter active discharge |

### robot Command Set

| Command Key / Command Type | Values / Notes | Capability Guard |
|---|---|---|
| `REQUEST-CURRENT-STATE` | State request | None |
| `START/FULL_CLEAN` | Start cleaning | None |
| `PAUSE` | Pause cleaning | None |
| `RESUME` | Resume cleaning | None |
| `ABORT` | Abort cleaning | None |
| Power level set | Values per capability type | `halfPower`/`fullPower` or `1`/`2`/`3` levels |

### vacuum Command Set

| Command | Notes |
|---|---|
| Standard vacuum control commands | Defined per vacuum model |

---

## MQTT Communication During Capture

### Topics

The capture service uses the device's existing MQTT connection managed by the coordinator.
It does **not** open a separate MQTT connection.

| Direction | Topic Pattern | Purpose |
|---|---|---|
| Publish | `{root_topic}/{serial}/command` | Send STATE-SET and REQUEST-* commands |
| Subscribe | `{root_topic}/{serial}/status/current` | Receive STATE-CHANGE and CURRENT-STATE |
| Subscribe | `{root_topic}/{serial}/status/fault` | Receive FAULT responses |

### STATE-SET Message Format

```json
{
  "msg": "STATE-SET",
  "time": "2026-01-15T12:00:00.000Z",
  "mode-reason": "RAPP",
  "data": {
    "{state_key}": "{value}"
  }
}
```

For multi-field restore commands, multiple keys are included in `data`.

### Response Detection

The capture service registers a temporary MQTT message handler for each command. The handler:

1. Listens for a `STATE-CHANGE` or `CURRENT-STATE` message on the status topic.
2. Extracts the `product-state` delta from the message.
3. Returns the delta as the `responded` payload.
4. If `command_timeout` elapses with no message received, records `no_response`.
5. If a message is received that contains an error key (`err`), records `rejected` with the
   full response payload.

### Restore Logic

The restore command is a `STATE-SET` message containing the full `restore_state` dict
captured at the beginning of the sequence. This is sent as a single multi-key command to
minimize the number of state transitions the device goes through.

If the restore command does not produce a confirming `STATE-CHANGE` within
`command_timeout * 2` seconds, the failure is logged at `ERROR` level and noted in the
persistent notification.

---

## Output File Handling

### File Path

```
/config/{output_path}/{product_type}.json
```

Where `{product_type}` is the device's Dyson type code (e.g. `438`, `527`).

If the file already exists, it is **overwritten** without warning. This is intentional —
captures are expected to be reviewed before committing.

### Post-Write Notification

After writing the file, the service fires a persistent notification in HA:

```
Title: Dyson fixture capture complete
Message: Fixture written to /config/dyson_fixtures/438.json.
         Download this file and follow the instructions in the developer documentation
         to sanitize and commit it to the repository.

         WARNING: Review the file before committing to ensure no personal data is present.
```

---

## Sanitization

The capture service applies sanitization at write time (before writing to disk). The
sanitization is performed by `tests/device_mocks/sanitizer.py`, which is importable by
both the capture service and standalone CLI usage.

### Sanitization Map

| What | Pattern Matched | Replacement |
|---|---|---|
| Serial number in `metadata` | Any string | `TEST-{product_type}-0001A` |
| Serial number in MQTT topic references | e.g. `VS6-EU-HJA1234A` | `TEST-{product_type}-0001A` |
| Device name in `metadata` | Any string | `Test Dyson Device` |
| MQTT credentials | Any credential-looking string | `test-mqtt-password-sanitized` |
| IPv4 addresses | Regex `\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}` | `192.168.1.100` |
| WiFi SSID (if present) | Any string | `TestNetwork` |
| WiFi password (if present) | Any string | `test-wifi-password-sanitized` |

### Developer Responsibility

The sanitizer is a best-effort tool. Developers **must** review the output file manually
before committing, especially the `metadata.notes` field (which is free text and not
sanitized) and any `sample_payload` fields in `fault_codes`.

---

## Error Handling

| Error Condition | Behavior |
|---|---|
| Device not found by serial number | Raise `ServiceValidationError`, log at `ERROR` |
| Device not connected (neither local nor cloud) | Raise `ServiceValidationError` with message directing user to check device connectivity and integration configuration |
| Device disconnects mid-capture | Log `WARNING` per command, mark remaining commands as `no_response`, continue to restore attempt |
| Restore fails | Log `ERROR`, fire persistent notification with manual restore instructions |
| MQTT publish fails | Log `WARNING`, mark command as `no_response`, continue |
| File write fails | Log `ERROR`, raise `HomeAssistantError` |

---

## Implementation Location

| Component | Location |
|---|---|
| Service handler | `custom_components/hass_dyson/services.py` — `async_capture_device_fixture()` |
| Service schema | `custom_components/hass_dyson/services.yaml` — `capture_device_fixture` |
| Sanitizer | `tests/device_mocks/sanitizer.py` — `sanitize_fixture()` |
| Command sets | `custom_components/hass_dyson/const.py` — `EC_CAPTURE_COMMANDS`, `ROBOT_CAPTURE_COMMANDS` |
| Output path default | `custom_components/hass_dyson/const.py` — `DEFAULT_FIXTURE_OUTPUT_PATH = "dyson_fixtures/"` |

---

## Testing the Capture Service Itself

The capture service must have its own unit tests in `tests/test_services.py` (or a
dedicated `tests/test_capture_service.py`). These tests should:

- Mock the MQTT client and coordinator
- Verify the full capture sequence is executed in order
- Verify that `no_response` is recorded when the mock MQTT returns nothing
- Verify that `rejected` is recorded when the mock MQTT returns an error payload
- Verify that the restore command is sent after the capture sequence regardless of errors
- Verify that the output file is written with correct sanitization applied
- Verify that `ServiceValidationError` is raised for unknown serial numbers
- Verify that `ServiceValidationError` is raised for cloud-only devices
