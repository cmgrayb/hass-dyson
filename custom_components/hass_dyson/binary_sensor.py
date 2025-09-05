"""Binary sensor platform for Dyson integration."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CAPABILITY_FAULT_CODES, DEVICE_CATEGORY_FAULT_CODES, DOMAIN, FAULT_TRANSLATIONS
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity

_LOGGER = logging.getLogger(__name__)


def _is_fault_code_relevant(fault_code: str, device_categories: Any, device_capabilities: List[Any]) -> bool:
    """Check if a fault code is relevant for a device based on category and capabilities."""
    # Handle device category list properly
    if isinstance(device_categories, list):
        category_strings = []
        for cat in device_categories:
            if hasattr(cat, "value"):
                category_strings.append(cat.value)
            else:
                category_strings.append(str(cat))
    else:
        # Single category - convert to list for consistency
        if hasattr(device_categories, "value"):
            category_strings = [device_categories.value]
        else:
            category_strings = [str(device_categories)]

    # Convert capabilities to string values if they are enum objects
    capability_strings = []
    for cap in device_capabilities:
        if hasattr(cap, "value"):
            capability_strings.append(cap.value)
        else:
            capability_strings.append(str(cap))

    _LOGGER.debug(
        "Checking fault code '%s' relevance - categories: %s, capabilities: %s",
        fault_code,
        category_strings,
        capability_strings,
    )

    # Check if fault code is relevant for any device category
    for category_str in category_strings:
        category_fault_codes = DEVICE_CATEGORY_FAULT_CODES.get(category_str, [])
        if fault_code in category_fault_codes:
            _LOGGER.debug("Fault code '%s' matches device category '%s'", fault_code, category_str)
            return True

    # Check if fault code requires specific capabilities
    for capability, fault_codes in CAPABILITY_FAULT_CODES.items():
        if fault_code in fault_codes:
            is_relevant = capability in capability_strings
            _LOGGER.debug(
                "Fault code '%s' requires capability '%s' - device has it: %s (available capabilities: %s)",
                fault_code,
                capability,
                is_relevant,
                capability_strings,
            )
            return is_relevant

    _LOGGER.debug("Fault code '%s' not relevant for this device", fault_code)
    return False


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Dyson binary sensor platform."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Basic binary sensors for all devices
    entities.extend(
        [
            DysonFilterReplacementSensor(coordinator),
        ]
    )

    # Individual fault binary sensors - filter by device category and capabilities
    device_categories = coordinator.device_category
    device_capabilities = coordinator.device_capabilities

    _LOGGER.debug(
        "Device categories: %s, capabilities: %s",
        device_categories,
        device_capabilities,
    )

    # Create fault sensors for all fault types that are relevant to this device
    for fault_code, fault_info in FAULT_TRANSLATIONS.items():
        if _is_fault_code_relevant(fault_code, device_categories, device_capabilities):
            entities.append(DysonFaultSensor(coordinator, fault_code, fault_info))
            _LOGGER.debug("Adding fault sensor for code: %s", fault_code)
        else:
            _LOGGER.debug("Skipping fault sensor for irrelevant code: %s", fault_code)

    async_add_entities(entities, True)
    return True


class DysonFilterReplacementSensor(DysonEntity, BinarySensorEntity):  # type: ignore[misc]
    """Representation of filter replacement needed status."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the filter replacement sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_filter_replacement"
        self._attr_name = f"{coordinator.device_name} Filter Replacement"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.device:
            filters_to_check = []

            # Check if HEPA filter is installed by looking at filter type
            device_data = self.coordinator.data.get("product-state", {}) if self.coordinator.data else {}
            hepa_filter_type = device_data.get("hflt", "NONE")

            if hepa_filter_type != "NONE":  # HEPA filter is installed
                hepa_life = self.coordinator.device.hepa_filter_life
                filters_to_check.append(hepa_life)

            # Only check carbon filter if device has formaldehyde capability and is installed
            # TODO: Update this when we identify the exact formaldehyde capability name
            # For now, since we don't have formaldehyde devices, carbon filter won't be checked
            # capabilities = self.coordinator.device_capabilities or []
            # capabilities_str = [cap.lower() if isinstance(cap, str) else str(cap).lower() for cap in capabilities]
            # if "formaldehyde" in capabilities_str:
            #     carbon_filter_type = device_data.get("cflt", "NONE")
            #     if carbon_filter_type != "NONE":  # Carbon filter is installed
            #         carbon_life = self.coordinator.device.carbon_filter_life
            #         filters_to_check.append(carbon_life)

            # Filter needs replacement if any of the installed filters is below 10%
            self._attr_is_on = any(filter_life <= 10 for filter_life in filters_to_check)
        else:
            self._attr_is_on = False
        super()._handle_coordinator_update()


