"""Additional number.py coverage tests to reach 75% overall target.

Targets uncovered areas in sleep timer polling and oscillation angle entities.
Expected impact: +2-3% overall coverage improvement (74% -> 76-77%).
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
from custom_components.hass_dyson.number import (
    DysonOscillationCenterAngleNumber,
    DysonOscillationLowerAngleNumber,
    DysonOscillationUpperAngleNumber,
    DysonSleepTimerNumber,
)


class TestSleepTimerPollingCoverage:
    """Tests for sleep timer polling logic."""

    @pytest.mark.asyncio
    async def test_poll_timer_updates_initial_polling_phase(self):
        """Test initial polling phase with 6 polls over 3 minutes."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-TIMER-001"
        coordinator.device = Mock()
        coordinator.device.is_connected = True
        coordinator.device._request_current_state = AsyncMock()
        coordinator.device.get_state_value = Mock(return_value="30")
        coordinator.data = {"product-state": {"sltm": "30"}}

        timer = DysonSleepTimerNumber(coordinator)

        # Mock asyncio.sleep to speed up test and count calls
        sleep_calls = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            sleep_calls.append(delay)
            # Use very short sleep to speed up test
            await original_sleep(0.001)

        with patch("asyncio.sleep", mock_sleep):
            with patch.object(timer, "_poll_timer_once", AsyncMock(return_value=True)):
                # Start polling task
                task = asyncio.create_task(timer._poll_timer_updates())

                # Wait briefly for initial polls to happen
                await asyncio.sleep(0.1)

                # Cancel task
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Should have at least attempted initial 30-second polls
        assert 30 in sleep_calls

    @pytest.mark.asyncio
    async def test_do_regular_polling_continues_with_60_second_intervals(self):
        """Test regular polling continues with 60-second intervals."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-TIMER-002"
        coordinator.device = Mock()
        coordinator.device.is_connected = True
        coordinator.device._request_current_state = AsyncMock()
        coordinator.device.get_state_value = Mock(return_value="45")
        coordinator.data = {"product-state": {"sltm": "45"}}

        timer = DysonSleepTimerNumber(coordinator)

        sleep_calls = []
        poll_count = [0]

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        async def mock_poll_once(poll_type):
            poll_count[0] += 1
            return poll_count[0] < 2

        with patch("custom_components.hass_dyson.number.asyncio.sleep", mock_sleep):
            with patch.object(timer, "_poll_timer_once", side_effect=mock_poll_once):
                await timer._do_regular_polling()

        assert 60 in sleep_calls
        assert poll_count[0] == 2

    @pytest.mark.asyncio
    async def test_poll_timer_once_device_not_connected(self):
        """Test poll_timer_once returns False when device not connected."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-TIMER-003"
        coordinator.device = Mock()
        coordinator.device.is_connected = False
        coordinator.data = {"product-state": {"sltm": "30"}}

        timer = DysonSleepTimerNumber(coordinator)

        result = await timer._poll_timer_once("test poll")

        assert result is False

    @pytest.mark.asyncio
    async def test_poll_timer_once_timer_is_off(self):
        """Test poll_timer_once returns False when timer shows OFF."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-TIMER-004"
        coordinator.device = Mock()
        coordinator.device.is_connected = True
        coordinator.device.get_state_value = Mock(return_value="OFF")
        coordinator.data = {"product-state": {"sltm": "OFF"}}

        timer = DysonSleepTimerNumber(coordinator)

        result = await timer._poll_timer_once("test poll")

        assert result is False

    @pytest.mark.asyncio
    async def test_poll_timer_once_timer_is_zero(self):
        """Test poll_timer_once returns False when timer value is 0."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-TIMER-005"
        coordinator.device = Mock()
        coordinator.device.is_connected = True
        coordinator.device.get_state_value = Mock(return_value="0")
        coordinator.data = {"product-state": {"sltm": "0"}}

        timer = DysonSleepTimerNumber(coordinator)

        result = await timer._poll_timer_once("test poll")

        assert result is False

    @pytest.mark.asyncio
    async def test_poll_timer_once_timer_active_success(self):
        """Test poll_timer_once returns True when timer active."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-TIMER-006"
        coordinator.device = Mock()
        coordinator.device.is_connected = True
        coordinator.device.get_state_value = Mock(return_value="45")
        coordinator.device._request_current_state = AsyncMock()
        coordinator.data = {"product-state": {"sltm": "45"}}

        timer = DysonSleepTimerNumber(coordinator)

        result = await timer._poll_timer_once("test poll")

        assert result is True
        coordinator.device._request_current_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_timer_polling_timer_value_error(self):
        """Test _start_timer_polling_if_needed handles ValueError in timer data."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-TIMER-007"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(return_value="INVALID")
        coordinator.data = {"product-state": {"sltm": "INVALID"}}

        timer = DysonSleepTimerNumber(coordinator)

        # Should not raise exception, should handle ValueError gracefully
        timer._start_timer_polling_if_needed()

        # No task should be created
        assert timer._timer_polling_task is None

    @pytest.mark.asyncio
    async def test_start_timer_polling_timer_type_error(self):
        """Test _start_timer_polling_if_needed handles TypeError in timer data."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-TIMER-008"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(return_value=["not", "an", "int"])
        coordinator.data = {"product-state": {"sltm": ["not", "an", "int"]}}

        timer = DysonSleepTimerNumber(coordinator)

        # Should not raise exception, should handle TypeError gracefully
        timer._start_timer_polling_if_needed()

        # No task should be created
        assert timer._timer_polling_task is None

    @pytest.mark.asyncio
    async def test_stop_timer_polling_task_done(self):
        """Test _stop_timer_polling when task is already done."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-TIMER-009"
        coordinator.device = Mock()

        timer = DysonSleepTimerNumber(coordinator)

        # Create a done task
        async def dummy_task():
            return True

        timer._timer_polling_task = asyncio.create_task(dummy_task())
        await asyncio.sleep(0.01)  # Let task complete

        # Stop should handle done task gracefully
        timer._stop_timer_polling()

        # Task should not be None since it was done (not cancelled)
        assert timer._timer_polling_task is not None


