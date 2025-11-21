"""Utility functions for device configuration and setup."""

import logging
from typing import Any

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


def normalize_device_category(category: Any) -> list[str]:
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


def normalize_capabilities(capabilities: Any) -> list[str]:  # noqa: C901
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
            elif isinstance(cap, int | float) and cap == 0:
                _LOGGER.warning("Found zero numeric capability in list, skipping")
                continue
            else:
                try:
                    if hasattr(cap, "value") and not isinstance(cap, int | float | str):
                        normalized_cap = str(cap.value)
                    else:
                        normalized_cap = str(cap)

                    # Validate that the normalized capability is meaningful
                    if normalized_cap.strip():
                        result.append(normalized_cap)
                        _LOGGER.debug(
                            "Normalized capability: %s -> %s", cap, normalized_cap
                        )
                    else:
                        _LOGGER.warning(
                            "Capability normalized to empty string, skipping: %s", cap
                        )
                except Exception as e:
                    _LOGGER.error(
                        "Failed to normalize capability %s (type: %s): %s",
                        cap,
                        type(cap),
                        e,
                    )
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
        if hasattr(capabilities, "value") and not isinstance(
            capabilities, int | float | str
        ):
            normalized = str(capabilities.value)
        else:
            normalized = str(capabilities)

        if normalized.strip():
            _LOGGER.debug(
                "Normalized non-standard capability: %s -> %s", capabilities, normalized
            )
            return [normalized]
        else:
            _LOGGER.warning(
                "Non-standard capability normalized to empty string: %s", capabilities
            )
            return []
    except Exception as e:
        _LOGGER.error(
            "Failed to normalize capabilities %s (type: %s): %s",
            capabilities,
            type(capabilities),
            e,
        )
        return []


def extract_capabilities_from_device_info(device_info: Any) -> list[str]:
    """Extract device capabilities from cloud device info.

    This function mirrors the logic from coordinator._extract_capabilities
    to ensure capabilities are available during config entry creation.

    Args:
        device_info: Device info object from libdyson-rest

    Returns:
        List of device capabilities
    """
    capabilities: list[str] = []

    # Get capabilities from device info if available
    if hasattr(device_info, "capabilities"):
        capabilities = device_info.capabilities or []
    elif hasattr(device_info, "connected_configuration"):
        # Try nested structure: device_info.connected_configuration.firmware.capabilities
        connected_config = device_info.connected_configuration
        if connected_config and hasattr(connected_config, "firmware"):
            firmware = connected_config.firmware
            if firmware and hasattr(firmware, "capabilities"):
                capabilities = firmware.capabilities or []

    # Add virtual capabilities based on product type
    product_type = getattr(
        device_info, "product_type", getattr(device_info, "type", "")
    )

    # Note: We do not want to use product type to determine device capabilities
    # Please do not replicate this functionality.  Instead, extract capabilities
    # from device state in the coordinator as needed.
    # To do: replace product_type.startswith("PH") with a function which determines
    # Humidifier capability from device state.
    if product_type:
        # PH model (Purifier/Humidifier) should have virtual Humidifier capability
        if product_type.startswith("PH"):
            if "Humidifier" not in capabilities:
                capabilities.append("Humidifier")
                _LOGGER.debug(
                    "Added virtual Humidifier capability for PH model %s",
                    product_type,
                )

        # Note: Heating capability detection is handled by the coordinator's
        # _refine_capabilities_from_device_state() method which checks for 'hmod'
        # state key presence. This avoids hardcoding product types.

    _LOGGER.debug("Raw extracted capabilities from device_info: %s", capabilities)
    _LOGGER.debug("Capability types: %s", [type(cap).__name__ for cap in capabilities])

    # Remove duplicates and return
    final_capabilities = list(set(capabilities))
    _LOGGER.debug("Final capabilities after deduplication: %s", final_capabilities)
    return final_capabilities


def has_capability_safe(capabilities: list[str] | None, capability_name: str) -> bool:
    """Safely check if device has a specific capability with case-insensitive matching.

    Args:
        capabilities: List of device capabilities (may be None or malformed)
        capability_name: Name of capability to check for

    Returns:
        True if capability is found, False otherwise
    """
    if not capabilities:
        _LOGGER.debug(
            "No capabilities provided for capability check: %s", capability_name
        )
        return False

    if not isinstance(capabilities, list):
        _LOGGER.warning(
            "Capabilities is not a list, cannot check for capability: %s",
            capability_name,
        )
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
                _LOGGER.warning(
                    "Failed to normalize capability for comparison %s: %s", cap, e
                )
                continue

        # Check for matches
        has_capability = search_term in normalized_caps
        _LOGGER.debug(
            "Capability check: '%s' in %s = %s",
            search_term,
            normalized_caps,
            has_capability,
        )
        return has_capability

    except Exception as e:
        _LOGGER.error("Error during capability check for '%s': %s", capability_name, e)
        return False


