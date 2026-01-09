"""Test humidifier platform for Dyson integration using pure pytest."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hass_dyson.const import DOMAIN
from custom_components.hass_dyson.humidifier import (
    MODE_AUTO,
    MODE_NORMAL,
    DysonHumidifierEntity,
    async_setup_entry,
)


class TestHumidifierPlatformSetup:
    """Test humidifier platform setup using pure pytest."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_humidifier(
        self, pure_mock_hass, pure_mock_config_entry, pure_mock_coordinator
    ):
        """Test setting up humidifier for Dyson devices with Humidifier capability."""
        # Arrange
        pure_mock_hass.data[DOMAIN] = {
            pure_mock_config_entry.entry_id: pure_mock_coordinator
        }
        mock_add_entities = MagicMock()
        pure_mock_coordinator.device_capabilities = ["Humidifier"]

        # Act
        result = await async_setup_entry(
            pure_mock_hass, pure_mock_config_entry, mock_add_entities
        )

        # Assert
        assert result is None  # async_setup_entry doesn't return a value
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DysonHumidifierEntity)

    @pytest.mark.asyncio
    async def test_setup_without_humidifier_capability(
        self, pure_mock_hass, pure_mock_config_entry, pure_mock_coordinator
    ):
        """Test no humidifier entity created without Humidifier capability."""
        # Arrange
        pure_mock_hass.data[DOMAIN] = {
            pure_mock_config_entry.entry_id: pure_mock_coordinator
        }
        mock_add_entities = MagicMock()
        pure_mock_coordinator.device_capabilities = ["Heating"]

        # Act
        await async_setup_entry(
            pure_mock_hass, pure_mock_config_entry, mock_add_entities
        )

        # Assert
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 0


