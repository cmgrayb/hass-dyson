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

from .const import DOMAIN

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
    ) -> None:
        """Initialize the device wrapper."""
        self.hass = hass
        self.serial_number = serial_number
        self.host = host
        self.credential = credential
        self.mqtt_prefix = mqtt_prefix
        self.capabilities = capabilities or []

        self._mqtt_client: Optional[mqtt.Client] = None
        self._connected = False
        self._last_reconnect_attempt = 0.0  # Track last reconnection attempt
        self._reconnect_backoff = 30.0  # Wait 30 seconds between reconnect attempts
        self._state_data: Dict[str, Any] = {}
        self._environmental_data: Dict[str, Any] = {}
        self._faults_data: Dict[str, Any] = {}  # Raw fault data from device
        self._message_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

        # Device info from successful connection
        self._device_info: Optional[Dict[str, Any]] = None
        self._firmware_version: str = "Unknown"

    async def connect(self) -> bool:
        """Connect to the device using paho-mqtt directly."""
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

        try:
            _LOGGER.debug("Connecting to device %s at %s", self.serial_number, self.host)
            _LOGGER.debug("Using credential length: %s", len(self.credential) if self.credential else 0)
            _LOGGER.debug("Using MQTT prefix: %s", self.mqtt_prefix)

            # Create paho MQTT client
            client_id = f"dyson-ha-{uuid.uuid4().hex[:8]}"
            self._mqtt_client = mqtt.Client(client_id=client_id)

            # Set up authentication
            self._mqtt_client.username_pw_set(self.serial_number, self.credential)

            # Set up callbacks
            self._mqtt_client.on_connect = self._on_connect
            self._mqtt_client.on_disconnect = self._on_disconnect
            self._mqtt_client.on_message = self._on_message

            # Connect to MQTT broker
            _LOGGER.debug("Attempting MQTT connection to %s:1883", self.host)
            result = await self.hass.async_add_executor_job(self._mqtt_client.connect, self.host, 1883, 60)

            if result == mqtt.CONNACK_ACCEPTED:
                # Start the network loop in a thread
                await self.hass.async_add_executor_job(self._mqtt_client.loop_start)

                # Wait for connection to be established
                connection_timeout = 10  # 10 seconds timeout
                check_interval = 0.1  # Check every 100ms
                elapsed_time = 0

                while elapsed_time < connection_timeout:
                    if self._connected:
                        _LOGGER.info(
                            "Successfully connected to device %s after %.1f seconds", self.serial_number, elapsed_time
                        )
                        return True

                    await asyncio.sleep(check_interval)
                    elapsed_time += check_interval

                _LOGGER.error("Connection timeout for device %s", self.serial_number)
                return False
            else:
                _LOGGER.error("MQTT connection failed with result: %s", result)
                return False

        except Exception as err:
            _LOGGER.error("Failed to connect to device %s: %s", self.serial_number, err)
            return False

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._mqtt_client and self._connected:
            try:
                _LOGGER.debug("Disconnecting from device %s", self.serial_number)
                await self.hass.async_add_executor_job(self._mqtt_client.loop_stop)
                await self.hass.async_add_executor_job(self._mqtt_client.disconnect)
                self._connected = False
            except Exception as err:
                _LOGGER.error("Failed to disconnect from device %s: %s", self.serial_number, err)

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
            # Get state from libdyson-mqtt client
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
        """Normalize faults data to list format."""
        if not faults:
            return []

        if isinstance(faults, list):
            return faults
        else:
            self._faults_data = faults
            return [faults]

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
