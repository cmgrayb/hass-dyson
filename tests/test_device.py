"""Test device wrapper communication logic."""

import socket
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.const import (
    CONNECTION_STATUS_CLOUD,
    CONNECTION_STATUS_DISCONNECTED,
    CONNECTION_STATUS_LOCAL,
)
from custom_components.hass_dyson.device import DysonDevice


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
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
    client.get_state = MagicMock(
        return_value={"product-state": {"fpwr": "ON", "nmdv": "0005"}}
    )
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

    def test_init_with_cloud_credentials(self, mock_hass):
        """Test device initialization with cloud credentials."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="CLOUD123",
            host="192.168.1.100",
            credential="local_cred",
            connection_type="cloud_local_fallback",
            cloud_host="aws-iot-endpoint.amazonaws.com",
            cloud_credential='{"client_id":"dyson_12345","custom_authorizer_name":"DysonDeviceAuth","token_key":"token","token_value":"abc123","token_signature":"def456"}',
        )

        assert device.connection_type == "cloud_local_fallback"
        assert device.cloud_host == "aws-iot-endpoint.amazonaws.com"
        assert device.cloud_credential is not None
        assert device._preferred_connection_type == "cloud"
        assert not device._using_fallback
        assert device._current_connection_type == CONNECTION_STATUS_DISCONNECTED

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
    async def test_connect_success(
        self, mock_hass, mock_mqtt_client, sample_device_data
    ):
        """Test successful device connection."""
        with patch("paho.mqtt.client.Client", return_value=mock_mqtt_client):
            mock_mqtt_client.connect.return_value = 0  # CONNACK_ACCEPTED
            mock_mqtt_client.is_connected.return_value = (
                True  # Mock MQTT client as connected
            )

            # Mock async_add_executor_job to actually call the function and return the result
            def mock_executor_job(func, *args):
                return func(*args) if args else func()

            mock_hass.async_add_executor_job.side_effect = mock_executor_job

            device = DysonDevice(
                hass=mock_hass,
                serial_number=sample_device_data["serial_number"],
                host=sample_device_data["host"],
                credential=sample_device_data["credential"],
            )

            # Mock the network connectivity test to return success
            with patch.object(device, "_test_network_connectivity", return_value=True):
                # Mock the wait for connection to return True and set internal state
                def mock_wait_for_connection(conn_type):
                    device._connected = True  # Simulate successful connection
                    return True

                with patch.object(
                    device, "_wait_for_connection", side_effect=mock_wait_for_connection
                ):
                    result = await device.connect()

            assert result is True
            assert device.is_connected is True

    def test_mqtt_on_connect_callback(self, mock_hass):
        """Test MQTT on_connect callback handling."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="CALLBACK123",
            host="192.168.1.100",
            credential="local_cred",
            mqtt_prefix="475",
        )

        # Mock MQTT client and thread-safe scheduling (API v2 change)
        mock_client = MagicMock()
        mock_hass.async_create_task = MagicMock()
        mock_hass.loop = MagicMock()
        mock_hass.loop.call_soon_threadsafe = MagicMock()

        # Test successful connection
        device._on_connect(mock_client, None, {}, 0)  # CONNACK_ACCEPTED

        assert device._connected is True
        mock_client.subscribe.assert_called()
        # Should call call_soon_threadsafe twice: once for initial state request, once for heartbeat
        assert mock_hass.loop.call_soon_threadsafe.call_count == 2

        # Test failed connection
        device._connected = False
        device._on_connect(mock_client, None, {}, 1)  # Connection refused

        assert device._connected is False

    def test_mqtt_on_disconnect_callback(self, mock_hass):
        """Test MQTT on_disconnect callback handling."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="DISCONNECT123",
            host="192.168.1.100",
            credential="local_cred",
        )

        device._connected = True
        device._current_connection_type = "LOCAL"

        # Test unexpected disconnection
        mock_client = MagicMock()
        mock_flags = MagicMock()  # API v2 flags parameter
        device._on_disconnect(
            mock_client, None, mock_flags, 1
        )  # Non-success return code

        assert device._connected is False
        assert device._current_connection_type == CONNECTION_STATUS_DISCONNECTED
        assert device._last_preferred_retry == 0.0  # Should reset for retry

        # Test normal disconnection
        device._connected = True
        device._on_disconnect(mock_client, None, mock_flags, 0)  # MQTT_ERR_SUCCESS

        assert device._connected is False

    def test_mqtt_message_processing_current_state(self, mock_hass):
        """Test MQTT message processing for current state messages."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="MESSAGE123",
            host="192.168.1.100",
            credential="local_cred",
        )

        # Create mock MQTT message for current state
        mock_message = MagicMock()
        mock_message.topic = "475/MESSAGE123/status/current"
        mock_message.payload = b'{"msg":"CURRENT-STATE","product-state":{"fpwr":"ON","nmdv":"0005","hflr":"0100","cflr":"0080"}}'

        # Test message processing
        mock_client = MagicMock()
        device._on_message(mock_client, None, mock_message)

        # Check that state data was updated
        assert "product-state" in device._state_data
        assert device._state_data["product-state"]["fpwr"] == "ON"
        assert device._state_data["product-state"]["hflr"] == "0100"

    def test_mqtt_message_processing_environmental_data(self, mock_hass):
        """Test MQTT message processing for environmental sensor data."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="ENV123",
            host="192.168.1.100",
            credential="local_cred",
        )

        # Add mock environmental callback
        callback_called = []

        def mock_callback():
            callback_called.append(True)

        device.add_environmental_callback(mock_callback)

        # Create mock MQTT message for environmental data
        mock_message = MagicMock()
        mock_message.topic = "475/ENV123/status/current"
        mock_message.payload = b'{"msg":"ENVIRONMENTAL-CURRENT-SENSOR-DATA","data":{"pm25":"0010","pm10":"0015","hmax":"0030"}}'

        # Test message processing
        mock_client = MagicMock()
        device._on_message(mock_client, None, mock_message)

        # Check that environmental data was updated
        assert device._environmental_data["pm25"] == "0010"
        assert device._environmental_data["pm10"] == "0015"
        assert device._environmental_data["hmax"] == "0030"

        # Check that environmental callback was triggered
        assert len(callback_called) == 1

    def test_mqtt_message_processing_faults_data(self, mock_hass):
        """Test MQTT message processing for faults data."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="FAULT123",
            host="192.168.1.100",
            credential="local_cred",
        )

        # Create mock MQTT message for faults
        mock_message = MagicMock()
        mock_message.topic = "475/FAULT123/status/faults"
        mock_message.payload = b'{"msg":"CURRENT-FAULTS","faults":["REPLACE_FILTER"]}'

        # Test message processing
        mock_client = MagicMock()
        device._on_message(mock_client, None, mock_message)

        # Check that faults data was updated
        assert "faults" in device._faults_data

    def test_mqtt_message_processing_invalid_json(self, mock_hass):
        """Test MQTT message processing with invalid JSON."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="INVALID123",
            host="192.168.1.100",
            credential="local_cred",
        )

        # Create mock MQTT message with invalid JSON
        mock_message = MagicMock()
        mock_message.topic = "475/INVALID123/status/current"
        mock_message.payload = b'{"invalid": json}'

        # Test message processing - should not crash
        mock_client = MagicMock()
        device._on_message(mock_client, None, mock_message)

        # State should remain empty since JSON parsing failed
        assert len(device._state_data) == 0

    def test_environmental_callback_management(self, mock_hass):
        """Test adding and removing environmental callbacks."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="CALLBACK123",
            host="192.168.1.100",
            credential="local_cred",
        )

        def mock_callback1():
            pass

        def mock_callback2():
            pass

        # Test adding callbacks
        device.add_environmental_callback(mock_callback1)
        device.add_environmental_callback(mock_callback2)
        assert len(device._environmental_callbacks) == 2

        # Test adding duplicate callback (should not add)
        device.add_environmental_callback(mock_callback1)
        assert len(device._environmental_callbacks) == 2

        # Test removing callback
        device.remove_environmental_callback(mock_callback1)
        assert len(device._environmental_callbacks) == 1
        assert mock_callback2 in device._environmental_callbacks

    def test_message_callback_management(self, mock_hass):
        """Test adding and removing message callbacks."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="MSG_CALLBACK123",
            host="192.168.1.100",
            credential="local_cred",
        )

        def mock_callback1(topic, data):
            pass

        def mock_callback2(topic, data):
            pass

        # Test adding callbacks
        device.add_message_callback(mock_callback1)
        device.add_message_callback(mock_callback2)
        assert len(device._message_callbacks) == 2

        # Test adding duplicate callback (should not add)
        device.add_message_callback(mock_callback1)
        assert len(device._message_callbacks) == 2

        # Test removing callback
        device.remove_message_callback(mock_callback1)
        assert len(device._message_callbacks) == 1
        assert mock_callback2 in device._message_callbacks

    @pytest.mark.asyncio
    async def test_attempt_cloud_connection_success(self, mock_hass):
        """Test successful cloud connection attempt."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="CLOUD123",
            host="192.168.1.100",
            credential="local_cred",
            cloud_host="aws-iot-endpoint.amazonaws.com",
            cloud_credential='{"client_id":"dyson_12345","custom_authorizer_name":"DysonDeviceAuth","token_key":"token","token_value":"abc123","token_signature":"def456"}',
        )

        # Mock executor job to execute functions
        def mock_executor_job(func, *args):
            if hasattr(func, "__name__") and func.__name__ == "connect":
                return 0  # CONNACK_ACCEPTED
            return func(*args) if args else func()

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        # Mock the wait for connection to return True
        with (
            patch.object(device, "_wait_for_connection", return_value=True),
            patch("paho.mqtt.client.Client") as mock_client_class,
        ):
            mock_client = MagicMock()
            mock_client.connect.return_value = (
                0  # CONNACK_ACCEPTED for cloud connection
            )
            mock_client_class.return_value = mock_client

            result = await device._attempt_cloud_connection(
                "aws-iot-endpoint.amazonaws.com",
                '{"client_id":"dyson_12345","custom_authorizer_name":"DysonDeviceAuth","token_key":"token","token_value":"abc123","token_signature":"def456"}',
            )

            assert result is True
            mock_client.tls_set.assert_called_once()
            mock_client.ws_set_options.assert_called_once()

    @pytest.mark.asyncio
    async def test_attempt_cloud_connection_invalid_credentials(self, mock_hass):
        """Test cloud connection attempt with invalid credentials."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="CLOUD123",
            host="192.168.1.100",
            credential="local_cred",
        )

        # Test with invalid JSON
        result = await device._attempt_cloud_connection(
            "aws-iot-endpoint.amazonaws.com", "invalid_json"
        )

        assert result is False

        # Test with missing required fields
        result = await device._attempt_cloud_connection(
            "aws-iot-endpoint.amazonaws.com",
            '{"client_id":"dyson_12345"}',  # Missing other required fields
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_attempt_local_connection_success(self, mock_hass):
        """Test successful local connection attempt."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="LOCAL123",
            host="192.168.1.100",
            credential="local_cred",
        )

        # Mock executor job to execute functions
        def mock_executor_job(func, *args):
            if hasattr(func, "__name__") and func.__name__ == "connect":
                return 0  # CONNACK_ACCEPTED
            return func(*args) if args else func()

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        # Mock the network connectivity test to return success
        with patch.object(device, "_test_network_connectivity", return_value=True):
            # Mock the wait for connection to return True
            with (
                patch.object(device, "_wait_for_connection", return_value=True),
                patch("paho.mqtt.client.Client") as mock_client_class,
            ):
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.connect.return_value = 0  # CONNACK_ACCEPTED

                result = await device._attempt_local_connection(
                    "192.168.1.100", "local_cred"
                )

                assert result is True
                mock_client.username_pw_set.assert_called_once_with(
                    "LOCAL123", "local_cred"
                )
            mock_client.connect.assert_called_once_with("192.168.1.100", 1883, 60)

    @pytest.mark.asyncio
    async def test_attempt_local_connection_failure(self, mock_hass):
        """Test failed local connection attempt."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="LOCAL123",
            host="192.168.1.100",
            credential="local_cred",
        )

        # Mock executor job to execute functions
        def mock_executor_job(func, *args):
            if hasattr(func, "__name__") and func.__name__ == "connect":
                return 1  # Connection refused
            return func(*args) if args else func()

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        with patch("paho.mqtt.client.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await device._attempt_local_connection(
                "192.168.1.100", "local_cred"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_disconnect_with_cleanup(self, mock_hass):
        """Test device disconnection with proper cleanup."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="DISCONNECT123",
            host="192.168.1.100",
            credential="local_cred",
        )

        # Mock executor job to execute functions
        def mock_executor_job(func, *args):
            return func(*args) if args else func()

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        # Set up connected state
        mock_client = MagicMock()
        device._mqtt_client = mock_client
        device._connected = True
        device._current_connection_type = "LOCAL"

        await device.disconnect()

        assert device._connected is False
        assert device._current_connection_type == CONNECTION_STATUS_DISCONNECTED
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_reconnect(self, mock_hass):
        """Test force reconnect functionality."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="RECONNECT123",
            host="192.168.1.100",
            credential="local_cred",
        )

        # Set up connected state
        device._connected = True
        device._using_fallback = True

        # Mock disconnect and connect methods
        with (
            patch.object(device, "disconnect") as mock_disconnect,
            patch.object(device, "connect", return_value=True) as mock_connect,
        ):
            result = await device.force_reconnect()

            assert result is True
            mock_disconnect.assert_called_once()
            mock_connect.assert_called_once()
            assert device._last_preferred_retry == 0.0  # Should reset retry timer

    @pytest.mark.asyncio
    async def test_connect_no_client(self, mock_hass, sample_device_data):
        """Test connection when no MQTT client library is available."""
        with patch("custom_components.hass_dyson.device.DysonDevice", None):
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
    async def test_connection_fallback_local_to_cloud(self, mock_hass):
        """Test fallback from local to cloud connection when local fails."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="FALLBACK123",
            host="192.168.1.100",
            credential="local_cred",
            connection_type="local_cloud_fallback",
            cloud_host="aws-iot-endpoint.amazonaws.com",
            cloud_credential='{"client_id":"dyson_12345","custom_authorizer_name":"DysonDeviceAuth","token_key":"token","token_value":"abc123","token_signature":"def456"}',
        )

        # Mock executor job to execute functions
        def mock_executor_job(func, *args):
            return func(*args) if args else func()

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        # Mock local connection to fail, cloud to succeed
        with (
            patch.object(device, "_attempt_local_connection", return_value=False),
            patch.object(device, "_attempt_cloud_connection", return_value=True),
        ):
            result = await device.connect()

            assert result is True
            assert device._using_fallback is True
            assert device._current_connection_type == CONNECTION_STATUS_CLOUD

    @pytest.mark.asyncio
    async def test_connection_fallback_cloud_to_local(self, mock_hass):
        """Test fallback from cloud to local connection when cloud fails."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="FALLBACK123",
            host="192.168.1.100",
            credential="local_cred",
            connection_type="cloud_local_fallback",
            cloud_host="aws-iot-endpoint.amazonaws.com",
            cloud_credential='{"client_id":"dyson_12345","custom_authorizer_name":"DysonDeviceAuth","token_key":"token","token_value":"abc123","token_signature":"def456"}',
        )

        # Mock executor job to execute functions
        def mock_executor_job(func, *args):
            return func(*args) if args else func()

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        # Mock cloud connection to fail, local to succeed
        with (
            patch.object(device, "_attempt_cloud_connection", return_value=False),
            patch.object(device, "_attempt_local_connection", return_value=True),
        ):
            result = await device.connect()

            assert result is True
            assert device._using_fallback is True
            assert device._current_connection_type == CONNECTION_STATUS_LOCAL

    @pytest.mark.asyncio
    async def test_reconnection_backoff_logic(self, mock_hass):
        """Test reconnection attempts respect backoff intervals."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="BACKOFF123",
            host="192.168.1.100",
            credential="local_cred",
        )

        # Set last reconnect attempt to recent time to trigger backoff
        device._last_reconnect_attempt = time.time()
        device._reconnect_backoff = 30.0  # 30 second backoff

        result = await device.connect()

        # Should return False due to backoff
        assert result is False

    @pytest.mark.asyncio
    async def test_preferred_connection_retry_logic(self, mock_hass):
        """Test retry of preferred connection when using fallback."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="RETRY123",
            host="192.168.1.100",
            credential="local_cred",
            connection_type="local_cloud_fallback",
            cloud_host="aws-iot-endpoint.amazonaws.com",
            cloud_credential='{"client_id":"dyson_12345","custom_authorizer_name":"DysonDeviceAuth","token_key":"token","token_value":"abc123","token_signature":"def456"}',
        )

        # Set up fallback state and old preferred retry time
        device._using_fallback = True
        device._last_preferred_retry = time.time() - 400  # Old enough to trigger retry
        device._preferred_retry_interval = 300  # 5 minutes

        # Mock executor job to execute functions
        def mock_executor_job(func, *args):
            return func(*args) if args else func()

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        # Mock preferred connection to succeed
        with patch.object(device, "_attempt_local_connection", return_value=True):
            result = await device.connect()

            assert result is True
            assert device._using_fallback is False
            assert device._current_connection_type == CONNECTION_STATUS_LOCAL

    def test_get_connection_details(self, mock_hass):
        """Test connection details retrieval for different connection types."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="DETAILS123",
            host="192.168.1.100",
            credential="local_cred",
            cloud_host="aws-iot-endpoint.amazonaws.com",
            cloud_credential="cloud_cred",
        )

        # Test local connection details
        host, cred = device._get_connection_details("local")
        assert host == "192.168.1.100"
        assert cred == "local_cred"

        # Test cloud connection details
        host, cred = device._get_connection_details("cloud")
        assert host == "aws-iot-endpoint.amazonaws.com"
        assert cred == "cloud_cred"

        # Test unknown connection type
        host, cred = device._get_connection_details("unknown")
        assert host is None
        assert cred is None

    def test_get_connection_order(self, mock_hass):
        """Test connection order for different connection types."""
        # Test local_only
        device = DysonDevice(
            hass=mock_hass,
            serial_number="ORDER123",
            host="192.168.1.100",
            credential="local_cred",
            connection_type="local_only",
        )
        order = device._get_connection_order()
        assert len(order) == 1
        assert order[0] == ("local", "192.168.1.100", "local_cred")

        # Test cloud_only
        device.connection_type = "cloud_only"
        device.cloud_host = "aws-iot-endpoint.amazonaws.com"
        device.cloud_credential = "cloud_cred"
        order = device._get_connection_order()
        assert len(order) == 1
        assert order[0] == ("cloud", "aws-iot-endpoint.amazonaws.com", "cloud_cred")

        # Test local_cloud_fallback
        device.connection_type = "local_cloud_fallback"
        order = device._get_connection_order()
        assert len(order) == 2
        assert order[0] == ("local", "192.168.1.100", "local_cred")
        assert order[1] == ("cloud", "aws-iot-endpoint.amazonaws.com", "cloud_cred")

        # Test cloud_local_fallback
        device.connection_type = "cloud_local_fallback"
        order = device._get_connection_order()
        assert len(order) == 2
        assert order[0] == ("cloud", "aws-iot-endpoint.amazonaws.com", "cloud_cred")
        assert order[1] == ("local", "192.168.1.100", "local_cred")

    @pytest.mark.asyncio
    async def test_send_command_success(
        self, mock_hass, mock_mqtt_client, sample_device_data
    ):
        """Test successful command sending."""
        with patch("paho.mqtt.client.Client", return_value=mock_mqtt_client):
            mock_mqtt_client.connect.return_value = 0  # CONNACK_ACCEPTED
            mock_mqtt_client.is_connected.return_value = (
                True  # Mock MQTT client as connected
            )

            # Mock async_add_executor_job to actually call the function and return the result
            def mock_executor_job(func, *args):
                return func(*args) if args else func()

            mock_hass.async_add_executor_job.side_effect = mock_executor_job

            device = DysonDevice(
                hass=mock_hass,
                serial_number=sample_device_data["serial_number"],
                host=sample_device_data["host"],
                credential=sample_device_data["credential"],
            )

            # Mock the network connectivity test to return success
            with patch.object(device, "_test_network_connectivity", return_value=True):
                # Mock the wait for connection to return True and set internal state
                def mock_wait_for_connection(conn_type):
                    device._connected = True  # Simulate successful connection
                    return True

                with patch.object(
                    device, "_wait_for_connection", side_effect=mock_wait_for_connection
                ):
                    # Connect first
                    await device.connect()

                    # Ensure device is connected
                    assert device.is_connected is True

                    # Test sending a command
                    await device.send_command("set_fan_speed", {"speed": 5})

                    # Verify the MQTT publish was called
                mock_mqtt_client.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_command_not_connected(self, mock_hass, sample_device_data):
        """Test command sending when not connected."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number=sample_device_data["serial_number"],
            host=sample_device_data["host"],
            credential=sample_device_data["credential"],
        )

        with pytest.raises(
            RuntimeError,
            match=f"Device {sample_device_data['serial_number']} is not connected",
        ):
            await device.send_command("set_fan_speed", {"speed": 5})

    @pytest.mark.asyncio
    async def test_get_state(self, mock_hass, mock_mqtt_client, sample_device_data):
        """Test getting device state."""
        mock_state_data = {
            "product-state": {"fpwr": "ON", "nmdv": "0007", "wacd": "AUTO"}
        }

        with patch("paho.mqtt.client.Client", return_value=mock_mqtt_client):
            mock_mqtt_client.connect.return_value = 0  # CONNACK_ACCEPTED
            mock_mqtt_client.is_connected.return_value = (
                True  # Mock MQTT client as connected
            )

            # Mock async_add_executor_job to actually call the function and return the result
            def mock_executor_job(func, *args):
                return func(*args) if args else func()

            mock_hass.async_add_executor_job.side_effect = mock_executor_job

            device = DysonDevice(
                hass=mock_hass,
                serial_number=sample_device_data["serial_number"],
                host=sample_device_data["host"],
                credential=sample_device_data["credential"],
            )

            # Mock the wait for connection to return True and set internal state
            def mock_wait_for_connection(conn_type):
                device._connected = True  # Simulate successful connection
                return True

            with patch.object(
                device, "_wait_for_connection", side_effect=mock_wait_for_connection
            ):
                # Connect first
                await device.connect()

                # Set up mock state data on the device
                device._state_data = mock_state_data

                state = await device.get_state()

                assert isinstance(state, dict)
                assert state == mock_state_data

    @pytest.mark.asyncio
    async def test_get_faults(self, mock_hass, mock_mqtt_client, sample_device_data):
        """Test getting device faults."""
        with patch("paho.mqtt.client.Client", return_value=mock_mqtt_client):
            mock_mqtt_client.connect.return_value = 0  # CONNACK_ACCEPTED
            mock_mqtt_client.is_connected.return_value = (
                True  # Mock MQTT client as connected
            )

            # Mock async_add_executor_job to actually call the function and return the result
            def mock_executor_job(func, *args):
                return func(*args) if args else func()

            mock_hass.async_add_executor_job.side_effect = mock_executor_job

            device = DysonDevice(
                hass=mock_hass,
                serial_number=sample_device_data["serial_number"],
                host=sample_device_data["host"],
                credential=sample_device_data["credential"],
            )

            # Mock the wait for connection to return True and set internal state
            def mock_wait_for_connection(conn_type):
                device._connected = True  # Simulate successful connection
                return True

            with patch.object(
                device, "_wait_for_connection", side_effect=mock_wait_for_connection
            ):
                # Connect first
                await device.connect()

                faults = await device.get_faults()

                # The faults should be normalized to a list format
                assert isinstance(faults, list)

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_hass, mock_mqtt_client, sample_device_data):
        """Test device disconnection."""
        with patch("paho.mqtt.client.Client", return_value=mock_mqtt_client):
            mock_mqtt_client.connect.return_value = 0  # CONNACK_ACCEPTED
            mock_mqtt_client.is_connected.return_value = (
                True  # Mock MQTT client as connected
            )

            device = DysonDevice(
                hass=mock_hass,
                serial_number=sample_device_data["serial_number"],
                host=sample_device_data["host"],
                credential=sample_device_data["credential"],
            )

            # Execute async_add_executor_job calls immediately
            def mock_executor_job(func, *args):
                return func(*args) if args else func()

            mock_hass.async_add_executor_job.side_effect = mock_executor_job

            # Mock the network connectivity test to return success
            with patch.object(device, "_test_network_connectivity", return_value=True):
                # Mock the wait for connection to return True and set internal state
                def mock_wait_for_connection(conn_type):
                    device._connected = True  # Simulate successful connection
                    return True

                with patch.object(
                    device, "_wait_for_connection", side_effect=mock_wait_for_connection
                ):
                    # Connect first
                    await device.connect()
                    assert device.is_connected is True

                    # Now disconnect
                    mock_mqtt_client.is_connected.return_value = (
                        False  # Mock MQTT client as disconnected
                    )
                await device.disconnect()

                assert device.is_connected is False
                mock_mqtt_client.disconnect.assert_called_once()

    # Network Connectivity Tests
    @pytest.mark.asyncio
    async def test_network_connectivity_success(self, mock_hass):
        """Test successful network connectivity test."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="NETTEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        def mock_executor_job(func, *args):
            # Mock successful socket connection
            if len(args) == 1 and hasattr(args[0], "__getitem__"):
                return None  # Successful connection
            return func(*args) if args else func()

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        with patch("socket.socket") as mock_socket_class:
            mock_socket = MagicMock()
            mock_socket_class.return_value = mock_socket

            result = await device._test_network_connectivity("192.168.1.100", 1883)

            assert result is True
            mock_socket.settimeout.assert_called_once_with(5)
            mock_socket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_network_connectivity_dns_failure(self, mock_hass):
        """Test network connectivity with DNS resolution failure."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="NETTEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        def mock_executor_job(func, *args):
            raise socket.gaierror("Name resolution failed")

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        with patch("socket.socket") as mock_socket_class:
            mock_socket = MagicMock()
            mock_socket_class.return_value = mock_socket

            result = await device._test_network_connectivity("nonexistent.local", 1883)

            assert result is False
            mock_socket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_network_connectivity_timeout(self, mock_hass):
        """Test network connectivity with timeout."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="NETTEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        def mock_executor_job(func, *args):
            raise TimeoutError("Connection timed out")

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        with patch("socket.socket") as mock_socket_class:
            mock_socket = MagicMock()
            mock_socket_class.return_value = mock_socket

            result = await device._test_network_connectivity("192.168.1.100", 1883)

            assert result is False
            mock_socket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_network_connectivity_connection_error(self, mock_hass):
        """Test network connectivity with connection error."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="NETTEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        def mock_executor_job(func, *args):
            raise ConnectionError("Connection refused")

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        with patch("socket.socket") as mock_socket_class:
            mock_socket = MagicMock()
            mock_socket_class.return_value = mock_socket

            result = await device._test_network_connectivity("192.168.1.100", 1883)

            assert result is False
            mock_socket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_network_connectivity_os_error(self, mock_hass):
        """Test network connectivity with OS error."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="NETTEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        def mock_executor_job(func, *args):
            raise OSError("Network unreachable")

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        with patch("socket.socket") as mock_socket_class:
            mock_socket = MagicMock()
            mock_socket_class.return_value = mock_socket

            result = await device._test_network_connectivity("192.168.1.100", 1883)

            assert result is False
            mock_socket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_network_connectivity_unexpected_error(self, mock_hass):
        """Test network connectivity with unexpected error."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="NETTEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        def mock_executor_job(func, *args):
            raise RuntimeError("Unexpected error")

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        with patch("socket.socket") as mock_socket_class:
            mock_socket = MagicMock()
            mock_socket_class.return_value = mock_socket

            result = await device._test_network_connectivity("192.168.1.100", 1883)

            assert result is False
            mock_socket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_local_connection_fails_network_test(self, mock_hass):
        """Test local connection when network connectivity test fails."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="NETFAIL123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Mock network connectivity test to fail
        with patch.object(device, "_test_network_connectivity", return_value=False):
            result = await device._attempt_local_connection(
                "192.168.1.100", "test_cred"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_local_connection_enhanced_error_handling(self, mock_hass):
        """Test enhanced error handling in local connection."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="ERRORTEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Mock executor job to execute functions
        def mock_executor_job(func, *args):
            if hasattr(func, "__name__") and func.__name__ == "connect":
                return 1  # Connection refused
            return func(*args) if args else func()

        mock_hass.async_add_executor_job.side_effect = mock_executor_job

        # Mock network connectivity test to succeed
        with patch.object(device, "_test_network_connectivity", return_value=True):
            with patch("paho.mqtt.client.Client") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.connect.return_value = 1  # Connection refused

                result = await device._attempt_local_connection(
                    "192.168.1.100", "test_cred"
                )

                assert result is False


class TestDysonDeviceConnectionLogic:
    """Test the advanced connection logic and fallback mechanisms."""

    @pytest.fixture
    def mock_hass(self):
        """Mock Home Assistant instance."""
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock()
        return hass

    def test_get_preferred_connection_type_cloud_only(self, mock_hass):
        """Test preferred connection type for cloud_only configuration."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
            connection_type="cloud_only",
            cloud_host="cloud.example.com",
            cloud_credential="cloud_cred",
        )

        assert device._get_preferred_connection_type() == "cloud"

    def test_get_preferred_connection_type_cloud_local_fallback(self, mock_hass):
        """Test preferred connection type for cloud_local_fallback configuration."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
            connection_type="cloud_local_fallback",
            cloud_host="cloud.example.com",
            cloud_credential="cloud_cred",
        )

        assert device._get_preferred_connection_type() == "cloud"

    def test_get_preferred_connection_type_local_cloud_fallback(self, mock_hass):
        """Test preferred connection type for local_cloud_fallback configuration."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
            connection_type="local_cloud_fallback",
            cloud_host="cloud.example.com",
            cloud_credential="cloud_cred",
        )

        assert device._get_preferred_connection_type() == "local"

    def test_get_preferred_connection_type_unknown_defaults_to_local(self, mock_hass):
        """Test that unknown connection types default to local."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
            connection_type="some_unknown_type",
        )

        assert device._get_preferred_connection_type() == "local"

    def test_check_reconnect_backoff_active(self, mock_hass):
        """Test reconnect backoff when still in backoff period."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Set last reconnect attempt to current time minus half the backoff period
        device._last_reconnect_attempt = time.time() - (device._reconnect_backoff / 2)

        result = device._check_reconnect_backoff()
        assert result is False

    def test_check_reconnect_backoff_expired(self, mock_hass):
        """Test reconnect backoff when backoff period has expired."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Set last reconnect attempt to time beyond backoff period
        device._last_reconnect_attempt = time.time() - (device._reconnect_backoff + 1)

        result = device._check_reconnect_backoff()
        assert result is True

    def test_get_connection_details_local(self, mock_hass):
        """Test getting connection details for local connection."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        host, credential = device._get_connection_details("local")
        assert host == "192.168.1.100"
        assert credential == "test_cred"

    def test_get_connection_details_cloud(self, mock_hass):
        """Test getting connection details for cloud connection."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
            cloud_host="cloud.example.com",
            cloud_credential="cloud_cred",
        )

        host, credential = device._get_connection_details("cloud")
        assert host == "cloud.example.com"
        assert credential == "cloud_cred"

    def test_get_connection_details_unknown_type(self, mock_hass):
        """Test getting connection details for unknown connection type."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        host, credential = device._get_connection_details("unknown")
        assert host is None
        assert credential is None

    def test_get_connection_order_local_cloud_fallback(self, mock_hass):
        """Test connection order for local_cloud_fallback."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
            connection_type="local_cloud_fallback",
            cloud_host="cloud.example.com",
            cloud_credential="cloud_cred",
        )

        order = device._get_connection_order()
        expected = [
            ("local", "192.168.1.100", "test_cred"),
            ("cloud", "cloud.example.com", "cloud_cred"),
        ]
        assert order == expected

    def test_get_connection_order_cloud_local_fallback(self, mock_hass):
        """Test connection order for cloud_local_fallback."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
            connection_type="cloud_local_fallback",
            cloud_host="cloud.example.com",
            cloud_credential="cloud_cred",
        )

        order = device._get_connection_order()
        expected = [
            ("cloud", "cloud.example.com", "cloud_cred"),
            ("local", "192.168.1.100", "test_cred"),
        ]
        assert order == expected

    def test_get_connection_order_cloud_only(self, mock_hass):
        """Test connection order for cloud_only."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
            connection_type="cloud_only",
            cloud_host="cloud.example.com",
            cloud_credential="cloud_cred",
        )

        order = device._get_connection_order()
        expected = [("cloud", "cloud.example.com", "cloud_cred")]
        assert order == expected

    def test_should_retry_preferred_true(self, mock_hass):
        """Test should retry preferred when conditions are met."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Set last preferred retry to time beyond retry interval
        device._last_preferred_retry = time.time() - (
            device._preferred_retry_interval + 1
        )

        result = device._should_retry_preferred()
        assert result is True

    def test_should_retry_preferred_false(self, mock_hass):
        """Test should retry preferred when still in retry interval."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Set last preferred retry to current time
        device._last_preferred_retry = time.time()

        result = device._should_retry_preferred()
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_with_backoff_active(self, mock_hass):
        """Test connect when reconnection backoff is active."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Set last reconnect attempt to current time (backoff active)
        device._last_reconnect_attempt = time.time()

        result = await device.connect()
        assert result is False

    def test_connection_status_property(self, mock_hass):
        """Test connection status property."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Test disconnected state
        device._current_connection_type = CONNECTION_STATUS_DISCONNECTED
        assert device.connection_status == CONNECTION_STATUS_DISCONNECTED

        # Test local connection
        device._current_connection_type = CONNECTION_STATUS_LOCAL
        assert device.connection_status == CONNECTION_STATUS_LOCAL

        # Test cloud connection
        device._current_connection_type = CONNECTION_STATUS_CLOUD
        assert device.connection_status == CONNECTION_STATUS_CLOUD


class TestDysonDeviceMessageHandling:
    """Test message handling and callback functionality."""

    @pytest.fixture
    def mock_hass(self):
        """Mock Home Assistant instance."""
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock()
        return hass

    def test_add_and_remove_environmental_callback(self, mock_hass):
        """Test adding and removing environmental callbacks."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        callback = MagicMock()

        # Add callback
        device.add_environmental_callback(callback)
        assert callback in device._environmental_callbacks

        # Remove callback
        device.remove_environmental_callback(callback)
        assert callback not in device._environmental_callbacks

    def test_add_and_remove_message_callback(self, mock_hass):
        """Test adding and removing message callbacks."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        callback = MagicMock()

        # Add callback
        device.add_message_callback(callback)
        assert callback in device._message_callbacks

        # Remove callback
        device.remove_message_callback(callback)
        assert callback not in device._message_callbacks

    def test_handle_current_state(self, mock_hass):
        """Test handling current state updates."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        test_data = {"fpwr": "ON", "nmdv": "0005", "wacd": "AUTO"}
        test_topic = "475/TEST123/status/current"
        device._handle_current_state(test_data, test_topic)

        assert device._state_data == test_data

    def test_handle_environmental_data(self, mock_hass):
        """Test handling environmental data updates."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Add callback to verify it gets triggered
        callback = MagicMock()
        device.add_environmental_callback(callback)

        # Add some PM data to ensure the callback gets triggered
        test_data = {
            "msg": "ENVIRONMENTAL-CURRENT-SENSOR-DATA",
            "data": {
                "tact": "2990",
                "hact": "0645",
                "pact": "0002",
                "pm25": "010",
                "pm10": "020",
            },
        }
        device._handle_environmental_data(test_data)

        # Environmental data stores only the "data" part
        expected_data = {
            "tact": "2990",
            "hact": "0645",
            "pact": "0002",
            "pm25": "010",
            "pm10": "020",
        }
        assert device._environmental_data == expected_data
        callback.assert_called_once()

    def test_handle_faults_data(self, mock_hass):
        """Test handling faults data updates."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        test_data = {"ercd": "NONE", "filf": "4300", "fmod": "OFF"}
        device._handle_faults_data(test_data)

        assert device._faults_data == test_data

    def test_handle_state_change(self, mock_hass):
        """Test handling state change updates."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        test_data = {
            "msg": "STATE-CHANGE",
            "product-state": {"fpwr": "OFF", "nmdv": "0001"},
        }
        device._handle_state_change(test_data)

        # Should update state data with the product state part
        expected_product_state = {"product-state": {"fpwr": "OFF", "nmdv": "0001"}}
        assert device._state_data == expected_product_state

    def test_notify_callbacks(self, mock_hass):
        """Test notification of message callbacks."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Add callback
        callback = MagicMock()
        device.add_message_callback(callback)

        test_topic = "test/topic"
        test_data = {"test": "data"}

        device._notify_callbacks(test_topic, test_data)
        callback.assert_called_once_with(test_topic, test_data)

    def test_get_timestamp(self, mock_hass):
        """Test timestamp generation."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        timestamp = device._get_timestamp()
        assert isinstance(timestamp, str)
        assert len(timestamp) > 0

    def test_is_connected_property(self, mock_hass):
        """Test is_connected property."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Test disconnected state (no mqtt client)
        device._connected = False
        device._mqtt_client = None
        assert device.is_connected is False

        # Test connected state with mqtt client
        mock_mqtt_client = MagicMock()
        mock_mqtt_client.is_connected.return_value = True
        device._connected = True
        device._mqtt_client = mock_mqtt_client
        assert device.is_connected is True


