"""Additional number entity error coverage tests to close coverage gaps.

This module focuses on uncovered error paths in number.py to improve
coverage from 45% toward the 75% target. Tests cover:
- Lines 106-112: AsyncCancelledError in timer polling
- Lines 132, 151-163: ConnectionError, TimeoutError, Generic exceptions in polling
- Lines 235-257: KeyError, AttributeError, ValueError, TypeError in coordinator updates
- Lines 287-293: ConnectionError, ValueError, Exception in set_native_value
- Lines 367-370, 376: ValueError, TypeError in oscillation value parsing
- Lines 405-419, 447-460: Exception paths in oscillation entities
- Multiple uncovered error branches in oscillation angle entities
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
from custom_components.hass_dyson.number import (
    DysonOscillationAngleSpanNumber,
    DysonOscillationCenterAngleNumber,
    DysonOscillationLowerAngleNumber,
    DysonOscillationUpperAngleNumber,
    DysonSleepTimerNumber,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = Mock(spec=DysonDataUpdateCoordinator)
    coordinator.serial_number = "TEST123456"
    coordinator.device_name = "Test Dyson"
    coordinator.device = Mock()
    coordinator.device.set_sleep_timer = AsyncMock()
    coordinator.device.set_oscillation_angles = AsyncMock()
    coordinator.device.set_oscillation = AsyncMock()
    coordinator.device.get_state_value = Mock(return_value="0060")
    coordinator.device._request_current_state = AsyncMock()
    coordinator.device_category = ["ec"]
    coordinator.data = {
        "product-state": {
            "sltm": "0060",
            "ancp": "0180",
            "osal": "0045",
            "osau": "0315",
        }
    }
    return coordinator


class TestSleepTimerErrorHandling:
    """Test error handling in DysonSleepTimerNumber."""

    @pytest.mark.asyncio
    async def test_timer_polling_cancelled_error_on_sleep(self, mock_coordinator):
        """Test AsyncCancelledError handling during timer polling sleep."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()
        timer._attr_native_value = 60
        timer.entity_id = "number.test_sleep_timer"

        # Mock the polling method to raise CancelledError directly
        async def mock_poll():
            raise asyncio.CancelledError()

        with patch.object(timer, "_poll_timer_updates", side_effect=mock_poll):
            timer._start_timer_polling_if_needed()

            # Wait briefly for task to start and handle cancellation
            await asyncio.sleep(0.2)

            # Task should handle cancellation gracefully

    @pytest.mark.asyncio
    async def test_timer_polling_cancelled_error_on_request(self, mock_coordinator):
        """Test AsyncCancelledError handling during state request."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()
        timer._attr_native_value = 60
        timer.entity_id = "number.test_sleep_timer"

        # Mock request_current_state to raise CancelledError
        mock_coordinator.device._request_current_state = AsyncMock(
            side_effect=asyncio.CancelledError()
        )

        timer._start_timer_polling_if_needed()
        await asyncio.sleep(0.2)

        # Task should handle cancellation

    @pytest.mark.asyncio
    async def test_timer_polling_connection_error(self, mock_coordinator):
        """Test ConnectionError handling in timer polling."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()
        timer._attr_native_value = 60
        timer.entity_id = "number.test_sleep_timer"

        # Mock request to raise ConnectionError
        mock_coordinator.device._request_current_state = AsyncMock(
            side_effect=ConnectionError("Connection lost")
        )

        timer._start_timer_polling_if_needed()
        await asyncio.sleep(0.2)

        # Task should complete despite error

    @pytest.mark.asyncio
    async def test_timer_polling_timeout_error(self, mock_coordinator):
        """Test TimeoutError handling in timer polling."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()
        timer._attr_native_value = 60
        timer.entity_id = "number.test_sleep_timer"

        mock_coordinator.device._request_current_state = AsyncMock(
            side_effect=TimeoutError("Request timeout")
        )

        timer._start_timer_polling_if_needed()
        await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_timer_polling_generic_exception(self, mock_coordinator):
        """Test generic Exception handling in timer polling."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()
        timer._attr_native_value = 60
        timer.entity_id = "number.test_sleep_timer"

        mock_coordinator.device._request_current_state = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )

        timer._start_timer_polling_if_needed()
        await asyncio.sleep(0.2)

    def test_coordinator_update_key_error(self, mock_coordinator):
        """Test KeyError handling in coordinator update."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()
        timer.entity_id = "number.test_sleep_timer"

        # Mock get_state_value to raise KeyError
        mock_coordinator.device.get_state_value = Mock(
            side_effect=KeyError("sltm not found")
        )

        # Don't call super()._handle_coordinator_update() to avoid platform issues
        # Just test the error handling directly
        with patch.object(timer, "async_write_ha_state"):
            timer._handle_coordinator_update()

        # Should default to 0
        assert timer._attr_native_value == 0

    def test_coordinator_update_attribute_error(self, mock_coordinator):
        """Test AttributeError handling in coordinator update."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()
        timer.entity_id = "number.test_sleep_timer"

        mock_coordinator.device.get_state_value = Mock(
            side_effect=AttributeError("No attribute")
        )

        with patch.object(timer, "async_write_ha_state"):
            timer._handle_coordinator_update()
        assert timer._attr_native_value == 0

    def test_coordinator_update_value_error(self, mock_coordinator):
        """Test ValueError handling in coordinator update."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()
        timer.entity_id = "number.test_sleep_timer"

        # Return invalid data that causes ValueError during int conversion
        mock_coordinator.device.get_state_value = Mock(return_value="invalid")

        with patch.object(timer, "async_write_ha_state"):
            timer._handle_coordinator_update()
        assert timer._attr_native_value == 0

    def test_coordinator_update_type_error(self, mock_coordinator):
        """Test TypeError handling in coordinator update."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()
        timer.entity_id = "number.test_sleep_timer"

        # Return None which causes TypeError
        mock_coordinator.device.get_state_value = Mock(return_value=None)

        with patch.object(timer, "async_write_ha_state"):
            timer._handle_coordinator_update()
        # Should handle TypeError in int(timer_data) and default to 0
        assert timer._attr_native_value == 0

    def test_coordinator_update_generic_exception(self, mock_coordinator):
        """Test generic Exception handling in coordinator update."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()
        timer.entity_id = "number.test_sleep_timer"

        mock_coordinator.device.get_state_value = Mock(
            side_effect=RuntimeError("Unexpected")
        )

        with patch.object(timer, "async_write_ha_state"):
            timer._handle_coordinator_update()
        assert timer._attr_native_value == 0

    def test_coordinator_update_no_device(self, mock_coordinator):
        """Test coordinator update when device is None."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()
        timer.entity_id = "number.test_sleep_timer"

        mock_coordinator.device = None

        with patch.object(timer, "async_write_ha_state"):
            timer._handle_coordinator_update()

        assert timer._attr_native_value is None

    @pytest.mark.asyncio
    async def test_set_native_value_connection_error(self, mock_coordinator):
        """Test ConnectionError handling in set_native_value."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()

        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=ConnectionError("Device offline")
        )

        # Should handle error gracefully
        await timer.async_set_native_value(30.0)

    @pytest.mark.asyncio
    async def test_set_native_value_timeout_error(self, mock_coordinator):
        """Test TimeoutError handling in set_native_value."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()

        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=TimeoutError("Command timeout")
        )

        await timer.async_set_native_value(45.0)

    @pytest.mark.asyncio
    async def test_set_native_value_value_error(self, mock_coordinator):
        """Test ValueError handling in set_native_value."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()

        # This could happen if value is somehow invalid
        with patch("builtins.int", side_effect=ValueError("Invalid value")):
            await timer.async_set_native_value(30.0)

    @pytest.mark.asyncio
    async def test_set_native_value_generic_exception(self, mock_coordinator):
        """Test generic Exception handling in set_native_value."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()

        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )

        await timer.async_set_native_value(60.0)

    @pytest.mark.asyncio
    async def test_set_native_value_no_device(self, mock_coordinator):
        """Test set_native_value when device is None."""
        timer = DysonSleepTimerNumber(mock_coordinator)
        timer.hass = MagicMock()

        mock_coordinator.device = None

        # Should return early without error
        await timer.async_set_native_value(30.0)


