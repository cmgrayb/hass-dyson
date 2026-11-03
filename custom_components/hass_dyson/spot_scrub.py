"""RB05 room preferences observed in MyDyson MQTT exchanges.

Keep this protocol separate from HA entities. Unknown formats fail closed rather
than overwriting room preferences with guessed defaults.
"""

from __future__ import annotations

import copy
import json
from typing import Any

MODE_CODES = {
    "vacuum_only": 0,
    "vacuum_and_mop": 1,
    "mop_only": 2,
    "vacuum_then_mop": 3,
}

# Other per-room settings, decoded by changing one MyDyson setting at a time
# and reading the room preferences back (RB05, 2026-10). Values are written
# into the same row as the cleaning mode; settings not listed are preserved.
VACUUM_POWER_CODES = {"auto": 0, "boost": 1, "quiet": 2, "quick": 3}
HYDRATION_CODES = {"very_low": 99, "low": 0, "medium": 1, "high": 2}
WASH_REPETITION_CODES = {1: 0, 2: 1}

# Setting name -> (room row index, option -> code)
ROOM_SETTINGS: dict[str, tuple[int, dict[Any, int]]] = {
    "cleaning_mode": (3, MODE_CODES),
    "vacuum_power": (4, VACUUM_POWER_CODES),
    "hydration": (5, HYDRATION_CODES),
    "wash_repetitions": (6, WASH_REPETITION_CODES),
}

# Preferences are only written while the robot is docked or finished.
IDLE_STATES = frozenset(
    {"INACTIVE_CHARGING", "INACTIVE_CHARGED", "FULL_CLEAN_FINISHED"}
)


def validate_preferences(data: dict[str, Any]) -> list[list[Any]]:
    """Validate the captured response layout before reading or writing it."""
    rows = data.get("room")
    if not isinstance(rows, list) or not rows:
        raise ValueError("No room preferences returned")
    ids = set()
    for row in rows:
        if (
            not isinstance(row, list)
            or len(row) != 12
            or type(row[0]) is not int
            or row[0] in ids
            or not isinstance(row[1], str)
            or type(row[3]) is not int
        ):
            raise ValueError("Unrecognized RB05 room preference format")
        ids.add(row[0])
    return rows


def room_name(row: list[Any]) -> str:
    """Return a room's display name, decoding MyDyson's JSON-encoded labels."""
    if not row[1].startswith("{"):
        return row[1]
    label = json.loads(row[1])
    if not isinstance(label, dict) or not isinstance(label.get("name"), str):
        raise ValueError("Unrecognized encoded room name")
    return label["name"]


def decode_room_settings(row: list[Any]) -> dict[str, Any]:
    """Return a row's known settings; unknown codes are reported as None."""
    decoded: dict[str, Any] = {}
    for setting, (index, codes) in ROOM_SETTINGS.items():
        reverse = {code: option for option, code in codes.items()}
        decoded[setting] = reverse.get(row[index])
    return decoded


def _normalize_settings(value: Any) -> dict[str, Any]:
    """Accept a bare cleaning mode or a mapping of settings, and validate it."""
    settings = {"cleaning_mode": value} if isinstance(value, str) else value
    if not isinstance(settings, dict) or not settings:
        raise ValueError(f"Invalid room settings: {value}")
    normalized: dict[str, Any] = {}
    for setting, option in settings.items():
        if setting not in ROOM_SETTINGS:
            raise ValueError(f"Unknown room setting: {setting}")
        if setting == "wash_repetitions" and isinstance(option, str):
            option = int(option) if option.strip().isdigit() else option
        if option not in ROOM_SETTINGS[setting][1]:
            raise ValueError(f"Unknown {setting}: {option}")
        normalized[setting] = option
    return normalized


