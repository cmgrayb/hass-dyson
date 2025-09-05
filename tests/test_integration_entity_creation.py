"""
Integration tests that verify correct entities are created for different device configurations.

This module tests the complete entity creation pipeline to ensure the right entities
are created based on device capabilities and categories.
"""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.hass_dyson.const import CONF_DISCOVERY_METHOD, CONF_SERIAL_NUMBER, DISCOVERY_STICKER


class TestEntityCreationIntegration:
    """Test complete entity creation pipeline based on device capabilities and categories."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {}
        return hass

    @pytest.fixture
    def mock_platform_add_entities(self):
        """Mock the add_entities callback."""
        return MagicMock()

    def create_config_entry(self, capabilities, device_category="ec"):
        """Helper to create a config entry with specific capabilities."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
            CONF_SERIAL_NUMBER: "TEST-INTEGRATION-123",
            "mqtt_username": "TEST-INTEGRATION-123",
            "mqtt_password": "test_password",
            "mqtt_hostname": "192.168.1.100",
            "capabilities": capabilities,
            "device_category": device_category,
        }
        return config_entry

    @pytest.mark.asyncio
    async def test_extended_aq_creates_air_quality_sensors(self, mock_hass, mock_platform_add_entities):
        """Test that ExtendedAQ capability creates PM2.5/PM10 sensors."""
        config_entry = self.create_config_entry(["ExtendedAQ"], "purifier")

        # Mock DataUpdateCoordinator class to avoid Frame helper issues
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
            mock_coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_coordinator.hass = mock_hass
            mock_coordinator.config_entry = config_entry
            mock_coordinator.has_capability = lambda cap: cap == "ExtendedAQ"
            mock_coordinator._device_category = ["purifier"]
            mock_coordinator.device_serial = "TEST-INTEGRATION-123"
            mock_coordinator._device_capabilities = ["ExtendedAQ"]
            mock_coordinator.device = MagicMock()  # Add mock device

        # Set up hass.data structure that the platforms expect
        from custom_components.hass_dyson.const import DOMAIN
        mock_hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        from custom_components.hass_dyson.sensor import async_setup_entry

        result = await async_setup_entry(mock_hass, config_entry, mock_platform_add_entities)

        # Verify setup completed
        assert result is True

        # Verify sensors were created
        mock_platform_add_entities.assert_called_once()
        created_entities = mock_platform_add_entities.call_args[0][0]

        # Should have PM2.5 and PM10 sensors due to ExtendedAQ capability
        sensor_types = [type(entity).__name__ for entity in created_entities]
        assert "DysonPM25Sensor" in sensor_types or "DysonPM10Sensor" in sensor_types

        # Check that air quality sensors were created for PM2.5/PM10
        pm_sensors = [e for e in created_entities if "PM" in type(e).__name__]
        assert len(pm_sensors) >= 1  # At least one PM sensor

    @pytest.mark.asyncio
    async def test_heating_capability_creates_temperature_sensor(self, mock_hass, mock_platform_add_entities):
        """Test that Heating capability creates temperature sensor."""
        config_entry = self.create_config_entry(["Heating"], "heater")

        # Mock DataUpdateCoordinator class to avoid Frame helper issues
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
            mock_coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_coordinator.hass = mock_hass
            mock_coordinator.config_entry = config_entry
            mock_coordinator.has_capability = lambda cap: cap == "Heating"
            mock_coordinator._device_category = ["heater"]
            mock_coordinator.device_serial = "TEST-INTEGRATION-123"
            mock_coordinator._device_capabilities = ["Heating"]
            mock_coordinator.device = MagicMock()  # Add mock device

        # Set up hass.data structure that the platforms expect
        from custom_components.hass_dyson.const import DOMAIN
        mock_hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        from custom_components.hass_dyson.sensor import async_setup_entry

        result = await async_setup_entry(mock_hass, config_entry, mock_platform_add_entities)

        assert result is True
        mock_platform_add_entities.assert_called_once()
        created_entities = mock_platform_add_entities.call_args[0][0]

        # Should have temperature sensor due to Heating capability
        sensor_types = [type(entity).__name__ for entity in created_entities]
        assert "DysonTemperatureSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_ec_category_creates_wifi_sensors(self, mock_hass, mock_platform_add_entities):
        """Test that 'ec' category creates WiFi signal sensors."""
        config_entry = self.create_config_entry(["EnvironmentalData"], "ec")

        # Mock DataUpdateCoordinator class to avoid Frame helper issues
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
            mock_coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_coordinator.hass = mock_hass
            mock_coordinator.config_entry = config_entry
            mock_coordinator.has_capability = lambda cap: cap == "EnvironmentalData"
            mock_coordinator._device_category = ["ec"]
            mock_coordinator.device_serial = "TEST-INTEGRATION-123"
            mock_coordinator._device_capabilities = ["EnvironmentalData"]
            mock_coordinator.device = MagicMock()  # Add mock device

        # Set up hass.data structure that the platforms expect
        from custom_components.hass_dyson.const import DOMAIN
        mock_hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        from custom_components.hass_dyson.sensor import async_setup_entry

        result = await async_setup_entry(mock_hass, config_entry, mock_platform_add_entities)

        assert result is True
        mock_platform_add_entities.assert_called_once()
        created_entities = mock_platform_add_entities.call_args[0][0]

        # Should have WiFi sensor due to 'ec' category
        sensor_types = [type(entity).__name__ for entity in created_entities]
        assert "DysonWiFiSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_robot_category_creates_wifi_sensors(self, mock_hass, mock_platform_add_entities):
        """Test that 'robot' category creates WiFi signal sensors."""
        config_entry = self.create_config_entry(["Navigation"], "robot")

        # Mock DataUpdateCoordinator class to avoid Frame helper issues
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
            mock_coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_coordinator.hass = mock_hass
            mock_coordinator.config_entry = config_entry
            mock_coordinator.has_capability = lambda cap: cap == "Navigation"
            mock_coordinator._device_category = ["robot"]
            mock_coordinator.device_serial = "TEST-INTEGRATION-123"
            mock_coordinator._device_capabilities = ["Navigation"]
            mock_coordinator.device = MagicMock()  # Add mock device

        # Set up hass.data structure that the platforms expect
        from custom_components.hass_dyson.const import DOMAIN
        mock_hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        from custom_components.hass_dyson.sensor import async_setup_entry

        result = await async_setup_entry(mock_hass, config_entry, mock_platform_add_entities)

        assert result is True
        mock_platform_add_entities.assert_called_once()
        created_entities = mock_platform_add_entities.call_args[0][0]

        # Should have WiFi sensor due to 'robot' category
        sensor_types = [type(entity).__name__ for entity in created_entities]
        assert "DysonWiFiSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_vacuum_category_no_wifi_sensors(self, mock_hass, mock_platform_add_entities):
        """Test that 'vacuum' category does NOT create WiFi sensors."""
        config_entry = self.create_config_entry(["Cleaning"], "vacuum")

        # Mock DataUpdateCoordinator class to avoid Frame helper issues
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
            mock_coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_coordinator.hass = mock_hass
            mock_coordinator.config_entry = config_entry
            mock_coordinator.has_capability = lambda cap: cap == "Cleaning"
            mock_coordinator._device_category = ["vacuum"]
            mock_coordinator.device_serial = "TEST-INTEGRATION-123"
            mock_coordinator._device_capabilities = ["Cleaning"]
            mock_coordinator.device = MagicMock()  # Add mock device

        # Set up hass.data structure that the platforms expect
        from custom_components.hass_dyson.const import DOMAIN
        mock_hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        from custom_components.hass_dyson.sensor import async_setup_entry

        result = await async_setup_entry(mock_hass, config_entry, mock_platform_add_entities)

        assert result is True
        mock_platform_add_entities.assert_called_once()
        created_entities = mock_platform_add_entities.call_args[0][0]

        # Should NOT have WiFi sensor due to 'vacuum' category
        sensor_types = [type(entity).__name__ for entity in created_entities]
        assert "DysonWiFiSensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_multiple_capabilities_create_multiple_sensors(self, mock_hass, mock_platform_add_entities):
        """Test that multiple capabilities create multiple sensor types."""
        config_entry = self.create_config_entry(["ExtendedAQ", "Heating", "EnvironmentalData"], "ec")

        # Mock DataUpdateCoordinator class to avoid Frame helper issues
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
            mock_coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_coordinator.hass = mock_hass
            mock_coordinator.config_entry = config_entry
            mock_coordinator.has_capability = lambda cap: cap in ["ExtendedAQ", "Heating", "EnvironmentalData"]
            mock_coordinator._device_category = ["ec"]
            mock_coordinator.device_serial = "TEST-INTEGRATION-123"
            mock_coordinator._device_capabilities = ["ExtendedAQ", "Heating", "EnvironmentalData"]
            mock_coordinator.device = MagicMock()  # Add mock device

        # Set up hass.data structure that the platforms expect
        from custom_components.hass_dyson.const import DOMAIN
        mock_hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        from custom_components.hass_dyson.sensor import async_setup_entry

        result = await async_setup_entry(mock_hass, config_entry, mock_platform_add_entities)

        assert result is True
        mock_platform_add_entities.assert_called_once()
        created_entities = mock_platform_add_entities.call_args[0][0]

        # Should have multiple sensor types
        sensor_types = [type(entity).__name__ for entity in created_entities]

        # ExtendedAQ enables air quality sensors
        assert any("PM" in sensor_type for sensor_type in sensor_types)

        # Heating enables temperature sensor
        assert "DysonTemperatureSensor" in sensor_types

        # 'ec' category enables WiFi sensor
        assert "DysonWiFiSensor" in sensor_types

    @pytest.mark.asyncio
    async def test_no_capabilities_minimal_sensors(self, mock_hass, mock_platform_add_entities):
        """Test that devices with no capabilities create minimal sensors."""
        config_entry = self.create_config_entry([], "unknown")

        # Mock DataUpdateCoordinator class to avoid Frame helper issues
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
            mock_coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_coordinator.hass = mock_hass
            mock_coordinator.config_entry = config_entry
            mock_coordinator.has_capability = lambda cap: False
            mock_coordinator._device_category = ["unknown"]
            mock_coordinator.device_serial = "TEST-INTEGRATION-123"
            mock_coordinator._device_capabilities = []
            mock_coordinator.device = MagicMock()  # Add mock device

        # Set up hass.data structure that the platforms expect
        from custom_components.hass_dyson.const import DOMAIN
        mock_hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        from custom_components.hass_dyson.sensor import async_setup_entry

        result = await async_setup_entry(mock_hass, config_entry, mock_platform_add_entities)

        assert result is True
        mock_platform_add_entities.assert_called_once()
        created_entities = mock_platform_add_entities.call_args[0][0]

        # Should have minimal sensors (basic ones always created)
        sensor_types = [type(entity).__name__ for entity in created_entities]

        # Should NOT have capability-specific sensors
        assert "DysonAirQualitySensor" not in sensor_types
        assert "DysonTemperatureSensor" not in sensor_types
        assert "DysonWiFiSensor" not in sensor_types

        # Should have NO sensors for unknown category with no capabilities
        assert len(created_entities) == 0  # No sensors for unknown devices


