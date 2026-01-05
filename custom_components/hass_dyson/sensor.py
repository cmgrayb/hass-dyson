"""Sensor platform for Dyson integration.

This module implements comprehensive sensor support for Dyson devices,
providing real-time monitoring of air quality, environmental conditions,
and device status. Sensors are created based on device capabilities
and provide accurate, calibrated data for home automation.

Sensor Categories:

Air Quality Sensors (ExtendedAQ capability):
    - PM2.5: Fine particulate matter concentration (μg/m³)
    - PM10: Coarse particulate matter concentration (μg/m³)
    - VOC: Volatile organic compounds index (0-10)
    - NO2: Nitrogen dioxide index (0-10)
    - Formaldehyde: HCHO concentration (mg/m³, if supported)

Environmental Sensors:
    - Temperature: Ambient temperature in °C
    - Humidity: Relative humidity percentage

Device Status Sensors:
    - Filter Life: HEPA and Carbon filter remaining life (0-100%)
    - Device Status: Overall device operational status
    - Connection Status: Local/Cloud/Disconnected

Key Features:
    - Real-time data updates via MQTT streaming
    - Capability-based sensor creation (only supported sensors)
    - Proper Home Assistant device classes and units
    - State classes for long-term statistics
    - Entity categories for organization (diagnostic sensors)
    - Thread-safe coordinator update handling
    - Calibrated data with manufacturer specifications

Data Quality:
    All sensor data is sourced directly from device environmental monitoring
    systems with Dyson's calibration and filtering applied. Updates occur
    in real-time as air quality conditions change.

Sensor States:
    - Measurement sensors: Provide continuous numeric values
    - Diagnostic sensors: Device status and maintenance information
    - Configuration sensors: Settings and operational parameters
"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CAPABILITY_EXTENDED_AQ,
    CAPABILITY_FORMALDEHYDE,
    CAPABILITY_VOC,
    DOMAIN,
)
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity

_LOGGER = logging.getLogger(__name__)


class DysonP25RSensor(DysonEntity, SensorEntity):
    """PM2.5 air quality sensor for Dyson devices with ExtendedAQ capability.

    This sensor monitors fine particulate matter (PM2.5) concentration in
    micrograms per cubic meter. PM2.5 particles are particularly harmful
    as they can penetrate deep into lungs and bloodstream.

    Attributes:
        device_class: SensorDeviceClass.PM25 for proper Home Assistant integration
        state_class: SensorStateClass.MEASUREMENT for long-term statistics
        unit_of_measurement: μg/m³ (micrograms per cubic meter)
        icon: mdi:air-filter for visual representation

    Health Guidelines (WHO recommendations):
        - Annual average: ≤ 5 μg/m³
        - Daily average: ≤ 15 μg/m³
        - Values > 200 μg/m³: Hazardous air quality

    Data Source:
        Real-time measurements from device environmental sensors,
        updated automatically as air quality conditions change.

    Availability:
        Only created for devices with "ExtendedAQ" capability that
        support advanced air quality monitoring beyond basic PM sensors.

    Example:
        Typical sensor values and automation:

        >>> # Good air quality
        >>> sensor.native_value = 8  # μg/m³
        >>>
        >>> # Poor air quality - trigger high fan speed
        >>> if sensor.native_value > 50:
        >>>     await fan.async_set_percentage(100)

    Note:
        This sensor provides highly accurate PM2.5 measurements using
        Dyson's laser particle counting technology with real-time updates.
    """

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the PM2.5 sensor with proper Home Assistant integration.

        Args:
            coordinator: DysonDataUpdateCoordinator providing device access

        Configuration:
        - unique_id: {serial_number}_p25r for entity registry
        - translation_key: "p25r" for localized naming
        - device_class: PM25 for proper sensor categorization
        - state_class: MEASUREMENT for long-term statistics
        - unit: μg/m³ for standard air quality measurements
        - icon: air-filter for visual representation

        Integration Features:
        - Automatic device registry linking via parent DysonEntity
        - Long-term statistics support for trend analysis
        - Proper sensor categorization in Home Assistant UI
        - Localized entity naming through translation system

        Note:
            Only initialized for devices with ExtendedAQ capability
            that support PM2.5 monitoring beyond basic air quality sensors.
        """
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_p25r"
        self._attr_translation_key = "p25r"
        self._attr_device_class = SensorDeviceClass.PM25
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        try:
            old_value = self._attr_native_value
            new_value = None

            # Get environmental data from coordinator
            env_data = (
                self.coordinator.data.get("environmental-data", {})
                if self.coordinator.data
                else {}
            )
            p25r_raw = env_data.get("p25r")

            if p25r_raw is not None:
                try:
                    # Convert and validate the P25R value
                    new_value = int(p25r_raw)
                    if not (0 <= new_value <= 999):
                        _LOGGER.warning(
                            "Invalid P25R value for device %s: %s (expected 0-999)",
                            device_serial,
                            new_value,
                        )
                        new_value = None
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Invalid P25R value format for device %s: %s",
                        device_serial,
                        p25r_raw,
                    )
                    new_value = None

            self._attr_native_value = new_value

            if new_value is not None:
                _LOGGER.debug(
                    "P25R sensor updated for %s: %s -> %s",
                    device_serial,
                    old_value,
                    new_value,
                )
            else:
                _LOGGER.debug("No P25R data available for device %s", device_serial)

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "P25R data not available for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid P25R data format for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating P25R sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonP10RSensor(DysonEntity, SensorEntity):
    """P10R level sensor for Dyson devices with ExtendedAQ capability."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the P10R sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_p10r"
        self._attr_translation_key = "p10r"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        try:
            old_value = self._attr_native_value
            new_value = None

            # Get environmental data from coordinator
            env_data = (
                self.coordinator.data.get("environmental-data", {})
                if self.coordinator.data
                else {}
            )
            p10r_raw = env_data.get("p10r")

            if p10r_raw is not None:
                try:
                    # Convert and validate the P10R value
                    new_value = int(p10r_raw)
                    if not (0 <= new_value <= 999):
                        _LOGGER.warning(
                            "Invalid P10R value for device %s: %s (expected 0-999)",
                            device_serial,
                            new_value,
                        )
                        new_value = None
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Invalid P10R value format for device %s: %s",
                        device_serial,
                        p10r_raw,
                    )
                    new_value = None

            self._attr_native_value = new_value

            if new_value is not None:
                _LOGGER.debug(
                    "P10R sensor updated for %s: %s -> %s",
                    device_serial,
                    old_value,
                    new_value,
                )
            else:
                _LOGGER.debug("No P10R data available for device %s", device_serial)

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "P10R data not available for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid P10R data format for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating P10R sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonCO2Sensor(DysonEntity, SensorEntity):
    """CO2 sensor for Dyson devices with ExtendedAQ capability."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the CO2 sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_co2"
        self._attr_translation_key = "co2"
        self._attr_device_class = SensorDeviceClass.CO2
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "ppm"
        self._attr_icon = "mdi:molecule-co2"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        try:
            old_value = self._attr_native_value
            new_value = None

            # Get environmental data from coordinator
            env_data = (
                self.coordinator.data.get("environmental-data", {})
                if self.coordinator.data
                else {}
            )
            co2_raw = env_data.get("co2r")

            if co2_raw is not None:
                try:
                    # Convert and validate the CO2 value
                    new_value = int(co2_raw)
                    if not (0 <= new_value <= 5000):
                        _LOGGER.warning(
                            "Invalid CO2 value for device %s: %s (expected 0-5000)",
                            device_serial,
                            new_value,
                        )
                        new_value = None
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Invalid CO2 value format for device %s: %s",
                        device_serial,
                        co2_raw,
                    )
                    new_value = None

            self._attr_native_value = new_value

            if new_value is not None:
                _LOGGER.debug(
                    "CO2 sensor updated for %s: %s -> %s",
                    device_serial,
                    old_value,
                    new_value,
                )
            else:
                _LOGGER.debug("No CO2 data available for device %s", device_serial)

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "CO2 data not available for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid CO2 data format for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating CO2 sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonVOCSensor(DysonEntity, SensorEntity):
    """VOC (Volatile Organic Compounds) sensor for Dyson devices with ExtendedAQ capability."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the VOC sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_voc"
        self._attr_translation_key = "voc"
        self._attr_device_class = SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        try:
            old_value = self._attr_native_value
            new_value = None

            # Get environmental data from coordinator
            env_data = (
                self.coordinator.data.get("environmental-data", {})
                if self.coordinator.data
                else {}
            )
            hcho_raw = env_data.get("va10")

            if hcho_raw is not None:
                try:
                    # Convert and validate the VOC value
                    raw_value = int(hcho_raw)
                    if not (0 <= raw_value <= 9999):
                        _LOGGER.warning(
                            "Invalid VOC raw value for device %s: %s (expected 0-9999)",
                            device_serial,
                            raw_value,
                        )
                        new_value = None
                    else:
                        # Convert from raw index to mg/m³ (matches libdyson-neon implementation)
                        # Range 0-9999 raw becomes 0.000-9.999 mg/m³ (reports actual conditions)
                        new_value = round(raw_value / 1000.0, 3)
                        _LOGGER.debug(
                            "VOC conversion for %s: %d raw -> %.3f mg/m³",
                            device_serial,
                            raw_value,
                            new_value,
                        )
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Invalid VOC value format for device %s: %s",
                        device_serial,
                        hcho_raw,
                    )
                    new_value = None

            self._attr_native_value = new_value

            if new_value is not None:
                _LOGGER.debug(
                    "VOC sensor updated for %s: %s -> %s",
                    device_serial,
                    old_value,
                    new_value,
                )
            else:
                _LOGGER.debug("No VOC data available for device %s", device_serial)

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "VOC data not available for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid VOC data format for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating VOC sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()


async def async_setup_entry(  # noqa: C901
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Dyson sensor platform."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Get device capabilities and category with error handling
    try:
        capabilities = coordinator.device_capabilities or []
        device_category = coordinator.device_category or []
        device_serial = coordinator.serial_number

        _LOGGER.debug(
            "Setting up sensors for device %s with capabilities: %s, category: %s",
            device_serial,
            capabilities,
            device_category,
        )

        # Import safe capability checking functions
        from .device_utils import has_any_capability_safe, has_capability_safe

        # Get environmental data for all sensor checks
        env_data = (
            coordinator.data.get("environmental-data", {}) if coordinator.data else {}
        )

        # Add PM2.5, PM10, P25R, P10R, and gas sensors for devices with ExtendedAQ capability
        # ExtendedAQ now supports PM2.5, PM10, CO2, NO2, and HCHO (Formaldehyde) metrics per discovery.md
        # Gas sensor key mappings (per cmgrayb/libdyson-neon):
        # - CO2: co2r (not co2)
        # - HCHO (VOC): va10 (not hcho)
        # - NO2: noxl (not no2)
        if has_any_capability_safe(
            capabilities, ["ExtendedAQ", "extended_aq", "extendedAQ"]
        ):
            _LOGGER.debug("Adding ExtendedAQ sensors for device %s", device_serial)

            # Add PM2.5 and PM10 sensors for ExtendedAQ devices
            # These sensors now automatically use revised values (p25r, p10r) when available,
            # falling back to legacy values (pm25, pm10) for older devices
            entities.extend(
                [
                    DysonPM25Sensor(coordinator),
                    DysonPM10Sensor(coordinator),
                ]
            )

            # Add CO2 sensor if CO2 data is present
            if "co2r" in env_data:
                _LOGGER.debug(
                    "Adding CO2 sensor for device %s - CO2 data detected", device_serial
                )
                entities.append(DysonCO2Sensor(coordinator))
            else:
                _LOGGER.debug(
                    "Skipping CO2 sensor for device %s - no CO2 data in environmental response",
                    device_serial,
                )

            # Add NO2 sensor if NO2 data is present
            if "noxl" in env_data:
                _LOGGER.debug(
                    "Adding NO2 sensor for device %s - NO2 data detected", device_serial
                )
                entities.append(DysonNO2Sensor(coordinator))
            else:
                _LOGGER.debug(
                    "Skipping NO2 sensor for device %s - no NO2 data in environmental response",
                    device_serial,
                )

            # Add VOC sensor if VOC data is present (va10)
            if "va10" in env_data:
                _LOGGER.debug(
                    "Adding VOC sensor for device %s - VOC data detected",
                    device_serial,
                )
                entities.append(DysonVOCSensor(coordinator))
            else:
                _LOGGER.debug(
                    "Skipping VOC sensor for device %s - no VOC data in environmental response",
                    device_serial,
                )

            # Add Formaldehyde sensor if HCHO data is present (hchr or hcho)
            if "hchr" in env_data or "hcho" in env_data:
                _LOGGER.debug(
                    "Adding Formaldehyde sensor for device %s - HCHO data detected",
                    device_serial,
                )
                entities.append(DysonFormaldehydeSensor(coordinator))
            else:
                _LOGGER.debug(
                    "Skipping Formaldehyde sensor for device %s - no HCHO data in environmental response",
                    device_serial,
                )
        else:
            _LOGGER.debug(
                "Skipping ExtendedAQ sensors for device %s - no ExtendedAQ capability",
                device_serial,
            )

        # Add WiFi-related sensors only for "ec" and "robot" device categories (devices with WiFi connectivity)
        if any(cat in ["ec", "robot"] for cat in device_category):
            _LOGGER.debug("Adding WiFi sensors for device %s", device_serial)
            entities.extend(
                [
                    DysonWiFiSensor(coordinator),
                    DysonConnectionStatusSensor(coordinator),
                ]
            )
        else:
            _LOGGER.debug(
                "Skipping WiFi sensors for device %s - category %s does not support WiFi monitoring",
                device_serial,
                device_category,
            )

        # Add HEPA filter sensors only for devices with ExtendedAQ capability
        if has_any_capability_safe(
            capabilities, ["ExtendedAQ", "extended_aq", "extendedAQ"]
        ):
            _LOGGER.debug("Adding HEPA filter sensors for device %s", device_serial)
            entities.extend(
                [
                    DysonHEPAFilterLifeSensor(coordinator),
                    DysonHEPAFilterTypeSensor(coordinator),
                ]
            )
        else:
            _LOGGER.debug(
                "Skipping HEPA filter sensors for device %s - no ExtendedAQ capability",
                device_serial,
            )

        # Add carbon filter sensors based on device state data presence
        # Check if carbon filter data is present in device state (cflt field)
        device_data = (
            coordinator.data.get("product-state", {}) if coordinator.data else {}
        )
        carbon_filter_type = device_data.get("cflt")

        # Add carbon filter sensors if filter data exists and is not "NONE" or "SCOG"
        if carbon_filter_type is not None and str(carbon_filter_type).upper() not in [
            "NONE",
            "SCOG",
        ]:
            _LOGGER.debug(
                "Adding carbon filter sensors for device %s - filter type: %s",
                device_serial,
                carbon_filter_type,
            )
            entities.extend(
                [
                    DysonCarbonFilterLifeSensor(coordinator),
                    DysonCarbonFilterTypeSensor(coordinator),
                ]
            )
        else:
            _LOGGER.debug(
                "Skipping carbon filter sensors for device %s - no carbon filter detected (cflt: %s)",
                device_serial,
                carbon_filter_type,
            )

        # Add temperature sensor based on capability AND data presence
        # Check both capability and actual data availability in environmental response
        has_temp_capability = has_capability_safe(
            capabilities, "heating"
        ) or has_any_capability_safe(
            capabilities,
            ["EnvironmentalData", "environmental_data", "environmentalData"],
        )

        if has_temp_capability and "tact" in env_data:
            _LOGGER.debug(
                "Adding temperature sensor for device %s - capability and temperature data detected",
                device_serial,
            )
            entities.append(DysonTemperatureSensor(coordinator))
        elif has_temp_capability:
            _LOGGER.debug(
                "Skipping temperature sensor for device %s - capability present but no temperature data in environmental response",
                device_serial,
            )
        else:
            _LOGGER.debug(
                "Skipping temperature sensor for device %s - no heating or environmental capability",
                device_serial,
            )

        # Add humidity sensor based on capability AND data presence
        # Check both capability and actual data availability in environmental response
        has_humidity_capability = has_any_capability_safe(
            capabilities, ["Humidifier", "humidifier", "Humidity"]
        ) or has_any_capability_safe(
            capabilities,
            ["EnvironmentalData", "environmental_data", "environmentalData"],
        )

        if has_humidity_capability and "hact" in env_data:
            _LOGGER.debug(
                "Adding humidity sensor for device %s - capability and humidity data detected",
                device_serial,
            )
            entities.append(DysonHumiditySensor(coordinator))
        elif has_humidity_capability:
            _LOGGER.debug(
                "Skipping humidity sensor for device %s - capability present but no humidity data in environmental response",
                device_serial,
            )
        else:
            _LOGGER.debug(
                "Skipping humidity sensor for device %s - no humidifier or environmental capability detected",
                device_serial,
            )

        # Add formaldehyde sensor for devices with Formaldehyde capability (manual testing placeholder)
        # Only add if NOT already covered by ExtendedAQ capability to prevent duplicates
        # Formaldehyde capability forces sensor creation for UI testing (regardless of data presence)
        if has_any_capability_safe(
            capabilities, [CAPABILITY_FORMALDEHYDE]
        ) and not has_any_capability_safe(
            capabilities, [CAPABILITY_EXTENDED_AQ, "extended_aq", "extendedAQ"]
        ):
            _LOGGER.debug(
                "Adding formaldehyde sensor for device %s - Formaldehyde capability (forced creation for UI testing)",
                device_serial,
            )
            entities.append(DysonFormaldehydeSensor(coordinator))
        elif has_any_capability_safe(
            capabilities, [CAPABILITY_FORMALDEHYDE]
        ) and has_any_capability_safe(
            capabilities, [CAPABILITY_EXTENDED_AQ, "extended_aq", "extendedAQ"]
        ):
            _LOGGER.debug(
                "Skipping formaldehyde sensor for device %s - already covered by ExtendedAQ capability",
                device_serial,
            )
        else:
            _LOGGER.debug(
                "Skipping formaldehyde sensor for device %s - no Formaldehyde capability",
                device_serial,
            )

        # Add gas sensors for devices with VOC capability (manual testing placeholder)
        # Only add if NOT already covered by ExtendedAQ capability to prevent duplicates
        # VOC capability forces sensor creation for UI testing (regardless of data presence)
        if has_any_capability_safe(
            capabilities, [CAPABILITY_VOC]
        ) and not has_any_capability_safe(
            capabilities, [CAPABILITY_EXTENDED_AQ, "extended_aq", "extendedAQ"]
        ):
            _LOGGER.debug(
                "Adding gas sensors for device %s - VOC capability (forced creation for UI testing)",
                device_serial,
            )
            # Add VOC sensor for UI testing
            entities.append(DysonVOCSensor(coordinator))
            # Add NO2 sensor for UI testing
            entities.append(DysonNO2Sensor(coordinator))
            # Add CO2 sensor for UI testing
            entities.append(DysonCO2Sensor(coordinator))
        elif has_any_capability_safe(
            capabilities, [CAPABILITY_VOC]
        ) and has_any_capability_safe(
            capabilities, [CAPABILITY_EXTENDED_AQ, "extended_aq", "extendedAQ"]
        ):
            _LOGGER.debug(
                "Skipping gas sensors for device %s - already covered by ExtendedAQ capability",
                device_serial,
            )
        else:
            _LOGGER.debug(
                "Skipping gas sensors for device %s - no VOC capability",
                device_serial,
            )

        # Add humidifier-specific sensors for devices with Humidifier capability
        if has_any_capability_safe(capabilities, ["Humidifier", "humidifier"]):
            _LOGGER.debug(
                "Adding humidifier sensors for device %s - Humidifier capability detected",
                device_serial,
            )
            entities.extend(
                [
                    DysonNextCleaningCycleSensor(coordinator),
                    DysonCleaningTimeRemainingSensor(coordinator),
                ]
            )
        else:
            _LOGGER.debug(
                "Skipping humidifier sensors for device %s - no Humidifier capability",
                device_serial,
            )

        # Add battery sensor only for devices with robot category
        # Robot devices report battery level via the vacuum entity battery_level property
        # No separate battery sensor needed - vacuum entity handles both control and battery monitoring
        if any(cat in ["robot"] for cat in device_category):
            _LOGGER.debug(
                "Robot device %s battery level available via vacuum entity",
                device_serial,
            )

        _LOGGER.info(
            "Successfully set up %d sensor entities for device %s",
            len(entities),
            device_serial,
        )

    except (KeyError, AttributeError) as err:
        _LOGGER.warning(
            "Device capability data unavailable for sensor setup on %s: %s",
            coordinator.serial_number,
            err,
        )
        # Don't fail completely - add basic sensors at minimum
        _LOGGER.info(
            "Falling back to basic sensor setup for device %s",
            coordinator.serial_number,
        )
        entities = []  # Reset entities list to prevent partial setup
    except (ValueError, TypeError) as err:
        _LOGGER.error(
            "Invalid device data format during sensor setup for %s: %s",
            coordinator.serial_number,
            err,
        )
        # Don't fail completely - add basic sensors at minimum
        _LOGGER.info(
            "Falling back to basic sensor setup for device %s",
            coordinator.serial_number,
        )
        entities = []  # Reset entities list to prevent partial setup
    except Exception as err:
        _LOGGER.error(
            "Unexpected error during sensor setup for device %s: %s",
            coordinator.serial_number,
            err,
        )
        # Don't fail completely - add basic sensors at minimum
        _LOGGER.warning(
            "Falling back to basic sensor setup for device %s",
            coordinator.serial_number,
        )
        entities = []  # Reset entities list to prevent partial setup

    async_add_entities(entities, True)
    return True


class DysonFilterLifeSensor(DysonEntity, SensorEntity):
    """Representation of a Dyson filter life sensor."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(
        self, coordinator: DysonDataUpdateCoordinator, filter_type: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.filter_type = filter_type
        self._attr_unique_id = f"{coordinator.serial_number}_{filter_type}_filter_life"
        self._attr_translation_key = "filter_life"
        self._attr_translation_placeholders = {"filter_type": filter_type.upper()}
        self._attr_native_unit_of_measurement = PERCENTAGE
        # No device class - filter life sensors don't have a specific Home Assistant device class
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            self._attr_native_value = None
            return

        # Update filter life based on coordinator data
        filter_life = self.coordinator.data.get(f"{self.filter_type}_filter_life")
        if filter_life is not None:
            try:
                self._attr_native_value = int(filter_life)
            except (ValueError, TypeError):
                self._attr_native_value = None
        else:
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonAirQualitySensor(DysonEntity, SensorEntity):
    """Representation of a Dyson air quality sensor."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(
        self, coordinator: DysonDataUpdateCoordinator, sensor_type: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.sensor_type = sensor_type
        self._attr_unique_id = f"{coordinator.serial_number}_{sensor_type}"
        self._attr_name = sensor_type.upper()
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:air-filter"

        if sensor_type in ["pm25", "pm10"]:
            self._attr_device_class = (
                SensorDeviceClass.PM25
                if sensor_type == "pm25"
                else SensorDeviceClass.PM10
            )
            self._attr_native_unit_of_measurement = (
                CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
            )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            self._attr_native_value = None
            return

        # Update air quality value based on coordinator data
        value = self.coordinator.data.get(self.sensor_type)
        if value is not None:
            try:
                self._attr_native_value = int(value)
            except (ValueError, TypeError):
                self._attr_native_value = None
        else:
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonTemperatureSensor(DysonEntity, SensorEntity):
    """Temperature sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_temperature"
        self._attr_translation_key = "temperature"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

        # Use Home Assistant's unit system for temperature display
        # Always report in Celsius as native unit - HA will convert for display
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            self._attr_native_value = None
            return

        # Temperature from environmental data using 'tact' key (temperature actual)
        environmental_data = self.coordinator.data.get("environmental-data", {})
        temperature = environmental_data.get("tact")
        if temperature is not None:
            try:
                # Handle "OFF" as a valid state when sensors are inactive
                if temperature == "OFF":
                    _LOGGER.debug(
                        "Temperature sensor inactive for device %s: %s",
                        self.coordinator.serial_number,
                        temperature,
                    )
                    self._attr_native_value = None
                else:
                    # Dyson reports temperature in Kelvin * 10 (e.g., "2977" = 297.7K)
                    # Convert to Celsius: (K * 10) / 10 - 273.15
                    # Home Assistant will automatically convert to Fahrenheit for imperial users
                    temp_celsius = (float(temperature) / 10) - 273.15
                    self._attr_native_value = round(temp_celsius, 1)
            except (ValueError, TypeError):
                self._attr_native_value = None
        else:
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonHumiditySensor(DysonEntity, SensorEntity):
    """Humidity sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the humidity sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_humidity"
        self._attr_translation_key = "humidity"
        self._attr_device_class = SensorDeviceClass.HUMIDITY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = PERCENTAGE

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        try:
            old_value = self._attr_native_value
            new_value = None

            # Get environmental data from coordinator
            env_data = (
                self.coordinator.data.get("environmental-data", {})
                if self.coordinator.data
                else {}
            )
            humidity_raw = env_data.get("hact")

            if humidity_raw is not None:
                try:
                    # Handle "OFF" as a valid state when sensors are inactive
                    if humidity_raw == "OFF":
                        _LOGGER.debug(
                            "Humidity sensor inactive for device %s: %s",
                            device_serial,
                            humidity_raw,
                        )
                        new_value = None
                    else:
                        # Convert and validate the humidity value
                        # libdyson-neon shows hact as 4-digit string: "0030" = 30%, "0058" = 58%
                        humidity_value = int(humidity_raw)
                        if not (0 <= humidity_value <= 100):
                            _LOGGER.warning(
                                "Invalid humidity value for device %s: %s%% (expected 0-100)",
                                device_serial,
                                humidity_value,
                            )
                            new_value = None
                        else:
                            new_value = humidity_value
                            _LOGGER.debug(
                                "Humidity conversion for %s: %s -> %d%%",
                                device_serial,
                                humidity_raw,
                                new_value,
                            )
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Invalid humidity value format for device %s: %s",
                        device_serial,
                        humidity_raw,
                    )
                    new_value = None

            self._attr_native_value = new_value

            if new_value is not None:
                _LOGGER.debug(
                    "Humidity sensor updated for %s: %s -> %s%%",
                    device_serial,
                    old_value,
                    new_value,
                )
            else:
                _LOGGER.debug(
                    "Humidity sensor update: no valid humidity data for device %s",
                    device_serial,
                )

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "Humidity data not available for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid humidity data format for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating humidity sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None

        self.async_write_ha_state()

        super()._handle_coordinator_update()


class DysonPM25Sensor(DysonEntity, SensorEntity):
    """PM2.5 sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the PM2.5 sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_pm25"
        self._attr_translation_key = "pm25"
        self._attr_device_class = SensorDeviceClass.PM25
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
        self._attr_icon = "mdi:air-filter"

        _LOGGER.debug(
            "Initialized PM2.5 sensor for %s with initial value: %s",
            coordinator.serial_number,
            self._attr_native_value,
        )

        # Immediately sync with current environmental data if available
        self._sync_with_current_data()

    def _sync_with_current_data(self) -> None:
        """Sync sensor with current environmental data if available."""
        if self.coordinator.device and hasattr(
            self.coordinator.device, "_environmental_data"
        ):
            env_data = self.coordinator.device.get_environmental_data()
            if env_data.get("pm25") is not None:
                old_value = self._attr_native_value
                new_value = self.coordinator.device.pm25
                self._attr_native_value = new_value
                _LOGGER.debug(
                    "PM2.5 sensor synced with existing data for %s: %s -> %s",
                    self.coordinator.serial_number,
                    old_value,
                    new_value,
                )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        try:
            # Read from coordinator data following Home Assistant best practices
            old_value = self._attr_native_value
            new_value = None

            # Get environmental data from coordinator
            env_data = (
                self.coordinator.data.get("environmental-data", {})
                if self.coordinator.data
                else {}
            )

            # Try revised value first (p25r), fall back to legacy (pm25)
            pm25_raw = env_data.get("p25r") or env_data.get("pm25")

            if pm25_raw is not None:
                try:
                    # Convert and validate the PM2.5 value
                    new_value = int(pm25_raw)
                    if not (0 <= new_value <= 999):
                        _LOGGER.warning(
                            "Invalid PM2.5 value for device %s: %s (expected 0-999)",
                            device_serial,
                            new_value,
                        )
                        new_value = None
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Invalid PM2.5 value format for device %s: %s",
                        device_serial,
                        pm25_raw,
                    )
                    new_value = None

            self._attr_native_value = new_value

            if new_value is not None:
                _LOGGER.debug(
                    "PM2.5 sensor updated for %s: %s -> %s",
                    device_serial,
                    old_value,
                    new_value,
                )
            else:
                _LOGGER.debug("No PM2.5 data available for device %s", device_serial)

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "PM2.5 data not available for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid PM2.5 data format for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating PM2.5 sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonPM10Sensor(DysonEntity, SensorEntity):
    """PM10 sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the PM10 sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_pm10"
        self._attr_translation_key = "pm10"
        self._attr_device_class = SensorDeviceClass.PM10
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
        self._attr_icon = "mdi:air-filter"

        _LOGGER.debug(
            "Initialized PM10 sensor for %s with initial value: %s",
            coordinator.serial_number,
            self._attr_native_value,
        )

        # Immediately sync with current environmental data if available
        self._sync_with_current_data()

    def _sync_with_current_data(self) -> None:
        """Sync sensor with current environmental data if available."""
        if self.coordinator.device and hasattr(
            self.coordinator.device, "_environmental_data"
        ):
            env_data = self.coordinator.device.get_environmental_data()
            if env_data.get("pm10") is not None:
                old_value = self._attr_native_value
                new_value = self.coordinator.device.pm10
                self._attr_native_value = new_value
                _LOGGER.debug(
                    "PM10 sensor synced with existing data for %s: %s -> %s",
                    self.coordinator.serial_number,
                    old_value,
                    new_value,
                )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        try:
            # Read from coordinator data following Home Assistant best practices
            old_value = self._attr_native_value
            new_value = None

            # Get environmental data from coordinator
            env_data = (
                self.coordinator.data.get("environmental-data", {})
                if self.coordinator.data
                else {}
            )

            # Try revised value first (p10r), fall back to legacy (pm10)
            pm10_raw = env_data.get("p10r") or env_data.get("pm10")

            if pm10_raw is not None:
                try:
                    # Convert and validate the PM10 value
                    new_value = int(pm10_raw)
                    if not (0 <= new_value <= 999):
                        _LOGGER.warning(
                            "Invalid PM10 value for device %s: %s (expected 0-999)",
                            device_serial,
                            new_value,
                        )
                        new_value = None
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Invalid PM10 value format for device %s: %s",
                        device_serial,
                        pm10_raw,
                    )
                    new_value = None

            self._attr_native_value = new_value

            if new_value is not None:
                _LOGGER.debug(
                    "PM10 sensor updated for %s: %s -> %s",
                    device_serial,
                    old_value,
                    new_value,
                )
            else:
                _LOGGER.debug("No PM10 data available for device %s", device_serial)

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "PM10 data not available for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid PM10 data format for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating PM10 sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonNO2Sensor(DysonEntity, SensorEntity):
    """NO2 (Nitrogen Dioxide) sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the NO2 sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_no2"
        self._attr_translation_key = "no2"
        self._attr_device_class = SensorDeviceClass.NITROGEN_DIOXIDE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
        self._attr_icon = "mdi:molecule"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        try:
            old_value = self._attr_native_value
            new_value = None

            # Get environmental data from coordinator
            env_data = (
                self.coordinator.data.get("environmental-data", {})
                if self.coordinator.data
                else {}
            )
            no2_raw = env_data.get("noxl")

            if no2_raw is not None:
                try:
                    # Convert and validate the NO2 value
                    new_value = int(no2_raw)
                    if not (0 <= new_value <= 200):
                        _LOGGER.warning(
                            "Invalid NO2 value for device %s: %s (expected 0-200)",
                            device_serial,
                            new_value,
                        )
                        new_value = None
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Invalid NO2 value format for device %s: %s",
                        device_serial,
                        no2_raw,
                    )
                    new_value = None

            self._attr_native_value = new_value

            if new_value is not None:
                _LOGGER.debug(
                    "NO2 sensor updated for %s: %s -> %s",
                    device_serial,
                    old_value,
                    new_value,
                )
            else:
                _LOGGER.debug("No NO2 data available for device %s", device_serial)

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "NO2 data not available for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid NO2 data format for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating NO2 sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonFormaldehydeSensor(DysonEntity, SensorEntity):
    """HCHO (Formaldehyde) sensor for legacy Dyson devices with Formaldehyde capability."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the formaldehyde sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_hcho"
        self._attr_translation_key = "hcho"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER
        self._attr_icon = "mdi:molecule"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        try:
            old_value = self._attr_native_value
            new_value = None

            # Get environmental data from coordinator
            env_data = (
                self.coordinator.data.get("environmental-data", {})
                if self.coordinator.data
                else {}
            )
            # Try revised value first (hchr), fall back to legacy (hcho)
            # Handle 'NONE' values explicitly - they should be treated as unavailable
            hchr_raw = env_data.get("hchr")
            hcho_raw = env_data.get("hcho")

            # Use hchr if available and not 'NONE', otherwise fall back to hcho
            if hchr_raw and hchr_raw != "NONE":
                hcho_raw = hchr_raw
            elif hcho_raw and hcho_raw != "NONE":
                hcho_raw = hcho_raw
            else:
                hcho_raw = None

            if hcho_raw is not None:
                try:
                    # Convert and validate the HCHO value
                    # Legacy devices provide hchr as raw index value that needs /1000 to get ppb
                    raw_value = int(hcho_raw)
                    if not (
                        0 <= raw_value <= 9999
                    ):  # Full range to report actual device measurements
                        _LOGGER.warning(
                            "Invalid HCHO raw value for device %s: %s (expected 0-9999)",
                            device_serial,
                            raw_value,
                        )
                        new_value = None
                    else:
                        # Convert from raw index to mg/m³ (matches libdyson-neon implementation)
                        # libdyson-neon uses: val = self._get_environmental_field_value("hchr", divisor=1000)
                        new_value = round(raw_value / 1000.0, 3)
                        _LOGGER.debug(
                            "HCHO conversion for %s: %d raw -> %.3f mg/m³",
                            device_serial,
                            raw_value,
                            new_value,
                        )
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Invalid HCHO value format for device %s: %s",
                        device_serial,
                        hcho_raw,
                    )
                    new_value = None

            self._attr_native_value = new_value

            if new_value is not None:
                _LOGGER.debug(
                    "HCHO sensor updated for %s: %s -> %s",
                    device_serial,
                    old_value,
                    new_value,
                )
            else:
                _LOGGER.debug("No HCHO data available for device %s", device_serial)

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "HCHO data not available for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid HCHO data format for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating HCHO sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonWiFiSensor(DysonEntity, SensorEntity):
    """WiFi signal strength sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the WiFi sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_wifi"
        self._attr_translation_key = "wifi_signal"
        self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "dBm"
        self._attr_icon = "mdi:wifi"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_native_value = None
            return

        # Use our device RSSI property
        self._attr_native_value = self.coordinator.device.rssi
        super()._handle_coordinator_update()


