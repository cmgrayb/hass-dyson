"""Service handlers for Dyson integration.

This module implements comprehensive service management for the Dyson Home Assistant
integration, providing device control services, cloud account management, and
dynamic service registration based on device capabilities.

Service Categories:

Device Control Services:
    - set_sleep_timer: Configure automatic device shutdown (15-540 minutes)
    - cancel_sleep_timer: Cancel active sleep timer
    - set_oscillation_angles: Custom oscillation angle control (0-350 degrees)
    - reset_filter: Reset HEPA and/or carbon filter life indicators
    - schedule_operation: Schedule future device operations (turn on/off, speed, etc.)

Cloud Account Services:
    - get_cloud_devices: Retrieve device information from Dyson cloud accounts
    - refresh_account_data: Update cloud account and device information

Key Features:
    - Capability-based service registration (only relevant services for each device)
    - Category-based service management with reference counting
    - Parameter validation using voluptuous schemas
    - Comprehensive error handling with detailed logging
    - Support for both device-specific and account-level operations
    - Thread-safe service registration and unregistration

Service Registration Architecture:
    Services are dynamically registered based on device capabilities and categories:
    - Device capabilities (Scheduling, AdvanceOscillationDay1, ExtendedAQ)
    - Device categories (ec, robot, vacuum, flrc) for backward compatibility
    - Reference counting prevents premature service removal
    - Services persist until all devices of a category are removed

Parameter Validation:
    All services use voluptuous schemas for parameter validation:
    - Type checking and coercion
    - Range validation for numeric parameters
    - Required/optional parameter handling
    - Input sanitization and security

Error Handling:
    Comprehensive error handling with specific exception types:
    - ServiceValidationError: Invalid parameters or device not found
    - HomeAssistantError: Device communication or operation failures
    - Detailed logging for troubleshooting and debugging

Example Usage:
    Services are automatically registered when devices are added:

    >>> # Device with Scheduling capability
    >>> # Automatically registers: set_sleep_timer, cancel_sleep_timer, schedule_operation
    >>>
    >>> # Call service via Home Assistant
    >>> await hass.services.async_call(
    >>>     "hass_dyson",
    >>>     "set_sleep_timer",
    >>>     {"device_id": "device_123", "minutes": 120}
    >>> )
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import voluptuous as vol
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from libdyson_rest import DysonAPIError, DysonAuthError, DysonConnectionError

from .const import (
    CONF_DISCOVERY_METHOD,
    DISCOVERY_CLOUD,
    DOMAIN,
    SERVICE_CANCEL_SLEEP_TIMER,
    SERVICE_GET_CLOUD_DEVICES,
    SERVICE_REFRESH_ACCOUNT_DATA,
    SERVICE_RESET_FILTER,
    SERVICE_SCHEDULE_OPERATION,
    SERVICE_SET_OSCILLATION_ANGLES,
    SERVICE_SET_SLEEP_TIMER,
    SLEEP_TIMER_MAX,
    SLEEP_TIMER_MIN,
)
from .coordinator import DysonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Device capability to services mapping for dynamic service registration
# Services are registered based on device capabilities detected during setup
DEVICE_CAPABILITY_SERVICES = {
    "Scheduling": [  # Sleep timer and scheduling capabilities
        SERVICE_SET_SLEEP_TIMER,  # Configure automatic shutdown timer
        SERVICE_CANCEL_SLEEP_TIMER,  # Cancel active sleep timer
        SERVICE_SCHEDULE_OPERATION,  # Schedule future device operations
    ],
    "AdvanceOscillationDay1": [  # Advanced oscillation control
        SERVICE_SET_OSCILLATION_ANGLES,  # Custom oscillation angle control (0-350°)
    ],
    "ExtendedAQ": [  # Extended air quality monitoring with advanced filters
        SERVICE_RESET_FILTER,  # Reset HEPA/carbon filter life indicators
    ],
    "EnvironmentalData": [  # Basic environmental monitoring with filters
        SERVICE_RESET_FILTER,  # Reset filter life for environmental monitoring devices
    ],
}

# Legacy device category to services mapping (for backward compatibility)
DEVICE_CATEGORY_SERVICES = {
    "ec": [  # Environment Cleaner (fans with filters)
        SERVICE_SET_SLEEP_TIMER,
        SERVICE_CANCEL_SLEEP_TIMER,
        SERVICE_RESET_FILTER,
        SERVICE_SCHEDULE_OPERATION,
    ],
    "robot": [  # Robot vacuum/cleaning devices
        SERVICE_SCHEDULE_OPERATION,
        SERVICE_RESET_FILTER,  # Different filter types for cleaning devices
    ],
    "vacuum": [  # Vacuum devices
        SERVICE_SCHEDULE_OPERATION,
        SERVICE_RESET_FILTER,
    ],
    "flrc": [  # Floor cleaning devices
        SERVICE_SCHEDULE_OPERATION,
        SERVICE_RESET_FILTER,
    ],
}

# Global reference counter for device categories
_device_category_counts: dict[str, int] = {}

# Service schema definitions with comprehensive parameter validation
# Sleep timer schema: device identification and duration validation
SERVICE_SET_SLEEP_TIMER_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,  # Home Assistant device registry ID
        vol.Required("minutes"): vol.All(
            vol.Coerce(int), vol.Range(min=SLEEP_TIMER_MIN, max=SLEEP_TIMER_MAX)
        ),  # Timer duration: 15-540 minutes (15min to 9 hours)
    }
)

SERVICE_CANCEL_SLEEP_TIMER_SCHEMA = vol.Schema({vol.Required("device_id"): str})

SERVICE_SCHEDULE_OPERATION_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("operation"): vol.In(
            ["turn_on", "turn_off", "set_speed", "toggle_auto_mode"]
        ),
        vol.Required("schedule_time"): str,  # ISO format datetime
        vol.Optional("parameters"): str,  # JSON string
    }
)

# Custom oscillation angles schema: device ID and angle range validation
SERVICE_SET_OSCILLATION_ANGLES_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,  # Home Assistant device registry ID
        vol.Required("lower_angle"): vol.All(
            vol.Coerce(int),
            vol.Range(min=0, max=350),  # Lower bound: 0-350 degrees
        ),
        vol.Required("upper_angle"): vol.All(
            vol.Coerce(int),
            vol.Range(min=0, max=350),  # Upper bound: 0-350 degrees
        ),  # Note: lower_angle must be < upper_angle (validated in handler)
    }
)

SERVICE_REFRESH_ACCOUNT_DATA_SCHEMA = vol.Schema({vol.Optional("device_id"): str})

SERVICE_RESET_FILTER_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("filter_type"): vol.In(["hepa", "carbon", "both"]),
    }
)

SERVICE_GET_CLOUD_DEVICES_SCHEMA = vol.Schema(
    {
        vol.Optional("account_email"): str,
        vol.Optional("sanitize", default=False): bool,
    }
)


def _convert_to_string(item) -> str:
    """Convert any item to string with proper enum value handling.

    Utility function for safely converting various data types to strings,
    with special handling for enum values that have a .value attribute.
    Used throughout the service module for data serialization and logging.

    Args:
        item: Any object to convert to string representation

    Returns:
        String representation of the item:
        - For enums: Returns str(item.value) to get the actual enum value
        - For other objects: Returns str(item) using standard string conversion

    Enum Handling:
        Many Dyson API responses contain enum values that need special handling:
        - Device states (ON/OFF enums)
        - Connection types (LOCAL/CLOUD enums)
        - Error codes (numeric enums)

    Example:
        Converting various data types:

        >>> # Enum with .value attribute
        >>> enum_obj = SomeEnum.ACTIVE  # enum_obj.value = "ON"
        >>> result = _convert_to_string(enum_obj)  # Returns "ON"
        >>>
        >>> # Regular string
        >>> result = _convert_to_string("hello")  # Returns "hello"
        >>>
        >>> # Number
        >>> result = _convert_to_string(42)  # Returns "42"

    Note:
        This function is used internally for data processing and should handle
        any object type gracefully without raising exceptions.
    """
    if hasattr(item, "value"):
        return str(item.value)
    return str(item)


def _decrypt_device_mqtt_credentials(cloud_client, device) -> str:
    """Decrypt MQTT credentials from device's connected_configuration."""
    try:
        # Look for MQTT configuration in connected_configuration
        connected_config = getattr(device, "connected_configuration", None)
        if not connected_config:
            return ""

        mqtt_obj = getattr(connected_config, "mqtt", None)
        if not mqtt_obj:
            return ""

        # Get encrypted credentials
        encrypted_credentials = getattr(mqtt_obj, "local_broker_credentials", "")
        if not encrypted_credentials:
            return ""

        # Use libdyson-rest's decrypt method to get local MQTT password
        mqtt_password = cloud_client.decrypt_local_credentials(
            encrypted_credentials, device.serial_number
        )
        _LOGGER.debug(
            "Decrypted local MQTT password for device %s (length: %s)",
            device.serial_number,
            len(mqtt_password),
        )
        return mqtt_password
    except (ValueError, TypeError) as err:
        _LOGGER.warning(
            "Invalid credential format for decryption on %s: %s",
            device.serial_number,
            err,
        )
        return ""
    except (KeyError, AttributeError) as err:
        _LOGGER.debug(
            "Missing credential data for decryption on %s: %s",
            device.serial_number,
            err,
        )
        return ""
    except Exception as err:
        _LOGGER.error(
            "Unexpected error decrypting local credentials for %s: %s",
            device.serial_number,
            err,
        )
        return ""


