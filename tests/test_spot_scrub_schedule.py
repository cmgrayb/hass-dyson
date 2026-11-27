"""Spot+Scrub (JDM) robot schedules: sanitized protocol, sync and entities."""

import asyncio
import copy
import hashlib
import json
from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.hass_dyson import (
    spot_scrub_schedule as ss,
    spot_scrub_schedule_entities as se,
)
from custom_components.hass_dyson.services import (
    SERVICE_DELETE_ROBOT_SCHEDULE_SCHEMA,
    SERVICE_SET_ROBOT_SCHEDULE_SCHEMA,
    _handle_delete_robot_schedule,
    _handle_set_robot_schedule,
)

SYDNEY = ZoneInfo("Australia/Sydney")
TOPIC = "RB05/TEST-SERIAL"
_ORIGINAL_OFFSET = ss.current_utc_offset


class FakeStore:
    """In-memory stand-in for homeassistant.helpers.storage.Store."""

    saved: dict = {}

    def __init__(self, hass, version, key):
        self.key = key

    async def async_load(self):
        return copy.deepcopy(FakeStore.saved.get(self.key))

    def async_delay_save(self, data_func, delay=0):
        FakeStore.saved[self.key] = copy.deepcopy(data_func())


class FakeRobot:
    """Keeps orders the way the robot does and answers JDM requests."""

    def __init__(self):
        self.orders = {}
        self.sent = []
        self.reject_delete = False
        self.connected = True
        self.preferences = {
            "prefer_on": 1,
            "room": [
                [1, "Room A", 2, 0, 0, 1, 0, 0, 1, 0, 1, 0],
                [
                    2,
                    '{"type":"hallway","name":"Room B"}',
                    2,
                    3,
                    0,
                    99,
                    0,
                    0,
                    0,
                    0,
                    2,
                    0,
                ],
            ],
            "uv_switch": [[1, 1], [2, 1]],
        }
        self.callbacks = []

    def md5(self):
        listed = [self.orders[key] for key in sorted(self.orders)]
        return hashlib.md5(json.dumps({"order_data": listed}).encode()).hexdigest()

    async def send_jdm_command(self, method, params):
        if not self.connected:
            raise RuntimeError("Spot+Scrub is disconnected")
        self.sent.append((method, copy.deepcopy(params)))
        if method == "service.get_map_list":
            return {"map_list": [{"id": 123, "cur": True}]}
        if method == "service.get_preference":
            return copy.deepcopy(self.preferences)
        if method == ss.ADD_ORDER:
            self.orders[params["id"]] = copy.deepcopy(params)
            return {"result": 0}
        if method == ss.DEL_ORDER:
            if self.reject_delete:
                raise RuntimeError("Spot+Scrub rejected the request")
            self.orders.pop(params["id"], None)
            return {"result": 0}
        assert method == ss.GET_ORDER
        return {"order_data_lite": self.lite()}

    def lite(self):
        return {
            "total": len(self.orders),
            "enable": int(any(o["enable"] for o in self.orders.values())),
            "md5": self.md5(),
            "timestamp": 1794330253,
        }

    def add_message_callback(self, cb):
        self.callbacks.append(cb)

    def remove_message_callback(self, cb):
        self.callbacks.remove(cb)


def app_order(order_id=7171834, enable=1, day=64):
    """add_order params as MyDyson sent them (rooms anonymised)."""
    return {
        "id": order_id,
        "enable": enable,
        "day": day,
        "hour": 10,
        "minute": 0,
        "repeat": 1,
        "map_id": 123,
        "room_count": 2,
        "time_zone": 39600,
        "prefer_type": 1,
        "is_global": 0,
        "areas": [],
        "room_preference": [
            [1, "Room A", 0, 0, 0, 1, 0, 0, 1, 0, 1],
            [2, "Room B", 0, 3, 0, 99, 0, 0, 0, 0, 2],
        ],
        "uv_switch": [[1, enable], [2, enable]],
    }


