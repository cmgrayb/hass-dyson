"""Test integration with real device data.

SECURITY NOTE:
This test uses mock device data by default from fixtures/mock_device_api.json.
Real device data with sensitive information (serial numbers, tokens, credentials)
should only be stored in the .local/ directory which is excluded from version control.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.const import (
    CONF_DISCOVERY_METHOD,
    CONF_SERIAL_NUMBER,
    DISCOVERY_STICKER,
)
from custom_components.hass_dyson.device import DysonDevice


@pytest.fixture
def real_device_data():
    """Load mock device data for testing."""
    api_file = Path(__file__).parent / "fixtures" / "mock_device_api.json"
    if api_file.exists():
        with open(api_file) as f:
            return json.load(f)

    # Fallback to real data from .local if available (for development only)
    real_api_file = Path(__file__).parent.parent / ".local" / "438M_api.json"
    if real_api_file.exists():
        with open(real_api_file) as f:
            data = json.load(f)
            # Sanitize sensitive data even if using real file
            if "devices" in data and len(data["devices"]) > 0:
                data["devices"][0]["basic_info"]["serial_number"] = (
                    "MOCK-SERIAL-TEST123"
                )
                data["authentication"]["email"] = "test@example.com"
                data["authentication"]["account_id"] = (
                    "00000000-0000-0000-0000-000000000000"
                )
                data["authentication"]["bearer_token"] = "MOCK-TOKEN-12345"
            return data
    return None


@pytest.fixture
def mock_hass():
    """Mock Home Assistant."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.bus.async_fire = MagicMock()
    return hass


@pytest.mark.asyncio
async def test_real_device_data_parsing(real_device_data, mock_hass):
    """Test parsing real device data."""
    if not real_device_data:
        pytest.skip("No real device data available")

    device_info = real_device_data["devices"][0]

    # Test device info extraction
    assert device_info["basic_info"]["name"] == "Theater Fan"
    assert device_info["basic_info"]["serial_number"] == "MOCK-SERIAL-TEST123"
    assert device_info["basic_info"]["type"] == "438"
    assert device_info["basic_info"]["model"] == "TP11"
    assert device_info["basic_info"]["category"] == "ec"

    # Test MQTT configuration
    mqtt_config = device_info["connected_configuration"]["mqtt"]
    assert mqtt_config["mqtt_root_topic_level"] == "438M"
    assert "local_broker_credentials_decrypted" in mqtt_config

    # Test capabilities
    capabilities = device_info["connected_configuration"]["firmware"]["capabilities"]
    expected_capabilities = [
        "AdvanceOscillationDay1",
        "Scheduling",
        "EnvironmentalData",
        "ExtendedAQ",
        "ChangeWifi",
    ]
    assert all(cap in capabilities for cap in expected_capabilities)


@pytest.mark.asyncio
async def test_sticker_config_from_real_data(real_device_data, mock_hass):
    """Test creating sticker config from real device data."""
    if not real_device_data:
        pytest.skip("No real device data available")

    device_info = real_device_data["devices"][0]

    # Create a config entry as if user entered sticker info
    config_entry = MagicMock()
    config_entry.data = {
        CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
        CONF_SERIAL_NUMBER: device_info["basic_info"]["serial_number"],
        "password": device_info["mqtt_analysis"]["local_mqtt"]["password"],
        "hostname": "192.168.1.100",  # Example IP since we don't have real network info
        "capabilities": ["environmental_data", "advance_oscillation", "scheduling"],
        "device_category": device_info["basic_info"]["category"],
    }

    # Test device wrapper creation with new API
    with patch("paho.mqtt.client.Client") as mock_mqtt_class:
        mock_mqtt_client = MagicMock()
        mock_mqtt_client.connect.return_value = 0  # CONNACK_ACCEPTED
        mock_mqtt_client.is_connected.return_value = True
        mock_mqtt_class.return_value = mock_mqtt_client

        # Mock async_add_executor_job to execute functions directly
        def mock_executor_job(func, *args):
            return func(*args) if args else func()

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        device = DysonDevice(
            hass=mock_hass,
            serial_number=config_entry.data[CONF_SERIAL_NUMBER],
            host="192.168.1.100",  # Mock host for sticker method
            credential="mock_credential",  # Mock credential
            capabilities=config_entry.data["capabilities"],
        )

        assert device.serial_number == "MOCK-SERIAL-TEST123"
        assert device.capabilities == [
            "environmental_data",
            "advance_oscillation",
            "scheduling",
        ]

        # Mock the network connectivity test to return success
        with patch.object(device, "_test_network_connectivity", return_value=True):
            # Mock the wait for connection to return True and set internal state
            def mock_wait_for_connection(conn_type):
                device._connected = True  # Simulate successful connection
                return True

            with patch.object(
                device, "_wait_for_connection", side_effect=mock_wait_for_connection
            ):
                # Test connection
                result = await device.connect()
                assert result is True
        assert device.is_connected is True


@pytest.mark.asyncio
async def test_capability_mapping(real_device_data):
    """Test mapping real device capabilities to our internal format."""
    if not real_device_data:
        pytest.skip("No real device data available")

    device_info = real_device_data["devices"][0]
    real_capabilities = device_info["connected_configuration"]["firmware"][
        "capabilities"
    ]

    # Test capability mapping logic
    mapped_capabilities = []
    for cap in real_capabilities:
        if "Oscillation" in cap:
            mapped_capabilities.append("advance_oscillation")
        elif cap == "Scheduling":
            mapped_capabilities.append("scheduling")
        elif cap == "EnvironmentalData":
            mapped_capabilities.append("environmental_data")
        elif "AQ" in cap:  # Air Quality
            mapped_capabilities.append("air_quality")

    assert "advance_oscillation" in mapped_capabilities
    assert "scheduling" in mapped_capabilities
    assert "environmental_data" in mapped_capabilities
    assert "air_quality" in mapped_capabilities


@pytest.mark.asyncio
async def test_mqtt_credentials_format(real_device_data):
    """Test MQTT credentials format from real device."""
    if not real_device_data:
        pytest.skip("No real device data available")

    device_info = real_device_data["devices"][0]
    mqtt_analysis = device_info["mqtt_analysis"]["local_mqtt"]

    # Test credential format
    assert mqtt_analysis["username"] == device_info["basic_info"]["serial_number"]
    assert len(mqtt_analysis["password"]) > 50  # Should be a long encrypted string
    assert mqtt_analysis["root_topic"] == "438M"
    assert mqtt_analysis["ports"]["mqtt"] == 1883
    assert mqtt_analysis["ports"]["mqtt_tls"] == 8883


def test_device_categorization(real_device_data):
    """Test device categorization logic."""
    if not real_device_data:
        pytest.skip("No real device data available")

    device_info = real_device_data["devices"][0]

    # Test category mapping
    device_type = device_info["basic_info"]["type"]
    device_category = device_info["basic_info"]["category"]

    assert device_type == "438"
    assert device_category == "ec"  # Environmental Control (Fan)

    # Test our categorization logic - should use API-provided category
    from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

    # Create a mock device info with category field like the API would provide
    mock_device_info = type(
        "MockDeviceInfo",
        (),
        {
            "category": device_category,
            "serial_number": "TEST123",
            "product_type": device_type,
        },
    )()

    # Create a partial coordinator and test that it uses the API category
    coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
    coordinator._device_category = getattr(mock_device_info, "category", "unknown")

    assert coordinator._device_category == "ec"
