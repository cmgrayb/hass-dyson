"""Data update coordinator for Dyson devices."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed  # noqa: F401
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DISCOVERY_METHOD,
    CONF_SERIAL_NUMBER,
    DEFAULT_DEVICE_POLLING_INTERVAL,
    DISCOVERY_CLOUD,
    DISCOVERY_STICKER,
    DOMAIN,
    EVENT_DEVICE_FAULT,
    MQTT_CMD_REQUEST_CURRENT_STATE,
    MQTT_CMD_REQUEST_FAULTS,
)
from .device import DysonDevice

_LOGGER = logging.getLogger(__name__)


class DysonDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Coordinator to manage data updates for a Dyson device."""

    def __init__(self, hass: HomeAssistant, config_entry) -> None:  # type: ignore
        """Initialize the coordinator."""
        self.config_entry = config_entry
        self.device: Optional[DysonDevice] = None
        self._device_capabilities: List[str] = []
        self._device_category: str = ""
        self._firmware_version: str = "Unknown"

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{config_entry.data[CONF_SERIAL_NUMBER]}",
            update_interval=timedelta(seconds=DEFAULT_DEVICE_POLLING_INTERVAL),
        )

    @property
    def device_capabilities(self) -> List[str]:
        """Return device capabilities."""
        return self._device_capabilities

    @property
    def device_category(self) -> str:
        """Return device category."""
        return self._device_category

    @property
    def firmware_version(self) -> str:
        """Return device firmware version."""
        return self._firmware_version

    @property
    def serial_number(self) -> str:
        """Return device serial number."""
        # Debug logging to see what's in the config data
        _LOGGER.debug("Config entry data keys: %s", list(self.config_entry.data.keys()))
        _LOGGER.debug("Config entry data: %s", self.config_entry.data)

        # Handle both legacy single-device entries and new account-level entries
        if CONF_SERIAL_NUMBER in self.config_entry.data:
            serial = self.config_entry.data[CONF_SERIAL_NUMBER]
            _LOGGER.debug("Found serial_number in config: %s", serial)
            return serial
        else:
            # For account-level entries, serial number should be passed differently
            serial = self.config_entry.data.get("device_serial_number", "unknown")
            _LOGGER.debug("Using device_serial_number fallback: %s", serial)
            return serial

    async def async_config_entry_first_refresh(self) -> None:
        """Perform first refresh and device setup."""
        _LOGGER.debug("Performing first refresh for device %s", self.serial_number)

        try:
            # Initialize device connection
            await self._async_setup_device()

            # Perform initial data fetch
            await super().async_config_entry_first_refresh()

        except Exception as err:
            _LOGGER.error("Failed to setup device %s: %s", self.serial_number, err)
            raise

    async def _async_setup_device(self) -> None:
        """Set up the Dyson device connection."""
        discovery_method = self.config_entry.data.get(CONF_DISCOVERY_METHOD, DISCOVERY_CLOUD)

        if discovery_method == DISCOVERY_CLOUD:
            await self._async_setup_cloud_device()
        elif discovery_method == DISCOVERY_STICKER:
            # TODO: Update sticker method to use paho-mqtt instead of libdyson_mqtt
            raise UpdateFailed("Sticker discovery method temporarily disabled - use cloud discovery instead")
            # await self._async_setup_sticker_device()
        else:
            raise UpdateFailed(f"Unknown discovery method: {discovery_method}")

    async def _async_setup_cloud_device(self) -> None:
        """Set up device discovered via cloud API."""
        from libdyson_rest import DysonClient

        _LOGGER.debug("Setting up cloud device for %s", self.serial_number)

        try:
            # Check if we have an auth token (from new config flow) or need to authenticate
            auth_token = self.config_entry.data.get("auth_token")
            username = self.config_entry.data.get("username")
            password = self.config_entry.data.get("password")

            _LOGGER.debug(
                "Cloud authentication for %s - username: %s, auth_token: %s",
                self.serial_number,
                username,
                "***" if auth_token else "None",
            )

            # Initialize cloud client
            if auth_token:
                # Use existing auth token from config flow
                cloud_client = DysonClient(email=username, auth_token=auth_token)
            elif username and password:
                # Legacy authentication method
                cloud_client = DysonClient(email=username, password=password)
                # Authenticate using proper flow
                challenge = await self.hass.async_add_executor_job(lambda: cloud_client.begin_login())
                await self.hass.async_add_executor_job(
                    lambda: cloud_client.complete_login(str(challenge.challenge_id), password)
                )
            else:
                raise UpdateFailed("Missing cloud credentials (auth_token or username/password)")

            # Get device list and find our device
            devices = await self.hass.async_add_executor_job(cloud_client.get_devices)
            device_info = None

            for device in devices:
                if device.serial_number == self.serial_number:
                    device_info = device
                    break

            if not device_info:
                raise UpdateFailed(f"Device {self.serial_number} not found in cloud account")

            # Debug: Log device info properties
            _LOGGER.debug("Device info object: %s", device_info)
            _LOGGER.debug("Device info dir: %s", [attr for attr in dir(device_info) if not attr.startswith("_")])

            # Check connected_configuration for MQTT details
            connected_config = getattr(device_info, "connected_configuration", None)
            if connected_config:
                _LOGGER.debug("Connected configuration: %s", connected_config)
                _LOGGER.debug("Connected config type: %s", type(connected_config))
                if hasattr(connected_config, "__dict__"):
                    _LOGGER.debug("Connected config attributes: %s", vars(connected_config))
                _LOGGER.debug(
                    "Connected config dir: %s", [attr for attr in dir(connected_config) if not attr.startswith("_")]
                )

                # Check MQTT object details
                mqtt_obj = getattr(connected_config, "mqtt", None)
                if mqtt_obj:
                    _LOGGER.debug("MQTT object: %s", mqtt_obj)
                    _LOGGER.debug("MQTT object dir: %s", [attr for attr in dir(mqtt_obj) if not attr.startswith("_")])
                    if hasattr(mqtt_obj, "__dict__"):
                        _LOGGER.debug("MQTT object attributes: %s", vars(mqtt_obj))

                    # Check for decoded password attributes that libdyson-rest might provide
                    possible_password_attrs = [
                        "password",
                        "decoded_password",
                        "mqtt_password",
                        "local_broker_password",
                        "broker_password",
                        "credentials",
                    ]
                    for attr in possible_password_attrs:
                        if hasattr(mqtt_obj, attr):
                            value = getattr(mqtt_obj, attr)
                            _LOGGER.debug(
                                "Found MQTT attribute %s: %s (length: %d)",
                                attr,
                                "***" if value else "None",
                                len(value) if value else 0,
                            )

                    # Check for decoded password attributes
                    for attr_name in ["password", "decoded_password", "local_password", "device_password"]:
                        if hasattr(mqtt_obj, attr_name):
                            attr_value = getattr(mqtt_obj, attr_name, "")
                            _LOGGER.debug(
                                "Found MQTT %s: length=%s, value=***", attr_name, len(attr_value) if attr_value else 0
                            )

            # Extract device capabilities and category from API response
            # The API should provide the device category directly
            self._device_category = getattr(device_info, "category", "unknown")
            self._device_capabilities = self._extract_capabilities(device_info)

            # Extract firmware version from connected_configuration
            self._firmware_version = "Unknown"
            connected_config = getattr(device_info, "connected_configuration", None)
            if connected_config:
                firmware_obj = getattr(connected_config, "firmware", None)
                if firmware_obj:
                    firmware_version = getattr(firmware_obj, "version", "Unknown")
                    if firmware_version and firmware_version != "Unknown":
                        self._firmware_version = firmware_version
                        _LOGGER.debug("Found firmware version: %s", firmware_version)

            # Set up MQTT connection with proper ConnectionConfig
            # Extract MQTT credentials from connected_configuration
            mqtt_username = self.serial_number
            mqtt_password = ""

            connected_config = getattr(device_info, "connected_configuration", None)
            if connected_config:
                mqtt_obj = getattr(connected_config, "mqtt", None)
                if mqtt_obj:
                    # Try to get the decoded/plain password first
                    for attr in ["password", "decoded_password", "local_password", "device_password"]:
                        mqtt_password = getattr(mqtt_obj, attr, "")
                        if mqtt_password:
                            _LOGGER.debug(
                                "Found MQTT password using attribute: mqtt.%s (length: %s)", attr, len(mqtt_password)
                            )
                            break

                    # Fall back to decrypting the encoded credentials if no plain password found
                    if not mqtt_password:
                        encrypted_credentials = getattr(mqtt_obj, "local_broker_credentials", "")
                        if encrypted_credentials:
                            try:
                                # Use libdyson-rest to decrypt the local MQTT credentials
                                mqtt_password = cloud_client.decrypt_local_credentials(
                                    encrypted_credentials, self.serial_number
                                )
                                _LOGGER.debug("Successfully decrypted MQTT password (length: %s)", len(mqtt_password))
                            except Exception as e:
                                _LOGGER.error("Failed to decrypt MQTT credentials: %s", e)
                                mqtt_password = ""
                        else:
                            _LOGGER.debug("No local_broker_credentials found in MQTT object")

            _LOGGER.debug(
                "MQTT credentials - username: %s, password_set: %s, password_length: %s",
                mqtt_username,
                bool(mqtt_password),
                len(mqtt_password) if mqtt_password else 0,
            )

            # Debug: Show first/last few characters of password for debugging (but not the full password)
            if mqtt_password:
                _LOGGER.debug("MQTT password format - starts: %s... ends: ...%s", mqtt_password[:8], mqtt_password[-8:])
                _LOGGER.debug(
                    "MQTT password is base64-like: %s",
                    all(
                        c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for c in mqtt_password
                    ),
                )

            if not mqtt_password:
                _LOGGER.error(
                    "MQTT password cannot be empty for device %s. Available attributes: %s",
                    self.serial_number,
                    [attr for attr in dir(device_info) if not attr.startswith("_")],
                )
                raise UpdateFailed("MQTT password cannot be empty")

            # Create our device wrapper with correct parameters
            # DysonDevice will handle the MQTT connection internally
            device_host = self._get_device_host(device_info)
            mqtt_prefix = self._get_mqtt_prefix(device_info)

            self.device = DysonDevice(
                self.hass,
                self.serial_number,
                device_host,
                mqtt_password,  # This becomes the credential for MQTT
                mqtt_prefix,
                self._device_capabilities,
            )

            # Set firmware version in the device for proper device info
            if self._firmware_version != "Unknown":
                self.device.set_firmware_version(self._firmware_version)

            # Let DysonDevice handle the connection
            connected = await self.device.connect()
            if not connected:
                raise UpdateFailed(f"Failed to connect to device {self.serial_number}")

            _LOGGER.info("Successfully set up cloud device %s (%s)", self.serial_number, self._device_category)

        except Exception as err:
            _LOGGER.error("Failed to set up cloud device %s: %s", self.serial_number, err)
            raise UpdateFailed(f"Cloud device setup failed: {err}") from err

    async def _async_setup_sticker_device(self) -> None:
        """Set up device using sticker/WiFi method."""
        # TODO: Update this method to use paho-mqtt instead of libdyson_mqtt
        raise UpdateFailed("Sticker discovery method temporarily disabled - use cloud discovery instead")

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data from the device."""
        if not self.device:
            raise UpdateFailed("Device not initialized")

        _LOGGER.info("Updating data for device %s", self.serial_number)

        try:
            # Check if device is still connected, attempt reconnection if needed
            if not self.device.is_connected:
                _LOGGER.warning("Device %s not connected, attempting reconnection", self.serial_number)
                success = await self.device.connect()
                if not success:
                    raise UpdateFailed(f"Failed to reconnect to device {self.serial_number}")
                _LOGGER.info("Successfully reconnected to device %s", self.serial_number)

            # Request current state (but don't fail if it doesn't work)
            try:
                await self.device.send_command(MQTT_CMD_REQUEST_CURRENT_STATE)
            except Exception as cmd_err:
                _LOGGER.warning("Failed to request current state for %s: %s", self.serial_number, cmd_err)

            # Check for faults (but don't fail if it doesn't work)
            try:
                await self.device.send_command(MQTT_CMD_REQUEST_FAULTS)
            except Exception as fault_err:
                _LOGGER.warning("Failed to request faults for %s: %s", self.serial_number, fault_err)

            # Get current device state - this should work even if commands failed
            device_state = await self.device.get_state()
            _LOGGER.info("Retrieved device state for %s with keys: %s", self.serial_number, list(device_state.keys()))

            # Handle any faults (but don't let this fail the update)
            try:
                await self._async_handle_faults()
            except Exception as handle_err:
                _LOGGER.warning("Failed to handle faults for %s: %s", self.serial_number, handle_err)

            return device_state

        except UpdateFailed:
            # Re-raise UpdateFailed exceptions
            raise
        except Exception as err:
            _LOGGER.error("Error updating data for device %s: %s", self.serial_number, err)
            raise UpdateFailed(f"Error communicating with device: {err}") from err

    async def _async_handle_faults(self) -> None:
        """Handle device faults by firing events."""
        if not self.device:
            return

        faults = await self.device.get_faults()

        for fault in faults:
            _LOGGER.warning("Device fault detected for %s: %s", self.serial_number, fault)

            # Fire event for device fault
            self.hass.bus.async_fire(
                EVENT_DEVICE_FAULT,
                {
                    "device_id": self.serial_number,
                    "fault": fault,
                    "timestamp": fault.get("time"),
                },
            )

    async def async_send_command(self, command: str, data: Optional[Dict[str, Any]] = None) -> bool:
        """Send a command to the device."""
        if not self.device:
            _LOGGER.error("Cannot send command - device not initialized")
            return False

        try:
            await self.device.send_command(command, data)

            # Request updated state after command
            await asyncio.sleep(1)  # Give device time to process
            await self.async_request_refresh()

            return True

        except Exception as err:
            _LOGGER.error("Failed to send command to device %s: %s", self.serial_number, err)
            return False

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and cleanup connections."""
        _LOGGER.debug("Shutting down coordinator for device %s", self.serial_number)

        if self.device:
            await self.device.disconnect()
            self.device = None

    def _extract_capabilities(self, device_info: Any) -> List[str]:
        """Extract device capabilities from cloud device info."""
        capabilities = []

        # Get capabilities from device info if available
        if hasattr(device_info, "capabilities"):
            capabilities = device_info.capabilities or []

        # Capabilities should come from the API response, not from static product type mapping
        # If the API doesn't provide capabilities, they should be configured by the user

        # Remove duplicates and return
        return list(set(capabilities))

    def _get_device_host(self, device_info: Any) -> str:
        """Get device host/IP address from device info."""
        # For cloud devices, try to get the local IP if available
        # Otherwise use the device serial number for mDNS resolution
        return getattr(device_info, "hostname", f"{self.serial_number}.local")

    def _get_mqtt_prefix(self, device_info: Any) -> str:
        """Get MQTT prefix from device info."""
        # The MQTT prefix is typically the product type + model suffix
        product_type = getattr(device_info, "product_type", getattr(device_info, "type", "438"))

        # Map known product types to MQTT prefixes
        prefix_map = {
            "438": "438M",  # Pure Cool
            "475": "475",  # Hot+Cool
            "455": "455",  # Pure Hot+Cool
            "469": "469",  # Pure Cool Desk
            "527": "527",  # V10/V11
        }

        return prefix_map.get(product_type, f"{product_type}M")