@pytest.fixture(autouse=True)
def _isolate():
    FakeStore.saved = {}
    with (
        patch.object(ss, "Store", FakeStore),
        patch.object(ss, "ir") as issues,
        patch.object(ss, "async_track_time_interval", return_value=MagicMock()),
        patch.object(ss, "current_utc_offset", return_value=39600),
    ):
        yield issues


@pytest.fixture
def robot():
    return FakeRobot()


@pytest.fixture
def manager(robot):
    hass = MagicMock()
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-SERIAL"
    coordinator.device_name = "Robot"
    coordinator.device = robot
    return ss.SpotScrubScheduleManager(hass, coordinator)


@pytest.fixture
async def live(manager):
    """Manager whose Paho-thread callbacks run on the test loop."""
    manager.hass.loop = asyncio.get_running_loop()
    return manager


async def mqtt(manager, suffix, data):
    """Deliver one MQTT message as the device's callback would, then settle."""
    manager._on_message(f"{TOPIC}/{suffix}", data)
    await asyncio.sleep(0)


async def app_sends(manager, method, params, msg_id="1", result=0, code=0):
    await mqtt(
        manager,
        "command/jdm",
        {"msgId": msg_id, "version": "1.0.1", "method": method, "params": params},
    )
    await mqtt(
        manager,
        "status/jdm",
        {"code": code, "data": {"result": result}, "method": method, "msgId": msg_id},
    )


async def summary(manager, robot, msg_id="9"):
    await mqtt(
        manager,
        "status/jdm",
        {
            "code": 0,
            "data": {"order_data_lite": robot.lite()},
            "method": ss.GET_ORDER,
            "msgId": msg_id,
        },
    )


# ---------------------------------------------------------------------------
# Protocol helpers
# ---------------------------------------------------------------------------


def test_day_mask_round_trip():
    assert ss.days_to_mask(["sun"]) == 64
    assert ss.days_to_mask(["Monday", "wed"]) == 5
    assert ss.mask_to_days(127) == list(ss.DAYS)
    assert ss.mask_to_days(64) == ["sun"]
    for bad in ([], ["funday"]):
        with pytest.raises(ValueError):
            ss.days_to_mask(bad)


@pytest.mark.parametrize(
    "change", [{"id": "1"}, {"enable": 2}, {"day": 0}, {"hour": 24}, {"minute": -1}]
)
def test_validate_order_rejects_unknown_shapes(change):
    with pytest.raises(ValueError):
        ss.validate_order({**app_order(), **change})
    with pytest.raises(ValueError):
        ss.validate_order([])


def test_describe_order():
    assert ss.describe_order(app_order()) == {
        "schedule_id": 7171834,
        "enabled": True,
        "days": ["sun"],
        "time": "10:00",
        "repeat": True,
        "rooms": ["Room A", "Room B"],
    }
    assert ss.room_names({"room_preference": None}) == []


def test_current_utc_offset_is_seconds():
    # The autouse fixture patches the module attribute; test the original.
    offset = ss.SpotScrubScheduleManager.__init__.__globals__["dt_util"]
    with patch.object(
        offset, "now", return_value=datetime(2026, 11, 12, tzinfo=SYDNEY)
    ):
        assert _ORIGINAL_OFFSET() == 39600
    with patch.object(offset, "now", return_value=MagicMock(utcoffset=lambda: None)):
        assert _ORIGINAL_OFFSET() == 0


# ---------------------------------------------------------------------------
# Live sync from MyDyson
# ---------------------------------------------------------------------------


async def test_app_add_is_learned_on_ack(live, robot):
    listener = MagicMock()
    live._listeners.append(listener)
    await mqtt(
        live,
        "command/jdm",
        {"msgId": "5", "method": ss.ADD_ORDER, "params": app_order()},
    )
    assert live.orders == {}
    await mqtt(
        live,
        "status/jdm",
        {"code": 0, "data": {"result": 0}, "method": ss.ADD_ORDER, "msgId": "5"},
    )
    assert live.orders == {7171834: app_order()}
    listener.assert_called_once()
    assert FakeStore.saved["hass_dyson.jdm_schedules.TEST-SERIAL"]["orders"] == [
        app_order()
    ]


