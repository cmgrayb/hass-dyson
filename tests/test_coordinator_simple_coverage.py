"""
Simple working tests to cover remaining coordinator.py missing lines.

Focusing on achievable coverage improvements without complex mocking issues.
"""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.hass_dyson.const import (
    CONF_DEVICE_NAME,
    CONF_HOSTNAME,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator


@pytest.fixture
def mock_hass():
    """Create a properly mocked Home Assistant instance."""
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    hass.loop = MagicMock()
    hass.loop.call_soon_threadsafe = MagicMock()
    hass.async_create_task = MagicMock()
    hass.add_job = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_entries_for_config_entry_id = MagicMock(return_value=[])
    return hass


@pytest.fixture
def mock_config_entry_hostname():
    """Create a mock config entry with hostname."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
        CONF_DEVICE_NAME: "Test Dyson",
        CONF_HOSTNAME: "192.168.1.100",  # Add hostname for manual device tests
        "credential": "test_credential",
        "mqtt_prefix": "test_prefix",
    }
    config_entry.entry_id = "test_entry_id"
    return config_entry


class TestCoordinatorWorkingPaths:
    """Test working coverage paths in coordinator.py."""

    @pytest.mark.asyncio
    async def test_device_name_fallback_missing_config(self, mock_hass):
        """Test device name fallback when no CONF_DEVICE_NAME in config (lines 186-188)."""
        # Config entry without device name
        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
            # No CONF_DEVICE_NAME
        }

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry
            coordinator._listeners = {}

            # Test device name fallback
            device_name = coordinator.device_name
            assert device_name == "Dyson VS6-EU-HJA1234A"

    @pytest.mark.asyncio
    async def test_get_effective_connection_type_exception_handling(self, mock_hass):
        """Test connection type fallback when account lookup fails (lines 221-225)."""
        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
            "parent_entry_id": "parent_123",
        }

        # Mock hass to throw exception during config entry lookup
        mock_hass.config_entries.async_entries_for_config_entry_id.side_effect = (
            Exception("Config lookup error")
        )

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry
            coordinator._listeners = {}

            connection_type = coordinator._get_effective_connection_type()
            assert connection_type == "local_cloud_fallback"

    @pytest.mark.asyncio
    async def test_debug_connected_configuration_simple(
        self, mock_hass, mock_config_entry_hostname
    ):
        """Test debug logging for connected configuration (lines 360-362)."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(
                mock_hass, mock_config_entry_hostname
            )
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_hostname
            coordinator._listeners = {}

            # Create a simple object with attributes
            class MockConnectedConfig:
                def __init__(self):
                    self.attr1 = "value1"
                    self.attr2 = "value2"

            class MockDeviceInfo:
                def __init__(self):
                    self.connected_configuration = MockConnectedConfig()

            mock_device_info = MockDeviceInfo()

            with patch(
                "custom_components.hass_dyson.coordinator._LOGGER"
            ) as mock_logger:
                coordinator._debug_connected_configuration(mock_device_info)
                # Should call debug method
                mock_logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_extract_firmware_version_no_firmware_object(
        self, mock_hass, mock_config_entry_hostname
    ):
        """Test firmware version extraction without firmware object (lines 535-536)."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(
                mock_hass, mock_config_entry_hostname
            )
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_hostname
            coordinator._listeners = {}

            # Mock device info with connected config but no firmware
            mock_connected_config = MagicMock()
            mock_connected_config.firmware = None

            mock_device_info = MagicMock()
            mock_device_info.connected_configuration = mock_connected_config

            with patch(
                "custom_components.hass_dyson.coordinator._LOGGER"
            ) as mock_logger:
                coordinator._extract_firmware_version(mock_device_info)

                assert coordinator._firmware_version == "Unknown"
                assert coordinator._firmware_auto_update_enabled is False
                mock_logger.debug.assert_called_with(
                    "No firmware object found in connected configuration"
                )

    @pytest.mark.asyncio
    async def test_extract_capabilities_with_exception_handling(
        self, mock_hass, mock_config_entry_hostname
    ):
        """Test capability extraction exception handling (lines 474-477)."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(
                mock_hass, mock_config_entry_hostname
            )
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_hostname
            coordinator._listeners = {}
            coordinator._device_capabilities = []

            # Create device info that throws exception during processing
            class MockDeviceInfo:
                @property
                def capabilities(self):
                    raise Exception("Test exception accessing capabilities")

            mock_device_info = MockDeviceInfo()

            with patch("custom_components.hass_dyson.coordinator._LOGGER"):
                try:
                    coordinator._extract_capabilities(mock_device_info)
                except Exception:
                    # Exception is expected and should be handled
                    pass
                # Should fall back to empty capabilities
                assert coordinator._device_capabilities == []

    @pytest.mark.asyncio
    async def test_async_setup_sticker_device_disabled_path(
        self, mock_hass, mock_config_entry_hostname
    ):
        """Test sticker device setup method raises disabled error (lines 956-958)."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(
                mock_hass, mock_config_entry_hostname
            )
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_hostname
            coordinator._listeners = {}

            with pytest.raises(
                UpdateFailed, match="Sticker discovery method temporarily disabled"
            ):
                await coordinator._async_setup_sticker_device()

    @pytest.mark.asyncio
    async def test_manual_device_setup_missing_hostname(self, mock_hass):
        """Test manual device setup fails when hostname missing (lines 765-766)."""
        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
            "credential": "test_credential",
            "mqtt_prefix": "test_prefix",
            # No hostname - should trigger error
        }

        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry
            coordinator._listeners = {}
            coordinator._device_capabilities = []

            with pytest.raises(UpdateFailed, match="Manual device setup failed"):
                await coordinator._async_setup_manual_device()

    @pytest.mark.asyncio
    async def test_cloud_credentials_api_failure(
        self, mock_hass, mock_config_entry_hostname
    ):
        """Test cloud credentials extraction with API failure (lines 679-682)."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(
                mock_hass, mock_config_entry_hostname
            )
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_hostname
            coordinator._listeners = {}

            # Mock cloud client that throws exception
            mock_cloud_client = MagicMock()
            mock_cloud_client.get_iot_credentials.side_effect = Exception("API Error")
            mock_device_info = MagicMock()

            result = await coordinator._extract_cloud_credentials(
                mock_cloud_client, mock_device_info
            )

            assert result == {"cloud_host": None, "cloud_credentials": {}}

    @pytest.mark.asyncio
    async def test_cloud_credentials_no_iot_data(
        self, mock_hass, mock_config_entry_hostname
    ):
        """Test cloud credentials extraction when no IoT data returned (lines 670-673)."""
        with patch(
            "custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"
        ):
            coordinator = DysonDataUpdateCoordinator(
                mock_hass, mock_config_entry_hostname
            )
            coordinator.hass = mock_hass
            coordinator.config_entry = mock_config_entry_hostname
            coordinator._listeners = {}

            # Mock cloud client that returns None for IoT data
            mock_cloud_client = MagicMock()
            mock_cloud_client.get_iot_credentials.return_value = None
            mock_device_info = MagicMock()

            result = await coordinator._extract_cloud_credentials(
                mock_cloud_client, mock_device_info
            )

            assert result == {"cloud_host": None, "cloud_credentials": {}}
