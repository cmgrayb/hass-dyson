"""Tests for the Dyson calendar platform (calendar.py).

Covers:
- expand_schedule_to_calendar_events helper: groupId deduplication, overnight
  schedules, disabled schedules, no-groupId fallback, day expansion
- DysonScheduleCalendar entity: async_added_to_hass registers timer,
  _async_refresh populates cache and writes state, event property, async_get_events
- async_setup_entry: creates entity for EC devices with auth_token only
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Fixtures (mirrors test_sensor_cloud.py conventions)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_cloud_client():
    client = MagicMock()
    client.get_scheduled_events = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_coordinator(mock_hass, mock_cloud_client):
    coordinator = MagicMock()
    coordinator.hass = mock_hass
    coordinator.serial_number = "TEST-CAL-001"
    coordinator.device_name = "Theater Fan"
    coordinator.device_category = ["ec"]
    coordinator.last_update_success = True
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {
        "auth_token": "test-token",
        "product_type": "438K",
    }

    @asynccontextmanager
    async def _cloud_ctx():
        yield mock_cloud_client

    coordinator.async_cloud_client = MagicMock(side_effect=_cloud_ctx)
    return coordinator


def _make_calendar(coordinator):
    """Instantiate DysonScheduleCalendar with minimal HA plumbing mocked."""
    from custom_components.hass_dyson.calendar import DysonScheduleCalendar

    entity = DysonScheduleCalendar(coordinator)
    entity.hass = coordinator.hass
    entity.async_write_ha_state = MagicMock()
    entity.async_on_remove = MagicMock()
    return entity


def _make_event(
    enabled=True, group_id=1, start_time="08:00:00", days=None, settings=None
):
    """Build a mock ScheduledEvent."""
    ev = MagicMock()
    ev.enabled = enabled
    ev.start_time = start_time
    ev.days = [str(d) for d in (days if days is not None else list(range(7)))]
    ev.raw = {
        "groupId": group_id,
        "startTime": start_time,
        "enabled": enabled,
        "days": days if days is not None else list(range(7)),
        "settings": settings or {"nmod": "ON", "auto": "ON"},
    }
    return ev


def _make_data(events, schedule_enabled=True):
    data = MagicMock()
    data.schedule_enabled = schedule_enabled
    data.events = events
    return data


# ---------------------------------------------------------------------------
# expand_schedule_to_calendar_events
# ---------------------------------------------------------------------------


class TestExpandScheduleToCalendarEvents:
    """Unit tests for the expand_schedule_to_calendar_events helper."""

    def test_returns_empty_when_data_is_none(self):
        from custom_components.hass_dyson.calendar import (
            expand_schedule_to_calendar_events,
        )

        start = datetime(2026, 5, 19, 0, 0, tzinfo=UTC)  # Monday
        result = expand_schedule_to_calendar_events(
            None, start, start + timedelta(days=7)
        )
        assert result == []

    def test_returns_empty_when_schedule_disabled(self):
        from custom_components.hass_dyson.calendar import (
            expand_schedule_to_calendar_events,
        )

        ev = _make_event(enabled=True)
        data = _make_data([ev], schedule_enabled=False)
        start = datetime(2026, 5, 19, 0, 0, tzinfo=UTC)
        result = expand_schedule_to_calendar_events(
            data, start, start + timedelta(days=7)
        )
        assert result == []

    def test_returns_empty_when_no_enabled_events(self):
        from custom_components.hass_dyson.calendar import (
            expand_schedule_to_calendar_events,
        )

        ev = _make_event(enabled=False)
        data = _make_data([ev])
        start = datetime(2026, 5, 19, 0, 0, tzinfo=UTC)
        result = expand_schedule_to_calendar_events(
            data, start, start + timedelta(days=7)
        )
        assert result == []

    def test_single_event_uses_one_hour_default_duration(self):
        from custom_components.hass_dyson.calendar import (
            expand_schedule_to_calendar_events,
        )

        ev = _make_event(
            start_time="09:00:00", days=[1]
        )  # Monday only (Dyson 1=Monday)
        data = _make_data([ev])
        # Range: one specific Monday
        start = datetime(2026, 5, 18, 0, 0, tzinfo=UTC)  # Monday 2026-05-18
        end = datetime(2026, 5, 18, 23, 59, tzinfo=UTC)
        result = expand_schedule_to_calendar_events(data, start, end)
        assert len(result) == 1
        assert result[0].start == datetime(2026, 5, 18, 9, 0, tzinfo=UTC)
        assert result[0].end == datetime(2026, 5, 18, 10, 0, tzinfo=UTC)

    def test_two_events_same_group_id_span_start_to_end(self):
        """Two events in the same group produce one calendar event spanning 01:00–06:00."""
        from custom_components.hass_dyson.calendar import (
            expand_schedule_to_calendar_events,
        )

        ev1 = _make_event(start_time="01:00:00", group_id=1, days=[1])
        ev2 = _make_event(start_time="06:00:00", group_id=1, days=[1])
        data = _make_data([ev1, ev2])
        start = datetime(2026, 5, 18, 0, 0, tzinfo=UTC)
        end = datetime(2026, 5, 18, 23, 59, tzinfo=UTC)
        result = expand_schedule_to_calendar_events(data, start, end)
        assert len(result) == 1
        assert result[0].start == datetime(2026, 5, 18, 1, 0, tzinfo=UTC)
        assert result[0].end == datetime(2026, 5, 18, 6, 0, tzinfo=UTC)

    def test_two_events_sorted_ascending_span_earlier_to_later(self):
        """Groups are sorted ascending by startTime; calendar spans first→last."""
        from custom_components.hass_dyson.calendar import (
            expand_schedule_to_calendar_events,
        )

        # Simulate a case where events arrive out of order
        ev_late = _make_event(start_time="23:00:00", group_id=1, days=[1])
        ev_early = _make_event(start_time="06:00:00", group_id=1, days=[1])
        data = _make_data([ev_late, ev_early])  # intentionally reversed
        start = datetime(2026, 5, 18, 0, 0, tzinfo=UTC)
        end = datetime(2026, 5, 18, 23, 59, tzinfo=UTC)
        result = expand_schedule_to_calendar_events(data, start, end)
        # After ascending sort: first=06:00, last=23:00 → spans 06:00–23:00
        assert len(result) == 1
        assert result[0].start == datetime(2026, 5, 18, 6, 0, tzinfo=UTC)
        assert result[0].end == datetime(2026, 5, 18, 23, 0, tzinfo=UTC)

    def test_two_groups_produce_two_events_per_day(self):
        """Two distinct groupIds each produce their own calendar event."""
        from custom_components.hass_dyson.calendar import (
            expand_schedule_to_calendar_events,
        )

        ev_a = _make_event(start_time="08:00:00", group_id=1, days=[1])
        ev_b = _make_event(start_time="20:00:00", group_id=2, days=[1])
        data = _make_data([ev_a, ev_b])
        start = datetime(2026, 5, 18, 0, 0, tzinfo=UTC)
        end = datetime(2026, 5, 18, 23, 59, tzinfo=UTC)
        result = expand_schedule_to_calendar_events(data, start, end)
        assert len(result) == 2

    def test_events_expand_across_multiple_days_in_range(self):
        """A schedule running every day appears once per day in a 7-day range."""
        from custom_components.hass_dyson.calendar import (
            expand_schedule_to_calendar_events,
        )

        ev = _make_event(start_time="09:00:00", days=list(range(7)))
        data = _make_data([ev])
        start = datetime(2026, 5, 18, 0, 0, tzinfo=UTC)
        end = start + timedelta(days=7)
        result = expand_schedule_to_calendar_events(data, start, end)
        assert len(result) == 7

    def test_events_not_on_unscheduled_days_are_excluded(self):
        """Events only run on their scheduled weekdays."""
        from custom_components.hass_dyson.calendar import (
            expand_schedule_to_calendar_events,
        )

        ev = _make_event(
            start_time="09:00:00", days=[1]
        )  # Monday only (Dyson 1=Monday)
        data = _make_data([ev])
        start = datetime(2026, 5, 18, 0, 0, tzinfo=UTC)  # Monday
        end = start + timedelta(days=7)
        result = expand_schedule_to_calendar_events(data, start, end)
        assert len(result) == 1
        assert result[0].start.weekday() == 0  # Monday

    def test_summary_includes_device_name_and_setting_label(self):
        from custom_components.hass_dyson.calendar import (
            expand_schedule_to_calendar_events,
        )

        ev = _make_event(
            start_time="22:00:00",
            days=[1],
            settings={"nmod": "ON", "auto": "ON"},
        )
        data = _make_data([ev])
        start = datetime(2026, 5, 18, 0, 0, tzinfo=UTC)
        result = expand_schedule_to_calendar_events(
            data, start, start + timedelta(hours=23), device_name="Theater Fan"
        )
        assert result[0].summary == "Theater Fan: Night Mode, Auto"

    def test_no_group_id_events_each_become_own_group(self):
        """Events without groupId each become independent calendar events."""
        from custom_components.hass_dyson.calendar import (
            expand_schedule_to_calendar_events,
        )

        ev1 = MagicMock()
        ev1.enabled = True
        ev1.start_time = "08:00:00"
        ev1.days = ["1"]
        ev1.raw = {"startTime": "08:00:00"}  # no groupId

        ev2 = MagicMock()
        ev2.enabled = True
        ev2.start_time = "20:00:00"
        ev2.days = ["1"]
        ev2.raw = {"startTime": "20:00:00"}  # no groupId

        data = _make_data([ev1, ev2])
        start = datetime(2026, 5, 18, 0, 0, tzinfo=UTC)
        result = expand_schedule_to_calendar_events(
            data, start, start + timedelta(hours=23)
        )
        assert len(result) == 2


# ---------------------------------------------------------------------------
# DysonScheduleCalendar entity
# ---------------------------------------------------------------------------


class TestDysonScheduleCalendar:
    """Tests for the DysonScheduleCalendar entity."""

    @pytest.mark.asyncio
    async def test_async_added_to_hass_registers_timer(self, mock_coordinator):
        """async_added_to_hass registers an async_track_time_interval."""
        entity = _make_calendar(mock_coordinator)

        with (
            patch(
                "custom_components.hass_dyson.calendar.async_track_time_interval",
                return_value=MagicMock(),
            ) as mock_tracker,
            patch.object(entity, "_async_refresh", new_callable=AsyncMock),
        ):
            await entity.async_added_to_hass()

        mock_tracker.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_added_to_hass_does_initial_fetch(self, mock_coordinator):
        """async_added_to_hass performs an initial data fetch."""
        entity = _make_calendar(mock_coordinator)

        with (
            patch(
                "custom_components.hass_dyson.calendar.async_track_time_interval",
                return_value=MagicMock(),
            ),
            patch.object(
                entity, "_async_refresh", new_callable=AsyncMock
            ) as mock_refresh,
        ):
            await entity.async_added_to_hass()

        mock_refresh.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_async_refresh_stores_data_and_writes_state(
        self, mock_coordinator, mock_cloud_client
    ):
        """_async_refresh fetches data, caches it, and calls async_write_ha_state."""

        entity = _make_calendar(mock_coordinator)

        ev = _make_event()
        sched_data = _make_data([ev])
        mock_cloud_client.get_scheduled_events.return_value = sched_data

        with patch(
            "custom_components.hass_dyson.calendar._device_product_type",
            return_value=None,
        ):
            await entity._async_refresh(None)

        assert entity._schedule_data is sched_data
        entity.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_refresh_falls_back_to_stale_on_error(
        self, mock_coordinator, mock_cloud_client
    ):
        """_async_refresh uses stale cache data when the API raises an error."""
        from libdyson_rest.exceptions import DysonAuthError

        from custom_components.hass_dyson.sensor import _schedule_cache

        serial = mock_coordinator.serial_number
        stale_data = _make_data([_make_event()])
        _schedule_cache._store[serial] = (0.0, stale_data)  # expired entry

        mock_cloud_client.get_scheduled_events.side_effect = DysonAuthError("expired")
        entity = _make_calendar(mock_coordinator)

        with patch(
            "custom_components.hass_dyson.calendar._device_product_type",
            return_value=None,
        ):
            await entity._async_refresh(None)

        assert entity._schedule_data is stale_data

    def test_event_property_returns_none_when_no_data(self, mock_coordinator):
        """event property returns None when no schedule data has been fetched."""
        entity = _make_calendar(mock_coordinator)
        assert entity.event is None

    def test_event_property_returns_next_upcoming_event(self, mock_coordinator):
        """event property returns the soonest-starting event in the next 7 days."""

        entity = _make_calendar(mock_coordinator)
        ev = _make_event(start_time="09:00:00", days=list(range(7)))
        entity._schedule_data = _make_data([ev])

        with patch(
            "custom_components.hass_dyson.calendar.dt_util.now",
            return_value=datetime(2026, 5, 18, 8, 0, tzinfo=UTC),
        ):
            result = entity.event

        assert result is not None
        assert result.start.hour == 9

    @pytest.mark.asyncio
    async def test_async_get_events_uses_cache(self, mock_coordinator):
        """async_get_events reads from _schedule_cache without calling the API."""
        from custom_components.hass_dyson.sensor import _schedule_cache

        serial = mock_coordinator.serial_number
        ev = _make_event(start_time="10:00:00", days=[1])  # Monday (Dyson 1=Monday)
        data = _make_data([ev])
        _schedule_cache.set(serial, data)

        entity = _make_calendar(mock_coordinator)
        start = datetime(2026, 5, 18, 0, 0, tzinfo=UTC)  # Monday
        end = start + timedelta(hours=23)

        result = await entity.async_get_events(mock_coordinator.hass, start, end)

        assert len(result) == 1
        assert result[0].start.hour == 10

    @pytest.mark.asyncio
    async def test_async_get_events_returns_empty_when_no_data(self, mock_coordinator):
        """async_get_events returns [] when neither cache nor fallback has data."""
        from custom_components.hass_dyson.sensor import _schedule_cache

        _schedule_cache.invalidate(mock_coordinator.serial_number)
        entity = _make_calendar(mock_coordinator)
        entity._schedule_data = None

        start = datetime(2026, 5, 18, 0, 0, tzinfo=UTC)
        result = await entity.async_get_events(
            mock_coordinator.hass, start, start + timedelta(days=7)
        )
        assert result == []


# ---------------------------------------------------------------------------
# async_setup_entry
# ---------------------------------------------------------------------------


class TestCalendarSetupEntry:
    """Tests for async_setup_entry platform wiring."""

    @pytest.mark.asyncio
    async def test_setup_entry_adds_entity_for_ec_with_auth(self):
        """Entity is created for EC devices that have an auth_token."""
        from custom_components.hass_dyson.calendar import async_setup_entry
        from custom_components.hass_dyson.const import DOMAIN

        coordinator = MagicMock()
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "EC-001"
        coordinator.device_name = "Fan"
        coordinator.config_entry = MagicMock()
        coordinator.config_entry.data = {"auth_token": "tok"}

        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "eid"
        hass.data = {DOMAIN: {"eid": coordinator}}

        add_entities = MagicMock()
        await async_setup_entry(hass, config_entry, add_entities)

        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        assert len(entities) == 1

    @pytest.mark.asyncio
    async def test_setup_entry_skips_entity_without_auth(self):
        """No entity is created for devices without an auth_token."""
        from custom_components.hass_dyson.calendar import async_setup_entry
        from custom_components.hass_dyson.const import DOMAIN

        coordinator = MagicMock()
        coordinator.device_category = ["ec"]
        coordinator.config_entry = MagicMock()
        coordinator.config_entry.data = {}  # no auth_token

        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "eid"
        hass.data = {DOMAIN: {"eid": coordinator}}

        add_entities = MagicMock()
        await async_setup_entry(hass, config_entry, add_entities)

        add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_setup_entry_skips_non_ec_devices(self):
        """No entity is created for non-EC devices (e.g. robot vacuums)."""
        from custom_components.hass_dyson.calendar import async_setup_entry
        from custom_components.hass_dyson.const import DOMAIN

        coordinator = MagicMock()
        coordinator.device_category = ["robot"]
        coordinator.config_entry = MagicMock()
        coordinator.config_entry.data = {"auth_token": "tok"}

        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "eid"
        hass.data = {DOMAIN: {"eid": coordinator}}

        add_entities = MagicMock()
        await async_setup_entry(hass, config_entry, add_entities)

        add_entities.assert_not_called()
