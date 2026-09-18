# Dyson BLE Floor-care Vacuums

Documentation for Dyson BLE-only floor-cleaning vacuums (LEC floorcare,
`connection_category: lecOnly` + device category `flrc`), e.g. the **V16
Piston Animal** (product type 692B / model SV53-AF).

## Overview

These vacuums have **no Wi-Fi and no MQTT** — they talk exclusively over
Bluetooth Low Energy using Dyson's binary **attribute protocol**.  The
integration authenticates with the same silent LTK re-auth handshake as the
BLE light and then:

- reads the full attribute registry on connect (labeled snapshot),
- subscribes to push notifications (0x97) for live attribute changes,
- reports whether a clean is in progress (no derived durations — see below),
- supports writing the five machine settings the official app exposes over
  BLE: brush-bar speed, dust illumination, task detection, battery care and
  the machine's UI language.

No Dyson cloud account or MQTT broker is required for normal operation;
a cloud-configured account is used **once** (automatically, when present) to
fetch the pairing LTK.

### Supported entities

| Platform | Entities |
|---|---|
| sensor | Battery level (%), power mode (eco/med/auto/boost), brush-bar type, battery temperature |
| binary_sensor | Actively charging, charger present (dock), blockage, filter missing, filter needs washing, system error, charge required, cleaning session active, non-genuine battery, dust-illumination auto available (diagnostic) |
| select | **Brush Bar Speed** (low/high/auto), **Dust Illumination Mode** (off/on/auto), **Machine UI Language** |
| switch | **Task Detection**, **Battery Care** |
| update | **Firmware** — reports installed vs pending; installing over BLE is not supported |

Writable attributes are exposed only as the writable entity — there is no
read-only sensor mirroring a select or switch.

