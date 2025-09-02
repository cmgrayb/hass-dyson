"""Config flow for Dyson Alternative integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback

from .const import CONF_SERIAL_NUMBER, DOMAIN

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


class DysonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dyson Alternative."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        _LOGGER.info("DysonConfigFlow.__init__ called")
        super().__init__()
        self._email: str | None = None
        self._password: str | None = None
        self._cloud_client = None  # type: ignore
        self._challenge_id: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step - Dyson account authentication."""
        try:
            _LOGGER.info("Starting async_step_user - Dyson account authentication with user_input: %s", user_input)
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
                    challenge = await self.hass.async_add_executor_job(lambda: self._cloud_client.begin_login())

                    # Store challenge ID for verification step
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
                    step_id="user",
                    data_schema=data_schema,
                    errors=errors,
                    description_placeholders={"docs_url": "https://www.dyson.com/support/account"},
                )
            except Exception as e:
                _LOGGER.exception("Error creating authentication form: %s", e)
                raise
        except Exception as e:
            _LOGGER.exception("Top-level exception in async_step_user: %s", e)
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
                        await self.hass.async_add_executor_job(
                            lambda: self._cloud_client.complete_login(self._challenge_id, verification_code)
                        )

                        _LOGGER.info("Successfully authenticated with Dyson API, got auth token")
                        return await self.async_step_connection()

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
                        devices = await self.hass.async_add_executor_job(self._cloud_client.get_devices)

                        if not devices:
                            _LOGGER.warning("No devices found in Dyson account")
                            errors["base"] = "no_devices"
                        else:
                            _LOGGER.info("Found %d devices in Dyson account", len(devices))

                            # Set unique ID based on email to prevent duplicate accounts
                            if self._email:
                                await self.async_set_unique_id(self._email.lower())
                                self._abort_if_unique_id_configured()

                            # Create config entry with all discovered devices
                            device_list = []
                            for device in devices:
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
                                    "connection_type": connection_type,
                                    "devices": device_list,
                                    "auth_token": getattr(self._cloud_client, "auth_token", None),
                                },
                            )

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
