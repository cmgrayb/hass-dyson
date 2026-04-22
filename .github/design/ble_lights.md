# BLE Lights Design

## Overview

This document captures the reverse-engineered BLE protocol for Dyson BLE-only lights,
specifically the **Lightcycle Morph (CD06)**.  The information was sourced from
S-Termi's contribution in discussion #334 and is used here with their authorization.

The Lightcycle Morph has no MQTT/Wi-Fi interface.  It is controlled exclusively via
Bluetooth Low Energy GATT characteristics.  Authentication uses a proprietary
challenge-response scheme (LTK re-auth) that, after a one-time cloud-assisted
fresh-pairing, operates fully offline.

The design is intentionally extensible: other BLE-only Dyson lights (future products)
are expected to share the same GATT service base UUID and message framing, requiring
only UUID remapping and minor state machine changes.

---

## GATT Characteristics (Lightcycle Morph / CD06)

All characteristics belong to the primary Dyson BLE service:

| Short ID | UUID | Direction | Format | Purpose |
|----------|------|-----------|--------|---------|
| Service | `2dd10010-1c37-452d-8979-d1b4a787d0a4` | — | — | Primary Dyson BLE service |
| 11011 | `2dd10011-1c37-452d-8979-d1b4a787d0a4` | read/write/notify | Framed msgs | Auth/messaging channel |
| 13 (RSSI) | `2dd10013-1c37-452d-8979-d1b4a787d0a4` | notify | 1 byte signed | RSSI proximity probe |
| 11000 | `2dd11000-1c37-452d-8979-d1b4a787d0a4` | read/write | 1 byte | Brightness 0–100 % |
| 11001 | `2dd11001-1c37-452d-8979-d1b4a787d0a4` | read/write | uint16 LE | Color temperature (Kelvin) |
| 11005 | `2dd11005-1c37-452d-8979-d1b4a787d0a4` | read/write | 1 byte | Power: `0x00`=off, `0x01`=on |
| 11006 | `2dd11006-1c37-452d-8979-d1b4a787d0a4` | read/notify | bytes | Runtime / scheduled-light flags |
| 11007 | `2dd11007-1c37-452d-8979-d1b4a787d0a4` | read/notify | bytes | Ambient sensor (not fully decoded) |
| 11008 | `2dd11008-1c37-452d-8979-d1b4a787d0a4` | notify | bytes | **Motion events** (non-zero = motion) |
| 11009 | `2dd11009-1c37-452d-8979-d1b4a787d0a4` | read/notify | bytes | Runtime flags (not fully decoded) |

All control writes use **write-without-response** (`response=False` in bleak).

---

## Message Framing on the Auth Characteristic (11011)

Every write to and notification from char 11011 uses a fragmented framing
identical to Dyson's internal `MessageFragmenter`/`MessageAssembler` (reverse-engineered
from the MyDyson Android app, Smali of `g20/a.java` and `g20/c.java`).

### Fragment header byte

```
First fragment:  0x80 | (total_fragments - 1)  followed by type_byte + payload_chunk
Subsequent:      fragment_index (0x01, 0x02…)  followed by payload_chunk
```

Putting it differently:  the high bit `0x80` marks the first fragment; the lower 7 bits
of the first fragment carry `(N-1)` where N is the total number of fragments.
Subsequent fragment headers carry the sequential 0-based index (starting at 1 for the
second fragment).

### Logical message layout (after reassembly)

```
[type_byte (1 byte)][payload (0-N bytes)]
```

### Default fragment capacity

The Dyson Android app uses **20 bytes** as its default fragment capacity (the MTU
negotiated during connection may increase this).  The integration uses 20 for
safety unless a larger MTU is confirmed.

### Fragment builder algorithm

```python
def fragment_dyson_message(type_id: int, payload: bytes, capacity: int = 20) -> list[bytes]:
    logical = bytes([type_id]) + payload
    data_per_fragment = capacity - 1          # 1 byte reserved for header
    total_fragments = max(1, math.ceil(len(logical) / data_per_fragment))
    fragments: list[bytes] = []
    for index in range(total_fragments):
        chunk = logical[index * data_per_fragment : (index + 1) * data_per_fragment]
        header = (0x80 | (total_fragments - 1)) if index == 0 else (index & 0x7F)
        fragments.append(bytes([header]) + chunk)
    return fragments
```

---