def resolve_room_settings(
    preferences: dict[str, Any], room_settings: dict[Any, Any]
) -> dict[int, dict[str, Any]]:
    """Map room ids or display names to validated settings; unknown rooms fail."""
    rows = validate_preferences(preferences)
    by_id = {row[0]: row for row in rows}
    by_name: dict[str, int] = {}
    for row in rows:
        by_name.setdefault(room_name(row).casefold(), row[0])
    resolved: dict[int, dict[str, Any]] = {}
    for key, value in room_settings.items():
        settings = _normalize_settings(value)
        text = str(key).strip()
        if text.isdigit() and int(text) in by_id:
            room_id = int(text)
        elif text.casefold() in by_name:
            room_id = by_name[text.casefold()]
        else:
            raise ValueError(f"Unknown room: {key}")
        resolved[room_id] = settings
    return resolved


def resolve_room_modes(
    preferences: dict[str, Any], room_modes: dict[Any, str]
) -> dict[int, str]:
    """Map room ids or display names to mode options; unknown rooms fail."""
    for option in room_modes.values():
        if option not in MODE_CODES:
            raise ValueError(f"Unknown cleaning mode: {option}")
    return {
        room_id: settings["cleaning_mode"]
        for room_id, settings in resolve_room_settings(preferences, room_modes).items()
    }


def settings_match(row: list[Any], settings: dict[str, Any]) -> bool:
    """True when a read-back row carries every requested setting."""
    return all(
        row[ROOM_SETTINGS[name][0]] == ROOM_SETTINGS[name][1][option]
        for name, option in settings.items()
    )


def room_settings_payload(
    map_id: int, preferences: dict[str, Any], changes: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    """Change listed settings of listed rooms; everything else is preserved."""
    rows = copy.deepcopy(validate_preferences(preferences))
    if preferences.get("prefer_on") != 1 or any(row[11] != 0 for row in rows):
        raise ValueError("Unsupported RB05 preference flags")
    uv = preferences.get("uv_switch")
    if not isinstance(uv, list) or any(
        not isinstance(item, list) or len(item) != 2 for item in uv
    ):
        raise ValueError("Missing or malformed UV preferences")
    if unknown := set(changes) - {row[0] for row in rows}:
        raise ValueError(f"Unknown room ids: {sorted(unknown)}")
    for row in rows:
        # MyDyson sends eleven fields, normalizes response field 2 to zero,
        # and converts encoded room labels to their display names.
        row.pop()
        row[2] = 0
        for setting, option in changes.get(row[0], {}).items():
            index, codes = ROOM_SETTINGS[setting]
            row[index] = codes[option]
        row[1] = room_name(row)
    return {
        "map_id": map_id,
        "prefer_type": 1,
        "room_preference": rows,
        "uv_switch": copy.deepcopy(uv),
    }


def room_modes_payload(
    map_id: int, preferences: dict[str, Any], room_modes: dict[int, str]
) -> dict[str, Any]:
    """Change listed rooms on this map; other rooms keep their current mode."""
    return room_settings_payload(
        map_id,
        preferences,
        {room_id: {"cleaning_mode": mode} for room_id, mode in room_modes.items()},
    )


def mode_payload(
    map_id: int, preferences: dict[str, Any], option: str
) -> dict[str, Any]:
    """Change all rooms on this map, preserving unrelated writable fields."""
    rows = validate_preferences(preferences)
    return room_modes_payload(map_id, preferences, {row[0]: option for row in rows})


async def read_preferences(device: Any) -> tuple[int, dict[str, Any]]:
    """Read preferences for the robot's unambiguous current map."""
    maps = await device.send_jdm_command("service.get_map_list", {})
    current = [m for m in maps.get("map_list", []) if m.get("cur") is True]
    if len(current) != 1 or type(current[0].get("id")) is not int:
        raise ValueError("No unambiguous current RB05 map")
    map_id = current[0]["id"]
    preferences = await device.send_jdm_command(
        "service.get_preference", {"map_id": map_id}
    )
    validate_preferences(preferences)
    return map_id, preferences
