"""Switch platform for Dyson integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CAPABILITY_ENVIRONMENTAL_DATA, DOMAIN
from .coordinator import DysonDataUpdateCoordinator
from .device_utils import mask_serial
from .entity import DysonEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Dyson switch platform."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[SwitchEntity] = []

    # Basic switches for all devices
    entities.append(DysonNightModeSwitch(coordinator))

    # Auto mode switch removed - now handled by fan platform preset modes

    # Add firmware auto-update switch for cloud-discovered devices only
    from .const import CONF_DISCOVERY_METHOD, DISCOVERY_CLOUD

    if config_entry.data.get(CONF_DISCOVERY_METHOD) == DISCOVERY_CLOUD:
        entities.append(DysonFirmwareAutoUpdateSwitch(coordinator))
        _LOGGER.debug(
            "Adding firmware auto-update switch for cloud device %s",
            coordinator.serial_number,
        )

    # Add additional switches based on capabilities
    device_capabilities = coordinator.device_capabilities

    # Note: Oscillation is now handled natively by the fan platform via FanEntityFeature.OSCILLATE
    # Advanced oscillation modes are available through the oscillation mode select entity

    # Note: Heating functionality is now integrated into the fan entity's HVAC modes
    # No separate heating switch needed

    if CAPABILITY_ENVIRONMENTAL_DATA in device_capabilities:
        entities.append(DysonContinuousMonitoringSwitch(coordinator))

    # Add Find+Follow switch for devices that report the 'soon' state key.
    # No dedicated capability flag exists; presence of 'soon' in product-state is
    # the sole gating criterion (same pattern as 'oton' for tilt oscillation).
    ff_product_state: dict = {}
    if coordinator.data:
        raw_ps = coordinator.data.get("product-state", {})
        if isinstance(raw_ps, dict):
            ff_product_state = raw_ps
    if "soon" in ff_product_state:
        entities.append(DysonFindFollowSwitch(coordinator))

    async_add_entities(entities, True)
    return True


class DysonAutoModeSwitch(DysonEntity, SwitchEntity):
    """Switch for auto mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the auto mode switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_auto_mode"
        self._attr_translation_key = "auto_mode"
        self._attr_icon = "mdi:auto-mode"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get auto mode from device state (auto)
            product_state = self.coordinator.data.get("product-state", {})
            auto_mode = self.coordinator.device.get_state_value(
                product_state, "auto", "OFF"
            )
            self._attr_is_on = auto_mode == "ON"
        else:
            self._attr_is_on = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on auto mode."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_auto_mode(True)
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug(
                "Turned on auto mode for %s",
                mask_serial(self.coordinator.serial_number),
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error enabling auto mode for %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except AttributeError as err:
            _LOGGER.error(
                "Device method not available for auto mode on %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error enabling auto mode for %s: %s",
                self.coordinator.serial_number,
                err,
            )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off auto mode."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_auto_mode(False)
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug(
                "Turned off auto mode for %s",
                mask_serial(self.coordinator.serial_number),
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error disabling auto mode for %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except AttributeError as err:
            _LOGGER.error(
                "Device method not available for auto mode on %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error disabling auto mode for %s: %s",
                self.coordinator.serial_number,
                err,
            )


class DysonNightModeSwitch(DysonEntity, SwitchEntity):
    """Switch for night mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the night mode switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_night_mode"
        self._attr_translation_key = "night_mode"
        self._attr_icon = "mdi:weather-night"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get night mode from device state (nmod)
            product_state = self.coordinator.data.get("product-state", {})
            night_mode = self.coordinator.device.get_state_value(
                product_state, "nmod", "OFF"
            )
            self._attr_is_on = night_mode == "ON"
        else:
            self._attr_is_on = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on night mode."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_night_mode(True)
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug(
                "Turned on night mode for %s",
                mask_serial(self.coordinator.serial_number),
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error enabling night mode for %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except AttributeError as err:
            _LOGGER.error(
                "Device method not available for night mode on %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error enabling night mode for %s: %s",
                self.coordinator.serial_number,
                err,
            )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off night mode."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_night_mode(False)
            # No need to refresh - MQTT provides real-time updates
            _LOGGER.debug(
                "Turned off night mode for %s", self.coordinator.serial_number
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error disabling night mode for %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except AttributeError as err:
            _LOGGER.error(
                "Device method not available for night mode on %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error disabling night mode for %s: %s",
                self.coordinator.serial_number,
                err,
            )


# DysonOscillationSwitch class removed - oscillation is now handled natively by the fan platform
# via FanEntityFeature.OSCILLATE and the fan.oscillate service


class DysonHeatingSwitch(DysonEntity, SwitchEntity):
    """Switch for heating mode."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the heating switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_heating"
        self._attr_translation_key = "heating"
        self._attr_icon = "mdi:radiator"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get heating from device state (hmod)
            product_state = self.coordinator.data.get("product-state", {})
            hmod = self.coordinator.device.get_state_value(product_state, "hmod", "OFF")
            self._attr_is_on = hmod != "OFF"
        else:
            self._attr_is_on = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on heating."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_heating_mode("HEAT")
            _LOGGER.debug(
                "Turned on heating for %s", mask_serial(self.coordinator.serial_number)
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error enabling heating for %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except AttributeError as err:
            _LOGGER.error(
                "Device method not available for heating on %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error enabling heating for %s: %s",
                self.coordinator.serial_number,
                err,
            )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off heating."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_heating_mode("OFF")
            _LOGGER.debug(
                "Turned off heating for %s", mask_serial(self.coordinator.serial_number)
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error disabling heating for %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except AttributeError as err:
            _LOGGER.error(
                "Device method not available for heating on %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error disabling heating for %s: %s",
                self.coordinator.serial_number,
                err,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return heating-specific state attributes for scene support."""
        if not self.coordinator.device:
            return None

        attributes: dict[str, Any] = {}
        product_state = self.coordinator.data.get("product-state", {})

        # Heating mode state for scene support
        hmod = self.coordinator.device.get_state_value(product_state, "hmod", "OFF")
        attributes["heating_mode"] = hmod
        heating_enabled: bool = hmod != "OFF"
        attributes["heating_enabled"] = heating_enabled  # type: ignore[assignment]

        # Include related heating properties if available
        try:
            # Target temperature in Kelvin
            hmax = self.coordinator.device.get_state_value(
                product_state, "hmax", "2980"
            )
            temp_kelvin: float = int(hmax) / 10  # Device reports in 0.1K increments
            target_celsius: float = temp_kelvin - 273.15
            attributes["target_temperature"] = round(target_celsius, 1)  # type: ignore[assignment]
            attributes["target_temperature_kelvin"] = hmax
        except (ValueError, TypeError):
            pass

        return attributes


class DysonContinuousMonitoringSwitch(DysonEntity, SwitchEntity):
    """Switch for continuous monitoring."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the continuous monitoring switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_continuous_monitoring"
        self._attr_translation_key = "continuous_monitoring"
        self._attr_icon = "mdi:monitor-eye"
        from homeassistant.const import EntityCategory

        self._attr_entity_category = EntityCategory.CONFIG

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Get monitoring from device state (rhtm)
            product_state = self.coordinator.data.get("product-state", {})
            rhtm = self.coordinator.device.get_state_value(product_state, "rhtm", "OFF")
            self._attr_is_on = rhtm == "ON"
        else:
            self._attr_is_on = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on continuous monitoring."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_continuous_monitoring(True)
            _LOGGER.debug(
                "Turned on continuous monitoring for %s", self.coordinator.serial_number
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error enabling continuous monitoring for %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except AttributeError as err:
            _LOGGER.error(
                "Device method not available for continuous monitoring on %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error enabling continuous monitoring for %s: %s",
                self.coordinator.serial_number,
                err,
            )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off continuous monitoring."""
        if not self.coordinator.device:
            return

        try:
            await self.coordinator.device.set_continuous_monitoring(False)
            _LOGGER.debug(
                "Turned off continuous monitoring for %s",
                self.coordinator.serial_number,
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error disabling continuous monitoring for %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except AttributeError as err:
            _LOGGER.error(
                "Device method not available for continuous monitoring on %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error disabling continuous monitoring for %s: %s",
                self.coordinator.serial_number,
                err,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:  # type: ignore[return]
        """Return continuous monitoring state attributes for scene support."""
        if not self.coordinator.device:
            return None

        attributes: dict[str, Any] = {}
        product_state = self.coordinator.data.get("product-state", {})

        # Continuous monitoring state for scene support
        rhtm = self.coordinator.device.get_state_value(product_state, "rhtm", "OFF")
        continuous_monitoring: bool = rhtm == "ON"
        attributes["continuous_monitoring"] = continuous_monitoring  # type: ignore[assignment]
        attributes["monitoring_mode"] = rhtm

        return attributes


class DysonFirmwareAutoUpdateSwitch(DysonEntity, SwitchEntity):
    """Switch to control firmware auto-update setting."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the firmware auto-update switch."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_firmware_auto_update"
        self._attr_translation_key = "firmware_auto_update"
        self._attr_icon = "mdi:cloud-sync"
        from homeassistant.const import EntityCategory

        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool | None:
        """Return True if firmware auto-update is enabled."""
        return self.coordinator.firmware_auto_update_enabled

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        attrs = dict(super().extra_state_attributes or {})
        attrs.update(
            {
                "current_firmware_version": self.coordinator.firmware_version,
            }
        )
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on firmware auto-update."""
        success = await self.coordinator.async_set_firmware_auto_update(True)
        if success:
            _LOGGER.info(
                "Enabled firmware auto-update for %s", self.coordinator.serial_number
            )
        else:
            _LOGGER.error(
                "Failed to enable firmware auto-update for %s",
                self.coordinator.serial_number,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off firmware auto-update."""
        success = await self.coordinator.async_set_firmware_auto_update(False)
        if success:
            _LOGGER.info(
                "Disabled firmware auto-update for %s", self.coordinator.serial_number
            )
        else:
            _LOGGER.error(
                "Failed to disable firmware auto-update for %s",
                self.coordinator.serial_number,
            )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "Firmware auto-update switch updated for %s: enabled=%s, version=%s",
            self.coordinator.serial_number,
            self.coordinator.firmware_auto_update_enabled,
            self.coordinator.firmware_version,
        )
        super()._handle_coordinator_update()


class DysonFindFollowSwitch(DysonEntity, SwitchEntity):
    """Switch for Find+Follow mode.

    Find+Follow uses the device camera to identify and track people in the
    room, directing airflow toward them.  The switch is detected at runtime
    by the presence of the ``soon`` state key in the device's product-state.
    """

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the Find+Follow switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_find_follow"
        self._attr_translation_key = "find_follow"
        self._attr_icon = "mdi:account-eye"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            product_state = self.coordinator.data.get("product-state", {})
            soon = self.coordinator.device.get_state_value(product_state, "soon", "OFF")
            # ON when actively tracking (ON) or scanning (SCAN);
            # scanning always transitions to ON after the scan completes.
            self._attr_is_on = soon in ("ON", "SCAN")
        else:
            self._attr_is_on = None
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return Find+Follow state attributes for diagnostics and automations."""
        if not self.coordinator.device:
            return None

        product_state = self.coordinator.data.get("product-state", {})
        soon = self.coordinator.device.get_state_value(product_state, "soon", "OFF")
        sost = self.coordinator.device.get_state_value(product_state, "sost", "OFF")

        return {
            "find_follow_active": soon in ("ON", "SCAN"),
            "find_follow_command": soon,
            "find_follow_engine_status": sost,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable Find+Follow mode."""
        if not self.coordinator.device:
            return
        try:
            await self.coordinator.device.set_find_follow("ON")
            _LOGGER.debug(
                "Enabled Find+Follow for %s",
                mask_serial(self.coordinator.serial_number),
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error enabling Find+Follow for %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error enabling Find+Follow for %s: %s",
                self.coordinator.serial_number,
                err,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable Find+Follow mode."""
        if not self.coordinator.device:
            return
        try:
            await self.coordinator.device.set_find_follow("OFF")
            _LOGGER.debug(
                "Disabled Find+Follow for %s",
                mask_serial(self.coordinator.serial_number),
            )
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error(
                "Communication error disabling Find+Follow for %s: %s",
                self.coordinator.serial_number,
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error disabling Find+Follow for %s: %s",
                self.coordinator.serial_number,
                err,
            )