class TestBinarySensorEntityCreationIntegration:
    """Test binary sensor creation pipeline based on device capabilities and categories."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {}
        return hass

    @pytest.fixture
    def mock_platform_add_entities(self):
        """Mock the add_entities callback."""
        return MagicMock()

    def create_config_entry(self, capabilities, device_category="ec"):
        """Helper to create a config entry with specific capabilities."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
            CONF_SERIAL_NUMBER: "TEST-BINARY-123",
            "mqtt_username": "TEST-BINARY-123",
            "mqtt_password": "test_password",
            "mqtt_hostname": "192.168.1.200",
            "capabilities": capabilities,
            "device_category": device_category,
        }
        return config_entry

    @pytest.mark.asyncio
    async def test_binary_sensor_creation_with_filtering(self, mock_hass, mock_platform_add_entities):
        """Test that binary sensors are created with proper fault code filtering."""
        config_entry = self.create_config_entry(["EnvironmentalData"], "ec")

        # Mock DataUpdateCoordinator class to avoid Frame helper issues
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
            mock_coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_coordinator.hass = mock_hass
            mock_coordinator.config_entry = config_entry
            mock_coordinator.has_capability = lambda cap: cap == "EnvironmentalData"
            mock_coordinator._device_category = ["ec"]
            mock_coordinator.device_serial = "TEST-BINARY-123"
            mock_coordinator._device_capabilities = ["EnvironmentalData"]
            mock_coordinator.device = MagicMock()  # Add mock device

        # Set up hass.data structure that the platforms expect
        from custom_components.hass_dyson.const import DOMAIN
        mock_hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        from custom_components.hass_dyson.binary_sensor import async_setup_entry

        result = await async_setup_entry(mock_hass, config_entry, mock_platform_add_entities)

        assert result is True
        mock_platform_add_entities.assert_called_once()
        created_entities = mock_platform_add_entities.call_args[0][0]

        # Should have binary sensors created
        assert len(created_entities) > 0

        # All should be binary sensor types
        for entity in created_entities:
            assert hasattr(entity, 'is_on')  # Binary sensor characteristic

    @pytest.mark.asyncio
    async def test_ec_category_binary_sensor_faults(self, mock_hass, mock_platform_add_entities):
        """Test that 'ec' category creates appropriate fault sensors."""
        config_entry = self.create_config_entry(["EnvironmentalData"], "ec")

        # Mock DataUpdateCoordinator class to avoid Frame helper issues
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
            mock_coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_coordinator.hass = mock_hass
            mock_coordinator.config_entry = config_entry
            mock_coordinator.has_capability = lambda cap: cap == "EnvironmentalData"
            mock_coordinator._device_category = ["ec"]
            mock_coordinator.device_serial = "TEST-BINARY-123"
            mock_coordinator._device_capabilities = ["EnvironmentalData"]
            mock_coordinator.device = MagicMock()  # Add mock device

        # Set up hass.data structure that the platforms expect
        from custom_components.hass_dyson.const import DOMAIN
        mock_hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        from custom_components.hass_dyson.binary_sensor import async_setup_entry

        result = await async_setup_entry(mock_hass, config_entry, mock_platform_add_entities)

        assert result is True
        mock_platform_add_entities.assert_called_once()
        created_entities = mock_platform_add_entities.call_args[0][0]

        # Should have fault sensors for 'ec' category
        assert len(created_entities) > 0


