"""Zone-name resolution on the clean-history and recommendation sensors.

Zone ids restart from 1 on every persistent map, so DysonLastCleanSensor and
DysonRecommendedCleanSensor must resolve names against the map the record
belongs to before falling back to the other cached maps.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.sensor import (
    DysonLastCleanSensor,
    DysonRecommendedCleanSensor,
)


@pytest.fixture
def mock_robot_coordinator():
    """Create a mock coordinator for a robot vacuum with cloud token."""
    coordinator = MagicMock()
    coordinator.serial_number = "VS9-GB-HJA0000A"
    coordinator.device_name = "Vis Nav"
    coordinator.device = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {"auth_token": "tok"}
    return coordinator


def _zone(zone_id: str, name: str):
    return SimpleNamespace(id=zone_id, name=name)


def _pmap(pmap_id: str, name: str, zones: list):
    return SimpleNamespace(id=pmap_id, name=name, zones=zones)


def _maps():
    """Two maps whose zone id '1' collides with different names."""
    return [
        _pmap("map-up", "Upstairs", [_zone("1", "Hallway"), _zone("2", "Office")]),
        _pmap("map-down", "Downstairs", [_zone("1", "Kitchen")]),
    ]


def _map_cache(maps):
    cache = MagicMock()
    cache.get.return_value = maps
    return cache


def _clean(zone_ids: list[str], map_id: str | None = None):
    """Minimal v2 CleanRecord stand-in."""
    rec = SimpleNamespace(
        clean_id="clean-1",
        start_time_epoch=1752480000,
        clean_duration=42,
        area_cleaned=18.5,
        zones=[SimpleNamespace(id=z, is_selected=True) for z in zone_ids],
        faults=[],
        is_spot_clean=False,
        sequence_number=7,
        start_battery=100,
        end_battery=61,
    )
    if map_id is not None:
        rec.persistent_map_id = map_id
    return rec


class TestLastCleanZoneNames:
    """DysonLastCleanSensor resolves zone names per the clean's own map."""

    async def _update(self, coordinator, clean):
        sensor = DysonLastCleanSensor(coordinator, 0)
        with (
            patch(
                "custom_components.hass_dyson.sensor.fetch_clean_maps",
                new=AsyncMock(return_value=[clean]),
            ),
            patch(
                "custom_components.hass_dyson.services._persistent_map_cache",
                _map_cache(_maps()),
            ),
        ):
            await sensor.async_update()
        return sensor

    @pytest.mark.asyncio
    async def test_zone_names_prefer_the_cleans_own_map(self, mock_robot_coordinator):
        """A colliding zone id resolves on the map the clean ran on."""
        sensor = await self._update(mock_robot_coordinator, _clean(["1"], "map-down"))
        assert sensor._attr_extra_state_attributes["zone_names"] == ["Kitchen"]

    @pytest.mark.asyncio
    async def test_foreign_ids_fall_back_to_other_maps(self, mock_robot_coordinator):
        """Ids the clean's map does not carry resolve from the other maps."""
        sensor = await self._update(
            mock_robot_coordinator, _clean(["1", "2"], "map-down")
        )
        assert sensor._attr_extra_state_attributes["zone_names"] == [
            "Kitchen",
            "Office",
        ]

    @pytest.mark.asyncio
    async def test_record_without_map_id_keeps_api_order(self, mock_robot_coordinator):
        """Pre-multi-map records (no map id) resolve first-map-wins."""
        sensor = await self._update(mock_robot_coordinator, _clean(["1"]))
        assert sensor._attr_extra_state_attributes["zone_names"] == ["Hallway"]


def _pred(zone_id: str, total: float = 10.0):
    dust = SimpleNamespace(
        extra_fine=1.0, fine=2.0, medium=3.0, large=4.0, other=0.5, total=total
    )
    return SimpleNamespace(zone_id=zone_id, dust=dust)


def _rcm(map_id: str, preds: list):
    return SimpleNamespace(persistent_map_id=map_id, zone_predictions=preds)


class TestRecommendedCleanZoneNames:
    """DysonRecommendedCleanSensor resolves names per the recommendation's map."""

    async def _update(self, coordinator, rcms):
        sensor = DysonRecommendedCleanSensor(coordinator)
        with (
            patch(
                "custom_components.hass_dyson.sensor._fetch_recommended_cleans",
                new=AsyncMock(return_value=rcms),
            ),
            patch(
                "custom_components.hass_dyson.services._persistent_map_cache",
                _map_cache(_maps()),
            ),
        ):
            await sensor.async_update()
        return sensor

    @pytest.mark.asyncio
    async def test_names_resolve_against_the_recommendations_own_map(
        self, mock_robot_coordinator
    ):
        """A colliding zone id names from the recommendation's map."""
        sensor = await self._update(
            mock_robot_coordinator, [_rcm("map-down", [_pred("1")])]
        )
        assert sensor._attr_native_value == "Kitchen"
        predictions = sensor._attr_extra_state_attributes["predictions"]
        assert predictions[0]["zone_name"] == "Kitchen"

    @pytest.mark.asyncio
    async def test_unknown_map_falls_back_to_global_names(self, mock_robot_coordinator):
        """A map id missing from the cache falls back to first-map-wins."""
        sensor = await self._update(
            mock_robot_coordinator, [_rcm("map-gone", [_pred("1")])]
        )
        assert sensor._attr_native_value == "Hallway"