Device info carries firmware version and hardware module/variant (from the
machine's product-info reply) plus the serial.  Because product info only
arrives after authentication — long after the entities and their device
registry entry are created — the coordinator pushes it into the device
registry on each successful connect.

The firmware `update` entity reports the installed build from product info and
the *staged* build from the `pending_fw` field of connection-established
(`0x26`).  It declares no `UpdateEntityFeature.INSTALL`, so Home Assistant
never offers to install — firmware updates go through the MyDyson app.

**It cannot tell you whether the firmware is up to date, and does not
pretend to.**  A `lecOnly` vacuum has no Wi-Fi and no MQTT, so it has no way
to ask Dyson whether a newer build exists.  The app downloads firmware from
the cloud and transfers it to the machine over BLE (hence the app's
`BleOtaUpdateController`), which means `pending_fw` says "an image is staged
on this machine", not "this is the latest release".  An all-zero `pending_fw`
means nothing is staged — which is not the same as being current.

`latest_version` is therefore `None` unless something is actually staged, and
Home Assistant renders the entity as *unknown*.  Getting a real "is it
current" answer needs the Dyson cloud, which will be a follow-up.

### Version formats: BLE and cloud agree

The cloud version string is built from the same product-info fields the BLE
link reports, as
`{project}{module}.{variant}.{major:02d}.{minor:03d}.{build:04d}`:

| Source | Value |
| --- | --- |
| BLE product info | fw `2.13.2`, module `0x5053`, variant `0x3530`, project `SVC0` |
| Reconstructed | `SVC0PS.50.02.013.0002` |
| Cloud `firmware.version` | `SVC0PS.50.02.013.0002` |

This confirms the module and variant fields are **printable ASCII**, not opaque
bytes — `0x5053` is `"PS"` and `0x3530` is `"50"` — so they are decoded as text
(with a hex fallback).  `dyson_firmware_version` exposes the reconstructed
string, which is the form to compare against a cloud latest version;
`firmware_version` stays the short `2.13.2` used for the device registry.

### Cleaning sessions — why there is no duration or history

The machine exposes a `sessionActiveState` attribute (`0x0740`), surfaced as
the **Cleaning Session Active** binary sensor.  That is all that is exposed,
deliberately.

Earlier revisions also shipped "cleaning duration", "last cleaning duration"
and "last cleaning end" sensors, computed by timing the attribute's
transitions.  They were removed because the numbers cannot be trusted:

- they require Home Assistant to observe **both** edges of a clean, and a
  handheld vacuum may be out of BLE range of the HA host during the clean;
- any BLE drop mid-clean discards the start time, so the duration is lost
  even if the end transition is later seen;
- nothing was persisted, so an HA restart or entry reload wiped the history;
- "duration" really meant *time since HA noticed the clean started*, which is
  not the same thing and is silently wrong rather than obviously missing.

Historic cleans are stored on the machine as an encrypted rolling journal
(pulled via message type 0x16/0x17 by the official app and forwarded to the
Dyson cloud).  Its payload is only decrypted Dyson-side, so the long history
in the MyDyson app is cloud-processed and cannot be reproduced locally.  This
integration does **not** upload anything anywhere.

---

## Requirements

### Home Assistant

- The **Bluetooth** integration must be enabled
  (`Settings → Devices & Services → Add Integration → Bluetooth`)

### Bluetooth adapter or proxy

The vacuum must be reachable by at least one of:

| Option | Notes |
|---|---|
| **Local Bluetooth adapter** | USB dongle or built-in adapter on the HA host |
| **ESPHome Bluetooth proxy** | Recommended when the vacuum lives in another room |

A received signal strength of **−70 dBm or better** is recommended.  The
vacuum advertises only while powered on (it sleeps when carried around
disconnected from its charger less than the dock idles), so give the adapter
a few seconds to see it if you just picked it up.

#### ESPHome Bluetooth proxy — active mode required

The proxy **must** run with `active: true` in the `bluetooth_proxy` component;
passive proxies cannot initiate the GATT connection that authentication
requires.

```yaml
substitutions:
  name: ble-proxy-vacuum

esphome:
  name: ${name}

esp32:
  board: esp32dev
  framework:
    type: esp-idf

bluetooth_proxy:
  active: true

# (plus your usual wifi/api/ota/logger bits)
```

### Bonding — why a fresh proxy sees nothing

The vacuum serves its own characteristics **only over an encrypted link**.
Read one without a bond and it answers ATT error `0x05`, *insufficient
authentication*; the standard GAP service stays readable, so service
discovery and the GATT table look completely healthy.

The integration therefore pairs on every connection before it touches a
Dyson characteristic.  Pairing is a no-op once a bond exists, and an ESPHome
proxy keeps its bond in NVS, so the cost is one-time per proxy.

This is worth understanding because the failure is **silent**.  Every Dyson
characteristic is *write-without-response* plus *notify* — the BLE spec never
acknowledges a Write Command — so an unbonded machine drops every frame with
no way to say so.  What you see is a connection that establishes normally,
`start_notify` that succeeds, and then the product-info request and the
PayloadB handshake both timing out with nothing in either direction.

If your logs show that pattern, check bonding first.  With debug logging on
(`custom_components.hass_dyson: debug`) the link probe reports it directly:

```
Link probe: GAP device name (00002a00-…) = 506973746f6e20416e696d616c
Link probe: Dyson auth-service status (2dd10013-…) failed:
  Bluetooth GATT Error handle=17 error=5 description=Insufficient authentication
```

GAP readable but the Dyson characteristic rejected is exactly this condition.

> A local adapter that has bonded once keeps the keys, which makes this easy
> to miss during development: direct connections keep working with no
> explicit pairing step long after the bond was established.

---

## Setup

### Automatic (cloud-assisted, recommended)

1. Add your **Dyson cloud account** first — the integration needs it once to
   fetch the pairing LTK for your vacuum.
2. When the V16 is discovered, the config flow routes it to the **BLE
   floor-care** configure step (not the BLE Light step — this was fixed in
   this release; see issue #434).
3. Confirm serial + BLE MAC (auto-resolved from the Bluetooth cache when
   possible), wait for the automatic LTK fetch, done.  No button press
   required.

### Manual

Choose *Dyson BLE Vacuum (e.g. V16 floor-care vacuums)* from the setup
method list and provide serial, MAC and LTK yourself.  The LTK can also be
retrieved with `libdyson-rest` (`GET /v1/lec/<serial>/ltk`).

---

## Write operations (selects/switches)

The machine answers a `0x93` write with a `0x94` write-status response and a
`0x97` attribute push; entity state is only applied after that confirmation,
never assumed optimistically.  If the machine rejects a write, the status byte
is logged as a warning and the previous value stays.

The writable set is not guesswork: it is exactly the `k50.i`
(WriteAttributeRequest) subclasses in the official app's
`mod-cat6-connected-floorcare` module.  There are five:

| App class | Attribute | Entity |
| --- | --- | --- |
| `mq/a` BrushBarSpeed | `0x0B40` | **Brush Bar Speed** (select — low/high/auto) |
| `mq/b` illuminationMode | `0x0A40` | **Dust Illumination Mode** (select — off/on/auto) |
| `mq/c` taskDetectMode | `0x0741` | **Task Detection** (switch) |
| `lq/a` batteryCareMode | `0x0841` | **Battery Care** (switch, config category) |
| `lq/b` ProductUILanguage$Ble | `0x0241` | **Machine UI Language** (select, config category) |

### Verified on hardware: status 0 means accepted, not applied

The `0x94` response is `attrId(2) | status(1)`; status `0` is success.  Two
writes on a V16 (firmware 2.13.2):

| Write | 0x94 response | Status | Attribute afterwards |
| --- | --- | --- | --- |
| task detection `0x0741` → 1 | `074100` | 0 | changed to `1` |
| dust illumination `0x0A40` → 0 | `0a4000` | 0 | **stayed** `1` |
| brush bar speed `0x0B40` → low | `0b4000` | 0 | **stayed** `auto` |
| UI language `0x0241` → English | `024100` | 0 | changed to `English` |
| battery care `0x0841` → 1 | `084100` | 0 | changed to `1` |

Three things this establishes:

1. **Status 0 means accepted, not applied.**  Dust illumination and brush bar
   speed both returned status 0 and both stayed put, because no cleaner head
   was attached — the LDI laser and the powered brush bar are *in* the head,
   so there was no hardware for either setting to act on, and no `0x97` push
   followed.  `write_attribute()` returns True for "the machine accepted the
   command"; the attribute push remains the only authority on what the value
   actually became.
2. **Status 1 is a rejection.**  The machine returns it when it refuses the
   request outright — writing a read-only attribute, for instance.  The entity
   keeps its previous value and the rejection is logged as a warning.
3. **An explicit status is authoritative over the current value.**  A rejected
   write must not be reported as success just because the attribute already
   holds the requested value, so the status is checked before any value
   comparison.

Writes are logged at debug level with the raw status byte; rejections are
warnings, and an accepted-but-unapplied write is logged at debug.

Two notes on things that look like duplicates but are not:

- Battery care has **two** attributes.  `0x0841` (app enum `vq.a`, MQTT key
  `bcms`) is the setting and the one `lq/a` writes; `0x1340` (`vq.f`, `bcmp`)
  is read-only and feeds the app's battery-management tile.  Writing `0x0841`
  produces a push on both, about 100 ms apart — `0x1340` only ever mirrors the
  setting, so it is not read, subscribed or exposed.
- Power mode (`0x0040`) has no write request in the app and remains a sensor.

Conversely, no writable attribute also gets a read-only mirror — brush-bar
speed, dust illumination and UI language are selects only.

> An earlier revision of this document claimed only three attributes were
> writable.  That came from searching the app for Kotlin suspend-function
> setters, which misses the RxJava-style controllers used for battery care and
> language.  Enumerating `k50.i` subclasses is the reliable query.

---

## Reliability notes

- The vacuum's BLE stack reboots if flooded with back-to-back writes —
  symptoms are a link drop plus several seconds of ignored button presses.
  All reads/subscribes/writes are therefore paced and ack-synchronised (the
  same discipline the official app uses).  If the device does reboot, the
  integration reconnects automatically within a minute (backoff 5/15/30/60 s).
- On unload or HA stop the integration unsubscribes pushes and sends an
  AppActiveStatus(INACTIVE) message — skipping either leaves the machine in a
  "foreground app attached" state in which it ignores its own buttons for a
  while.
- Holding the BLE link is intentional and matches the app's behavior while it
  is in the foreground; Home Assistant is safe to keep connected.
- The machine temporarily ignores the **MyDyson app** (and this integration)
  while a **different** BLE client is connected — one client at a time.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Nothing connects | Proxy passive, or vacuum asleep/out of range | `active: true`, move closer, power the device on |
| Connects, then product info **and** PayloadB both time out | No bond — the machine drops every write unencrypted, silently | See [Bonding](#bonding--why-a-fresh-proxy-sees-nothing); confirm with the link probe |
| Auth immediately fails | Wrong LTK / stale pairing | Refetch LTK from the cloud account |
| Entities unknown after connect | Attribute sweep didn't finish (out-of-range bursts) | Reload the integration; check the debug log for unanswered reads |
| Power button ignored after setup | Old version without INACTIVE teardown | Update; the teardown runs on every clean unload |
| Vacuum reboots during setup | Write burst | Update; pacing + ack-synced subscribes are in place |

---

## Attribute 0x0243 is a bitmask, not a value

`0x0243` looks like a small integer on the wire (0x00 / 0x07 observed on a
V16) but it is a 32-bit little-endian **capability bitmask**.  The MyDyson app
(`iq/b.java`) widens the payload to four bytes, reads it little-endian, and
mask-tests it against `iq.c`:

| Flag | Value |
| --- | --- |
| `AUTO` | `7` (`0b111`) |
| `NOT_AUTO` | `-1` (fallback) |

The match is `(flag & value) == flag`, so a partial mask such as `0x03` is
**not** AUTO.  The app reduces the whole attribute to that one boolean, which
it calls `dustIlluminationAutoState`, so this integration does the same and
exposes it as a diagnostic binary sensor rather than a number.

Observed behaviour confirms it is a *capability*, not the current mode:

| | `dust_illumination` | `0x0243` | `brush_bar_type` |
| --- | --- | --- | --- |
| Cleaning | `on` | `0x07` → auto available | `row_768` |
| Docked | `on` | `0x00` → not available | `none_attached` |

The mode was `on` in both samples, so the mask tracks the attached cleaner
head, not the selected mode.  The dust-illumination select therefore hides its
`auto` option while the flag is clear — except when `auto` is already the
current value.  Home Assistant's `SelectEntity.state` reports `None` for a
`current_option` that is not in `options`, so hiding it in that case would
make the entity read *unknown* rather than `auto`.