class DysonFaultSensor(DysonEntity, BinarySensorEntity):  # type: ignore[misc]
    """Representation of a device fault status."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator, fault_code: str, fault_info: Dict[str, str]) -> None:
        """Initialize the fault sensor."""
        super().__init__(coordinator)
        self._fault_code = fault_code
        self._fault_info = fault_info
        self._attr_unique_id = f"{coordinator.serial_number}_fault_{fault_code}"
        self._attr_name = f"{coordinator.device_name} Fault {self._get_fault_friendly_name()}"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    def _get_fault_friendly_name(self) -> str:
        """Get a friendly name for the fault code."""
        fault_names = {
            "aqs": "Air Quality Sensor",
            "fltr": "Filter",
            "hflr": "HEPA Filter",
            "cflr": "Carbon Filter",
            "mflr": "Motor",
            "temp": "Temperature Sensor",
            "humi": "Humidity Sensor",
            "pwr": "Power Supply",
            "wifi": "WiFi Connection",
            "sys": "System",
            "brsh": "Brush",
            "bin": "Dustbin",
        }
        return fault_names.get(self._fault_code, self._fault_code.upper())

    def _get_fault_icon(self, is_fault: bool = False) -> str:
        """Get an appropriate icon for the fault type based on state."""
        if self._fault_code == "aqs":
            # Air quality sensor: air-purifier when OK, air-purifier-off when fault
            return "mdi:air-purifier-off" if is_fault else "mdi:air-purifier"

        # Other fault types use static icons
        fault_icons = {
            "fltr": "mdi:air-filter",
            "hflr": "mdi:air-filter",
            "cflr": "mdi:air-filter",
            "mflr": "mdi:fan-alert",
            "temp": "mdi:thermometer-alert",
            "humi": "mdi:water-alert",
            "pwr": "mdi:power-plug-off",
            "wifi": "mdi:wifi-off",
            "sys": "mdi:alert-circle",
            "brsh": "mdi:brush-variant",
            "bin": "mdi:delete-alert",
        }
        return fault_icons.get(self._fault_code, "mdi:alert")

    @property
    def icon(self) -> str | None:
        """Return the icon based on current sensor state."""
        is_fault = self.is_on if self.is_on is not None else False
        return self._get_fault_icon(is_fault=is_fault)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_is_on = False
            self._attr_extra_state_attributes = {}
            super()._handle_coordinator_update()
            return

        # Check if this fault code is relevant to the current device category and capabilities
        device_category_str = self.coordinator.device_category
        device_capabilities = self.coordinator.device_capabilities

        if not _is_fault_code_relevant(self._fault_code, device_category_str, device_capabilities):
            # This fault sensor is not relevant to the current device type
            self._attr_available = False
            self._attr_is_on = False
            self._attr_extra_state_attributes = {
                "fault_code": self._fault_code,
                "status": f"Not applicable to {device_category_str} devices",
            }
            super()._handle_coordinator_update()
            return

        # Make sure the sensor is available for relevant fault codes
        self._attr_available = True

        # Get current faults from device
        try:
            # We'll use the same method the coordinator uses
            if hasattr(self.coordinator.device, "_faults_data") and self.coordinator.device._faults_data:
                raw_faults = self.coordinator.device._faults_data
                # Check if this fault code has any non-OK values in any section
                fault_found, fault_value = self._search_fault_in_data(raw_faults)

                if fault_found:
                    # Only consider it a fault if it's not OK/NONE/PASS/GOOD
                    if fault_value and fault_value.upper() not in ["OK", "NONE", "PASS", "GOOD"]:
                        self._attr_is_on = True
                        # Get human-readable description
                        description = self._fault_info.get(fault_value, f"Unknown fault: {fault_value}")
                        self._attr_extra_state_attributes = {
                            "fault_code": self._fault_code,
                            "fault_value": fault_value,
                            "description": description,
                            "severity": self._get_fault_severity(fault_value),
                        }
                    else:
                        self._attr_is_on = False
                        self._attr_extra_state_attributes = {
                            "fault_code": self._fault_code,
                            "fault_value": fault_value,
                            "status": "OK",
                        }
                else:
                    self._attr_is_on = False
                    self._attr_extra_state_attributes = {
                        "fault_code": self._fault_code,
                        "status": "No data",
                    }
            else:
                self._attr_is_on = False
                self._attr_extra_state_attributes = {}

        except Exception as err:
            _LOGGER.warning("Error updating fault sensor %s: %s", self._fault_code, err)
            self._attr_is_on = False
            self._attr_extra_state_attributes = {}

        super()._handle_coordinator_update()

    def _search_fault_in_data(self, fault_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Search for fault code in nested fault data structure."""
        # Search in all fault sections
        sections_to_search = ["product-errors", "product-warnings", "module-errors", "module-warnings"]

        for section_name in sections_to_search:
            section = fault_data.get(section_name, {})
            if self._fault_code in section:
                return True, section[self._fault_code]

        # Also check top-level for simple fault structure
        if self._fault_code in fault_data:
            return True, fault_data[self._fault_code]

        return False, ""

    def _get_fault_severity(self, fault_value: str) -> str:
        """Determine fault severity based on fault value."""
        if fault_value.upper() in ["FAIL", "STLL"]:
            return "Critical"
        elif fault_value.upper() in ["WARN", "HIGH", "LOW", "WEAK"]:
            return "Warning"
        elif fault_value.upper() in ["CHNG", "FULL", "WORN"]:
            return "Maintenance"
        else:
            return "Unknown"
