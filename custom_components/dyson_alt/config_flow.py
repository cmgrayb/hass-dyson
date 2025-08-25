"""Config flow for Dyson Alternative integration."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CAPABILITY_ADVANCE_OSCILLATION,
    CAPABILITY_ENVIRONMENTAL_DATA,
    CAPABILITY_EXTENDED_AQ,
    CAPABILITY_SCHEDULING,
    CONF_CAPABILITIES,
    CONF_DEVICE_TYPE,
    CONF_DISCOVERY_METHOD,
    CONF_SERIAL_NUMBER,
    DISCOVERY_CLOUD,
    DISCOVERY_MANUAL,
    DISCOVERY_STICKER,
    DOMAIN,
    SUPPORTED_DEVICE_CATEGORIES,
)

_LOGGER = logging.getLogger(__name__)

# Configuration schemas
CLOUD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STICKER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_NUMBER): str,
        vol.Required(CONF_PASSWORD, description="MQTT Password from sticker"): str,
        vol.Required("mqtt_prefix", description="MQTT Prefix (e.g., 438M, 475, etc.)"): str,
        vol.Optional(CONF_HOST, description="Device hostname or IP (optional)"): str,
    }
)

CAPABILITIES_SCHEMA = vol.Schema(
    {
        vol.Optional(CAPABILITY_ADVANCE_OSCILLATION, default=False): bool,
        vol.Optional(CAPABILITY_SCHEDULING, default=False): bool,
        vol.Optional(CAPABILITY_ENVIRONMENTAL_DATA, default=False): bool,
        vol.Optional(CAPABILITY_EXTENDED_AQ, default=False): bool,
    }
)

DEVICE_TYPE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_TYPE, default="ec"): vol.In(SUPPORTED_DEVICE_CATEGORIES),
    }
)


class DysonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dyson Alternative."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_method: Optional[str] = None
        self._cloud_devices: List[Dict[str, Any]] = []
        self._user_input: Dict[str, Any] = {}

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._discovery_method = user_input["discovery_method"]

            if self._discovery_method == DISCOVERY_CLOUD:
                return await self.async_step_cloud()
            elif self._discovery_method == DISCOVERY_STICKER:
                return await self.async_step_sticker()
            else:
                return await self.async_step_manual()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("discovery_method", default=DISCOVERY_CLOUD): vol.In(
                        {
                            DISCOVERY_CLOUD: "Dyson Cloud Account",
                            DISCOVERY_STICKER: "Device Sticker/WiFi Info",
                            DISCOVERY_MANUAL: "Manual Configuration",
                        }
                    ),
                }
            ),
            description_placeholders={
                "cloud_desc": "Login with your Dyson account to automatically discover devices",
                "sticker_desc": "Use information from the device sticker for older models",
                "manual_desc": "Manually configure device connection details",
            },
        )

    async def async_step_cloud(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle cloud authentication step."""
        errors = {}

        if user_input is not None:
            try:
                # Validate cloud credentials and discover devices
                devices = await self._async_validate_cloud_auth(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])

                if not devices:
                    errors["base"] = "no_devices_found"
                else:
                    self._cloud_devices = devices
                    self._user_input.update(user_input)

                    if len(devices) == 1:
                        # Single device - proceed directly to creation
                        return await self._async_create_cloud_entry(devices[0])
                    else:
                        # Multiple devices - let user select
                        return await self.async_step_cloud_select()

            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during cloud authentication")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="cloud",
            data_schema=CLOUD_SCHEMA,
            errors=errors,
            description_placeholders={
                "account_info": "Enter your Dyson account credentials to discover your devices",
            },
        )

    async def async_step_cloud_select(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle device selection for cloud discovery."""
        if user_input is not None:
            selected_device = user_input["device"]
            device_data = next(d for d in self._cloud_devices if d["serial"] == selected_device)
            return await self._async_create_cloud_entry(device_data)

        device_options = {
            device["serial"]: f"{device.get('name', device['serial'])} ({device['model']})"
            for device in self._cloud_devices
        }

        return self.async_show_form(
            step_id="cloud_select",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): vol.In(device_options),
                }
            ),
            description_placeholders={
                "device_count": str(len(self._cloud_devices)),
            },
        )

    async def async_step_sticker(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle sticker/WiFi configuration step."""
        errors = {}

        if user_input is not None:
            try:
                # Validate sticker credentials
                await self._async_validate_sticker_auth(user_input)
                self._user_input.update(user_input)
                return await self.async_step_device_type()

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during sticker validation")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="sticker",
            data_schema=STICKER_SCHEMA,
            errors=errors,
            description_placeholders={
                "sticker_info": "Find the serial number and WiFi password on your device sticker",
            },
        )

    async def async_step_device_type(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle device type selection for manual configuration."""
        if user_input is not None:
            self._user_input.update(user_input)
            return await self.async_step_capabilities()

        return self.async_show_form(
            step_id="device_type",
            data_schema=DEVICE_TYPE_SCHEMA,
            description_placeholders={
                "type_info": "Select your device type to enable appropriate features",
            },
        )

    async def async_step_capabilities(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle capability selection for manual configuration."""
        if user_input is not None:
            # Convert boolean selections to capability list
            capabilities = [cap for cap, enabled in user_input.items() if enabled]
            self._user_input[CONF_CAPABILITIES] = capabilities
            return await self._async_create_sticker_entry()

        return self.async_show_form(
            step_id="capabilities",
            data_schema=CAPABILITIES_SCHEMA,
            description_placeholders={
                "cap_info": "Select the capabilities your device supports",
            },
        )

    async def async_step_manual(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle manual configuration (placeholder)."""
        # TODO: Implement manual configuration for advanced users
        return self.async_abort(reason="not_implemented")

    async def _async_validate_cloud_auth(self, username: str, password: str) -> List[Dict[str, Any]]:
        """Validate cloud credentials and return available devices."""
        from libdyson_rest import DysonClient

        try:
            # Initialize cloud client
            cloud_client = DysonClient()

            # Authenticate with Dyson cloud API using two-step process
            await self.hass.async_add_executor_job(lambda: cloud_client.begin_login(username))

            await self.hass.async_add_executor_job(lambda: cloud_client.authenticate(password))

            # Get devices list
            devices = await self.hass.async_add_executor_job(cloud_client.get_devices)

            # Convert devices to our format and filter connected ones
            device_list = []
            for device in devices:
                if hasattr(device, "connection_state") and device.connection_state != "OFFLINE":
                    device_data = {
                        "serial": device.serial,
                        "name": getattr(device, "name", device.serial),
                        "product_type": getattr(device, "product_type", "Unknown"),
                        # Store credentials in device data for later use
                        "username": username,
                        "password": password,
                    }
                    device_list.append(device_data)

            return device_list

        except Exception as exc:
            _LOGGER.error("Cloud authentication failed: %s", exc)
            if "InvalidAuth" in str(type(exc)):
                raise InvalidAuth from exc
            else:
                raise CannotConnect from exc

    async def _async_validate_sticker_auth(self, config: Dict[str, Any]) -> None:
        """Validate sticker credentials."""
        # TODO: Implement sticker/WiFi validation
        # This should test MQTT connection with provided credentials

        raise NotImplementedError("Sticker validation not yet implemented")

    async def _async_create_cloud_entry(self, device_data: Dict[str, Any]) -> FlowResult:
        """Create config entry for cloud-discovered device."""
        serial = device_data["serial"]

        # Check if device already configured
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=device_data.get("name", serial),
            data={
                CONF_SERIAL_NUMBER: serial,
                CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD,
                CONF_USERNAME: self._user_input[CONF_USERNAME],
                CONF_PASSWORD: self._user_input[CONF_PASSWORD],
                "device_data": device_data,
            },
        )

    async def _async_create_sticker_entry(self) -> FlowResult:
        """Create config entry for sticker-configured device."""
        serial = self._user_input[CONF_SERIAL_NUMBER]

        # Check if device already configured
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Dyson {serial}",
            data={
                CONF_SERIAL_NUMBER: serial,
                CONF_DISCOVERY_METHOD: DISCOVERY_STICKER,
                CONF_PASSWORD: self._user_input[CONF_PASSWORD],
                CONF_HOST: self._user_input.get(CONF_HOST, serial),
                CONF_DEVICE_TYPE: self._user_input[CONF_DEVICE_TYPE],
                CONF_CAPABILITIES: self._user_input[CONF_CAPABILITIES],
                "mqtt_prefix": self._user_input["mqtt_prefix"],  # Add MQTT prefix from user input
            },
        )

    async def async_step_import(self, import_config: Dict[str, Any]) -> FlowResult:
        """Handle import from YAML configuration."""
        _LOGGER.debug("Importing YAML configuration: %s", import_config)

        # Check if device is already configured
        serial = import_config[CONF_SERIAL_NUMBER]
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()

        # Create config entry from YAML data
        return self.async_create_entry(
            title=f"Theater Fan ({serial})",
            data=import_config,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the device."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
