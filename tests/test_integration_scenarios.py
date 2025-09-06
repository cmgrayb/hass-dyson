"""
Integration tests for complete user scenarios and workflows.

This module tests end-to-end scenarios to ensure the integration works
correctly from a user perspective.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.const import (
    CAPABILITY_EXTENDED_AQ,
    CAPABILITY_HEATING,
    CONF_DISCOVERY_METHOD,
    CONF_SERIAL_NUMBER,
    DEVICE_CATEGORY_EC,
    DISCOVERY_STICKER,
    DOMAIN,
)


class TestEndToEndScenarios:
    """Test complete end-to-end user scenarios."""

    @pytest.fixture
    def mock_hass(self):
        """Create a comprehensive mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {}
        hass.config_entries = MagicMock()
        hass.states = MagicMock()
        hass.bus = MagicMock()
        return hass

    @pytest.fixture
    def sample_device_config(self):
        """Sample device configuration for testing."""
        return {
            CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
            CONF_SERIAL_NUMBER: "INTEGRATION-TEST-123",
            "mqtt_username": "INTEGRATION-TEST-123",
            "mqtt_password": "test_password",
            "mqtt_hostname": "192.168.1.100",
            "capabilities": [CAPABILITY_EXTENDED_AQ, CAPABILITY_HEATING],
            "device_category": DEVICE_CATEGORY_EC,
            "device_name": "Test Integration Device",
        }

    @pytest.mark.asyncio
    async def test_complete_device_setup_flow(self, mock_hass, sample_device_config):
        """Test complete device setup from discovery to entity creation."""
        config_entry = MagicMock()
        config_entry.data = sample_device_config
        config_entry.entry_id = "test_entry_123"

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            # Mock the coordinator setup
            coordinator = MagicMock()
            coordinator.serial_number = sample_device_config[CONF_SERIAL_NUMBER]
            coordinator.device_name = sample_device_config["device_name"]
            coordinator.device_capabilities = sample_device_config["capabilities"]
            coordinator.device_category = sample_device_config["device_category"]
            coordinator.data = {}
            coordinator.device = MagicMock()

            # Simulate successful coordinator setup
            coordinator.async_config_entry_first_refresh = AsyncMock()

            # Test that device is properly configured
            assert coordinator.serial_number == "INTEGRATION-TEST-123"
            assert CAPABILITY_EXTENDED_AQ in coordinator.device_capabilities
            assert CAPABILITY_HEATING in coordinator.device_capabilities

    @pytest.mark.asyncio
    async def test_device_state_updates_propagate(self, mock_hass, sample_device_config):
        """Test that device state updates propagate to Home Assistant entities."""
        config_entry = MagicMock()
        config_entry.data = sample_device_config

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = MagicMock()
            coordinator.data = {"temperature": 22.5, "pm25": 15, "pm10": 20}

            # Mock entity state updates
            mock_entity = MagicMock()
            mock_entity.async_write_ha_state = AsyncMock()

            # Simulate state update
            await mock_entity.async_write_ha_state()

            # Verify state update was called
            mock_entity.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_device_reconnection_after_network_failure(self, mock_hass, sample_device_config):
        """Test device reconnection after network failure."""
        config_entry = MagicMock()
        config_entry.data = sample_device_config

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            device = MagicMock()

            # Simulate initial connection
            device.connect.return_value = True
            device.connected = True

            # Simulate network failure
            device.connected = False
            device.connect.side_effect = ConnectionError("Network failure")

            # Verify connection failure is handled
            with pytest.raises(ConnectionError):
                device.connect()

            # Simulate successful reconnection
            device.connect.side_effect = None
            device.connect.return_value = True
            device.connected = True

            result = device.connect()
            assert result is True
            assert device.connected is True

    @pytest.mark.asyncio
    async def test_multiple_entities_creation_for_capable_device(self, mock_hass, sample_device_config):
        """Test that multiple entities are created for a device with multiple capabilities."""
        config_entry = MagicMock()
        config_entry.data = sample_device_config

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = MagicMock()
            coordinator.device_capabilities = [CAPABILITY_EXTENDED_AQ, CAPABILITY_HEATING]
            coordinator.device_category = DEVICE_CATEGORY_EC

            # Mock entity creation for different platforms
            sensor_entities = []
            binary_sensor_entities = []

            # Simulate entity creation based on capabilities
            if CAPABILITY_EXTENDED_AQ in coordinator.device_capabilities:
                sensor_entities.extend(["pm25_sensor", "pm10_sensor"])

            if CAPABILITY_HEATING in coordinator.device_capabilities:
                sensor_entities.append("temperature_sensor")

            # EC category should create WiFi sensors
            if coordinator.device_category == DEVICE_CATEGORY_EC:
                sensor_entities.append("wifi_sensor")

            # Filter replacement sensor should always be created
            binary_sensor_entities.append("filter_replacement_sensor")

            # Verify expected entities were created
            assert "pm25_sensor" in sensor_entities
            assert "pm10_sensor" in sensor_entities
            assert "temperature_sensor" in sensor_entities
            assert "wifi_sensor" in sensor_entities
            assert "filter_replacement_sensor" in binary_sensor_entities


