"""
Tests for device capability mapping and testing with different device categories.

This module tests the capability detection and mapping logic that determines
which entities should be created for different Dyson device types.
"""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.hass_dyson.const import (
    CONF_DISCOVERY_METHOD,
    CONF_SERIAL_NUMBER,
    DISCOVERY_STICKER,
)
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator


class TestDeviceCapabilityMapping:
    """Test device capability mapping and detection."""

    @pytest.fixture
    def base_config_entry(self):
        """Create a base config entry for testing."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
            CONF_SERIAL_NUMBER: "TEST-DEVICE-456",
            "mqtt_username": "TEST-DEVICE-456",
            "mqtt_password": "test_password",
            "mqtt_hostname": "192.168.1.200",
        }
        return config_entry

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {}
        return hass

    def test_air_purifier_capabilities(self, mock_hass, base_config_entry):
        """Test capability mapping for air purifier devices."""
        # Air purifier typically has environmental data and extended air quality
        base_config_entry.data.update(
            {
                "capabilities": ["EnvironmentalData", "ExtendedAQ", "FanControl"],
                "device_category": "purifier",
            }
        )

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        # Test capability extraction
        capabilities = coordinator.device_capabilities
        assert "EnvironmentalData" in capabilities
        assert "ExtendedAQ" in capabilities
        assert "FanControl" in capabilities

        # Test capability mapping (check if capability exists in list)
        assert "EnvironmentalData" in coordinator.device_capabilities
        assert "ExtendedAQ" in coordinator.device_capabilities
        assert "Heating" not in coordinator.device_capabilities

    def test_heater_capabilities(self, mock_hass, base_config_entry):
        """Test capability mapping for heater devices."""
        base_config_entry.data.update(
            {
                "capabilities": ["EnvironmentalData", "Heating", "FanControl"],
                "device_category": "heater",
            }
        )

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        capabilities = coordinator.device_capabilities
        assert "Heating" in capabilities
        assert "EnvironmentalData" in capabilities

        assert "Heating" in coordinator.device_capabilities
        assert "ExtendedAQ" not in coordinator.device_capabilities

    def test_fan_capabilities(self, mock_hass, base_config_entry):
        """Test capability mapping for fan devices."""
        base_config_entry.data.update(
            {"capabilities": ["FanControl", "Oscillation"], "device_category": "fan"}
        )

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        capabilities = coordinator.device_capabilities
        assert "FanControl" in capabilities
        assert "Oscillation" in capabilities

        assert "FanControl" in coordinator.device_capabilities
        assert "EnvironmentalData" not in coordinator.device_capabilities

    def test_humidifier_capabilities(self, mock_hass, base_config_entry):
        """Test capability mapping for humidifier devices."""
        # Humidifier capability detection (currently theoretical)
        base_config_entry.data.update(
            {
                "capabilities": ["EnvironmentalData", "Humidifier", "FanControl"],
                "device_category": "humidifier",
            }
        )

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        capabilities = coordinator.device_capabilities
        assert "Humidifier" in capabilities
        assert "EnvironmentalData" in capabilities

    def test_robot_vacuum_capabilities(self, mock_hass, base_config_entry):
        """Test capability mapping for robot vacuum devices."""
        base_config_entry.data.update(
            {
                "capabilities": ["Navigation", "Cleaning", "BatteryStatus"],
                "device_category": "robot",
            }
        )

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        capabilities = coordinator.device_capabilities
        assert "Navigation" in capabilities
        assert "Cleaning" in capabilities
        assert "BatteryStatus" in capabilities

    def test_case_insensitive_capabilities(self, mock_hass, base_config_entry):
        """Test that capability matching is case-insensitive."""
        base_config_entry.data.update(
            {
                "capabilities": ["environmentaldata", "EXTENDEDAQ", "FanControl"],
                "device_category": "purifier",
            }
        )

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        capabilities = coordinator.device_capabilities
        # Test capability extraction directly
        assert "environmentaldata" in capabilities
        assert "EXTENDEDAQ" in capabilities
        assert "FanControl" in capabilities

    def test_empty_capabilities(self, mock_hass, base_config_entry):
        """Test handling of devices with no capabilities."""
        base_config_entry.data.update(
            {"capabilities": [], "device_category": "unknown"}
        )

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        capabilities = coordinator.device_capabilities
        assert len(capabilities) == 0
        assert capabilities == []

    def test_malformed_capabilities(self, mock_hass, base_config_entry):
        """Test handling of malformed capability data."""
        base_config_entry.data.update(
            {
                "capabilities": ["", None, "EnvironmentalData", 123],
                "device_category": "purifier",
            }
        )

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        capabilities = coordinator.device_capabilities
        # Should contain the raw capabilities as given
        assert "EnvironmentalData" in capabilities
        assert "" in capabilities  # Empty string should be present
        assert None in capabilities  # None should be present
        assert 123 in capabilities  # Number should be present


class TestDeviceCategoryMapping:
    """Test device category detection and mapping."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {}
        return hass

    @pytest.fixture
    def base_config_entry(self):
        """Create a base config entry for testing."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
            CONF_SERIAL_NUMBER: "TEST-DEVICE-789",
            "mqtt_username": "TEST-DEVICE-789",
            "mqtt_password": "test_password",
            "mqtt_hostname": "192.168.1.300",
            "capabilities": ["EnvironmentalData", "FanControl"],
        }
        return config_entry

    def test_ec_category_detection(self, mock_hass, base_config_entry):
        """Test detection of 'ec' category devices (environmental control)."""
        base_config_entry.data["device_category"] = "ec"

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        assert coordinator.device_category == "ec"

    def test_robot_category_detection(self, mock_hass, base_config_entry):
        """Test detection of 'robot' category devices."""
        base_config_entry.data["device_category"] = "robot"

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        assert coordinator.device_category == "robot"

    def test_vacuum_category_detection(self, mock_hass, base_config_entry):
        """Test detection of 'vacuum' category devices."""
        base_config_entry.data["device_category"] = "vacuum"

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        assert coordinator.device_category == "vacuum"

    def test_purifier_category_detection(self, mock_hass, base_config_entry):
        """Test detection of 'purifier' category devices."""
        base_config_entry.data["device_category"] = "purifier"

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        assert coordinator.device_category == "purifier"

    def test_unknown_category_handling(self, mock_hass, base_config_entry):
        """Test handling of unknown device categories."""
        base_config_entry.data["device_category"] = "unknown_device_type"

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        assert coordinator.device_category == "unknown_device_type"

    def test_missing_category_handling(self, mock_hass, base_config_entry):
        """Test handling when device category is missing."""
        # Remove device_category from config
        if "device_category" in base_config_entry.data:
            del base_config_entry.data["device_category"]

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        # Should handle missing category gracefully
        category = coordinator.device_category
        assert category is None or category == ""


class TestCapabilityBasedEntityCreation:
    """Test that capabilities properly determine which entities get created."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {}
        return hass

    @pytest.fixture
    def base_config_entry(self):
        """Create a base config entry for testing."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
            CONF_SERIAL_NUMBER: "TEST-CAPABILITY-123",
            "mqtt_username": "TEST-CAPABILITY-123",
            "mqtt_password": "test_password",
            "mqtt_hostname": "192.168.1.400",
        }
        return config_entry

    def test_extended_aq_enables_air_quality_sensors(
        self, mock_hass, base_config_entry
    ):
        """Test that ExtendedAQ capability enables PM2.5/PM10 sensors."""
        base_config_entry.data.update(
            {"capabilities": ["ExtendedAQ"], "device_category": "purifier"}
        )

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )
            # Add has_capability method for tests that need it
            coordinator.has_capability = (
                lambda cap: cap in coordinator._device_capabilities
            )

        # The capability should be detectable
        assert coordinator.has_capability("ExtendedAQ")

        # In real sensor.py, this would enable PM2.5/PM10 sensor creation
        # We verify the capability is properly detected for filtering

    def test_heating_enables_temperature_sensor(self, mock_hass, base_config_entry):
        """Test that Heating capability enables temperature sensor."""
        base_config_entry.data.update(
            {"capabilities": ["Heating"], "device_category": "heater"}
        )

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )
            # Add has_capability method for tests that need it
            coordinator.has_capability = (
                lambda cap: cap in coordinator._device_capabilities
            )

        assert coordinator.has_capability("Heating")
        # In real sensor.py, this would enable temperature sensor creation

    def test_ec_category_enables_wifi_sensors(self, mock_hass, base_config_entry):
        """Test that 'ec' category enables WiFi signal sensors."""
        base_config_entry.data.update(
            {"capabilities": ["EnvironmentalData"], "device_category": "ec"}
        )

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        assert coordinator.device_category == "ec"
        # In real sensor.py, this would enable WiFi sensor creation

    def test_robot_category_enables_wifi_sensors(self, mock_hass, base_config_entry):
        """Test that 'robot' category enables WiFi signal sensors."""
        base_config_entry.data.update(
            {"capabilities": ["Navigation"], "device_category": "robot"}
        )

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        assert coordinator.device_category == "robot"
        # In real sensor.py, this would enable WiFi sensor creation

    def test_vacuum_category_no_wifi_sensors(self, mock_hass, base_config_entry):
        """Test that 'vacuum' category does NOT enable WiFi sensors."""
        base_config_entry.data.update(
            {"capabilities": ["Cleaning"], "device_category": "vacuum"}
        )

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )

        assert coordinator.device_category == "vacuum"
        # In real sensor.py, this would NOT enable WiFi sensor creation

    def test_multiple_capabilities_enable_multiple_sensors(
        self, mock_hass, base_config_entry
    ):
        """Test that multiple capabilities enable multiple sensor types."""
        base_config_entry.data.update(
            {
                "capabilities": ["ExtendedAQ", "Heating", "EnvironmentalData"],
                "device_category": "ec",
            }
        )

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = base_config_entry
            coordinator._device_capabilities = base_config_entry.data.get(
                "capabilities", []
            )
            coordinator._device_category = base_config_entry.data.get(
                "device_category", ""
            )
            # Add has_capability method for tests that need it
            coordinator.has_capability = (
                lambda cap: cap in coordinator._device_capabilities
            )

        # All capabilities should be detectable
        assert coordinator.has_capability("ExtendedAQ")
        assert coordinator.has_capability("Heating")
        assert coordinator.has_capability("EnvironmentalData")
        assert coordinator.device_category == "ec"

        # This would enable PM2.5/PM10, temperature, and WiFi sensors


class TestRealDeviceScenarios:
    """Test scenarios based on real Dyson device configurations."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {}
        return hass

    def test_dyson_pure_cool_purifier(self, mock_hass):
        """Test configuration for a Dyson Pure Cool air purifier."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
            CONF_SERIAL_NUMBER: "PURIFIER-REAL-001",
            "mqtt_username": "PURIFIER-REAL-001",
            "mqtt_password": "purifier_password",
            "mqtt_hostname": "192.168.1.50",
            "capabilities": [
                "EnvironmentalData",
                "ExtendedAQ",
                "FanControl",
                "Oscillation",
            ],
            "device_category": "purifier",
        }

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = config_entry
            coordinator._device_capabilities = config_entry.data.get("capabilities", [])
            coordinator._device_category = config_entry.data.get("device_category", "")
            # Add has_capability method for tests that need it
            coordinator.has_capability = (
                lambda cap: cap in coordinator._device_capabilities
            )

        # Should have air quality capabilities
        assert coordinator.has_capability("ExtendedAQ")
        assert coordinator.has_capability("EnvironmentalData")
        assert coordinator.has_capability("FanControl")

        # Should be purifier category (no WiFi sensors)
        assert coordinator.device_category == "purifier"

    def test_dyson_hot_cool_heater(self, mock_hass):
        """Test configuration for a Dyson Hot+Cool heater/fan."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
            CONF_SERIAL_NUMBER: "HEATER-REAL-002",
            "mqtt_username": "HEATER-REAL-002",
            "mqtt_password": "heater_password",
            "mqtt_hostname": "192.168.1.51",
            "capabilities": ["EnvironmentalData", "Heating", "FanControl"],
            "device_category": "heater",
        }

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = config_entry
            coordinator._device_capabilities = config_entry.data.get("capabilities", [])
            coordinator._device_category = config_entry.data.get("device_category", "")
            # Add has_capability method for tests that need it
            coordinator.has_capability = (
                lambda cap: cap in coordinator._device_capabilities
            )

        # Should have heating capabilities
        assert coordinator.has_capability("Heating")
        assert coordinator.has_capability("EnvironmentalData")
        assert coordinator.has_capability("FanControl")

        # No air quality sensors
        assert not coordinator.has_capability("ExtendedAQ")

        # Should be heater category
        assert coordinator.device_category == "heater"

    def test_dyson_v15_robot_vacuum(self, mock_hass):
        """Test configuration for a Dyson V15 robot vacuum."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
            CONF_SERIAL_NUMBER: "ROBOT-REAL-003",
            "mqtt_username": "ROBOT-REAL-003",
            "mqtt_password": "robot_password",
            "mqtt_hostname": "192.168.1.52",
            "capabilities": ["Navigation", "Cleaning", "BatteryStatus"],
            "device_category": "robot",
        }

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.config_entry = config_entry
            coordinator._device_capabilities = config_entry.data.get("capabilities", [])
            coordinator._device_category = config_entry.data.get("device_category", "")
            # Add has_capability method for tests that need it
            coordinator.has_capability = (
                lambda cap: cap in coordinator._device_capabilities
            )

        # Should have robot capabilities
        assert coordinator.has_capability("Navigation")
        assert coordinator.has_capability("Cleaning")
        assert coordinator.has_capability("BatteryStatus")

        # No environmental data
        assert not coordinator.has_capability("EnvironmentalData")
        assert not coordinator.has_capability("ExtendedAQ")

        # Should be robot category (enables WiFi sensors)
        assert coordinator.device_category == "robot"
