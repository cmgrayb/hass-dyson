#!/usr/bin/env python3
"""Guided MQTT capture for Dyson robot vacuums.

Walks you through the controls in the MyDyson app one at a time and records
what the robot sends over MQTT while you use each one. Every message in the
log is labelled with the step that produced it, so the integration's
developers can see which app action maps to which command and status.

The script only listens. It never sends anything to the robot.

Requirements: Python 3.10+, plus
    pip install "libdyson-rest==0.17.2" "paho-mqtt>=2.2"

Run:
    python3 capture_robot_mqtt.py

See docs/CAPTURE_ROBOT_MQTT.md for the full walkthrough.
"""

from __future__ import annotations

import asyncio
import getpass
import json
import re
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import paho.mqtt.client as mqtt
    from libdyson_rest import AsyncDysonClient
except ImportError:
    print(
        "\nThis script needs two Python packages. Install them with:\n\n"
        '    python3 -m pip install "libdyson-rest==0.17.2" "paho-mqtt>=2.2"\n\n'
        "then run the script again.\n"
    )
    sys.exit(1)

SCRIPT_VERSION = "1.0"
SETTLE_SECONDS = 10
CONNECT_TIMEOUT = 30
FIRST_MESSAGE_TIMEOUT = 90

# Field names whose values are blanked before anything is written to disk.
SENSITIVE_KEYS = re.compile(
    r"password|token|secret|signature|credential|ssid|mac_?address|ip_?address"
    r"|^(mac|ip|pass|pwd)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Step:
    """One thing to do in the MyDyson app."""

    title: str
    instruction: str
    needs_docked: bool = False


STEPS: list[Step] = [
    Step(
        "Quiet baseline",
        "Leave the robot on its dock and don't touch the app. "
        "This records what it sends on its own.",
    ),
    Step(
        "Open the robot in the app",
        "Open the MyDyson app and tap your robot so its home screen loads. "
        "Wait until the map and battery level appear.",
    ),
    Step(
        "Change the cleaning mode",
        "Change the whole-home cleaning mode once (for example from "
        "'Vacuum and mop' to 'Vacuum only'). Don't start a clean yet.",
        needs_docked=True,
    ),
    Step(
        "Change the suction power",
        "Change the whole-home suction or power level once "
        "(for example Auto, Quick, Quiet or Boost).",
        needs_docked=True,
    ),
    Step(
        "Change the mop water level",
        "If the app has a water or hydration setting, change it once.",
        needs_docked=True,
    ),
    Step(
        "Change one room's cleaning mode",
        "Open one room's settings and change only its cleaning mode.",
        needs_docked=True,
    ),
    Step(
        "Change one room's suction power",
        "In the same room's settings, change only its suction or power level.",
        needs_docked=True,
    ),
    Step(
        "Change one room's mopping settings",
        "In the same room's settings, change its water level or number of "
        "mop passes or scrubs.",
        needs_docked=True,
    ),
    Step(
        "Put the room settings back",
        "Set that room back the way it was before.",
        needs_docked=True,
    ),
    Step(
        "Start a whole-home clean",
        "Start a normal clean of the whole home and let it run for about a minute.",
    ),
    Step(
        "Pause the clean",
        "Pause the clean in the app.",
    ),
    Step(
        "Resume the clean",
        "Resume the clean in the app and let it run for about 30 seconds.",
    ),
    Step(
        "Send it back to the dock",
        "Tap the button that sends the robot home, and wait until it has docked.",
    ),
    Step(
        "Clean one room",
        "Start a clean of a single room, let it run for about a minute, "
        "then send it home again.",
    ),
    Step(
        "Dock maintenance",
        "If the app has dock actions (empty the bin, wash or dry the mop "
        "pads, refill water), run each one you can.",
        needs_docked=True,
    ),
    Step(
        "Edit the map",
        "Rename one room, then change the name back.",
        needs_docked=True,
    ),
    Step(
        "Schedules",
        "Create a schedule, then delete it again.",
    ),
    Step(
        "Anything else",
        "Try any other button or setting your RB07 has that we haven't "
        "covered (camera, carpet or obstacle settings, child lock, "
        "do-not-disturb and so on). You'll get the chance to name each one.",
    ),
]


def utc_now() -> str:
    """Return an ISO timestamp with millisecond precision."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def redact(value: Any, serial: str) -> Any:
    """Blank sensitive fields and replace the serial number everywhere."""
    if isinstance(value, dict):
        return {
            key: "<redacted>"
            if SENSITIVE_KEYS.search(str(key))
            else redact(item, serial)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, serial) for item in value]
    if isinstance(value, str) and serial:
        return value.replace(serial, "SERIAL")
    return value


class CaptureLog:
    """Thread-safe writer that tags every MQTT message with the current step."""

    def __init__(self, path: Path, serial: str) -> None:
        self.path = path
        self.serial = serial
        self._lock = threading.Lock()
        self._file = path.open("w", encoding="utf-8")
        self._step = "connecting"
        self._step_count = 0
        self.total = 0

    def set_step(self, label: str) -> None:
        with self._lock:
            self._step = label
            self._step_count = 0

    @property
    def step_count(self) -> int:
        with self._lock:
            return self._step_count

    def write(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._file.flush()

    def note(self, kind: str, **fields: Any) -> None:
        """Record a marker such as a step starting, finishing or being skipped."""
        with self._lock:
            step = self._step
        self.write({"t": utc_now(), "kind": kind, "step": step, **fields})

    def message(self, topic: str, raw: bytes) -> None:
        try:
            payload: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {"_raw_hex": raw.hex()}
        parts = topic.split("/")
        # prefix/serial/<status|command>/<channel>
        direction = parts[2] if len(parts) > 2 else ""
        with self._lock:
            step = self._step
            self._step_count += 1
            self.total += 1
        self.write(
            {
                "t": utc_now(),
                "kind": "mqtt",
                "step": step,
                "direction": direction,
                "topic": topic.replace(self.serial, "SERIAL"),
                "payload": redact(payload, self.serial),
            }
        )

    def close(self) -> None:
        with self._lock:
            self._file.close()


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        answer = input(f"{prompt}{suffix}: ").strip()
        if answer:
            return answer
        if default is not None:
            return default
        print("  Please type an answer.")


def banner(text: str) -> None:
    print("\n" + "=" * 64)
    print(text)
    print("=" * 64)


async def sign_in_and_get_robot() -> tuple[str, str, str, str, dict[str, str]]:
    """Sign in to MyDyson and return (name, serial, prefix, host, credentials)."""
    banner("1. Sign in to your MyDyson account")
    print(
        "Use the same account as the MyDyson app. Dyson will send you a\n"
        "one-time code. Your password and the code are only sent to Dyson\n"
        "and are never written to the log.\n"
    )
    account = ask("Email address (or mobile number with +country code, China only)")
    is_mobile = account.startswith("+")
    country = ask(
        "Two-letter country code of your account", "CN" if is_mobile else "US"
    )
    country = country.upper()
    culture = "zh-CN" if country == "CN" else f"en-{country}"

    client = AsyncDysonClient(email=account, country=country, culture=culture)
    try:
        await client.provision()
        if is_mobile:
            challenge = await client.begin_login_mobile(account)
        else:
            challenge = await client.begin_login(account)
        password = "" if is_mobile else getpass.getpass("MyDyson password (hidden): ")
        where = "phone" if is_mobile else "email"
        code = ask(f"Code Dyson just sent to your {where}")
        if is_mobile:
            await client.complete_login_mobile(
                str(challenge.challenge_id), code, account
            )
        else:
            await client.complete_login(
                str(challenge.challenge_id), code, account, password
            )
        print("  Signed in.")

        robots = [
            device
            for device in await client.get_devices()
            if getattr(device.category, "value", device.category) == "robot"
        ]
        if not robots:
            raise SystemExit(
                "\nNo robot vacuum was found on this account. Check that you "
                "signed in with the account the robot is set up on."
            )
        if len(robots) == 1:
            robot = robots[0]
        else:
            print("\nWhich robot should I listen to?")
            for index, device in enumerate(robots, 1):
                print(f"  {index}. {device.name} ({device.type})")
            while True:
                choice = ask("Number")
                if choice.isdigit() and 1 <= int(choice) <= len(robots):
                    robot = robots[int(choice) - 1]
                    break
                print("  Please type one of the numbers above.")

        config = robot.connected_configuration
        prefix = (
            config.mqtt.mqtt_root_topic_level
            if config is not None and config.mqtt is not None
            else robot.type
        )
        iot = await client.get_iot_credentials(robot.serial_number)
        creds = iot.iot_credentials
        credentials = {
            "client_id": str(creds.client_id),
            "custom_authorizer_name": creds.custom_authorizer_name,
            "token_key": creds.token_key,
            "token_value": str(creds.token_value),
            "token_signature": creds.token_signature,
        }
        return robot.name, robot.serial_number, prefix, iot.endpoint, credentials
    finally:
        await client.close()


def connect(
    host: str, credentials: dict[str, str], topic: str, log: CaptureLog
) -> mqtt.Client:
    """Open a listen-only connection to Dyson's cloud MQTT broker."""
    connected = threading.Event()
    failure: list[str] = []

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=credentials["client_id"],
        transport="websockets",
    )
    client.tls_set()
    client.ws_set_options(
        path="/mqtt",
        headers={
            "Host": host,
            credentials["token_key"]: credentials["token_value"],
            "X-Amz-CustomAuthorizer-Name": credentials["custom_authorizer_name"],
            "X-Amz-CustomAuthorizer-Signature": credentials["token_signature"],
        },
    )

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            failure.append(str(reason_code))
        else:
            client.subscribe(topic)
            log.note("connected")
        connected.set()

    def on_disconnect(client, userdata, flags, reason_code, properties):
        log.note("disconnected", reason=str(reason_code))
        if reason_code.is_failure:
            print(
                "\n  (The connection dropped. It usually comes back by itself "
                "within a few seconds.)"
            )

    def on_message(client, userdata, message):
        log.message(message.topic, message.payload)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    client.connect_async(host, 443, keepalive=60)
    client.loop_start()

    if not connected.wait(CONNECT_TIMEOUT) or failure:
        client.loop_stop()
        reason = failure[0] if failure else "no answer from Dyson's server"
        raise SystemExit(
            f"\nCouldn't connect to Dyson's cloud ({reason}).\n"
            "Check your internet connection and try again in a minute."
        )
    return client


