"""Binary sensor entities for Dyson BLE floor-cleaning vacuums (e.g. V16).

States arrive over the BLE attribute protocol (see :mod:`.ble_vacuum`).
Fault-style sensors use :attr:`BinarySensorDeviceClass.PROBLEM`.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DysonBLEVacuumDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: Any,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up BLE vacuum binary sensors for a config entry."""
    coordinator: DysonBLEVacuumDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["ble_vacuum_coordinator"]

    entities: list[BinarySensorEntity] = [
        DysonBleVacuumActivelyChargingSensor(coordinator),
        DysonBleVacuumChargerPresentSensor(coordinator),
        DysonBleVacuumBlockageSensor(coordinator),
        DysonBleVacuumFilterPresentSensor(coordinator),
        DysonBleVacuumFilterWashSensor(coordinator),
        DysonBleVacuumSystemErrorSensor(coordinator),
        DysonBleVacuumChargeRequiredSensor(coordinator),
        DysonBleVacuumSessionActiveSensor(coordinator),
        DysonBleVacuumBatteryAuthenticitySensor(coordinator),
        # Battery care *current* (0x0841) is the machine's live state and is
        # read-only.  The user setting (0x1340) and task detection (0x0741)
        # are writable and live on the switch platform instead.
        DysonBleVacuumBatteryCareCurrentSensor(coordinator),
        DysonBleVacuumDustIlluminationAutoSensor(coordinator),
    ]
    async_add_entities(entities)
    return True


class DysonBleVacuumBinarySensorBase(CoordinatorEntity, BinarySensorEntity):
    """Base entity for Dyson BLE vacuum binary sensors."""

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


class DysonBleVacuumActivelyChargingSensor(DysonBleVacuumBinarySensorBase):
    """Reports whether the vacuum is currently charging the battery."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_translation_key = "ble_vacuum_actively_charging"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_actively_charging"

    @property
    def is_on(self) -> bool | None:
        """Return True while the battery is actively charging."""
        value = self._attr_value("actively_charging")
        return bool(value) if value is not None else None


class DysonBleVacuumChargerPresentSensor(DysonBleVacuumBinarySensorBase):
    """Reports whether the vacuum is on its charger/dock."""

    _attr_device_class = BinarySensorDeviceClass.PLUG
    _attr_translation_key = "ble_vacuum_charger_present"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_charger_present"

    @property
    def is_on(self) -> bool | None:
        """Return True when the charger/dock is present."""
        value = self._attr_value("charger_present")
        return bool(value) if value is not None else None


class _ProblemAttr(DysonBleVacuumBinarySensorBase):
    """Base for problem-style binary sensors driven by a string/bool attr."""

    _state_key: str = ""
    _bad_values: frozenset[Any] = frozenset()

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool | None:
        """Return True when the attribute is in a problem state."""
        value = self._attr_value(self._state_key)
        if value is None:
            return None
        return value in self._bad_values

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the raw attribute value for user-readable context."""
        value = self._attr_value(self._state_key)
        return {"state": value}


class DysonBleVacuumBlockageSensor(_ProblemAttr):
    """Airway/duct blockage present."""

    _state_key = "blockage"
    _bad_values = frozenset(
        {
            "inlet_blocked",
            "inlet_blocked_and_error",
            "outlet_blocked_and_error",
        }
    )
    _attr_translation_key = "ble_vacuum_blockage"
    _attr_icon = "mdi:pipe-wrench"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_blockage"


class DysonBleVacuumFilterPresentSensor(_ProblemAttr):
    """Filter missing / not seated."""

    _state_key = "filter_present"
    _bad_values = frozenset({"filter_not_present"})
    _attr_translation_key = "ble_vacuum_filter_present"
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_filter_present"


class DysonBleVacuumFilterWashSensor(_ProblemAttr):
    """Filter needs washing."""

    _state_key = "filter_wash"
    _bad_values = frozenset({"filter_needs_cleaning"})
    _attr_translation_key = "ble_vacuum_filter_wash"
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_filter_wash"


class DysonBleVacuumSystemErrorSensor(_ProblemAttr):
    """System error present on the machine."""

    _state_key = "system_error"
    _attr_translation_key = "ble_vacuum_system_error"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_system_error"

    @property
    def is_on(self) -> bool | None:
        """Return True when a system error is present."""
        value = self._attr_value("system_error")
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        return bool(value)


class DysonBleVacuumChargeRequiredSensor(_ProblemAttr):
    """Battery empty — machine asks to be placed on charge."""

    _state_key = "charge_required"
    _bad_values = frozenset({"place_on_charge"})
    _attr_translation_key = "ble_vacuum_charge_required"
    _attr_icon = "mdi:battery-charging-outline"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_charge_required"


class DysonBleVacuumSessionActiveSensor(DysonBleVacuumBinarySensorBase):
    """Cleaning session in progress."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "ble_vacuum_session_active"
    _attr_icon = "mdi:vacuum-outline"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_session_active"

    @property
    def is_on(self) -> bool | None:
        """Return True while a cleaning session is active."""
        data = self.coordinator.data
        if not isinstance(data, dict):
            return None
        return bool(data.get("session_active"))

    @property
    def icon(self) -> str:
        """Icon shows activity."""
        return "mdi:vacuum-outline" if not self.is_on else "mdi:vacuum"


class DysonBleVacuumBatteryAuthenticitySensor(DysonBleVacuumBinarySensorBase):
    """Battery pack is not a genuine Dyson part."""

    _attr_translation_key = "ble_vacuum_battery_authenticity"
    _attr_icon = "mdi:battery-check-outline"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_battery_authenticity"

    @property
    def is_on(self) -> bool | None:
        """Return True when a non-genuine battery is fitted."""
        value = self._attr_value("battery_authenticity")
        if value is None:
            return None
        return value == "non_dyson"

    @property
    def device_class(self):
        """Report as a battery/device problem."""
        return BinarySensorDeviceClass.PROBLEM

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose genuineness as a readable attribute."""
        return {"battery_authenticity": self._attr_value("battery_authenticity")}


class DysonBleVacuumBatteryCareCurrentSensor(DysonBleVacuumBinarySensorBase):
    """Battery-care mode active right now."""

    _attr_translation_key = "ble_vacuum_battery_care_current"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_battery_care_current"

    @property
    def is_on(self) -> bool | None:
        """Return True while a battery-care cycle is active."""
        value = self._attr_value("battery_care_current")
        return bool(value) if value is not None else None

    @property
    def icon(self) -> str:
        """Battery-heart icon reflecting state."""
        return "mdi:battery-heart" if self.is_on else "mdi:battery-heart-outline"


class DysonBleVacuumDustIlluminationAutoSensor(DysonBleVacuumBinarySensorBase):
    """Whether AUTO dust illumination is available (attribute 0x0243).

    0x0243 is a capability bitmask, not a scalar.  The MyDyson app reduces it
    to this single boolean (``dustIlluminationAutoState``) by mask-testing
    against 0b111; observed as set with a laser head fitted and clear with no
    head attached.
    """

    _attr_translation_key = "ble_vacuum_dust_illumination_auto"
    _attr_icon = "mdi:laser-pointer"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_dust_illumination_auto"

    @property
    def is_on(self) -> bool | None:
        """Return True when the AUTO option is available."""
        value = self._attr_value("dust_illumination_auto")
        return bool(value) if value is not None else None
