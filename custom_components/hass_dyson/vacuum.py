"""Vacuum platform for Dyson integration.

This module implements the Home Assistant vacuum platform for Dyson robot vacuum
cleaners, providing comprehensive control including cleaning operations, state
monitoring, battery management, and device-specific features.

Key Features:
    - Start, pause, resume, and stop cleaning operations
    - Real-time state tracking (cleaning, docked, returning, error, etc.)
    - Battery level monitoring via separate battery sensor entity
    - Position tracking during cleaning operations
    - Error and fault condition reporting
    - Cleaning session management with unique identifiers
    - Device-specific power level control (via select entities)

Supported Robot Operations:
    - PAUSE: Suspend current cleaning operation
    - RESUME: Continue paused cleaning operation
    - ABORT: Stop and cancel current cleaning task
    - Status requests: Get current device state
Robot State Management:
    Maps Dyson robot states to Home Assistant vacuum states:
    - FULL_CLEAN_* → STATE_CLEANING/STATE_PAUSED/STATE_RETURNING
    - INACTIVE_* → STATE_DOCKED
    - MAPPING_* → STATE_IDLE/STATE_PAUSED
    - FAULT_* → STATE_ERROR

Device Categories:
    Supports devices with category "robot" as identified by Dyson API.
    Future support may include "vacuum" and "flrc" categories.

MQTT Communication:
    Uses existing DysonDevice MQTT infrastructure with robot-specific
    commands and state parsing. Commands sent to device command topic,
    status received via device status topic.

Position Tracking:
    Provides globalPosition coordinates when available during cleaning
    operations, allowing integration with mapping and location services.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.vacuum import (
    Segment,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_CATEGORY_ROBOT, DOMAIN, ROBOT_STATE_TO_HA_STATE
from .coordinator import DysonDataUpdateCoordinator, TTLCache
from .device_utils import mask_serial
from .entity import DysonEntity

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Clean-maps fetch helper (shared by sensor.py and image.py for vacuum data)
# ---------------------------------------------------------------------------

# Cache cleaning runs for 30 minutes to avoid hammering the cloud API.
_clean_maps_cache: TTLCache = TTLCache(30 * 60)


async def fetch_clean_maps(coordinator: DysonDataUpdateCoordinator) -> list:
    """Fetch recent cleaning runs via libdyson-rest (cached 30 min, newest-first).

    Uses ``AsyncDysonClient.get_clean_maps()`` which requests the dust-map
    blob (``include_dust_map=True``) and returns typed ``CleanRecord`` objects.

    Returns an empty list (or stale cache) on any failure.
    """
    from libdyson_rest.exceptions import DysonAPIError, DysonAuthError

    serial = coordinator.serial_number
    fresh = _clean_maps_cache.get(serial)
    if fresh is not None:
        return fresh

    async with coordinator.async_cloud_client() as client:
        if client is None:
            return _clean_maps_cache.get_stale(serial) or []
        try:
            records = await client.get_clean_maps(serial, include_dust_map=True)
        except (DysonAPIError, DysonAuthError) as err:
            _LOGGER.debug("Failed to fetch clean maps for %s: %s", serial, err)
            return _clean_maps_cache.get_stale(serial) or []

    # Newest-first: sort by earliest timeline event timestamp.
    records.sort(
        key=lambda c: min(
            (e.time for e in c.timeline if e.time),
            default="",
        ),
        reverse=True,
    )
    _clean_maps_cache.set(serial, records)
    return records


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dyson vacuum platform entities.

    Creates vacuum entities for devices that support robot vacuum functionality,
    specifically devices in the "robot" category as identified by the Dyson API.

    Args:
        hass: Home Assistant instance
        config_entry: Configuration entry for the Dyson integration
        async_add_entities: Callback to add entities to Home Assistant

    Note:
        Only creates vacuum entities for devices with "robot" in device_category.
        This includes Dyson 360 Eye, 360 Heurist, and 360 Vis Nav models.
    """
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Only create vacuum entities for robot devices
    if any(cat == DEVICE_CATEGORY_ROBOT for cat in coordinator.device_category):
        _LOGGER.debug(
            "Setting up vacuum entity for robot device %s", coordinator.serial_number
        )
        async_add_entities([DysonVacuumEntity(coordinator)])
    else:
        _LOGGER.debug(
            "Skipping vacuum entity for non-robot device %s (categories: %s)",
            coordinator.serial_number,
            coordinator.device_category,
        )