def wait_with_counter(log: CaptureLog, seconds: int) -> None:
    """Keep listening for late replies, showing how many messages arrived."""
    for remaining in range(seconds, 0, -1):
        print(
            f"\r  Listening for replies... {remaining:2d}s  "
            f"({log.step_count} messages so far)",
            end="",
            flush=True,
        )
        time.sleep(1)
    print("\r" + " " * 60 + "\r", end="")


def wait_for_first_message(log: CaptureLog) -> bool:
    print(
        "\nNow open the MyDyson app and tap your robot. I'll wait until it says hello."
    )
    deadline = time.monotonic() + FIRST_MESSAGE_TIMEOUT
    while time.monotonic() < deadline:
        if log.total:
            print(f"  Connected. The robot is talking ({log.total} messages).")
            return True
        left = int(deadline - time.monotonic())
        print(f"\r  Waiting for the robot... {left:2d}s", end="", flush=True)
        time.sleep(1)
    print()
    return False


def run_step(log: CaptureLog, number: int, total: int, step: Step) -> str:
    """Show one step and return 'done', 'skipped' or 'quit'."""
    label = f"{number:02d} {step.title}"
    print(f"\nStep {number} of {total}: {step.title}")
    print(f"  {step.instruction}")
    if step.needs_docked:
        print("  (Do this while the robot is on its dock.)")
    log.set_step(label)
    log.note("step_start", instruction=step.instruction)
    answer = input("  Press Enter when you've done it (s = skip, q = finish now): ")
    answer = answer.strip().lower()
    if answer == "q":
        log.note("step_quit")
        return "quit"
    if answer == "s":
        log.note("step_skipped")
        print("  Skipped.")
        return "skipped"
    wait_with_counter(log, SETTLE_SECONDS)
    count = log.step_count
    log.note("step_done", messages=count)
    if count:
        print(f"  Got it: {count} messages recorded for this step.")
    else:
        print(
            "  No messages came in for this step. That's fine if the app "
            "didn't offer it; otherwise you can redo it later under "
            "'Anything else'."
        )
    return "done"


