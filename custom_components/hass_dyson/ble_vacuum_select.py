"""Select entities for Dyson BLE floor-cleaning vacuums (e.g. V16).

These mirror the multi-valued BLE writers exposed by the MyDyson app's
connected-floorcare module: brush-bar speed (0x0B40), dust-illumination
mode (0x0A40) and the machine's UI language (0x0241).  Writes travel as
0x93 WRITE_ATTRIBUTE requests; state is applied only after the machine
confirms via a 0x97 push — never assumed optimistically.

The writable set is defined by the ``k50.i`` (WriteAttributeRequest)
subclasses in the app's floorcare module: ``mq/a`` BrushBarSpeed,
``mq/b`` illuminationMode, ``lq/b`` ProductUILanguage$Ble (here), plus
``mq/c`` taskDetectMode and ``lq/a`` batteryCareMode (switches).
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BLE_VACUUM_ATTR_BRUSH_BAR_SPEED,
    BLE_VACUUM_ATTR_DUST_ILLUMINATION,
    BLE_VACUUM_ATTR_UI_LANGUAGE,
    BLE_VACUUM_BRUSH_BAR_SPEEDS,
    BLE_VACUUM_DUST_ILLUMINATION_MODES,
    BLE_VACUUM_LANGUAGES,
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
    """Set up BLE vacuum selects for a config entry."""
    coordinator: DysonBLEVacuumDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["ble_vacuum_coordinator"]

    async_add_entities(
        [
            DysonBleVacuumBrushBarSpeedSelect(coordinator),
            DysonBleVacuumDustIlluminationSelect(coordinator),
            DysonBleVacuumUiLanguageSelect(coordinator),
        ]
    )
    return True


class _BleVacuumSelectBase(CoordinatorEntity, SelectEntity):
    """Base for BLE vacuum attribute selects (0x93 writes)."""

    coordinator: DysonBLEVacuumDataUpdateCoordinator
    _attr_has_entity_name = True

    _attr_id: bytes = b""
    _state_key: str = ""
    _options_map: dict[int, str] = {}

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
    def options(self) -> list[str]:
        """Return the possible enum labels."""
        return [label for _v, label in sorted(self._options_map.items())]

    def _attr_value(self, key: str) -> Any:
        """Read one attribute from coordinator data."""
        data = self.coordinator.data
        if not isinstance(data, dict):
            return None
        return data.get("attributes", {}).get(key)

    @property
    def current_option(self) -> str | None:
        """Return the current option label."""
        value = self._attr_value(self._state_key)
        if value is None:
            return None
        if isinstance(value, str):
            return value
        try:
            return self._options_map.get(int(value))
        except (TypeError, ValueError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Write the selected option to the machine."""
        if self.coordinator.ble_device is None:
            return
        # Home Assistant validates the option against `options` in the @final
        # async_handle_select_option() wrapper before reaching us, raising
        # ServiceValidationError.  This check only catches a direct/internal
        # call with a label that is not in the map at all — a programming
        # error, hence ValueError.
        value_map = {label: value for value, label in self._options_map.items()}
        if option not in value_map:
            raise ValueError(f"Unknown option for {self._state_key}: {option!r}")
        ok = await self.coordinator.ble_device.write_attribute(
            self._attr_id, bytes((value_map[option],))
        )
        if not ok:
            _LOGGER.warning(
                "%s: machine did not confirm %s=%s (write may have been rejected)",
                mask_serial(self.coordinator.serial_number),
                self._state_key,
                option,
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Push updates to the frontend."""
        self.async_write_ha_state()


class DysonBleVacuumBrushBarSpeedSelect(_BleVacuumSelectBase):
    """Brush bar speed select (attribute 0x0B40) — low / high / auto."""

    _attr_id = BLE_VACUUM_ATTR_BRUSH_BAR_SPEED
    _state_key = "brush_bar_speed"
    _options_map = BLE_VACUUM_BRUSH_BAR_SPEEDS
    _attr_translation_key = "ble_vacuum_brush_bar_speed_select"
    _attr_icon = "mdi:rotate-right"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_brush_bar_speed_select"


class DysonBleVacuumDustIlluminationSelect(_BleVacuumSelectBase):
    """Dust illumination mode select (attribute 0x0A40) — off / on / auto."""

    _attr_id = BLE_VACUUM_ATTR_DUST_ILLUMINATION
    _state_key = "dust_illumination"
    _options_map = BLE_VACUUM_DUST_ILLUMINATION_MODES
    _attr_translation_key = "ble_vacuum_dust_illumination_select"
    _attr_icon = "mdi:laser-pointer"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the select."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.serial_number}_ble_dust_illumination_select"
        )

    @property
    def options(self) -> list[str]:
        """Hide "auto" when the attached head cannot do it.

        The 0x0243 capability bitmask says whether AUTO is available (the app
        gates its own option list the same way).  "auto" is kept in the list
        whenever it is the *current* value regardless: Home Assistant's
        ``SelectEntity.state`` reports ``None`` for a ``current_option`` outside
        ``options``, so hiding it would make the entity read *unknown* while the
        machine legitimately sits in auto with a non-laser head fitted.
        """
        options = super().options
        if self._attr_value("dust_illumination_auto"):
            return options
        return [
            option
            for option in options
            if option != "auto" or option == self.current_option
        ]


class DysonBleVacuumUiLanguageSelect(_BleVacuumSelectBase):
    """Machine UI language select (attribute 0x0241).

    Writable over BLE via the app's ``lq/b`` ProductUILanguage$Ble write
    request.  Marked as a config entity: it changes what the machine itself
    displays, so it does not belong on the main device card.
    """

    _attr_id = BLE_VACUUM_ATTR_UI_LANGUAGE
    _state_key = "ui_language"
    _options_map = BLE_VACUUM_LANGUAGES
    _attr_translation_key = "ble_vacuum_ui_language_select"
    _attr_icon = "mdi:translate"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_ui_language_select"

    @property
    def options(self) -> list[str]:
        """Return the languages sorted by name.

        The base class orders by wire value, which is the right thing for the
        small ordinal selects (off/on/auto).  Dyson's language enum order is
        arbitrary, so a 30-item dropdown is far easier to use alphabetically.
        Ordering is display-only — writes still map label to wire value.
        """
        return sorted(self._options_map.values())
