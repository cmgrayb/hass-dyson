"""Data update coordinator for Dyson devices."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from homeassistant.config_entries import ConfigEntry
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

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.config_entry = config_entry
        self.device: Optional[DysonDevice] = None
        self._device_capabilities: List[str] = []
        self._device_category: str = ""

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
    def serial_number(self) -> str:
        """Return device serial number."""
        return self.config_entry.data[CONF_SERIAL_NUMBER]

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
        discovery_method = self.config_entry.data[CONF_DISCOVERY_METHOD]

        if discovery_method == DISCOVERY_CLOUD:
            await self._async_setup_cloud_device()
        elif discovery_method == DISCOVERY_STICKER:
            await self._async_setup_sticker_device()
        else:
            raise UpdateFailed(f"Unknown discovery method: {discovery_method}")

    async def _async_setup_cloud_device(self) -> None:
        """Set up device discovered via cloud API."""
        from libdyson_mqtt import ConnectionConfig, DysonMqttClient
        from libdyson_rest import DysonClient

        _LOGGER.debug("Setting up cloud device for %s", self.serial_number)

        try:
            # Get cloud credentials from config entry
            username = self.config_entry.data.get("username")
            password = self.config_entry.data.get("password")

            _LOGGER.debug(
                "Cloud authentication for %s - username: %s, password: %s",
                self.serial_number,
                username,
                "***" if password else "None",
            )

            if not username or not password:
                raise UpdateFailed("Missing cloud credentials")

            # Initialize cloud client and authenticate using proper flow
            cloud_client = DysonClient()

            # First, begin the login process to get challenge
            await self.hass.async_add_executor_job(lambda: cloud_client.begin_login(username))

            # Then authenticate with password (no OTP for now)
            await self.hass.async_add_executor_job(lambda: cloud_client.authenticate(password))

            # Get device list and find our device
            devices = await self.hass.async_add_executor_job(cloud_client.get_devices)
            device_info = None

            for device in devices:
                if device.serial_number == self.serial_number:
                    device_info = device
                    break

            if not device_info:
                raise UpdateFailed(f"Device {self.serial_number} not found in cloud account")

            # Extract device capabilities and category from API response
            # The API should provide the device category directly
            self._device_category = getattr(device_info, "category", "unknown")
            self._device_capabilities = self._extract_capabilities(device_info)

            # Set up MQTT connection with proper ConnectionConfig
            # For cloud devices, we need to extract connection details from device_info
            connection_config = ConnectionConfig(
                host=getattr(device_info, "hostname", f"{self.serial_number}.local"),
                mqtt_username=getattr(device_info, "mqtt_username", self.serial_number),
                mqtt_password=getattr(device_info, "mqtt_password", ""),
                mqtt_topics=[getattr(device_info, "product_type", "unknown")],
            )
            mqtt_client = DysonMqttClient(connection_config)
            await self.hass.async_add_executor_job(mqtt_client.connect)

            # Create our device wrapper with correct parameters
            self.device = DysonDevice(
                self.hass,
                self.serial_number,
                getattr(device_info, "hostname", f"{self.serial_number}.local"),
                getattr(device_info, "mqtt_password", ""),
                getattr(device_info, "product_type", "unknown"),  # Use API-provided product type
                self._device_capabilities,
            )

            _LOGGER.info("Successfully set up cloud device %s (%s)", self.serial_number, self._device_category)

        except Exception as err:
            _LOGGER.error("Failed to set up cloud device %s: %s", self.serial_number, err)
            raise UpdateFailed(f"Cloud device setup failed: {err}") from err

    async def _async_setup_sticker_device(self) -> None:
        """Set up device using sticker/WiFi method."""
        from libdyson_mqtt import ConnectionConfig, DysonMqttClient

        _LOGGER.debug("Setting up sticker device for %s", self.serial_number)

        try:
            # Get credentials from config entry
            serial_number = self.config_entry.data[CONF_SERIAL_NUMBER]
            password = self.config_entry.data.get("password")
            hostname = self.config_entry.data.get("hostname")
            capabilities = self.config_entry.data.get("capabilities", [])

            if not password:
                raise UpdateFailed("Missing device password for sticker setup")

            # Set capabilities and category from user input
            self._device_capabilities = capabilities
            self._device_category = self.config_entry.data.get("device_category", "unknown")

            # Get MQTT prefix from config entry (user input or API response)
            mqtt_prefix = self.config_entry.data.get("mqtt_prefix")
            if not mqtt_prefix:
                raise UpdateFailed("Missing MQTT prefix for sticker setup")
            _LOGGER.debug("Using MQTT prefix: %s", mqtt_prefix)

            # Create MQTT client with manual credentials using ConnectionConfig
            connection_config = ConnectionConfig(
                host=hostname or f"{serial_number}.local",
                mqtt_username=serial_number or "",
                mqtt_password=password or "",
                mqtt_topics=[mqtt_prefix],  # Use dynamic MQTT prefix from config
            )
            mqtt_client = DysonMqttClient(connection_config)
            await self.hass.async_add_executor_job(mqtt_client.connect)

            # Create our device wrapper with correct parameters
            self.device = DysonDevice(
                self.hass,
                serial_number,
                hostname or f"{serial_number}.local",
                password,
                mqtt_prefix,  # Use dynamic MQTT prefix from config
                self._device_capabilities,
            )

            _LOGGER.info("Successfully set up sticker device %s", self.serial_number)

        except Exception as err:
            _LOGGER.error("Failed to set up sticker device %s: %s", self.serial_number, err)
            raise UpdateFailed(f"Sticker device setup failed: {err}") from err

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data from the device."""
        if not self.device:
            raise UpdateFailed("Device not initialized")

        try:
            # Request current state
            await self.device.send_command(MQTT_CMD_REQUEST_CURRENT_STATE)

            # Check for faults
            await self.device.send_command(MQTT_CMD_REQUEST_FAULTS)

            # Get current device state
            device_state = await self.device.get_state()

            # Handle any faults
            await self._async_handle_faults()

            return device_state

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
