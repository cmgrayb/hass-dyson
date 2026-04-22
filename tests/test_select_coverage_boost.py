"""Coverage boost tests for select.py targeting specific uncovered branches.

Covers:
- Robot power select entity setup in async_setup_entry (VisNav, Heurist, 360 Eye, Generic)
- DysonFanControlModeSelect local_only connection type paths
- DysonFanControlModeSelect async_select_option Sleep mode
- DysonOscillationModeSelect midpoint save/restore transitions
- DysonWaterHardnessSelect update and option selection methods
- Robot power select entity _handle_coordinator_update and async_select_option
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from custom_components.hass_dyson.const import (
    CONF_HOSTNAME,
    DOMAIN,
    ROBOT_POWER_OPTIONS_360_EYE,
    ROBOT_POWER_OPTIONS_HEURIST,
    ROBOT_POWER_OPTIONS_VIS_NAV,
)
from custom_components.hass_dyson.select import (
    DysonFanControlModeSelect,
    DysonOscillationModeSelect,
    DysonRobotPower360EyeSelect,
    DysonRobotPowerGenericSelect,
    DysonRobotPowerHeuristSelect,
    DysonRobotPowerVisNavSelect,
    DysonWaterHardnessSelect,
    async_setup_entry,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator with all required attributes."""
    coordinator = Mock()
    coordinator.serial_number = "NK6-EU-MHA0000A"
    coordinator.device_name = "Test Device"
    coordinator.device = Mock()
    coordinator.device_capabilities = []
    coordinator.device_category = []
    coordinator.device.get_state_value = Mock(return_value="OFF")
    coordinator.device.auto_mode = False
    coordinator.device.set_auto_mode = AsyncMock()
    coordinator.device.set_night_mode = AsyncMock()
    coordinator.device.set_water_hardness = AsyncMock()
    coordinator.device.set_robot_power = AsyncMock()
    coordinator.device.set_oscillation_preset = AsyncMock()
    coordinator.device.set_oscillation_angles = AsyncMock()
    coordinator.device.set_oscillation_breeze = AsyncMock()
    coordinator.device._state_data = {"product-state": {}}
    coordinator.data = {
        "product-state": {
            "auto": "OFF",
            "nmod": "OFF",
            "oson": "OFF",
            "osal": "0000",
            "osau": "0350",
            "ancp": "0175",
            "wath": "1350",
        }
    }
    coordinator.config_entry = Mock()
    coordinator.config_entry.data = {
        CONF_HOSTNAME: "192.168.1.100",
        "connection_type": "cloud",
    }
    coordinator.config_entry.unique_id = "NK6-EU-MHA0000A"
    coordinator.config_entry.entry_id = "NK6-EU-MHA0000A"
    return coordinator


@pytest.fixture
def mock_hass(mock_coordinator):
    """Create a mock Home Assistant instance."""
    hass = Mock()
    hass.data = {DOMAIN: {"NK6-EU-MHA0000A": mock_coordinator}}
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = Mock()
    entry.data = {CONF_HOSTNAME: "192.168.1.100", "connection_type": "cloud"}
    entry.unique_id = "NK6-EU-MHA0000A"
    entry.entry_id = "NK6-EU-MHA0000A"
    return entry


# ===== Robot power entity setup tests =====


