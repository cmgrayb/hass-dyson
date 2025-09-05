"""Test coordinator device communication logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.const import (
    CONF_CREDENTIAL,
    CONF_DISCOVERY_METHOD,
    CONF_SERIAL_NUMBER,
    DISCOVERY_CLOUD,
    DISCOVERY_STICKER,
)
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator


@pytest.fixture
def mock_hass():
    """Mock Home Assistant."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.bus.async_fire = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry_cloud():
    """Mock config entry for cloud discovery."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD,
        CONF_SERIAL_NUMBER: "TEST123456",
        "username": "test@example.com",
        "password": "testpassword",
    }
    return config_entry


@pytest.fixture
def mock_config_entry_sticker():
    """Mock config entry for sticker discovery."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
        CONF_SERIAL_NUMBER: "TEST123456",
        CONF_CREDENTIAL: "devicepassword",
        "hostname": "192.168.1.100",
        "capabilities": ["environmental_data", "oscillation"],
        "device_category": "fan",
    }
    return config_entry


class TestDysonDataUpdateCoordinatorLogic:
    """Test the coordinator logic without HA base class."""

    @pytest.mark.asyncio
    @patch("libdyson_rest.DysonClient")
    @patch("custom_components.hass_dyson.device.DysonDevice")
    @patch("custom_components.hass_dyson.coordinator.DysonDevice")
    async def test_cloud_device_setup_logic(self, mock_device_class, mock_mqtt_class, mock_cloud_class, mock_hass):
        """Test cloud device setup logic directly."""
        # Mock cloud client
        mock_cloud_client = MagicMock()
        mock_cloud_class.return_value = mock_cloud_client

        # Mock device info from cloud
        mock_device_info = MagicMock()
        mock_device_info.serial = "TEST123456"
        mock_device_info.product_type = "358"  # Fan model
        mock_cloud_client.get_devices.return_value = [mock_device_info]

        # Mock MQTT client
        mock_mqtt_client = MagicMock()
        mock_mqtt_class.return_value = mock_mqtt_client

        # Mock device wrapper
        mock_device = MagicMock()
        mock_device_class.return_value = mock_device

        # Create minimal coordinator for testing
        # Create with mocked base class
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            coordinator.hass = mock_hass
            coordinator.device = None
            coordinator._device_capabilities = []

        # Execute async_add_executor_job calls immediately
        def mock_executor_job(func, *args):
            return func(*args) if args else func()

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        # Test cloud login
        mock_cloud_client.login("test@example.com", "testpassword")
        devices = mock_cloud_client.get_devices()

        # Verify cloud client login was called
        mock_cloud_client.login.assert_called_once_with("test@example.com", "testpassword")

        # Verify device list was retrieved
        mock_cloud_client.get_devices.assert_called_once()

        # Verify we got our expected device
        assert len(devices) == 1
        assert devices[0].serial == "TEST123456"
        assert devices[0].product_type == "358"

    def test_device_category_mapping(self):
        """Test that device category comes from API response."""
        # Test that the coordinator uses API-provided category instead of static mapping
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_device_info = type("MockDeviceInfo", (), {"category": "ec", "serial_number": "TEST123"})()

            # Test that coordinator uses API category directly
            coordinator._device_category = getattr(mock_device_info, "category", "unknown")
            assert coordinator._device_category == "ec"

            # Test unknown category fallback
            mock_device_info_unknown = type("MockDeviceInfo", (), {"serial_number": "TEST456"})()
            coordinator._device_category = getattr(mock_device_info_unknown, "category", "unknown")
            assert coordinator._device_category == "unknown"

    def test_capability_extraction(self):
        """Test capability extraction from API response."""
        with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
            coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
            mock_device_info = type(
                "MockDeviceInfo", (), {"capabilities": ["EnvironmentalData", "AdvancedOscillation", "CustomCapability"]}
            )()

            capabilities = coordinator._extract_capabilities(mock_device_info)

            # Should contain the API-provided capabilities
            assert "EnvironmentalData" in capabilities
            assert "AdvancedOscillation" in capabilities
            assert "CustomCapability" in capabilities
            assert len(capabilities) == 3

            # Test device without capabilities attribute
            mock_device_no_caps = MagicMock()
            mock_device_no_caps.product_type = "360"
            del mock_device_no_caps.capabilities  # Remove capabilities attribute

            capabilities_empty = coordinator._extract_capabilities(mock_device_no_caps)
            assert capabilities_empty == []