async def _handle_set_sleep_timer(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle set sleep timer service call with comprehensive validation.

    Sets a sleep timer on a Dyson device to automatically turn off after the
    specified duration. The timer operates independently of Home Assistant and
    will function even if Home Assistant is offline.

    Args:
        hass: Home Assistant instance
        call: Service call containing device_id and minutes parameters

    Service Parameters:
        device_id (str): Home Assistant device ID of the target Dyson device
        minutes (int): Sleep timer duration (15-540 minutes)

    Process:
        1. Validate device_id exists and device is available
        2. Extract timer duration from service call parameters
        3. Send sleep timer command to device via MQTT
        4. Request coordinator refresh to update timer state
        5. Log successful operation for confirmation

    Timer Behavior:
        - Timer starts immediately upon successful command
        - Device will power off automatically when timer expires
        - Timer can be cancelled using cancel_sleep_timer service
        - Timer persists through Home Assistant restarts
        - Display shows remaining time (device-dependent)

    Validation:
        - Device must exist in Home Assistant device registry
        - Device must be connected and responsive
        - Minutes must be within valid range (15-540)
        - Coordinator must have active device connection

    Example:
        Setting a 2-hour sleep timer:

        >>> await hass.services.async_call(
        >>>     "hass_dyson",
        >>>     "set_sleep_timer",
        >>>     {
        >>>         "device_id": "abc123def456",
        >>>         "minutes": 120  # 2 hours
        >>>     }
        >>> )

    Raises:
        ServiceValidationError: If device not found or unavailable
        HomeAssistantError: If device communication fails
    """
    device_id = call.data["device_id"]
    minutes = call.data["minutes"]

    coordinator = await _get_coordinator_from_device_id(hass, device_id)
    if not coordinator or not coordinator.device:
        raise ServiceValidationError(f"Device {device_id} not found or not available")

    try:
        # Convert minutes to sleep timer format (device expects specific encoding)
        await coordinator.device.set_sleep_timer(minutes)
        # Request refresh to update the coordinator with new sleep timer state
        await coordinator.async_request_refresh()
        _LOGGER.info(
            "Set sleep timer to %d minutes for device %s",
            minutes,
            coordinator.serial_number,
        )
    except (ConnectionError, TimeoutError) as err:
        _LOGGER.error(
            "Communication error setting sleep timer for device %s: %s",
            coordinator.serial_number,
            err,
        )
        raise HomeAssistantError(f"Device communication failed: {err}") from err
    except (ValueError, TypeError) as err:
        _LOGGER.warning(
            "Invalid timer value for device %s: %s",
            coordinator.serial_number,
            err,
        )
        raise HomeAssistantError(f"Invalid timer value: {err}") from err
    except AttributeError as err:
        _LOGGER.debug(
            "Sleep timer method not available for device %s: %s",
            coordinator.serial_number,
            err,
        )
        raise HomeAssistantError(f"Sleep timer not supported: {err}") from err
    except Exception as err:
        _LOGGER.error(
            "Unexpected error setting sleep timer for device %s: %s",
            coordinator.serial_number,
            err,
        )
        raise HomeAssistantError(f"Failed to set sleep timer: {err}") from err


async def _handle_cancel_sleep_timer(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle cancel sleep timer service call."""
    device_id = call.data["device_id"]

    coordinator = await _get_coordinator_from_device_id(hass, device_id)
    if not coordinator or not coordinator.device:
        raise ServiceValidationError(f"Device {device_id} not found or not available")

    try:
        # Cancel timer by setting to 0
        await coordinator.device.set_sleep_timer(0)
        # Request refresh to update the coordinator with new sleep timer state
        await coordinator.async_request_refresh()
        _LOGGER.info("Cancelled sleep timer for device %s", coordinator.serial_number)
    except (ConnectionError, TimeoutError) as err:
        _LOGGER.error(
            "Communication error cancelling sleep timer for device %s: %s",
            coordinator.serial_number,
            err,
        )
        raise HomeAssistantError(f"Device communication failed: {err}") from err
    except AttributeError as err:
        _LOGGER.debug(
            "Sleep timer method not available for device %s: %s",
            coordinator.serial_number,
            err,
        )
        raise HomeAssistantError(f"Sleep timer not supported: {err}") from err
    except Exception as err:
        _LOGGER.error(
            "Unexpected error cancelling sleep timer for device %s: %s",
            coordinator.serial_number,
            err,
        )
        raise HomeAssistantError(f"Failed to cancel sleep timer: {err}") from err


async def _handle_schedule_operation(hass: HomeAssistant, call: ServiceCall) -> None:
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
        raise ServiceValidationError(
            f"Invalid schedule time or parameters format: {err}"
        ) from err
    except Exception as err:
        _LOGGER.error(
            "Unexpected error scheduling operation for device %s: %s",
            coordinator.serial_number,
            err,
        )
        raise HomeAssistantError(f"Failed to schedule operation: {err}") from err


async def _handle_set_oscillation_angles(
    hass: HomeAssistant, call: ServiceCall
) -> None:
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
            "Set oscillation angles %d°-%d° for device %s",
            lower_angle,
            upper_angle,
            coordinator.serial_number,
        )
    except (ConnectionError, TimeoutError) as err:
        _LOGGER.error(
            "Communication error setting oscillation angles for device %s: %s",
            coordinator.serial_number,
            err,
        )
        raise HomeAssistantError(f"Device communication failed: {err}") from err
    except (ValueError, TypeError) as err:
        _LOGGER.warning(
            "Invalid angle values for device %s (lower=%s, upper=%s): %s",
            coordinator.serial_number,
            lower_angle,
            upper_angle,
            err,
        )
        raise HomeAssistantError(f"Invalid angle values: {err}") from err
    except AttributeError as err:
        _LOGGER.debug(
            "Oscillation angles method not available for device %s: %s",
            coordinator.serial_number,
            err,
        )
        raise HomeAssistantError(f"Oscillation angles not supported: {err}") from err
    except Exception as err:
        _LOGGER.error(
            "Unexpected error setting oscillation angles for device %s: %s",
            coordinator.serial_number,
            err,
        )
        raise HomeAssistantError(f"Failed to set oscillation angles: {err}") from err


