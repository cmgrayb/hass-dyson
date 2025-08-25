"""Config flow for Dyson Alternative integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.config_entries import ConfigFlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DysonConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for Dyson Alternative."""

    VERSION = 1
    domain = DOMAIN

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # For now, just create a basic entry to test the config flow
                return self.async_create_entry(
                    title="Dyson Device",
                    data={
                        "username": user_input.get(CONF_USERNAME, ""),
                        "password": user_input.get(CONF_PASSWORD, ""),
                        "host": user_input.get(CONF_HOST, ""),
                    },
                )
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Show the configuration form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_HOST): str,
                }
            ),
            errors=errors,
        )
