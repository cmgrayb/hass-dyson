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
    coordinator.device.get_state_value = MagicMock(return_value="OFF")
    coordinator.device.set_target_temperature = AsyncMock()
    coordinator.device_capabilities = ["Heating"]
    coordinator.data = {"product-state": {}}
    coordinator.async_send_command = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
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
    async def test_async_setup_entry_with_heating_capability(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Test platform setup when device has heating capability."""
        # Arrange
        async_add_entities = MagicMock()
        mock_coordinator.device_capabilities = ["Heating"]

        mock_hass.data = {"hass_dyson": {mock_config_entry.entry_id: mock_coordinator}}

        # Act
        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        # Assert
        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        assert len(call_args) == 1
        assert isinstance(call_args[0], DysonClimateEntity)

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_humidifier_capability(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Test platform setup when device has humidifier capability."""
        # Arrange
        async_add_entities = MagicMock()
        mock_coordinator.device_capabilities = ["Humidifier"]

        mock_hass.data = {"hass_dyson": {mock_config_entry.entry_id: mock_coordinator}}

        # Act
        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        # Assert
        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        assert len(call_args) == 1
        assert isinstance(call_args[0], DysonClimateEntity)

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_both_heating_and_humidifier(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Test platform setup when device has both heating and humidifier capabilities."""
        # Arrange
        async_add_entities = MagicMock()
        mock_coordinator.device_capabilities = ["Heating", "Humidifier"]

        mock_hass.data = {"hass_dyson": {mock_config_entry.entry_id: mock_coordinator}}

        # Act
        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        # Assert
        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        assert len(call_args) == 1
        assert isinstance(call_args[0], DysonClimateEntity)

    @pytest.mark.asyncio
    async def test_async_setup_entry_without_heating_or_humidifier_capability(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Test platform setup when device lacks both heating and humidifier capabilities."""
        # Arrange
        async_add_entities = MagicMock()
        mock_coordinator.device_capabilities = [
            "Fan"
        ]  # No heating or humidifier capability

        mock_hass.data = {"hass_dyson": {mock_config_entry.entry_id: mock_coordinator}}

        # Act
        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        # Assert
        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        assert len(call_args) == 0  # No entities added


class TestDysonClimateEntity:
    """Test DysonClimateEntity class."""

    def test_init_sets_attributes_correctly_heating_only(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly for heating-only device."""
        # Act
        entity = DysonClimateEntity(mock_coordinator)

        # Assert
        assert entity.coordinator == mock_coordinator
        assert entity._attr_unique_id == "TEST-SERIAL-123_climate"
        assert entity._attr_name is None  # Uses device name from device_info
        assert entity._attr_icon == "mdi:thermostat"

        # Climate features (heating only)
        expected_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        assert entity._attr_supported_features == expected_features

        # Temperature settings
        assert entity._attr_temperature_unit == UnitOfTemperature.CELSIUS
        assert entity._attr_min_temp == 1
        assert entity._attr_max_temp == 37
        assert entity._attr_target_temperature_step == 1

        # HVAC modes (heating device)
        expected_hvac_modes = [
            HVACMode.OFF,
            HVACMode.COOL,
            HVACMode.HEAT,
        ]
        assert entity._attr_hvac_modes == expected_hvac_modes

    def test_init_sets_attributes_correctly_humidifier_only(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly for humidifier-only device."""
        # Arrange
        mock_coordinator.device_capabilities = ["Humidifier"]

        # Act
        entity = DysonClimateEntity(mock_coordinator)

        # Assert
        assert entity.coordinator == mock_coordinator
        assert entity._attr_unique_id == "TEST-SERIAL-123_climate"

        # Climate features (humidifier only)
        expected_features = (
            ClimateEntityFeature.TARGET_HUMIDITY
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        assert entity._attr_supported_features == expected_features

        # Humidity settings
        assert entity._attr_min_humidity == 30
        assert entity._attr_max_humidity == 50
        assert entity._attr_target_humidity_step == 1

        # HVAC modes (humidifier device)
        expected_hvac_modes = [
            HVACMode.OFF,
            HVACMode.COOL,
            HVACMode.DRY,  # DRY mode for humidification
        ]
        assert entity._attr_hvac_modes == expected_hvac_modes

    def test_init_sets_attributes_correctly_both_capabilities(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly for device with both heating and humidifier."""
        # Arrange
        mock_coordinator.device_capabilities = ["Heating", "Humidifier"]

        # Act
        entity = DysonClimateEntity(mock_coordinator)

        # Assert
        # Climate features (both capabilities)
        expected_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_HUMIDITY
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        assert entity._attr_supported_features == expected_features

        # HVAC modes (both capabilities)
        expected_hvac_modes = [
            HVACMode.OFF,
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.DRY,  # DRY mode for humidification
        ]
        assert entity._attr_hvac_modes == expected_hvac_modes

    def test_handle_coordinator_update_with_device(self, mock_coordinator):
        """Test coordinator update handling when device is available."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        mock_coordinator.device.get_state_value.side_effect = (
            lambda state, key, default: {
                "tmp": "2730",  # 0°C in 0.1K (273.0K)
                "hmax": "2930",  # 20°C in 0.1K (293.0K)
                "fpwr": "ON",
                "hmod": "HEAT",
                "fnst": "FAN",
                "auto": "OFF",
                "fnsp": "0005",
            }.get(key, default)
        )

        # Act
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        # Assert
        assert entity._attr_current_temperature is not None
        assert entity._attr_target_temperature is not None
        assert (
            abs(entity._attr_current_temperature - 0.0) < 0.2
        )  # Allow for floating point precision
        assert abs(entity._attr_target_temperature - 19.85) < 0.2

    def test_handle_coordinator_update_with_humidifier_data(self, mock_coordinator):
        """Test coordinator update handling for humidifier device."""
        # Arrange
        mock_coordinator.device_capabilities = ["Humidifier"]
        entity = DysonClimateEntity(mock_coordinator)
        mock_coordinator.device.get_state_value.side_effect = (
            lambda state, key, default: {
                "humi": "0045",  # 45% current humidity
                "humt": "0040",  # 40% target humidity
                "fpwr": "ON",
                "hume": "HUMD",
                "haut": "OFF",
            }.get(key, default)
        )

        # Act
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        # Assert
        assert entity._attr_current_humidity == 45
        assert entity._attr_target_humidity == 40

    def test_update_humidity_with_invalid_data(self, mock_coordinator):
        """Test humidity update with invalid sensor data."""
        # Arrange
        mock_coordinator.device_capabilities = ["Humidifier"]
        entity = DysonClimateEntity(mock_coordinator)
        mock_coordinator.device.get_state_value.side_effect = (
            lambda state, key, default: {
                "humi": "0000",  # Invalid current humidity
                "humt": "invalid",  # Invalid target humidity
            }.get(key, default)
        )

        # Act
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        # Assert
        assert entity._attr_current_humidity is None
        assert entity._attr_target_humidity == 40  # Default fallback

    def test_hvac_mode_humidifier_enabled(self, mock_coordinator):
        """Test HVAC mode detection when humidifier is enabled."""
        # Arrange
        mock_coordinator.device_capabilities = ["Humidifier"]
        entity = DysonClimateEntity(mock_coordinator)
        mock_coordinator.device.get_state_value.side_effect = (
            lambda state, key, default: {
                "fpwr": "ON",
                "hume": "HUMD",
                "haut": "OFF",
            }.get(key, default)
        )

        # Act
        entity._update_hvac_mode({"product-state": {}})

        # Assert
        assert entity._attr_hvac_mode == HVACMode.DRY

    def test_hvac_mode_humidifier_auto(self, mock_coordinator):
        """Test HVAC mode detection when humidifier auto is enabled."""
        # Arrange
        mock_coordinator.device_capabilities = ["Humidifier"]
        entity = DysonClimateEntity(mock_coordinator)
        mock_coordinator.device.get_state_value.side_effect = (
            lambda state, key, default: {
                "fpwr": "ON",
                "hume": "OFF",
                "haut": "ON",
            }.get(key, default)
        )

        # Act
        entity._update_hvac_mode({"product-state": {}})

        # Assert
        assert entity._attr_hvac_mode == HVACMode.DRY

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
        mock_coordinator.device.get_state_value.side_effect = (
            lambda state, key, default: {
                "tmp": "2980",  # 25°C in 0.1K (298.0K)
                "hmax": "3000",  # 26.85°C in 0.1K (300.0K)
            }.get(key, default)
        )

        # Act
        entity._update_temperatures(device_data)

        # Assert
        assert entity._attr_current_temperature is not None
        assert entity._attr_target_temperature is not None
        assert (
            abs(entity._attr_current_temperature - 24.85) < 0.01
        )  # Allow for floating point precision
        assert abs(entity._attr_target_temperature - 26.85) < 0.01

    def test_update_temperatures_invalid_values(self, mock_coordinator):
        """Test temperature update with invalid device values."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        device_data = {"product-state": {}}
        mock_coordinator.device.get_state_value.side_effect = (
            lambda state, key, default: {
                "tmp": "invalid",
                "hmax": "also_invalid",
            }.get(key, default)
        )

        # Act
        entity._update_temperatures(device_data)

        # Assert
        assert entity._attr_current_temperature is None
        assert entity._attr_target_temperature == 20  # Default value

    def test_update_hvac_mode_off(self, mock_coordinator):
        """Test HVAC mode update when device is off."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        device_data = {"product-state": {}}
        mock_coordinator.device.get_state_value.side_effect = (
            lambda state, key, default: {
                "fpwr": "OFF",
                "hmod": "OFF",
            }.get(key, default)
        )

        # Act
        entity._update_hvac_mode(device_data)

        # Assert
        assert entity._attr_hvac_mode == HVACMode.OFF

    def test_update_hvac_mode_heat(self, mock_coordinator):
        """Test HVAC mode update when heating is on."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        device_data = {"product-state": {}}
        mock_coordinator.device.get_state_value.side_effect = (
            lambda state, key, default: {
                "fpwr": "ON",
                "hmod": "HEAT",
            }.get(key, default)
        )

        # Act
        entity._update_hvac_mode(device_data)

        # Assert
        assert entity._attr_hvac_mode == HVACMode.HEAT

    def test_update_hvac_mode_cool(self, mock_coordinator):
        """Test HVAC mode update when cooling is on."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        device_data = {"product-state": {}}
        mock_coordinator.device.get_state_value.side_effect = (
            lambda state, key, default: {
                "fpwr": "ON",
                "hmod": "OFF",
            }.get(key, default)
        )

        # Act
        entity._update_hvac_mode(device_data)

        # Assert
        assert entity._attr_hvac_mode == HVACMode.COOL

    def test_update_hvac_action_heating(self, mock_coordinator):
        """Test HVAC action update when device is actively heating."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        entity._attr_hvac_mode = HVACMode.HEAT  # Set heating mode
        device_data = {"product-state": {}}
        mock_coordinator.device.get_state_value.side_effect = (
            lambda state, key, default: {
                "hsta": "HEAT",
                "fpwr": "ON",
            }.get(key, default)
        )

        # Act
        entity._update_hvac_action(device_data)

        # Assert
        from homeassistant.components.climate.const import HVACAction

        assert entity._attr_hvac_action == HVACAction.HEATING

    def test_update_hvac_action_idle(self, mock_coordinator):
        """Test HVAC action update when device is idle (heating mode on but not heating)."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        entity._attr_hvac_mode = HVACMode.HEAT  # Set heating mode
        device_data = {"product-state": {}}
        mock_coordinator.device.get_state_value.side_effect = (
            lambda state, key, default: {
                "hsta": "OFF",
                "fpwr": "ON",
            }.get(key, default)
        )

        # Act
        entity._update_hvac_action(device_data)

        # Assert
        from homeassistant.components.climate.const import HVACAction

        assert entity._attr_hvac_action == HVACAction.IDLE

    def test_update_hvac_action_cooling(self, mock_coordinator):
        """Test HVAC action update when device is actively cooling."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        entity._attr_hvac_mode = HVACMode.COOL  # Set cooling mode
        device_data = {"product-state": {}}
        mock_coordinator.device.get_state_value.side_effect = (
            lambda state, key, default: {
                "hsta": "OFF",
                "fpwr": "ON",
            }.get(key, default)
        )

        # Act
        entity._update_hvac_action(device_data)

        # Assert
        from homeassistant.components.climate.const import HVACAction

        assert entity._attr_hvac_action == HVACAction.COOLING

    def test_update_hvac_action_off(self, mock_coordinator):
        """Test HVAC action update when HVAC mode is off."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        entity._attr_hvac_mode = HVACMode.OFF  # Set mode to off
        device_data = {"product-state": {}}
        mock_coordinator.device.get_state_value.side_effect = (
            lambda state, key, default: {
                "hsta": "OFF",
                "fpwr": "OFF",
            }.get(key, default)
        )

        # Act
        entity._update_hvac_action(device_data)

        # Assert
        from homeassistant.components.climate.const import HVACAction

        assert entity._attr_hvac_action == HVACAction.OFF

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_off(self, mock_coordinator):
        """Test setting HVAC mode to OFF."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        entity.hass = MagicMock()  # Mock hass for async_write_ha_state
        entity.async_write_ha_state = MagicMock()
        mock_coordinator.device.send_command = AsyncMock()

        # Act
        await entity.async_set_hvac_mode(HVACMode.OFF)

        # Assert - Should turn off fan and heating since device has Heating capability
        mock_coordinator.device.send_command.assert_called_once_with(
            "STATE-SET", {"fpwr": "OFF", "hmod": "OFF"}
        )

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_heat(self, mock_coordinator):
        """Test setting HVAC mode to HEAT."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        entity.hass = MagicMock()  # Mock hass for async_write_ha_state
        entity.async_write_ha_state = MagicMock()
        mock_coordinator.device.send_command = AsyncMock()

        # Act
        await entity.async_set_hvac_mode(HVACMode.HEAT)

        # Assert
        mock_coordinator.device.send_command.assert_called_once_with(
            "STATE-SET", {"fpwr": "ON", "hmod": "HEAT"}
        )

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_cool(self, mock_coordinator):
        """Test setting HVAC mode to COOL."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        entity.hass = MagicMock()  # Mock hass for async_write_ha_state
        entity.async_write_ha_state = MagicMock()
        mock_coordinator.device.send_command = AsyncMock()

        # Act
        await entity.async_set_hvac_mode(HVACMode.COOL)

        # Assert
        mock_coordinator.device.send_command.assert_called_once_with(
            "STATE-SET", {"fpwr": "ON", "hmod": "OFF"}
        )

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_unsupported(self, mock_coordinator):
        """Test setting unsupported HVAC mode logs warning and doesn't call device."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        mock_coordinator.device.send_command = AsyncMock()

        # Act
        await entity.async_set_hvac_mode(HVACMode.FAN_ONLY)

        # Assert
        mock_coordinator.device.send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_dry_humidifier(self, mock_coordinator):
        """Test setting HVAC mode to DRY (humidifier mode)."""
        # Arrange
        mock_coordinator.device_capabilities = ["Humidifier"]
        entity = DysonClimateEntity(mock_coordinator)
        entity.hass = MagicMock()
        entity.async_write_ha_state = MagicMock()
        mock_coordinator.device.send_command = AsyncMock()

        # Act
        await entity.async_set_hvac_mode(HVACMode.DRY)

        # Assert
        mock_coordinator.device.send_command.assert_called_once_with(
            "STATE-SET", {"fpwr": "ON", "hume": "HUMD", "haut": "OFF"}
        )

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_off_with_humidifier(self, mock_coordinator):
        """Test setting HVAC mode to OFF with humidifier capabilities."""
        # Arrange
        mock_coordinator.device_capabilities = ["Heating", "Humidifier"]
        entity = DysonClimateEntity(mock_coordinator)
        entity.hass = MagicMock()
        entity.async_write_ha_state = MagicMock()
        mock_coordinator.device.send_command = AsyncMock()

        # Act
        await entity.async_set_hvac_mode(HVACMode.OFF)

        # Assert
        expected_command = {"fpwr": "OFF", "hmod": "OFF", "hume": "OFF", "haut": "OFF"}
        mock_coordinator.device.send_command.assert_called_once_with(
            "STATE-SET", expected_command
        )

    @pytest.mark.asyncio
    async def test_async_set_humidity(self, mock_coordinator):
        """Test setting target humidity."""
        # Arrange
        mock_coordinator.device_capabilities = ["Humidifier"]
        entity = DysonClimateEntity(mock_coordinator)
        entity.hass = MagicMock()
        entity.async_write_ha_state = MagicMock()
        mock_coordinator.device.send_command = AsyncMock()

        # Act
        await entity.async_set_humidity(45)

        # Assert
        mock_coordinator.device.send_command.assert_called_once_with(
            "STATE-SET", {"humt": "0045"}
        )

    @pytest.mark.asyncio
    async def test_async_set_humidity_without_capability(self, mock_coordinator):
        """Test setting humidity without humidifier capability."""
        # Arrange
        mock_coordinator.device_capabilities = ["Heating"]  # No humidifier
        entity = DysonClimateEntity(mock_coordinator)
        mock_coordinator.device.send_command = AsyncMock()

        # Act
        await entity.async_set_humidity(45)

        # Assert
        mock_coordinator.device.send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_turn_on_humidifier_device(self, mock_coordinator):
        """Test turn_on defaults to DRY mode for humidifier-only device."""
        # Arrange
        mock_coordinator.device_capabilities = ["Humidifier"]
        entity = DysonClimateEntity(mock_coordinator)
        entity.async_set_hvac_mode = AsyncMock()

        # Act
        entity.hass = MagicMock()
        await entity.async_turn_on()

        # Assert - should be called with DRY mode for humidifier
        entity.async_set_hvac_mode.assert_called_once_with(HVACMode.DRY)

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
        # Mock hass for async_write_ha_state
        entity.hass = MagicMock()
        entity.async_write_ha_state = MagicMock()

        # Act
        await entity.async_set_temperature(**{ATTR_TEMPERATURE: 22.5})

        # Assert
        # Should call the device's set_target_temperature method with temperature in Celsius
        mock_coordinator.device.set_target_temperature.assert_called_once_with(22.5)
        # Should update local state immediately
        assert entity._attr_target_temperature == 22.5
        entity.async_write_ha_state.assert_called()

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
    async def test_async_turn_on(self, mock_coordinator):
        """Test turning the climate entity on."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        entity.hass = MagicMock()  # Mock hass for async_write_ha_state
        entity.async_write_ha_state = MagicMock()
        mock_coordinator.device.send_command = AsyncMock()

        # Act
        await entity.async_turn_on()

        # Assert
        mock_coordinator.device.send_command.assert_called_once_with(
            "STATE-SET", {"fpwr": "ON", "hmod": "HEAT"}
        )

    @pytest.mark.asyncio
    async def test_async_turn_off(self, mock_coordinator):
        """Test turning the climate entity off."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        entity.hass = MagicMock()  # Mock hass for async_write_ha_state
        entity.async_write_ha_state = MagicMock()
        mock_coordinator.device.send_command = AsyncMock()

        # Act
        await entity.async_turn_off()

        # Assert - Should turn off fan and heating since device has Heating capability
        mock_coordinator.device.send_command.assert_called_once_with(
            "STATE-SET", {"fpwr": "OFF", "hmod": "OFF"}
        )

    def test_extra_state_attributes_with_device(self, mock_coordinator):
        """Test extra state attributes when device is available."""
        # Arrange
        entity = DysonClimateEntity(mock_coordinator)
        entity._attr_target_temperature = 21.5
        entity._attr_hvac_mode = HVACMode.HEAT

        mock_coordinator.device.get_state_value.side_effect = (
            lambda state, key, default: {
                "fpwr": "ON",
                "hmod": "HEAT",
                "hsta": "OFF",
            }.get(key, default)
        )

        # Act
        attributes = entity.extra_state_attributes

        # Assert
        assert attributes is not None
        assert attributes["target_temperature"] == 21.5
        assert attributes["hvac_mode"] == HVACMode.HEAT
        assert attributes["fan_power"] == "ON"
        assert attributes["heating_mode"] == "HEAT"
        assert attributes["heating_status"] == "OFF"
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
        mock_coordinator.device.set_target_temperature.side_effect = Exception(
            "Temperature test error"
        )

        # Act & Assert - should not raise exception
        mock_coordinator.device.send_command = AsyncMock(
            side_effect=Exception("Command test error")
        )

        await entity.async_set_temperature(**{ATTR_TEMPERATURE: 20.0})
        mock_coordinator.device.set_target_temperature.assert_called_once_with(20.0)