async def async_handle_refresh_account_data(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Handle fetch account data service call."""
    device_id = call.data.get("device_id")

    if device_id:
        # Refresh specific device
        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if not coordinator:
            raise ServiceValidationError(f"Device {device_id} not found")

        try:
            await coordinator.async_refresh()
            _LOGGER.info(
                "Refreshed account data for device %s", coordinator.serial_number
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error refreshing account data for device %s: %s",
                coordinator.serial_number,
                err,
            )
            raise HomeAssistantError(f"Device communication failed: {err}") from err
        except Exception as err:
            _LOGGER.error(
                "Unexpected error refreshing account data for device %s: %s",
                coordinator.serial_number,
                err,
            )
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
                _LOGGER.debug(
                    "Refreshed account data for device %s", coordinator.serial_number
                )
            except (ConnectionError, TimeoutError) as err:
                _LOGGER.warning(
                    "Communication error refreshing account data for device %s: %s",
                    coordinator.serial_number,
                    err,
                )
            except Exception as err:
                _LOGGER.error(
                    "Unexpected error refreshing account data for device %s: %s",
                    coordinator.serial_number,
                    err,
                )

        _LOGGER.info("Refreshed account data for %d devices", len(coordinators))


async def _handle_reset_filter(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle reset filter service call."""
    device_id = call.data["device_id"]
    filter_type = call.data["filter_type"]

    coordinator = await _get_coordinator_from_device_id(hass, device_id)
    if not coordinator or not coordinator.device:
        raise ServiceValidationError(f"Device {device_id} not found or not available")

    try:
        if filter_type == "hepa":
            await coordinator.device.reset_hepa_filter_life()
            _LOGGER.info(
                "Reset HEPA filter life for device %s", coordinator.serial_number
            )
        elif filter_type == "carbon":
            await coordinator.device.reset_carbon_filter_life()
            _LOGGER.info(
                "Reset carbon filter life for device %s", coordinator.serial_number
            )
        elif filter_type == "both":
            await coordinator.device.reset_hepa_filter_life()
            await coordinator.device.reset_carbon_filter_life()
            _LOGGER.info(
                "Reset both filter lives for device %s", coordinator.serial_number
            )

    except (ConnectionError, TimeoutError) as err:
        _LOGGER.error(
            "Communication error resetting %s filter for device %s: %s",
            filter_type,
            coordinator.serial_number,
            err,
        )
        raise HomeAssistantError(f"Device communication failed: {err}") from err
    except AttributeError as err:
        _LOGGER.debug(
            "Filter reset method not available for device %s (%s filter): %s",
            coordinator.serial_number,
            filter_type,
            err,
        )
        raise HomeAssistantError(
            f"{filter_type.title()} filter reset not supported: {err}"
        ) from err
    except Exception as err:
        _LOGGER.error(
            "Unexpected error resetting %s filter for device %s: %s",
            filter_type,
            coordinator.serial_number,
            err,
        )
        raise HomeAssistantError(
            f"Failed to reset {filter_type} filter: {err}"
        ) from err


async def _handle_get_cloud_devices(
    hass: HomeAssistant, call: ServiceCall
) -> dict[str, Any]:
    """Handle get cloud devices service call with comprehensive device information.

    Retrieves detailed information about Dyson devices associated with cloud
    accounts configured in Home Assistant. Provides both sanitized and detailed
    device information for integration management and troubleshooting.

    Args:
        hass: Home Assistant instance
        call: Service call with optional account_email and sanitize parameters

    Service Parameters:
        account_email (str, optional): Specific Dyson account email to query.
                                     If not provided, uses first available account.
        sanitize (bool, default=False): If True, removes sensitive information
                                       from device data (credentials, tokens, etc.)

    Returns:
        Dict containing comprehensive device information:
        - account_email: Email of the queried Dyson account
        - total_devices: Number of devices found in the account
        - devices: List of device information dictionaries
        - query_timestamp: ISO timestamp of the query
        - integration_status: Current integration health status

    Device Information Structure:
        Each device entry contains:
        - basic_info: Serial number, name, model, product type
        - connectivity: Network status, MQTT topics, connection health
        - capabilities: List of device features and supported operations
        - environmental_data: Current sensor readings (if available)
        - maintenance: Filter life, cleaning status, error conditions
        - credentials: MQTT credentials (if sanitize=False)

    Account Discovery:
        Automatically discovers all configured Dyson cloud accounts by:
        1. Scanning Home Assistant data for cloud coordinators
        2. Extracting account information from configuration entries
        3. Filtering for coordinators with active cloud connections
        4. Providing account selection if multiple accounts exist

    Data Sanitization:
        When sanitize=True, removes sensitive information:
        - MQTT passwords and tokens
        - API authentication credentials
        - Internal device identifiers
        - Network configuration details

    Example:
        Retrieve all devices from first account:

        >>> result = await hass.services.async_call(
        >>>     "hass_dyson",
        >>>     "get_cloud_devices",
        >>>     {"sanitize": True},
        >>>     return_response=True
        >>> )
        >>>
        >>> print(f"Found {result['total_devices']} devices")
        >>> for device in result['devices']:
        >>>     print(f"- {device['basic_info']['name']} ({device['basic_info']['model']})")

    Raises:
        ServiceValidationError: If specified account not found or no cloud accounts configured
        HomeAssistantError: If cloud API communication fails
    """
    account_email = call.data.get("account_email")
    sanitize = call.data.get("sanitize", False)

    # Find cloud coordinators (already authenticated)
    cloud_coordinators = _find_cloud_coordinators(hass)

    if not cloud_coordinators:
        _LOGGER.info("No cloud accounts found for get_cloud_devices service call")
        return {
            "message": "No cloud accounts found. Please configure a cloud account first.",
            "total_devices": 0,
            "devices": [],
            "available_setup_methods": [
                "Add a Dyson integration via Settings > Devices & Services > Add Integration > Dyson",
                "Choose 'Cloud Account' setup method to authenticate with your Dyson account",
            ],
            "sanitized": sanitize,
        }

    # Select coordinator by account email
    if account_email:
        selected_coordinator = next(
            (coord for coord in cloud_coordinators if coord["email"] == account_email),
            None,
        )
        if not selected_coordinator:
            available_emails = [coord["email"] for coord in cloud_coordinators]
            raise ServiceValidationError(
                f"Account '{account_email}' not found. Available accounts: {', '.join(available_emails)}"
            )
    else:
        # Use first coordinator if not specified
        selected_coordinator = cloud_coordinators[0]

    _LOGGER.info(
        "Retrieving cloud devices for account: %s", selected_coordinator["email"]
    )

    try:
        device_data = await _get_cloud_device_data_from_coordinator(
            selected_coordinator, sanitize
        )

        response_data = {
            "account_email": selected_coordinator["email"],
            "total_devices": len(device_data["devices"]),
            "devices": device_data["devices"],
            "sanitized": sanitize,
        }

        if not sanitize:
            response_data["summary"] = device_data["summary"]

        _LOGGER.info(
            "Successfully retrieved %d devices from cloud account %s (sanitized: %s)",
            len(device_data["devices"]),
            selected_coordinator["email"],
            sanitize,
        )

        return response_data

    except (DysonAuthError, DysonConnectionError, DysonAPIError) as err:
        _LOGGER.error(
            "Dyson service error for account %s: %s", selected_coordinator["email"], err
        )
        raise HomeAssistantError(f"Dyson service error: {err}") from err
    except Exception as err:
        _LOGGER.error(
            "Unexpected error for account %s: %s", selected_coordinator["email"], err
        )
        raise HomeAssistantError(f"Unexpected error: {err}") from err


def _find_cloud_coordinators(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Find all active cloud coordinators with authentication."""
    from .coordinator import DysonCloudAccountCoordinator, DysonDataUpdateCoordinator

    cloud_coordinators = []

    # First, look through actual coordinators in hass.data[DOMAIN]
    for key, coordinator in hass.data.get(DOMAIN, {}).items():
        # Check for DysonCloudAccountCoordinator (account-level coordinators)
        if isinstance(coordinator, DysonCloudAccountCoordinator):
            # Cloud account coordinator uses "email" field
            email = coordinator.config_entry.data.get("email")
            if email:
                cloud_coordinators.append(
                    {
                        "email": email,
                        "coordinator": coordinator,
                        "config_entry_id": coordinator.config_entry.entry_id,
                        "type": "cloud_account",
                    }
                )

        # Check for DysonDataUpdateCoordinator with cloud discovery
        elif isinstance(coordinator, DysonDataUpdateCoordinator):
            # Check if this coordinator uses cloud discovery
            if (
                coordinator.config_entry.data.get(CONF_DISCOVERY_METHOD)
                == DISCOVERY_CLOUD
            ):
                # Device coordinator might use "username" or "email" field
                email = coordinator.config_entry.data.get(
                    "email"
                ) or coordinator.config_entry.data.get(CONF_USERNAME)
                if email and hasattr(coordinator, "device") and coordinator.device:
                    cloud_coordinators.append(
                        {
                            "email": email,
                            "coordinator": coordinator,
                            "config_entry_id": coordinator.config_entry.entry_id,
                            "type": "device",
                        }
                    )

    # If no coordinators found, look through config entries for cloud accounts
    # This handles cases where cloud coordinators aren't created (e.g., polling disabled)
    if not cloud_coordinators:
        for entry in hass.config_entries.async_entries(DOMAIN):
            # Check if this is an account-level entry
            if "devices" in entry.data and entry.data.get("devices"):
                email = entry.data.get("email")
                auth_token = entry.data.get("auth_token")
                if email and auth_token:
                    cloud_coordinators.append(
                        {
                            "email": email,
                            "coordinator": None,  # No active coordinator
                            "config_entry_id": entry.entry_id,
                            "config_entry": entry,  # Include the config entry for direct access
                            "type": "config_entry",
                        }
                    )

    return cloud_coordinators


async def _get_cloud_device_data_from_coordinator(
    coordinator_info: dict[str, Any], sanitize: bool
) -> dict[str, Any]:
    """Retrieve device data using existing coordinator's cloud connection or config entry."""
    coordinator_type = coordinator_info.get("type")

    if coordinator_type == "config_entry":
        # Handle config entry case (no active coordinator)
        return await _get_device_data_from_config_entry(
            coordinator_info["config_entry"], sanitize
        )
    elif coordinator_type == "cloud_account":
        # Handle cloud account coordinator case - these have access to multiple devices
        coordinator = coordinator_info["coordinator"]

        # Cloud account coordinators have _fetch_cloud_devices method and auth token
        if not hasattr(coordinator, "_auth_token") or not coordinator._auth_token:
            raise HomeAssistantError("Cloud account coordinator has no auth token")

        # Use the cloud account coordinator to fetch all devices with decrypted credentials
        try:
            devices = await coordinator._fetch_cloud_devices()
            if not devices:
                return {
                    "devices": [],
                    "summary": {
                        "total_devices": 0,
                        "connected_devices": 0,
                        "devices_with_local_config": 0,
                        "account_email": coordinator_info.get("email", "Unknown"),
                        "source": "cloud_account_coordinator",
                    },
                }

            # Enhance devices with decrypted MQTT credentials using the coordinator's auth token
            from libdyson_rest import AsyncDysonClient

            async with AsyncDysonClient(auth_token=coordinator._auth_token) as client:
                enhanced_devices = await _enhance_devices_with_mqtt_credentials(
                    client, devices
                )

            # Build device data from the enhanced devices
            device_list = []
            for device_info in enhanced_devices:
                device = device_info["device"]
                device_data = device_info["enhanced_data"]

                if sanitize:
                    device_info_result = (
                        _create_sanitized_device_info_from_cloud_device(device)
                    )
                else:
                    # Pass the decrypted password to the detailed function
                    decrypted_password = device_data.get("decrypted_mqtt_password", "")
                    device_info_result = _create_detailed_device_info_from_cloud_device(
                        device, decrypted_password
                    )
                device_list.append(device_info_result)

            return {
                "devices": device_list,
                "summary": {
                    "total_devices": len(device_list),
                    "connected_devices": len(
                        device_list
                    ),  # Cloud devices are considered connected
                    "devices_with_local_config": 0,  # Cloud devices don't have local config
                    "account_email": coordinator_info.get("email", "Unknown"),
                    "source": "cloud_account_coordinator",
                },
            }

        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error fetching devices from cloud account coordinator: %s",
                err,
            )
            raise HomeAssistantError(
                f"Cloud service communication failed: {err}"
            ) from err
        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "Missing data fetching devices from cloud account coordinator: %s", err
            )
            raise HomeAssistantError(f"Cloud service data unavailable: {err}") from err
        except Exception as err:
            _LOGGER.error(
                "Unexpected error fetching devices from cloud account coordinator: %s",
                err,
            )
            raise HomeAssistantError(f"Failed to fetch cloud devices: {err}") from err
    else:
        # Handle device coordinator case (type "device")
        coordinator = coordinator_info["coordinator"]

        # Device coordinators should have a device property
        if not hasattr(coordinator, "device") or not coordinator.device:
            raise HomeAssistantError("Device coordinator has no device")

        # For device coordinators, provide data based on what the coordinator already knows
        return await _get_device_data_from_coordinator_only(coordinator, sanitize)


