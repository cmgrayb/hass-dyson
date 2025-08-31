"""Config flow for Dyson Alternative integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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
                                title=f"Dyson Account ({len(devices)} devices)",
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