class DysonHEPAFilterLifeSensor(DysonEntity, SensorEntity):
    """HEPA filter life sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the HEPA filter life sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_hepa_filter_life"
        self._attr_translation_key = "hepa_filter_life"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:air-filter"
        # No device class - filter life sensors don't have a specific Home Assistant device class

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        if not self.coordinator.device:
            self._attr_native_value = None
            _LOGGER.debug(
                "HEPA filter life sensor update: device not available for %s",
                device_serial,
            )
            return

        try:
            # Use our device HEPA filter life property with enhanced error handling
            filter_life_value = getattr(
                self.coordinator.device, "hepa_filter_life", None
            )

            # Validate the filter life value is reasonable
            if filter_life_value is not None:
                if (
                    isinstance(filter_life_value, int | float)
                    and 0 <= filter_life_value <= 100
                ):
                    self._attr_native_value = filter_life_value
                    _LOGGER.debug(
                        "HEPA filter life updated for %s: %s%%",
                        device_serial,
                        filter_life_value,
                    )
                else:
                    _LOGGER.warning(
                        "Invalid HEPA filter life value for device %s: %s (expected 0-100)",
                        device_serial,
                        filter_life_value,
                    )
                    self._attr_native_value = None
            else:
                self._attr_native_value = None
                _LOGGER.debug(
                    "No HEPA filter life data available for device %s", device_serial
                )

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "HEPA filter life data not available for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid HEPA filter life data format for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating HEPA filter life sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonCarbonFilterLifeSensor(DysonEntity, SensorEntity):
    """Carbon filter life sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the carbon filter life sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_carbon_filter_life"
        self._attr_translation_key = "carbon_filter_life"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:air-filter"
        # No device class - filter life sensors don't have a specific Home Assistant device class

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        if not self.coordinator.device:
            self._attr_native_value = None
            _LOGGER.debug(
                "Carbon filter life sensor update: device not available for %s",
                device_serial,
            )
            return

        try:
            # Use our device carbon filter life property with enhanced error handling
            filter_life_value = getattr(
                self.coordinator.device, "carbon_filter_life", None
            )

            # Validate the filter life value is reasonable
            if filter_life_value is not None:
                if (
                    isinstance(filter_life_value, int | float)
                    and 0 <= filter_life_value <= 100
                ):
                    self._attr_native_value = filter_life_value
                    _LOGGER.debug(
                        "Carbon filter life updated for %s: %s%%",
                        device_serial,
                        filter_life_value,
                    )
                else:
                    _LOGGER.warning(
                        "Invalid carbon filter life value for device %s: %s (expected 0-100)",
                        device_serial,
                        filter_life_value,
                    )
                    self._attr_native_value = None
            else:
                self._attr_native_value = None
                _LOGGER.debug(
                    "No carbon filter life data available for device %s", device_serial
                )

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "Carbon filter life data not available for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid carbon filter life data format for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating carbon filter life sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonFilterStatusSensor(DysonEntity, SensorEntity):
    """Filter status sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the filter status sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_filter_status"
        self._attr_translation_key = "filter_status"
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_native_value = None
            return

        # Use our device filter status property
        self._attr_native_value = self.coordinator.device.filter_status
        super()._handle_coordinator_update()


class DysonHEPAFilterTypeSensor(DysonEntity, SensorEntity):
    """HEPA filter type sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the HEPA filter type sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_hepa_filter_type"
        self._attr_translation_key = "hepa_filter_type"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_native_value = None
            return

        # Get HEPA filter type from device data
        device_data = self.coordinator.data.get("product-state", {})
        filter_type = device_data.get("hflt", "NONE")

        # Convert "NONE" to "Not Installed", otherwise return the actual type
        if filter_type == "NONE":
            self._attr_native_value = "Not Installed"
        else:
            self._attr_native_value = filter_type

        _LOGGER.debug(
            "HEPA Filter Type Sensor Update for %s: %s",
            self.coordinator.serial_number,
            self._attr_native_value,
        )
        super()._handle_coordinator_update()