class TestRobotPowerSetup:
    """Test robot power select setup in async_setup_entry."""

    @pytest.mark.asyncio
    async def test_setup_vis_nav_robot(self, mock_hass, mock_config_entry):
        """Test setup creates VisNav select for Mapping+DirectedCleaning capabilities."""
        coordinator = mock_hass.data[DOMAIN]["NK6-EU-MHA0000A"]
        coordinator.device_capabilities = ["Mapping", "DirectedCleaning"]
        coordinator.device_category = ["robot"]

        mock_add_entities = MagicMock()
        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        entities = mock_add_entities.call_args[0][0]
        entity_types = [type(e).__name__ for e in entities]
        assert "DysonRobotPowerVisNavSelect" in entity_types
        # VisNav only - not 360 Eye or Generic
        assert "DysonRobotPower360EyeSelect" not in entity_types
        assert "DysonRobotPowerGenericSelect" not in entity_types

    @pytest.mark.asyncio
    async def test_setup_heurist_robot(self, mock_hass, mock_config_entry):
        """Test setup creates Heurist select for Heat capability."""
        coordinator = mock_hass.data[DOMAIN]["NK6-EU-MHA0000A"]
        coordinator.device_capabilities = ["Heat"]
        coordinator.device_category = ["robot"]

        mock_add_entities = MagicMock()
        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        entities = mock_add_entities.call_args[0][0]
        entity_types = [type(e).__name__ for e in entities]
        assert "DysonRobotPowerHeuristSelect" in entity_types
        assert "DysonRobotPowerVisNavSelect" not in entity_types
        assert "DysonRobotPower360EyeSelect" not in entity_types

    @pytest.mark.asyncio
    async def test_setup_360_eye_and_generic_robot(self, mock_hass, mock_config_entry):
        """Test setup creates 360Eye + Generic selects for unknown robot capabilities."""
        coordinator = mock_hass.data[DOMAIN]["NK6-EU-MHA0000A"]
        coordinator.device_capabilities = []  # No special capabilities
        coordinator.device_category = ["robot"]

        mock_add_entities = MagicMock()
        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        entities = mock_add_entities.call_args[0][0]
        entity_types = [type(e).__name__ for e in entities]
        assert "DysonRobotPower360EyeSelect" in entity_types
        assert "DysonRobotPowerGenericSelect" in entity_types
        assert "DysonRobotPowerVisNavSelect" not in entity_types
        assert "DysonRobotPowerHeuristSelect" not in entity_types


# ===== DysonFanControlModeSelect tests =====


class TestFanControlModeSelectLocalOnly:
    """Test DysonFanControlModeSelect local_only connection type paths."""

    def test_initialization_local_only_options(self, mock_coordinator):
        """Test local_only devices show only Auto and Manual options."""
        mock_coordinator.config_entry.data = {"connection_type": "local_only"}
        entity = DysonFanControlModeSelect(mock_coordinator)

        assert entity._attr_options == ["Auto", "Manual"]
        assert "Sleep" not in entity._attr_options

    def test_handle_update_local_only_auto(self, mock_coordinator):
        """Test coordinator update sets Auto for local_only device in auto mode."""
        mock_coordinator.config_entry.data = {"connection_type": "local_only"}
        mock_coordinator.device.auto_mode = True

        entity = DysonFanControlModeSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            entity._handle_coordinator_update()

        assert entity._attr_current_option == "Auto"

    def test_handle_update_local_only_manual(self, mock_coordinator):
        """Test coordinator update sets Manual for local_only device not in auto mode."""
        mock_coordinator.config_entry.data = {"connection_type": "local_only"}
        mock_coordinator.device.auto_mode = False

        entity = DysonFanControlModeSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            entity._handle_coordinator_update()

        assert entity._attr_current_option == "Manual"

    def test_handle_update_no_device(self, mock_coordinator):
        """Test coordinator update when device is None sets option to None."""
        mock_coordinator.config_entry.data = {"connection_type": "local_only"}
        mock_coordinator.device = None

        entity = DysonFanControlModeSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            entity._handle_coordinator_update()

        assert entity._attr_current_option is None

    @pytest.mark.asyncio
    async def test_select_option_sleep_calls_night_mode(self, mock_coordinator):
        """Test selecting Sleep calls set_night_mode and set_auto_mode(False)."""
        mock_coordinator.config_entry.data = {"connection_type": "cloud"}
        mock_coordinator.device.set_night_mode = AsyncMock()
        mock_coordinator.device.set_auto_mode = AsyncMock()

        entity = DysonFanControlModeSelect(mock_coordinator)
        await entity.async_select_option("Sleep")

        mock_coordinator.device.set_night_mode.assert_called_once_with(True)
        mock_coordinator.device.set_auto_mode.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_select_option_sleep_connection_error(self, mock_coordinator):
        """Test Sleep option handles ConnectionError gracefully."""
        mock_coordinator.config_entry.data = {"connection_type": "cloud"}
        mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        entity = DysonFanControlModeSelect(mock_coordinator)
        # Should not raise
        await entity.async_select_option("Sleep")

    @pytest.mark.asyncio
    async def test_select_option_sleep_value_error(self, mock_coordinator):
        """Test Sleep option handles ValueError gracefully."""
        mock_coordinator.config_entry.data = {"connection_type": "cloud"}
        mock_coordinator.device.set_night_mode = AsyncMock(
            side_effect=ValueError("Bad value")
        )

        entity = DysonFanControlModeSelect(mock_coordinator)
        # Should not raise
        await entity.async_select_option("Sleep")

    @pytest.mark.asyncio
    async def test_select_option_no_device(self, mock_coordinator):
        """Test selecting option when device is None returns early."""
        mock_coordinator.device = None
        entity = DysonFanControlModeSelect(mock_coordinator)
        # Should return without error
        await entity.async_select_option("Auto")


