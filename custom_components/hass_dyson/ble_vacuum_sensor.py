"""Sensor entities for Dyson BLE floor-cleaning vacuums (e.g. V16).

All values arrive over the BLE attribute protocol (see :mod:`.ble_vacuum`).

This module carries only the genuinely read-only attributes.  Anything the
machine accepts a 0x93 write for lives on the select/switch platforms
instead (brush-bar speed, dust illumination, UI language, task detection,
battery care) — there is deliberately no read-only mirror of a writable
attribute.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BLE_VACUUM_BRUSH_BAR_TYPES,
    BLE_VACUUM_POWER_MODES,
    DOMAIN,
)
from .coordinator import DysonBLEVacuumDataUpdateCoordinator
from .device_utils import mask_serial

_LOGGER = logging.getLogger(__name__)


def _enum_options(value_map: dict[int, str]) -> list[str]:
    """Ordered option labels for an ENUM sensor from a wire-value map."""
    return [label for _v, label in sorted(value_map.items())]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: Any,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up BLE vacuum sensors for a config entry."""
    coordinator: DysonBLEVacuumDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["ble_vacuum_coordinator"]

    # Brush-bar speed, dust illumination and UI language are writable over BLE
    # and are exposed as selects — no read-only mirror of the same attribute.
    entities: list[SensorEntity] = [
        DysonBleVacuumBatteryLevelSensor(coordinator),
        DysonBleVacuumPowerModeSensor(coordinator),
        DysonBleVacuumBrushBarTypeSensor(coordinator),
        DysonBleVacuumBatteryTemperatureSensor(coordinator),
    ]
    async_add_entities(entities)
    return True


class DysonBleVacuumEntity(CoordinatorEntity):
    """Base entity for Dyson BLE vacuum siblings."""

    coordinator: DysonBLEVacuumDataUpdateCoordinator
    _attr_has_entity_name = True

    @property
    def available(self) -> bool:
        """Return True when the vacuum is connected and authenticated."""
        return (
            self.coordinator.last_update_success is not False
            and self.coordinator.is_connected
        )

    @property
    def device_info(self):
        """Return device info for the Home Assistant device registry."""
        if self.coordinator.ble_device is not None:
            return self.coordinator.ble_device.device_info
        return None

    def _attr_value(self, key: str) -> Any:
        """Read one attribute from coordinator data, tolerating absence."""
        data = self.coordinator.data
        if not isinstance(data, dict):
            return None
        return data.get("attributes", {}).get(key)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Push updates to the frontend."""
        self.async_write_ha_state()


class DysonBleVacuumBatteryLevelSensor(DysonBleVacuumEntity, SensorEntity):
    """Battery charge level in percent."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "ble_vacuum_battery_level"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_battery_level"

    @property
    def native_value(self) -> int | None:
        """Return the battery level in percent."""
        value = self._attr_value("battery_level")
        if value is None or isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class _EnumSensorBase(DysonBleVacuumEntity, SensorEntity):
    """Base for enum-valued attribute sensors."""

    _state_key: str = ""
    _options: dict[int, str] = {}
    _attr_device_class = SensorDeviceClass.ENUM

    @property
    def options(self) -> list[str]:
        """Return the possible enum labels for this sensor."""
        return _enum_options(self._options)

    @property
    def native_value(self) -> str | None:
        """Return the current enum label — but never an out-of-options value.

        Home Assistant raises ``ValueError`` for ENUM sensors whose value is
        not in ``options`` (e.g. ``"unknown (ff)"``), so unmapped wire values
        must degrade to ``None`` (unknown) instead.
        """
        value = self._attr_value(self._state_key)
        if value is None:
            return None
        # decode_attribute_value returns "unknown (xx)" for unmapped bytes —
        # those are never in options and must not be reported.
        try:
            label = value if isinstance(value, str) else self._options.get(int(value))
        except (TypeError, ValueError):
            label = None
        if label is None or label not in self.options:
            _LOGGER.debug(
                "%s: attribute %s reported an out-of-options value %r",
                mask_serial(self.coordinator.serial_number),
                self._state_key,
                value,
            )
            return None
        return label


class DysonBleVacuumPowerModeSensor(_EnumSensorBase):
    """Current suction power mode (eco / med / auto / boost)."""

    _state_key = "power_mode"
    _options = BLE_VACUUM_POWER_MODES
    _attr_translation_key = "ble_vacuum_power_mode"
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_power_mode"

    @property
    def icon(self) -> str:
        """Icon follows the power mode."""
        mode = self.native_value
        return {
            "eco": "mdi:fan-speed-1",
            "med": "mdi:fan-speed-2",
            "auto": "mdi:fan-auto",
            "boost": "mdi:fan-speed-3",
        }.get(mode or "", "mdi:fan")


class DysonBleVacuumBrushBarTypeSensor(_EnumSensorBase):
    """Identified brush bar / cleaner head type."""

    _state_key = "brush_bar_type"
    _options = BLE_VACUUM_BRUSH_BAR_TYPES
    _attr_translation_key = "ble_vacuum_brush_bar_type"
    _attr_icon = "mdi:vacuum-outline"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_brush_bar_type"


class DysonBleVacuumBatteryTemperatureSensor(DysonBleVacuumEntity, SensorEntity):
    """Battery temperature category with alert styling."""

    _state_key = "battery_temperature"
    _attr_translation_key = "ble_vacuum_battery_temperature"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_battery_temperature"

    @property
    def native_value(self) -> str | None:
        """Return the battery temperature category."""
        value = self._attr_value(self._state_key)
        return value if isinstance(value, str) else None

    @property
    def icon(self) -> str:
        """Alert icon for out-of-range battery temperatures."""
        state = self.native_value
        return {
            "ok": "mdi:thermometer-check",
            "cold": "mdi:thermometer-chevron-down",
            "hot": "mdi:thermometer-chevron-up",
        }.get(state or "", "mdi:thermometer")
