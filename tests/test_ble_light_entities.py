"""BLE lamp entity tests using the project's HA mocks, never real accounts."""

import json
from datetime import date, time, timezone
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.ble_light_entities import (
    DysonBLELightAwayDate,
    DysonBLELightModeSelect,
    lightcycle_buttons,
    lightcycle_numbers,
    lightcycle_switches,
    lightcycle_times,
)
from custom_components.hass_dyson.ble_light_protocol import (
    MODE_ATTRIBUTES,
    LightAttribute,
)
from custom_components.hass_dyson.const import DOMAIN
from custom_components.hass_dyson.coordinator import DysonBLEDataUpdateCoordinator


@pytest.fixture
def coordinator():
    """Mock only transport/coordinator and retain the real entity behaviour."""
    result = MagicMock(spec=DysonBLEDataUpdateCoordinator)
    result.serial_number = "TEST-LAMP"
    result.is_connected = True
    result.last_update_success = True
    result.data = {"auto_brightness": False, "movement_sensor": True}
    settings = SimpleNamespace(
        available=True,
        attributes={},
        birth_year=None,
        set_sensor=AsyncMock(),
        set_attribute=AsyncMock(),
        set_mode=AsyncMock(),
        set_birth_year=AsyncMock(),
        reset_daylight_times=AsyncMock(),
    )
    result.ble_device = SimpleNamespace(
        lighting=settings,
        device_info={
            "identifiers": {(DOMAIN, "TEST-LAMP")},
            "name": "Dyson TEST-LAMP",
        },
    )
    result.async_sync_light_location = AsyncMock()
    with patch(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        new=lambda entity, coord: setattr(entity, "coordinator", coord),
    ):
        yield result


def by_key(entities):
    """Index production entities by their stable, translated feature key."""
    return {
        entity.translation_key.removeprefix("lightcycle_"): entity
        for entity in entities
    }


def all_entities(coord):
    """Cover each new platform without replacing the original light entity."""
    return [
        *lightcycle_switches(coord),
        *lightcycle_numbers(coord),
        DysonBLELightModeSelect(coord),
        *lightcycle_times(coord),
        DysonBLELightAwayDate(coord),
        *lightcycle_buttons(coord),
    ]


def test_entities_share_identity_and_have_translations(coordinator):
    """No second device/hub or unrelated naming scheme is introduced."""
    entities = all_entities(coordinator)
    assert len({entity.unique_id for entity in entities}) == len(entities)
    for lang in ("en", "de", "fr"):
        translations = json.loads(
            (
                Path(__file__).parents[1]
                / "custom_components"
                / "hass_dyson"
                / "translations"
                / f"{lang}.json"
            ).read_text()
        )
        for entity in entities:
            assert entity.device_info == coordinator.ble_device.device_info
            platform = entity.__class__.__mro__
            key = entity.translation_key
            assert any(key in group for group in translations["entity"].values()), (
                lang,
                key,
                platform,
            )


def test_unknown_optional_values_are_not_invented(coordinator):
    """Absent settings are unavailable, not zero, false or invented defaults."""
    for entity in [
        *lightcycle_numbers(coordinator),
        DysonBLELightModeSelect(coordinator),
        *lightcycle_times(coordinator),
        DysonBLELightAwayDate(coordinator),
    ]:
        assert not entity.available


@pytest.mark.asyncio
async def test_sensor_switches_use_enablement_only(coordinator):
    """Expose the two physical sensor toggles, not raw sensor readings."""
    switches = by_key(lightcycle_switches(coordinator))
    assert switches["auto_brightness"].is_on is False
    assert switches["movement_sensor"].is_on is True
    await switches["auto_brightness"].async_turn_on()
    coordinator.ble_device.lighting.set_sensor.assert_awaited_once_with(
        "auto_brightness", True
    )
    await switches["movement_sensor"].async_turn_off()
    coordinator.ble_device.lighting.set_sensor.assert_awaited_with(
        "movement_sensor", False
    )
    assert "daylight_tracking" not in switches  # Original entity is retained.


@pytest.mark.asyncio
async def test_native_switch_and_mode_commands(coordinator):
    """Apply real native attributes and keep manual mode distinct."""
    settings = coordinator.ble_device.lighting
    switch = by_key(lightcycle_switches(coordinator))["away_mode"]
    assert switch.is_on is None
    settings.attributes[LightAttribute.AWAY_MODE] = b"\1"
    assert switch.is_on is True
    await switch.async_turn_off()
    settings.set_attribute.assert_awaited_with(LightAttribute.AWAY_MODE, b"\0")
    mode = DysonBLELightModeSelect(coordinator)
    settings.attributes.update(dict.fromkeys(MODE_ATTRIBUTES.values(), b"\0"))
    assert mode.current_option == "manual"
    settings.attributes[LightAttribute.STUDY_MODE] = b"\1"
    assert mode.current_option == "study"
    await mode.async_select_option("relax")
    settings.set_mode.assert_awaited_once_with("relax")
    with pytest.raises(ValueError):
        await mode.async_select_option("fake")