## Message Types

| Type | Direction | Purpose |
|------|-----------|---------|
| `0x01` | → lamp | PayloadA — fresh-pair auth step 1 |
| `0x02` | ← lamp | PayloadB — fresh-pair auth step 2 / LTK re-auth challenge |
| `0x03` | → lamp | Payload3 — fresh-pair final verify |
| `0x04` | → lamp | Hello — start fresh pairing |
| `0x05` | ← lamp | Unique product code (32 bytes) |
| `0x06` | → lamp | LTK re-auth PayloadA (82 bytes) |
| `0x07` | ← lamp | LTK re-auth PayloadB |
| `0x08` | → lamp | LTK re-auth PayloadC (66 bytes) |
| `0x09` | → lamp | apiRanNum / session nonce |
| `0x0A` | → lamp | Request product info |
| `0x0B` | ← lamp | Product info response (8 or 16 bytes) |
| `0x0C` | → lamp | RSSI / proximity probe (empty payload) |
| `0x0D` | ← lamp | User confirmed pairing (Flash button pressed) |
| `0x26` | ← lamp | Connection Established — auth complete |

---

## Fresh Pairing Handshake (requires physical button press)

```
Integration / Bridge                Lamp
  │  GATT connect                    │
  ├─────────────────────────────────▶│
  │  0x0C  RSSI probe (empty)        │
  ├─────────────────────────────────▶│
  │  0x04  Hello (empty)             │
  ├─────────────────────────────────▶│
  │             0x05  unique code     │
  │◀─────────────────────────────────┤
  │  0x09  apiRanNum nonce            │
  ├─────────────────────────────────▶│
  │    *** user holds Flash button ***│
  │             0x0D  confirmed       │
  │◀─────────────────────────────────┤
  │  Cloud: POST /v1/lec/<serial>/auth
  │  0x01  PayloadA (apiAuthCode)     │
  ├─────────────────────────────────▶│
  │             0x02  PayloadB        │
  │◀─────────────────────────────────┤
  │  Cloud: POST /v1/lec/<serial>/verify
  │  0x03  Payload3 (pairingToken)    │
  ├─────────────────────────────────▶│
  │             0x26  Established     │
  │◀─────────────────────────────────┤
  │  Cloud: POST /v1/lec/<serial>/provision
  │  Cloud: POST /v1/lec/<serial>/ltk  → save LTK locally
```

