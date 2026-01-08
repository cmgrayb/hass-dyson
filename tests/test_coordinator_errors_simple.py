"""Simplified error handling tests for DysonDataUpdateCoordinator.

Focuses on testing actual error paths in coordinator methods.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.const import (
    CONF_DISCOVERY_METHOD,
    CONF_SERIAL_NUMBER,
    DISCOVERY_CLOUD,
)
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator


@pytest.fixture
def mock_hass():
    """Create a mocked Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    hass.loop = MagicMock()
    hass.add_job = MagicMock()
    hass.bus = MagicMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    return hass


@pytest.fixture
def mock_config_entry_cloud():
    """Mock config entry for cloud discovery."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD,
        CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
        "username": "test@example.com",
        "auth_token": "test_auth_token_123",
    }
    config_entry.entry_id = "test_entry_id_123"
    return config_entry


class TestCoordinatorErrorHandling:
    """Test coordinator error handling paths."""

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    @pytest.mark.asyncio
    async def test_notify_ha_get_state_exception(
        self, mock_super_init, mock_hass, mock_config_entry_cloud
    ):
        """Test notification when get_state raises exception."""
        mock_super_init.return_value = None
        coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
        coordinator.hass = mock_hass
        coordinator._listeners = {}
        coordinator.config_entry = mock_config_entry_cloud
        coordinator.device = MagicMock()
        coordinator.async_set_updated_data = MagicMock()

        # Mock get_state to raise exception
        coordinator.device.get_state = AsyncMock(
            side_effect=RuntimeError("Failed to get state")
        )

        # Should handle exception gracefully
        await coordinator._notify_ha_of_state_change()

        # Verify async_set_updated_data was not called
        coordinator.async_set_updated_data.assert_not_called()

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    @pytest.mark.asyncio
    async def test_notify_ha_no_device(
        self, mock_super_init, mock_hass, mock_config_entry_cloud
    ):
        """Test notification when device is None."""
        mock_super_init.return_value = None
        coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
        coordinator.hass = mock_hass
        coordinator._listeners = {}
        coordinator.config_entry = mock_config_entry_cloud
        coordinator.device = None
        coordinator.async_set_updated_data = MagicMock()

        # Should skip if no device
        await coordinator._notify_ha_of_state_change()

        # Verify nothing was called
        coordinator.async_set_updated_data.assert_not_called()

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    def test_handle_environmental_message_exception(
        self, mock_super_init, mock_hass, mock_config_entry_cloud
    ):
        """Test environmental message handling with exception."""
        mock_super_init.return_value = None
        coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
        coordinator.hass = mock_hass
        coordinator._listeners = {}
        coordinator.config_entry = mock_config_entry_cloud
        coordinator.device = MagicMock()

        # Mock _schedule_coordinator_data_update to raise exception
        with patch.object(
            coordinator,
            "_schedule_coordinator_data_update",
            side_effect=RuntimeError("Schedule failed"),
        ):
            # Should handle exception and log warning
            coordinator._handle_environmental_message({"pm25": 10})

        # Verify device is still available
        assert coordinator.device is not None

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    def test_handle_state_change_message_exception(
        self, mock_super_init, mock_hass, mock_config_entry_cloud
    ):
        """Test state change message handling with exception."""
        mock_super_init.return_value = None
        coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
        coordinator.hass = mock_hass
        coordinator._listeners = {}
        coordinator.config_entry = mock_config_entry_cloud
        coordinator.device = MagicMock()

        # Mock scheduling methods to raise exceptions
        with patch.object(
            coordinator,
            "_schedule_coordinator_data_update",
            side_effect=RuntimeError("Schedule failed"),
        ):
            with patch.object(
                coordinator, "_schedule_fallback_update"
            ) as mock_fallback:
                # Should handle exception and call fallback
                coordinator._handle_state_change_message()

                # Verify fallback was called
                mock_fallback.assert_called_once()

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    @patch("libdyson_rest.DysonClient")
    @pytest.mark.asyncio
    async def test_cloud_device_setup_authentication_failure(
        self, mock_cloud_class, mock_super_init, mock_hass, mock_config_entry_cloud
    ):
        """Test cloud device setup with authentication failure."""
        mock_super_init.return_value = None
        coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
        coordinator.hass = mock_hass
        coordinator.hass.async_add_executor_job = AsyncMock(
            side_effect=RuntimeError("Authentication failed")
        )
        coordinator._listeners = {}
        coordinator.config_entry = mock_config_entry_cloud

        # Should raise RuntimeError (not wrapped for auth_token path)
        with pytest.raises(RuntimeError, match="Authentication failed"):
            await coordinator._authenticate_cloud_client()

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    @patch("libdyson_rest.DysonClient")
    @pytest.mark.asyncio
    async def test_extract_cloud_credentials_api_failure(
        self, mock_cloud_class, mock_super_init, mock_hass, mock_config_entry_cloud
    ):
        """Test cloud credential extraction with API failure."""
        mock_super_init.return_value = None
        coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
        coordinator.hass = mock_hass
        coordinator._listeners = {}
        coordinator.config_entry = mock_config_entry_cloud

        # Mock cloud client to raise exception on get_iot_credentials
        mock_cloud_client = MagicMock()
        mock_cloud_client.get_iot_credentials = AsyncMock(
            side_effect=RuntimeError("API request failed")
        )

        # Mock device info
        device_info = MagicMock()

        # Should handle exception and return empty credentials
        result = await coordinator._extract_cloud_credentials(
            mock_cloud_client, device_info
        )

        assert result["cloud_host"] is None
        assert result["cloud_credentials"] == {}

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    def test_extract_capabilities_critical_error(
        self, mock_super_init, mock_hass, mock_config_entry_cloud
    ):
        """Test capability extraction with critical error."""
        mock_super_init.return_value = None
        coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
        coordinator.hass = mock_hass
        coordinator._listeners = {}
        coordinator.config_entry = mock_config_entry_cloud

        # Mock device info to raise exception
        device_info = MagicMock()

        # Force extraction to fail
        with patch.object(
            coordinator,
            "_extract_capabilities",
            side_effect=RuntimeError("Critical error"),
        ):
            # Should handle exception and set empty capabilities
            coordinator._extract_device_capabilities(device_info)

        assert coordinator._device_capabilities == []

    @patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__")
    def test_get_effective_connection_type_exception(
        self, mock_super_init, mock_hass, mock_config_entry_cloud
    ):
        """Test connection type determination with exception."""
        mock_super_init.return_value = None
        coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry_cloud)
        coordinator.hass = mock_hass
        coordinator._listeners = {}
        coordinator.config_entry = mock_config_entry_cloud

        # Mock config_entries.async_entries to raise exception
        coordinator.hass.config_entries.async_entries = MagicMock(
            side_effect=RuntimeError("Failed to get config entries")
        )

        # Should handle exception and return default
        result = coordinator._get_effective_connection_type()

        assert result == "local_cloud_fallback"