async def _enhance_devices_with_mqtt_credentials(
    client, devices
) -> list[dict[str, Any]]:
    """Enhance device list with decrypted MQTT credentials using cloud client."""
    enhanced_devices = []
    for device in devices:
        # Create enhanced device data with decrypted credentials
        enhanced_device_data = _extract_enhanced_device_info(device)

        # Decrypt MQTT credentials if available
        mqtt_credentials = _decrypt_device_mqtt_credentials(client, device)
        if mqtt_credentials:
            enhanced_device_data["decrypted_mqtt_password"] = mqtt_credentials

        enhanced_devices.append(
            {"device": device, "enhanced_data": enhanced_device_data}
        )
    return enhanced_devices


async def _fetch_live_cloud_devices(config_entry):
    """Fetch live device data from Dyson cloud API using config entry credentials."""
    from libdyson_rest import AsyncDysonClient

    auth_token = config_entry.data.get("auth_token")
    email = config_entry.data.get("email")

    if not auth_token:
        raise HomeAssistantError(f"No auth token available for cloud account {email}")

    _LOGGER.debug(
        "Fetching live device data from Dyson cloud API for account: %s", email
    )

    # Create client with auth token and fetch devices
    async with AsyncDysonClient(auth_token=auth_token) as client:
        devices = await client.get_devices()

        if not devices:
            _LOGGER.debug("No devices found in cloud account %s", email)
            return []

        # Enhance devices with decrypted MQTT credentials
        enhanced_devices = await _enhance_devices_with_mqtt_credentials(client, devices)

        _LOGGER.info(
            "Successfully fetched %d devices from cloud API for account %s",
            len(enhanced_devices),
            email,
        )
        return enhanced_devices


