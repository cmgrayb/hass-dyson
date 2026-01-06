"""Humidifier platform for Dyson integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.components.humidifier.const import MODE_AUTO, MODE_NORMAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity

_LOGGER = logging.getLogger(__name__)

AVAILABLE_MODES = [MODE_NORMAL, MODE_AUTO]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dyson humidifier from a config entry."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    _LOGGER.info(
        "Setting up humidifier entity for %s",
        coordinator.serial_number,
    )
    async_add_entities([DysonHumidifierEntity(coordinator)], True)


class DysonHumidifierEntity(DysonEntity, HumidifierEntity):
    """Dyson humidifier entity."""

    coordinator: DysonDataUpdateCoordinator

    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_available_modes = AVAILABLE_MODES
    _attr_max_humidity = 70
    _attr_min_humidity = 30
    _attr_supported_features = HumidifierEntityFeature.MODES

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the humidifier entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_humidifier"
        self._attr_translation_key = "humidifier"

    @property
    def available(self) -> bool:
        """Return if entity is available - only if device has 'hume' key in MQTT state."""
        if not self.coordinator.device:
            return False

        product_state = self.coordinator.data.get("product-state", {})
        has_humidifier = "hume" in product_state
        return has_humidifier and super().available

    @property
    def is_on(self) -> bool:
        """Return if humidification is on."""
        if not self.coordinator.device:
            return False

        product_state = self.coordinator.data.get("product-state", {})
        hume_data = self.coordinator.device.get_state_value(
            product_state, "hume", "OFF"
        )
        return hume_data == "HUMD"

    @property
    def target_humidity(self) -> int | None:
        """Return the target humidity."""
        if not self.coordinator.device:
            return None

        if self._is_auto_mode:
            return None

        product_state = self.coordinator.data.get("product-state", {})
        humt_data = self.coordinator.device.get_state_value(
            product_state, "humt", "0050"
        )

        try:
            return int(humt_data.lstrip("0") or "50")
        except (ValueError, TypeError):
            return 50

    @property
    def current_humidity(self) -> int | None:
        """Return current humidity."""
        if not self.coordinator.device:
            return None

        env_data = self.coordinator.data.get("environmental-data", {})
        if "hact" in env_data:
            try:
                hact = env_data.get("hact", "0")
                if isinstance(hact, str):
                    value = int(hact.lstrip("0") or "0")
                else:
                    value = int(hact)
                if 0 <= value <= 100:
                    return value
            except (ValueError, TypeError):
                pass

        product_state = self.coordinator.data.get("product-state", {})
        humi_data = self.coordinator.device.get_state_value(
            product_state, "humi", None
        )
        if humi_data:
            try:
                if isinstance(humi_data, str):
                    value = int(humi_data.lstrip("0") or "0")
                else:
                    value = int(humi_data)
                if 0 <= value <= 100:
                    return value
            except (ValueError, TypeError):
                pass

        return None

    @property
    def mode(self) -> str:
        """Return current mode."""
        return MODE_AUTO if self._is_auto_mode else MODE_NORMAL

    @property
    def _is_auto_mode(self) -> bool:
        """Return True if auto humidity mode is enabled."""
        if not self.coordinator.device:
            return False

        product_state = self.coordinator.data.get("product-state", {})
        haut_data = self.coordinator.device.get_state_value(
            product_state, "haut", "OFF"
        )
        return haut_data == "ON"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on humidification."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_humidifier_mode(
                enabled=True, auto_mode=self._is_auto_mode
            )
            _LOGGER.debug(
                "Turned on humidifier for %s",
                self.coordinator.serial_number,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error turning on humidifier for %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error turning on humidifier for %s: %s",
                self.coordinator.serial_number,
                err,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off humidification."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_humidifier_mode(enabled=False)
            _LOGGER.debug(
                "Turned off humidifier for %s",
                self.coordinator.serial_number,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error turning off humidifier for %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error turning off humidifier for %s: %s",
                self.coordinator.serial_number,
                err,
            )

    async def async_set_humidity(self, humidity: int) -> None:
        """Set target humidity."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_target_humidity(humidity)
            await self.async_set_mode(MODE_NORMAL)
            _LOGGER.debug(
                "Set target humidity to %s%% for %s",
                humidity,
                self.coordinator.serial_number,
            )
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid humidity value %s for %s: %s",
                humidity,
                self.coordinator.serial_number,
                err,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting humidity to %s%% for %s: %s",
                humidity,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting humidity to %s%% for %s: %s",
                humidity,
                self.coordinator.serial_number,
                err,
            )

    async def async_set_mode(self, mode: str) -> None:
        """Set humidification mode."""
        if not self.coordinator.device:
            return

        try:
            if mode == MODE_AUTO:
                await self.coordinator.device.set_humidifier_mode(
                    enabled=True, auto_mode=True
                )
                _LOGGER.debug(
                    "Set humidifier to auto mode for %s",
                    self.coordinator.serial_number,
                )
            elif mode == MODE_NORMAL:
                await self.coordinator.device.set_humidifier_mode(
                    enabled=True, auto_mode=False
                )
                _LOGGER.debug(
                    "Set humidifier to normal mode for %s",
                    self.coordinator.serial_number,
                )
            else:
                raise ValueError(f"Invalid mode: {mode}")
        except ValueError as err:
            _LOGGER.warning(
                "Invalid humidifier mode %s for %s: %s",
                mode,
                self.coordinator.serial_number,
                err,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting humidifier mode to %s for %s: %s",
                mode,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting humidifier mode to %s for %s: %s",
                mode,
                self.coordinator.serial_number,
                err,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.device:
            return None

        attributes: dict[str, Any] = {}
        product_state = self.coordinator.data.get("product-state", {})

        wath = self.coordinator.device.get_state_value(product_state, "wath", None)
        if wath:
            attributes["water_hardness"] = wath

        cltr = self.coordinator.device.get_state_value(product_state, "cltr", None)
        if cltr:
            try:
                attributes["clean_time_remaining_hours"] = int(cltr)
            except (ValueError, TypeError):
                pass

        cdrr = self.coordinator.device.get_state_value(product_state, "cdrr", None)
        if cdrr:
            try:
                attributes["cleaning_cycle_remaining_minutes"] = int(cdrr)
            except (ValueError, TypeError):
                pass

        return attributes if attributes else None
