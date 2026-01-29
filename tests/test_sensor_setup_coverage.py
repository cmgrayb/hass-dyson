"""Test coverage for sensor async_setup_entry conditional paths.

This module targets uncovered conditional logic in sensor.py's async_setup_entry
function to improve coverage from 57% to 70%+. Focus areas:
1. Conditional sensor creation based on capabilities
2. Conditional sensor creation based on data presence
3. Error handling in setup (KeyError, AttributeError, ValueError, TypeError, Exception)
4. Fallback behavior when exceptions occur
5. WiFi sensor creation for ec/robot categories
6. Filter sensor creation logic
7. Humidifier sensor creation
8. ExtendedAQ conditional paths

Target: +5-10% sensor.py coverage improvement through setup path testing
"""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.hass_dyson.const import DOMAIN
from custom_components.hass_dyson.sensor import async_setup_entry


class TestSensorSetupCapabilityPaths:
    """Test sensor creation based on different capability combinations."""

    @pytest.mark.asyncio
    async def test_setup_with_extended_aq_no_env_data(self):
        """Test ExtendedAQ capability without environmental data."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["ExtendedAQ"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-001"
        coordinator.data = {}  # No environmental-data key

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        async_add_entities.assert_called_once()
        # PM sensors should NOT be created without data, but HEPA filters and WiFi sensors should
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonPM25Sensor" not in sensor_types
        assert "DysonPM10Sensor" not in sensor_types
        # HEPA filter and WiFi sensors should be created
        assert "DysonHEPAFilterLifeSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_with_extended_aq_co2_data_present(self):
        """Test CO2 sensor creation when co2r data is present."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["ExtendedAQ"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-002"
        coordinator.data = {"environmental-data": {"co2r": "500"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        # Should include PM25, PM10, and CO2 sensors
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonCO2Sensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_with_extended_aq_no_co2_data(self):
        """Test CO2 sensor NOT created when co2r data is missing."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["ExtendedAQ"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-003"
        coordinator.data = {"environmental-data": {}}  # No co2r key

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonCO2Sensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_setup_with_extended_aq_no2_data_present(self):
        """Test NO2 sensor creation when noxl data is present."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["ExtendedAQ"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-004"
        coordinator.data = {"environmental-data": {"noxl": "2"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonNO2Sensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_with_extended_aq_no_no2_data(self):
        """Test NO2 sensor NOT created when noxl data is missing."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["ExtendedAQ"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-005"
        coordinator.data = {"environmental-data": {}}  # No noxl key

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonNO2Sensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_setup_with_extended_aq_voc_data_present(self):
        """Test VOC sensor creation when va10 data is present."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["ExtendedAQ"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-006"
        coordinator.data = {"environmental-data": {"va10": "1500"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonVOCSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_with_extended_aq_no_voc_data(self):
        """Test VOC sensor NOT created when va10 data is missing."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["ExtendedAQ"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-007"
        coordinator.data = {"environmental-data": {}}  # No va10 key

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonVOCSensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_setup_with_extended_aq_formaldehyde_hchr_present(self):
        """Test Formaldehyde sensor creation when hchr data is present."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["ExtendedAQ"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-008"
        coordinator.data = {"environmental-data": {"hchr": "0"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonFormaldehydeSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_with_extended_aq_formaldehyde_hcho_present(self):
        """Test Formaldehyde sensor creation when hcho data is present."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["ExtendedAQ"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-009"
        coordinator.data = {"environmental-data": {"hcho": "1"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonFormaldehydeSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_with_extended_aq_no_formaldehyde_data(self):
        """Test Formaldehyde sensor NOT created when hchr/hcho data is missing."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["ExtendedAQ"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-010"
        coordinator.data = {"environmental-data": {}}  # No hchr or hcho keys

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonFormaldehydeSensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_setup_without_extended_aq_capability(self):
        """Test no ExtendedAQ sensors created without capability."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []  # No ExtendedAQ capability
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-011"
        coordinator.data = {"environmental-data": {"co2r": "500", "noxl": "2"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        # No PM25, PM10, CO2, NO2 sensors should be created
        assert "DysonPM25Sensor" not in sensor_types
        assert "DysonPM10Sensor" not in sensor_types
        assert "DysonCO2Sensor" not in sensor_types
        assert "DysonNO2Sensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_setup_environmental_data_with_pm25_data(self):
        """Test PM2.5 sensor created with EnvironmentalData capability and p25r data."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["EnvironmentalData"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TP02-001"
        coordinator.data = {"environmental-data": {"p25r": "15", "tact": "2950"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        # PM2.5 sensor should be created with EnvironmentalData capability
        assert "DysonPM25Sensor" in sensor_types
        # But ExtendedAQ-only sensors should not be created
        assert "DysonCO2Sensor" not in sensor_types
        assert "DysonNO2Sensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_setup_environmental_data_with_pm10_data(self):
        """Test PM10 sensor created with EnvironmentalData capability and p10r data."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["EnvironmentalData"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TP02-002"
        coordinator.data = {"environmental-data": {"p10r": "28", "tact": "2950"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        # PM10 sensor should be created with EnvironmentalData capability
        assert "DysonPM10Sensor" in sensor_types
        # But ExtendedAQ-only sensors should not be created
        assert "DysonCO2Sensor" not in sensor_types
        assert "DysonVOCSensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_setup_environmental_data_with_both_pm_sensors(self):
        """Test both PM2.5 and PM10 sensors created with EnvironmentalData capability."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["EnvironmentalData"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TP02-003"
        coordinator.data = {
            "environmental-data": {
                "p25r": "15",
                "p10r": "28",
                "tact": "2950",
                "hact": "55",
            }
        }

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        # Both PM sensors should be created with EnvironmentalData capability
        assert "DysonPM25Sensor" in sensor_types
        assert "DysonPM10Sensor" in sensor_types
        # Temperature and humidity sensors should also be created
        assert "DysonTemperatureSensor" in sensor_types
        assert "DysonHumiditySensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_environmental_data_without_pm_data(self):
        """Test PM sensors NOT created when EnvironmentalData has no PM data."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["EnvironmentalData"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-012"
        coordinator.data = {
            "environmental-data": {"tact": "2950", "hact": "55"}  # No PM data
        }

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        # PM sensors should NOT be created without data
        assert "DysonPM25Sensor" not in sensor_types
        assert "DysonPM10Sensor" not in sensor_types
        # Temperature and humidity should still be created
        assert "DysonTemperatureSensor" in sensor_types
        assert "DysonHumiditySensor" in sensor_types


class TestSensorSetupCategoryPaths:
    """Test sensor creation based on device category."""

    @pytest.mark.asyncio
    async def test_setup_wifi_sensors_for_ec_category(self):
        """Test WiFi sensors created for ec category devices."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []
        coordinator.device_category = ["ec"]  # EC category
        coordinator.serial_number = "TEST-EC-001"
        coordinator.data = {}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonWiFiSensor" in sensor_types
        assert "DysonConnectionStatusSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_wifi_sensors_for_robot_category(self):
        """Test WiFi sensors created for robot category devices."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []
        coordinator.device_category = ["robot"]  # Robot category
        coordinator.serial_number = "TEST-ROBOT-001"
        coordinator.data = {}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonWiFiSensor" in sensor_types
        assert "DysonConnectionStatusSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_no_wifi_sensors_for_other_categories(self):
        """Test WiFi sensors NOT created for non-ec/robot categories."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []
        coordinator.device_category = ["fan"]  # Not ec or robot
        coordinator.serial_number = "TEST-FAN-001"
        coordinator.data = {}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonWiFiSensor" not in sensor_types
        assert "DysonConnectionStatusSensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_setup_robot_category_battery_log(self):
        """Test robot category logs battery message."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []
        coordinator.device_category = ["robot"]
        coordinator.serial_number = "TEST-ROBOT-002"
        coordinator.data = {}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act - should log message about adding battery sensor for robot device
        with patch("custom_components.hass_dyson.sensor._LOGGER") as mock_logger:
            result = await async_setup_entry(hass, config_entry, async_add_entities)

            # Assert
            assert result is True
            # Check that debug message about robot battery sensor was logged
            assert any(
                "Adding battery sensor for robot device" in str(call)
                for call in mock_logger.debug.call_args_list
            )


class TestSensorSetupFilterPaths:
    """Test filter sensor creation logic."""

    @pytest.mark.asyncio
    async def test_setup_hepa_filters_with_extended_aq(self):
        """Test HEPA filter sensors created with ExtendedAQ capability."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["ExtendedAQ"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-HEPA-001"
        coordinator.data = {}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonHEPAFilterLifeSensor" in sensor_types
        assert "DysonHEPAFilterTypeSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_no_hepa_filters_without_extended_aq(self):
        """Test HEPA filter sensors NOT created without ExtendedAQ capability."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []  # No ExtendedAQ
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-NO-HEPA-001"
        coordinator.data = {}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonHEPAFilterLifeSensor" not in sensor_types
        assert "DysonHEPAFilterTypeSensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_setup_carbon_filters_with_filter_data(self):
        """Test carbon filter sensors created when cflt data present and valid."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-CARBON-001"
        coordinator.data = {"product-state": {"cflt": "CARF"}}  # Valid carbon filter

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonCarbonFilterLifeSensor" in sensor_types
        assert "DysonCarbonFilterTypeSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_no_carbon_filters_when_cflt_none(self):
        """Test carbon filter sensors NOT created when cflt is NONE."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-NO-CARBON-001"
        coordinator.data = {"product-state": {"cflt": "NONE"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonCarbonFilterLifeSensor" not in sensor_types
        assert "DysonCarbonFilterTypeSensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_setup_no_carbon_filters_when_cflt_scog(self):
        """Test carbon filter sensors NOT created when cflt is SCOG."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-NO-CARBON-002"
        coordinator.data = {"product-state": {"cflt": "SCOG"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonCarbonFilterLifeSensor" not in sensor_types
        assert "DysonCarbonFilterTypeSensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_setup_no_carbon_filters_when_cflt_missing(self):
        """Test carbon filter sensors NOT created when cflt key is missing."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-NO-CARBON-003"
        coordinator.data = {"product-state": {}}  # No cflt key

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonCarbonFilterLifeSensor" not in sensor_types
        assert "DysonCarbonFilterTypeSensor" not in sensor_types


class TestSensorSetupTemperatureHumidity:
    """Test temperature and humidity sensor creation logic."""

    @pytest.mark.asyncio
    async def test_setup_temperature_with_heating_capability_and_data(self):
        """Test temperature sensor created with heating capability and tact data."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["heating"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-TEMP-001"
        coordinator.data = {"environmental-data": {"tact": "2985"}}  # Temperature data

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonTemperatureSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_temperature_with_environmental_capability_and_data(self):
        """Test temperature sensor created with EnvironmentalData capability and tact data."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["EnvironmentalData"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-TEMP-002"
        coordinator.data = {"environmental-data": {"tact": "2950"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonTemperatureSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_no_temperature_with_capability_but_no_data(self):
        """Test temperature sensor NOT created with capability but no tact data."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["heating"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-NO-TEMP-001"
        coordinator.data = {"environmental-data": {}}  # No tact key

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonTemperatureSensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_setup_no_temperature_without_capability(self):
        """Test temperature sensor NOT created without heating/environmental capability."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []  # No capability
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-NO-TEMP-002"
        coordinator.data = {"environmental-data": {"tact": "2985"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonTemperatureSensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_setup_humidity_with_humidifier_capability_and_data(self):
        """Test humidity sensor created with Humidifier capability and hact data."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["Humidifier"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-HUMID-001"
        coordinator.data = {"environmental-data": {"hact": "45"}}  # Humidity data

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonHumiditySensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_humidity_with_environmental_capability_and_data(self):
        """Test humidity sensor created with EnvironmentalData capability and hact data."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["EnvironmentalData"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-HUMID-002"
        coordinator.data = {"environmental-data": {"hact": "52"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonHumiditySensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_no_humidity_with_capability_but_no_data(self):
        """Test humidity sensor NOT created with capability but no hact data."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["Humidifier"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-NO-HUMID-001"
        coordinator.data = {"environmental-data": {}}  # No hact key

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonHumiditySensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_setup_no_humidity_without_capability(self):
        """Test humidity sensor NOT created without humidifier/environmental capability."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []  # No capability
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-NO-HUMID-002"
        coordinator.data = {"environmental-data": {"hact": "45"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonHumiditySensor" not in sensor_types


class TestSensorSetupFormaldehydeVOCPaths:
    """Test formaldehyde and VOC sensor creation with Formaldehyde/VOC capabilities."""

    @pytest.mark.asyncio
    async def test_setup_formaldehyde_capability_without_extended_aq(self):
        """Test Formaldehyde sensor created with Formaldehyde capability (no ExtendedAQ)."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["Formaldehyde"]  # Formaldehyde only
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-FORM-001"
        coordinator.data = {}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        # Should create formaldehyde sensor for UI testing
        assert "DysonFormaldehydeSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_formaldehyde_capability_with_extended_aq_skipped(self):
        """Test Formaldehyde sensor NOT created when both Formaldehyde and ExtendedAQ present (no duplicate)."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = [
            "Formaldehyde",
            "ExtendedAQ",
        ]  # Both capabilities
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-FORM-002"
        coordinator.data = {}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        with patch("custom_components.hass_dyson.sensor._LOGGER") as mock_logger:
            result = await async_setup_entry(hass, config_entry, async_add_entities)

            # Assert
            assert result is True
            # Should log that formaldehyde is already covered by ExtendedAQ
            assert any(
                "already covered by ExtendedAQ" in str(call)
                for call in mock_logger.debug.call_args_list
            )

    @pytest.mark.asyncio
    async def test_setup_no_formaldehyde_without_capability(self):
        """Test Formaldehyde sensor NOT created without Formaldehyde or ExtendedAQ capability."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []  # No Formaldehyde capability
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-NO-FORM-001"
        coordinator.data = {"environmental-data": {"hchr": "0"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonFormaldehydeSensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_setup_voc_capability_without_extended_aq(self):
        """Test VOC/NO2/CO2 sensors created with VOC capability (no ExtendedAQ)."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["VOC"]  # VOC only
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-VOC-001"
        coordinator.data = {}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        # Should create all gas sensors for UI testing
        assert "DysonVOCSensor" in sensor_types
        assert "DysonNO2Sensor" in sensor_types
        assert "DysonCO2Sensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_voc_capability_with_extended_aq_skipped(self):
        """Test gas sensors NOT created when both VOC and ExtendedAQ present (no duplicate)."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["VOC", "ExtendedAQ"]  # Both capabilities
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-VOC-002"
        coordinator.data = {}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        with patch("custom_components.hass_dyson.sensor._LOGGER") as mock_logger:
            result = await async_setup_entry(hass, config_entry, async_add_entities)

            # Assert
            assert result is True
            # Should log that gas sensors are already covered by ExtendedAQ
            assert any(
                "already covered by ExtendedAQ" in str(call)
                for call in mock_logger.debug.call_args_list
            )

    @pytest.mark.asyncio
    async def test_setup_no_voc_without_capability(self):
        """Test gas sensors NOT created without VOC or ExtendedAQ capability."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []  # No VOC capability
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-NO-VOC-001"
        coordinator.data = {"environmental-data": {"va10": "1500"}}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonVOCSensor" not in sensor_types
        assert "DysonNO2Sensor" not in sensor_types
        assert "DysonCO2Sensor" not in sensor_types


class TestSensorSetupHumidifierPaths:
    """Test humidifier-specific sensor creation."""

    @pytest.mark.asyncio
    async def test_setup_humidifier_sensors_with_capability(self):
        """Test humidifier sensors created with Humidifier capability."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = ["Humidifier"]
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-HUM-001"
        coordinator.data = {}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonNextCleaningCycleSensor" in sensor_types
        assert "DysonCleaningTimeRemainingSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_setup_no_humidifier_sensors_without_capability(self):
        """Test humidifier sensors NOT created without Humidifier capability."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []  # No Humidifier capability
        coordinator.device_category = ["ec"]
        coordinator.serial_number = "TEST-NO-HUM-001"
        coordinator.data = {}

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        result = await async_setup_entry(hass, config_entry, async_add_entities)

        # Assert
        assert result is True
        entities = async_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in entities]
        assert "DysonNextCleaningCycleSensor" not in sensor_types
        assert "DysonCleaningTimeRemainingSensor" not in sensor_types


class TestSensorSetupErrorHandling:
    """Test error handling in async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_keyerror_in_capability_check(self):
        """Test KeyError handling when capability data is malformed."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        # Make device_capabilities raise KeyError
        type(coordinator).device_capabilities = property(lambda self: [][999])
        coordinator.serial_number = "TEST-ERR-001"

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        with patch("custom_components.hass_dyson.sensor._LOGGER") as mock_logger:
            result = await async_setup_entry(hass, config_entry, async_add_entities)

            # Assert - should handle gracefully
            assert result is True
            mock_logger.warning.assert_called()
            # Should fall back to empty entities list
            async_add_entities.assert_called_with([], True)

    @pytest.mark.asyncio
    async def test_setup_attribute_error_in_coordinator_access(self):
        """Test AttributeError handling when coordinator has missing attributes."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        # Remove device_capabilities attribute
        del coordinator.device_capabilities
        coordinator.serial_number = "TEST-ERR-002"

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        with patch("custom_components.hass_dyson.sensor._LOGGER") as mock_logger:
            result = await async_setup_entry(hass, config_entry, async_add_entities)

            # Assert
            assert result is True
            mock_logger.warning.assert_called()
            async_add_entities.assert_called_with([], True)

    @pytest.mark.asyncio
    async def test_setup_value_error_in_data_processing(self):
        """Test ValueError handling during sensor setup."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []
        coordinator.device_category = []
        coordinator.serial_number = "TEST-ERR-003"
        # Make data.get raise ValueError
        coordinator.data = MagicMock()
        coordinator.data.get = MagicMock(side_effect=ValueError("Data error"))

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        with patch("custom_components.hass_dyson.sensor._LOGGER") as mock_logger:
            result = await async_setup_entry(hass, config_entry, async_add_entities)

            # Assert
            assert result is True
            mock_logger.error.assert_called()
            async_add_entities.assert_called_with([], True)

    @pytest.mark.asyncio
    async def test_setup_type_error_in_data_processing(self):
        """Test TypeError handling during sensor setup."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []
        coordinator.device_category = []
        coordinator.serial_number = "TEST-ERR-004"
        # Make data.get raise TypeError
        coordinator.data = MagicMock()
        coordinator.data.get = MagicMock(side_effect=TypeError("Type error"))

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        with patch("custom_components.hass_dyson.sensor._LOGGER") as mock_logger:
            result = await async_setup_entry(hass, config_entry, async_add_entities)

            # Assert
            assert result is True
            mock_logger.error.assert_called()
            async_add_entities.assert_called_with([], True)

    @pytest.mark.asyncio
    async def test_setup_generic_exception_handling(self):
        """Test generic Exception handling during sensor setup."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        async_add_entities = MagicMock()

        coordinator = MagicMock()
        coordinator.device_capabilities = []
        coordinator.device_category = []
        coordinator.serial_number = "TEST-ERR-005"
        # Make data.get raise generic Exception
        coordinator.data = MagicMock()
        coordinator.data.get = MagicMock(side_effect=Exception("Unexpected error"))

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}

        # Act
        with patch("custom_components.hass_dyson.sensor._LOGGER") as mock_logger:
            result = await async_setup_entry(hass, config_entry, async_add_entities)

            # Assert
            assert result is True
            mock_logger.error.assert_called()
            mock_logger.warning.assert_called()
            async_add_entities.assert_called_with([], True)
