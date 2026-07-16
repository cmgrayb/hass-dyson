"""Sensor platform for Dyson integration.

This module implements comprehensive sensor support for Dyson devices,
providing real-time monitoring of air quality, environmental conditions,
and device status. Sensors are created based on device capabilities
and provide accurate, calibrated data for home automation.

Sensor Categories:

Air Quality Sensors (EnvironmentalData capability):
    - PM2.5: Fine particulate matter concentration (μg/m³)
    - PM10: Coarse particulate matter concentration (μg/m³)

Advanced Air Quality Sensors (ExtendedAQ capability, data-dependent):
    - VOC: Volatile organic compounds index (0-10)
    - NO2: Nitrogen dioxide index (0-10)
    - CO2: Carbon dioxide concentration (ppm)
    - Formaldehyde: HCHO concentration (mg/m³, if supported)

Environmental Sensors (EnvironmentalData capability):
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
from datetime import timedelta
from typing import Any

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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    _PM_SENSOR_UNAVAILABLE_STATES,
    CAPABILITY_EXTENDED_AQ,
    CAPABILITY_FORMALDEHYDE,
    CAPABILITY_VOC,
    DOMAIN,
)
from .coordinator import DysonDataUpdateCoordinator, TTLCache
from .device_utils import mask_serial
from .entity import DysonEntity
from .vacuum import _clean_maps_cache, fetch_clean_maps

_LOGGER = logging.getLogger(__name__)


class DysonP25RSensor(DysonEntity, SensorEntity):
    """PM2.5 air quality sensor for Dyson devices with EnvironmentalData or ExtendedAQ capability.

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
        Created for devices with "EnvironmentalData" or "ExtendedAQ" capability
        that report PM2.5 data (p25r or pm25 keys in environmental data).

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
            Initialized for devices with EnvironmentalData or ExtendedAQ capability
            that report PM2.5 data in environmental-data messages.
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
                # Handle "OFF" when continuous monitoring is disabled or "INIT" when initializing
                if p25r_raw in ("OFF", "INIT"):
                    _LOGGER.debug(
                        "P25R sensor %s for device %s",
                        "inactive" if p25r_raw == "OFF" else "initializing",
                        device_serial,
                    )
                    new_value = None
                else:
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
                _LOGGER.debug(
                    "No P25R data available for device %s", mask_serial(device_serial)
                )

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
    """PM10 air quality sensor for Dyson devices with EnvironmentalData or ExtendedAQ capability.

    This sensor monitors coarse particulate matter (PM10) concentration in
    micrograms per cubic meter. PM10 particles can irritate airways and
    exacerbate respiratory conditions.

    Availability:
        Created for devices with "EnvironmentalData" or "ExtendedAQ" capability
        that report PM10 data (p10r or pm10 keys in environmental data).
    """

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
                # Handle "OFF" when continuous monitoring is disabled or "INIT" when initializing
                if p10r_raw in ("OFF", "INIT"):
                    _LOGGER.debug(
                        "P10R sensor %s for device %s",
                        "inactive" if p10r_raw == "OFF" else "initializing",
                        device_serial,
                    )
                    new_value = None
                else:
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
                _LOGGER.debug(
                    "No P10R data available for device %s", mask_serial(device_serial)
                )

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
                # Handle "OFF" when continuous monitoring is disabled or "INIT" when initializing
                if co2_raw in ("OFF", "INIT"):
                    _LOGGER.debug(
                        "CO2 sensor %s for device %s",
                        "inactive" if co2_raw == "OFF" else "initializing",
                        device_serial,
                    )
                    new_value = None
                else:
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
                _LOGGER.debug(
                    "No CO2 data available for device %s", mask_serial(device_serial)
                )

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
                # Handle "OFF" when continuous monitoring is disabled or "INIT" when initializing
                if hcho_raw in ("OFF", "INIT"):
                    _LOGGER.debug(
                        "VOC sensor %s for device %s",
                        "inactive" if hcho_raw == "OFF" else "initializing",
                        device_serial,
                    )
                    new_value = None
                else:
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
                _LOGGER.debug(
                    "No VOC data available for device %s", mask_serial(device_serial)
                )

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


def _calculate_pollutant_aqi(
    value: float | int, ranges: list[tuple[float | int, float | int, int, int, str]]
) -> tuple[int | None, str | None]:
    """Calculate AQI value and category for a single pollutant.

    Uses linear interpolation within range breakpoints per EPA AQI formula:
    I_p = ((I_Hi - I_Lo) / (BP_Hi - BP_Lo)) * (C_p - BP_Lo) + I_Lo

    Args:
        value: Pollutant concentration value
        ranges: List of (low, high, aqi_low, aqi_high, category) tuples

    Returns:
        Tuple of (aqi_value, category) or (None, None) if value is invalid
    """
    if value is None or value < 0:
        return None, None

    for low, high, aqi_low, aqi_high, category in ranges:
        if low <= value <= high:
            # Linear interpolation between breakpoints
            if high == low:
                # Avoid division by zero for single-value ranges
                calculated_aqi: int = aqi_low
            else:
                calculated_aqi = int(
                    round(
                        ((aqi_high - aqi_low) / (high - low)) * (value - low) + aqi_low
                    )
                )
            return calculated_aqi, category

    # Value exceeds all ranges - return highest category
    if ranges:
        _, _, _, aqi_high, category = ranges[-1]
        return aqi_high, category

    return None, None


def _get_environmental_value(
    env_data: dict[str, Any], keys: list[str]
) -> float | int | None:
    """Get environmental data value using priority key list.

    Args:
        env_data: Environmental data dictionary from device
        keys: List of keys to check in priority order (newest to oldest)

    Returns:
        Value from first matching key, or None if no key found
    """
    for key in keys:
        if key in env_data:
            return env_data[key]
    return None


def _calculate_overall_aqi(
    env_data: dict[str, Any],
) -> tuple[int | None, str | None, list[str]]:
    """Calculate overall AQI as the highest individual pollutant AQI.

    Checks all available pollutants and returns the worst (highest) AQI value.
    Uses Dyson ranges for PM2.5, PM10, VOC, NO2, HCHO and EPA ranges for CO2.

    Args:
        env_data: Environmental data dictionary from device

    Returns:
        Tuple of (overall_aqi, worst_category, dominant_pollutants) or (None, None, []) if no data
        dominant_pollutants is a list of pollutant names at the maximum AQI level
    """
    from .const import (
        AQI_CO2_RANGES,
        AQI_HCHO_RANGES,
        AQI_NO2_RANGES,
        AQI_PM10_RANGES,
        AQI_PM25_RANGES,
        AQI_VOC_RANGES,
        POLLUTANT_KEYS,
    )

    max_aqi = None
    max_category = None
    dominant_pollutants = []

    # Define pollutant configurations: (pollutant_name, display_name, ranges, scale_factor)
    # scale_factor converts device units to range units
    pollutant_configs: list[
        tuple[
            str, str, list[tuple[float | int, float | int, int, int, str]], float | int
        ]
    ] = [
        ("pm25", "PM2.5", AQI_PM25_RANGES, 1),  # μg/m³
        ("pm10", "PM10", AQI_PM10_RANGES, 1),  # μg/m³
        ("voc", "VOC", AQI_VOC_RANGES, 1),  # Use raw device value directly
        ("no2", "NO2", AQI_NO2_RANGES, 1),  # ppb (EPA guidelines)
        ("co2", "CO2", AQI_CO2_RANGES, 1),  # ppm
        ("hcho", "Formaldehyde", AQI_HCHO_RANGES, 0.001),  # Convert mg/m³ to ppm
    ]

    # First pass: calculate all AQI values
    pollutant_aqis = []
    for pollutant_name, display_name, ranges, scale_factor in pollutant_configs:
        # Get value using priority key list
        keys = POLLUTANT_KEYS.get(pollutant_name, [])
        raw_value = _get_environmental_value(env_data, keys)

        if raw_value is not None:
            # Skip "OFF" and "INIT" values - sensors are inactive or initializing
            if raw_value in ("OFF", "INIT"):
                _LOGGER.debug(
                    "%s sensor %s, skipping AQI calculation",
                    display_name,
                    "inactive" if raw_value == "OFF" else "initializing",
                )
                continue

            try:
                # Convert to numeric and apply scale factor
                value = float(raw_value) * scale_factor
                aqi, category = _calculate_pollutant_aqi(value, ranges)

                if aqi is not None:
                    pollutant_aqis.append((display_name, aqi, category))
                    _LOGGER.debug(
                        "Pollutant %s: value=%.3f, AQI=%s, category=%s",
                        pollutant_name,
                        value,
                        aqi,
                        category,
                    )
            except (ValueError, TypeError) as err:
                _LOGGER.debug(
                    "Could not convert %s value %s: %s", pollutant_name, raw_value, err
                )

    # Second pass: find maximum AQI and all pollutants at that level
    if pollutant_aqis:
        max_aqi = max(aqi for _, aqi, _ in pollutant_aqis)
        # Get category from any pollutant at max AQI (they should all have same category)
        max_category = next(cat for _, aqi, cat in pollutant_aqis if aqi == max_aqi)
        # Get all pollutants at max AQI level
        dominant_pollutants = [
            name for name, aqi, _ in pollutant_aqis if aqi == max_aqi
        ]

    return max_aqi, max_category, dominant_pollutants