# ===== DysonOscillationModeSelect midpoint transition tests =====


class TestOscillationMidpointTransitions:
    """Test oscillation mode midpoint save/restore during mode transitions."""

    def test_midpoint_saved_on_transition_to_350(self, mock_coordinator):
        """Test midpoint saved when transitioning from non-350 to 350 mode."""
        mock_coordinator.device_capabilities = []
        mock_coordinator.device.get_state_value = Mock(
            side_effect=lambda ps, key, default: {
                "ancp": "0350",
                "osal": "0000",
                "osau": "0350",
                "oson": "ON",
            }.get(key, default)
        )

        entity = DysonOscillationModeSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        entity._last_known_mode = "90°"
        entity._saved_sweep_midpoint = None

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            entity._handle_coordinator_update()

        # Should have saved midpoint (0+350)//2 = 175
        assert entity._saved_sweep_midpoint == 175
        assert entity._last_known_mode == "350°"

    def test_midpoint_cleared_on_transition_from_350(self, mock_coordinator):
        """Test midpoint discarded when transitioning from 350 to non-350 mode."""
        mock_coordinator.device_capabilities = []
        mock_coordinator.device.get_state_value = Mock(
            side_effect=lambda ps, key, default: {
                "ancp": "0090",
                "osal": "0045",
                "osau": "0135",
                "oson": "ON",
            }.get(key, default)
        )

        entity = DysonOscillationModeSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        entity._last_known_mode = "350°"
        entity._saved_sweep_midpoint = 175  # Previously saved

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            entity._handle_coordinator_update()

        # Midpoint should be cleared since device left 350° mode externally
        assert entity._saved_sweep_midpoint is None
        assert entity._last_known_mode == "90°"

    def test_no_midpoint_save_when_already_350(self, mock_coordinator):
        """Test midpoint NOT saved when device stays in 350 mode."""
        mock_coordinator.device_capabilities = []
        mock_coordinator.device.get_state_value = Mock(
            side_effect=lambda ps, key, default: {
                "ancp": "0350",
                "osal": "0000",
                "osau": "0350",
            }.get(key, default)
        )

        entity = DysonOscillationModeSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        entity._last_known_mode = "350°"  # Already in 350°
        entity._saved_sweep_midpoint = None

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            entity._handle_coordinator_update()

        # Midpoint should NOT be saved (already was in 350°)
        assert entity._saved_sweep_midpoint is None


# ===== DysonWaterHardnessSelect tests =====