def run_extra_steps(log: CaptureLog) -> None:
    """Let the user name and record any number of extra controls."""
    index = 1
    while True:
        name = input(
            "\n  Name the next button you'll try (or just press Enter if you're done): "
        ).strip()
        if not name:
            return
        label = f"extra {index:02d} {name[:60]}"
        log.set_step(label)
        log.note("step_start", instruction=name)
        input(f"  Now use '{name}' in the app, then press Enter: ")
        wait_with_counter(log, SETTLE_SECONDS)
        log.note("step_done", messages=log.step_count)
        print(f"  Got it: {log.step_count} messages recorded for '{name}'.")
        index += 1


def main() -> None:
    banner("Dyson robot MQTT capture")
    print(
        "This records what your robot says while you use the MyDyson app,\n"
        "so the Home Assistant integration can learn your model. It only\n"
        "listens and never sends commands to the robot.\n\n"
        "Before you start:\n"
        "  - Have your phone with the MyDyson app ready.\n"
        "  - Put the robot on its dock with a charged battery.\n"
        "  - In Home Assistant, temporarily disable the Dyson integration\n"
        "    (Settings > Devices & services > Dyson > three dots > Disable)\n"
        "    so it doesn't share the connection with this script. Re-enable\n"
        "    it when you're done.\n"
        "  - Allow about 20 minutes. You can skip any step."
    )
    input("\nPress Enter to begin...")

    try:
        name, serial, prefix, host, credentials = asyncio.run(sign_in_and_get_robot())
    except SystemExit:
        raise
    except Exception as err:  # noqa: BLE001 - show a friendly message, not a trace
        raise SystemExit(
            f"\nSigning in didn't work: {err}\n"
            "Check the email, password and code, and that the country matches "
            "the one in your MyDyson account. Then run the script again."
        ) from None

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    out_path = Path.cwd() / f"dyson_{prefix}_capture_{stamp}.txt"
    log = CaptureLog(out_path, serial)
    log.write(
        {
            "t": utc_now(),
            "kind": "header",
            "script_version": SCRIPT_VERSION,
            "model_prefix": prefix,
            "robot_name": name.replace(serial, "SERIAL"),
            "steps": [step.title for step in STEPS],
        }
    )

    banner(f"2. Listening to {name} ({prefix})")
    client = connect(host, credentials, f"{prefix}/{serial}/#", log)
    print("  Connected to Dyson's cloud.")

    try:
        if not wait_for_first_message(log):
            print(
                "\nThe robot hasn't sent anything yet. Check that:\n"
                "  - the robot is online in the MyDyson app,\n"
                "  - the Dyson integration in Home Assistant is disabled for now.\n"
                "You can keep going: messages may still come in once you start "
                "the steps."
            )
            if input("Keep going? (Enter = yes, q = stop): ").strip().lower() == "q":
                return

        banner(f"3. Try each control ({len(STEPS)} steps)")
        for number, step in enumerate(STEPS, 1):
            if step.title == "Anything else":
                print(f"\nStep {number} of {len(STEPS)}: {step.title}")
                print(f"  {step.instruction}")
                run_extra_steps(log)
                continue
            if run_step(log, number, len(STEPS), step) == "quit":
                break
    except KeyboardInterrupt:
        print("\n  Stopping early. Everything so far has been saved.")
    finally:
        log.set_step("finished")
        log.note("end", total_messages=log.total)
        client.disconnect()
        client.loop_stop()
        log.close()

    banner("All done, thank you!")
    print(
        f"Recorded {log.total} messages to:\n\n    {out_path}\n\n"
        "Please drag that file into a comment on the GitHub issue you're\n"
        "helping with (for the RB07 that's issue #538). Your serial number,\n"
        "passwords and tokens are already removed,\n"
        "but room names and map positions are kept; open the file first if\n"
        "you want to check what's in it.\n\n"
        "Remember to re-enable the Dyson integration in Home Assistant."
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
