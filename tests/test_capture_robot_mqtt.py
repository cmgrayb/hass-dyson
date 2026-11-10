"""Tests for the guided robot MQTT capture script."""

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "capture_robot_mqtt.py"
_spec = importlib.util.spec_from_file_location("capture_robot_mqtt", SCRIPT)
capture = importlib.util.module_from_spec(_spec)
# dataclasses look the module up by name while the class is built
sys.modules[_spec.name] = capture
_spec.loader.exec_module(capture)


def test_redact_hides_secrets_and_serial():
    """Credentials and the serial never reach the log; robot state does."""
    payload = {
        "msg": "CURRENT-STATE",
        "machineState": "INACTIVE_CHARGED",
        "ssid": "home-wifi",
        "macAddress": "aa:bb",
        "ip": "192.0.2.10",
        "nested": [{"token": "abc", "name": "Room of ABC-XX-12345678"}],
    }
    out = capture.redact(payload, "ABC-XX-12345678")
    assert out["machineState"] == "INACTIVE_CHARGED"
    assert out["ssid"] == out["macAddress"] == out["ip"] == "<redacted>"
    assert out["nested"][0]["token"] == "<redacted>"
    assert out["nested"][0]["name"] == "Room of SERIAL"


def test_messages_are_labelled_with_the_current_step(tmp_path):
    """Each message carries the step it arrived during, with a per-step count."""
    log = capture.CaptureLog(tmp_path / "out.txt", "ABC-XX-12345678")
    log.set_step("03 Change the cleaning mode")
    log.message(
        "RB07/ABC-XX-12345678/command/jdm",
        json.dumps({"method": "service.set_preference"}).encode(),
    )
    log.message("RB07/ABC-XX-12345678/status/jdm", b"\x00\xff")
    assert log.step_count == 2
    log.set_step("04 Change the suction power")
    assert log.step_count == 0
    log.close()

    first, second = (
        json.loads(line) for line in (tmp_path / "out.txt").read_text().splitlines()
    )
    assert first["step"] == "03 Change the cleaning mode"
    assert first["direction"] == "command"
    assert first["topic"] == "RB07/SERIAL/command/jdm"
    assert second["direction"] == "status"
    assert second["payload"] == {"_raw_hex": "00ff"}
    assert log.total == 2


def test_every_step_has_a_title_and_instruction():
    """The walkthrough ends with the free-form step and has no blanks."""
    assert capture.STEPS[-1].title == "Anything else"
    assert all(step.title and step.instruction for step in capture.STEPS)
