# hass_dyson_local_fix

Purpose: local patch project for the Dyson TP04 local MQTT reconnect storm seen from Home Assistant `10.88.0.21` to Dyson `10.88.14.52:1883`.

## Evidence summary

- Dyson local MQTT broker accepts valid HA credentials and returns CONNACK 0.
- HA packet captures showed repeated concurrent SYNs to `10.88.14.52:1883`; some succeed, many stay in `SYN_SENT`.
- pfSense did not show an obvious block; LAN rule permits HA to all LAN subnets.
- `hass_dyson` code already contains workarounds for Dyson stale-session/RST behaviour, but still allows overlapping connect attempts and paho background reconnect behaviour.

## Patch intent

`custom_components/hass_dyson/device.py` now:

1. Adds a per-device `asyncio.Lock` around `connect()` and suppresses duplicate concurrent connect attempts.
2. Returns immediately if already connected instead of tearing down/rebuilding a working MQTT session.
3. Removes the separate raw TCP preflight probe before MQTT CONNECT to avoid doubling TCP session churn against the Dyson broker.
4. Adds exponential local retry backoff after local MQTT failures.
5. Creates paho clients with `reconnect_on_failure=False` so reconnects are controlled by integration logic, not paho loop threads.
6. Makes `disconnect()` clean any existing MQTT client, even if `_connected` is false, and calls `disconnect()` before `loop_stop()`.

## Verification run

From project root:

```bash
python3 -m py_compile custom_components/hass_dyson/device.py
git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check
```

Both passed on 2026-06-24.

## Deployment note

Do not deploy directly without approval. Live deployment requires copying the patched `device.py` into Home Assistant custom components and restarting/reloading HA Core. Rollback is to restore the previous `device.py` or reinstall the upstream HACS integration.
