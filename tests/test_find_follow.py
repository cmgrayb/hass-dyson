"""Tests for Find+Follow switch and scan button entities."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from custom_components.hass_dyson.button import (
    DysonFindFollowScanButton,
    async_setup_entry as button_setup_entry,
)
from custom_components.hass_dyson.const import CONF_HOSTNAME
from custom_components.hass_dyson.select import DysonOscillationModeSelect
from custom_components.hass_dyson.switch import (
    DysonFindFollowSwitch,
    async_setup_entry as switch_setup_entry,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for a PC3 device with 'soon' in product-state."""
    coordinator = Mock()
    coordinator.serial_number = "PC3-EU-TST0000A"
    coordinator.device_name = "Find+Follow Purifier Cool PC3"
    coordinator.device = Mock()
    coordinator.device_capabilities = ["AdvanceOscillationDay1", "EnvironmentalData"]
    coordinator.device_category = ["ec"]
    coordinator.device.get_state_value = Mock(return_value="OFF")
    coordinator.config_entry = Mock()
    coordinator.config_entry.data = {"device_name": "PC3"}
    coordinator.data = {
        "product-state": {
            "fpwr": "ON",
            "oson": "OFF",
            "ancp": "CUST",
            "soon": "OFF",
            "sost": "OFF",
        }
    }
    return coordinator


@pytest.fixture
def mock_hass(mock_coordinator):
    """Create a mock Home Assistant instance."""
    hass = Mock()
    hass.data = {"hass_dyson": {mock_coordinator.serial_number: mock_coordinator}}
    return hass


@pytest.fixture
def mock_config_entry(mock_coordinator):
    """Create a mock config entry."""
    entry = Mock()
    entry.data = {CONF_HOSTNAME: "192.168.1.50", "connection_type": "local"}
    entry.unique_id = mock_coordinator.serial_number
    entry.entry_id = mock_coordinator.serial_number
    return entry


# ---------------------------------------------------------------------------
# Switch — entity creation gating
# ---------------------------------------------------------------------------


