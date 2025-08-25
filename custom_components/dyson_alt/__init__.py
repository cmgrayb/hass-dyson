"""The Dyson Alternative integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_SERIAL_NUMBER,
    DISCOVERY_CLOUD,
    DISCOVERY_STICKER,
    DOMAIN,
)
from .coordinator import DysonDataUpdateCoordinator
from .services import async_setup_services, async_remove_services

# Import config flow explicitly to ensure it's available for registration
from .config_flow import DysonConfigFlow  # noqa: F401

_LOGGER = logging.getLogger(__name__)

# YAML Configuration Schema
DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_NUMBER): cv.string,
        vol.Optional("discovery_method", default=DISCOVERY_CLOUD): vol.In([DISCOVERY_CLOUD, DISCOVERY_STICKER]),
        vol.Optional("hostname"): cv.string,
        vol.Optional("credential"): cv.string,
        vol.Optional("capabilities", default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional("username"): cv.string,
                vol.Optional("password"): cv.string,
                vol.Optional("devices", default=[]): vol.All(cv.ensure_list, [DEVICE_SCHEMA]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS_MAP = {
    Platform.FAN: "fan",
    Platform.SENSOR: "sensor",
    Platform.BINARY_SENSOR: "binary_sensor",
    Platform.BUTTON: "button",
    Platform.NUMBER: "number",
    Platform.SELECT: "select",
    Platform.SWITCH: "switch",
    Platform.VACUUM: "vacuum",
    Platform.CLIMATE: "climate",
}


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up Dyson Alternative integration from YAML configuration."""
    domain_config = config.get(DOMAIN, {})
    devices = domain_config.get("devices", [])

    if not devices:
        _LOGGER.debug("No devices configured in YAML, skipping YAML setup")
        return True

    _LOGGER.info("Setting up %d device(s) from YAML configuration", len(devices))

    # Extract cloud credentials from YAML
    cloud_username = domain_config.get("username")
    cloud_password = domain_config.get("password")

    # Import here to avoid circular imports
    from homeassistant.config_entries import SOURCE_IMPORT

    for device_config in devices:
        # Check if device is already configured
        existing_entries = [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.data.get(CONF_SERIAL_NUMBER) == device_config[CONF_SERIAL_NUMBER]
        ]

        if existing_entries:
            _LOGGER.debug(
                "Device %s already configured via config entry, skipping YAML setup", device_config[CONF_SERIAL_NUMBER]
            )
            continue

        # Create a config entry from YAML data
        _LOGGER.debug("Creating config entry for device: %s", device_config[CONF_SERIAL_NUMBER])

        # Prepare config entry data
        entry_data = {
            CONF_SERIAL_NUMBER: device_config[CONF_SERIAL_NUMBER],
            "discovery_method": device_config.get("discovery_method", DISCOVERY_CLOUD),
        }

        # Add cloud credentials if provided and device uses cloud discovery
        if (
            device_config.get("discovery_method", DISCOVERY_CLOUD) == DISCOVERY_CLOUD
            and cloud_username
            and cloud_password
        ):
            entry_data[CONF_USERNAME] = cloud_username
            entry_data[CONF_PASSWORD] = cloud_password

        # Add optional fields if present
        if "hostname" in device_config:
            entry_data["hostname"] = device_config["hostname"]
        if "credential" in device_config:
            entry_data["credential"] = device_config["credential"]
        if "capabilities" in device_config:
            entry_data["capabilities"] = device_config["capabilities"]

        # Create config entry
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=entry_data,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dyson Alternative from a config entry."""
    _LOGGER.debug("Setting up Dyson Alternative integration for device: %s", entry.title)

    try:
        # Create data update coordinator
        coordinator = DysonDataUpdateCoordinator(hass, entry)

        # Perform initial data fetch
        await coordinator.async_config_entry_first_refresh()

        # Store coordinator in hass data
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = coordinator

        # Determine which platforms to set up based on device capabilities
        platforms_to_setup = _get_platforms_for_device(coordinator)

        # Forward setup to platforms
        await hass.config_entries.async_forward_entry_setups(entry, platforms_to_setup)

        # Set up services (only once when first device is added)
        if len(hass.data[DOMAIN]) == 1:
            await async_setup_services(hass)

        _LOGGER.info("Successfully set up Dyson device '%s' with platforms: %s", entry.title, platforms_to_setup)

        return True

    except Exception as err:
        _LOGGER.error("Failed to set up Dyson device '%s': %s", entry.title, err)
        raise ConfigEntryNotReady(f"Failed to connect to Dyson device: {err}") from err


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Dyson Alternative config entry."""
    _LOGGER.debug("Unloading Dyson Alternative integration for device: %s", entry.title)

    # Get coordinator
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Determine platforms that were set up
    platforms_to_unload = _get_platforms_for_device(coordinator)

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms_to_unload)

    if unload_ok:
        # Clean up coordinator
        await coordinator.async_shutdown()
        hass.data[DOMAIN].pop(entry.entry_id)

        # Remove services if this was the last device
        if not hass.data[DOMAIN]:
            await async_remove_services(hass)

        _LOGGER.info("Successfully unloaded Dyson device '%s'", entry.title)

    return unload_ok


def _get_platforms_for_device(coordinator: DysonDataUpdateCoordinator) -> list[str]:
    """Determine which platforms should be set up for this device."""
    device_capabilities = coordinator.device_capabilities
    device_category = coordinator.device_category
    platforms = []

    # Base platforms for all devices
    platforms.extend(["sensor", "binary_sensor", "button"])

    # Device category specific platforms
    if device_category in ["ec"]:  # Environment Cleaner (fans with filters)
        platforms.extend(["fan", "climate"])

    elif device_category in ["robot", "vacuum", "flrc"]:  # Cleaning devices
        platforms.append("vacuum")

    # Capability-based platforms
    if "AdvanceOscillationDay1" in device_capabilities:
        platforms.extend(["number", "switch"])  # For oscillation controls

    if "Scheduling" in device_capabilities:
        platforms.append("number")  # For sleep timer

    if "ExtendedAQ" in device_capabilities:
        platforms.append("switch")  # For continuous monitoring

    # Remove duplicates and return
    return list(set(platforms))
