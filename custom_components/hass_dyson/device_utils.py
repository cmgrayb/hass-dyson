"""Utility functions for device configuration and setup."""

import logging
from typing import Any, Dict, List, Optional

from homeassistant.const import CONF_USERNAME

from .const import (
    CONF_CREDENTIAL,
    CONF_DISCOVERY_METHOD,
    CONF_HOSTNAME,
    CONF_MQTT_PREFIX,
    CONF_SERIAL_NUMBER,
    CONNECTION_TYPE_LOCAL_ONLY,
    DISCOVERY_CLOUD,
    DISCOVERY_MANUAL,
)

_LOGGER = logging.getLogger(__name__)


def normalize_device_category(category: Any) -> List[str]:
    """Normalize device category to a consistent list format.

    Args:
        category: Can be string, list, enum, or None

    Returns:
        List of category strings, defaults to ["ec"] if invalid
    """
    if category is None:
        return ["ec"]

    # Handle enum objects
    if hasattr(category, "value"):
        category = category.value
    elif hasattr(category, "name"):
        category = category.name.lower()

    # Convert to list if string
    if isinstance(category, str):
        return [category]

    # If already a list, ensure all items are strings
    if isinstance(category, list):
        return [str(item) for item in category if item]

    # Fallback for any other type
    _LOGGER.warning("Unknown category type %s, defaulting to ['ec']", type(category))
    return ["ec"]


def normalize_capabilities(capabilities: Any) -> List[str]:  # noqa: C901
    """Normalize device capabilities to a consistent list format.

    Args:
        capabilities: Can be list, None, or other types

    Returns:
        List of capability strings, empty list if invalid
    """
    if capabilities is None:
        _LOGGER.debug("No capabilities provided, returning empty list")
        return []

    if isinstance(capabilities, list):
        # Convert enum objects to their string values, otherwise use str()
        result = []
        for cap in capabilities:
            if cap is None:
                _LOGGER.warning("Found None capability in list, skipping")
                continue
            elif cap == "":
                _LOGGER.warning("Found empty string capability in list, skipping")
                continue
            elif isinstance(cap, (int, float)) and cap == 0:
                _LOGGER.warning("Found zero numeric capability in list, skipping")
                continue
            else:
                try:
                    if hasattr(cap, "value") and not isinstance(cap, (int, float, str)):
                        normalized_cap = str(cap.value)
                    else:
                        normalized_cap = str(cap)

                    # Validate that the normalized capability is meaningful
                    if normalized_cap.strip():
                        result.append(normalized_cap)
                        _LOGGER.debug("Normalized capability: %s -> %s", cap, normalized_cap)
                    else:
                        _LOGGER.warning("Capability normalized to empty string, skipping: %s", cap)
                except Exception as e:
                    _LOGGER.error("Failed to normalize capability %s (type: %s): %s", cap, type(cap), e)
                    continue

        _LOGGER.debug("Normalized capabilities list: %s -> %s", capabilities, result)
        return result

    # Single capability as string
    if isinstance(capabilities, str):
        if capabilities.strip():
            _LOGGER.debug("Normalized single capability: %s", capabilities)
            return [capabilities]
        else:
            _LOGGER.warning("Single capability is empty string, returning empty list")
            return []

    # Handle other types that might be convertible
    try:
        if hasattr(capabilities, "value") and not isinstance(capabilities, (int, float, str)):
            normalized = str(capabilities.value)
        else:
            normalized = str(capabilities)

        if normalized.strip():
            _LOGGER.debug("Normalized non-standard capability: %s -> %s", capabilities, normalized)
            return [normalized]
        else:
            _LOGGER.warning("Non-standard capability normalized to empty string: %s", capabilities)
            return []
    except Exception as e:
        _LOGGER.error("Failed to normalize capabilities %s (type: %s): %s", capabilities, type(capabilities), e)
        return []


