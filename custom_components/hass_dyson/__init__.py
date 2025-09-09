"""The Dyson integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

# Import config flow explicitly to ensure it's available for registration
from .config_flow import DysonConfigFlow  # noqa: F401
from .const import (
    CONF_AUTO_ADD_DEVICES,
    CONF_POLL_FOR_DEVICES,
    CONF_SERIAL_NUMBER,
    DEFAULT_AUTO_ADD_DEVICES,
    DEFAULT_POLL_FOR_DEVICES,
    DISCOVERY_CLOUD,
    DISCOVERY_MANUAL,
    DISCOVERY_STICKER,
    DOMAIN,
)
from .coordinator import DysonCloudAccountCoordinator, DysonDataUpdateCoordinator
from .services import async_remove_services, async_setup_services

_LOGGER = logging.getLogger(__name__)

# YAML Configuration Schema
DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_NUMBER): cv.string,
        vol.Optional("discovery_method", default=DISCOVERY_CLOUD): vol.In(
            [DISCOVERY_CLOUD, DISCOVERY_STICKER, DISCOVERY_MANUAL]
        ),
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
    """Set up Dyson integration from YAML configuration."""
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


async def _create_device_entry(hass: HomeAssistant, device_data: dict, device_info: dict) -> None:
    """Create a device config entry as a background task."""
    device_serial = device_data.get(CONF_SERIAL_NUMBER, "unknown")

    try:
        _LOGGER.info("Background task: Creating device entry for %s", device_serial)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "device_auto_create"},
            data=device_data,
        )
        _LOGGER.info("Background task: Device entry creation result: %s", result)

    except Exception as e:
        _LOGGER.error("Background task: Failed to create device entry for %s: %s", device_serial, e)


async def _create_discovery_flow(hass: HomeAssistant, entry: ConfigEntry, device_info: dict) -> None:
    """Create a discovery flow for manual device confirmation as a background task."""
    device_serial = device_info.get("serial_number", "unknown")
    device_name = device_info.get("name", f"Dyson {device_serial}")

    try:
        _LOGGER.info("Background task: Creating discovery flow for %s (%s)", device_name, device_serial)

        # Check if discovery already exists for this device
        existing_flows = [
            flow
            for flow in hass.config_entries.flow.async_progress()
            if (
                flow["handler"] == DOMAIN
                and flow.get("context", {}).get("source") == "discovery"
                and flow.get("context", {}).get("unique_id") == device_serial
            )
        ]

        if existing_flows:
            _LOGGER.debug("Discovery flow already exists for device %s", device_serial)
            return

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": "discovery",
                "unique_id": device_serial,
                "title_placeholders": {"device_name": device_name},
            },
            data={
                "serial_number": device_serial,
                "name": device_name,
                "product_type": device_info.get("product_type", "unknown"),
                "category": device_info.get("category", "unknown"),
                "auth_token": entry.data.get("auth_token"),
                "email": entry.data.get("email"),
                "parent_entry_id": entry.entry_id,
            },
        )
        _LOGGER.info("Background task: Discovery flow creation result for %s: %s", device_name, result)

    except Exception as e:
        _LOGGER.error("Background task: Failed to create discovery flow for %s: %s", device_serial, e)


async def _setup_account_level_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up account-level config entry with multiple devices."""
    _LOGGER.info("Setting up account-level entry with %d devices", len(entry.data["devices"]))
    devices = entry.data["devices"]

    # Get auto_add_devices setting with backward-compatible default
    auto_add_devices = entry.data.get(CONF_AUTO_ADD_DEVICES, DEFAULT_AUTO_ADD_DEVICES)
    _LOGGER.info("Auto-add devices setting: %s", auto_add_devices)

    # Process each device
    await _process_account_devices(hass, entry, devices, auto_add_devices)

    # Set up cloud account coordinator for device polling if enabled
    await _setup_cloud_coordinator(hass, entry)

    _LOGGER.info("Account entry setup complete - individual device entries will be created")
    return True


