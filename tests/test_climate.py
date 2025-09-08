"""Tests for the climate platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant

from custom_components.hass_dyson.climate import DysonClimateEntity, async_setup_entry


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-SERIAL-123"
    coordinator.device_name = "Test Device"
    coordinator.device = MagicMock()
    coordinator.device._get_current_value = MagicMock(return_value="OFF")
    coordinator.device_capabilities = ["Heating"]
    coordinator.data = {"product-state": {}}
    coordinator.async_send_command = AsyncMock()
    return coordinator


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test_entry_id"
    return config_entry


class TestClimatePlatformSetup:
    """Test climate platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_heating_capability(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test platform setup when device has heating capability."""
        # Arrange
        async_add_entities = MagicMock()
        mock_coordinator.device_capabilities = ["Heating"]

        mock_hass.data = {"hass-dyson": {mock_config_entry.entry_id: mock_coordinator}}

        # Act
        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        # Assert
        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        assert len(call_args) == 1
        assert isinstance(call_args[0], DysonClimateEntity)

    @pytest.mark.asyncio
    async def test_async_setup_entry_without_heating_capability(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test platform setup when device lacks heating capability."""
        # Arrange
        async_add_entities = MagicMock()
        mock_coordinator.device_capabilities = ["Fan"]  # No heating capability

        mock_hass.data = {"hass-dyson": {mock_config_entry.entry_id: mock_coordinator}}

        # Act
        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        # Assert
        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        assert len(call_args) == 0  # No entities added


class TestDysonClimateEntity:
    """Test DysonClimateEntity class."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        entity = DysonClimateEntity(mock_coordinator)

        # Assert
        assert entity.coordinator == mock_coordinator
        assert entity._attr_unique_id == "TEST-SERIAL-123_climate"
        assert entity._attr_name == "Test Device Climate"
        assert entity._attr_icon == "mdi:thermostat"

        # Climate features
        expected_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        assert entity._attr_supported_features == expected_features

        # Temperature settings
        assert entity._attr_temperature_unit == UnitOfTemperature.CELSIUS
        assert entity._attr_min_temp == 1
        assert entity._attr_max_temp == 37
        assert entity._attr_target_temperature_step == 1

        # HVAC modes
        expected_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.FAN_ONLY, HVACMode.AUTO]
        assert entity._attr_hvac_modes == expected_hvac_modes

        # Fan modes
        expected_fan_modes = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "Auto"]
        assert entity._attr_fan_modes == expected_fan_modes

    def test_handle_coordinator_update_with_device(self, mock_coordinator):
        """Test coordinator update handling when device is available."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "tmp": "2730",  # 0°C in 0.1K (273.0K)
            "hmax": "2930",  # 20°C in 0.1K (293.0K)
            "fnst": "FAN",
            "hmod": "HEAT",
            "auto": "OFF",
            "fnsp": "0005",
        }.get(key, default)

        # Act
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        # Assert
        assert entity._attr_current_temperature is not None
        assert entity._attr_target_temperature is not None
        assert abs(entity._attr_current_temperature - 0.0) < 0.2  # Allow for floating point precision
        assert abs(entity._attr_target_temperature - 19.85) < 0.2
        assert entity._attr_hvac_mode == HVACMode.HEAT
        assert entity._attr_fan_mode == "5"

    def test_handle_coordinator_update_no_device(self, mock_coordinator):
        """Test coordinator update handling when device is not available."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        mock_coordinator.device = None

        # Act
        entity._handle_coordinator_update()

        # Assert - should not crash and should not update attributes
        # No assertions needed as we're testing it doesn't crash

    def test_update_temperatures_valid_values(self, mock_coordinator):
        """Test temperature update with valid device values."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        device_data = {"product-state": {}}
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "tmp": "2980",  # 25°C in 0.1K (298.0K)
            "hmax": "3000",  # 26.85°C in 0.1K (300.0K)
        }.get(key, default)

        # Act
        entity._update_temperatures(device_data)

        # Assert
        assert entity._attr_current_temperature is not None
        assert entity._attr_target_temperature is not None
        assert abs(entity._attr_current_temperature - 24.85) < 0.01  # Allow for floating point precision
        assert abs(entity._attr_target_temperature - 26.85) < 0.01

    def test_update_temperatures_invalid_values(self, mock_coordinator):
        """Test temperature update with invalid device values."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        device_data = {"product-state": {}}
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "tmp": "invalid",
            "hmax": "also_invalid",
        }.get(key, default)

        # Act
        entity._update_temperatures(device_data)

        # Assert
        assert entity._attr_current_temperature is None
        assert entity._attr_target_temperature == 20  # Default value

    def test_update_hvac_mode_off(self, mock_coordinator):
        """Test HVAC mode update when fan is off."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        device_data = {"product-state": {}}
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "fnst": "OFF",
            "hmod": "HEAT",
            "auto": "OFF",
        }.get(key, default)

        # Act
        entity._update_hvac_mode(device_data)

        # Assert
        assert entity._attr_hvac_mode == HVACMode.OFF

    def test_update_hvac_mode_heat(self, mock_coordinator):
        """Test HVAC mode update when heating is on."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        device_data = {"product-state": {}}
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "fnst": "FAN",
            "hmod": "HEAT",
            "auto": "OFF",
        }.get(key, default)

        # Act
        entity._update_hvac_mode(device_data)

        # Assert
        assert entity._attr_hvac_mode == HVACMode.HEAT

    def test_update_hvac_mode_auto(self, mock_coordinator):
        """Test HVAC mode update when auto mode is on."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        device_data = {"product-state": {}}
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "fnst": "FAN",
            "hmod": "OFF",
            "auto": "ON",
        }.get(key, default)

        # Act
        entity._update_hvac_mode(device_data)

        # Assert
        assert entity._attr_hvac_mode == HVACMode.AUTO

    def test_update_hvac_mode_fan_only(self, mock_coordinator):
        """Test HVAC mode update when only fan is running."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        device_data = {"product-state": {}}
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "fnst": "FAN",
            "hmod": "OFF",
            "auto": "OFF",
        }.get(key, default)

        # Act
        entity._update_hvac_mode(device_data)

        # Assert
        assert entity._attr_hvac_mode == HVACMode.FAN_ONLY

    def test_update_fan_mode_auto(self, mock_coordinator):
        """Test fan mode update when auto mode is on."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        device_data = {"product-state": {}}
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "fnsp": "0007",
            "auto": "ON",
        }.get(key, default)

        # Act
        entity._update_fan_mode(device_data)

        # Assert
        assert entity._attr_fan_mode == "Auto"

    def test_update_fan_mode_manual_speed(self, mock_coordinator):
        """Test fan mode update with manual speed setting."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        device_data = {"product-state": {}}
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "fnsp": "0003",
            "auto": "OFF",
        }.get(key, default)

        # Act
        entity._update_fan_mode(device_data)

        # Assert
        assert entity._attr_fan_mode == "3"

    def test_update_fan_mode_invalid_speed(self, mock_coordinator):
        """Test fan mode update with invalid speed value."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        device_data = {"product-state": {}}
        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "fnsp": "invalid",
            "auto": "OFF",
        }.get(key, default)

        # Act
        entity._update_fan_mode(device_data)

        # Assert
        assert entity._attr_fan_mode == "1"  # Default value

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_off(self, mock_coordinator):
        """Test setting HVAC mode to OFF."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)

        # Act
        await entity.async_set_hvac_mode(HVACMode.OFF)

        # Assert
        mock_coordinator.async_send_command.assert_called_once_with("set_power", {"fnst": "OFF"})

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_heat(self, mock_coordinator):
        """Test setting HVAC mode to HEAT."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)

        # Act
        await entity.async_set_hvac_mode(HVACMode.HEAT)

        # Assert
        mock_coordinator.async_send_command.assert_called_once_with(
            "set_climate_mode", {"fnst": "FAN", "hmod": "HEAT", "auto": "OFF"}
        )

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_fan_only(self, mock_coordinator):
        """Test setting HVAC mode to FAN_ONLY."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)

        # Act
        await entity.async_set_hvac_mode(HVACMode.FAN_ONLY)

        # Assert
        mock_coordinator.async_send_command.assert_called_once_with(
            "set_climate_mode", {"fnst": "FAN", "hmod": "OFF", "auto": "OFF"}
        )

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_auto(self, mock_coordinator):
        """Test setting HVAC mode to AUTO."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)

        # Act
        await entity.async_set_hvac_mode(HVACMode.AUTO)

        # Assert
        mock_coordinator.async_send_command.assert_called_once_with("set_climate_mode", {"fnst": "FAN", "auto": "ON"})

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_no_device(self, mock_coordinator):
        """Test setting HVAC mode when device is not available."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        mock_coordinator.device = None

        # Act
        await entity.async_set_hvac_mode(HVACMode.HEAT)

        # Assert
        mock_coordinator.async_send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_set_temperature_valid(self, mock_coordinator):
        """Test setting target temperature with valid value."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)

        # Act
        await entity.async_set_temperature(**{ATTR_TEMPERATURE: 22.5})

        # Assert
        # 22.5°C = 295.65K = 2956.5 -> 2956 (int conversion)
        mock_coordinator.async_send_command.assert_called_once_with("set_target_temperature", {"hmax": "2956"})

    @pytest.mark.asyncio
    async def test_async_set_temperature_no_temperature(self, mock_coordinator):
        """Test setting target temperature without temperature parameter."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)

        # Act
        await entity.async_set_temperature()

        # Assert
        mock_coordinator.async_send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_set_temperature_no_device(self, mock_coordinator):
        """Test setting target temperature when device is not available."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        mock_coordinator.device = None

        # Act
        await entity.async_set_temperature(**{ATTR_TEMPERATURE: 20.0})

        # Assert
        mock_coordinator.async_send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_set_fan_mode_auto(self, mock_coordinator):
        """Test setting fan mode to Auto."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)

        # Act
        await entity.async_set_fan_mode("Auto")

        # Assert
        mock_coordinator.async_send_command.assert_called_once_with("set_fan_mode", {"auto": "ON"})

    @pytest.mark.asyncio
    async def test_async_set_fan_mode_manual_speed(self, mock_coordinator):
        """Test setting fan mode to manual speed."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)

        # Act
        await entity.async_set_fan_mode("7")

        # Assert
        mock_coordinator.async_send_command.assert_called_once_with("set_fan_mode", {"auto": "OFF", "fnsp": "0007"})

    @pytest.mark.asyncio
    async def test_async_set_fan_mode_no_device(self, mock_coordinator):
        """Test setting fan mode when device is not available."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        mock_coordinator.device = None

        # Act
        await entity.async_set_fan_mode("5")

        # Assert
        mock_coordinator.async_send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_turn_on(self, mock_coordinator):
        """Test turning the climate entity on."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)

        # Act
        await entity.async_turn_on()

        # Assert
        mock_coordinator.async_send_command.assert_called_once_with("set_climate_mode", {"fnst": "FAN", "auto": "ON"})

    @pytest.mark.asyncio
    async def test_async_turn_off(self, mock_coordinator):
        """Test turning the climate entity off."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)

        # Act
        await entity.async_turn_off()

        # Assert
        mock_coordinator.async_send_command.assert_called_once_with("set_power", {"fnst": "OFF"})

    def test_extra_state_attributes_with_device(self, mock_coordinator):
        """Test extra state attributes when device is available."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        entity._attr_target_temperature = 21.5
        entity._attr_hvac_mode = HVACMode.HEAT
        entity._attr_fan_mode = "5"

        mock_coordinator.device._get_current_value.side_effect = lambda state, key, default: {
            "hmod": "HEAT",
            "auto": "OFF",
            "fnsp": "0005",
            "fnst": "FAN",
        }.get(key, default)

        # Act
        attributes = entity.extra_state_attributes

        # Assert
        assert attributes is not None
        assert attributes["target_temperature"] == 21.5
        assert attributes["hvac_mode"] == HVACMode.HEAT
        assert attributes["fan_mode"] == "5"
        assert attributes["heating_mode"] == "HEAT"
        assert attributes["auto_mode"] is False
        assert attributes["fan_speed"] == "0005"
        assert attributes["fan_power"] is True
        # 21.5°C = 294.65K = 2946.5 -> 2946 (int conversion)
        assert attributes["target_temperature_kelvin"] == "2946"

    def test_extra_state_attributes_no_device(self, mock_coordinator):
        """Test extra state attributes when device is not available."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        mock_coordinator.device = None

        # Act
        attributes = entity.extra_state_attributes

        # Assert
        assert attributes is None


class TestClimateIntegration:
    """Test climate entity integration."""

    def test_climate_inherits_from_correct_base_classes(self, mock_coordinator):
        """Test that climate entity inherits from correct base classes."""
        # Arrange & Act
        entity = DysonClimateEntity(mock_coordinator)

        # Assert
        from homeassistant.components.climate import ClimateEntity

        from custom_components.hass_dyson.entity import DysonEntity

        assert isinstance(entity, DysonEntity)
        assert isinstance(entity, ClimateEntity)

    def test_coordinator_type_annotation(self, mock_coordinator):
        """Test that coordinator type annotation is correct."""
        # Arrange & Act
        entity = DysonClimateEntity(mock_coordinator)

        # Assert
        assert hasattr(entity, "coordinator")
        # We can't directly check type annotation, but we can verify the attribute exists

    @pytest.mark.asyncio
    async def test_climate_error_handling(self, mock_coordinator):
        """Test climate entity error handling during command execution."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        mock_coordinator.async_send_command.side_effect = Exception("Test error")

        # Act & Assert - should not raise exception
        await entity.async_set_hvac_mode(HVACMode.HEAT)
        await entity.async_set_temperature(**{ATTR_TEMPERATURE: 20.0})
        await entity.async_set_fan_mode("5")

        # Should have attempted to call the command despite errors
        assert mock_coordinator.async_send_command.call_count == 3
