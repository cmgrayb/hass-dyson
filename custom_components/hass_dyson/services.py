"""Service handlers for Dyson integration."""

from __future__ import annotations

import json
import logging
from datetime import datetime

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    SERVICE_CANCEL_SLEEP_TIMER,
    SERVICE_FETCH_ACCOUNT_DATA,
    SERVICE_RESET_FILTER,
    SERVICE_SCHEDULE_OPERATION,
    SERVICE_SET_OSCILLATION_ANGLES,
    SERVICE_SET_SLEEP_TIMER,
    SLEEP_TIMER_MAX,
    SLEEP_TIMER_MIN,
)
from .coordinator import DysonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Service schema definitions
SERVICE_SET_SLEEP_TIMER_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("minutes"): vol.All(vol.Coerce(int), vol.Range(min=SLEEP_TIMER_MIN, max=SLEEP_TIMER_MAX)),
    }
)

SERVICE_CANCEL_SLEEP_TIMER_SCHEMA = vol.Schema({vol.Required("device_id"): str})

SERVICE_SCHEDULE_OPERATION_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("operation"): vol.In(["turn_on", "turn_off", "set_speed", "toggle_auto_mode"]),
        vol.Required("schedule_time"): str,  # ISO format datetime
        vol.Optional("parameters"): str,  # JSON string
    }
)

SERVICE_SET_OSCILLATION_ANGLES_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("lower_angle"): vol.All(vol.Coerce(int), vol.Range(min=0, max=350)),
        vol.Required("upper_angle"): vol.All(vol.Coerce(int), vol.Range(min=0, max=350)),
    }
)

SERVICE_FETCH_ACCOUNT_DATA_SCHEMA = vol.Schema({vol.Optional("device_id"): str})

