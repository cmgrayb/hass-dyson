"""Config flow for Dyson integration."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    AVAILABLE_CAPABILITIES,
    AVAILABLE_DEVICE_CATEGORIES,
    CONF_AUTO_ADD_DEVICES,
    CONF_CREDENTIAL,
    CONF_HOSTNAME,
    CONF_MQTT_PREFIX,
    CONF_POLL_FOR_DEVICES,
    CONF_SERIAL_NUMBER,
    DEFAULT_AUTO_ADD_DEVICES,
    DEFAULT_POLL_FOR_DEVICES,
    DOMAIN,
    MDNS_SERVICE_DYSON,
)

_LOGGER = logging.getLogger(__name__)

# Connection type display names for UI
CONNECTION_TYPE_NAMES = {
    "local_only": "Local Only",
    "local_cloud_fallback": "Local with Cloud Fallback",
    "cloud_local_fallback": "Cloud with Local Fallback",
    "cloud_only": "Cloud Only",
}


def _get_connection_type_display_name(connection_type: str) -> str:
    """Get user-friendly display name for connection type."""
    return CONNECTION_TYPE_NAMES.get(connection_type, connection_type)


async def _discover_device_via_mdns(hass, serial_number: str, timeout: int = 10) -> str | None:
    """Discover Dyson device via mDNS using Home Assistant's shared zeroconf instance.

    Args:
        hass: Home Assistant instance
        serial_number: Device serial number to search for
        timeout: Discovery timeout in seconds

    Returns:
        IP address if found, None otherwise
    """
    from homeassistant.components import zeroconf

    try:
        # Get Home Assistant's shared zeroconf instance
        zeroconf_instance = await zeroconf.async_get_instance(hass)
        if zeroconf_instance is None:
            _LOGGER.warning("Unable to get shared zeroconf instance")
            return None

        def _find_device():
            """Synchronous mDNS discovery function."""
            try:
                # Look for Dyson services
                services = zeroconf_instance.get_service_info(
                    MDNS_SERVICE_DYSON, f"{serial_number}.{MDNS_SERVICE_DYSON}"
                )
                if services and services.addresses:
                    # Return the first available IP address
                    return socket.inet_ntoa(services.addresses[0])

                # Also try the common pattern {serial}.local
                try:
                    hostname = f"{serial_number}.local"
                    ip = socket.gethostbyname(hostname)
                    return ip
                except socket.gaierror:
                    pass

            except Exception as e:
                _LOGGER.debug("mDNS discovery error for %s: %s", serial_number, e)
                return None

        # Run discovery in executor to avoid blocking
        try:
            return await asyncio.wait_for(asyncio.get_event_loop().run_in_executor(None, _find_device), timeout=timeout)
        except asyncio.TimeoutError:
            _LOGGER.debug("mDNS discovery timeout for device %s", serial_number)
            return None
    except Exception as e:
        _LOGGER.debug("Error getting zeroconf instance: %s", e)
        return None


class DysonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dyson."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        _LOGGER.info("DysonConfigFlow.__init__ called")
        super().__init__()
        self._email: str | None = None
        self._password: str | None = None
        self._cloud_client = None  # type: ignore
        self._challenge_id: str | None = None
        self._discovered_devices = None  # type: ignore
        self._connection_type: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step - setup method selection."""
        try:
            _LOGGER.info("Starting async_step_user - setup method selection with user_input: %s", user_input)
            errors = {}

            if user_input is not None:
                setup_method = user_input.get("setup_method")
                _LOGGER.info("User selected setup method: %s", setup_method)

                if setup_method == "cloud_account":
                    return await self.async_step_cloud_account()
                elif setup_method == "manual_device":
                    return await self.async_step_manual_device()
                else:
                    _LOGGER.error("Invalid setup method selected: %s", setup_method)
                    errors["base"] = "invalid_setup_method"

            # Show the setup method selection form
            _LOGGER.info("Showing setup method selection form")
            try:
                data_schema = vol.Schema(
                    {
                        vol.Required("setup_method"): vol.In(
                            {
                                "cloud_account": "Dyson Cloud Account (Recommended)",
                                "manual_device": "Manual Device Setup",
                            }
                        ),
                    }
                )
                _LOGGER.info("Setup method selection form schema created successfully")

                return self.async_show_form(
                    step_id="user",
                    data_schema=data_schema,
                    errors=errors,
                )
            except Exception as e:
                _LOGGER.exception("Error creating setup method selection form: %s", e)
                raise
        except Exception as e:
            _LOGGER.exception("Top-level exception in async_step_user: %s", e)
            raise

    async def async_step_cloud_account(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the cloud account authentication step."""
        try:
            _LOGGER.info(
                "Starting async_step_cloud_account - Dyson account authentication with user_input: %s", user_input
            )
            errors = {}

            if user_input is not None:
                try:
                    # Store email and password for verification step
                    self._email = user_input.get("email", "")
                    self._password = user_input.get("password", "")

                    _LOGGER.info("Attempting to authenticate with Dyson API using email: %s", self._email)

                    # Initialize libdyson-rest client with credentials
                    from libdyson_rest import DysonClient

                    self._cloud_client = DysonClient(email=self._email, password=self._password)

                    # Begin the login process to get challenge_id - this triggers the OTP email
                    if self._cloud_client is None:
                        raise ValueError("Failed to initialize Dyson client")
                    challenge = await self.hass.async_add_executor_job(lambda: self._cloud_client.begin_login())

                    # Validate and store challenge ID for verification step
                    if challenge is None or challenge.challenge_id is None:
                        _LOGGER.error("No challenge received from Dyson API")
                        errors["base"] = "cannot_connect"
                    else:
                        self._challenge_id = str(challenge.challenge_id)
                        _LOGGER.info("Successfully initiated login process, challenge ID received")
                        return await self.async_step_verify()

                except Exception as e:
                    _LOGGER.exception("Error during Dyson authentication: %s", e)
                    errors["base"] = "auth_failed"

            # Show the Dyson account authentication form
            _LOGGER.info("Showing Dyson account authentication form")
            try:
                data_schema = vol.Schema(
                    {
                        vol.Required("email"): str,
                        vol.Required("password"): str,
                    }
                )
                _LOGGER.info("Authentication form schema created successfully")

                return self.async_show_form(
                    step_id="cloud_account",
                    data_schema=data_schema,
                    errors=errors,
                    description_placeholders={"docs_url": "https://www.dyson.com/support/account"},
                )
            except Exception as e:
                _LOGGER.exception("Error creating authentication form: %s", e)
                raise
        except Exception as e:
            _LOGGER.exception("Top-level exception in async_step_cloud_account: %s", e)
            raise

    async def async_step_manual_device(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle manual device setup."""
        try:
            _LOGGER.info("Starting async_step_manual_device with user_input: %s", user_input)
            errors = {}

            if user_input is not None:
                errors = await self._process_manual_device_input(user_input)
                if not errors:
                    return await self._create_manual_device_entry(user_input)

            # Show the manual device setup form
            return self._show_manual_device_form(errors)

        except Exception as e:
            _LOGGER.exception("Top-level exception in async_step_manual_device: %s", e)
            raise

    async def _process_manual_device_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Process and validate manual device input."""
        errors = {}
        try:
            # Validate required fields
            required_fields = {
                CONF_SERIAL_NUMBER: "required",
                CONF_CREDENTIAL: "required",
                CONF_MQTT_PREFIX: "required",
            }

            for field, error_msg in required_fields.items():
                if not user_input.get(field, "").strip():
                    errors[field] = error_msg

            if not errors:
                serial_number = user_input.get(CONF_SERIAL_NUMBER, "").strip()
                # Check if device already exists
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()

        except Exception as e:
            _LOGGER.exception("Error during manual device setup: %s", e)
            errors["base"] = "manual_setup_failed"

        return errors

    async def _create_manual_device_entry(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Create the manual device entry."""
        # Get device information from user input
        serial_number = user_input.get(CONF_SERIAL_NUMBER, "").strip()
        credential = user_input.get(CONF_CREDENTIAL, "").strip()
        mqtt_prefix = user_input.get(CONF_MQTT_PREFIX, "").strip()
        hostname = user_input.get(CONF_HOSTNAME, "").strip()
        device_name = user_input.get("device_name", f"Dyson {serial_number}").strip()
        device_category = user_input.get("device_category", ["ec"])  # Default to Environment Cleaner list
        capabilities = user_input.get("capabilities", [])

        _LOGGER.info("Manual setup for device: %s", serial_number)

        # Determine hostname: use provided value or discover via mDNS
        hostname = await self._resolve_device_hostname(serial_number, hostname)

        # Create the device entry with manual discovery method
        from .device_utils import create_manual_device_config

        config_data = create_manual_device_config(
            serial_number=serial_number,
            credential=credential,
            mqtt_prefix=mqtt_prefix,
            device_name=device_name,
            hostname=hostname,
            device_category=device_category,
            capabilities=capabilities,
        )

        _LOGGER.info("Creating manual device config entry for: %s", device_name)
        return self.async_create_entry(
            title=device_name,
            data=config_data,
        )

    async def _resolve_device_hostname(self, serial_number: str, hostname: str) -> str:
        """Resolve device hostname either from input or via mDNS discovery."""
        if hostname:
            _LOGGER.info("Using provided hostname/IP for device %s: %s", serial_number, hostname)
            return hostname

        # Try to discover device via mDNS
        _LOGGER.info("No hostname provided, attempting mDNS discovery for device %s", serial_number)
        discovered_hostname = await _discover_device_via_mdns(self.hass, serial_number)

        if discovered_hostname:
            _LOGGER.info("Found device %s at IP: %s", serial_number, discovered_hostname)
            return discovered_hostname
        else:
            _LOGGER.warning("Could not discover device %s via mDNS, will use serial.local", serial_number)
            return f"{serial_number}.local"

    def _show_manual_device_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        """Show the manual device setup form."""
        _LOGGER.info("Showing manual device setup form")
        try:
            data_schema = vol.Schema(
                {
                    vol.Required(CONF_SERIAL_NUMBER): str,
                    vol.Required(CONF_CREDENTIAL): str,
                    vol.Required(CONF_MQTT_PREFIX): str,
                    vol.Optional(CONF_HOSTNAME): str,
                    vol.Optional("device_name"): str,
                    vol.Optional("device_category", default=["ec"]): cv.multi_select(AVAILABLE_DEVICE_CATEGORIES),
                    vol.Optional("capabilities", default=[]): cv.multi_select(AVAILABLE_CAPABILITIES),
                }
            )
            _LOGGER.info("Manual device setup form schema created successfully")

            return self.async_show_form(
                step_id="manual_device",
                data_schema=data_schema,
                errors=errors,
                description_placeholders={"discovery_info": "Leave IP Address blank for automatic discovery via mDNS"},
            )
        except Exception as e:
            _LOGGER.exception("Error creating manual device setup form: %s", e)
            raise

    async def async_step_verify(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the verification code step."""
        try:
            _LOGGER.info("Starting async_step_verify with user_input: %s", user_input)
            errors = {}

            if user_input is not None:
                try:
                    verification_code = user_input.get("verification_code", "")
                    _LOGGER.info("Received verification code: %s", verification_code)

                    if not self._cloud_client or not self._challenge_id:
                        _LOGGER.error("Missing cloud client or challenge ID for verification")
                        errors["base"] = "verification_failed"
                    else:
                        # Complete authentication with libdyson-rest using challenge_id and verification code
                        _LOGGER.debug(
                            "Attempting complete_login with challenge_id=%s, verification_code=%s",
                            self._challenge_id,
                            verification_code,
                        )

                        try:
                            await self.hass.async_add_executor_job(
                                lambda: self._cloud_client.complete_login(self._challenge_id, verification_code)
                            )
                            _LOGGER.info("Successfully authenticated with Dyson API, got auth token")
                            return await self.async_step_connection()
                        except Exception as complete_error:
                            _LOGGER.error(
                                "complete_login failed: %s (Type: %s)", complete_error, type(complete_error).__name__
                            )
                            # Check if it's specifically an auth error vs other errors
                            if "401" in str(complete_error) or "Unauthorized" in str(complete_error):
                                _LOGGER.error("Authentication failed - invalid credentials or expired challenge")
                                errors["base"] = "invalid_auth"
                            else:
                                errors["base"] = "verification_failed"

                except Exception as e:
                    _LOGGER.exception("Error during verification: %s", e)
                    errors["base"] = "verification_failed"

            # Show the verification code form
            _LOGGER.info("Showing verification code form")
            try:
                data_schema = vol.Schema(
                    {
                        vol.Required("verification_code"): str,
                    }
                )
                _LOGGER.info("Verification form schema created successfully")

                return self.async_show_form(
                    step_id="verify",
                    data_schema=data_schema,
                    errors=errors,
                    description_placeholders={"email": getattr(self, "_email", "your email")},
                )
            except Exception as e:
                _LOGGER.exception("Error creating verification form: %s", e)
                raise
        except Exception as e:
            _LOGGER.exception("Top-level exception in async_step_verify: %s", e)
            raise

    async def async_step_connection(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle connection preferences and device selection."""
        try:
            _LOGGER.info("Starting async_step_connection with user_input: %s", user_input)
            errors = {}

            if user_input is not None:
                try:
                    connection_type = user_input.get("connection_type", "local_cloud_fallback")
                    _LOGGER.info("Selected connection type: %s", connection_type)

                    if not self._cloud_client:
                        _LOGGER.error("Missing cloud client for device discovery")
                        errors["base"] = "connection_failed"
                    else:
                        # Discover devices using libdyson-rest
                        _LOGGER.info("Discovering devices from Dyson API")
                        try:
                            devices = await self.hass.async_add_executor_job(self._cloud_client.get_devices)
                        except Exception as device_error:
                            _LOGGER.error("Failed to retrieve devices from Dyson API: %s", device_error)
                            if "Missing required field: productType" in str(device_error):
                                _LOGGER.error(
                                    "Cloud API response missing productType field - this is a known issue with libdyson-rest v0.5.0"
                                )
                                errors["base"] = "api_format_changed"
                            elif "JSONValidationError" in str(device_error):
                                _LOGGER.error("Cloud API response format validation failed: %s", device_error)
                                errors["base"] = "api_validation_failed"
                            else:
                                errors["base"] = "cloud_api_error"
                            devices = None

                        if not devices:
                            if "base" not in errors:  # Only set this if we don't already have a more specific error
                                _LOGGER.warning("No devices found in Dyson account")
                                errors["base"] = "no_devices"
                        else:
                            _LOGGER.info("Found %d devices in Dyson account", len(devices))

                            # Store devices and connection type for next step
                            self._discovered_devices = devices
                            self._connection_type = connection_type

                            return await self.async_step_cloud_preferences()

                except Exception as e:
                    _LOGGER.exception("Error processing connection preferences: %s", e)
                    errors["base"] = "connection_failed"

            # Show the connection preferences form
            _LOGGER.info("Showing connection preferences form")
            try:
                data_schema = vol.Schema(
                    {
                        vol.Required("connection_type", default="local_cloud_fallback"): vol.In(
                            {
                                "local_only": "Local Only (Maximum Privacy, No Internet Required)",
                                "local_cloud_fallback": "Local with Cloud Fallback (Recommended)",
                                "cloud_local_fallback": "Cloud with Local Fallback (More Reliable)",
                                "cloud_only": "Cloud Only (For Networks Without mDNS/Zeroconf)",
                            }
                        ),
                    }
                )
                _LOGGER.info("Connection preferences form schema created successfully")

                return self.async_show_form(
                    step_id="connection",
                    data_schema=data_schema,
                    errors=errors,
                )
            except Exception as e:
                _LOGGER.exception("Error creating connection preferences form: %s", e)
                raise
        except Exception as e:
            _LOGGER.exception("Top-level exception in async_step_connection: %s", e)
            raise

    async def async_step_cloud_preferences(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle cloud account preferences configuration."""
        try:
            _LOGGER.info("Starting async_step_cloud_preferences with user_input: %s", user_input)
            errors = {}

            if user_input is not None:
                errors = await self._process_cloud_preferences_input(user_input)
                if not errors:
                    return await self._create_cloud_account_entry(user_input)

            # Show the cloud preferences form
            return self._show_cloud_preferences_form(errors)

        except Exception as e:
            _LOGGER.exception("Top-level exception in async_step_cloud_preferences: %s", e)
            raise

    async def _process_cloud_preferences_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Process and validate cloud preferences input."""
        errors = {}
        try:
            poll_for_devices = user_input.get(CONF_POLL_FOR_DEVICES, DEFAULT_POLL_FOR_DEVICES)
            auto_add_devices = user_input.get(CONF_AUTO_ADD_DEVICES, DEFAULT_AUTO_ADD_DEVICES)

            _LOGGER.info(
                "Cloud preferences: poll_for_devices=%s, auto_add_devices=%s",
                poll_for_devices,
                auto_add_devices,
            )

            if not self._cloud_client or not self._discovered_devices:
                _LOGGER.error("Missing cloud client or discovered devices")
                errors["base"] = "preferences_failed"

        except Exception as e:
            _LOGGER.exception("Error processing cloud preferences: %s", e)
            errors["base"] = "preferences_failed"

        return errors

    async def _create_cloud_account_entry(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Create the cloud account config entry."""
        poll_for_devices = user_input.get(CONF_POLL_FOR_DEVICES, DEFAULT_POLL_FOR_DEVICES)
        auto_add_devices = user_input.get(CONF_AUTO_ADD_DEVICES, DEFAULT_AUTO_ADD_DEVICES)

        # Set unique ID based on email to prevent duplicate accounts
        if self._email:
            await self.async_set_unique_id(self._email.lower())
            self._abort_if_unique_id_configured()

        # Create device list from discovered devices
        device_list: list[dict[str, Any]] = []
        if self._discovered_devices is not None:
            for device in self._discovered_devices:
                device_info = {
                    "serial_number": device.serial_number,
                    "name": getattr(device, "name", f"Dyson {device.serial_number}"),
                    "product_type": getattr(device, "product_type", "unknown"),
                    "category": getattr(device, "category", "unknown"),
                }
                device_list.append(device_info)

        return self.async_create_entry(
            title=f"Dyson Account ({self._email})",
            data={
                "email": self._email,
                "connection_type": self._connection_type,
                "devices": device_list,
                "auth_token": getattr(self._cloud_client, "auth_token", None),
                CONF_POLL_FOR_DEVICES: poll_for_devices,
                CONF_AUTO_ADD_DEVICES: auto_add_devices,
            },
        )

    def _show_cloud_preferences_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        """Show the cloud preferences form."""
        _LOGGER.info("Showing cloud preferences form")
        try:
            data_schema = vol.Schema(
                {
                    vol.Required(CONF_POLL_FOR_DEVICES, default=DEFAULT_POLL_FOR_DEVICES): bool,
                    vol.Required(CONF_AUTO_ADD_DEVICES, default=DEFAULT_AUTO_ADD_DEVICES): bool,
                }
            )
            _LOGGER.info("Cloud preferences form schema created successfully")

            device_count = len(self._discovered_devices) if self._discovered_devices else 0

            return self.async_show_form(
                step_id="cloud_preferences",
                data_schema=data_schema,
                errors=errors,
                description_placeholders={
                    "device_count": str(device_count),
                    "email": self._email or "your account",
                },
            )
        except Exception as e:
            _LOGGER.exception("Error creating cloud preferences form: %s", e)
            raise

    async def async_step_discovery(self, discovery_info: dict[str, Any]) -> ConfigFlowResult:
        """Handle discovery of a Dyson device from cloud account."""
        _LOGGER.info("Discovery step triggered for device: %s", discovery_info)

        # Extract device information
        device_serial = discovery_info.get("serial_number")
        device_name = discovery_info.get("name", f"Dyson {device_serial}")

        if not device_serial:
            _LOGGER.error("No serial number in discovery info: %s", discovery_info)
            return self.async_abort(reason="invalid_discovery_info")

        _LOGGER.info("Processing discovery for device %s (%s)", device_name, device_serial)

        # Set unique_id to prevent duplicate discoveries
        await self.async_set_unique_id(device_serial)
        self._abort_if_unique_id_configured()

        # Store discovery info for later use
        self.init_data = discovery_info
        _LOGGER.debug("Stored discovery info: %s", discovery_info)

        # Update context with device name for discovery card subtitle
        self.context["title_placeholders"] = {"name": device_name}

        # Get better display name for device type
        from .const import AVAILABLE_DEVICE_CATEGORIES

        category = discovery_info.get("category", "unknown")
        product_type = discovery_info.get("product_type", "unknown")

        # Use category display name if available, otherwise use product_type
        if category in AVAILABLE_DEVICE_CATEGORIES:
            device_type_display = AVAILABLE_DEVICE_CATEGORIES[category]
        elif product_type != "unknown":
            device_type_display = product_type
        else:
            device_type_display = "Dyson Device"

        # Show confirmation dialog to user with device name in title
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "device_name": device_name,
                "device_serial": device_serial,
                "product_type": device_type_display,
            },
        )

    async def async_step_discovery_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle user confirmation of discovered device."""
        if user_input is None:
            # Get device info for placeholders
            discovery_info = self.init_data
            if not discovery_info:
                _LOGGER.error("No discovery info available for form display")
                return self.async_abort(reason="no_discovery_info")

            device_serial = discovery_info["serial_number"]
            device_name = discovery_info.get("name", f"Dyson {device_serial}")

            # Get better display name for device type
            from .const import AVAILABLE_DEVICE_CATEGORIES

            category = discovery_info.get("category", "unknown")
            product_type = discovery_info.get("product_type", "unknown")

            # Use category display name if available, otherwise use product_type
            if category in AVAILABLE_DEVICE_CATEGORIES:
                device_type_display = AVAILABLE_DEVICE_CATEGORIES[category]
            elif product_type != "unknown":
                device_type_display = product_type
            else:
                device_type_display = "Dyson Device"

            # Show confirmation form with device info placeholders
            return self.async_show_form(
                step_id="discovery_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required("confirm", default=True): bool,
                    }
                ),
                description_placeholders={
                    "device_name": device_name,
                    "device_serial": device_serial,
                    "product_type": device_type_display,
                },
            )

        if not user_input.get("confirm", False):
            _LOGGER.info("User declined to add discovered device")
            return self.async_abort(reason="user_declined")

        # User confirmed, create the device entry
        discovery_info = self.init_data
        if not discovery_info:
            _LOGGER.error("No discovery info available for device creation")
            return self.async_abort(reason="no_discovery_info")

        device_serial = discovery_info["serial_number"]
        device_name = discovery_info.get("name", f"Dyson {device_serial}")

        _LOGGER.info("User confirmed device addition: %s (%s)", device_name, device_serial)

        # Create proper device config using the same method as auto-add
        from .device_utils import create_cloud_device_config

        device_info = {
            "serial_number": device_serial,
            "name": device_name,
            "product_type": discovery_info.get("product_type", "unknown"),
        }

        config_data = create_cloud_device_config(
            serial_number=device_serial,
            username=discovery_info["email"],
            device_info=device_info,
            auth_token=discovery_info["auth_token"],
            parent_entry_id=discovery_info["parent_entry_id"],
        )

        _LOGGER.info("Creating config entry for discovered device: %s", device_name)
        return self.async_create_entry(
            title=device_name,
            data=config_data,
        )

    async def async_step_device_auto_create(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle automatic device entry creation from account setup."""
        _LOGGER.info("Device auto-create flow started with data: %s", user_input)

        if user_input is None:
            _LOGGER.error("Device auto-create called with no user_input")
            return self.async_abort(reason="no_device_data")

        device_serial = user_input.get(CONF_SERIAL_NUMBER)
        device_name = user_input.get("device_name", f"Dyson {device_serial}")

        _LOGGER.info("Creating device config entry for serial: %s, name: %s", device_serial, device_name)

        # Check if device already exists
        await self.async_set_unique_id(device_serial)
        self._abort_if_unique_id_configured()

        # Create the device entry
        _LOGGER.info("Creating config entry with title: %s", device_name)
        return self.async_create_entry(
            title=device_name,
            data=user_input,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return DysonOptionsFlow(config_entry)


class DysonOptionsFlow(config_entries.OptionsFlow):
    """Dyson config flow options handler."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the Dyson devices or individual device."""
        # Check if this is an account entry (has multiple devices) or individual device entry
        if "devices" in self.config_entry.data and self.config_entry.data.get("devices"):
            # This is an account-level entry - show account management
            return await self.async_step_manage_devices()
        else:
            # This is an individual device entry - show device-specific options
            return await self.async_step_device_options()

    async def async_step_manage_devices(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the device management menu."""
        if user_input is not None:
            action = user_input.get("action", "")
            if action == "reload_all":
                return await self.async_step_reload_all()
            elif action == "reconfigure_connection":
                return await self.async_step_reconfigure_connection()
            elif action == "cloud_preferences":
                return await self.async_step_manage_cloud_preferences()

        # Get current devices from config entry
        devices = self.config_entry.data.get("devices", [])

        # Get child device entries
        child_entries = [
            entry
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data.get("parent_entry_id") == self.config_entry.entry_id
        ]

        # Build actions for account-level operations only
        action_options = {
            "reload_all": "🔄 Reload All Devices",
            "reconfigure_connection": "⚙️ Reconfigure Default Connection Settings",
            "cloud_preferences": "☁️ Configure Cloud Account Settings",
        }

        # Show device status for reference (but no individual actions since devices have native controls)
        device_status_info = []
        for device in devices:
            serial = device["serial_number"]
            name = device.get("name", f"Dyson {serial}")

            # Check if device has active config entry
            device_entry = next((e for e in child_entries if e.data.get(CONF_SERIAL_NUMBER) == serial), None)
            status = "✅ Active" if device_entry else "❌ Inactive"
            device_status_info.append(f"{name}: {status}")

        status_summary = "\n".join(device_status_info) if device_status_info else "No devices found"

        return self.async_show_form(
            step_id="manage_devices",
            data_schema=vol.Schema({vol.Required("action"): vol.In(action_options)}),
            description_placeholders={
                "device_count": str(len(devices)),
                "active_count": str(len(child_entries)),
                "account_email": self.config_entry.data.get("email", "Unknown"),
                "device_status": status_summary,
            },
        )

    async def async_step_reload_all(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle reloading all devices."""
        if user_input is not None:
            if user_input.get("confirm"):
                # Reload all child device entries
                child_entries = [
                    entry
                    for entry in self.hass.config_entries.async_entries(DOMAIN)
                    if entry.data.get("parent_entry_id") == self.config_entry.entry_id
                ]

                for child_entry in child_entries:
                    await self.hass.config_entries.async_reload(child_entry.entry_id)

                return self.async_create_entry(title="", data={})
            else:
                return await self.async_step_manage_devices()

        child_count = len(
            [
                entry
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                if entry.data.get("parent_entry_id") == self.config_entry.entry_id
            ]
        )

        return self.async_show_form(
            step_id="reload_all",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            description_placeholders={
                "device_count": str(len(self.config_entry.data.get("devices", []))),
                "active_count": str(child_count),
            },
        )

    async def async_step_delete_device(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle deleting a specific device."""
        if user_input is None:
            return await self.async_step_manage_devices()

        device_serial = user_input.get("device_serial")
        if not device_serial:
            return await self.async_step_manage_devices()

        devices = self.config_entry.data.get("devices", [])
        device = next((d for d in devices if d["serial_number"] == device_serial), None)

        if not device:
            return await self.async_step_manage_devices()

        if user_input.get("confirm"):
            # Remove device from the account entry
            updated_devices = [d for d in devices if d["serial_number"] != device_serial]

            # Find and remove the corresponding device entry
            device_entry = next(
                (
                    entry
                    for entry in self.hass.config_entries.async_entries(DOMAIN)
                    if (
                        entry.data.get("parent_entry_id") == self.config_entry.entry_id
                        and entry.data.get(CONF_SERIAL_NUMBER) == device_serial
                    )
                ),
                None,
            )

            if device_entry:
                await self.hass.config_entries.async_remove(device_entry.entry_id)

            if not updated_devices:
                # If no devices left, delete the entire account entry
                await self.hass.config_entries.async_remove(self.config_entry.entry_id)
                return self.async_create_entry(title="", data={})
            else:
                # Update the account entry with remaining devices
                updated_data = dict(self.config_entry.data)
                updated_data["devices"] = updated_devices

                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=updated_data, title=f"Dyson Account ({len(updated_devices)} devices)"
                )

                return self.async_create_entry(title="", data={})

        if "confirm" not in user_input:
            # Find the corresponding device entry to show status
            device_entry = next(
                (
                    entry
                    for entry in self.hass.config_entries.async_entries(DOMAIN)
                    if (
                        entry.data.get("parent_entry_id") == self.config_entry.entry_id
                        and entry.data.get(CONF_SERIAL_NUMBER) == device_serial
                    )
                ),
                None,
            )
            status = "✅ Active" if device_entry else "❌ Inactive"

            return self.async_show_form(
                step_id="delete_device",
                data_schema=vol.Schema(
                    {
                        vol.Required("confirm", default=False): bool,
                        vol.Required("device_serial", default=device_serial): str,
                    }
                ),
                description_placeholders={
                    "device_name": device.get("name", f"Dyson {device_serial}"),
                    "device_serial": device_serial,
                    "device_status": status,
                },
            )

        return await self.async_step_manage_devices()

    async def async_step_reconfigure_connection(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle reconfiguring connection settings."""
        if user_input is not None:
            # Update connection type
            updated_data = dict(self.config_entry.data)
            updated_data["connection_type"] = user_input.get("connection_type")

            self.hass.config_entries.async_update_entry(self.config_entry, data=updated_data)

            # Reload to apply changes
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        current_connection_type = self.config_entry.data.get("connection_type", "local_cloud_fallback")

        return self.async_show_form(
            step_id="reconfigure_connection",
            data_schema=vol.Schema(
                {
                    vol.Required("connection_type", default=current_connection_type): vol.In(
                        {
                            "local_only": "Local Only (Maximum Privacy, No Internet Required)",
                            "local_cloud_fallback": "Local with Cloud Fallback (Recommended)",
                            "cloud_local_fallback": "Cloud with Local Fallback (More Reliable)",
                            "cloud_only": "Cloud Only (For Networks Without mDNS/Zeroconf)",
                        }
                    )
                }
            ),
            description_placeholders={
                "current_type": current_connection_type,
            },
        )

    # Device-specific options flow methods

    async def async_step_device_options(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle individual device options - go directly to connection settings since it's the only option."""
        # Skip the menu and go directly to connection configuration
        return await self.async_step_device_reconfigure_connection()

    async def async_step_device_reconfigure_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle individual device connection reconfiguration."""
        if user_input is not None:
            connection_type = user_input.get("connection_type")

            # Update this device's connection type
            updated_data = dict(self.config_entry.data)

            if connection_type == "use_account_default":
                # Remove device-specific override to use account default
                updated_data.pop("connection_type", None)
            else:
                # Set device-specific override
                updated_data["connection_type"] = connection_type

            self.hass.config_entries.async_update_entry(self.config_entry, data=updated_data)

            # Reload to apply changes
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        # Get current settings
        device_connection_type = self.config_entry.data.get("connection_type")
        parent_entry_id = self.config_entry.data.get("parent_entry_id")

        # Get account-level connection type
        account_connection_type = "local_cloud_fallback"  # Default fallback
        if parent_entry_id:
            account_entries = [
                entry for entry in self.hass.config_entries.async_entries(DOMAIN) if entry.entry_id == parent_entry_id
            ]
            if account_entries:
                account_connection_type = account_entries[0].data.get("connection_type", "local_cloud_fallback")

        # Determine current selection
        if device_connection_type:
            current_selection = device_connection_type
        else:
            current_selection = "use_account_default"

        connection_options = {
            "use_account_default": f"📋 Use Account Default ({_get_connection_type_display_name(account_connection_type)})",
            "local_only": "🔒 Local Only (Maximum Privacy, No Internet Required)",
            "local_cloud_fallback": "🏠 Local with Cloud Fallback (Recommended)",
            "cloud_local_fallback": "☁️ Cloud with Local Fallback (More Reliable)",
            "cloud_only": "🌐 Cloud Only (For Networks Without mDNS/Zeroconf)",
        }

        device_name = self.config_entry.data.get("device_name", "This Device")

        return self.async_show_form(
            step_id="device_reconfigure_connection",
            data_schema=vol.Schema(
                {vol.Required("connection_type", default=current_selection): vol.In(connection_options)}
            ),
            description_placeholders={
                "device_name": device_name,
                "account_connection_type": _get_connection_type_display_name(account_connection_type),
                "current_setting": "Override" if device_connection_type else "Account Default",
            },
        )

    async def async_step_manage_cloud_preferences(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle cloud account preferences management."""
        if user_input is not None:
            # Update cloud preferences
            updated_data = dict(self.config_entry.data)
            updated_data[CONF_POLL_FOR_DEVICES] = user_input.get(CONF_POLL_FOR_DEVICES, DEFAULT_POLL_FOR_DEVICES)
            updated_data[CONF_AUTO_ADD_DEVICES] = user_input.get(CONF_AUTO_ADD_DEVICES, DEFAULT_AUTO_ADD_DEVICES)

            self.hass.config_entries.async_update_entry(self.config_entry, data=updated_data)

            # Reload to apply changes
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        # Get current settings with backward-compatible defaults
        current_poll_for_devices = self.config_entry.data.get(CONF_POLL_FOR_DEVICES, DEFAULT_POLL_FOR_DEVICES)
        current_auto_add_devices = self.config_entry.data.get(CONF_AUTO_ADD_DEVICES, DEFAULT_AUTO_ADD_DEVICES)

        return self.async_show_form(
            step_id="manage_cloud_preferences",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_POLL_FOR_DEVICES, default=current_poll_for_devices): bool,
                    vol.Required(CONF_AUTO_ADD_DEVICES, default=current_auto_add_devices): bool,
                }
            ),
            description_placeholders={
                "email": self.config_entry.data.get("email", "your account"),
                "device_count": str(len(self.config_entry.data.get("devices", []))),
            },
        )