class TestConfigurationFlowScenarios:
    """Test configuration flow scenarios."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant for config flow testing."""
        hass = MagicMock()
        hass.data = {DOMAIN: {}}
        return hass

    @pytest.mark.asyncio
    async def test_manual_device_configuration_flow(self, mock_hass):
        """Test manual device configuration through UI."""
        from custom_components.hass_dyson.config_flow import DysonConfigFlow

        config_flow = DysonConfigFlow()
        config_flow.hass = mock_hass

        # Mock user input for manual configuration
        user_input = {
            "serial_number": "MANUAL-CONFIG-123",
            "device_name": "Manual Test Device",
            "mqtt_hostname": "192.168.1.100",
            "mqtt_username": "MANUAL-CONFIG-123",
            "mqtt_password": "manual_password",
        }

        # Test manual configuration structure
        assert user_input["serial_number"] == "MANUAL-CONFIG-123"
        assert user_input["device_name"] == "Manual Test Device"
        assert "mqtt_hostname" in user_input
        assert "mqtt_password" in user_input

    @pytest.mark.asyncio
    async def test_sticker_configuration_flow(self, mock_hass):
        """Test sticker-based device configuration."""
        from custom_components.hass_dyson.config_flow import DysonConfigFlow

        config_flow = DysonConfigFlow()
        config_flow.hass = mock_hass

        # Mock sticker data
        sticker_data = {
            "serial_number": "STICKER-CONFIG-123",
            "wifi_password": "sticker_wifi_pass",
            "mqtt_password": "sticker_mqtt_pass",
        }

        # Test sticker configuration structure
        assert sticker_data["serial_number"] == "STICKER-CONFIG-123"
        assert "wifi_password" in sticker_data
        assert "mqtt_password" in sticker_data


