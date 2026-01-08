"""Tests for Day0 oscillation number entities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.number import (
    DysonOscillationDay0AngleSpanNumber,
    DysonOscillationDay0CenterAngleNumber,
    DysonOscillationDay0LowerAngleNumber,
    DysonOscillationDay0UpperAngleNumber,
)


@pytest.fixture
def mock_day0_coordinator(pure_mock_hass):
    """Create a mock coordinator for Day0 oscillation tests."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-DAY0-123"
    coordinator.hass = pure_mock_hass  # Use proper pure_mock_hass fixture
    coordinator.device = MagicMock()
    coordinator.device.set_oscillation_angles_day0 = AsyncMock()
    coordinator.device.get_state_value = MagicMock()
    coordinator.data = {
        "product-state": {
            "osal": "0150",  # Lower angle: 150°
            "osau": "0200",  # Upper angle: 200°
        }
    }
    return coordinator


class TestDysonOscillationDay0LowerAngle:
    """Tests for Day0 lower angle number entity."""

    def test_init(self, mock_day0_coordinator):
        """Test Day0 lower angle number initialization."""
        entity = DysonOscillationDay0LowerAngleNumber(mock_day0_coordinator)
        assert entity._attr_unique_id == "TEST-DAY0-123_oscillation_low_angle"
        assert entity._attr_translation_key == "oscillation_low_angle"
        assert entity._attr_icon == "mdi:rotate-left"
        assert entity._attr_native_min_value == 142
        assert entity._attr_native_max_value == 212
        assert entity._attr_native_step == 5
        assert entity._attr_native_unit_of_measurement == "°"

    def test_handle_coordinator_update_valid_data(self, mock_day0_coordinator):
        """Test coordinator update with valid lower angle data."""
        mock_day0_coordinator.device.get_state_value.return_value = "0150"

        entity = DysonOscillationDay0LowerAngleNumber(mock_day0_coordinator)
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity._attr_native_value == 150

    def test_handle_coordinator_update_edge_cases(self, mock_day0_coordinator):
        """Test coordinator update with edge case values."""
        entity = DysonOscillationDay0LowerAngleNumber(mock_day0_coordinator)

        # Test minimum valid value
        mock_day0_coordinator.device.get_state_value.return_value = "0142"
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value == 142

        # Test maximum valid value
        mock_day0_coordinator.device.get_state_value.return_value = "0212"
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value == 212

        # Test value below minimum (constrained)
        mock_day0_coordinator.device.get_state_value.return_value = "0100"
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value == 142

        # Test value above maximum (constrained)
        mock_day0_coordinator.device.get_state_value.return_value = "0250"
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value == 212

    def test_handle_coordinator_update_invalid_data(self, mock_day0_coordinator):
        """Test coordinator update with invalid data."""
        entity = DysonOscillationDay0LowerAngleNumber(mock_day0_coordinator)

        # Test ValueError
        mock_day0_coordinator.device.get_state_value.return_value = "invalid"
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value == 142  # Default

        # Test empty string (should use default)
        mock_day0_coordinator.device.get_state_value.return_value = "0000"
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value == 142  # Default for empty after lstrip

    def test_handle_coordinator_update_no_device(self, mock_day0_coordinator):
        """Test coordinator update when device is None."""
        mock_day0_coordinator.device = None
        entity = DysonOscillationDay0LowerAngleNumber(mock_day0_coordinator)
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value is None

    @pytest.mark.asyncio
    async def test_set_native_value_success(self, mock_day0_coordinator):
        """Test setting Day0 lower angle successfully."""
        entity = DysonOscillationDay0LowerAngleNumber(mock_day0_coordinator)

        await entity.async_set_native_value(160.0)

        mock_day0_coordinator.device.set_oscillation_angles_day0.assert_called_once()
        call_args = mock_day0_coordinator.device.set_oscillation_angles_day0.call_args[
            0
        ]
        assert call_args[0] == 160  # Lower angle
        assert call_args[1] == 200  # Upper angle (from mock data)

    @pytest.mark.asyncio
    async def test_set_native_value_constrains_to_range(self, mock_day0_coordinator):
        """Test that lower angle is constrained to valid Day0 range."""
        entity = DysonOscillationDay0LowerAngleNumber(mock_day0_coordinator)

        # Test value below minimum
        await entity.async_set_native_value(100.0)
        call_args = mock_day0_coordinator.device.set_oscillation_angles_day0.call_args[
            0
        ]
        assert call_args[0] >= 142  # Should be constrained to minimum

        # Test value ensuring lower < upper
        mock_day0_coordinator.data["product-state"]["osau"] = "0180"
        await entity.async_set_native_value(178.0)
        call_args = mock_day0_coordinator.device.set_oscillation_angles_day0.call_args[
            0
        ]
        assert call_args[0] < call_args[1]  # Lower must be less than upper

    @pytest.mark.asyncio
    async def test_set_native_value_no_device(self, mock_day0_coordinator):
        """Test setting value when device is None."""
        mock_day0_coordinator.device = None
        entity = DysonOscillationDay0LowerAngleNumber(mock_day0_coordinator)

        await entity.async_set_native_value(160.0)
        # Should return early without error

    @pytest.mark.asyncio
    async def test_set_native_value_connection_error(self, mock_day0_coordinator):
        """Test ConnectionError handling when setting lower angle."""
        mock_day0_coordinator.device.set_oscillation_angles_day0.side_effect = (
            ConnectionError("Network error")
        )
        entity = DysonOscillationDay0LowerAngleNumber(mock_day0_coordinator)

        await entity.async_set_native_value(160.0)
        # Should handle error gracefully (logged, not raised)

    @pytest.mark.asyncio
    async def test_set_native_value_timeout_error(self, mock_day0_coordinator):
        """Test TimeoutError handling when setting lower angle."""
        mock_day0_coordinator.device.set_oscillation_angles_day0.side_effect = (
            TimeoutError("Request timeout")
        )
        entity = DysonOscillationDay0LowerAngleNumber(mock_day0_coordinator)

        await entity.async_set_native_value(160.0)
        # Should handle error gracefully (logged, not raised)

    @pytest.mark.asyncio
    async def test_set_native_value_key_error(self, mock_day0_coordinator):
        """Test KeyError handling when upper angle data is missing."""
        mock_day0_coordinator.data = {}  # No product-state data
        entity = DysonOscillationDay0LowerAngleNumber(mock_day0_coordinator)

        await entity.async_set_native_value(160.0)
        # Should handle error gracefully (logged, not raised)

    @pytest.mark.asyncio
    async def test_set_native_value_attribute_error(self, mock_day0_coordinator):
        """Test AttributeError handling when data structure is wrong."""
        mock_day0_coordinator.data = None
        entity = DysonOscillationDay0LowerAngleNumber(mock_day0_coordinator)

        await entity.async_set_native_value(160.0)
        # Should handle error gracefully (logged, not raised)

    @pytest.mark.asyncio
    async def test_set_native_value_value_error(self, mock_day0_coordinator):
        """Test ValueError handling when upper angle data is invalid."""
        mock_day0_coordinator.data["product-state"]["osau"] = "invalid"
        entity = DysonOscillationDay0LowerAngleNumber(mock_day0_coordinator)

        await entity.async_set_native_value(160.0)
        # Should handle error gracefully (logged, not raised)

    @pytest.mark.asyncio
    async def test_set_native_value_type_error(self, mock_day0_coordinator):
        """Test TypeError handling when data types are wrong."""
        mock_day0_coordinator.data["product-state"]["osau"] = None
        entity = DysonOscillationDay0LowerAngleNumber(mock_day0_coordinator)

        await entity.async_set_native_value(160.0)
        # Should handle error gracefully (logged, not raised)

    @pytest.mark.asyncio
    async def test_set_native_value_unexpected_error(self, mock_day0_coordinator):
        """Test unexpected exception handling."""
        mock_day0_coordinator.device.set_oscillation_angles_day0.side_effect = (
            RuntimeError("Unexpected error")
        )
        entity = DysonOscillationDay0LowerAngleNumber(mock_day0_coordinator)

        await entity.async_set_native_value(160.0)
        # Should handle error gracefully (logged, not raised)


