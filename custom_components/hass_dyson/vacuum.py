"""Vacuum platform for Dyson integration.

This module implements the Home Assistant vacuum platform for Dyson robot vacuum
cleaners, providing comprehensive control including cleaning operations, state
monitoring, battery management, and device-specific features.

Key Features:
    - Start, pause, resume, and stop cleaning operations
    - Real-time state tracking (cleaning, docked, returning, error, etc.)
    - Battery level monitoring and charging status
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
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_CATEGORY_ROBOT, DOMAIN, ROBOT_STATE_TO_HA_STATE
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity

_LOGGER = logging.getLogger(__name__)


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
        - BATTERY: Battery level monitoring and charging status

    State Mapping:
        Dyson robot states are mapped to Home Assistant vacuum states using
        ROBOT_STATE_TO_HA_STATE constant. Provides detailed state information
        through the extra_state_attributes property.

    Device Information:
        - Model: Determined from device capabilities and category
        - Battery: Percentage level with charging status
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
        self._attr_supported_features = (
            VacuumEntityFeature.PAUSE
            | VacuumEntityFeature.STOP
            | VacuumEntityFeature.STATE
            | VacuumEntityFeature.BATTERY
        )

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
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum.

        Provides battery percentage from 0-100 if available. Returns None
        if device is not available or battery level is not reported.

        Returns:
            Battery percentage (0-100) or None if unavailable
        """
        if not self.available or not self.coordinator.device:
            return None

        battery = self.coordinator.device.robot_battery_level
        if battery is not None:
            _LOGGER.debug(
                "Robot %s battery level: %d%%", self.coordinator.serial_number, battery
            )
        return battery

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
        attributes = {}

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

        _LOGGER.info("Pausing robot vacuum %s", self.coordinator.serial_number)

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
        """Start or resume vacuum cleaning operation.

        If robot is paused, sends RESUME command to continue cleaning.
        If robot is idle/docked, this would typically start a new cleaning
        cycle, but the specific behavior depends on robot state and model.

        Note:
            Starting new cleaning cycles may require additional commands
            not yet implemented. This primarily serves as resume functionality.

        Raises:
            HomeAssistantError: If device is not available or command fails
        """
        if not self.available or not self.coordinator.device:
            raise HomeAssistantError("Device not available for start command")

        _LOGGER.info(
            "Starting/resuming robot vacuum %s", self.coordinator.serial_number
        )

        try:
            await self.coordinator.device.robot_resume()
            _LOGGER.debug(
                "Resume command sent successfully to %s", self.coordinator.serial_number
            )
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

        _LOGGER.info("Stopping robot vacuum %s", self.coordinator.serial_number)

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
