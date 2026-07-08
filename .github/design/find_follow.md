# Find+Follow Support (PC3 / Type 438)

This document describes the design for supporting the Find+Follow feature on Dyson devices
that expose the `soon` and `sost` state keys — first observed on the
Dyson Find+Follow Purifier Cool PC3 (model `TP14-AC`, product type `438`, variant `N`).

## Background

Find+Follow is a camera-assisted oscillation feature that uses the device's built-in camera
to identify people in the room and automatically oscillate the fan toward them.  When more
than one person is detected, the fan cycles between their positions.

The feature has three operational states:

- **Off** — camera is inactive; standard oscillation behaves normally.
- **Find+Follow** (`NOD` engine state) — camera is active; device tracks detected people
  and directs airflow accordingly.
- **Scanning** — camera is performing an immediate (forced) sweep to reacquire people.
  After the scan the device transitions automatically back to the Find+Follow state.

From the user's perspective this closely resembles the **Breeze** oscillation mode on
humidifier-capable fans (`ancp=BRZE`): it replaces the user-controlled oscillation sweep
with an automatic pattern driven by the device's own logic.

## MQTT State Keys

### Writable

| Key    | Description                                           | Values                 |
|--------|-------------------------------------------------------|------------------------|
| `soon` | Find+Follow on/off command and forced scan trigger    | `ON`, `OFF`, `SCAN`    |

### Read-only

| Key    | Description                                           | Values                            |
|--------|-------------------------------------------------------|-----------------------------------|
| `sost` | Find+Follow engine status (reported by device)        | `OFF`, `NOD` (sleep/standby), `SCAN` (actively scanning) |
| `ancp` | Angle current preset; changes to `SMRT` when F+F is active | `CUST`, `SMRT`, `0045`, `0090`, etc. |

> **Note:** `ancp=SMRT` is a side-effect of enabling Find+Follow, not its primary control.
> Always use `soon` to enable/disable the feature.  Do not rely on `ancp` alone for state
> detection, as `ancp` can be `SMRT` briefly during transitions.

## Observed MQTT Traces (PC3, firmware 438NPF.01.01.007.0006)

### Enable Find+Follow
```
Command:  {"msg":"STATE-SET","data":{"soon":"ON"},"mode-reason":"RAPP"}
State:    ancp: ["CUST","SMRT"], soon: ["OFF","ON"]
```

### Disable Find+Follow
```
Command:  {"msg":"STATE-SET","data":{"soon":"OFF"},"mode-reason":"RAPP"}
State:    ancp: ["SMRT","CUST"], soon: ["ON","OFF"]
```

### Force Scan (from Off)
```
Command:  {"msg":"STATE-SET","data":{"soon":"SCAN"},"mode-reason":"RAPP"}
State 1:  soon: ["OFF","SCAN"], sost: ["OFF","SCAN"]
State 2:  soon: ["SCAN","SCAN"], sost: ["SCAN","SCAN"]   (scan in progress)
Settles:  soon: ["SCAN","ON"],  sost: ["SCAN","NOD"]     (returns to F+F on)
```

### Force Scan (from On)
```
Command:  {"msg":"STATE-SET","data":{"soon":"SCAN"},"mode-reason":"RAPP"}
State 1:  soon: ["ON","SCAN"],  sost: ["NOD","SCAN"]
State 2:  soon: ["SCAN","SCAN"],sost: ["SCAN","SCAN"]    (scan in progress)
Settles:  soon: ["SCAN","ON"],  sost: ["SCAN","NOD"]     (returns to F+F on)
```

## Capability Gating

The PC3 device does **not** expose a dedicated capability flag for Find+Follow.  Its
capability list (as of firmware 438NPF.01.01.007.0006) is:

```
AdvanceOscillationDay1, Scheduling, EnvironmentalData, ExtendedAQ, ChangeWifi, Matter
```

Find+Follow support must therefore be detected at runtime from device state data:

1. The `soon` key must be present in the `product-state` of the first `STATE-CHANGE`
   message received from the device.

