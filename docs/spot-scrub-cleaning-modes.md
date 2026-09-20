# Spot+Scrub cleaning modes

RB05 devices get a **Cleaning mode (all rooms)** select with four options:

| Option | Room preference index 3 |
| --- | --- |
| Vacuum only | 0 |
| Vacuum and mop (simultaneous) | 1 |
| Mop only | 2 |
| Vacuum then mop (sequential) | 3 |

Select a mode while the robot is docked or inactive. This updates the preferences
of all rooms on the current map; it does not start the robot. Other supported
room settings are preserved. If rooms have different modes, the select has no
common current option; its `room_modes` and `mixed_modes` attributes describe the
individual preferences. Preferences are refreshed every 60 seconds and read back
after writes. Errors are surfaced rather than showing an unconfirmed choice.

This control is only added for the RB05 MQTT prefix. Vis Nav, older robots, and
air treatment devices are unaffected. No additional credentials or MQTT broker
are needed: it uses the integration's existing device connection.

## Protocol evidence

The mode mapping comes from MyDyson runs observed on one Spot+Scrub on
2026-09-20. The contributing user selected the modes in the app, and the MQTT
preferences and robot activity were compared. Identifiers and labels below are
synthetic; private logs, maps, credentials and serial numbers are not included.

- A controlled same-room comparison of vacuum-only and vacuum-then-mop writes
  differed only at index 3 (`0` versus `3`). The sequential run reported
  `VACUUMING`, then a mop wash, then `MOPPING`.
- The mop-only run wrote `2` and reported `MOPPING`. Index 5 also changed between
  that run and the earlier captures; its semantics are not claimed here and the
  implementation preserves it.
- The simultaneous run's acknowledged preference readbacks contained `1` and the
  robot reported `VACUUMING_AND_MOPPING`. Capture began after the outgoing write,
  so evidence for this value is readback plus activity, not the write itself.

The standard `START` message used `cleaningMode: zoneConfigured`. The accompanying
`service.set_room_clean` used `clean_type: 0` for all four modes. That field is
therefore not the vacuum/mop selector. This change does not alter start commands;
the captured behaviour was room cleaning, not a verified whole-home start.

Requests use `RB05/<serial>/command/jdm`, with replies on
`RB05/<serial>/status/jdm`. Replies are matched by topic, method and `msgId` and
must acknowledge success. The protocol layer uses existing message listeners;
it does not replace the integration's MQTT callback.

```json
{
  "msgId": "12345",
  "version": "1.0.1",
  "method": "service.set_preference",
  "params": {
    "map_id": 123,
    "prefer_type": 1,
    "room_preference": [[1, "Room A", 0, 1, 0, 1, 0, 0, 1, 0, 1]],
    "uv_switch": [[1, 0]]
  }
}
```

`service.get_map_list` identifies the current map. `service.get_preference`
returns room rows with twelve fields. Observed app writes use eleven fields,
normalize response field 2 to zero, and unwrap JSON-encoded room names. The final
response field was zero in these captures. Unknown row lengths, unsupported
flags or missing UV preferences are rejected, rather than guessed. Other
firmware layouts require further captures.

## Validation boundary

The mode values were observed on real hardware. The new native integration code
is covered by mocked protocol and entity tests; it has not been installed and
tested end-to-end on hardware. Maintainer/hardware review is requested before
merging. In particular, retain the distinction between simultaneous and
sequential modes and review the response-to-write field conversion.
