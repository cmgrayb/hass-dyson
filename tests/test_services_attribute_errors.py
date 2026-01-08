"""Tests for services.py AttributeError exception handling paths.

Targets uncovered AttributeError handlers in service functions to reach 75% overall coverage.
Expected impact: +1% overall coverage improvement (74% -> 75%).
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.hass_dyson.const import DOMAIN
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator


class TestSleepTimerAttributeErrors:
    """Tests for AttributeError handling in sleep timer services."""

    @pytest.mark.asyncio
    async def test_set_sleep_timer_attribute_error(self, mock_hass):
        """Test _handle_set_sleep_timer raises HomeAssistantError on AttributeError."""
        # Setup mock coordinator
        mock_coordinator = Mock(spec=DysonDataUpdateCoordinator)
        mock_coordinator.serial_number = "TEST-123"
        mock_coordinator.device = Mock()
        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=AttributeError("set_sleep_timer method not available")
        )

        # Setup hass with coordinator
        mock_hass.data[DOMAIN] = {"config_entry_id": mock_coordinator}

        # Mock device registry to return device entry
        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            AsyncMock(return_value=mock_coordinator),
        ):
            # Import after patching
            from custom_components.hass_dyson.services import _handle_set_sleep_timer

            # Create service call
            call = Mock()
            call.data = {"device_id": "test_device", "minutes": 30}

            # Should raise HomeAssistantError wrapping AttributeError
            with pytest.raises(HomeAssistantError, match="Sleep timer not supported"):
                await _handle_set_sleep_timer(mock_hass, call)

    @pytest.mark.asyncio
    async def test_cancel_sleep_timer_attribute_error(self, mock_hass):
        """Test _handle_cancel_sleep_timer raises HomeAssistantError on AttributeError."""
        # Setup mock coordinator
        mock_coordinator = Mock(spec=DysonDataUpdateCoordinator)
        mock_coordinator.serial_number = "TEST-123"
        mock_coordinator.device = Mock()
        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=AttributeError("set_sleep_timer method not available")
        )

        # Setup hass with coordinator
        mock_hass.data[DOMAIN] = {"config_entry_id": mock_coordinator}

        # Mock device registry
        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            AsyncMock(return_value=mock_coordinator),
        ):
            # Import after patching
            from custom_components.hass_dyson.services import _handle_cancel_sleep_timer

            # Create service call
            call = Mock()
            call.data = {"device_id": "test_device"}

            # Should raise HomeAssistantError wrapping AttributeError
            with pytest.raises(HomeAssistantError, match="Sleep timer not supported"):
                await _handle_cancel_sleep_timer(mock_hass, call)


class TestOscillationAnglesAttributeErrors:
    """Tests for AttributeError handling in oscillation angles service."""

    @pytest.mark.asyncio
    async def test_set_oscillation_angles_attribute_error(self, mock_hass):
        """Test _handle_set_oscillation_angles raises HomeAssistantError on AttributeError."""
        # Setup mock coordinator
        mock_coordinator = Mock(spec=DysonDataUpdateCoordinator)
        mock_coordinator.serial_number = "TEST-123"
        mock_coordinator.device = Mock()
        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=AttributeError("set_oscillation_angles method not available")
        )

        # Setup hass with coordinator
        mock_hass.data[DOMAIN] = {"config_entry_id": mock_coordinator}

        # Mock device registry
        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            AsyncMock(return_value=mock_coordinator),
        ):
            # Import after patching
            from custom_components.hass_dyson.services import (
                _handle_set_oscillation_angles,
            )

            # Create service call
            call = Mock()
            call.data = {
                "device_id": "test_device",
                "lower_angle": 45,
                "upper_angle": 315,
            }

            # Should raise HomeAssistantError wrapping AttributeError
            with pytest.raises(
                HomeAssistantError, match="Oscillation angles not supported"
            ):
                await _handle_set_oscillation_angles(mock_hass, call)


class TestResetFilterAttributeErrors:
    """Tests for AttributeError handling in reset filter service."""

    @pytest.mark.asyncio
    async def test_reset_filter_hepa_attribute_error(self, mock_hass):
        """Test _handle_reset_filter HEPA raises HomeAssistantError on AttributeError."""
        # Setup mock coordinator
        mock_coordinator = Mock(spec=DysonDataUpdateCoordinator)
        mock_coordinator.serial_number = "TEST-123"
        mock_coordinator.device = Mock()
        mock_coordinator.device.reset_hepa_filter_life = AsyncMock(
            side_effect=AttributeError("reset_hepa_filter_life method not available")
        )

        # Setup hass with coordinator
        mock_hass.data[DOMAIN] = {"config_entry_id": mock_coordinator}

        # Mock device registry
        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            AsyncMock(return_value=mock_coordinator),
        ):
            # Import after patching
            from custom_components.hass_dyson.services import _handle_reset_filter

            # Create service call
            call = Mock()
            call.data = {"device_id": "test_device", "filter_type": "hepa"}

            # Should raise HomeAssistantError wrapping AttributeError
            with pytest.raises(HomeAssistantError, match="filter reset not supported"):
                await _handle_reset_filter(mock_hass, call)

    @pytest.mark.asyncio
    async def test_reset_filter_carbon_attribute_error(self, mock_hass):
        """Test _handle_reset_filter carbon raises HomeAssistantError on AttributeError."""
        # Setup mock coordinator
        mock_coordinator = Mock(spec=DysonDataUpdateCoordinator)
        mock_coordinator.serial_number = "TEST-123"
        mock_coordinator.device = Mock()
        mock_coordinator.device.reset_carbon_filter_life = AsyncMock(
            side_effect=AttributeError("reset_carbon_filter_life method not available")
        )

        # Setup hass with coordinator
        mock_hass.data[DOMAIN] = {"config_entry_id": mock_coordinator}

        # Mock device registry
        with patch(
            "custom_components.hass_dyson.services._get_coordinator_from_device_id",
            AsyncMock(return_value=mock_coordinator),
        ):
            # Import after patching
            from custom_components.hass_dyson.services import _handle_reset_filter

            # Create service call
            call = Mock()
            call.data = {"device_id": "test_device", "filter_type": "carbon"}

            # Should raise HomeAssistantError wrapping AttributeError
            with pytest.raises(HomeAssistantError, match="filter reset not supported"):
                await _handle_reset_filter(mock_hass, call)