class DysonAQISensor(DysonEntity, SensorEntity):
    """Numeric AQI sensor for Dyson devices with EnvironmentalData capability.

    This sensor calculates the overall Air Quality Index (AQI) as the highest
    individual pollutant AQI value across all available sensors. The AQI
    provides a standardized measure of air quality from 0 (best) to 500 (worst).

    Attributes:
        device_class: SensorDeviceClass.AQI for proper Home Assistant integration
        state_class: SensorStateClass.MEASUREMENT for long-term statistics
        native_unit_of_measurement: None (AQI is dimensionless)
        icon: mdi:air-filter for visual representation

    AQI Scale:
        - 0-50: Good (green)
        - 51-100: Fair/Moderate (yellow)
        - 101-150: Poor/Unhealthy for Sensitive Groups (orange)
        - 151-200: Very Poor/Unhealthy (red)
        - 201-300: Extremely Poor/Very Unhealthy (purple)
        - 301-500: Severe/Hazardous (maroon)

    Calculation Method:
        Uses Dyson's official PH05 ranges for PM2.5, PM10, VOC, NO2, and HCHO,
        with EPA AirNow ranges for CO2. The overall AQI is the highest value
        across all available pollutants.

    Data Source:
        Real-time measurements from device environmental sensors, checking:
        - PM2.5 (p25r/pm25/pact)
        - PM10 (p10r/pm10)
        - VOC (va10/vact)
        - NO2 (noxl)
        - CO2 (co2r/co2)
        - Formaldehyde (hcho)

    Availability:
        Created for devices with "EnvironmentalData" capability that report
        at least one air quality pollutant.
    """

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the AQI sensor.

        Args:
            coordinator: DysonDataUpdateCoordinator providing device access
        """
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_aqi"
        self._attr_translation_key = "aqi"
        self._attr_device_class = SensorDeviceClass.AQI
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        try:
            # Get environmental data from coordinator
            env_data = (
                self.coordinator.data.get("environmental-data", {})
                if self.coordinator.data
                else {}
            )

            # Calculate overall AQI
            aqi_value, aqi_category, dominant_pollutants = _calculate_overall_aqi(
                env_data
            )

            old_value = self._attr_native_value
            self._attr_native_value = aqi_value

            # Store category and dominant pollutants as extra state attributes
            if aqi_category:
                self._attr_extra_state_attributes = {
                    "category": aqi_category,
                    "dominant_pollutants": dominant_pollutants,
                }
            else:
                self._attr_extra_state_attributes = {}

            if aqi_value is not None:
                _LOGGER.debug(
                    "AQI sensor updated for %s: %s -> %s (%s)",
                    device_serial,
                    old_value,
                    aqi_value,
                    aqi_category,
                )
            else:
                _LOGGER.debug(
                    "No AQI data available for device %s", mask_serial(device_serial)
                )

        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating AQI sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}

        super()._handle_coordinator_update()


class DysonAQICategorySensor(DysonEntity, SensorEntity):
    """Text category AQI sensor for Dyson devices with EnvironmentalData capability.

    This sensor reports the air quality category as text (Good, Fair, Poor, etc.)
    based on the overall AQI calculation. Useful for automations that need
    readable air quality status.

    Attributes:
        device_class: None (text sensor)
        icon: mdi:air-filter for visual representation
        entity_category: None (measurement sensor)

    Categories:
        - Good: Best air quality (AQI 0-50)
        - Fair: Acceptable air quality (AQI 51-100)
        - Poor: Unhealthy for sensitive groups (AQI 101-150)
        - Very Poor: Unhealthy (AQI 151-200)
        - Extremely Poor: Very unhealthy (AQI 201-300)
        - Severe: Hazardous (AQI 301-500)

    Data Source:
        Uses same calculation as DysonAQISensor, reporting the category
        of the worst pollutant detected.

    Availability:
        Created for devices with "EnvironmentalData" capability that report
        at least one air quality pollutant.
    """

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the AQI category sensor.

        Args:
            coordinator: DysonDataUpdateCoordinator providing device access
        """
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_aqi_category"
        self._attr_translation_key = "aqi_category"
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        try:
            # Get environmental data from coordinator
            env_data = (
                self.coordinator.data.get("environmental-data", {})
                if self.coordinator.data
                else {}
            )

            # Calculate overall AQI
            aqi_value, aqi_category, dominant_pollutants = _calculate_overall_aqi(
                env_data
            )

            old_value = self._attr_native_value
            self._attr_native_value = aqi_category

            # Store numeric AQI and dominant pollutants as extra state attributes
            if aqi_value is not None:
                self._attr_extra_state_attributes = {
                    "aqi": aqi_value,
                    "dominant_pollutants": dominant_pollutants,
                }
            else:
                self._attr_extra_state_attributes = {}

            if aqi_category is not None:
                _LOGGER.debug(
                    "AQI category sensor updated for %s: %s -> %s (AQI: %s)",
                    device_serial,
                    old_value,
                    aqi_category,
                    aqi_value,
                )
            else:
                _LOGGER.debug(
                    "No AQI category data available for device %s", device_serial
                )

        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating AQI category sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}

        super()._handle_coordinator_update()


