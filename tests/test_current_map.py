"""Tests for current-map tracking: device MQTT harvest, _effective_current_map,
and the Current Map sensor.

The 360 Vis Nav announces the persistentMapId (and per-zone progress) in its
MQTT state stream during cleans but never via the cloud isCurrentMap flag;
v2/Spot+Clean devices set the cloud flag instead. Both signals are covered.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from libdyson_rest.models import PersistentMapMeta, ZoneMeta

from custom_components.hass_dyson.device import DysonDevice
from custom_components.hass_dyson.sensor import DysonCurrentMapSensor
from custom_components.hass_dyson.services import _effective_current_map

SERIAL = "VS9-GB-HJA0000A"


def _zone(zone_id: str, name: str) -> ZoneMeta:
    return ZoneMeta(id=zone_id, name=name, icon=None, area=None)


def _maps(current: str | None = None) -> list[PersistentMapMeta]:
    return [
        PersistentMapMeta(
            id="map-up",
            name="Upstairs",
            zones_definition_last_updated_date=None,
            zones=[_zone("1", "Hallway"), _zone("2", "Office")],
            is_current_map=current == "map-up",
        ),
        PersistentMapMeta(
            id="map-down",
            name="Downstairs",
            zones_definition_last_updated_date=None,
            zones=[_zone("1", "Hallway"), _zone("3", "Mud Room")],
            is_current_map=current == "map-down",
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


class TestEffectiveCurrentMap:
    """Test the robot-first, cloud-fallback current-map resolution."""

    @staticmethod
    def _coordinator(device_map_id) -> MagicMock:
        coordinator = MagicMock()
        coordinator.device = MagicMock()
        coordinator.device.robot_current_map_id = device_map_id
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
            patch(
                "custom_components.hass_dyson.sensor._clean_maps_cache", clean_cache
            ),
        )

    def test_unique_id_and_name(self):
        sensor = self._sensor()
        assert sensor._attr_unique_id == f"{SERIAL}_current_map"
        assert sensor._attr_name == "Current Map"

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
        sensor = self._sensor(device_map_id=None)
        sensor._restored_map_id = "map-down"
        sensor._restored_name = "Downstairs"
        p1, p2 = self._patched(_maps())
        with p1, p2:
            assert sensor.native_value == "Downstairs"
            assert sensor.extra_state_attributes["source"] == "restored"

    def test_clean_history_fallback(self):
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

    def test_robot_map_id_without_metadata_shows_id(self):
        sensor = self._sensor(device_map_id="map-mystery")
        p1, p2 = self._patched([])
        with p1, p2:
            assert sensor.native_value == "map-mystery"

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