def has_any_capability_safe(
    capabilities: list[str] | None, capability_names: list[str]
) -> bool:
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
            _LOGGER.debug(
                "Found capability '%s' in any-capability check", capability_name
            )
            return True

    _LOGGER.debug(
        "No capabilities found in any-capability check for: %s", capability_names
    )
    return False


def get_sensor_data_safe(
    data: dict[str, Any] | None, key: str, device_serial: str = "unknown"
) -> Any:
    """Safely extract sensor data with proper error handling and logging.

    Args:
        data: Dictionary containing sensor data (may be None)
        key: Key to extract from data
        device_serial: Device serial for logging context

    Returns:
        The value if found and valid, None otherwise
    """
    if data is None:
        _LOGGER.debug(
            "No data available for sensor key '%s' on device %s", key, device_serial
        )
        return None

    if not isinstance(data, dict):
        _LOGGER.warning(
            "Data is not a dictionary for sensor key '%s' on device %s (type: %s)",
            key,
            device_serial,
            type(data),
        )
        return None

    try:
        value = data.get(key)
        if value is None:
            _LOGGER.debug(
                "Sensor key '%s' not found in data for device %s", key, device_serial
            )
            return None

        # Log successful data access
        _LOGGER.debug(
            "Successfully extracted sensor data for key '%s' on device %s: %s",
            key,
            device_serial,
            value,
        )
        return value

    except Exception as e:
        _LOGGER.error(
            "Error accessing sensor data for key '%s' on device %s: %s",
            key,
            device_serial,
            e,
        )
        return None


def convert_sensor_value_safe(
    value: Any,
    target_type: type,
    device_serial: str = "unknown",
    sensor_name: str = "unknown",
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
        _LOGGER.debug(
            "Cannot convert None value for %s sensor on device %s",
            sensor_name,
            device_serial,
        )
        return None

    try:
        converted_value: Any = None
        if target_type is int:
            converted_value = int(value)
        elif target_type is float:
            converted_value = float(value)
        elif target_type is str:
            converted_value = str(value)
        else:
            _LOGGER.warning(
                "Unsupported target type %s for %s sensor on device %s",
                target_type,
                sensor_name,
                device_serial,
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
        _LOGGER.error(
            "Unexpected error converting %s sensor value for device %s: %s",
            sensor_name,
            device_serial,
            e,
        )
        return None


def create_device_config_data(
    serial_number: str,
    discovery_method: str,
    device_name: str | None = None,
    hostname: str | None = None,
    credential: str | None = None,
    mqtt_prefix: str | None = None,
    device_category: Any | None = None,
    capabilities: Any | None = None,
    connection_type: str | None = None,
    username: str | None = None,
    auth_token: str | None = None,
    product_type: str | None = None,
    category: str | None = None,
    parent_entry_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
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
    config_data: dict[str, Any] = {
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


def _add_optional_fields(
    config_data: dict[str, Any], optional_fields: dict[str, Any]
) -> None:
    """Add optional fields to config data if they are not None."""
    for key, value in optional_fields.items():
        if value is not None:
            config_data[key] = value


def create_manual_device_config(
    serial_number: str,
    credential: str,
    mqtt_prefix: str,
    device_name: str | None = None,
    hostname: str | None = None,
    device_category: Any | None = None,
    capabilities: Any | None = None,
) -> dict[str, Any]:
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
    device_info: dict[str, Any] | Any,
    auth_token: str | None = None,
    parent_entry_id: str | None = None,
) -> dict[str, Any]:
    """Create config data for cloud-discovered device.

    Args:
        serial_number: Device serial number
        username: Cloud account username/email
        device_info: Device information from cloud API (dict or object)
        auth_token: Authentication token
        parent_entry_id: Parent account entry ID

    Returns:
        Dictionary of config entry data for cloud device
    """
    # Extract capabilities from device_info if it's a libdyson-rest object
    capabilities = []
    if hasattr(device_info, "capabilities") or hasattr(
        device_info, "connected_configuration"
    ):
        # This is a libdyson-rest device object with capability data
        capabilities = extract_capabilities_from_device_info(device_info)
        _LOGGER.debug(
            "Extracted capabilities for %s during config creation: %s",
            serial_number,
            capabilities,
        )
    elif isinstance(device_info, dict):
        # This is already a dict (like from config flow discovery)
        capabilities = device_info.get("capabilities", [])

    # Get device info values (handle both dict and object)
    if isinstance(device_info, dict):
        device_name = device_info.get("name")
        product_type = device_info.get("product_type")
        category = device_info.get("category")
    else:
        device_name = getattr(device_info, "name", None)
        product_type = getattr(device_info, "product_type", None)
        category = getattr(device_info, "category", None)

    return create_device_config_data(
        serial_number=serial_number,
        discovery_method=DISCOVERY_CLOUD,
        device_name=device_name,
        username=username,
        auth_token=auth_token,
        product_type=product_type,
        category=category,
        device_category=category,
        capabilities=capabilities,  # Now properly extracted from device_info
        parent_entry_id=parent_entry_id,
    )
