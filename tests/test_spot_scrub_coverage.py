"""Spot+Scrub live position and clean coverage; no hardware or credentials."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from custom_components.hass_dyson import spot_scrub_coverage as coverage
from custom_components.hass_dyson.device import DysonDevice
from custom_components.hass_dyson.image import DysonCleanCoverageImage
from custom_components.hass_dyson.sensor import DysonRobotCurrentRoomSensor
from custom_components.hass_dyson.spot_scrub_coverage import (
    MOP,
    VACUUM,
    CoverageRecorder,
    parse_cur_path,
    parse_geometry,
    parse_global_position,
    render_coverage_png,
    zone_at,
)


def _square(x0, y0, x1, y1):
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return [
        {
            "start": {"x": ax, "y": ay},
            "end": {"x": bx, "y": by},
            "type": 0,
        }
        for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1])
    ]


# Shaped like GET /v2/{serial}/clean-maps-data/{cleanId}
CLEAN_MAP_DATA = {
    "orientation": 90,
    "dockLocation": {"x": 0.2, "y": 0.2, "angle": 0},
    "zones": [
        {
            "id": "10",
            "name": "Kitchen",
            "nameLocation": {"x": 2, "y": 1.5},
            "presentation": _square(0, 0, 4, 3),
            "cleanStatus": "CLEAN_COMPLETE",
        },
        {
            "id": "11",
            "name": "Bedroom",
            "nameLocation": {"x": 6, "y": 2.5},
            "presentation": _square(4, 0, 8, 5),
        },
        "not a zone",
    ],
    "cleanPath": [{"x": 1, "y": 1, "update": 1}, {"x": 1.1, "y": 1, "update": 0}],
}


@pytest.fixture
def geometry():
    return parse_geometry(CLEAN_MAP_DATA)


@pytest.fixture
def recorder(geometry):
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-SERIAL"
    coordinator.device.robot_full_clean_action = "VACUUMING_AND_MOPPING"
    with patch.object(coverage, "Store"):
        rec = CoverageRecorder(MagicMock(), coordinator)
    rec.geometry = geometry
    return rec


def test_parse_cur_path_batch():
    """First id, then x/y/angle/update per point, then a timestamp."""
    batch = [1210, 1.0, 0.1, -1.5, 3, 1.1, 0.2, -1.6, 0, 1792793330]

    assert parse_cur_path(batch) == [
        (1210, 1.0, 0.1, -1.5, 3),
        (1211, 1.1, 0.2, -1.6, 0),
    ]


@pytest.mark.parametrize(
    "value", [None, [], [1, 2, 3], [1, 1.0, 0.1, -1.5, 3], [1, "x", 1, 1, 1, 9]]
)
def test_parse_cur_path_rejects_other_shapes(value):
    assert parse_cur_path(value) == []


def test_parse_global_position_uses_latest_point():
    value = [
        {"id": 1, "x": 0, "y": 0, "angle": 0, "update": 0},
        {"id": 171, "x": 3.05, "y": 2.85, "angle": -0.43, "update": 3},
    ]

    assert parse_global_position(value) == (171, 3.05, 2.85, -0.43, 3)
    assert parse_global_position([1250, 800]) is None
    assert parse_global_position([{"id": 1}]) is None


def test_device_position_accepts_spot_scrub_points():
    """RB05 reports a list of points in metres, not an [x, y] pair."""
    device = DysonDevice(
        MagicMock(), "TEST-SERIAL", "192.0.2.1", "test", mqtt_prefix="RB05"
    )
    device._state_data = {
        "globalPosition": [
            {"id": 171, "x": 3.056798, "y": 2.855042, "angle": -0.4, "update": 3}
        ]
    }

    assert device.robot_global_position == [3.057, 2.855]

    device._state_data = {"globalPosition": [1250, 800]}
    assert device.robot_global_position == [1250, 800]


def test_parse_geometry(geometry):
    assert [zone["name"] for zone in geometry["zones"]] == ["Kitchen", "Bedroom"]
    assert geometry["dock"] == (0.2, 0.2)
    assert geometry["orientation"] == 90
    assert geometry["clean_path"] == [(1.0, 1.0, 1), (1.1, 1.0, 0)]
    assert parse_geometry({"zones": []}) is None
    assert parse_geometry("nope") is None


def test_zone_at(geometry):
    assert zone_at(geometry, 1, 1)["name"] == "Kitchen"
    assert zone_at(geometry, 6, 4)["id"] == "11"
    assert zone_at(geometry, 2, 4) is None
    assert zone_at(None, 1, 1) is None


def test_path_points_are_tagged_with_the_action(recorder):
    """Working points carry the run's action; travel points carry none."""
    recorder.ingest(
        {
            "method": "prop.post",
            "params": {"cur_path": [5, 1.0, 1.0, 0, 3, 1.1, 1.0, 0, 0, 99]},
        }
    )
    recorder.coordinator.device.robot_full_clean_action = "VACUUMING"
    recorder.ingest(
        {"method": "prop.post", "params": {"cur_path": [7, 6.0, 4.0, 1.5, 1, 99]}}
    )

    assert [p[4] for p in recorder.points] == [3, 0, VACUUM]
    assert recorder.pose == {
        "x": 6.0,
        "y": 4.0,
        "angle": 1.5,
        "room_id": "11",
        "room": "Bedroom",
    }
    recorder._store.async_delay_save.assert_called()


