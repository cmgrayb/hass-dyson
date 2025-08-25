"""Binary sensor platform for Dyson Alternative integration."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DysonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dyson binary sensor platform."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Basic binary sensors for all devices
    entities.extend(
        [
            DysonConnectivitySensor(coordinator),
            DysonFilterReplacementSensor(coordinator),
        ]
    )

    async_add_entities(entities, True)


class DysonConnectivitySensor(CoordinatorEntity, BinarySensorEntity):  # type: ignore[misc]
    """Representation of device connectivity status."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the connectivity sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_connectivity"
        self._attr_name = f"{coordinator.config_entry.title} Connectivity"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_icon = "mdi:wifi"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            self._attr_is_on = self.coordinator.device.is_connected
        else:
            self._attr_is_on = False
        super()._handle_coordinator_update()


class DysonFilterReplacementSensor(CoordinatorEntity, BinarySensorEntity):  # type: ignore[misc]
    """Representation of filter replacement needed status."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the filter replacement sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_filter_replacement"
        self._attr_name = f"{coordinator.config_entry.title} Filter Replacement"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            # Filter needs replacement if either HEPA or carbon life is very low
            hepa_life = self.coordinator.device.hepa_filter_life
            carbon_life = self.coordinator.device.carbon_filter_life

            # Check if either filter is below 10%
            self._attr_is_on = (hepa_life <= 10 and hepa_life > 0) or (carbon_life <= 10 and carbon_life > 0)
        else:
            self._attr_is_on = False
        super()._handle_coordinator_update()
