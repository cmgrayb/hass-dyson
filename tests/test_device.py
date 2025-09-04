"""Test device wrapper communication logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.device import DysonDevice


@pytest.fixture
def mock_hass():
    """Mock Home Assistant."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    return hass


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client for paho-mqtt."""
    client = MagicMock()
    client.is_connected = MagicMock(return_value=True)
    client.connect = MagicMock()
    client.disconnect = MagicMock()
    client.publish = MagicMock()
    client.get_state = MagicMock(return_value={"product-state": {"fpwr": "ON", "nmdv": "0005"}})
    client.get_faults = MagicMock(return_value=[])
    client.set_message_callback = MagicMock()
    return client


@pytest.fixture
def sample_device_data():
    """Sample device configuration data."""
    return {
        "serial_number": "TEST123456",
        "host": "192.168.1.100",
        "credential": "test_credential_123",
        "mqtt_prefix": "475",
        "capabilities": ["environmental_data", "heating"],
    }


class TestDysonDevice:
    """Test the DysonDevice wrapper class."""

    def test_init_with_device_info(self, mock_hass, sample_device_data):
        """Test device initialization with device data."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number=sample_device_data["serial_number"],
            host=sample_device_data["host"],
            credential=sample_device_data["credential"],
            mqtt_prefix=sample_device_data["mqtt_prefix"],
            capabilities=sample_device_data["capabilities"],
        )

        assert device.hass == mock_hass
        assert device.serial_number == sample_device_data["serial_number"]
        assert device.host == sample_device_data["host"]
        assert device.credential == sample_device_data["credential"]
        assert device.mqtt_prefix == sample_device_data["mqtt_prefix"]
        assert device.capabilities == sample_device_data["capabilities"]

    def test_init_with_manual_params(self, mock_hass):
        """Test device initialization with manual parameters."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="MANUAL123",
            host="10.0.0.50",
            credential="manual_cred",
            capabilities=["scheduling"],
        )

        assert device.hass == mock_hass
        assert device.serial_number == "MANUAL123"
        assert device.host == "10.0.0.50"
        assert device.credential == "manual_cred"
        assert device.capabilities == ["scheduling"]

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_hass, mock_mqtt_client, sample_device_data):
        """Test successful device connection."""
        with (
            patch("custom_components.hass_dyson.device.DysonMqttClient", return_value=mock_mqtt_client),
            patch("custom_components.hass_dyson.device.ConnectionConfig"),
        ):

            device = DysonDevice(
                hass=mock_hass,
                serial_number=sample_device_data["serial_number"],
                host=sample_device_data["host"],
                credential=sample_device_data["credential"],
            )

            result = await device.connect()

            assert result is True
            assert device.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_no_client(self, mock_hass, sample_device_data):
        """Test connection when no MQTT client library is available."""
        with (
            patch("custom_components.hass_dyson.device.DysonMqttClient", None),
            patch("custom_components.hass_dyson.device.ConnectionConfig", None),
        ):

            device = DysonDevice(
                hass=mock_hass,
                serial_number=sample_device_data["serial_number"],
                host=sample_device_data["host"],
                credential=sample_device_data["credential"],
            )

            result = await device.connect()

            assert result is False
            assert device.is_connected is False

    @pytest.mark.asyncio
    async def test_send_command_success(self, mock_hass, mock_mqtt_client, sample_device_data):
        """Test successful command sending."""
        with (
            patch("custom_components.hass_dyson.device.DysonMqttClient", return_value=mock_mqtt_client),
            patch("custom_components.hass_dyson.device.ConnectionConfig"),
        ):

            device = DysonDevice(
                hass=mock_hass,
                serial_number=sample_device_data["serial_number"],
                host=sample_device_data["host"],
                credential=sample_device_data["credential"],
            )

            # Connect first
            await device.connect()

            # Mock the command method
            mock_mqtt_client.send_command = MagicMock()

            # Execute async_add_executor_job calls immediately
            def mock_executor_job(func, *args):
                return func(*args) if args else func()

            mock_hass.async_add_executor_job.side_effect = mock_executor_job

            await device.send_command("set_fan_speed", {"speed": 5})

            mock_mqtt_client.send_command.assert_called_once_with("set_fan_speed", {"speed": 5})

    @pytest.mark.asyncio
    async def test_send_command_not_connected(self, mock_hass, sample_device_data):
        """Test command sending when not connected."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number=sample_device_data["serial_number"],
            host=sample_device_data["host"],
            credential=sample_device_data["credential"],
        )

        with pytest.raises(RuntimeError, match=f"Device {sample_device_data['serial_number']} is not connected"):
            await device.send_command("set_fan_speed", {"speed": 5})

    @pytest.mark.asyncio
    async def test_get_state(self, mock_hass, mock_mqtt_client, sample_device_data):
        """Test getting device state."""
        mock_state_data = {"product-state": {"fpwr": "ON", "nmdv": "0007", "wacd": "AUTO"}}
        mock_mqtt_client.get_state = MagicMock(return_value=mock_state_data)

        with (
            patch("custom_components.hass_dyson.device.DysonMqttClient", return_value=mock_mqtt_client),
            patch("custom_components.hass_dyson.device.ConnectionConfig"),
        ):

            device = DysonDevice(
                hass=mock_hass,
                serial_number=sample_device_data["serial_number"],
                host=sample_device_data["host"],
                credential=sample_device_data["credential"],
            )

            # Connect first
            await device.connect()

            # Execute async_add_executor_job calls immediately
            def mock_executor_job(func, *args):
                return func(*args) if args else func()

            mock_hass.async_add_executor_job.side_effect = mock_executor_job

            state = await device.get_state()

            assert isinstance(state, dict)
            mock_mqtt_client.get_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_faults(self, mock_hass, mock_mqtt_client, sample_device_data):
        """Test getting device faults."""
        mock_fault_data = [{"fault_code": "F001", "description": "Filter needs replacement"}]
        mock_mqtt_client.get_faults = MagicMock(return_value=mock_fault_data)

        with (
            patch("custom_components.hass_dyson.device.DysonMqttClient", return_value=mock_mqtt_client),
            patch("custom_components.hass_dyson.device.ConnectionConfig"),
        ):

            device = DysonDevice(
                hass=mock_hass,
                serial_number=sample_device_data["serial_number"],
                host=sample_device_data["host"],
                credential=sample_device_data["credential"],
            )

            # Connect first
            await device.connect()

            # Execute async_add_executor_job calls immediately
            def mock_executor_job(func, *args):
                return func(*args) if args else func()

            mock_hass.async_add_executor_job.side_effect = mock_executor_job

            faults = await device.get_faults()

            assert len(faults) == 1
            assert faults[0]["fault_code"] == "F001"
            mock_mqtt_client.get_faults.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_hass, mock_mqtt_client, sample_device_data):
        """Test device disconnection."""
        with (
            patch("custom_components.hass_dyson.device.DysonMqttClient", return_value=mock_mqtt_client),
            patch("custom_components.hass_dyson.device.ConnectionConfig"),
        ):

            device = DysonDevice(
                hass=mock_hass,
                serial_number=sample_device_data["serial_number"],
                host=sample_device_data["host"],
                credential=sample_device_data["credential"],
            )

            # Connect first
            await device.connect()
            assert device.is_connected is True

            # Execute async_add_executor_job calls immediately
            def mock_executor_job(func, *args):
                return func(*args) if args else func()

            mock_hass.async_add_executor_job.side_effect = mock_executor_job

            await device.disconnect()

            assert device.is_connected is False
            mock_mqtt_client.disconnect.assert_called_once()
