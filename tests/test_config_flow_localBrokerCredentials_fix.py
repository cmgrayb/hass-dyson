"""Test config flow device filtering by connectivity type."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hass_dyson.config_flow import DysonConfigFlow


@pytest.fixture
def config_flow_with_client(mock_hass):
    """Create a DysonConfigFlow instance with an initialized client."""
    flow = DysonConfigFlow()
    flow.hass = mock_hass
    flow._email = "test@example.com"
    flow._cloud_client = AsyncMock()
    return flow


class TestConfigFlowConnectivityTypeFiltering:
    """Test device filtering based on connectivity types."""

    @pytest.mark.asyncio
    async def test_unsupported_connectivity_type_handling(
        self, config_flow_with_client
    ):
        """Test filtering of devices with unsupported connectivity types."""
        # Mock devices with different connectivity types
        standard_device = MagicMock()
        standard_device.name = "Standard Device"
        standard_device.connection_category = (
            None  # Most existing devices have no category
        )
        standard_device.serial_number = "STD123"
        standard_device.product_type = "475"

        lec_only_device = MagicMock()
        lec_only_device.name = "LEC Only Device"
        lec_only_device.connection_category = "lecOnly"
        lec_only_device.serial_number = "LEC456"
        lec_only_device.product_type = "999"

        config_flow_with_client._cloud_client.get_devices.return_value = [
            standard_device,
            lec_only_device,
        ]

        user_input = {"connection_type": "local_cloud_fallback"}

        result = await config_flow_with_client.async_step_connection(user_input)

        # Should proceed to cloud_preferences step with filtered devices
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "cloud_preferences"

        # Should have only the standard device (lecOnly filtered out)
        assert len(config_flow_with_client._discovered_devices) == 1
        assert config_flow_with_client._discovered_devices[0].name == "Standard Device"

    @pytest.mark.asyncio
    async def test_supported_devices_successful_flow(self, config_flow_with_client):
        """Test that device discovery works with standard devices (including None connectivity)."""
        # Mock successful device discovery - standard device without connectivity category
        mock_device = MagicMock()
        mock_device.serial_number = "TEST123"
        mock_device.name = "Test Device"
        mock_device.product_type = "475"
        # Most real devices don't have connection_category attribute
        del mock_device.connection_category

        config_flow_with_client._cloud_client.get_devices.return_value = [mock_device]

        user_input = {"connection_type": "local_cloud_fallback"}

        result = await config_flow_with_client.async_step_connection(user_input)

        # Should proceed to cloud_preferences step
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "cloud_preferences"

    @pytest.mark.asyncio
    async def test_informational_logging_for_unsupported_devices(
        self, config_flow_with_client, caplog
    ):
        """Test that unsupported devices are logged informationally."""
        # Mock devices with unsupported connectivity
        lec_device = MagicMock()
        lec_device.name = "LEC Device"
        lec_device.connection_category = "lecOnly"
        lec_device.serial_number = "LEC789"

        config_flow_with_client._cloud_client.get_devices.return_value = [lec_device]

        user_input = {"connection_type": "local_cloud_fallback"}

        result = await config_flow_with_client.async_step_connection(user_input)

        # Flow continues to cloud_preferences even with no supported devices
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "cloud_preferences"

        # Check that informational logging occurred
        assert "Skipping device" in caplog.text
        assert "lecOnly" in caplog.text
        assert "will be supported in future release" in caplog.text

    @pytest.mark.asyncio
    async def test_mixed_connectivity_devices(self, config_flow_with_client):
        """Test handling mix of supported and unsupported connectivity devices."""
        # Mock devices with mixed connectivity types
        standard_device1 = MagicMock()
        standard_device1.name = "Standard Device"
        standard_device1.connection_category = None  # Standard device

        standard_device2 = MagicMock()
        standard_device2.name = "WiFi Device"
        standard_device2.connection_category = "wifiOnly"  # Explicitly supported

        standard_device3 = MagicMock()
        standard_device3.name = "LEC+WiFi Device"
        standard_device3.connection_category = "lecAndWifi"  # Also supported

        unsupported_device = MagicMock()
        unsupported_device.name = "LEC Only Device"
        unsupported_device.connection_category = "lecOnly"  # Only this is filtered

        config_flow_with_client._cloud_client.get_devices.return_value = [
            standard_device1,
            standard_device2,
            standard_device3,
            unsupported_device,
        ]

        user_input = {"connection_type": "local_cloud_fallback"}

        result = await config_flow_with_client.async_step_connection(user_input)

        # Should proceed with all devices except lecOnly
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "cloud_preferences"
        assert (
            len(config_flow_with_client._discovered_devices) == 3
        )  # All except lecOnly

    @pytest.mark.asyncio
    async def test_api_format_changed_error_still_handled(
        self, config_flow_with_client
    ):
        """Test that productType missing errors are still handled correctly."""
        # Mock the get_devices call to raise productType error
        config_flow_with_client._cloud_client.get_devices.side_effect = Exception(
            "Missing required field: productType"
        )

        user_input = {"connection_type": "local_cloud_fallback"}

        result = await config_flow_with_client.async_step_connection(user_input)

        # Should show the form with the API format changed error
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "connection"
        assert "api_format_changed" in result["errors"]["base"]