class TestWaterHardnessSelect:
    """Test DysonWaterHardnessSelect entity."""

    def test_handle_update_soft(self, mock_coordinator):
        """Test coordinator update with Soft (2025) water hardness."""
        mock_coordinator.device.get_state_value = Mock(return_value="2025")

        entity = DysonWaterHardnessSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            entity._handle_coordinator_update()

        assert entity._attr_current_option == "Soft"

    def test_handle_update_medium(self, mock_coordinator):
        """Test coordinator update with Medium (1350) water hardness."""
        mock_coordinator.device.get_state_value = Mock(return_value="1350")

        entity = DysonWaterHardnessSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            entity._handle_coordinator_update()

        assert entity._attr_current_option == "Medium"

    def test_handle_update_hard(self, mock_coordinator):
        """Test coordinator update with Hard (0675) water hardness."""
        mock_coordinator.device.get_state_value = Mock(return_value="0675")

        entity = DysonWaterHardnessSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            entity._handle_coordinator_update()

        assert entity._attr_current_option == "Hard"

    def test_handle_update_unknown_defaults_medium(self, mock_coordinator):
        """Test coordinator update with unknown value defaults to Medium."""
        mock_coordinator.device.get_state_value = Mock(return_value="9999")

        entity = DysonWaterHardnessSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            entity._handle_coordinator_update()

        assert entity._attr_current_option == "Medium"

    def test_handle_update_no_device(self, mock_coordinator):
        """Test coordinator update with no device sets None."""
        mock_coordinator.device = None

        entity = DysonWaterHardnessSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            entity._handle_coordinator_update()

        assert entity._attr_current_option is None

    @pytest.mark.asyncio
    async def test_select_option_soft(self, mock_coordinator):
        """Test selecting Soft water hardness calls set_water_hardness."""
        mock_coordinator.device.set_water_hardness = AsyncMock()
        mock_coordinator.device.async_write_ha_state = MagicMock()

        entity = DysonWaterHardnessSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()

        await entity.async_select_option("Soft")

        mock_coordinator.device.set_water_hardness.assert_called_once_with("soft")
        assert entity._attr_current_option == "Soft"

    @pytest.mark.asyncio
    async def test_select_option_hard(self, mock_coordinator):
        """Test selecting Hard water hardness calls set_water_hardness."""
        mock_coordinator.device.set_water_hardness = AsyncMock()

        entity = DysonWaterHardnessSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()

        await entity.async_select_option("Hard")

        mock_coordinator.device.set_water_hardness.assert_called_once_with("hard")

    @pytest.mark.asyncio
    async def test_select_option_invalid(self, mock_coordinator):
        """Test selecting invalid option returns without calling device."""
        mock_coordinator.device.set_water_hardness = AsyncMock()

        entity = DysonWaterHardnessSelect(mock_coordinator)
        await entity.async_select_option("VeryHard")

        mock_coordinator.device.set_water_hardness.assert_not_called()

    @pytest.mark.asyncio
    async def test_select_option_connection_error(self, mock_coordinator):
        """Test water hardness option handles ConnectionError gracefully."""
        mock_coordinator.device.set_water_hardness = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        entity = DysonWaterHardnessSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        # Should not raise
        await entity.async_select_option("Medium")

    @pytest.mark.asyncio
    async def test_select_option_no_device(self, mock_coordinator):
        """Test water hardness option returns early when no device."""
        mock_coordinator.device = None

        entity = DysonWaterHardnessSelect(mock_coordinator)
        # Should not raise
        await entity.async_select_option("Soft")

    def test_extra_state_attributes(self, mock_coordinator):
        """Test extra_state_attributes returns water hardness data."""
        mock_coordinator.device.get_state_value = Mock(return_value="1350")

        entity = DysonWaterHardnessSelect(mock_coordinator)
        entity._attr_current_option = "Medium"

        attrs = entity.extra_state_attributes
        assert attrs is not None
        assert "water_hardness" in attrs
        assert "water_hardness_raw" in attrs

    def test_extra_state_attributes_no_device(self, mock_coordinator):
        """Test extra_state_attributes returns None when no device."""
        mock_coordinator.device = None

        entity = DysonWaterHardnessSelect(mock_coordinator)
        assert entity.extra_state_attributes is None


# ===== Robot power select entity tests =====