class TestFindFollowSwitchCreation:
    """Tests for conditional switch entity creation."""

    @pytest.mark.asyncio
    async def test_switch_created_when_soon_in_product_state(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Switch is created when 'soon' is present in product-state."""
        mock_add = MagicMock()
        await switch_setup_entry(mock_hass, mock_config_entry, mock_add)
        entities = mock_add.call_args[0][0]
        ff_switches = [e for e in entities if isinstance(e, DysonFindFollowSwitch)]
        assert len(ff_switches) == 1

    @pytest.mark.asyncio
    async def test_switch_not_created_when_soon_absent(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Switch is NOT created when 'soon' is absent from product-state."""
        del mock_coordinator.data["product-state"]["soon"]
        mock_add = MagicMock()
        await switch_setup_entry(mock_hass, mock_config_entry, mock_add)
        entities = mock_add.call_args[0][0]
        ff_switches = [e for e in entities if isinstance(e, DysonFindFollowSwitch)]
        assert len(ff_switches) == 0

    @pytest.mark.asyncio
    async def test_switch_not_created_when_coordinator_data_is_none(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Switch is NOT created when coordinator has no data yet."""
        mock_coordinator.data = None
        mock_add = MagicMock()
        await switch_setup_entry(mock_hass, mock_config_entry, mock_add)
        entities = mock_add.call_args[0][0]
        ff_switches = [e for e in entities if isinstance(e, DysonFindFollowSwitch)]
        assert len(ff_switches) == 0


# ---------------------------------------------------------------------------
# Switch — initialisation
# ---------------------------------------------------------------------------


class TestFindFollowSwitchInit:
    """Tests for switch attribute initialisation."""

    def test_unique_id(self, mock_coordinator):
        entity = DysonFindFollowSwitch(mock_coordinator)
        assert entity._attr_unique_id == "PC3-EU-TST0000A_find_follow"

    def test_translation_key(self, mock_coordinator):
        entity = DysonFindFollowSwitch(mock_coordinator)
        assert entity._attr_translation_key == "find_follow"

    def test_icon(self, mock_coordinator):
        entity = DysonFindFollowSwitch(mock_coordinator)
        assert entity._attr_icon == "mdi:account-eye"


# ---------------------------------------------------------------------------
# Switch — state reading
# ---------------------------------------------------------------------------


class TestFindFollowSwitchState:
    """Tests for switch state derived from 'soon' key."""

    def _make(self, coordinator, soon_value: str) -> DysonFindFollowSwitch:
        coordinator.device.get_state_value = Mock(
            side_effect=lambda data, key, default: (
                soon_value if key == "soon" else default
            )
        )
        entity = DysonFindFollowSwitch(coordinator)
        entity.async_write_ha_state = MagicMock()
        return entity

    def test_is_off_when_soon_off(self, mock_coordinator):
        entity = self._make(mock_coordinator, "OFF")
        entity._handle_coordinator_update()
        assert entity._attr_is_on is False

    def test_is_on_when_soon_on(self, mock_coordinator):
        entity = self._make(mock_coordinator, "ON")
        entity._handle_coordinator_update()
        assert entity._attr_is_on is True

    def test_is_on_when_soon_scan(self, mock_coordinator):
        """soon=SCAN should show switch as ON (scan implies F+F is active)."""
        entity = self._make(mock_coordinator, "SCAN")
        entity._handle_coordinator_update()
        assert entity._attr_is_on is True

    def test_is_none_when_no_device(self, mock_coordinator):
        mock_coordinator.device = None
        entity = DysonFindFollowSwitch(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        entity._handle_coordinator_update()
        assert entity._attr_is_on is None


# ---------------------------------------------------------------------------
# Switch — extra_state_attributes
# ---------------------------------------------------------------------------


class TestFindFollowSwitchAttributes:
    """Tests for switch extra_state_attributes."""

    def _make(self, coordinator, state: dict) -> DysonFindFollowSwitch:
        coordinator.data = {"product-state": state}
        coordinator.device.get_state_value = Mock(
            side_effect=lambda data, key, default: data.get(key, default)
        )
        return DysonFindFollowSwitch(coordinator)

    def test_returns_none_when_no_device(self, mock_coordinator):
        mock_coordinator.device = None
        entity = DysonFindFollowSwitch(mock_coordinator)
        assert entity.extra_state_attributes is None

    def test_off_state_attributes(self, mock_coordinator):
        entity = self._make(mock_coordinator, {"soon": "OFF", "sost": "OFF"})
        attrs = entity.extra_state_attributes
        assert attrs["find_follow_active"] is False
        assert attrs["find_follow_command"] == "OFF"
        assert attrs["find_follow_engine_status"] == "OFF"

    def test_on_state_attributes(self, mock_coordinator):
        entity = self._make(mock_coordinator, {"soon": "ON", "sost": "NOD"})
        attrs = entity.extra_state_attributes
        assert attrs["find_follow_active"] is True
        assert attrs["find_follow_command"] == "ON"
        assert attrs["find_follow_engine_status"] == "NOD"

    def test_scanning_state_attributes(self, mock_coordinator):
        entity = self._make(mock_coordinator, {"soon": "SCAN", "sost": "SCAN"})
        attrs = entity.extra_state_attributes
        assert attrs["find_follow_active"] is True
        assert attrs["find_follow_command"] == "SCAN"
        assert attrs["find_follow_engine_status"] == "SCAN"

    def test_all_keys_present(self, mock_coordinator):
        entity = self._make(mock_coordinator, {"soon": "ON", "sost": "NOD"})
        assert set(entity.extra_state_attributes.keys()) == {
            "find_follow_active",
            "find_follow_command",
            "find_follow_engine_status",
        }


# ---------------------------------------------------------------------------
# Switch — commands
# ---------------------------------------------------------------------------


class TestFindFollowSwitchCommands:
    """Tests for switch turn_on / turn_off."""

    @pytest.mark.asyncio
    async def test_turn_on_sends_soon_on(self, mock_coordinator):
        mock_coordinator.device.set_find_follow = AsyncMock()
        entity = DysonFindFollowSwitch(mock_coordinator)
        await entity.async_turn_on()
        mock_coordinator.device.set_find_follow.assert_awaited_once_with("ON")

    @pytest.mark.asyncio
    async def test_turn_off_sends_soon_off(self, mock_coordinator):
        mock_coordinator.device.set_find_follow = AsyncMock()
        entity = DysonFindFollowSwitch(mock_coordinator)
        await entity.async_turn_off()
        mock_coordinator.device.set_find_follow.assert_awaited_once_with("OFF")

    @pytest.mark.asyncio
    async def test_no_command_when_device_none(self, mock_coordinator):
        mock_coordinator.device = None
        entity = DysonFindFollowSwitch(mock_coordinator)
        await entity.async_turn_on()  # should not raise

    @pytest.mark.asyncio
    async def test_connection_error_logged_not_raised(self, mock_coordinator):
        mock_coordinator.device.set_find_follow = AsyncMock(
            side_effect=ConnectionError()
        )
        entity = DysonFindFollowSwitch(mock_coordinator)
        await entity.async_turn_on()

    @pytest.mark.asyncio
    async def test_unexpected_error_logged_not_raised(self, mock_coordinator):
        mock_coordinator.device.set_find_follow = AsyncMock(side_effect=RuntimeError())
        entity = DysonFindFollowSwitch(mock_coordinator)
        await entity.async_turn_off()


# ---------------------------------------------------------------------------
# Button — entity creation gating
# ---------------------------------------------------------------------------


class TestFindFollowScanButtonCreation:
    """Tests for conditional button entity creation."""

    @pytest.mark.asyncio
    async def test_button_created_when_soon_in_product_state(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Scan button is created when 'soon' is present in product-state."""
        mock_add = MagicMock()
        await button_setup_entry(mock_hass, mock_config_entry, mock_add)
        entities = mock_add.call_args[0][0]
        buttons = [e for e in entities if isinstance(e, DysonFindFollowScanButton)]
        assert len(buttons) == 1

    @pytest.mark.asyncio
    async def test_button_not_created_when_soon_absent(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Scan button is NOT created when 'soon' is absent."""
        del mock_coordinator.data["product-state"]["soon"]
        mock_add = MagicMock()
        await button_setup_entry(mock_hass, mock_config_entry, mock_add)
        entities = mock_add.call_args[0][0]
        buttons = [e for e in entities if isinstance(e, DysonFindFollowScanButton)]
        assert len(buttons) == 0

    @pytest.mark.asyncio
    async def test_button_created_regardless_of_switch_state(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Scan button is always visible when device supports F+F (soon=ON)."""
        mock_coordinator.data["product-state"]["soon"] = "ON"
        mock_add = MagicMock()
        await button_setup_entry(mock_hass, mock_config_entry, mock_add)
        entities = mock_add.call_args[0][0]
        buttons = [e for e in entities if isinstance(e, DysonFindFollowScanButton)]
        assert len(buttons) == 1


# ---------------------------------------------------------------------------
# Button — initialisation and press
# ---------------------------------------------------------------------------


class TestFindFollowScanButtonBehavior:
    """Tests for button attributes and press command."""

    def test_unique_id(self, mock_coordinator):
        entity = DysonFindFollowScanButton(mock_coordinator)
        assert entity._attr_unique_id == "PC3-EU-TST0000A_find_follow_scan"

    def test_translation_key(self, mock_coordinator):
        entity = DysonFindFollowScanButton(mock_coordinator)
        assert entity._attr_translation_key == "find_follow_scan"

    def test_icon(self, mock_coordinator):
        entity = DysonFindFollowScanButton(mock_coordinator)
        assert entity._attr_icon == "mdi:radar"

    @pytest.mark.asyncio
    async def test_press_sends_soon_scan(self, mock_coordinator):
        mock_coordinator.device.set_find_follow = AsyncMock()
        entity = DysonFindFollowScanButton(mock_coordinator)
        await entity.async_press()
        mock_coordinator.device.set_find_follow.assert_awaited_once_with("SCAN")

    @pytest.mark.asyncio
    async def test_press_does_nothing_when_device_none(self, mock_coordinator):
        mock_coordinator.device = None
        entity = DysonFindFollowScanButton(mock_coordinator)
        await entity.async_press()  # should not raise

    @pytest.mark.asyncio
    async def test_connection_error_logged_not_raised(self, mock_coordinator):
        mock_coordinator.device.set_find_follow = AsyncMock(
            side_effect=ConnectionError()
        )
        entity = DysonFindFollowScanButton(mock_coordinator)
        await entity.async_press()

    @pytest.mark.asyncio
    async def test_unexpected_error_logged_not_raised(self, mock_coordinator):
        mock_coordinator.device.set_find_follow = AsyncMock(side_effect=RuntimeError())
        entity = DysonFindFollowScanButton(mock_coordinator)
        await entity.async_press()


# ---------------------------------------------------------------------------
# ancp=SMRT interaction — switch reads 'soon', not 'ancp'
# ---------------------------------------------------------------------------


class TestFindFollowAncpSmrt:
    """Tests verifying correct behaviour when device reports ancp=SMRT."""

    def _make_switch(self, coordinator, state: dict) -> DysonFindFollowSwitch:
        coordinator.data = {"product-state": state}
        coordinator.device.get_state_value = Mock(
            side_effect=lambda data, key, default: data.get(key, default)
        )
        entity = DysonFindFollowSwitch(coordinator)
        entity.async_write_ha_state = MagicMock()
        return entity

    def _make_osc(self, coordinator, state: dict) -> DysonOscillationModeSelect:
        coordinator.data = {"product-state": state}
        coordinator.device.get_state_value = Mock(
            side_effect=lambda data, key, default: data.get(key, default)
        )
        entity = DysonOscillationModeSelect(coordinator)
        entity.async_write_ha_state = MagicMock()
        return entity

    def test_switch_is_on_when_soon_on_and_ancp_smrt(self, mock_coordinator):
        """Switch reads soon=ON, ignores ancp=SMRT."""
        state = {"soon": "ON", "sost": "NOD", "ancp": "SMRT", "oson": "OFF"}
        entity = self._make_switch(mock_coordinator, state)
        entity._handle_coordinator_update()
        assert entity._attr_is_on is True

    def test_switch_is_off_when_soon_off_despite_ancp_smrt(self, mock_coordinator):
        """Switch shows Off when soon=OFF even if ancp is still SMRT mid-transition."""
        state = {"soon": "OFF", "sost": "OFF", "ancp": "SMRT"}
        entity = self._make_switch(mock_coordinator, state)
        entity._handle_coordinator_update()
        assert entity._attr_is_on is False

    def test_switch_is_on_when_soon_scan_and_ancp_smrt(self, mock_coordinator):
        """Switch shows ON during scan (soon=SCAN) with ancp=SMRT."""
        state = {"soon": "SCAN", "sost": "SCAN", "ancp": "SMRT"}
        entity = self._make_switch(mock_coordinator, state)
        entity._handle_coordinator_update()
        assert entity._attr_is_on is True

    def test_oscillation_select_returns_custom_when_ancp_smrt(self, mock_coordinator):
        """Oscillation select falls through to span detection for ancp=SMRT."""
        state = {
            "soon": "ON",
            "ancp": "SMRT",
            "oson": "OFF",
            "osal": "0180",
            "osau": "0180",
        }
        entity = self._make_osc(mock_coordinator, state)
        assert entity._detect_mode_from_angles() == "Custom"

    def test_oscillation_select_does_not_crash_when_ancp_smrt(self, mock_coordinator):
        """Oscillation select does not raise for ancp=SMRT."""
        state = {
            "soon": "ON",
            "ancp": "SMRT",
            "oson": "OFF",
            "osal": "0120",
            "osau": "0240",
        }
        entity = self._make_osc(mock_coordinator, state)
        assert entity._detect_mode_from_angles() == "Custom"
