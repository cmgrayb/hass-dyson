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


def mode_payload(
    map_id: int, preferences: dict[str, Any], option: str
) -> dict[str, Any]:
    """Change all rooms on this map, preserving unrelated writable fields."""
    mode = MODE_CODES[option]
    rows = copy.deepcopy(validate_preferences(preferences))
    if preferences.get("prefer_on") != 1 or any(row[11] != 0 for row in rows):
        raise ValueError("Unsupported RB05 preference flags")
    uv = preferences.get("uv_switch")
    if not isinstance(uv, list) or any(
        not isinstance(item, list) or len(item) != 2 for item in uv
    ):
        raise ValueError("Missing or malformed UV preferences")
    for row in rows:
        # MyDyson sends eleven fields, normalizes response field 2 to zero,
        # and converts encoded room labels to their display names.
        row.pop()
        row[2] = 0
        row[3] = mode
        if row[1].startswith("{"):
            label = json.loads(row[1])
            if not isinstance(label, dict) or not isinstance(label.get("name"), str):
                raise ValueError("Unrecognized encoded room name")
            row[1] = label["name"]
    return {
        "map_id": map_id,
        "prefer_type": 1,
        "room_preference": rows,
        "uv_switch": copy.deepcopy(uv),
    }


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