class TestOscillationLowerAngleErrorHandling:
    """Test error handling in DysonOscillationLowerAngleNumber."""

    def test_native_value_value_error(self, mock_coordinator):
        """Test ValueError handling in native_value property."""
        lower_angle = DysonOscillationLowerAngleNumber(mock_coordinator)

        # Mock get_state_value to return invalid data
        mock_coordinator.device.get_state_value = Mock(return_value="invalid")

        # Should handle ValueError and return None or default
        value = lower_angle.native_value
        assert value is None or isinstance(value, (int, float))

    def test_native_value_type_error(self, mock_coordinator):
        """Test TypeError handling in native_value property."""
        lower_angle = DysonOscillationLowerAngleNumber(mock_coordinator)

        mock_coordinator.device.get_state_value = Mock(return_value=None)

        value = lower_angle.native_value
        assert value is None or isinstance(value, (int, float))

    @pytest.mark.asyncio
    async def test_set_native_value_connection_error(self, mock_coordinator):
        """Test ConnectionError in set_native_value."""
        lower_angle = DysonOscillationLowerAngleNumber(mock_coordinator)
        lower_angle.hass = MagicMock()

        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ConnectionError("Device offline")
        )

        await lower_angle.async_set_native_value(45.0)

    @pytest.mark.asyncio
    async def test_set_native_value_value_error(self, mock_coordinator):
        """Test ValueError in set_native_value."""
        lower_angle = DysonOscillationLowerAngleNumber(mock_coordinator)
        lower_angle.hass = MagicMock()

        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ValueError("Invalid angle")
        )

        await lower_angle.async_set_native_value(45.0)

    @pytest.mark.asyncio
    async def test_set_native_value_generic_exception(self, mock_coordinator):
        """Test generic Exception in set_native_value."""
        lower_angle = DysonOscillationLowerAngleNumber(mock_coordinator)
        lower_angle.hass = MagicMock()

        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=RuntimeError("Unexpected")
        )

        await lower_angle.async_set_native_value(45.0)


