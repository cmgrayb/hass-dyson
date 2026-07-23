"""Tests for the endOfClean → clean-history cache refresh hook.

Live-verified timing: the cloud history entry for a finished clean appears
within ~2 minutes of the robot's ``endOfClean: true`` STATE-CHANGE, while
the clean-maps cache TTL is 30 minutes — the hook bridges the gap.
"""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.hass_dyson.sensor import (
    CLEAN_HISTORY_REFRESH_DELAY,
    _register_end_of_clean_listener,
)

SERIAL = "VS9-GB-HJA0000A"


def _hass():
    hass = MagicMock(spec=HomeAssistant)
    hass.loop = MagicMock()
    hass.loop.call_soon_threadsafe.side_effect = lambda fn, *args: fn(*args)
    return hass


def _coordinator():
    coordinator = MagicMock()
    coordinator.serial_number = SERIAL
    coordinator.device = MagicMock()
    return coordinator


def _entry():
    return MagicMock(spec=ConfigEntry)


class TestEndOfCleanListener:
    def test_registers_and_unloads(self):
        hass, entry, coordinator = _hass(), _entry(), _coordinator()
        _register_end_of_clean_listener(hass, entry, coordinator)
        coordinator.device.add_message_callback.assert_called_once()
        entry.async_on_unload.assert_called_once()
        entry.async_on_unload.call_args[0][0]()
        coordinator.device.remove_message_callback.assert_called_once()

    def test_no_device_is_a_noop(self):
        hass, entry, coordinator = _hass(), _entry(), _coordinator()
        coordinator.device = None
        _register_end_of_clean_listener(hass, entry, coordinator)
        entry.async_on_unload.assert_not_called()

    def test_end_of_clean_schedules_delayed_invalidation(self):
        hass, entry, coordinator = _hass(), _entry(), _coordinator()
        with patch(
            "custom_components.hass_dyson.sensor.async_call_later"
        ) as call_later:
            _register_end_of_clean_listener(hass, entry, coordinator)
            listener = coordinator.device.add_message_callback.call_args[0][0]
            listener(
                "topic",
                {
                    "msg": "STATE-CHANGE",
                    "newstate": "FULL_CLEAN_FINISHED",
                    "endOfClean": True,
                },
            )
        call_later.assert_called_once()
        assert call_later.call_args[0][1] == CLEAN_HISTORY_REFRESH_DELAY

    def test_other_messages_ignored(self):
        hass, entry, coordinator = _hass(), _entry(), _coordinator()
        with patch(
            "custom_components.hass_dyson.sensor.async_call_later"
        ) as call_later:
            _register_end_of_clean_listener(hass, entry, coordinator)
            listener = coordinator.device.add_message_callback.call_args[0][0]
            listener("topic", {"msg": "STATE-CHANGE", "newstate": "FULL_CLEAN_RUNNING"})
            listener("topic", {"msg": "CURRENT-STATE", "state": "INACTIVE_CHARGED"})
        call_later.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_invalidates_clean_maps_cache(self):
        hass, entry, coordinator = _hass(), _entry(), _coordinator()
        with (
            patch("custom_components.hass_dyson.sensor.async_call_later") as call_later,
            patch("custom_components.hass_dyson.vacuum._clean_maps_cache") as cache,
        ):
            _register_end_of_clean_listener(hass, entry, coordinator)
            listener = coordinator.device.add_message_callback.call_args[0][0]
            listener("topic", {"msg": "STATE-CHANGE", "endOfClean": True})
            refresh_cb = call_later.call_args[0][2]
            await refresh_cb(None)
        cache.invalidate.assert_called_once_with(SERIAL)

    @pytest.mark.asyncio
    async def test_refresh_invalidates_image_and_recommendation_caches(self):
        """The robot re-versions the persistent map after a clean, so the
        image-side caches (floor plan, offsets, rendered maps) and the
        recommended-cleans cache must be dropped alongside the history."""
        hass, entry, coordinator = _hass(), _entry(), _coordinator()
        with (
            patch("custom_components.hass_dyson.sensor.async_call_later") as call_later,
            patch("custom_components.hass_dyson.vacuum._clean_maps_cache"),
            patch(
                "custom_components.hass_dyson.image._persist_map_cache"
            ) as persist_cache,
            patch(
                "custom_components.hass_dyson.image._floor_plan_cache"
            ) as floor_cache,
            patch(
                "custom_components.hass_dyson.image._map_image_cache"
            ) as map_img_cache,
            patch(
                "custom_components.hass_dyson.sensor._recommended_cleans_cache"
            ) as rec_cache,
        ):
            _register_end_of_clean_listener(hass, entry, coordinator)
            listener = coordinator.device.add_message_callback.call_args[0][0]
            listener("topic", {"msg": "STATE-CHANGE", "endOfClean": True})
            refresh_cb = call_later.call_args[0][2]
            await refresh_cb(None)
        persist_cache.expire_prefix.assert_called_once_with(f"{SERIAL}:")
        floor_cache.invalidate_prefix.assert_called_once_with(f"{SERIAL}:")
        map_img_cache.invalidate_prefix.assert_called_once_with(f"{SERIAL}:")
        rec_cache.invalidate.assert_called_once_with(SERIAL)

    def test_repeated_end_of_clean_coalesces(self):
        hass, entry, coordinator = _hass(), _entry(), _coordinator()
        cancel = MagicMock()
        with patch(
            "custom_components.hass_dyson.sensor.async_call_later",
            return_value=cancel,
        ) as call_later:
            _register_end_of_clean_listener(hass, entry, coordinator)
            listener = coordinator.device.add_message_callback.call_args[0][0]
            listener("topic", {"msg": "STATE-CHANGE", "endOfClean": True})
            listener("topic", {"msg": "STATE-CHANGE", "endOfClean": True})
        assert call_later.call_count == 2
        cancel.assert_called_once()

    def test_message_in_flight_at_unload_does_not_rearm(self):
        hass, entry, coordinator = _hass(), _entry(), _coordinator()
        queued = []
        hass.loop.call_soon_threadsafe.side_effect = lambda fn, *args: queued.append(
            (fn, args)
        )
        with patch(
            "custom_components.hass_dyson.sensor.async_call_later"
        ) as call_later:
            _register_end_of_clean_listener(hass, entry, coordinator)
            listener = coordinator.device.add_message_callback.call_args[0][0]
            listener("topic", {"msg": "STATE-CHANGE", "endOfClean": True})
            entry.async_on_unload.call_args[0][0]()
            for fn, args in queued:
                fn(*args)
        call_later.assert_not_called()

    def test_unload_cancels_pending_refresh(self):
        hass, entry, coordinator = _hass(), _entry(), _coordinator()
        cancel = MagicMock()
        with patch(
            "custom_components.hass_dyson.sensor.async_call_later",
            return_value=cancel,
        ):
            _register_end_of_clean_listener(hass, entry, coordinator)
            listener = coordinator.device.add_message_callback.call_args[0][0]
            listener("topic", {"msg": "STATE-CHANGE", "endOfClean": True})
            entry.async_on_unload.call_args[0][0]()
        cancel.assert_called_once()


