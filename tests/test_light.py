"""Unit tests for the light platform (DysonLightEntity)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hass_dyson.const import BLE_MAX_KELVIN, BLE_MIN_KELVIN
from custom_components.hass_dyson.coordinator import DysonBLEDataUpdateCoordinator
from custom_components.hass_dyson.light import DysonLightEntity


def _make_entity(coordinator=None):
    """Construct DysonLightEntity bypassing CoordinatorEntity.__init__ setup."""
    from homeassistant.helpers.update_coordinator import CoordinatorEntity

    if coordinator is None:
        coordinator = MagicMock(spec=DysonBLEDataUpdateCoordinator)
        coordinator.serial_number = "CD06-GB-HAA0001A"
        coordinator.is_connected = True
        coordinator.last_update_success = True
        coordinator.ble_device = MagicMock()
        coordinator.ble_device.set_power = AsyncMock()
        coordinator.ble_device.set_brightness = AsyncMock()
        coordinator.ble_device.set_color_temp_kelvin = AsyncMock()
        coordinator.data = {
            "power": True,
            "brightness": 191,
            "color_temp_kelvin": 4000,
            "color_temp_mired": 250,
            "motion_detected": False,
            "connected": True,
        }

    with MagicMock():
        with pytest.MonkeyPatch().context() as m:
            m.setattr(CoordinatorEntity, "__init__", lambda s, c: None)
            entity = DysonLightEntity.__new__(DysonLightEntity)
            entity.coordinator = coordinator
            # Set attrs normally set by DysonLightEntity.__init__
            entity._attr_unique_id = f"{coordinator.serial_number}_light"
            entity._attr_name = "Light"
    return entity


class TestDysonLightEntityProperties:
    """State property tests for DysonLightEntity."""

    def test_is_on_when_power_true(self):
        """is_on returns True when coordinator data reports power=True."""
        entity = _make_entity()
        assert entity.is_on is True

    def test_is_on_when_power_false(self):
        """is_on returns False when power is False."""
        entity = _make_entity()
        entity.coordinator.data = {
            "power": False,
            "brightness": 0,
            "color_temp_kelvin": 4000,
        }
        assert entity.is_on is False

    def test_is_on_when_no_data(self):
        """is_on returns None when coordinator data is None."""
        entity = _make_entity()
        entity.coordinator.data = None
        assert entity.is_on is None

    def test_brightness_from_coordinator_data(self):
        """brightness returns the HA-scale value from coordinator data."""
        entity = _make_entity()
        entity.coordinator.data = {"brightness": 200}
        assert entity.brightness == 200

    def test_brightness_none_when_no_data(self):
        """brightness returns None when coordinator has no data."""
        entity = _make_entity()
        entity.coordinator.data = None
        assert entity.brightness is None

    def test_color_temp_kelvin_from_data(self):
        """color_temp_kelvin returns value from coordinator data."""
        entity = _make_entity()
        entity.coordinator.data = {"color_temp_kelvin": 4500}
        assert entity.color_temp_kelvin == 4500

    def test_color_temp_kelvin_none_when_no_data(self):
        """color_temp_kelvin returns None when no data."""
        entity = _make_entity()
        entity.coordinator.data = None
        assert entity.color_temp_kelvin is None

    def test_supported_color_modes(self):
        """Entity declares COLOR_TEMP as its only color mode."""
        from homeassistant.components.light import ColorMode

        entity = _make_entity()
        assert ColorMode.COLOR_TEMP in entity._attr_supported_color_modes

    def test_min_max_color_temp_kelvin(self):
        """Min/max color temp matches BLE constants."""
        entity = _make_entity()
        assert entity._attr_min_color_temp_kelvin == BLE_MIN_KELVIN
        assert entity._attr_max_color_temp_kelvin == BLE_MAX_KELVIN

    def test_unique_id_includes_serial(self):
        """Unique ID is serial + '_light'."""
        entity = _make_entity()
        assert entity._attr_unique_id == "CD06-GB-HAA0001A_light"


class TestDysonLightEntityCommands:
    """Command (service call) tests for DysonLightEntity."""

    @pytest.mark.asyncio
    async def test_turn_on_calls_set_power(self):
        """async_turn_on() calls set_power(True) on the BLE device."""
        entity = _make_entity()
        await entity.async_turn_on()
        entity.coordinator.ble_device.set_power.assert_awaited_once_with(on=True)

    @pytest.mark.asyncio
    async def test_turn_on_with_brightness_calls_set_brightness(self):
        """async_turn_on(brightness=X) calls set_brightness(X)."""
        from homeassistant.components.light import ATTR_BRIGHTNESS

        entity = _make_entity()
        await entity.async_turn_on(**{ATTR_BRIGHTNESS: 128})
        entity.coordinator.ble_device.set_brightness.assert_awaited_once_with(128)

    @pytest.mark.asyncio
    async def test_turn_on_with_color_temp_calls_set_color_temp_kelvin(self):
        """async_turn_on(color_temp_kelvin=X) calls set_color_temp_kelvin(X)."""
        from homeassistant.components.light import ATTR_COLOR_TEMP_KELVIN

        entity = _make_entity()
        await entity.async_turn_on(**{ATTR_COLOR_TEMP_KELVIN: 5000})
        entity.coordinator.ble_device.set_color_temp_kelvin.assert_awaited_once_with(
            5000
        )

    @pytest.mark.asyncio
    async def test_turn_off_calls_set_power_false(self):
        """async_turn_off() calls set_power(False) on the BLE device."""
        entity = _make_entity()
        await entity.async_turn_off()
        entity.coordinator.ble_device.set_power.assert_awaited_once_with(on=False)

    @pytest.mark.asyncio
    async def test_turn_on_without_ble_device_logs_warning(self):
        """async_turn_on does not raise when ble_device is None — logs warning."""
        entity = _make_entity()
        entity.coordinator.ble_device = None
        # Should not raise
        await entity.async_turn_on()

    @pytest.mark.asyncio
    async def test_turn_off_without_ble_device_logs_warning(self):
        """async_turn_off does not raise when ble_device is None."""
        entity = _make_entity()
        entity.coordinator.ble_device = None
        await entity.async_turn_off()

    @pytest.mark.asyncio
    async def test_turn_on_brightness_and_color_temp_together(self):
        """Can set both brightness and color temperature in one call."""
        from homeassistant.components.light import (
            ATTR_BRIGHTNESS,
            ATTR_COLOR_TEMP_KELVIN,
        )

        entity = _make_entity()
        await entity.async_turn_on(
            **{ATTR_BRIGHTNESS: 200, ATTR_COLOR_TEMP_KELVIN: 3000}
        )
        entity.coordinator.ble_device.set_power.assert_awaited_once_with(on=True)
        entity.coordinator.ble_device.set_brightness.assert_awaited_once_with(200)
        entity.coordinator.ble_device.set_color_temp_kelvin.assert_awaited_once_with(
            3000
        )


class TestDysonLightEntityAvailability:
    """Availability tests for DysonLightEntity."""

    def test_available_when_connected(self):
        """Entity is available when coordinator is connected and last_update_success."""
        entity = _make_entity()
        entity.coordinator.is_connected = True
        entity.coordinator.last_update_success = True
        assert entity.available is True

    def test_unavailable_when_not_connected(self):
        """Entity is unavailable when coordinator reports not connected."""
        entity = _make_entity()
        entity.coordinator.is_connected = False
        assert entity.available is False

    def test_unavailable_when_last_update_failed(self):
        """Entity is unavailable when last_update_success is False."""
        entity = _make_entity()
        entity.coordinator.last_update_success = False
        assert entity.available is False


class TestDysonLightEntitySetup:
    """Tests for async_setup_entry."""

    @pytest.mark.asyncio
    async def test_setup_entry_creates_entity(
        self, pure_mock_hass, mock_ble_coordinator, mock_ble_config_entry
    ):
        """async_setup_entry creates a DysonLightEntity and calls async_add_entities."""
        from custom_components.hass_dyson.const import DOMAIN
        from custom_components.hass_dyson.light import async_setup_entry

        pure_mock_hass.data = {
            DOMAIN: {
                mock_ble_config_entry.entry_id: {
                    "ble_coordinator": mock_ble_coordinator,
                    "is_ble": True,
                }
            }
        }
        add_entities = MagicMock()
        await async_setup_entry(pure_mock_hass, mock_ble_config_entry, add_entities)
        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DysonLightEntity)