class TestDysonDeviceFaultHandling:
    """Test fault handling and normalization functionality."""

    @pytest.fixture
    def mock_hass(self):
        """Mock Home Assistant instance."""
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock()
        return hass

    def test_normalize_faults_to_list_with_dict(self, mock_hass):
        """Test normalizing fault dict to list format."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        fault_dict = {"aqs": "FAIL", "tds": "WARN"}
        result = device._normalize_faults_to_list(fault_dict)

        # Check that the faults are normalized correctly with proper structure
        assert len(result) == 2
        # Check that each fault has the expected keys
        for fault in result:
            assert "code" in fault
            assert "value" in fault
            assert "description" in fault
            assert "timestamp" in fault

        # Check specific fault codes
        fault_codes = [fault["code"] for fault in result]
        assert "aqs" in fault_codes
        assert "tds" in fault_codes

    def test_normalize_faults_to_list_with_list(self, mock_hass):
        """Test normalizing fault list (already normalized)."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Provide a list of dict that looks like faults data
        fault_list = [{"aqs": "FAIL", "tds": "OK"}]
        result = device._normalize_faults_to_list(fault_list)

        # Should process the dict inside the list and filter out OK values
        assert len(result) == 1  # Only FAIL, not OK
        assert result[0]["code"] == "aqs"
        assert result[0]["value"] == "FAIL"

    def test_normalize_faults_to_list_with_none(self, mock_hass):
        """Test normalizing None faults."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        result = device._normalize_faults_to_list(None)
        assert result == []

    def test_normalize_faults_to_list_with_invalid_type(self, mock_hass):
        """Test normalizing invalid fault type."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        result = device._normalize_faults_to_list("invalid_string")
        assert result == []

    def test_translate_fault_code_known(self, mock_hass):
        """Test translating known fault codes."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Test with a known fault code (assuming "aqs" exists in FAULT_TRANSLATIONS)
        result = device._translate_fault_code("aqs", "FAIL")
        # Should return the translation if it exists, otherwise the original
        assert isinstance(result, str)
        assert len(result) > 0

    def test_translate_fault_code_unknown(self, mock_hass):
        """Test translating unknown fault codes."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        result = device._translate_fault_code("unknown_code", "FAIL")
        assert result == "UNKNOWN_CODE fault: FAIL"

    @pytest.mark.asyncio
    async def test_get_faults_when_disconnected(self, mock_hass):
        """Test getting faults when device is disconnected."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        device._connected = False
        result = await device.get_faults()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_faults_with_cached_data(self, mock_hass):
        """Test getting faults with cached fault data."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        device._connected = True
        device._faults_data = {"aqs": "FAIL", "tds": "OK"}

        result = await device.get_faults()
        # Should only return the FAIL fault, filtering out OK
        assert len(result) == 1
        assert result[0]["code"] == "aqs"
        assert result[0]["value"] == "FAIL"


