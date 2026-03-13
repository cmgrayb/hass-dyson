"""Tests for tilt (vertical) oscillation select entity and device method."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from custom_components.hass_dyson.const import (
    CONF_HOSTNAME,
    STATE_KEY_TILT_ANGLE_CONTROL,
    STATE_KEY_TILT_OSCILLATION_LOWER,
    STATE_KEY_TILT_OSCILLATION_ON,
    STATE_KEY_TILT_OSCILLATION_STATUS,
    STATE_KEY_TILT_OSCILLATION_UPPER,
)
from custom_components.hass_dyson.select import (
    DysonTiltOscillationModeSelect,
    async_setup_entry,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tilt_coordinator():
    """Mock coordinator for a device that has the oton key in product-state."""
    coordinator = Mock()
    coordinator.serial_number = "664-EU-ABC1234A"
    coordinator.device_name = "Bedroom"
    coordinator.device = Mock()
    coordinator.device_capabilities = [
        "Scheduling",
        "EnvironmentalData",
        "ExtendedAQ",
        "ChangeWifi",
    ]
    coordinator.device_category = ["ec"]
    coordinator.device.get_state_value = Mock(
        side_effect=lambda state, key, default: state.get(key, default)
    )
    coordinator.data = {
        "product-state": {
            "fpwr": "ON",
            "oton": "OFF",
            "otcs": "OFF",
            "anct": "CUST",
            "otal": "0000",
            "otau": "0000",
        }
    }
    return coordinator


@pytest.fixture
def mock_hass(tilt_coordinator):
    """Home Assistant mock wired to the tilt coordinator."""
    hass = Mock()
    hass.data = {"hass_dyson": {"664-EU-ABC1234A": tilt_coordinator}}
    return hass


@pytest.fixture
def mock_config_entry():
    """Config entry pointing at the tilt coordinator."""
    entry = Mock()
    entry.data = {CONF_HOSTNAME: "192.168.1.200", "connection_type": "local_only"}
    entry.unique_id = "664-EU-ABC1234A"
    entry.entry_id = "664-EU-ABC1234A"
    return entry


# ---------------------------------------------------------------------------
# Constant values
# ---------------------------------------------------------------------------


class TestTiltOscillationConstants:
    """Verify the new state-key constants have the correct raw MQTT values."""

    def test_state_key_tilt_oscillation_on(self):
        assert STATE_KEY_TILT_OSCILLATION_ON == "oton"

    def test_state_key_tilt_oscillation_lower(self):
        assert STATE_KEY_TILT_OSCILLATION_LOWER == "otal"

    def test_state_key_tilt_oscillation_upper(self):
        assert STATE_KEY_TILT_OSCILLATION_UPPER == "otau"

    def test_state_key_tilt_angle_control(self):
        assert STATE_KEY_TILT_ANGLE_CONTROL == "anct"

    def test_state_key_tilt_oscillation_status(self):
        assert STATE_KEY_TILT_OSCILLATION_STATUS == "otcs"


# ---------------------------------------------------------------------------
# async_setup_entry gating
# ---------------------------------------------------------------------------


class TestTiltSelectSetupEntry:
    """Test that the tilt select is added only when oton is present."""

    @pytest.mark.asyncio
    async def test_tilt_entity_added_when_oton_present(
        self, mock_hass, mock_config_entry, tilt_coordinator
    ):
        """Entity created when device_category is ec and oton is in product-state."""
        add_entities = MagicMock()
        await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        tilt_entities = [
            e for e in entities if isinstance(e, DysonTiltOscillationModeSelect)
        ]
        assert len(tilt_entities) == 1

    @pytest.mark.asyncio
    async def test_tilt_entity_not_added_when_oton_absent(
        self, mock_hass, mock_config_entry, tilt_coordinator
    ):
        """Entity not created when oton is absent from product-state."""
        tilt_coordinator.data = {"product-state": {"fpwr": "ON"}}  # no oton
        add_entities = MagicMock()
        await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        tilt_entities = [
            e for e in entities if isinstance(e, DysonTiltOscillationModeSelect)
        ]
        assert len(tilt_entities) == 0

    @pytest.mark.asyncio
    async def test_tilt_entity_not_added_for_robot_category(
        self, mock_hass, mock_config_entry, tilt_coordinator
    ):
        """Entity not created for robot vacuum devices even if oton is present."""
        tilt_coordinator.device_category = ["robot"]
        add_entities = MagicMock()
        await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        entities = add_entities.call_args[0][0]
        tilt_entities = [
            e for e in entities if isinstance(e, DysonTiltOscillationModeSelect)
        ]
        assert len(tilt_entities) == 0

    @pytest.mark.asyncio
    async def test_tilt_entity_not_added_when_data_is_none(
        self, mock_hass, mock_config_entry, tilt_coordinator
    ):
        """Entity not created when coordinator has no data yet."""
        tilt_coordinator.data = None
        add_entities = MagicMock()
        await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        entities = add_entities.call_args[0][0]
        tilt_entities = [
            e for e in entities if isinstance(e, DysonTiltOscillationModeSelect)
        ]
        assert len(tilt_entities) == 0


# ---------------------------------------------------------------------------
# Entity initialisation
# ---------------------------------------------------------------------------


class TestDysonTiltOscillationModeSelectInit:
    """Test entity attributes set during __init__."""

    def test_unique_id(self, tilt_coordinator):
        entity = DysonTiltOscillationModeSelect(tilt_coordinator)
        assert entity._attr_unique_id == "664-EU-ABC1234A_tilt_oscillation_mode"

    def test_translation_key(self, tilt_coordinator):
        entity = DysonTiltOscillationModeSelect(tilt_coordinator)
        assert entity._attr_translation_key == "tilt_oscillation_mode"

    def test_options(self, tilt_coordinator):
        entity = DysonTiltOscillationModeSelect(tilt_coordinator)
        assert entity._attr_options == ["Off", "25°", "50°", "Breeze"]

    def test_icon(self, tilt_coordinator):
        entity = DysonTiltOscillationModeSelect(tilt_coordinator)
        assert entity._attr_icon == "mdi:angle-acute"


# ---------------------------------------------------------------------------
# State reading (_detect_tilt_mode)
# ---------------------------------------------------------------------------


class TestDetectTiltMode:
    """Test the mode detection logic."""

    def _make_entity(self, coordinator) -> DysonTiltOscillationModeSelect:
        return DysonTiltOscillationModeSelect(coordinator)

    def test_off_when_oton_off_and_otal_zero(self, tilt_coordinator):
        tilt_coordinator.data = {"product-state": {"oton": "OFF", "otal": "0000"}}
        entity = self._make_entity(tilt_coordinator)
        assert entity._detect_tilt_mode() == "Off"

    def test_25_degrees(self, tilt_coordinator):
        tilt_coordinator.data = {"product-state": {"oton": "OFF", "otal": "0025"}}
        entity = self._make_entity(tilt_coordinator)
        assert entity._detect_tilt_mode() == "25°"

    def test_50_degrees(self, tilt_coordinator):
        tilt_coordinator.data = {"product-state": {"oton": "OFF", "otal": "0050"}}
        entity = self._make_entity(tilt_coordinator)
        assert entity._detect_tilt_mode() == "50°"

    def test_breeze_when_oton_on(self, tilt_coordinator):
        tilt_coordinator.data = {"product-state": {"oton": "ON", "otal": "0359"}}
        entity = self._make_entity(tilt_coordinator)
        assert entity._detect_tilt_mode() == "Breeze"

    def test_oton_on_overrides_otal(self, tilt_coordinator):
        """When oton=ON the mode is always Breeze regardless of otal."""
        tilt_coordinator.data = {"product-state": {"oton": "ON", "otal": "0000"}}
        entity = self._make_entity(tilt_coordinator)
        assert entity._detect_tilt_mode() == "Breeze"

    def test_unknown_otal_returns_off(self, tilt_coordinator):
        tilt_coordinator.data = {"product-state": {"oton": "OFF", "otal": "0099"}}
        entity = self._make_entity(tilt_coordinator)
        assert entity._detect_tilt_mode() == "Off"

    def test_no_device_returns_off(self, tilt_coordinator):
        tilt_coordinator.device = None
        entity = self._make_entity(tilt_coordinator)
        assert entity._detect_tilt_mode() == "Off"


# ---------------------------------------------------------------------------
# Coordinator update handling
# ---------------------------------------------------------------------------


class TestHandleCoordinatorUpdate:
    """Test _handle_coordinator_update sets current_option correctly."""

    def test_updates_current_option(self, tilt_coordinator):
        from unittest.mock import patch

        from custom_components.hass_dyson.entity import DysonEntity

        tilt_coordinator.data = {"product-state": {"oton": "OFF", "otal": "0025"}}
        entity = DysonTiltOscillationModeSelect(tilt_coordinator)
        with patch.object(DysonEntity, "_handle_coordinator_update"):
            entity._handle_coordinator_update()
        assert entity._attr_current_option == "25°"

    def test_no_device_sets_none(self, tilt_coordinator):
        from unittest.mock import patch

        from custom_components.hass_dyson.entity import DysonEntity

        tilt_coordinator.device = None
        entity = DysonTiltOscillationModeSelect(tilt_coordinator)
        with patch.object(DysonEntity, "_handle_coordinator_update"):
            entity._handle_coordinator_update()
        assert entity._attr_current_option is None

    def test_breeze_state(self, tilt_coordinator):
        from unittest.mock import patch

        from custom_components.hass_dyson.entity import DysonEntity

        tilt_coordinator.data = {"product-state": {"oton": "ON", "otal": "0359"}}
        entity = DysonTiltOscillationModeSelect(tilt_coordinator)
        with patch.object(DysonEntity, "_handle_coordinator_update"):
            entity._handle_coordinator_update()
        assert entity._attr_current_option == "Breeze"


# ---------------------------------------------------------------------------
# async_select_option (command dispatch)
# ---------------------------------------------------------------------------


class TestAsyncSelectOption:
    """Test that the correct device command is sent for each option."""

    @pytest.mark.asyncio
    async def test_select_off(self, tilt_coordinator):
        tilt_coordinator.device.set_tilt_oscillation = AsyncMock()
        entity = DysonTiltOscillationModeSelect(tilt_coordinator)
        entity.async_write_ha_state = MagicMock()

        await entity.async_select_option("Off")

        tilt_coordinator.device.set_tilt_oscillation.assert_awaited_once_with("Off")
        assert entity._attr_current_option == "Off"

    @pytest.mark.asyncio
    async def test_select_25_degrees(self, tilt_coordinator):
        tilt_coordinator.device.set_tilt_oscillation = AsyncMock()
        entity = DysonTiltOscillationModeSelect(tilt_coordinator)
        entity.async_write_ha_state = MagicMock()

        await entity.async_select_option("25°")

        tilt_coordinator.device.set_tilt_oscillation.assert_awaited_once_with("25°")
        assert entity._attr_current_option == "25°"

    @pytest.mark.asyncio
    async def test_select_50_degrees(self, tilt_coordinator):
        tilt_coordinator.device.set_tilt_oscillation = AsyncMock()
        entity = DysonTiltOscillationModeSelect(tilt_coordinator)
        entity.async_write_ha_state = MagicMock()

        await entity.async_select_option("50°")

        tilt_coordinator.device.set_tilt_oscillation.assert_awaited_once_with("50°")
        assert entity._attr_current_option == "50°"

    @pytest.mark.asyncio
    async def test_select_breeze(self, tilt_coordinator):
        tilt_coordinator.device.set_tilt_oscillation = AsyncMock()
        entity = DysonTiltOscillationModeSelect(tilt_coordinator)
        entity.async_write_ha_state = MagicMock()

        await entity.async_select_option("Breeze")

        tilt_coordinator.device.set_tilt_oscillation.assert_awaited_once_with("Breeze")
        assert entity._attr_current_option == "Breeze"

    @pytest.mark.asyncio
    async def test_no_device_does_nothing(self, tilt_coordinator):
        tilt_coordinator.device = None
        entity = DysonTiltOscillationModeSelect(tilt_coordinator)
        # Should return without error
        await entity.async_select_option("Off")

    @pytest.mark.asyncio
    async def test_connection_error_logged(self, tilt_coordinator):
        tilt_coordinator.device.set_tilt_oscillation = AsyncMock(
            side_effect=ConnectionError("disconnected")
        )
        entity = DysonTiltOscillationModeSelect(tilt_coordinator)
        entity.async_write_ha_state = MagicMock()
        # Should not raise
        await entity.async_select_option("25°")

    @pytest.mark.asyncio
    async def test_value_error_logged(self, tilt_coordinator):
        tilt_coordinator.device.set_tilt_oscillation = AsyncMock(
            side_effect=ValueError("bad option")
        )
        entity = DysonTiltOscillationModeSelect(tilt_coordinator)
        entity.async_write_ha_state = MagicMock()
        await entity.async_select_option("25°")

    @pytest.mark.asyncio
    async def test_unexpected_error_logged(self, tilt_coordinator):
        tilt_coordinator.device.set_tilt_oscillation = AsyncMock(
            side_effect=RuntimeError("unexpected")
        )
        entity = DysonTiltOscillationModeSelect(tilt_coordinator)
        entity.async_write_ha_state = MagicMock()
        await entity.async_select_option("25°")


# ---------------------------------------------------------------------------
# device.set_tilt_oscillation payloads
# ---------------------------------------------------------------------------


class TestDeviceSetTiltOscillation:
    """Test the device-layer set_tilt_oscillation method."""

    def _make_device(self):

        with MagicMock() as device:
            device.send_command = AsyncMock()
            device.serial_number = "664-EU-ABC1234A"
            return device

    @pytest.mark.asyncio
    async def test_off_payload(self):
        from unittest.mock import AsyncMock

        from custom_components.hass_dyson.device import DysonDevice

        device = Mock()
        device.send_command = AsyncMock()
        device.serial_number = "664-EU-ABC1234A"

        # Call the actual method by binding it
        await DysonDevice.set_tilt_oscillation(device, "Off")
        device.send_command.assert_awaited_once_with("STATE-SET", {"oton": "OFF"})

    @pytest.mark.asyncio
    async def test_25_degrees_payload(self):
        from custom_components.hass_dyson.device import DysonDevice

        device = Mock()
        device.send_command = AsyncMock()
        device.serial_number = "664-EU-ABC1234A"

        await DysonDevice.set_tilt_oscillation(device, "25°")
        device.send_command.assert_awaited_once_with(
            "STATE-SET", {"anct": "CUST", "otal": "0025", "otau": "0025"}
        )

    @pytest.mark.asyncio
    async def test_50_degrees_payload(self):
        from custom_components.hass_dyson.device import DysonDevice

        device = Mock()
        device.send_command = AsyncMock()
        device.serial_number = "664-EU-ABC1234A"

        await DysonDevice.set_tilt_oscillation(device, "50°")
        device.send_command.assert_awaited_once_with(
            "STATE-SET", {"anct": "CUST", "otal": "0050", "otau": "0050"}
        )

    @pytest.mark.asyncio
    async def test_breeze_payload(self):
        from custom_components.hass_dyson.device import DysonDevice

        device = Mock()
        device.send_command = AsyncMock()
        device.serial_number = "664-EU-ABC1234A"

        await DysonDevice.set_tilt_oscillation(device, "Breeze")
        device.send_command.assert_awaited_once_with(
            "STATE-SET",
            {"oton": "ON", "anct": "BRZE", "otal": "0359", "otau": "0359"},
        )

    @pytest.mark.asyncio
    async def test_invalid_option_raises(self):
        from custom_components.hass_dyson.device import DysonDevice

        device = Mock()
        device.send_command = AsyncMock()
        device.serial_number = "664-EU-ABC1234A"

        with pytest.raises(ValueError, match="Invalid tilt oscillation option"):
            await DysonDevice.set_tilt_oscillation(device, "invalid")
