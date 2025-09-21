"""Test switch platform for Dyson integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.hass_dyson.const import CONF_DISCOVERY_METHOD, DOMAIN
from custom_components.hass_dyson.switch import (
    DysonAutoModeSwitch,
    DysonContinuousMonitoringSwitch,
    DysonHeatingSwitch,
    DysonNightModeSwitch,
    DysonOscillationSwitch,
    async_setup_entry,
)


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test-entry-id"
    config_entry.data = {CONF_DISCOVERY_METHOD: "manual"}  # Default to manual
    return config_entry


@pytest.fixture
def mock_entity_setup():
    """Fixture to setup entity mocks properly."""

    def setup_entity(entity):
        """Setup entity with required Home Assistant attributes."""
        entity.hass = MagicMock()
        entity.entity_id = "switch.test"
        entity._attr_should_poll = False
        with patch("homeassistant.helpers.entity.Entity.async_write_ha_state"):
            return entity

    return setup_entity


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    return hass


class TestSwitchPlatformSetup:
    """Test switch platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_basic_switches(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Test that async_setup_entry creates basic switches."""
        # Arrange
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator
        mock_add_entities = MagicMock()

        # Act
        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        # Assert
        mock_add_entities.assert_called_once()
        added_entities = mock_add_entities.call_args[0][0]

        # Should have night mode, heating, and continuous monitoring switches (no firmware switch for manual)
        assert len(added_entities) == 3
        entity_types = [type(entity).__name__ for entity in added_entities]
        assert "DysonNightModeSwitch" in entity_types
        assert "DysonHeatingSwitch" in entity_types
        assert "DysonContinuousMonitoringSwitch" in entity_types

    @pytest.mark.asyncio
    async def test_async_setup_entry_cloud_device_with_firmware_switch(
        self, mock_hass, mock_coordinator
    ):
        """Test that cloud devices get firmware auto-update switch."""
        # Arrange
        cloud_config_entry = MagicMock(spec=ConfigEntry)
        cloud_config_entry.entry_id = "test-cloud-entry"
        cloud_config_entry.data = {CONF_DISCOVERY_METHOD: "cloud"}

        mock_hass.data[DOMAIN][cloud_config_entry.entry_id] = mock_coordinator
        mock_add_entities = MagicMock()

        # Act
        await async_setup_entry(mock_hass, cloud_config_entry, mock_add_entities)

        # Assert
        mock_add_entities.assert_called_once()
        added_entities = mock_add_entities.call_args[0][0]

        # Should have night mode, firmware auto-update, heating, and continuous monitoring switches
        assert len(added_entities) == 4
        entity_types = [type(entity).__name__ for entity in added_entities]
        assert "DysonNightModeSwitch" in entity_types
        assert "DysonFirmwareAutoUpdateSwitch" in entity_types
        assert "DysonHeatingSwitch" in entity_types
        assert "DysonContinuousMonitoringSwitch" in entity_types

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_optional_capabilities(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Test setup with no optional capabilities."""
        # Arrange
        mock_coordinator.device_capabilities = []  # No optional capabilities
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator
        mock_add_entities = MagicMock()

        # Act
        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        # Assert
        added_entities = mock_add_entities.call_args[0][0]
        # Should only have night mode switch
        assert len(added_entities) == 1
        assert isinstance(added_entities[0], DysonNightModeSwitch)


class TestDysonAutoModeSwitch:
    """Test DysonAutoModeSwitch class."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        switch = DysonAutoModeSwitch(mock_coordinator)

        # Assert
        assert switch.coordinator == mock_coordinator
        assert switch._attr_unique_id == "TEST-SERIAL-123_auto_mode"
        assert switch._attr_translation_key == "auto_mode"
        assert switch._attr_icon == "mdi:auto-mode"

    def test_handle_coordinator_update_auto_on(self, mock_coordinator):
        """Test coordinator update when auto mode is on."""
        # Arrange
        switch = DysonAutoModeSwitch(mock_coordinator)
        mock_coordinator.device._get_current_value.return_value = "ON"

        with patch.object(switch, "async_write_ha_state"):
            # Act
            switch._handle_coordinator_update()

            # Assert
            assert switch._attr_is_on is True
            mock_coordinator.device._get_current_value.assert_called_with(
                mock_coordinator.data["product-state"], "auto", "OFF"
            )

    def test_handle_coordinator_update_auto_off(self, mock_coordinator):
        """Test coordinator update when auto mode is off."""
        # Arrange
        switch = DysonAutoModeSwitch(mock_coordinator)
        mock_coordinator.device._get_current_value.return_value = "OFF"

        with patch.object(switch, "async_write_ha_state"):
            # Act
            switch._handle_coordinator_update()

            # Assert
            assert switch._attr_is_on is False

    def test_handle_coordinator_update_no_device(self, mock_coordinator):
        """Test coordinator update when no device is available."""
        # Arrange
        mock_coordinator.device = None
        switch = DysonAutoModeSwitch(mock_coordinator)

        with patch.object(switch, "async_write_ha_state"):
            # Act
            switch._handle_coordinator_update()

            # Assert
            assert switch._attr_is_on is None

    @pytest.mark.asyncio
    async def test_async_turn_on_success(self, mock_coordinator):
        """Test successful auto mode turn on."""
        # Arrange
        switch = DysonAutoModeSwitch(mock_coordinator)
        mock_coordinator.device.set_auto_mode = AsyncMock()

        # Act
        await switch.async_turn_on()

        # Assert
        mock_coordinator.device.set_auto_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_async_turn_on_no_device(self, mock_coordinator):
        """Test auto mode turn on with no device."""
        # Arrange
        mock_coordinator.device = None
        switch = DysonAutoModeSwitch(mock_coordinator)

        # Act
        await switch.async_turn_on()

        # Assert - should not raise an exception

    @pytest.mark.asyncio
    async def test_async_turn_on_device_error(self, mock_coordinator):
        """Test auto mode turn on with device error."""
        # Arrange
        switch = DysonAutoModeSwitch(mock_coordinator)
        mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=Exception("Device error")
        )

        with patch("custom_components.hass_dyson.switch._LOGGER") as mock_logger:
            # Act
            await switch.async_turn_on()

            # Assert
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_turn_off_success(self, mock_coordinator):
        """Test successful auto mode turn off."""
        # Arrange
        switch = DysonAutoModeSwitch(mock_coordinator)
        mock_coordinator.device.set_auto_mode = AsyncMock()

        # Act
        await switch.async_turn_off()

        # Assert
        mock_coordinator.device.set_auto_mode.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_async_turn_off_device_error(self, mock_coordinator):
        """Test auto mode turn off with device error."""
        # Arrange
        switch = DysonAutoModeSwitch(mock_coordinator)
        mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=Exception("Device error")
        )

        with patch("custom_components.hass_dyson.switch._LOGGER") as mock_logger:
            # Act
            await switch.async_turn_off()

            # Assert
            mock_logger.error.assert_called_once()


class TestDysonNightModeSwitch:
    """Test DysonNightModeSwitch class."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        switch = DysonNightModeSwitch(mock_coordinator)

        # Assert
        assert switch.coordinator == mock_coordinator
        assert switch._attr_unique_id == "TEST-SERIAL-123_night_mode"
        assert switch._attr_translation_key == "night_mode"
        assert switch._attr_icon == "mdi:weather-night"

    def test_handle_coordinator_update_night_mode_on(self, mock_coordinator):
        """Test coordinator update when night mode is on."""
        # Arrange
        switch = DysonNightModeSwitch(mock_coordinator)
        mock_coordinator.device._get_current_value.return_value = "ON"

        with patch.object(switch, "async_write_ha_state"):
            # Act
            switch._handle_coordinator_update()

            # Assert
            assert switch._attr_is_on is True
            mock_coordinator.device._get_current_value.assert_called_with(
                mock_coordinator.data["product-state"], "nmod", "OFF"
            )

    @pytest.mark.asyncio
    async def test_async_turn_on_success(self, mock_coordinator):
        """Test successful night mode turn on."""
        # Arrange
        switch = DysonNightModeSwitch(mock_coordinator)
        mock_coordinator.device.set_night_mode = AsyncMock()

        # Act
        await switch.async_turn_on()

        # Assert
        mock_coordinator.device.set_night_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_async_turn_off_success(self, mock_coordinator):
        """Test successful night mode turn off."""
        # Arrange
        switch = DysonNightModeSwitch(mock_coordinator)
        mock_coordinator.device.set_night_mode = AsyncMock()

        # Act
        await switch.async_turn_off()

        # Assert
        mock_coordinator.device.set_night_mode.assert_called_once_with(False)


class TestDysonOscillationSwitch:
    """Test DysonOscillationSwitch class."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        switch = DysonOscillationSwitch(mock_coordinator)

        # Assert
        assert switch.coordinator == mock_coordinator
        assert switch._attr_unique_id == "TEST-SERIAL-123_oscillation"
        assert switch._attr_translation_key == "oscillation"
        assert switch._attr_icon == "mdi:rotate-3d-variant"

    def test_handle_coordinator_update_oscillation_on(self, mock_coordinator):
        """Test coordinator update when oscillation is on."""
        # Arrange
        switch = DysonOscillationSwitch(mock_coordinator)
        mock_coordinator.device._get_current_value.return_value = "ON"

        with patch.object(switch, "async_write_ha_state"):
            # Act
            switch._handle_coordinator_update()

            # Assert
            assert switch._attr_is_on is True
            mock_coordinator.device._get_current_value.assert_called_with(
                mock_coordinator.data["product-state"], "oson", "OFF"
            )

    @pytest.mark.asyncio
    async def test_async_turn_on_success(self, mock_coordinator):
        """Test successful oscillation turn on."""
        # Arrange
        switch = DysonOscillationSwitch(mock_coordinator)
        mock_coordinator.device.set_oscillation = AsyncMock()

        # Act
        await switch.async_turn_on()

        # Assert
        mock_coordinator.device.set_oscillation.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_async_turn_off_success(self, mock_coordinator):
        """Test successful oscillation turn off."""
        # Arrange
        switch = DysonOscillationSwitch(mock_coordinator)
        mock_coordinator.device.set_oscillation = AsyncMock()

        # Act
        await switch.async_turn_off()

        # Assert
        mock_coordinator.device.set_oscillation.assert_called_once_with(False)

    def test_extra_state_attributes_with_device(self, mock_coordinator):
        """Test extra_state_attributes when device is available."""
        # Arrange
        switch = DysonOscillationSwitch(mock_coordinator)
        mock_coordinator.device._get_current_value.side_effect = (
            lambda state, key, default: {
                "osal": "0045",
                "osau": "0315",
            }.get(key, default)
        )

        # Act
        attributes = switch.extra_state_attributes

        # Assert
        assert attributes is not None
        assert "oscillation_enabled" in attributes
        assert "oscillation_angle_low" in attributes
        assert "oscillation_angle_high" in attributes
        assert attributes["oscillation_angle_low"] == 45
        assert attributes["oscillation_angle_high"] == 315

    def test_extra_state_attributes_without_device(self, mock_coordinator):
        """Test extra_state_attributes when no device is available."""
        # Arrange
        mock_coordinator.device = None
        switch = DysonOscillationSwitch(mock_coordinator)

        # Act
        attributes = switch.extra_state_attributes

        # Assert
        assert attributes is None


class TestDysonHeatingSwitch:
    """Test DysonHeatingSwitch class."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        switch = DysonHeatingSwitch(mock_coordinator)

        # Assert
        assert switch.coordinator == mock_coordinator
        assert switch._attr_unique_id == "TEST-SERIAL-123_heating"
        assert switch._attr_translation_key == "heating"
        assert switch._attr_icon == "mdi:radiator"

    def test_handle_coordinator_update_heating_on(self, mock_coordinator):
        """Test coordinator update when heating is on."""
        # Arrange
        switch = DysonHeatingSwitch(mock_coordinator)
        mock_coordinator.device._get_current_value.return_value = "HEAT"

        with patch.object(switch, "async_write_ha_state"):
            # Act
            switch._handle_coordinator_update()

            # Assert
            assert switch._attr_is_on is True
            mock_coordinator.device._get_current_value.assert_called_with(
                mock_coordinator.data["product-state"], "hmod", "OFF"
            )

    def test_handle_coordinator_update_heating_off(self, mock_coordinator):
        """Test coordinator update when heating is off."""
        # Arrange
        switch = DysonHeatingSwitch(mock_coordinator)
        mock_coordinator.device._get_current_value.return_value = "OFF"

        with patch.object(switch, "async_write_ha_state"):
            # Act
            switch._handle_coordinator_update()

            # Assert
            assert switch._attr_is_on is False

    @pytest.mark.asyncio
    async def test_async_turn_on_success(self, mock_coordinator):
        """Test successful heating turn on."""
        # Arrange
        mock_coordinator.device.set_heating_mode = AsyncMock()
        switch = DysonHeatingSwitch(mock_coordinator)

        # Act
        await switch.async_turn_on()

        # Assert
        mock_coordinator.device.set_heating_mode.assert_called_once_with("HEAT")

    @pytest.mark.asyncio
    async def test_async_turn_off_success(self, mock_coordinator):
        """Test successful heating turn off."""
        # Arrange
        mock_coordinator.device.set_heating_mode = AsyncMock()
        switch = DysonHeatingSwitch(mock_coordinator)

        # Act
        await switch.async_turn_off()

        # Assert
        mock_coordinator.device.set_heating_mode.assert_called_once_with("OFF")

    def test_extra_state_attributes_with_device(self, mock_coordinator):
        """Test extra_state_attributes when device is available."""
        # Arrange
        switch = DysonHeatingSwitch(mock_coordinator)
        mock_coordinator.device._get_current_value.side_effect = (
            lambda state, key, default: {"hmax": "2980"}.get(key, default)
        )

        # Act
        attributes = switch.extra_state_attributes

        # Assert
        assert attributes is not None
        assert "heating_mode" in attributes
        assert "heating_enabled" in attributes
        assert "target_temperature" in attributes
        assert "target_temperature_kelvin" in attributes


class TestDysonContinuousMonitoringSwitch:
    """Test DysonContinuousMonitoringSwitch class."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        switch = DysonContinuousMonitoringSwitch(mock_coordinator)

        # Assert
        assert switch.coordinator == mock_coordinator
        assert switch._attr_unique_id == "TEST-SERIAL-123_continuous_monitoring"
        assert switch._attr_translation_key == "continuous_monitoring"
        assert switch._attr_icon == "mdi:monitor-eye"
        from homeassistant.const import EntityCategory

        assert switch._attr_entity_category == EntityCategory.CONFIG

    def test_handle_coordinator_update_monitoring_on(self, mock_coordinator):
        """Test coordinator update when continuous monitoring is on."""
        # Arrange
        switch = DysonContinuousMonitoringSwitch(mock_coordinator)
        mock_coordinator.device._get_current_value.return_value = "ON"

        with patch.object(switch, "async_write_ha_state"):
            # Act
            switch._handle_coordinator_update()

            # Assert
            assert switch._attr_is_on is True
            mock_coordinator.device._get_current_value.assert_called_with(
                mock_coordinator.data["product-state"], "rhtm", "OFF"
            )

    @pytest.mark.asyncio
    async def test_async_turn_on_success(self, mock_coordinator):
        """Test successful continuous monitoring turn on."""
        # Arrange
        mock_coordinator.device.set_continuous_monitoring = AsyncMock()
        switch = DysonContinuousMonitoringSwitch(mock_coordinator)

        # Act
        await switch.async_turn_on()

        # Assert
        mock_coordinator.device.set_continuous_monitoring.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_async_turn_off_success(self, mock_coordinator):
        """Test successful continuous monitoring turn off."""
        # Arrange
        mock_coordinator.device.set_continuous_monitoring = AsyncMock()
        switch = DysonContinuousMonitoringSwitch(mock_coordinator)

        # Act
        await switch.async_turn_off()

        # Assert
        mock_coordinator.device.set_continuous_monitoring.assert_called_once_with(False)


class TestSwitchIntegration:
    """Test switch platform integration scenarios."""

    def test_all_switch_types_inherit_correctly(self, mock_coordinator):
        """Test that all switch entities inherit from correct base classes."""
        switches = [
            DysonAutoModeSwitch(mock_coordinator),
            DysonNightModeSwitch(mock_coordinator),
            DysonOscillationSwitch(mock_coordinator),
            DysonHeatingSwitch(mock_coordinator),
            DysonContinuousMonitoringSwitch(mock_coordinator),
        ]

        for switch in switches:
            assert isinstance(switch, SwitchEntity)
            from custom_components.hass_dyson.entity import DysonEntity

            assert isinstance(switch, DysonEntity)

    @pytest.mark.asyncio
    async def test_multiple_capabilities_creates_multiple_switches(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Test that multiple capabilities create multiple switches."""
        # Arrange
        mock_coordinator.device_capabilities = ["Heating", "EnvironmentalData"]
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator
        mock_add_entities = MagicMock()

        # Act
        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        # Assert
        added_entities = mock_add_entities.call_args[0][0]
        assert len(added_entities) == 3  # Night mode + heating + continuous monitoring

        entity_types = [type(entity).__name__ for entity in added_entities]
        assert "DysonNightModeSwitch" in entity_types
        assert "DysonHeatingSwitch" in entity_types
        assert "DysonContinuousMonitoringSwitch" in entity_types

    def test_switch_state_consistency_across_updates(self, mock_coordinator):
        """Test that switch state remains consistent across multiple updates."""
        # Arrange
        switch = DysonNightModeSwitch(mock_coordinator)
        mock_coordinator.device._get_current_value.return_value = "ON"

        with patch.object(switch, "async_write_ha_state"):
            # Act - call update multiple times
            switch._handle_coordinator_update()
            first_state = switch._attr_is_on

            switch._handle_coordinator_update()
            second_state = switch._attr_is_on

            # Assert - state should be consistent
            assert first_state == second_state
            assert first_state is True
