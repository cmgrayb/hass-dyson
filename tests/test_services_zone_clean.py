"""Tests for multi-map zone-clean map selection and the zone services.

Covers _select_map / _zone_in_map (issue #398: named identification instead
of maps[0]) and the start_zone_clean / set_zone_behaviour handlers against a
two-map Vis Nav topology where zone ids restart from 1 on each map and zone
names repeat across maps.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import ServiceValidationError
from libdyson_rest.models import PersistentMapMeta, ZoneMeta

from custom_components.hass_dyson.services import (
    _handle_set_zone_behaviour,
    _handle_start_zone_clean,
    _select_map,
    _zone_in_map,
)

SERIAL = "VS9-GB-HJA0000A"


def _zone(zone_id: str, name: str) -> ZoneMeta:
    return ZoneMeta(id=zone_id, name=name, icon=None, area=None)


def _two_maps(current: str | None = None) -> list[PersistentMapMeta]:
    """Upstairs/Downstairs with colliding zone ids and duplicate zone names."""
    return [
        PersistentMapMeta(
            id="map-up",
            name="Upstairs",
            zones_definition_last_updated_date="2026-03-23T07:02:59Z",
            zones=[
                _zone("1", "Hallway"),
                _zone("2", "Living room"),
                _zone("3", "Office"),
            ],
            is_current_map=current == "map-up",
        ),
        PersistentMapMeta(
            id="map-down",
            name="Downstairs",
            zones_definition_last_updated_date="2026-07-10T14:09:15Z",
            zones=[
                _zone("1", "Hallway"),
                _zone("2", "Living room"),
                _zone("5", "Kitchen"),
            ],
            is_current_map=current == "map-down",
        ),
    ]


class TestZoneInMap:
    """Test _zone_in_map resolution order."""

    def test_id_match_wins_over_name(self):
        pmap = _two_maps()[0]
        assert _zone_in_map(pmap, "2").id == "2"

    def test_name_match_case_insensitive(self):
        pmap = _two_maps()[0]
        assert _zone_in_map(pmap, "living ROOM").id == "2"

    def test_no_match_returns_none(self):
        pmap = _two_maps()[0]
        assert _zone_in_map(pmap, "Kitchen") is None


class TestSelectMap:
    """Test _select_map precedence (never positional)."""

    def test_explicit_map_id(self):
        maps = _two_maps()
        assert _select_map(maps, "map-down", ["1"]).id == "map-down"

    def test_explicit_map_name_case_insensitive(self):
        maps = _two_maps()
        assert _select_map(maps, "downstairs", ["1"]).id == "map-down"

    def test_unknown_map_raises_with_known_names(self):
        maps = _two_maps()
        with pytest.raises(ServiceValidationError, match="Unknown map 'Basement'"):
            _select_map(maps, "Basement", ["1"])

    def test_ambiguous_map_name_raises_with_ids(self):
        maps = _two_maps()
        maps[1].name = "Upstairs"
        with pytest.raises(ServiceValidationError, match="ambiguous"):
            _select_map(maps, "Upstairs", ["1"])

    def test_current_map_preferred(self):
        maps = _two_maps(current="map-down")
        assert _select_map(maps, None, ["Hallway"]).id == "map-down"

    def test_caller_resolved_current_map_wins(self):
        # The robot's MQTT-derived map (resolved by the caller via
        # _effective_current_map) short-circuits without any cloud flag.
        maps = _two_maps()
        pmap = _select_map(maps, None, ["Hallway"], current_map=maps[1])
        assert pmap.id == "map-down"

    def test_current_map_wins_over_zone_inference(self):
        # "Office" only exists Upstairs, but the robot is on Downstairs —
        # physical cleans must target the map the robot is on.
        maps = _two_maps(current="map-down")
        assert _select_map(maps, None, ["Office"]).id == "map-down"

    def test_single_map_selected(self):
        maps = [_two_maps()[1]]
        assert _select_map(maps, None, ["Kitchen"]).id == "map-down"

    def test_zone_inference_unique(self):
        # No currency info (v1 API omits isCurrentMap): "Kitchen" is
        # Downstairs-only, so the map is inferred.
        maps = _two_maps()
        assert _select_map(maps, None, ["Kitchen"]).id == "map-down"

    def test_zone_inference_no_single_map_raises(self):
        maps = _two_maps()
        with pytest.raises(
            ServiceValidationError, match="do not all belong to a single map"
        ):
            _select_map(maps, None, ["Kitchen", "Office"])

    def test_zone_inference_ambiguous_raises(self):
        maps = _two_maps()
        with pytest.raises(ServiceValidationError, match="more than one map"):
            _select_map(maps, None, ["Hallway"])

    def test_prefer_current_false_zone_inference_wins(self):
        # Cloud-only ops (zone behaviours) are valid for any map — a zone
        # unique to the non-current map resolves there.
        maps = _two_maps(current="map-up")
        pmap = _select_map(maps, None, ["Kitchen"], prefer_current=False)
        assert pmap.id == "map-down"

    def test_prefer_current_false_ambiguity_falls_back_to_current(self):
        maps = _two_maps(current="map-up")
        pmap = _select_map(maps, None, ["Hallway"], prefer_current=False)
        assert pmap.id == "map-up"


def _make_coordinator() -> MagicMock:
    coordinator = MagicMock()
    coordinator.serial_number = SERIAL
    coordinator.device = MagicMock()
    coordinator.device.robot_start_clean = AsyncMock()
    return coordinator


def _call(data: dict) -> MagicMock:
    call = MagicMock()
    call.data = data
    return call


class TestStartZoneCleanService:
    """Test _handle_start_zone_clean with multi-map metadata."""

    async def _run(self, coordinator, maps, data):
        with (
            patch(
                "custom_components.hass_dyson.services._get_coordinator_from_device_id",
                AsyncMock(return_value=coordinator),
            ),
            patch(
                "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
                AsyncMock(return_value=maps),
            ),
        ):
            await _handle_start_zone_clean(MagicMock(), _call(data))

    @pytest.mark.asyncio
    async def test_zone_unique_to_second_map_is_cleanable(self):
        """A Downstairs-only zone starts a clean on the Downstairs map."""
        coordinator = _make_coordinator()
        await self._run(
            coordinator,
            _two_maps(),
            {"device_id": "dev", "zones": ["Kitchen"]},
        )

        programme = coordinator.device.robot_start_clean.call_args.kwargs[
            "cleaning_programme"
        ]
        assert programme["persistentMapId"] == "map-down"
        assert programme["unorderedZones"] == ["5"]
        assert programme["zonesDefinitionLastUpdatedDate"] == "2026-07-10T14:09:15Z"

    @pytest.mark.asyncio
    async def test_explicit_map_targets_that_map(self):
        """map: Downstairs resolves duplicate zone names on that map."""
        coordinator = _make_coordinator()
        await self._run(
            coordinator,
            _two_maps(),
            {"device_id": "dev", "zones": ["Living room"], "map": "Downstairs"},
        )

        programme = coordinator.device.robot_start_clean.call_args.kwargs[
            "cleaning_programme"
        ]
        assert programme["persistentMapId"] == "map-down"
        assert programme["unorderedZones"] == ["2"]

    @pytest.mark.asyncio
    async def test_current_map_used_when_flagged(self):
        """isCurrentMap=true selects the map without an explicit request."""
        coordinator = _make_coordinator()
        await self._run(
            coordinator,
            _two_maps(current="map-up"),
            {"device_id": "dev", "zones": ["Hallway", "Office"]},
        )

        programme = coordinator.device.robot_start_clean.call_args.kwargs[
            "cleaning_programme"
        ]
        assert programme["persistentMapId"] == "map-up"
        assert programme["unorderedZones"] == ["1", "3"]

    @pytest.mark.asyncio
    async def test_unknown_zone_error_hints_at_other_map(self):
        """A zone on the non-selected map is named in the error hint."""
        coordinator = _make_coordinator()
        with pytest.raises(ServiceValidationError, match="is on map"):
            await self._run(
                coordinator,
                _two_maps(current="map-up"),
                {"device_id": "dev", "zones": ["Kitchen"]},
            )
        coordinator.device.robot_start_clean.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_zone_name_without_map_or_currency_raises(self):
        """Ambiguous zone names demand an explicit map when currency is unknown."""
        coordinator = _make_coordinator()
        with pytest.raises(ServiceValidationError, match="more than one map"):
            await self._run(
                coordinator,
                _two_maps(),
                {"device_id": "dev", "zones": ["Living room"]},
            )
        coordinator.device.robot_start_clean.assert_not_called()


class TestSetZoneBehaviourService:
    """Test _handle_set_zone_behaviour map selection (cloud-only op)."""

    async def _run(self, coordinator, maps, data):
        with (
            patch(
                "custom_components.hass_dyson.services._get_coordinator_from_device_id",
                AsyncMock(return_value=coordinator),
            ),
            patch(
                "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
                AsyncMock(return_value=maps),
            ),
        ):
            await _handle_set_zone_behaviour(MagicMock(), _call(data))

    @staticmethod
    def _with_cloud_client(coordinator) -> MagicMock:
        client = MagicMock()
        client.set_zone_behaviour = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=False)
        coordinator.async_cloud_client.return_value = cm
        return client

    @pytest.mark.asyncio
    async def test_zone_on_non_current_map_is_settable(self):
        """Zone behaviours are cloud state — currency must not block them."""
        coordinator = _make_coordinator()
        client = self._with_cloud_client(coordinator)
        await self._run(
            coordinator,
            _two_maps(current="map-up"),
            {"device_id": "dev", "zone": "Kitchen", "cleaning_strategy": "boost"},
        )

        client.set_zone_behaviour.assert_awaited_once_with(
            SERIAL, "map-down", "5", "boost"
        )

    @pytest.mark.asyncio
    async def test_ambiguous_zone_without_currency_raises(self):
        coordinator = _make_coordinator()
        self._with_cloud_client(coordinator)
        with pytest.raises(ServiceValidationError, match="more than one map"):
            await self._run(
                coordinator,
                _two_maps(),
                {"device_id": "dev", "zone": "Hallway", "cleaning_strategy": "auto"},
            )