class TestOscillationAngleErrorCoverage:
    """Tests for oscillation angle number entity error paths."""

    @pytest.mark.asyncio
    async def test_lower_angle_set_native_value_timeout_error(self):
        """Test lower angle logs error on TimeoutError but doesn't raise."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-OSC-001"
        coordinator.device = Mock()
        coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=TimeoutError("Connection timeout")
        )
        coordinator.device.osal = 45
        coordinator.device.osau = 315
        coordinator.data = {"product-state": {"osal": "0045", "osau": "0315"}}

        entity = DysonOscillationLowerAngleNumber(coordinator)

        # Should not raise, but should log error
        await entity.async_set_native_value(90)

        # Verify the device method was called
        coordinator.device.set_oscillation_angles.assert_called_once()

    @pytest.mark.asyncio
    async def test_lower_angle_set_native_value_connection_error(self):
        """Test lower angle logs error on ConnectionError but doesn't raise."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-OSC-002"
        coordinator.device = Mock()
        coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ConnectionError("Device offline")
        )
        coordinator.device.osal = 45
        coordinator.device.osau = 315
        coordinator.data = {"product-state": {"osal": "0045", "osau": "0315"}}

        entity = DysonOscillationLowerAngleNumber(coordinator)

        # Should not raise, but should log error
        await entity.async_set_native_value(90)

        # Verify the device method was called
        coordinator.device.set_oscillation_angles.assert_called_once()

    @pytest.mark.asyncio
    async def test_upper_angle_set_native_value_timeout_error(self):
        """Test upper angle logs error on TimeoutError but doesn't raise."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-OSC-003"
        coordinator.device = Mock()
        coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=TimeoutError("Connection timeout")
        )
        coordinator.device.osal = 45
        coordinator.device.osau = 315
        coordinator.data = {"product-state": {"osal": "0045", "osau": "0315"}}

        entity = DysonOscillationUpperAngleNumber(coordinator)

        # Should not raise, but should log error
        await entity.async_set_native_value(270)

        # Verify the device method was called
        coordinator.device.set_oscillation_angles.assert_called_once()

    @pytest.mark.asyncio
    async def test_upper_angle_set_native_value_connection_error(self):
        """Test upper angle logs error on ConnectionError but doesn't raise."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-OSC-004"
        coordinator.device = Mock()
        coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ConnectionError("Device offline")
        )
        coordinator.device.osal = 45
        coordinator.device.osau = 315
        coordinator.data = {"product-state": {"osal": "0045", "osau": "0315"}}

        entity = DysonOscillationUpperAngleNumber(coordinator)

        # Should not raise, but should log error
        await entity.async_set_native_value(270)

        # Verify the device method was called
        coordinator.device.set_oscillation_angles.assert_called_once()

    @pytest.mark.asyncio
    async def test_center_angle_set_native_value_timeout_error(self):
        """Test center angle logs error on TimeoutError but doesn't raise."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-OSC-005"
        coordinator.device = Mock()
        coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=TimeoutError("Connection timeout")
        )
        coordinator.device.get_state_value = Mock(side_effect=["0045", "0315"])
        coordinator.data = {"product-state": {"osal": "0045", "osau": "0315"}}

        entity = DysonOscillationCenterAngleNumber(coordinator)

        await entity.async_set_native_value(180)

        coordinator.device.set_oscillation_angles.assert_called_once()

    @pytest.mark.asyncio
    async def test_center_angle_set_native_value_connection_error(self):
        """Test center angle logs error on ConnectionError but doesn't raise."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-OSC-006"
        coordinator.device = Mock()
        coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ConnectionError("Device offline")
        )
        coordinator.device.get_state_value = Mock(side_effect=["0045", "0315"])
        coordinator.data = {"product-state": {"osal": "0045", "osau": "0315"}}

        entity = DysonOscillationCenterAngleNumber(coordinator)

        await entity.async_set_native_value(180)

        coordinator.device.set_oscillation_angles.assert_called_once()

    def test_lower_angle_native_value_no_osal_attribute(self):
        """Test lower angle native_value when device has no osal attribute."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-OSC-007"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(return_value="invalid")
        coordinator.data = {"product-state": {}}

        entity = DysonOscillationLowerAngleNumber(coordinator)
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity.native_value == 0

    def test_upper_angle_native_value_no_osau_attribute(self):
        """Test upper angle native_value when device has no osau attribute."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-OSC-008"
        coordinator.device = Mock()
        coordinator.device.get_state_value = Mock(return_value="invalid")
        coordinator.data = {"product-state": {}}

        entity = DysonOscillationUpperAngleNumber(coordinator)
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity.native_value == 350

    def test_center_angle_native_value_calculation_edge_cases(self):
        """Test center angle calculation with various lower/upper combinations."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-OSC-009"
        coordinator.device = Mock()
        coordinator.data = {"product-state": {}}

        entity = DysonOscillationCenterAngleNumber(coordinator)

        # Test case 1: Normal case - symmetric range
        coordinator.device.osal = 90
        coordinator.device.osau = 270
        coordinator.device.get_state_value = Mock(side_effect=["0090", "0270"])
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity.native_value == 180

        # Test case 2: Another normal case
        coordinator.device.osal = 45
        coordinator.device.osau = 315
        coordinator.device.get_state_value = Mock(side_effect=["0045", "0315"])
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        # Center should be calculated correctly
        assert entity.native_value is not None

    def test_center_angle_native_value_no_attributes(self):
        """Test center angle when device has no osal/osau attributes."""
        coordinator = Mock(spec=DysonDataUpdateCoordinator)
        coordinator.serial_number = "TEST-OSC-010"
        coordinator.device = None  # No device

        entity = DysonOscillationCenterAngleNumber(coordinator)
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity.native_value is None
