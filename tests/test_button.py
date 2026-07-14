"""Test button platform for Dyson integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from libdyson_rest.models import PersistentMapMeta, ZoneMeta

from custom_components.hass_dyson.button import (
    ZONE_DISCOVERY_RETRY_DELAYS,
    DysonReconnectButton,
    DysonRefreshZonesButton,
    DysonZoneCleanButton,
    _async_migrate_zone_button_unique_ids,
    _icon_for_zone,
    async_setup_entry,
)
from custom_components.hass_dyson.const import DEVICE_CATEGORY_ROBOT, DOMAIN


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-SERIAL-123"
    coordinator.device_name = "Test Device"
    coordinator.device = MagicMock()
    coordinator.device_category = []
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {}
    return coordinator


@pytest.fixture
def mock_robot_coordinator():
    """Create a mock coordinator for a robot vacuum with cloud token."""
    coordinator = MagicMock()
    coordinator.serial_number = "VS9-GB-HJA0000A"
    coordinator.device_name = "Vis Nav"
    coordinator.device = MagicMock()
    coordinator.device_category = [DEVICE_CATEGORY_ROBOT]
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {"auth_token": "tok"}
    return coordinator


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test-entry-id"
    return config_entry


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    return hass


@pytest.fixture(autouse=True)
def mock_entity_registry():
    """Stub the entity registry used by the zone-button unique_id migration.

    Defaults to an empty registry (no pre-multi-map entities to migrate).
    """
    registry = MagicMock()
    registry.async_get_entity_id.return_value = None
    with patch(
        "custom_components.hass_dyson.button.er.async_get", return_value=registry
    ):
        yield registry


class TestButtonPlatformSetup:
    """Test button platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_reconnect_button(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Test that async_setup_entry creates a reconnect button."""
        # Arrange
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator
        mock_add_entities = MagicMock()

        # Act
        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        # Assert
        mock_add_entities.assert_called_once()
        added_entities = mock_add_entities.call_args[0][0]
        assert len(added_entities) == 1
        assert isinstance(added_entities[0], DysonReconnectButton)
        # Check the second argument is True
        assert mock_add_entities.call_args[0][1] is True

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_missing_coordinator(
        self, mock_hass, mock_config_entry
    ):
        """Test async_setup_entry with missing coordinator raises KeyError."""
        # Arrange
        mock_add_entities = AsyncMock()

        # Act & Assert
        with pytest.raises(KeyError):
            await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)


class TestDysonReconnectButton:
    """Test DysonReconnectButton class."""

    def test_init_sets_attributes_correctly(self, mock_coordinator):
        """Test that __init__ sets all attributes correctly."""
        # Act
        button = DysonReconnectButton(mock_coordinator)

        # Assert
        assert button.coordinator == mock_coordinator
        assert button._attr_unique_id == "TEST-SERIAL-123_reconnect"
        assert button._attr_name == "Reconnect"
        assert button._attr_icon == "mdi:wifi-sync"
        assert button._attr_entity_category == EntityCategory.DIAGNOSTIC

    @pytest.mark.asyncio
    async def test_async_press_successful_reconnect(self, mock_coordinator):
        """Test successful reconnection when button is pressed."""
        # Arrange
        button = DysonReconnectButton(mock_coordinator)
        mock_coordinator.device.force_reconnect = AsyncMock(return_value=True)
        mock_coordinator.async_request_refresh = AsyncMock()

        # Act
        await button.async_press()

        # Assert
        mock_coordinator.device.force_reconnect.assert_called_once()
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_press_failed_reconnect(self, mock_coordinator):
        """Test failed reconnection when button is pressed."""
        # Arrange
        button = DysonReconnectButton(mock_coordinator)
        mock_coordinator.device.force_reconnect = AsyncMock(return_value=False)
        mock_coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.hass_dyson.button._LOGGER") as mock_logger:
            # Act
            await button.async_press()

            # Assert
            mock_coordinator.device.force_reconnect.assert_called_once()
            mock_coordinator.async_request_refresh.assert_not_called()
            mock_logger.warning.assert_called_with(
                "Manual reconnection failed for %s", "TEST-SERIAL-123"
            )

    @pytest.mark.asyncio
    async def test_async_press_no_device_available(self, mock_coordinator):
        """Test button press when no device is available."""
        # Arrange
        mock_coordinator.device = None
        button = DysonReconnectButton(mock_coordinator)

        with patch("custom_components.hass_dyson.button._LOGGER") as mock_logger:
            # Act
            await button.async_press()

            # Assert
            mock_logger.warning.assert_called_with("Device not available for reconnect")

    @pytest.mark.asyncio
    async def test_async_press_exception_handling(self, mock_coordinator):
        """Test exception handling during button press."""
        # Arrange
        button = DysonReconnectButton(mock_coordinator)
        mock_coordinator.device.force_reconnect = AsyncMock(
            side_effect=Exception("Connection error")
        )

        with patch("custom_components.hass_dyson.button._LOGGER") as mock_logger:
            # Act
            await button.async_press()

            # Assert
            mock_coordinator.device.force_reconnect.assert_called_once()
            mock_logger.error.assert_called_with(
                "Failed to manually reconnect %s: %s",
                "TEST-SERIAL-123",
                mock_coordinator.device.force_reconnect.side_effect,
            )

    @pytest.mark.asyncio
    async def test_async_press_logs_info_messages(self, mock_coordinator):
        """Test that async_press logs appropriate info messages."""
        # Arrange
        button = DysonReconnectButton(mock_coordinator)
        mock_coordinator.device.force_reconnect = AsyncMock(return_value=True)
        mock_coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.hass_dyson.button._LOGGER") as mock_logger:
            # Act
            await button.async_press()

            # Assert
            expected_calls = [
                (
                    "Manual reconnect triggered for %s",
                    "TEST-SERIAL-123",
                ),
                (
                    "Manual reconnection successful for %s",
                    "TEST-SERIAL-123",
                ),
            ]

            # Check that info was called with expected arguments
            assert mock_logger.info.call_count == 2
            for call_args, expected_args in zip(
                mock_logger.info.call_args_list, expected_calls
            ):
                assert call_args[0] == expected_args

    def test_inherits_from_correct_base_classes(self, mock_coordinator):
        """Test that DysonReconnectButton inherits from correct base classes."""
        # Act
        button = DysonReconnectButton(mock_coordinator)

        # Assert
        from homeassistant.components.button import ButtonEntity

        from custom_components.hass_dyson.entity import DysonEntity

        assert isinstance(button, DysonEntity)
        assert isinstance(button, ButtonEntity)

    def test_coordinator_type_annotation(self, mock_coordinator):
        """Test that coordinator has correct type annotation."""
        # Act
        button = DysonReconnectButton(mock_coordinator)

        # Assert
        assert hasattr(button, "coordinator")
        # Verify the coordinator attribute is set correctly
        assert button.coordinator == mock_coordinator


class TestButtonPlatformIntegration:
    """Test button platform integration scenarios."""

    @pytest.mark.asyncio
    async def test_button_entity_in_home_assistant_context(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Test button entity works correctly in Home Assistant context."""
        # Arrange
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator
        mock_add_entities = MagicMock()

        # Act
        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        # Assert
        entities = mock_add_entities.call_args[0][0]
        button = entities[0]

        # Verify button properties work as expected
        assert button.unique_id == "TEST-SERIAL-123_reconnect"
        assert button.name == "Reconnect"
        assert button.icon == "mdi:wifi-sync"
        assert button.entity_category == EntityCategory.DIAGNOSTIC

    @pytest.mark.asyncio
    async def test_multiple_config_entries(self, mock_hass):
        """Test that multiple config entries can have their own buttons."""
        # Arrange
        coordinator1 = MagicMock()
        coordinator1.serial_number = "DEVICE-001"
        coordinator1.device_name = "Living Room Fan"
        coordinator1.device = MagicMock()

        coordinator2 = MagicMock()
        coordinator2.serial_number = "DEVICE-002"
        coordinator2.device_name = "Bedroom Purifier"
        coordinator2.device = MagicMock()

        config_entry1 = MagicMock(spec=ConfigEntry)
        config_entry1.entry_id = "entry-1"

        config_entry2 = MagicMock(spec=ConfigEntry)
        config_entry2.entry_id = "entry-2"

        mock_hass.data[DOMAIN]["entry-1"] = coordinator1
        mock_hass.data[DOMAIN]["entry-2"] = coordinator2

        mock_add_entities = MagicMock()

        # Act
        await async_setup_entry(mock_hass, config_entry1, mock_add_entities)
        button1 = mock_add_entities.call_args[0][0][0]

        await async_setup_entry(mock_hass, config_entry2, mock_add_entities)
        button2 = mock_add_entities.call_args[0][0][0]

        # Assert
        assert button1.unique_id == "DEVICE-001_reconnect"
        assert button1.name == "Reconnect"
        assert button2.unique_id == "DEVICE-002_reconnect"
        assert button2.name == "Reconnect"

    @pytest.mark.asyncio
    async def test_button_press_integration_with_coordinator(self, mock_coordinator):
        """Test button press properly integrates with coordinator methods."""
        # Arrange
        button = DysonReconnectButton(mock_coordinator)
        mock_coordinator.device.force_reconnect = AsyncMock(return_value=True)
        mock_coordinator.async_request_refresh = AsyncMock()

        # Act
        await button.async_press()

        # Assert
        # Verify the call sequence
        mock_coordinator.device.force_reconnect.assert_called_once()
        mock_coordinator.async_request_refresh.assert_called_once()

        # Verify that refresh is called after successful reconnect
        force_reconnect_call_order = (
            mock_coordinator.device.force_reconnect.call_args_list
        )
        refresh_call_order = mock_coordinator.async_request_refresh.call_args_list
        assert len(force_reconnect_call_order) == 1
        assert len(refresh_call_order) == 1


# ---------------------------------------------------------------------------
# Tests: async_setup_entry robot/zone paths
# ---------------------------------------------------------------------------


class TestButtonPlatformRobotSetup:
    """Test async_setup_entry for robot vacuum with zone buttons."""

    @pytest.fixture
    def mock_hass(self):
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {DOMAIN: {}}
        return hass

    @pytest.fixture
    def mock_config_entry(self):
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "robot-entry"
        return entry

    @pytest.mark.asyncio
    async def test_ble_device_returns_early(self, mock_hass, mock_config_entry):
        """BLE device skips button setup entirely."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = {"is_ble": True}
        add_entities = MagicMock()
        await async_setup_entry(mock_hass, mock_config_entry, add_entities)
        add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_robot_with_token_creates_zone_buttons(
        self, mock_hass, mock_config_entry, mock_robot_coordinator
    ):
        """Robot device with auth_token creates per-zone clean buttons."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_robot_coordinator
        add_entities = MagicMock()
        fake_maps = [
            PersistentMapMeta(
                id="map-1",
                name=None,
                zones_definition_last_updated_date=None,
                zones=[
                    ZoneMeta(id="z1", name="Kitchen", icon="kitchen", area=None),
                    ZoneMeta(id="z2", name="Bedroom", icon="bedroom", area=None),
                ],
            )
        ]
        with patch(
            "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
            AsyncMock(return_value=fake_maps),
        ):
            await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        # Base call: reconnect + refresh; second call: the discovered zones
        assert add_entities.call_count == 2
        base = add_entities.call_args_list[0][0][0]
        assert len(base) == 2
        assert isinstance(base[0], DysonReconnectButton)
        assert isinstance(base[1], DysonRefreshZonesButton)
        zones = add_entities.call_args_list[1][0][0]
        assert len(zones) == 2
        assert all(isinstance(entity, DysonZoneCleanButton) for entity in zones)

    @pytest.mark.asyncio
    async def test_robot_zone_fetch_exception_defers_discovery(
        self, mock_hass, mock_config_entry, mock_robot_coordinator
    ):
        """Exception during zone fetch keeps recovery buttons and schedules a retry."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_robot_coordinator
        add_entities = MagicMock()
        with (
            patch(
                "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
                AsyncMock(side_effect=Exception("network error")),
            ),
            patch(
                "custom_components.hass_dyson.button.async_call_later"
            ) as mock_call_later,
        ):
            await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        # Reconnect + refresh are still created — no zone buttons yet
        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        assert len(entities) == 2
        assert isinstance(entities[0], DysonReconnectButton)
        assert isinstance(entities[1], DysonRefreshZonesButton)
        # The first background retry is scheduled
        mock_call_later.assert_called_once()
        assert mock_call_later.call_args[0][1] == ZONE_DISCOVERY_RETRY_DELAYS[0]

    @pytest.mark.asyncio
    async def test_robot_empty_maps_no_zone_buttons(
        self, mock_hass, mock_config_entry, mock_robot_coordinator
    ):
        """Robot with empty persistent map list creates no zone buttons."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_robot_coordinator
        add_entities = MagicMock()
        with (
            patch(
                "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
                AsyncMock(return_value=[]),
            ),
            patch(
                "custom_components.hass_dyson.button.async_call_later"
            ) as mock_call_later,
        ):
            await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        # Recovery buttons only; a successful-but-empty fetch schedules no retry
        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        assert len(entities) == 2
        assert isinstance(entities[0], DysonReconnectButton)
        assert isinstance(entities[1], DysonRefreshZonesButton)
        mock_call_later.assert_not_called()

    @pytest.mark.asyncio
    async def test_same_zone_id_on_two_maps_creates_two_buttons(
        self, mock_hass, mock_config_entry, mock_robot_coordinator
    ):
        """Zone ids restart per map — each map gets its own button (issue #398)."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_robot_coordinator
        add_entities = MagicMock()
        fake_maps = [
            PersistentMapMeta(
                id="map-1",
                name="Upstairs",
                zones_definition_last_updated_date=None,
                zones=[ZoneMeta(id="z1", name="Kitchen", icon=None, area=None)],
            ),
            PersistentMapMeta(
                id="map-2",
                name="Downstairs",
                zones_definition_last_updated_date=None,
                zones=[ZoneMeta(id="z1", name="Kitchen", icon=None, area=None)],
            ),
        ]
        with patch(
            "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
            AsyncMock(return_value=fake_maps),
        ):
            await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        zones = add_entities.call_args_list[1][0][0]
        assert len(zones) == 2
        assert all(isinstance(entity, DysonZoneCleanButton) for entity in zones)
        # Map-qualified unique_ids and names disambiguate the two buttons
        assert {b._attr_unique_id for b in zones} == {
            "VS9-GB-HJA0000A_clean_zone_map-1_z1",
            "VS9-GB-HJA0000A_clean_zone_map-2_z1",
        }
        assert {b._attr_name for b in zones} == {
            "Clean Kitchen (Upstairs)",
            "Clean Kitchen (Downstairs)",
        }

    @pytest.mark.asyncio
    async def test_single_map_names_not_qualified(
        self, mock_hass, mock_config_entry, mock_robot_coordinator
    ):
        """Single-map robots keep the unqualified 'Clean <zone>' names."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_robot_coordinator
        add_entities = MagicMock()
        fake_maps = [
            PersistentMapMeta(
                id="map-1",
                name="Home",
                zones_definition_last_updated_date=None,
                zones=[ZoneMeta(id="z1", name="Kitchen", icon=None, area=None)],
            )
        ]
        with patch(
            "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
            AsyncMock(return_value=fake_maps),
        ):
            await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        zones = add_entities.call_args_list[1][0][0]
        assert len(zones) == 1
        assert zones[0]._attr_name == "Clean Kitchen"
        assert zones[0]._attr_unique_id == "VS9-GB-HJA0000A_clean_zone_map-1_z1"

    @pytest.mark.asyncio
    async def test_non_robot_with_token_no_zone_buttons(
        self, mock_hass, mock_config_entry, mock_robot_coordinator
    ):
        """Non-robot device gets no zone buttons even with auth_token."""
        mock_robot_coordinator.device_category = ["fan"]
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_robot_coordinator
        add_entities = MagicMock()
        await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        entities = add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DysonReconnectButton)

    @pytest.mark.asyncio
    async def test_robot_without_token_no_zone_buttons(
        self, mock_hass, mock_config_entry, mock_robot_coordinator
    ):
        """Robot without auth_token gets no zone buttons."""
        mock_robot_coordinator.config_entry.data = {}
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_robot_coordinator
        add_entities = MagicMock()
        await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        entities = add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DysonReconnectButton)