@pytest.mark.parametrize("result,code", [(1, 0), (0, 1)])
async def test_rejected_or_unmatched_changes_are_ignored(live, result, code):
    await app_sends(live, ss.ADD_ORDER, app_order(), result=result, code=code)
    await mqtt(
        live,
        "status/jdm",
        {"code": 0, "data": {"result": 0}, "method": ss.ADD_ORDER, "msgId": "x"},
    )
    await app_sends(live, ss.ADD_ORDER, {"id": "bad"})
    assert live.orders == {}


async def test_unrelated_messages_are_ignored(live):
    live.hass.loop = MagicMock()
    live._on_message(f"{TOPIC}/status/current", {"method": ss.ADD_ORDER})
    live._on_message(f"{TOPIC}/command/jdm", {"method": "service.set_preference"})
    live.hass.loop.call_soon_threadsafe.assert_not_called()


async def test_app_toggle_and_delete(live):
    await app_sends(live, ss.ADD_ORDER, app_order())
    await app_sends(live, ss.ADD_ORDER, app_order(enable=0), msg_id="2")
    assert live.orders[7171834]["enable"] == 0
    # The switched-on UV rows are kept for switching on again from HA.
    assert live._uv_on[7171834] == [[1, 1], [2, 1]]
    await app_sends(live, ss.DEL_ORDER, {"id": 7171834}, msg_id="3")
    assert live.orders == {}
    # Deleting something unknown changes nothing.
    await app_sends(live, ss.DEL_ORDER, {"id": 1}, msg_id="4")
    await app_sends(live, ss.DEL_ORDER, {"id": "1"}, msg_id="5")


async def test_expired_pending_requests_are_dropped(live):
    clock = MagicMock()
    with patch.object(ss, "time", clock):
        clock.monotonic.return_value = 0
        live._handle_message(
            f"{TOPIC}/command/jdm", {"msgId": "1", "method": ss.ADD_ORDER}
        )
        assert "1" in live._pending
        clock.monotonic.return_value = ss.PENDING_TTL + 1
        live._handle_message(f"{TOPIC}/status/jdm", {"code": 0, "msgId": "z"})
    assert live._pending == {}


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


async def test_drift_detection(live, robot, _isolate):
    issues = _isolate
    await summary(live, robot)
    assert live.in_sync is True
    issues.async_delete_issue.assert_called()

    # A schedule appears that HA never saw (made while HA was offline).
    robot.orders[1] = app_order(order_id=1)
    await summary(live, robot)
    assert live.in_sync is False
    issues.async_create_issue.assert_called_once()
    assert (
        issues.async_create_issue.call_args.kwargs["translation_placeholders"][
            "robot_total"
        ]
        == "1"
    )

    # Toggling it in MyDyson re-sends it, and HA learns it.
    await app_sends(live, ss.ADD_ORDER, robot.orders[1])
    await summary(live, robot)
    assert live.in_sync is True

    # Same count, different list (edited while HA was offline).
    robot.orders[1] = app_order(order_id=1, day=1)
    await summary(live, robot)
    assert live.in_sync is False

    live._apply_summary({"total": "x"})
    live._apply_summary(None)
    assert live.in_sync is False


# ---------------------------------------------------------------------------
# Writes from Home Assistant
# ---------------------------------------------------------------------------