class TestDysonDeviceProperties:
    """Test device property methods."""

    @pytest.fixture
    def device_with_state(self, mock_hass):
        """Create device with mock state data."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="PROP123",
            host="192.168.1.100",
            credential="test_cred",
        )
        return device

    def test_fan_power_with_fpwr_on(self, device_with_state):
        """Test fan_power property when fpwr is ON."""
        # Setup device state with fpwr ON
        device_with_state._state_data = {"product-state": {"fpwr": "ON", "fnst": "FAN"}}

        result = device_with_state.fan_power

        assert result is True

    def test_fan_power_with_fpwr_off(self, device_with_state):
        """Test fan_power property when fpwr is OFF."""
        # Setup device state with fpwr OFF
        device_with_state._state_data = {
            "product-state": {"fpwr": "OFF", "fnst": "FAN"}
        }

        result = device_with_state.fan_power

        assert result is False

    def test_fan_power_no_fpwr_fnst_fan(self, device_with_state):
        """Test fan_power property fallback to fnst when fpwr missing and fnst is FAN."""
        # Setup device state without fpwr but with fnst FAN
        device_with_state._state_data = {
            "product-state": {"fnst": "FAN", "fnsp": "0007"}
        }

        result = device_with_state.fan_power

        assert result is True

    def test_fan_power_no_fpwr_fnst_off(self, device_with_state):
        """Test fan_power property fallback to fnst when fpwr missing and fnst is OFF."""
        # Setup device state without fpwr but with fnst OFF
        device_with_state._state_data = {"product-state": {"fnst": "OFF"}}

        result = device_with_state.fan_power

        assert result is False

    def test_fan_power_no_fpwr_no_fnst(self, device_with_state):
        """Test fan_power property when both fpwr and fnst are missing."""
        # Setup device state without fpwr or fnst
        device_with_state._state_data = {"product-state": {"hmod": "OFF"}}

        result = device_with_state.fan_power

        assert result is False

    def test_fan_power_empty_state(self, device_with_state):
        """Test fan_power property with empty state data."""
        # Setup empty device state
        device_with_state._state_data = {}

        result = device_with_state.fan_power

        assert result is False

    def test_fan_power_no_product_state(self, device_with_state):
        """Test fan_power property without product-state key."""
        # Setup device state without product-state
        device_with_state._state_data = {"some-other-data": {}}

        result = device_with_state.fan_power

        assert result is False


class TestDysonDeviceMQTTCallbacks:
    """Test MQTT connection and callback functionality."""

    @pytest.fixture
    def mock_hass(self):
        """Mock Home Assistant instance."""
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock()
        return hass

    @pytest.fixture
    def mock_mqtt_client(self):
        """Mock MQTT client for paho-mqtt."""
        client = MagicMock()
        client.is_connected = MagicMock(return_value=True)
        client.connect = MagicMock()
        client.disconnect = MagicMock()
        client.publish = MagicMock()
        return client

    def test_on_connect_success(self, mock_hass, mock_mqtt_client):
        """Test successful MQTT connection callback."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        device._mqtt_client = mock_mqtt_client
        mock_hass.async_create_task = MagicMock()
        mock_hass.loop = MagicMock()
        mock_hass.loop.call_soon_threadsafe = MagicMock()

        # Simulate successful connection (rc = 0)
        device._on_connect(mock_mqtt_client, None, {}, 0)

        assert device._connected is True
        # Should subscribe to topics
        assert mock_mqtt_client.subscribe.call_count == 6
        # Should schedule task twice: once for requesting current state, once for heartbeat (API v2 change)
        assert mock_hass.loop.call_soon_threadsafe.call_count == 2

    def test_on_connect_failure(self, mock_hass, mock_mqtt_client):
        """Test failed MQTT connection callback."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        device._mqtt_client = mock_mqtt_client

        # Simulate failed connection (rc != 0)
        device._on_connect(mock_mqtt_client, None, {}, 1)

        assert device._connected is False
        # Should not subscribe to any topics on failure
        mock_mqtt_client.subscribe.assert_not_called()

    def test_on_disconnect(self, mock_hass, mock_mqtt_client):
        """Test MQTT disconnection callback."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        device._mqtt_client = mock_mqtt_client
        device._connected = True

        # Simulate disconnection (API v2 signature with flags parameter)
        mock_flags = MagicMock()
        device._on_disconnect(mock_mqtt_client, None, mock_flags, 0)

        assert device._connected is False
        assert device._current_connection_type == CONNECTION_STATUS_DISCONNECTED

    def test_on_message_valid_json(self, mock_hass, mock_mqtt_client):
        """Test MQTT message callback with valid JSON."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Mock message
        message = MagicMock()
        message.topic = "475/TEST123/status/current"
        message.payload = b'{"msg": "STATE-CHANGE", "product-state": {"fpwr": "ON"}}'

        # Mock the _process_message_data method to verify it's called
        device._process_message_data = MagicMock()

        device._on_message(mock_mqtt_client, None, message)

        expected_data = {"msg": "STATE-CHANGE", "product-state": {"fpwr": "ON"}}
        device._process_message_data.assert_called_once_with(
            expected_data, "475/TEST123/status/current"
        )

    def test_on_message_invalid_json(self, mock_hass, mock_mqtt_client):
        """Test MQTT message callback with invalid JSON."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Mock message with invalid JSON
        message = MagicMock()
        message.topic = "475/TEST123/status/current"
        message.payload = b"invalid json{"

        device._process_message_data = MagicMock()

        # Should handle gracefully and not crash
        device._on_message(mock_mqtt_client, None, message)

        # _process_message_data should not be called with invalid JSON
        device._process_message_data.assert_not_called()

    def test_process_message_data_state_change(self, mock_hass):
        """Test processing state change messages."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        device._handle_state_change = MagicMock()
        device._notify_callbacks = MagicMock()

        data = {"msg": "STATE-CHANGE", "product-state": {"fpwr": "ON"}}
        topic = "475/TEST123/status/current"

        device._process_message_data(data, topic)

        device._handle_state_change.assert_called_once_with(data)
        device._notify_callbacks.assert_called_once_with(topic, data)

    def test_process_message_data_environmental_current_data(self, mock_hass):
        """Test processing environmental current data messages."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        device._handle_environmental_data = MagicMock()
        device._notify_callbacks = MagicMock()

        data = {"msg": "ENVIRONMENTAL-CURRENT-SENSOR-DATA", "data": {"tact": "2990"}}
        topic = "475/TEST123/status/current"

        device._process_message_data(data, topic)

        device._handle_environmental_data.assert_called_once_with(data)
        device._notify_callbacks.assert_called_once_with(topic, data)

    def test_process_message_data_current_state(self, mock_hass):
        """Test processing current state messages."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        device._handle_current_state = MagicMock()
        device._notify_callbacks = MagicMock()

        data = {"msg": "CURRENT-STATE", "product-state": {"fpwr": "OFF"}}
        topic = "475/TEST123/status/current"

        device._process_message_data(data, topic)

        device._handle_current_state.assert_called_once_with(data, topic)
        device._notify_callbacks.assert_called_once_with(topic, data)

    @pytest.mark.asyncio
    async def test_set_target_temperature_valid(self, mock_hass, mock_mqtt_client):
        """Test setting target temperature with valid value."""
        with patch("paho.mqtt.client.Client", return_value=mock_mqtt_client):
            mock_mqtt_client.connect.return_value = 0  # CONNACK_ACCEPTED
            mock_mqtt_client.is_connected.return_value = True

            # Mock async_add_executor_job to actually call the function
            def mock_executor_job(func, *args):
                return func(*args) if args else func()

            mock_hass.async_add_executor_job.side_effect = mock_executor_job

            device = DysonDevice(
                hass=mock_hass,
                serial_number="TEST123",
                host="192.168.1.100",
                credential="test_cred",
            )

            # Mock connection state
            device._connected = True
            device._mqtt_client = mock_mqtt_client

            # Test setting valid temperature
            await device.set_target_temperature(22.5)

            # Verify MQTT publish was called with correct data
            mock_mqtt_client.publish.assert_called_once()
            call_args = mock_mqtt_client.publish.call_args

            # Parse the JSON command
            import json

            command_data = json.loads(
                call_args[0][1]
            )  # Second argument is the JSON payload

            assert command_data["msg"] == "STATE-SET"
            assert command_data["data"]["hmod"] == "HEAT"
            # 22.5°C = 295.65K = 2956.5 -> 2956 (int conversion)
            assert command_data["data"]["hmax"] == "2956"

    @pytest.mark.asyncio
    async def test_set_target_temperature_out_of_range_low(self, mock_hass):
        """Test setting target temperature below minimum range."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        with pytest.raises(
            ValueError, match="Target temperature must be between 1°C and 37°C"
        ):
            await device.set_target_temperature(0.5)  # Below 1°C

    @pytest.mark.asyncio
    async def test_set_target_temperature_out_of_range_high(self, mock_hass):
        """Test setting target temperature above maximum range."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        with pytest.raises(
            ValueError, match="Target temperature must be between 1°C and 37°C"
        ):
            await device.set_target_temperature(37.5)  # Above 37°C

    @pytest.mark.asyncio
    async def test_set_target_temperature_not_connected(self, mock_hass):
        """Test setting target temperature when device is not connected."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="TEST123",
            host="192.168.1.100",
            credential="test_cred",
        )

        # Device is not connected (default state)
        assert device._connected is False

        # Should raise RuntimeError when device is not connected
        with pytest.raises(RuntimeError, match="Device TEST123 is not connected"):
            await device.set_target_temperature(22.0)

        # No MQTT client should have been used since device is not connected