@pytest.mark.asyncio
async def test_numbers_and_sensitive_birth_year(coordinator):
    """Only validated, integral values are written; birth year is opt-in."""
    settings = coordinator.ble_device.lighting
    numbers = by_key(lightcycle_numbers(coordinator))
    value = numbers["baseline_brightness"]
    settings.attributes[LightAttribute.BASELINE_BRIGHTNESS] = (400).to_bytes(
        2, "little"
    )
    assert value.native_value == 400
    assert value.available
    await value.async_set_native_value(800)
    settings.set_attribute.assert_awaited_once_with(
        LightAttribute.BASELINE_BRIGHTNESS, b"\x20\x03"
    )
    birth = numbers["birth_year"]
    settings.attributes[LightAttribute.YEAR_OF_BIRTH] = bytes(64)
    assert birth.native_value is None
    assert birth.available
    assert birth.entity_registry_enabled_default is False
    await birth.async_set_native_value(1990)
    settings.set_birth_year.assert_awaited_once_with(1990)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), 1.5, 0, 1001])
async def test_invalid_number_never_writes(coordinator, value):
    """Reject malformed service-call values before the transport sees them."""
    entity = by_key(lightcycle_numbers(coordinator))["baseline_brightness"]
    with pytest.raises(ValueError):
        await entity.async_set_native_value(value)
    coordinator.ble_device.lighting.set_attribute.assert_not_awaited()


@pytest.mark.asyncio
async def test_unset_times_and_dates_remain_editable(coordinator):
    """Sentinels are unset values, not evidence that the feature is unsupported."""
    settings = coordinator.ble_device.lighting
    entity = by_key(lightcycle_times(coordinator))["sunrise_time"]
    settings.attributes[LightAttribute.SUNRISE_TIME] = b"\xff\xff"
    assert entity.available and entity.native_value is None
    await entity.async_set_value(time(6, 30))
    settings.set_attribute.assert_awaited_with(
        LightAttribute.SUNRISE_TIME, (390).to_bytes(2, "little")
    )
    for invalid in (time(6, 30, 1), time(6, 30, tzinfo=timezone.utc)):
        with pytest.raises(ValueError):
            await entity.async_set_value(invalid)
    away = DysonBLELightAwayDate(coordinator)
    settings.attributes[LightAttribute.AWAY_MODE_START_DATE] = bytes(4)
    assert away.available and away.native_value is None
    await away.async_set_value(date(2026, 1, 2))
    settings.set_attribute.assert_awaited_with(
        LightAttribute.AWAY_MODE_START_DATE, (2012026).to_bytes(4, "little")
    )


@pytest.mark.asyncio
async def test_buttons_do_not_expose_cloud_payloads(coordinator):
    """Use explicit configuration actions without leaking location or key data."""
    buttons = by_key(lightcycle_buttons(coordinator))
    await buttons["sync_location"].async_press()
    coordinator.async_sync_light_location.assert_awaited_once_with()
    await buttons["reset_daylight_times"].async_press()
    coordinator.ble_device.lighting.reset_daylight_times.assert_awaited_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "platform,count",
    [
        ("switch", 8),
        ("select", 1),
        ("number", 4),
        ("time", 4),
        ("date", 1),
        ("button", 2),
    ],
)
async def test_lamp_platforms_route_to_existing_coordinator(
    coordinator, platform, count
):
    """Optional lamp setup does not fall through to MQTT or vacuum handlers."""
    hass = MagicMock()
    entry = SimpleNamespace(entry_id="test-lamp")
    hass.data = {
        DOMAIN: {entry.entry_id: {"is_ble": True, "ble_coordinator": coordinator}}
    }
    add = MagicMock()
    await import_module(f"custom_components.hass_dyson.{platform}").async_setup_entry(
        hass, entry, add
    )
    entities = add.call_args.args[0]
    assert len(entities) == count
    assert all(entity.coordinator is coordinator for entity in entities)


def test_disconnect_and_malformed_attributes_are_unavailable(coordinator):
    """An old cached value is not exposed as current after channel failure."""
    settings = coordinator.ble_device.lighting
    entity = by_key(lightcycle_switches(coordinator))["away_mode"]
    settings.attributes[LightAttribute.AWAY_MODE] = b"\xff"
    assert not entity.available
    settings.attributes[LightAttribute.AWAY_MODE] = b"\1"
    assert entity.available
    settings.available = False
    assert not entity.available
