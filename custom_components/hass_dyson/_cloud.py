"""Shared HTTP + TTL-cache helpers for Dyson cloud REST calls.

Used by sensor.py, image.py, and services.py for the handful of REST endpoints
we hit on top of the integration's MQTT plumbing. Centralised here to avoid
the copy-paste sprawl of per-endpoint cache dicts and per-file aiohttp wrappers
that the integration accumulated over time.

The endpoints all live under https://appapi.cp.dyson.com — Bearer auth, JSON
in/out. iOS-app headers are spoofed so a future server-side fingerprint check
doesn't lock us out.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


_BASE_URL = "https://appapi.cp.dyson.com"
_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=15)

# Headers matching MyDyson iOS app traffic. The Authorization header is added
# per-request from the device's auth_token.
_BASE_HEADERS: dict[str, str] = {
    "Accept": "application/json",
    "User-Agent": "DysonLink/226342 CFNetwork/3860.600.12 Darwin/25.5.0",
    "X-Platform": "ios",
    "X-App-Version": "6.4.26181",
}


class TTLCache:
    """Tiny in-process TTL cache keyed by string.

    All entries share the same TTL; entries expire lazily on `get()`. Suitable
    for memoising small JSON responses from the Dyson cloud; not a substitute
    for a real LRU or async coordinator if the dataset grows large.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        cached = self._store.get(key)
        if cached is None:
            return None
        if (time.monotonic() - cached[0]) >= self._ttl:
            return None
        return cached[1]

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic(), value)

    def get_stale(self, key: str) -> Any | None:
        """Return the cached value regardless of TTL (use only as a fallback)."""
        cached = self._store.get(key)
        return cached[1] if cached else None

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)


def _auth_header(coordinator) -> dict[str, str] | None:
    """Build the Authorization header from the coordinator's stored token."""
    token = coordinator.config_entry.data.get("auth_token")
    if not token:
        return None
    return {**_BASE_HEADERS, "Authorization": f"Bearer {token}"}


async def dyson_cloud_get(coordinator, path: str) -> Any:
    """Bearer-authenticated GET. Returns parsed JSON on success; None on any
    failure (network error, non-200 status, missing token). Callers typically
    fall back to a stale cache entry on None.

    Uses HA's shared aiohttp client session (one connection pool per HA
    instance, lifecycle managed by HA) rather than spinning up a fresh
    session per call.
    """
    headers = _auth_header(coordinator)
    if headers is None:
        return None
    session = async_get_clientsession(coordinator.hass)
    url = f"{_BASE_URL}{path}"
    try:
        async with session.get(url, headers=headers, timeout=_DEFAULT_TIMEOUT) as resp:
            if resp.status != 200:
                _LOGGER.debug(
                    "Dyson cloud GET %s → HTTP %d",
                    path,
                    resp.status,
                )
                return None
            return await resp.json()
    except aiohttp.ClientError as err:
        _LOGGER.debug("Dyson cloud GET %s failed: %s", path, err)
        return None


async def dyson_cloud_put(
    coordinator,
    path: str,
    body: dict,
    *,
    ok_statuses: tuple[int, ...] = (200, 204),
) -> None:
    """Bearer-authenticated PUT. Raises HomeAssistantError on any failure.

    Unlike dyson_cloud_get, this raises rather than returns None — writes
    have side effects and the caller usually wants to surface a failure
    to the user (service-call error path).
    """
    auth_token = coordinator.config_entry.data.get("auth_token")
    if not auth_token:
        raise HomeAssistantError(
            f"No auth_token on config entry for {coordinator.serial_number}"
        )
    headers = {
        **_BASE_HEADERS,
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }
    session = async_get_clientsession(coordinator.hass)
    url = f"{_BASE_URL}{path}"
    try:
        async with session.put(
            url, headers=headers, json=body, timeout=_DEFAULT_TIMEOUT
        ) as resp:
            if resp.status not in ok_statuses:
                text = await resp.text()
                raise HomeAssistantError(
                    f"Dyson cloud PUT {path} returned HTTP {resp.status}: {text[:200]}"
                )
    except aiohttp.ClientError as err:
        raise HomeAssistantError(f"Network error on PUT {path}: {err}") from err


# ----------------------------------------------------------------------------
# Shared per-endpoint accessors. Live here (rather than in sensor.py +
# image.py) when two or more consumers in the integration hit the same
# endpoint — keeps the cache + fetch logic in one place so independent
# consumers don't double-fetch the same blob seconds apart.
# ----------------------------------------------------------------------------

# Recent cleaning runs for the Vis Nav. Read by both the cleaning-history
# sensors (sensor.py) and the dust-map image (image.py); the latter also
# pulls per-clean metadata (cleanedFootprint, cleaningProgramme, etc) from
# the same response.
_clean_maps_cache = TTLCache(30 * 60)


async def fetch_clean_maps(coordinator) -> list[dict]:
    """Fetch the device's recent cleaning runs (cached 30 min, newest first).

    Endpoint: GET /v1/{serial}/clean-maps?dustMap=total
    Returns the parsed JSON list (or [] / stale cache on any failure).
    """
    serial = coordinator.serial_number
    fresh = _clean_maps_cache.get(serial)
    if fresh is not None:
        return fresh
    data = await dyson_cloud_get(coordinator, f"/v1/{serial}/clean-maps?dustMap=total")
    if not isinstance(data, list):
        return _clean_maps_cache.get_stale(serial) or []
    # Newest-first defensive sort. The API generally returns newest first
    # already, but don't rely on it.
    data.sort(
        key=lambda c: min(
            (
                e.get("time")
                for e in (c.get("cleanTimeline") or [])
                if isinstance(e, dict) and e.get("time")
            ),
            default="",
        ),
        reverse=True,
    )
    _clean_maps_cache.set(serial, data)
    return data
