"""Test for device name validation error handling."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hass_dyson.config_flow import DysonConfigFlow


class TestDeviceNameValidationError:
    """Test handling of device name validation errors."""

    @pytest.mark.asyncio
    async def test_device_name_validation_error_handling(self):
        """Test that device name validation errors are properly handled."""
        # Arrange
        config_flow = DysonConfigFlow()
        config_flow._cloud_client = MagicMock()
        config_flow._email = "test@example.com"

        # Mock get_devices to raise the specific validation error
        config_flow._cloud_client.get_devices = AsyncMock(
            side_effect=Exception("Expected str for name, got NoneType")
        )

        user_input = {"connection_type": "cloud_only"}

        # Act
        result = await config_flow.async_step_connection(user_input)

        # Assert
        assert result["type"] == "form"
        assert result["step_id"] == "connection"
        assert result["errors"]["base"] == "device_data_invalid"

    @pytest.mark.asyncio
    async def test_other_device_errors_still_work(self):
        """Test that other device errors are still handled as generic errors."""
        # Arrange
        config_flow = DysonConfigFlow()
        config_flow._cloud_client = MagicMock()
        config_flow._email = "test@example.com"

        # Mock get_devices to raise a different error
        config_flow._cloud_client.get_devices = AsyncMock(
            side_effect=Exception("Some other API error")
        )

        user_input = {"connection_type": "cloud_only"}

        # Act
        result = await config_flow.async_step_connection(user_input)

        # Assert
        assert result["type"] == "form"
        assert result["step_id"] == "connection"
        assert result["errors"]["base"] == "cloud_api_error"