async def _process_account_devices(
    hass: HomeAssistant, entry: ConfigEntry, devices: list, auto_add_devices: bool
) -> None:
    """Process devices for account-level entry."""
    for device_info in devices:
        device_serial = device_info["serial_number"]

        # Check if device already has its own config entry
        existing_entries = [
            existing_entry
            for existing_entry in hass.config_entries.async_entries(DOMAIN)
            if (
                existing_entry.data.get(CONF_SERIAL_NUMBER) == device_serial
                and existing_entry.entry_id != entry.entry_id
            )
        ]

        if existing_entries:
            continue

        # Get polling setting to determine if devices should be processed
        poll_for_devices = entry.data.get(CONF_POLL_FOR_DEVICES, DEFAULT_POLL_FOR_DEVICES)

        if not poll_for_devices:
            _LOGGER.debug(
                "Device %s found in stored data but polling is disabled - skipping device processing",
                device_serial,
            )
            continue

        await _handle_new_device(hass, entry, device_info, auto_add_devices)


async def _handle_new_device(
    hass: HomeAssistant, entry: ConfigEntry, device_info: dict, auto_add_devices: bool
) -> None:
    """Handle setup for a new device."""
    device_serial = device_info["serial_number"]

    if auto_add_devices:
        # Create individual config entry for this device
        from .device_utils import create_cloud_device_config

        device_data = create_cloud_device_config(
            serial_number=device_serial,
            username=entry.data.get("email", ""),
            device_info=device_info,
            auth_token=entry.data.get("auth_token"),
            parent_entry_id=entry.entry_id,
        )

        _LOGGER.info("Auto-creating individual config entry for device: %s", device_serial)
        # Schedule device entry creation as a background task
        hass.async_create_background_task(
            _create_device_entry(hass, device_data, device_info),
            f"dyson_create_device_{device_serial}",
        )
    else:
        _LOGGER.info(
            "Device %s discovered but auto-add disabled - device will be available for manual setup",
            device_serial,
        )
        # Create discovery flow for manual device confirmation
        hass.async_create_background_task(
            _create_discovery_flow(hass, entry, device_info),
            f"dyson_discovery_{device_serial}",
        )


