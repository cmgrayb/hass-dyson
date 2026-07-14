"""Test vacuum platform for Dyson integration."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.components.vacuum import Segment, VacuumActivity, VacuumEntityFeature
from homeassistant.exceptions import HomeAssistantError

from custom_components.hass_dyson.const import (
    DEVICE_CATEGORY_ROBOT,
    DOMAIN,
    ROBOT_STATE_FAULT_CRITICAL,
    ROBOT_STATE_FULL_CLEAN_PAUSED,
    ROBOT_STATE_FULL_CLEAN_RUNNING,
    ROBOT_STATE_INACTIVE_CHARGED,
)
from custom_components.hass_dyson.vacuum import (
    DysonVacuumEntity,
    _clean_maps_cache,
    _clean_maps_locks,
    async_setup_entry,
    fetch_clean_maps,
)


@pytest.fixture
def mock_coordinator_robot():
    """Create a mock coordinator for robot vacuum."""
    coordinator = MagicMock()
    coordinator.serial_number = "ROBOT-TEST-123"
    coordinator.device_name = "Test Robot Vacuum"
    coordinator.device_category = [DEVICE_CATEGORY_ROBOT]
    coordinator.device_capabilities = ["RobotVacuum"]

    coordinator.data = {
        "product-state": {
            "state": "INACTIVE_CHARGED",
            "batteryChargeLevel": 100,
            "globalPosition": [1250, 800],
            "fullCleanType": "",
            "cleanId": "",
        }
    }

    # Mock device with robot vacuum methods
    coordinator.device = MagicMock()
    coordinator.device.robot_state = "INACTIVE_CHARGED"
    coordinator.device.robot_battery_level = 100
    coordinator.device.robot_global_position = [1250, 800]
    coordinator.device.robot_full_clean_type = ""
    coordinator.device.robot_clean_id = ""

    # Mock robot command methods
    coordinator.device.robot_pause = AsyncMock()
    coordinator.device.robot_resume = AsyncMock()
    coordinator.device.robot_start_clean = AsyncMock()
    coordinator.device.robot_abort = AsyncMock()
    coordinator.device.robot_request_state = AsyncMock()

    coordinator.async_request_refresh = AsyncMock()

    # Config entry without auth_token by default (non-Vis Nav robot).
    # Tests that require zone support should set coordinator.config_entry.data
    # to include auth_token="some_token".
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {}

    return coordinator


@pytest.fixture
def mock_coordinator_non_robot():
    """Create a mock coordinator for non-robot device."""
    coordinator = MagicMock()
    coordinator.serial_number = "FAN-TEST-123"
    coordinator.device_name = "Test Fan"
    coordinator.device_category = ["ec"]  # Environment cleaner, not robot
    coordinator.device_capabilities = ["Fan", "AutoMode"]

    return coordinator


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry_id"
    return config_entry


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": MagicMock()}}
    return hass


class TestVacuumSetup:
    """Test vacuum platform setup."""

    @pytest.mark.asyncio
    async def test_setup_robot_vacuum(
        self, mock_hass, mock_config_entry, mock_coordinator_robot
    ):
        """Test setup of robot vacuum entity."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator_robot
        add_entities = AsyncMock()

        await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        # Should create vacuum entity
        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DysonVacuumEntity)

    @pytest.mark.asyncio
    async def test_setup_non_robot_device(
        self, mock_hass, mock_config_entry, mock_coordinator_non_robot
    ):
        """Test setup skips non-robot devices."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator_non_robot
        add_entities = AsyncMock()

        await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        # Should not create vacuum entity
        add_entities.assert_not_called()


class TestDysonVacuumEntity:
    """Test DysonVacuumEntity functionality."""

    def test_init(self, mock_coordinator_robot):
        """Test vacuum entity initialization."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        assert entity._attr_unique_id == "ROBOT-TEST-123_vacuum"
        assert entity._attr_name is None  # Uses device name
        assert entity._attr_has_entity_name is True

        # Check supported features - battery monitoring moved to separate sensor
        # to comply with Home Assistant deprecation (HA 2026.8).
        # START + RETURN_HOME added when zone-cleaning support landed.
        expected_features = (
            VacuumEntityFeature.START
            | VacuumEntityFeature.PAUSE
            | VacuumEntityFeature.STOP
            | VacuumEntityFeature.RETURN_HOME
            | VacuumEntityFeature.STATE
        )
        assert entity._attr_supported_features == expected_features
        # Verify BATTERY feature is not present
        assert not (entity._attr_supported_features & VacuumEntityFeature.BATTERY)

    def test_state_mapping(self, mock_coordinator_robot):
        """Test robot state to HA state mapping."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Test various robot states
        test_cases = [
            ("FULL_CLEAN_RUNNING", VacuumActivity.CLEANING),
            ("FULL_CLEAN_PAUSED", VacuumActivity.PAUSED),
            ("INACTIVE_CHARGED", VacuumActivity.DOCKED),
            ("MAPPING_RUNNING", VacuumActivity.IDLE),
            ("FAULT_CRITICAL", VacuumActivity.ERROR),
        ]

        for robot_state, expected_ha_state in test_cases:
            mock_coordinator_robot.device.robot_state = robot_state
            assert entity.activity == expected_ha_state

    def test_state_unavailable_device(self, mock_coordinator_robot):
        """Test state when device is unavailable."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Mock missing device
        mock_coordinator_robot.device = None
        assert entity.activity is None

        # Mock device unavailable through coordinator
        mock_coordinator_robot.device = MagicMock()
        mock_coordinator_robot.device.robot_state = "INACTIVE_CHARGED"
        with patch.object(entity.coordinator, "last_update_success", False):
            # Entity inherits available from parent, which checks coordinator
            assert entity.activity is None

    def test_state_unknown_robot_state(self, mock_coordinator_robot):
        """Test state with unknown robot state."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        mock_coordinator_robot.device.robot_state = None
        assert entity.activity is None

    def test_extra_state_attributes(self, mock_coordinator_robot):
        """Test additional state attributes."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Setup mock device with all attributes
        mock_coordinator_robot.device.robot_state = "FULL_CLEAN_RUNNING"
        mock_coordinator_robot.device.robot_global_position = [1200, 850]
        mock_coordinator_robot.device.robot_full_clean_type = "immediate"
        mock_coordinator_robot.device.robot_clean_id = "clean_20251217_103245"

        attributes = entity.extra_state_attributes

        expected_attributes = {
            "raw_state": "FULL_CLEAN_RUNNING",
            "global_position": [1200, 850],
            "full_clean_type": "immediate",
            "clean_id": "clean_20251217_103245",
        }
        assert attributes == expected_attributes

    def test_extra_state_attributes_empty(self, mock_coordinator_robot):
        """Test attributes when device data is not available."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Test missing device
        mock_coordinator_robot.device = None
        assert entity.extra_state_attributes == {}

        # Test unavailable device through coordinator
        mock_coordinator_robot.device = MagicMock()
        with patch.object(entity.coordinator, "last_update_success", False):
            assert entity.extra_state_attributes == {}

    def test_extra_state_attributes_partial(self, mock_coordinator_robot):
        """Test attributes with partial data."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Setup device with only some attributes
        mock_coordinator_robot.device.robot_state = "INACTIVE_CHARGED"
        mock_coordinator_robot.device.robot_global_position = None
        mock_coordinator_robot.device.robot_full_clean_type = None
        mock_coordinator_robot.device.robot_clean_id = None

        attributes = entity.extra_state_attributes
        expected_attributes = {"raw_state": "INACTIVE_CHARGED"}
        assert attributes == expected_attributes

    def test_extra_state_attributes_no_state_with_position(
        self, mock_coordinator_robot
    ):
        """Test attributes when robot_state is None but global_position is set.

        Covers the branch where the robot_state condition (line 202) is False
        and execution falls through to the robot_global_position check.
        """
        entity = DysonVacuumEntity(mock_coordinator_robot)

        mock_coordinator_robot.device.robot_state = None
        mock_coordinator_robot.device.robot_global_position = [500, 300]
        mock_coordinator_robot.device.robot_full_clean_type = None
        mock_coordinator_robot.device.robot_clean_id = None

        attributes = entity.extra_state_attributes
        assert attributes == {"global_position": [500, 300]}

    @pytest.mark.asyncio
    async def test_pause(self, mock_coordinator_robot):
        """Test pause command."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        await entity.async_pause()

        mock_coordinator_robot.device.robot_pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_unavailable_device(self, mock_coordinator_robot):
        """Test pause command with unavailable device."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Mock coordinator unavailable
        with patch.object(entity.coordinator, "last_update_success", False):
            with pytest.raises(HomeAssistantError, match="Device not available"):
                await entity.async_pause()

        mock_coordinator_robot.device.robot_pause.assert_not_called()

    @pytest.mark.asyncio
    async def test_pause_missing_device(self, mock_coordinator_robot):
        """Test pause command with missing device."""
        entity = DysonVacuumEntity(mock_coordinator_robot)
        mock_coordinator_robot.device = None

        with pytest.raises(HomeAssistantError, match="Device not available"):
            await entity.async_pause()

    @pytest.mark.asyncio
    async def test_pause_command_failure(self, mock_coordinator_robot):
        """Test pause command failure handling."""
        entity = DysonVacuumEntity(mock_coordinator_robot)
        mock_coordinator_robot.device.robot_pause.side_effect = Exception("MQTT error")

        with pytest.raises(HomeAssistantError, match="Failed to pause vacuum"):
            await entity.async_pause()

    @pytest.mark.asyncio
    async def test_start_resume(self, mock_coordinator_robot):
        """Test start command resumes when the robot is paused mid-clean."""
        # Set the device to a paused mid-clean state so async_start() takes the
        # RESUME branch — the START-new-clean branch is covered in
        # test_start_from_dock_calls_robot_start_clean.
        mock_coordinator_robot.device.robot_state = "FULL_CLEAN_PAUSED"
        entity = DysonVacuumEntity(mock_coordinator_robot)

        await entity.async_start()

        mock_coordinator_robot.device.robot_resume.assert_called_once()
        mock_coordinator_robot.device.robot_start_clean.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_from_dock_calls_robot_start_clean(
        self, mock_coordinator_robot
    ):
        """Test start command begins a new clean when the robot is on the dock."""
        # INACTIVE_CHARGED is the default in the fixture — set explicitly here
        # so the test stays correct if the fixture default ever changes.
        mock_coordinator_robot.device.robot_state = "INACTIVE_CHARGED"
        entity = DysonVacuumEntity(mock_coordinator_robot)

        await entity.async_start()

        mock_coordinator_robot.device.robot_start_clean.assert_called_once()
        mock_coordinator_robot.device.robot_resume.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_unavailable_device(self, mock_coordinator_robot):
        """Test start command with unavailable device."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Mock coordinator unavailable
        with patch.object(entity.coordinator, "last_update_success", False):
            with pytest.raises(HomeAssistantError, match="Device not available"):
                await entity.async_start()

        mock_coordinator_robot.device.robot_resume.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_command_failure(self, mock_coordinator_robot):
        """Test start command failure handling."""
        entity = DysonVacuumEntity(mock_coordinator_robot)
        # State is INACTIVE_CHARGED so async_start calls robot_start_clean, not robot_resume
        mock_coordinator_robot.device.robot_start_clean.side_effect = Exception(
            "Connection lost"
        )

        with pytest.raises(HomeAssistantError, match="Failed to start vacuum"):
            await entity.async_start()

    @pytest.mark.asyncio
    async def test_stop(self, mock_coordinator_robot):
        """Test stop command."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        await entity.async_stop()

        mock_coordinator_robot.device.robot_abort.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_with_kwargs(self, mock_coordinator_robot):
        """Test stop command with additional kwargs."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        await entity.async_stop(some_param="value")

        mock_coordinator_robot.device.robot_abort.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_unavailable_device(self, mock_coordinator_robot):
        """Test stop command with unavailable device."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Mock coordinator unavailable
        with patch.object(entity.coordinator, "last_update_success", False):
            with pytest.raises(HomeAssistantError, match="Device not available"):
                await entity.async_stop()

        mock_coordinator_robot.device.robot_abort.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_command_failure(self, mock_coordinator_robot):
        """Test stop command failure handling."""
        entity = DysonVacuumEntity(mock_coordinator_robot)
        mock_coordinator_robot.device.robot_abort.side_effect = RuntimeError(
            "Device offline"
        )

        with pytest.raises(HomeAssistantError, match="Failed to stop vacuum"):
            await entity.async_stop()

    @pytest.mark.asyncio
    async def test_return_to_base(self, mock_coordinator_robot):
        """Test return to base command."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        await entity.async_return_to_base()

        # Should call robot_abort (same as stop)
        mock_coordinator_robot.device.robot_abort.assert_called_once()

    @pytest.mark.asyncio
    async def test_return_to_base_with_kwargs(self, mock_coordinator_robot):
        """Test return to base command with kwargs."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        await entity.async_return_to_base(param="test")

        mock_coordinator_robot.device.robot_abort.assert_called_once()

    @pytest.mark.asyncio
    async def test_return_to_base_failure(self, mock_coordinator_robot):
        """Test return to base command failure."""
        entity = DysonVacuumEntity(mock_coordinator_robot)
        mock_coordinator_robot.device.robot_abort.side_effect = Exception(
            "Network error"
        )

        with pytest.raises(HomeAssistantError, match="Failed to stop vacuum"):
            await entity.async_return_to_base()


