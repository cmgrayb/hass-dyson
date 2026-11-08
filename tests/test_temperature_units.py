"""Regression tests for unit-aware Dyson heater controls."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import UnitOfTemperature

from custom_components.hass_dyson.climate import DysonClimateEntity
from custom_components.hass_dyson.const import (
    decikelvin_to_target_units,
    decikelvin_to_units,
    units_to_decikelvin,
)
from custom_components.hass_dyson.device import DysonDevice
from custom_components.hass_dyson.fan import DysonFan

C = UnitOfTemperature.CELSIUS
F = UnitOfTemperature.FAHRENHEIT


@pytest.mark.parametrize(
    ("unit", "target"),
    [(C, value) for value in range(1, 38)] + [(F, value) for value in range(34, 99)],
)
async def test_entity_setpoints_survive_repeated_readback(unit, target):
    """Exercise entity setters, wire commands, readings and scene attributes."""
    device = DysonDevice.__new__(DysonDevice)
    device.send_command = AsyncMock()
    device.get_state_value = lambda data, key, default: data.get(key, default)
    device._state_data = {}
    coordinator = MagicMock()
    coordinator.hass.config.units.temperature_unit = unit
    coordinator.device = device
    coordinator.device_capabilities = ["Heating"]
    coordinator.serial_number = "test-heater"
    coordinator.data = {"product-state": {}, "environmental-data": {"tact": "2987"}}

    for entity_type, update in (
        (DysonClimateEntity, "_update_temperatures"),
        (DysonFan, "_update_heating_data"),
    ):
        entity = entity_type(coordinator)
        entity.async_write_ha_state = MagicMock()
        assert entity._attr_temperature_unit == unit
        assert entity._attr_target_temperature_step == 1
        for _ in range(10):
            device.send_command.reset_mock()
            await entity.async_set_temperature(temperature=target)
            device.send_command.assert_awaited_once_with(
                "STATE-SET",
                {"hmod": "HEAT", "hmax": f"{units_to_decikelvin(target, unit):04d}"},
            )
            raw = device.send_command.call_args.args[1]["hmax"]
            getattr(entity, update)({"hmax": raw})
            assert entity._attr_target_temperature == target
            assert entity._attr_current_temperature == round(
                decikelvin_to_units(2987, unit), 1
            )
            attrs = entity.extra_state_attributes
            assert attrs["target_temperature"] == target
            assert attrs["temperature_unit"] == unit
            assert attrs["target_temperature_kelvin"] == raw


def test_fahrenheit_regression():
    """78°F must remain 78°F instead of snapping to 26°C / 79°F."""
    assert units_to_decikelvin(78, F) == 2987
    assert decikelvin_to_units(2987, F) == pytest.approx(77.99)
    assert decikelvin_to_target_units(2987, F) == 78


@pytest.mark.parametrize(
    ("unit", "minimum", "maximum", "default"), [(C, 1, 37, 20), (F, 34, 98, 68)]
)
def test_limits_and_invalid_reading_defaults(unit, minimum, maximum, default):
    """Both units advertise valid whole-degree endpoints and matching defaults."""
    coordinator = MagicMock()
    coordinator.hass.config.units.temperature_unit = unit
    coordinator.device_capabilities = ["Heating"]
    coordinator.data = {"product-state": {}, "environmental-data": {}}
    coordinator.device.get_state_value.side_effect = lambda data, key, fallback: (
        data.get(key, fallback)
    )
    climate = DysonClimateEntity(coordinator)
    fan = DysonFan(coordinator)
    assert (climate.min_temp, climate.max_temp) == (minimum, maximum)
    assert (fan._attr_min_temp, fan._attr_max_temp) == (minimum, maximum)
    for raw in ("0000", "OFF", None):
        climate._update_temperatures({"hmax": raw})
        fan._update_heating_data({"hmax": raw})
        assert climate._attr_target_temperature == default
        assert fan._attr_target_temperature == default


@pytest.mark.parametrize(
    ("unit", "target"),
    [(C, 0), (C, 37.1), (F, 33), (F, 99), (C, float("nan")), (F, float("inf"))],
)
async def test_invalid_target_never_sends_command(unit, target):
    """Range validation happens before the transport is called."""
    device = DysonDevice.__new__(DysonDevice)
    device.send_command = AsyncMock()
    with pytest.raises(ValueError):
        await device.set_target_temperature(target, unit)
    device.send_command.assert_not_awaited()


async def test_device_api_defaults_to_celsius():
    """Existing single-argument device callers retain Celsius semantics."""
    device = DysonDevice.__new__(DysonDevice)
    device.send_command = AsyncMock()
    await device.set_target_temperature(37)
    device.send_command.assert_awaited_once_with(
        "STATE-SET", {"hmod": "HEAT", "hmax": "3102"}
    )
