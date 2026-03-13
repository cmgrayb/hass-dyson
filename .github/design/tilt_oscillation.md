# Tilt Oscillation Support

This document describes the design for supporting tilt oscillation on Dyson devices
that expose vertical (tilt) oscillation in addition to the existing horizontal oscillation.

## Background

Certain Dyson fan models include a motorised tilt axis that can sweep up and down between
fixed angles or perform an automatic "Breeze" sweep.  This is distinct from horizontal
oscillation (`oson`/`osal`/`osau`/`ancp`) and the two axes can be active simultaneously,
producing a wave-pattern airflow.

## MQTT State Keys

### Writable

| Key | Constant | Description |
|-----|----------|-------------|
| `oton` | `STATE_KEY_TILT_OSCILLATION_ON` | Enable/disable tilt oscillation (`ON`/`OFF`) |
| `otal` | `STATE_KEY_TILT_OSCILLATION_LOWER` | Lower tilt angle (`0000`–`0050`, or `0359` for Breeze) |
| `otau` | `STATE_KEY_TILT_OSCILLATION_UPPER` | Upper tilt angle (`0000`–`0050`, or `0359` for Breeze) |
| `anct` | `STATE_KEY_TILT_ANGLE_CONTROL` | Angle control preset (`CUST` or `BRZE`) |

### Read-only (internal only — no HA entity)

| Key | Constant | Description |
|-----|----------|-------------|
| `otcs` | `STATE_KEY_TILT_OSCILLATION_STATUS` | Oscillation tilt control status (`ON`/`OFF`) |

`otcs` mirrors `oton` in the observed data and is used internally by the device firmware.
It is tracked in `_state_data` but not exposed as a Home Assistant entity.

## Observed Behaviour

`otal` and `otau` are always set to the same value.  `otal` is therefore authoritative for
reading the current tilt angle.  The `0359` value is a sentinel meaning "full/automatic sweep"
and is only valid when Breeze mode is active.

Numeric `anct` presets (e.g. `0025`, `0050`) have not been confirmed to work.  Until
verified, only `CUST` and `BRZE` should be sent.

## Capability Gating

The example device (Dyson BP04, product type `664`) has none of the `AdvanceOscillationDay0/Day1`
capability flags.  Its capability list is:

```
Scheduling, EnvironmentalData, ExtendedAQ, ChangeWifi
```

Tilt oscillation must therefore be detected at runtime from device state data, using
the same pattern as `_check_oscillation_support()` in `fan.py`:

1. `ec` must be present in `device_category` (rules out robot vacuums and lighting).
2. `oton` key must be present in the `product-state` of the first `STATE-CHANGE` message
   received from the device.

A `_check_tilt_oscillation_support()` helper (mirroring `_check_oscillation_support()`) is
used both in `select.py`'s `async_setup_entry` (to decide whether to add the entity) and
as an `available` guard inside the entity itself in case state data is absent at setup.

## HA Entity: `DysonTiltOscillationModeSelect`

**Platform**: `select`
**File**: `select.py` (alongside `DysonOscillationModeSelect`)

### Options

```
["Off", "25°", "50°", "Breeze"]
```

`Breeze` is always included.  No `Custom` option is exposed.

### State Reading Logic

| `oton` | `otal` | Displayed option |
|--------|--------|-----------------|
| `ON`   | any    | `Breeze`        |
| `OFF`  | `0000` | `Off`           |
| `OFF`  | `0025` | `25°`           |
| `OFF`  | `0050` | `50°`           |
| `OFF`  | other  | `Off` (safe fallback) |

### Command Payloads

| Option  | `oton` | `anct` | `otal` | `otau` |
|---------|--------|--------|--------|--------|
| `Off`   | `OFF`  | —      | —      | —      |
| `25°`   | —      | `CUST` | `0025` | `0025` |
| `50°`   | —      | `CUST` | `0050` | `0050` |
| `Breeze`| `ON`   | `BRZE` | `0359` | `0359` |

`Off` sends only `oton=OFF`, leaving the last angle intact on the device (consistent with
how `oson=OFF` works for horizontal oscillation).

## Interaction with Horizontal Oscillation

Tilt oscillation (`oton`) and horizontal oscillation (`oson`) are **independent** and can
both be active simultaneously.  No mutual exclusivity logic is required in either entity.

## Open Items

- Confirm whether numeric `anct` values (`0025`, `0050`) are accepted by the device
  firmware (may simplify future angle expansion).
- Confirm maximum tilt angle — only 0°, 25°, and 50° have been observed to date.
