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


def normalize_capabilities(capabilities: Any) -> List[str]:
    """Normalize device capabilities to a consistent list format.

    Args:
        capabilities: Can be list, None, or other types

    Returns:
        List of capability strings, empty list if invalid
    """
    if capabilities is None:
        return []

    if isinstance(capabilities, list):
        # Convert enum objects to their string values, otherwise use str()
        result = []
        for cap in capabilities:
            if cap:  # Skip empty/None values
                if hasattr(cap, "value"):
                    result.append(cap.value)  # Use enum value
                else:
                    result.append(str(cap))  # Fallback to string conversion
        return result

    # Single capability as string
    if isinstance(capabilities, str):
        return [capabilities]

    _LOGGER.warning("Unknown capabilities type %s, defaulting to []", type(capabilities))
    return []


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
    config_data = {
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