# ---------------------------------------------------------------------------
# Tests: zone discovery retry + manual recovery
# ---------------------------------------------------------------------------


class TestZoneDiscoveryRetry:
    """Test background retry and manual recovery for zone discovery."""

    _FAKE_MAPS = [
        PersistentMapMeta(
            id="map-1",
            name=None,
            zones_definition_last_updated_date=None,
            zones=[
                ZoneMeta(id="z1", name="Kitchen", icon="kitchen", area=None),
                ZoneMeta(id="z2", name="Bedroom", icon="bedroom", area=None),
            ],
        )
    ]

    @pytest.mark.asyncio
    async def test_retry_adds_zone_buttons_after_recovery(
        self, mock_hass, mock_config_entry, mock_robot_coordinator
    ):
        """A scheduled retry adds the zone buttons once the cloud recovers."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_robot_coordinator
        add_entities = MagicMock()
        scheduled = []

        def fake_call_later(hass, delay, action):
            scheduled.append((delay, action))
            return MagicMock()

        with (
            patch(
                "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
                AsyncMock(side_effect=[Exception("cloud down"), self._FAKE_MAPS]),
            ),
            patch(
                "custom_components.hass_dyson.button.async_call_later",
                side_effect=fake_call_later,
            ),
        ):
            await async_setup_entry(mock_hass, mock_config_entry, add_entities)
            assert add_entities.call_count == 1
            assert len(scheduled) == 1
            await scheduled[0][1](None)

        assert add_entities.call_count == 2
        zones = add_entities.call_args_list[1][0][0]
        assert len(zones) == 2
        assert all(isinstance(entity, DysonZoneCleanButton) for entity in zones)

    @pytest.mark.asyncio
    async def test_retry_schedule_exhausts_with_backoff(
        self, mock_hass, mock_config_entry, mock_robot_coordinator
    ):
        """Retries follow the backoff schedule and stop when it is exhausted."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_robot_coordinator
        add_entities = MagicMock()
        delays_seen: list[float] = []
        pending = []

        def fake_call_later(hass, delay, action):
            delays_seen.append(delay)
            pending.append(action)
            return MagicMock()

        with (
            patch(
                "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
                AsyncMock(side_effect=Exception("cloud down")),
            ),
            patch(
                "custom_components.hass_dyson.button.async_call_later",
                side_effect=fake_call_later,
            ),
        ):
            await async_setup_entry(mock_hass, mock_config_entry, add_entities)
            while pending:
                await pending.pop(0)(None)

        assert delays_seen == list(ZONE_DISCOVERY_RETRY_DELAYS)
        # Only the base reconnect + refresh call — no zone buttons were added
        assert add_entities.call_count == 1

    @pytest.mark.asyncio
    async def test_unload_cancels_pending_retry(
        self, mock_hass, mock_config_entry, mock_robot_coordinator
    ):
        """Unloading the entry cancels a pending discovery retry."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_robot_coordinator
        add_entities = MagicMock()
        cancel = MagicMock()

        with (
            patch(
                "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
                AsyncMock(side_effect=Exception("cloud down")),
            ),
            patch(
                "custom_components.hass_dyson.button.async_call_later",
                return_value=cancel,
            ),
        ):
            await async_setup_entry(mock_hass, mock_config_entry, add_entities)

        mock_config_entry.async_on_unload.assert_called_once()
        unload_callback = mock_config_entry.async_on_unload.call_args[0][0]
        unload_callback()
        cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_press_adds_new_zones_without_restart(
        self, mock_robot_coordinator
    ):
        """Pressing refresh invalidates the cache and adds new zone buttons."""
        discover = AsyncMock(return_value=3)
        btn = DysonRefreshZonesButton(mock_robot_coordinator, discover)
        with patch(
            "custom_components.hass_dyson.services._persistent_map_cache"
        ) as mock_cache:
            await btn.async_press()

        mock_cache.invalidate.assert_called_once_with("VS9-GB-HJA0000A")
        discover.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_refresh_press_discovery_failure_raises(self, mock_robot_coordinator):
        """Discovery failures on refresh surface as HomeAssistantError."""
        discover = AsyncMock(side_effect=Exception("cloud down"))
        btn = DysonRefreshZonesButton(mock_robot_coordinator, discover)
        with patch("custom_components.hass_dyson.services._persistent_map_cache"):
            with pytest.raises(HomeAssistantError, match="Failed to refresh zones"):
                await btn.async_press()


# ---------------------------------------------------------------------------
# Tests: DysonZoneCleanButton
# ---------------------------------------------------------------------------


class TestDysonZoneCleanButton:
    """Test DysonZoneCleanButton entity."""

    _FAKE_PMAP = PersistentMapMeta(
        id="pmap-1", name=None, zones_definition_last_updated_date=None, zones=[]
    )
    _FAKE_ZONE = ZoneMeta(id="zone-99", name="Kitchen", icon="kitchen", area=None)

    def _make(self, coordinator, pmap=None, zone=None) -> DysonZoneCleanButton:
        return DysonZoneCleanButton(
            coordinator,
            pmap or self._FAKE_PMAP,
            zone or self._FAKE_ZONE,
        )

    def test_init_sets_unique_id(self, mock_robot_coordinator):
        """unique_id is map-qualified: serial + map id + zone id."""
        btn = self._make(mock_robot_coordinator)
        assert btn._attr_unique_id == "VS9-GB-HJA0000A_clean_zone_pmap-1_zone-99"

    def test_init_sets_name_from_zone(self, mock_robot_coordinator):
        """Name is 'Clean <zone name>'."""
        btn = self._make(mock_robot_coordinator)
        assert btn._attr_name == "Clean Kitchen"

    def test_init_qualified_name_includes_map(self, mock_robot_coordinator):
        """qualify_name=True appends the map name (multi-map robots)."""
        pmap = PersistentMapMeta(
            id="pmap-2",
            name="Downstairs",
            zones_definition_last_updated_date=None,
            zones=[],
        )
        btn = DysonZoneCleanButton(
            mock_robot_coordinator, pmap, self._FAKE_ZONE, qualify_name=True
        )
        assert btn._attr_name == "Clean Kitchen (Downstairs)"

    def test_init_zone_name_fallback(self, mock_robot_coordinator):
        """Missing zone name falls back to 'Zone <id>'."""
        zone = ZoneMeta(id="z42", name=None, icon=None, area=None)
        btn = self._make(mock_robot_coordinator, zone=zone)
        assert btn._attr_name == "Clean Zone z42"

    def test_init_stores_pmap_and_zone_ids(self, mock_robot_coordinator):
        """_pmap_id and _zone_id are stored correctly."""
        btn = self._make(mock_robot_coordinator)
        assert btn._pmap_id == "pmap-1"
        assert btn._zone_id == "zone-99"

    def test_init_icon_from_known_key(self, mock_robot_coordinator):
        """Icon is resolved from zone icon key."""
        btn = self._make(mock_robot_coordinator)
        assert btn._attr_icon == "mdi:silverware-fork-knife"

    @pytest.mark.asyncio
    async def test_async_press_sends_correct_command(self, mock_robot_coordinator):
        """async_press calls robot_start_clean with the right cleaning programme."""
        mock_robot_coordinator.device.robot_start_clean = AsyncMock()
        btn = self._make(mock_robot_coordinator)
        await btn.async_press()

        mock_robot_coordinator.device.robot_start_clean.assert_called_once_with(
            cleaning_mode="zoneConfigured",
            full_clean_type="immediate",
            cleaning_programme={
                "persistentMapId": "pmap-1",
                "orderedZones": [],
                "unorderedZones": ["zone-99"],
            },
        )

    @pytest.mark.asyncio
    async def test_async_press_no_device_raises(self, mock_robot_coordinator):
        """async_press raises HomeAssistantError when device is None."""
        mock_robot_coordinator.device = None
        btn = self._make(mock_robot_coordinator)
        with pytest.raises(HomeAssistantError):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_async_press_exception_wraps_as_ha_error(
        self, mock_robot_coordinator
    ):
        """Exceptions from robot_start_clean are wrapped as HomeAssistantError."""
        mock_robot_coordinator.device.robot_start_clean = AsyncMock(
            side_effect=Exception("mqtt failure")
        )
        btn = self._make(mock_robot_coordinator)
        with pytest.raises(HomeAssistantError, match="Failed to start clean"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_async_press_includes_zdlud_when_present(
        self, mock_robot_coordinator
    ):
        """zonesDefinitionLastUpdatedDate from the map is sent in the programme."""
        mock_robot_coordinator.device.robot_start_clean = AsyncMock()
        pmap = PersistentMapMeta(
            id="pmap-1",
            name=None,
            zones_definition_last_updated_date="2026-03-01T12:00:00Z",
            zones=[],
        )
        btn = self._make(mock_robot_coordinator, pmap=pmap)
        await btn.async_press()

        programme = mock_robot_coordinator.device.robot_start_clean.call_args.kwargs[
            "cleaning_programme"
        ]
        assert programme["zonesDefinitionLastUpdatedDate"] == "2026-03-01T12:00:00Z"

    @pytest.mark.asyncio
    async def test_async_press_blocked_when_other_map_is_current(
        self, mock_robot_coordinator
    ):
        """Pressing a zone on a non-current map raises instead of sending."""
        mock_robot_coordinator.device.robot_start_clean = AsyncMock()
        cached_maps = [
            PersistentMapMeta(
                id="pmap-1",
                name="Upstairs",
                zones_definition_last_updated_date=None,
                zones=[],
            ),
            PersistentMapMeta(
                id="pmap-2",
                name="Downstairs",
                zones_definition_last_updated_date=None,
                zones=[],
                is_current_map=True,
            ),
        ]
        cache = MagicMock()
        cache.get_stale.return_value = cached_maps
        btn = self._make(mock_robot_coordinator)  # button belongs to pmap-1
        with patch(
            "custom_components.hass_dyson.services._persistent_map_cache", cache
        ):
            with pytest.raises(HomeAssistantError, match="currently using map"):
                await btn.async_press()

        mock_robot_coordinator.device.robot_start_clean.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_press_allowed_when_own_map_is_current(
        self, mock_robot_coordinator
    ):
        """Pressing a zone on the current map sends the command."""
        mock_robot_coordinator.device.robot_start_clean = AsyncMock()
        cached_maps = [
            PersistentMapMeta(
                id="pmap-1",
                name="Upstairs",
                zones_definition_last_updated_date=None,
                zones=[],
                is_current_map=True,
            ),
        ]
        cache = MagicMock()
        cache.get_stale.return_value = cached_maps
        btn = self._make(mock_robot_coordinator)
        with patch(
            "custom_components.hass_dyson.services._persistent_map_cache", cache
        ):
            await btn.async_press()

        mock_robot_coordinator.device.robot_start_clean.assert_called_once()

    def test_available_false_when_other_map_is_current(self, mock_robot_coordinator):
        """Button is unavailable while the cloud flags a different map current."""
        cached_maps = [
            PersistentMapMeta(
                id="pmap-2",
                name="Downstairs",
                zones_definition_last_updated_date=None,
                zones=[],
                is_current_map=True,
            ),
        ]
        cache = MagicMock()
        cache.get_stale.return_value = cached_maps
        btn = self._make(mock_robot_coordinator)  # belongs to pmap-1
        with patch(
            "custom_components.hass_dyson.services._persistent_map_cache", cache
        ):
            assert btn.available is False

    def test_available_when_currency_unknown(self, mock_robot_coordinator):
        """No isCurrentMap flag anywhere (v1 API) → every button stays available."""
        cached_maps = [
            PersistentMapMeta(
                id="pmap-1",
                name=None,
                zones_definition_last_updated_date=None,
                zones=[],
            ),
            PersistentMapMeta(
                id="pmap-2",
                name=None,
                zones_definition_last_updated_date=None,
                zones=[],
            ),
        ]
        cache = MagicMock()
        cache.get_stale.return_value = cached_maps
        btn = self._make(mock_robot_coordinator)
        with patch(
            "custom_components.hass_dyson.services._persistent_map_cache", cache
        ):
            assert btn.available is True


# ---------------------------------------------------------------------------
# Tests: DysonRefreshZonesButton
# ---------------------------------------------------------------------------


class TestDysonRefreshZonesButton:
    """Test DysonRefreshZonesButton entity."""

    def test_init_sets_unique_id(self, mock_robot_coordinator):
        """unique_id is based on serial number."""
        btn = DysonRefreshZonesButton(mock_robot_coordinator)
        assert btn._attr_unique_id == "VS9-GB-HJA0000A_refresh_zones"

    def test_init_sets_name_and_icon(self, mock_robot_coordinator):
        """Name and icon are set correctly."""
        btn = DysonRefreshZonesButton(mock_robot_coordinator)
        assert btn._attr_name == "Refresh Zone List"
        assert btn._attr_icon == "mdi:refresh"

    def test_init_entity_category_diagnostic(self, mock_robot_coordinator):
        """Entity category is DIAGNOSTIC."""
        btn = DysonRefreshZonesButton(mock_robot_coordinator)
        assert btn._attr_entity_category == EntityCategory.DIAGNOSTIC

    @pytest.mark.asyncio
    async def test_async_press_invalidates_cache_and_refetches(
        self, mock_robot_coordinator
    ):
        """async_press invalidates the cache entry and re-fetches map metadata."""
        from custom_components.hass_dyson.coordinator import TTLCache

        btn = DysonRefreshZonesButton(mock_robot_coordinator)
        fake_maps = [
            PersistentMapMeta(
                id="map-1",
                name=None,
                zones_definition_last_updated_date=None,
                zones=[ZoneMeta(id="z1", name=None, icon=None, area=None)],
            )
        ]
        fake_cache = TTLCache(3600)
        fake_cache.set("VS9-GB-HJA0000A", "stale_data")
        with (
            patch(
                "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
                AsyncMock(return_value=fake_maps),
            ),
            patch(
                "custom_components.hass_dyson.services._persistent_map_cache",
                fake_cache,
            ),
        ):
            await btn.async_press()

        # Cache entry should be removed after invalidation
        assert fake_cache.get_stale("VS9-GB-HJA0000A") is None

    @pytest.mark.asyncio
    async def test_async_press_exception_raises_ha_error(self, mock_robot_coordinator):
        """Exceptions from _fetch_persistent_map_metadata are wrapped as HAError."""
        btn = DysonRefreshZonesButton(mock_robot_coordinator)
        with (
            patch(
                "custom_components.hass_dyson.services._fetch_persistent_map_metadata",
                AsyncMock(side_effect=Exception("cloud down")),
            ),
            patch(
                "custom_components.hass_dyson.services._persistent_map_cache",
                MagicMock(),
            ),
        ):
            with pytest.raises(HomeAssistantError, match="Failed to refresh zones"):
                await btn.async_press()


# ---------------------------------------------------------------------------
# Tests: _icon_for_zone
# ---------------------------------------------------------------------------


class TestIconForZone:
    """Test the _icon_for_zone helper."""

    def test_known_icon_key_returns_mdi(self):
        """Known icon keys return the mapped MDI icon."""
        assert _icon_for_zone("kitchen") == "mdi:silverware-fork-knife"
        assert _icon_for_zone("bedroom") == "mdi:bed-outline"
        assert _icon_for_zone("bathroom") == "mdi:shower"
        assert _icon_for_zone("living_room") == "mdi:sofa"
        assert _icon_for_zone("hallway") == "mdi:floor-plan"

    def test_unknown_icon_key_returns_vacuum(self):
        """Unknown keys fall back to mdi:vacuum."""
        assert _icon_for_zone("conservatory") == "mdi:vacuum"
        assert _icon_for_zone("random_room") == "mdi:vacuum"

    def test_none_returns_vacuum(self):
        """None icon key falls back to mdi:vacuum."""
        assert _icon_for_zone(None) == "mdi:vacuum"

    def test_empty_string_returns_vacuum(self):
        """Empty string falls back to mdi:vacuum."""
        assert _icon_for_zone("") == "mdi:vacuum"


# ---------------------------------------------------------------------------
# Tests: pre-multi-map unique_id migration
# ---------------------------------------------------------------------------


class _FakeEntityRegistry:
    """Minimal entity-registry stand-in: unique_id → entity_id mapping."""

    def __init__(self, entries: dict[str, str]):
        # entries: {unique_id: entity_id}
        self.entries = dict(entries)
        self.updates: list[tuple[str, str]] = []

    def async_get_entity_id(self, domain, platform, unique_id):
        return self.entries.get(unique_id)

    def async_update_entity(self, entity_id, *, new_unique_id):
        for uid, eid in list(self.entries.items()):
            if eid == entity_id:
                del self.entries[uid]
        self.entries[new_unique_id] = entity_id
        self.updates.append((entity_id, new_unique_id))


class TestZoneButtonUniqueIdMigration:
    """Test _async_migrate_zone_button_unique_ids."""

    @staticmethod
    def _maps():
        return [
            PersistentMapMeta(
                id="map-1",
                name="Upstairs",
                zones_definition_last_updated_date=None,
                zones=[
                    ZoneMeta(id="1", name="Hallway", icon=None, area=None),
                    ZoneMeta(id="2", name="Office", icon=None, area=None),
                ],
            ),
            PersistentMapMeta(
                id="map-2",
                name="Downstairs",
                zones_definition_last_updated_date=None,
                zones=[ZoneMeta(id="1", name="Kitchen", icon=None, area=None)],
            ),
        ]

    def _run(self, registry, mock_robot_coordinator, maps=None):
        with patch(
            "custom_components.hass_dyson.button.er.async_get",
            return_value=registry,
        ):
            _async_migrate_zone_button_unique_ids(
                MagicMock(), mock_robot_coordinator, maps or self._maps()
            )

    def test_old_unique_ids_migrate_to_first_map_in_api_order(
        self, mock_robot_coordinator
    ):
        """Old bare-zone-id unique_ids migrate to the first map carrying the id.

        This reproduces which map the pre-multi-map dedupe created the button
        for, so existing entities keep their entity_id and history.
        """
        registry = _FakeEntityRegistry(
            {
                "VS9-GB-HJA0000A_clean_zone_1": "button.visnav_clean_hallway",
                "VS9-GB-HJA0000A_clean_zone_2": "button.visnav_clean_office",
            }
        )
        self._run(registry, mock_robot_coordinator)

        assert sorted(registry.updates) == [
            ("button.visnav_clean_hallway", "VS9-GB-HJA0000A_clean_zone_map-1_1"),
            ("button.visnav_clean_office", "VS9-GB-HJA0000A_clean_zone_map-1_2"),
        ]
        # The second map's colliding zone id "1" did NOT steal the old entity
        assert "VS9-GB-HJA0000A_clean_zone_map-2_1" not in registry.entries

    def test_migration_is_idempotent(self, mock_robot_coordinator):
        """A second run after migration performs no further updates."""
        registry = _FakeEntityRegistry(
            {"VS9-GB-HJA0000A_clean_zone_1": "button.visnav_clean_hallway"}
        )
        self._run(registry, mock_robot_coordinator)
        first = list(registry.updates)
        self._run(registry, mock_robot_coordinator)
        assert registry.updates == first

    def test_no_old_entities_no_updates(self, mock_robot_coordinator):
        """Fresh installs (no old-format unique_ids) are untouched."""
        registry = _FakeEntityRegistry({})
        self._run(registry, mock_robot_coordinator)
        assert registry.updates == []

    def test_collision_with_existing_new_unique_id_skips(
        self, mock_robot_coordinator
    ):
        """If the map-qualified unique_id already exists, the old one is left."""
        registry = _FakeEntityRegistry(
            {
                "VS9-GB-HJA0000A_clean_zone_1": "button.old_hallway",
                "VS9-GB-HJA0000A_clean_zone_map-1_1": "button.new_hallway",
            }
        )
        self._run(registry, mock_robot_coordinator)
        assert registry.updates == []
        assert (
            registry.entries["VS9-GB-HJA0000A_clean_zone_1"] == "button.old_hallway"
        )
