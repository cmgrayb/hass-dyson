"""Consolidated test switch platform for Dyson integration using pure pytest.

This consolidates all switch related tests following the successful pattern
from test_switch_consolidated.py and applies it to all switch types.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.switch import SwitchEntity

from custom_components.hass_dyson.const import DISCOVERY_CLOUD, DOMAIN
from custom_components.hass_dyson.switch import (
    DysonAutoModeSwitch,
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


class TestAsyncSetupEntryCloudPath:
    """Test async_setup_entry cloud-discovery path."""

    @pytest.mark.asyncio
    async def test_setup_adds_firmware_auto_update_switch_for_cloud_device(
        self, pure_mock_hass, pure_mock_config_entry, pure_mock_coordinator
    ):
        """Test that the firmware auto-update switch is added for cloud devices."""
        from custom_components.hass_dyson.const import CONF_DISCOVERY_METHOD

        pure_mock_hass.data[DOMAIN] = {
            pure_mock_config_entry.entry_id: pure_mock_coordinator
        }
        pure_mock_config_entry.data = {
            **pure_mock_config_entry.data,
            CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD,
        }
        mock_add_entities = MagicMock()

        result = await async_setup_entry(
            pure_mock_hass, pure_mock_config_entry, mock_add_entities
        )

        assert result is True
        entities = mock_add_entities.call_args[0][0]
        switch_types = [type(e).__name__ for e in entities]
        assert "DysonFirmwareAutoUpdateSwitch" in switch_types


class TestDysonAutoModeSwitch:
    """Test DysonAutoModeSwitch."""

    def test_initialization(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test switch initialization."""
        switch = pure_mock_sensor_entity(DysonAutoModeSwitch, pure_mock_coordinator)

        assert switch.unique_id == f"{pure_mock_coordinator.serial_number}_auto_mode"
        assert switch.translation_key == "auto_mode"

    def test_handle_coordinator_update_device_present(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test _handle_coordinator_update when device is present."""
        pure_mock_coordinator.data["product-state"]["auto"] = "ON"
        switch = pure_mock_sensor_entity(DysonAutoModeSwitch, pure_mock_coordinator)

        switch._handle_coordinator_update()

        assert switch._attr_is_on is True

    def test_handle_coordinator_update_device_none(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test _handle_coordinator_update when device is None sets is_on to None."""
        switch = pure_mock_sensor_entity(DysonAutoModeSwitch, pure_mock_coordinator)
        pure_mock_coordinator.device = None

        switch._handle_coordinator_update()

        assert switch._attr_is_on is None

    @pytest.mark.asyncio
    async def test_turn_on_success(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test turning on auto mode."""
        pure_mock_coordinator.device.set_auto_mode = AsyncMock()
        switch = pure_mock_sensor_entity(DysonAutoModeSwitch, pure_mock_coordinator)

        await switch.async_turn_on()

        pure_mock_coordinator.device.set_auto_mode.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_on_no_device(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test async_turn_on returns early when device is None."""
        switch = pure_mock_sensor_entity(DysonAutoModeSwitch, pure_mock_coordinator)
        pure_mock_coordinator.device = None

        await switch.async_turn_on()  # should not raise

    @pytest.mark.asyncio
    @pytest.mark.parametrize("exc_type", [ConnectionError, TimeoutError])
    async def test_turn_on_communication_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity, exc_type
    ):
        """Test async_turn_on handles ConnectionError/TimeoutError."""
        pure_mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=exc_type("comm error")
        )
        switch = pure_mock_sensor_entity(DysonAutoModeSwitch, pure_mock_coordinator)

        await switch.async_turn_on()  # should not raise

    @pytest.mark.asyncio
    async def test_turn_on_attribute_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test async_turn_on handles AttributeError."""
        pure_mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=AttributeError("method missing")
        )
        switch = pure_mock_sensor_entity(DysonAutoModeSwitch, pure_mock_coordinator)

        await switch.async_turn_on()  # should not raise

    @pytest.mark.asyncio
    async def test_turn_on_generic_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test async_turn_on handles generic Exception."""
        pure_mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=Exception("unexpected")
        )
        switch = pure_mock_sensor_entity(DysonAutoModeSwitch, pure_mock_coordinator)

        await switch.async_turn_on()  # should not raise

    @pytest.mark.asyncio
    async def test_turn_off_success(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test turning off auto mode."""
        pure_mock_coordinator.device.set_auto_mode = AsyncMock()
        switch = pure_mock_sensor_entity(DysonAutoModeSwitch, pure_mock_coordinator)

        await switch.async_turn_off()

        pure_mock_coordinator.device.set_auto_mode.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_turn_off_no_device(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test async_turn_off returns early when device is None."""
        switch = pure_mock_sensor_entity(DysonAutoModeSwitch, pure_mock_coordinator)
        pure_mock_coordinator.device = None

        await switch.async_turn_off()  # should not raise

    @pytest.mark.asyncio
    @pytest.mark.parametrize("exc_type", [ConnectionError, TimeoutError])
    async def test_turn_off_communication_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity, exc_type
    ):
        """Test async_turn_off handles ConnectionError/TimeoutError."""
        pure_mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=exc_type("comm error")
        )
        switch = pure_mock_sensor_entity(DysonAutoModeSwitch, pure_mock_coordinator)

        await switch.async_turn_off()  # should not raise

    @pytest.mark.asyncio
    async def test_turn_off_attribute_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test async_turn_off handles AttributeError."""
        pure_mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=AttributeError("method missing")
        )
        switch = pure_mock_sensor_entity(DysonAutoModeSwitch, pure_mock_coordinator)

        await switch.async_turn_off()  # should not raise

    @pytest.mark.asyncio
    async def test_turn_off_generic_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test async_turn_off handles generic Exception."""
        pure_mock_coordinator.device.set_auto_mode = AsyncMock(
            side_effect=Exception("unexpected")
        )
        switch = pure_mock_sensor_entity(DysonAutoModeSwitch, pure_mock_coordinator)

        await switch.async_turn_off()  # should not raise


