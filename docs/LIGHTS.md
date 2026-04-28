# Dyson BLE Lights

Documentation for Dyson BLE-only lights (Lightcycle Morph and compatible desk/floor lamps).

## Overview

Dyson Lightcycle Morph lamps communicate **exclusively over Bluetooth Low Energy (BLE)**.
They do not have Wi-Fi or MQTT capability.  This integration connects to them directly
over BLE using the same silent re-authentication protocol used by the MyDyson app.

Supported controls:

| Entity | Description |
|---|---|
| Light | On/off, brightness (1–100 %), colour temperature (2 700–6 500 K / ≈ 154–370 mired) |
| Binary sensor (motion) | Triggers when the built-in occupancy sensor detects movement |

---

## Requirements

### Home Assistant

- The **Bluetooth** integration must be enabled
  (`Settings → Devices & Services → Add Integration → Bluetooth`)
  - For more information, see [Bluetooth](https://www.home-assistant.io/integrations/bluetooth/)

### Bluetooth adapter or proxy

The lamp must be reachable by at least one of:

| Option | Notes |
|---|---|
| **Local Bluetooth adapter** | USB dongle or built-in adapter on the HA host |
| **ESPHome Bluetooth proxy** | Recommended for lamps in a different room (see below) |

#### Minimum RSSI

A received signal strength of **−70 dBm or better** is recommended for a stable connection.
At −80 dBm and below you may see authentication timeouts, keepalive failures, and frequent
reconnects.  If you observe these symptoms, move the proxy or adapter closer to the lamp.

The integration logs the RSSI of the connectable advertisement at every connection attempt:

```
BLE device CD06-EU-XYZ1234A (AA:BB:CC:DD:EE:FF) found as CONNECTABLE via adapter/proxy
'esphome_proxy' (RSSI: -62 dBm) — connecting via bleak_retry_connector
```

Use this value to verify signal quality.

#### ESPHome Bluetooth proxy — active mode required

The proxy **must** be configured in **active mode**.  Passive proxies can hear BLE
advertisements but cannot initiate GATT connections, which the integration requires for
authentication and commands.

Minimum ESPHome configuration:

```yaml
bluetooth_proxy:
  active: true    # ← required — omitting this defaults to passive (inactive) mode in older versions of esphome
```

If active mode is missing you will see this warning in the Home Assistant logs:

```
BLE device CD06-EU-XYZ1234A (AA:BB:CC:DD:EE:FF) is visible (RSSI: -65 dBm, source:
'esphome_proxy') but NOT connectable.  If using an ESPHome Bluetooth proxy, ensure it is
configured with 'active: true' in the bluetooth_proxy component.
```

One ESPHome proxy can serve multiple lamps simultaneously, but each proxy has a limited
number of simultaneous GATT connections (typically 3).  Place proxies so each lamp has
at least one proxy with strong signal.

---

## Long Term Key (LTK)

The LTK is a 32-byte secret that proves your Home Assistant instance is authorised to connect
to the lamp without a button press.  It is obtained from the Dyson cloud during fresh pairing
and never changes unless you reset the lamp.

The integration can retrieve the LTK automatically from an existing Dyson cloud account
entry, or you can enter it manually.  See Step 4 of onboarding details for more information.

---

## Setup: Onboarding Flow

### Step 1 — Add the integration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Dyson**
3. On the setup method screen select **"Dyson BLE Light (e.g. Lightcycle Morph)"**

### Step 2 — Device discovery

The integration scans for nearby devices advertising the Dyson BLE service UUID.

**If one or more lamps are found** a dropdown is shown:

```
Select a discovered device:
  ● Lightcycle Morph (AA:BB:CC:DD:EE:FF)
  ○ Enter device MAC address manually
```

Select your lamp or choose manual entry if your lamp is not in the list (e.g. the lamp is
powered off, or your BLE proxy was not yet active at scan time).

**If no lamps are found** the discovery step is skipped and you are taken directly to
[Step 3](#step-3--device-details).

### Step 3 — Device details

Enter or confirm the following:

| Field | Required | Description |
|---|---|---|
| **Serial Number** | Yes | From the sticker on the lamp base (format `CD06-EU-XYZ1234A`) |
| **MAC Address** | Yes | BLE MAC address, pre-filled if discovered (format `AA:BB:CC:DD:EE:FF`) |
| **Device Name** | No | Friendly name shown in Home Assistant (default: `Dyson <serial>`) |
| **Bluetooth Proxy** | No | Leave blank to let HA pick the best adapter or proxy automatically |

After clicking **Submit**, the integration attempts to retrieve the LTK automatically from
any Dyson cloud account already configured in Home Assistant.

**If a cloud account is present** — setup completes immediately.  No further steps required.

**If no cloud account is found** — you are forwarded to [Step 4](#step-4--manual-ltk-entry).

### Step 4 — Manual LTK entry (fallback)

If auto-retrieval fails, enter the LTK manually:

| Field | Required | Description |
|---|---|---|
| **MAC Address** | Yes | Pre-filled from Step 3 |
| **Long Term Key (LTK)** | Yes | 64-character hex string from Dyson cloud pairing |
| **Bluetooth Proxy** | No | Optional pinned proxy host |

#### How to obtain the LTK

**Option A — via this integration (recommended)**

1. Add a Dyson cloud account entry first (see [SETUP.md](SETUP.md))
2. Delete the BLE light config entry if you already added it
3. Re-add the BLE light — the LTK is fetched automatically in Step 3

No further steps needed.

**Option B — via libdyson-rest**

[libdyson-rest](https://github.com/cmgrayb/libdyson-rest) provides a helper script that
logs into the Dyson cloud and prints the LTK for a given serial number.

```bash
pip install libdyson-rest
python -m libdyson_rest.examples.dyson_api_device_scan
```

The script will prompt for your Dyson account email, send an OTP, then list all devices
with their LTK values.  Copy the 64-character hex string for your lamp.

**Option C — via opendyson**

[opendyson](https://github.com/libdyson-wg/opendyson) is a Go CLI tool that can authenticate
with the Dyson cloud and fetch device keys.

```bash
# Install (requires Go 1.21+)
go install github.com/libdyson-wg/opendyson@latest

# Fetch LTK for a specific serial number
opendyson ltk --serial CD06-EU-XYZ1234A
```

Follow the prompts to authenticate with your Dyson account.  The LTK is printed as a hex
string.

**Option D — direct API call**

If you already have a Dyson API bearer token (e.g. from a previous tool run), you can
fetch the LTK directly:

```bash
curl -s \
  -H "Authorization: Bearer <your_auth_token>" \
  -H "X-Dyson-ApiAuthCode: 80541406" \
  -H "Accept: application/json" \
  https://appapi.cp.dyson.com/v1/lec/CD06-EU-XYZ1234A/ltk
```

The response contains a `"ltk"` field — a 64-character lowercase hex string.  That is the
value to enter in the **Long Term Key** field.

> **Note**: The LTK is 32 bytes represented as 64 hex characters, e.g.
> `a1b2c3d4e5f6...` (64 characters total).  If the value you have is shorter or
> contains non-hex characters it is not a valid LTK.

---

## After Setup

Once the config entry is created, the integration will:

1. Locate the lamp via the HA Bluetooth stack (local adapter or any active ESPHome proxy)
2. Establish a GATT connection using `bleak_retry_connector` with up to 4 connection attempts
3. Authenticate silently using the LTK (no button press, no cloud call)
4. Read initial state (power, brightness, colour temperature, firmware version)
5. Subscribe to motion and runtime notifications
6. Fire a keepalive poll every 20 seconds to detect silent disconnects
7. Reconnect automatically with exponential backoff (5 s, 15 s, 30 s, 60 s) on disconnect

State updates propagate to Home Assistant via the `dyson_ble_state_change` event bus event.

---

## Entities Created

| Entity | Platform | Notes |
|---|---|---|
| `light.<name>` | `light` | Power, brightness, colour temperature (2 700–6 500 K) |
| `binary_sensor.<name>_motion` | `binary_sensor` | `on` when occupancy detected |

---

## Troubleshooting

### Lamp not found during discovery

**Symptom**: The discovery dropdown is empty or the lamp never appears.

**Checklist**:
- Lamp is powered on (touch the base to wake it)
- A Bluetooth adapter or ESPHome proxy is configured in HA with `active: true`
- The proxy or adapter is within range (target RSSI −70 dBm or better)
- HA Bluetooth integration is enabled (`Settings → Devices & Services → Bluetooth`)

**Workaround**: Use **"Enter device MAC address manually"** and type the MAC from the lamp
sticker.

---

### Lamp is visible but NOT connectable

**Symptom** (in logs):

```
BLE device ... is visible ... but NOT connectable.
If using an ESPHome Bluetooth proxy, ensure it is configured with 'active: true' ...
```

**Fix**: Add `active: true` to your ESPHome `bluetooth_proxy:` component and reflash.

---

### Authentication / HMAC verification failure

**Symptom** (in logs):

```
PayloadB from CD06-EU-XYZ1234A failed HMAC verification —
LTK may be incorrect or corrupted
```

**Causes**:
- The stored LTK is wrong or was entered with a typo
- The lamp was reset to factory defaults (LTK is regenerated on factory reset)
- The lamp was re-paired with a different account since the LTK was fetched

**Fix**:
1. Delete the BLE light config entry
2. Re-add it — if a cloud account entry is present the correct LTK is fetched automatically
3. If no cloud account: obtain the correct LTK via the Dyson cloud (see
   [Manual LTK entry](#step-4--manual-ltk-entry-fallback))

---

### Connection drops frequently / keepalive failures

**Symptom**: Light entity becomes unavailable and reconnects repeatedly.

**Checklist**:
- Check RSSI in the log at connection time — below −75 dBm is unreliable
- Ensure only **one** ESPHome proxy is within strong-signal range of the lamp
  (multiple strong-signal proxies can cause simultaneous connection conflicts)
- Verify the proxy has a stable Wi-Fi connection to the HA host

---

### Timeout waiting for BLE message

**Symptom** (in logs):

```
Timed out waiting for BLE message type 0x07 from CD06-EU-XYZ1234A
```

**Causes**:
- Lamp took too long to respond (possibly busy or out of range)
- GATT connection dropped mid-handshake

The integration will disconnect and retry with backoff automatically.  If it persists, improve
signal quality.

---

### Commands accepted but state does not update in HA

**Symptom**: Turning the light on/off from HA appears to work but the entity stays stuck.

**Cause**: The notification subscription for power/brightness may have been dropped on
reconnect.

**Fix**: Reload the integration entry (`Settings → Devices & Services → Dyson → … → Reload`).

---

### Motion sensor always off

**Symptom**: The motion binary sensor never triggers even when movement is detected.

**Checklist**:
- Verify motion detection is enabled on the lamp (hold the touch ring for ~3 s to toggle)
- Confirm the lamp is fully authenticated (`authenticated: true` in the debug log)
- The motion characteristic requires an active GATT subscription — reload if just reconnected

---

### BLE proxy has a connection limit

ESPHome Bluetooth proxies typically support a maximum of **3 simultaneous active GATT
connections**.  If you have more than 3 BLE lights or other active devices near one proxy,
some may fail to connect.  This can be verified in Settings > System > Bluetooth.
Deploy additional proxies as needed.

---

## Notes

- The lamp's BLE MAC address is printed on the base sticker below the serial number
- The LTK never expires under normal use; it only changes on factory reset
- Setting a pinned proxy (`CONF_BLE_PROXY`) is reserved for future direct-proxy support;
  currently HA selects the best connectable adapter or proxy automatically
- Colour temperature is clamped to the lamp's supported range (2 700–6 500 K)
- Brightness below 1 % is sent as 1 % to the lamp (the lamp does not support true off via
  the brightness characteristic — use the power state instead)