class TestDysonHumidifierEntity:
    """Test DysonHumidifierEntity using pure pytest patterns."""

    def test_initialization(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test humidifier initialization."""
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        assert humidifier.coordinator == pure_mock_coordinator
        assert (
            humidifier.unique_id == f"{pure_mock_coordinator.serial_number}_humidifier"
        )
        assert humidifier.translation_key == "dyson_humidifier"
        assert humidifier.min_humidity == 30
        assert humidifier.max_humidity == 70
        assert MODE_NORMAL in humidifier.available_modes
        assert MODE_AUTO in humidifier.available_modes

    def test_update_state_normal_mode(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test state update when humidifier is in normal mode."""
        pure_mock_coordinator.data["product-state"] = {
            "hume": "HUMD",
            "haut": "OFF",
            "humi": "0045",
            "humt": "0040",
        }
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        humidifier._handle_coordinator_update()

        assert humidifier._attr_is_on is True
        assert humidifier._attr_mode == MODE_NORMAL
        assert humidifier._attr_current_humidity == 45
        assert humidifier._attr_target_humidity == 40

    def test_update_state_auto_mode(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test state update when humidifier is in auto mode."""
        pure_mock_coordinator.data["product-state"] = {
            "hume": "OFF",
            "haut": "ON",
            "humi": "0050",
            "humt": "0045",
        }
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        humidifier._handle_coordinator_update()

        assert humidifier._attr_is_on is True
        assert humidifier._attr_mode == MODE_AUTO
        assert humidifier._attr_current_humidity == 50
        assert humidifier._attr_target_humidity == 45

    def test_update_state_off(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test state update when humidifier is off."""
        pure_mock_coordinator.data["product-state"] = {
            "hume": "OFF",
            "haut": "OFF",
            "humi": "0042",
            "humt": "0040",
        }
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        humidifier._handle_coordinator_update()

        assert humidifier._attr_is_on is False
        assert humidifier._attr_mode is None

    def test_update_humidity_invalid_data(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test humidity update with invalid data."""
        pure_mock_coordinator.data["product-state"] = {
            "hume": "HUMD",
            "haut": "OFF",
            "humi": "0000",  # Invalid
            "humt": "0000",  # Invalid
        }
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        humidifier._handle_coordinator_update()

        assert humidifier._attr_current_humidity is None
        assert humidifier._attr_target_humidity == 40  # Default

    @pytest.mark.asyncio
    async def test_turn_on(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test turning on humidifier."""
        pure_mock_coordinator.device.set_humidifier_mode = AsyncMock()
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        await humidifier.async_turn_on()

        pure_mock_coordinator.device.set_humidifier_mode.assert_called_once_with(
            enabled=True, auto_mode=False
        )
        assert humidifier._attr_is_on is True
        assert humidifier._attr_mode == MODE_NORMAL

    @pytest.mark.asyncio
    async def test_turn_off(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test turning off humidifier."""
        pure_mock_coordinator.device.set_humidifier_mode = AsyncMock()
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        await humidifier.async_turn_off()

        pure_mock_coordinator.device.set_humidifier_mode.assert_called_once_with(
            enabled=False, auto_mode=False
        )
        assert humidifier._attr_is_on is False
        assert humidifier._attr_mode is None

    @pytest.mark.asyncio
    async def test_set_humidity(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test setting target humidity."""
        pure_mock_coordinator.device.set_target_humidity = AsyncMock()
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        await humidifier.async_set_humidity(44)

        pure_mock_coordinator.device.set_target_humidity.assert_called_once_with(40)
        assert humidifier._attr_target_humidity == 40

    @pytest.mark.asyncio
    async def test_set_mode_normal(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test setting mode to normal."""
        pure_mock_coordinator.device.set_humidifier_mode = AsyncMock()
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        await humidifier.async_set_mode(MODE_NORMAL)

        pure_mock_coordinator.device.set_humidifier_mode.assert_called_once_with(
            enabled=True, auto_mode=False
        )
        assert humidifier._attr_mode == MODE_NORMAL
        assert humidifier._attr_is_on is True

    @pytest.mark.asyncio
    async def test_set_mode_auto(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test setting mode to auto."""
        pure_mock_coordinator.device.set_humidifier_mode = AsyncMock()
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        await humidifier.async_set_mode(MODE_AUTO)

        pure_mock_coordinator.device.set_humidifier_mode.assert_called_once_with(
            enabled=True, auto_mode=True
        )
        assert humidifier._attr_mode == MODE_AUTO
        assert humidifier._attr_is_on is True

    @pytest.mark.asyncio
    async def test_set_mode_invalid(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test setting invalid mode."""
        pure_mock_coordinator.device.set_humidifier_mode = AsyncMock()
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        await humidifier.async_set_mode("invalid_mode")

        # Should not call set_humidifier_mode for invalid mode
        pure_mock_coordinator.device.set_humidifier_mode.assert_not_called()

    @pytest.mark.asyncio
    async def test_turn_on_communication_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test turn on with communication error."""
        pure_mock_coordinator.device.set_humidifier_mode = AsyncMock(
            side_effect=ConnectionError("Connection failed")
        )
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        await humidifier.async_turn_on()

        # Should handle error gracefully
        pure_mock_coordinator.device.set_humidifier_mode.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_humidity_communication_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test set humidity with communication error."""
        pure_mock_coordinator.device.set_target_humidity = AsyncMock(
            side_effect=TimeoutError("Timeout")
        )
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        await humidifier.async_set_humidity(45)

        # Should handle error gracefully
        pure_mock_coordinator.device.set_target_humidity.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_humidity_value_error(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test set humidity with value error."""
        pure_mock_coordinator.device.set_target_humidity = AsyncMock(
            side_effect=ValueError("Invalid humidity value")
        )
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        await humidifier.async_set_humidity(100)  # Out of range

        # Should handle error gracefully
        pure_mock_coordinator.device.set_target_humidity.assert_called_once()

    def test_extra_state_attributes(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test extra state attributes."""
        pure_mock_coordinator.data["product-state"] = {
            "hume": "HUMD",
            "haut": "OFF",
            "humi": "0045",
            "humt": "0040",
        }
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        attributes = humidifier.extra_state_attributes

        assert attributes is not None
        assert attributes["humidity_enabled_raw"] == "HUMD"
        assert attributes["humidity_auto_raw"] == "OFF"
        assert attributes["current_humidity_raw"] == "0045"
        assert attributes["target_humidity_raw"] == "0040"

    def test_handle_coordinator_update_no_device(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test coordinator update with no device."""
        pure_mock_coordinator.device = None
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        # Should not raise exception
        humidifier._handle_coordinator_update()


class TestHumidifierEdgeCases:
    """Test edge cases for humidifier entity."""

    def test_humidity_value_boundaries(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test humidity values at boundaries."""
        # Test minimum humidity
        pure_mock_coordinator.data["product-state"] = {
            "hume": "HUMD",
            "haut": "OFF",
            "humi": "0030",
            "humt": "0030",
        }
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        humidifier._handle_coordinator_update()

        assert humidifier._attr_current_humidity == 30
        assert humidifier._attr_target_humidity == 30

        # Test maximum humidity
        pure_mock_coordinator.data["product-state"] = {
            "hume": "HUMD",
            "haut": "OFF",
            "humi": "0050",
            "humt": "0050",
        }

        humidifier._handle_coordinator_update()

        assert humidifier._attr_current_humidity == 50
        assert humidifier._attr_target_humidity == 50

    def test_both_modes_enabled(self, pure_mock_coordinator, pure_mock_sensor_entity):
        """Test state when both manual and auto modes are reported as enabled."""
        # This shouldn't happen in reality, but test priority
        pure_mock_coordinator.data["product-state"] = {
            "hume": "HUMD",
            "haut": "ON",
            "humi": "0045",
            "humt": "0040",
        }
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        humidifier._handle_coordinator_update()

        # Auto mode should take priority
        assert humidifier._attr_is_on is True
        assert humidifier._attr_mode == MODE_AUTO

    @pytest.mark.asyncio
    async def test_turn_on_no_device(
        self, pure_mock_coordinator, pure_mock_sensor_entity
    ):
        """Test turn on with no device."""
        pure_mock_coordinator.device = None
        humidifier = pure_mock_sensor_entity(
            DysonHumidifierEntity, pure_mock_coordinator
        )

        # Should not raise exception
        await humidifier.async_turn_on()
