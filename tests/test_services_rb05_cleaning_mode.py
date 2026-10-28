"""Tests for the RB05 per-room cleaning_mode option on start_zone_clean."""

import copy
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from libdyson_rest.models import PersistentMapMeta, ZoneMeta

from custom_components.hass_dyson.services import (
    _handle_start_zone_clean,
    _rb05_set_room_modes,
)

MAP_ID = 1791116399


def _row(room_id: int, name: str, mode: int) -> list[Any]:
    """A 12-field room_preference row as returned by service.get_preference."""
    return [room_id, name, 2, mode, 0, 1, 0, 0, 1, 0, 3, 0]


def _preferences(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "prefer_on": 1,
        "room": [
            _row(11, "Living room", 0),
            _row(15, json.dumps({"type": "kitchen", "name": "Keuken"}), 0),
            _row(17, "Bathroom", 1),
        ],
        "uv_switch": [[11, 0], [15, 1], [17, 1]],
    }
    data.update(overrides)
    return data


class FakeRB05:
    """Minimal RB05 that answers the JDM methods used by the preference path."""

    def __init__(
        self,
        preferences: dict[str, Any],
        *,
        map_id: int = MAP_ID,
        store: bool = True,
        set_error: Exception | None = None,
        read_errors: list[Exception | None] | None = None,
    ) -> None:
        self.preferences = preferences
        self.map_id = map_id
        self.store = store
        self.set_error = set_error
        self.read_errors = list(read_errors or [])
        self.sent: list[dict[str, Any]] = []
        self.send_jdm_command = AsyncMock(side_effect=self._jdm)

    async def _jdm(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "service.get_map_list":
            return {"map_list": [{"id": self.map_id, "cur": True}]}
        if method == "service.get_preference":
            if self.read_errors:
                err = self.read_errors.pop(0)
                if err is not None:
                    raise err
            return copy.deepcopy(self.preferences)
        if method == "service.set_preference":
            self.sent.append(copy.deepcopy(params))
            if self.store:
                modes = {row[0]: row[3] for row in params["room_preference"]}
                for row in self.preferences["room"]:
                    row[3] = modes.get(row[0], row[3])
            if self.set_error is not None:
                raise self.set_error
            return {"code": 0}
        raise AssertionError(f"unexpected method {method}")


class TestRb05SetRoomModes:
    """Test _rb05_set_room_modes."""

    @pytest.mark.asyncio
    async def test_sets_only_targeted_rooms(self):
        device = FakeRB05(_preferences())

        await _rb05_set_room_modes(device, MAP_ID, [15], "vacuum_and_mop")

        assert len(device.sent) == 1
        payload = device.sent[0]
        assert payload["map_id"] == MAP_ID
        assert payload["prefer_type"] == 1
        assert payload["uv_switch"] == [[11, 0], [15, 1], [17, 1]]
        rows = {row[0]: row for row in payload["room_preference"]}
        # Same normalisation as MyDyson: eleven fields, field 2 zero.
        assert all(len(row) == 11 and row[2] == 0 for row in rows.values())
        # Encoded room names are sent as their display name.
        assert rows[15][1] == "Keuken"
        # Only the targeted room changes mode.
        assert rows[15][3] == 1
        assert rows[11][3] == 0
        assert rows[17][3] == 1

    @pytest.mark.asyncio
    async def test_already_set_sends_nothing(self):
        device = FakeRB05(_preferences())

        await _rb05_set_room_modes(device, MAP_ID, [11], "vacuum_only")

        assert device.sent == []

    @pytest.mark.asyncio
    async def test_non_zero_reply_code_is_verified_by_reread(self):
        device = FakeRB05(_preferences(), set_error=RuntimeError("code 1"))

        await _rb05_set_room_modes(device, MAP_ID, [11, 15], "mop_only")

        assert len(device.sent) == 1
        modes = {row[0]: row[3] for row in device.preferences["room"]}
        assert modes == {11: 2, 15: 2, 17: 1}

    @pytest.mark.asyncio
    async def test_not_stored_raises(self):
        device = FakeRB05(_preferences(), store=False)

        with pytest.raises(HomeAssistantError, match="did not store"):
            await _rb05_set_room_modes(device, MAP_ID, [15], "vacuum_and_mop")

    @pytest.mark.asyncio
    async def test_read_failure_raises(self):
        device = FakeRB05(_preferences(), read_errors=[RuntimeError("timeout")])

        with pytest.raises(HomeAssistantError, match="Could not read"):
            await _rb05_set_room_modes(device, MAP_ID, [15], "vacuum_and_mop")
        assert device.sent == []

    @pytest.mark.asyncio
    async def test_confirm_failure_raises(self):
        device = FakeRB05(
            _preferences(), read_errors=[None, ValueError("No room preferences")]
        )

        with pytest.raises(HomeAssistantError, match="Could not confirm"):
            await _rb05_set_room_modes(device, MAP_ID, [15], "vacuum_and_mop")

    @pytest.mark.asyncio
    async def test_other_current_map_raises(self):
        device = FakeRB05(_preferences(), map_id=42)

        with pytest.raises(HomeAssistantError, match="not the requested map"):
            await _rb05_set_room_modes(device, MAP_ID, [15], "vacuum_and_mop")
        assert device.sent == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "preferences",
        [
            _preferences(prefer_on=0),
            _preferences(room=[[*_row(11, "Living room", 0)[:11], 1]]),
        ],
    )
    async def test_unsupported_flags_raise(self, preferences):
        device = FakeRB05(preferences)

        with pytest.raises(HomeAssistantError, match="Unsupported RB05"):
            await _rb05_set_room_modes(device, MAP_ID, [11], "vacuum_and_mop")
        assert device.sent == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("uv", [None, [[11]], ["bad"]])
    async def test_malformed_uv_raises(self, uv):
        device = FakeRB05(_preferences(uv_switch=uv))

        with pytest.raises(HomeAssistantError, match="UV preferences"):
            await _rb05_set_room_modes(device, MAP_ID, [11], "vacuum_and_mop")
        assert device.sent == []

    @pytest.mark.asyncio
    async def test_room_without_preferences_raises(self):
        device = FakeRB05(_preferences())

        with pytest.raises(HomeAssistantError, match="have no preferences"):
            await _rb05_set_room_modes(device, MAP_ID, [99], "vacuum_and_mop")
        assert device.sent == []

    @pytest.mark.asyncio
    async def test_unrecognized_encoded_name_raises(self):
        preferences = _preferences()
        preferences["room"][1][1] = json.dumps({"type": "kitchen"})
        device = FakeRB05(preferences)

        with pytest.raises(HomeAssistantError, match="encoded room name"):
            await _rb05_set_room_modes(device, MAP_ID, [15], "vacuum_and_mop")
        assert device.sent == []