def test_update_flag_says_what_was_done(recorder):
    """1 vacuum, 2 mop, 3 both; other values fall back to the run's action."""
    recorder.coordinator.device.robot_full_clean_action = "VACUUMING_AND_MOPPING"
    recorder.add_points(
        [(1, 1, 1, 0, 1), (2, 1, 1, 0, 2), (3, 1, 1, 0, 3), (4, 1, 1, 0, 4)],
        recorder._current_bits(),
    )

    assert [p[4] for p in recorder.points] == [VACUUM, MOP, 3, 3]


def test_repeated_and_new_runs(recorder):
    recorder.add_points([(100, 1, 1, 0, 1), (101, 1.1, 1, 0, 1)], MOP)
    revision = recorder.revision
    recorder.add_points([(101, 1.1, 1, 0, 1)], MOP)
    assert len(recorder.points) == 2
    assert recorder.revision == revision

    # Point ids restart at each clean.
    recorder.add_points([(0, 2, 2, 0, 1)], VACUUM)
    assert [p[0] for p in recorder.points] == [0]

    recorder.ingest({"method": "event.startClean.post", "params": {}})
    assert recorder.points == []


def test_state_messages_only_move_the_marker(recorder):
    recorder.ingest(
        {
            "msg": "CURRENT-STATE",
            "globalPosition": [{"id": 9, "x": 1, "y": 1, "angle": 0, "update": 3}],
        }
    )

    assert recorder.points == []
    assert recorder.pose["room"] == "Kitchen"


def test_path_falls_back_to_the_cloud(recorder):
    assert recorder.path() == ("cloud", [(1.0, 1.0, 0, 1), (1.1, 1.0, 1, 0)])

    recorder.add_points([(1, 1, 1, 0, 1)], MOP)
    assert recorder.path() == ("live", [(1, 1, 1, VACUUM)])


async def test_start_loads_saved_run_and_follows_messages(recorder):
    recorder._store.async_load = AsyncMock(
        return_value={"points": [[4, 1, 1, 1, 1]], "started": 1.0, "updated": 2.0}
    )
    device = recorder.coordinator.device

    await recorder.async_start()
    await recorder.async_start()

    assert recorder.points == [[4, 1, 1, 1, 1]]
    assert recorder._last_id == 4
    device.add_message_callback.assert_called_once_with(recorder._on_message)
    recorder.async_stop()
    device.remove_message_callback.assert_called_once_with(recorder._on_message)


def test_render_coverage_png(geometry):
    path = [(0.5 + i * 0.05, 1.0, i, 3) for i in range(40)]
    path += [(4.5 + i * 0.05, 2.0, 40 + i, VACUUM) for i in range(40)]

    png, areas = render_coverage_png(geometry, path, {"x": 6, "y": 4}, "footer")

    image = Image.open(io.BytesIO(png))
    assert image.format == "PNG"
    assert image.width > image.height
    assert areas["vacuumed"] > areas["mopped"] > 0


def test_render_needs_room_outlines():
    assert render_coverage_png({"zones": []}, []) is None


async def test_coverage_image_renders_and_caches(recorder, geometry):
    recorder.async_refresh_geometry = AsyncMock(return_value=False)
    recorder.geometry_clean_id = "clean-1"
    recorder.add_points([(1, 1, 1, 0, 1), (2, 1.1, 1, 0, 1)], VACUUM)
    coordinator = recorder.coordinator
    coordinator.device.robot_state = "FULL_CLEAN_RUNNING"
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func: func())
    with (
        patch(
            "custom_components.hass_dyson.image.ImageEntity.__init__",
            return_value=None,
        ),
        patch(
            "custom_components.hass_dyson.image.DysonEntity.__init__",
            return_value=None,
        ),
    ):
        entity = DysonCleanCoverageImage(hass, coordinator, recorder)
    entity.hass = hass
    entity.coordinator = coordinator

    first = await entity.async_image()
    second = await entity.async_image()

    assert first and first == second
    assert hass.async_add_executor_job.await_count == 1
    attributes = entity.extra_state_attributes
    assert attributes["source"] == "live"
    assert attributes["vacuumed_m2"] > 0
    assert attributes["mopped_m2"] == 0
    assert attributes["map_clean_id"] == "clean-1"
    assert attributes["map_dock"] == (0.2, 0.2)
    assert attributes["map_bounds"] == [0.0, 8.0, 0.0, 5.0]


async def test_coverage_image_without_geometry(recorder):
    recorder.geometry = None
    recorder.async_refresh_geometry = AsyncMock(return_value=False)
    with (
        patch(
            "custom_components.hass_dyson.image.ImageEntity.__init__",
            return_value=None,
        ),
        patch(
            "custom_components.hass_dyson.image.DysonEntity.__init__",
            return_value=None,
        ),
    ):
        entity = DysonCleanCoverageImage(MagicMock(), recorder.coordinator, recorder)
    entity.coordinator = recorder.coordinator

    assert await entity.async_image() is None


def test_current_room_sensor(pure_mock_sensor_entity, recorder):
    coordinator = recorder.coordinator
    with patch(
        "custom_components.hass_dyson.sensor.get_coverage_recorder",
        return_value=recorder,
    ):
        sensor = pure_mock_sensor_entity(DysonRobotCurrentRoomSensor, coordinator)

    recorder.add_points([(1, 6.0, 4.0, 0.5, 1)], VACUUM)
    sensor._handle_coordinator_update()
    assert sensor.native_value == "Bedroom"
    assert sensor.extra_state_attributes == {
        "x": 6.0,
        "y": 4.0,
        "angle": 0.5,
        "room_id": "11",
    }

    # Before any path point, the device's reported position is used.
    recorder.pose = None
    coordinator.device.robot_global_position = [1.0, 1.0]
    sensor._handle_coordinator_update()
    assert sensor.native_value == "Kitchen"
