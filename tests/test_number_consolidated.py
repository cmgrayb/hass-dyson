"""Comprehensive tests for the Dyson number platform.

This consolidated module combines number platform testing including:
- Main number platform functionality (test_number.py)
- Missing coverage areas and edge cases (test_number_missing_coverage.py)

Following pure pytest patterns for Home Assistant integration testing.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from homeassistant.components.number import NumberMode
from homeassistant.const import CONF_HOST

from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
from custom_components.hass_dyson.number import (
    DysonOscillationAngleSpanNumber,
    DysonOscillationCenterAngleNumber,
    DysonOscillationLowerAngleNumber,
    DysonOscillationUpperAngleNumber,
    DysonSleepTimerNumber,
    async_setup_entry,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = Mock(spec=DysonDataUpdateCoordinator)
    coordinator.serial_number = "NK6-EU-MHA0000A"
    coordinator.device_name = "Test Dyson"
    coordinator.device = Mock()
    coordinator.device.set_sleep_timer = AsyncMock()
    coordinator.device.set_oscillation_angles = AsyncMock()
    coordinator.device.set_oscillation = AsyncMock()
    coordinator.device.get_state_value = Mock()
    # Set up device_category as a list of strings
    coordinator.device_category = ["ec"]  # Environment cleaner category
    coordinator.data = {
        "product-state": {
            "sltm": "0060",  # Sleep timer: 60 minutes
            "ancp": "0180",  # Oscillation angle: 180°
            "osal": "0045",  # Lower angle: 45°
            "osau": "0315",  # Upper angle: 315°
        }
    }
    return coordinator


@pytest.fixture
def mock_hass(mock_coordinator):
    """Create a mock Home Assistant instance."""
    hass = Mock()
    hass.data = {"hass_dyson": {"NK6-EU-MHA0000A": mock_coordinator}}
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = Mock()
    entry.data = {CONF_HOST: "192.168.1.100"}
    entry.unique_id = "NK6-EU-MHA0000A"
    entry.entry_id = "NK6-EU-MHA0000A"
    return entry


class TestNumberPlatformSetup:
    """Test number platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_scheduling_capability(
        self, mock_hass, mock_config_entry
    ):
        """Test setting up entry with scheduling capability."""
        coordinator = mock_hass.data["hass_dyson"]["NK6-EU-MHA0000A"]
        coordinator.device.device_info = {
            "product_type": "469",
            "capabilities": ["Scheduling"],
        }
        coordinator.device_capabilities = ["Scheduling"]
        coordinator.device_category = ["other"]

        mock_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DysonSleepTimerNumber)

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_oscillation_capability(
        self, mock_hass, mock_config_entry
    ):
        """Test setting up entry with oscillation capability."""
        coordinator = mock_hass.data["hass_dyson"]["NK6-EU-MHA0000A"]
        coordinator.device.device_info = {
            "product_type": "469",
            "capabilities": ["AdvanceOscillationDay1"],
        }
        coordinator.device_capabilities = ["AdvanceOscillationDay1"]

        mock_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 4
        assert isinstance(entities[0], DysonOscillationLowerAngleNumber)
        assert isinstance(entities[1], DysonOscillationUpperAngleNumber)
        assert isinstance(entities[2], DysonOscillationCenterAngleNumber)
        assert isinstance(entities[3], DysonOscillationAngleSpanNumber)