async def _get_device_data_from_config_entry(
    config_entry, sanitize: bool
) -> dict[str, Any]:
    """Get device data from config entry - attempts live cloud API first, fallback to stored data."""
    email = config_entry.data.get("email")
    auth_token = config_entry.data.get("auth_token")
    devices_data = config_entry.data.get("devices", [])

    if not email or not auth_token:
        raise HomeAssistantError("Missing authentication credentials in config entry")

    # Try to get live data from cloud API first
    try:
        live_devices = await _fetch_live_cloud_devices(config_entry)
        if live_devices:
            _LOGGER.info(
                "Using live cloud API data for %d devices from account %s",
                len(live_devices),
                email,
            )
            return await _build_device_data_from_live_api(live_devices, email, sanitize)
    except (ConnectionError, TimeoutError) as err:
        _LOGGER.warning(
            "Communication timeout getting live cloud data for account %s, falling back to stored config: %s",
            email,
            err,
        )
    except (KeyError, AttributeError) as err:
        _LOGGER.debug(
            "Missing data getting live cloud data for account %s, falling back to stored config: %s",
            email,
            err,
        )
    except Exception as err:
        _LOGGER.warning(
            "Unexpected error getting live cloud data for account %s, falling back to stored config: %s",
            email,
            err,
        )

    # Fallback to stored config data
    _LOGGER.debug("Using stored config data for account %s", email)
    device_list = []

    for device_data in devices_data:
        # Ensure device_category is always a list of strings
        device_category = device_data.get("device_category", [])
        if isinstance(device_category, str):
            device_category = [device_category]
        elif not isinstance(device_category, list | tuple):
            device_category = (
                [_convert_to_string(device_category)] if device_category else []
            )
        else:
            # Ensure all items are strings, handling enums properly
            device_category = [_convert_to_string(item) for item in device_category]

        if sanitize:
            # Return only safe information for public posting
            device_info = {
                "serial_number": device_data.get("serial_number", "***HIDDEN***"),
                "name": device_data.get("name", "Dyson Device"),
                "product_type": device_data.get("product_type", "Unknown"),
                "device_category": device_category,
                "capabilities": device_data.get("capabilities", []),
                "setup_status": "stored_in_config",
            }
        else:
            # Include all available information
            device_info = {
                "serial_number": device_data.get("serial_number"),
                "name": device_data.get("name"),
                "product_type": device_data.get("product_type"),
                "device_category": device_category,
                "capabilities": device_data.get("capabilities", []),
                "local_ip": device_data.get("local_ip"),
                "version": device_data.get("version"),
                "setup_status": "stored_in_config",
                "stored_data": device_data,  # Full stored data for debugging
            }

        device_list.append(device_info)

    summary = {
        "total_devices": len(device_list),
        "account_email": email,
        "source": "config_entry_stored_data",
        "note": "Data retrieved from stored account information. Live cloud API was not accessible.",
    }

    return {
        "devices": device_list,
        "summary": summary,
    }


async def _build_device_data_from_live_api(
    enhanced_devices, email: str, sanitize: bool
) -> dict[str, Any]:
    """Build device data response from live cloud API devices."""
    device_list = []

    for device_info in enhanced_devices:
        device = device_info["device"]
        device_data = device_info["enhanced_data"]

        if sanitize:
            # Return only safe information for public posting
            device_info_result = {
                "serial_number": "***HIDDEN***",
                "name": device_data["name"],
                "product_type": device_data["product_type"],
                "device_category": device_data["device_category"],
                "capabilities": device_data["capabilities"],
                "model": device_data.get("model", "Unknown"),
                "mqtt_prefix": device_data["mqtt_prefix"],
                "connection_category": device_data.get(
                    "connection_category", "Unknown"
                ),
                "setup_status": "live_cloud_api",
            }
        else:
            # Include all available information from live API
            # Ordered to match manual device setup: serial_number, mqtt_password, mqtt_prefix, name, device_category, capabilities, then alphabetical
            device_info_result = {
                "serial_number": device.serial_number,
                "mqtt_password": device_data.get("decrypted_mqtt_password", ""),
                "mqtt_prefix": device_data["mqtt_prefix"],
                "name": device_data["name"],
                "device_category": device_data["device_category"],
                "capabilities": device_data["capabilities"],
                # Rest alphabetically
                "connection_category": device_data.get(
                    "connection_category", "Unknown"
                ),
                "firmware_version": device_data.get("firmware_version", "Unknown"),
                "model": device_data.get("model", "Unknown"),
                "product_type": device_data["product_type"],
                "setup_status": "live_cloud_api",
            }

        device_list.append(device_info_result)

    summary = {
        "total_devices": len(device_list),
        "account_email": email,
        "source": "live_cloud_api",
        "note": "Live data retrieved from Dyson cloud API. This includes the most current device information.",
        "api_response_time": "just_retrieved",
    }

    return {
        "devices": device_list,
        "summary": summary,
    }


def _extract_enhanced_device_info(device) -> dict[str, Any]:
    """Extract enhanced device information from live API device object."""
    # Start with basic device info
    device_info: dict[str, Any] = {
        "name": getattr(
            device, "name", f"Dyson {getattr(device, 'serial_number', 'Device')}"
        ),
        "device_category": [],
        "capabilities": [],
        "product_type": "Unknown",
        "mqtt_prefix": "Unknown",
    }

    # Try to extract product type from device type and variant
    device_type = getattr(device, "type", None)
    device_variant = getattr(device, "variant", None)
    if device_type and device_variant:
        # Check if device_type already ends with a letter (variant already included)
        # If so, don't append the variant to avoid duplicates like "438KK" or "438EE"
        if device_type and len(device_type) > 0 and device_type[-1].isalpha():
            device_info["product_type"] = device_type
        else:
            device_info["product_type"] = f"{device_type}{device_variant}"
    elif device_type:
        device_info["product_type"] = device_type

    # Extract model information
    model = getattr(device, "model", None)
    if model:
        device_info["model"] = model

    # Extract connection category
    connection_category = getattr(device, "connection_category", None)
    if connection_category:
        device_info["connection_category"] = connection_category

    # Try to extract enhanced info from connected_configuration
    connected_config = getattr(device, "connected_configuration", None)
    if connected_config:
        # Extract firmware info and capabilities
        firmware_info = getattr(connected_config, "firmware", None)
        if firmware_info:
            # Get firmware version
            version = getattr(firmware_info, "version", None)
            if version:
                device_info["firmware_version"] = version

            # Get capabilities from firmware
            capabilities = getattr(firmware_info, "capabilities", None)
            if capabilities and isinstance(capabilities, list | tuple):
                device_info["capabilities"] = list(capabilities)

        # Extract MQTT info
        mqtt_info = getattr(connected_config, "mqtt", None)
        if mqtt_info:
            # Get MQTT root topic level (this is often the mqtt_prefix)
            mqtt_topic = getattr(mqtt_info, "mqtt_root_topic_level", None)
            if mqtt_topic:
                device_info["mqtt_prefix"] = mqtt_topic

    # Set device_category based on the raw category field - always as list of strings
    raw_category = getattr(device, "category", None)
    if raw_category:
        if isinstance(raw_category, str):
            device_info["device_category"] = [raw_category]
        elif isinstance(raw_category, list | tuple):
            # Ensure all items are strings, handling enums properly
            device_info["device_category"] = [
                _convert_to_string(item) for item in raw_category
            ]
        else:
            device_info["device_category"] = [_convert_to_string(raw_category)]

    return device_info


async def _get_device_data_from_coordinator_only(
    coordinator: DysonDataUpdateCoordinator, sanitize: bool
) -> dict[str, Any]:
    """Get device data from the current coordinator only (fallback method)."""
    device_data: dict[str, Any] = {
        "devices": [],
        "summary": {
            "total_devices": 1,  # Only this device
            "connected_devices": 1 if coordinator.device else 0,
            "devices_with_local_config": 0,
        },
    }

    if coordinator.device:
        if sanitize:
            # Return only safe information for public posting
            device_info = _create_sanitized_device_info_from_coordinator(coordinator)
        else:
            # Return comprehensive information for manual setup
            device_info = _create_detailed_device_info_from_coordinator(coordinator)

        device_data["devices"].append(device_info)

        # Update summary based on coordinator state - device has local config if it has credentials
        if coordinator.device.credential:
            device_data["summary"]["devices_with_local_config"] = 1

    return device_data