async def test_create_disabled_schedule(manager, robot):
    order = await manager.async_set_schedule(
        days=["sun"], hour=10, minute=0, enabled=False
    )
    method, params = robot.sent[-2]
    assert method == ss.ADD_ORDER
    assert list(params) == list(ss.ORDER_KEYS)
    assert params == order
    assert params["enable"] == 0
    assert params["day"] == 64
    assert params["time_zone"] == 39600
    assert params["map_id"] == 123
    assert params["room_count"] == 2
    assert params["uv_switch"] == [[1, 0], [2, 0]]
    assert params["room_preference"][1][1] == "Room B"
    assert manager.orders[order["id"]] == params
    assert robot.sent[-1][0] == ss.GET_ORDER
    assert manager.in_sync is True

    # Switching on restores the robot's UV rows.
    on = await manager.async_set_schedule(order["id"], enabled=True)
    assert on["enable"] == 1
    assert on["uv_switch"] == [[1, 1], [2, 1]]
    assert on["room_preference"] == params["room_preference"]


async def test_edit_keeps_unlisted_fields(manager, robot):
    robot.orders[7171834] = app_order()
    manager.orders[7171834] = app_order()
    edited = await manager.async_set_schedule(
        7171834, days=["mon", "fri"], hour=7, minute=30
    )
    assert edited["day"] == 17
    assert (edited["hour"], edited["minute"]) == (7, 30)
    assert edited["enable"] == 1
    assert edited["room_preference"] == app_order()["room_preference"]
    assert not any(m == "service.get_preference" for m, _ in robot.sent)

    # Room changes re-read the robot's rooms.
    edited = await manager.async_set_schedule(
        7171834, room_modes={"Room B": "mop_only"}
    )
    assert edited["room_preference"][1][3] == 2


async def test_enable_without_known_uv_reads_robot(manager, robot):
    manager.orders[5] = app_order(order_id=5, enable=0)
    robot.orders[5] = app_order(order_id=5, enable=0)
    order = await manager.async_set_schedule(5, enabled=True)
    assert order["uv_switch"] == [[1, 1], [2, 1]]
    order = await manager.async_set_schedule(5, enabled=False)
    assert order["uv_switch"] == [[1, 0], [2, 0]]


async def test_invalid_writes(manager, robot):
    with pytest.raises(ss.ScheduleNotFoundError):
        await manager.async_set_schedule(42, enabled=False)
    with pytest.raises(ValueError):
        await manager.async_set_schedule(days=["sun"])
    with pytest.raises(ValueError):
        await manager.async_set_schedule(
            days=["sun"], hour=1, minute=0, room_modes={"Nowhere": "mop_only"}
        )
    with pytest.raises(ss.ScheduleNotFoundError):
        await manager.async_delete_schedule(42)
    manager.coordinator.device = None
    with pytest.raises(RuntimeError):
        await manager.async_set_schedule(days=["sun"], hour=1, minute=0)
    with pytest.raises(RuntimeError):
        await manager.async_delete_schedule(1)
    assert not any(m == ss.ADD_ORDER for m, _ in robot.sent)


async def test_delete(manager, robot):
    order = await manager.async_set_schedule(
        days=["sun"], hour=1, minute=0, enabled=False
    )
    await manager.async_delete_schedule(order["id"])
    assert manager.orders == {} and robot.orders == {}
    assert manager.in_sync is True

    # Already gone from the robot: HA's stale copy is dropped too.
    manager.orders[9] = app_order(order_id=9)
    robot.reject_delete = True
    await manager.async_delete_schedule(9)
    assert manager.orders == {}

    manager.orders[9] = app_order(order_id=9)
    robot.connected = False
    with pytest.raises(RuntimeError):
        await manager.async_delete_schedule(9)
    assert 9 in manager.orders


async def test_poll_failure_and_no_device(manager, robot):
    robot.connected = False
    await manager.async_poll()
    assert manager.robot_summary is None
    manager.coordinator.device = None
    await manager.async_poll()


async def test_store_round_trip(manager, robot):
    order = await manager.async_set_schedule(
        days=["sat"], hour=9, minute=5, enabled=False
    )
    FakeStore.saved["hass_dyson.jdm_schedules.TEST-SERIAL"]["orders"].append(
        {"id": "bad"}
    )
    FakeStore.saved["hass_dyson.jdm_schedules.TEST-SERIAL"]["uv_on"]["x"] = []
    again = ss.SpotScrubScheduleManager(manager.hass, manager.coordinator)
    await again.async_load()
    await again.async_load()
    assert again.orders == {order["id"]: order}
    assert again._uv_on == {order["id"]: [[1, 1], [2, 1]]}
    assert again.in_sync is True
    assert again.robot_summary["total"] == 1