class TestRobotPower360EyeSelect:
    """Test DysonRobotPower360EyeSelect entity."""

    def test_initialization(self, mock_coordinator):
        """Test 360 Eye select initialization."""
        entity = DysonRobotPower360EyeSelect(mock_coordinator)

        assert "_robot_power_360_eye" in entity._attr_unique_id
        assert entity._attr_options == list(ROBOT_POWER_OPTIONS_360_EYE.values())

    def test_handle_update_with_power_level(self, mock_coordinator):
        """Test coordinator update with known power level."""
        # Get first key from options dict
        first_key = list(ROBOT_POWER_OPTIONS_360_EYE.keys())[0]
        first_val = ROBOT_POWER_OPTIONS_360_EYE[first_key]
        mock_coordinator.device._state_data = {"product-state": {"fPwr": first_key}}

        entity = DysonRobotPower360EyeSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        entity._handle_coordinator_update()

        assert entity._attr_current_option == first_val

    def test_handle_update_unknown_power_defaults_first(self, mock_coordinator):
        """Test coordinator update with unknown power defaults to first option."""
        mock_coordinator.device._state_data = {
            "product-state": {"fPwr": "UNKNOWN_LEVEL"}
        }

        entity = DysonRobotPower360EyeSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        entity._handle_coordinator_update()

        assert (
            entity._attr_current_option == list(ROBOT_POWER_OPTIONS_360_EYE.values())[0]
        )

    def test_handle_update_no_fPwr_defaults_first(self, mock_coordinator):
        """Test coordinator update with no fPwr key defaults to first option."""
        mock_coordinator.device._state_data = {"product-state": {}}

        entity = DysonRobotPower360EyeSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        entity._handle_coordinator_update()

        assert (
            entity._attr_current_option == list(ROBOT_POWER_OPTIONS_360_EYE.values())[0]
        )

    def test_handle_update_attribute_error_defaults_first(self, mock_coordinator):
        """Test coordinator update with AttributeError defaults to first option."""
        mock_coordinator.device._state_data = None  # Will cause AttributeError

        entity = DysonRobotPower360EyeSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        entity._handle_coordinator_update()

        assert (
            entity._attr_current_option == list(ROBOT_POWER_OPTIONS_360_EYE.values())[0]
        )

    def test_handle_update_no_device(self, mock_coordinator):
        """Test coordinator update sets None when no device."""
        mock_coordinator.device = None

        entity = DysonRobotPower360EyeSelect(mock_coordinator)
        entity._handle_coordinator_update()

        assert entity._attr_current_option is None

    @pytest.mark.asyncio
    async def test_select_option_valid(self, mock_coordinator):
        """Test selecting a valid power option calls set_robot_power."""
        mock_coordinator.device.set_robot_power = AsyncMock()

        first_val = list(ROBOT_POWER_OPTIONS_360_EYE.values())[0]
        first_key = list(ROBOT_POWER_OPTIONS_360_EYE.keys())[0]

        entity = DysonRobotPower360EyeSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        await entity.async_select_option(first_val)

        mock_coordinator.device.set_robot_power.assert_called_once_with(
            first_key, "360eye"
        )

    @pytest.mark.asyncio
    async def test_select_option_invalid(self, mock_coordinator):
        """Test selecting an invalid power option skips device call."""
        mock_coordinator.device.set_robot_power = AsyncMock()

        entity = DysonRobotPower360EyeSelect(mock_coordinator)
        await entity.async_select_option("INVALID_OPTION")

        mock_coordinator.device.set_robot_power.assert_not_called()

    @pytest.mark.asyncio
    async def test_select_option_no_device(self, mock_coordinator):
        """Test select option when device is None returns early."""
        mock_coordinator.device = None

        entity = DysonRobotPower360EyeSelect(mock_coordinator)
        # Should not raise
        await entity.async_select_option(list(ROBOT_POWER_OPTIONS_360_EYE.values())[0])

    @pytest.mark.asyncio
    async def test_select_option_exception(self, mock_coordinator):
        """Test select option handles exceptions gracefully."""
        mock_coordinator.device.set_robot_power = AsyncMock(
            side_effect=Exception("Device error")
        )

        entity = DysonRobotPower360EyeSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        first_val = list(ROBOT_POWER_OPTIONS_360_EYE.values())[0]
        # Should not raise
        await entity.async_select_option(first_val)