class DysonDominantPollutantSensor(DysonEntity, SensorEntity):
    """Dominant pollutant sensor for Dyson devices with EnvironmentalData capability.

    This sensor reports which pollutant(s) have the worst air quality (highest AQI).
    If multiple pollutants have the same highest AQI value, all are listed.

    Attributes:
        device_class: None (text sensor)
        icon: mdi:molecule for visual representation
        entity_category: None (measurement sensor)

    Output Format:
        - Single pollutant: "PM2.5"
        - Multiple pollutants: "PM2.5, PM10"
        - No data: None

    Tracked Pollutants:
        - PM2.5: Fine particulate matter
        - PM10: Coarse particulate matter
        - VOC: Volatile organic compounds
        - NO2: Nitrogen dioxide
        - CO2: Carbon dioxide
        - Formaldehyde: HCHO

    Use Cases:
        - Identify which pollutant is causing poor air quality
        - Target specific air quality issues with appropriate filters
        - Automation triggers based on specific pollutant problems

    Availability:
        Created for devices with "EnvironmentalData" capability that report
        at least one air quality pollutant.
    """

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the dominant pollutant sensor.

        Args:
            coordinator: DysonDataUpdateCoordinator providing device access
        """
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_dominant_pollutant"
        self._attr_translation_key = "dominant_pollutant"
        self._attr_icon = "mdi:molecule"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        try:
            # Get environmental data from coordinator
            env_data = (
                self.coordinator.data.get("environmental-data", {})
                if self.coordinator.data
                else {}
            )

            # Calculate overall AQI to get dominant pollutants
            aqi_value, aqi_category, dominant_pollutants = _calculate_overall_aqi(
                env_data
            )

            old_value = self._attr_native_value

            # Format dominant pollutants as comma-separated string
            # When AQI is 0, show "None" instead of listing all pollutants
            if dominant_pollutants and aqi_value != 0:
                self._attr_native_value = ", ".join(dominant_pollutants)
            elif aqi_value == 0:
                self._attr_native_value = "None"
            else:
                self._attr_native_value = None

            # Store AQI and category as extra state attributes
            if aqi_value is not None:
                self._attr_extra_state_attributes = {
                    "aqi": aqi_value,
                    "category": aqi_category,
                    "pollutant_count": len(dominant_pollutants),
                }
            else:
                self._attr_extra_state_attributes = {}

            if dominant_pollutants:
                _LOGGER.debug(
                    "Dominant pollutant sensor updated for %s: %s -> %s (AQI: %s, %s)",
                    device_serial,
                    old_value,
                    self._attr_native_value,
                    aqi_value,
                    aqi_category,
                )
            else:
                _LOGGER.debug(
                    "No dominant pollutant data available for device %s", device_serial
                )

        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating dominant pollutant sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}

        super()._handle_coordinator_update()


async def async_setup_entry(  # noqa: C901
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Dyson sensor platform."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[SensorEntity] = []

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

        # Add PM2.5 and PM10 sensors for devices with EnvironmentalData or ExtendedAQ capability
        # PM2.5 and PM10 are available on older devices (e.g., TP02) with EnvironmentalData capability
        # as well as newer devices with ExtendedAQ capability
        # Sensors are only created if the device actually reports the data keys
        has_environmental_aq = has_any_capability_safe(
            capabilities,
            [
                "EnvironmentalData",
                "environmental_data",
                "environmentalData",
                "ExtendedAQ",
                "extended_aq",
                "extendedAQ",
            ],
        )

        if has_environmental_aq:
            _LOGGER.debug(
                "Checking for PM sensors for device %s with environmental/air quality capability",
                device_serial,
            )

            # Pure Cool Link (TP02) models use 'pact' for particulates
            # Newer models use 'p25r'/'pm25' and 'p10r'/'pm10'
            # These are mutually exclusive - prioritize pact for older models
            if "pact" in env_data:
                _LOGGER.debug(
                    "Adding Particulates sensor for device %s - pact data detected (Pure Cool Link)",
                    device_serial,
                )
                entities.append(DysonParticulatesSensor(coordinator))
            else:
                # Only add PM2.5 and PM10 sensors if pact is NOT present
                # Add PM2.5 sensor if PM2.5 data is present (p25r or pm25)
                if "p25r" in env_data or "pm25" in env_data:
                    _LOGGER.debug(
                        "Adding PM2.5 sensor for device %s - PM2.5 data detected",
                        device_serial,
                    )
                    entities.append(DysonPM25Sensor(coordinator))
                else:
                    _LOGGER.debug(
                        "Skipping PM2.5 sensor for device %s - no PM2.5 data in environmental response",
                        device_serial,
                    )

                # Add PM10 sensor if PM10 data is present (p10r or pm10)
                if "p10r" in env_data or "pm10" in env_data:
                    _LOGGER.debug(
                        "Adding PM10 sensor for device %s - PM10 data detected",
                        device_serial,
                    )
                    entities.append(DysonPM10Sensor(coordinator))
                else:
                    _LOGGER.debug(
                        "Skipping PM10 sensor for device %s - no PM10 data in environmental response",
                        device_serial,
                    )

            # Add VOC Link sensor if vact data is present (Pure Cool Link TP02 models)
            # Only add if va10 is not present (va10 takes priority as the newer format)
            if "vact" in env_data and "va10" not in env_data:
                _LOGGER.debug(
                    "Adding VOC Link sensor for device %s - vact data detected (Pure Cool Link)",
                    device_serial,
                )
                entities.append(DysonVOCLinkSensor(coordinator))
            elif "vact" in env_data and "va10" in env_data:
                _LOGGER.debug(
                    "Skipping VOC Link sensor for device %s - va10 (newer format) takes priority over vact",
                    device_serial,
                )
            else:
                _LOGGER.debug(
                    "Skipping VOC Link sensor for device %s - no vact data in environmental response",
                    device_serial,
                )
        else:
            _LOGGER.debug(
                "Skipping PM sensors for device %s - no EnvironmentalData or ExtendedAQ capability",
                device_serial,
            )

        # Add advanced air quality sensors for devices with ExtendedAQ capability
        # ExtendedAQ supports CO2, NO2, VOC, and HCHO (Formaldehyde) metrics
        # Gas sensor key mappings (per cmgrayb/libdyson-neon):
        # - CO2: co2r (not co2)
        # - HCHO (VOC): va10 (not hcho)
        # - NO2: noxl (not no2)
        if has_any_capability_safe(
            capabilities, ["ExtendedAQ", "extended_aq", "extendedAQ"]
        ):
            _LOGGER.debug(
                "Checking for advanced air quality sensors for device %s with ExtendedAQ capability",
                device_serial,
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
                "Skipping advanced air quality sensors for device %s - no ExtendedAQ capability",
                device_serial,
            )

        # Add WiFi-related sensors only for "ec" and "robot" device categories (devices with WiFi connectivity)
        if any(cat in ["ec", "robot"] for cat in device_category):
            _LOGGER.debug(
                "Adding WiFi sensors for device %s", mask_serial(device_serial)
            )
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

        # Add HEPA filter sensors for devices with EnvironmentalData or ExtendedAQ capability
        # These capabilities indicate the device has air filtration with PM monitoring
        if has_any_capability_safe(
            capabilities,
            [
                "EnvironmentalData",
                "environmental_data",
                "environmentalData",
                "ExtendedAQ",
                "extended_aq",
                "extendedAQ",
            ],
        ):
            _LOGGER.debug(
                "Adding HEPA filter sensors for device %s", mask_serial(device_serial)
            )
            entities.extend(
                [
                    DysonHEPAFilterLifeSensor(coordinator),
                    DysonHEPAFilterTypeSensor(coordinator),
                ]
            )
        else:
            _LOGGER.debug(
                "Skipping HEPA filter sensors for device %s - no EnvironmentalData or ExtendedAQ capability",
                device_serial,
            )

        # Add carbon filter sensors based on device state data presence
        # Check if carbon filter data is present in device state (cflt field)
        device_data = (
            coordinator.data.get("product-state", {}) if coordinator.data else {}
        )
        carbon_filter_type = device_data.get("cflt")
        carbon_filter_type_normalized = (
            str(carbon_filter_type).strip().upper()
            if carbon_filter_type is not None
            else None
        )

        # Skip if cflt indicates no separate carbon filter. SCO* values
        # (SCOG/SCOF/SCOH/...) are generational variants Dyson reports on
        # pre-11-series devices with a combination cartridge; 11-series and
        # later use "NONE" for the same thing.
        if (
            carbon_filter_type_normalized is not None
            and carbon_filter_type_normalized != "NONE"
            and not carbon_filter_type_normalized.startswith("SCO")
        ):
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

        # Create temperature sensor if capability is present AND either:
        # (a) env_data has the 'tact' key (regardless of value - 'OFF' is valid when device is off), or
        # (b) env_data is empty because coordinator data hasn't arrived yet at setup time
        env_data_available = coordinator.data is not None and bool(env_data)
        if has_temp_capability and ("tact" in env_data or not env_data_available):
            _LOGGER.debug(
                "Adding temperature sensor for device %s - %s",
                device_serial,
                "tact key present"
                if "tact" in env_data
                else "capability present, no env data yet at setup time",
            )
            entities.append(DysonTemperatureSensor(coordinator))
        elif has_temp_capability:
            _LOGGER.debug(
                "Skipping temperature sensor for device %s - capability present but tact key absent from environmental data",
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

        # Create humidity sensor if capability is present AND either:
        # (a) env_data has the 'hact' key (regardless of value - 'OFF' is valid when device is off), or
        # (b) env_data is empty because coordinator data hasn't arrived yet at setup time
        if has_humidity_capability and ("hact" in env_data or not env_data_available):
            _LOGGER.debug(
                "Adding humidity sensor for device %s - %s",
                device_serial,
                "hact key present"
                if "hact" in env_data
                else "capability present, no env data yet at setup time",
            )
            entities.append(DysonHumiditySensor(coordinator))
        elif has_humidity_capability:
            _LOGGER.debug(
                "Skipping humidity sensor for device %s - capability present but hact key absent from environmental data",
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

        # Add AQI (Air Quality Index) sensors for devices with EnvironmentalData capability
        # AQI sensors provide overall air quality assessment based on all available pollutants
        if has_environmental_aq:
            _LOGGER.debug(
                "Adding AQI sensors for device %s - EnvironmentalData capability detected",
                device_serial,
            )
            # Add numeric AQI, text category, and dominant pollutant sensors
            entities.extend(
                [
                    DysonAQISensor(coordinator),
                    DysonAQICategorySensor(coordinator),
                    DysonDominantPollutantSensor(coordinator),
                ]
            )
        else:
            _LOGGER.debug(
                "Skipping AQI sensors for device %s - no EnvironmentalData capability",
                device_serial,
            )

        # Add battery sensor for devices with robot category
        # Battery sensor replaces the deprecated battery_level property and
        # VacuumEntityFeature.BATTERY on the vacuum entity (deprecated in HA 2026.8)
        if any(cat in ["robot"] for cat in device_category):
            _LOGGER.debug(
                "Adding battery sensor for robot device %s",
                device_serial,
            )
            entities.append(DysonRobotBatterySensor(coordinator))
            # Cloud-fetched cleaning history + Dyson's recommended-next-room
            # sensor. Both gated on cloud auth.
            if coordinator.config_entry.data.get("auth_token"):
                for i in range(5):
                    entities.append(DysonLastCleanSensor(coordinator, slot=i))
                entities.append(DysonRecommendedCleanSensor(coordinator))
                entities.append(DysonCurrentMapSensor(coordinator))

        # Cloud-fetched purifier sensors (outdoor AQI, daily history,
        # MyDyson scheduled events). Only for ec-category devices (air
        # purifiers / heaters / fans with environmental sensing) that have
        # a usable cloud auth token.
        if any(
            cat == "ec" for cat in device_category
        ) and coordinator.config_entry.data.get("auth_token"):
            entities.append(DysonOutdoorAQISensor(coordinator))
            entities.append(DysonDailyAirQualitySensor(coordinator))
            entities.append(DysonScheduledEventsSensor(coordinator))

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
                # Handle Dyson's non-numeric PM sensor states without warning.
                if pm25_raw in _PM_SENSOR_UNAVAILABLE_STATES:
                    _LOGGER.debug(
                        "PM2.5 sensor %s for device %s",
                        _PM_SENSOR_UNAVAILABLE_STATES[pm25_raw],
                        device_serial,
                    )
                    new_value = None
                else:
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
                _LOGGER.debug(
                    "No PM2.5 data available for device %s", mask_serial(device_serial)
                )

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
                # Handle Dyson's non-numeric PM sensor states without warning.
                if pm10_raw in _PM_SENSOR_UNAVAILABLE_STATES:
                    _LOGGER.debug(
                        "PM10 sensor %s for device %s",
                        _PM_SENSOR_UNAVAILABLE_STATES[pm10_raw],
                        device_serial,
                    )
                    new_value = None
                else:
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
                _LOGGER.debug(
                    "No PM10 data available for device %s", mask_serial(device_serial)
                )

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


class DysonParticulatesSensor(DysonEntity, SensorEntity):
    """Particulates sensor for Dyson Pure Cool Link devices (TP02).

    This sensor monitors particulate matter using the 'pact' key from older
    Pure Cool Link models. Unlike PM2.5/PM10 sensors that report specific
    particle size ranges, this reports general particulate levels in an
    unknown unit specific to Pure Cool Link devices.

    Key Differences from PM2.5:
        - Uses 'pact' key instead of 'p25r'/'pm25'
        - Only present on Pure Cool Link models (device type 475)
        - Unit is micrograms per cubic meter for consistency
        - Different measurement methodology than PM2.5

    Attributes:
        device_class: SensorDeviceClass.PM25 (closest match for particulates)
        state_class: SensorStateClass.MEASUREMENT for statistics
        unit_of_measurement: μg/m³ (micrograms per cubic meter)
        icon: mdi:air-filter for visual representation

    Data Source:
        Environmental sensor data from device MQTT 'pact' key
    """

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the Particulates sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_pact"
        self._attr_translation_key = "pact"
        self._attr_device_class = SensorDeviceClass.PM25
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
        self._attr_icon = "mdi:air-filter"

        _LOGGER.debug(
            "Initialized Particulates sensor for %s with initial value: %s",
            coordinator.serial_number,
            self._attr_native_value,
        )

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
            pact_raw = env_data.get("pact")

            if pact_raw is not None:
                # Handle "OFF" when continuous monitoring is disabled or "INIT" when initializing
                if pact_raw in ("OFF", "INIT"):
                    _LOGGER.debug(
                        "Particulates sensor %s for device %s",
                        "inactive" if pact_raw == "OFF" else "initializing",
                        device_serial,
                    )
                    new_value = None
                else:
                    try:
                        # Convert and validate the particulates value
                        new_value = int(pact_raw)
                        if not (0 <= new_value <= 9999):
                            _LOGGER.warning(
                                "Invalid particulates value for device %s: %s (expected 0-9999)",
                                device_serial,
                                new_value,
                            )
                            new_value = None
                    except (ValueError, TypeError):
                        _LOGGER.warning(
                            "Invalid particulates value format for device %s: %s",
                            device_serial,
                            pact_raw,
                        )
                        new_value = None

            self._attr_native_value = new_value

            if new_value is not None:
                _LOGGER.debug(
                    "Particulates sensor updated for %s: %s -> %s",
                    device_serial,
                    old_value,
                    new_value,
                )
            else:
                _LOGGER.debug(
                    "No particulates data available for device %s", device_serial
                )

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "Particulates data not available for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid particulates data format for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating particulates sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonVOCLinkSensor(DysonEntity, SensorEntity):
    """VOC sensor for Dyson Pure Cool Link devices (TP02).

    This sensor monitors volatile organic compounds using the 'vact' key from
    older Pure Cool Link models. Unlike the newer 'va10' sensor that reports
    VOC index values, this reports raw VOC levels.

    Key Differences from va10 VOC:
        - Uses 'vact' key instead of 'va10'
        - Only present on Pure Cool Link models (device type 475)
        - Reports raw values without division by 10
        - Different measurement methodology than newer models

    Attributes:
        device_class: SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
        state_class: SensorStateClass.MEASUREMENT for statistics
        unit_of_measurement: mg/m³ (milligrams per cubic meter)
        icon: mdi:air-filter for visual representation

    Data Source:
        Environmental sensor data from device MQTT 'vact' key
    """

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the VOC Link sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_vact"
        self._attr_translation_key = "voc"
        self._attr_device_class = SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER
        self._attr_icon = "mdi:air-filter"

        _LOGGER.debug(
            "Initialized VOC Link sensor for %s with initial value: %s",
            coordinator.serial_number,
            self._attr_native_value,
        )

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
            vact_raw = env_data.get("vact")

            if vact_raw is not None:
                # Handle "OFF" when continuous monitoring is disabled or "INIT" when initializing
                if vact_raw in ("OFF", "INIT"):
                    _LOGGER.debug(
                        "VOC Link sensor %s for device %s",
                        "inactive" if vact_raw == "OFF" else "initializing",
                        device_serial,
                    )
                    new_value = None
                else:
                    try:
                        # Convert and validate the VOC value
                        raw_value = int(vact_raw)
                        if not (0 <= raw_value <= 9999):
                            _LOGGER.warning(
                                "Invalid VOC Link value for device %s: %s (expected 0-9999)",
                                device_serial,
                                raw_value,
                            )
                            new_value = None
                        else:
                            # Convert from raw value to mg/m³ (same conversion as va10)
                            # Range 0-9999 raw becomes 0.000-9.999 mg/m³
                            new_value = round(raw_value / 1000.0, 3)
                            _LOGGER.debug(
                                "VOC Link conversion for %s: %d raw -> %.3f mg/m³",
                                device_serial,
                                raw_value,
                                new_value,
                            )
                    except (ValueError, TypeError):
                        _LOGGER.warning(
                            "Invalid VOC Link value format for device %s: %s",
                            device_serial,
                            vact_raw,
                        )
                        new_value = None

            self._attr_native_value = new_value

            if new_value is not None:
                _LOGGER.debug(
                    "VOC Link sensor updated for %s: %s -> %s",
                    device_serial,
                    old_value,
                    new_value,
                )
            else:
                _LOGGER.debug(
                    "No VOC Link data available for device %s",
                    mask_serial(device_serial),
                )

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "VOC Link data not available for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid VOC Link data format for device %s: %s", device_serial, err
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating VOC Link sensor for device %s: %s",
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
                # Handle "OFF" when continuous monitoring is disabled or "INIT" when initializing
                if no2_raw in ("OFF", "INIT"):
                    _LOGGER.debug(
                        "NO2 sensor %s for device %s",
                        "inactive" if no2_raw == "OFF" else "initializing",
                        device_serial,
                    )
                    new_value = None
                else:
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
                _LOGGER.debug(
                    "No NO2 data available for device %s", mask_serial(device_serial)
                )

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
            if hchr_raw and hchr_raw not in ("NONE", "OFF", "INIT"):
                hcho_raw = hchr_raw
            elif hcho_raw and hcho_raw not in ("NONE", "OFF", "INIT"):
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
                _LOGGER.debug(
                    "No HCHO data available for device %s", mask_serial(device_serial)
                )

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
                # Convert "NONE" or any SCO* variant to "Not Installed",
                # otherwise return the actual type. SCO* values (SCOG/SCOF/
                # SCOH/...) are generational variants Dyson reports on pre-11
                # series devices with a combination cartridge.
                filter_type_normalized = str(filter_type).strip().upper()
                if (
                    filter_type_normalized == "NONE"
                    or filter_type_normalized.startswith("SCO")
                ):
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
        self._attr_icon = "mdi:calendar-filter"

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
        self._attr_icon = "mdi:wrench-clock"

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


class DysonRobotBatterySensor(DysonEntity, SensorEntity):
    """Battery sensor for Dyson robot vacuum devices.

    This sensor provides battery level monitoring for Dyson robot vacuum cleaners,
    replacing the deprecated battery_level property on the vacuum entity.

    Attributes:
        device_class: SensorDeviceClass.BATTERY for proper Home Assistant integration
        state_class: SensorStateClass.MEASUREMENT for long-term statistics
        unit_of_measurement: PERCENTAGE (0-100%)
        entity_category: EntityCategory.DIAGNOSTIC for diagnostic information
        icon: mdi:battery for visual representation

    Data Source:
        Battery level from robot vacuum device state (batteryChargeLevel field),
        updated automatically via MQTT as battery state changes.

    Availability:
        Only created for devices with "robot" device category (Dyson 360 Eye,
        360 Heurist, 360 Vis Nav models).

    Migration:
        This sensor replaces the deprecated battery_level property and
        VacuumEntityFeature.BATTERY feature flag on the vacuum entity,
        which will be removed in Home Assistant 2026.8.

    Example:
        Typical sensor values and automation:

        >>> # Battery at 85%
        >>> sensor.native_value = 85
        >>>
        >>> # Low battery - send notification
        >>> if sensor.native_value < 20:
        >>>     await notify.async_send_message("Robot vacuum battery low")

    Note:
        Battery percentage is reported directly from the robot device without
        additional processing or calibration.
    """

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the robot battery sensor.

        Args:
            coordinator: DysonDataUpdateCoordinator providing device access

        Configuration:
        - unique_id: {serial_number}_robot_battery for entity registry
        - translation_key: "robot_battery" for localized naming
        - device_class: BATTERY for proper sensor categorization
        - state_class: MEASUREMENT for long-term statistics
        - unit: PERCENTAGE for battery level display
        - entity_category: DIAGNOSTIC for diagnostic information
        - icon: battery for visual representation

        Integration Features:
        - Automatic device registry linking via parent DysonEntity
        - Long-term statistics support for trend analysis
        - Proper sensor categorization in Home Assistant UI
        - Localized entity naming through translation system

        Note:
            Only initialized for devices with "robot" device category.
        """
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_robot_battery"
        self._attr_translation_key = "robot_battery"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:battery"

        _LOGGER.debug(
            "Initialized robot battery sensor for %s",
            coordinator.serial_number,
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_native_value = None
            super()._handle_coordinator_update()
            return

        device_serial = self.coordinator.serial_number

        try:
            old_value = self._attr_native_value
            new_value = self.coordinator.device.robot_battery_level

            self._attr_native_value = new_value

            if new_value is not None:
                _LOGGER.debug(
                    "Robot battery sensor updated for %s: %s -> %s%%",
                    device_serial,
                    old_value,
                    new_value,
                )
            else:
                _LOGGER.debug(
                    "Robot battery sensor update: no battery data for device %s",
                    device_serial,
                )

        except (KeyError, AttributeError) as err:
            _LOGGER.debug(
                "Robot battery data not available for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid robot battery data format for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error(
                "Unexpected error updating robot battery sensor for device %s: %s",
                device_serial,
                err,
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()


# ============================================================================
# Cleaning history sensor (Vis Nav)
# ============================================================================
# Pulls the last N cleaning runs from /{apiVer}/{serial}/clean-maps?dustMap=total and
# exposes one sensor per slot (state = clean timestamp, attrs = area/duration/zones).
# Uses HA's built-in polling (should_poll=True, scan_interval=30min) — independent
# of the MQTT coordinator since this is REST cloud data.

# Note: the clean-maps endpoint is fetched via the shared `fetch_clean_maps`
# in _cloud.py so this module and image.py share one cache (the dust-map
# image consumes the same blob seconds after we do).


def _extract_start_time(clean) -> str | None:
    """Pull the start timestamp from a CleanRecord (v1 or v2 schema).

    v2: ``start_time_epoch`` is a Unix timestamp (int) — converted to ISO-8601.
    v1: earliest timestamp from the ``timeline`` event list.
    """
    epoch = getattr(clean, "start_time_epoch", None)
    if epoch is not None:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
    times = [e.time for e in (getattr(clean, "timeline", None) or []) if e.time]
    return min(times) if times else None


def _extract_end_time(clean) -> str | None:
    """Pull the end timestamp from a CleanRecord (v1 or v2 schema)."""
    epoch = getattr(clean, "end_time_epoch", None)
    if epoch is not None:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
    times = [e.time for e in (getattr(clean, "timeline", None) or []) if e.time]
    return max(times) if times else None


def _extract_duration_minutes(clean) -> int | None:
    """Return clean duration in minutes (v1 or v2 schema).

    v2: ``clean_duration`` is provided directly in minutes.
    v1: computed from the difference between start and end timeline events.
    """
    # v2 direct field
    duration = getattr(clean, "clean_duration", None)
    if duration is not None:
        return int(duration)
    # v1 fallback: compute from ISO timeline timestamps
    from datetime import datetime

    start, end = _extract_start_time(clean), _extract_end_time(clean)
    if not start or not end:
        return None
    try:
        s = datetime.fromisoformat(start.replace("Z", "+00:00"))
        e = datetime.fromisoformat(end.replace("Z", "+00:00"))
        return max(0, int((e - s).total_seconds() // 60))
    except (ValueError, TypeError):
        return None


def _extract_cleaned_area_m2(clean) -> float | None:
    """Return cleaned area in m² (v1 or v2 schema).

    v2: ``area_cleaned`` is provided directly in m².
    v1: computed from ``CleanedFootprint.compute_area_m2()``.
    """
    # v2 direct field
    area = getattr(clean, "area_cleaned", None)
    if area is not None:
        return round(float(area), 2)
    # v1 fallback: compute from cleaned_footprint
    if getattr(clean, "cleaned_footprint", None) is None:
        return None
    resolution_mm = (
        clean.dust_map.resolution if getattr(clean, "dust_map", None) else 20
    )
    return clean.cleaned_footprint.compute_area_m2(tile_resolution_mm=resolution_mm)


def _extract_zone_ids(clean) -> list[str]:
    """Return the zone IDs targeted by this CleanRecord (v1 or v2 schema).

    v2: ``zones`` list of ``CleanZone`` objects; selected zones only.
    v1: derived from ``cleaning_programme`` ordered/unordered zone IDs.
    Whole-house ("global") cleans may return all zone IDs or an empty list.
    """
    # v2: zones list with is_selected flag
    zones = getattr(clean, "zones", None)
    if zones:
        return [z.id for z in zones if z.is_selected]
    # v1 fallback
    prog = getattr(clean, "cleaning_programme", None)
    if not prog:
        return []
    return list(prog.unordered_zones) + list(prog.ordered_zones)


def _extract_clean_type(clean) -> str:
    """Return a clean-type string (v1 or v2 schema).

    v2: derived from ``is_spot_clean`` bool ("spot" or "global").
    v1: ``clean_type`` string from the CleanRecord.
    """
    is_spot = getattr(clean, "is_spot_clean", None)
    if is_spot is not None:
        return "spot" if is_spot else "global"
    return getattr(clean, "clean_type", "unknown")


def _extract_fault_count(clean) -> int:
    """Return the number of fault events (v1 or v2 schema).

    v2: length of the ``faults`` list.
    v1: count of timeline events carrying a fault location or name.
    """
    faults = getattr(clean, "faults", None)
    if faults is not None:
        return len(faults)
    return sum(
        1
        for e in (getattr(clean, "timeline", None) or [])
        if e.fault_location is not None or "fault" in (e.event_name or "").lower()
    )


class DysonLastCleanSensor(DysonEntity, SensorEntity):
    """Sensor for one of the last N cleans (slot 0 = most recent).

    State: ISO timestamp of the clean's start. Attributes carry the full summary.
    Polled every 30 minutes; cache shared across all 5 slot sensors.
    """

    coordinator: DysonDataUpdateCoordinator
    _attr_should_poll = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: DysonDataUpdateCoordinator, slot: int) -> None:
        super().__init__(coordinator)
        self._slot = slot
        suffix = "" if slot == 0 else f"_{slot + 1}"
        self._attr_unique_id = f"{coordinator.serial_number}_last_clean{suffix}"
        label = "Last Clean" if slot == 0 else f"Last Clean #{slot + 1}"
        self._attr_name = label
        self._attr_icon = "mdi:vacuum"

    @property
    def should_poll(self) -> bool:
        return True

    async def async_update(self) -> None:
        from datetime import datetime

        cleans = await fetch_clean_maps(self.coordinator)
        if len(cleans) <= self._slot:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return
        clean = cleans[self._slot]

        start_str = _extract_start_time(clean)
        try:
            self._attr_native_value = (
                datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                if start_str
                else None
            )
        except (ValueError, AttributeError):
            self._attr_native_value = None

        # Cross-reference zone IDs with the persistent-map metadata cache
        # (populated by services.py) to resolve human-readable room names.
        zone_ids = _extract_zone_ids(clean)
        zone_names: list[str] = []
        if zone_ids:
            try:
                from .services import _persistent_map_cache

                maps = _persistent_map_cache.get(self.coordinator.serial_number)
                if maps is None:
                    maps = _persistent_map_cache.get_stale(
                        self.coordinator.serial_number
                    )
                if maps:
                    # Zone ids restart from 1 on every map — resolve names
                    # from the map the clean ran on, falling back to the
                    # other maps only for ids it does not carry.
                    clean_map_id = getattr(clean, "persistent_map_id", None)
                    id_to_name: dict[str, str] = {}
                    for pmap in sorted(maps, key=lambda m: m.id != clean_map_id):
                        for z in pmap.zones:
                            id_to_name.setdefault(z.id, z.name or z.id)
                    zone_names = [id_to_name.get(zid, zid) for zid in zone_ids]
            except Exception:  # noqa: BLE001 — names are a nice-to-have
                zone_names = []

        self._attr_extra_state_attributes = {
            "clean_id": clean.clean_id,
            "clean_type": _extract_clean_type(clean),
            "duration_minutes": _extract_duration_minutes(clean),
            "area_m2": _extract_cleaned_area_m2(clean),
            "zone_ids": zone_ids,
            "zone_names": zone_names,
            "fault_count": _extract_fault_count(clean),
            "sequence_number": getattr(clean, "sequence_number", None),
            # v2 fields (None on v1 records)
            "start_battery": getattr(clean, "start_battery", None),
            "end_battery": getattr(clean, "end_battery", None),
            "is_spot_clean": getattr(clean, "is_spot_clean", None),
        }


# ============================================================================
# Cleaning recommendations sensor (Vis Nav)
# ============================================================================
# /v1/app/{serial}/recommended-cleans returns Dyson's suggestion of which
# zones to clean next based on how long since each was last visited.

_recommended_cleans_cache = TTLCache(30 * 60)


async def _fetch_recommended_cleans(coordinator: DysonDataUpdateCoordinator) -> list:
    """Fetch recommended zone cleans via libdyson-rest (cached 30 min).

    Returns a list of ``RecommendedCleanMap`` objects (or stale cache / [] on
    failure).
    """
    from libdyson_rest.exceptions import DysonAPIError, DysonAuthError

    serial = coordinator.serial_number
    fresh = _recommended_cleans_cache.get(serial)
    if fresh is not None:
        return fresh

    async with coordinator.async_cloud_client() as client:
        if client is None:
            return _recommended_cleans_cache.get_stale(serial) or []
        try:
            records = await client.get_recommended_cleans(serial)
        except (DysonAPIError, DysonAuthError) as err:
            _LOGGER.debug("Failed to fetch recommended cleans for %s: %s", serial, err)
            return _recommended_cleans_cache.get_stale(serial) or []

    _recommended_cleans_cache.set(serial, records)
    return records


class DysonRecommendedCleanSensor(DysonEntity, SensorEntity):
    """Dyson's recommendation for the next zone to clean (Vis Nav).

    State: human-readable name of the top recommended zone (or 'None').
    Attributes: full list of {zone_id, zone_name, days_since_last_visit, priority}.
    """

    coordinator: DysonDataUpdateCoordinator
    _attr_should_poll = True
    _attr_icon = "mdi:lightbulb-on-outline"

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_recommended_clean"
        self._attr_name = "Recommended Clean"

    async def async_update(self) -> None:
        data = await _fetch_recommended_cleans(self.coordinator)
        # Cross-reference zone IDs with cached persistent-map names. Use the
        # stale-cache fallback so we still get friendly names even if the
        # main metadata TTL has expired since the last fetch.
        id_to_name: dict[str, str] = {}
        names_by_map: dict[str, dict[str, str]] = {}
        try:
            from .services import _persistent_map_cache

            maps = _persistent_map_cache.get(self.coordinator.serial_number)
            if maps is None:
                maps = _persistent_map_cache.get_stale(self.coordinator.serial_number)
            if maps:
                for pmap in maps:
                    per_map = {z.id: (z.name or z.id) for z in pmap.zones}
                    names_by_map[pmap.id] = per_map
                    for zid, zname in per_map.items():
                        id_to_name.setdefault(zid, zname)
        except Exception:  # noqa: BLE001
            pass

        # data is a list of RecommendedCleanMap objects from libdyson-rest.
        # Each has .zone_predictions (list[ZonePrediction]) with .dust.total etc.
        predictions: list[dict] = []
        for rcm in data:
            # Zone ids restart from 1 per map — resolve against this
            # recommendation's own map when it is in the cache.
            rcm_names = names_by_map.get(
                getattr(rcm, "persistent_map_id", None), id_to_name
            )
            for pred in rcm.zone_predictions:
                zid = pred.zone_id
                dust_breakdown = {
                    "extra_fine": round(pred.dust.extra_fine, 1),
                    "fine": round(pred.dust.fine, 1),
                    "medium": round(pred.dust.medium, 1),
                    "large": round(pred.dust.large, 1),
                    "other": round(pred.dust.other, 1),
                    "total": round(pred.dust.total, 1),
                }
                predictions.append(
                    {
                        "zone_id": zid,
                        "zone_name": rcm_names.get(zid, id_to_name.get(zid, zid)),
                        "total_dust_mg": round(pred.dust.total, 1),
                        "dust_breakdown_mg": dust_breakdown,
                    }
                )
        # Sort by total dust descending (dirtiest first)
        predictions.sort(key=lambda p: p["total_dust_mg"], reverse=True)

        if predictions and predictions[0]["total_dust_mg"] > 0:
            self._attr_native_value = predictions[0]["zone_name"]
        else:
            self._attr_native_value = "None"
        self._attr_extra_state_attributes = {
            "top_zone_dust_mg": (predictions[0]["total_dust_mg"] if predictions else 0),
            "predictions": predictions,
        }


class DysonCurrentMapSensor(DysonEntity, RestoreEntity, SensorEntity):
    """Which persistent map a multi-map robot is currently using.

    Source priority (exposed via the ``source`` attribute):
      1. ``robot`` — the persistentMapId the robot itself announced over
         MQTT (present in every clean's state stream, retained afterwards);
      2. ``cloud`` — the isCurrentMap flag from persistent-map metadata
         (set by v2/Spot+Clean devices; the Vis Nav v1 endpoint omits it);
      3. ``restored`` — the last known value from before a restart;
      4. ``last_visited`` — the map with the newest lastVisited timestamp
         in the persistent-map metadata (v1 payloads include it);
      5. ``clean_history`` — the map of the most recent cloud clean record.

    During zone cleans the robot also streams per-zone progress, surfaced
    as the ``zone_status`` attribute.
    """

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_current_map"
        self._attr_name = "Current Map"
        self._attr_icon = "mdi:map-marker-path"
        self._restored_map_id: str | None = None
        self._restored_name: str | None = None

    @property
    def should_poll(self) -> bool:
        # _attr_should_poll is inert on CoordinatorEntity subclasses (#408);
        # the explicit override keeps the cache-warming async_update polling.
        return True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state not in ("unknown", "unavailable"):
            self._restored_name = last.state
            self._restored_map_id = last.attributes.get("map_id")

    async def async_update(self) -> None:
        """Warm the metadata and clean-history caches (both TTL-cached)."""
        from .services import _fetch_persistent_map_metadata

        try:
            await _fetch_persistent_map_metadata(self.coordinator)
        except HomeAssistantError:
            pass
        try:
            await fetch_clean_maps(self.coordinator)
        except HomeAssistantError:
            pass

    def _cached_maps(self) -> list:
        from .services import _persistent_map_cache

        serial = self.coordinator.serial_number
        maps = _persistent_map_cache.get(serial)
        if maps is None:
            maps = _persistent_map_cache.get_stale(serial)
        return maps or []

    def _resolve(self) -> tuple[str | None, str | None, str | None]:
        """Return (map_id, map_name, source) from the best available signal."""
        from .services import _current_map

        maps = self._cached_maps()
        by_id = {m.id: m for m in maps}

        device = self.coordinator.device
        map_id = getattr(device, "robot_current_map_id", None) if device else None
        if map_id:
            pmap = by_id.get(map_id)
            return map_id, (pmap.name if pmap else None), "robot"

        cloud = _current_map(maps)
        if cloud is not None:
            return cloud.id, cloud.name, "cloud"

        if self._restored_map_id or self._restored_name:
            pmap = by_id.get(self._restored_map_id or "")
            name = pmap.name if pmap else self._restored_name
            return self._restored_map_id, name, "restored"

        # Restricted to maps that carry lastVisited so find_current_map
        # cannot raise; with no cloud flag set (the v1 norm) it returns
        # the newest-visited map.
        visited = [m for m in maps if m.last_visited]
        if visited:
            from libdyson_rest.models import find_current_map

            pmap = find_current_map(visited)
            return pmap.id, pmap.name, "last_visited"

        serial = self.coordinator.serial_number
        records = _clean_maps_cache.get(serial) or _clean_maps_cache.get_stale(serial)
        for record in records or []:
            record_map_id = getattr(record, "persistent_map_id", None)
            if record_map_id:
                pmap = by_id.get(record_map_id)
                return record_map_id, (pmap.name if pmap else None), "clean_history"

        return None, None, None

    @property
    def native_value(self) -> str | None:
        map_id, name, _source = self._resolve()
        if name is None and map_id is None:
            return None
        return str(name or map_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        from .services import _ACTIVE_ROBOT_STATE_PREFIXES

        map_id, _name, source = self._resolve()
        attrs: dict[str, Any] = {"map_id": map_id, "source": source}

        pmap = next((m for m in self._cached_maps() if m.id == map_id), None)
        if pmap is not None:
            attrs["zones"] = [str(z.name or z.id) for z in pmap.zones]

        # Per-zone progress is only meaningful while a clean is running —
        # the robot retains the last zoneStatus after docking.
        device = self.coordinator.device
        zone_status = getattr(device, "robot_zone_status", None) if device else None
        robot_state = str(getattr(device, "robot_state", "") or "")
        if zone_status and robot_state.startswith(_ACTIVE_ROBOT_STATE_PREFIXES):
            names = {z.id: str(z.name or z.id) for z in pmap.zones} if pmap else {}
            attrs["zone_status"] = {
                names.get(entry.get("zoneId"), entry.get("zoneId")): entry.get(
                    "cleanStatus"
                )
                for entry in zone_status
                if isinstance(entry, dict)
            }
        return attrs


# ============================================================================
# Cloud-fetched purifier sensors (Master Bedroom Purifier, Guest Room, etc.)
# ============================================================================
# Three new sensors driven by REST endpoints discovered via mitmproxy capture
# of the MyDyson iOS app:
#   - DysonOutdoorAQISensor:        /v1/environment/devices/{serial}/data
#   - DysonDailyAirQualitySensor:   /v1/messageprocessor/devices/{serial}/environmentdata/daily
#   - DysonScheduledEventsSensor:   /v1/unifiedscheduler/{serial}/events
#
# Each sensor manages its own in-process cache (TTLs tuned for the underlying
# data volatility) so multiple polls don't hammer the Dyson cloud.

# TTLs tuned per data volatility — outdoor AQI refreshes every ~15min,
# the daily series and per-device schedules barely change.
_outdoor_aqi_cache = TTLCache(15 * 60)
_daily_env_cache = TTLCache(60 * 60)
_schedule_cache = TTLCache(5 * 60)  # 5-min TTL so schedule changes surface quickly


def _device_product_type(coordinator: DysonDataUpdateCoordinator) -> str | None:
    """Return the device's productType code (e.g. '438K') for query params.

    Priority: config-entry product_type → device-registry model → None.
    cmgrayb's manifest extractor often stores 'unknown'; the device registry
    'model' field carries the real code in that case.
    """
    pt = coordinator.config_entry.data.get("product_type")
    if pt and str(pt).lower() != "unknown":
        return str(pt)
    # Fall back to the device-registry model. coordinator doesn't expose this
    # directly; query the registry through hass if available.
    try:
        from homeassistant.helpers import device_registry as dr

        dev_reg = dr.async_get(coordinator.hass)
        for d in dev_reg.devices.values():
            if any(
                idn[0] == DOMAIN and idn[1] == coordinator.serial_number
                for idn in d.identifiers
            ):
                if d.model and str(d.model).lower() not in ("unknown", ""):
                    return d.model
    except Exception:  # noqa: BLE001
        pass
    return None


class DysonOutdoorAQISensor(DysonEntity, SensorEntity):
    """Outdoor air-quality at the device's registered location.

    Source: ``AsyncDysonClient.get_outdoor_environment_data()`` (libdyson-rest).
    Returns Dyson's third-party outdoor AQI feed for the device's location.
    State = AQI value (1-500 scale); attributes carry PM2.5/PM10/NO2/weather.
    """

    coordinator: DysonDataUpdateCoordinator
    _attr_icon = "mdi:weather-windy"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.AQI
    _UPDATE_INTERVAL = timedelta(minutes=15)

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_outdoor_aqi"
        self._attr_name = "Outdoor AQI"

    async def async_added_to_hass(self) -> None:
        """Register periodic cloud refresh when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._async_scheduled_update,
                self._UPDATE_INTERVAL,
            )
        )

    async def _async_scheduled_update(self, now: object = None) -> None:
        """Fetch fresh outdoor AQI data and push state to Home Assistant."""
        _outdoor_aqi_cache.expire(self.coordinator.serial_number)
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        from libdyson_rest.exceptions import DysonAPIError, DysonAuthError

        serial = self.coordinator.serial_number
        data = _outdoor_aqi_cache.get(serial)
        if data is None:
            async with self.coordinator.async_cloud_client() as client:
                if client is not None:
                    try:
                        data = await client.get_outdoor_environment_data(serial)
                        _outdoor_aqi_cache.set(serial, data)
                    except (DysonAPIError, DysonAuthError) as err:
                        _LOGGER.debug(
                            "Failed to fetch outdoor AQI for %s: %s", serial, err
                        )
                        data = _outdoor_aqi_cache.get_stale(serial)

        if not data:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return

        self._attr_native_value = data.aqi_value
        self._attr_extra_state_attributes = {
            "aqi_name": data.aqi_name,
            "aqi_description": data.aqi_description,
            "pm2_5": data.pm25_value,
            "pm10": data.pm10_value,
            "no2": data.no2_value,
            "humidity": data.humidity,
            "temperature": data.temperature,
            "weather_state": data.weather_state,
            "location": data.location_name,
            "dominant_pollen": data.dominant_pollen,
            "as_of": data.date_time,
        }


class DysonDailyAirQualitySensor(DysonEntity, SensorEntity):
    """Indoor air-quality series from the device, 15-min resolution.

    Source: GET /v1/messageprocessor/devices/{serial}/environmentdata/daily
    State = the most recent 15-min AQI sample (effectively "now"). Attributes
    carry the full series + resolution so dashboards can chart history.
    """

    coordinator: DysonDataUpdateCoordinator
    _attr_icon = "mdi:chart-line"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _UPDATE_INTERVAL = timedelta(minutes=60)

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_daily_aqi"
        self._attr_name = "Indoor AQI (15-min)"

    async def async_added_to_hass(self) -> None:
        """Register periodic cloud refresh when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._async_scheduled_update,
                self._UPDATE_INTERVAL,
            )
        )

    async def _async_scheduled_update(self, now: object = None) -> None:
        """Fetch fresh daily AQI data and push state to Home Assistant."""
        _daily_env_cache.expire(self.coordinator.serial_number)
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        from libdyson_rest.exceptions import DysonAPIError, DysonAuthError

        serial = self.coordinator.serial_number
        data = _daily_env_cache.get(serial)
        if data is None:
            async with self.coordinator.async_cloud_client() as client:
                if client is not None:
                    try:
                        data = await client.get_daily_environment_data(serial)
                        _daily_env_cache.set(serial, data)
                    except (DysonAPIError, DysonAuthError) as err:
                        _LOGGER.debug(
                            "Failed to fetch daily AQI for %s: %s", serial, err
                        )
                        data = _daily_env_cache.get_stale(serial)

        if not data:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return

        latest = data.latest_sample
        series = data.samples
        self._attr_native_value = round(latest, 1) if latest is not None else None
        numeric = [v for v in series if v is not None]
        self._attr_extra_state_attributes = {
            "start_time": data.start_time,
            "resolution": data.resolution_minutes,
            "sample_count": len(series),
            "min": round(min(numeric, default=0), 1) if numeric else None,
            "max": round(max(numeric, default=0), 1) if numeric else None,
            # Keep the last 96 samples (24h at 15min) on the attribute.
            "last_24h": [
                round(float(v), 1) if v is not None else None for v in series[-96:]
            ],
        }


class DysonScheduledEventsSensor(DysonEntity, SensorEntity):
    """Read-only view of MyDyson-app scheduled events for this device.

    Source: GET /v1/unifiedscheduler/{serial}/events?productType={code}
    State = "<N> active" (count of enabled events). Attributes carry the
    full schedule list including each event's days, startTime, and MQTT
    state-set payload that Dyson would push at trigger time.
    """

    coordinator: DysonDataUpdateCoordinator
    _attr_icon = "mdi:calendar-clock"
    _UPDATE_INTERVAL = timedelta(minutes=5)

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_scheduled_events"
        self._attr_name = "Scheduled Events"

    async def async_added_to_hass(self) -> None:
        """Register periodic cloud refresh when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._async_scheduled_update,
                self._UPDATE_INTERVAL,
            )
        )

    async def _async_scheduled_update(self, now: object = None) -> None:
        """Fetch fresh scheduled-events data and push state to Home Assistant."""
        _schedule_cache.expire(self.coordinator.serial_number)
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        from libdyson_rest.exceptions import DysonAPIError, DysonAuthError

        serial = self.coordinator.serial_number
        data = _schedule_cache.get(serial)
        if data is None:
            product_type = _device_product_type(self.coordinator) or None
            async with self.coordinator.async_cloud_client() as client:
                if client is not None:
                    try:
                        data = await client.get_scheduled_events(
                            serial, product_type=product_type
                        )
                        _schedule_cache.set(serial, data)
                        _LOGGER.debug(
                            "Scheduled events for %s: schedule_enabled=%s, "
                            "total=%d, raw_events=%s",
                            serial,
                            data.schedule_enabled,
                            len(data.events),
                            [e.raw for e in data.events],
                        )
                    except (DysonAPIError, DysonAuthError) as err:
                        _LOGGER.debug(
                            "Failed to fetch scheduled events for %s: %s", serial, err
                        )
                        data = _schedule_cache.get_stale(serial)

        if not data:
            self._attr_native_value = "unknown"
            self._attr_extra_state_attributes = {}
            return

        events = data.events
        active_events = [e for e in events if e.enabled]

        # The Dyson API stores each schedule as multiple events (e.g. a start
        # event and an end event) sharing a common ``groupId``.  Count unique
        # group IDs so we report "1 active" when the user has 1 schedule in
        # the MyDyson app, even though it appears as 2 raw events.
        active_group_ids: set[int] = {
            e.raw["groupId"]
            for e in active_events
            if isinstance(e.raw.get("groupId"), int)
        }
        # Fall back to raw event count if no groupId is present.
        active_count = len(active_group_ids) if active_group_ids else len(active_events)

        # Gate the active count on the top-level schedule switch.  Individual
        # events may still have enabled=True even when the overall schedule is
        # disabled in the MyDyson app, so check schedule_enabled first.
        if not data.schedule_enabled:
            self._attr_native_value = "disabled"
        else:
            self._attr_native_value = f"{active_count} active"

        self._attr_extra_state_attributes = {
            "schedule_enabled": data.schedule_enabled,
            "active_schedule_count": active_count,
            "active_event_count": len(active_events),
            "total_event_count": len(events),
            "events": [e.raw for e in active_events],
        }
