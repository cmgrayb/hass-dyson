"""Tests for current-map tracking: device MQTT harvest, _effective_current_map,
and the Current Map sensor.

The 360 Vis Nav announces the persistentMapId (and per-zone progress) in its
MQTT state stream during cleans but never via the cloud isCurrentMap flag;
v2/Spot+Clean devices set the cloud flag instead. Both signals are covered.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from libdyson_rest.models import PersistentMapMeta, ZoneMeta

from custom_components.hass_dyson.device import DysonDevice
from custom_components.hass_dyson.entity import DysonEntity
from custom_components.hass_dyson.sensor import DysonCurrentMapSensor
from custom_components.hass_dyson.services import _effective_current_map

SERIAL = "VS9-GB-HJA0000A"


def _zone(zone_id: str, name: str) -> ZoneMeta:
    return ZoneMeta(id=zone_id, name=name, icon=None, area=None)


def _maps(
    current: str | None = None, visited: dict[str, str] | None = None
) -> list[PersistentMapMeta]:
    visited = visited or {}
    return [
        PersistentMapMeta(
            id="map-up",
            name="Upstairs",
            zones_definition_last_updated_date=None,
            zones=[_zone("1", "Hallway"), _zone("2", "Office")],
            is_current_map=current == "map-up",
            last_visited=visited.get("map-up"),
        ),
        PersistentMapMeta(
            id="map-down",
            name="Downstairs",
            zones_definition_last_updated_date=None,
            zones=[_zone("1", "Hallway"), _zone("3", "Mud Room")],
            is_current_map=current == "map-down",
            last_visited=visited.get("map-down"),
        ),
    ]


def _bare_device() -> DysonDevice:
    device = object.__new__(DysonDevice)
    device._state_data = {}
    device._log_serial = "TEST-SERIAL"
    device._message_callbacks = []
    return device


class TestDeviceMapHarvest:
    """Test that state messages populate robot_current_map_id/zone_status."""

    def test_state_change_harvests_programme_map_id(self):
        device = _bare_device()
        device._handle_state_change(
            {
                "msg": "STATE-CHANGE",
                "oldstate": "INACTIVE_CHARGED",
                "newstate": "FULL_CLEAN_INITIATED",
                "cleaningProgramme": {
                    "persistentMapId": "map-down",
                    "orderedZones": [],
                    "unorderedZones": ["3"],
                },
            }
        )
        assert device.robot_current_map_id == "map-down"

    def test_state_change_harvests_top_level_map_and_zone_status(self):
        device = _bare_device()
        zone_status = [
            {"zoneId": "1", "cleanStatus": "CLEAN_NOT_REQUESTED"},
            {"zoneId": "3", "cleanStatus": "CLEAN_IN_PROGRESS"},
        ]
        device._handle_state_change(
            {
                "msg": "STATE-CHANGE",
                "newstate": "FULL_CLEAN_RUNNING",
                "persistentMapId": "map-down",
                "zoneStatus": zone_status,
            }
        )
        assert device.robot_current_map_id == "map-down"
        assert device.robot_zone_status == zone_status

    def test_idle_current_state_retains_last_map(self):
        """A docked CURRENT-STATE (no map fields) must not clear the map."""
        device = _bare_device()
        device._handle_state_change(
            {"msg": "STATE-CHANGE", "persistentMapId": "map-down"}
        )
        device._handle_current_state(
            {"msg": "CURRENT-STATE", "state": "INACTIVE_CHARGED"}, "topic"
        )
        assert device.robot_current_map_id == "map-down"

    def test_unset_returns_none(self):
        device = _bare_device()
        assert device.robot_current_map_id is None
        assert device.robot_zone_status is None


class TestRobotSessionTracking:
    """robot_session_active opens on activity, survives faults, closes docked.

    Fault semantics come from real captures (matterbridge-dyson-robot
    277.jsonl, firmware RB03PR.01.08.006.5079): FAULT_USER_RECOVERABLE was
    observed both mid-clean (from FULL_CLEAN_PAUSED — robot on the floor)
    and while docked (from INACTIVE_CHARGING) — the flag must differ.
    """

    @staticmethod
    def _sc(device, newstate, oldstate=None):
        device._handle_state_change(
            {"msg": "STATE-CHANGE", "oldstate": oldstate, "newstate": newstate}
        )

    def test_defaults_inactive(self):
        assert _bare_device().robot_session_active is False

    def test_opens_on_clean_and_closes_on_finish(self):
        device = _bare_device()
        self._sc(device, "FULL_CLEAN_INITIATED", oldstate="INACTIVE_CHARGED")
        assert device.robot_session_active is True
        self._sc(device, "FULL_CLEAN_FINISHED")
        assert device.robot_session_active is False

    def test_mid_clean_fault_keeps_session_open(self):
        device = _bare_device()
        self._sc(device, "FULL_CLEAN_RUNNING")
        self._sc(device, "FULL_CLEAN_PAUSED")
        self._sc(device, "FAULT_USER_RECOVERABLE", oldstate="FULL_CLEAN_PAUSED")
        assert device.robot_session_active is True
        self._sc(device, "FULL_CLEAN_RUNNING", oldstate="FAULT_USER_RECOVERABLE")
        assert device.robot_session_active is True

    def test_docked_fault_keeps_session_closed(self):
        device = _bare_device()
        self._sc(device, "FAULT_USER_RECOVERABLE", oldstate="INACTIVE_CHARGING")
        assert device.robot_session_active is False

    def test_on_dock_fault_closes_session(self):
        device = _bare_device()
        self._sc(device, "FULL_CLEAN_RUNNING")
        self._sc(device, "FAULT_ON_DOCK_CHARGING")
        assert device.robot_session_active is False

    def test_abort_keeps_session_until_inactive(self):
        """ABORTED means returning to dock — still out on the floor."""
        device = _bare_device()
        self._sc(device, "FULL_CLEAN_RUNNING")
        self._sc(device, "FULL_CLEAN_ABORTED")
        assert device.robot_session_active is True
        device._handle_current_state(
            {"msg": "CURRENT-STATE", "state": "INACTIVE_CHARGING"}, "topic"
        )
        assert device.robot_session_active is False

    def test_current_state_primes_session_after_restart(self):
        """HA restarting mid-clean re-learns the session from CURRENT-STATE."""
        device = _bare_device()
        device._handle_current_state(
            {"msg": "CURRENT-STATE", "state": "FULL_CLEAN_RUNNING"}, "topic"
        )
        assert device.robot_session_active is True

    def test_mapping_lifecycle(self):
        device = _bare_device()
        self._sc(device, "MAPPING_RUNNING")
        assert device.robot_session_active is True
        self._sc(device, "MAPPING_FINISHED")
        assert device.robot_session_active is False

    def test_replace_on_dock_fault_closes_session(self):
        """FAULT_REPLACE_ON_DOCK is terminal — the robot will not resume."""
        device = _bare_device()
        self._sc(device, "FULL_CLEAN_RUNNING")
        self._sc(device, "FAULT_REPLACE_ON_DOCK")
        assert device.robot_session_active is False

    def test_machine_off_closes_session(self):
        device = _bare_device()
        self._sc(device, "FULL_CLEAN_RUNNING")
        self._sc(device, "MACHINE_OFF")
        assert device.robot_session_active is False

    def test_missing_state_field_preserves_session(self):
        device = _bare_device()
        self._sc(device, "FULL_CLEAN_RUNNING")
        device._handle_state_change(
            {"msg": "STATE-CHANGE", "persistentMapId": "map-down"}
        )
        assert device.robot_session_active is True


class TestEffectiveCurrentMap:
    """Test the robot-first, cloud-fallback current-map resolution."""

    @staticmethod
    def _coordinator(
        device_map_id, robot_state: str = "FULL_CLEAN_RUNNING"
    ) -> MagicMock:
        coordinator = MagicMock()
        coordinator.device = MagicMock()
        coordinator.device.robot_current_map_id = device_map_id
        coordinator.device.robot_state = robot_state
        return coordinator

    def test_robot_reported_map_wins_over_cloud_flag(self):
        maps = _maps(current="map-up")
        coordinator = self._coordinator("map-down")
        assert _effective_current_map(maps, coordinator).id == "map-down"

    def test_unmatched_robot_id_falls_back_to_cloud(self):
        maps = _maps(current="map-up")
        coordinator = self._coordinator("map-gone")
        assert _effective_current_map(maps, coordinator).id == "map-up"

    def test_no_signals_returns_none(self):
        coordinator = self._coordinator(None)
        assert _effective_current_map(_maps(), coordinator) is None

    def test_docked_retained_map_defers_to_cloud_flag(self):
        """Docked, the retained MQTT map is stale — the cloud flag wins."""
        maps = _maps(current="map-up")
        coordinator = self._coordinator("map-down", robot_state="INACTIVE_CHARGED")
        assert _effective_current_map(maps, coordinator).id == "map-up"

    def test_docked_retained_map_without_cloud_flag_is_unknown(self):
        """Docked with no cloud flag: currency is unknown, not the stale map."""
        coordinator = self._coordinator("map-down", robot_state="INACTIVE_CHARGED")
        assert _effective_current_map(_maps(), coordinator) is None

    def test_mapping_state_counts_as_active(self):
        """First-run mapping announces the map being built — trust it."""
        coordinator = self._coordinator("map-down", robot_state="MAPPING_RUNNING")
        assert _effective_current_map(_maps(), coordinator).id == "map-down"

    def test_mid_clean_fault_trusts_robot_map_via_session(self):
        """A transient fault mid-clean keeps the MQTT map authoritative.

        Real devices report FAULT_USER_RECOVERABLE while still out on the
        floor mid-clean; the session flag (a real bool on DysonDevice)
        outranks the state-prefix heuristic.
        """
        maps = _maps(current="map-up")
        coordinator = self._coordinator(
            "map-down", robot_state="FAULT_USER_RECOVERABLE"
        )
        coordinator.device.robot_session_active = True
        assert _effective_current_map(maps, coordinator).id == "map-down"

    def test_session_flag_false_defers_to_cloud(self):
        """An explicit closed session ignores the retained MQTT map."""
        maps = _maps(current="map-up")
        coordinator = self._coordinator("map-down", robot_state="FULL_CLEAN_FINISHED")
        coordinator.device.robot_session_active = False
        assert _effective_current_map(maps, coordinator).id == "map-up"

    def test_no_coordinator_uses_cloud_flag(self):
        assert _effective_current_map(_maps(current="map-down")).id == "map-down"


class TestCurrentMapSensor:
    """Test DysonCurrentMapSensor source priority and attributes."""

    @staticmethod
    def _sensor(device_map_id=None, robot_state="INACTIVE_CHARGED"):
        coordinator = MagicMock()
        coordinator.serial_number = SERIAL
        coordinator.device = MagicMock()
        coordinator.device.robot_current_map_id = device_map_id
        coordinator.device.robot_zone_status = None
        coordinator.device.robot_state = robot_state
        return DysonCurrentMapSensor(coordinator)

    @staticmethod
    def _patched(maps, records=None):
        pmap_cache = MagicMock()
        pmap_cache.get.return_value = maps
        pmap_cache.get_stale.return_value = maps
        clean_cache = MagicMock()
        clean_cache.get.return_value = records
        clean_cache.get_stale.return_value = records
        return (
            patch(
                "custom_components.hass_dyson.services._persistent_map_cache",
                pmap_cache,
            ),
            patch("custom_components.hass_dyson.sensor._clean_maps_cache", clean_cache),
        )

    def test_unique_id_and_name(self):
        sensor = self._sensor()
        assert sensor._attr_unique_id == f"{SERIAL}_current_map"
        assert sensor._attr_name == "Current Map"

    def test_should_poll_is_effective(self):
        """_attr_should_poll is inert on CoordinatorEntity subclasses (#408)."""
        assert self._sensor().should_poll is True

    def test_robot_source_wins(self):
        sensor = self._sensor(device_map_id="map-down")
        p1, p2 = self._patched(_maps(current="map-up"))
        with p1, p2:
            assert sensor.native_value == "Downstairs"
            attrs = sensor.extra_state_attributes
        assert attrs["source"] == "robot"
        assert attrs["map_id"] == "map-down"
        assert attrs["zones"] == ["Hallway", "Mud Room"]

    def test_cloud_source(self):
        sensor = self._sensor(device_map_id=None)
        p1, p2 = self._patched(_maps(current="map-up"))
        with p1, p2:
            assert sensor.native_value == "Upstairs"
            assert sensor.extra_state_attributes["source"] == "cloud"

    def test_restored_source(self):
        """A restored id resolves to the LIVE metadata name, not the persisted one."""
        sensor = self._sensor(device_map_id=None)
        sensor._restored_map_id = "map-down"
        sensor._restored_name = "Stale Persisted Name"
        p1, p2 = self._patched(_maps())
        with p1, p2:
            assert sensor.native_value == "Downstairs"
            assert sensor.extra_state_attributes["source"] == "restored"

    def test_cloud_outranks_restored(self):
        sensor = self._sensor(device_map_id=None)
        sensor._restored_map_id = "map-down"
        sensor._restored_name = "Downstairs"
        p1, p2 = self._patched(_maps(current="map-up"))
        with p1, p2:
            assert sensor.native_value == "Upstairs"
            assert sensor.extra_state_attributes["source"] == "cloud"

    def test_last_visited_newest_wins(self):
        sensor = self._sensor(device_map_id=None)
        p1, p2 = self._patched(
            _maps(
                visited={
                    "map-up": "2026-07-10T09:12:00Z",
                    "map-down": "2026-07-11T16:39:57.525Z",
                }
            )
        )
        with p1, p2:
            assert sensor.native_value == "Downstairs"
            assert sensor.extra_state_attributes["source"] == "last_visited"

    def test_restored_outranks_last_visited(self):
        sensor = self._sensor(device_map_id=None)
        sensor._restored_map_id = "map-up"
        sensor._restored_name = "Upstairs"
        p1, p2 = self._patched(_maps(visited={"map-down": "2026-07-11T16:39:57Z"}))
        with p1, p2:
            assert sensor.native_value == "Upstairs"
            assert sensor.extra_state_attributes["source"] == "restored"

    def test_last_visited_outranks_clean_history(self):
        sensor = self._sensor(device_map_id=None)
        record = MagicMock()
        record.persistent_map_id = "map-up"
        p1, p2 = self._patched(
            _maps(visited={"map-down": "2026-07-11T16:39:57Z"}), records=[record]
        )
        with p1, p2:
            assert sensor.native_value == "Downstairs"
            assert sensor.extra_state_attributes["source"] == "last_visited"

    def test_clean_history_fallback(self):
        """All-None lastVisited must skip the last_visited source entirely."""
        sensor = self._sensor(device_map_id=None)
        record = MagicMock()
        record.persistent_map_id = "map-up"
        p1, p2 = self._patched(_maps(), records=[record])
        with p1, p2:
            assert sensor.native_value == "Upstairs"
            assert sensor.extra_state_attributes["source"] == "clean_history"

    def test_no_signal_is_unknown(self):
        sensor = self._sensor(device_map_id=None)
        p1, p2 = self._patched(_maps(), records=[])
        with p1, p2:
            assert sensor.native_value is None

    def test_stale_metadata_cache_still_resolves(self):
        """A fresh-cache miss must fall back to the stale metadata copy."""
        sensor = self._sensor(device_map_id=None)
        pmap_cache = MagicMock()
        pmap_cache.get.return_value = None
        pmap_cache.get_stale.return_value = _maps(current="map-up")
        clean_cache = MagicMock()
        clean_cache.get.return_value = None
        clean_cache.get_stale.return_value = None
        with (
            patch(
                "custom_components.hass_dyson.services._persistent_map_cache",
                pmap_cache,
            ),
            patch("custom_components.hass_dyson.sensor._clean_maps_cache", clean_cache),
        ):
            assert sensor.native_value == "Upstairs"
            assert sensor.extra_state_attributes["source"] == "cloud"

    def test_robot_map_id_without_metadata_shows_id(self):
        sensor = self._sensor(device_map_id="map-mystery")
        p1, p2 = self._patched([])
        with p1, p2:
            assert sensor.native_value == "map-mystery"
            attrs = sensor.extra_state_attributes
        assert attrs["map_id"] == "map-mystery"
        assert "zones" not in attrs

    def test_clean_history_skips_records_without_map_id(self):
        sensor = self._sensor(device_map_id=None)
        empty = MagicMock()
        empty.persistent_map_id = None
        record = MagicMock()
        record.persistent_map_id = "map-up"
        p1, p2 = self._patched(_maps(), records=[empty, record])
        with p1, p2:
            assert sensor.native_value == "Upstairs"
            assert sensor.extra_state_attributes["source"] == "clean_history"

    def test_zone_status_attribute_while_cleaning(self):
        sensor = self._sensor(
            device_map_id="map-down", robot_state="FULL_CLEAN_RUNNING"
        )
        sensor.coordinator.device.robot_zone_status = [
            {"zoneId": "1", "cleanStatus": "CLEAN_NOT_REQUESTED"},
            {"zoneId": "3", "cleanStatus": "CLEAN_IN_PROGRESS"},
        ]
        p1, p2 = self._patched(_maps())
        with p1, p2:
            attrs = sensor.extra_state_attributes
        assert attrs["zone_status"] == {
            "Hallway": "CLEAN_NOT_REQUESTED",
            "Mud Room": "CLEAN_IN_PROGRESS",
        }

    def test_zone_status_hidden_when_docked(self):
        sensor = self._sensor(device_map_id="map-down", robot_state="INACTIVE_CHARGED")
        sensor.coordinator.device.robot_zone_status = [
            {"zoneId": "3", "cleanStatus": "CLEAN_IN_PROGRESS"}
        ]
        p1, p2 = self._patched(_maps())
        with p1, p2:
            attrs = sensor.extra_state_attributes
        assert "zone_status" not in attrs

    def test_zone_status_survives_mid_clean_fault(self):
        """A transient fault must not hide live per-zone progress."""
        sensor = self._sensor(
            device_map_id="map-down", robot_state="FAULT_USER_RECOVERABLE"
        )
        sensor.coordinator.device.robot_session_active = True
        sensor.coordinator.device.robot_zone_status = [
            {"zoneId": "3", "cleanStatus": "CLEAN_IN_PROGRESS"}
        ]
        p1, p2 = self._patched(_maps())
        with p1, p2:
            attrs = sensor.extra_state_attributes
        assert attrs["zone_status"] == {"Mud Room": "CLEAN_IN_PROGRESS"}

    def test_zone_status_hidden_when_session_closed(self):
        """Explicit closed session hides retained zoneStatus even mid-FINISHED."""
        sensor = self._sensor(
            device_map_id="map-down", robot_state="FULL_CLEAN_FINISHED"
        )
        sensor.coordinator.device.robot_session_active = False
        sensor.coordinator.device.robot_zone_status = [
            {"zoneId": "3", "cleanStatus": "CLEAN_COMPLETE"}
        ]
        p1, p2 = self._patched(_maps())
        with p1, p2:
            attrs = sensor.extra_state_attributes
        assert "zone_status" not in attrs

    @pytest.mark.asyncio
    async def test_async_update_warms_both_caches(self):
        sensor = self._sensor()
        with (
            patch(
                "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
                AsyncMock(return_value=[]),
            ) as fetch_maps,
            patch(
                "custom_components.hass_dyson.sensor.fetch_clean_maps",
                AsyncMock(return_value=[]),
            ) as fetch_cleans,
        ):
            await sensor.async_update()
        fetch_maps.assert_awaited_once()
        fetch_cleans.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_added_to_hass_restores_state(self):
        """A valid previous state seeds the restored map name and id."""
        sensor = self._sensor()
        last = MagicMock()
        last.state = "Downstairs"
        last.attributes = {"map_id": "map-down"}
        with (
            patch.object(DysonEntity, "async_added_to_hass", AsyncMock()),
            patch.object(sensor, "async_get_last_state", AsyncMock(return_value=last)),
        ):
            await sensor.async_added_to_hass()
        assert sensor._restored_name == "Downstairs"
        assert sensor._restored_map_id == "map-down"

    @pytest.mark.asyncio
    async def test_added_to_hass_ignores_unknown_state(self):
        sensor = self._sensor()
        last = MagicMock()
        last.state = "unknown"
        with (
            patch.object(DysonEntity, "async_added_to_hass", AsyncMock()),
            patch.object(sensor, "async_get_last_state", AsyncMock(return_value=last)),
        ):
            await sensor.async_added_to_hass()
        assert sensor._restored_name is None
        assert sensor._restored_map_id is None

    @pytest.mark.asyncio
    async def test_added_to_hass_without_previous_state(self):
        sensor = self._sensor()
        with (
            patch.object(DysonEntity, "async_added_to_hass", AsyncMock()),
            patch.object(sensor, "async_get_last_state", AsyncMock(return_value=None)),
        ):
            await sensor.async_added_to_hass()
        assert sensor._restored_name is None
        assert sensor._restored_map_id is None

    @pytest.mark.asyncio
    async def test_async_update_metadata_failure_still_warms_clean_history(self):
        """A cloud failure on one cache must not stop warming the other."""
        sensor = self._sensor()
        with (
            patch(
                "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
                AsyncMock(side_effect=HomeAssistantError("cloud down")),
            ),
            patch(
                "custom_components.hass_dyson.sensor.fetch_clean_maps",
                AsyncMock(return_value=[]),
            ) as fetch_cleans,
        ):
            await sensor.async_update()
        fetch_cleans.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_update_clean_history_failure_is_swallowed(self):
        """A clean-history fetch failure must not escape async_update."""
        sensor = self._sensor()
        with (
            patch(
                "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
                AsyncMock(return_value=[]),
            ) as fetch_maps,
            patch(
                "custom_components.hass_dyson.sensor.fetch_clean_maps",
                AsyncMock(side_effect=HomeAssistantError("cloud down")),
            ),
        ):
            await sensor.async_update()
        fetch_maps.assert_awaited_once()


class TestCurrentZoneAttribute:
    """current_zone / traverse_target on the current-map sensor."""

    @staticmethod
    def _sensor_with_zone(zone_id, target=None, session=True):
        coordinator = MagicMock()
        coordinator.serial_number = SERIAL
        coordinator.device = MagicMock()
        coordinator.device.robot_current_map_id = "map-down"
        coordinator.device.robot_zone_status = None
        coordinator.device.robot_state = "FULL_CLEAN_RUNNING"
        coordinator.device.robot_session_active = session
        coordinator.device.robot_current_zone_id = zone_id
        coordinator.device.robot_traverse_target_id = target
        return DysonCurrentMapSensor(coordinator)

    def test_zone_name_resolved_while_active(self):
        sensor = self._sensor_with_zone("3")
        p1, p2 = TestCurrentMapSensor._patched(_maps())
        with p1, p2:
            attrs = sensor.extra_state_attributes
        assert attrs["current_zone"] == "Mud Room"
        assert "traverse_target" not in attrs

    def test_traverse_target_resolved_during_transit(self):
        sensor = self._sensor_with_zone("1", target="3")
        p1, p2 = TestCurrentMapSensor._patched(_maps())
        with p1, p2:
            attrs = sensor.extra_state_attributes
        assert attrs["current_zone"] == "Hallway"
        assert attrs["traverse_target"] == "Mud Room"

    def test_hidden_when_session_closed(self):
        sensor = self._sensor_with_zone("3", session=False)
        sensor.coordinator.device.robot_state = "INACTIVE_CHARGED"
        p1, p2 = TestCurrentMapSensor._patched(_maps())
        with p1, p2:
            attrs = sensor.extra_state_attributes
        assert "current_zone" not in attrs

    def test_unknown_zone_id_passes_through_raw(self):
        sensor = self._sensor_with_zone("99")
        p1, p2 = TestCurrentMapSensor._patched(_maps())
        with p1, p2:
            attrs = sensor.extra_state_attributes
        assert attrs["current_zone"] == "99"
