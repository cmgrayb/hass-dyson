"""Test vacuum platform for Dyson integration."""

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
from custom_components.hass_dyson.vacuum import DysonVacuumEntity, async_setup_entry


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


def _make_pmap(pmap_id: str, zones: list, zdlud: str | None = "2026-01-01T00:00:00Z"):
    """Create a minimal PersistentMapMeta-like mock."""
    p = MagicMock()
    p.id = pmap_id
    p.name = "Ground floor"
    p.zones = zones
    p.zones_definition_last_updated_date = zdlud
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
                "custom_components.hass_dyson.services._persistent_map_cache"
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
                "custom_components.hass_dyson.services._persistent_map_cache"
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
                "custom_components.hass_dyson.services._persistent_map_cache"
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
                "custom_components.hass_dyson.services._persistent_map_cache"
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
                "custom_components.hass_dyson.services._persistent_map_cache"
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
