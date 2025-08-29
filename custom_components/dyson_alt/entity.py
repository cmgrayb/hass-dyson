"""Base entity class for Dyson Alternative integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import DysonDataUpdateCoordinator


class DysonEntity(CoordinatorEntity):
    """Base class for all Dyson entities."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the Dyson entity."""
        super().__init__(coordinator)

    @property
    def device_info(self):
        """Return device information to link this entity with the device."""
        if self.coordinator.device:
            return self.coordinator.device.device_info
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and (
            self.coordinator.device is not None and self.coordinator.device.is_connected
        )