def _rb05_map() -> list[PersistentMapMeta]:
    return [
        PersistentMapMeta(
            id=str(MAP_ID),
            name="Begane grond",
            zones_definition_last_updated_date="2026-10-18T09:00:00Z",
            zones=[
                ZoneMeta(id="11", name="Living room", icon=None, area=None),
                ZoneMeta(id="15", name="Keuken", icon=None, area=None),
            ],
            is_current_map=True,
        )
    ]


def _coordinator(prefix: str | None) -> MagicMock:
    coordinator = MagicMock()
    coordinator.serial_number = "7VS-EU-TEST0000A"
    coordinator.device = MagicMock()
    coordinator.device.mqtt_prefix = prefix
    coordinator.device.robot_start_clean = AsyncMock()
    return coordinator


class TestStartZoneCleanCleaningMode:
    """Test the cleaning_mode option of _handle_start_zone_clean."""

    async def _run(self, coordinator, data, set_modes=None):
        call = MagicMock()
        call.data = data
        with (
            patch(
                "custom_components.hass_dyson.services._get_coordinator_from_device_id",
                AsyncMock(return_value=coordinator),
            ),
            patch(
                "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
                AsyncMock(return_value=_rb05_map()),
            ),
            patch(
                "custom_components.hass_dyson.services._rb05_set_room_modes",
                set_modes or AsyncMock(),
            ) as mock_set,
        ):
            await _handle_start_zone_clean(MagicMock(), call)
        return mock_set

    @pytest.mark.asyncio
    async def test_sets_modes_before_start(self):
        coordinator = _coordinator("RB05")
        mock_set = await self._run(
            coordinator,
            {
                "device_id": "dev",
                "zones": ["Keuken"],
                "cleaning_mode": "vacuum_and_mop",
            },
        )

        mock_set.assert_awaited_once_with(
            coordinator.device, MAP_ID, [15], "vacuum_and_mop"
        )
        coordinator.device.robot_start_clean.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_start_when_setting_modes_fails(self):
        coordinator = _coordinator("RB05")
        with pytest.raises(HomeAssistantError):
            await self._run(
                coordinator,
                {
                    "device_id": "dev",
                    "zones": ["Living room"],
                    "cleaning_mode": "vacuum_only",
                },
                set_modes=AsyncMock(side_effect=HomeAssistantError("failed")),
            )
        coordinator.device.robot_start_clean.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejected_on_other_robots(self):
        coordinator = _coordinator("N223")
        with pytest.raises(ServiceValidationError, match="only supported"):
            await self._run(
                coordinator,
                {
                    "device_id": "dev",
                    "zones": ["Keuken"],
                    "cleaning_mode": "vacuum_and_mop",
                },
            )
        coordinator.device.robot_start_clean.assert_not_called()

    @pytest.mark.asyncio
    async def test_without_cleaning_mode_preferences_untouched(self):
        coordinator = _coordinator("RB05")
        mock_set = await self._run(
            coordinator, {"device_id": "dev", "zones": ["Keuken"]}
        )

        mock_set.assert_not_called()
        coordinator.device.robot_start_clean.assert_awaited_once()
