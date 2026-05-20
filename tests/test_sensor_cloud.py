"""Tests for cloud-fetched sensor classes.

Covers DysonOutdoorAQISensor, DysonDailyAirQualitySensor, and
DysonScheduledEventsSensor — the three sensors that periodically call the
Dyson cloud REST API and refresh their state via async_track_time_interval.

Tests verify:
- async_added_to_hass registers a periodic timer via async_track_time_interval
- _async_scheduled_update invalidates the cache, calls async_update, writes state
- async_update uses the TTL cache on hits and fetches from cloud on misses
- async_update falls back to stale cache when the API fails
- async_update sets "unknown"/None state when no data is available
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_hass():
    """Minimal Home Assistant mock sufficient for cloud-sensor tests."""
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_cloud_client():
    """Mock of AsyncDysonClient with cloud-data methods pre-configured."""
    client = MagicMock()
    client.get_outdoor_environment_data = AsyncMock()
    client.get_daily_environment_data = AsyncMock()
    client.get_scheduled_events = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_coordinator(mock_hass, mock_cloud_client):
    """Coordinator mock wired with an async_cloud_client context manager."""
    coordinator = MagicMock()
    coordinator.hass = mock_hass
    coordinator.serial_number = "TEST-CLOUD-001"
    coordinator.last_update_success = True
    coordinator.device = MagicMock()
    coordinator.device.is_connected = True
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {
        "auth_token": "test-auth-token",
        "product_type": "438K",
    }

    # Wire async_cloud_client as an async context manager yielding the client.
    @asynccontextmanager
    async def _cloud_ctx():
        yield mock_cloud_client

    coordinator.async_cloud_client = MagicMock(side_effect=_cloud_ctx)
    return coordinator


# ---------------------------------------------------------------------------
# Helper — build a sensor with its hass/write-state plumbing mocked out
# ---------------------------------------------------------------------------


def _make_sensor(sensor_class, coordinator):
    """Instantiate *sensor_class* with mock hass and async_write_ha_state."""
    sensor = sensor_class(coordinator)
    sensor.hass = coordinator.hass
    sensor.async_write_ha_state = MagicMock()
    sensor.async_on_remove = MagicMock()
    return sensor


# ===========================================================================
# DysonOutdoorAQISensor
# ===========================================================================


class TestDysonOutdoorAQISensor:
    """Tests for DysonOutdoorAQISensor."""

    @pytest.mark.asyncio
    async def test_async_added_to_hass_registers_timer(self, mock_coordinator):
        """async_added_to_hass should register a periodic interval callback."""
        from custom_components.hass_dyson.sensor import DysonOutdoorAQISensor

        sensor = _make_sensor(DysonOutdoorAQISensor, mock_coordinator)
        with patch(
            "custom_components.hass_dyson.sensor.async_track_time_interval"
        ) as mock_track:
            # Patch CoordinatorEntity.async_added_to_hass so the listener
            # registration doesn't try to touch the real coordinator listener list.
            with patch(
                "homeassistant.helpers.update_coordinator.CoordinatorEntity.async_added_to_hass",
                new_callable=AsyncMock,
            ):
                await sensor.async_added_to_hass()

        mock_track.assert_called_once()
        args = mock_track.call_args[0]
        assert args[0] is mock_coordinator.hass
        assert args[2] == DysonOutdoorAQISensor._UPDATE_INTERVAL

    @pytest.mark.asyncio
    async def test_async_scheduled_update_invalidates_cache_and_writes_state(
        self, mock_coordinator, mock_cloud_client
    ):
        """_async_scheduled_update should invalidate cache then write new state."""
        from custom_components.hass_dyson.sensor import (
            DysonOutdoorAQISensor,
            _outdoor_aqi_cache,
        )

        sensor = _make_sensor(DysonOutdoorAQISensor, mock_coordinator)

        # Pre-populate cache so we can verify it gets invalidated.
        aqi_data = MagicMock()
        aqi_data.aqi_value = 42
        aqi_data.aqi_name = "Good"
        aqi_data.aqi_description = "Air quality is good"
        aqi_data.pm25_value = 5
        aqi_data.pm10_value = 8
        aqi_data.no2_value = 2
        aqi_data.humidity = 60
        aqi_data.temperature = 22
        aqi_data.weather_state = "Sunny"
        aqi_data.location_name = "London"
        aqi_data.dominant_pollen = "Grass"
        aqi_data.date_time = "2025-01-01T12:00:00Z"

        _outdoor_aqi_cache.set(mock_coordinator.serial_number, aqi_data)
        mock_cloud_client.get_outdoor_environment_data.return_value = aqi_data

        await sensor._async_scheduled_update()

        # Cache must have been re-populated (invalidate forces a fetch)
        assert _outdoor_aqi_cache.get(mock_coordinator.serial_number) is not None
        mock_cloud_client.get_outdoor_environment_data.assert_called_once_with(
            mock_coordinator.serial_number
        )
        sensor.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_uses_fresh_cache(
        self, mock_coordinator, mock_cloud_client
    ):
        """async_update should use the cache without calling the API when fresh."""
        from custom_components.hass_dyson.sensor import (
            DysonOutdoorAQISensor,
            _outdoor_aqi_cache,
        )

        sensor = _make_sensor(DysonOutdoorAQISensor, mock_coordinator)

        aqi_data = MagicMock()
        aqi_data.aqi_value = 99
        aqi_data.aqi_name = "Poor"
        aqi_data.aqi_description = "Unhealthy"
        aqi_data.pm25_value = 80
        aqi_data.pm10_value = 90
        aqi_data.no2_value = 30
        aqi_data.humidity = 40
        aqi_data.temperature = 30
        aqi_data.weather_state = "Cloudy"
        aqi_data.location_name = "Berlin"
        aqi_data.dominant_pollen = "Tree"
        aqi_data.date_time = "2025-06-01T08:00:00Z"

        _outdoor_aqi_cache.set(mock_coordinator.serial_number, aqi_data)

        await sensor.async_update()

        # API should NOT have been called (cache hit).
        mock_cloud_client.get_outdoor_environment_data.assert_not_called()
        assert sensor._attr_native_value == 99

    @pytest.mark.asyncio
    async def test_async_update_fetches_when_cache_empty(
        self, mock_coordinator, mock_cloud_client
    ):
        """async_update fetches from cloud when cache is empty."""
        from custom_components.hass_dyson.sensor import (
            DysonOutdoorAQISensor,
            _outdoor_aqi_cache,
        )

        _outdoor_aqi_cache.invalidate(mock_coordinator.serial_number)
        sensor = _make_sensor(DysonOutdoorAQISensor, mock_coordinator)

        aqi_data = MagicMock()
        aqi_data.aqi_value = 55
        aqi_data.aqi_name = "Moderate"
        aqi_data.aqi_description = "Moderate air quality"
        aqi_data.pm25_value = 20
        aqi_data.pm10_value = 30
        aqi_data.no2_value = 10
        aqi_data.humidity = 50
        aqi_data.temperature = 18
        aqi_data.weather_state = "Overcast"
        aqi_data.location_name = "Paris"
        aqi_data.dominant_pollen = None
        aqi_data.date_time = "2025-01-01T09:00:00Z"

        mock_cloud_client.get_outdoor_environment_data.return_value = aqi_data

        await sensor.async_update()

        mock_cloud_client.get_outdoor_environment_data.assert_called_once_with(
            mock_coordinator.serial_number
        )
        assert sensor._attr_native_value == 55

    @pytest.mark.asyncio
    async def test_async_update_falls_back_to_stale_on_api_error(
        self, mock_coordinator, mock_cloud_client
    ):
        """async_update falls back to stale cache when the API raises an error."""
        from libdyson_rest.exceptions import DysonAPIError

        from custom_components.hass_dyson.sensor import (
            DysonOutdoorAQISensor,
            _outdoor_aqi_cache,
        )

        serial = mock_coordinator.serial_number
        # Seed the cache then manually expire it by manipulating the internal store.
        stale = MagicMock()
        stale.aqi_value = 12
        stale.aqi_name = "Good"
        stale.aqi_description = "Stale"
        stale.pm25_value = 1
        stale.pm10_value = 2
        stale.no2_value = 0
        stale.humidity = 55
        stale.temperature = 20
        stale.weather_state = "Clear"
        stale.location_name = "Dublin"
        stale.dominant_pollen = "Mold"
        stale.date_time = "2025-01-01T00:00:00Z"
        # Write directly to _store so get() sees an expired entry but get_stale() works.
        _outdoor_aqi_cache._store[serial] = (0.0, stale)

        mock_cloud_client.get_outdoor_environment_data.side_effect = DysonAPIError(
            "timeout"
        )
        sensor = _make_sensor(DysonOutdoorAQISensor, mock_coordinator)

        await sensor.async_update()

        # Should fall back to stale value.
        assert sensor._attr_native_value == 12

    @pytest.mark.asyncio
    async def test_async_update_sets_none_when_no_data(
        self, mock_coordinator, mock_cloud_client
    ):
        """async_update sets native_value=None when no data is available."""
        from custom_components.hass_dyson.sensor import (
            DysonOutdoorAQISensor,
            _outdoor_aqi_cache,
        )

        _outdoor_aqi_cache.invalidate(mock_coordinator.serial_number)

        # Simulate no_auth (client returns None via coordinator that yields None)
        @asynccontextmanager
        async def _no_client():
            yield None

        mock_coordinator.async_cloud_client = MagicMock(side_effect=_no_client)
        sensor = _make_sensor(DysonOutdoorAQISensor, mock_coordinator)

        await sensor.async_update()

        assert sensor._attr_native_value is None
        assert sensor._attr_extra_state_attributes == {}


# ===========================================================================
# DysonDailyAirQualitySensor
# ===========================================================================


class TestDysonDailyAirQualitySensor:
    """Tests for DysonDailyAirQualitySensor."""

    @pytest.mark.asyncio
    async def test_async_added_to_hass_registers_timer(self, mock_coordinator):
        """async_added_to_hass should register a periodic interval callback."""
        from custom_components.hass_dyson.sensor import DysonDailyAirQualitySensor

        sensor = _make_sensor(DysonDailyAirQualitySensor, mock_coordinator)
        with patch(
            "custom_components.hass_dyson.sensor.async_track_time_interval"
        ) as mock_track:
            with patch(
                "homeassistant.helpers.update_coordinator.CoordinatorEntity.async_added_to_hass",
                new_callable=AsyncMock,
            ):
                await sensor.async_added_to_hass()

        mock_track.assert_called_once()
        args = mock_track.call_args[0]
        assert args[0] is mock_coordinator.hass
        assert args[2] == DysonDailyAirQualitySensor._UPDATE_INTERVAL

    @pytest.mark.asyncio
    async def test_async_scheduled_update_invalidates_cache_and_writes_state(
        self, mock_coordinator, mock_cloud_client
    ):
        """_async_scheduled_update invalidates cache then fetches and writes state."""
        from custom_components.hass_dyson.sensor import (
            DysonDailyAirQualitySensor,
            _daily_env_cache,
        )

        sensor = _make_sensor(DysonDailyAirQualitySensor, mock_coordinator)

        env_data = MagicMock()
        env_data.latest_sample = 35.0
        env_data.samples = [30.0, 35.0]
        env_data.start_time = "2025-01-01T00:00:00Z"
        env_data.resolution_minutes = 15

        _daily_env_cache.set(mock_coordinator.serial_number, env_data)
        mock_cloud_client.get_daily_environment_data.return_value = env_data

        await sensor._async_scheduled_update()

        mock_cloud_client.get_daily_environment_data.assert_called_once()
        sensor.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_uses_fresh_cache(
        self, mock_coordinator, mock_cloud_client
    ):
        """async_update returns cached data without calling the API."""
        from custom_components.hass_dyson.sensor import (
            DysonDailyAirQualitySensor,
            _daily_env_cache,
        )

        env_data = MagicMock()
        env_data.latest_sample = 22.5
        env_data.samples = [20.0, 22.5]
        env_data.start_time = "2025-01-01T00:00:00Z"
        env_data.resolution_minutes = 15

        _daily_env_cache.set(mock_coordinator.serial_number, env_data)
        sensor = _make_sensor(DysonDailyAirQualitySensor, mock_coordinator)

        await sensor.async_update()

        mock_cloud_client.get_daily_environment_data.assert_not_called()
        assert sensor._attr_native_value == 22.5

    @pytest.mark.asyncio
    async def test_async_update_fetches_when_cache_empty(
        self, mock_coordinator, mock_cloud_client
    ):
        """async_update fetches from cloud when cache is empty."""
        from custom_components.hass_dyson.sensor import (
            DysonDailyAirQualitySensor,
            _daily_env_cache,
        )

        _daily_env_cache.invalidate(mock_coordinator.serial_number)
        sensor = _make_sensor(DysonDailyAirQualitySensor, mock_coordinator)

        env_data = MagicMock()
        env_data.latest_sample = 40.0
        env_data.samples = [38.0, 39.0, 40.0]
        env_data.start_time = "2025-01-01T00:00:00Z"
        env_data.resolution_minutes = 15

        mock_cloud_client.get_daily_environment_data.return_value = env_data

        await sensor.async_update()

        mock_cloud_client.get_daily_environment_data.assert_called_once_with(
            mock_coordinator.serial_number
        )
        assert sensor._attr_native_value == 40.0

    @pytest.mark.asyncio
    async def test_async_update_falls_back_to_stale_on_api_error(
        self, mock_coordinator, mock_cloud_client
    ):
        """Falls back to stale cache data when API raises DysonAPIError."""
        from libdyson_rest.exceptions import DysonConnectionError

        from custom_components.hass_dyson.sensor import (
            DysonDailyAirQualitySensor,
            _daily_env_cache,
        )

        serial = mock_coordinator.serial_number
        stale = MagicMock()
        stale.latest_sample = 15.5
        stale.samples = [15.0, 15.5]
        stale.start_time = "2025-01-01T00:00:00Z"
        stale.resolution_minutes = 15
        _daily_env_cache._store[serial] = (0.0, stale)  # expired entry

        mock_cloud_client.get_daily_environment_data.side_effect = DysonConnectionError(
            "network error"
        )
        sensor = _make_sensor(DysonDailyAirQualitySensor, mock_coordinator)

        await sensor.async_update()

        assert sensor._attr_native_value == 15.5

    @pytest.mark.asyncio
    async def test_async_update_sets_none_when_no_data(self, mock_coordinator):
        """async_update sets native_value=None when no data is available."""
        from custom_components.hass_dyson.sensor import (
            DysonDailyAirQualitySensor,
            _daily_env_cache,
        )

        _daily_env_cache.invalidate(mock_coordinator.serial_number)

        @asynccontextmanager
        async def _no_client():
            yield None

        mock_coordinator.async_cloud_client = MagicMock(side_effect=_no_client)
        sensor = _make_sensor(DysonDailyAirQualitySensor, mock_coordinator)

        await sensor.async_update()

        assert sensor._attr_native_value is None
        assert sensor._attr_extra_state_attributes == {}

    @pytest.mark.asyncio
    async def test_async_update_handles_none_latest_sample(
        self, mock_coordinator, mock_cloud_client
    ):
        """native_value is None when latest_sample is None."""
        from custom_components.hass_dyson.sensor import (
            DysonDailyAirQualitySensor,
            _daily_env_cache,
        )

        _daily_env_cache.invalidate(mock_coordinator.serial_number)
        sensor = _make_sensor(DysonDailyAirQualitySensor, mock_coordinator)

        env_data = MagicMock()
        env_data.latest_sample = None
        env_data.samples = []
        env_data.start_time = "2025-01-01T00:00:00Z"
        env_data.resolution_minutes = 15
        mock_cloud_client.get_daily_environment_data.return_value = env_data

        await sensor.async_update()

        assert sensor._attr_native_value is None


# ===========================================================================
# DysonScheduledEventsSensor
# ===========================================================================


class TestDysonScheduledEventsSensor:
    """Tests for DysonScheduledEventsSensor."""

    @pytest.mark.asyncio
    async def test_async_added_to_hass_registers_timer(self, mock_coordinator):
        """async_added_to_hass should register a periodic interval callback."""
        from custom_components.hass_dyson.sensor import DysonScheduledEventsSensor

        sensor = _make_sensor(DysonScheduledEventsSensor, mock_coordinator)
        with patch(
            "custom_components.hass_dyson.sensor.async_track_time_interval"
        ) as mock_track:
            with patch(
                "homeassistant.helpers.update_coordinator.CoordinatorEntity.async_added_to_hass",
                new_callable=AsyncMock,
            ):
                await sensor.async_added_to_hass()

        mock_track.assert_called_once()
        args = mock_track.call_args[0]
        assert args[0] is mock_coordinator.hass
        assert args[2] == DysonScheduledEventsSensor._UPDATE_INTERVAL

    @pytest.mark.asyncio
    async def test_async_scheduled_update_invalidates_cache_and_writes_state(
        self, mock_coordinator, mock_cloud_client
    ):
        """_async_scheduled_update invalidates cache then fetches and writes state."""
        from custom_components.hass_dyson.sensor import (
            DysonScheduledEventsSensor,
            _schedule_cache,
        )

        sensor = _make_sensor(DysonScheduledEventsSensor, mock_coordinator)

        event1 = MagicMock()
        event1.enabled = True
        event1.raw = {"id": "ev1"}

        sched_data = MagicMock()
        sched_data.schedule_enabled = True
        sched_data.events = [event1]

        _schedule_cache.set(mock_coordinator.serial_number, sched_data)
        mock_cloud_client.get_scheduled_events.return_value = sched_data

        with patch(
            "custom_components.hass_dyson.sensor._device_product_type",
            return_value="438K",
        ):
            await sensor._async_scheduled_update()

        mock_cloud_client.get_scheduled_events.assert_called_once()
        sensor.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_uses_fresh_cache(
        self, mock_coordinator, mock_cloud_client
    ):
        """async_update uses cached data without calling the API."""
        from custom_components.hass_dyson.sensor import (
            DysonScheduledEventsSensor,
            _schedule_cache,
        )

        event1 = MagicMock()
        event1.enabled = True
        event1.raw = {"id": "ev1"}

        sched_data = MagicMock()
        sched_data.schedule_enabled = True
        sched_data.events = [event1]

        _schedule_cache.set(mock_coordinator.serial_number, sched_data)
        sensor = _make_sensor(DysonScheduledEventsSensor, mock_coordinator)

        with patch(
            "custom_components.hass_dyson.sensor._device_product_type",
            return_value="438K",
        ):
            await sensor.async_update()

        mock_cloud_client.get_scheduled_events.assert_not_called()
        assert sensor._attr_native_value == "1 active"

    @pytest.mark.asyncio
    async def test_async_update_fetches_when_cache_empty(
        self, mock_coordinator, mock_cloud_client
    ):
        """async_update fetches from cloud when cache is empty."""
        from custom_components.hass_dyson.sensor import (
            DysonScheduledEventsSensor,
            _schedule_cache,
        )

        _schedule_cache.invalidate(mock_coordinator.serial_number)
        sensor = _make_sensor(DysonScheduledEventsSensor, mock_coordinator)

        event1 = MagicMock()
        event1.enabled = True
        event1.raw = {"id": "ev1"}
        event2 = MagicMock()
        event2.enabled = True
        event2.raw = {"id": "ev2"}

        sched_data = MagicMock()
        sched_data.schedule_enabled = True
        sched_data.events = [event1, event2]

        mock_cloud_client.get_scheduled_events.return_value = sched_data

        with patch(
            "custom_components.hass_dyson.sensor._device_product_type",
            return_value="438K",
        ):
            await sensor.async_update()

        mock_cloud_client.get_scheduled_events.assert_called_once_with(
            mock_coordinator.serial_number, product_type="438K"
        )
        assert sensor._attr_native_value == "2 active"

    @pytest.mark.asyncio
    async def test_async_update_schedule_disabled(
        self, mock_coordinator, mock_cloud_client
    ):
        """State is 'disabled' when schedule_enabled is False."""
        from custom_components.hass_dyson.sensor import (
            DysonScheduledEventsSensor,
            _schedule_cache,
        )

        _schedule_cache.invalidate(mock_coordinator.serial_number)
        sensor = _make_sensor(DysonScheduledEventsSensor, mock_coordinator)

        event1 = MagicMock()
        event1.enabled = True  # event enabled but schedule is off
        event1.raw = {"id": "ev1"}

        sched_data = MagicMock()
        sched_data.schedule_enabled = False
        sched_data.events = [event1]

        mock_cloud_client.get_scheduled_events.return_value = sched_data

        with patch(
            "custom_components.hass_dyson.sensor._device_product_type",
            return_value=None,
        ):
            await sensor.async_update()

        assert sensor._attr_native_value == "disabled"
        assert sensor._attr_extra_state_attributes["schedule_enabled"] is False
        assert sensor._attr_extra_state_attributes["active_event_count"] == 1
        assert sensor._attr_extra_state_attributes["active_schedule_count"] == 1

    @pytest.mark.asyncio
    async def test_async_update_counts_only_enabled_events(
        self, mock_coordinator, mock_cloud_client
    ):
        """Only enabled individual events are counted in active_event_count."""
        from custom_components.hass_dyson.sensor import (
            DysonScheduledEventsSensor,
            _schedule_cache,
        )

        _schedule_cache.invalidate(mock_coordinator.serial_number)
        sensor = _make_sensor(DysonScheduledEventsSensor, mock_coordinator)

        ev_on = MagicMock()
        ev_on.enabled = True
        ev_on.raw = {"id": "on"}
        ev_off = MagicMock()
        ev_off.enabled = False
        ev_off.raw = {"id": "off"}

        sched_data = MagicMock()
        sched_data.schedule_enabled = True
        sched_data.events = [ev_on, ev_off]

        mock_cloud_client.get_scheduled_events.return_value = sched_data

        with patch(
            "custom_components.hass_dyson.sensor._device_product_type",
            return_value="438K",
        ):
            await sensor.async_update()

        assert sensor._attr_native_value == "1 active"
        assert sensor._attr_extra_state_attributes["active_event_count"] == 1
        assert sensor._attr_extra_state_attributes["active_schedule_count"] == 1
        assert sensor._attr_extra_state_attributes["total_event_count"] == 2

    @pytest.mark.asyncio
    async def test_async_update_deduplicates_by_group_id(
        self, mock_coordinator, mock_cloud_client
    ):
        """Two events sharing a groupId count as one active schedule."""
        from custom_components.hass_dyson.sensor import (
            DysonScheduledEventsSensor,
            _schedule_cache,
        )

        _schedule_cache.invalidate(mock_coordinator.serial_number)
        sensor = _make_sensor(DysonScheduledEventsSensor, mock_coordinator)

        # Dyson represents start + end of a schedule as two events with the same groupId
        ev_start = MagicMock()
        ev_start.enabled = True
        ev_start.raw = {"groupId": 1, "startTime": "01:00:00"}
        ev_end = MagicMock()
        ev_end.enabled = True
        ev_end.raw = {"groupId": 1, "startTime": "06:00:00"}

        sched_data = MagicMock()
        sched_data.schedule_enabled = True
        sched_data.events = [ev_start, ev_end]

        mock_cloud_client.get_scheduled_events.return_value = sched_data

        with patch(
            "custom_components.hass_dyson.sensor._device_product_type",
            return_value=None,
        ):
            await sensor.async_update()

        # 2 raw events but 1 unique groupId → 1 active schedule
        assert sensor._attr_native_value == "1 active"
        assert sensor._attr_extra_state_attributes["active_schedule_count"] == 1
        assert sensor._attr_extra_state_attributes["active_event_count"] == 2

    @pytest.mark.asyncio
    async def test_async_update_falls_back_to_stale_on_api_error(
        self, mock_coordinator, mock_cloud_client
    ):
        """Falls back to stale cache data when API raises an error."""
        from libdyson_rest.exceptions import DysonAuthError

        from custom_components.hass_dyson.sensor import (
            DysonScheduledEventsSensor,
            _schedule_cache,
        )

        serial = mock_coordinator.serial_number
        ev = MagicMock()
        ev.enabled = True
        ev.raw = {"id": "stale"}
        stale = MagicMock()
        stale.schedule_enabled = True
        stale.events = [ev]
        _schedule_cache._store[serial] = (0.0, stale)  # expired

        mock_cloud_client.get_scheduled_events.side_effect = DysonAuthError("expired")
        sensor = _make_sensor(DysonScheduledEventsSensor, mock_coordinator)

        with patch(
            "custom_components.hass_dyson.sensor._device_product_type",
            return_value=None,
        ):
            await sensor.async_update()

        assert sensor._attr_native_value == "1 active"

    @pytest.mark.asyncio
    async def test_async_update_sets_unknown_when_no_data(self, mock_coordinator):
        """State is 'unknown' when no data is available at all."""
        from custom_components.hass_dyson.sensor import (
            DysonScheduledEventsSensor,
            _schedule_cache,
        )

        _schedule_cache.invalidate(mock_coordinator.serial_number)

        @asynccontextmanager
        async def _no_client():
            yield None

        mock_coordinator.async_cloud_client = MagicMock(side_effect=_no_client)
        sensor = _make_sensor(DysonScheduledEventsSensor, mock_coordinator)

        with patch(
            "custom_components.hass_dyson.sensor._device_product_type",
            return_value=None,
        ):
            await sensor.async_update()

        assert sensor._attr_native_value == "unknown"
        assert sensor._attr_extra_state_attributes == {}

    @pytest.mark.asyncio
    async def test_async_update_with_no_product_type(
        self, mock_coordinator, mock_cloud_client
    ):
        """get_scheduled_events is called with product_type=None when unavailable."""
        from custom_components.hass_dyson.sensor import (
            DysonScheduledEventsSensor,
            _schedule_cache,
        )

        _schedule_cache.invalidate(mock_coordinator.serial_number)
        sensor = _make_sensor(DysonScheduledEventsSensor, mock_coordinator)

        sched_data = MagicMock()
        sched_data.schedule_enabled = True
        sched_data.events = []

        mock_cloud_client.get_scheduled_events.return_value = sched_data

        with patch(
            "custom_components.hass_dyson.sensor._device_product_type",
            return_value=None,
        ):
            await sensor.async_update()

        mock_cloud_client.get_scheduled_events.assert_called_once_with(
            mock_coordinator.serial_number, product_type=None
        )

    def test_update_interval_is_five_minutes(self):
        """Sanity-check that the update interval class attribute is 5 minutes."""
        from datetime import timedelta

        from custom_components.hass_dyson.sensor import DysonScheduledEventsSensor

        assert DysonScheduledEventsSensor._UPDATE_INTERVAL == timedelta(minutes=5)

    def test_outdoor_aqi_update_interval_is_fifteen_minutes(self):
        """Sanity-check that outdoor AQI uses a 15-minute update interval."""
        from datetime import timedelta

        from custom_components.hass_dyson.sensor import DysonOutdoorAQISensor

        assert DysonOutdoorAQISensor._UPDATE_INTERVAL == timedelta(minutes=15)

    def test_daily_aqi_update_interval_is_sixty_minutes(self):
        """Sanity-check that daily AQI uses a 60-minute update interval."""
        from datetime import timedelta

        from custom_components.hass_dyson.sensor import DysonDailyAirQualitySensor

        assert DysonDailyAirQualitySensor._UPDATE_INTERVAL == timedelta(minutes=60)
