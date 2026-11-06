"""Repairs for Dyson temperature unit changes."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_ISSUE_PREFIX = "temperature_unit_changed_"


@callback
def _async_create_unit_issue(
    hass: HomeAssistant, entry: ConfigEntry, old_unit: str
) -> None:
    """Request a reload for one device entry."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{_ISSUE_PREFIX}{entry.entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="temperature_unit_changed",
        translation_placeholders={
            "device_name": entry.title,
            "old_unit": old_unit,
            "new_unit": hass.config.units.temperature_unit,
        },
        data={"entry_id": entry.entry_id, "old_unit": old_unit},
    )


@callback
def async_watch_temperature_unit(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Notify when HA's unit differs from the unit selected at device setup."""
    setup_unit = hass.config.units.temperature_unit
    issue_id = f"{_ISSUE_PREFIX}{entry.entry_id}"
    ir.async_delete_issue(hass, DOMAIN, issue_id)

    @callback
    def async_unit_changed(event: Event) -> None:
        if hass.config.units.temperature_unit == setup_unit:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
        else:
            _async_create_unit_issue(hass, entry, setup_unit)

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, async_unit_changed)
    )
    entry.async_on_unload(lambda: ir.async_delete_issue(hass, DOMAIN, issue_id))


class TemperatureUnitRepairFlow(RepairsFlow):
    """Reload the affected Dyson device after the user confirms."""

    def __init__(self, entry_id: str, old_unit: str) -> None:
        self.entry_id = entry_id
        self.old_unit = old_unit

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        entry = self.hass.config_entries.async_get_entry(self.entry_id)
        if entry is None or entry.domain != DOMAIN:
            return self.async_create_entry(data={})

        errors = {}
        if user_input is not None:
            try:
                reloaded = await self.hass.config_entries.async_reload(self.entry_id)
            except HomeAssistantError:
                _LOGGER.exception("Unable to reload Dyson device %s", entry.title)
                reloaded = False
            if reloaded:
                return self.async_create_entry(data={})
            # An unsuccessful reload can unload the entry and clear its issue.
            _async_create_unit_issue(self.hass, entry, self.old_unit)
            errors["base"] = "reload_failed"

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"device_name": entry.title},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a repair flow for a temperature unit mismatch."""
    if not issue_id.startswith(_ISSUE_PREFIX) or not data:
        raise ValueError(f"Unknown Dyson repair: {issue_id}")
    return TemperatureUnitRepairFlow(str(data["entry_id"]), str(data["old_unit"]))