class TestVacuumEntityIntegration:
    """Test vacuum entity integration scenarios."""

    def test_availability_logic(self, mock_coordinator_robot):
        """Test entity availability logic."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Mock the parent availability property
        with patch("custom_components.hass_dyson.vacuum.DysonEntity.available", True):
            # Device present and coordinator available
            assert entity.available is True

        with patch("custom_components.hass_dyson.vacuum.DysonEntity.available", False):
            # Coordinator not available
            assert entity.available is False

    @pytest.mark.asyncio
    async def test_state_updates(self, mock_coordinator_robot):
        """Test entity responds to state updates."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Initial state
        mock_coordinator_robot.device.robot_state = ROBOT_STATE_INACTIVE_CHARGED
        assert entity.activity == VacuumActivity.DOCKED

        # State change to cleaning
        mock_coordinator_robot.device.robot_state = ROBOT_STATE_FULL_CLEAN_RUNNING
        assert entity.activity == VacuumActivity.CLEANING

        # State change to paused
        mock_coordinator_robot.device.robot_state = ROBOT_STATE_FULL_CLEAN_PAUSED
        assert entity.activity == VacuumActivity.PAUSED

        # State change to error
        mock_coordinator_robot.device.robot_state = ROBOT_STATE_FAULT_CRITICAL
        assert entity.activity == VacuumActivity.ERROR

    def test_position_tracking(self, mock_coordinator_robot):
        """Test position tracking in attributes."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Test position updates
        positions = [
            [1000, 500],
            [1100, 600],
            [1200, 700],
        ]

        for position in positions:
            mock_coordinator_robot.device.robot_global_position = position
            attributes = entity.extra_state_attributes
            assert attributes.get("global_position") == position

    def test_cleaning_session_tracking(self, mock_coordinator_robot):
        """Test cleaning session information tracking."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Test cleaning session updates
        mock_coordinator_robot.device.robot_full_clean_type = "immediate"
        mock_coordinator_robot.device.robot_clean_id = "session_123"

        attributes = entity.extra_state_attributes
        assert attributes.get("full_clean_type") == "immediate"
        assert attributes.get("clean_id") == "session_123"

        # Test session cleared
        mock_coordinator_robot.device.robot_full_clean_type = None
        mock_coordinator_robot.device.robot_clean_id = None

        attributes = entity.extra_state_attributes
        assert "full_clean_type" not in attributes
        assert "clean_id" not in attributes