class TestTTLCacheInvalidatePrefix:
    def test_removes_only_matching_keys(self):
        from custom_components.hass_dyson.coordinator import TTLCache

        cache = TTLCache(3600)
        cache.set(f"{SERIAL}:map-1", "a")
        cache.set(f"{SERIAL}:map-2", "b")
        cache.set("OTHER-SERIAL:map-1", "c")
        cache.invalidate_prefix(f"{SERIAL}:")
        assert cache.get(f"{SERIAL}:map-1") is None
        assert cache.get_stale(f"{SERIAL}:map-1") is None
        assert cache.get(f"{SERIAL}:map-2") is None
        assert cache.get("OTHER-SERIAL:map-1") == "c"

    def test_empty_cache_is_a_noop(self):
        from custom_components.hass_dyson.coordinator import TTLCache

        cache = TTLCache(3600)
        cache.invalidate_prefix("anything:")
        assert cache.get_stale("anything:x") is None

    def test_expire_prefix_keeps_stale_fallback(self):
        from custom_components.hass_dyson.coordinator import TTLCache

        cache = TTLCache(3600)
        cache.set(f"{SERIAL}:map-1", "a")
        cache.set("OTHER-SERIAL:map-1", "c")
        cache.expire_prefix(f"{SERIAL}:")
        assert cache.get(f"{SERIAL}:map-1") is None
        assert cache.get_stale(f"{SERIAL}:map-1") == "a"
        assert cache.get("OTHER-SERIAL:map-1") == "c"
