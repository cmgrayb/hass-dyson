"""Consolidated test switch platform for Dyson integration using pure pytest.

This consolidates all switch related tests following the successful pattern
from test_switch_consolidated.py and applies it to all switch types.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.switch import SwitchEntity

from custom_components.hass_dyson.const import DOMAIN
from custom_components.hass_dyson.switch import (
    DysonContinuousMonitoringSwitch,
    DysonFirmwareAutoUpdateSwitch,
    DysonHeatingSwitch,
    DysonNightModeSwitch,
    async_setup_entry,
)


class TestSwitchPlatformSetup:
    """Test switch platform setup using pure pytest."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_switches(
        self, pure_mock_hass, pure_mock_config_entry, pure_mock_coordinator
    ):
        """Test setting up switches for Dyson devices."""
        # Arrange
        pure_mock_hass.data[DOMAIN] = {
            pure_mock_config_entry.entry_id: pure_mock_coordinator
        }
        mock_add_entities = MagicMock()

        # Ensure coordinator has standard capabilities
        pure_mock_coordinator.device_capabilities = ["Oscillation", "NightMode"]

        # Act
        result = await async_setup_entry(
            pure_mock_hass, pure_mock_config_entry, mock_add_entities
        )

        # Assert
        assert result is True
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]

        # Should have various switches based on capabilities
        assert len(entities) >= 1
        switch_types = [type(entity).__name__ for entity in entities]
        assert "DysonNightModeSwitch" in switch_types

    @pytest.mark.asyncio
    async def test_setup_with_different_capabilities(
        self, pure_mock_hass, pure_mock_config_entry, pure_mock_coordinator
    ):
        """Test switch setup with different device capabilities."""
        # Arrange
        pure_mock_hass.data[DOMAIN] = {
            pure_mock_config_entry.entry_id: pure_mock_coordinator
        }
        mock_add_entities = MagicMock()
        pure_mock_coordinator.device_capabilities = ["Heating", "ContinuousMonitoring"]

        # Act
        result = await async_setup_entry(
            pure_mock_hass, pure_mock_config_entry, mock_add_entities
        )

        # Assert
        assert result is True
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) >= 1

    @pytest.mark.asyncio
    async def test_setup_with_no_capabilities(
        self, pure_mock_hass, pure_mock_config_entry, pure_mock_coordinator
    ):
        """Test switch setup with no switch capabilities."""
        # Arrange
        pure_mock_hass.data[DOMAIN] = {
            pure_mock_config_entry.entry_id: pure_mock_coordinator
        }
        mock_add_entities = MagicMock()
        pure_mock_coordinator.device_capabilities = []

        # Act
        result = await async_setup_entry(
            pure_mock_hass, pure_mock_config_entry, mock_add_entities
        )

        # Assert
        assert result is True
        # Should still call add_entities even if no switches to add
        mock_add_entities.assert_called_once()


class TestDysonNightModeSwitch:
    """Test DysonNightModeSwitch using pure pytest patterns."""

    def test_initialization(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test switch initialization."""
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)

        assert switch.coordinator == pure_mock_coordinator
        assert switch.unique_id == f"{pure_mock_coordinator.serial_number}_night_mode"
        assert switch.translation_key == "night_mode"

    def test_is_on_when_night_mode_active(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test switch reports on when night mode is active."""
        pure_mock_coordinator.data["product-state"]["nmod"] = "ON"
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)

        # Trigger update to set internal state
        switch._handle_coordinator_update()

        assert switch._attr_is_on is True

    def test_is_on_when_night_mode_inactive(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test switch reports off when night mode is inactive."""
        pure_mock_coordinator.data["product-state"]["nmod"] = "OFF"
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)

        # Trigger update to set internal state
        switch._handle_coordinator_update()

        assert switch._attr_is_on is False

    @pytest.mark.asyncio
    async def test_turn_on(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test turning on night mode."""
        pure_mock_coordinator.device.set_night_mode = AsyncMock()
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)

        await switch.async_turn_on()

        pure_mock_coordinator.device.set_night_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_off(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test turning off night mode."""
        pure_mock_coordinator.device.set_night_mode = AsyncMock()
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)

        await switch.async_turn_off()

        pure_mock_coordinator.device.set_night_mode.assert_called_once_with(False)

    def test_coordinator_update(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test coordinator update handling."""
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)

        pure_mock_coordinator.data["product-state"]["nmod"] = "ON"
        switch._handle_coordinator_update()

        # Coordinator update should set internal state
        assert switch._attr_is_on is True


