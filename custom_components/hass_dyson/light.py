"""Light platform for Dyson BLE lights (Lightcycle Morph CD06).

This module registers the :class:`DysonLightEntity` entity, which controls
a Dyson Lightcycle Morph lamp over Bluetooth Low Energy.

The entity supports:
- On / off control
- Brightness (0-255 HA scale ↔ 1-100 lamp percent)
- Color temperature (mired input ↔ Kelvin wire protocol, 2700-6500 K)

No MQTT is required.  State is received from the event bus via
:class:`.coordinator.DysonBLEDataUpdateCoordinator`.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BLE_MAX_KELVIN,
    BLE_MIN_KELVIN,
    DOMAIN,
)
from .coordinator import DysonBLEDataUpdateCoordinator
from .entity import DysonBLEEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dyson BLE light entities from a config entry.

    Args:
        hass: Home Assistant instance.
        config_entry: Config entry for this device.
        async_add_entities: Callback to register new entities.
    """
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: DysonBLEDataUpdateCoordinator = data["ble_coordinator"]
    async_add_entities([DysonLightEntity(coordinator)])


class DysonLightEntity(DysonBLEEntity, LightEntity):
    """Represent a Dyson Lightcycle Morph lamp in Home Assistant.

    Provides on/off, brightness, and color temperature control via the
    BLE GATT protocol, using :class:`.ble_device.DysonBLEDevice` as the
    transport layer.

    Attributes:
        _attr_supported_color_modes: ``{ColorMode.COLOR_TEMP}``
        _attr_color_mode: Always ``ColorMode.COLOR_TEMP``
        _attr_min_color_temp_kelvin: 2700 K (warm white)
        _attr_max_color_temp_kelvin: 6500 K (cool daylight)
    """

    _attr_supported_color_modes: set[ColorMode] = {ColorMode.COLOR_TEMP}
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_min_color_temp_kelvin = BLE_MIN_KELVIN
    _attr_max_color_temp_kelvin = BLE_MAX_KELVIN

    def __init__(self, coordinator: DysonBLEDataUpdateCoordinator) -> None:
        """Initialise the light entity.

        Args:
            coordinator: BLE data update coordinator for this device.
        """
        super().__init__(coordinator)
        serial = coordinator.serial_number
        self._attr_unique_id = f"{serial}_light"
        self._attr_name = "Light"

    # ── State properties ──────────────────────────────────────────────────────

    @property
    def is_on(self) -> bool | None:
        """Return True when the lamp is powered on."""
        data = self.coordinator.data
        if data is None:
            return None
        return bool(data.get("power"))

    @property
    def brightness(self) -> int | None:
        """Return current brightness on the 0-255 HA scale."""
        data = self.coordinator.data
        if data is None:
            return None
        return data.get("brightness")

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return current color temperature in Kelvin."""
        data = self.coordinator.data
        if data is None:
            return None
        return data.get("color_temp_kelvin")

    # ── Command service calls ─────────────────────────────────────────────────

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the lamp on, optionally updating brightness or color temperature.

        Args:
            **kwargs: Optional HA service call keyword arguments:
                - ``brightness``: 0-255 HA brightness value
                - ``color_temp_kelvin``: Color temperature in Kelvin (preferred)
                - ``color_temp``: Color temperature in mired (fallback)
        """
        dev = self.coordinator.ble_device
        if dev is None:
            _LOGGER.warning(
                "No BLE device available for %s", self.coordinator.serial_number
            )
            return

        await dev.set_power(on=True)

        if ATTR_BRIGHTNESS in kwargs:
            await dev.set_brightness(kwargs[ATTR_BRIGHTNESS])

        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            await dev.set_color_temp_kelvin(kwargs[ATTR_COLOR_TEMP_KELVIN])

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the lamp off.

        Args:
            **kwargs: Unused HA service call keyword arguments.
        """
        dev = self.coordinator.ble_device
        if dev is None:
            _LOGGER.warning(
                "No BLE device available for %s", self.coordinator.serial_number
            )
            return
        await dev.set_power(on=False)
