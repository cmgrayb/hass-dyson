"""Tests for Find+Follow mode select entity (DysonFindFollowModeSelect)."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from custom_components.hass_dyson.const import CONF_HOSTNAME
from custom_components.hass_dyson.select import (
    DysonFindFollowModeSelect,
    DysonOscillationModeSelect,
    async_setup_entry,
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
    coordinator.data = {
        "product-state": {
            "fpwr": "ON",
            "oson": "OFF",
            "osal": "0180",
            "osau": "0180",
            "ancp": "CUST",
            "soon": "OFF",
            "sost": "OFF",
        }
    }
    return coordinator


@pytest.fixture
def mock_coordinator_no_find_follow():
    """Create a mock coordinator for a device without 'soon' in product-state."""
    coordinator = Mock()
    coordinator.serial_number = "TP04-EU-TST0000A"
    coordinator.device_name = "Purifier Cool TP04"
    coordinator.device = Mock()
    coordinator.device_capabilities = ["AdvanceOscillationDay1", "EnvironmentalData"]
    coordinator.device_category = ["ec"]
    coordinator.device.get_state_value = Mock(return_value="OFF")
    coordinator.data = {
        "product-state": {
            "fpwr": "ON",
            "oson": "OFF",
            "osal": "0090",
            "osau": "0270",
            "ancp": "0180",
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
# async_setup_entry — entity creation gating
# ---------------------------------------------------------------------------


class TestFindFollowEntityCreation:
    """Tests for conditional entity creation based on 'soon' key presence."""

    @pytest.mark.asyncio
    async def test_entity_created_when_soon_in_product_state(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Entity is created when 'soon' is present in product-state."""
        mock_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        entities = mock_add_entities.call_args[0][0]
        find_follow_entities = [
            e for e in entities if isinstance(e, DysonFindFollowModeSelect)
        ]
        assert len(find_follow_entities) == 1

    @pytest.mark.asyncio
    async def test_entity_not_created_when_soon_absent(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Entity is NOT created when 'soon' is absent from product-state."""
        # Remove 'soon' from product-state
        del mock_coordinator.data["product-state"]["soon"]
        del mock_coordinator.data["product-state"]["sost"]

        mock_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        entities = mock_add_entities.call_args[0][0]
        find_follow_entities = [
            e for e in entities if isinstance(e, DysonFindFollowModeSelect)
        ]
        assert len(find_follow_entities) == 0

    @pytest.mark.asyncio
    async def test_entity_not_created_when_coordinator_data_is_none(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Entity is NOT created when coordinator has no data yet."""
        mock_coordinator.data = None

        mock_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        entities = mock_add_entities.call_args[0][0]
        find_follow_entities = [
            e for e in entities if isinstance(e, DysonFindFollowModeSelect)
        ]
        assert len(find_follow_entities) == 0

    @pytest.mark.asyncio
    async def test_find_follow_and_oscillation_both_created_for_pc3(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Both oscillation select and Find+Follow select are created for a PC3."""
        mock_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        entities = mock_add_entities.call_args[0][0]
        entity_types = [type(e) for e in entities]
        assert DysonOscillationModeSelect in entity_types
        assert DysonFindFollowModeSelect in entity_types


# ---------------------------------------------------------------------------
# DysonFindFollowModeSelect — initialisation
# ---------------------------------------------------------------------------


class TestFindFollowModeSelectInit:
    """Tests for entity attribute initialisation."""

    def test_unique_id(self, mock_coordinator):
        """Unique ID incorporates device serial number."""
        entity = DysonFindFollowModeSelect(mock_coordinator)
        assert entity._attr_unique_id == "PC3-EU-TST0000A_find_follow_mode"

    def test_translation_key(self, mock_coordinator):
        """Translation key is 'find_follow_mode'."""
        entity = DysonFindFollowModeSelect(mock_coordinator)
        assert entity._attr_translation_key == "find_follow_mode"

    def test_icon(self, mock_coordinator):
        """Icon is mdi:account-eye."""
        entity = DysonFindFollowModeSelect(mock_coordinator)
        assert entity._attr_icon == "mdi:account-eye"

    def test_options(self, mock_coordinator):
        """Options list contains Off, Find+Follow, and Scanning."""
        entity = DysonFindFollowModeSelect(mock_coordinator)
        assert entity._attr_options == ["Off", "Find+Follow", "Scanning"]


# ---------------------------------------------------------------------------
# DysonFindFollowModeSelect — state reading
# ---------------------------------------------------------------------------


class TestFindFollowModeSelectState:
    """Tests for state reading from device product-state."""

    def _make_entity(self, coordinator, soon_value: str) -> DysonFindFollowModeSelect:
        """Helper: build an entity and wire get_state_value to return soon_value for 'soon'."""
        coordinator.device.get_state_value = Mock(
            side_effect=lambda data, key, default: (
                soon_value if key == "soon" else default
            )
        )
        entity = DysonFindFollowModeSelect(coordinator)
        # Stub out HA state-writing machinery so unit tests don't need a live hass.
        entity.async_write_ha_state = MagicMock()
        return entity

    def test_state_off_when_soon_is_off(self, mock_coordinator):
        """State is 'Off' when soon == 'OFF'."""
        entity = self._make_entity(mock_coordinator, "OFF")
        entity._handle_coordinator_update()
        assert entity._attr_current_option == "Off"

    def test_state_find_follow_when_soon_is_on(self, mock_coordinator):
        """State is 'Find+Follow' when soon == 'ON'."""
        entity = self._make_entity(mock_coordinator, "ON")
        entity._handle_coordinator_update()
        assert entity._attr_current_option == "Find+Follow"

    def test_state_scanning_when_soon_is_scan(self, mock_coordinator):
        """State is 'Scanning' when soon == 'SCAN'."""
        entity = self._make_entity(mock_coordinator, "SCAN")
        entity._handle_coordinator_update()
        assert entity._attr_current_option == "Scanning"

    def test_state_off_fallback_for_unknown_soon_value(self, mock_coordinator):
        """Unknown soon value falls back to 'Off' (safe default)."""
        entity = self._make_entity(mock_coordinator, "UNKNOWN")
        entity._handle_coordinator_update()
        assert entity._attr_current_option == "Off"

    def test_state_none_when_device_is_none(self, mock_coordinator):
        """current_option is None when coordinator has no device."""
        mock_coordinator.device = None
        entity = DysonFindFollowModeSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()
        entity._handle_coordinator_update()
        assert entity._attr_current_option is None


# ---------------------------------------------------------------------------
# DysonFindFollowModeSelect — option selection (commands)
# ---------------------------------------------------------------------------


class TestFindFollowModeSelectCommands:
    """Tests for option selection sending correct device commands."""

    @pytest.mark.asyncio
    async def test_select_off_sends_soon_off(self, mock_coordinator):
        """Selecting 'Off' calls set_find_follow('OFF')."""
        mock_coordinator.device.set_find_follow = AsyncMock()
        entity = DysonFindFollowModeSelect(mock_coordinator)

        await entity.async_select_option("Off")

        mock_coordinator.device.set_find_follow.assert_awaited_once_with("OFF")

    @pytest.mark.asyncio
    async def test_select_find_follow_sends_soon_on(self, mock_coordinator):
        """Selecting 'Find+Follow' calls set_find_follow('ON')."""
        mock_coordinator.device.set_find_follow = AsyncMock()
        entity = DysonFindFollowModeSelect(mock_coordinator)

        await entity.async_select_option("Find+Follow")

        mock_coordinator.device.set_find_follow.assert_awaited_once_with("ON")

    @pytest.mark.asyncio
    async def test_select_scanning_sends_soon_scan(self, mock_coordinator):
        """Selecting 'Scanning' calls set_find_follow('SCAN')."""
        mock_coordinator.device.set_find_follow = AsyncMock()
        entity = DysonFindFollowModeSelect(mock_coordinator)

        await entity.async_select_option("Scanning")

        mock_coordinator.device.set_find_follow.assert_awaited_once_with("SCAN")

    @pytest.mark.asyncio
    async def test_optimistic_update_on_selection(self, mock_coordinator):
        """current_option is updated optimistically after a selection."""
        mock_coordinator.device.set_find_follow = AsyncMock()
        entity = DysonFindFollowModeSelect(mock_coordinator)
        entity.async_write_ha_state = MagicMock()

        await entity.async_select_option("Find+Follow")

        assert entity._attr_current_option == "Find+Follow"
        entity.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_option_logs_error_no_command_sent(self, mock_coordinator):
        """An unrecognised option logs an error and sends no command."""
        mock_coordinator.device.set_find_follow = AsyncMock()
        entity = DysonFindFollowModeSelect(mock_coordinator)

        await entity.async_select_option("Invalid")

        mock_coordinator.device.set_find_follow.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_command_when_device_is_none(self, mock_coordinator):
        """No command is sent when device is unavailable."""
        mock_coordinator.device = None
        entity = DysonFindFollowModeSelect(mock_coordinator)

        # Should return immediately without raising
        await entity.async_select_option("Find+Follow")

    @pytest.mark.asyncio
    async def test_connection_error_is_logged_not_raised(self, mock_coordinator):
        """ConnectionError during command is caught and logged, not re-raised."""
        mock_coordinator.device.set_find_follow = AsyncMock(
            side_effect=ConnectionError("MQTT disconnected")
        )
        entity = DysonFindFollowModeSelect(mock_coordinator)

        # Must not propagate
        await entity.async_select_option("Find+Follow")

    @pytest.mark.asyncio
    async def test_timeout_error_is_logged_not_raised(self, mock_coordinator):
        """TimeoutError during command is caught and logged, not re-raised."""
        mock_coordinator.device.set_find_follow = AsyncMock(
            side_effect=TimeoutError("device did not respond")
        )
        entity = DysonFindFollowModeSelect(mock_coordinator)

        await entity.async_select_option("Off")

    @pytest.mark.asyncio
    async def test_value_error_is_logged_not_raised(self, mock_coordinator):
        """ValueError from device method is caught and logged, not re-raised."""
        mock_coordinator.device.set_find_follow = AsyncMock(
            side_effect=ValueError("bad mode")
        )
        entity = DysonFindFollowModeSelect(mock_coordinator)

        await entity.async_select_option("Scanning")

    @pytest.mark.asyncio
    async def test_unexpected_error_is_logged_not_raised(self, mock_coordinator):
        """Unexpected exceptions are caught and logged, not re-raised."""
        mock_coordinator.device.set_find_follow = AsyncMock(
            side_effect=RuntimeError("unexpected")
        )
        entity = DysonFindFollowModeSelect(mock_coordinator)

        await entity.async_select_option("Find+Follow")


# ---------------------------------------------------------------------------
# ancp=SMRT interaction — Find+Follow select reads 'soon', not 'ancp'
# ---------------------------------------------------------------------------


class TestFindFollowAncpSmrt:
    """Tests verifying correct behaviour when device reports ancp=SMRT.

    When Find+Follow is active the device sets ancp=SMRT as a side-effect.
    The Find+Follow select entity must continue to derive its state from
    ``soon``, not from ``ancp``.  The oscillation select must handle
    ancp=SMRT gracefully (falls through to span-based detection → "Custom").
    """

    def _make_ff_entity(self, coordinator, state: dict) -> DysonFindFollowModeSelect:
        """Helper: build F+F entity with a full realistic product-state dict."""
        coordinator.data = {"product-state": state}
        coordinator.device.get_state_value = Mock(
            side_effect=lambda data, key, default: data.get(key, default)
        )
        entity = DysonFindFollowModeSelect(coordinator)
        entity.async_write_ha_state = MagicMock()
        return entity

    def _make_osc_entity(self, coordinator, state: dict) -> DysonOscillationModeSelect:
        """Helper: build oscillation select with a full realistic product-state dict."""
        coordinator.data = {"product-state": state}
        coordinator.device.get_state_value = Mock(
            side_effect=lambda data, key, default: data.get(key, default)
        )
        entity = DysonOscillationModeSelect(coordinator)
        entity.async_write_ha_state = MagicMock()
        return entity

    # -- Find+Follow select --------------------------------------------------

    def test_find_follow_reads_soon_not_ancp(self, mock_coordinator):
        """F+F select shows 'Find+Follow' when soon=ON even though ancp=SMRT."""
        state = {
            "soon": "ON",
            "sost": "NOD",
            "ancp": "SMRT",
            "oson": "OFF",
            "osal": "0180",
            "osau": "0180",
        }
        entity = self._make_ff_entity(mock_coordinator, state)
        entity._handle_coordinator_update()
        assert entity._attr_current_option == "Find+Follow"

    def test_find_follow_shows_off_when_soon_off_despite_ancp_smrt(
        self, mock_coordinator
    ):
        """F+F select shows 'Off' when soon=OFF even if ancp hasn't reverted yet.

        The disable trace shows ancp still showing SMRT as the old value in
        the first state element before transitioning to CUST.  soon is the
        authoritative key.
        """
        state = {
            "soon": "OFF",
            "sost": "OFF",
            "ancp": "SMRT",  # stale — device is mid-transition
            "oson": "OFF",
            "osal": "0180",
            "osau": "0180",
        }
        entity = self._make_ff_entity(mock_coordinator, state)
        entity._handle_coordinator_update()
        assert entity._attr_current_option == "Off"

    def test_find_follow_shows_scanning_when_soon_scan_and_ancp_smrt(
        self, mock_coordinator
    ):
        """F+F select shows 'Scanning' when soon=SCAN and ancp=SMRT."""
        state = {
            "soon": "SCAN",
            "sost": "SCAN",
            "ancp": "SMRT",
            "oson": "OFF",
            "osal": "0180",
            "osau": "0180",
        }
        entity = self._make_ff_entity(mock_coordinator, state)
        entity._handle_coordinator_update()
        assert entity._attr_current_option == "Scanning"

    # -- Oscillation select --------------------------------------------------

    def test_oscillation_select_returns_custom_when_ancp_smrt(self, mock_coordinator):
        """Oscillation select falls through to span detection when ancp=SMRT.

        ancp=SMRT is not in _PRESET_ANCP_MAP and does not match 'BRZE', so
        the select falls through to osal/osau span detection.  With equal
        osal/osau (span=0, as seen on the PC3 in F+F mode) no preset matches,
        giving 'Custom'.
        """
        state = {
            "soon": "ON",
            "sost": "NOD",
            "ancp": "SMRT",
            "oson": "OFF",
            "osal": "0180",
            "osau": "0180",  # span = 0 → no preset match → Custom
        }
        entity = self._make_osc_entity(mock_coordinator, state)
        result = entity._detect_mode_from_angles()
        assert result == "Custom"

    def test_oscillation_select_does_not_crash_when_ancp_smrt(self, mock_coordinator):
        """Oscillation select handles ancp=SMRT without raising an exception."""
        state = {
            "soon": "ON",
            "sost": "SCAN",
            "ancp": "SMRT",
            "oson": "OFF",
            "osal": "0120",
            "osau": "0240",  # span = 120 → no preset → Custom
        }
        entity = self._make_osc_entity(mock_coordinator, state)
        # Must not raise
        result = entity._detect_mode_from_angles()
        assert result == "Custom"


# ---------------------------------------------------------------------------
# DysonFindFollowModeSelect — extra_state_attributes (scene support)
# ---------------------------------------------------------------------------


class TestFindFollowExtraStateAttributes:
    """Test extra_state_attributes for scene support."""

    def _make_entity(self, coordinator, state: dict) -> DysonFindFollowModeSelect:
        """Helper: build entity with given product-state."""
        coordinator.data = {"product-state": state}
        coordinator.device.get_state_value = Mock(
            side_effect=lambda data, key, default: data.get(key, default)
        )
        entity = DysonFindFollowModeSelect(coordinator)
        # Set current_option from the soon value to mirror real state
        soon = state.get("soon", "OFF")
        entity._attr_current_option = DysonFindFollowModeSelect._SOON_TO_OPTION.get(
            soon, "Off"
        )
        return entity

    def test_returns_none_when_no_device(self, mock_coordinator):
        """Returns None when device is unavailable."""
        mock_coordinator.device = None
        entity = DysonFindFollowModeSelect(mock_coordinator)
        assert entity.extra_state_attributes is None

    def test_off_state_attributes(self, mock_coordinator):
        """Correct attributes when Find+Follow is Off."""
        state = {"soon": "OFF", "sost": "OFF"}
        entity = self._make_entity(mock_coordinator, state)

        attrs = entity.extra_state_attributes

        assert attrs["find_follow_mode"] == "Off"
        assert attrs["find_follow_active"] is False
        assert attrs["find_follow_command"] == "OFF"
        assert attrs["find_follow_engine_status"] == "OFF"

    def test_on_state_attributes(self, mock_coordinator):
        """Correct attributes when Find+Follow is active (NOD = standby tracking)."""
        state = {"soon": "ON", "sost": "NOD"}
        entity = self._make_entity(mock_coordinator, state)

        attrs = entity.extra_state_attributes

        assert attrs["find_follow_mode"] == "Find+Follow"
        assert attrs["find_follow_active"] is True
        assert attrs["find_follow_command"] == "ON"
        assert attrs["find_follow_engine_status"] == "NOD"

    def test_scanning_state_attributes(self, mock_coordinator):
        """Correct attributes during an active scan."""
        state = {"soon": "SCAN", "sost": "SCAN"}
        entity = self._make_entity(mock_coordinator, state)

        attrs = entity.extra_state_attributes

        assert attrs["find_follow_mode"] == "Scanning"
        assert attrs["find_follow_active"] is True
        assert attrs["find_follow_command"] == "SCAN"
        assert attrs["find_follow_engine_status"] == "SCAN"

    def test_all_required_keys_present(self, mock_coordinator):
        """All four expected keys are always present."""
        state = {"soon": "ON", "sost": "NOD"}
        entity = self._make_entity(mock_coordinator, state)

        attrs = entity.extra_state_attributes

        assert set(attrs.keys()) == {
            "find_follow_mode",
            "find_follow_active",
            "find_follow_command",
            "find_follow_engine_status",
        }