The fresh pairing flow is a **one-time, out-of-band operation**.  It is not automated
by the integration.  Users complete it once (using the standalone pairing script that
can be derived from S-Termi's `dyson_fresh_pair.py`), then supply the resulting LTK to
the integration during config flow.

*Future*: the integration config flow may offer a guided fresh-pairing mode via the HA
UI once more BLE-only devices are supported.

---

## LTK Re-auth (Silent Reconnect — No Button, No Cloud)

```
Integration                        Lamp
  │  GATT connect                    │
  ├─────────────────────────────────▶│
  │  0x0A  request product info      │
  ├─────────────────────────────────▶│
  │             0x0B  product info    │
  │◀─────────────────────────────────┤
  │  0x06  PayloadA (82 bytes)        │
  │    = account_guid(16) ∥ 0x00 0x00 ∥ g20c_encrypt(enc_key, random_nonce_16)
  ├─────────────────────────────────▶│
  │             0x07  PayloadB        │
  │◀─────────────────────────────────┤
  │  0x08  PayloadC (66 bytes)        │
  │    = 0x00 0x00 ∥ g20c_encrypt(enc_key, challenge_from_PayloadB)
  ├─────────────────────────────────▶│
  │             0x26  Established     │
  │◀─────────────────────────────────┤
```

This is the **primary runtime reconnect flow**.  After every BLE disconnect, the
integration automatically reattempts using the stored LTK.

---

## Cryptography

> **Note on terminology**: the PROTOCOL.md included with S-Termi's archive
> uses "AES-GCM" in its summary section.  The actual implementation in
> `dyson_fresh_pair.py` uses **AES-128-CBC + HMAC-SHA256 (Encrypt-then-MAC)**.
> The implementation here follows the code, not the summary.

### Key derivation (HKDF-SHA256, empty salt)

```python
import hashlib, hmac

USER_AUTH_AES_INFO = b"USER_AUTH_AES\x00\x00\x00"

def hkdf_derive_aes_key(ltk: bytes) -> bytes:
    """Derive 16-byte AES key from LTK.  Mirror of g20/b.d in the Android app."""
    prk = hmac.new(b"", ltk, hashlib.sha256).digest()           # extract
    block1 = hmac.new(prk, USER_AUTH_AES_INFO + b"\x01", hashlib.sha256).digest()  # expand
    return block1[:16]
```

### Encrypt-then-MAC (g20c)

```python
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

def g20c_encrypt(enc_key: bytes, plaintext: bytes) -> bytes:
    """Produce IV(16) + AES-CBC(plaintext)(16) + HMAC-SHA256(key, ct)(32) = 64 bytes."""
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(enc_key), modes.CBC(iv), backend=default_backend())
    ct = cipher.encryptor().update(plaintext) + cipher.encryptor().finalize()
    mac = hmac.new(enc_key, ct, hashlib.sha256).digest()
    return iv + ct + mac
```

### PayloadA construction (type 0x06)

```python
from uuid import UUID

def build_reauth_payload_a(account_uuid: str, enc_key: bytes, nonce: bytes) -> bytes:
    """account_guid(16) + 0x00 0x00 + g20c_encrypt(nonce) = 82 bytes."""
    return UUID(account_uuid).bytes + b"\x00\x00" + g20c_encrypt(enc_key, nonce)
```

### PayloadC construction (type 0x08)

```python
def build_reauth_payload_c(enc_key: bytes, challenge: bytes) -> bytes:
    """0x00 0x00 + g20c_encrypt(challenge) = 66 bytes."""
    return b"\x00\x00" + g20c_encrypt(enc_key, challenge)
```

---

## Cloud Endpoints (Fresh Pairing Only)

Base URLs are tried in order: `appapi.cp.dyson.com`, `api.dyson.com`, `linkapp-api.dyson.com`.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/lec/<serial>/auth` | POST | Start auth, returns `apiAuthCode` |
| `/v1/lec/<serial>/verify` | POST | Verify challenge, returns `pairingToken` |
| `/v1/lec/<serial>/reverify` | POST | Alternative verify path |
| `/v1/lec/<serial>/provision` | POST | Request LTK provisioning |
| `/v1/lec/<serial>/ltk` | POST | Fetch LTK bytes |

The `/ltk` endpoint accepts either:
- The session `apiAuthCode` obtained during pairing, **or**
- The hardcoded fallback value `"80541406"` (observed from multiple accounts)

All requests require the `Authorization: Bearer <token>` header from the user's
Dyson cloud account.  HTTPS is mandatory; SSL certificates must be validated.

---

## Value Scaling

### Brightness

The lamp stores brightness as 0–100 (percent). Home Assistant uses 0–255.

```python
def ha_to_raw_brightness(ha_brightness: int) -> int:
    """Map HA brightness (0-255) to lamp percent (1-100).

    Minimum raw value is 1 to prevent confusion with power-off.
    """
    if ha_brightness <= 0:
        return 1
    return max(1, min(100, round(ha_brightness * 100 / 255)))

def raw_to_ha_brightness(raw: int) -> int:
    """Map lamp percent (0-100) to HA brightness (0-255)."""
    return max(0, min(255, round(raw * 255 / 100)))
```

### Color Temperature

The lamp stores color temperature as a **16-bit little-endian integer in Kelvin**,
range **2700 K – 6500 K**.  Home Assistant uses mired (reciprocal megakelvin).

```python
BLE_MIN_KELVIN = 2700   # warmest = 370 mireds
BLE_MAX_KELVIN = 6500   # coolest = ~154 mireds

def kelvin_to_mired(kelvin: int) -> int:
    return round(1_000_000 / kelvin)

def mired_to_kelvin(mired: int) -> int:
    kelvin = round(1_000_000 / mired)
    return max(BLE_MIN_KELVIN, min(BLE_MAX_KELVIN, kelvin))
```

HA entity attributes: `min_color_temp_kelvin = 2700`, `max_color_temp_kelvin = 6500`
(equivalently `min_mireds ≈ 154`, `max_mireds = 370`).

---

## Write Operations

All characteristic writes use `response=False` (write-without-response):

```python
# Power
await client.write_gatt_char(BLE_POWER_UUID, b"\x01" if on else b"\x00", response=False)

# Brightness (0-100 raw)
await client.write_gatt_char(BLE_BRIGHTNESS_UUID, bytes([raw_percent]), response=False)

# Color temperature (Kelvin, uint16 little-endian)
await client.write_gatt_char(
    BLE_COLOR_TEMP_UUID, kelvin.to_bytes(2, byteorder="little"), response=False
)
```

---

## Motion Detection

Motion events arrive as GATT notifications on characteristic **11008**
(`2dd11008-1c37-452d-8979-d1b4a787d0a4`).

A notification payload of all-zero bytes means **no motion** (idle).
Any non-zero byte in the payload indicates **motion detected**.

The integration fires `EVENT_BLE_STATE_CHANGE` with `motion_detected: True/False`
upon each notification.  The `DysonMotionBinarySensor` entity updates its state
in response.

---

## Connection Lifecycle

```
  ┌────────────────────────────────────────────────────┐
  │              DysonBLEDataUpdateCoordinator          │
  │                                                    │
  │  asyncio.Task "dyson-ble-<serial>"                 │
  │                                                    │
  │   IDLE ──scan──▶ CONNECTING ──reauth──▶ CONNECTED  │
  │     ▲                                      │       │
  │     └──────── reconnect (backoff) ─────────┘       │
  │                                                    │
  │   On connected:                                    │
  │     • subscribe char 11008 (motion)               │
  │     • subscribe chars 11006/11007/11009 (debug)   │
  │     • read initial power/brightness/color_temp    │
  │     • start keepalive loop (read every 20s)       │
  │                                                    │
  │   On disconnect:                                   │
  │     • mark entity unavailable                     │
  │     • schedule reconnect with exponential backoff │
  └────────────────────────────────────────────────────┘
```

### Reconnect strategy

| Attempt | Delay before retry |
|---------|-------------------|
| 1 | 5 s |
| 2 | 15 s |
| 3 | 30 s |
| 4+ | 60 s |

---

## Home Assistant Integration Architecture

```
DysonBLEDevice (ble_device.py)
  │  GATT notify / read
  │  hass.bus.async_fire(EVENT_BLE_STATE_CHANGE, state_dict)
  ▼
DysonBLEDataUpdateCoordinator (coordinator.py)
  │  hass.bus.async_listen → updates self.data
  │  DataUpdateCoordinator.async_set_updated_data()
  ▼
DysonBLEEntity (entity.py)          ← CoordinatorEntity base
  │
  ├── DysonLightEntity (light.py)   ← LightEntity
  └── DysonMotionBinarySensor       ← BinarySensorEntity
          (binary_sensor.py)
```

Key design principle: **no MQTT**.  All state flows through the HA event bus.
Entity updates go through the coordinator's `async_set_updated_data()` which
triggers `CoordinatorEntity._handle_coordinator_update()` on all subscribers.

---

## Extensibility for Future BLE Devices

To add a new BLE-only Dyson device (e.g., a future Dyson light with different
brightness range or additional temperature presets):

1. Add new GATT UUID constants to `const.py` using the same naming convention
2. Subclass `DysonBLEDevice` in `ble_device.py` if the auth flow differs;
   otherwise, set different UUID parameters at construction time
3. Extend `DysonLightEntity` or create a sibling entity class in `light.py`
4. Add the new product's model identifiers to `AVAILABLE_DEVICE_CATEGORIES`
5. Add a test fixture and test file following the `test_light.py` pattern

The BLE coordinator and entity base classes require no changes for new light
products, as they are generic over the device type.

---

## Known Limitations and Open Questions

- **Fresh pairing not in config flow**: Fresh pairing requires a physical button press
  and is a one-time operation.  The current design requires users to run the pairing
  script separately and then enter the resulting LTK during config flow.  A future
  iteration may add a guided pairing step within the HA UI.
- **Char 11006/11007/11009**: These characteristics are observed but not fully decoded.
  Their purpose is logged as diagnostic attributes but not surfaced as HA entities.
- **RSSI gating**: The original bridge implements an RSSI threshold gate before
  fresh pairing.  The HA integration omits this (HA's bluetooth framework handles
  device proximity natively).
- **BlueZ bonding**: The original bridge calls `client.pair()` post-auth for BlueZ
  bonding.  HA's bluetooth framework manages bonding; this step is not replicated.
- **Multi-lamp**: Only one lamp per config entry is supported.  Each lamp requires
  a separate config flow invocation.
