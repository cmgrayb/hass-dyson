"""Dyson device wrapper using paho-mqtt directly."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant

from .const import (
    CONNECTION_STATUS_CLOUD,
    CONNECTION_STATUS_DISCONNECTED,
    CONNECTION_STATUS_LOCAL,
    DOMAIN,
    FAULT_TRANSLATIONS,
    MQTT_CMD_REQUEST_ENVIRONMENT,
)

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
        capabilities: list[str] | None = None,
        connection_type: str = "local_cloud_fallback",
        cloud_host: str | None = None,
        cloud_credential: str | None = None,
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

        self._mqtt_client: mqtt.Client | None = None
        self._connected = False
        self._current_connection_type: str = (
            CONNECTION_STATUS_DISCONNECTED  # Track current connection
        )
        self._preferred_connection_type: str = (
            self._get_preferred_connection_type()
        )  # Store preferred type
        self._using_fallback: bool = False  # Track if we're using fallback connection
        self._last_reconnect_attempt = 0.0  # Track last reconnection attempt
        self._last_preferred_retry = 0.0  # Track last preferred connection retry
        self._reconnect_backoff = 30.0  # Wait 30 seconds between reconnect attempts
        self._preferred_retry_interval = (
            300.0  # Retry preferred connection every 5 minutes
        )

        # Heartbeat mechanism to keep device active and get regular updates
        self._heartbeat_interval = 30.0  # Send REQUEST-CURRENT-STATE every 30 seconds
        self._heartbeat_task: asyncio.Task | None = None
        self._last_heartbeat = 0.0
        self._state_data: dict[str, Any] = {}
        self._environmental_data: dict[str, Any] = {}
        self._faults_data: dict[str, Any] = {}  # Raw fault data from device
        self._message_callbacks: list[Callable[[str, dict[str, Any]], None]] = []
        self._environmental_callbacks: list[
            Callable[[], None]
        ] = []  # Environmental update callbacks

        _LOGGER.debug(
            "Initialized environmental data as empty dict for %s", serial_number
        )

        # Device info from successful connection
        self._device_info: dict[str, Any] | None = None
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
        if not self._check_reconnect_backoff():
            return False

        self._last_reconnect_attempt = time.time()

        # Try preferred connection after disconnection
        if await self._try_preferred_connection_after_disconnect():
            return True

        # Try preferred connection if using fallback and it's time to retry
        if await self._try_preferred_connection_retry():
            return True

        # Try connections in order
        return await self._try_connection_order()

    def _check_reconnect_backoff(self) -> bool:
        """Check if reconnection backoff period has passed."""
        current_time = time.time()
        if current_time - self._last_reconnect_attempt < self._reconnect_backoff:
            time_remaining = self._reconnect_backoff - (
                current_time - self._last_reconnect_attempt
            )
            _LOGGER.debug(
                "Reconnection backoff active for %s, waiting %.1f more seconds",
                self.serial_number,
                time_remaining,
            )
            return False
        return True

    async def _try_preferred_connection_after_disconnect(self) -> bool:
        """Try preferred connection after disconnection."""
        if not self._connected and self._using_fallback:
            _LOGGER.debug(
                "Attempting to reconnect to preferred connection after disconnection for %s",
                self.serial_number,
            )

            preferred_host, preferred_credential = self._get_connection_details(
                self._preferred_connection_type
            )
            if preferred_host and preferred_credential:
                if await self._attempt_connection(
                    self._preferred_connection_type,
                    preferred_host,
                    preferred_credential,
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

            _LOGGER.debug(
                "Failed to reconnect to preferred connection, falling back to connection order"
            )
        return False

    async def _try_preferred_connection_retry(self) -> bool:
        """Try preferred connection if using fallback and it's time to retry."""
        if self._using_fallback and self._should_retry_preferred():
            _LOGGER.debug(
                "Attempting to reconnect to preferred connection type for %s",
                self.serial_number,
            )

            preferred_host, preferred_credential = self._get_connection_details(
                self._preferred_connection_type
            )
            if preferred_host and preferred_credential:
                if await self._attempt_connection(
                    self._preferred_connection_type,
                    preferred_host,
                    preferred_credential,
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

            self._last_preferred_retry = time.time()
        return False

    async def _try_connection_order(self) -> bool:
        """Try connections in order until one succeeds."""
        connection_attempts = self._get_connection_order()

        # Try each connection method in order
        for conn_type, host, credential in connection_attempts:
            if host is None or credential is None:
                _LOGGER.debug(
                    "Skipping %s connection - missing host or credential", conn_type
                )
                continue

            _LOGGER.debug(
                "Attempting %s connection to %s for device %s",
                conn_type,
                host,
                self.serial_number,
            )

            if await self._attempt_connection(conn_type, host, credential):
                # Track if we're using fallback
                self._using_fallback = conn_type != self._preferred_connection_type
                self._current_connection_type = (
                    CONNECTION_STATUS_LOCAL
                    if conn_type == "local"
                    else CONNECTION_STATUS_CLOUD
                )

                _LOGGER.info(
                    "Successfully connected to %s via %s%s",
                    self.serial_number,
                    conn_type.upper(),
                    " (fallback)" if self._using_fallback else "",
                )
                return True

        _LOGGER.error(
            "Failed to connect to device %s via any method", self.serial_number
        )
        self._current_connection_type = CONNECTION_STATUS_DISCONNECTED
        self._using_fallback = False
        return False

    def _should_retry_preferred(self) -> bool:
        """Check if it's time to retry the preferred connection."""
        current_time = time.time()
        return (
            current_time - self._last_preferred_retry
        ) >= self._preferred_retry_interval

    def _get_connection_details(self, conn_type: str) -> tuple[str | None, str | None]:
        """Get connection details for a specific connection type."""
        if conn_type == "local":
            return self.host, self.credential
        elif conn_type == "cloud":
            return self.cloud_host, self.cloud_credential
        return None, None

    def _get_connection_order(self) -> list[tuple[str, str | None, str | None]]:
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

    async def _attempt_connection(
        self, conn_type: str, host: str, credential: str
    ) -> bool:
        """Attempt a single connection method."""

        try:
            _LOGGER.debug("Connecting to device %s at %s", self.serial_number, host)
            _LOGGER.debug(
                "Using credential length: %s", len(credential) if credential else 0
            )
            _LOGGER.debug("Using MQTT prefix: %s", self.mqtt_prefix)

            # Skip connection if host or credential is missing
            if not host or not credential:
                _LOGGER.debug(
                    "Missing host or credential for %s connection to %s",
                    conn_type,
                    self.serial_number,
                )
                return False

            if conn_type == "local":
                return await self._attempt_local_connection(host, credential)
            else:  # cloud connection
                return await self._attempt_cloud_connection(host, credential)

        except Exception as err:
            _LOGGER.error(
                "Connection attempt failed for %s: %s", self.serial_number, err
            )
            return False

    async def _attempt_local_connection(self, host: str, credential: str) -> bool:
        """Attempt local MQTT connection."""
        try:
            # Create paho MQTT client for local connection
            client_id = f"dyson-ha-local-{uuid.uuid4().hex[:8]}"
            username = self.serial_number

            _LOGGER.debug("Using MQTT client ID: %s", client_id)
            _LOGGER.debug("Using MQTT username: %s", username)

            mqtt_client = mqtt.Client(
                client_id=client_id,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            )
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

            result = await self.hass.async_add_executor_job(
                mqtt_client.connect, host, port, 60
            )

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
                custom_authorizer_name = cloud_credentials.get(
                    "custom_authorizer_name", ""
                )
                token_key = cloud_credentials.get("token_key", "token")
                token_value = cloud_credentials.get("token_value", "")
                token_signature = cloud_credentials.get("token_signature", "")

                if not all(
                    [client_id, custom_authorizer_name, token_value, token_signature]
                ):
                    _LOGGER.error(
                        "Incomplete AWS IoT credentials: client_id=%s, authorizer=%s, token=%s, signature=%s",
                        bool(client_id),
                        bool(custom_authorizer_name),
                        bool(token_value),
                        bool(token_signature),
                    )
                    return False

                _LOGGER.debug(
                    "Parsed AWS IoT credentials: client_id=%s, authorizer=%s",
                    client_id,
                    custom_authorizer_name,
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
            # Use executor to avoid blocking SSL operations in the event loop
            await self.hass.async_add_executor_job(mqtt_client.tls_set)

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
                _LOGGER.debug(
                    "Set WebSocket headers: %s", list(websocket_headers.keys())
                )
            else:
                _LOGGER.warning(
                    "WebSocket options not supported in this paho-mqtt version"
                )

            # Set up callbacks
            mqtt_client.on_connect = self._on_connect
            mqtt_client.on_disconnect = self._on_disconnect
            mqtt_client.on_message = self._on_message

            # Connect to AWS IoT WebSocket endpoint on port 443
            port = 443
            _LOGGER.debug(
                "Attempting AWS IoT WebSocket connection to %s:%s", host, port
            )

            result = await self.hass.async_add_executor_job(
                mqtt_client.connect, host, port, 60
            )

            if result == mqtt.CONNACK_ACCEPTED:
                # Start the network loop in a thread
                await self.hass.async_add_executor_job(mqtt_client.loop_start)

                # Wait for connection to be established
                return await self._wait_for_connection("cloud")
            else:
                _LOGGER.debug(
                    "AWS IoT WebSocket connection failed with result: %s", result
                )
                return False

        except Exception as err:
            _LOGGER.error("AWS IoT connection failed: %s", err)
            return False

    async def _wait_for_connection(self, conn_type: str) -> bool:
        """Wait for MQTT connection to be established."""
        connection_timeout = 10  # 10 seconds timeout
        check_interval = 0.1  # Check every 100ms
        elapsed_time = 0.0

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

        _LOGGER.debug(
            "Connection timeout for device %s via %s", self.serial_number, conn_type
        )
        return False

    @property
    def connection_status(self) -> str:
        """Return current connection status."""
        return self._current_connection_type

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        # Stop heartbeat before disconnecting
        await self._stop_heartbeat()

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
                _LOGGER.error(
                    "Failed to disconnect from device %s: %s", self.serial_number, err
                )

    async def _start_heartbeat(self) -> None:
        """Start the heartbeat task to keep device active."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()

        # If Home Assistant is still starting up, wait for it to complete
        if not self.hass.is_running:
            _LOGGER.debug(
                "Home Assistant is starting, delaying heartbeat for device %s",
                self.serial_number,
            )

            def start_heartbeat_after_startup(event: Any) -> None:  # noqa: ARG001
                """Start heartbeat after HA startup completes."""
                _LOGGER.debug(
                    "Home Assistant startup complete, starting heartbeat for device %s",
                    self.serial_number,
                )
                # Use call_soon_threadsafe to schedule task from potentially different thread
                self.hass.loop.call_soon_threadsafe(
                    lambda: self.hass.async_create_task(self._start_heartbeat_now())
                )

            # Register one-time listener for startup completion
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, start_heartbeat_after_startup
            )
            return

        # Home Assistant is already running, start heartbeat immediately
        await self._start_heartbeat_now()

    async def _start_heartbeat_now(self) -> None:
        """Actually start the heartbeat loop."""
        _LOGGER.debug("Starting heartbeat for device %s", self.serial_number)
        self._last_heartbeat = time.time()  # Initialize heartbeat time
        self._heartbeat_task = self.hass.async_create_task(self._heartbeat_loop())

    async def _stop_heartbeat(self) -> None:
        """Stop the heartbeat task."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            _LOGGER.debug("Stopping heartbeat for device %s", self.serial_number)
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

    async def _heartbeat_loop(self) -> None:
        """Heartbeat loop that sends REQUEST-CURRENT-STATE every 30 seconds."""
        _LOGGER.debug("Heartbeat loop started for device %s", self.serial_number)

        while self._connected:
            try:
                await asyncio.sleep(self._heartbeat_interval)

                if not self._connected:
                    break

                current_time = time.time()
                if current_time - self._last_heartbeat >= self._heartbeat_interval:
                    _LOGGER.debug("Sending heartbeat to device %s", self.serial_number)
                    await self._request_current_state()
                    # Check for faults on each heartbeat per discovery.md requirements
                    await self._request_current_faults()
                    self._last_heartbeat = current_time

            except asyncio.CancelledError:
                _LOGGER.debug(
                    "Heartbeat loop cancelled for device %s", self.serial_number
                )
                break
            except Exception as err:
                _LOGGER.error(
                    "Error in heartbeat loop for %s: %s", self.serial_number, err
                )
                # Continue the loop despite errors
                await asyncio.sleep(5)  # Brief pause before retry

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

    def _on_connect(
        self, client: mqtt.Client, userdata: Any, flags, rc, properties=None, *args
    ) -> None:
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

            # Request initial device state (schedule safely from callback)
            # Note: REQUEST-CURRENT-STATE automatically includes environmental data
            self.hass.loop.call_soon_threadsafe(
                lambda: self.hass.async_create_task(self._request_current_state())
            )

            # Start heartbeat to keep device active and get regular updates
            self.hass.loop.call_soon_threadsafe(
                lambda: self.hass.async_create_task(self._start_heartbeat())
            )
        else:
            _LOGGER.error(
                "MQTT connection failed for device %s with code: %s",
                self.serial_number,
                rc,
            )

    def _on_disconnect(
        self, client: mqtt.Client, userdata: Any, rc, properties=None, *args
    ) -> None:
        """Handle MQTT disconnection callback."""
        _LOGGER.warning(
            "MQTT client disconnected for %s, code: %s", self.serial_number, rc
        )
        self._connected = False
        self._current_connection_type = CONNECTION_STATUS_DISCONNECTED

        # Stop heartbeat when disconnected
        self.hass.loop.call_soon_threadsafe(
            lambda: self.hass.async_create_task(self._stop_heartbeat())
        )

        # If this is an unexpected disconnection (not initiated by us), prepare for intelligent reconnection
        if rc != mqtt.MQTT_ERR_SUCCESS:
            _LOGGER.info(
                "Unexpected disconnection for %s, will retry preferred connection on next attempt",
                self.serial_number,
            )
            # Reset the preferred retry timer so we'll try preferred connection first on next connect
            self._last_preferred_retry = 0.0

    def _on_message(
        self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        """Handle MQTT message callback."""
        try:
            topic = message.topic
            payload: str | bytes = message.payload

            _LOGGER.debug("Received MQTT message on %s: %s", topic, payload[:100])
            _LOGGER.info(
                "MQTT MESSAGE RECEIVED for %s - Topic: %s", self.serial_number, topic
            )

            # Log the full payload for filter debugging
            _LOGGER.debug(
                "Full message payload for %s: %s", self.serial_number, payload
            )

            # Parse JSON payload
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")

            data = json.loads(payload)
            _LOGGER.debug("Parsed message data for %s: %s", self.serial_number, data)
            _LOGGER.info("MQTT PARSED DATA for %s: %s", self.serial_number, data)

            self._process_message_data(data, topic)

        except Exception as err:
            _LOGGER.error(
                "Error handling MQTT message for %s: %s", self.serial_number, err
            )

    def _process_message_data(self, data: dict[str, Any], topic: str) -> None:
        """Process parsed message data by type."""
        message_type = data.get("msg", "")
        _LOGGER.debug(
            "Processing message type '%s' for device %s",
            message_type,
            self.serial_number,
        )

        # Handle different message types based on our successful test
        if message_type == "CURRENT-STATE":
            _LOGGER.debug("Processing CURRENT-STATE message for %s", self.serial_number)
            self._handle_current_state(data, topic)
        elif message_type == "ENVIRONMENTAL-CURRENT-SENSOR-DATA":
            _LOGGER.debug(
                "Processing ENVIRONMENTAL-CURRENT-SENSOR-DATA message for %s",
                self.serial_number,
            )
            self._handle_environmental_data(data)
        elif message_type == "CURRENT-FAULTS":
            _LOGGER.debug(
                "Processing CURRENT-FAULTS message for %s", self.serial_number
            )
            self._handle_faults_data(data)
        elif message_type == "STATE-CHANGE":
            _LOGGER.debug("Processing STATE-CHANGE message for %s", self.serial_number)
            self._handle_state_change(data)
        else:
            _LOGGER.debug(
                "Unknown message type '%s' for device %s: %s",
                message_type,
                self.serial_number,
                data,
            )

        # Notify callbacks
        self._notify_callbacks(topic, data)

    def _handle_current_state(self, data: dict[str, Any], topic: str) -> None:
        """Handle current state message."""
        _LOGGER.debug(
            "Received current state data for %s: %s", self.serial_number, data
        )

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

        # For CURRENT-STATE messages, values are already strings - store directly
        self._state_data.update(data)
        _LOGGER.debug("Updated device state for %s", self.serial_number)

        # Notify callbacks (including coordinator)
        self._notify_callbacks(topic, data)

    def _handle_environmental_data(self, data: dict[str, Any]) -> None:
        """Handle environmental sensor data message."""
        env_data = data.get("data", {})
        _LOGGER.debug(
            "Processing environmental data for %s: received_keys=%s",
            self.serial_number,
            list(env_data.keys()),
        )

        # Log specific PM data if present
        pm25_in_message = env_data.get("pm25")
        pm10_in_message = env_data.get("pm10")
        _LOGGER.debug(
            "Environmental message PM data for %s: pm25='%s', pm10='%s'",
            self.serial_number,
            pm25_in_message,
            pm10_in_message,
        )

        # Log PM2.5, PM10, and level updates specifically
        if "pm25" in env_data:
            _LOGGER.debug(
                "PM2.5 updated for %s: %s", self.serial_number, env_data["pm25"]
            )
        if "pm10" in env_data:
            _LOGGER.debug(
                "PM10 updated for %s: %s", self.serial_number, env_data["pm10"]
            )
        if "p25r" in env_data:
            _LOGGER.debug("P25R value for %s: %s", self.serial_number, env_data["p25r"])
        if "p10r" in env_data:
            _LOGGER.debug("P10R value for %s: %s", self.serial_number, env_data["p10r"])

        # Log gaseous sensor updates (ExtendedAQ capability)
        if "co2" in env_data:
            _LOGGER.debug("CO2 updated for %s: %s", self.serial_number, env_data["co2"])
        if "no2" in env_data:
            _LOGGER.debug("NO2 updated for %s: %s", self.serial_number, env_data["no2"])
        if "hcho" in env_data:
            _LOGGER.debug(
                "HCHO (Formaldehyde) updated for %s: %s",
                self.serial_number,
                env_data["hcho"],
            )

        # Store previous environmental data for comparison
        previous_pm25 = self._environmental_data.get("pm25")
        previous_pm10 = self._environmental_data.get("pm10")

        self._environmental_data.update(env_data)
        _LOGGER.debug(
            "Updated environmental data for %s: keys=%s",
            self.serial_number,
            list(env_data.keys()),
        )
        _LOGGER.debug(
            "Environmental data state before callback for %s: pm25=%s->%s, pm10=%s->%s",
            self.serial_number,
            previous_pm25,
            env_data.get("pm25"),
            previous_pm10,
            env_data.get("pm10"),
        )

        # Only trigger update if PM data actually changed to avoid unnecessary updates
        pm25_changed = previous_pm25 != env_data.get("pm25")
        pm10_changed = previous_pm10 != env_data.get("pm10")

        if pm25_changed or pm10_changed:
            _LOGGER.debug(
                "PM data changed for %s, triggering environmental update",
                self.serial_number,
            )
            # Trigger immediate environmental sensor batch update
            self._trigger_environmental_update()
        else:
            _LOGGER.debug(
                "PM data unchanged for %s, skipping environmental update",
                self.serial_number,
            )

    def _trigger_environmental_update(self) -> None:
        """Trigger immediate update of all environmental sensors."""
        # Notify environmental update callbacks
        for callback in self._environmental_callbacks:
            try:
                callback()
            except Exception as err:
                _LOGGER.error("Error in environmental update callback: %s", err)

    def add_environmental_callback(self, callback: Callable[[], None]) -> None:
        """Add a callback to be notified of environmental data updates."""
        if callback not in self._environmental_callbacks:
            self._environmental_callbacks.append(callback)

    def remove_environmental_callback(self, callback: Callable[[], None]) -> None:
        """Remove an environmental update callback."""
        if callback in self._environmental_callbacks:
            self._environmental_callbacks.remove(callback)

    def add_message_callback(
        self, callback: Callable[[str, dict[str, Any]], None]
    ) -> None:
        """Add a callback to be notified of all message updates."""
        if callback not in self._message_callbacks:
            self._message_callbacks.append(callback)

    def remove_message_callback(
        self, callback: Callable[[str, dict[str, Any]], None]
    ) -> None:
        """Remove a message update callback."""
        if callback in self._message_callbacks:
            self._message_callbacks.remove(callback)

    def _handle_faults_data(self, data: dict[str, Any]) -> None:
        """Handle faults data message and create Home Assistant events for device faults."""
        fault_data = data.get("data", {})

        # Check if there are any faults reported
        if fault_data:
            _LOGGER.warning(
                "Device faults detected for %s: %s", self.serial_number, fault_data
            )

            # Create Home Assistant event for device fault detection
            # Per discovery.md: event should have description "Device Fault Detected"
            self.hass.bus.async_fire(
                "dyson_device_fault_detected",
                {
                    "device_serial": self.serial_number,
                    "description": "Device Fault Detected",
                    "fault_data": fault_data,
                    "timestamp": self._get_timestamp(),
                },
            )

            # Log each individual fault for debugging
            for fault_key, fault_value in fault_data.items():
                _LOGGER.warning(
                    "Fault detected on %s - %s: %s",
                    self.serial_number,
                    fault_key,
                    fault_value,
                )
        else:
            _LOGGER.debug("No faults reported for %s", self.serial_number)

        self._faults_data.update(data)
        _LOGGER.debug("Updated faults data for %s", self.serial_number)

    def _handle_state_change(self, data: dict[str, Any]) -> None:
        """Handle state change message."""
        _LOGGER.debug("Received state change data for %s: %s", self.serial_number, data)

        product_state = data.get("product-state", {})
        if product_state:
            _LOGGER.debug(
                "State change product state contains: %s", list(product_state.keys())
            )
            hflr = product_state.get("hflr")
            cflr = product_state.get("cflr")
            if hflr is not None:
                _LOGGER.debug("HEPA filter life (hflr) in state change: %s", hflr)
            if cflr is not None:
                _LOGGER.debug("Carbon filter life (cflr) in state change: %s", cflr)

        # For STATE-CHANGE messages, normalize [previous, current] arrays to current values
        normalized_product_state = {}
        for key, value in product_state.items():
            if isinstance(value, list) and len(value) >= 2:
                # Take the current value (second element) from [previous, current]
                normalized_product_state[key] = value[1]
                _LOGGER.debug(
                    "Normalized state change %s: %s -> %s", key, value, value[1]
                )
            elif isinstance(value, list) and len(value) == 1:
                # Single element list, take the only value
                normalized_product_state[key] = value[0]
                _LOGGER.debug(
                    "Normalized single-element state change %s: %s -> %s",
                    key,
                    value,
                    value[0],
                )
            else:
                # Already a string or other type, keep as-is
                normalized_product_state[key] = value

        if "product-state" not in self._state_data:
            self._state_data["product-state"] = {}
        self._state_data["product-state"].update(normalized_product_state)
        _LOGGER.debug("State change for %s", self.serial_number)

    def _notify_callbacks(self, topic: str, data: dict[str, Any]) -> None:
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
            command = json.dumps(
                {
                    "msg": "REQUEST-CURRENT-STATE",
                    "time": timestamp,
                    "mode-reason": "RAPP",
                }
            )

            _LOGGER.debug("Publishing to topic: %s", command_topic)
            _LOGGER.debug("Publishing command: %s", command)

            result = await self.hass.async_add_executor_job(
                self._mqtt_client.publish, command_topic, command
            )
            _LOGGER.debug("Publish result: %s", result)
            _LOGGER.debug("Requested current state from %s", self.serial_number)

            # Give device time to respond
            await asyncio.sleep(3.0)

        except Exception as err:
            _LOGGER.error(
                "Failed to request state from %s: %s", self.serial_number, err
            )

    async def _request_current_faults(self) -> None:
        """Request current faults from device."""
        if not self._connected or not self._mqtt_client:
            return

        try:
            command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
            timestamp = self._get_timestamp()
            command = json.dumps(
                {
                    "msg": "REQUEST-CURRENT-FAULTS",
                    "time": timestamp,
                    "mode-reason": "RAPP",
                }
            )

            await self.hass.async_add_executor_job(
                self._mqtt_client.publish, command_topic, command
            )
            _LOGGER.debug("Requested current faults from %s", self.serial_number)

        except Exception as err:
            _LOGGER.error(
                "Failed to request faults from %s: %s", self.serial_number, err
            )

    async def _request_environmental_data(self) -> None:
        """Request current environmental data from device."""
        if not self._connected or not self._mqtt_client:
            return

        try:
            command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
            timestamp = self._get_timestamp()
            command = json.dumps(
                {
                    "msg": MQTT_CMD_REQUEST_ENVIRONMENT,
                    "time": timestamp,
                    "mode-reason": "RAPP",
                }
            )

            await self.hass.async_add_executor_job(
                self._mqtt_client.publish, command_topic, command
            )
            _LOGGER.debug("Requested environmental data from %s", self.serial_number)

        except Exception as err:
            _LOGGER.error(
                "Failed to request environmental data from %s: %s",
                self.serial_number,
                err,
            )

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
                    _LOGGER.warning(
                        "MQTT client disconnected for %s, updating connection state",
                        self.serial_number,
                    )
                    self._connected = False
                return mqtt_connected
        except Exception as err:
            _LOGGER.warning(
                "Failed to check MQTT connection status for %s: %s",
                self.serial_number,
                err,
            )
            self._connected = False
            return False

        return self._connected

    async def send_command(
        self, command: str, data: dict[str, Any] | None = None
    ) -> None:
        """Send a command to the device."""
        if not self._connected or not self._mqtt_client:
            raise RuntimeError(f"Device {self.serial_number} is not connected")

        try:
            _LOGGER.debug(
                "Sending command %s to device %s", command, self.serial_number
            )

            # Handle heartbeat commands (REQUEST-CURRENT-STATE and REQUEST-CURRENT-FAULTS)
            if command == "REQUEST-CURRENT-STATE":
                await self._request_current_state()
                return
            elif command == "REQUEST-CURRENT-FAULTS":
                await self._request_current_faults()
                return
            elif command == MQTT_CMD_REQUEST_ENVIRONMENT:
                await self._request_environmental_data()
                return

            # For other commands, use the generic command format
            command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"

            if data:
                # If data is provided, construct command with data
                command_msg = {
                    "msg": command,
                    "time": self._get_timestamp(),
                    "mode-reason": "RAPP",
                }
                command_msg.update(data)
                command_json = json.dumps(command_msg)
            else:
                # Simple command without additional data
                command_json = json.dumps({"msg": command})

            await self.hass.async_add_executor_job(
                self._mqtt_client.publish, command_topic, command_json
            )
            _LOGGER.debug("Sent command %s to %s", command, self.serial_number)

        except Exception as err:
            _LOGGER.error(
                "Failed to send command %s to device %s: %s",
                command,
                self.serial_number,
                err,
            )
            raise

    async def get_state(self) -> dict[str, Any]:
        """Get current device state."""
        if not self._connected or not self._mqtt_client:
            _LOGGER.debug(
                "Device %s not connected, returning cached state", self.serial_number
            )
            return self._state_data

        try:
            # Get state from paho-mqtt client
            if hasattr(self._mqtt_client, "get_state"):
                # type: ignore[attr-defined]
                state = await self.hass.async_add_executor_job(
                    self._mqtt_client.get_state
                )
                if state:
                    _LOGGER.debug(
                        "Received state data for %s: %s", self.serial_number, state
                    )
                    self._state_data.update(state)
                else:
                    _LOGGER.debug(
                        "No state data returned from get_state for %s",
                        self.serial_number,
                    )
            elif hasattr(self._mqtt_client, "state"):
                # Some MQTT clients might have a state property
                state = getattr(self._mqtt_client, "state", {})
                if state:
                    _LOGGER.debug(
                        "Received state from property for %s: %s",
                        self.serial_number,
                        state,
                    )
                    self._state_data.update(state)
                else:
                    _LOGGER.debug(
                        "No state data in property for %s", self.serial_number
                    )

        except Exception as err:
            _LOGGER.warning(
                "Failed to get state from device %s: %s", self.serial_number, err
            )

        _LOGGER.debug(
            "Final state data for %s: %s", self.serial_number, self._state_data
        )
        return self._state_data

    def _normalize_faults_to_list(self, faults: Any) -> list[dict[str, Any]]:
        """Normalize faults data to list format, filtering out OK statuses."""
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
        # Use static translation from const.py
        fault_translations = FAULT_TRANSLATIONS.get(fault_key, {})

        # Try to get specific translation for this value
        if fault_value in fault_translations:
            return fault_translations[fault_value]

        # Final fallback to generic description
        return f"{fault_key.upper()} fault: {fault_value}"

    async def _get_faults_from_client(self) -> list[dict[str, Any]]:
        """Get faults from MQTT client."""
        if not self._mqtt_client:
            return []

        # Try get_faults method
        if hasattr(self._mqtt_client, "get_faults"):
            faults = await self.hass.async_add_executor_job(
                self._mqtt_client.get_faults
            )  # type: ignore[attr-defined]
            if faults:
                return self._normalize_faults_to_list(faults)

        # Try faults property
        elif hasattr(self._mqtt_client, "faults"):
            faults = getattr(self._mqtt_client, "faults", {})
            if faults:
                return self._normalize_faults_to_list(faults)

        return []

    async def get_faults(self) -> list[dict[str, Any]]:
        """Get device faults."""
        if not self._connected or not self._mqtt_client:
            return self._normalize_faults_to_list(self._faults_data)

        try:
            faults = await self._get_faults_from_client()
            if faults:
                return faults
        except Exception as err:
            _LOGGER.warning(
                "Failed to get faults from device %s: %s", self.serial_number, err
            )

        return self._normalize_faults_to_list(self._faults_data)

    def set_firmware_version(self, firmware_version: str) -> None:
        """Set the firmware version for this device."""
        if firmware_version and firmware_version != "Unknown":
            self._firmware_version = firmware_version
            _LOGGER.debug(
                "Set firmware version for %s: %s", self.serial_number, firmware_version
            )

    @property
    def device_info(self) -> dict[str, Any]:
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
        product_state = self._state_data.get("product-state", {})
        nmod = self._get_current_value(product_state, "nmod", "OFF")
        return nmod == "ON"

    @property
    def auto_mode(self) -> bool:
        """Return if auto mode is enabled (wacd)."""
        product_state = self._state_data.get("product-state", {})
        wacd = self._get_current_value(product_state, "wacd", "NONE")
        return wacd != "NONE"

    @property
    def fan_speed(self) -> int:
        """Return fan speed (nmdv)."""
        try:
            product_state = self._state_data.get("product-state", {})
            nmdv = self._get_current_value(product_state, "nmdv", "0000")
            return int(nmdv)
        except (ValueError, TypeError):
            return 0

    @property
    def fan_power(self) -> bool:
        """Return if fan power is on (fpwr)."""
        product_state = self._state_data.get("product-state", {})
        fpwr = self._get_current_value(product_state, "fpwr", "OFF")
        return fpwr == "ON"

    @property
    def fan_speed_setting(self) -> str:
        """Return fan speed setting (fnsp) - controllable setting."""
        product_state = self._state_data.get("product-state", {})
        fnsp = self._get_current_value(product_state, "fnsp", "0001")
        return fnsp

    @property
    def fan_state(self) -> str:
        """Return fan state (fnst) - OFF/FAN."""
        product_state = self._state_data.get("product-state", {})
        fnst = self._get_current_value(product_state, "fnst", "OFF")
        return fnst

    @property
    def brightness(self) -> int:
        """Return display brightness (bril)."""
        try:
            product_state = self._state_data.get("product-state", {})
            bril = self._get_current_value(product_state, "bril", "0002")
            return int(bril)
        except (ValueError, TypeError):
            return 2

    # Environmental sensor properties (from our MQTT test)
    @property
    def pm25(self) -> int | None:
        """Return PM2.5 reading."""
        try:
            # Take a snapshot of environmental data to avoid race conditions
            env_data_snapshot = dict(self._environmental_data)
            pm25_raw = env_data_snapshot.get("pm25")
            if pm25_raw is None:
                _LOGGER.debug(
                    "PM2.5 property for %s: no data available", self.serial_number
                )
                return None

            value = int(pm25_raw)
            import datetime

            _LOGGER.debug(
                "PM2.5 property accessed for %s at %s: raw='%s', value=%d",
                self.serial_number,
                datetime.datetime.now().isoformat(),
                pm25_raw,
                value,
            )
            return value
        except (ValueError, TypeError) as e:
            _LOGGER.warning(
                "Invalid PM2.5 value for %s: %s, error: %s",
                self.serial_number,
                self._environmental_data.get("pm25"),
                e,
            )
            return None

    @property
    def pm10(self) -> int | None:
        """Return PM10 reading."""
        try:
            # Take a snapshot of environmental data to avoid race conditions
            env_data_snapshot = dict(self._environmental_data)
            pm10_raw = env_data_snapshot.get("pm10")
            if pm10_raw is None:
                _LOGGER.debug(
                    "PM10 property for %s: no data available", self.serial_number
                )
                return None

            value = int(pm10_raw)
            import datetime

            _LOGGER.debug(
                "PM10 property accessed for %s at %s: raw='%s', value=%d",
                self.serial_number,
                datetime.datetime.now().isoformat(),
                pm10_raw,
                value,
            )
            return value
        except (ValueError, TypeError) as e:
            _LOGGER.warning(
                "Invalid PM10 value for %s: %s, error: %s",
                self.serial_number,
                self._environmental_data.get("pm10"),
                e,
            )
            return None

    @property
    def voc(self) -> float | None:
        """Return VOC (Volatile Organic Compounds) reading in ppb."""
        try:
            # Take a snapshot of environmental data to avoid race conditions
            env_data_snapshot = dict(self._environmental_data)
            voc_raw = env_data_snapshot.get("va10")
            if voc_raw is None:
                _LOGGER.debug(
                    "VOC property for %s: no data available", self.serial_number
                )
                return None

            # Convert from index to ppb (divide by 10 as per libdyson-neon)
            value = float(voc_raw) / 10.0
            import datetime

            _LOGGER.debug(
                "VOC property accessed for %s at %s: raw='%s', value=%.1f ppb",
                self.serial_number,
                datetime.datetime.now().isoformat(),
                voc_raw,
                value,
            )
            return value
        except (ValueError, TypeError) as e:
            _LOGGER.warning(
                "Invalid VOC value for %s: %s, error: %s",
                self.serial_number,
                self._environmental_data.get("va10"),
                e,
            )
            return None

    @property
    def no2(self) -> float | None:
        """Return NO2 (Nitrogen Dioxide) reading in ppb."""
        try:
            # Take a snapshot of environmental data to avoid race conditions
            env_data_snapshot = dict(self._environmental_data)
            no2_raw = env_data_snapshot.get("noxl")
            if no2_raw is None:
                _LOGGER.debug(
                    "NO2 property for %s: no data available", self.serial_number
                )
                return None

            # Convert from index to ppb (divide by 10 as per libdyson-neon)
            value = float(no2_raw) / 10.0
            import datetime

            _LOGGER.debug(
                "NO2 property accessed for %s at %s: raw='%s', value=%.1f ppb",
                self.serial_number,
                datetime.datetime.now().isoformat(),
                no2_raw,
                value,
            )
            return value
        except (ValueError, TypeError) as e:
            _LOGGER.warning(
                "Invalid NO2 value for %s: %s, error: %s",
                self.serial_number,
                self._environmental_data.get("noxl"),
                e,
            )
            return None

    @property
    def formaldehyde(self) -> float | None:
        """Return formaldehyde reading in ppb."""
        try:
            # Take a snapshot of environmental data to avoid race conditions
            env_data_snapshot = dict(self._environmental_data)
            formaldehyde_raw = env_data_snapshot.get("hchr")
            if formaldehyde_raw is None:
                _LOGGER.debug(
                    "Formaldehyde property for %s: no data available",
                    self.serial_number,
                )
                return None

            # Convert from index to ppb (divide by 1000 as per libdyson-neon)
            value = float(formaldehyde_raw) / 1000.0
            import datetime

            _LOGGER.debug(
                "Formaldehyde property accessed for %s at %s: raw='%s', value=%.3f ppb",
                self.serial_number,
                datetime.datetime.now().isoformat(),
                formaldehyde_raw,
                value,
            )
            return value
        except (ValueError, TypeError) as e:
            _LOGGER.warning(
                "Invalid formaldehyde value for %s: %s, error: %s",
                self.serial_number,
                self._environmental_data.get("hchr"),
                e,
            )
            return None

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
            _LOGGER.warning(
                "Failed to parse HEPA filter life for %s: %s", self.serial_number, e
            )
            return 0

    @property
    def carbon_filter_life(self) -> int:
        """Return carbon filter life percentage."""
        try:
            product_state = self._state_data.get("product-state", {})
            cflr = self._get_current_value(product_state, "cflr", "0000")
            if cflr == "INV":  # Invalid/no filter installed
                return 0
            return int(cflr)
        except (ValueError, TypeError):
            return 0

    @property
    def hepa_filter_type(self) -> str:
        """Return HEPA filter type."""
        product_state = self._state_data.get("product-state", {})
        filter_type = self._get_current_value(product_state, "hflt", "NONE")
        _LOGGER.debug("HEPA filter type for %s: %s", self.serial_number, filter_type)
        return filter_type

    @property
    def carbon_filter_type(self) -> str:
        """Return carbon filter type."""
        product_state = self._state_data.get("product-state", {})
        filter_type = self._get_current_value(product_state, "cflt", "NONE")
        _LOGGER.debug("Carbon filter type for %s: %s", self.serial_number, filter_type)
        return filter_type

    def _get_command_timestamp(self) -> str:
        """Get formatted timestamp for MQTT commands."""
        from datetime import datetime

        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    def _get_current_value(
        self, data: dict[str, Any], key: str, default: str = "OFF"
    ) -> str:
        """Get current value from device data.

        Values are normalized at message processing time:
        - CURRENT-STATE messages: already strings
        - STATE-CHANGE messages: [previous, current] arrays converted to current string
        - ENVIRONMENTAL-CURRENT-SENSOR-DATA messages: already strings
        - Fault messages: already strings
        """
        value = data.get(key, default)
        return str(value)

    # Command methods for device control
    async def set_night_mode(self, enabled: bool) -> None:
        """Set night mode on/off."""
        _LOGGER.debug(
            "=== DEBUG set_night_mode called for %s: enabled=%s ===",
            self.serial_number,
            enabled,
        )
        _LOGGER.debug(
            "Device connection state: _mqtt_client=%s, _connected=%s",
            self._mqtt_client is not None,
            self._connected,
        )

        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
        nmod_value = "ON" if enabled else "OFF"

        # Include required headers: time and mode-reason
        command = json.dumps(
            {
                "msg": "STATE-SET",
                "time": self._get_command_timestamp(),
                "data": {"nmod": nmod_value},
                "mode-reason": "RAPP",
            }
        )

        _LOGGER.debug(
            "=== Sending night mode command to topic %s: %s ===", command_topic, command
        )

        if self._mqtt_client:
            try:
                _LOGGER.debug("=== About to publish MQTT command ===")
                await self.hass.async_add_executor_job(
                    self._mqtt_client.publish, command_topic, command
                )
                _LOGGER.debug(
                    "=== Successfully sent night mode command to %s ===",
                    self.serial_number,
                )
            except Exception as err:
                _LOGGER.error(
                    "=== Failed to publish night mode command to %s: %s ===",
                    self.serial_number,
                    err,
                )
        else:
            _LOGGER.warning(
                "=== No MQTT client available for device %s ===", self.serial_number
            )

    async def set_fan_speed(self, speed: int) -> None:
        """Set fan speed (1-10) using fnsp."""
        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
        if speed == 0:
            # Speed 0 means turn off the fan
            await self.set_fan_power(False)
            return

        # Ensure speed is in valid range and format as 4-digit string
        speed = max(1, min(10, speed))
        speed_str = f"{speed:04d}"

        # Include required headers: time and mode-reason
        command = json.dumps(
            {
                "msg": "STATE-SET",
                "time": self._get_command_timestamp(),
                "data": {"fnsp": speed_str},
                "mode-reason": "RAPP",
            }
        )

        if self._mqtt_client:
            await self.hass.async_add_executor_job(
                self._mqtt_client.publish, command_topic, command
            )

    async def set_fan_power(self, enabled: bool) -> None:
        """Set fan power on/off using fpwr."""
        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
        fpwr_value = "ON" if enabled else "OFF"

        # Include required headers: time and mode-reason
        command = json.dumps(
            {
                "msg": "STATE-SET",
                "time": self._get_command_timestamp(),
                "data": {"fpwr": fpwr_value},
                "mode-reason": "RAPP",
            }
        )

        if self._mqtt_client:
            await self.hass.async_add_executor_job(
                self._mqtt_client.publish, command_topic, command
            )

    async def reset_hepa_filter_life(self) -> None:
        """Reset HEPA filter life to 100%."""
        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
        command = json.dumps(
            {
                "msg": "STATE-SET",
                "time": self._get_command_timestamp(),
                "data": {"hflr": "0100"},
                "mode-reason": "RAPP",
            }
        )

        if self._mqtt_client:
            await self.hass.async_add_executor_job(
                self._mqtt_client.publish, command_topic, command
            )

    async def reset_carbon_filter_life(self) -> None:
        """Reset carbon filter life to 100%."""
        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
        command = json.dumps(
            {
                "msg": "STATE-SET",
                "time": self._get_command_timestamp(),
                "data": {"cflr": "0100"},
                "mode-reason": "RAPP",
            }
        )

        if self._mqtt_client:
            await self.hass.async_add_executor_job(
                self._mqtt_client.publish, command_topic, command
            )

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

        # Include required headers: time and mode-reason
        command = json.dumps(
            {
                "msg": "STATE-SET",
                "time": self._get_command_timestamp(),
                "data": {"sltm": timer_value},
                "mode-reason": "RAPP",
            }
        )

        if self._mqtt_client:
            await self.hass.async_add_executor_job(
                self._mqtt_client.publish, command_topic, command
            )

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

        # Include required headers: time and mode-reason
        command = json.dumps(
            {
                "msg": "STATE-SET",
                "time": self._get_command_timestamp(),
                "data": {
                    "osal": lower_str,  # Oscillation angle lower
                    "osau": upper_str,  # Oscillation angle upper
                    "oson": "ON",  # Enable oscillation
                    "ancp": "CUST",  # Custom angles
                },
                "mode-reason": "RAPP",
            }
        )

        if self._mqtt_client:
            await self.hass.async_add_executor_job(
                self._mqtt_client.publish, command_topic, command
            )

    async def set_auto_mode(self, enabled: bool) -> None:
        """Set auto mode on/off."""
        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
        auto_value = "ON" if enabled else "OFF"

        # Include required headers: time and mode-reason
        command = json.dumps(
            {
                "msg": "STATE-SET",
                "time": self._get_command_timestamp(),
                "data": {"auto": auto_value},
                "mode-reason": "RAPP",
            }
        )

        if self._mqtt_client:
            await self.hass.async_add_executor_job(
                self._mqtt_client.publish, command_topic, command
            )

    async def set_oscillation(self, enabled: bool, angle: int | None = None) -> None:
        """Set oscillation on/off with optional angle."""
        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"

        data = {"oson": "ON" if enabled else "OFF"}

        if enabled and angle is not None:
            # Set specific oscillation angle
            angle_str = f"{angle:04d}"
            data["ancp"] = angle_str

        # Include required headers: time and mode-reason
        command = json.dumps(
            {
                "msg": "STATE-SET",
                "time": self._get_command_timestamp(),
                "data": data,
                "mode-reason": "RAPP",
            }
        )

        if self._mqtt_client:
            await self.hass.async_add_executor_job(
                self._mqtt_client.publish, command_topic, command
            )

    async def set_heating_mode(self, mode: str) -> None:
        """Set heating mode (OFF, HEAT, AUTO)."""
        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
        command = json.dumps(
            {
                "msg": "STATE-SET",
                "time": self._get_command_timestamp(),
                "data": {"hmod": mode},
                "mode-reason": "RAPP",
            }
        )

        if self._mqtt_client:
            await self.hass.async_add_executor_job(
                self._mqtt_client.publish, command_topic, command
            )

    async def set_target_temperature(self, temperature: float) -> None:
        """Set target temperature in Celsius.

        Args:
            temperature: Target temperature in Celsius (1-37°C)
        """
        # Validate temperature range (convert to Kelvin for validation)
        temp_kelvin = temperature + 273.15
        if not 274 <= temp_kelvin <= 310:
            raise ValueError("Target temperature must be between 1°C and 37°C")

        # Convert Celsius to Kelvin × 10 format for device
        temp_value = int(temp_kelvin * 10)
        temp_str = f"{temp_value:04d}"

        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
        command = json.dumps(
            {
                "msg": "STATE-SET",
                "time": self._get_command_timestamp(),
                "data": {
                    "hmod": "HEAT",  # Enable heating mode when setting temperature
                    "hmax": temp_str,
                },
                "mode-reason": "RAPP",
            }
        )

        if self._mqtt_client:
            await self.hass.async_add_executor_job(
                self._mqtt_client.publish, command_topic, command
            )

    async def set_continuous_monitoring(self, enabled: bool) -> None:
        """Set continuous monitoring on/off."""
        command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
        command = json.dumps(
            {
                "msg": "STATE-SET",
                "time": self._get_command_timestamp(),
                "data": {"rhtm": "ON" if enabled else "OFF"},
                "mode-reason": "RAPP",
            }
        )

        if self._mqtt_client:
            await self.hass.async_add_executor_job(
                self._mqtt_client.publish, command_topic, command
            )