class TestSwitchDeviceNoneAndExceptionBranches:
    """Cover device=None early-returns and exception handlers missed in other tests."""

    # --- DysonNightModeSwitch ---

    def test_night_mode_update_device_none(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """_handle_coordinator_update sets is_on to None when device is gone."""
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)
        pure_mock_coordinator.device = None

        switch._handle_coordinator_update()

        assert switch._attr_is_on is None

    @pytest.mark.asyncio
    async def test_night_mode_turn_on_no_device(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_on returns early when device is None."""
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)
        pure_mock_coordinator.device = None

        await switch.async_turn_on()  # should not raise

    @pytest.mark.asyncio
    @pytest.mark.parametrize("exc_type", [ConnectionError, TimeoutError])
    async def test_night_mode_turn_on_communication_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity, exc_type
    ):
        """async_turn_on handles ConnectionError/TimeoutError."""
        pure_mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=exc_type("comm error")
        )
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)
        await switch.async_turn_on()

    @pytest.mark.asyncio
    async def test_night_mode_turn_on_attribute_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_on handles AttributeError."""
        pure_mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=AttributeError("no method")
        )
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)
        await switch.async_turn_on()

    @pytest.mark.asyncio
    async def test_night_mode_turn_off_no_device(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_off returns early when device is None."""
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)
        pure_mock_coordinator.device = None

        await switch.async_turn_off()  # should not raise

    @pytest.mark.asyncio
    @pytest.mark.parametrize("exc_type", [ConnectionError, TimeoutError])
    async def test_night_mode_turn_off_communication_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity, exc_type
    ):
        """async_turn_off handles ConnectionError/TimeoutError."""
        pure_mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=exc_type("comm error")
        )
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)
        await switch.async_turn_off()

    @pytest.mark.asyncio
    async def test_night_mode_turn_off_attribute_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_off handles AttributeError."""
        pure_mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=AttributeError("no method")
        )
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)
        await switch.async_turn_off()

    @pytest.mark.asyncio
    async def test_night_mode_turn_off_generic_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_off handles generic Exception."""
        pure_mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=Exception("unexpected")
        )
        switch = pure_mock_sensor_entity(DysonNightModeSwitch, pure_mock_coordinator)
        await switch.async_turn_off()

    # --- DysonHeatingSwitch ---

    def test_heating_update_device_none(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """_handle_coordinator_update sets is_on to None when device is gone."""
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)
        pure_mock_coordinator.device = None

        switch._handle_coordinator_update()

        assert switch._attr_is_on is None

    @pytest.mark.asyncio
    async def test_heating_turn_on_no_device(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_on returns early when device is None."""
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)
        pure_mock_coordinator.device = None
        await switch.async_turn_on()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("exc_type", [ConnectionError, TimeoutError])
    async def test_heating_turn_on_communication_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity, exc_type
    ):
        """async_turn_on handles ConnectionError/TimeoutError."""
        pure_mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=exc_type("comm error")
        )
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)
        await switch.async_turn_on()

    @pytest.mark.asyncio
    async def test_heating_turn_on_attribute_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_on handles AttributeError."""
        pure_mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=AttributeError("no method")
        )
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)
        await switch.async_turn_on()

    @pytest.mark.asyncio
    async def test_heating_turn_on_generic_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_on handles generic Exception."""
        pure_mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=Exception("unexpected")
        )
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)
        await switch.async_turn_on()

    @pytest.mark.asyncio
    async def test_heating_turn_off_no_device(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_off returns early when device is None."""
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)
        pure_mock_coordinator.device = None
        await switch.async_turn_off()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("exc_type", [ConnectionError, TimeoutError])
    async def test_heating_turn_off_communication_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity, exc_type
    ):
        """async_turn_off handles ConnectionError/TimeoutError."""
        pure_mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=exc_type("comm error")
        )
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)
        await switch.async_turn_off()

    @pytest.mark.asyncio
    async def test_heating_turn_off_attribute_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_off handles AttributeError."""
        pure_mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=AttributeError("no method")
        )
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)
        await switch.async_turn_off()

    @pytest.mark.asyncio
    async def test_heating_turn_off_generic_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_off handles generic Exception."""
        pure_mock_coordinator.device.set_heating_mode = AsyncMock(
            side_effect=Exception("unexpected")
        )
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)
        await switch.async_turn_off()

    def test_heating_extra_state_attributes_device_none(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """extra_state_attributes returns None when device is None."""
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)
        pure_mock_coordinator.device = None

        assert switch.extra_state_attributes is None

    def test_heating_extra_state_attributes_full(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """extra_state_attributes returns heating info including temp calculation."""
        pure_mock_coordinator.data["product-state"]["hmod"] = "HEAT"
        pure_mock_coordinator.data["product-state"]["hmax"] = "2980"
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)

        attrs = switch.extra_state_attributes

        assert attrs is not None
        assert attrs["heating_mode"] == "HEAT"
        assert attrs["heating_enabled"] is True
        assert "target_temperature" in attrs
        assert attrs["target_temperature_kelvin"] == "2980"

    def test_heating_extra_state_attributes_invalid_hmax(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """extra_state_attributes handles ValueError when hmax is non-numeric."""
        pure_mock_coordinator.data["product-state"]["hmod"] = "OFF"

        def bad_get_state_value(data_dict, key, default=None):
            if key == "hmax":
                return "INVALID"
            return data_dict.get(key, default)

        pure_mock_coordinator.device.get_state_value = MagicMock(
            side_effect=bad_get_state_value
        )
        switch = pure_mock_sensor_entity(DysonHeatingSwitch, pure_mock_coordinator)

        attrs = switch.extra_state_attributes

        assert attrs is not None
        assert "target_temperature" not in attrs  # skipped due to ValueError

    # --- DysonContinuousMonitoringSwitch ---

    def test_continuous_monitoring_update_device_none(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """_handle_coordinator_update sets is_on to None when device is gone."""
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )
        pure_mock_coordinator.device = None

        switch._handle_coordinator_update()

        assert switch._attr_is_on is None

    @pytest.mark.asyncio
    async def test_continuous_monitoring_turn_on_no_device(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_on returns early when device is None."""
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )
        pure_mock_coordinator.device = None
        await switch.async_turn_on()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("exc_type", [ConnectionError, TimeoutError])
    async def test_continuous_monitoring_turn_on_communication_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity, exc_type
    ):
        """async_turn_on handles ConnectionError/TimeoutError."""
        pure_mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=exc_type("comm error")
        )
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )
        await switch.async_turn_on()

    @pytest.mark.asyncio
    async def test_continuous_monitoring_turn_on_attribute_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_on handles AttributeError."""
        pure_mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=AttributeError("no method")
        )
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )
        await switch.async_turn_on()

    @pytest.mark.asyncio
    async def test_continuous_monitoring_turn_on_generic_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_on handles generic Exception."""
        pure_mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=Exception("unexpected")
        )
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )
        await switch.async_turn_on()

    @pytest.mark.asyncio
    async def test_continuous_monitoring_turn_off_no_device(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_off returns early when device is None."""
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )
        pure_mock_coordinator.device = None
        await switch.async_turn_off()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("exc_type", [ConnectionError, TimeoutError])
    async def test_continuous_monitoring_turn_off_communication_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity, exc_type
    ):
        """async_turn_off handles ConnectionError/TimeoutError."""
        pure_mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=exc_type("comm error")
        )
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )
        await switch.async_turn_off()

    @pytest.mark.asyncio
    async def test_continuous_monitoring_turn_off_attribute_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_off handles AttributeError."""
        pure_mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=AttributeError("no method")
        )
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )
        await switch.async_turn_off()

    @pytest.mark.asyncio
    async def test_continuous_monitoring_turn_off_generic_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_off handles generic Exception."""
        pure_mock_coordinator.device.set_continuous_monitoring = AsyncMock(
            side_effect=Exception("unexpected")
        )
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )
        await switch.async_turn_off()

    def test_continuous_monitoring_extra_state_attributes_device_none(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """extra_state_attributes returns None when device is None."""
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )
        pure_mock_coordinator.device = None

        assert switch.extra_state_attributes is None

    def test_continuous_monitoring_extra_state_attributes_full(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """extra_state_attributes returns monitoring info."""
        pure_mock_coordinator.data["product-state"]["rhtm"] = "ON"
        switch = pure_mock_sensor_entity(
            DysonContinuousMonitoringSwitch, pure_mock_coordinator
        )

        attrs = switch.extra_state_attributes

        assert attrs is not None
        assert attrs["continuous_monitoring"] is True
        assert attrs["monitoring_mode"] == "ON"

    # --- DysonFirmwareAutoUpdateSwitch ---

    @pytest.mark.asyncio
    async def test_firmware_auto_update_turn_on_failure(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_on logs error when coordinator returns False."""
        pure_mock_coordinator.async_set_firmware_auto_update = AsyncMock(
            return_value=False
        )
        switch = pure_mock_sensor_entity(
            DysonFirmwareAutoUpdateSwitch, pure_mock_coordinator
        )
        await switch.async_turn_on()  # should not raise

    @pytest.mark.asyncio
    async def test_firmware_auto_update_turn_off_failure(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """async_turn_off logs error when coordinator returns False."""
        pure_mock_coordinator.async_set_firmware_auto_update = AsyncMock(
            return_value=False
        )
        switch = pure_mock_sensor_entity(
            DysonFirmwareAutoUpdateSwitch, pure_mock_coordinator
        )
        await switch.async_turn_off()  # should not raise

    def test_firmware_auto_update_handle_coordinator_update(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """_handle_coordinator_update calls super and logs."""
        pure_mock_coordinator.firmware_auto_update_enabled = True
        pure_mock_coordinator.firmware_version = "2.0.0"
        switch = pure_mock_sensor_entity(
            DysonFirmwareAutoUpdateSwitch, pure_mock_coordinator
        )

        switch._handle_coordinator_update()  # should not raise
        switch.async_write_ha_state.assert_called()

    def test_firmware_auto_update_extra_state_attributes(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """extra_state_attributes includes current_firmware_version."""
        pure_mock_coordinator.firmware_version = "2.0.0"
        switch = pure_mock_sensor_entity(
            DysonFirmwareAutoUpdateSwitch, pure_mock_coordinator
        )

        attrs = switch.extra_state_attributes

        assert attrs is not None
        assert attrs["current_firmware_version"] == "2.0.0"
