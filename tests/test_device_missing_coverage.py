"""Test device.py missing coverage areas."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.device import DysonDevice


class TestDeviceMissingCoverage:
    """Test previously uncovered device.py code paths."""

    @pytest.mark.asyncio
    async def test_attempt_connection_missing_host(self, mock_hass):
        """Test connection attempt with missing host."""
        device = DysonDevice("TEST123", "Test Device", mock_hass, "credential")
        result = await device._attempt_connection("local", None, "credential")
        assert result is False

    @pytest.mark.asyncio
    async def test_attempt_connection_missing_credential(self, mock_hass):
        """Test connection attempt with missing credential."""
        device = DysonDevice("TEST123", "Test Device", mock_hass, "credential")
        result = await device._attempt_connection("local", "host", None)
        assert result is False

    @pytest.mark.asyncio
    async def test_attempt_connection_generic_exception(self, mock_hass):
        """Test connection attempt with generic exception."""
        device = DysonDevice("TEST123", "Test Device", mock_hass, "credential")
        with patch.object(
            device, "_attempt_local_connection", side_effect=Exception("Test error")
        ):
            result = await device._attempt_connection("local", "host", "credential")
            assert result is False

    @pytest.mark.asyncio
    async def test_attempt_local_connection_mqtt_error(self, mock_hass):
        """Test local connection with MQTT error."""
        device = DysonDevice("TEST123", "Test Device", mock_hass, "credential")
        with patch("custom_components.hass_dyson.device.mqtt.Client") as mock_client:
            mock_mqtt_instance = MagicMock()
            mock_client.return_value = mock_mqtt_instance

            # Mock executor job to raise exception
            mock_hass.async_add_executor_job = AsyncMock(
                side_effect=Exception("MQTT error")
            )

            result = await device._attempt_local_connection("192.168.1.100", "password")
            assert result is False

    @pytest.mark.asyncio
    async def test_attempt_cloud_connection_aws_error(self, mock_hass):
        """Test cloud connection with AWS IoT error."""
        device = DysonDevice("TEST123", "Test Device", mock_hass, "credential")

        # Mock the executor job to simulate connection failure
        mock_hass.async_add_executor_job = AsyncMock(return_value=False)

        result = await device._attempt_cloud_connection(
            "host.iot.amazonaws.com", "cert_data"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_attempt_cloud_connection_exception(self, mock_hass):
        """Test cloud connection with general exception."""
        device = DysonDevice("TEST123", "Test Device", mock_hass, "credential")

        # Mock the executor job to raise exception
        mock_hass.async_add_executor_job = AsyncMock(side_effect=Exception("AWS error"))

        result = await device._attempt_cloud_connection(
            "host.iot.amazonaws.com", "cert_data"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_disconnect_without_client(self, mock_hass):
        """Test disconnect when no MQTT client exists."""
        device = DysonDevice("TEST123", "Test Device", mock_hass, "credential")
        device._mqtt_client = None

        # Should not raise exception
        await device.disconnect()

        assert device._mqtt_client is None