class TestRobotPowerGenericSelect:
    """Test DysonRobotPowerGenericSelect entity."""

    def test_initialization(self, mock_coordinator):
        """Test Generic robot power select initialization."""
        entity = DysonRobotPowerGenericSelect(mock_coordinator)

        assert "_robot_power_generic" in entity._attr_unique_id

    def test_handle_update_with_power_level(self, mock_coordinator):
        """Test coordinator update sets current option from state."""
        first_key = list(ROBOT_POWER_OPTIONS_HEURIST.keys())[0]
        first_val = ROBOT_POWER_OPTIONS_HEURIST[first_key]
        mock_coordinator.device._state_data = {"product-state": {"fPwr": first_key}}

        entity = DysonRobotPowerGenericSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        entity._handle_coordinator_update()

        # Generic uses HEURIST options
        assert entity._attr_current_option == first_val

    def test_handle_update_no_device(self, mock_coordinator):
        """Test coordinator update sets None when no device."""
        mock_coordinator.device = None

        entity = DysonRobotPowerGenericSelect(mock_coordinator)
        entity._handle_coordinator_update()

        assert entity._attr_current_option is None

    @pytest.mark.asyncio
    async def test_select_option_valid(self, mock_coordinator):
        """Test selecting a valid power option calls set_robot_power."""
        mock_coordinator.device.set_robot_power = AsyncMock()

        entity = DysonRobotPowerGenericSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()

        first_val = list(ROBOT_POWER_OPTIONS_HEURIST.values())[0]
        first_key = list(ROBOT_POWER_OPTIONS_HEURIST.keys())[0]

        await entity.async_select_option(first_val)

        mock_coordinator.device.set_robot_power.assert_called_once_with(
            first_key, "generic"
        )

    @pytest.mark.asyncio
    async def test_select_option_invalid_skips(self, mock_coordinator):
        """Test invalid option skips device call."""
        mock_coordinator.device.set_robot_power = AsyncMock()

        entity = DysonRobotPowerGenericSelect(mock_coordinator)
        await entity.async_select_option("NONEXISTENT_OPTION")

        mock_coordinator.device.set_robot_power.assert_not_called()

    @pytest.mark.asyncio
    async def test_select_option_no_device(self, mock_coordinator):
        """Test select option when device is None returns early."""
        mock_coordinator.device = None

        entity = DysonRobotPowerGenericSelect(mock_coordinator)
        await entity.async_select_option(list(ROBOT_POWER_OPTIONS_HEURIST.values())[0])

    @pytest.mark.asyncio
    async def test_select_option_exception(self, mock_coordinator):
        """Test select option handles exceptions gracefully."""
        mock_coordinator.device.set_robot_power = AsyncMock(
            side_effect=Exception("Failure")
        )

        entity = DysonRobotPowerGenericSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        first_val = list(ROBOT_POWER_OPTIONS_HEURIST.values())[0]
        # Should not raise
        await entity.async_select_option(first_val)


class TestRobotPowerHeuristSelect:
    """Test DysonRobotPowerHeuristSelect entity."""

    def test_initialization(self, mock_coordinator):
        """Test Heurist robot power select initialization."""
        entity = DysonRobotPowerHeuristSelect(mock_coordinator)

        assert "_robot_power_heurist" in entity._attr_unique_id
        assert entity._attr_options == list(ROBOT_POWER_OPTIONS_HEURIST.values())

    def test_handle_update_with_power_level(self, mock_coordinator):
        """Test coordinator update sets current option from state."""
        first_key = list(ROBOT_POWER_OPTIONS_HEURIST.keys())[0]
        first_val = ROBOT_POWER_OPTIONS_HEURIST[first_key]
        mock_coordinator.device._state_data = {"product-state": {"fPwr": first_key}}

        entity = DysonRobotPowerHeuristSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        entity._handle_coordinator_update()

        assert entity._attr_current_option == first_val

    def test_handle_update_unknown_power(self, mock_coordinator):
        """Test coordinator update with unknown power defaults to first option."""
        mock_coordinator.device._state_data = {"product-state": {"fPwr": "UNKNOWN"}}

        entity = DysonRobotPowerHeuristSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        entity._handle_coordinator_update()

        assert (
            entity._attr_current_option == list(ROBOT_POWER_OPTIONS_HEURIST.values())[0]
        )

    def test_handle_update_no_device(self, mock_coordinator):
        """Test coordinator update sets None when no device."""
        mock_coordinator.device = None

        entity = DysonRobotPowerHeuristSelect(mock_coordinator)
        entity._handle_coordinator_update()

        assert entity._attr_current_option is None

    @pytest.mark.asyncio
    async def test_select_option_valid(self, mock_coordinator):
        """Test selecting a valid power option calls set_robot_power."""
        mock_coordinator.device.set_robot_power = AsyncMock()

        entity = DysonRobotPowerHeuristSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()

        first_val = list(ROBOT_POWER_OPTIONS_HEURIST.values())[0]
        first_key = list(ROBOT_POWER_OPTIONS_HEURIST.keys())[0]

        await entity.async_select_option(first_val)

        mock_coordinator.device.set_robot_power.assert_called_once_with(
            first_key, "heurist"
        )

    @pytest.mark.asyncio
    async def test_select_option_invalid_skips(self, mock_coordinator):
        """Test invalid option skips device call."""
        mock_coordinator.device.set_robot_power = AsyncMock()

        entity = DysonRobotPowerHeuristSelect(mock_coordinator)
        await entity.async_select_option("NONEXISTENT")

        mock_coordinator.device.set_robot_power.assert_not_called()

    @pytest.mark.asyncio
    async def test_select_option_no_device(self, mock_coordinator):
        """Test select option when device is None returns early."""
        mock_coordinator.device = None

        entity = DysonRobotPowerHeuristSelect(mock_coordinator)
        await entity.async_select_option(list(ROBOT_POWER_OPTIONS_HEURIST.values())[0])