SERVICE_RESET_FILTER_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("filter_type"): vol.In(["hepa", "carbon", "both"]),
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Dyson integration."""

    async def handle_set_sleep_timer(call: ServiceCall) -> None:
        """Handle set sleep timer service call."""
        device_id = call.data["device_id"]
        minutes = call.data["minutes"]

        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if not coordinator or not coordinator.device:
            raise ServiceValidationError(f"Device {device_id} not found or not available")

        try:
            # Convert minutes to sleep timer format (device expects specific encoding)
            await coordinator.device.set_sleep_timer(minutes)
            _LOGGER.info("Set sleep timer to %d minutes for device %s", minutes, coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to set sleep timer for device %s: %s", coordinator.serial_number, err)
            raise HomeAssistantError(f"Failed to set sleep timer: {err}") from err

    async def handle_cancel_sleep_timer(call: ServiceCall) -> None:
        """Handle cancel sleep timer service call."""
        device_id = call.data["device_id"]

        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if not coordinator or not coordinator.device:
            raise ServiceValidationError(f"Device {device_id} not found or not available")

        try:
            # Cancel timer by setting to 0
            await coordinator.device.set_sleep_timer(0)
            _LOGGER.info("Cancelled sleep timer for device %s", coordinator.serial_number)
        except Exception as err:
            _LOGGER.error("Failed to cancel sleep timer for device %s: %s", coordinator.serial_number, err)
            raise HomeAssistantError(f"Failed to cancel sleep timer: {err}") from err

    async def handle_schedule_operation(call: ServiceCall) -> None:
        """Handle schedule operation service call (experimental)."""
        device_id = call.data["device_id"]
        operation = call.data["operation"]
        schedule_time_str = call.data["schedule_time"]
        parameters_str = call.data.get("parameters")

        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if not coordinator or not coordinator.device:
            raise ServiceValidationError(f"Device {device_id} not found or not available")

        try:
            # Parse schedule time
            schedule_time = datetime.fromisoformat(schedule_time_str.replace("Z", "+00:00"))

            # Parse parameters if provided
            parameters = {}
            if parameters_str:
                parameters = json.loads(parameters_str)

            # For now, just log the scheduled operation (would need proper scheduler implementation)
            _LOGGER.warning(
                "Scheduled operation '%s' for device %s at %s with parameters %s - "
                "Note: Scheduling is experimental and not yet fully implemented",
                operation,
                coordinator.serial_number,
                schedule_time,
                parameters,
            )

        except (ValueError, json.JSONDecodeError) as err:
            raise ServiceValidationError(f"Invalid schedule time or parameters format: {err}") from err
        except Exception as err:
            _LOGGER.error("Failed to schedule operation for device %s: %s", coordinator.serial_number, err)
            raise HomeAssistantError(f"Failed to schedule operation: {err}") from err

    async def handle_set_oscillation_angles(call: ServiceCall) -> None:
        """Handle set oscillation angles service call."""
        device_id = call.data["device_id"]
        lower_angle = call.data["lower_angle"]
        upper_angle = call.data["upper_angle"]

        if lower_angle >= upper_angle:
            raise ServiceValidationError("Lower angle must be less than upper angle")

        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if not coordinator or not coordinator.device:
            raise ServiceValidationError(f"Device {device_id} not found or not available")

        try:
            await coordinator.device.set_oscillation_angles(lower_angle, upper_angle)
            _LOGGER.info(
                "Set oscillation angles %d°-%d° for device %s", lower_angle, upper_angle, coordinator.serial_number
            )
        except Exception as err:
            _LOGGER.error("Failed to set oscillation angles for device %s: %s", coordinator.serial_number, err)
            raise HomeAssistantError(f"Failed to set oscillation angles: {err}") from err

    async def handle_fetch_account_data(call: ServiceCall) -> None:
        """Handle fetch account data service call."""
        device_id = call.data.get("device_id")

        if device_id:
            # Refresh specific device
            coordinator = await _get_coordinator_from_device_id(hass, device_id)
            if not coordinator:
                raise ServiceValidationError(f"Device {device_id} not found")

            try:
                await coordinator.async_refresh()
                _LOGGER.info("Refreshed account data for device %s", coordinator.serial_number)
            except Exception as err:
                _LOGGER.error("Failed to refresh account data for device %s: %s", coordinator.serial_number, err)
                raise HomeAssistantError(f"Failed to refresh account data: {err}") from err
        else:
            # Refresh all devices
            coordinators = [
                coordinator
                for coordinator in hass.data.get(DOMAIN, {}).values()
                if isinstance(coordinator, DysonDataUpdateCoordinator)
            ]

            for coordinator in coordinators:
                try:
                    await coordinator.async_refresh()
                    _LOGGER.debug("Refreshed account data for device %s", coordinator.serial_number)
                except Exception as err:
                    _LOGGER.error("Failed to refresh account data for device %s: %s", coordinator.serial_number, err)

            _LOGGER.info("Refreshed account data for %d devices", len(coordinators))

    async def handle_reset_filter(call: ServiceCall) -> None:
        """Handle reset filter service call."""
        device_id = call.data["device_id"]
        filter_type = call.data["filter_type"]

        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if not coordinator or not coordinator.device:
            raise ServiceValidationError(f"Device {device_id} not found or not available")

        try:
            if filter_type == "hepa":
                await coordinator.device.reset_hepa_filter_life()
                _LOGGER.info("Reset HEPA filter life for device %s", coordinator.serial_number)
            elif filter_type == "carbon":
                await coordinator.device.reset_carbon_filter_life()
                _LOGGER.info("Reset carbon filter life for device %s", coordinator.serial_number)
            elif filter_type == "both":
                await coordinator.device.reset_hepa_filter_life()
                await coordinator.device.reset_carbon_filter_life()
                _LOGGER.info("Reset both filter lives for device %s", coordinator.serial_number)

        except Exception as err:
            _LOGGER.error("Failed to reset %s filter for device %s: %s", filter_type, coordinator.serial_number, err)
            raise HomeAssistantError(f"Failed to reset {filter_type} filter: {err}") from err

    # Register all services
    hass.services.async_register(
        DOMAIN, SERVICE_SET_SLEEP_TIMER, handle_set_sleep_timer, schema=SERVICE_SET_SLEEP_TIMER_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_SLEEP_TIMER, handle_cancel_sleep_timer, schema=SERVICE_CANCEL_SLEEP_TIMER_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, SERVICE_SCHEDULE_OPERATION, handle_schedule_operation, schema=SERVICE_SCHEDULE_OPERATION_SCHEMA
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_OSCILLATION_ANGLES,
        handle_set_oscillation_angles,
        schema=SERVICE_SET_OSCILLATION_ANGLES_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN, SERVICE_FETCH_ACCOUNT_DATA, handle_fetch_account_data, schema=SERVICE_FETCH_ACCOUNT_DATA_SCHEMA
    )

    hass.services.async_register(DOMAIN, SERVICE_RESET_FILTER, handle_reset_filter, schema=SERVICE_RESET_FILTER_SCHEMA)

    _LOGGER.info("Registered Dyson services")


async def async_remove_services(hass: HomeAssistant) -> None:
    """Remove services for Dyson integration."""
    services_to_remove = [
        SERVICE_SET_SLEEP_TIMER,
        SERVICE_CANCEL_SLEEP_TIMER,
        SERVICE_SCHEDULE_OPERATION,
        SERVICE_SET_OSCILLATION_ANGLES,
        SERVICE_FETCH_ACCOUNT_DATA,
        SERVICE_RESET_FILTER,
    ]

    for service in services_to_remove:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)

    _LOGGER.info("Removed Dyson services")


async def _get_coordinator_from_device_id(hass: HomeAssistant, device_id: str) -> DysonDataUpdateCoordinator | None:
    """Get coordinator from device ID."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)

    if not device_entry:
        return None

    # Find the config entry associated with this device
    for config_entry_id in device_entry.config_entries:
        coordinator = hass.data.get(DOMAIN, {}).get(config_entry_id)
        if isinstance(coordinator, DysonDataUpdateCoordinator):
            return coordinator

    return None
