"""Shared identity and validated state access for optional BLE lamp settings."""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityDescription

from .ble_light_attributes import BLELightAttributes
from .coordinator import DysonBLEDataUpdateCoordinator
from .entity import DysonBLEEntity


class DysonBLELightSettingEntity(DysonBLEEntity):
    """Share the original BLE light's coordinator, device and registry identity."""

    _attr_should_poll = False

    def __init__(
        self, coordinator: DysonBLEDataUpdateCoordinator, key: str, name: str | None
    ) -> None:
        """Use stable feature IDs and the existing translation conventions."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_lightcycle_{key}"
        self._attr_translation_key = f"lightcycle_{key}"
        self.entity_description = EntityDescription(key=key, name=name)

    @property
    def lighting(self) -> BLELightAttributes:
        """Return the optional settings interface for an initialized device."""
        device = self.coordinator.ble_device
        if device is None:
            raise HomeAssistantError("Lamp is not initialized")
        return device.lighting

    def attribute_bytes(self, attribute: int, size: int) -> bytes | None:
        """Reject absent and malformed optional attributes independently."""
        device = self.coordinator.ble_device
        if device is None or not device.lighting.available:
            return None
        value = device.lighting.attributes.get(attribute)
        return value if isinstance(value, bytes) and len(value) == size else None

    def attribute_bool(self, attribute: int) -> bool | None:
        """Accept only the native Boolean representation."""
        value = self.attribute_bytes(attribute, 1)
        return value == b"\1" if value in (b"\0", b"\1") else None

    def attribute_uint16(self, attribute: int) -> int | None:
        """Read an optional two-byte little-endian setting."""
        value = self.attribute_bytes(attribute, 2)
        return int.from_bytes(value, "little") if value is not None else None