def has_capability_safe(capabilities: Optional[List[str]], capability_name: str) -> bool:
    """Safely check if device has a specific capability with case-insensitive matching.

    Args:
        capabilities: List of device capabilities (may be None or malformed)
        capability_name: Name of capability to check for

    Returns:
        True if capability is found, False otherwise
    """
    if not capabilities:
        _LOGGER.debug("No capabilities provided for capability check: %s", capability_name)
        return False

    if not isinstance(capabilities, list):
        _LOGGER.warning("Capabilities is not a list, cannot check for capability: %s", capability_name)
        return False

    try:
        # Normalize the search term
        search_term = capability_name.lower().strip()
        if not search_term:
            _LOGGER.warning("Empty capability name provided for search")
            return False

        # Convert capabilities to lowercase strings for comparison
        normalized_caps = []
        for cap in capabilities:
            try:
                if cap is not None:
                    normalized_caps.append(str(cap).lower().strip())
            except Exception as e:
                _LOGGER.warning("Failed to normalize capability for comparison %s: %s", cap, e)
                continue

        # Check for matches
        has_capability = search_term in normalized_caps
        _LOGGER.debug("Capability check: '%s' in %s = %s", search_term, normalized_caps, has_capability)
        return has_capability

    except Exception as e:
        _LOGGER.error("Error during capability check for '%s': %s", capability_name, e)
        return False


def has_any_capability_safe(capabilities: Optional[List[str]], capability_names: List[str]) -> bool:
    """Safely check if device has any of the specified capabilities.

    Args:
        capabilities: List of device capabilities (may be None or malformed)
        capability_names: List of capability names to check for

    Returns:
        True if any capability is found, False otherwise
    """
    if not capability_names:
        _LOGGER.debug("No capability names provided for any-capability check")
        return False

    for capability_name in capability_names:
        if has_capability_safe(capabilities, capability_name):
            _LOGGER.debug("Found capability '%s' in any-capability check", capability_name)
            return True

    _LOGGER.debug("No capabilities found in any-capability check for: %s", capability_names)
    return False


def get_sensor_data_safe(data: Optional[Dict[str, Any]], key: str, device_serial: str = "unknown") -> Any:
    """Safely extract sensor data with proper error handling and logging.

    Args:
        data: Dictionary containing sensor data (may be None)
        key: Key to extract from data
        device_serial: Device serial for logging context

    Returns:
        The value if found and valid, None otherwise
    """
    if data is None:
        _LOGGER.debug("No data available for sensor key '%s' on device %s", key, device_serial)
        return None

    if not isinstance(data, dict):
        _LOGGER.warning(
            "Data is not a dictionary for sensor key '%s' on device %s (type: %s)", key, device_serial, type(data)
        )
        return None

    try:
        value = data.get(key)
        if value is None:
            _LOGGER.debug("Sensor key '%s' not found in data for device %s", key, device_serial)
            return None

        # Log successful data access
        _LOGGER.debug("Successfully extracted sensor data for key '%s' on device %s: %s", key, device_serial, value)
        return value

    except Exception as e:
        _LOGGER.error("Error accessing sensor data for key '%s' on device %s: %s", key, device_serial, e)
        return None


def convert_sensor_value_safe(
    value: Any, target_type: type, device_serial: str = "unknown", sensor_name: str = "unknown"
) -> Any:
    """Safely convert sensor value to target type with proper error handling.

    Args:
        value: Raw sensor value
        target_type: Target type to convert to (int, float, str)
        device_serial: Device serial for logging context
        sensor_name: Sensor name for logging context

    Returns:
        Converted value or None if conversion fails
    """
    if value is None:
        _LOGGER.debug("Cannot convert None value for %s sensor on device %s", sensor_name, device_serial)
        return None

    try:
        converted_value: Any = None
        if target_type == int:
            converted_value = int(value)
        elif target_type == float:
            converted_value = float(value)
        elif target_type == str:
            converted_value = str(value)
        else:
            _LOGGER.warning(
                "Unsupported target type %s for %s sensor on device %s", target_type, sensor_name, device_serial
            )
            return None

        _LOGGER.debug(
            "Successfully converted %s sensor value for device %s: %s -> %s (%s)",
            sensor_name,
            device_serial,
            value,
            converted_value,
            target_type.__name__,
        )
        return converted_value

    except (ValueError, TypeError, OverflowError) as e:
        _LOGGER.warning(
            "Failed to convert %s sensor value for device %s: %s -> %s (%s)",
            sensor_name,
            device_serial,
            value,
            target_type.__name__,
            e,
        )
        return None
    except Exception as e:
        _LOGGER.error("Unexpected error converting %s sensor value for device %s: %s", sensor_name, device_serial, e)
        return None


