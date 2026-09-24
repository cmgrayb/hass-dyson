"""Switch entities for Dyson BLE floor-cleaning vacuums (e.g. V16).

The two boolean settings the MyDyson app writes over BLE for this device
family — task detection (0x0741, app ``mq/c``) and battery care mode
(0x0841, app ``lq/a``).  Both are ``k50.i`` WriteAttributeRequest subclasses
in the app's floorcare module, so reads AND writes are supported via 0x93.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BLE_VACUUM_ATTR_BATTERY_CARE_SETTING,
    BLE_VACUUM_ATTR_TASK_DETECTION,
    DOMAIN,
)
from .coordinator import DysonBLEVacuumDataUpdateCoordinator
from .device_utils import mask_serial

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: Any,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up BLE vacuum switches for a config entry."""
    coordinator: DysonBLEVacuumDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["ble_vacuum_coordinator"]

    async_add_entities(
        [
            DysonBleVacuumTaskDetectionSwitch(coordinator),
            DysonBleVacuumBatteryCareSwitch(coordinator),
        ]
    )
    return True


class _BleVacuumSwitchBase(CoordinatorEntity, SwitchEntity):
    """Base for BLE vacuum boolean attribute switches (0x93 writes)."""

    coordinator: DysonBLEVacuumDataUpdateCoordinator
    _attr_has_entity_name = True

    _attr_id: bytes = b""
    _state_key: str = ""

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

    @property
    def is_on(self) -> bool | None:
        """Return the current boolean state of the attribute."""
        data = self.coordinator.data
        if not isinstance(data, dict):
            return None
        value = data.get("attributes", {}).get(self._state_key)
        return bool(value) if value is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the setting on the machine."""
        await self._write(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the setting on the machine."""
        await self._write(False)

    async def _write(self, enabled: bool) -> None:
        """Write the toggle via the 0x93 attribute writer."""
        if self.coordinator.ble_device is None:
            return
        ok = await self.coordinator.ble_device.write_attribute(
            self._attr_id, bytes((0x01 if enabled else 0x00,))
        )
        if not ok:
            _LOGGER.warning(
                "%s: machine did not confirm %s=%s",
                mask_serial(self.coordinator.serial_number),
                self._state_key,
                enabled,
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Push updates to the frontend."""
        self.async_write_ha_state()


class DysonBleVacuumTaskDetectionSwitch(_BleVacuumSwitchBase):
    """Task detection switch (BLE attribute 0x0741)."""

    _attr_id = BLE_VACUUM_ATTR_TASK_DETECTION
    _state_key = "task_detection"
    _attr_translation_key = "ble_vacuum_task_detection_switch"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_task_detection_switch"

    @property
    def icon(self) -> str:
        """Icon follows the switch state."""
        return "mdi:motion-sensor" if self.is_on else "mdi:motion-sensor-off"


class DysonBleVacuumBatteryCareSwitch(_BleVacuumSwitchBase):
    """Battery care mode switch (BLE attribute 0x0841)."""

    _attr_id = BLE_VACUUM_ATTR_BATTERY_CARE_SETTING
    _state_key = "battery_care_setting"
    _attr_translation_key = "ble_vacuum_battery_care_switch"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_battery_care_switch"

    @property
    def icon(self) -> str:
        """Shield icon reflecting the setting."""
        return "mdi:shield-check" if self.is_on else "mdi:shield-check-outline"