async def test_listener_lifecycle(manager, robot):
    manager.hass.async_create_background_task = MagicMock(
        side_effect=lambda coro, name: coro.close()
    )
    first = manager.async_add_listener(MagicMock())
    second = manager.async_add_listener(MagicMock())
    assert robot.callbacks == [manager._on_message]
    manager.hass.async_create_background_task.assert_called_once()
    first()
    first()
    assert robot.callbacks
    second()
    assert robot.callbacks == []
    assert manager._unsubs == []


def test_one_manager_per_robot(manager):
    coordinator = manager.coordinator
    assert ss.get_schedule_manager(MagicMock(), coordinator) is ss.get_schedule_manager(
        MagicMock(), coordinator
    )


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


def test_calendar_events():
    orders = [app_order(), app_order(order_id=2, enable=0, day=1)]
    start = datetime(2026, 11, 9, tzinfo=SYDNEY)  # Monday
    events = se.expand_orders(
        orders, start, start + timedelta(days=14), "Robot", SYDNEY
    )
    assert [e.start for e in events] == [
        datetime(2026, 11, 15, 10, tzinfo=SYDNEY),
        datetime(2026, 11, 22, 10, tzinfo=SYDNEY),
    ]
    assert events[0].summary == "Robot: room clean"
    assert events[0].end - events[0].start == se.EVENT_LENGTH
    assert "Room A, Room B" in events[0].description
    no_rooms = {**app_order(), "room_preference": []}
    assert (
        "unknown"
        in se.expand_orders([no_rooms], start, start + timedelta(days=7), "R", SYDNEY)[
            0
        ].description
    )


def test_schedule_label():
    assert se.schedule_label(app_order(day=127)) == "10:00 Every day"
    assert se.schedule_label(app_order(day=5)) == "10:00 Mon, Wed"


def _entity(cls, manager, *args):
    entity = cls(manager.coordinator, manager, *args)
    entity.hass = MagicMock()
    entity.entity_id = "x.y"
    entity.async_write_ha_state = MagicMock()
    return entity


async def test_calendar_entity(manager):
    calendar = _entity(se.DysonJdmScheduleCalendar, manager)
    assert calendar.unique_id == "TEST-SERIAL_schedule_calendar"
    assert calendar.event is None
    manager.orders[1] = app_order(order_id=1, day=127)
    with (
        patch.object(
            se.dt_util, "now", return_value=datetime(2026, 11, 12, 11, tzinfo=SYDNEY)
        ),
        patch.object(se.dt_util, "get_default_time_zone", return_value=SYDNEY),
    ):
        assert calendar.event.start == datetime(2026, 11, 13, 10, tzinfo=SYDNEY)
    start = datetime(2026, 11, 9, tzinfo=SYDNEY)
    events = await calendar.async_get_events(None, start, start + timedelta(days=1))
    assert len(events) == 1


async def test_sensor_entity(manager, robot):
    sensor = _entity(se.DysonJdmSchedulesSensor, manager)
    assert sensor.native_value == 0
    await manager.async_set_schedule(days=["sun"], hour=10, minute=0, enabled=False)
    attrs = sensor.extra_state_attributes
    assert sensor.native_value == 1
    assert attrs["schedules"][0]["days"] == ["sun"]
    assert attrs["in_sync"] is True
    assert attrs["robot_total"] == 1
    assert attrs["robot_checksum"] == robot.md5()


