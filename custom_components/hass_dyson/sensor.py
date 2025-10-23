"""Sensor platform for Dyson integration."""

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
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity

_LOGGER = logging.getLogger(__name__)


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

        # Add PM2.5 and PM10 sensors only for devices with ExtendedAQ capability
        if has_any_capability_safe(
            capabilities, ["ExtendedAQ", "extended_aq", "extendedAQ"]
        ):
            _LOGGER.debug("Adding PM2.5 and PM10 sensors for device %s", device_serial)
            entities.extend(
                [
                    DysonPM25Sensor(coordinator),
                    DysonPM10Sensor(coordinator),
                ]
            )
        else:
            _LOGGER.debug(
                "Skipping PM2.5/PM10 sensors for device %s - no ExtendedAQ capability",
                device_serial,
            )

        # Add VOC and NO2 sensors only for devices with VOC capability
        if has_any_capability_safe(capabilities, ["VOC", "voc"]):
            _LOGGER.debug("Adding VOC and NO2 sensors for device %s", device_serial)
            entities.extend(
                [
                    DysonVOCSensor(coordinator),
                    DysonNO2Sensor(coordinator),
                ]
            )
        else:
            _LOGGER.debug(
                "Skipping VOC/NO2 sensors for device %s - no VOC capability",
                device_serial,
            )

        # Add formaldehyde sensor only for devices with Formaldehyde capability
        if has_any_capability_safe(capabilities, ["Formaldehyde", "formaldehyde"]):
            _LOGGER.debug("Adding formaldehyde sensor for device %s", device_serial)
            entities.append(DysonFormaldehydeSensor(coordinator))
        else:
            _LOGGER.debug(
                "Skipping formaldehyde sensor for device %s - no formaldehyde capability",
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

        # Add carbon filter sensors only for devices with Formaldehyde capability
        # TODO: Update this when we identify the exact formaldehyde capability name
        # For now, don't add carbon filter sensors to any devices until we have a formaldehyde device to test
        if has_any_capability_safe(
            capabilities, ["Formaldehyde", "formaldehyde", "CarbonFilter"]
        ):
            _LOGGER.debug("Adding carbon filter sensors for device %s", device_serial)
            entities.extend(
                [
                    DysonCarbonFilterLifeSensor(coordinator),
                    DysonCarbonFilterTypeSensor(coordinator),
                ]
            )
        else:
            _LOGGER.debug(
                "Skipping carbon filter sensors for device %s - no formaldehyde capability detected",
                device_serial,
            )

        # Add temperature sensor only for devices with Heating capability
        if has_capability_safe(capabilities, "heating"):
            _LOGGER.debug("Adding temperature sensor for device %s", device_serial)
            entities.append(DysonTemperatureSensor(coordinator))
        else:
            _LOGGER.debug(
                "Skipping temperature sensor for device %s - no heating capability",
                device_serial,
            )

        # Add humidity sensor only for devices with Humidifier capability
        # TODO: Update this when we identify the exact humidifier capability name
        # For now, don't add humidity sensor to any devices until we have a humidifier to test
        if has_any_capability_safe(
            capabilities, ["Humidifier", "humidifier", "Humidity"]
        ):
            _LOGGER.debug("Adding humidity sensor for device %s", device_serial)
            entities.append(DysonHumiditySensor(coordinator))
        else:
            _LOGGER.debug(
                "Skipping humidity sensor for device %s - no humidifier capability detected",
                device_serial,
            )

        # Add battery sensor only for devices with robot category
        # TODO: Implement when we have a robot device to test battery data format
        if any(cat in ["robot"] for cat in device_category):
            _LOGGER.debug(
                "Robot device detected for %s, but battery sensor not yet implemented",
                device_serial,
            )
            # entities.append(DysonBatterySensor(coordinator))

        _LOGGER.info(
            "Successfully set up %d sensor entities for device %s",
            len(entities),
            device_serial,
        )

    except Exception as e:
        _LOGGER.error(
            "Error during sensor setup for device %s: %s", coordinator.serial_number, e
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
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            self._attr_native_value = None
            return

        temperature = self.coordinator.data.get("tmp")
        if temperature is not None:
            try:
                # Dyson typically reports temperature in Kelvin * 10
                # Convert to Celsius: (K * 10) / 10 - 273.15
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
        from .device_utils import convert_sensor_value_safe, get_sensor_data_safe

        device_serial = self.coordinator.serial_number

        if not self.coordinator.data:
            self._attr_native_value = None
            _LOGGER.debug(
                "Humidity sensor update: no coordinator data available for device %s",
                device_serial,
            )
            return

        # Safely extract humidity data
        humidity = get_sensor_data_safe(self.coordinator.data, "hact", device_serial)

        if humidity is not None:
            # Safely convert to integer with proper error handling
            converted_humidity = convert_sensor_value_safe(
                humidity, int, device_serial, "humidity"
            )
            self._attr_native_value = converted_humidity

            if converted_humidity is not None:
                _LOGGER.debug(
                    "Humidity sensor updated for device %s: %s%%",
                    device_serial,
                    converted_humidity,
                )
            else:
                _LOGGER.warning(
                    "Failed to convert humidity value for device %s: %s",
                    device_serial,
                    humidity,
                )
        else:
            self._attr_native_value = None
            _LOGGER.debug("No humidity data available for device %s", device_serial)

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
            env_data = self.coordinator.device._environmental_data
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
            env_data = self.coordinator.data.get("environmental-data", {}) if self.coordinator.data else {}
            pm25_raw = env_data.get("pm25")

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

        except Exception as e:
            _LOGGER.error(
                "Error updating PM2.5 sensor for device %s: %s", device_serial, e
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
            env_data = self.coordinator.device._environmental_data
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
            env_data = self.coordinator.data.get("environmental-data", {}) if self.coordinator.data else {}
            pm10_raw = env_data.get("pm10")

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

        except Exception as e:
            _LOGGER.error(
                "Error updating PM10 sensor for device %s: %s", device_serial, e
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonVOCSensor(DysonEntity, SensorEntity):
    """VOC (Volatile Organic Compounds) sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the VOC sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_voc"
        self._attr_translation_key = "voc"
        self._attr_device_class = SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "ppb"
        self._attr_icon = "mdi:chemical-weapon"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        try:
            old_value = self._attr_native_value
            new_value = getattr(self.coordinator.device, "voc", None)

            # Validate the new value is reasonable for VOC
            if new_value is not None:
                if isinstance(new_value, int | float) and 0 <= new_value <= 500:
                    self._attr_native_value = new_value
                    _LOGGER.debug(
                        "VOC sensor updated for %s: %s -> %s",
                        device_serial,
                        old_value,
                        new_value,
                    )
                else:
                    _LOGGER.warning(
                        "Invalid VOC value for device %s: %s (expected 0-500)",
                        device_serial,
                        new_value,
                    )
                    self._attr_native_value = None
            else:
                self._attr_native_value = None
                _LOGGER.debug("No VOC data available for device %s", device_serial)

        except Exception as e:
            _LOGGER.error(
                "Error updating VOC sensor for device %s: %s", device_serial, e
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
        self._attr_native_unit_of_measurement = "ppb"
        self._attr_icon = "mdi:molecule"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        try:
            old_value = self._attr_native_value
            new_value = getattr(self.coordinator.device, "no2", None)

            # Validate the new value is reasonable for NO2
            if new_value is not None:
                if isinstance(new_value, int | float) and 0 <= new_value <= 200:
                    self._attr_native_value = new_value
                    _LOGGER.debug(
                        "NO2 sensor updated for %s: %s -> %s",
                        device_serial,
                        old_value,
                        new_value,
                    )
                else:
                    _LOGGER.warning(
                        "Invalid NO2 value for device %s: %s (expected 0-200)",
                        device_serial,
                        new_value,
                    )
                    self._attr_native_value = None
            else:
                self._attr_native_value = None
                _LOGGER.debug("No NO2 data available for device %s", device_serial)

        except Exception as e:
            _LOGGER.error(
                "Error updating NO2 sensor for device %s: %s", device_serial, e
            )
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonFormaldehydeSensor(DysonEntity, SensorEntity):
    """Formaldehyde sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the formaldehyde sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_formaldehyde"
        self._attr_translation_key = "formaldehyde"
        self._attr_device_class = SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "ppb"
        self._attr_icon = "mdi:chemical-weapon"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_serial = self.coordinator.serial_number

        try:
            old_value = self._attr_native_value
            new_value = getattr(self.coordinator.device, "formaldehyde", None)

            # Validate the new value is reasonable for formaldehyde
            if new_value is not None:
                if isinstance(new_value, int | float) and 0 <= new_value <= 100:
                    self._attr_native_value = new_value
                    _LOGGER.debug(
                        "Formaldehyde sensor updated for %s: %s -> %s",
                        device_serial,
                        old_value,
                        new_value,
                    )
                else:
                    _LOGGER.warning(
                        "Invalid formaldehyde value for device %s: %s (expected 0-100)",
                        device_serial,
                        new_value,
                    )
                    self._attr_native_value = None
            else:
                self._attr_native_value = None
                _LOGGER.debug(
                    "No formaldehyde data available for device %s", device_serial
                )

        except Exception as e:
            _LOGGER.error(
                "Error updating formaldehyde sensor for device %s: %s", device_serial, e
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
        # No device class - filter life sensors don't have a specific Home Assistant device class
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:air-filter"

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

        except Exception as e:
            _LOGGER.error(
                "Error updating HEPA filter life sensor for device %s: %s",
                device_serial,
                e,
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
        # No device class - filter life sensors don't have a specific Home Assistant device class
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:air-filter"

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

        except Exception as e:
            _LOGGER.error(
                "Error updating carbon filter life sensor for device %s: %s",
                device_serial,
                e,
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
        self._attr_icon = "mdi:air-filter"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

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
        self._attr_name = "Carbon Filter Type"
        self._attr_icon = "mdi:air-filter"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

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
                # Convert "NONE" to "Not Installed", otherwise return the actual type
                if str(filter_type).upper() == "NONE":
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

        except Exception as e:
            _LOGGER.error(
                "Error updating carbon filter type sensor for device %s: %s",
                device_serial,
                e,
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