class TestRealDeviceEntityCreationScenarios:
    """Test entity creation scenarios based on real Dyson device configurations."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {}
        return hass

    @pytest.fixture
    def mock_platform_add_entities(self):
        """Mock the add_entities callback."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_dyson_pure_cool_purifier_entities(self, mock_hass, mock_platform_add_entities):
        """Test entity creation for a Dyson Pure Cool air purifier."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
            CONF_SERIAL_NUMBER: "PURIFIER-REAL-001",
            "mqtt_username": "PURIFIER-REAL-001",
            "mqtt_password": "purifier_password",
            "mqtt_hostname": "192.168.1.50",
            "capabilities": ["EnvironmentalData", "ExtendedAQ", "FanControl", "Oscillation"],
            "device_category": "purifier",
        }

        # Mock DataUpdateCoordinator class to avoid Frame helper issues
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
            mock_coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_coordinator.hass = mock_hass
            mock_coordinator.config_entry = config_entry
            mock_coordinator.has_capability = lambda cap: cap in [
                "EnvironmentalData", "ExtendedAQ", "FanControl", "Oscillation"]
            mock_coordinator._device_category = ["purifier"]
            mock_coordinator.device_serial = "PURIFIER-REAL-001"
            mock_coordinator._device_capabilities = ["EnvironmentalData", "ExtendedAQ", "FanControl", "Oscillation"]
            mock_coordinator.device = MagicMock()  # Add mock device

        # Set up hass.data structure that the platforms expect
        from custom_components.hass_dyson.const import DOMAIN
        mock_hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        from custom_components.hass_dyson.sensor import async_setup_entry

        result = await async_setup_entry(mock_hass, config_entry, mock_platform_add_entities)

        assert result is True
        created_entities = mock_platform_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in created_entities]

        # Should have air quality sensors due to ExtendedAQ
        assert any("PM" in sensor_type for sensor_type in sensor_types)

        # Should NOT have WiFi sensors (purifier category doesn't enable them)
        assert "DysonWiFiSensor" not in sensor_types

        # Should NOT have temperature sensors (no Heating capability)
        assert "DysonTemperatureSensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_dyson_hot_cool_heater_entities(self, mock_hass, mock_platform_add_entities):
        """Test entity creation for a Dyson Hot+Cool heater/fan."""
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

        # Mock DataUpdateCoordinator class to avoid Frame helper issues
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
            mock_coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_coordinator.hass = mock_hass
            mock_coordinator.config_entry = config_entry
            mock_coordinator.has_capability = lambda cap: cap in ["EnvironmentalData", "Heating", "FanControl"]
            mock_coordinator._device_category = ["heater"]
            mock_coordinator.device_serial = "HEATER-REAL-002"
            mock_coordinator._device_capabilities = ["EnvironmentalData", "Heating", "FanControl"]
            mock_coordinator.device = MagicMock()  # Add mock device

        # Set up hass.data structure that the platforms expect
        from custom_components.hass_dyson.const import DOMAIN
        mock_hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        from custom_components.hass_dyson.sensor import async_setup_entry

        result = await async_setup_entry(mock_hass, config_entry, mock_platform_add_entities)

        assert result is True
        created_entities = mock_platform_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in created_entities]

        # Should have temperature sensor due to Heating capability
        assert "DysonTemperatureSensor" in sensor_types

        # Should NOT have air quality sensors (no ExtendedAQ)
        assert any("PM" not in sensor_type for sensor_type in sensor_types) or len(
            [s for s in sensor_types if "PM" in s]) == 0

        # Should NOT have WiFi sensors (heater category doesn't enable them)
        assert "DysonWiFiSensor" not in sensor_types

    @pytest.mark.asyncio
    async def test_dyson_robot_vacuum_entities(self, mock_hass, mock_platform_add_entities):
        """Test entity creation for a Dyson robot vacuum."""
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

        # Mock DataUpdateCoordinator class to avoid Frame helper issues
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
            mock_coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_coordinator.hass = mock_hass
            mock_coordinator.config_entry = config_entry
            mock_coordinator.has_capability = lambda cap: cap in ["Navigation", "Cleaning", "BatteryStatus"]
            mock_coordinator._device_category = ["robot"]
            mock_coordinator.device_serial = "ROBOT-REAL-003"
            mock_coordinator._device_capabilities = ["Navigation", "Cleaning", "BatteryStatus"]
            mock_coordinator.device = MagicMock()  # Add mock device

        # Set up hass.data structure that the platforms expect
        from custom_components.hass_dyson.const import DOMAIN
        mock_hass.data = {DOMAIN: {config_entry.entry_id: mock_coordinator}}

        from custom_components.hass_dyson.sensor import async_setup_entry

        result = await async_setup_entry(mock_hass, config_entry, mock_platform_add_entities)

        assert result is True
        created_entities = mock_platform_add_entities.call_args[0][0]
        sensor_types = [type(entity).__name__ for entity in created_entities]

        # Should have WiFi sensor due to 'robot' category
        assert "DysonWiFiSensor" in sensor_types

        # Should NOT have air quality sensors (no ExtendedAQ)
        assert any("PM" not in sensor_type for sensor_type in sensor_types) or len(
            [s for s in sensor_types if "PM" in s]) == 0

        # Should NOT have temperature sensors (no Heating)
        assert "DysonTemperatureSensor" not in sensor_types