async def _setup_cloud_coordinator(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up cloud account coordinator for device polling if enabled."""
    poll_for_devices = entry.data.get(CONF_POLL_FOR_DEVICES, DEFAULT_POLL_FOR_DEVICES)

    if poll_for_devices:
        cloud_coordinator = DysonCloudAccountCoordinator(hass, entry)

        # Store coordinator in hass data
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][f"{entry.entry_id}_cloud"] = cloud_coordinator

        # Start the coordinator
        await cloud_coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Cloud device polling coordinator started for account: %s", entry.data.get("email"))
    else:
        _LOGGER.info("Cloud device polling disabled for account: %s", entry.data.get("email"))


async def _setup_individual_device_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up individual device config entry."""
    _LOGGER.debug("Setting up individual device config entry")
    coordinator = DysonDataUpdateCoordinator(hass, entry)

    # Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Check for firmware updates if this is a cloud device
    await _check_firmware_updates(coordinator, entry)

    # Set up platforms and services
    await _setup_platforms_and_services(hass, entry, coordinator)

    _LOGGER.info("Successfully set up Dyson device '%s'", coordinator.serial_number)
    return True


async def _check_firmware_updates(coordinator: "DysonDataUpdateCoordinator", entry: ConfigEntry) -> None:
    """Check for firmware updates if this is a cloud device."""
    from .const import CONF_DISCOVERY_METHOD, DISCOVERY_CLOUD

    if entry.data.get(CONF_DISCOVERY_METHOD) == DISCOVERY_CLOUD:
        try:
            await coordinator.async_check_firmware_update()
        except Exception as err:
            _LOGGER.debug("Initial firmware update check failed for %s: %s", coordinator.serial_number, err)


async def _setup_platforms_and_services(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: "DysonDataUpdateCoordinator"
) -> None:
    """Set up platforms and services for the device."""
    # Determine which platforms to set up based on device capabilities
    platforms_to_setup = _get_platforms_for_device(coordinator)

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, platforms_to_setup)

    # Set up services (only once when first device is added)
    if not any(key == "services_setup" for key in hass.data.get(DOMAIN, {})):
        await async_setup_services(hass)
        hass.data.setdefault(DOMAIN, {})["services_setup"] = True

    _LOGGER.info("Set up platforms: %s", platforms_to_setup)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # noqa: C901
    """Set up Dyson from a config entry."""
    _LOGGER.debug("Setting up Dyson integration for device: %s", entry.title)

    try:
        # Check if this is a new account-level config entry with multiple devices
        if "devices" in entry.data and entry.data.get("devices"):
            return await _setup_account_level_entry(hass, entry)
        else:
            # Handle individual device config entries
            return await _setup_individual_device_entry(hass, entry)

    except Exception as err:
        _LOGGER.error("Failed to set up Dyson device '%s': %s", entry.title, err)
        raise ConfigEntryNotReady(f"Failed to connect to Dyson device: {err}") from err


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Dyson config entry."""
    _LOGGER.debug("Unloading Dyson integration for device: %s", entry.title)

    # Check if this is an account-level entry
    if "devices" in entry.data and entry.data.get("devices"):
        _LOGGER.info("Unloading account-level entry - removing child device entries")

        # Clean up cloud coordinator if it exists
        cloud_coordinator_key = f"{entry.entry_id}_cloud"
        if cloud_coordinator_key in hass.data.get(DOMAIN, {}):
            cloud_coordinator = hass.data[DOMAIN][cloud_coordinator_key]
            await cloud_coordinator.async_shutdown()
            hass.data[DOMAIN].pop(cloud_coordinator_key)
            _LOGGER.info("Cloud coordinator cleaned up for account entry")

        # Find and remove all child device entries
        device_entries_to_remove = [
            device_entry
            for device_entry in hass.config_entries.async_entries(DOMAIN)
            if device_entry.data.get("parent_entry_id") == entry.entry_id
        ]

        for device_entry in device_entries_to_remove:
            _LOGGER.info("Removing child device entry: %s", device_entry.title)
            await hass.config_entries.async_remove(device_entry.entry_id)

        # Account entries don't have coordinators themselves
        return True

    # Handle individual device entries
    if entry.entry_id not in hass.data.get(DOMAIN, {}):
        _LOGGER.warning("No coordinator found for entry %s", entry.entry_id)
        return True

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
        if not hass.data[DOMAIN] or all(key == "services_setup" for key in hass.data[DOMAIN]):
            await async_remove_services(hass)

        _LOGGER.info("Successfully unloaded Dyson device '%s'", entry.title)

    return unload_ok


def _get_platforms_for_device(coordinator: DysonDataUpdateCoordinator) -> list[str]:
    """Determine which platforms should be set up for this device."""
    device_category = coordinator.device_category  # This is now a list
    device_capabilities = coordinator.device_capabilities
    platforms = []

    # Base platforms for all devices
    platforms.extend(["sensor", "binary_sensor", "button"])

    # Device category specific platforms - check if any category matches
    if any(cat in ["ec"] for cat in device_category):  # Environment Cleaner (fans with filters)
        # For fans, add fan platform and supporting control platforms
        platforms.append("fan")
        # Add number and select platforms for advanced controls
        platforms.extend(["number", "select"])
        # Climate platform for heating/cooling modes if device supports it
        platforms.append("climate")

    elif any(cat in ["robot", "vacuum", "flrc"] for cat in device_category):  # Cleaning devices
        platforms.append("vacuum")

    # Add capability-based platforms for enhanced functionality
    if "Scheduling" in device_capabilities or "AdvanceOscillationDay1" in device_capabilities:
        if "number" not in platforms:
            platforms.append("number")
        if "select" not in platforms:
            platforms.append("select")

    # Add switch platform for devices with switching capabilities
    if "Switch" in device_capabilities or any(cat in ["ec"] for cat in device_category):
        platforms.append("switch")

    # Add update platform for cloud-discovered devices (for firmware updates)
    from .const import CONF_DISCOVERY_METHOD, DISCOVERY_CLOUD

    if coordinator.config_entry.data.get(CONF_DISCOVERY_METHOD) == DISCOVERY_CLOUD:
        platforms.append("update")

    # Remove duplicates and return
    return list(set(platforms))