class TestDysonOscillationDay0UpperAngle:
    """Tests for Day0 upper angle number entity."""

    def test_init(self, mock_day0_coordinator):
        """Test Day0 upper angle number initialization."""
        entity = DysonOscillationDay0UpperAngleNumber(mock_day0_coordinator)
        assert entity._attr_unique_id == "TEST-DAY0-123_oscillation_high_angle"
        assert entity._attr_translation_key == "oscillation_high_angle"
        assert entity._attr_icon == "mdi:rotate-right"
        assert entity._attr_native_min_value == 142
        assert entity._attr_native_max_value == 212
        assert entity._attr_native_step == 5
        assert entity._attr_native_unit_of_measurement == "°"

    def test_handle_coordinator_update_valid_data(self, mock_day0_coordinator):
        """Test coordinator update with valid upper angle data."""
        mock_day0_coordinator.device.get_state_value.return_value = "0200"

        entity = DysonOscillationDay0UpperAngleNumber(mock_day0_coordinator)
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity._attr_native_value == 200

    def test_handle_coordinator_update_edge_cases(self, mock_day0_coordinator):
        """Test coordinator update with edge case values."""
        entity = DysonOscillationDay0UpperAngleNumber(mock_day0_coordinator)

        # Test minimum valid value
        mock_day0_coordinator.device.get_state_value.return_value = "0142"
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value == 142

        # Test maximum valid value
        mock_day0_coordinator.device.get_state_value.return_value = "0212"
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value == 212

        # Test value below minimum (constrained)
        mock_day0_coordinator.device.get_state_value.return_value = "0100"
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value == 142

        # Test value above maximum (constrained)
        mock_day0_coordinator.device.get_state_value.return_value = "0300"
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value == 212

    def test_handle_coordinator_update_invalid_data(self, mock_day0_coordinator):
        """Test coordinator update with invalid data."""
        entity = DysonOscillationDay0UpperAngleNumber(mock_day0_coordinator)

        # Test ValueError
        mock_day0_coordinator.device.get_state_value.return_value = "invalid"
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value == 212  # Default

        # Test empty string (should use default)
        mock_day0_coordinator.device.get_state_value.return_value = "0000"
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value == 212  # Default for empty after lstrip

    def test_handle_coordinator_update_no_device(self, mock_day0_coordinator):
        """Test coordinator update when device is None."""
        mock_day0_coordinator.device = None
        entity = DysonOscillationDay0UpperAngleNumber(mock_day0_coordinator)
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value is None

    @pytest.mark.asyncio
    async def test_set_native_value_success(self, mock_day0_coordinator):
        """Test setting Day0 upper angle successfully."""
        entity = DysonOscillationDay0UpperAngleNumber(mock_day0_coordinator)

        await entity.async_set_native_value(190.0)

        mock_day0_coordinator.device.set_oscillation_angles_day0.assert_called_once()
        call_args = mock_day0_coordinator.device.set_oscillation_angles_day0.call_args[
            0
        ]
        assert call_args[0] == 150  # Lower angle (from mock data)
        assert call_args[1] == 190  # Upper angle

    @pytest.mark.asyncio
    async def test_set_native_value_constrains_to_range(self, mock_day0_coordinator):
        """Test that upper angle is constrained to valid Day0 range."""
        entity = DysonOscillationDay0UpperAngleNumber(mock_day0_coordinator)

        # Test value above maximum
        await entity.async_set_native_value(250.0)
        call_args = mock_day0_coordinator.device.set_oscillation_angles_day0.call_args[
            0
        ]
        assert call_args[1] <= 212  # Should be constrained to maximum

        # Test value ensuring upper > lower
        mock_day0_coordinator.data["product-state"]["osal"] = "0175"
        await entity.async_set_native_value(178.0)
        call_args = mock_day0_coordinator.device.set_oscillation_angles_day0.call_args[
            0
        ]
        assert call_args[1] > call_args[0]  # Upper must be greater than lower

    @pytest.mark.asyncio
    async def test_set_native_value_all_errors(self, mock_day0_coordinator):
        """Test all error conditions for upper angle."""
        entity = DysonOscillationDay0UpperAngleNumber(mock_day0_coordinator)

        # No device
        mock_day0_coordinator.device = None
        await entity.async_set_native_value(190.0)
        mock_day0_coordinator.device = MagicMock()
        mock_day0_coordinator.device.set_oscillation_angles_day0 = AsyncMock()

        # ConnectionError
        mock_day0_coordinator.device.set_oscillation_angles_day0.side_effect = (
            ConnectionError()
        )
        await entity.async_set_native_value(190.0)

        # TimeoutError
        mock_day0_coordinator.device.set_oscillation_angles_day0.side_effect = (
            TimeoutError()
        )
        await entity.async_set_native_value(190.0)

        # KeyError (missing data)
        mock_day0_coordinator.device.set_oscillation_angles_day0.side_effect = None
        mock_day0_coordinator.data = {}
        await entity.async_set_native_value(190.0)

        # ValueError (invalid data)
        mock_day0_coordinator.data = {"product-state": {"osal": "invalid"}}
        await entity.async_set_native_value(190.0)

        # Exception
        mock_day0_coordinator.device.set_oscillation_angles_day0.side_effect = (
            RuntimeError()
        )
        await entity.async_set_native_value(190.0)


