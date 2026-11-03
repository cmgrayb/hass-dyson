"""Tests for the reload repair following a change of HA temperature units."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import UnitOfTemperature

from custom_components.hass_dyson.const import DOMAIN
from custom_components.hass_dyson.repairs import (
    TemperatureUnitRepairFlow,
    async_watch_temperature_unit,
)

REPAIRS = "custom_components.hass_dyson.repairs"


@pytest.mark.parametrize(
    ("old_unit", "new_unit"),
    [
        (UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT),
        (UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS),
    ],
)
def test_unit_change_creates_repair_and_switching_back_clears_it(old_unit, new_unit):
    """Create one repair per device, without reloading automatically."""
    hass = MagicMock()
    entry = MagicMock(entry_id="heater", title="Heater")
    hass.config.units.temperature_unit = old_unit
    with (
        patch(f"{REPAIRS}.ir.async_create_issue") as create,
        patch(f"{REPAIRS}.ir.async_delete_issue") as delete,
    ):
        async_watch_temperature_unit(hass, entry)
        callback = hass.bus.async_listen.call_args.args[1]
        hass.config.units.temperature_unit = new_unit
        callback(MagicMock())
        assert create.call_args.kwargs["is_fixable"] is True
        assert create.call_args.kwargs["data"] == {
            "entry_id": "heater",
            "old_unit": old_unit,
        }
        assert (
            create.call_args.kwargs["translation_placeholders"]["new_unit"] == new_unit
        )
        hass.config_entries.async_reload.assert_not_called()
        create.reset_mock()
        hass.config.units.temperature_unit = old_unit
        callback(MagicMock())
        create.assert_not_called()
        delete.assert_called_with(hass, DOMAIN, "temperature_unit_changed_heater")
        # Unload removes the listener and any outstanding issue.
        for call in entry.async_on_unload.call_args_list:
            call.args[0]()
        hass.bus.async_listen.return_value.assert_called_once_with()


@pytest.mark.parametrize("success", [True, False])
async def test_reload_requires_confirmation_and_failed_reload_can_retry(success):
    """Confirmation reloads only the affected entry; failure retains the issue."""
    flow = TemperatureUnitRepairFlow("heater", UnitOfTemperature.CELSIUS)
    flow.hass = MagicMock()
    flow.context = {"issue_id": "temperature_unit_changed_heater"}
    entry = MagicMock(domain=DOMAIN, title="Heater")
    flow.hass.config_entries.async_get_entry.return_value = entry
    reload = AsyncMock(return_value=success)
    flow.hass.config_entries.async_reload = reload
    with patch(f"{REPAIRS}.ir.async_create_issue") as create:
        result = await flow.async_step_init()
        assert result["type"] == "form"
        reload.assert_not_awaited()
        result = await flow.async_step_confirm({})
        reload.assert_awaited_once_with("heater")
        if success:
            assert result["type"] == "create_entry"
            create.assert_not_called()
        else:
            assert result["errors"] == {"base": "reload_failed"}
            create.assert_called_once()
