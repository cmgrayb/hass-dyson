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
    CONF_AUTO_ADD_DEVICES,
    CONF_CREDENTIAL,
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_METHOD,
    CONF_HOSTNAME,
    CONF_MQTT_PREFIX,
    CONF_POLL_FOR_DEVICES,
    CONF_SERIAL_NUMBER,
    DEFAULT_AUTO_ADD_DEVICES,
    DEFAULT_CLOUD_POLLING_INTERVAL,
    DEFAULT_DEVICE_POLLING_INTERVAL,
    DEFAULT_POLL_FOR_DEVICES,
    DISCOVERY_CLOUD,
    DISCOVERY_MANUAL,
    DISCOVERY_STICKER,
    DOMAIN,
    EVENT_DEVICE_FAULT,
    MQTT_CMD_REQUEST_CURRENT_STATE,
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
        self._device_category: list[str] = []
        self._device_type: str = ""  # Will be extracted from device info
        self._firmware_version: str = "Unknown"
        self._firmware_auto_update_enabled: bool = False
        self._firmware_latest_version: str | None = None
        self._firmware_update_in_progress: bool = False
        # TODO: Temporarily disabled due to bug in libdyson-rest firmware update detection
        # self._firmware_update_available: bool = False

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
    def device_category(self) -> list[str]:
        """Return device category list."""
        return self._device_category

    @property
    def device_type(self) -> str:
        """Return device type."""
        return self._device_type

    @property
    def firmware_version(self) -> str:
        """Return device firmware version."""
        return self._firmware_version

    @property
    def firmware_auto_update_enabled(self) -> bool:
        """Return whether firmware auto-update is enabled."""
        return self._firmware_auto_update_enabled

    @property
    def firmware_latest_version(self) -> str | None:
        """Return the latest available firmware version."""
        return self._firmware_latest_version

    @property
    def firmware_update_in_progress(self) -> bool:
        """Return whether a firmware update is in progress."""
        return self._firmware_update_in_progress

    # TODO: Temporarily disabled due to bug in libdyson-rest firmware update detection
    # @property
    # def firmware_update_available(self) -> bool:
    #     """Return whether a firmware update is available."""
    #     return self._firmware_update_available

    def _on_environmental_update(self) -> None:
        """Handle environmental data update from device."""
        _LOGGER.debug("Received environmental update notification for %s - updating sensors", self.serial_number)

        # Log current environmental data state for debugging
        if self.device and hasattr(self.device, "_environmental_data"):
            env_data = self.device._environmental_data
            _LOGGER.debug(
                "Environmental data at callback time for %s: pm25=%s, pm10=%s",
                self.serial_number,
                env_data.get("pm25"),
                env_data.get("pm10"),
            )

        # Schedule the async update on the event loop to ensure thread safety
        self.hass.add_job(self.async_update_listeners)

    def _on_message_update(self, topic: str, data: Dict[str, Any]) -> None:
        """Handle message updates from device for real-time state changes."""
        _LOGGER.debug("Received message update for %s on topic %s", self.serial_number, topic)

        # Update entity states for STATE-CHANGE messages
        if data.get("msg") == "STATE-CHANGE":
            _LOGGER.debug("Processing STATE-CHANGE message for real-time entity updates")
            self._handle_state_change_message()

    def _handle_state_change_message(self) -> None:
        """Handle STATE-CHANGE message updates."""
        try:
            if self.device:
                self._schedule_coordinator_data_update()
            else:
                self._schedule_listener_update()
        except Exception as e:
            _LOGGER.warning("Error setting up STATE-CHANGE data update: %s", e)
            self._schedule_fallback_update()

    def _schedule_coordinator_data_update(self) -> None:
        """Schedule coordinator data update with fresh device state."""
        self.hass.loop.call_soon_threadsafe(self._create_coordinator_update_task)

    def _create_coordinator_update_task(self) -> None:
        """Create the async update task."""
        self.hass.async_create_task(self._update_coordinator_data())

    async def _update_coordinator_data(self) -> None:
        """Update coordinator data in the event loop."""
        try:
            fresh_state = await self.device.get_state()
            self.data = fresh_state
            _LOGGER.debug("Updated coordinator data for STATE-CHANGE, triggering listeners")
        except Exception as e:
            _LOGGER.warning("Error getting fresh state for STATE-CHANGE: %s", e)
        finally:
            # Always trigger listeners, even if data update failed
            self.async_update_listeners()

    def _schedule_listener_update(self) -> None:
        """Schedule async listener update when no device is available."""
        self.hass.loop.call_soon_threadsafe(self.async_update_listeners)

    def _schedule_fallback_update(self) -> None:
        """Schedule fallback listener update in case of errors."""
        try:
            self.hass.loop.call_soon_threadsafe(self.async_update_listeners)
        except Exception as fallback_e:
            _LOGGER.warning("Failed to schedule fallback update: %s", fallback_e)

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

    @property
    def device_name(self) -> str:
        """Return device friendly name."""
        # Get device name from config entry data
        device_name = self.config_entry.data.get(CONF_DEVICE_NAME)
        if device_name:
            return device_name

        # Fallback to "Dyson [serial]" if no device name provided
        return f"Dyson {self.serial_number}"

    def _get_effective_connection_type(self) -> str:
        """Get the effective connection type for this device."""
        # Check if device has its own connection type override
        device_connection_type = self.config_entry.data.get("connection_type")
        if device_connection_type:
            _LOGGER.debug("Using device-specific connection type: %s", device_connection_type)
            return device_connection_type

        # Fall back to account-level connection type
        parent_entry_id = self.config_entry.data.get("parent_entry_id")
        if parent_entry_id:
            # This is a device entry, get connection type from parent account entry
            try:
                account_entries = [
                    entry
                    for entry in self.hass.config_entries.async_entries(DOMAIN)
                    if entry.entry_id == parent_entry_id
                ]

                if account_entries:
                    account_connection_type = account_entries[0].data.get("connection_type", "local_cloud_fallback")
                    _LOGGER.debug("Using account-level connection type: %s", account_connection_type)
                    return account_connection_type
            except Exception as err:
                _LOGGER.warning("Failed to get account connection type: %s", err)

        # Default fallback
        default_type = "local_cloud_fallback"
        _LOGGER.debug("Using default connection type: %s", default_type)
        return default_type

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
            # TODO: Update sticker method to use paho-mqtt directly
            raise UpdateFailed("Sticker discovery method temporarily disabled - use cloud discovery instead")
            # await self._async_setup_sticker_device()
        elif discovery_method == DISCOVERY_MANUAL:
            await self._async_setup_manual_device()
        else:
            raise UpdateFailed(f"Unknown discovery method: {discovery_method}")

    async def _async_setup_cloud_device(self) -> None:
        """Set up device discovered via cloud API."""
        _LOGGER.debug("Setting up cloud device for %s", self.serial_number)

        try:
            cloud_client = await self._authenticate_cloud_client()
            device_info = await self._find_cloud_device(cloud_client)
            self._extract_device_info(device_info)
            mqtt_credentials = await self._extract_mqtt_credentials(cloud_client, device_info)
            cloud_credentials = await self._extract_cloud_credentials(cloud_client, device_info)
            await self._create_cloud_device(device_info, mqtt_credentials, cloud_credentials)

            _LOGGER.info("Successfully set up cloud device %s (%s)", self.serial_number, self._device_category)

        except Exception as err:
            _LOGGER.error("Failed to set up cloud device %s: %s", self.serial_number, err)
            raise UpdateFailed(f"Cloud device setup failed: {err}") from err

    async def _authenticate_cloud_client(self):
        """Authenticate and return a cloud client."""
        from libdyson_rest.async_client import AsyncDysonClient

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
            # Use existing auth token from config flow (in executor to avoid blocking SSL calls)
            def create_client_with_token():
                return AsyncDysonClient(email=username, auth_token=auth_token)

            return await self.hass.async_add_executor_job(create_client_with_token)
        elif username and password:
            # Legacy authentication method (in executor to avoid blocking SSL calls)
            def create_client():
                return AsyncDysonClient(email=username)

            cloud_client = await self.hass.async_add_executor_job(create_client)
            # Authenticate using proper flow
            challenge = await cloud_client.begin_login()
            await cloud_client.complete_login(str(challenge.challenge_id), "", username, password)
            return cloud_client
        else:
            raise UpdateFailed("Missing cloud credentials (auth_token or username/password)")

    async def _find_cloud_device(self, cloud_client):
        """Find our device in the cloud device list."""
        devices = await cloud_client.get_devices()

        for device in devices:
            if device.serial_number == self.serial_number:
                return device

        raise UpdateFailed(f"Device {self.serial_number} not found in cloud account")

    def _extract_device_info(self, device_info) -> None:
        """Extract device category and capabilities from device info."""
        _LOGGER.debug("Device info object: %s", device_info)
        _LOGGER.debug("Device info dir: %s", [attr for attr in dir(device_info) if not attr.startswith("_")])

        self._debug_connected_configuration(device_info)
        self._extract_device_type(device_info)
        self._extract_device_category(device_info)
        self._extract_device_capabilities(device_info)
        self._extract_firmware_version(device_info)

    def _debug_connected_configuration(self, device_info) -> None:
        """Debug connected configuration details."""
        connected_config = getattr(device_info, "connected_configuration", None)
        if connected_config:
            _LOGGER.debug("Connected configuration: %s", connected_config)
            _LOGGER.debug("Connected config type: %s", type(connected_config))
            if hasattr(connected_config, "__dict__"):
                _LOGGER.debug("Connected config attributes: %s", vars(connected_config))
            _LOGGER.debug(
                "Connected config dir: %s", [attr for attr in dir(connected_config) if not attr.startswith("_")]
            )
            self._debug_mqtt_object(connected_config)

    def _debug_mqtt_object(self, connected_config) -> None:
        """Debug MQTT object details."""
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

    def _extract_device_type(self, device_info) -> None:
        """Extract device type from device info."""
        # Extract device type from device_info using both possible field names
        device_type = getattr(device_info, "product_type", None)
        if device_type is None:
            device_type = getattr(device_info, "type", None)

        if device_type is None:
            raise ValueError(f"Device type not available for device {self.serial_number}")

        self._device_type = str(device_type)
        _LOGGER.debug("Extracted device type: %s", self._device_type)

    def _extract_device_category(self, device_info) -> None:
        """Extract device category from config entry or API response."""
        from .device_utils import normalize_device_category

        # Check if device_category was provided in config entry (like manual devices)
        config_device_category = self.config_entry.data.get("device_category")
        if config_device_category:
            # Use device_category from config entry if available (ensures consistency)
            self._device_category = normalize_device_category(config_device_category)
            _LOGGER.debug("Using device category from config entry: %s", self._device_category)
        else:
            # Extract category from API response
            raw_category = getattr(device_info, "category", "unknown")
            self._device_category = normalize_device_category(raw_category)
            _LOGGER.debug("Extracted device category from API: %s", self._device_category)

    def _extract_device_capabilities(self, device_info) -> None:
        """Extract device capabilities from config entry or API response."""
        from .device_utils import normalize_capabilities

        try:
            # Extract capabilities from config entry or API
            config_capabilities = self.config_entry.data.get("capabilities")

            if config_capabilities and len(config_capabilities) > 0:
                # Use capabilities from config entry if non-empty
                self._device_capabilities = normalize_capabilities(config_capabilities)
                _LOGGER.debug(
                    "Using capabilities from config entry for %s: %s", self.serial_number, self._device_capabilities
                )

                # Validate that we got meaningful capabilities
                if not self._device_capabilities:
                    _LOGGER.warning(
                        "Config capabilities for %s resulted in empty list after normalization: %s",
                        self.serial_number,
                        config_capabilities,
                    )
            else:
                # Extract capabilities from API response
                try:
                    api_capabilities = self._extract_capabilities(device_info)
                    self._device_capabilities = normalize_capabilities(api_capabilities)
                    _LOGGER.debug(
                        "Extracted capabilities from API for %s: %s", self.serial_number, self._device_capabilities
                    )

                    # Validate that we got meaningful capabilities from API
                    if not self._device_capabilities:
                        _LOGGER.warning(
                            "API capabilities for %s resulted in empty list after normalization: %s",
                            self.serial_number,
                            api_capabilities,
                        )
                except Exception as api_error:
                    _LOGGER.error("Failed to extract capabilities from API for %s: %s", self.serial_number, api_error)
                    self._device_capabilities = []

        except Exception as e:
            _LOGGER.error("Critical error during capability extraction for %s: %s", self.serial_number, e)
            # Fallback to empty capabilities to prevent integration failure
            self._device_capabilities = []

        # Log final capability state for debugging
        _LOGGER.info("Final capabilities for device %s: %s", self.serial_number, self._device_capabilities)

    def _extract_firmware_version(self, device_info) -> None:
        """Extract firmware version and update information from device info."""
        self._firmware_version = "Unknown"
        self._firmware_auto_update_enabled = False
        # TODO: Temporarily disabled due to bug in libdyson-rest firmware update detection
        # self._firmware_update_available = False

        connected_config = getattr(device_info, "connected_configuration", None)
        if connected_config:
            firmware_obj = getattr(connected_config, "firmware", None)
            if firmware_obj:
                # Debug: Log all firmware object attributes
                _LOGGER.debug("Firmware object: %s", firmware_obj)
                _LOGGER.debug("Firmware object type: %s", type(firmware_obj))
                if hasattr(firmware_obj, "__dict__"):
                    _LOGGER.debug("Firmware object attributes: %s", vars(firmware_obj))
                _LOGGER.debug(
                    "Firmware object dir: %s", [attr for attr in dir(firmware_obj) if not attr.startswith("_")]
                )

                # Extract firmware version
                firmware_version = getattr(firmware_obj, "version", "Unknown")
                if firmware_version and firmware_version != "Unknown":
                    self._firmware_version = firmware_version
                    _LOGGER.debug("Found firmware version: %s", firmware_version)

                # Extract auto-update setting
                auto_update = getattr(firmware_obj, "auto_update_enabled", None)
                if auto_update is not None:
                    self._firmware_auto_update_enabled = bool(auto_update)
                    _LOGGER.debug("Found firmware auto-update enabled: %s", self._firmware_auto_update_enabled)

                # TODO: Temporarily disabled due to bug in libdyson-rest firmware update detection
                # Extract update availability - try multiple possible field names
                # update_available = None
                # possible_update_fields = [
                #     "new_version_available",
                #     "update_available",
                #     "upgrade_available",
                #     "pending_update",
                #     "has_update",
                #     "available_update"
                # ]
                #
                # for field_name in possible_update_fields:
                #     update_available = getattr(firmware_obj, field_name, None)
                #     if update_available is not None:
                #         _LOGGER.debug("Found firmware update field '%s' with value: %s", field_name, update_available)
                #         self._firmware_update_available = bool(update_available)
                #         break
                # else:
                #     _LOGGER.debug("No firmware update availability field found in: %s",
                #                   [attr for attr in dir(firmware_obj) if not attr.startswith("_")])
            else:
                _LOGGER.debug("No firmware object found in connected configuration")
        else:
            _LOGGER.debug("No connected configuration found in device info")

    async def _extract_mqtt_credentials(self, cloud_client, device_info) -> dict:
        """Extract MQTT credentials from device info."""
        mqtt_username = self.serial_number
        mqtt_password = ""

        mqtt_obj = self._get_mqtt_object(device_info)
        if mqtt_obj:
            mqtt_username = self._get_mqtt_username(mqtt_obj)
            mqtt_password = self._get_mqtt_password(cloud_client, mqtt_obj)

        if not mqtt_password:
            _LOGGER.error("MQTT password cannot be empty for device %s", self.serial_number)
            raise UpdateFailed("MQTT password cannot be empty")

        self._log_mqtt_credentials(mqtt_username, mqtt_password)

        return {
            "mqtt_username": mqtt_username,
            "mqtt_password": mqtt_password,
        }

    def _get_mqtt_object(self, device_info):
        """Extract MQTT object from device info."""
        connected_config = getattr(device_info, "connected_configuration", None)
        if connected_config:
            return getattr(connected_config, "mqtt", None)
        return None

    def _get_mqtt_username(self, mqtt_obj) -> str:
        """Extract MQTT username from mqtt object."""
        # Debug: Log all available attributes on the mqtt object
        mqtt_attrs = [attr for attr in dir(mqtt_obj) if not attr.startswith("_")]
        _LOGGER.debug("Available MQTT attributes: %s", mqtt_attrs)

        # Check for alternative username fields
        for username_attr in ["username", "local_username", "broker_username"]:
            alt_username = getattr(mqtt_obj, username_attr, "")
            if alt_username:
                _LOGGER.debug("Found alternative username: mqtt.%s = %s", username_attr, alt_username)
                return alt_username

        return self.serial_number

    def _get_mqtt_password(self, cloud_client, mqtt_obj) -> str:
        """Extract MQTT password from mqtt object."""
        # Try to get the decoded/plain password first
        password = self._get_plain_password(mqtt_obj)
        if password:
            return password

        # If no plain password found, decrypt local_broker_credentials
        return self._decrypt_mqtt_credentials(cloud_client, mqtt_obj)

    def _get_plain_password(self, mqtt_obj) -> str:
        """Try to get plain text MQTT password from mqtt object."""
        for attr in [
            "password",
            "decoded_password",
            "local_password",
            "device_password",
        ]:
            mqtt_password = getattr(mqtt_obj, attr, "")
            if mqtt_password:
                _LOGGER.debug("Found MQTT password using attribute: mqtt.%s (length: %s)", attr, len(mqtt_password))
                return mqtt_password
        return ""

    def _decrypt_mqtt_credentials(self, cloud_client, mqtt_obj) -> str:
        """Decrypt MQTT credentials from local_broker_credentials."""
        encrypted_credentials = getattr(mqtt_obj, "local_broker_credentials", "")
        if not encrypted_credentials:
            return ""

        try:
            # Use libdyson-rest's decrypt method to get local MQTT password
            mqtt_password = cloud_client.decrypt_local_credentials(encrypted_credentials, self.serial_number)
            _LOGGER.debug(
                "Decrypted local MQTT password from local_broker_credentials (length: %s)",
                len(mqtt_password),
            )
            return mqtt_password
        except Exception as e:
            _LOGGER.error("Failed to decrypt local credentials for %s: %s", self.serial_number, e)
            # Fall back to using encrypted credentials directly (likely won't work)
            _LOGGER.debug(
                "Using encrypted local_broker_credentials as fallback (length: %s)",
                len(encrypted_credentials),
            )
            return encrypted_credentials

    def _log_mqtt_credentials(self, mqtt_username: str, mqtt_password: str) -> None:
        """Log MQTT credentials for debugging (partially masked)."""
        _LOGGER.debug(
            "MQTT credentials for device %s - Username: %s, Password: %s...%s (length: %s)",
            self.serial_number,
            mqtt_username,
            mqtt_password[:10] if mqtt_password else "None",
            mqtt_password[-10:] if len(mqtt_password) > 20 else "",
            len(mqtt_password),
        )

    async def _extract_cloud_credentials(self, cloud_client, device_info) -> dict:
        """Extract cloud credentials from device info."""
        cloud_host = None
        cloud_credentials = {}

        try:
            # Check for IoT credentials using separate API call
            _LOGGER.debug("Requesting IoT credentials for device %s", self.serial_number)
            iot_data = await cloud_client.get_iot_credentials(self.serial_number)

            if iot_data:
                # Extract AWS IoT endpoint
                cloud_host = getattr(iot_data, "endpoint", None)
                _LOGGER.debug("Cloud host from iot_data.endpoint: %s", cloud_host)

                # Extract credentials object
                credentials_obj = getattr(iot_data, "iot_credentials", None)
                if credentials_obj:
                    cloud_client_id = str(getattr(credentials_obj, "client_id", ""))
                    cloud_token_key = str(getattr(credentials_obj, "token_key", ""))
                    cloud_token_value = str(getattr(credentials_obj, "token_value", ""))
                    cloud_token_signature = str(getattr(credentials_obj, "token_signature", ""))
                    cloud_custom_authorizer = str(getattr(credentials_obj, "custom_authorizer_name", ""))

                    cloud_credentials = {
                        "client_id": cloud_client_id,
                        "custom_authorizer_name": cloud_custom_authorizer,
                        "token_key": cloud_token_key,
                        "token_value": cloud_token_value,
                        "token_signature": cloud_token_signature,
                    }

                    _LOGGER.debug("Successfully extracted cloud credentials")
                else:
                    _LOGGER.warning("No credentials object found in IoT data")
            else:
                _LOGGER.warning("No IoT data returned from API")

        except Exception as e:
            _LOGGER.error("Failed to retrieve IoT credentials: %s", e)

        return {
            "cloud_host": cloud_host,
            "cloud_credentials": cloud_credentials,
        }

    async def _create_cloud_device(self, device_info, mqtt_credentials, cloud_credentials) -> None:
        """Create and connect to cloud device."""
        device_host = self._get_device_host(device_info)
        mqtt_prefix = self._get_mqtt_prefix(device_info)
        connection_type = self._get_effective_connection_type()

        # Create cloud credential structure for AWS IoT if available
        cloud_credential_data = None
        cloud_host = cloud_credentials.get("cloud_host")
        creds = cloud_credentials.get("cloud_credentials", {})

        if cloud_host and creds.get("client_id") and creds.get("token_value") and creds.get("token_signature"):
            import json

            cloud_credential_data = json.dumps(creds)
            _LOGGER.debug("Created cloud credential data structure for AWS IoT")

        from .device import DysonDevice

        self.device = DysonDevice(
            self.hass,
            self.serial_number,
            device_host,
            mqtt_credentials["mqtt_password"],
            mqtt_prefix,
            self._device_capabilities,
            connection_type,
            cloud_host,
            cloud_credential_data,
        )

        # Set firmware version in the device for proper device info
        if self._firmware_version != "Unknown":
            self.device.set_firmware_version(self._firmware_version)

        # Let DysonDevice handle the connection
        connected = await self.device.connect()
        if not connected:
            raise UpdateFailed(f"Failed to connect to device {self.serial_number}")

        # Register for environmental update notifications
        self.device.add_environmental_callback(self._on_environmental_update)
        # Register for message updates to get real-time state changes
        self.device.add_message_callback(self._on_message_update)

    async def _async_setup_manual_device(self) -> None:
        """Set up device configured manually."""
        try:
            _LOGGER.info("Setting up manual device: %s", self.serial_number)

            # Get configuration from config entry
            serial_number = self.config_entry.data[CONF_SERIAL_NUMBER]
            credential = self.config_entry.data[CONF_CREDENTIAL]
            mqtt_prefix = self.config_entry.data[CONF_MQTT_PREFIX]
            hostname = self.config_entry.data.get(CONF_HOSTNAME, "").strip()
            device_category = self.config_entry.data.get("device_category", ["ec"])
            capabilities = self.config_entry.data.get("capabilities", [])

            # Set device type, category and capabilities from config entry
            from .device_utils import normalize_capabilities, normalize_device_category

            device_type = self.config_entry.data.get("device_type", "438")
            device_category = self.config_entry.data.get("device_category", ["ec"])
            capabilities = self.config_entry.data.get("capabilities", [])

            # Ensure consistent normalization
            self._device_type = str(device_type)
            self._device_category = normalize_device_category(device_category)
            self._device_capabilities = normalize_capabilities(capabilities)

            _LOGGER.debug(
                "Manual device setup - device_type: %s, category: %s, capabilities: %s",
                self._device_type,
                self._device_category,
                self._device_capabilities,
            )

            # Validate that we have required information for manual setup
            if not hostname:
                raise UpdateFailed(f"Manual device setup requires hostname/IP address for device {serial_number}")

            # Get connection type from config entry
            connection_type = self._get_effective_connection_type()

            # For manual setup, we don't have cloud credentials
            self.device = DysonDevice(
                self.hass,
                serial_number,
                hostname,  # Device hostname (required for manual setup)
                credential,  # Local MQTT credential
                mqtt_prefix,  # User-provided MQTT prefix
                self._device_capabilities,
                connection_type,
                None,  # No cloud host for manual setup
                None,  # No cloud credential for manual setup
            )

            # Set unknown firmware version since we don't get it from cloud
            self.device.set_firmware_version("Unknown")

            # Let DysonDevice handle the connection
            connected = await self.device.connect()
            if not connected:
                raise UpdateFailed(f"Failed to connect to manual device {self.serial_number}")

            # Register for environmental update notifications
            self.device.add_environmental_callback(self._on_environmental_update)

            # Register for message updates to get real-time state changes
            self.device.add_message_callback(self._on_message_update)

            _LOGGER.info("Successfully set up manual device %s", self.serial_number)

        except Exception as err:
            _LOGGER.error("Failed to set up manual device %s: %s", self.serial_number, err)
            raise UpdateFailed(f"Manual device setup failed: {err}") from err

    async def _async_setup_sticker_device(self) -> None:
        """Set up device using sticker/WiFi method."""
        # TODO: Update this method to use paho-mqtt directly
        raise UpdateFailed("Sticker discovery method temporarily disabled - use cloud discovery instead")

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data from the device - mainly for connectivity checks."""
        if not self.device:
            raise UpdateFailed("Device not initialized")

        _LOGGER.debug("Checking connectivity for device %s", self.serial_number)

        try:
            # Check if device is still connected, attempt reconnection if needed
            if not self.device.is_connected:
                _LOGGER.warning("Device %s not connected, attempting reconnection", self.serial_number)
                success = await self.device.connect()
                if not success:
                    raise UpdateFailed(f"Failed to reconnect to device {self.serial_number}")
                _LOGGER.info("Successfully reconnected to device %s", self.serial_number)

                # Only request current state after reconnection to get initial state
                try:
                    await self.device.send_command(MQTT_CMD_REQUEST_CURRENT_STATE)
                    _LOGGER.debug("Requested current state after reconnection for %s", self.serial_number)
                except Exception as cmd_err:
                    _LOGGER.warning(
                        "Failed to request current state after reconnection for %s: %s", self.serial_number, cmd_err
                    )

            # Get current device state (from last received MQTT message)
            device_state = await self.device.get_state()
            _LOGGER.debug(
                "Retrieved cached device state for %s with keys: %s",
                self.serial_number,
                list(device_state.keys()) if device_state else "None",
            )

            return device_state

        except UpdateFailed:
            # Re-raise UpdateFailed exceptions
            raise
        except Exception as err:
            _LOGGER.error("Error checking connectivity for device %s: %s", self.serial_number, err)
            raise UpdateFailed(f"Error communicating with device: {err}") from err

    async def _async_handle_faults(self) -> None:
        """Handle device faults by firing events."""
        if not self.device:
            return

        faults = await self.device.get_faults()

        # Only log and fire events for actual faults (not OK statuses)
        for fault in faults:
            # The device.get_faults() method now filters out OK statuses
            _LOGGER.info("Device fault detected for %s: %s", self.serial_number, fault.get("description", fault))

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

    async def async_set_firmware_auto_update(self, enabled: bool) -> bool:
        """Set firmware auto-update setting.

        Note: This function updates the local state immediately for UI responsiveness,
        but the actual API call to change the setting is not yet implemented as the
        libdyson-rest API endpoint for this feature is not documented.
        """
        if self.config_entry.data.get(CONF_DISCOVERY_METHOD) != DISCOVERY_CLOUD:
            _LOGGER.warning("Firmware auto-update setting only available for cloud-discovered devices")
            return False

        _LOGGER.info("Setting firmware auto-update for %s to %s", self.serial_number, enabled)

        # Update local state immediately for UI responsiveness
        old_value = self._firmware_auto_update_enabled
        self._firmware_auto_update_enabled = enabled

        # Notify listeners of the state change
        self.async_update_listeners()

        # TODO: Implement actual API call to Dyson cloud service
        # when the libdyson-rest API endpoint for this feature becomes available
        _LOGGER.debug(
            "Updated firmware auto-update setting for %s from %s to %s (API call not yet implemented)",
            self.serial_number,
            old_value,
            enabled,
        )

        return True

    async def async_check_firmware_update(self) -> bool:
        """Check for available firmware updates using libdyson-rest 0.7.0b1."""
        from libdyson_rest.exceptions import DysonAPIError, DysonAuthError, DysonConnectionError

        if self.config_entry.data.get(CONF_DISCOVERY_METHOD) != DISCOVERY_CLOUD:
            _LOGGER.debug("Firmware update check only available for cloud-discovered devices")
            return False

        try:
            # Create a temporary cloud client for the update check
            cloud_client = await self._authenticate_cloud_client()

            try:
                # Use new libdyson-rest 0.7.0b1 async method
                pending_release = await cloud_client.get_pending_release(self.serial_number)

                if pending_release:
                    self._firmware_latest_version = pending_release.version
                    _LOGGER.info("Firmware update available for %s: %s", self.serial_number, pending_release.version)

                    # Notify listeners of the update
                    self.async_update_listeners()
                    return True
                else:
                    self._firmware_latest_version = self._firmware_version
                    _LOGGER.debug("No firmware update available for %s", self.serial_number)
                    return False
            finally:
                # Ensure client is properly closed
                await cloud_client.close()

        except (DysonAPIError, DysonAuthError, DysonConnectionError) as e:
            # Handle specific Dyson API errors
            _LOGGER.debug("Dyson API error checking firmware update for %s: %s", self.serial_number, e)
            self._firmware_latest_version = self._firmware_version
            return False
        except Exception as e:
            # Handle other unexpected errors
            _LOGGER.debug("Unexpected error checking firmware update for %s: %s", self.serial_number, e)
            self._firmware_latest_version = self._firmware_version
            return False

    async def async_install_firmware_update(self, version: str) -> bool:
        """Install firmware update via MQTT command."""
        if not self.device:
            _LOGGER.error("No device connection available for firmware update")
            return False

        try:
            # Use the extracted device type for the firmware URL
            device_type = self._device_type

            # Construct firmware URL following the pattern from MQTT trace
            firmware_url = f"http://ota-firmware.cp.dyson.com/{device_type}/M__SC04.WF02/{version}/manifest.bin"

            _LOGGER.info("Using device type %s for firmware URL: %s", device_type, firmware_url)

            # Prepare MQTT command with current timestamp
            from datetime import datetime

            command_data = {
                "msg": "SOFTWARE-UPGRADE",
                "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z",
                "version": version,
                "url": firmware_url,
            }

            _LOGGER.info("Initiating firmware update for %s to version %s", self.serial_number, version)

            # Mark update as in progress
            self._firmware_update_in_progress = True
            self.async_update_listeners()

            # Send the command using device's send_command method
            # send_command returns None on success and raises on failure
            await self.device.send_command("SOFTWARE-UPGRADE", command_data)

            _LOGGER.info("Firmware update command sent successfully for %s", self.serial_number)
            # Note: Update progress tracking would require monitoring device state
            # but MQTT doesn't provide progress updates based on the trace
            return True

        except Exception as e:
            _LOGGER.error("Error installing firmware update for %s: %s", self.serial_number, e)
            self._firmware_update_in_progress = False
            self.async_update_listeners()
            return False

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and cleanup connections."""
        _LOGGER.debug("Shutting down coordinator for device %s", self.serial_number)

        if self.device:
            # Remove environmental callback before disconnecting
            self.device.remove_environmental_callback(self._on_environmental_update)
            # Remove message callback before disconnecting
            self.device.remove_message_callback(self._on_message_update)
            await self.device.disconnect()
            self.device = None

    def _extract_capabilities(self, device_info: Any) -> List[str]:
        """Extract device capabilities from cloud device info."""
        capabilities: list[str] = []

        # Get capabilities from device info if available
        if hasattr(device_info, "capabilities"):
            capabilities = device_info.capabilities or []
        elif hasattr(device_info, "connected_configuration"):
            # Try nested structure: device_info.connected_configuration.firmware.capabilities
            connected_config = device_info.connected_configuration
            if connected_config and hasattr(connected_config, "firmware"):
                firmware = connected_config.firmware
                if firmware and hasattr(firmware, "capabilities"):
                    capabilities = firmware.capabilities or []

        # Capabilities should come from the API response, not from static product type mapping
        # If the API doesn't provide capabilities, they should be configured by the user

        _LOGGER.debug("Raw extracted capabilities from device_info: %s", capabilities)
        _LOGGER.debug("Capability types: %s", [type(cap).__name__ for cap in capabilities])

        # Remove duplicates and return
        final_capabilities = list(set(capabilities))
        _LOGGER.debug("Final capabilities after deduplication: %s", final_capabilities)
        return final_capabilities

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


class DysonCloudAccountCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Coordinator to manage cloud account and device discovery."""

    def __init__(self, hass: HomeAssistant, config_entry) -> None:  # type: ignore
        """Initialize the cloud account coordinator."""
        self.config_entry = config_entry
        self._email = config_entry.data.get("email")
        self._auth_token = config_entry.data.get("auth_token")
        self._last_known_devices = set()

        # Get polling settings with backward-compatible defaults
        poll_for_devices = config_entry.data.get(CONF_POLL_FOR_DEVICES, DEFAULT_POLL_FOR_DEVICES)

        # Only set up polling if enabled
        update_interval = None
        if poll_for_devices:
            update_interval = timedelta(seconds=DEFAULT_CLOUD_POLLING_INTERVAL)
            _LOGGER.info(
                "Cloud device polling enabled for %s, interval: %d seconds",
                self._email,
                DEFAULT_CLOUD_POLLING_INTERVAL,
            )
        else:
            _LOGGER.info("Cloud device polling disabled for %s", self._email)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_cloud_account_{self._email}",
            update_interval=update_interval,
        )

        # Initialize known devices from config
        for device_info in config_entry.data.get("devices", []):
            self._last_known_devices.add(device_info["serial_number"])

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data by checking for new devices in the cloud account."""
        _LOGGER.info("Cloud coordinator update triggered for account: %s", self._email)

        if not self.config_entry.data.get(CONF_POLL_FOR_DEVICES, DEFAULT_POLL_FOR_DEVICES):
            # Polling is disabled, return empty data
            _LOGGER.debug("Device polling disabled for account %s", self._email)
            return {"devices": []}

        try:
            devices = await self._fetch_cloud_devices()
            if not devices:
                return {"devices": []}

            updated_devices = self._build_device_list(devices)
            await self._process_device_changes(devices, updated_devices)

            return {"devices": [device_info for device_info in updated_devices if device_info]}

        except Exception as err:
            _LOGGER.error("Error checking for new devices in cloud account %s: %s", self._email, err)
            raise UpdateFailed(f"Failed to check for new devices: {err}") from err

    async def _fetch_cloud_devices(self):
        """Fetch devices from cloud API."""
        _LOGGER.info("Checking for new devices in Dyson cloud account: %s", self._email)

        # Initialize libdyson-rest client
        from libdyson_rest.async_client import AsyncDysonClient

        if not self._auth_token:
            _LOGGER.warning("No auth token available for cloud account %s", self._email)
            return []

        # Create client with auth token
        async with AsyncDysonClient(auth_token=self._auth_token) as client:
            # Get devices from cloud API
            devices = await client.get_devices()

            if not devices:
                _LOGGER.debug("No devices found in cloud account %s", self._email)
                return []

            return devices

    def _build_device_list(self, devices):
        """Build device info list from cloud devices."""
        updated_devices = []
        for device in devices:
            device_info = {
                "serial_number": device.serial_number,
                "name": getattr(device, "name", f"Dyson {device.serial_number}"),
                "product_type": getattr(device, "product_type", "unknown"),
                "category": getattr(device, "category", "unknown"),
            }
            updated_devices.append(device_info)
        return updated_devices

    async def _process_device_changes(self, devices, updated_devices):
        """Process new and changed devices."""
        # Check for new devices
        current_devices = {device.serial_number for device in devices}
        new_devices = current_devices - self._last_known_devices

        if new_devices:
            await self._handle_new_devices(devices, new_devices, updated_devices)
        else:
            _LOGGER.debug("No new devices found in cloud account %s", self._email)

        return new_devices

    async def _handle_new_devices(self, devices, new_devices, updated_devices):
        """Handle new devices discovered in cloud account."""
        _LOGGER.info(
            "Found %d new device(s) in cloud account %s: %s",
            len(new_devices),
            self._email,
            list(new_devices),
        )

        # Get auto_add setting
        auto_add_devices = self.config_entry.data.get(CONF_AUTO_ADD_DEVICES, DEFAULT_AUTO_ADD_DEVICES)

        # Update the account config entry with new devices
        updated_data = dict(self.config_entry.data)
        updated_data["devices"] = updated_devices
        self.hass.config_entries.async_update_entry(self.config_entry, data=updated_data)

        # Create individual device entries for new devices if auto-add is enabled
        if auto_add_devices:
            for device in devices:
                if device.serial_number in new_devices:
                    await self._create_device_entry(device)
        else:
            # Create discovery flows for manual device addition
            for device in devices:
                if device.serial_number in new_devices:
                    await self._create_discovery_flow(device)
            _LOGGER.info("Auto-add disabled, %d new devices will be available for manual setup", len(new_devices))

        # Update our known devices set
        self._last_known_devices = {device.serial_number for device in devices}

    async def _create_device_entry(self, device) -> None:
        """Create a new device config entry."""
        from .device_utils import create_cloud_device_config

        device_serial = device.serial_number
        device_name = getattr(device, "name", f"Dyson {device_serial}")

        # Check if device already exists
        existing_entries = [
            entry
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if (entry.data.get(CONF_SERIAL_NUMBER) == device_serial and entry.entry_id != self.config_entry.entry_id)
        ]

        if existing_entries:
            _LOGGER.debug("Device %s already has a config entry, skipping", device_serial)
            return

        device_info = {
            "serial_number": device_serial,
            "name": device_name,
            "product_type": getattr(device, "product_type", "unknown"),
            "category": getattr(device, "category", "unknown"),
        }

        device_data = create_cloud_device_config(
            serial_number=device_serial,
            username=self._email,
            device_info=device_info,
            auth_token=self._auth_token,
            parent_entry_id=self.config_entry.entry_id,
        )

        _LOGGER.info("Auto-creating config entry for newly discovered device: %s", device_name)

        # Create the device entry
        result = await self.hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "device_auto_create"},
            data=device_data,
        )
        _LOGGER.debug("Device entry creation result for %s: %s", device_serial, result)

    async def _create_discovery_flow(self, device) -> None:
        """Create a native Home Assistant discovery for manual device confirmation."""
        device_serial = device.serial_number
        device_name = getattr(device, "name", f"Dyson {device_serial}")

        # Check if device already exists
        existing_entries = [
            entry
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if (entry.data.get(CONF_SERIAL_NUMBER) == device_serial and entry.entry_id != self.config_entry.entry_id)
        ]

        if existing_entries:
            _LOGGER.debug("Device %s already has a config entry, skipping discovery", device_serial)
            return

        # Check if discovery already exists for this device
        existing_flows = [
            flow
            for flow in self.hass.config_entries.flow.async_progress()
            if (
                flow["handler"] == DOMAIN
                and flow.get("context", {}).get("source") == "discovery"
                and flow.get("context", {}).get("unique_id") == device_serial
            )
        ]

        if existing_flows:
            _LOGGER.debug("Discovery flow already exists for device %s", device_serial)
            return

        _LOGGER.info("Creating discovery for device: %s (%s)", device_name, device_serial)

        # Create a native Home Assistant discovery
        try:
            result = await self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={
                        "source": "discovery",
                        "unique_id": device_serial,
                    },
                    data={
                        "serial_number": device_serial,
                        "name": device_name,
                        "product_type": getattr(device, "product_type", "unknown"),
                        "auth_token": self._auth_token,
                        "email": self._email,
                        "parent_entry_id": self.config_entry.entry_id,
                    },
                )
            )
            _LOGGER.info("Discovery flow created successfully for %s: %s", device_name, result)
        except Exception as e:
            _LOGGER.error("Failed to create discovery flow for %s: %s", device_name, e)