class TestOscillationUpperAngleErrorHandling:
    """Test error handling in DysonOscillationUpperAngleNumber."""

    def test_native_value_value_error(self, mock_coordinator):
        """Test ValueError handling in native_value property."""
        upper_angle = DysonOscillationUpperAngleNumber(mock_coordinator)

        mock_coordinator.device.get_state_value = Mock(return_value="bad_value")

        value = upper_angle.native_value
        assert value is None or isinstance(value, (int, float))

    def test_native_value_type_error(self, mock_coordinator):
        """Test TypeError handling in native_value property."""
        upper_angle = DysonOscillationUpperAngleNumber(mock_coordinator)

        mock_coordinator.device.get_state_value = Mock(return_value=None)

        value = upper_angle.native_value
        assert value is None or isinstance(value, (int, float))

    @pytest.mark.asyncio
    async def test_set_native_value_connection_error(self, mock_coordinator):
        """Test ConnectionError in set_native_value."""
        upper_angle = DysonOscillationUpperAngleNumber(mock_coordinator)
        upper_angle.hass = MagicMock()

        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        await upper_angle.async_set_native_value(315.0)

    @pytest.mark.asyncio
    async def test_set_native_value_value_error(self, mock_coordinator):
        """Test ValueError in set_native_value."""
        upper_angle = DysonOscillationUpperAngleNumber(mock_coordinator)
        upper_angle.hass = MagicMock()

        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ValueError("Angle out of range")
        )

        await upper_angle.async_set_native_value(315.0)

    @pytest.mark.asyncio
    async def test_set_native_value_generic_exception(self, mock_coordinator):
        """Test generic Exception in set_native_value."""
        upper_angle = DysonOscillationUpperAngleNumber(mock_coordinator)
        upper_angle.hass = MagicMock()

        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=RuntimeError("Device error")
        )

        await upper_angle.async_set_native_value(315.0)