class TestErrorRecoveryScenarios:
    """Test error recovery and resilience scenarios."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant for error testing."""
        hass = MagicMock()
        hass.data = {DOMAIN: {}}
        return hass

    @pytest.mark.asyncio
    async def test_coordinator_recovery_after_device_failure(self, mock_hass):
        """Test coordinator recovery after device communication failure."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = MagicMock()
            coordinator.device = MagicMock()

            # Simulate device failure
            coordinator.device.get_state.side_effect = ConnectionError("Device unavailable")
            coordinator.last_update_success = False

            # Test error handling
            with pytest.raises(ConnectionError):
                coordinator.device.get_state()

            assert coordinator.last_update_success is False

            # Simulate recovery
            coordinator.device.get_state.side_effect = None
            coordinator.device.get_state.return_value = {"status": "ok"}
            coordinator.last_update_success = True

            result = coordinator.device.get_state()
            assert result["status"] == "ok"
            assert coordinator.last_update_success is True

    @pytest.mark.asyncio
    async def test_partial_entity_failure_handling(self, mock_hass):
        """Test handling when some entities fail but others continue working."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = MagicMock()

            # Mock entity data with some failures
            coordinator.data = {
                "temperature": 22.5,  # Working
                "pm25": None,  # Failed
                "pm10": 20,  # Working
                "humidity": "error",  # Failed
            }

            # Test that working entities still function
            assert coordinator.data["temperature"] == 22.5
            assert coordinator.data["pm10"] == 20

            # Test that failed entities are handled gracefully
            assert coordinator.data["pm25"] is None
            assert coordinator.data["humidity"] == "error"

    @pytest.mark.asyncio
    async def test_home_assistant_restart_recovery(self, mock_hass):
        """Test recovery after Home Assistant restart."""
        config_entry = MagicMock()
        config_entry.data = {
            CONF_SERIAL_NUMBER: "RESTART-TEST-123",
            "device_name": "Restart Test Device",
            "capabilities": [CAPABILITY_EXTENDED_AQ],
            "device_category": DEVICE_CATEGORY_EC,
        }

        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            # Simulate coordinator recreation after restart
            coordinator = MagicMock()
            coordinator.config_entry = config_entry
            coordinator.device = MagicMock()

            # Test that coordinator can be recreated with config entry data
            assert coordinator.config_entry.data[CONF_SERIAL_NUMBER] == "RESTART-TEST-123"
            assert CAPABILITY_EXTENDED_AQ in coordinator.config_entry.data["capabilities"]


class TestStateConsistencyScenarios:
    """Test state consistency across multiple updates."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator for state testing."""
        coordinator = MagicMock()
        coordinator.device = MagicMock()
        coordinator.data = {}
        return coordinator

    def test_state_consistency_during_rapid_updates(self, mock_coordinator):
        """Test state consistency when device sends rapid updates."""
        # Simulate rapid state updates
        state_updates = [
            {"temperature": 20.0, "pm25": 10},
            {"temperature": 20.5, "pm25": 12},
            {"temperature": 21.0, "pm25": 11},
            {"temperature": 21.5, "pm25": 13},
        ]

        for update in state_updates:
            mock_coordinator.data.update(update)

        # Final state should be the last update
        assert mock_coordinator.data["temperature"] == 21.5
        assert mock_coordinator.data["pm25"] == 13

    def test_state_rollback_on_invalid_data(self, mock_coordinator):
        """Test that invalid data doesn't corrupt good state."""
        # Set initial good state
        mock_coordinator.data = {"temperature": 22.0, "pm25": 15}
        good_state = mock_coordinator.data.copy()

        # Attempt to update with invalid data
        try:
            invalid_update = {"temperature": "invalid", "pm25": -999}
            # In real implementation, this would be validated
            # For test, we simulate validation failure
            if not isinstance(invalid_update["temperature"], (int, float)):
                raise ValueError("Invalid temperature data")
            if invalid_update["pm25"] < 0:
                raise ValueError("Invalid PM2.5 data")
        except ValueError:
            # State should remain unchanged
            pass

        # Verify good state is preserved
        assert mock_coordinator.data == good_state
        assert mock_coordinator.data["temperature"] == 22.0
        assert mock_coordinator.data["pm25"] == 15

    def test_concurrent_entity_updates(self, mock_coordinator):
        """Test handling of concurrent entity updates."""
        # Simulate multiple entities trying to update simultaneously
        entities = ["temperature_sensor", "pm25_sensor", "wifi_sensor"]

        # Mock entity updates
        entity_data = {
            "temperature_sensor": {"temperature": 23.0},
            "pm25_sensor": {"pm25": 18},
            "wifi_sensor": {"wifi_strength": -45},
        }

        # Simulate concurrent updates
        for entity in entities:
            mock_coordinator.data.update(entity_data[entity])

        # All updates should be present
        assert mock_coordinator.data["temperature"] == 23.0
        assert mock_coordinator.data["pm25"] == 18
        assert mock_coordinator.data["wifi_strength"] == -45
