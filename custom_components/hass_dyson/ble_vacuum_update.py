"""Update entity for Dyson BLE floor-cleaning vacuums (e.g. V16).

Reports firmware state only — this integration deliberately does **not**
support installing updates over BLE, so no ``UpdateEntityFeature.INSTALL``
is declared and Home Assistant will not offer an install button.

Both versions come from the machine itself:

- installed version — Product Info (0x0B)
- latest version — the ``pending_fw`` field of Connection Established (0x26)

**"Up to date" is not knowable over BLE.**  A ``lecOnly`` vacuum has no Wi-Fi
and no MQTT, so it cannot ask Dyson whether a newer build exists.  The MyDyson
app downloads firmware from the cloud and transfers it to the machine over BLE
(the app has a ``BleOtaUpdateController``), so ``pending_fw`` means "an image
is staged on the machine", not "this is the newest release".

An all-zero ``pending_fw`` therefore means "nothing staged", which is *not*
the same as "up to date" — the machine simply has no idea.

The Dyson cloud *does* know: ``Firmware.new_version_available`` is populated
even for ``lecOnly`` devices (their ``connected_configuration`` is present with
``mqtt=None``).  The coordinator refreshes that periodically and the entity
prefers it.  Without a configured account the entity reports *unknown* rather
than asserting the firmware is current on no evidence.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.core import HomeAssistant, callback
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
    """Set up the BLE vacuum firmware update entity."""
    coordinator: DysonBLEVacuumDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["ble_vacuum_coordinator"]

    async_add_entities([DysonBleVacuumFirmwareUpdate(coordinator)])
    return True


class DysonBleVacuumFirmwareUpdate(CoordinatorEntity, UpdateEntity):
    """Firmware status for a BLE floor-care vacuum (read-only).

    No ``supported_features`` are declared, so this is informational only:
    Home Assistant shows installed vs latest and never offers to install.
    Firmware updates for these machines go through the MyDyson app.
    """

    coordinator: DysonBLEVacuumDataUpdateCoordinator
    _attr_has_entity_name = True
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_translation_key = "ble_vacuum_firmware"

    def __init__(self, coordinator: DysonBLEVacuumDataUpdateCoordinator) -> None:
        """Initialise the update entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_ble_firmware"

    @property
    def available(self) -> bool:
        """Available whenever a firmware version is known.

        Unlike the live sensors this stays available while the vacuum is out
        of range — the last known firmware is still the truth.
        """
        return self.installed_version is not None

    @property
    def device_info(self):
        """Return device info for the Home Assistant device registry."""
        if self.coordinator.ble_device is not None:
            return self.coordinator.ble_device.device_info
        return None

    def _value(self, key: str) -> Any:
        """Read one top-level field from coordinator data."""
        data = self.coordinator.data
        if not isinstance(data, dict):
            return None
        return data.get(key)

    @property
    def installed_version(self) -> str | None:
        """Return the firmware currently running on the machine.

        Uses Dyson's own version format (``SVC0PS.50.02.013.0002``) when the
        product-info fields allow it to be reconstructed, so it is directly
        comparable with what the cloud reports.  Falls back to the short
        ``2.13.2`` form otherwise.
        """
        for key in ("dyson_firmware_version", "firmware_version"):
            value = self._value(key)
            if isinstance(value, str) and value:
                return value
        return None

    @property
    def latest_version(self) -> str | None:
        """Return the newest firmware available, or None when unknowable.

        Three sources, in order of authority:

        1. The Dyson cloud, which is the only thing that actually knows whether
           a newer build exists — the vacuum has no internet.  When it says
           nothing newer is available, the installed version *is* the latest.
        2. A build the phone app has staged on the machine over BLE
           (``pending_fw`` of 0x26), which implies one exists.
        3. Nothing — report ``None`` so Home Assistant shows *unknown* rather
           than claiming the firmware is current on no evidence.
        """
        if self._value("cloud_firmware_version") is not None:
            if self._value("cloud_new_version_available"):
                pending = self._value("cloud_pending_version")
                if isinstance(pending, str) and pending:
                    return pending
                # Newer build exists but the cloud did not name it; anything
                # unequal to installed makes HA show "update available".
                return "unknown (newer available)"
            return self.installed_version

        staged = self._value("pending_firmware_version")
        if isinstance(staged, str) and staged:
            return staged
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the recovery image and OTA status for diagnostics."""
        return {
            "recovery_firmware_version": self._value("recovery_firmware_version"),
            "ota_status": self._value("ota_status"),
            "staged_firmware_version": self._value("pending_firmware_version"),
            "cloud_firmware_version": self._value("cloud_firmware_version"),
            "cloud_auto_update_enabled": self._value("cloud_auto_update_enabled"),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Push updates to the frontend."""
        self.async_write_ha_state()