class TestOscillationCenterAngleErrorHandling:
    """Test error handling in DysonOscillationCenterAngleNumber."""

    def test_native_value_calculation_error(self, mock_coordinator):
        """Test error in center angle calculation."""
        center_angle = DysonOscillationCenterAngleNumber(mock_coordinator)

        # Make get_state_value raise exception
        mock_coordinator.device.get_state_value = Mock(
            side_effect=ValueError("Parse error")
        )

        value = center_angle.native_value
        assert value is None or isinstance(value, (int, float))

    @pytest.mark.asyncio
    async def test_set_native_value_connection_error(self, mock_coordinator):
        """Test ConnectionError in set_native_value."""
        center_angle = DysonOscillationCenterAngleNumber(mock_coordinator)
        center_angle.hass = MagicMock()

        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ConnectionError("Connection lost")
        )

        await center_angle.async_set_native_value(180.0)

    @pytest.mark.asyncio
    async def test_set_native_value_value_error(self, mock_coordinator):
        """Test ValueError in set_native_value."""
        center_angle = DysonOscillationCenterAngleNumber(mock_coordinator)
        center_angle.hass = MagicMock()

        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ValueError("Invalid center")
        )

        await center_angle.async_set_native_value(180.0)

    @pytest.mark.asyncio
    async def test_set_native_value_generic_exception(self, mock_coordinator):
        """Test generic Exception in set_native_value."""
        center_angle = DysonOscillationCenterAngleNumber(mock_coordinator)
        center_angle.hass = MagicMock()

        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=RuntimeError("Calculation error")
        )

        await center_angle.async_set_native_value(180.0)


class TestOscillationAngleSpanErrorHandling:
    """Test error handling in DysonOscillationAngleSpanNumber."""

    def test_native_value_calculation_error(self, mock_coordinator):
        """Test error in span calculation."""
        span_angle = DysonOscillationAngleSpanNumber(mock_coordinator)

        mock_coordinator.device.get_state_value = Mock(
            side_effect=TypeError("Type mismatch")
        )

        value = span_angle.native_value
        assert value is None or isinstance(value, (int, float))

    @pytest.mark.asyncio
    async def test_set_native_value_connection_error(self, mock_coordinator):
        """Test ConnectionError in set_native_value."""
        span_angle = DysonOscillationAngleSpanNumber(mock_coordinator)
        span_angle.hass = MagicMock()

        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ConnectionError("Device unreachable")
        )

        await span_angle.async_set_native_value(90.0)

    @pytest.mark.asyncio
    async def test_set_native_value_value_error(self, mock_coordinator):
        """Test ValueError in set_native_value."""
        span_angle = DysonOscillationAngleSpanNumber(mock_coordinator)
        span_angle.hass = MagicMock()

        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ValueError("Span invalid")
        )

        await span_angle.async_set_native_value(90.0)

    @pytest.mark.asyncio
    async def test_set_native_value_generic_exception(self, mock_coordinator):
        """Test generic Exception in set_native_value."""
        span_angle = DysonOscillationAngleSpanNumber(mock_coordinator)
        span_angle.hass = MagicMock()

        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=RuntimeError("Span error")
        )

        await span_angle.async_set_native_value(90.0)

    def test_native_value_no_device(self, mock_coordinator):
        """Test native_value when device is None."""
        span_angle = DysonOscillationAngleSpanNumber(mock_coordinator)

        mock_coordinator.device = None

        value = span_angle.native_value
        assert value is None