This is the same pattern used for tilt oscillation (`oton` key detection) and horizontal
oscillation support (`oson` key detection) in `fan.py`.

No device-category restriction is applied — if a future non-`ec` device reports `soon`,
the entity will be created for it as well.

## Interaction with Horizontal Oscillation

Find+Follow is **independent** of horizontal oscillation (`oson`/`osal`/`osau`/`ancp`
presets).  The PC3 reports `oson=OFF` while Find+Follow is active; it manages its own
internal oscillation pattern without setting `oson=ON`.

Consequently:

- The fan entity's `oscillating` property (driven by `oson`) correctly shows `False`
  while Find+Follow is active.  No override is applied.
- The existing `DysonOscillationModeSelect` entity is unaffected.  When `ancp=SMRT`
  none of its named presets match, so it falls through to "Custom" — this is acceptable
  because users control Find+Follow exclusively through the dedicated entity.
- No mutual-exclusivity logic is required between Find+Follow and horizontal oscillation.

## HA Entity: `DysonFindFollowModeSelect`

**Platform**: `select`
**File**: `select.py` (alongside `DysonTiltOscillationModeSelect`)
**Translation key**: `find_follow_mode`
**Icon**: `mdi:account-eye`

### Options

```
["Off", "Find+Follow", "Scanning"]
```

### State Reading Logic

The `soon` key is the authoritative source for current state because it directly reflects
the last command outcome and is updated synchronously with device transitions.

| `soon` value | Displayed option |
|--------------|-----------------|
| `"OFF"`      | `Off`           |
| `"ON"`       | `Find+Follow`   |
| `"SCAN"`     | `Scanning`      |
| absent / unknown | `Off` (safe fallback) |

`sost` is not used for state display.  It is useful for diagnostics but `soon` is
sufficient and more consistent.

### Command Payloads

| Selected option | `soon` value sent |
|-----------------|------------------|
| `Off`           | `OFF`            |
| `Find+Follow`   | `ON`             |
| `Scanning`      | `SCAN`           |

`Scanning` is an action-like selection: after the scan completes the device automatically
returns `soon=ON`, which causes the select to display `Find+Follow` again.  No HA-side
timer or state reset is needed.

### Entity Creation in `async_setup_entry`

```python
# Add Find+Follow select for devices that report the 'soon' state key.
# No dedicated capability flag exists; presence of 'soon' in product-state is
# the sole gating criterion (same pattern as 'oton' for tilt oscillation).
product_state = coordinator.data.get("product-state", {}) if coordinator.data else {}
if "soon" in product_state:
    entities.append(DysonFindFollowModeSelect(coordinator))
```

## `device.py` Method: `set_find_follow`

```python
async def set_find_follow(self, mode: str) -> None:
    """Set Find+Follow mode.

    Args:
        mode: One of ``"ON"``, ``"OFF"``, or ``"SCAN"``.

    Raises:
        ValueError: If *mode* is not one of the supported values.
    """
    if mode not in ("ON", "OFF", "SCAN"):
        raise ValueError(f"Invalid Find+Follow mode '{mode}'. Must be ON, OFF, or SCAN.")
    await self.send_command("STATE-SET", {"soon": mode})
```

## `const.py` Constants

```python
STATE_KEY_FIND_FOLLOW: Final = "soon"         # Find+Follow on/off/scan command key
STATE_KEY_FIND_FOLLOW_STATUS: Final = "sost"  # Find+Follow engine status (read-only)
```

## Open Items

- Confirm whether `sost` ever diverges from the `soon`-derived state in edge cases
  (e.g. camera hardware fault).  If it does, add a fallback that marks the entity
  unavailable when `sost` indicates an error state.
- Confirm whether future Dyson devices add a capability flag for Find+Follow
  (e.g. `FindAndFollow`, `SmartOscillation`).  If added, prefer capability-gating
  over key-detection for cleaner setup-time determination.
- Investigate whether `soon=SCAN` can be sent when Find+Follow is `OFF` to perform
  a one-shot scan without entering continuous tracking mode (trace shows it does
  enable F+F after the scan; this may be intentional device behaviour).
