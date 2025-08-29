"""Sensor platform for Dyson Alternative integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dyson sensor platform."""
    coordinator: DysonDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Air quality sensors - we know these work from our MQTT test
    entities.extend(
        [
            DysonPM25Sensor(coordinator),
            DysonPM10Sensor(coordinator),
            DysonWiFiSensor(coordinator),
            DysonHEPAFilterLifeSensor(coordinator),
            DysonCarbonFilterLifeSensor(coordinator),
            DysonFirmwareVersionSensor(coordinator),
        ]
    )

    async_add_entities(entities, True)


class DysonFilterLifeSensor(DysonEntity, SensorEntity):
    """Representation of a Dyson filter life sensor."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator, filter_type: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.filter_type = filter_type
        self._attr_unique_id = f"{coordinator.serial_number}_{filter_type}_filter_life"
        self._attr_name = f"{filter_type.upper()} Filter Life"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.BATTERY  # Closest available
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

    def __init__(self, coordinator: DysonDataUpdateCoordinator, sensor_type: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.sensor_type = sensor_type
        self._attr_unique_id = f"{coordinator.serial_number}_{sensor_type}"
        self._attr_name = sensor_type.upper()
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:air-filter"

        if sensor_type in ["pm25", "pm10"]:
            self._attr_device_class = SensorDeviceClass.PM25 if sensor_type == "pm25" else SensorDeviceClass.PM10
            self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER

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
        self._attr_name = "Temperature"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "°C"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            self._attr_native_value = None
            return

        temperature = self.coordinator.data.get("temperature")
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
        self._attr_name = "Humidity"
        self._attr_device_class = SensorDeviceClass.HUMIDITY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = PERCENTAGE

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            self._attr_native_value = None
            return

        humidity = self.coordinator.data.get("humidity")
        if humidity is not None:
            try:
                # Dyson typically reports humidity as percentage
                self._attr_native_value = int(humidity)
            except (ValueError, TypeError):
                self._attr_native_value = None
        else:
            self._attr_native_value = None

        super()._handle_coordinator_update()


class DysonPM25Sensor(DysonEntity, SensorEntity):
    """PM2.5 sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the PM2.5 sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_pm25"
        self._attr_name = "PM2.5"
        self._attr_device_class = SensorDeviceClass.PM25
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_native_value = None
            return

        # Use our device PM2.5 property
        self._attr_native_value = self.coordinator.device.pm25
        super()._handle_coordinator_update()


class DysonPM10Sensor(DysonEntity, SensorEntity):
    """PM10 sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the PM10 sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_pm10"
        self._attr_name = "PM10"
        self._attr_device_class = SensorDeviceClass.PM10
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_native_value = None
            return

        # Use our device PM10 property
        self._attr_native_value = self.coordinator.device.pm10
        super()._handle_coordinator_update()


class DysonWiFiSensor(DysonEntity, SensorEntity):
    """WiFi signal strength sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the WiFi sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_wifi"
        self._attr_name = "WiFi Signal"
        self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "dBm"
        self._attr_icon = "mdi:wifi"

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
        self._attr_name = "HEPA Filter Life"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.BATTERY  # Closest available
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_native_value = None
            return

        # Use our device HEPA filter life property
        self._attr_native_value = self.coordinator.device.hepa_filter_life
        super()._handle_coordinator_update()


class DysonCarbonFilterLifeSensor(DysonEntity, SensorEntity):
    """Carbon filter life sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the carbon filter life sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_carbon_filter_life"
        self._attr_name = "Carbon Filter Life"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.BATTERY  # Closest available
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_native_value = None
            return

        # Use our device carbon filter life property
        self._attr_native_value = self.coordinator.device.carbon_filter_life
        super()._handle_coordinator_update()


class DysonFilterStatusSensor(DysonEntity, SensorEntity):
    """Filter status sensor for Dyson devices."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the filter status sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_number}_filter_status"
        self._attr_name = "Filter Status"
        self._attr_icon = "mdi:air-filter"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_native_value = None
            return

        # Use our device filter status property
        self._attr_native_value = self.coordinator.device.filter_status
        super()._handle_coordinator_update()


class DysonFirmwareVersionSensor(DysonEntity, SensorEntity):
    """Sensor for firmware version information."""

    coordinator: DysonDataUpdateCoordinator

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the firmware version sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_firmware_version"
        self._attr_name = "Firmware Version"
        self._attr_icon = "mdi:chip"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.device:
            self._attr_native_value = None
            return

        # Extract firmware version from device data
        # This would typically come from device info or status messages
        device_data = self.coordinator.data.get("product-state", {})
        firmware_version = device_data.get("fwv", "Unknown")

        # Format firmware version for display
        if firmware_version and firmware_version != "Unknown":
            self._attr_native_value = firmware_version
        else:
            self._attr_native_value = "Unknown"

        super()._handle_coordinator_update()