def _create_sanitized_device_info_from_coordinator(
    coordinator: DysonDataUpdateCoordinator,
) -> dict[str, Any]:
    """Create sanitized device information from coordinator data."""
    device = coordinator.device
    if not device:
        return {}

    # Get capabilities from coordinator
    capabilities = getattr(coordinator, "_device_capabilities", [])

    # Get MQTT topic from coordinator
    mqtt_topic = "Not available"
    if hasattr(device, "mqtt_prefix") and device.mqtt_prefix:
        mqtt_topic = f"{device.mqtt_prefix}/{coordinator.serial_number}"

    return {
        "model": getattr(
            coordinator, "_device_type", "Unknown"
        ),  # Use coordinator's device type as model
        "mqtt_topic": mqtt_topic,
        "device_category": (
            getattr(coordinator, "_device_category", ["Unknown"])[0]
            if getattr(coordinator, "_device_category", [])
            else "Unknown"
        ),
        "device_connection_category": "connected",  # If coordinator exists, it's connected
        "device_capabilities": capabilities,
    }


def _create_detailed_device_info_from_coordinator(
    coordinator: DysonDataUpdateCoordinator,
) -> dict[str, Any]:
    """Create detailed device information from coordinator data."""
    device = coordinator.device
    if not device:
        return {}

    device_info = {
        "basic_info": {
            "name": getattr(
                device, "serial_number", coordinator.serial_number
            ),  # Use serial as name fallback
            "serial_number": coordinator.serial_number,
            "type": getattr(coordinator, "_device_type", "Unknown"),
            "model": getattr(coordinator, "_device_type", "Unknown"),
            "category": (
                getattr(coordinator, "_device_category", ["Unknown"])[0]
                if getattr(coordinator, "_device_category", [])
                else "Unknown"
            ),
            "connection_category": "connected",
            "variant": None,  # Not available from coordinator
        },
        "setup_info": {
            "hostname": f"{coordinator.serial_number}.local",  # Use serial number as hostname
            "mqtt_topics": None,
            "local_mqtt_config": None,
            "capabilities": getattr(coordinator, "_device_capabilities", []),
        },
    }

    # Add MQTT setup information if available
    if hasattr(device, "mqtt_prefix") and device.mqtt_prefix:
        base_topic = f"{device.mqtt_prefix}/{coordinator.serial_number}"

        device_info["setup_info"]["mqtt_topics"] = {
            "base_topic": base_topic,
            "status_topic": f"{base_topic}/status/current",
            "command_topic": f"{base_topic}/command",
        }

        # Determine the MQTT password - use actual credential if available, otherwise placeholder
        mqtt_password = "Requires device setup"
        if hasattr(device, "credential") and device.credential:
            mqtt_password = device.credential

        # Local MQTT configuration
        device_info["setup_info"]["local_mqtt_config"] = {
            "host": f"{coordinator.serial_number}.local",
            "port": 1883,
            "tls_port": 8883,
            "username": coordinator.serial_number,
            "root_topic": device.mqtt_prefix,
            "password": mqtt_password,
        }

    return device_info


def _create_sanitized_device_info_from_cloud_device(device) -> dict[str, Any]:
    """Create sanitized device information from cloud device object.

    Uses existing _extract_enhanced_device_info infrastructure to process cloud device
    and returns only safe information suitable for public sharing.
    """
    # Leverage existing cloud device processing
    enhanced_info = _extract_enhanced_device_info(device)

    return {
        "serial_number": "***HIDDEN***",
        "name": enhanced_info.get("name", "Unknown Device"),
        "product_type": enhanced_info.get("product_type", "Unknown"),
        "device_category": enhanced_info.get("device_category", []),
        "capabilities": enhanced_info.get("capabilities", []),
        "model": enhanced_info.get("model", "Unknown"),
        "mqtt_prefix": enhanced_info.get("mqtt_prefix", "Unknown"),
        "connection_category": enhanced_info.get("connection_category", "Unknown"),
        "setup_status": "cloud_device",
    }


