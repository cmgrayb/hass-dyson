"""Single place that decides what kind of device a config entry is.

Before this module every platform sniffed ``hass.data[DOMAIN][entry_id]`` for
``is_ble`` / ``is_ble_vacuum`` flags and fell through to the MQTT path when it
did not recognise them.  Adding a device family therefore meant editing every
platform file, and missing one failed *silently*: forwarding a BLE vacuum entry
to ``select``/``switch`` raised ``'dict' object has no attribute
'device_capabilities'`` at runtime while setup still logged success.

Platforms call :func:`async_route_ble_platform` instead.  For families listed
in :data:`_BLE_PLATFORM_MODULES` the table below is the only thing that needs
to change, and a platform the family does not implement is a clean no-op
rather than a fall-through.

Scope note: only the floor-care vacuum is table-driven today.  The BLE light
still builds its entities inline inside each platform, so the router reports
"not mine" for it and those platforms keep their existing branches.  Migrating
the light needs characterisation tests for its connect/auth path first — it
sits below 50% coverage and there is no lamp on hand to catch a regression.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.importlib import async_import_module

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEVICE_KIND_MQTT = "mqtt"
DEVICE_KIND_BLE_LIGHT = "ble_light"
DEVICE_KIND_BLE_VACUUM = "ble_vacuum"

# Marker key stored in hass.data[DOMAIN][entry_id] for each BLE family, and the
# key its coordinator lives under.
_BLE_ENTRY_MARKERS: dict[str, tuple[str, str]] = {
    DEVICE_KIND_BLE_VACUUM: ("is_ble_vacuum", "ble_vacuum_coordinator"),
    DEVICE_KIND_BLE_LIGHT: ("is_ble", "ble_coordinator"),
}

# device kind -> {platform: module implementing async_setup_entry}.
# A family present here is fully table-driven: a platform missing from its map
# is a no-op, never a fall-through to the MQTT path.
_BLE_PLATFORM_MODULES: dict[str, dict[str, str]] = {
    DEVICE_KIND_BLE_VACUUM: {
        "sensor": "ble_vacuum_sensor",
        "binary_sensor": "ble_vacuum_binary_sensor",
        "select": "ble_vacuum_select",
        "switch": "ble_vacuum_switch",
        "update": "ble_vacuum_update",
    },
}

# Platforms each BLE family forwards during entry setup.  Kept beside the
# routing table so the two cannot drift apart.
BLE_PLATFORMS: dict[str, list[str]] = {
    DEVICE_KIND_BLE_VACUUM: ["sensor", "binary_sensor", "select", "switch", "update"],
    DEVICE_KIND_BLE_LIGHT: ["light", "binary_sensor"],
}


def async_entry_kind(hass: HomeAssistant, entry_id: str) -> str:
    """Return the device family backing a config entry.

    Args:
        hass: Home Assistant instance.
        entry_id: Config entry id.

    Returns:
        ``DEVICE_KIND_BLE_VACUUM``, ``DEVICE_KIND_BLE_LIGHT``, or
        ``DEVICE_KIND_MQTT`` for cloud/MQTT coordinators.
    """
    entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
    if isinstance(entry_data, dict):
        for kind, (marker, _coord_key) in _BLE_ENTRY_MARKERS.items():
            if entry_data.get(marker):
                return kind
    return DEVICE_KIND_MQTT


def async_ble_coordinator(hass: HomeAssistant, entry_id: str) -> Any | None:
    """Return the BLE coordinator for an entry, or None if it is not BLE."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
    if not isinstance(entry_data, dict):
        return None
    kind = async_entry_kind(hass, entry_id)
    marker = _BLE_ENTRY_MARKERS.get(kind)
    if marker is None:
        return None
    return entry_data.get(marker[1])


async def async_route_ble_platform(
    hass: HomeAssistant,
    config_entry: Any,
    async_add_entities: Any,
    platform: str,
) -> bool | None:
    """Hand a table-driven BLE entry to the module owning ``platform``.

    Args:
        hass: Home Assistant instance.
        config_entry: The config entry being set up.
        async_add_entities: The platform's add-entities callback.
        platform: Platform name, e.g. ``"select"``.

    Returns:
        ``None`` when this router is not responsible — the entry is MQTT, or a
        BLE family that still builds its entities inline — and the caller should
        continue with its own setup.  ``True``/``False`` when the router has
        taken responsibility, including the no-op case where the family has no
        entities on that platform.
    """
    kind = async_entry_kind(hass, config_entry.entry_id)
    platform_modules = _BLE_PLATFORM_MODULES.get(kind)
    if platform_modules is None:
        # MQTT, or a BLE family handled inline by the platform itself.
        return None

    module_name = platform_modules.get(platform)
    if module_name is None:
        # Table-driven family with nothing on this platform.  Claiming it keeps
        # the entry away from the MQTT path, which would raise on the dict.
        _LOGGER.debug(
            "No %s entities for %s entries; skipping platform", platform, kind
        )
        return True

    # Import off the event loop: a cold import touches the filesystem, and HA
    # flags importlib.import_module() here as a blocking call.
    module = await async_import_module(hass, f"{__package__}.{module_name}")
    result = await module.async_setup_entry(hass, config_entry, async_add_entities)
    return True if result is None else bool(result)
