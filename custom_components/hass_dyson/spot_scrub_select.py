"""Confirmed cleaning mode for all rooms on a Spot+Scrub's current map."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity
from .spot_scrub import MODE_CODES, mode_payload, read_preferences

_LOGGER = logging.getLogger(__name__)


class DysonSpotScrubCleaningModeSelect(DysonEntity, SelectEntity):
    """Apply a cleaning mode to mapped rooms without starting a clean."""

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize a device-scoped selector; no account identifiers are fixed."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_cleaning_mode"
        self._attr_translation_key = "spot_scrub_cleaning_mode"
        self._attr_icon = "mdi:robot-vacuum"
        self._attr_options = list(MODE_CODES)
        self._attr_current_option = None
        self._preferences: dict[str, Any] | None = None
        self._lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        """Only expose usable controls after a successful preference read."""
        return super().available and self._preferences is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose mixed room settings without inventing a common mode."""
        reverse = {code: name for name, code in MODE_CODES.items()}
        rows = (self._preferences or {}).get("room", [])
        return {
            "scope": "all_mapped_rooms",
            "room_modes": {str(row[0]): reverse.get(row[3]) for row in rows},
            "mixed_modes": len({row[3] for row in rows}) > 1,
        }

    def _apply_preferences(self, preferences: dict[str, Any]) -> None:
        self._preferences = preferences
        codes = {row[3] for row in preferences["room"]}
        reverse = {code: name for name, code in MODE_CODES.items()}
        self._attr_current_option = (
            reverse.get(next(iter(codes))) if len(codes) == 1 else None
        )

    async def async_added_to_hass(self) -> None:
        """Refresh app changes periodically; unregister the timer on unload."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_interval(self.hass, self._refresh, timedelta(seconds=60))
        )

    async def _refresh(self, _now: Any) -> None:
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Read the robot without changing preferences or starting it."""
        async with self._lock:
            try:
                _, preferences = await read_preferences(self.coordinator.device)
                self._apply_preferences(preferences)
            except (RuntimeError, ValueError, TimeoutError, AttributeError) as err:
                self._preferences = None
                _LOGGER.debug("Unable to read Spot+Scrub preferences: %s", err)

    async def async_select_option(self, option: str) -> None:
        """Write and verify a mode while the robot is inactive."""
        if option not in MODE_CODES:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="spot_scrub_invalid_mode"
            )
        async with self._lock:
            device = self.coordinator.device
            if device is None or device.robot_state not in {
                "INACTIVE_CHARGING",
                "INACTIVE_CHARGED",
                "FULL_CLEAN_FINISHED",
            }:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="spot_scrub_not_idle"
                )
            try:
                map_id, preferences = await read_preferences(device)
                payload = mode_payload(map_id, preferences, option)
                await device.send_jdm_command("service.set_preference", payload)
                confirmed_map, confirmed = await read_preferences(device)
                self._apply_preferences(confirmed)
                if confirmed_map != map_id or any(
                    row[3] != MODE_CODES[option] for row in confirmed["room"]
                ):
                    raise ValueError(
                        "Robot did not confirm the requested cleaning mode"
                    )
            except (RuntimeError, ValueError, TimeoutError) as err:
                self._preferences = None
                _LOGGER.debug("Spot+Scrub mode change failed: %s", err)
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="spot_scrub_request_failed",
                ) from err
            finally:
                self.async_write_ha_state()