class TestDysonOscillationDay0AngleSpan:
    """Tests for Day0 angle span number entity."""

    def test_init(self, mock_day0_coordinator):
        """Test Day0 angle span number initialization."""
        entity = DysonOscillationDay0AngleSpanNumber(mock_day0_coordinator)
        assert entity._attr_unique_id == "TEST-DAY0-123_oscillation_angle"
        assert entity._attr_translation_key == "oscillation_angle_span"
        assert entity._attr_icon == "mdi:angle-acute"
        assert entity._attr_native_min_value == 10
        assert entity._attr_native_max_value == 70
        assert entity._attr_native_step == 5
        assert entity._attr_native_unit_of_measurement == "°"

    def test_handle_coordinator_update_calculates_span(self, mock_day0_coordinator):
        """Test coordinator update calculates span from lower and upper angles."""
        mock_day0_coordinator.device.get_state_value.side_effect = ["0150", "0200"]

        entity = DysonOscillationDay0AngleSpanNumber(mock_day0_coordinator)
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity._attr_native_value == 50  # 200 - 150

    def test_handle_coordinator_update_invalid_data(self, mock_day0_coordinator):
        """Test coordinator update with invalid angle data."""
        mock_day0_coordinator.device.get_state_value.side_effect = [
            "invalid",
            "invalid",
        ]

        entity = DysonOscillationDay0AngleSpanNumber(mock_day0_coordinator)
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity._attr_native_value == 70  # Default for Day0

    def test_handle_coordinator_update_no_device(self, mock_day0_coordinator):
        """Test coordinator update when device is None."""
        mock_day0_coordinator.device = None
        entity = DysonOscillationDay0AngleSpanNumber(mock_day0_coordinator)
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value is None

    @pytest.mark.asyncio
    async def test_set_native_value_calculates_angles_from_span(
        self, mock_day0_coordinator
    ):
        """Test setting span calculates lower and upper angles around center 177°."""
        entity = DysonOscillationDay0AngleSpanNumber(mock_day0_coordinator)

        # Set span of 50° centered at 177°
        await entity.async_set_native_value(50.0)

        mock_day0_coordinator.device.set_oscillation_angles_day0.assert_called_once()
        call_args = mock_day0_coordinator.device.set_oscillation_angles_day0.call_args[
            0
        ]
        lower = call_args[0]
        upper = call_args[1]

        # Should be approximately centered at 177° with 50° span
        assert upper - lower == 50
        assert lower >= 0 and upper <= 350

    @pytest.mark.asyncio
    async def test_set_native_value_constrains_to_bounds(self, mock_day0_coordinator):
        """Test that angles are constrained when span would exceed bounds."""
        entity = DysonOscillationDay0AngleSpanNumber(mock_day0_coordinator)

        # Large span that would exceed 350°
        await entity.async_set_native_value(70.0)

        call_args = mock_day0_coordinator.device.set_oscillation_angles_day0.call_args[
            0
        ]
        assert call_args[0] >= 0  # Lower bound
        assert call_args[1] <= 350  # Upper bound

    @pytest.mark.asyncio
    async def test_set_native_value_no_device(self, mock_day0_coordinator):
        """Test setting span when device is None."""
        mock_day0_coordinator.device = None
        entity = DysonOscillationDay0AngleSpanNumber(mock_day0_coordinator)

        await entity.async_set_native_value(50.0)
        # Should return early without error

    @pytest.mark.asyncio
    async def test_set_native_value_all_errors(self, mock_day0_coordinator):
        """Test all error conditions for angle span."""
        entity = DysonOscillationDay0AngleSpanNumber(mock_day0_coordinator)

        # ConnectionError
        mock_day0_coordinator.device.set_oscillation_angles_day0.side_effect = (
            ConnectionError()
        )
        await entity.async_set_native_value(50.0)

        # TimeoutError
        mock_day0_coordinator.device.set_oscillation_angles_day0.side_effect = (
            TimeoutError()
        )
        await entity.async_set_native_value(50.0)

        # KeyError
        mock_day0_coordinator.device.set_oscillation_angles_day0.side_effect = None
        mock_day0_coordinator.data = {}
        await entity.async_set_native_value(50.0)

        # ValueError
        mock_day0_coordinator.data = {"product-state": {"osal": "invalid"}}
        await entity.async_set_native_value(50.0)

        # Exception
        mock_day0_coordinator.device.set_oscillation_angles_day0.side_effect = (
            RuntimeError()
        )
        await entity.async_set_native_value(50.0)