class DysonCarbonFilterTypeSensor(DysonEntity, SensorEntity):
    """Carbon filter type sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the carbon filter type sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_carbon_filter_type"
        self._attr_translation_key = "carbon_filter_type"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        from .device_utils import get_sensor_data_safe

        device_serial = self.coordinator.serial_number

        if not self.coordinator.device:
            self._attr_native_value = None
            _LOGGER.debug(
                "Carbon filter type sensor update: device not available for %s",
                device_serial,
            )
            return

        try:
            # Get carbon filter type from device data with safe access
            device_data = get_sensor_data_safe(
                self.coordinator.data, "product-state", device_serial
            )
            if device_data and isinstance(device_data, dict):
                filter_type = get_sensor_data_safe(device_data, "cflt", device_serial)
            else:
                filter_type = None
                _LOGGER.debug(
                    "No product-state data available for carbon filter type on device %s",
                    device_serial,
                )

            # Handle filter type conversion with validation
            if filter_type is not None:
                # Convert "NONE" or "SCOG" to "Not Installed", otherwise return the actual type
                if str(filter_type).upper() in ["NONE", "SCOG"]:
                    self._attr_native_value = "Not Installed"
                    _LOGGER.debug(
                        "Carbon filter not installed on device %s", device_serial
                    )
                else:
                    # Validate filter type is a reasonable string
                    filter_type_str = str(filter_type).strip()
                    if (
                        filter_type_str and len(filter_type_str) <= 50
                    ):  # Reasonable max length
                        self._attr_native_value = filter_type_str
                        _LOGGER.debug(
                            "Carbon filter type updated for %s: %s",
                            device_serial,
                            filter_type_str,
                        )
                    else:
                        _LOGGER.warning(
                            "Invalid carbon filter type for device %s: %s",
                            device_serial,
                            filter_type,
                        )
                        self._attr_native_value = "Unknown"
            else:
                self._attr_native_value = "Unknown"
                _LOGGER.debug(
                    "No carbon filter type data available for device %s", device_serial
                )

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "Carbon filter type data not available for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = "Unknown"
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid carbon filter type data format for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = "Unknown"
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating carbon filter type sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = "Unknown"

        super()._handle_coordinator_update()


class DysonConnectionStatusSensor(DysonEntity, SensorEntity):
    """Representation of a Dyson connection status sensor."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the connection status sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_connection_status"
        self._attr_translation_key = "connection_status"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:connection"
        self._attr_device_class = None

    @property
    def native_value(self) -> str:
        """Return the connection status."""
        if self.coordinator.device:
            return self.coordinator.device.connection_status
        return "Disconnected"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Connection status is updated directly from the device
        super()._handle_coordinator_update()


