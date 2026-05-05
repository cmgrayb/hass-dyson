# BLE Lights Implementation

## Overview

This document describes the implementation of Bluetooth Low Energy (BLE) support
for Dyson lights, starting with the **Dyson Lightcycle Morph (CD06)**.  It
complements the protocol reference in `.github/design/ble_lights.md` with
implementation-level decisions and conventions for future contributors.

---

## Architecture

```
Config Entry (type: ble_light)
        │
        ▼
DysonBLEDataUpdateCoordinator   ← asyncio.Task "dyson-ble-<serial>"
        │                             connects, auths, keepalives
        │   hass.bus.async_fire(EVENT_BLE_STATE_CHANGE)
        │◄──────────────────────────────────────────────
        │                        DysonBLEDevice
        │                          (ble_device.py)
        ├──► DysonLightEntity (light.py)
        └──► DysonMotionBinarySensor (binary_sensor.py)
```

State flows *up* via events:

```
DysonBLEDevice._fire_state_change()
    → hass.bus.async_fire(EVENT_BLE_STATE_CHANGE, {...})
    → DysonBLEDataUpdateCoordinator._handle_ble_event()
    → self.async_set_updated_data(state_dict)
    → CoordinatorEntity._handle_coordinator_update() on all entities
    → UI refresh
```

Commands flow *down* directly:

```
Entity.async_turn_on() / async_turn_off() / async_set_X()
    → coordinator.ble_device.set_*(...)
    → GATT characteristic write (response=False)
    → DysonBLEDevice._read_initial_state()   ← read-back for confirmation
    → DysonBLEDevice._fire_state_change()
```

---

## File Map

| File | Role |
|------|------|
| `custom_components/hass_dyson/ble_device.py` | BLE transport: framing, crypto, GATT ops |
| `custom_components/hass_dyson/coordinator.py` | `DysonBLEDataUpdateCoordinator` appended at end |
| `custom_components/hass_dyson/entity.py` | `DysonBLEEntity` base class appended at end |
| `custom_components/hass_dyson/light.py` | `DysonLightEntity` platform (NEW file) |
| `custom_components/hass_dyson/binary_sensor.py` | `DysonMotionBinarySensor` added; branching in `async_setup_entry` |
| `custom_components/hass_dyson/__init__.py` | `_setup_ble_device_entry`, BLE detection in `async_setup_entry` / `async_unload_entry` |
| `custom_components/hass_dyson/config_flow.py` | `async_step_ble_light`, `CONF_BLE_MAC/LTK/PROXY` imports, "ble_light" menu option |
| `custom_components/hass_dyson/const.py` | All BLE constants (UUIDs, message types, scaling bounds) |
| `custom_components/hass_dyson/manifest.json` | `"dependencies": ["bluetooth"]` |
| `.github/design/ble_lights.md` | Full protocol reference |

---

## Key Implementation Decisions

### No MQTT

Unlike fan/purifier devices, BLE lights use no MQTT.  The entire state
propagation chain uses the HA event bus (`EVENT_BLE_STATE_CHANGE`).

### Entry Type Detection

BLE entries are detected by the presence of `CONF_BLE_MAC` in `entry.data`.
The `hass.data[DOMAIN][entry.entry_id]` value for BLE entries is always a dict:

```python
{"ble_coordinator": DysonBLEDataUpdateCoordinator, "is_ble": True}
```

MQTT entries store the coordinator directly (not wrapped in a dict).  Every
platform that reads `hass.data[DOMAIN][entry.entry_id]` must check this.

### Coordinator Setup Order

`DysonBLEDataUpdateCoordinator.__init__` creates a placeholder `DysonBLEDevice`
with a zero-UUID account UUID.  `async_setup()` must be called immediately
after construction — it derives the real account UUID from the HA instance ID
and recreates the `DysonBLEDevice` before starting the BLE task.

### BLE Task Lifecycle