async def test_switch_entity(manager, robot):
    order = await manager.async_set_schedule(
        days=["sun"], hour=10, minute=0, enabled=False
    )
    switch = _entity(se.DysonJdmScheduleSwitch, manager, order["id"])
    assert switch.unique_id == f"TEST-SERIAL_jdm_schedule_{order['id']}"
    assert switch.name == "Schedule 10:00 Sun"
    assert switch.is_on is False
    assert switch.extra_state_attributes["time"] == "10:00"
    await switch.async_turn_on()
    assert switch.is_on is True and robot.orders[order["id"]]["enable"] == 1
    await switch.async_turn_off()
    assert switch.is_on is False
    switch._schedules_changed()
    switch.async_write_ha_state.assert_called()

    robot.connected = False
    with pytest.raises(HomeAssistantError):
        await switch.async_turn_on()
    robot.connected = True

    registry = MagicMock()
    with patch.object(se.er, "async_get", return_value=registry):
        await manager.async_delete_schedule(order["id"])
        assert switch.name == "Schedule" and switch.is_on is None
        assert switch.extra_state_attributes == {}
        switch._schedules_changed()
        registry.async_remove.assert_called_once_with("x.y")
        registry.async_get.return_value = None
        switch._schedules_changed()
        switch.hass.async_create_task.assert_called_once()
        switch.hass.async_create_task.call_args.args[0].close()


async def test_entity_registers_with_manager(manager):
    sensor = _entity(se.DysonJdmSchedulesSensor, manager)
    sensor.async_on_remove = MagicMock()
    manager.async_add_listener = MagicMock(return_value="unsub")
    with patch.object(se.DysonEntity, "async_added_to_hass", AsyncMock()):
        await sensor.async_added_to_hass()
    sensor.async_on_remove.assert_called_once_with("unsub")


async def test_switch_setup_adds_new_schedules(manager, robot):
    manager.orders[1] = app_order(order_id=1)
    manager.coordinator.config_entry.entry_id = "entry"
    add = MagicMock()
    unload = MagicMock()
    stale = [
        MagicMock(
            domain="switch",
            unique_id="TEST-SERIAL_jdm_schedule_99",
            entity_id="switch.old",
        ),
        MagicMock(
            domain="switch",
            unique_id="TEST-SERIAL_jdm_schedule_1",
            entity_id="switch.keep",
        ),
        MagicMock(
            domain="sensor",
            unique_id="TEST-SERIAL_jdm_schedules",
            entity_id="sensor.keep",
        ),
    ]
    registry = MagicMock()
    manager.async_add_listener = MagicMock(return_value="unsub")
    with (
        patch.object(se, "get_schedule_manager", return_value=manager),
        patch.object(se.er, "async_get", return_value=registry),
        patch.object(se.er, "async_entries_for_config_entry", return_value=stale),
    ):
        await se.async_setup_schedule_switches(
            MagicMock(), manager.coordinator, add, unload
        )
    registry.async_remove.assert_called_once_with("switch.old")
    assert [e._schedule_id for e in add.call_args.args[0]] == [1]
    unload.assert_called_once_with("unsub")
    add_new = manager.async_add_listener.call_args.args[0]
    add_new()
    assert add.call_count == 1
    manager.orders[2] = app_order(order_id=2)
    add_new()
    assert [e._schedule_id for e in add.call_args.args[0]] == [2]


# ---------------------------------------------------------------------------
# Platforms and services
# ---------------------------------------------------------------------------


def _jdm_coordinator(prefix="RB05"):
    coordinator = MagicMock()
    coordinator.device.mqtt_prefix = prefix
    coordinator.device_category = ["robot"]
    coordinator.device_capabilities = []
    coordinator.config_entry.data = {}
    return coordinator


@pytest.mark.parametrize(
    "prefix,expected", [("RB05", True), ("RB07", True), ("276", False)]
)
def test_platforms(prefix, expected):
    from custom_components.hass_dyson import _get_platforms_for_device

    platforms = _get_platforms_for_device(_jdm_coordinator(prefix))
    assert ("switch" in platforms) is expected
    assert ("calendar" in platforms) is expected