class DysonNextCleaningCycleSensor(DysonEntity, SensorEntity):
    """Representation of a Dyson next cleaning cycle sensor for humidifier devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the next cleaning cycle sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_next_cleaning_cycle"
        self._attr_translation_key = "next_cleaning_cycle"
        self._attr_native_unit_of_measurement = UnitOfTime.HOURS
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:timer-outline"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_native_value = None
            super()._handle_coordinator_update()
            return

        device_serial = self.coordinator.serial_number

        try:
            product_state = self.coordinator.data.get("product-state", {})

            # Get clean time remaining (cltr) - 4-digit response in hours
            clean_time_remaining = self.coordinator.device.get_state_value(
                product_state, "cltr", "0000"
            )

            # Convert to integer hours
            if clean_time_remaining and clean_time_remaining != "0000":
                hours_remaining = int(clean_time_remaining)
                self._attr_native_value = hours_remaining
                _LOGGER.debug(
                    "Next cleaning cycle for device %s: %s hours",
                    device_serial,
                    hours_remaining,
                )
            else:
                self._attr_native_value = None
                _LOGGER.debug(
                    "No cleaning cycle data available for device %s", device_serial
                )

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "Next cleaning cycle data not available for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid next cleaning cycle data format for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating next cleaning cycle sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonCleaningTimeRemainingSensor(DysonEntity, SensorEntity):
    """Representation of a Dyson cleaning time remaining sensor for humidifier devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the cleaning time remaining sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_cleaning_time_remaining"
        self._attr_translation_key = "cleaning_time_remaining"
        self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:timer"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_native_value = None
            super()._handle_coordinator_update()
            return

        device_serial = self.coordinator.serial_number

        try:
            product_state = self.coordinator.data.get("product-state", {})

            # Get clean/descale removal remaining (cdrr) - 4-digit response in minutes
            cleaning_time_remaining = self.coordinator.device.get_state_value(
                product_state, "cdrr", "0000"
            )

            # Convert to integer minutes
            if cleaning_time_remaining and cleaning_time_remaining != "0000":
                minutes_remaining = int(cleaning_time_remaining)
                self._attr_native_value = minutes_remaining
                _LOGGER.debug(
                    "Cleaning time remaining for device %s: %s minutes",
                    device_serial,
                    minutes_remaining,
                )
            else:
                self._attr_native_value = None
                _LOGGER.debug(
                    "No cleaning time remaining data available for device %s",
                    device_serial,
                )

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "Cleaning time remaining data not available for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid cleaning time remaining data format for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating cleaning time remaining sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()
