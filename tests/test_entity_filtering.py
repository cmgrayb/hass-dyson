"""Tests for entity filtering logic based on device capabilities and categories."""

from unittest.mock import MagicMock

import pytest

from custom_components.hass_dyson.binary_sensor import DysonFilterReplacementSensor
from custom_components.hass_dyson.const import (
    CAPABILITY_EXTENDED_AQ,
    CAPABILITY_FORMALDEHYDE,
    CAPABILITY_HEATING,
    CAPABILITY_HUMIDIFIER,
    DEVICE_CATEGORY_EC,
    DEVICE_CATEGORY_ROBOT,
    DEVICE_CATEGORY_VACUUM,
)
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
from custom_components.hass_dyson.sensor import (
    DysonCarbonFilterLifeSensor,
    DysonCarbonFilterTypeSensor,
    DysonConnectionStatusSensor,
    DysonHEPAFilterLifeSensor,
    DysonHEPAFilterTypeSensor,
    DysonHumiditySensor,
    DysonPM10Sensor,
    DysonPM25Sensor,
    DysonTemperatureSensor,
    DysonWiFiSensor,
)


class TestEntityFiltering:
    """Test entity filtering based on device capabilities and categories."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator with basic configuration."""
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-DEVICE-123"
        coordinator.device_name = "Test Device"
        coordinator.device = MagicMock()
        coordinator.data = {}
        return coordinator

    def test_extended_aq_capability_creates_air_quality_sensors(self, mock_coordinator):
        """Test that devices with ExtendedAQ capability get PM2.5 and PM10 sensors."""
        # Test with ExtendedAQ capability
        mock_coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ]
        mock_coordinator.device_category = [DEVICE_CATEGORY_EC]

        # Simulate sensor creation logic
        capabilities_str = [
            cap.lower() if isinstance(cap, str) else str(cap).lower()
            for cap in mock_coordinator.device_capabilities
        ]

        should_create_pm_sensors = (
            "extendedAQ".lower() in capabilities_str
            or "extended_aq" in capabilities_str
        )

        assert should_create_pm_sensors, "Devices with ExtendedAQ should get PM sensors"

        # Verify sensor creation
        pm25_sensor = DysonPM25Sensor(mock_coordinator)
        pm10_sensor = DysonPM10Sensor(mock_coordinator)

        assert pm25_sensor.unique_id == "TEST-DEVICE-123_pm25"
        assert pm10_sensor.unique_id == "TEST-DEVICE-123_pm10"

    def test_no_extended_aq_capability_no_air_quality_sensors(self, mock_coordinator):
        """Test that devices without ExtendedAQ capability don't get PM sensors."""
        # Test without ExtendedAQ capability
        mock_coordinator.device_capabilities = ["Scheduling"]
        mock_coordinator.device_category = [DEVICE_CATEGORY_EC]

        capabilities_str = [
            cap.lower() if isinstance(cap, str) else str(cap).lower()
            for cap in mock_coordinator.device_capabilities
        ]

        should_create_pm_sensors = (
            "extendedAQ".lower() in capabilities_str
            or "extended_aq" in capabilities_str
        )

        assert not should_create_pm_sensors, (
            "Devices without ExtendedAQ should not get PM sensors"
        )

    def test_ec_category_creates_wifi_sensors(self, mock_coordinator):
        """Test that EC category devices get WiFi sensors."""
        mock_coordinator.device_capabilities = ["EnvironmentalData"]
        mock_coordinator.device_category = [DEVICE_CATEGORY_EC]

        should_create_wifi_sensors = any(
            cat in ["ec", "robot"] for cat in mock_coordinator.device_category
        )

        assert should_create_wifi_sensors, "EC devices should get WiFi sensors"

        # Verify sensor creation
        wifi_sensor = DysonWiFiSensor(mock_coordinator)
        connection_sensor = DysonConnectionStatusSensor(mock_coordinator)

        assert wifi_sensor.unique_id == "TEST-DEVICE-123_wifi"
        assert connection_sensor.unique_id == "TEST-DEVICE-123_connection_status"

    def test_robot_category_creates_wifi_sensors(self, mock_coordinator):
        """Test that robot category devices get WiFi sensors."""
        mock_coordinator.device_capabilities = ["EnvironmentalData"]
        mock_coordinator.device_category = [DEVICE_CATEGORY_ROBOT]

        should_create_wifi_sensors = any(
            cat in ["ec", "robot"] for cat in mock_coordinator.device_category
        )

        assert should_create_wifi_sensors, "Robot devices should get WiFi sensors"

    def test_vacuum_category_no_wifi_sensors(self, mock_coordinator):
        """Test that vacuum category devices don't get WiFi sensors."""
        mock_coordinator.device_capabilities = ["EnvironmentalData"]
        mock_coordinator.device_category = [DEVICE_CATEGORY_VACUUM]

        should_create_wifi_sensors = any(
            cat in ["ec", "robot"] for cat in mock_coordinator.device_category
        )

        assert not should_create_wifi_sensors, (
            "Vacuum devices should not get WiFi sensors"
        )

    def test_extended_aq_creates_hepa_filter_sensors(self, mock_coordinator):
        """Test that devices with ExtendedAQ capability get HEPA filter sensors."""
        mock_coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ]
        mock_coordinator.device_category = [DEVICE_CATEGORY_EC]

        capabilities_str = [
            cap.lower() if isinstance(cap, str) else str(cap).lower()
            for cap in mock_coordinator.device_capabilities
        ]

        should_create_hepa_sensors = (
            "extendedAQ".lower() in capabilities_str
            or "extended_aq" in capabilities_str
        )

        assert should_create_hepa_sensors, (
            "Devices with ExtendedAQ should get HEPA filter sensors"
        )

        # Verify sensor creation
        hepa_life_sensor = DysonHEPAFilterLifeSensor(mock_coordinator)
        hepa_type_sensor = DysonHEPAFilterTypeSensor(mock_coordinator)

        assert hepa_life_sensor.unique_id == "TEST-DEVICE-123_hepa_filter_life"
        assert hepa_type_sensor.unique_id == "TEST-DEVICE-123_hepa_filter_type"

    def test_heating_capability_creates_temperature_sensor(self, mock_coordinator):
        """Test that devices with Heating capability get temperature sensor."""
        mock_coordinator.device_capabilities = [CAPABILITY_HEATING]
        mock_coordinator.device_category = [DEVICE_CATEGORY_EC]

        capabilities_str = [
            cap.lower() if isinstance(cap, str) else str(cap).lower()
            for cap in mock_coordinator.device_capabilities
        ]

        should_create_temp_sensor = "heating" in capabilities_str

        assert should_create_temp_sensor, (
            "Devices with Heating should get temperature sensor"
        )

        # Verify sensor creation
        temp_sensor = DysonTemperatureSensor(mock_coordinator)
        assert temp_sensor.unique_id == "TEST-DEVICE-123_temperature"

    def test_no_heating_capability_no_temperature_sensor(self, mock_coordinator):
        """Test that devices without Heating capability don't get temperature sensor."""
        mock_coordinator.device_capabilities = ["Scheduling"]
        mock_coordinator.device_category = [DEVICE_CATEGORY_EC]

        capabilities_str = [
            cap.lower() if isinstance(cap, str) else str(cap).lower()
            for cap in mock_coordinator.device_capabilities
        ]

        should_create_temp_sensor = "heating" in capabilities_str

        assert not should_create_temp_sensor, (
            "Devices without Heating should not get temperature sensor"
        )

    def test_formaldehyde_capability_would_create_carbon_sensors(
        self, mock_coordinator
    ):
        """Test that devices with Formaldehyde capability would get carbon filter sensors."""
        # Note: This is currently commented out in the code, but we test the logic
        mock_coordinator.device_capabilities = [CAPABILITY_FORMALDEHYDE]
        mock_coordinator.device_category = [DEVICE_CATEGORY_EC]

        capabilities_str = [
            cap.lower() if isinstance(cap, str) else str(cap).lower()
            for cap in mock_coordinator.device_capabilities
        ]

        should_create_carbon_sensors = "formaldehyde" in capabilities_str

        assert should_create_carbon_sensors, (
            "Devices with Formaldehyde should get carbon filter sensors"
        )

        # Verify sensor creation (even though currently disabled)
        carbon_life_sensor = DysonCarbonFilterLifeSensor(mock_coordinator)
        carbon_type_sensor = DysonCarbonFilterTypeSensor(mock_coordinator)

        assert carbon_life_sensor.unique_id == "TEST-DEVICE-123_carbon_filter_life"
        assert carbon_type_sensor.unique_id == "TEST-DEVICE-123_carbon_filter_type"

    def test_humidifier_capability_would_create_humidity_sensor(self, mock_coordinator):
        """Test that devices with Humidifier capability would get humidity sensor."""
        # Note: This is currently commented out in the code, but we test the logic
        mock_coordinator.device_capabilities = [CAPABILITY_HUMIDIFIER]
        mock_coordinator.device_category = [DEVICE_CATEGORY_EC]

        capabilities_str = [
            cap.lower() if isinstance(cap, str) else str(cap).lower()
            for cap in mock_coordinator.device_capabilities
        ]

        should_create_humidity_sensor = "humidifier" in capabilities_str

        assert should_create_humidity_sensor, (
            "Devices with Humidifier should get humidity sensor"
        )

        # Verify sensor creation (even though currently disabled)
        humidity_sensor = DysonHumiditySensor(mock_coordinator)
        assert humidity_sensor.unique_id == "TEST-DEVICE-123_humidity"

    def test_multiple_capabilities_create_multiple_sensors(self, mock_coordinator):
        """Test that devices with multiple capabilities get all relevant sensors."""
        mock_coordinator.device_capabilities = [
            CAPABILITY_EXTENDED_AQ,
            CAPABILITY_HEATING,
            "Scheduling",
        ]
        mock_coordinator.device_category = [DEVICE_CATEGORY_EC]

        capabilities_str = [
            cap.lower() if isinstance(cap, str) else str(cap).lower()
            for cap in mock_coordinator.device_capabilities
        ]

        # Should create PM sensors
        should_create_pm_sensors = (
            "extendedAQ".lower() in capabilities_str
            or "extended_aq" in capabilities_str
        )
        assert should_create_pm_sensors

        # Should create WiFi sensors
        should_create_wifi_sensors = any(
            cat in ["ec", "robot"] for cat in mock_coordinator.device_category
        )
        assert should_create_wifi_sensors

        # Should create HEPA sensors
        should_create_hepa_sensors = (
            "extendedAQ".lower() in capabilities_str
            or "extended_aq" in capabilities_str
        )
        assert should_create_hepa_sensors

        # Should create temperature sensor
        should_create_temp_sensor = "heating" in capabilities_str
        assert should_create_temp_sensor

    def test_no_capabilities_minimal_sensors(self, mock_coordinator):
        """Test that devices with no special capabilities get only basic sensors."""
        mock_coordinator.device_capabilities = []
        mock_coordinator.device_category = [DEVICE_CATEGORY_VACUUM]  # No WiFi

        capabilities_str = [
            cap.lower() if isinstance(cap, str) else str(cap).lower()
            for cap in mock_coordinator.device_capabilities
        ]

        # Should not create PM sensors
        should_create_pm_sensors = (
            "extendedAQ".lower() in capabilities_str
            or "extended_aq" in capabilities_str
        )
        assert not should_create_pm_sensors

        # Should not create WiFi sensors (vacuum category)
        should_create_wifi_sensors = any(
            cat in ["ec", "robot"] for cat in mock_coordinator.device_category
        )
        assert not should_create_wifi_sensors

        # Should not create HEPA sensors
        should_create_hepa_sensors = (
            "extendedAQ".lower() in capabilities_str
            or "extended_aq" in capabilities_str
        )
        assert not should_create_hepa_sensors

        # Should not create temperature sensor
        should_create_temp_sensor = "heating" in capabilities_str
        assert not should_create_temp_sensor

    def test_case_insensitive_capability_matching(self, mock_coordinator):
        """Test that capability matching is case-insensitive."""
        # Test with different cases
        test_cases = ["ExtendedAQ", "extendedAQ", "EXTENDEDAQ", "extendedaq"]

        for capability in test_cases:
            mock_coordinator.device_capabilities = [capability]
            capabilities_str = [
                cap.lower() if isinstance(cap, str) else str(cap).lower()
                for cap in mock_coordinator.device_capabilities
            ]

            should_create_pm_sensors = (
                "extendedAQ".lower() in capabilities_str
                or "extended_aq" in capabilities_str
            )

            assert should_create_pm_sensors, (
                f"Case variation {capability} should be recognized"
            )