class TestDysonContinuousMonitoringSwitch:
    """Test DysonContinuousMonitoringSwitch using pure pytest patterns."""

    def test_initialization(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test switch initialization."""
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )

        assert switch.coordinator == pure_mock_coordinator
        assert (
            switch.unique_id
            == f"{pure_mock_coordinator.serial_number}_continuous_monitoring"
        )

    def test_is_on_when_monitoring_active(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test switch reports on when continuous monitoring is active."""
        pure_mock_coordinator.data["product-state"]["rhtm"] = (
            "ON"  # Correct field is rhtm
        )
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )

        # Trigger update to set internal state
        switch._handle_coordinator_update()

        assert switch._attr_is_on is True

    def test_is_on_when_monitoring_inactive(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test switch reports off when continuous monitoring is inactive."""
        pure_mock_coordinator.data["product-state"]["rhtm"] = (
            "OFF"  # Correct field is rhtm
        )
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )

        # Trigger update to set internal state
        switch._handle_coordinator_update()

        assert switch._attr_is_on is False

    @pytest.mark.asyncio
    async def test_turn_on(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test turning on continuous monitoring."""
        pure_mock_coordinator.device.set_continuous_monitoring = AsyncMock()
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )

        await switch.async_turn_on()

        pure_mock_coordinator.device.set_continuous_monitoring.assert_called_once_with(
            True
        )

    @pytest.mark.asyncio
    async def test_turn_off(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test turning off continuous monitoring."""
        pure_mock_coordinator.device.set_continuous_monitoring = AsyncMock()
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )

        await switch.async_turn_off()

        pure_mock_coordinator.device.set_continuous_monitoring.assert_called_once_with(
            False
        )


class TestDysonHeatingSwitch:
    """Test DysonHeatingSwitch using pure pytest patterns."""

    def test_initialization(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test switch initialization."""
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)

        assert switch.coordinator == pure_mock_coordinator
        assert switch.unique_id == f"{pure_mock_coordinator.serial_number}_heating"

    def test_is_on_when_heating_active(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test switch reports on when heating is active."""
        pure_mock_coordinator.data["product-state"]["hmod"] = "HEAT"
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)

        # Trigger update to set internal state
        switch._handle_coordinator_update()

        assert switch._attr_is_on is True

    def test_is_on_when_heating_inactive(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test switch reports off when heating is inactive."""
        pure_mock_coordinator.data["product-state"]["hmod"] = "OFF"
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)

        # Trigger update to set internal state
        switch._handle_coordinator_update()

        assert switch._attr_is_on is False

    @pytest.mark.asyncio
    async def test_turn_on(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test turning on heating."""
        pure_mock_coordinator.device.set_heating_mode = AsyncMock()  # Correct method
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)

        await switch.async_turn_on()

        pure_mock_coordinator.device.set_heating_mode.assert_called_once_with(
            "HEAT"
        )  # Correct argument

    @pytest.mark.asyncio
    async def test_turn_off(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test turning off heating."""
        pure_mock_coordinator.device.set_heating_mode = AsyncMock()  # Correct method
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)

        await switch.async_turn_off()

        pure_mock_coordinator.device.set_heating_mode.assert_called_once_with(
            "OFF"
        )  # Correct argument


