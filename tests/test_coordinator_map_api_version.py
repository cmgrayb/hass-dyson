"""Tests for DysonDataUpdateCoordinator.async_discover_map_api_version.

Covers the map-endpoint API version probe: caching of definitive results,
non-caching of transient failures, and HTTP-status extraction from
libdyson-rest error messages.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from libdyson_rest.exceptions import DysonAPIError, DysonAuthError

from custom_components.hass_dyson.const import (
    CONF_DISCOVERY_METHOD,
    CONF_SERIAL_NUMBER,
    DISCOVERY_CLOUD,
)
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

PROBE_404 = (
    "Failed to get clean maps: Client error '404 Not Found' for url "
    "'https://appapi.cp.dyson.com/v1/VS9-GB-HJA0000A/clean-maps'"
)
PROBE_500 = (
    "Failed to get clean maps: Server error '500 Internal Server Error' for url "
    "'https://appapi.cp.dyson.com/v1/VS9-GB-HJA0000A/clean-maps'"
)


@pytest.fixture
def pure_mock_hass():
    """Create a minimal mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    hass.add_job = MagicMock()
    hass.bus = MagicMock()
    hass.config = MagicMock()
    hass.config.country = "US"
    hass.config.language = "en"
    hass.async_add_executor_job = AsyncMock()
    return hass


@pytest.fixture
def mock_config_entry_cloud():
    """Mock config entry for a cloud-discovered robot."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD,
        CONF_SERIAL_NUMBER: "VS9-GB-HJA0000A",
        "username": "test@example.com",
        "auth_token": "test_token_123",
        "capabilities": [],
        "device_category": "robot",
    }
    config_entry.entry_id = "test_entry_probe"
    return config_entry


@pytest.fixture
def coordinator(pure_mock_hass, mock_config_entry_cloud):
    """Create a coordinator with patched parent initialisation."""
    with patch(
        "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__",
        return_value=None,
    ):
        coordinator = DysonDataUpdateCoordinator(
            pure_mock_hass, mock_config_entry_cloud
        )
    coordinator.hass = pure_mock_hass
    coordinator._listeners = {}
    return coordinator


def _client(**get_clean_maps_kwargs):
    """Create a mock cloud client with a configurable get_clean_maps."""
    client = MagicMock()
    client.get_clean_maps = AsyncMock(**get_clean_maps_kwargs)
    return client


class TestAsyncDiscoverMapApiVersion:
    """Test the map API version probe outcomes and caching behaviour."""

    @pytest.mark.asyncio
    async def test_probe_success_returns_and_caches_v1(self, coordinator):
        """A successful v1 probe returns 1 and caches it."""
        client = _client(return_value=[])

        assert await coordinator.async_discover_map_api_version(client) == 1
        assert coordinator._map_api_version == 1

        assert await coordinator.async_discover_map_api_version(client) == 1
        client.get_clean_maps.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_probe_definitive_4xx_returns_and_caches_v2(self, coordinator):
        """A 404 from the v1 endpoint means a v2-only device; 2 is cached."""
        client = _client(side_effect=DysonAPIError(PROBE_404))

        assert await coordinator.async_discover_map_api_version(client) == 2
        assert coordinator._map_api_version == 2

        assert await coordinator.async_discover_map_api_version(client) == 2
        client.get_clean_maps.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_probe_5xx_returns_v2_without_caching(self, coordinator):
        """A 5xx is ambiguous: v2 is used for the call but never cached."""
        client = _client(side_effect=DysonAPIError(PROBE_500))

        assert await coordinator.async_discover_map_api_version(client) == 2
        assert coordinator._map_api_version is None

        assert await coordinator.async_discover_map_api_version(client) == 2
        assert client.get_clean_maps.await_count == 2

    @pytest.mark.asyncio
    async def test_probe_recovers_after_transient_5xx(self, coordinator):
        """A Vis Nav is not locked onto v2 by a transient v1 outage."""
        client = _client(side_effect=[DysonAPIError(PROBE_500), []])

        assert await coordinator.async_discover_map_api_version(client) == 2
        assert await coordinator.async_discover_map_api_version(client) == 1
        assert coordinator._map_api_version == 1

    @pytest.mark.asyncio
    async def test_probe_auth_error_returns_v1_without_caching(self, coordinator):
        """Auth failures are not version signals; nothing is cached."""
        client = _client(side_effect=DysonAuthError("Authentication token expired"))

        assert await coordinator.async_discover_map_api_version(client) == 1
        assert coordinator._map_api_version is None

    @pytest.mark.asyncio
    async def test_probe_non_http_error_returns_v1_without_caching(self, coordinator):
        """Connection/shape errors default to v1 and retry on the next call."""
        client = _client(
            side_effect=DysonAPIError("Expected list in clean-maps response")
        )

        assert await coordinator.async_discover_map_api_version(client) == 1
        assert coordinator._map_api_version is None

        assert await coordinator.async_discover_map_api_version(client) == 1
        assert client.get_clean_maps.await_count == 2

    @pytest.mark.asyncio
    async def test_status_extraction_ignores_digit_groups_in_message(self, coordinator):
        """Digit groups in serials/URLs are not mistaken for HTTP statuses."""
        client = _client(
            side_effect=DysonAPIError(
                "Failed to get clean maps: connection reset for device VS6-EU-521ABCD"
            )
        )

        assert await coordinator.async_discover_map_api_version(client) == 1
        assert coordinator._map_api_version is None