class TestRobotPowerVisNavSelect:
    """Test DysonRobotPowerVisNavSelect entity."""

    def test_initialization(self, mock_coordinator):
        """Test Vis Nav robot power select initialization."""
        entity = DysonRobotPowerVisNavSelect(mock_coordinator)

        assert "_robot_power_vis_nav" in entity._attr_unique_id
        assert entity._attr_options == list(ROBOT_POWER_OPTIONS_VIS_NAV.values())

    def test_handle_update_with_power_level(self, mock_coordinator):
        """Test coordinator update sets current option from state."""
        first_key = list(ROBOT_POWER_OPTIONS_VIS_NAV.keys())[0]
        first_val = ROBOT_POWER_OPTIONS_VIS_NAV[first_key]
        mock_coordinator.device._state_data = {"product-state": {"fPwr": first_key}}

        entity = DysonRobotPowerVisNavSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        entity._handle_coordinator_update()

        assert entity._attr_current_option == first_val

    def test_handle_update_no_device(self, mock_coordinator):
        """Test coordinator update sets None when no device."""
        mock_coordinator.device = None

        entity = DysonRobotPowerVisNavSelect(mock_coordinator)
        entity._handle_coordinator_update()

        assert entity._attr_current_option is None

    @pytest.mark.asyncio
    async def test_select_option_valid(self, mock_coordinator):
        """Test selecting a valid power option calls set_robot_power."""
        mock_coordinator.device.set_robot_power = AsyncMock()

        entity = DysonRobotPowerVisNavSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()

        first_val = list(ROBOT_POWER_OPTIONS_VIS_NAV.values())[0]
        first_key = list(ROBOT_POWER_OPTIONS_VIS_NAV.keys())[0]

        await entity.async_select_option(first_val)

        mock_coordinator.device.set_robot_power.assert_called_once_with(
            first_key, "vis_nav"
        )

    @pytest.mark.asyncio
    async def test_select_option_invalid_skips(self, mock_coordinator):
        """Test invalid option skips device call."""
        mock_coordinator.device.set_robot_power = AsyncMock()

        entity = DysonRobotPowerVisNavSelect(mock_coordinator)
        await entity.async_select_option("NONEXISTENT")

        mock_coordinator.device.set_robot_power.assert_not_called()

    @pytest.mark.asyncio
    async def test_select_option_no_device(self, mock_coordinator):
        """Test select option when device is None returns early."""
        mock_coordinator.device = None

        entity = DysonRobotPowerVisNavSelect(mock_coordinator)
        await entity.async_select_option(list(ROBOT_POWER_OPTIONS_VIS_NAV.values())[0])

    @pytest.mark.asyncio
    async def test_select_option_exception(self, mock_coordinator):
        """Test select option handles exceptions gracefully."""
        mock_coordinator.device.set_robot_power = AsyncMock(
            side_effect=Exception("Device error")
        )

        entity = DysonRobotPowerVisNavSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        first_val = list(ROBOT_POWER_OPTIONS_VIS_NAV.values())[0]
        # Should not raise
        await entity.async_select_option(first_val)