def create_device_config_data(
    serial_number: str,
    discovery_method: str,
    device_name: Optional[str] = None,
    hostname: Optional[str] = None,
    credential: Optional[str] = None,
    mqtt_prefix: Optional[str] = None,
    device_category: Optional[Any] = None,
    capabilities: Optional[Any] = None,
    connection_type: Optional[str] = None,
    username: Optional[str] = None,
    auth_token: Optional[str] = None,
    product_type: Optional[str] = None,
    category: Optional[str] = None,
    parent_entry_id: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Create standardized device configuration data.

    This consolidates the config data creation logic used by both
    manual and cloud device setup flows.

    Args:
        serial_number: Device serial number (required)
        discovery_method: How device was discovered (required)
        device_name: Human-readable device name
        hostname: Device IP/hostname for local connection
        credential: Device credential for MQTT
        mqtt_prefix: MQTT topic prefix
        device_category: Device category (normalized to list)
        capabilities: Device capabilities (normalized to list)
        connection_type: Connection preference
        username: Cloud username/email
        auth_token: Cloud authentication token
        product_type: Product type from cloud
        category: Raw category from cloud (for compatibility)
        parent_entry_id: Link to parent account entry
        **kwargs: Additional fields to include

    Returns:
        Dictionary of config entry data
    """
    # Start with required fields
    config_data: Dict[str, Any] = {
        CONF_SERIAL_NUMBER: serial_number,
        CONF_DISCOVERY_METHOD: discovery_method,
    }

    # Add optional fields
    _add_optional_fields(
        config_data,
        {
            "device_name": device_name,
            CONF_HOSTNAME: hostname,
            CONF_CREDENTIAL: credential,
            CONF_MQTT_PREFIX: mqtt_prefix,
            "connection_type": connection_type,
            CONF_USERNAME: username,
            "auth_token": auth_token,
            "product_type": product_type,
            "category": category,
            "parent_entry_id": parent_entry_id,
        },
    )

    # Normalize and add device category and capabilities
    config_data["device_category"] = normalize_device_category(device_category)
    config_data["capabilities"] = normalize_capabilities(capabilities)

    # Add any additional fields
    config_data.update(kwargs)

    return config_data


def _add_optional_fields(config_data: Dict[str, Any], optional_fields: Dict[str, Any]) -> None:
    """Add optional fields to config data if they are not None."""
    for key, value in optional_fields.items():
        if value is not None:
            config_data[key] = value


def create_manual_device_config(
    serial_number: str,
    credential: str,
    mqtt_prefix: str,
    device_name: Optional[str] = None,
    hostname: Optional[str] = None,
    device_category: Optional[Any] = None,
    capabilities: Optional[Any] = None,
) -> Dict[str, Any]:
    """Create config data for manually configured device.

    Args:
        serial_number: Device serial number
        credential: Device WiFi credential
        mqtt_prefix: MQTT topic prefix
        device_name: Human-readable device name
        hostname: Device IP/hostname
        device_category: Device category
        capabilities: Device capabilities

    Returns:
        Dictionary of config entry data for manual device
    """
    return create_device_config_data(
        serial_number=serial_number,
        discovery_method=DISCOVERY_MANUAL,
        device_name=device_name or f"Dyson {serial_number}",
        hostname=hostname,
        credential=credential,
        mqtt_prefix=mqtt_prefix,
        device_category=device_category or ["ec"],
        capabilities=capabilities or [],
        connection_type=CONNECTION_TYPE_LOCAL_ONLY,  # Default for manual
    )


def create_cloud_device_config(
    serial_number: str,
    username: str,
    device_info: Dict[str, Any],
    auth_token: Optional[str] = None,
    parent_entry_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create config data for cloud-discovered device.

    Args:
        serial_number: Device serial number
        username: Cloud account username/email
        device_info: Device information from cloud API
        auth_token: Authentication token
        parent_entry_id: Parent account entry ID

    Returns:
        Dictionary of config entry data for cloud device
    """
    return create_device_config_data(
        serial_number=serial_number,
        discovery_method=DISCOVERY_CLOUD,
        device_name=device_info.get("name"),
        username=username,
        auth_token=auth_token,
        product_type=device_info.get("product_type"),
        category=device_info.get("category"),
        device_category=device_info.get("category"),
        capabilities=[],  # Will be extracted during coordinator setup
        parent_entry_id=parent_entry_id,
    )