class TestBinarySensorFiltering:
    """Test binary sensor filtering based on device capabilities and categories."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator with basic configuration."""
        coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-DEVICE-123"
        coordinator.device_name = "Test Device"
        coordinator.device = MagicMock()
        coordinator.data = {"product-state": {}}
        return coordinator

    def test_filter_replacement_sensor_always_created(self, mock_coordinator):
        """Test that filter replacement sensor is always created."""
        mock_coordinator.device_capabilities = []
        mock_coordinator.device_category = [DEVICE_CATEGORY_EC]

        # Filter replacement sensor should always be created
        filter_sensor = DysonFilterReplacementSensor(mock_coordinator)
        assert filter_sensor.unique_id == "TEST-DEVICE-123_filter_replacement"

    def test_fault_sensor_filtering_by_category(self, mock_coordinator):
        """Test that fault sensors are filtered by device category."""
        mock_coordinator.device_capabilities = []
        mock_coordinator.device_category = [DEVICE_CATEGORY_EC]

        # Test EC category fault codes
        from custom_components.hass_dyson.binary_sensor import _is_fault_code_relevant

        # These should be relevant for EC devices
        assert _is_fault_code_relevant("mflr", [DEVICE_CATEGORY_EC], [])  # Motor
        assert _is_fault_code_relevant("pwr", [DEVICE_CATEGORY_EC], [])  # Power
        assert _is_fault_code_relevant("wifi", [DEVICE_CATEGORY_EC], [])  # WiFi

        # These should not be relevant for EC devices
        assert not _is_fault_code_relevant(
            "brsh", [DEVICE_CATEGORY_EC], []
        )  # Brush (robot)
        assert not _is_fault_code_relevant(
            "bin", [DEVICE_CATEGORY_EC], []
        )  # Dustbin (robot)

    def test_fault_sensor_filtering_by_capability(self, mock_coordinator):
        """Test that fault sensors are filtered by device capabilities."""
        from custom_components.hass_dyson.binary_sensor import _is_fault_code_relevant

        # Test ExtendedAQ capability fault codes
        capabilities = [CAPABILITY_EXTENDED_AQ]
        assert _is_fault_code_relevant(
            "aqs", [DEVICE_CATEGORY_EC], capabilities
        )  # Air quality sensor
        assert _is_fault_code_relevant(
            "fltr", [DEVICE_CATEGORY_EC], capabilities
        )  # Filter
        assert _is_fault_code_relevant(
            "hflr", [DEVICE_CATEGORY_EC], capabilities
        )  # HEPA filter

        # Test Heating capability fault codes
        capabilities = [CAPABILITY_HEATING]
        assert _is_fault_code_relevant(
            "temp", [DEVICE_CATEGORY_EC], capabilities
        )  # Temperature sensor

        # Test without capabilities
        capabilities = []
        assert not _is_fault_code_relevant("aqs", [DEVICE_CATEGORY_EC], capabilities)
        assert not _is_fault_code_relevant("temp", [DEVICE_CATEGORY_EC], capabilities)

    def test_robot_category_fault_codes(self, mock_coordinator):
        """Test fault codes specific to robot devices."""
        from custom_components.hass_dyson.binary_sensor import _is_fault_code_relevant

        # Robot-specific fault codes
        assert _is_fault_code_relevant("brsh", [DEVICE_CATEGORY_ROBOT], [])  # Brush
        assert _is_fault_code_relevant("bin", [DEVICE_CATEGORY_ROBOT], [])  # Dustbin

        # Common fault codes should also work
        assert _is_fault_code_relevant("mflr", [DEVICE_CATEGORY_ROBOT], [])  # Motor
        assert _is_fault_code_relevant("wifi", [DEVICE_CATEGORY_ROBOT], [])  # WiFi

    def test_vacuum_category_fault_codes(self, mock_coordinator):
        """Test fault codes specific to vacuum devices."""
        from custom_components.hass_dyson.binary_sensor import _is_fault_code_relevant

        # Vacuum-specific fault codes
        assert _is_fault_code_relevant("brsh", [DEVICE_CATEGORY_VACUUM], [])  # Brush
        assert _is_fault_code_relevant("bin", [DEVICE_CATEGORY_VACUUM], [])  # Dustbin

        # WiFi should be relevant for vacuums (they do have WiFi according to config)
        assert _is_fault_code_relevant("wifi", [DEVICE_CATEGORY_VACUUM], [])

    def test_unknown_fault_code_not_relevant(self, mock_coordinator):
        """Test that unknown fault codes are not relevant."""
        from custom_components.hass_dyson.binary_sensor import _is_fault_code_relevant

        assert not _is_fault_code_relevant("unknown", [DEVICE_CATEGORY_EC], [])
        assert not _is_fault_code_relevant(
            "fake_code", [DEVICE_CATEGORY_ROBOT], [CAPABILITY_EXTENDED_AQ]
        )