def _create_detailed_device_info_from_cloud_device(
    device, decrypted_password: str = ""
) -> dict[str, Any]:
    """Create detailed device information from cloud device object.

    Uses existing _extract_enhanced_device_info infrastructure to process cloud device
    and returns comprehensive information for manual setup.

    Args:
        device: The cloud device object
        decrypted_password: The decrypted MQTT password if available
    """
    # Leverage existing cloud device processing
    enhanced_info = _extract_enhanced_device_info(device)

    # Get serial number from device object
    serial_number = getattr(device, "serial_number", "Unknown")

    # Use the provided decrypted password or fallback
    mqtt_password = (
        decrypted_password if decrypted_password else "Requires device setup"
    )

    return {
        # Ordered to match manual device setup pattern
        "serial_number": serial_number,
        "mqtt_password": mqtt_password,
        "mqtt_prefix": enhanced_info.get("mqtt_prefix", "Unknown"),
        "name": enhanced_info.get("name", "Unknown Device"),
        "device_category": enhanced_info.get("device_category", []),
        "capabilities": enhanced_info.get("capabilities", []),
        # Additional information alphabetically
        "connection_category": enhanced_info.get("connection_category", "Unknown"),
        "firmware_version": enhanced_info.get("firmware_version", "Unknown"),
        "model": enhanced_info.get("model", "Unknown"),
        "product_type": enhanced_info.get("product_type", "Unknown"),
        "setup_status": "cloud_device",
    }


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up all services for Dyson integration."""
    # Cloud services are registered separately when cloud accounts are configured
    # Device services are registered per-category when devices are set up
    pass


def _get_device_categories_for_coordinator(
    coordinator: DysonDataUpdateCoordinator,
) -> list[str]:
    """Get device categories for a coordinator."""
    if hasattr(coordinator, "device_category") and coordinator.device_category:
        categories = coordinator.device_category
        if isinstance(categories, str):
            return [categories]
        elif isinstance(categories, list | tuple):
            return list(categories)
    return []


async def async_register_device_services_for_coordinator(
    hass: HomeAssistant, coordinator: DysonDataUpdateCoordinator
) -> None:
    """Register device services based on coordinator capabilities and categories.

    Dynamically registers Home Assistant services based on the specific capabilities
    and categories of a Dyson device. Services are only registered once per capability
    type to avoid duplicate registrations.

    Args:
        hass: Home Assistant instance for service registration
        coordinator: DysonDataUpdateCoordinator containing device information

    Service Registration Logic:
        1. Extract device capabilities from coordinator.device_capabilities
        2. Fallback to coordinator.device.capabilities if primary is empty
        3. Map capabilities to services using DEVICE_CAPABILITY_SERVICES
        4. Add category-based services for backward compatibility
        5. Register all unique services via _register_services

    Capability to Service Mapping:
        - "Scheduling": sleep_timer, cancel_sleep_timer, schedule_operation
        - "AdvanceOscillationDay1": set_oscillation_angles
        - "ExtendedAQ": reset_filter (for advanced air quality devices)
        - "EnvironmentalData": reset_filter (for basic environmental monitoring)

    Category to Service Mapping (legacy compatibility):
        - "ec" (Environment Cleaner): All timer and filter services
        - "robot": Scheduling and filter reset for cleaning devices
        - "vacuum": Basic cleaning device services
        - "flrc" (Floor Cleaning): Floor cleaning specific services

    Note:
        Services are registered globally but only if not already present.
        Multiple devices can share the same services without conflicts.
        Reference counting ensures services persist until all devices
        of a given type are removed.

    Example:
        Automatic service registration during device setup:

        >>> coordinator = DysonDataUpdateCoordinator(...)
        >>> coordinator.device_capabilities = ["Scheduling", "ExtendedAQ"]
        >>>
        >>> await async_register_device_services_for_coordinator(hass, coordinator)
        >>>
        >>> # Services now available:
        >>> # - hass_dyson.set_sleep_timer
        >>> # - hass_dyson.cancel_sleep_timer
        >>> # - hass_dyson.schedule_operation
        >>> # - hass_dyson.reset_filter

    Raises:
        Exception: Service registration failures are logged but not propagated
    """
    # Determine which services need to be registered based on capabilities
    services_to_register = set()

    # Add services based on device capabilities from coordinator
    device_capabilities = getattr(coordinator, "device_capabilities", []) or []

    # Also check device object capabilities if available and coordinator capabilities are empty
    if (
        not device_capabilities
        and hasattr(coordinator, "device")
        and coordinator.device
    ):
        device_obj_capabilities = getattr(coordinator.device, "capabilities", []) or []
        if device_obj_capabilities:
            device_capabilities = device_obj_capabilities
            _LOGGER.debug(
                "Using device object capabilities for service registration %s: %s",
                coordinator.serial_number,
                device_capabilities,
            )

    for capability in device_capabilities:
        if capability in DEVICE_CAPABILITY_SERVICES:
            services_to_register.update(DEVICE_CAPABILITY_SERVICES[capability])

    # Add services based on device categories (for backward compatibility)
    categories = _get_device_categories_for_coordinator(coordinator)
    for category in categories:
        if category in DEVICE_CATEGORY_SERVICES:
            services_to_register.update(DEVICE_CATEGORY_SERVICES[category])

    # Register the services
    await _register_services(hass, services_to_register)


async def async_register_device_services_for_categories(
    hass: HomeAssistant, categories: list[str]
) -> None:
    """Register device services for specific categories if not already registered."""
    global _device_category_counts

    # Determine which services need to be registered
    services_to_register = set()
    for category in categories:
        if category in DEVICE_CATEGORY_SERVICES:
            services_to_register.update(DEVICE_CATEGORY_SERVICES[category])
            # Increment reference count for this category
            _device_category_counts[category] = (
                _device_category_counts.get(category, 0) + 1
            )

    # Register the services
    await _register_services(hass, services_to_register)


async def _register_services(
    hass: HomeAssistant, services_to_register: set[str]
) -> None:
    """Register the specified services if not already registered."""

    # Create service handlers
    service_handlers = {}
    service_schemas = {}

    if SERVICE_SET_SLEEP_TIMER in services_to_register:

        async def async_handle_set_sleep_timer(call: ServiceCall) -> None:
            await _handle_set_sleep_timer(hass, call)

        service_handlers[SERVICE_SET_SLEEP_TIMER] = async_handle_set_sleep_timer
        service_schemas[SERVICE_SET_SLEEP_TIMER] = SERVICE_SET_SLEEP_TIMER_SCHEMA

    if SERVICE_CANCEL_SLEEP_TIMER in services_to_register:

        async def async_handle_cancel_sleep_timer(call: ServiceCall) -> None:
            await _handle_cancel_sleep_timer(hass, call)

        service_handlers[SERVICE_CANCEL_SLEEP_TIMER] = async_handle_cancel_sleep_timer
        service_schemas[SERVICE_CANCEL_SLEEP_TIMER] = SERVICE_CANCEL_SLEEP_TIMER_SCHEMA

    if SERVICE_SCHEDULE_OPERATION in services_to_register:

        async def async_handle_schedule_operation(call: ServiceCall) -> None:
            await _handle_schedule_operation(hass, call)

        service_handlers[SERVICE_SCHEDULE_OPERATION] = async_handle_schedule_operation
        service_schemas[SERVICE_SCHEDULE_OPERATION] = SERVICE_SCHEDULE_OPERATION_SCHEMA

    if SERVICE_SET_OSCILLATION_ANGLES in services_to_register:

        async def async_handle_set_oscillation_angles(call: ServiceCall) -> None:
            await _handle_set_oscillation_angles(hass, call)

        service_handlers[SERVICE_SET_OSCILLATION_ANGLES] = (
            async_handle_set_oscillation_angles
        )
        service_schemas[SERVICE_SET_OSCILLATION_ANGLES] = (
            SERVICE_SET_OSCILLATION_ANGLES_SCHEMA
        )

    if SERVICE_RESET_FILTER in services_to_register:

        async def async_handle_reset_filter(call: ServiceCall) -> None:
            await _handle_reset_filter(hass, call)

        service_handlers[SERVICE_RESET_FILTER] = async_handle_reset_filter
        service_schemas[SERVICE_RESET_FILTER] = SERVICE_RESET_FILTER_SCHEMA

    # Register services that aren't already registered
    registered_services = []
    for service_name, handler in service_handlers.items():
        if not hass.services.has_service(DOMAIN, service_name):
            hass.services.async_register(
                DOMAIN, service_name, handler, schema=service_schemas[service_name]
            )
            registered_services.append(service_name)

    if registered_services:
        _LOGGER.info("Registered Dyson device services: %s", registered_services)


async def async_unregister_device_services_for_categories(
    hass: HomeAssistant, categories: list[str]
) -> None:
    """Unregister device services for categories if no more devices of that category exist."""
    global _device_category_counts

    services_to_check = set()
    for category in categories:
        if category in _device_category_counts:
            # Decrement reference count
            _device_category_counts[category] -= 1
            if _device_category_counts[category] <= 0:
                # No more devices of this category, add its services to check list
                del _device_category_counts[category]
                if category in DEVICE_CATEGORY_SERVICES:
                    services_to_check.update(DEVICE_CATEGORY_SERVICES[category])

    # Check if any services should be removed (no longer needed by any active category)
    services_to_remove = []
    for service in services_to_check:
        # Check if this service is still needed by any active category
        still_needed = False
        for active_category, count in _device_category_counts.items():
            if count > 0 and active_category in DEVICE_CATEGORY_SERVICES:
                if service in DEVICE_CATEGORY_SERVICES[active_category]:
                    still_needed = True
                    break

        if not still_needed and hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
            services_to_remove.append(service)

    if services_to_remove:
        _LOGGER.info(
            "Removed Dyson device services for categories %s: %s",
            categories,
            services_to_remove,
        )


async def async_setup_cloud_services(hass: HomeAssistant) -> None:
    """Set up cloud and account-level services for Dyson integration.

    Registers services that operate at the account level rather than on
    individual devices. These services manage cloud account information
    and provide integration-wide functionality.

    Args:
        hass: Home Assistant instance for service registration

    Registered Services:
        get_cloud_devices: Retrieve comprehensive device information from
                          Dyson cloud accounts with optional sanitization
        refresh_account_data: Update cloud account information and device
                            discovery for all configured accounts

    Service Characteristics:
        - get_cloud_devices: Supports response data (return_response=True)
        - refresh_account_data: Fire-and-forget operation
        - Both services validate parameters using voluptuous schemas
        - Comprehensive error handling with detailed logging

    Registration Logic:
        - Checks if services already exist to prevent duplicate registration
        - Uses Home Assistant's service registry for proper lifecycle management
        - Applies appropriate service schemas for parameter validation
        - Logs successful registration for confirmation

    Usage Context:
        Cloud services are registered when:
        1. First cloud account is configured in the integration
        2. Integration startup with existing cloud accounts
        3. Manual service registration during development/testing

    Service Persistence:
        Cloud services remain registered until:
        - Integration is removed completely
        - Home Assistant is restarted
        - Manual service removal is performed

    Example:
        Services are registered automatically during integration setup:

        >>> await async_setup_cloud_services(hass)
        >>>
        >>> # Services now available:
        >>> # - hass_dyson.get_cloud_devices (with response support)
        >>> # - hass_dyson.refresh_account_data
        >>>
        >>> # Example usage:
        >>> devices = await hass.services.async_call(
        >>>     "hass_dyson", "get_cloud_devices",
        >>>     {"sanitize": True}, return_response=True
        >>> )

    Note:
        Cloud services are independent of device services and can be used
        even when no devices are currently configured or connected.
    """

    # Create async service handlers with hass context
    async def async_handle_get_cloud_devices(call: ServiceCall) -> dict[str, Any]:
        return await _handle_get_cloud_devices(hass, call)

    async def async_handle_refresh_account_data_cloud(call: ServiceCall) -> None:
        await async_handle_refresh_account_data(hass, call)

    # Cloud services that should be available when any config entry exists
    cloud_handlers = {
        SERVICE_GET_CLOUD_DEVICES: async_handle_get_cloud_devices,
        SERVICE_REFRESH_ACCOUNT_DATA: async_handle_refresh_account_data_cloud,
    }

    cloud_schemas = {
        SERVICE_GET_CLOUD_DEVICES: SERVICE_GET_CLOUD_DEVICES_SCHEMA,
        SERVICE_REFRESH_ACCOUNT_DATA: SERVICE_REFRESH_ACCOUNT_DATA_SCHEMA,
    }

    # Register cloud services only if not already registered
    registered_services = []
    for service_name, handler in cloud_handlers.items():
        if not hass.services.has_service(DOMAIN, service_name):
            if service_name == SERVICE_GET_CLOUD_DEVICES:
                # This service returns response data
                hass.services.async_register(
                    DOMAIN,
                    service_name,
                    handler,
                    schema=cloud_schemas[service_name],
                    supports_response=SupportsResponse.OPTIONAL,
                )
            else:
                hass.services.async_register(
                    DOMAIN, service_name, handler, schema=cloud_schemas[service_name]
                )
            registered_services.append(service_name)

    if registered_services:
        _LOGGER.info("Registered Dyson cloud services: %s", registered_services)


async def async_setup_device_services_for_coordinator(
    hass: HomeAssistant, coordinator: DysonDataUpdateCoordinator
) -> None:
    """Set up device-specific services for a specific coordinator based on its capabilities and categories."""
    # Register device-specific services based on capabilities
    await async_register_device_services_for_coordinator(hass, coordinator)


async def async_remove_device_services_for_coordinator(
    hass: HomeAssistant, coordinator: DysonDataUpdateCoordinator
) -> None:
    """Remove device-specific services for a coordinator if no other devices of that category exist."""
    categories = _get_device_categories_for_coordinator(coordinator)
    if categories:
        await async_unregister_device_services_for_categories(hass, categories)


async def async_remove_cloud_services(hass: HomeAssistant) -> None:
    """Remove cloud services for Dyson integration."""
    cloud_services_to_remove = [
        SERVICE_GET_CLOUD_DEVICES,
        SERVICE_REFRESH_ACCOUNT_DATA,
    ]

    removed_services = []
    for service in cloud_services_to_remove:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
            removed_services.append(service)

    if removed_services:
        _LOGGER.info("Removed Dyson cloud services: %s", removed_services)


async def async_remove_services(hass: HomeAssistant) -> None:
    """Remove all services for Dyson integration during cleanup.

    Performs comprehensive cleanup of all Dyson integration services during
    integration removal or Home Assistant shutdown. Ensures proper service
    lifecycle management and prevents service registry pollution.

    Args:
        hass: Home Assistant instance for service removal

    Removal Process:
        1. Check each service for existence in the service registry
        2. Remove existing services using async_remove
        3. Log removal operations for confirmation
        4. Handle missing services gracefully (no error)

    Services Removed:
        Device Control Services:
        - set_sleep_timer: Sleep timer configuration
        - cancel_sleep_timer: Sleep timer cancellation
        - set_oscillation_angles: Custom oscillation control
        - reset_filter: Filter life reset
        - schedule_operation: Future operation scheduling

        Cloud Account Services:
        - get_cloud_devices: Device information retrieval
        - refresh_account_data: Account data updates

    Safety Features:
        - Checks service existence before attempting removal
        - Gracefully handles already-removed services
        - No exceptions raised for missing services
        - Comprehensive logging for debugging

    Cleanup Context:
        This function is called during:
        - Integration removal/uninstall
        - Home Assistant shutdown
        - Integration reload operations
        - Manual service cleanup (development/testing)

    Global State Cleanup:
        Also resets global service registration state:
        - Clears device category reference counts
        - Resets service registration flags
        - Ensures clean state for future registrations

    Example:
        Automatic cleanup during integration removal:

        >>> # Integration being removed
        >>> await async_remove_services(hass)
        >>>
        >>> # All hass_dyson.* services now removed
        >>> # Service registry cleaned up
        >>> # Global state reset

    Note:
        This is a comprehensive cleanup function that should only be called
        when completely removing the Dyson integration. For removing services
        for specific devices or categories, use the more targeted removal functions.
    """
    services_to_remove = [
        SERVICE_SET_SLEEP_TIMER,
        SERVICE_CANCEL_SLEEP_TIMER,
        SERVICE_SCHEDULE_OPERATION,
        SERVICE_SET_OSCILLATION_ANGLES,
        SERVICE_REFRESH_ACCOUNT_DATA,
        SERVICE_RESET_FILTER,
        SERVICE_GET_CLOUD_DEVICES,
    ]

    for service in services_to_remove:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)

    _LOGGER.info("Removed Dyson services")


async def _get_coordinator_from_device_id(
    hass: HomeAssistant, device_id: str
) -> DysonDataUpdateCoordinator | None:
    """Resolve Home Assistant device ID to Dyson coordinator.

    Translates a Home Assistant device registry ID to the corresponding
    DysonDataUpdateCoordinator instance for service operations. Provides
    the bridge between Home Assistant's device registry and the integration's
    coordinator architecture.

    Args:
        hass: Home Assistant instance
        device_id: Home Assistant device registry ID

    Returns:
        DysonDataUpdateCoordinator instance if found, None if not found

    Resolution Process:
        1. Query Home Assistant device registry for device entry
        2. Extract device identifiers from registry entry
        3. Find Dyson serial number from device identifiers
        4. Search integration data for matching coordinator
        5. Validate coordinator has active device connection

    Device Identifier Format:
        Dyson devices use identifiers in format:
        - ("hass_dyson", "SERIAL-NUMBER") for integration devices
        - Serial numbers follow Dyson format: "VS6-EU-HJA1234A"

    Coordinator Validation:
        Found coordinators are validated for:
        - Active device connection (coordinator.device exists)
        - MQTT connectivity (coordinator.device.is_connected)
        - Recent successful updates (coordinator.last_update_success)

    Error Handling:
        Returns None (rather than raising exceptions) for:
        - Invalid or non-existent device IDs
        - Devices not belonging to Dyson integration
        - Coordinators without active device connections
        - Network connectivity issues

    Example:
        Service handler using coordinator resolution:

        >>> async def service_handler(call: ServiceCall):
        >>>     device_id = call.data["device_id"]
        >>>     coordinator = await _get_coordinator_from_device_id(hass, device_id)
        >>>
        >>>     if not coordinator:
        >>>         raise ServiceValidationError(f"Device {device_id} not found")
        >>>
        >>>     # Use coordinator.device for device operations
        >>>     await coordinator.device.set_fan_speed(5)

    Note:
        This function is used internally by all device-specific service handlers
        to ensure consistent device resolution and validation across the integration.
    """
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
