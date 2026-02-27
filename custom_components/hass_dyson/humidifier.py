"""Humidifier platform for Dyson integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity

_LOGGER = logging.getLogger(__name__)

# Humidifier modes based on Dyson device capabilities
MODE_OFF = "off"
MODE_NORMAL = "normal"  # hume=HUMD
MODE_AUTO = "auto"  # haut=ON

AVAILABLE_MODES = [MODE_NORMAL, MODE_AUTO]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dyson humidifier platform."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Add humidifier entity for devices with Humidifier capability
    device_capabilities = coordinator.device_capabilities
    if "Humidifier" in device_capabilities:
        entities.append(DysonHumidifierEntity(coordinator))

    async_add_entities(entities, True)


class DysonHumidifierEntity(DysonEntity, HumidifierEntity):  # type: ignore[misc]
    """Humidifier entity for Dyson humidifier devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the humidifier entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_humidifier"
        self._attr_name = None  # Use device name from device_info
        self._attr_icon = "mdi:air-humidifier"
        self._attr_translation_key = "dyson_humidifier"

        # Humidifier features
        self._attr_supported_features = HumidifierEntityFeature.MODES
        self._attr_device_class = HumidifierDeviceClass.HUMIDIFIER

        # Humidity settings - matches Dyson app (30-70% in 10% steps)
        self._attr_min_humidity = 30
        self._attr_max_humidity = 70
        # Note: Home Assistant doesn't have a native step attribute for humidifier,
        # but the frontend will respect the 10% increments when using the slider
        # based on the range 30-70 which divides evenly by 10

        # Available modes
        self._attr_available_modes = AVAILABLE_MODES

        # Initialize state (will be updated in _handle_coordinator_update)
        self._attr_is_on = False
        self._attr_mode = None
        self._attr_current_humidity = None
        self._attr_target_humidity = 40  # Default to 40%

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            return

        device_data = self.coordinator.data.get("product-state", {})

        self._update_state(device_data)
        self._update_humidity(device_data)

        super()._handle_coordinator_update()

    def _update_state(self, device_data: dict[str, Any]) -> None:
        """Update humidifier state and mode from device data."""
        if not self.coordinator.device:
            return

        # Check humidity enabled state (hume)
        humidity_enabled = self.coordinator.device.get_state_value(
            device_data, "hume", "OFF"
        )
        # Check auto mode state (haut)
        humidity_auto = self.coordinator.device.get_state_value(
            device_data, "haut", "OFF"
        )

        # Determine if humidifier is on (either manual or auto mode)
        self._attr_is_on = humidity_enabled == "HUMD" or humidity_auto == "ON"

        # Determine current mode
        if humidity_auto == "ON":
            self._attr_mode = MODE_AUTO
        elif humidity_enabled == "HUMD":
            self._attr_mode = MODE_NORMAL
        else:
            self._attr_mode = None  # Off has no mode

    def _update_humidity(self, device_data: dict[str, Any]) -> None:
        """Update current and target humidity from device data."""
        if not self.coordinator.device:
            return

        # Current humidity (if available)
        current_humidity = self.coordinator.device.get_state_value(
            device_data, "humi", "0000"
        )
        try:
            humidity_percent = int(current_humidity)
            # Only set humidity if we have a valid reading (not default 0000)
            if current_humidity != "0000" and humidity_percent > 0:
                self._attr_current_humidity = humidity_percent
            else:
                self._attr_current_humidity = None
        except ValueError, TypeError:
            self._attr_current_humidity = None

        # Target humidity
        target_humidity = self.coordinator.device.get_state_value(
            device_data, "humt", "0040"
        )
        try:
            humidity_percent = int(target_humidity)
            # Only set target humidity if we have a valid reading
            if target_humidity != "0000" and humidity_percent > 0:
                self._attr_target_humidity = humidity_percent
            else:
                self._attr_target_humidity = 40  # Default to 40%
        except ValueError, TypeError:
            self._attr_target_humidity = 40  # Default to 40%

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the humidifier on."""
        if not self.coordinator.device:
            return

        try:
            # Turn on in normal mode by default (can be changed via set_mode)
            await self.coordinator.device.set_humidifier_mode(
                enabled=True, auto_mode=False
            )

            # Update local state immediately for responsive UI
            self._attr_is_on = True
            self._attr_mode = MODE_NORMAL
            self.async_write_ha_state()

            _LOGGER.debug("Turned on humidifier for %s", self.coordinator.serial_number)
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
        """Turn the humidifier off."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_humidifier_mode(
                enabled=False, auto_mode=False
            )

            # Update local state immediately for responsive UI
            self._attr_is_on = False
            self._attr_mode = None
            self.async_write_ha_state()

            _LOGGER.debug(
                "Turned off humidifier for %s", self.coordinator.serial_number
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
        """Set new target humidity (rounded to nearest 10% increment)."""
        if not self.coordinator.device:
            return

        # Round to nearest 10% increment (30, 40, 50, 60, 70) to match Dyson app behavior
        rounded_humidity = round(humidity / 10) * 10
        rounded_humidity = max(30, min(70, rounded_humidity))

        if rounded_humidity != humidity:
            _LOGGER.debug(
                "Adjusted humidity from %s%% to %s%% (nearest 10%% increment) for %s",
                humidity,
                rounded_humidity,
                self.coordinator.serial_number,
            )

        try:
            await self.coordinator.device.set_target_humidity(rounded_humidity)

            # Update local state immediately for responsive UI
            self._attr_target_humidity = rounded_humidity
            self.async_write_ha_state()

            _LOGGER.debug(
                "Set target humidity to %s%% for %s",
                rounded_humidity,
                self.coordinator.serial_number,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting humidity to %s%% for %s: %s",
                humidity,
                self.coordinator.serial_number,
                err,
            )
        except ValueError as err:
            _LOGGER.error(
                "Invalid humidity value %s%% for %s: %s",
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
        """Set humidifier mode (normal or auto)."""
        if not self.coordinator.device:
            return

        if mode not in AVAILABLE_MODES:
            _LOGGER.error(
                "Invalid humidifier mode '%s' for %s. Available modes: %s",
                mode,
                self.coordinator.serial_number,
                AVAILABLE_MODES,
            )
            return

        try:
            if mode == MODE_AUTO:
                # Enable auto mode
                await self.coordinator.device.set_humidifier_mode(
                    enabled=True, auto_mode=True
                )
                self._attr_mode = MODE_AUTO
            elif mode == MODE_NORMAL:
                # Enable normal/manual mode
                await self.coordinator.device.set_humidifier_mode(
                    enabled=True, auto_mode=False
                )
                self._attr_mode = MODE_NORMAL

            # Ensure humidifier is marked as on
            self._attr_is_on = True
            self.async_write_ha_state()

            _LOGGER.debug(
                "Set humidifier mode to %s for %s",
                mode,
                self.coordinator.serial_number,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error setting humidifier mode to '%s' for %s: %s",
                mode,
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error setting humidifier mode to '%s' for %s: %s",
                mode,
                self.coordinator.serial_number,
                err,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return humidifier-specific state attributes."""
        if not self.coordinator.device:
            return None

        device_data = self.coordinator.data.get("product-state", {})

        attributes: dict[str, Any] = {}

        # Raw state values for debugging
        humidity_enabled = self.coordinator.device.get_state_value(
            device_data, "hume", "OFF"
        )
        humidity_auto = self.coordinator.device.get_state_value(
            device_data, "haut", "OFF"
        )
        current_humidity_raw = self.coordinator.device.get_state_value(
            device_data, "humi", "0000"
        )
        target_humidity_raw = self.coordinator.device.get_state_value(
            device_data, "humt", "0040"
        )

        attributes["humidity_enabled_raw"] = humidity_enabled
        attributes["humidity_auto_raw"] = humidity_auto
        attributes["current_humidity_raw"] = current_humidity_raw
        attributes["target_humidity_raw"] = target_humidity_raw

        return attributes
