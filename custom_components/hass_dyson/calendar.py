"""Calendar platform for Dyson integration.

Exposes each enabled Dyson schedule group as a weekly recurring
:class:`~homeassistant.components.calendar.CalendarEvent`.  The entity
shares the TTL cache maintained by :mod:`.sensor` so that the scheduler
cloud endpoint is not queried more than once per 5-minute window.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity
from .sensor import _device_product_type, _schedule_cache

_LOGGER = logging.getLogger(__name__)

_UPDATE_INTERVAL = timedelta(minutes=5)

# Day names indexed by Python weekday (0 = Monday … 6 = Sunday)
_DAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dyson calendar entities from a config entry."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    device_category: list[str] = coordinator.device_category
    _CALENDAR_CATEGORIES: set[str] = {"ec", "robot", "vacuum", "flrc"}
    if any(
        cat in _CALENDAR_CATEGORIES for cat in device_category
    ) and coordinator.config_entry.data.get("auth_token"):
        async_add_entities([DysonScheduleCalendar(coordinator)])


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _parse_hhmm(time_str: str | None) -> time | None:
    """Parse an ``HH:MM`` or ``HH:MM:SS`` string into a :class:`datetime.time`."""
    if not time_str:
        return None
    try:
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None


def _describe_settings(settings: dict[str, Any]) -> str:
    """Return a short human-readable label derived from Dyson device settings."""
    if not settings:
        return ""
    parts: list[str] = []
    if settings.get("nmod") == "ON":
        parts.append("Night Mode")
    if settings.get("auto") == "ON":
        parts.append("Auto")
    speed = settings.get("fnsp")
    if speed and speed != "AUTO":
        parts.append(f"Speed {speed}")
    if settings.get("oson") == "ON":
        parts.append("Oscillating")
    return ", ".join(parts)


def _group_events(events: list[Any]) -> list[list[Any]]:
    """Group ``ScheduledEvent`` objects by ``groupId``, sorted by ``start_time``.

    Events without a ``groupId`` each become their own singleton group.
    Returns a list of groups; each group is a list of events in ascending
    ``startTime`` order.
    """
    buckets: dict[Any, list[Any]] = {}
    ungrouped: list[list[Any]] = []
    for event in events:
        gid = event.raw.get("groupId")
        if gid is None:
            ungrouped.append([event])
        else:
            buckets.setdefault(gid, []).append(event)

    groups = list(buckets.values()) + ungrouped
    for group in groups:
        group.sort(key=lambda e: e.start_time or "")
    return groups


def expand_schedule_to_calendar_events(
    data: Any,
    range_start: datetime,
    range_end: datetime,
    device_name: str = "Dyson",
    local_tz: dt_util.dt.tzinfo | None = None,
) -> list[CalendarEvent]:
    """Expand :class:`~libdyson_rest.models.ScheduledEventsData` into a list of
    :class:`~homeassistant.components.calendar.CalendarEvent` instances for
    the given date range.

    Each enabled schedule group is turned into weekly recurring events.
    The **start** of each calendar event is the group's earliest ``startTime``;
    the **end** is the group's latest ``startTime`` (or start + 1 hour when the
    group has only a single event).  Overnight schedules (end < start) are
    handled by advancing the end date by one day.

    Args:
        data: A ``ScheduledEventsData`` instance (or ``None``).
        range_start: Inclusive start of the requested date range (timezone-aware).
        range_end: Inclusive end of the requested date range (timezone-aware).
        device_name: Human-readable device name used in event summaries.
        local_tz: The local timezone to interpret schedule times in.  Dyson
            schedule times are in local time, so passing ``hass``'s timezone
            ensures events appear at the correct hour in the HA calendar.

    Returns:
        A list of ``CalendarEvent`` objects that overlap with the range.
    """
    if not data or not data.schedule_enabled:
        return []

    # Schedule times from Dyson are in the device's local time.  Use the
    # caller-supplied local timezone (from hass.config) so events land on
    # the correct hour in the HA calendar.  Fall back to the HA default
    # timezone when not supplied, and only use range_start.tzinfo (UTC) as
    # a last resort.
    tz: dt_util.dt.tzinfo = (
        local_tz or dt_util.get_default_time_zone() or range_start.tzinfo or dt_util.UTC
    )
    active = [e for e in data.events if e.enabled]
    groups = _group_events(active)
    cal_events: list[CalendarEvent] = []

    for group_idx, group in enumerate(groups, start=1):
        first = group[0]
        last = group[-1]

        start_t = _parse_hhmm(first.start_time)
        end_t = _parse_hhmm(last.start_time) if len(group) > 1 else None

        if start_t is None:
            continue

        # Collect weekdays (Python 0=Mon … 6=Sun).
        # Dyson API uses 0=Sunday (JS convention), so convert:
        #   python_weekday = (dyson_day - 1) % 7
        weekdays: set[int] = set()
        for ev in group:
            for d in ev.days:
                try:
                    weekdays.add((int(d) - 1) % 7)
                except (ValueError, TypeError):
                    pass
        if not weekdays:
            weekdays = set(range(7))

        # Build human-readable summary / description
        first_settings = first.raw.get("settings") or {}
        label = _describe_settings(first_settings) or f"Schedule {group_idx}"
        summary = f"{device_name}: {label}"

        desc_lines: list[str] = [
            f"Group {first.raw.get('groupId', group_idx)}",
        ]
        for ev in group:
            t = ev.start_time or "?"
            s = _describe_settings(ev.raw.get("settings") or {}) or "—"
            desc_lines.append(f"  {t}: {s}")
        days_label = ", ".join(
            _DAY_NAMES[d] for d in sorted(weekdays) if d < len(_DAY_NAMES)
        )
        desc_lines.append(f"Days: {days_label}")
        description = "\n".join(desc_lines)

        # Expand recurring occurrences within the requested range.
        # Walk dates in the local timezone to avoid boundary edge cases.
        local_start = range_start.astimezone(tz)
        local_end = range_end.astimezone(tz)
        current_date = local_start.date()
        while current_date <= local_end.date():
            if current_date.weekday() in weekdays:
                ev_start = datetime.combine(current_date, start_t, tzinfo=tz)
                if end_t and end_t != start_t:
                    ev_end = datetime.combine(current_date, end_t, tzinfo=tz)
                    if ev_end <= ev_start:
                        # Overnight: schedule ends the following day
                        ev_end += timedelta(days=1)
                else:
                    ev_end = ev_start + timedelta(hours=1)

                # Include only events that overlap with the requested range
                if ev_end > range_start and ev_start < range_end:
                    cal_events.append(
                        CalendarEvent(
                            summary=summary,
                            start=ev_start,
                            end=ev_end,
                            description=description,
                        )
                    )
            current_date += timedelta(days=1)

    return cal_events


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


class DysonScheduleCalendar(DysonEntity, CalendarEntity):
    """CalendarEntity that surfaces Dyson scheduled automation events.

    Data is fetched from the Dyson cloud and cached for 5 minutes.  The
    same :data:`~hass_dyson.sensor._schedule_cache` used by
    :class:`~hass_dyson.sensor.DysonScheduledEventsSensor` is shared here so
    that both entities stay in sync without making redundant API calls.
    """

    coordinator: DysonDataUpdateCoordinator
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialise the calendar entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_schedule_calendar"
        self._attr_name = "Schedule"
        self._schedule_data: Any = None

    async def async_added_to_hass(self) -> None:
        """Perform an initial data fetch and register the refresh timer."""
        await super().async_added_to_hass()
        # Fetch immediately so the calendar is populated on first load
        await self._async_refresh(None)
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._async_refresh,
                _UPDATE_INTERVAL,
            )
        )

    async def _async_refresh(self, now: object = None) -> None:
        """Fetch fresh schedule data from the Dyson cloud and update state."""
        from libdyson_rest.exceptions import DysonAPIError, DysonAuthError

        serial = self.coordinator.serial_number
        # Expire the cache entry so get() misses but get_stale() still works as
        # a fallback when the live fetch fails.
        _schedule_cache.expire(serial)

        product_type = _device_product_type(self.coordinator) or None
        async with self.coordinator.async_cloud_client() as client:
            if client is not None:
                try:
                    data = await client.get_scheduled_events(
                        serial, product_type=product_type
                    )
                    _schedule_cache.set(serial, data)
                    self._schedule_data = data
                except (DysonAPIError, DysonAuthError) as err:
                    _LOGGER.debug(
                        "Failed to refresh schedule calendar for %s: %s", serial, err
                    )
                    stale = _schedule_cache.get_stale(serial)
                    if stale is not None:
                        self._schedule_data = stale

        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # CalendarEntity interface
    # ------------------------------------------------------------------

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming (or currently active) calendar event."""
        if not self._schedule_data:
            return None
        now = dt_util.now()
        events = expand_schedule_to_calendar_events(
            self._schedule_data,
            now,
            now + timedelta(days=7),
            device_name=self.coordinator.device_name,
            local_tz=dt_util.get_default_time_zone(),
        )
        if not events:
            return None
        # Return the soonest-starting event
        return min(events, key=lambda e: e.start)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return all calendar events within the requested date range.

        Reads from the shared TTL cache so the cloud is not queried on
        every calendar view render.
        """
        data = (
            _schedule_cache.get(self.coordinator.serial_number) or self._schedule_data
        )
        if not data:
            return []
        return expand_schedule_to_calendar_events(
            data,
            start_date,
            end_date,
            device_name=self.coordinator.device_name,
            local_tz=dt_util.get_default_time_zone(),
        )