class TestDysonSleepTimerNumber:
    """Test DysonSleepTimerNumber entity."""

    def test_sleep_timer_initialization(self, mock_coordinator):
        """Test sleep timer number initialization."""
        entity = DysonSleepTimerNumber(mock_coordinator)

        assert entity._attr_unique_id == "NK6-EU-MHA0000A_sleep_timer"
        assert entity._attr_translation_key == "sleep_timer"
        assert entity._attr_icon == "mdi:timer"
        assert entity._attr_mode == NumberMode.BOX
        assert entity._attr_native_min_value == 0
        assert entity._attr_native_max_value == 540  # 9 hours
        assert entity._attr_native_step == 15  # 15-minute increments
        assert entity._attr_native_unit_of_measurement == "min"

    def test_handle_coordinator_update_with_device(self, mock_coordinator):
        """Test handling coordinator update with device."""
        entity = DysonSleepTimerNumber(mock_coordinator)
        mock_coordinator.device.get_state_value.return_value = "0060"

        with patch.object(entity, "async_write_ha_state"):
            with patch.object(entity, "_start_timer_polling_if_needed"):
                entity._handle_coordinator_update()

        assert entity._attr_native_value == 60

    def test_handle_coordinator_update_zero_timer(self, mock_coordinator):
        """Test handling coordinator update with zero timer."""
        entity = DysonSleepTimerNumber(mock_coordinator)
        mock_coordinator.device.get_state_value.return_value = "0000"

        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity._attr_native_value == 0

    @pytest.mark.asyncio
    async def test_async_set_native_value_success(self, mock_coordinator):
        """Test setting sleep timer value successfully."""
        entity = DysonSleepTimerNumber(mock_coordinator)

        with patch("custom_components.hass_dyson.number._LOGGER") as mock_logger:
            await entity.async_set_native_value(90.0)

        mock_coordinator.device.set_sleep_timer.assert_called_once_with(90)
        assert mock_logger.debug.call_count == 2  # Setting + waiting logs

    @pytest.mark.asyncio
    async def test_async_set_native_value_no_device(self, mock_coordinator):
        """Test setting sleep timer value without device."""
        entity = DysonSleepTimerNumber(mock_coordinator)
        mock_coordinator.device = None

        await entity.async_set_native_value(90.0)
        # Should return early without calling device method

    @pytest.mark.asyncio
    async def test_async_set_native_value_exception(self, mock_coordinator):
        """Test setting sleep timer value with exception."""
        entity = DysonSleepTimerNumber(mock_coordinator)
        mock_coordinator.device.set_sleep_timer.side_effect = Exception("Test error")

        with patch("custom_components.hass_dyson.number._LOGGER") as mock_logger:
            await entity.async_set_native_value(90.0)

        mock_logger.error.assert_called_once()


class TestDysonOscillationLowerAngleNumber:
    """Test DysonOscillationLowerAngleNumber entity."""

    def test_lower_angle_initialization(self, mock_coordinator):
        """Test lower angle number initialization."""
        entity = DysonOscillationLowerAngleNumber(mock_coordinator)

        assert entity._attr_unique_id == "NK6-EU-MHA0000A_oscillation_lower_angle"
        assert entity._attr_translation_key == "oscillation_low_angle"
        assert entity._attr_icon == "mdi:rotate-left"
        assert entity._attr_mode == NumberMode.SLIDER
        assert entity._attr_native_min_value == 0
        assert entity._attr_native_max_value == 350
        assert entity._attr_native_step == 5
        assert entity._attr_native_unit_of_measurement == "°"

    def test_handle_coordinator_update_with_device(self, mock_coordinator):
        """Test handling coordinator update with device."""
        entity = DysonOscillationLowerAngleNumber(mock_coordinator)
        mock_coordinator.device.get_state_value.return_value = "0045"

        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity._attr_native_value == 45

    @pytest.mark.asyncio
    async def test_async_set_native_value_success(self, mock_coordinator):
        """Test setting lower angle value successfully."""
        entity = DysonOscillationLowerAngleNumber(mock_coordinator)
        # Mock current upper angle
        mock_coordinator.data = {"product-state": {"osau": "0315"}}

        with patch("custom_components.hass_dyson.number._LOGGER") as mock_logger:
            await entity.async_set_native_value(90.0)

        mock_coordinator.device.set_oscillation_angles.assert_called_once_with(90, 315)
        mock_logger.debug.assert_called_once()


class TestDysonOscillationUpperAngleNumber:
    """Test DysonOscillationUpperAngleNumber entity."""

    def test_upper_angle_initialization(self, mock_coordinator):
        """Test upper angle number initialization."""
        entity = DysonOscillationUpperAngleNumber(mock_coordinator)

        assert entity._attr_unique_id == "NK6-EU-MHA0000A_oscillation_upper_angle"
        assert entity._attr_translation_key == "oscillation_high_angle"
        assert entity._attr_icon == "mdi:rotate-right"

    @pytest.mark.asyncio
    async def test_async_set_native_value_success(self, mock_coordinator):
        """Test setting upper angle value successfully."""
        entity = DysonOscillationUpperAngleNumber(mock_coordinator)
        # Mock current lower angle
        mock_coordinator.data = {"product-state": {"osal": "0045"}}

        await entity.async_set_native_value(270.0)

        mock_coordinator.device.set_oscillation_angles.assert_called_once_with(45, 270)


