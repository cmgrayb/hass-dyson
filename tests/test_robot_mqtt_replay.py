"""Replay a sanitized real-device MQTT capture through the device handlers.

The fixture (tests/fixtures/devices/robot/277_zone_clean_replay.jsonl) is the
inbound message stream captured 2026-07-17 from a 360 Vis Nav (product type
277, firmware RB03PR.01.08.006.5079) across a full zone clean plus two
zone renames made in the MyDyson app, sanitized (serial-embedded GUIDs
remapped to MOCKSERIAL01). One JSON payload per line, chronological.

It guards the whole message vocabulary a real robot emits — dispatch must
accept every message without falling into the unknown-type branch, harvest
map/zone state, and track the clean session. This is a Layer-0-style capture
per .github/design/testing-mqtt-fixture-architecture.md; the future
DeviceMock work can convert it into a DeviceFixture.
"""

import json
import logging
from pathlib import Path

from custom_components.hass_dyson.device import DysonDevice

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "devices"
    / "robot"
    / "277_zone_clean_replay.jsonl"
)


def _bare_device() -> DysonDevice:
    device = object.__new__(DysonDevice)
    device._state_data = {}
    device._log_serial = "TEST-SERIAL"
    device._message_callbacks = []
    # STATE-CHANGE bookkeeping touched by _process_message_data
    device._total_state_messages = 0
    device._fpwr_message_count = 0
    device._fmod_message_count = 0
    device._power_control_type = "fpwr"
    return device


def _load_messages() -> list[dict]:
    return [
        json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()
    ]


class TestVisNavCaptureReplay:
    """Replay the captured session end to end."""

    def test_capture_has_expected_shape(self):
        messages = _load_messages()
        kinds = [m.get("msg") for m in messages]
        assert kinds.count("STATE-CHANGE") == 32
        assert kinds.count("CURRENT-STATE") == 6
        assert kinds.count("PERSISTENT-MAP-MANIFEST-UPDATED") == 3

    def test_replays_without_unknown_message_types(self, caplog):
        device = _bare_device()
        with caplog.at_level(
            logging.DEBUG, logger="custom_components.hass_dyson.device"
        ):
            for payload in _load_messages():
                device._process_message_data(payload, "277/TEST-SERIAL/status")
        assert "Unknown message type" not in caplog.text

    def test_manifest_broadcasts_reach_message_callbacks(self):
        device = _bare_device()
        seen: list[str] = []
        device._message_callbacks.append(
            lambda _topic, data: seen.append(data.get("msg"))
        )
        for payload in _load_messages():
            device._process_message_data(payload, "277/TEST-SERIAL/status")
        assert seen.count("PERSISTENT-MAP-MANIFEST-UPDATED") == 3

    def test_final_state_matches_real_session(self):
        """End-of-capture facts observed live on the real robot."""
        device = _bare_device()
        for payload in _load_messages():
            device._process_message_data(payload, "277/TEST-SERIAL/status")
        assert device.robot_state == "INACTIVE_CHARGED"
        assert device.robot_session_active is False
        # Map and per-zone progress are retained after docking
        assert device.robot_current_map_id
        statuses = {z["zoneId"]: z["cleanStatus"] for z in device.robot_zone_status}
        assert statuses["3"] == "CLEAN_COMPLETE"

    def test_session_flag_follows_lifecycle(self):
        """After each message, the flag matches that message's own state.

        Keyed on the payload's state field (not the robot_state property,
        which by design only refreshes from CURRENT-STATE snapshots).
        """
        device = _bare_device()
        session_by_state: dict[str, set[bool]] = {}
        for payload in _load_messages():
            device._process_message_data(payload, "277/TEST-SERIAL/status")
            state = payload.get("newstate") or payload.get("state")
            if state:
                session_by_state.setdefault(state, set()).add(
                    device.robot_session_active
                )
        assert session_by_state["FULL_CLEAN_RUNNING"] == {True}
        assert session_by_state["FULL_CLEAN_TRAVERSING"] == {True}
        assert session_by_state["FULL_CLEAN_FINISHED"] == {False}
        assert session_by_state["INACTIVE_CHARGED"] == {False}


class TestCommunityVocabulary:
    """Message shapes seen only in community captures (matterbridge 277.jsonl,
    identical firmware) — a healthy single robot never exhibits them."""

    def test_zone_status_full_vocabulary_passes_through(self):
        vocabulary = [
            "CLEAN_NOT_REQUESTED",
            "CLEAN_PENDING",
            "CLEAN_IN_PROGRESS",
            "CLEAN_COMPLETE",
            "CANT_CLEAN",
        ]
        device = _bare_device()
        zone_status = [
            {"zoneId": str(i), "cleanStatus": status}
            for i, status in enumerate(vocabulary, start=1)
        ]
        device._handle_state_change(
            {
                "msg": "STATE-CHANGE",
                "newstate": "FULL_CLEAN_RUNNING",
                "zoneStatus": zone_status,
            }
        )
        assert device.robot_zone_status == zone_status

    def test_fault_mid_clean_sequence_from_community_capture(self):
        """FULL_CLEAN_PAUSED → FAULT_USER_RECOVERABLE → clear → resume."""
        device = _bare_device()
        for oldstate, newstate in [
            ("INACTIVE_CHARGED", "FULL_CLEAN_INITIATED"),
            ("FULL_CLEAN_INITIATED", "FULL_CLEAN_RUNNING"),
            ("FULL_CLEAN_RUNNING", "FULL_CLEAN_PAUSED"),
            ("FULL_CLEAN_PAUSED", "FAULT_USER_RECOVERABLE"),
            ("FAULT_USER_RECOVERABLE", "FAULT_USER_RECOVERABLE"),
        ]:
            device._handle_state_change(
                {"msg": "STATE-CHANGE", "oldstate": oldstate, "newstate": newstate}
            )
        assert device.robot_session_active is True

    def test_fault_cleared_to_dock_closes_session(self):
        """FAULT_USER_RECOVERABLE → INACTIVE_CHARGING (community capture)."""
        device = _bare_device()
        for oldstate, newstate in [
            ("INACTIVE_CHARGED", "FULL_CLEAN_RUNNING"),
            ("FULL_CLEAN_RUNNING", "FAULT_USER_RECOVERABLE"),
        ]:
            device._handle_state_change(
                {"msg": "STATE-CHANGE", "oldstate": oldstate, "newstate": newstate}
            )
        assert device.robot_session_active is True
        device._handle_state_change(
            {
                "msg": "STATE-CHANGE",
                "oldstate": "FAULT_USER_RECOVERABLE",
                "newstate": "INACTIVE_CHARGING",
            }
        )
        assert device.robot_session_active is False