class DysonVacuumEntity(DysonEntity, StateVacuumEntity):
    """Dyson robot vacuum entity implementation.

    Provides comprehensive robot vacuum control and monitoring through Home
    Assistant's vacuum platform. Integrates with existing DysonDevice MQTT
    infrastructure for real-time communication with robot vacuum devices.

    Supported Features:
        - PAUSE: Suspend current cleaning operation
        - STOP: Abort current cleaning and return to dock
        - RETURN_HOME: Not directly supported (use stop to abort and return)
        - STATE: Real-time state reporting with detailed status information
        - Battery monitoring is provided by a separate battery sensor entity

    State Mapping:
        Dyson robot states are mapped to Home Assistant vacuum states using
        ROBOT_STATE_TO_HA_STATE constant. Provides detailed state information
        through the extra_state_attributes property.

    Device Information:
        - Model: Determined from device capabilities and category
        - Battery: Monitored via separate battery sensor entity
        - Position: Global coordinates when available
        - Cleaning Session: Unique identifier for current cleaning operation
    """

    _attr_has_entity_name = True
    _attr_name = None  # Use device name as entity name

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the Dyson vacuum entity.

        Args:
            coordinator: DysonDataUpdateCoordinator managing device communication
        """
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_vacuum"

        # Set supported features based on robot capabilities
        # Note: Battery monitoring is now handled by a separate battery sensor
        # to comply with Home Assistant deprecation (HA 2026.8)
        self._attr_supported_features = (
            VacuumEntityFeature.START
            | VacuumEntityFeature.PAUSE
            | VacuumEntityFeature.STOP
            | VacuumEntityFeature.RETURN_HOME
            | VacuumEntityFeature.STATE
        )

        # CLEAN_AREA requires a cloud auth_token to fetch the persistent map
        # (Vis Nav only). Mirror the same guard used in button.py for zone buttons.
        self._has_zone_support: bool = bool(
            coordinator.config_entry.data.get("auth_token")
        )
        if self._has_zone_support:
            self._attr_supported_features |= VacuumEntityFeature.CLEAN_AREA

        _LOGGER.debug(
            "Initialized vacuum entity for %s with features: %s",
            coordinator.serial_number,
            self._attr_supported_features,
        )

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the current activity of the vacuum.

        Maps Dyson robot states to Home Assistant vacuum activities using the
        ROBOT_STATE_TO_HA_STATE mapping. Returns None if device is not
        available or state is unknown.

        Returns:
            HA vacuum activity constant or None if unavailable
        """
        if not self.available or not self.coordinator.device:
            return None

        robot_state = self.coordinator.device.robot_state
        if robot_state is None:
            _LOGGER.debug(
                "Robot state not available for %s", self.coordinator.serial_number
            )
            return None

        ha_activity = ROBOT_STATE_TO_HA_STATE.get(robot_state, VacuumActivity.IDLE)
        _LOGGER.debug(
            "Robot %s state: %s → %s",
            self.coordinator.serial_number,
            robot_state,
            ha_activity,
        )
        return ha_activity

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes for the vacuum.

        Provides detailed robot vacuum information including:
        - raw_state: Original Dyson robot state
        - global_position: Current coordinates [x, y] if available
        - full_clean_type: Type of cleaning operation (immediate, scheduled, etc.)
        - clean_id: Unique identifier for current cleaning session

        Returns:
            Dictionary of additional state attributes
        """
        if not self.available or not self.coordinator.device:
            return {}

        device = self.coordinator.device
        attributes: dict[str, Any] = {}

        # Raw robot state for debugging and advanced automations
        if device.robot_state:
            attributes["raw_state"] = device.robot_state

        # Position information during cleaning
        if device.robot_global_position:
            attributes["global_position"] = device.robot_global_position

        # Cleaning operation details
        if device.robot_full_clean_type:
            attributes["full_clean_type"] = device.robot_full_clean_type

        if device.robot_clean_id:
            attributes["clean_id"] = device.robot_clean_id

        _LOGGER.debug(
            "Robot %s attributes: %s", self.coordinator.serial_number, attributes
        )
        return attributes

    async def async_pause(self) -> None:
        """Pause the vacuum cleaning operation.

        Sends PAUSE command to robot vacuum via MQTT. Robot will suspend
        current cleaning operation and remain in place. Cleaning can be
        resumed using async_start().

        Raises:
            HomeAssistantError: If device is not available or command fails
        """
        if not self.available or not self.coordinator.device:
            raise HomeAssistantError("Device not available for pause command")

        _LOGGER.info(
            "Pausing robot vacuum %s", mask_serial(self.coordinator.serial_number)
        )

        try:
            await self.coordinator.device.robot_pause()
            _LOGGER.debug(
                "Pause command sent successfully to %s", self.coordinator.serial_number
            )
        except Exception as ex:
            _LOGGER.error(
                "Failed to pause robot vacuum %s: %s",
                self.coordinator.serial_number,
                ex,
            )
            raise HomeAssistantError(f"Failed to pause vacuum: {ex}") from ex

    async def async_start(self) -> None:
        """Start a new clean (if docked) or resume a paused clean."""
        if not self.available or not self.coordinator.device:
            raise HomeAssistantError("Device not available for start command")

        device = self.coordinator.device
        robot_state = device.robot_state or ""

        # Anything in an INACTIVE_* / FULL_CLEAN_FINISHED / FAULT_ON_DOCK
        # state means the robot isn't mid-clean, so vacuum.start must begin a
        # new cycle rather than send RESUME (which the device would ignore).
        dock_states = {
            "INACTIVE_CHARGED",
            "INACTIVE_CHARGING",
            "INACTIVE_DISCHARGING",
            "FULL_CLEAN_FINISHED",
            "FAULT_ON_DOCK",
        }
        start_new = robot_state in dock_states

        _LOGGER.info(
            "vacuum.start on %s: state=%s → %s",
            self.coordinator.serial_number,
            robot_state,
            "START new clean" if start_new else "RESUME paused clean",
        )

        try:
            if start_new:
                await device.robot_start_clean(cleaning_mode="global")
            else:
                await device.robot_resume()
        except Exception as ex:
            _LOGGER.error(
                "Failed to start/resume robot vacuum %s: %s",
                self.coordinator.serial_number,
                ex,
            )
            raise HomeAssistantError(f"Failed to start vacuum: {ex}") from ex

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum and return to dock.

        Sends ABORT command to robot vacuum via MQTT. Robot will stop
        current operation and return to charging dock. This cancels
        any ongoing cleaning session.

        Args:
            **kwargs: Additional arguments (currently unused)

        Raises:
            HomeAssistantError: If device is not available or command fails
        """
        if not self.available or not self.coordinator.device:
            raise HomeAssistantError("Device not available for stop command")

        _LOGGER.info(
            "Stopping robot vacuum %s", mask_serial(self.coordinator.serial_number)
        )

        try:
            await self.coordinator.device.robot_abort()
            _LOGGER.debug(
                "Abort command sent successfully to %s", self.coordinator.serial_number
            )
        except Exception as ex:
            _LOGGER.error(
                "Failed to stop robot vacuum %s: %s", self.coordinator.serial_number, ex
            )
            raise HomeAssistantError(f"Failed to stop vacuum: {ex}") from ex

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return vacuum to charging dock.

        Currently implemented as alias to async_stop() since ABORT command
        causes robot to return to dock. Future implementation may include
        a specific return-to-dock command if available in robot firmware.

        Args:
            **kwargs: Additional arguments (currently unused)

        Raises:
            HomeAssistantError: If device is not available or command fails
        """
        _LOGGER.debug(
            "Return to base requested for %s, using stop/abort command",
            self.coordinator.serial_number,
        )
        await self.async_stop(**kwargs)

    async def async_get_segments(self) -> list[Segment]:
        """Return the cleanable segments (zones) from the Vis Nav persistent map.

        Called by Home Assistant when the user opens the "Map vacuum segments to
        areas" dialog in entity settings. Returns fully up-to-date zone information
        fetched from the Dyson cloud via the cached persistent-map metadata.

        Only meaningful for Vis Nav robots that have a cloud auth_token. Other
        robot models will never reach this method because CLEAN_AREA is not added
        to their supported_features.

        Returns:
            List of Segment objects, one per zone in the active persistent map.
            Empty list if no map is available yet.

        Raises:
            HomeAssistantError: If the cloud fetch fails with no stale cache.
        """
        # Lazy import to avoid a circular dependency between vacuum.py and services.py.
        from .services import _fetch_persistent_map_metadata

        try:
            maps = await _fetch_persistent_map_metadata(self.coordinator)
        except HomeAssistantError:
            _LOGGER.warning(
                "Could not fetch persistent map for %s; returning empty segment list",
                self.coordinator.serial_number,
            )
            return []

        segments: list[Segment] = []
        for pmap in maps:
            for zone in pmap.zones:
                if not zone.id:
                    continue
                segments.append(Segment(id=zone.id, name=str(zone.name or zone.id)))

        _LOGGER.debug(
            "Returning %d segments for %s",
            len(segments),
            self.coordinator.serial_number,
        )
        return segments

    async def async_clean_segments(self, segment_ids: list[str], **kwargs: Any) -> None:
        """Clean the specified segments by their IDs.

        Called by Home Assistant's ``vacuum.clean_area`` action after resolving
        the targeted HA areas to Dyson zone IDs using the saved area mapping.

        Args:
            segment_ids: List of Dyson zone IDs to clean.
            **kwargs: Additional arguments (currently unused).

        Raises:
            HomeAssistantError: If the device is unavailable, no map is found,
                or the MQTT command fails.
        """
        if not self.available or not self.coordinator.device:
            raise HomeAssistantError("Device not available for zone clean command")

        # Lazy import to avoid circular dependency.
        from .services import _fetch_persistent_map_metadata

        maps = await _fetch_persistent_map_metadata(self.coordinator)
        if not maps:
            raise HomeAssistantError(
                f"No persistent maps available for {self.coordinator.serial_number} — "
                "has the robot completed its initial map run?"
            )

        # Use the first (most-recently-visited) map — mirrors services.py behaviour.
        pmap = maps[0]
        cleaning_programme: dict[str, Any] = {
            "persistentMapId": pmap.id,
            "orderedZones": [],
            "unorderedZones": segment_ids,
        }
        # zonesDefinitionLastUpdatedDate is required for the device to honour
        # a zoneConfigured request; without it the robot silently falls back to
        # a global (whole-house) clean.
        zdlud = getattr(pmap, "zones_definition_last_updated_date", None)
        if zdlud:
            cleaning_programme["zonesDefinitionLastUpdatedDate"] = zdlud

        _LOGGER.info(
            "vacuum.clean_area on %s: segments=%s (map %s)",
            self.coordinator.serial_number,
            segment_ids,
            pmap.id,
        )
        try:
            await self.coordinator.device.robot_start_clean(
                cleaning_mode="zoneConfigured",
                full_clean_type="immediate",
                cleaning_programme=cleaning_programme,
            )
        except Exception as ex:
            _LOGGER.error(
                "Failed to start zone clean on %s: %s",
                self.coordinator.serial_number,
                ex,
            )
            raise HomeAssistantError(f"Failed to start zone clean: {ex}") from ex

    def _handle_coordinator_update(self) -> None:
        """Handle coordinator data update; detect segment changes for repair issues.

        Compares the segment IDs currently in the cached persistent map against
        those stored in ``last_seen_segments`` (written by HA when the user saves
        the area mapping). Creates a repair issue when they differ so the user
        knows to re-configure the mapping.

        The persistent-map cache is read synchronously (no I/O) — if the cache
        is empty (first run, or TTL expired), the check is skipped for this cycle.
        """
        super()._handle_coordinator_update()

        if not self._has_zone_support:
            return

        # registry_entry is required to access last_seen_segments (stored in options).
        if self.registry_entry is None:
            return

        last_seen = self.last_seen_segments
        if last_seen is None:
            # No mapping has been configured yet; nothing to compare against.
            return

        # Read from cache only — no network call during a coordinator tick.
        from .services import _persistent_map_cache

        cached_maps = _persistent_map_cache.get(self.coordinator.serial_number)
        if cached_maps is None:
            # Cache miss; skip this cycle.
            return

        current_ids = {
            zone.id for pmap in cached_maps for zone in pmap.zones if zone.id
        }
        last_seen_ids = {seg.id for seg in last_seen}

        if current_ids != last_seen_ids:
            _LOGGER.info(
                "Segment change detected for %s: was %s, now %s — creating repair issue",
                self.coordinator.serial_number,
                last_seen_ids,
                current_ids,
            )
            self.async_create_segments_issue()