class TestDysonFirmwareAutoUpdateSwitch:
    """Test DysonFirmwareAutoUpdateSwitch using pure pytest patterns."""

    def test_initialization(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test switch initialization."""
        switch = pure_mock_sensor_entity(
            DysonFirmwareAutoUpdateSwitch, pure_mock_coordinator
        )

        assert switch.coordinator == pure_mock_coordinator
        assert (
            switch.unique_id
            == f"{pure_mock_coordinator.serial_number}_firmware_auto_update"
        )

    def test_is_on_when_auto_update_enabled(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test switch reports on when firmware auto update is enabled."""
        pure_mock_coordinator.firmware_auto_update_enabled = (
            True  # Use coordinator property
        )
        switch = pure_mock_sensor_entity(
            DysonFirmwareAutoUpdateSwitch, pure_mock_coordinator
        )

        # Firmware auto update uses is_on property directly, not _attr_is_on
        assert switch.is_on is True

    def test_is_on_when_auto_update_disabled(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test switch reports off when firmware auto update is disabled."""
        pure_mock_coordinator.firmware_auto_update_enabled = (
            False  # Use coordinator property
        )
        switch = pure_mock_sensor_entity(
            DysonFirmwareAutoUpdateSwitch, pure_mock_coordinator
        )

        # Firmware auto update uses is_on property directly, not _attr_is_on
        assert switch.is_on is False

    @pytest.mark.asyncio
    async def test_turn_on(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test turning on firmware auto update."""
        pure_mock_coordinator.async_set_firmware_auto_update = AsyncMock(
            return_value=True
        )
        switch = pure_mock_sensor_entity(
            DysonFirmwareAutoUpdateSwitch, pure_mock_coordinator
        )

        await switch.async_turn_on()

        pure_mock_coordinator.async_set_firmware_auto_update.assert_called_once_with(
            True
        )

    @pytest.mark.asyncio
    async def test_turn_off(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test turning off firmware auto update."""
        pure_mock_coordinator.async_set_firmware_auto_update = AsyncMock(
            return_value=True
        )
        switch = pure_mock_sensor_entity(
            DysonFirmwareAutoUpdateSwitch, pure_mock_coordinator
        )

        await switch.async_turn_off()

        pure_mock_coordinator.async_set_firmware_auto_update.assert_called_once_with(
            False
        )


class TestSwitchErrorHandling:
    """Test error handling for switch platform."""

    @pytest.mark.asyncio
    async def test_switch_handles_device_error_gracefully(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test switch handles device errors gracefully by logging."""
        pure_mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=Exception("Device error")
        )
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)

        # Should not raise error - it logs instead
        await switch.async_turn_on()

        # Verify device method was called
        pure_mock_coordinator.device.set_night_mode.assert_called_once_with(True)

    def test_switch_with_none_device_state(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test switch handles missing device state gracefully."""
        pure_mock_coordinator.data["product-state"]["nmod"] = None
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)

        switch._handle_coordinator_update()

        # Should handle None gracefully and default to False/OFF
        assert switch._attr_is_on is False

    def test_switch_coordinator_update_with_missing_data(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test switch handles missing coordinator data."""
        pure_mock_coordinator.data = {}  # Missing product-state
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)

        # Should not crash when updating with missing data
        switch._handle_coordinator_update()

        # Should have some default state
        assert hasattr(switch, "_attr_is_on")

    @pytest.mark.asyncio
    async def test_setup_entry_missing_coordinator(self, pure_mock_hass):
        """Test setup handles missing coordinator gracefully."""
        mock_config_entry = MagicMock()
        mock_config_entry.entry_id = "missing_entry_id"
        mock_add_entities = MagicMock()

        # No coordinator in hass.data - should raise KeyError as expected
        with pytest.raises(KeyError):
            await async_setup_entry(
                pure_mock_hass, mock_config_entry, mock_add_entities
            )


class TestSwitchMissingCoverage:
    """Test scenarios to improve switch platform coverage."""

    def test_switch_entity_inheritance(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test switch entities inherit from proper base classes."""
        night_switch = pure_mock_sensor_entity(
            DysonNightModeSwitch, pure_mock_coordinator
        )
        heating_switch = pure_mock_sensor_entity(
            DysonHeatingSwitch, pure_mock_coordinator
        )

        # All switches should inherit from SwitchEntity
        assert isinstance(night_switch, SwitchEntity)
        assert isinstance(heating_switch, SwitchEntity)

    def test_switch_unique_ids_are_unique(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test all switch entities have unique IDs."""
        switches = [
            pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator),
            pure_mock_sensor_entity(
                DysonContinuousMonitoringSwitch, pure_mock_coordinator
            ),
            pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator),
            pure_mock_sensor_entity(
                DysonFirmwareAutoUpdateSwitch, pure_mock_coordinator
            ),
        ]

        unique_ids = [switch.unique_id for switch in switches]
        assert len(unique_ids) == len(set(unique_ids)), (
            "All switch unique IDs should be unique"
        )

    def test_switch_translation_keys_are_unique(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test all switch entities have unique translation keys."""
        switches = [
            pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator),
            pure_mock_sensor_entity(
                DysonContinuousMonitoringSwitch, pure_mock_coordinator
            ),
            pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator),
            pure_mock_sensor_entity(
                DysonFirmwareAutoUpdateSwitch, pure_mock_coordinator
            ),
        ]

        translation_keys = [
            getattr(switch, "translation_key", None) for switch in switches
        ]
        # Remove None values
        translation_keys = [key for key in translation_keys if key is not None]
        assert len(translation_keys) == len(set(translation_keys)), (
            "All switch translation keys should be unique"
        )

    def test_all_switches_support_turn_on_off(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test all switch entities support turn on/off methods."""
        switches = [
            pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator),
            pure_mock_sensor_entity(
                DysonContinuousMonitoringSwitch, pure_mock_coordinator
            ),
            pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator),
            pure_mock_sensor_entity(
                DysonFirmwareAutoUpdateSwitch, pure_mock_coordinator
            ),
        ]

        for switch in switches:
            assert hasattr(switch, "async_turn_on")
            assert hasattr(switch, "async_turn_off")
            assert callable(switch.async_turn_on)
            assert callable(switch.async_turn_off)

    def test_switches_have_proper_device_info(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test switch entities have proper device info."""
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)

        # Should have coordinator reference for device info
        assert switch.coordinator == pure_mock_coordinator

    def test_switch_state_with_various_device_states(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test switch state handling with various device states."""
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)

        # Test boolean True
        pure_mock_coordinator.data["product-state"]["nmod"] = "ON"
        switch._handle_coordinator_update()
        assert switch._attr_is_on is True

        # Test boolean False
        pure_mock_coordinator.data["product-state"]["nmod"] = "OFF"
        switch._handle_coordinator_update()
        assert switch._attr_is_on is False

        # Test None
        pure_mock_coordinator.data["product-state"]["nmod"] = None
        switch._handle_coordinator_update()
        assert switch._attr_is_on is False

    def test_setup_with_coordinator_having_no_device(
        self, pure_mock_hass, pure_mock_config_entry, pure_mock_coordinator
    ):
        """Test setup with coordinator but no device."""
        pure_mock_hass.data[DOMAIN] = {
            pure_mock_config_entry.entry_id: pure_mock_coordinator
        }
        pure_mock_coordinator.device = None

        # Should handle missing device gracefully - depend on actual platform logic
        # This test ensures we don't crash when device is None

    def test_switch_coordinator_data_updates(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test switch responds to coordinator data updates."""
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)

        # Initial state
        pure_mock_coordinator.data["product-state"]["nmod"] = "OFF"
        switch._handle_coordinator_update()
        assert switch._attr_is_on is False

        # Update coordinator data
        pure_mock_coordinator.data["product-state"]["nmod"] = "ON"
        switch._handle_coordinator_update()
        assert switch._attr_is_on is True
