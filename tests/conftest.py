"""Test configuration for Dyson Alternative integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_dyson_device():
    """Create a mock Dyson device for testing."""
    device = MagicMock()
    device.serial_number = "TEST-SERIAL-123"
    device.hostname = "test-device.local"
    device.username = "TEST-SERIAL-123"
    device.password = "test-password"
    device.is_connected = True
    device.connect = AsyncMock(return_value=True)
    device.disconnect = AsyncMock()
    device.send_command = AsyncMock()
    device.get_state = AsyncMock(return_value={})
    device.get_faults = AsyncMock(return_value=[])
    return device


@pytest.fixture
def mock_cloud_devices():
    """Create mock cloud device data for testing."""
    return [
        {
            "serial": "TEST-DEVICE-001",
            "name": "Living Room Fan",
            "model": "DP04",
            "category": "ec",
            "capabilities": ["AdvanceOscillationDay1", "ExtendedAQ"],
            "hostname": "192.168.1.100",
            "username": "TEST-DEVICE-001",
            "password": "mqtt-password-001",
        },
        {
            "serial": "TEST-DEVICE-002",
            "name": "Bedroom Purifier",
            "model": "HP04",
            "category": "ec",
            "capabilities": ["Scheduling", "EnvironmentalData"],
            "hostname": "192.168.1.101",
            "username": "TEST-DEVICE-002",
            "password": "mqtt-password-002",
        },
    ]


@pytest.fixture
def mock_libdyson_rest():
    """Mock libdyson-rest library."""
    with patch("libdyson_rest.DysonCloudClient") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.authenticate = AsyncMock(return_value=True)
        mock_instance.get_devices = AsyncMock()
        yield mock_instance


@pytest.fixture
def mock_libdyson_mqtt():
    """Mock libdyson-mqtt library."""
    with patch("libdyson_mqtt.DysonMQTTClient") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.connect = AsyncMock(return_value=True)
        mock_instance.disconnect = AsyncMock()
        mock_instance.send_command = AsyncMock()
        mock_instance.subscribe = AsyncMock()
        yield mock_instance