class TestVacuumEntityErrorHandling:
    """Test vacuum entity error handling scenarios."""

    @pytest.mark.asyncio
    async def test_command_timeout_handling(self, mock_coordinator_robot):
        """Test handling of command timeouts."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        mock_coordinator_robot.device.robot_pause.side_effect = TimeoutError(
            "Command timeout"
        )

        with pytest.raises(HomeAssistantError, match="Failed to pause vacuum"):
            await entity.async_pause()

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, mock_coordinator_robot):
        """Test handling of connection errors."""
        entity = DysonVacuumEntity(mock_coordinator_robot)
        # State is INACTIVE_CHARGED so async_start calls robot_start_clean, not robot_resume
        mock_coordinator_robot.device.robot_start_clean.side_effect = ConnectionError(
            "Lost connection"
        )

        with pytest.raises(HomeAssistantError, match="Failed to start vacuum"):
            await entity.async_start()

    def test_invalid_state_handling(self, mock_coordinator_robot):
        """Test handling of invalid robot states."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Test unknown state
        mock_coordinator_robot.device.robot_state = "UNKNOWN_STATE"
        assert entity.activity == VacuumActivity.IDLE  # Default fallback

        # Test empty state
        mock_coordinator_robot.device.robot_state = ""
        assert entity.activity == VacuumActivity.IDLE

    def test_device_state_corruption(self, mock_coordinator_robot):
        """Test handling of corrupted device state."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Test when device properties return None
        mock_coordinator_robot.device.robot_state = None

        # Entity should handle gracefully and return None/empty
        assert entity.activity is None

    @pytest.mark.asyncio
    async def test_partial_device_functionality(self, mock_coordinator_robot):
        """Test entity behavior when device has partial functionality."""
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Remove some methods to simulate partial functionality
        del mock_coordinator_robot.device.robot_pause

        # Entity should still work for other operations
        assert entity.activity == VacuumActivity.DOCKED

        # But missing methods should raise HomeAssistantError (wrapped AttributeError)
        with pytest.raises(HomeAssistantError, match="Failed to pause vacuum"):
            await entity.async_pause()


# ---------------------------------------------------------------------------
# Helpers used by TestCleanArea
# ---------------------------------------------------------------------------


def _make_zone(zone_id: str, zone_name: str, icon: str = "living_room"):
    """Create a minimal ZoneMeta-like mock."""
    z = MagicMock()
    z.id = zone_id
    z.name = zone_name
    z.icon = icon
    return z


def _make_pmap(
    pmap_id: str,
    zones: list,
    zdlud: str | None = "2026-01-01T00:00:00Z",
    name: str = "Ground floor",
    is_current: bool = False,
):
    """Create a minimal PersistentMapMeta-like mock."""
    p = MagicMock()
    p.id = pmap_id
    p.name = name
    p.zones = zones
    p.zones_definition_last_updated_date = zdlud
    p.is_current_map = is_current
    p.zone_by_id = lambda zid: next((z for z in zones if z.id == zid), None)
    p.zone_by_name = lambda n: next(
        (z for z in zones if (z.name or "").lower() == n.lower()), None
    )
    return p


class TestCleanArea:
    """Tests for HA 2026.3 CLEAN_AREA support on DysonVacuumEntity."""

    # ------------------------------------------------------------------
    # Feature flag tests
    # ------------------------------------------------------------------

    def test_clean_area_feature_set_with_auth_token(self, mock_coordinator_robot):
        """CLEAN_AREA added to supported_features when auth_token is present."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok123"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        assert VacuumEntityFeature.CLEAN_AREA in entity._attr_supported_features
        assert entity._has_zone_support is True

    def test_clean_area_feature_not_set_without_auth_token(
        self, mock_coordinator_robot
    ):
        """CLEAN_AREA absent from supported_features when no auth_token."""
        # Fixture default: config_entry.data = {}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        assert VacuumEntityFeature.CLEAN_AREA not in entity._attr_supported_features
        assert entity._has_zone_support is False

    def test_clean_area_feature_not_set_with_empty_token(self, mock_coordinator_robot):
        """CLEAN_AREA absent when auth_token is empty string."""
        mock_coordinator_robot.config_entry.data = {"auth_token": ""}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        assert VacuumEntityFeature.CLEAN_AREA not in entity._attr_supported_features
        assert entity._has_zone_support is False

    # ------------------------------------------------------------------
    # async_get_segments tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_async_get_segments_returns_segments(self, mock_coordinator_robot):
        """async_get_segments returns a Segment per zone."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        zones = [_make_zone("z1", "Kitchen"), _make_zone("z2", "Living Room")]
        pmap = _make_pmap("map1", zones)

        with patch(
            "custom_components.hass_dyson.vacuum._fetch_persistent_map_metadata",
            new=AsyncMock(return_value=[pmap]),
        ):
            segments = await entity.async_get_segments()

        assert len(segments) == 2
        assert segments[0] == Segment(id="z1", name="Kitchen")
        assert segments[1] == Segment(id="z2", name="Living Room")

    @pytest.mark.asyncio
    async def test_async_get_segments_zone_without_name_uses_id(
        self, mock_coordinator_robot
    ):
        """Zones with no name fall back to zone.id as the segment name."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        zone = _make_zone("z99", "")
        zone.name = None  # Simulate missing name
        pmap = _make_pmap("map1", [zone])

        with patch(
            "custom_components.hass_dyson.vacuum._fetch_persistent_map_metadata",
            new=AsyncMock(return_value=[pmap]),
        ):
            segments = await entity.async_get_segments()

        assert len(segments) == 1
        assert segments[0] == Segment(id="z99", name="z99")

    @pytest.mark.asyncio
    async def test_async_get_segments_skips_zones_without_id(
        self, mock_coordinator_robot
    ):
        """Zones with no id are silently skipped."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        valid_zone = _make_zone("z1", "Bedroom")
        no_id_zone = _make_zone("", "Unknown")
        no_id_zone.id = None
        pmap = _make_pmap("map1", [valid_zone, no_id_zone])

        with patch(
            "custom_components.hass_dyson.vacuum._fetch_persistent_map_metadata",
            new=AsyncMock(return_value=[pmap]),
        ):
            segments = await entity.async_get_segments()

        assert len(segments) == 1
        assert segments[0].id == "z1"

    @pytest.mark.asyncio
    async def test_async_get_segments_empty_maps(self, mock_coordinator_robot):
        """async_get_segments returns [] when no maps are available."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        with patch(
            "custom_components.hass_dyson.vacuum._fetch_persistent_map_metadata",
            new=AsyncMock(return_value=[]),
        ):
            segments = await entity.async_get_segments()

        assert segments == []

    @pytest.mark.asyncio
    async def test_async_get_segments_exception_returns_empty(
        self, mock_coordinator_robot
    ):
        """async_get_segments returns [] (logged warning) when fetch raises."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        with patch(
            "custom_components.hass_dyson.vacuum._fetch_persistent_map_metadata",
            new=AsyncMock(side_effect=HomeAssistantError("cloud down")),
        ):
            segments = await entity.async_get_segments()

        assert segments == []

    # ------------------------------------------------------------------
    # async_clean_segments tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_async_clean_segments_success(self, mock_coordinator_robot):
        """async_clean_segments calls robot_start_clean with correct arguments."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        zones = [_make_zone("z1", "Kitchen"), _make_zone("z2", "Lounge")]
        pmap = _make_pmap("map1", zones, zdlud="2026-03-01T12:00:00Z")

        with patch(
            "custom_components.hass_dyson.vacuum._fetch_persistent_map_metadata",
            new=AsyncMock(return_value=[pmap]),
        ):
            await entity.async_clean_segments(["z1"])

        mock_coordinator_robot.device.robot_start_clean.assert_called_once_with(
            cleaning_mode="zoneConfigured",
            full_clean_type="immediate",
            cleaning_programme={
                "persistentMapId": "map1",
                "orderedZones": [],
                "unorderedZones": ["z1"],
                "zonesDefinitionLastUpdatedDate": "2026-03-01T12:00:00Z",
            },
        )

    @pytest.mark.asyncio
    async def test_async_clean_segments_no_zdlud(self, mock_coordinator_robot):
        """zonesDefinitionLastUpdatedDate omitted from programme when None."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        pmap = _make_pmap("map1", [_make_zone("z1", "Hall")], zdlud=None)

        with patch(
            "custom_components.hass_dyson.vacuum._fetch_persistent_map_metadata",
            new=AsyncMock(return_value=[pmap]),
        ):
            await entity.async_clean_segments(["z1"])

        call_kwargs = mock_coordinator_robot.device.robot_start_clean.call_args.kwargs
        assert "zonesDefinitionLastUpdatedDate" not in call_kwargs["cleaning_programme"]

    @pytest.mark.asyncio
    async def test_async_clean_segments_unavailable(self, mock_coordinator_robot):
        """async_clean_segments raises HomeAssistantError when device unavailable."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        with patch.object(entity.coordinator, "last_update_success", False):
            with pytest.raises(HomeAssistantError, match="Device not available"):
                await entity.async_clean_segments(["z1"])

        mock_coordinator_robot.device.robot_start_clean.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_clean_segments_no_maps(self, mock_coordinator_robot):
        """async_clean_segments raises HomeAssistantError when no maps returned."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        with patch(
            "custom_components.hass_dyson.vacuum._fetch_persistent_map_metadata",
            new=AsyncMock(return_value=[]),
        ):
            with pytest.raises(HomeAssistantError, match="No persistent maps"):
                await entity.async_clean_segments(["z1"])

        mock_coordinator_robot.device.robot_start_clean.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_clean_segments_device_error(self, mock_coordinator_robot):
        """async_clean_segments wraps device errors in HomeAssistantError."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)
        mock_coordinator_robot.device.robot_start_clean.side_effect = RuntimeError(
            "MQTT disconnected"
        )

        pmap = _make_pmap("map1", [_make_zone("z1", "Hall")])

        with patch(
            "custom_components.hass_dyson.vacuum._fetch_persistent_map_metadata",
            new=AsyncMock(return_value=[pmap]),
        ):
            with pytest.raises(HomeAssistantError, match="Failed to start zone clean"):
                await entity.async_clean_segments(["z1"])

    # ------------------------------------------------------------------
    # _handle_coordinator_update (segment change detection) tests
    # ------------------------------------------------------------------

    def test_handle_coordinator_update_no_change(self, mock_coordinator_robot):
        """No repair issue when current segments match last_seen_segments."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        zones = [_make_zone("z1", "Kitchen")]
        pmap = _make_pmap("map1", zones)
        cached_maps = [pmap]

        entity.registry_entry = MagicMock()
        last_seen = [Segment(id="z1", name="Kitchen")]

        with (
            patch.object(entity, "async_write_ha_state"),
            patch.object(
                type(entity),
                "last_seen_segments",
                new_callable=PropertyMock,
                return_value=last_seen,
            ),
            patch.object(entity, "async_create_segments_issue") as mock_issue,
            patch(
                "custom_components.hass_dyson.vacuum._persistent_map_cache"
            ) as mock_cache,
        ):
            mock_cache.get.return_value = cached_maps
            entity._handle_coordinator_update()

        mock_issue.assert_not_called()

    def test_handle_coordinator_update_segments_changed(self, mock_coordinator_robot):
        """Repair issue created when current segments differ from last_seen."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        # Current map has two zones; user's mapping was configured with one
        zones = [_make_zone("z1", "Kitchen"), _make_zone("z2", "Bedroom")]
        pmap = _make_pmap("map1", zones)

        entity.registry_entry = MagicMock()
        last_seen = [Segment(id="z1", name="Kitchen")]  # Only one zone was mapped

        with (
            patch.object(entity, "async_write_ha_state"),
            patch.object(
                type(entity),
                "last_seen_segments",
                new_callable=PropertyMock,
                return_value=last_seen,
            ),
            patch.object(entity, "async_create_segments_issue") as mock_issue,
            patch(
                "custom_components.hass_dyson.vacuum._persistent_map_cache"
            ) as mock_cache,
        ):
            mock_cache.get.return_value = [pmap]
            entity._handle_coordinator_update()

        mock_issue.assert_called_once()

    def test_handle_coordinator_update_cache_miss_skips(self, mock_coordinator_robot):
        """No repair issue when persistent map cache is empty (first run)."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        entity.registry_entry = MagicMock()
        last_seen = [Segment(id="z1", name="Kitchen")]

        with (
            patch.object(entity, "async_write_ha_state"),
            patch.object(
                type(entity),
                "last_seen_segments",
                new_callable=PropertyMock,
                return_value=last_seen,
            ),
            patch.object(entity, "async_create_segments_issue") as mock_issue,
            patch(
                "custom_components.hass_dyson.vacuum._persistent_map_cache"
            ) as mock_cache,
        ):
            mock_cache.get.return_value = None  # cache miss
            entity._handle_coordinator_update()

        mock_issue.assert_not_called()

    def test_handle_coordinator_update_no_last_seen_skips(self, mock_coordinator_robot):
        """No repair issue when no area mapping has been configured yet."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        entity.registry_entry = MagicMock()

        with (
            patch.object(entity, "async_write_ha_state"),
            patch.object(
                type(entity),
                "last_seen_segments",
                new_callable=PropertyMock,
                return_value=None,
            ),
            patch.object(entity, "async_create_segments_issue") as mock_issue,
            patch(
                "custom_components.hass_dyson.vacuum._persistent_map_cache"
            ) as mock_cache,
        ):
            mock_cache.get.return_value = [_make_pmap("map1", [_make_zone("z1", "K")])]
            entity._handle_coordinator_update()

        mock_issue.assert_not_called()

    def test_handle_coordinator_update_no_zone_support_skips(
        self, mock_coordinator_robot
    ):
        """_handle_coordinator_update skips segment check when no auth_token."""
        # Fixture default: no auth_token → _has_zone_support = False
        entity = DysonVacuumEntity(mock_coordinator_robot)

        entity.registry_entry = MagicMock()

        with (
            patch.object(entity, "async_write_ha_state"),
            patch.object(entity, "async_create_segments_issue") as mock_issue,
            patch(
                "custom_components.hass_dyson.vacuum._persistent_map_cache"
            ) as mock_cache,
        ):
            mock_cache.get.return_value = [_make_pmap("map1", [_make_zone("z1", "K")])]
            entity._handle_coordinator_update()

        mock_issue.assert_not_called()

    def test_handle_coordinator_update_no_registry_entry_skips(
        self, mock_coordinator_robot
    ):
        """No issue created when entity has no registry_entry (pre-registration)."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        entity.registry_entry = None

        with (
            patch.object(entity, "async_write_ha_state"),
            patch.object(entity, "async_create_segments_issue") as mock_issue,
        ):
            entity._handle_coordinator_update()

        mock_issue.assert_not_called()


# ---------------------------------------------------------------------------
# fetch_clean_maps tests
# ---------------------------------------------------------------------------


def _make_coordinator(serial: str = "FCM-TEST-001", client=None, api_version: int = 1):
    """Return a minimal coordinator mock suitable for fetch_clean_maps."""
    coordinator = MagicMock()
    coordinator.serial_number = serial
    coordinator.device_type = "RB05"
    coordinator.async_discover_map_api_version = AsyncMock(return_value=api_version)

    @asynccontextmanager
    async def _cloud_client():
        yield client

    coordinator.async_cloud_client = _cloud_client
    return coordinator


def _make_v2_record(start_epoch: int, end_epoch: int | None = None):
    """Return a MagicMock that looks like a v2 CleanRecord."""
    r = MagicMock()
    r.start_time_epoch = start_epoch
    r.end_time_epoch = end_epoch
    r.timeline = None
    return r


def _make_v1_record(iso_start: str):
    """Return a MagicMock that looks like a v1 CleanRecord (timeline-based)."""
    r = MagicMock()
    r.start_time_epoch = None
    event = MagicMock()
    event.time = iso_start
    r.timeline = [event]
    return r


@pytest.fixture(autouse=True)
def _reset_clean_maps_state():
    """Isolate each test: clear the module-level cache and lock dict."""
    _clean_maps_cache._store.clear()
    _clean_maps_locks.clear()
    yield
    _clean_maps_cache._store.clear()
    _clean_maps_locks.clear()


class TestFetchCleanMaps:
    """Unit tests for the fetch_clean_maps helper in vacuum.py."""

    # ------------------------------------------------------------------
    # Cache-hit fast path
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_returns_cached_value_without_api_call(self):
        """When a fresh cache entry exists, no API call is made."""
        cached = [_make_v2_record(1000)]
        _clean_maps_cache.set("FCM-TEST-001", cached)

        client = AsyncMock()
        coordinator = _make_coordinator(client=client)

        result = await fetch_clean_maps(coordinator)

        assert result is cached
        client.get_clean_maps.assert_not_called()

    # ------------------------------------------------------------------
    # Successful fetch — sorting
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_successful_v2_fetch_sorted_newest_first(self):
        """v2 records are sorted by start_time_epoch descending."""
        old = _make_v2_record(1000)
        new = _make_v2_record(2000)

        client = AsyncMock()
        client.get_clean_maps = AsyncMock(return_value=[old, new])
        coordinator = _make_coordinator(client=client)

        result = await fetch_clean_maps(coordinator)

        assert result == [new, old]
        assert _clean_maps_cache.get("FCM-TEST-001") == [new, old]

    @pytest.mark.asyncio
    async def test_successful_v1_fetch_sorted_newest_first(self):
        """v1 records (timeline-based) are sorted by ISO start time descending."""
        old = _make_v1_record("2024-01-01T10:00:00Z")
        new = _make_v1_record("2024-06-01T10:00:00Z")

        client = AsyncMock()
        client.get_clean_maps = AsyncMock(return_value=[old, new])
        coordinator = _make_coordinator(client=client)

        result = await fetch_clean_maps(coordinator)

        assert result == [new, old]

    @pytest.mark.asyncio
    async def test_successful_fetch_caches_result(self):
        """A successful fetch populates the cache so subsequent calls skip the API."""
        record = _make_v2_record(5000)

        client = AsyncMock()
        client.get_clean_maps = AsyncMock(return_value=[record])
        coordinator = _make_coordinator(client=client)

        await fetch_clean_maps(coordinator)

        # Second call — client must NOT be hit again.
        client.get_clean_maps.reset_mock()
        result2 = await fetch_clean_maps(coordinator)

        assert result2 == [record]
        client.get_clean_maps.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_records_list_cached_and_returned(self):
        """An empty list from the API is cached and returned as-is."""
        client = AsyncMock()
        client.get_clean_maps = AsyncMock(return_value=[])
        coordinator = _make_coordinator(client=client)

        result = await fetch_clean_maps(coordinator)

        assert result == []
        assert _clean_maps_cache.get("FCM-TEST-001") == []

    # ------------------------------------------------------------------
    # client is None (no auth_token)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_client_and_no_stale(self):
        """Returns [] when client is None and no stale cache entry exists."""
        coordinator = _make_coordinator(client=None)

        result = await fetch_clean_maps(coordinator)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_stale_when_no_client_and_stale_exists(self):
        """Returns the stale cache entry when client is None."""
        stale = [_make_v2_record(3000)]
        _clean_maps_cache.set("FCM-TEST-001", stale)
        _clean_maps_cache.expire("FCM-TEST-001")

        coordinator = _make_coordinator(client=None)

        result = await fetch_clean_maps(coordinator)

        assert result == stale

    # ------------------------------------------------------------------
    # DysonAuthError — must NOT be cached
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_auth_error_not_cached_returns_empty(self):
        """DysonAuthError is not cached; returns empty list."""
        from libdyson_rest.exceptions import DysonAuthError

        client = AsyncMock()
        client.get_clean_maps = AsyncMock(side_effect=DysonAuthError("token expired"))
        coordinator = _make_coordinator(client=client)

        result = await fetch_clean_maps(coordinator)

        assert result == []
        # Cache must remain unpopulated so the next call retries.
        assert _clean_maps_cache.get("FCM-TEST-001") is None

    @pytest.mark.asyncio
    async def test_auth_error_returns_stale_when_available(self):
        """DysonAuthError falls back to stale cache if one exists."""
        from libdyson_rest.exceptions import DysonAuthError

        stale = [_make_v2_record(9000)]
        _clean_maps_cache.set("FCM-TEST-001", stale)
        _clean_maps_cache.expire("FCM-TEST-001")

        client = AsyncMock()
        client.get_clean_maps = AsyncMock(side_effect=DysonAuthError("token expired"))
        coordinator = _make_coordinator(client=client)

        result = await fetch_clean_maps(coordinator)

        assert result == stale

    # ------------------------------------------------------------------
    # DysonAPIError — must be cached to prevent retry spam
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_api_error_400_cached_returns_empty(self):
        """A 400 DysonAPIError is cached so the endpoint is not retried."""
        from libdyson_rest.exceptions import DysonAPIError

        client = AsyncMock()
        client.get_clean_maps = AsyncMock(side_effect=DysonAPIError("400 Bad Request"))
        coordinator = _make_coordinator(client=client)

        result = await fetch_clean_maps(coordinator)

        assert result == []
        # Failure must be cached (empty list stored).
        assert _clean_maps_cache.get("FCM-TEST-001") == []

    @pytest.mark.asyncio
    async def test_api_error_400_not_retried_on_second_call(self):
        """After a cached 400 failure, subsequent calls skip the API entirely."""
        from libdyson_rest.exceptions import DysonAPIError

        client = AsyncMock()
        client.get_clean_maps = AsyncMock(side_effect=DysonAPIError("400 Bad Request"))
        coordinator = _make_coordinator(client=client)

        await fetch_clean_maps(coordinator)
        client.get_clean_maps.reset_mock()

        result2 = await fetch_clean_maps(coordinator)

        assert result2 == []
        client.get_clean_maps.assert_not_called()

    @pytest.mark.asyncio
    async def test_api_error_non_400_cached_returns_stale(self):
        """Non-400 DysonAPIError is cached and stale fallback is returned."""
        from libdyson_rest.exceptions import DysonAPIError

        stale = [_make_v2_record(7000)]
        _clean_maps_cache.set("FCM-TEST-001", stale)
        _clean_maps_cache.expire("FCM-TEST-001")

        client = AsyncMock()
        client.get_clean_maps = AsyncMock(
            side_effect=DysonAPIError("503 Service Unavailable")
        )
        coordinator = _make_coordinator(client=client)

        result = await fetch_clean_maps(coordinator)

        assert result == stale
        # Failure is cached (stale value is stored, not None).
        assert _clean_maps_cache.get("FCM-TEST-001") == stale

    @pytest.mark.asyncio
    async def test_api_error_non_400_no_stale_returns_empty(self):
        """Non-400 DysonAPIError with no stale cache returns []."""
        from libdyson_rest.exceptions import DysonAPIError

        client = AsyncMock()
        client.get_clean_maps = AsyncMock(
            side_effect=DysonAPIError("503 Service Unavailable")
        )
        coordinator = _make_coordinator(client=client)

        result = await fetch_clean_maps(coordinator)

        assert result == []

    # ------------------------------------------------------------------
    # Concurrent stampede prevention (double-checked locking)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # _sort_epoch edge cases (v1 timeline with degenerate data)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_v1_record_with_all_falsy_times_sorted_last(self):
        """v1 record whose timeline events all have falsy .time values gets epoch 0."""
        good = _make_v2_record(5000)
        bad_event = MagicMock()
        bad_event.time = None  # falsy → filtered out → times=[] → epoch 0.0
        bad_v1 = MagicMock()
        bad_v1.start_time_epoch = None
        bad_v1.timeline = [bad_event]

        client = AsyncMock()
        client.get_clean_maps = AsyncMock(return_value=[bad_v1, good])
        coordinator = _make_coordinator(client=client)

        result = await fetch_clean_maps(coordinator)

        # good (epoch 5000) should be first; bad_v1 (epoch 0) last.
        assert result[0] is good
        assert result[1] is bad_v1

    @pytest.mark.asyncio
    async def test_v1_record_with_invalid_iso_string_sorted_last(self):
        """v1 record with a malformed ISO timestamp falls back to epoch 0."""
        good = _make_v2_record(5000)
        bad_event = MagicMock()
        bad_event.time = "not-a-valid-date"
        bad_v1 = MagicMock()
        bad_v1.start_time_epoch = None
        bad_v1.timeline = [bad_event]

        client = AsyncMock()
        client.get_clean_maps = AsyncMock(return_value=[bad_v1, good])
        coordinator = _make_coordinator(client=client)

        result = await fetch_clean_maps(coordinator)

        assert result[0] is good
        assert result[1] is bad_v1

    @pytest.mark.asyncio
    async def test_concurrent_callers_only_one_api_hit(self):
        """Concurrent calls for the same serial trigger only one API request."""
        import asyncio

        record = _make_v2_record(4000)

        call_count = 0

        async def _slow_get_clean_maps(serial, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0)  # yield so the second coroutine can reach the lock
            return [record]

        client = AsyncMock()
        client.get_clean_maps = _slow_get_clean_maps
        coordinator = _make_coordinator(client=client)

        results = await asyncio.gather(
            fetch_clean_maps(coordinator),
            fetch_clean_maps(coordinator),
        )

        assert call_count == 1
        assert results[0] == results[1] == [record]


# ---------------------------------------------------------------------------
# Multi-map CLEAN_AREA behaviour (issue #398)
# ---------------------------------------------------------------------------


class TestCleanAreaMultiMap:
    """Segments and zone cleans on robots with more than one persistent map."""

    @staticmethod
    def _maps():
        upstairs = _make_pmap(
            "map-up",
            [_make_zone("1", "Hallway"), _make_zone("2", "Office")],
            zdlud="2026-03-23T07:02:59Z",
            name="Upstairs",
        )
        downstairs = _make_pmap(
            "map-down",
            [_make_zone("1", "Hallway"), _make_zone("5", "Kitchen")],
            zdlud="2026-07-10T14:09:15Z",
            name="Downstairs",
        )
        return [upstairs, downstairs]

    @pytest.mark.asyncio
    async def test_get_segments_multi_map_qualified(self, mock_coordinator_robot):
        """Multi-map segments get map-qualified ids and map-suffixed names."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        with patch(
            "custom_components.hass_dyson.vacuum._fetch_persistent_map_metadata",
            new=AsyncMock(return_value=self._maps()),
        ):
            segments = await entity.async_get_segments()

        assert len(segments) == 4
        assert segments[0] == Segment(id="map-up:1", name="Hallway (Upstairs)")
        assert segments[3] == Segment(id="map-down:5", name="Kitchen (Downstairs)")

    @pytest.mark.asyncio
    async def test_clean_segments_qualified_ids_target_their_map(
        self, mock_coordinator_robot
    ):
        """Qualified segment ids clean on the map they name."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        with patch(
            "custom_components.hass_dyson.vacuum._fetch_persistent_map_metadata",
            new=AsyncMock(return_value=self._maps()),
        ):
            await entity.async_clean_segments(["map-down:1", "map-down:5"])

        mock_coordinator_robot.device.robot_start_clean.assert_called_once_with(
            cleaning_mode="zoneConfigured",
            full_clean_type="immediate",
            cleaning_programme={
                "persistentMapId": "map-down",
                "orderedZones": [],
                "unorderedZones": ["1", "5"],
                "zonesDefinitionLastUpdatedDate": "2026-07-10T14:09:15Z",
            },
        )

    @pytest.mark.asyncio
    async def test_clean_segments_spanning_maps_raises(self, mock_coordinator_robot):
        """One run cannot clean zones from two different maps."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        with patch(
            "custom_components.hass_dyson.vacuum._fetch_persistent_map_metadata",
            new=AsyncMock(return_value=self._maps()),
        ):
            with pytest.raises(HomeAssistantError, match="span multiple maps"):
                await entity.async_clean_segments(["map-up:1", "map-down:5"])

        mock_coordinator_robot.device.robot_start_clean.assert_not_called()

    @pytest.mark.asyncio
    async def test_clean_segments_unknown_map_id_raises(self, mock_coordinator_robot):
        """A qualified id for a map that no longer exists raises."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        with patch(
            "custom_components.hass_dyson.vacuum._fetch_persistent_map_metadata",
            new=AsyncMock(return_value=self._maps()),
        ):
            with pytest.raises(HomeAssistantError, match="Unknown map id"):
                await entity.async_clean_segments(["map-gone:1"])

    @pytest.mark.asyncio
    async def test_clean_segments_zone_not_on_map_raises(self, mock_coordinator_robot):
        """Zone ids that are not on the targeted map raise instead of sending."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        with patch(
            "custom_components.hass_dyson.vacuum._fetch_persistent_map_metadata",
            new=AsyncMock(return_value=self._maps()),
        ):
            with pytest.raises(HomeAssistantError, match="not on map"):
                await entity.async_clean_segments(["map-up:5"])

        mock_coordinator_robot.device.robot_start_clean.assert_not_called()

    @pytest.mark.asyncio
    async def test_clean_segments_empty_list_raises(self, mock_coordinator_robot):
        """An empty segment list must not be sent as a whole-house clean."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        with pytest.raises(HomeAssistantError, match="No segments specified"):
            await entity.async_clean_segments([])

        mock_coordinator_robot.device.robot_start_clean.assert_not_called()

    @pytest.mark.asyncio
    async def test_clean_segments_bare_id_inferred_across_maps(
        self, mock_coordinator_robot
    ):
        """Pre-multi-map bare ids still work when they match exactly one map."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        with patch(
            "custom_components.hass_dyson.vacuum._fetch_persistent_map_metadata",
            new=AsyncMock(return_value=self._maps()),
        ):
            await entity.async_clean_segments(["5"])

        programme = mock_coordinator_robot.device.robot_start_clean.call_args.kwargs[
            "cleaning_programme"
        ]
        assert programme["persistentMapId"] == "map-down"
        assert programme["unorderedZones"] == ["5"]

    def test_segment_drift_uses_qualified_ids_when_multi_map(
        self, mock_coordinator_robot
    ):
        """Drift comparison keys mirror the qualified segment ids."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        entity.registry_entry = MagicMock()
        last_seen = [
            Segment(id="map-up:1", name="Hallway (Upstairs)"),
            Segment(id="map-up:2", name="Office (Upstairs)"),
            Segment(id="map-down:1", name="Hallway (Downstairs)"),
            Segment(id="map-down:5", name="Kitchen (Downstairs)"),
        ]

        with (
            patch.object(entity, "async_write_ha_state"),
            patch.object(
                type(entity),
                "last_seen_segments",
                new_callable=PropertyMock,
                return_value=last_seen,
            ),
            patch.object(entity, "async_create_segments_issue") as mock_issue,
            patch(
                "custom_components.hass_dyson.vacuum._persistent_map_cache"
            ) as mock_cache,
        ):
            mock_cache.get.return_value = self._maps()
            entity._handle_coordinator_update()

        mock_issue.assert_not_called()

    def test_segment_drift_bare_mapping_on_multi_map_raises_issue(
        self, mock_coordinator_robot
    ):
        """A pre-multi-map bare-id mapping flags re-mapping once a 2nd map exists."""
        mock_coordinator_robot.config_entry.data = {"auth_token": "tok"}
        entity = DysonVacuumEntity(mock_coordinator_robot)

        entity.registry_entry = MagicMock()
        last_seen = [Segment(id="1", name="Hallway"), Segment(id="2", name="Office")]

        with (
            patch.object(entity, "async_write_ha_state"),
            patch.object(
                type(entity),
                "last_seen_segments",
                new_callable=PropertyMock,
                return_value=last_seen,
            ),
            patch.object(entity, "async_create_segments_issue") as mock_issue,
            patch(
                "custom_components.hass_dyson.vacuum._persistent_map_cache"
            ) as mock_cache,
        ):
            mock_cache.get.return_value = self._maps()
            entity._handle_coordinator_update()

        mock_issue.assert_called_once()
