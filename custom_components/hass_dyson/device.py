"""Dyson device wrapper providing direct MQTT communication and control.

This module implements the core DysonDevice class that handles all communication
with Dyson devices using the paho-mqtt library. It provides a comprehensive API
for device connection management, state monitoring, environmental data collection,
and device control operations.

Key Features:
    - Direct MQTT communication with local and cloud connections
    - Real-time environmental data streaming (PM2.5, PM10, VOC, temperature, etc.)
    - Complete device control API (fan speed, oscillation, heating, etc.)
    - Automatic connection failover (local → cloud → reconnection)
    - Heartbeat monitoring and automatic reconnection
    - Filter life tracking and maintenance operations
    - Advanced oscillation with custom angle control
    - Sleep timer and scheduling functionality

Connection Types:
    - local_only: Direct local network connection only
    - cloud_only: Dyson cloud service connection only
    - local_cloud_fallback: Local preferred with cloud fallback (default)

Supported Device Categories:
    - Pure series (air purifiers): PM monitoring, filter management
    - Hot+Cool series (heater/fan): Temperature control, heating modes
    - Humidify series: Humidity control and water tank monitoring
    - Lightcycle series: Lighting control and circadian rhythm
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
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
    """Primary interface for Dyson device communication and control.

    This class provides comprehensive access to Dyson device functionality through
    direct MQTT communication. It handles connection management, real-time data
    streaming, device control, and environmental monitoring.

    The device wrapper automatically manages:
    - MQTT connection establishment and maintenance
    - Heartbeat monitoring for connection health
    - Environmental data collection and caching
    - Command execution with proper formatting
    - Connection failover between local and cloud endpoints
    - Filter life tracking and maintenance scheduling

    Attributes:
        serial_number: Unique device identifier
        host: Local network address for direct connection
        credential: Authentication credential for MQTT
        capabilities: List of device capability strings
        connection_type: Connection strategy (local_only, cloud_only, local_cloud_fallback)
        is_connected: Current connection status
        connection_status: Detailed connection state (LOCAL/CLOUD/DISCONNECTED)

    Environmental Properties:
        pm25: PM2.5 particulate matter (μg/m³)
        pm10: PM10 particulate matter (μg/m³)
        voc: Volatile organic compounds index
        nox: Nitrogen dioxide index
        temperature: Current temperature (°C)
        humidity: Relative humidity (%)

    Device State Properties:
        fan_power: Fan power state (on/off)
        fan_speed: Current fan speed (1-10)
        night_mode: Night mode status
        auto_mode: Automatic speed adjustment status
        oscillation_enabled: Oscillation state
        heating_mode: Heating mode (OFF/HEAT/AUTO)
        target_temperature: Target temperature for heating

    Filter Properties:
        hepa_filter_life: HEPA filter remaining life (0-100%)
        carbon_filter_life: Carbon filter remaining life (0-100%)

    Example:
        Basic device setup and control:

        >>> device = DysonDevice(
        >>>     hass=hass,
        >>>     serial_number="VS6-EU-HJA1234A",
        >>>     host="192.168.1.100",
        >>>     credential="device_credential",
        >>>     capabilities=["WiFi", "ExtendedAQ", "Heat"]
        >>> )
        >>>
        >>> # Connect and get initial state
        >>> await device.connect()
        >>> state = await device.get_state()
        >>>
        >>> # Control fan speed and oscillation
        >>> await device.set_fan_speed(7)
        >>> await device.set_oscillation(True)
        >>>
        >>> # Monitor environmental data
        >>> pm25_level = device.pm25
        >>> temperature = device.temperature
        >>>
        >>> # Set up heating (if supported)
        >>> if "Heat" in device.capabilities:
        >>>     await device.set_target_temperature(22.0)
        >>>     await device.set_heating_mode("HEAT")

    Note:
        The device automatically handles connection management including
        heartbeat monitoring, reconnection attempts, and failover between
        local and cloud connections based on the configured connection_type.

        Environmental data is streamed in real-time via MQTT callbacks,
        providing immediate updates when air quality changes.

        All control methods are asynchronous and may raise RuntimeError
        if the device is not connected when commands are sent.
    """

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
        self._had_stable_connection = False  # Track if we've had a stable connection
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
        self._intentional_disconnect = False  # Track intentional disconnections

        # Heartbeat mechanism to keep device active and get regular updates
        self._heartbeat_interval = 30.0  # Send REQUEST-CURRENT-STATE every 30 seconds
        self._heartbeat_task: asyncio.Task | None = None
        self._last_heartbeat = 0.0
        self._state_data: dict[str, Any] = {}
        self._environmental_data: dict[str, Any] = {}
        self._faults_data: dict[str, Any] = {}  # Raw fault data from device
        self._message_callbacks: list[Callable[[str, dict[str, Any]], None]] = []

        # Power control capability detection
        self._fpwr_message_count = 0  # Track messages containing fpwr
        self._fmod_message_count = 0  # Track messages containing fmod
        self._total_state_messages = 0  # Total STATE-CHANGE messages received
        self._power_control_type: str | None = (
            None  # "fpwr" or "fmod" or None (detecting)
        )
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

    async def connect(self, force: bool = False) -> bool:
        """Establish MQTT connection to the Dyson device.

        Attempts to connect using the configured connection strategy:
        - local_only: Direct local network connection only
        - cloud_only: Dyson cloud service connection only
        - local_cloud_fallback: Local first, cloud fallback if local fails

        The connection process includes:
        1. MQTT client initialization with proper credentials
        2. SSL/TLS setup for secure communication
        3. Topic subscription for device state and environmental data
        4. Heartbeat task initialization for connection monitoring
        5. Initial state and environmental data requests

        Args:
            force: If True, bypass reconnection backoff and attempt connection immediately

        Returns:
            True if connection successful, False if all connection attempts failed

        Raises:
            Exception: If MQTT client setup fails or connection parameters invalid

        Example:
            Connect with automatic failover:

            >>> device = DysonDevice(
            >>>     hass=hass,
            >>>     serial_number="VS6-EU-HJA1234A",
            >>>     host="192.168.1.100",
            >>>     credential="local_credential",
            >>>     connection_type="local_cloud_fallback",
            >>>     cloud_host="cloud.dyson.com",
            >>>     cloud_credential="cloud_credential"
            >>> )
            >>>
            >>> success = await device.connect()
            >>> if success:
            >>>     print(f"Connected: {device.connection_status}")
            >>>     # Device ready for commands and data collection
            >>> else:
            >>>     print("Failed to connect to device")

        Note:
            Connection is performed asynchronously and includes automatic
            retry logic. The heartbeat task is started upon successful
            connection to monitor connection health and trigger reconnection
            if the connection is lost.
        """
        # Check reconnection backoff to prevent rapid reconnection attempts
        if not self._check_reconnect_backoff(force):
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

    def _check_reconnect_backoff(self, force: bool = False) -> bool:
        """Check if reconnection backoff period has passed."""
        current_time = time.time()

        # Allow immediate connection attempts if force is True
        if force:
            _LOGGER.debug(
                "Bypassing reconnection backoff for %s due to forced connection attempt",
                self.serial_number,
            )
            return True

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

    async def _test_network_connectivity(self, host: str, port: int = 1883) -> bool:
        """Test basic network connectivity to device."""
        try:
            # Attempt to establish a basic socket connection
            _LOGGER.debug("Testing network connectivity to %s:%s", host, port)

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # 5 second timeout

            try:
                await self.hass.async_add_executor_job(sock.connect, (host, port))
                _LOGGER.debug(
                    "Network connectivity test successful for %s:%s", host, port
                )
                return True
            finally:
                sock.close()

        except socket.gaierror as err:
            _LOGGER.warning(
                "DNS resolution failed for %s: %s. "
                "Device hostname is not resolvable on local network.",
                host,
                err,
            )
            return False
        except (TimeoutError, ConnectionError, OSError) as err:
            _LOGGER.warning(
                "Network connectivity test failed for %s:%s: %s. "
                "Device may be unreachable or port blocked.",
                host,
                port,
                err,
            )
            return False
        except Exception as err:
            _LOGGER.warning(
                "Unexpected error during network test for %s:%s: %s", host, port, err
            )
            return False

    async def _attempt_local_connection(self, host: str, credential: str) -> bool:
        """Attempt local MQTT connection."""
        try:
            # First test basic network connectivity
            if not await self._test_network_connectivity(host, 1883):
                _LOGGER.info(
                    "Skipping MQTT connection attempt to %s due to network connectivity failure. "
                    "Consider switching to cloud-only connection or checking network configuration.",
                    host,
                )
                return False

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

            # Disable automatic reconnection - we handle reconnection ourselves
            mqtt_client.enable_logger(
                logger=None
            )  # Disable MQTT client logging to reduce noise
            # Note: paho-mqtt doesn't have a direct disable auto-reconnect method,
            # so we rely on our own connection management

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
                connection_success = await self._wait_for_connection("local")

                if not connection_success:
                    # Clean up failed connection attempt
                    try:
                        await self.hass.async_add_executor_job(mqtt_client.loop_stop)
                        await self.hass.async_add_executor_job(mqtt_client.disconnect)
                        _LOGGER.debug(
                            "Cleaned up failed local connection attempt for %s",
                            self.serial_number,
                        )
                    except Exception as cleanup_err:
                        _LOGGER.debug(
                            "Failed to clean up connection for %s: %s",
                            self.serial_number,
                            cleanup_err,
                        )

                return connection_success
            else:
                _LOGGER.warning(
                    "Local MQTT connection to %s failed with result: %s. "
                    "Common causes: device not reachable, mDNS resolution failure, "
                    "network firewall blocking port 1883, or device on different VLAN. "
                    "Consider using cloud-only connection type if local network issues persist.",
                    host,
                    result,
                )
                return False

        except socket.gaierror as err:
            _LOGGER.warning(
                "DNS resolution failed for %s: %s. "
                "Device may not be discoverable on local network. "
                "Try using the device's IP address instead of hostname, "
                "or switch to cloud-only connection.",
                host,
                err,
            )
            return False
        except ConnectionError as err:
            _LOGGER.warning(
                "Network connection failed to %s: %s. "
                "Check if device is on same network segment and port 1883 is accessible.",
                host,
                err,
            )
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

            # Disable automatic reconnection - we handle reconnection ourselves
            mqtt_client.enable_logger(
                logger=None
            )  # Disable MQTT client logging to reduce noise

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
                connection_success = await self._wait_for_connection("cloud")

                if not connection_success:
                    # Clean up failed connection attempt
                    try:
                        await self.hass.async_add_executor_job(mqtt_client.loop_stop)
                        await self.hass.async_add_executor_job(mqtt_client.disconnect)
                        _LOGGER.debug(
                            "Cleaned up failed cloud connection attempt for %s",
                            self.serial_number,
                        )
                    except Exception as cleanup_err:
                        _LOGGER.debug(
                            "Failed to clean up connection for %s: %s",
                            self.serial_number,
                            cleanup_err,
                        )

                return connection_success
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
        connection_timeout = 5  # Reduced to 5 seconds timeout for faster failover
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
            "Connection timeout for device %s via %s after %.1f seconds",
            self.serial_number,
            conn_type,
            elapsed_time,
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

        # Mark this as an intentional disconnect
        self._intentional_disconnect = True

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
            self._had_stable_connection = (
                True  # Mark that we've had a successful connection
            )

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
        # Use appropriate log level based on whether disconnect was intentional
        if self._intentional_disconnect:
            _LOGGER.debug(
                "MQTT client disconnected for %s (intentional), code: %s",
                self.serial_number,
                rc,
            )
            # Reset the flag after logging
            self._intentional_disconnect = False
        else:
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
        # Only apply the 15-minute fallback timer if we had a stable connection (not during initial connection attempts)
        if (
            rc != mqtt.MQTT_ERR_SUCCESS
            and hasattr(self, "_had_stable_connection")
            and self._had_stable_connection
        ):
            _LOGGER.info(
                "Unexpected disconnection for %s, will stay on fallback connection for 15 minutes unless manually reconnected",
                self.serial_number,
            )
            # Set preferred retry timer to 15 minutes from now to prevent automatic retry of preferred connection
            # Manual reconnection (force_reconnect) will reset this to allow immediate preferred connection attempts
            self._last_preferred_retry = time.time() + 900  # 15 minutes = 900 seconds
        elif rc != mqtt.MQTT_ERR_SUCCESS:
            _LOGGER.debug(
                "Disconnection during connection attempt for %s, not applying fallback timer",
                self.serial_number,
            )

    def _on_message(
        self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        """Handle MQTT message callback."""
        try:
            topic = message.topic
            payload: str | bytes = message.payload

            _LOGGER.debug("Received MQTT message on %s: %s", topic, payload[:100])
            _LOGGER.debug(
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
            _LOGGER.debug("MQTT PARSED DATA for %s: %s", self.serial_number, data)

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

            # Track power control capability patterns for device type detection
            self._total_state_messages += 1
            product_state = data.get("product-state", {})
            if "fpwr" in product_state:
                self._fpwr_message_count += 1
            if "fmod" in product_state:
                self._fmod_message_count += 1

            # Update power control type detection if we have enough data
            # Note: Only runs when coordinator immediate detection failed to set _power_control_type
            if self._power_control_type is None and self._total_state_messages >= 1:
                detected_type = self._detect_power_control_type()
                if detected_type != "unknown":
                    self._power_control_type = detected_type
                    _LOGGER.info(
                        "Device %s fallback detection: %s-based power control (fpwr_msgs: %d, fmod_msgs: %d, total: %d)",
                        self.serial_number,
                        detected_type,
                        self._fpwr_message_count,
                        self._fmod_message_count,
                        self._total_state_messages,
                    )
                    _LOGGER.debug(
                        "Fallback detection completed for %s after %d STATE-CHANGE message(s)",
                        self.serial_number,
                        self._total_state_messages,
                    )

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
        """Send a command to the Dyson device via MQTT.

        Executes device commands using Dyson's MQTT protocol. Commands are
        formatted with proper timestamps and published to device-specific topics.

        Args:
            command: Command type to execute. Common commands:
                - "STATE-SET": Set device state parameters
                - "REQUEST-CURRENT-STATE": Request full device state
                - "REQUEST-CURRENT-FAULTS": Request device fault status
                - "REQUEST-PRODUCT-ENVIRONMENT-CURRENT-SENSOR-DATA": Environmental data
            data: Command parameters as key-value pairs. Common parameters:
                - "fnsp": Fan speed ("0001" to "0010")
                - "fpwr": Fan power ("ON"/"OFF")
                - "oson": Oscillation ("ON"/"OFF")
                - "nmod": Night mode ("ON"/"OFF")
                - "auto": Auto mode ("ON"/"OFF")
                - "hmod": Heating mode ("OFF"/"HEAT"/"AUTO")
                - "hmax": Target temperature ("2731" + temp in Kelvin)

        Raises:
            RuntimeError: If device is not connected or MQTT client unavailable
            Exception: If command publishing fails or data formatting invalid

        Example:
            Execute common device commands:

            >>> # Set fan to speed 5 with oscillation
            >>> await device.send_command("STATE-SET", {
            >>>     "fnsp": "0005",
            >>>     "fpwr": "ON",
            >>>     "oson": "ON"
            >>> })
            >>>
            >>> # Enable night mode with auto speed
            >>> await device.send_command("STATE-SET", {
            >>>     "nmod": "ON",
            >>>     "auto": "ON"
            >>> })
            >>>
            >>> # Set heating to 22°C
            >>> await device.send_command("STATE-SET", {
            >>>     "hmod": "HEAT",
            >>>     "hmax": "2953"  # 22°C = 295.15K = 2951.5 ≈ 2953
            >>> })
            >>>
            >>> # Request current state
            >>> await device.send_command("REQUEST-CURRENT-STATE")

        Note:
            Commands are executed asynchronously and may take 1-3 seconds
            for the device to process and reflect in state updates.

            Temperature values are sent in Kelvin * 10 format. For example,
            22°C = 295.15K = 2951.5 ≈ 2953.

            The device will respond with updated state via MQTT callbacks,
            triggering coordinator updates in Home Assistant.
        """
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
                command_msg: dict[str, Any] = {
                    "msg": command,
                    "time": self._get_timestamp(),
                    "mode-reason": "RAPP",
                }

                # STATE-SET commands need data wrapped in a "data" field
                if command == "STATE-SET":
                    command_msg["data"] = data
                else:
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

    async def request_current_faults(self) -> None:
        """Request current faults from the device.

        Sends REQUEST-CURRENT-FAULTS command to get immediate fault status update.
        Device will respond with current fault information on status/fault topic.

        Raises:
            RuntimeError: If device is not connected
            Exception: If command transmission fails
        """
        if not self.is_connected:
            raise RuntimeError(f"Device {self.serial_number} is not connected")

        _LOGGER.debug("Requesting current faults from %s", self.serial_number)

        await self._request_current_faults()

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
        nmod = self.get_state_value(product_state, "nmod", "OFF")
        return nmod == "ON"

    @property
    def auto_mode(self) -> bool:
        """Return if auto mode is enabled.

        Checks multiple keys depending on device type:
        - fmod: "AUTO" for TP02 and similar devices (fan auto mode)
        - wacd: !="NONE" for humidifier devices (water hardness auto-adjust)
        """
        product_state = self._state_data.get("product-state", {})

        # Check fmod for fan auto mode (TP02, HP02, etc.)
        fmod = self.get_state_value(product_state, "fmod", "MISSING")
        if fmod == "AUTO":
            return True

        # Check wacd for humidifier auto mode
        wacd = self.get_state_value(product_state, "wacd", "NONE")
        if wacd != "NONE":
            return True

        # Default: not in auto mode
        return False

    @property
    def fan_speed(self) -> int:
        """Return fan speed (nmdv)."""
        try:
            product_state = self._state_data.get("product-state", {})
            nmdv = self.get_state_value(product_state, "nmdv", "0000")
            return int(nmdv)
        except (ValueError, TypeError):
            return 0

    @property
    def fan_power(self) -> bool:
        """Return if fan power is on, handling both fpwr and fmod-based devices."""
        product_state = self._state_data.get("product-state", {})

        # Determine power control type if not yet detected
        power_control_type = (
            self._power_control_type or self._detect_power_control_type()
        )

        if power_control_type == "fmod":
            # HP02 and similar devices: power state based on fmod
            fmod = self.get_state_value(product_state, "fmod", "OFF")
            _LOGGER.debug(
                "Device %s fan_power using fmod (HP02-style): %s",
                self.serial_number,
                fmod,
            )
            return fmod in ["FAN", "AUTO"]
        else:
            # Most devices: try fpwr first, fallback to fnst
            fpwr = self.get_state_value(product_state, "fpwr", "MISSING")

            if fpwr != "MISSING":
                _LOGGER.debug(
                    "Device %s fan_power using fpwr: %s", self.serial_number, fpwr
                )
                return fpwr == "ON"

            # Fallback to fnst (fan state) when fpwr is not available
            # This handles cases where STATE-CHANGE messages don't include fpwr
            fnst = self.get_state_value(product_state, "fnst", "OFF")
            _LOGGER.debug(
                "Device %s fan_power using fnst fallback: %s", self.serial_number, fnst
            )
            return fnst == "FAN"

    @property
    def fan_speed_setting(self) -> str:
        """Return fan speed setting (fnsp) - controllable setting."""
        product_state = self._state_data.get("product-state", {})
        fnsp = self.get_state_value(product_state, "fnsp", "0001")
        return fnsp

    @property
    def fan_state(self) -> str:
        """Return fan state (fnst) - OFF/FAN."""
        product_state = self._state_data.get("product-state", {})
        fnst = self.get_state_value(product_state, "fnst", "OFF")
        return fnst

    @property
    def brightness(self) -> int:
        """Return display brightness (bril)."""
        try:
            product_state = self._state_data.get("product-state", {})
            bril = self.get_state_value(product_state, "bril", "0002")
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
            cflr = self.get_state_value(product_state, "cflr", "0000")
            if cflr == "INV":  # Invalid/no filter installed
                return 0
            return int(cflr)
        except (ValueError, TypeError):
            return 0

    @property
    def hepa_filter_type(self) -> str:
        """Return HEPA filter type."""
        product_state = self._state_data.get("product-state", {})
        filter_type = self.get_state_value(product_state, "hflt", "NONE")
        _LOGGER.debug("HEPA filter type for %s: %s", self.serial_number, filter_type)
        return filter_type

    @property
    def carbon_filter_type(self) -> str:
        """Return carbon filter type."""
        product_state = self._state_data.get("product-state", {})
        filter_type = self.get_state_value(product_state, "cflt", "NONE")
        _LOGGER.debug("Carbon filter type for %s: %s", self.serial_number, filter_type)
        return filter_type

    # Robot Vacuum Properties
    # =======================

    @property
    def robot_state(self) -> str | None:
        """Return current robot vacuum state.

        Maps to Dyson robot vacuum operational states like:
        FULL_CLEAN_RUNNING, INACTIVE_CHARGED, FAULT_LOST, etc.

        Returns:
            Robot state string or None if not available or not a robot device
        """
        try:
            product_state = self._state_data.get("product-state", {})
            # Robot state may be in 'state' or 'newstate' field depending on model
            robot_state = product_state.get("state") or product_state.get("newstate")
            if robot_state:
                _LOGGER.debug("Robot state for %s: %s", self.serial_number, robot_state)
            return robot_state
        except (KeyError, TypeError) as e:
            _LOGGER.debug("Failed to get robot state for %s: %s", self.serial_number, e)
            return None

    @property
    def robot_battery_level(self) -> int | None:
        """Return robot vacuum battery level percentage.

        Returns:
            Battery level (0-100) or None if not available
        """
        try:
            product_state = self._state_data.get("product-state", {})
            battery = product_state.get("batteryChargeLevel")
            if battery is not None:
                battery_int = int(battery)
                _LOGGER.debug(
                    "Robot battery for %s: %d%%", self.serial_number, battery_int
                )
                return battery_int
        except (ValueError, TypeError, KeyError) as e:
            _LOGGER.debug(
                "Failed to get robot battery for %s: %s", self.serial_number, e
            )
        return None

    @property
    def robot_global_position(self) -> list[int] | None:
        """Return robot vacuum global position coordinates.

        Returns:
            List of [x, y] coordinates or None if not available
        """
        try:
            product_state = self._state_data.get("product-state", {})
            position = product_state.get("globalPosition")
            if position and isinstance(position, list) and len(position) == 2:
                pos_coords = [int(position[0]), int(position[1])]
                _LOGGER.debug(
                    "Robot position for %s: %s", self.serial_number, pos_coords
                )
                return pos_coords
        except (ValueError, TypeError, KeyError, IndexError) as e:
            _LOGGER.debug(
                "Failed to get robot position for %s: %s", self.serial_number, e
            )
        return None

    @property
    def robot_full_clean_type(self) -> str | None:
        """Return robot vacuum cleaning operation type.

        Returns:
            Clean type (immediate, scheduled, manual) or None if not available
        """
        try:
            product_state = self._state_data.get("product-state", {})
            clean_type = product_state.get("fullCleanType")
            if clean_type:
                _LOGGER.debug(
                    "Robot clean type for %s: %s", self.serial_number, clean_type
                )
            return clean_type
        except (KeyError, TypeError) as e:
            _LOGGER.debug(
                "Failed to get robot clean type for %s: %s", self.serial_number, e
            )
            return None

    @property
    def robot_clean_id(self) -> str | None:
        """Return robot vacuum current cleaning session ID.

        Returns:
            Unique clean session identifier or None if not available
        """
        try:
            product_state = self._state_data.get("product-state", {})
            clean_id = product_state.get("cleanId")
            if clean_id:
                _LOGGER.debug("Robot clean ID for %s: %s", self.serial_number, clean_id)
            return clean_id
        except (KeyError, TypeError) as e:
            _LOGGER.debug(
                "Failed to get robot clean ID for %s: %s", self.serial_number, e
            )
            return None

    def _get_command_timestamp(self) -> str:
        """Get formatted timestamp for MQTT commands."""
        from datetime import datetime

        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    def _detect_power_control_type(self) -> str:
        """Detect device power control type based on MQTT message patterns.

        Returns:
            "fpwr" for modern devices that have fpwr key in their state messages
            "fmod" for HP02-style devices that use fmod for power control (no fpwr key)
            "unknown" if not enough data to determine

        Note:
            This is a fallback detection method that only runs when the coordinator's
            immediate detection failed during startup. It analyzes STATE-CHANGE messages:
            - Modern devices: include fpwr key in messages, use fpwr-based control
            - HP02-style devices: have fmod but no fpwr key, use fmod-based power control
            - Some modern heating devices may have both fpwr and fmod (fpwr is power, fmod is fan mode)
            - Only requires 1 STATE-CHANGE message since we just need to see which keys are present
        """
        # Need at least one message to make a determination
        if self._total_state_messages < 1:
            return "unknown"

        # If we've seen fpwr in any messages, this is a modern fpwr-based device
        if self._fpwr_message_count > 0:
            return "fpwr"

        # If we've never seen fpwr but have seen fmod, this is an HP02-style fmod-based device
        if self._fmod_message_count > 0:
            return "fmod"

        return "unknown"

    def get_state_value(
        self, data: dict[str, Any], key: str, default: str = "OFF"
    ) -> str:
        """Get current value from device data.

        Public interface for retrieving device state values from formatted data.

        Args:
            data: Device state data dictionary
            key: The state key to retrieve
            default: Default value if key is not found

        Returns:
            String representation of the state value

        Note:
            Values are normalized at message processing time:
            - CURRENT-STATE messages: already strings
            - STATE-CHANGE messages: [previous, current] arrays converted to current string
            - ENVIRONMENTAL-CURRENT-SENSOR-DATA messages: already strings
            - Fault messages: already strings
        """
        value = data.get(key, default)
        return str(value)

    def get_environmental_data(self) -> dict[str, Any]:
        """Get environmental data from the device.

        Public interface for accessing environmental sensor data such as PM2.5,
        PM10, humidity, temperature, and other air quality measurements.

        Returns:
            Dictionary containing environmental data with keys like:
            - pm25: PM2.5 particle concentration
            - pm10: PM10 particle concentration
            - va10: Volatile organic compounds
            - noxl: Nitrogen dioxide levels
            - hchr: Formaldehyde concentration
            - hact: Humidity percentage
            - tact: Temperature readings

        Note:
            Returns a copy of the internal environmental data to prevent
            external modifications. Use specific properties like pm25,
            pm10, etc. for type-safe access to individual values.
        """
        return dict(self._environmental_data)

    # Command methods for device control
    async def set_night_mode(self, enabled: bool) -> None:
        """Enable or disable night mode for quiet operation.

        Args:
            enabled: True to enable night mode, False to disable

        Raises:
            RuntimeError: If device is not connected
            Exception: If command transmission fails

        Note:
            Night mode reduces fan speed, dims display brightness, and
            minimizes operational noise for bedroom use. When enabled:
            - Fan speed is limited to lower levels (typically 1-4)
            - Display brightness is significantly reduced
            - Operational sounds are minimized
            - Air quality monitoring continues normally

            Night mode automatically overrides manual speed settings
            while active, returning to previous settings when disabled.

        Example:
            Activate night mode for bedroom use:

            >>> # Enable quiet night operation
            >>> await device.set_night_mode(True)
            >>> print(f"Night mode: {device.night_mode}")
            >>>
            >>> # Morning routine - disable night mode
            >>> await device.set_night_mode(False)
            >>>
            >>> # Check current night mode status
            >>> if device.night_mode:
            >>>     print("Device in quiet night mode")
            >>> else:
            >>>     print("Device in normal operation mode")
        """
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

        nmod_value = "ON" if enabled else "OFF"

        _LOGGER.debug("=== Sending night mode command: nmod=%s ===", nmod_value)

        try:
            await self.send_command("STATE-SET", {"nmod": nmod_value})
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

    async def set_fan_speed(self, speed: int) -> None:
        """Set fan speed using Dyson's 10-level speed control.

        Args:
            speed: Fan speed level from 0-10 where:
                - 0: Turn off fan (equivalent to set_fan_power(False))
                - 1: Minimum speed (quiet operation)
                - 5: Medium speed (balanced performance/noise)
                - 10: Maximum speed (maximum air circulation)

        Raises:
            RuntimeError: If device is not connected
            Exception: If command transmission fails

        Note:
            Speed levels are automatically clamped to valid range (1-10).
            Setting speed 0 will turn off the fan entirely.

            The device will respond with updated fnsp state via MQTT,
            typically within 1-2 seconds of command execution.

        Example:
            Control fan speed based on air quality:

            >>> pm25 = device.pm25
            >>> if pm25 > 100:  # Very unhealthy air
            >>>     await device.set_fan_speed(10)  # Maximum filtration
            >>> elif pm25 > 50:   # Moderate pollution
            >>>     await device.set_fan_speed(7)   # High speed
            >>> elif pm25 > 25:   # Light pollution
            >>>     await device.set_fan_speed(4)   # Medium speed
            >>> else:  # Good air quality
            >>>     await device.set_fan_speed(2)   # Low speed
        """
        if speed == 0:
            # Speed 0 means turn off the fan
            await self.set_fan_power(False)
            return

        # Ensure speed is in valid range and format as 4-digit string
        speed = max(1, min(10, speed))
        speed_str = f"{speed:04d}"

        await self.send_command("STATE-SET", {"fnsp": speed_str})

    async def set_fan_power(self, enabled: bool) -> None:
        """Set fan power on/off using appropriate method for device type."""
        # Determine power control type if not yet detected
        power_control_type = (
            self._power_control_type or self._detect_power_control_type()
        )

        if power_control_type == "fmod":
            # HP02 and similar devices: use fmod for power control
            fmod_value = "FAN" if enabled else "OFF"
            _LOGGER.debug(
                "Device %s setting power via fmod (HP02-style): %s",
                self.serial_number,
                fmod_value,
            )
            await self.send_command("STATE-SET", {"fmod": fmod_value})
        else:
            # Most devices: use fpwr for power control
            fpwr_value = "ON" if enabled else "OFF"
            _LOGGER.debug(
                "Device %s setting power via fpwr: %s", self.serial_number, fpwr_value
            )
            await self.send_command("STATE-SET", {"fpwr": fpwr_value})

    async def reset_hepa_filter_life(self) -> None:
        """Reset HEPA filter life to 100%."""
        await self.send_command("STATE-SET", {"hflr": "0100"})

    async def reset_carbon_filter_life(self) -> None:
        """Reset carbon filter life to 100%."""
        await self.send_command("STATE-SET", {"cflr": "0100"})

    async def set_sleep_timer(self, minutes: int) -> None:
        """Set sleep timer in minutes (0 to cancel, 15-540 for active timer)."""
        # Convert minutes to the format expected by the device
        # Dyson uses a specific encoding for sleep timer values
        if minutes == 0:
            timer_value = "OFF"
        else:
            # Ensure minutes is within valid range
            minutes = max(15, min(540, minutes))
            # Convert to 4-digit string format (e.g., 15 minutes = "0015", 240 minutes = "0240")
            timer_value = f"{minutes:04d}"

        await self.send_command("STATE-SET", {"sltm": timer_value})

    async def set_oscillation_angles(self, lower_angle: int, upper_angle: int) -> None:
        """Set custom oscillation angles."""

        # Ensure angles are within valid range (0-350 degrees)
        lower_angle = max(0, min(350, lower_angle))
        upper_angle = max(0, min(350, upper_angle))

        # Ensure lower angle is less than upper angle
        if lower_angle >= upper_angle:
            raise ValueError("Lower angle must be less than upper angle")

        # Convert angles to 4-digit string format
        lower_str = f"{lower_angle:04d}"
        upper_str = f"{upper_angle:04d}"

        await self.send_command(
            "STATE-SET",
            {
                "osal": lower_str,  # Oscillation angle lower
                "osau": upper_str,  # Oscillation angle upper
                "oson": "ON",  # Enable oscillation
                "ancp": "CUST",  # Custom angles
            },
        )

    async def set_oscillation_angles_day0(
        self, lower_angle: int, upper_angle: int, ancp_value: int | None = None
    ) -> None:
        """Set oscillation angles for AdvanceOscillationDay0 capability.

        Day0 devices use fixed physical angles (157°-197°) but variable ancp to
        control the oscillation pattern within that range.
        Based on MQTT trace analysis, ancp specifies the preset mode (15°, 40°, 70°).

        Special behavior:
        - ancp_value specifies the oscillation preset pattern
        - Fixed lower/upper angles are always used (157°-197°)
        - ancp determines how the device oscillates within that range
        """
        # Day0 devices use fixed physical angles and variable ancp for preset control
        # Based on MQTT trace: osal=0157, osau=0197, ancp=preset_value
        lower_str = f"{lower_angle:04d}"
        upper_str = f"{upper_angle:04d}"

        # Build the command data
        command_data = {
            "osal": lower_str,  # Oscillation angle lower (fixed 157°)
            "osau": upper_str,  # Oscillation angle upper (fixed 197°)
            "oson": "ON",  # Enable oscillation
        }

        # Add ancp parameter if provided (preset pattern control)
        if ancp_value is not None:
            ancp_str = f"{ancp_value:04d}"
            command_data["ancp"] = ancp_str

            _LOGGER.debug(
                "Setting Day0 oscillation: angles %s°-%s°, ancp=%s (preset %s°) for %s",
                lower_angle,
                upper_angle,
                ancp_value,
                ancp_value,
                self.serial_number,
            )
        else:
            _LOGGER.debug(
                "Setting Day0 oscillation: angles %s°-%s° (no ancp) for %s",
                lower_angle,
                upper_angle,
                self.serial_number,
            )

        # Send the complete command
        await self.send_command("STATE-SET", command_data)

    async def set_auto_mode(self, enabled: bool) -> None:
        """Set auto mode on/off."""
        auto_value = "ON" if enabled else "OFF"
        await self.send_command("STATE-SET", {"auto": auto_value})

    async def set_oscillation(self, enabled: bool, angle: int | None = None) -> None:
        """Control fan oscillation with optional angle specification.

        Args:
            enabled: True to enable oscillation, False to disable
            angle: Optional specific oscillation angle in degrees (0-350).
                  If provided, enables oscillation at the specified angle.
                  If None, uses device default oscillation pattern.

        Raises:
            RuntimeError: If device is not connected
            ValueError: If angle is outside valid range (0-350)
            Exception: If command transmission fails

        Note:
            Oscillation distributes airflow across a wider area for more
            effective room coverage. Different Dyson models support different
            oscillation patterns and angle ranges.

            When angle is specified, oscillation is automatically enabled
            regardless of the enabled parameter value.

        Example:
            Control oscillation for optimal air distribution:

            >>> # Enable default oscillation pattern
            >>> await device.set_oscillation(True)
            >>>
            >>> # Set specific oscillation angle (if supported)
            >>> await device.set_oscillation(True, angle=90)  # 90-degree sweep
            >>>
            >>> # Disable oscillation for focused airflow
            >>> await device.set_oscillation(False)
            >>>
            >>> # Check if oscillation is currently active
            >>> if device.oscillation_enabled:
            >>>     print("Device is oscillating")
        """
        data = {"oson": "ON" if enabled else "OFF"}

        if enabled and angle is not None:
            # Set specific oscillation angle
            angle_str = f"{angle:04d}"
            data["ancp"] = angle_str

        await self.send_command("STATE-SET", data)

    async def set_humidifier_mode(self, enabled: bool, auto_mode: bool = False) -> None:
        """Set humidifier mode on/off with optional auto mode."""
        hume_value = "HUMD" if enabled else "OFF"
        # Only set auto mode if humidifier is enabled
        haut_value = "ON" if (enabled and auto_mode) else "OFF"
        await self.send_command("STATE-SET", {"hume": hume_value, "haut": haut_value})

    async def set_target_humidity(self, humidity: int) -> None:
        """Set target humidity percentage (30-70% in 10% steps).

        Args:
            humidity: Target humidity percentage (30-70%)
        """
        if not 30 <= humidity <= 70:
            raise ValueError("Target humidity must be between 30% and 70%")

        # Convert humidity percentage to device format (4-digit string)
        humidity_value = f"{humidity:04d}"
        await self.send_command("STATE-SET", {"humt": humidity_value})

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

        await self.send_command(
            "STATE-SET",
            {
                "hmod": "HEAT",  # Enable heating mode when setting temperature
                "hmax": temp_str,
            },
        )

    async def set_continuous_monitoring(self, enabled: bool) -> None:
        """Set continuous monitoring on/off."""
        await self.send_command("STATE-SET", {"rhtm": "ON" if enabled else "OFF"})

    # Robot Vacuum Control Methods
    # ============================

    async def robot_pause(self) -> None:
        """Pause robot vacuum cleaning operation.

        Sends PAUSE command via MQTT to suspend current cleaning.
        Robot will remain in place and can be resumed later.

        Raises:
            RuntimeError: If device is not connected
            Exception: If command transmission fails
        """
        if not self.is_connected:
            raise RuntimeError(f"Device {self.serial_number} is not connected")

        _LOGGER.info("Sending pause command to robot %s", self.serial_number)

        from .const import ROBOT_CMD_PAUSE

        command_data = {
            "msg": ROBOT_CMD_PAUSE,
            "time": self._get_command_timestamp(),
        }

        await self._send_robot_command(command_data)

    async def robot_resume(self) -> None:
        """Resume robot vacuum cleaning operation.

        Sends RESUME command via MQTT to continue paused cleaning.
        Robot will continue from where it was paused.

        Raises:
            RuntimeError: If device is not connected
            Exception: If command transmission fails
        """
        if not self.is_connected:
            raise RuntimeError(f"Device {self.serial_number} is not connected")

        _LOGGER.info("Sending resume command to robot %s", self.serial_number)

        from .const import ROBOT_CMD_RESUME

        command_data = {
            "msg": ROBOT_CMD_RESUME,
            "time": self._get_command_timestamp(),
        }

        await self._send_robot_command(command_data)

    async def robot_abort(self) -> None:
        """Abort robot vacuum cleaning and return to dock.

        Sends ABORT command via MQTT to stop cleaning and return to dock.
        This cancels the current cleaning session.

        Raises:
            RuntimeError: If device is not connected
            Exception: If command transmission fails
        """
        if not self.is_connected:
            raise RuntimeError(f"Device {self.serial_number} is not connected")

        _LOGGER.info("Sending abort command to robot %s", self.serial_number)

        from .const import ROBOT_CMD_ABORT

        command_data = {
            "msg": ROBOT_CMD_ABORT,
            "time": self._get_command_timestamp(),
        }

        await self._send_robot_command(command_data)

    async def robot_request_state(self) -> None:
        """Request current robot vacuum state.

        Sends REQUEST-CURRENT-STATE command to get immediate status update.
        Robot will respond with complete state information on status topic.

        Raises:
            RuntimeError: If device is not connected
            Exception: If command transmission fails
        """
        if not self.is_connected:
            raise RuntimeError(f"Device {self.serial_number} is not connected")

        _LOGGER.debug("Requesting current state from robot %s", self.serial_number)

        from .const import ROBOT_CMD_REQUEST_STATE

        command_data = {
            "msg": ROBOT_CMD_REQUEST_STATE,
            "time": self._get_command_timestamp(),
        }

        await self._send_robot_command(command_data)

    async def _send_robot_command(self, command_data: dict[str, Any]) -> None:
        """Send robot vacuum command via MQTT.

        Sends command to robot vacuum using device-specific MQTT topic.
        Uses existing MQTT client infrastructure with JSON message format.

        Args:
            command_data: Command dictionary with msg, time, and optional data

        Raises:
            RuntimeError: If device is not connected or MQTT client unavailable
            Exception: If command transmission fails
        """
        if not self.is_connected or not self._mqtt_client:
            raise RuntimeError(f"Device {self.serial_number} MQTT not available")

        # Use existing command topic format for robot vacuums
        topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
        message = json.dumps(command_data)

        _LOGGER.debug(
            "Sending robot command to %s on topic %s: %s",
            self.serial_number,
            topic,
            command_data,
        )

        try:
            # Use asyncio to make MQTT publish non-blocking
            import asyncio

            loop = asyncio.get_event_loop()

            # Publish command using existing MQTT infrastructure
            def _publish_command():
                result = self._mqtt_client.publish(topic, message)
                result.wait_for_publish(timeout=5.0)  # 5 second timeout

            await loop.run_in_executor(None, _publish_command)

            _LOGGER.debug("Robot command sent successfully to %s", self.serial_number)

        except Exception as ex:
            _LOGGER.error(
                "Failed to send robot command to %s: %s", self.serial_number, ex
            )
            raise

    async def set_direction(self, direction: str) -> None:
        """Set fan direction (forward/reverse).

        Args:
            direction: Direction to set ("forward" or "reverse")
        """
        # Map Home Assistant direction to Dyson direction values
        # Based on libdyson-neon: fdir="ON" = front airflow = forward direction
        #                         fdir="OFF" = no front airflow = reverse direction
        direction_value = "ON" if direction.lower() == "forward" else "OFF"

        await self.send_command("STATE-SET", {"fdir": direction_value})

        _LOGGER.debug(
            "Set fan direction to %s (%s) for %s",
            direction,
            direction_value,
            self.serial_number,
        )

    async def set_heating_mode(self, mode: str) -> None:
        """Set heating mode.

        Args:
            mode: Heating mode to set ("HEAT", "OFF")
        """
        await self.send_command("STATE-SET", {"hmod": mode})

        _LOGGER.debug(
            "Set heating mode to %s for %s",
            mode,
            self.serial_number,
        )

    async def set_fan_state(self, state: str) -> None:
        """Set fan state.

        Args:
            state: Fan state to set ("OFF", "FAN")
        """
        await self.send_command("STATE-SET", {"fnst": state})

        _LOGGER.debug(
            "Set fan state to %s for %s",
            state,
            self.serial_number,
        )

    async def set_water_hardness(self, hardness: str) -> None:
        """Set water hardness level for humidifier.

        Args:
            hardness: Water hardness level ("soft", "medium", "hard")
        """
        # Map hardness level to device values
        hardness_map = {
            "soft": "0675",
            "medium": "1350",
            "hard": "2025",
        }

        if hardness not in hardness_map:
            raise ValueError(
                f"Invalid water hardness: {hardness}. Must be one of {list(hardness_map.keys())}"
            )

        await self.send_command("STATE-SET", {"wath": hardness_map[hardness]})

        _LOGGER.debug(
            "Set water hardness to %s (%s) for %s",
            hardness,
            hardness_map[hardness],
            self.serial_number,
        )

    async def set_robot_power(
        self, power_level: str, model_type: str = "generic"
    ) -> None:
        """Set robot vacuum power level.

        Args:
            power_level: Power level value (model-specific)
            model_type: Robot model type ("360eye", "heurist", "vis_nav", or "generic")
        """
        # Build the robot command data structure
        command_data = {
            "msg": "STATE-SET",
            "time": self._get_command_timestamp(),
            "data": {
                "fPwr": int(power_level) if model_type != "360eye" else power_level
            },
        }

        await self._send_robot_command(command_data)

        _LOGGER.debug(
            "Set %s robot power to %s for %s",
            model_type,
            power_level,
            self.serial_number,
        )