class TestDysonOscillationCenterAngleNumber:
    """Test DysonOscillationCenterAngleNumber entity."""

    def test_center_angle_initialization(self, mock_coordinator):
        """Test center angle number initialization."""
        entity = DysonOscillationCenterAngleNumber(mock_coordinator)

        assert entity._attr_unique_id == "NK6-EU-MHA0000A_oscillation_center_angle"
        assert entity._attr_translation_key == "oscillation_center_angle"
        assert entity._attr_icon == "mdi:crosshairs"

    def test_handle_coordinator_update_with_device(self, mock_coordinator):
        """Test handling coordinator update with device."""
        entity = DysonOscillationCenterAngleNumber(mock_coordinator)
        # Mock lower and upper angles: 45° and 315°, center should be 180°
        mock_coordinator.device.get_state_value.side_effect = ["0045", "0315"]

        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity._attr_native_value == 180  # (45 + 315) // 2


class TestDysonOscillationAngleSpanNumber:
    """Test DysonOscillationAngleSpanNumber entity."""

    def test_angle_span_initialization(self, mock_coordinator):
        """Test angle span number initialization."""
        entity = DysonOscillationAngleSpanNumber(mock_coordinator)

        assert entity._attr_unique_id == "NK6-EU-MHA0000A_oscillation_angle_span"
        assert entity._attr_translation_key == "oscillation_angle_span"
        assert entity._attr_icon == "mdi:angle-acute"

    def test_handle_coordinator_update_with_device(self, mock_coordinator):
        """Test handling coordinator update with device."""
        entity = DysonOscillationAngleSpanNumber(mock_coordinator)
        # Mock lower and upper angles to create 270° span (45° to 315°)
        mock_coordinator.device.get_state_value.side_effect = ["0045", "0315"]

        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity._attr_native_value == 270  # 315 - 45


class TestNumberMissingCoverage:
    """Test previously uncovered number.py code paths."""

    @pytest.mark.asyncio
    async def test_async_will_remove_from_hass_with_task(self, mock_coordinator):
        """Test entity removal with active polling task."""
        entity = DysonSleepTimerNumber(mock_coordinator)

        # Create a mock task
        mock_task = MagicMock()
        entity._timer_polling_task = mock_task

        # Mock the parent method
        with patch(
            "custom_components.hass_dyson.entity.DysonEntity.async_will_remove_from_hass",
            new=AsyncMock(),
        ):
            await entity.async_will_remove_from_hass()

        mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_will_remove_from_hass_no_task(self, mock_coordinator):
        """Test entity removal without polling task."""
        entity = DysonSleepTimerNumber(mock_coordinator)
        # Don't set _timer_polling_task attribute

        # Mock the parent method
        with patch(
            "custom_components.hass_dyson.entity.DysonEntity.async_will_remove_from_hass",
            new=AsyncMock(),
        ):
            # Should not raise exception
            await entity.async_will_remove_from_hass()

    def test_start_timer_polling_already_running(self, mock_coordinator):
        """Test starting timer polling when already running."""
        entity = DysonSleepTimerNumber(mock_coordinator)

        # Create mock running task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        entity._timer_polling_task = mock_task

        # Mock coordinator with timer data
        entity.coordinator.device = MagicMock()
        entity.coordinator.data = {
            "product-state": {
                "sltm": "0060"  # 60 minutes timer
            }
        }

        # Should return early without creating new task
        entity._start_timer_polling_if_needed()

        # Task should not have been replaced
        assert entity._timer_polling_task is mock_task

    @pytest.mark.asyncio
    async def test_poll_timer_updates_cancelled(self, mock_coordinator):
        """Test timer polling with cancellation."""
        entity = DysonSleepTimerNumber(mock_coordinator)

        # Mock the polling methods to raise CancelledError
        with patch.object(
            entity, "_do_frequent_initial_polling", side_effect=asyncio.CancelledError
        ):
            await entity._poll_timer_updates()
            # Should handle CancelledError gracefully

    @pytest.mark.asyncio
    async def test_poll_timer_updates_connection_error(self, mock_coordinator):
        """Test timer polling with connection error."""
        entity = DysonSleepTimerNumber(mock_coordinator)

        # Mock the polling methods to raise ConnectionError
        with patch.object(
            entity,
            "_do_frequent_initial_polling",
            side_effect=ConnectionError("Connection failed"),
        ):
            await entity._poll_timer_updates()
            # Should handle ConnectionError gracefully


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
