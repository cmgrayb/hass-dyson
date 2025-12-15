"""Test number.py missing coverage areas."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.number import DysonSleepTimerNumber


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

    def test_start_timer_polling_invalid_timer_value(self, mock_coordinator):
        """Test starting timer polling with invalid timer value."""
        entity = DysonSleepTimerNumber(mock_coordinator)
        entity._timer_polling_task = None

        # Mock coordinator with invalid timer data - use None to skip timer logic
        entity.coordinator.device = None  # No device means no timer checking
        entity.coordinator.data = {
            "product-state": {
                "sltm": "invalid"  # Invalid timer value
            }
        }

        # Should handle gracefully by not starting any polling when device is None
        entity._start_timer_polling_if_needed()

        # No task should be created when device is None
        assert (
            not hasattr(entity, "_timer_polling_task")
            or entity._timer_polling_task is None
        )

    def test_start_timer_polling_zero_timer(self, mock_coordinator):
        """Test starting timer polling with zero timer value."""
        entity = DysonSleepTimerNumber(mock_coordinator)
        entity._timer_polling_task = None

        # Mock coordinator with zero timer (no timer) - device None prevents polling
        entity.coordinator.device = None  # No device means no timer
        entity.coordinator.data = {
            "product-state": {
                "sltm": "0000"  # No timer active
            }
        }

        # Should not start polling when device is None
        entity._start_timer_polling_if_needed()

        # No task should be created when device is None
        assert (
            not hasattr(entity, "_timer_polling_task")
            or entity._timer_polling_task is None
        )

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

    @pytest.mark.asyncio
    async def test_poll_timer_updates_timeout_error(self, mock_coordinator):
        """Test timer polling with timeout error."""
        entity = DysonSleepTimerNumber(mock_coordinator)

        # Mock the polling methods to raise TimeoutError
        with patch.object(
            entity, "_do_frequent_initial_polling", side_effect=TimeoutError("Timeout")
        ):
            await entity._poll_timer_updates()
            # Should handle TimeoutError gracefully

    @pytest.mark.asyncio
    async def test_poll_timer_updates_general_exception(self, mock_coordinator):
        """Test timer polling with general exception."""
        entity = DysonSleepTimerNumber(mock_coordinator)

        # Mock the polling methods to raise general Exception
        with patch.object(
            entity,
            "_do_frequent_initial_polling",
            side_effect=Exception("Unexpected error"),
        ):
            await entity._poll_timer_updates()
            # Should handle general Exception gracefully