The coordinator starts a named `asyncio.Task("dyson-ble-<serial>")` that:

1. Obtains a `BleakClient` via HA's `bluetooth.async_last_service_info()` or
   falls back to MAC address.
2. Connects (retries 4×, 1.25 s apart).
3. Subscribes to auth-char notifications.
4. Performs LTK re-auth.
5. Reads initial state.
6. Subscribes to motion/flag notifications.
7. Polls state every 20 s while connected.
8. On disconnect, reconnects with backoff (5 / 15 / 30 / 60 s).

### Crypto

See `.github/design/ble_lights.md` §Crypto.  Summary:

- Key derivation: HKDF-SHA256 (empty salt), first 16 bytes of expand block 1.
- `g20c_encrypt`: AES-128-CBC (random IV) + HMAC-SHA256 over ciphertext.
- PROTOCOL.md summary (AES-GCM) is **wrong**; the actual code uses CBC+HMAC.

### Fragment Assembler

`DysonFragmentAssembler` reassembles multi-fragment BLE messages.  Header byte
encoding:

- First fragment: `header = 0x80 | (total_fragments - 1)`, followed by type byte.
- Subsequent fragments: `header = fragment_index & 0x7F`, no type byte.

`fragment_dyson_message()` produces frags with default capacity 20 bytes.

### Scaling

| HA value | Lamp value | Formula |
|----------|------------|---------|
| Brightness 0-255 | Percent 1-100 | `max(1, round(ha * 100 / 255))` |
| Brightness 0-255 | Percent 0-100 | `round(raw * 255 / 100)` (read-back) |
| Color temp mired | Kelvin uint16-LE | `round(1_000_000 / mired)`, clamped 2700-6500 |

---

## Adding Support for a New BLE Device

1. Study its GATT service and characteristic UUIDs (use `gatttool` or nRF Connect).
2. Add UUID constants to `const.py` (or reuse existing ones if shared).
3. Create (or extend) a device class in `ble_device.py` with read/write/notify methods.
4. Add a new coordinator subclass in `coordinator.py` if the lifecycle differs.
5. Create a platform file (e.g. `light_v2.py`, `fan_ble.py`).
6. Add entry-type detection in `__init__.py`.
7. Write tests in `tests/test_<type>.py` following patterns in `test_light.py`.

---

## Testing

BLE tests use `unittest.mock` and `pytest-asyncio` — no physical hardware needed.

### Key Mock Patterns

```python
# Mock BleakClient
mock_client = AsyncMock()
mock_client.is_connected = True
mock_client.read_gatt_char = AsyncMock(return_value=bytearray([0x01]))
mock_client.write_gatt_char = AsyncMock()
mock_client.start_notify = AsyncMock()

# Mock DysonBLEDevice
device = MagicMock(spec=DysonBLEDevice)
device.is_connected = True
device.set_power = AsyncMock()

# Mock coordinator
coord = MagicMock(spec=DysonBLEDataUpdateCoordinator)
coord.serial_number = "CD06-GB-HAA0001A"
coord.ble_device = device
coord.is_connected = True
coord.data = {"power": True, "brightness": 200, "color_temp_kelvin": 4000, "motion_detected": False}
```

### Running BLE-specific tests

```bash
python -m pytest tests/test_ble_device.py tests/test_light.py tests/test_binary_sensor.py -v
```

---

## Known Limitations

- **Button press required for fresh pairing**: First-time pairing via Dyson cloud
  requires the user to press the lamp's pairing button.  This is a one-time step.
- **LTK storage**: The LTK is stored in the config entry.  If the lamp resets its
  BLE keys, the user must re-pair and update the config entry.
- **Proxy support**: `CONF_BLE_PROXY` is stored but the coordinator does not yet
  implement targeted proxy selection (planned).
- **Single MAC**: Each config entry represents one lamp MAC.  Multi-lamp support
  requires multiple entries.
