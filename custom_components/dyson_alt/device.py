"""Dyson device wrapper using libdyson_mqtt."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from libdyson_mqtt import ConnectionConfig, DysonMqttClient, MqttMessage
else:
    try:
        from libdyson_mqtt import ConnectionConfig, DysonMqttClient, MqttMessage
    except ImportError:
        _LOGGER.error("libdyson_mqtt not available")
        DysonMqttClient = None  # type: ignore[misc,assignment]
        ConnectionConfig = None  # type: ignore[misc,assignment]
        MqttMessage = None  # type: ignore[misc,assignment]


class DysonDevice:
    """Wrapper for Dyson device communication using libdyson_mqtt."""

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

        self._mqtt_client: Optional["DysonMqttClient"] = None
        self._connected = False
        self._state_data: Dict[str, Any] = {}
        self._environmental_data: Dict[str, Any] = {}
        self._faults_data: Dict[str, Any] = {}  # Raw fault data from device
        self._message_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

        # Device info from successful connection
        self._device_info: Optional[Dict[str, Any]] = None

    async def connect(self) -> bool:
        """Connect to the device using libdyson_mqtt."""
        if DysonMqttClient is None or ConnectionConfig is None:
            _LOGGER.error("libdyson_mqtt not available")
            return False

        try:
            _LOGGER.debug("Connecting to device %s at %s", self.serial_number, self.host)
            _LOGGER.debug("Using credential length: %s", len(self.credential) if self.credential else 0)
            _LOGGER.debug("Using MQTT prefix: %s", self.mqtt_prefix)

            # Create MQTT topics using our working format
            mqtt_topics = [
                f"{self.mqtt_prefix}/{self.serial_number}/status/current",
                f"{self.mqtt_prefix}/{self.serial_number}/status/faults",
            ]

            # Create connection configuration (using our successful test format)
            config = ConnectionConfig(
                host=self.host,
                mqtt_username=self.serial_number,
                mqtt_password=self.credential,
                mqtt_topics=mqtt_topics,
                port=1883,
                keepalive=60,
                client_id=self.serial_number,
            )

            # Create MQTT client
            self._mqtt_client = DysonMqttClient(config)

            # Set up message handler
            if self._mqtt_client and hasattr(self._mqtt_client, "set_message_callback"):
                self._mqtt_client.set_message_callback(self._handle_message)

            # Connect to device
            if self._mqtt_client and hasattr(self._mqtt_client, "connect"):
                await self.hass.async_add_executor_job(self._mqtt_client.connect)

                # Wait for connection to be established (with timeout)
                connection_timeout = 30  # 30 seconds timeout
                check_interval = 0.5  # Check every 500ms
                elapsed_time = 0

                while elapsed_time < connection_timeout:
                    if (
                        self._mqtt_client
                        and hasattr(self._mqtt_client, "is_connected")
                        and self._mqtt_client.is_connected()
                    ):
                        self._connected = True
                        _LOGGER.info(
                            "Successfully connected to device %s after %.1f seconds", self.serial_number, elapsed_time
                        )

                        # Request initial state
                        await self._request_current_state()
                        return True

                    # Wait before checking again
                    await asyncio.sleep(check_interval)
                    elapsed_time += check_interval

                # Connection timed out
                _LOGGER.error(
                    "Connection timeout after %.1f seconds for device %s", connection_timeout, self.serial_number
                )
                return False
            else:
                _LOGGER.error("Failed to connect to device %s - MQTT client not available", self.serial_number)
                return False

        except Exception as err:
            _LOGGER.error("Failed to connect to device %s: %s", self.serial_number, err)
            return False

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._mqtt_client and self._connected:
            try:
                _LOGGER.debug("Disconnecting from device %s", self.serial_number)
                await self.hass.async_add_executor_job(self._mqtt_client.disconnect)
                self._connected = False
            except Exception as err:
                _LOGGER.error("Failed to disconnect from device %s: %s", self.serial_number, err)

    def _handle_message(self, message: Any) -> None:
        """Handle MQTT message from device."""
        try:
            # Extract topic and payload from MqttMessage object
            topic = getattr(message, "topic", "")
            payload = getattr(message, "payload", "")

            _LOGGER.debug("Received message on %s: %s", topic, payload[:100])

            # Parse JSON payload
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")

            data = json.loads(payload)
            self._process_message_data(data, topic)

        except Exception as err:
            _LOGGER.error("Error handling message: %s", err)

    def _process_message_data(self, data: Dict[str, Any], topic: str) -> None:
        """Process parsed message data by type."""
        message_type = data.get("msg", "")

        # Handle different message types based on our successful test
        if message_type == "CURRENT-STATE":
            self._handle_current_state(data)
        elif message_type == "ENVIRONMENTAL-CURRENT-SENSOR-DATA":
            self._handle_environmental_data(data)
        elif message_type == "CURRENT-FAULTS":
            self._handle_faults_data(data)
        elif message_type == "STATE-CHANGE":
            self._handle_state_change(data)

        # Notify callbacks
        self._notify_callbacks(topic, data)

    def _handle_current_state(self, data: Dict[str, Any]) -> None:
        """Handle current state message."""
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
        product_state = data.get("product-state", {})
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
            command = '{"msg":"REQUEST-CURRENT-STATE"}'

            await self.hass.async_add_executor_job(self._mqtt_client.publish, command_topic, command)
            _LOGGER.debug("Requested current state from %s", self.serial_number)

        except Exception as err:
            _LOGGER.error("Failed to request state from %s: %s", self.serial_number, err)

    async def _request_current_faults(self) -> None:
        """Request current faults from device."""
        if not self._connected or not self._mqtt_client:
            return

        try:
            command_topic = f"{self.mqtt_prefix}/{self.serial_number}/command"
            command = '{"msg":"REQUEST-CURRENT-FAULTS"}'

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
            return self._state_data

        try:
            # Get state from libdyson-mqtt client
            if hasattr(self._mqtt_client, "get_state"):
                state = await self.hass.async_add_executor_job(self._mqtt_client.get_state)  # type: ignore[attr-defined]
                if state:
                    self._state_data.update(state)
            elif hasattr(self._mqtt_client, "state"):
                # Some MQTT clients might have a state property
                state = getattr(self._mqtt_client, "state", {})
                if state:
                    self._state_data.update(state)

        except Exception as err:
            _LOGGER.warning("Failed to get state from device %s: %s", self.serial_number, err)

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

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information for Home Assistant."""
        return {
            "identifiers": {(DOMAIN, self.serial_number)},
            "name": f"Dyson {self.serial_number}",
            "manufacturer": "Dyson",
            "model": self.mqtt_prefix,  # Use MQTT prefix as model indicator
            "sw_version": self._state_data.get("product-state", {}).get("ver", "Unknown"),
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
            hflr = self._state_data.get("product-state", {}).get("hflr", "0000")
            if hflr == "INV":  # Invalid/no filter installed
                return 0
            return int(hflr)
        except (ValueError, TypeError):
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
        return self._state_data.get("product-state", {}).get("hflt", "NONE")

    @property
    def carbon_filter_type(self) -> str:
        """Return carbon filter type."""
        return self._state_data.get("product-state", {}).get("cflt", "NONE")

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