async def test_calendar_platform_uses_robot_schedules():
    from custom_components.hass_dyson import calendar

    coordinator = _jdm_coordinator()
    entry = MagicMock(entry_id="e")
    hass = MagicMock()
    hass.data = {"hass_dyson": {"e": coordinator}}
    add = MagicMock()
    await calendar.async_setup_entry(hass, entry, add)
    assert isinstance(add.call_args.args[0][0], se.DysonJdmScheduleCalendar)


async def test_switch_platform_only_adds_schedule_switches():
    from custom_components.hass_dyson import switch

    coordinator = _jdm_coordinator()
    entry = MagicMock(entry_id="e")
    hass = MagicMock()
    hass.data = {"hass_dyson": {"e": coordinator}}
    with (
        patch(
            "custom_components.hass_dyson.entry_routing.async_route_ble_platform",
            AsyncMock(return_value=None),
        ),
        patch.object(se, "async_setup_schedule_switches", AsyncMock()) as setup,
    ):
        assert await switch.async_setup_entry(hass, entry, MagicMock()) is True
    setup.assert_awaited_once()


def test_service_schemas():
    data = SERVICE_SET_ROBOT_SCHEDULE_SCHEMA(
        {"device_id": "d", "days": ["Monday", "sun"], "time": "07:30", "enabled": "off"}
    )
    assert data["days"] == ["mon", "sun"]
    assert data["time"] == time(7, 30)
    assert data["enabled"] is False
    assert SERVICE_SET_ROBOT_SCHEDULE_SCHEMA({"device_id": "d", "days": "fri"})[
        "days"
    ] == ["fri"]
    with pytest.raises(Exception):
        SERVICE_SET_ROBOT_SCHEDULE_SCHEMA({"device_id": "d", "days": ["someday"]})
    assert (
        SERVICE_DELETE_ROBOT_SCHEDULE_SCHEMA({"device_id": "d", "schedule_id": "7"})[
            "schedule_id"
        ]
        == 7
    )


async def _call(handler, coordinator, manager, **data):
    call = MagicMock()
    call.data = {"device_id": "abc", **data}
    with (
        patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            AsyncMock(return_value=coordinator),
        ),
        patch(
            "custom_components.hass_dyson.services.get_schedule_manager",
            return_value=manager,
        ),
    ):
        return await handler(MagicMock(), call)


async def test_services(manager, robot):
    coordinator = _jdm_coordinator()
    result = await _call(
        _handle_set_robot_schedule,
        coordinator,
        manager,
        days=["sun"],
        time=time(10, 0),
        enabled=False,
    )
    assert result["enabled"] is False and result["time"] == "10:00"
    schedule_id = result["schedule_id"]
    result = await _call(
        _handle_set_robot_schedule,
        coordinator,
        manager,
        schedule_id=schedule_id,
        enabled=True,
    )
    assert result["enabled"] is True
    await _call(
        _handle_delete_robot_schedule, coordinator, manager, schedule_id=schedule_id
    )
    assert robot.orders == {}

    with pytest.raises(ServiceValidationError) as err:
        await _call(_handle_set_robot_schedule, coordinator, manager, schedule_id=1)
    assert err.value.translation_key == "jdm_schedule_unknown"
    with pytest.raises(ServiceValidationError):
        await _call(_handle_set_robot_schedule, coordinator, manager, days=["sun"])
    with pytest.raises(ServiceValidationError):
        await _call(_handle_delete_robot_schedule, coordinator, manager, schedule_id=1)
    robot.connected = False
    with pytest.raises(HomeAssistantError) as err:
        await _call(
            _handle_set_robot_schedule, coordinator, manager, days=["sun"], time=time(1)
        )
    assert err.value.translation_key == "jdm_schedule_failed"


async def test_services_refuse_other_devices(manager):
    with pytest.raises(ServiceValidationError):
        await _call(_handle_set_robot_schedule, None, manager)
    with pytest.raises(ServiceValidationError) as err:
        await _call(
            _handle_delete_robot_schedule,
            _jdm_coordinator("276"),
            manager,
            schedule_id=1,
        )
    assert err.value.translation_key == "jdm_schedule_unsupported"
