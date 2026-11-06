"""Optional account-owned location sync, independent of BLE connection setup."""

from __future__ import annotations

import asyncio
import math
import struct
from datetime import datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.httpx_client import get_async_client

from .ble_light_cloud import DysonBLELightCloudClient, DysonBLELightCloudError
from .ble_light_protocol import LightAttribute, encode_dst, encode_timezone

if TYPE_CHECKING:
    from .coordinator import DysonBLEDataUpdateCoordinator

_CACHE_KEY = "ble_light_location"


class BLELightLocation:
    """Use the owning account only; a cloud failure never breaks local control."""

    def __init__(self, coordinator: DysonBLEDataUpdateCoordinator) -> None:
        """Own the optional startup task and its cancellation."""
        self._coordinator = coordinator
        self._task: asyncio.Task[None] | None = None
        self._attempted = False

    def start(self) -> None:
        """Restore once, in the background, after the first successful connect."""
        if not self._attempted:
            self._attempted = True
            self._task = asyncio.create_task(
                self._restore(), name="dyson-light-location"
            )

    async def close(self) -> None:
        """Await cancellation on config-entry unload."""
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    def _account_value(self, key: str) -> Any:
        entry = self._coordinator._config_entry
        parent_id = entry.data.get("parent_entry_id")
        parent = (
            self._coordinator.hass.config_entries.async_get_entry(parent_id)
            if parent_id
            else None
        )
        # A reauthenticated parent takes precedence over a stale copied token.
        return parent.data.get(key) if parent is not None else entry.data.get(key)

    async def _restore(self) -> None:
        try:
            async with asyncio.timeout(30):
                device = self._coordinator.ble_device
                while device is not None and not device.lighting.available:
                    if not device.is_connected:
                        return
                    await asyncio.sleep(0.1)
                await self.sync(use_cache=True)
        except (HomeAssistantError, TimeoutError, OSError):
            # Optional cloud metadata must not stop the connection lifecycle.
            return

    async def sync(self, *, use_cache: bool = False) -> None:
        """Apply saved location without changing any Dyson cloud configuration."""
        coordinator = self._coordinator
        entry = coordinator._config_entry
        location = entry.data.get(_CACHE_KEY) if use_cache else None
        if location is None:
            token = self._account_value("auth_token")
            if not token:
                raise HomeAssistantError(
                    "A Dyson account is needed to sync lamp location"
                )
            cloud = DysonBLELightCloudClient(
                token,
                self._account_value("country") or "US",
                client=get_async_client(coordinator.hass),
            )
            try:
                async with asyncio.timeout(20):
                    location = dict(
                        await cloud.fetch_location(coordinator.serial_number)
                    )
                    location["timezone"] = await cloud.fetch_timezone(
                        coordinator.serial_number
                    )
                    location["dst"] = (
                        await cloud.fetch_dst(location["timezone"])
                    ).hex()
            except DysonBLELightCloudError as err:
                raise HomeAssistantError(str(err)) from None
            except TimeoutError:
                raise HomeAssistantError("Dyson location sync timed out") from None
        try:
            offset = datetime.now(ZoneInfo(location["timezone"])).utcoffset()
            if offset is None or any(
                type(location[key]) is bool for key in ("latitude", "longitude")
            ):
                raise ValueError
            latitude, longitude = (
                float(location["latitude"]),
                float(location["longitude"]),
            )
            if not (
                math.isfinite(latitude)
                and -90 <= latitude <= 90
                and math.isfinite(longitude)
                and -180 <= longitude <= 180
            ):
                raise ValueError
            values: dict[int, bytes] = {
                LightAttribute.LATITUDE: struct.pack("<d", latitude),
                LightAttribute.LONGITUDE: struct.pack("<d", longitude),
                LightAttribute.TIMEZONE: encode_timezone(int(offset.total_seconds())),
                LightAttribute.DAYLIGHT_SAVING_ADJUSTMENT: encode_dst(
                    bytes.fromhex(location["dst"])
                ),
            }
        except (ValueError, KeyError, TypeError, OverflowError):
            raise HomeAssistantError("Invalid saved lamp location") from None
        device = coordinator.ble_device
        if device is None or not device.is_connected:
            raise HomeAssistantError("Lamp disconnected")
        await device.lighting.set_attributes(values)
        if entry.data.get(_CACHE_KEY) != location:
            coordinator.hass.config_entries.async_update_entry(
                entry, data={**entry.data, _CACHE_KEY: location}
            )