class TestLastCleanZoneStitch:
    """Cloud entries for MQTT-initiated cleans carry no zone info — the
    robot's retained cleaningProgramme echo fills the gap (matched on
    cleanId)."""

    async def _update(self, coordinator, clean):
        sensor = DysonLastCleanSensor(coordinator, 0)
        with (
            patch(
                "custom_components.hass_dyson.sensor.fetch_clean_maps",
                new=AsyncMock(return_value=[clean]),
            ),
            patch(
                "custom_components.hass_dyson.services._persistent_map_cache",
                _map_cache(_maps()),
            ),
        ):
            await sensor.async_update()
        return sensor

    @pytest.mark.asyncio
    async def test_matching_clean_id_stitches_zones(self, mock_robot_coordinator):
        clean = _clean([], "map-down")
        mock_robot_coordinator.device.robot_clean_id = "clean-1"
        mock_robot_coordinator.device.robot_last_clean_zones = ["1"]
        sensor = await self._update(mock_robot_coordinator, clean)
        attrs = sensor._attr_extra_state_attributes
        assert attrs["zone_ids"] == ["1"]
        assert attrs["zone_names"] == ["Kitchen"]
        assert attrs["zone_source"] == "device_mqtt"

    @pytest.mark.asyncio
    async def test_mismatched_clean_id_does_not_stitch(self, mock_robot_coordinator):
        clean = _clean([], "map-down")
        mock_robot_coordinator.device.robot_clean_id = "some-older-clean"
        mock_robot_coordinator.device.robot_last_clean_zones = ["1"]
        sensor = await self._update(mock_robot_coordinator, clean)
        attrs = sensor._attr_extra_state_attributes
        assert attrs["zone_ids"] == []
        assert attrs["zone_source"] is None

    @pytest.mark.asyncio
    async def test_cloud_zones_win_over_stitch(self, mock_robot_coordinator):
        clean = _clean(["2"], "map-up")
        mock_robot_coordinator.device.robot_clean_id = "clean-1"
        mock_robot_coordinator.device.robot_last_clean_zones = ["1"]
        sensor = await self._update(mock_robot_coordinator, clean)
        attrs = sensor._attr_extra_state_attributes
        assert attrs["zone_ids"] == ["2"]
        assert attrs["zone_source"] == "cloud"

    @pytest.mark.asyncio
    async def test_no_device_no_stitch(self, mock_robot_coordinator):
        clean = _clean([], "map-down")
        mock_robot_coordinator.device = None
        sensor = await self._update(mock_robot_coordinator, clean)
        assert sensor._attr_extra_state_attributes["zone_ids"] == []


class TestStitchMapHint:
    """Stitched cleans resolve colliding zone ids on the robot's own map."""

    async def _update(self, coordinator, clean):
        sensor = DysonLastCleanSensor(coordinator, 0)
        with (
            patch(
                "custom_components.hass_dyson.sensor.fetch_clean_maps",
                new=AsyncMock(return_value=[clean]),
            ),
            patch(
                "custom_components.hass_dyson.services._persistent_map_cache",
                _map_cache(_maps()),
            ),
        ):
            await sensor.async_update()
        return sensor

    @pytest.mark.asyncio
    async def test_device_map_disambiguates_colliding_zone_id(
        self, mock_robot_coordinator
    ):
        """Record without a map id: the retained MQTT map picks the names."""
        clean = _clean([])  # no persistent_map_id, no zones — MQTT-initiated
        mock_robot_coordinator.device.robot_clean_id = "clean-1"
        mock_robot_coordinator.device.robot_last_clean_zones = ["1"]
        mock_robot_coordinator.device.robot_current_map_id = "map-down"
        sensor = await self._update(mock_robot_coordinator, clean)
        assert sensor._attr_extra_state_attributes["zone_names"] == ["Kitchen"]

    @pytest.mark.asyncio
    async def test_other_map_resolves_its_own_name(self, mock_robot_coordinator):
        clean = _clean([])
        mock_robot_coordinator.device.robot_clean_id = "clean-1"
        mock_robot_coordinator.device.robot_last_clean_zones = ["1"]
        mock_robot_coordinator.device.robot_current_map_id = "map-up"
        sensor = await self._update(mock_robot_coordinator, clean)
        assert sensor._attr_extra_state_attributes["zone_names"] == ["Hallway"]


class TestStitchEmptyZones:
    @pytest.mark.asyncio
    async def test_matching_id_with_empty_zone_list_does_not_stitch(
        self, mock_robot_coordinator
    ):
        """A whole-house MQTT clean retains no programme zones — no stitch."""
        clean = _clean([])
        mock_robot_coordinator.device.robot_clean_id = "clean-1"
        mock_robot_coordinator.device.robot_last_clean_zones = []
        sensor = DysonLastCleanSensor(mock_robot_coordinator, 0)
        with (
            patch(
                "custom_components.hass_dyson.sensor.fetch_clean_maps",
                new=AsyncMock(return_value=[clean]),
            ),
            patch(
                "custom_components.hass_dyson.services._persistent_map_cache",
                _map_cache(_maps()),
            ),
        ):
            await sensor.async_update()
        attrs = sensor._attr_extra_state_attributes
        assert attrs["zone_ids"] == []
        assert attrs["zone_source"] is None