class TestDysonOscillationDay0CenterAngle:
    """Tests for Day0 center angle number entity."""

    def test_init(self, mock_day0_coordinator):
        """Test Day0 center angle number initialization."""
        entity = DysonOscillationDay0CenterAngleNumber(mock_day0_coordinator)
        assert entity._attr_unique_id == "TEST-DAY0-123_oscillation_center_angle"
        assert entity._attr_translation_key == "oscillation_center_angle"
        assert entity._attr_icon == "mdi:crosshairs"
        assert entity._attr_native_min_value == 147
        assert entity._attr_native_max_value == 207
        assert entity._attr_native_step == 1
        assert entity._attr_native_unit_of_measurement == "°"

    def test_handle_coordinator_update_calculates_center(self, mock_day0_coordinator):
        """Test coordinator update calculates center from lower and upper angles."""
        mock_day0_coordinator.device.get_state_value.side_effect = ["0150", "0200"]

        entity = DysonOscillationDay0CenterAngleNumber(mock_day0_coordinator)
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity._attr_native_value == 175  # (150 + 200) // 2

    def test_handle_coordinator_update_constrains_center(self, mock_day0_coordinator):
        """Test that calculated center is constrained to valid range."""
        entity = DysonOscillationDay0CenterAngleNumber(mock_day0_coordinator)

        # Test center below minimum
        mock_day0_coordinator.device.get_state_value.side_effect = ["0100", "0120"]
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value >= 147  # Constrained to minimum

        # Test center above maximum
        mock_day0_coordinator.device.get_state_value.side_effect = ["0300", "0350"]
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value <= 207  # Constrained to maximum

    def test_handle_coordinator_update_invalid_data(self, mock_day0_coordinator):
        """Test coordinator update with invalid angle data."""
        mock_day0_coordinator.device.get_state_value.side_effect = [
            "invalid",
            "invalid",
        ]

        entity = DysonOscillationDay0CenterAngleNumber(mock_day0_coordinator)
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity._attr_native_value == 177  # Default Day0 center

    def test_handle_coordinator_update_no_device(self, mock_day0_coordinator):
        """Test coordinator update when device is None."""
        mock_day0_coordinator.device = None
        entity = DysonOscillationDay0CenterAngleNumber(mock_day0_coordinator)
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()
        assert entity._attr_native_value is None

    @pytest.mark.asyncio
    async def test_set_native_value_maintains_span(self, mock_day0_coordinator):
        """Test setting center maintains current span."""
        # Current state: lower=150, upper=200, span=50
        mock_day0_coordinator.device.get_state_value.side_effect = ["0150", "0200"]

        entity = DysonOscillationDay0CenterAngleNumber(mock_day0_coordinator)

        # Move center to 180°
        await entity.async_set_native_value(180.0)

        mock_day0_coordinator.device.set_oscillation_angles_day0.assert_called_once()
        call_args = mock_day0_coordinator.device.set_oscillation_angles_day0.call_args[
            0
        ]
        lower = call_args[0]
        upper = call_args[1]

        # Span should remain ~50° (with center at 180°)
        span = upper - lower
        assert abs(span - 50) <= 2  # Allow small rounding difference
        center = (lower + upper) // 2
        assert abs(center - 180) <= 1  # Center should be ~180°

    @pytest.mark.asyncio
    async def test_set_native_value_constrains_to_day0_bounds(
        self, mock_day0_coordinator
    ):
        """Test that angles are adjusted to stay within Day0 bounds (142°-212°)."""
        # Current span: 50°
        mock_day0_coordinator.device.get_state_value.side_effect = ["0150", "0200"]

        entity = DysonOscillationDay0CenterAngleNumber(mock_day0_coordinator)

        # Try to set center that would push lower below 142°
        await entity.async_set_native_value(150.0)

        call_args = mock_day0_coordinator.device.set_oscillation_angles_day0.call_args[
            0
        ]
        assert call_args[0] >= 142  # Lower must be >= 142
        assert call_args[1] <= 212  # Upper must be <= 212

    @pytest.mark.asyncio
    async def test_set_native_value_adjusts_when_lower_below_bound(
        self, mock_day0_coordinator
    ):
        """Test adjustment when calculated lower angle would be below 142°."""
        # Current span: 50°
        mock_day0_coordinator.device.get_state_value.side_effect = ["0150", "0200"]

        entity = DysonOscillationDay0CenterAngleNumber(mock_day0_coordinator)

        # Set center that would put lower at 147-25=122 (below 142)
        await entity.async_set_native_value(147.0)

        call_args = mock_day0_coordinator.device.set_oscillation_angles_day0.call_args[
            0
        ]
        lower = call_args[0]
        upper = call_args[1]

        assert lower == 142  # Should be constrained to 142
        assert upper <= 212  # Upper should be adjusted accordingly

    @pytest.mark.asyncio
    async def test_set_native_value_adjusts_when_upper_above_bound(
        self, mock_day0_coordinator
    ):
        """Test adjustment when calculated upper angle would be above 212°."""
        # Current span: 50°
        mock_day0_coordinator.device.get_state_value.side_effect = ["0150", "0200"]

        entity = DysonOscillationDay0CenterAngleNumber(mock_day0_coordinator)

        # Set center that would put upper at 207+25=232 (above 212)
        await entity.async_set_native_value(207.0)

        call_args = mock_day0_coordinator.device.set_oscillation_angles_day0.call_args[
            0
        ]
        lower = call_args[0]
        upper = call_args[1]

        assert upper == 212  # Should be constrained to 212
        assert lower >= 142  # Lower should be adjusted accordingly

    @pytest.mark.asyncio
    async def test_set_native_value_no_device(self, mock_day0_coordinator):
        """Test setting center when device is None."""
        mock_day0_coordinator.device = None
        entity = DysonOscillationDay0CenterAngleNumber(mock_day0_coordinator)

        await entity.async_set_native_value(177.0)
        # Should return early without error

    @pytest.mark.asyncio
    async def test_set_native_value_all_errors(self, mock_day0_coordinator):
        """Test all error conditions for center angle."""
        mock_day0_coordinator.device.get_state_value.side_effect = ["0150", "0200"]
        entity = DysonOscillationDay0CenterAngleNumber(mock_day0_coordinator)

        # ConnectionError
        mock_day0_coordinator.device.set_oscillation_angles_day0.side_effect = (
            ConnectionError()
        )
        await entity.async_set_native_value(177.0)

        # TimeoutError
        mock_day0_coordinator.device.set_oscillation_angles_day0.side_effect = (
            TimeoutError()
        )
        await entity.async_set_native_value(177.0)

        # KeyError
        mock_day0_coordinator.device.set_oscillation_angles_day0.side_effect = None
        mock_day0_coordinator.device.get_state_value.side_effect = KeyError()
        await entity.async_set_native_value(177.0)

        # ValueError
        mock_day0_coordinator.device.get_state_value.side_effect = [
            "invalid",
            "invalid",
        ]
        await entity.async_set_native_value(177.0)

        # Exception
        mock_day0_coordinator.device.set_oscillation_angles_day0.side_effect = (
            RuntimeError()
        )
        await entity.async_set_native_value(177.0)
