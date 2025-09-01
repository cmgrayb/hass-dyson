"""Dyson device wrapper using paho-mqtt directly."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

import paho.mqtt.client as mqtt
from homeassistant.core import HomeAssistant

from .const import CONNECTION_STATUS_CLOUD, CONNECTION_STATUS_DISCONNECTED, CONNECTION_STATUS_LOCAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class DysonDevice:
    """Wrapper for Dyson device communication using paho-mqtt directly."""

    def __init__(
        self,
        hass: HomeAssistant,
        serial_number: str,
        host: str,
        credential: str,
        mqtt_prefix: str = "475",  # Default, will be overridden
        capabilities: Optional[List[str]] = None,
        connection_type: str = "local_cloud_fallback",
        cloud_host: Optional[str] = None,
        cloud_credential: Optional[str] = None,
    ) -> None:
        """Initialize the device wrapper."""
        self.hass = hass
        self.serial_number = serial_number
        self.host = host  # Local host
        self.credential = credential  # Local credential
        self.mqtt_prefix = mqtt_prefix
        self.capabilities = capabilities or []
        self.connection_type = connection_type
        self.cloud_host = cloud_host
        self.cloud_credential = cloud_credential

        self._mqtt_client: Optional[mqtt.Client] = None
        self._connected = False
        self._current_connection_type: str = CONNECTION_STATUS_DISCONNECTED  # Track current connection
        self._preferred_connection_type: str = self._get_preferred_connection_type()  # Store preferred type
        self._using_fallback: bool = False  # Track if we're using fallback connection
        self._last_reconnect_attempt = 0.0  # Track last reconnection attempt
        self._last_preferred_retry = 0.0  # Track last preferred connection retry
        self._reconnect_backoff = 30.0  # Wait 30 seconds between reconnect attempts
        self._preferred_retry_interval = 300.0  # Retry preferred connection every 5 minutes
        self._state_data: Dict[str, Any] = {}
        self._environmental_data: Dict[str, Any] = {}
        self._faults_data: Dict[str, Any] = {}  # Raw fault data from device
        self._message_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

        # Device info from successful connection
        self._device_info: Optional[Dict[str, Any]] = None
        self._firmware_version: str = "Unknown"

    def _get_preferred_connection_type(self) -> str:
        """Determine the preferred connection type based on connection_type setting."""
        if self.connection_type == "cloud_only":
            return "cloud"
        elif self.connection_type == "cloud_local_fallback":
            return "cloud"
        else:
            # local_only, local_cloud_fallback, or any unknown type defaults to local
            return "local"

    async def connect(self) -> bool:
        """Connect to the device using paho-mqtt with intelligent fallback support."""
        # Check reconnection backoff to prevent rapid reconnection attempts
        current_time = time.time()
        if current_time - self._last_reconnect_attempt < self._reconnect_backoff:
            time_remaining = self._reconnect_backoff - (current_time - self._last_reconnect_attempt)
            _LOGGER.debug(
                "Reconnection backoff active for %s, waiting %.1f more seconds",
                self.serial_number,
                time_remaining,
            )
            return False

        self._last_reconnect_attempt = current_time

        # After disconnection, try preferred connection first (one retry)
        if not self._connected and self._using_fallback:
            _LOGGER.debug(
                "Attempting to reconnect to preferred connection after disconnection for %s", self.serial_number
            )

            preferred_host, preferred_credential = self._get_connection_details(self._preferred_connection_type)
            if preferred_host and preferred_credential:
                if await self._attempt_connection(
                    self._preferred_connection_type, preferred_host, preferred_credential
                ):
                    self._using_fallback = False
                    self._current_connection_type = (
                        CONNECTION_STATUS_LOCAL
                        if self._preferred_connection_type == "local"
                        else CONNECTION_STATUS_CLOUD
                    )
                    _LOGGER.info(
                        "Successfully reconnected to preferred connection (%s) after disconnection for %s",
                        self._preferred_connection_type.upper(),
                        self.serial_number,
                    )
                    return True

            _LOGGER.debug("Failed to reconnect to preferred connection, falling back to connection order")

        # If we're using fallback connection, check if it's time to retry preferred
        if self._using_fallback and self._should_retry_preferred():
            _LOGGER.debug("Attempting to reconnect to preferred connection type for %s", self.serial_number)

            # Try preferred connection once
            preferred_host, preferred_credential = self._get_connection_details(self._preferred_connection_type)
            if preferred_host and preferred_credential:
                if await self._attempt_connection(
                    self._preferred_connection_type, preferred_host, preferred_credential
                ):
                    self._using_fallback = False
                    self._current_connection_type = (
                        CONNECTION_STATUS_LOCAL
                        if self._preferred_connection_type == "local"
                        else CONNECTION_STATUS_CLOUD
                    )
                    _LOGGER.info(
                        "Successfully reconnected to preferred connection (%s) for %s",
                        self._preferred_connection_type.upper(),
                        self.serial_number,
                    )
                    return True

            self._last_preferred_retry = current_time

        # Initial connection or fallback reconnection logic
        connection_attempts = self._get_connection_order()

        # Try each connection method in order
        for conn_type, host, credential in connection_attempts:
            if host is None or credential is None:
                _LOGGER.debug("Skipping %s connection - missing host or credential", conn_type)
                continue

            _LOGGER.debug("Attempting %s connection to %s for device %s", conn_type, host, self.serial_number)

            if await self._attempt_connection(conn_type, host, credential):
                # Track if we're using fallback
                self._using_fallback = conn_type != self._preferred_connection_type
                self._current_connection_type = (
                    CONNECTION_STATUS_LOCAL if conn_type == "local" else CONNECTION_STATUS_CLOUD
                )

                _LOGGER.info(
                    "Successfully connected to %s via %s%s",
                    self.serial_number,
                    conn_type.upper(),
                    " (fallback)" if self._using_fallback else "",
                )
                return True

        _LOGGER.error("Failed to connect to device %s via any method", self.serial_number)
        self._current_connection_type = CONNECTION_STATUS_DISCONNECTED
        self._using_fallback = False
        return False

    def _should_retry_preferred(self) -> bool:
        """Check if it's time to retry the preferred connection."""
        current_time = time.time()
        return (current_time - self._last_preferred_retry) >= self._preferred_retry_interval

    def _get_connection_details(self, conn_type: str) -> tuple[Optional[str], Optional[str]]:
        """Get connection details for a specific connection type."""
        if conn_type == "local":
            return self.host, self.credential
        elif conn_type == "cloud":
            return self.cloud_host, self.cloud_credential
        return None, None

    def _get_connection_order(self) -> list[tuple[str, Optional[str], Optional[str]]]:
        """Get the connection order based on connection type."""
        if self.connection_type == "local_only":
            return [("local", self.host, self.credential)]
        elif self.connection_type == "cloud_only":
            return [("cloud", self.cloud_host, self.cloud_credential)]
        elif self.connection_type == "local_cloud_fallback":
            return [
                ("local", self.host, self.credential),
                ("cloud", self.cloud_host, self.cloud_credential),
            ]
        elif self.connection_type == "cloud_local_fallback":
            return [
                ("cloud", self.cloud_host, self.cloud_credential),
                ("local", self.host, self.credential),
            ]
        else:
            # Default to local with cloud fallback
            return [
                ("local", self.host, self.credential),
                ("cloud", self.cloud_host, self.cloud_credential),
            ]

    async def _attempt_connection(self, conn_type: str, host: str, credential: str) -> bool:
        """Attempt a single connection method."""

        try:
            _LOGGER.debug("Connecting to device %s at %s", self.serial_number, host)
            _LOGGER.debug("Using credential length: %s", len(credential) if credential else 0)
            _LOGGER.debug("Using MQTT prefix: %s", self.mqtt_prefix)

            # Skip connection if host or credential is missing
            if not host or not credential:
                _LOGGER.debug("Missing host or credential for %s connection to %s", conn_type, self.serial_number)
                return False

            if conn_type == "local":
                return await self._attempt_local_connection(host, credential)
            else:  # cloud connection
                return await self._attempt_cloud_connection(host, credential)

        except Exception as err:
            _LOGGER.error("Connection attempt failed for %s: %s", self.serial_number, err)
            return False

    async def _attempt_local_connection(self, host: str, credential: str) -> bool:
        """Attempt local MQTT connection."""
        try:
            # Create paho MQTT client for local connection
            client_id = f"dyson-ha-local-{uuid.uuid4().hex[:8]}"
            username = self.serial_number

            _LOGGER.debug("Using MQTT client ID: %s", client_id)
            _LOGGER.debug("Using MQTT username: %s", username)

            mqtt_client = mqtt.Client(client_id=client_id)
            self._mqtt_client = mqtt_client

            # Set up authentication
            mqtt_client.username_pw_set(username, credential)

            # Set up callbacks
            mqtt_client.on_connect = self._on_connect
            mqtt_client.on_disconnect = self._on_disconnect
            mqtt_client.on_message = self._on_message

            # Connect to local MQTT broker
            port = 1883
            _LOGGER.debug("Attempting local MQTT connection to %s:%s", host, port)

            result = await self.hass.async_add_executor_job(mqtt_client.connect, host, port, 60)

            if result == mqtt.CONNACK_ACCEPTED:
                # Start the network loop in a thread
                await self.hass.async_add_executor_job(mqtt_client.loop_start)

                # Wait for connection to be established
                return await self._wait_for_connection("local")
            else:
                _LOGGER.debug("Local MQTT connection failed with result: %s", result)
                return False

        except Exception as err:
            _LOGGER.error("Local connection failed: %s", err)
            return False

    async def _attempt_cloud_connection(self, host: str, credential: str) -> bool:
        """Attempt AWS IoT WebSocket MQTT connection."""
        try:
            # Parse AWS IoT credentials from JSON string
            try:
                cloud_credentials = json.loads(credential)
                client_id = cloud_credentials.get("client_id", "")
                custom_authorizer_name = cloud_credentials.get("custom_authorizer_name", "")
                token_key = cloud_credentials.get("token_key", "token")
                token_value = cloud_credentials.get("token_value", "")
                token_signature = cloud_credentials.get("token_signature", "")

                if not all([client_id, custom_authorizer_name, token_value, token_signature]):
                    _LOGGER.error(
                        "Incomplete AWS IoT credentials: client_id=%s, authorizer=%s, token=%s, signature=%s",
                        bool(client_id),
                        bool(custom_authorizer_name),
                        bool(token_value),
                        bool(token_signature),
                    )
                    return False

                _LOGGER.debug(
                    "Parsed AWS IoT credentials: client_id=%s, authorizer=%s", client_id, custom_authorizer_name
                )
                _LOGGER.debug("AWS IoT client_id length: %s", len(client_id))

            except (json.JSONDecodeError, KeyError) as err:
                _LOGGER.error("Failed to parse cloud credentials: %s", err)
                return False

            # Create paho MQTT client for WebSocket connection with exact client_id
            # Note: For AWS IoT, the client_id must be exact - no prefixes allowed
            mqtt_client = mqtt.Client(client_id=client_id, transport="websockets")

            _LOGGER.debug("Created MQTT client with exact ID: %s", client_id)
            _LOGGER.debug("MQTT client internal ID: %s", mqtt_client._client_id)

            self._mqtt_client = mqtt_client

            # Set up TLS for secure WebSocket connection
            mqtt_client.tls_set()

            # Set up WebSocket headers for AWS IoT Custom Authorizer
            # Following OpenDyson Go implementation: use HTTP headers instead of query parameters
            websocket_headers = {
                "Host": host,
                token_key: token_value,  # Token value in header
                "X-Amz-CustomAuthorizer-Name": custom_authorizer_name,
                "X-Amz-CustomAuthorizer-Signature": token_signature,
            }

            # Set custom WebSocket headers (if paho-mqtt supports it)
            if hasattr(mqtt_client, "ws_set_options"):
                # Set WebSocket path and headers (following OpenDyson pattern)
                mqtt_client.ws_set_options(path="/mqtt", headers=websocket_headers)
                _LOGGER.debug("Set WebSocket headers: %s", list(websocket_headers.keys()))
            else:
                _LOGGER.warning("WebSocket options not supported in this paho-mqtt version")

            # Set up callbacks
            mqtt_client.on_connect = self._on_connect
            mqtt_client.on_disconnect = self._on_disconnect
            mqtt_client.on_message = self._on_message

            # Connect to AWS IoT WebSocket endpoint on port 443
            port = 443
            _LOGGER.debug("Attempting AWS IoT WebSocket connection to %s:%s", host, port)

            result = await self.hass.async_add_executor_job(mqtt_client.connect, host, port, 60)

            if result == mqtt.CONNACK_ACCEPTED:
                # Start the network loop in a thread
                await self.hass.async_add_executor_job(mqtt_client.loop_start)

                # Wait for connection to be established
                return await self._wait_for_connection("cloud")
            else:
                _LOGGER.debug("AWS IoT WebSocket connection failed with result: %s", result)
                return False

        except Exception as err:
            _LOGGER.error("AWS IoT connection failed: %s", err)
            return False

    async def _wait_for_connection(self, conn_type: str) -> bool:
        """Wait for MQTT connection to be established."""
        connection_timeout = 10  # 10 seconds timeout
        check_interval = 0.1  # Check every 100ms
        elapsed_time = 0

        while elapsed_time < connection_timeout:
            if self._connected:
                _LOGGER.info(
                    "Successfully connected to device %s via %s after %.1f seconds",
                    self.serial_number,
                    conn_type,
                    elapsed_time,
                )
                return True

            await asyncio.sleep(check_interval)
            elapsed_time += check_interval

        _LOGGER.debug("Connection timeout for device %s via %s", self.serial_number, conn_type)
        return False

    @property
    def connection_status(self) -> str:
        """Return current connection status."""
        return self._current_connection_type

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._mqtt_client and self._connected:
            try:
                _LOGGER.debug("Disconnecting from device %s", self.serial_number)
                await self.hass.async_add_executor_job(self._mqtt_client.loop_stop)
                await self.hass.async_add_executor_job(self._mqtt_client.disconnect)
                self._connected = False
                self._current_connection_type = CONNECTION_STATUS_DISCONNECTED
                # Don't reset _using_fallback here - we want to remember if we were using fallback
                # for the next reconnection attempt
            except Exception as err:
                _LOGGER.error("Failed to disconnect from device %s: %s", self.serial_number, err)

    async def force_reconnect(self) -> bool:
        """Force a reconnection attempt with preferred connection priority."""
        _LOGGER.info("Force reconnect triggered for %s", self.serial_number)

        # Disconnect if currently connected
        if self._connected:
            await self.disconnect()

        # Reset preferred retry timer to force immediate preferred connection attempt
        self._last_preferred_retry = 0.0

        # Attempt reconnection with full intelligent logic
        return await self.connect()

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int) -> None:
        """Handle MQTT connection callback."""
        if rc == mqtt.CONNACK_ACCEPTED:
            _LOGGER.info("MQTT connected to device %s", self.serial_number)
            self._connected = True

            # Subscribe to device topics
            topics_to_subscribe = [
                f"{self.mqtt_prefix}/{self.serial_number}/status/current",
                f"{self.mqtt_prefix}/{self.serial_number}/status/faults",
                f"{self.mqtt_prefix}/{self.serial_number}/status/connection",
                f"{self.mqtt_prefix}/{self.serial_number}/status/software",
                f"{self.mqtt_prefix}/{self.serial_number}/status/summary",
                f"{self.mqtt_prefix}/{self.serial_number}/#",  # Subscribe to all topics for this device
            ]

            for topic in topics_to_subscribe:
                client.subscribe(topic)
                _LOGGER.debug("Subscribed to topic: %s", topic)

            # Request initial device state
            self.hass.create_task(self._request_current_state())
        else:
            _LOGGER.error("MQTT connection failed for device %s with code: %s", self.serial_number, rc)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        """Handle MQTT disconnection callback."""
        _LOGGER.warning("MQTT client disconnected for %s, code: %s", self.serial_number, rc)
        self._connected = False
        self._current_connection_type = CONNECTION_STATUS_DISCONNECTED

        # If this is an unexpected disconnection (not initiated by us), prepare for intelligent reconnection
        if rc != mqtt.MQTT_ERR_SUCCESS:
            _LOGGER.info(
                "Unexpected disconnection for %s, will retry preferred connection on next attempt", self.serial_number
            )
            # Reset the preferred retry timer so we'll try preferred connection first on next connect
            self._last_preferred_retry = 0.0

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        """Handle MQTT message callback."""
        try:
            topic = message.topic
            payload = message.payload

            _LOGGER.debug("Received MQTT message on %s: %s", topic, payload[:100])
            _LOGGER.info("MQTT MESSAGE RECEIVED for %s - Topic: %s", self.serial_number, topic)

            # Log the full payload for filter debugging
            _LOGGER.debug("Full message payload for %s: %s", self.serial_number, payload)

            # Parse JSON payload
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")

            data = json.loads(payload)
            _LOGGER.debug("Parsed message data for %s: %s", self.serial_number, data)
            _LOGGER.info("MQTT PARSED DATA for %s: %s", self.serial_number, data)

            self._process_message_data(data, topic)

        except Exception as err:
            _LOGGER.error("Error handling MQTT message for %s: %s", self.serial_number, err)

    def _process_message_data(self, data: Dict[str, Any], topic: str) -> None:
        """Process parsed message data by type."""
        message_type = data.get("msg", "")
        _LOGGER.debug("Processing message type '%s' for device %s", message_type, self.serial_number)

        # Handle different message types based on our successful test
        if message_type == "CURRENT-STATE":
            _LOGGER.debug("Processing CURRENT-STATE message for %s", self.serial_number)
            self._handle_current_state(data)
        elif message_type == "ENVIRONMENTAL-CURRENT-SENSOR-DATA":
            _LOGGER.debug("Processing ENVIRONMENTAL-CURRENT-SENSOR-DATA message for %s", self.serial_number)
            self._handle_environmental_data(data)
        elif message_type == "CURRENT-FAULTS":
            _LOGGER.debug("Processing CURRENT-FAULTS message for %s", self.serial_number)
            self._handle_faults_data(data)
        elif message_type == "STATE-CHANGE":
            _LOGGER.debug("Processing STATE-CHANGE message for %s", self.serial_number)
            self._handle_state_change(data)
        else:
            _LOGGER.debug("Unknown message type '%s' for device %s: %s", message_type, self.serial_number, data)

        # Notify callbacks
        self._notify_callbacks(topic, data)

    def _handle_current_state(self, data: Dict[str, Any]) -> None:
        """Handle current state message."""
        _LOGGER.debug("Received current state data for %s: %s", self.serial_number, data)

        # Check specifically for filter data
        product_state = data.get("product-state", {})
        if product_state:
            _LOGGER.debug("Product state contains: %s", list(product_state.keys()))

            # Log all filter-related fields
            filter_fields = ["hflr", "cflr", "fflr", "hflt", "cflt", "fflt"]
            for field in filter_fields:
                value = product_state.get(field)
                if value is not None:
                    _LOGGER.debug("Filter field %s: %s", field, value)

        self._state_data.update(data)
        _LOGGER.debug("Updated device state for %s", self.serial_number)

    def _handle_environmental_data(self, data: Dict[str, Any]) -> None:
        """Handle environmental sensor data message."""
        self._environmental_data.update(data.get("data", {}))
        _LOGGER.debug("Updated environmental data for %s", self.serial_number)

    def _handle_faults_data(self, data: Dict[str, Any]) -> None:
        """Handle faults data message."""
        self._faults_data.update(data)
        _LOGGER.debug("Updated faults for %s", self.serial_number)

    def _handle_state_change(self, data: Dict[str, Any]) -> None:
        """Handle state change message."""
        _LOGGER.debug("Received state change data for %s: %s", self.serial_number, data)

        product_state = data.get("product-state", {})
        if product_state:
            _LOGGER.debug("State change product state contains: %s", list(product_state.keys()))
            hflr = product_state.get("hflr")
            cflr = product_state.get("cflr")
            if hflr is not None:
                _LOGGER.debug("HEPA filter life (hflr) in state change: %s", hflr)
            if cflr is not None:
                _LOGGER.debug("Carbon filter life (cflr) in state change: %s", cflr)

        if "product-state" not in self._state_data:
            self._state_data["product-state"] = {}
        self._state_data["product-state"].update(product_state)
        _LOGGER.debug("State change for %s", self.serial_number)

    def _notify_callbacks(self, topic: str, data: Dict[str, Any]) -> None:
        """Notify registered callbacks of new message."""
        for msg_callback in self._message_callbacks:
            try:
                msg_callback(topic, data)
            except Exception as err:
                _LOGGER.error("Error in message callback: %s", err)

    async def _request_current_state(self) -> None:
        """Request current state from device."""
        if not self._connected or not self._mqtt_client:
            return

        try:
            command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
            timestamp = self._get_timestamp()
            command = json.dumps({"msg": "REQUEST-CURRENT-STATE", "time": timestamp, "mode-reason": "RAPP"})

            _LOGGER.debug("Publishing to topic: %s", command_topic)
            _LOGGER.debug("Publishing command: %s", command)

            result = await self.hass.async_add_executor_job(self._mqtt_client.publish, command_topic, command)
            _LOGGER.debug("Publish result: %s", result)
            _LOGGER.debug("Requested current state from %s", self.serial_number)

            # Give device time to respond
            await asyncio.sleep(3.0)

        except Exception as err:
            _LOGGER.error("Failed to request state from %s: %s", self.serial_number, err)

    async def _request_current_faults(self) -> None:
        """Request current faults from device."""
        if not self._connected or not self._mqtt_client:
            return

        try:
            command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
            timestamp = self._get_timestamp()
            command = json.dumps({"msg": "REQUEST-CURRENT-FAULTS", "time": timestamp, "mode-reason": "RAPP"})

            await self.hass.async_add_executor_job(self._mqtt_client.publish, command_topic, command)
            _LOGGER.debug("Requested current faults from %s", self.serial_number)

        except Exception as err:
            _LOGGER.error("Failed to request faults from %s: %s", self.serial_number, err)

    def _get_timestamp(self) -> str:
        """Get timestamp in the format expected by Dyson devices."""
        return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

    @property
    def is_connected(self) -> bool:
        """Return if device is connected."""
        if not self._connected or not self._mqtt_client:
            return False

        # Check if the underlying MQTT client is actually connected
        try:
            if hasattr(self._mqtt_client, "is_connected"):
                mqtt_connected = self._mqtt_client.is_connected()
                if not mqtt_connected and self._connected:
                    _LOGGER.warning("MQTT client disconnected for %s, updating connection state", self.serial_number)
                    self._connected = False
                return mqtt_connected
        except Exception as err:
            _LOGGER.warning("Failed to check MQTT connection status for %s: %s", self.serial_number, err)
            self._connected = False
            return False

        return self._connected

    async def send_command(self, command: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Send a command to the device."""
        if not self._connected or not self._mqtt_client:
            raise RuntimeError(f"Device {self.serial_number} is not connected")

        try:
            _LOGGER.debug("Sending command %s to device %s", command, self.serial_number)

            # Handle heartbeat commands (REQUEST-CURRENT-STATE and REQUEST-CURRENT-FAULTS)
            if command == "REQUEST-CURRENT-STATE":
                await self._request_current_state()
                return
            elif command == "REQUEST-CURRENT-FAULTS":
                await self._request_current_faults()
                return

            # For other commands, use the generic command format
            command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"

            if data:
                # If data is provided, construct command with data
                command_msg = {"msg": command, "time": self._get_timestamp(), "mode-reason": "RAPP"}
                command_msg.update(data)
                command_json = json.dumps(command_msg)
            else:
                # Simple command without additional data
                command_json = json.dumps({"msg": command})

            await self.hass.async_add_executor_job(self._mqtt_client.publish, command_topic, command_json)
            _LOGGER.debug("Sent command %s to %s", command, self.serial_number)

        except Exception as err:
            _LOGGER.error("Failed to send command %s to device %s: %s", command, self.serial_number, err)
            raise

    async def get_state(self) -> Dict[str, Any]:
        """Get current device state."""
        if not self._connected or not self._mqtt_client:
            _LOGGER.debug("Device %s not connected, returning cached state", self.serial_number)
            return self._state_data

        try:
            # Get state from paho-mqtt client
            if hasattr(self._mqtt_client, "get_state"):
                state = await self.hass.async_add_executor_job(self._mqtt_client.get_state)  # type: ignore[attr-defined]
                if state:
                    _LOGGER.debug("Received state data for %s: %s", self.serial_number, state)
                    self._state_data.update(state)
                else:
                    _LOGGER.debug("No state data returned from get_state for %s", self.serial_number)
            elif hasattr(self._mqtt_client, "state"):
                # Some MQTT clients might have a state property
                state = getattr(self._mqtt_client, "state", {})
                if state:
                    _LOGGER.debug("Received state from property for %s: %s", self.serial_number, state)
                    self._state_data.update(state)
                else:
                    _LOGGER.debug("No state data in property for %s", self.serial_number)

        except Exception as err:
            _LOGGER.warning("Failed to get state from device %s: %s", self.serial_number, err)

        _LOGGER.debug("Final state data for %s: %s", self.serial_number, self._state_data)
        return self._state_data

    def _normalize_faults_to_list(self, faults: Any) -> List[Dict[str, Any]]:
        """Normalize faults data to list format, filtering out OK statuses."""
        from .const import FAULT_TRANSLATIONS

        if not faults:
            return []

        actual_faults = []

        # Handle different fault data formats
        if isinstance(faults, list):
            fault_data_list = faults
        else:
            fault_data_list = [faults]

        for fault_data in fault_data_list:
            if not isinstance(fault_data, dict):
                continue

            # Process each fault key in the data
            for fault_key, fault_value in fault_data.items():
                # Skip if the value indicates no fault (OK, NONE, etc.)
                if not fault_value or fault_value in ["OK", "NONE", "PASS", "GOOD"]:
                    continue

                # Get human-readable description
                fault_description = self._translate_fault_code(fault_key, fault_value)

                actual_faults.append(
                    {
                        "code": fault_key,
                        "value": fault_value,
                        "description": fault_description,
                        "timestamp": fault_data.get("timestamp"),
                    }
                )

        # Store the raw fault data for other methods
        if not isinstance(faults, list):
            self._faults_data = faults

        return actual_faults

    def _translate_fault_code(self, fault_key: str, fault_value: str) -> str:
        """Translate a fault code and value to human-readable description."""
        from .const import FAULT_TRANSLATIONS

        # Get translation for this fault key
        fault_translations = FAULT_TRANSLATIONS.get(fault_key, {})

        # Try to get specific translation for this value
        if fault_value in fault_translations:
            return fault_translations[fault_value]

        # Fallback to generic description
        return f"{fault_key.upper()} fault: {fault_value}"

    async def _get_faults_from_client(self) -> List[Dict[str, Any]]:
        """Get faults from MQTT client."""
        if not self._mqtt_client:
            return []

        # Try get_faults method
        if hasattr(self._mqtt_client, "get_faults"):
            faults = await self.hass.async_add_executor_job(self._mqtt_client.get_faults)  # type: ignore[attr-defined]
            if faults:
                return self._normalize_faults_to_list(faults)

        # Try faults property
        elif hasattr(self._mqtt_client, "faults"):
            faults = getattr(self._mqtt_client, "faults", {})
            if faults:
                return self._normalize_faults_to_list(faults)

        return []

    async def get_faults(self) -> List[Dict[str, Any]]:
        """Get device faults."""
        if not self._connected or not self._mqtt_client:
            return self._normalize_faults_to_list(self._faults_data)

        try:
            faults = await self._get_faults_from_client()
            if faults:
                return faults
        except Exception as err:
            _LOGGER.warning("Failed to get faults from device %s: %s", self.serial_number, err)

        return self._normalize_faults_to_list(self._faults_data)

    def set_firmware_version(self, firmware_version: str) -> None:
        """Set the firmware version for this device."""
        if firmware_version and firmware_version != "Unknown":
            self._firmware_version = firmware_version
            _LOGGER.debug("Set firmware version for %s: %s", self.serial_number, firmware_version)

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information for Home Assistant."""
        return {
            "identifiers": {(DOMAIN, self.serial_number)},
            "name": f"Dyson {self.serial_number}",
            "manufacturer": "Dyson",
            "model": self.mqtt_prefix,  # Use MQTT prefix as model indicator
            "sw_version": self._firmware_version,
        }

    # Properties for device state (based on our MQTT test data)
    @property
    def night_mode(self) -> bool:
        """Return if night mode is enabled (nmod)."""
        nmod = self._state_data.get("product-state", {}).get("nmod", "OFF")
        return nmod == "ON"

    @property
    def auto_mode(self) -> bool:
        """Return if auto mode is enabled (wacd)."""
        wacd = self._state_data.get("product-state", {}).get("wacd", "NONE")
        return wacd != "NONE"

    @property
    def fan_speed(self) -> int:
        """Return fan speed (nmdv)."""
        try:
            nmdv = self._state_data.get("product-state", {}).get("nmdv", "0000")
            return int(nmdv)
        except (ValueError, TypeError):
            return 0

    @property
    def brightness(self) -> int:
        """Return display brightness (bril)."""
        try:
            bril = self._state_data.get("product-state", {}).get("bril", "0002")
            return int(bril)
        except (ValueError, TypeError):
            return 2

    # Environmental sensor properties (from our MQTT test)
    @property
    def pm25(self) -> int:
        """Return PM2.5 reading."""
        try:
            pm25 = self._environmental_data.get("pm25", "0000")
            return int(pm25)
        except (ValueError, TypeError):
            return 0

    @property
    def pm10(self) -> int:
        """Return PM10 reading."""
        try:
            pm10 = self._environmental_data.get("pm10", "0000")
            return int(pm10)
        except (ValueError, TypeError):
            return 0

    @property
    def rssi(self) -> int:
        """Return WiFi signal strength."""
        try:
            rssi = self._state_data.get("rssi", "-99")
            return int(rssi)
        except (ValueError, TypeError):
            return -99

    @property
    def filter_status(self) -> str:
        """Return filter status."""
        return self._faults_data.get("product-warnings", {}).get("fltr", "Unknown")

    @property
    def hepa_filter_life(self) -> int:
        """Return HEPA filter life percentage."""
        try:
            product_state = self._state_data.get("product-state", {})

            # Check filter types to determine which field to use
            hflt = product_state.get("hflt", "NONE")
            cflt = product_state.get("cflt", "NONE")

            # Debug logging to troubleshoot filter life issue
            _LOGGER.debug("HEPA filter life debug for %s:", self.serial_number)
            _LOGGER.debug("  HEPA filter type (hflt): %s", hflt)
            _LOGGER.debug("  Carbon filter type (cflt): %s", cflt)
            _LOGGER.debug("  Product state keys: %s", list(product_state.keys()))

            # For combination filters (GCOM), the life might be in a different field
            if hflt == "GCOM" or cflt == "GCOM":
                _LOGGER.debug("  Detected GCOM (combination) filter")
                # Try checking for fflr (combination filter life) first
                fflr = product_state.get("fflr")
                if fflr is not None and fflr != "INV":
                    _LOGGER.debug("  Using fflr (combination filter life): %s", fflr)
                    try:
                        result = int(fflr)
                        _LOGGER.debug("  Converted fflr to int: %s", result)
                        return result
                    except (ValueError, TypeError):
                        _LOGGER.warning("  Failed to convert fflr value: %s", fflr)

            # Fall back to standard hflr field
            hflr = product_state.get("hflr", "0000")
            _LOGGER.debug("  Raw hflr value: %s (type: %s)", hflr, type(hflr))

            if hflr == "INV":  # Invalid/no filter installed
                _LOGGER.debug("  HEPA filter marked as INV (invalid/no filter)")
                return 0

            result = int(hflr)
            _LOGGER.debug("  Converted hflr to int: %s", result)
            return result
        except (ValueError, TypeError) as e:
            _LOGGER.warning("Failed to parse HEPA filter life for %s: %s", self.serial_number, e)
            return 0

    @property
    def carbon_filter_life(self) -> int:
        """Return carbon filter life percentage."""
        try:
            cflr = self._state_data.get("product-state", {}).get("cflr", "0000")
            if cflr == "INV":  # Invalid/no filter installed
                return 0
            return int(cflr)
        except (ValueError, TypeError):
            return 0

    @property
    def hepa_filter_type(self) -> str:
        """Return HEPA filter type."""
        filter_type = self._state_data.get("product-state", {}).get("hflt", "NONE")
        _LOGGER.debug("HEPA filter type for %s: %s", self.serial_number, filter_type)
        return filter_type

    @property
    def carbon_filter_type(self) -> str:
        """Return carbon filter type."""
        filter_type = self._state_data.get("product-state", {}).get("cflt", "NONE")
        _LOGGER.debug("Carbon filter type for %s: %s", self.serial_number, filter_type)
        return filter_type

    # Command methods for device control
    async def set_night_mode(self, enabled: bool) -> None:
        """Set night mode on/off."""
        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
        nmod_value = "ON" if enabled else "OFF"
        command = json.dumps({"msg": "STATE-SET", "data": {"nmod": nmod_value}})

        if self._mqtt_client:
            await self.hass.async_add_executor_job(self._mqtt_client.publish, command_topic, command)

    async def set_fan_speed(self, speed: int) -> None:
        """Set fan speed (0-10)."""
        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
        speed_str = f"{speed:04d}"  # Format as 4-digit string like device expects
        command = json.dumps({"msg": "STATE-SET", "data": {"nmdv": speed_str}})

        if self._mqtt_client:
            await self.hass.async_add_executor_job(self._mqtt_client.publish, command_topic, command)

    async def reset_hepa_filter_life(self) -> None:
        """Reset HEPA filter life to 100%."""
        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
        command = json.dumps({"msg": "STATE-SET", "data": {"hflr": "0100"}})

        if self._mqtt_client:
            await self.hass.async_add_executor_job(self._mqtt_client.publish, command_topic, command)

    async def reset_carbon_filter_life(self) -> None:
        """Reset carbon filter life to 100%."""
        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
        command = json.dumps({"msg": "STATE-SET", "data": {"cflr": "0100"}})

        if self._mqtt_client:
            await self.hass.async_add_executor_job(self._mqtt_client.publish, command_topic, command)

    async def set_sleep_timer(self, minutes: int) -> None:
        """Set sleep timer in minutes (0 to cancel, 15-540 for active timer)."""
        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"

        # Convert minutes to the format expected by the device
        # Dyson uses a specific encoding for sleep timer values
        if minutes == 0:
            timer_value = "OFF"
        else:
            # Ensure minutes is within valid range
            minutes = max(15, min(540, minutes))
            # Convert to 4-digit string format (e.g., 15 minutes = "0015", 240 minutes = "0240")
            timer_value = f"{minutes:04d}"

        command = json.dumps({"msg": "STATE-SET", "data": {"sltm": timer_value}})

        if self._mqtt_client:
            await self.hass.async_add_executor_job(self._mqtt_client.publish, command_topic, command)

    async def set_oscillation_angles(self, lower_angle: int, upper_angle: int) -> None:
        """Set custom oscillation angles."""
        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"

        # Ensure angles are within valid range (0-350 degrees)
        lower_angle = max(0, min(350, lower_angle))
        upper_angle = max(0, min(350, upper_angle))

        # Ensure lower angle is less than upper angle
        if lower_angle >= upper_angle:
            raise ValueError("Lower angle must be less than upper angle")

        # Convert angles to 4-digit string format
        lower_str = f"{lower_angle:04d}"
        upper_str = f"{upper_angle:04d}"

        command = json.dumps(
            {
                "msg": "STATE-SET",
                "data": {
                    "osal": lower_str,  # Oscillation angle lower
                    "osau": upper_str,  # Oscillation angle upper
                    "oson": "ON",  # Enable oscillation
                },
            }
        )

        if self._mqtt_client:
            await self.hass.async_add_executor_job(self._mqtt_client.publish, command_topic, command)
