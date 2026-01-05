"""Test suite for Dyson robot power select entities.

This module provides comprehensive testing for robot vacuum power level
select entities that use the centralized device.set_robot_power() method
instead of direct MQTT commands.

Test Coverage:
- Robot power select entities for all models (360 Eye, Heurist, Vis Nav, Generic)
- Option mapping for each robot type
- Device method invocation with correct parameters
- Error handling for invalid options
- Entity state management and attributes

The tests ensure proper encapsulation of robot power control through
device methods rather than scattered MQTT commands.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.hass_dyson.select import (
    DysonRobotPower360EyeSelect,
    DysonRobotPowerGenericSelect,
    DysonRobotPowerHeuristSelect,
    DysonRobotPowerVisNavSelect,
)


class TestDysonRobotPowerSelects:
    """Test robot power select entities."""

    @pytest.fixture
    def mock_robot_coordinator(self):
        """Create a mock coordinator for robot vacuum devices."""
        coordinator = Mock()
        coordinator.serial_number = "360EY-ABC-123456"
        coordinator.device_name = "Test Robot"
        coordinator.device = Mock()
        coordinator.device_capabilities = ["RobotVacuum"]
        coordinator.device.get_state_value = Mock()
        coordinator.device.set_robot_power = AsyncMock()
        coordinator.device._state_data = {
            "product-state": {
                "fPwr": "halfPower",  # Default for 360 Eye
            }
        }
        coordinator.data = coordinator.device._state_data
        return coordinator

    @pytest.mark.asyncio
    async def test_robot_power_360eye_full_power(self, mock_robot_coordinator):
        """Test 360 Eye robot selecting full power."""
        entity = DysonRobotPower360EyeSelect(mock_robot_coordinator)
        entity.async_write_ha_state = Mock()

        await entity.async_select_option("Deep Clean (Full Power)")

        mock_robot_coordinator.device.set_robot_power.assert_called_once_with(
            "fullPower", "360eye"
        )
        assert entity._attr_current_option == "Deep Clean (Full Power)"

    @pytest.mark.asyncio
    async def test_robot_power_360eye_half_power(self, mock_robot_coordinator):
        """Test 360 Eye robot selecting half power."""
        entity = DysonRobotPower360EyeSelect(mock_robot_coordinator)
        entity.async_write_ha_state = Mock()

        await entity.async_select_option("Quiet (Half Power)")

        mock_robot_coordinator.device.set_robot_power.assert_called_once_with(
            "halfPower", "360eye"
        )
        assert entity._attr_current_option == "Quiet (Half Power)"

    @pytest.mark.asyncio
    async def test_robot_power_heurist_quiet(self, mock_robot_coordinator):
        """Test Heurist robot selecting quiet power."""
        # Update mock data for Heurist
        mock_robot_coordinator.data["product-state"]["fPwr"] = 1

        entity = DysonRobotPowerHeuristSelect(mock_robot_coordinator)
        entity.async_write_ha_state = Mock()

        await entity.async_select_option("Quiet Mode")

        mock_robot_coordinator.device.set_robot_power.assert_called_once_with(
            "1", "heurist"
        )
        assert entity._attr_current_option == "Quiet Mode"

    @pytest.mark.asyncio
    async def test_robot_power_heurist_high(self, mock_robot_coordinator):
        """Test Heurist robot selecting high power."""
        entity = DysonRobotPowerHeuristSelect(mock_robot_coordinator)
        entity.async_write_ha_state = Mock()

        await entity.async_select_option("High Mode")

        mock_robot_coordinator.device.set_robot_power.assert_called_once_with(
            "2", "heurist"
        )
        assert entity._attr_current_option == "High Mode"

    @pytest.mark.asyncio
    async def test_robot_power_vis_nav_quiet(self, mock_robot_coordinator):
        """Test Vis Nav robot selecting quiet power."""
        # Update mock data for Vis Nav
        mock_robot_coordinator.data["product-state"]["fPwr"] = 3

        entity = DysonRobotPowerVisNavSelect(mock_robot_coordinator)
        entity.async_write_ha_state = Mock()

        await entity.async_select_option("Quiet Mode")

        mock_robot_coordinator.device.set_robot_power.assert_called_once_with(
            "3", "vis_nav"
        )
        assert entity._attr_current_option == "Quiet Mode"

    @pytest.mark.asyncio
    async def test_robot_power_vis_nav_boost(self, mock_robot_coordinator):
        """Test Vis Nav robot selecting boost power."""
        entity = DysonRobotPowerVisNavSelect(mock_robot_coordinator)
        entity.async_write_ha_state = Mock()

        await entity.async_select_option("Boost Mode")

        mock_robot_coordinator.device.set_robot_power.assert_called_once_with(
            "4", "vis_nav"
        )
        assert entity._attr_current_option == "Boost Mode"

    @pytest.mark.asyncio
    async def test_robot_power_generic_quiet(self, mock_robot_coordinator):
        """Test generic robot selecting quiet power."""
        # Update mock data for generic
        mock_robot_coordinator.data["product-state"]["fPwr"] = 1

        entity = DysonRobotPowerGenericSelect(mock_robot_coordinator)
        entity.async_write_ha_state = Mock()

        await entity.async_select_option("Quiet Mode")

        mock_robot_coordinator.device.set_robot_power.assert_called_once_with(
            "1", "generic"
        )
        assert entity._attr_current_option == "Quiet Mode"

    @pytest.mark.asyncio
    async def test_robot_power_generic_high(self, mock_robot_coordinator):
        """Test generic robot selecting high power."""
        entity = DysonRobotPowerGenericSelect(mock_robot_coordinator)
        entity.async_write_ha_state = Mock()

        await entity.async_select_option("High Mode")

        mock_robot_coordinator.device.set_robot_power.assert_called_once_with(
            "2", "generic"
        )
        assert entity._attr_current_option == "High Mode"

    @pytest.mark.asyncio
    async def test_robot_power_360eye_invalid_option(self, mock_robot_coordinator):
        """Test 360 Eye robot with invalid option."""
        entity = DysonRobotPower360EyeSelect(mock_robot_coordinator)

        with patch("custom_components.hass_dyson.select._LOGGER") as mock_logger:
            await entity.async_select_option("Invalid")

        mock_robot_coordinator.device.set_robot_power.assert_not_called()
        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_robot_power_heurist_invalid_option(self, mock_robot_coordinator):
        """Test Heurist robot with invalid option."""
        entity = DysonRobotPowerHeuristSelect(mock_robot_coordinator)

        with patch("custom_components.hass_dyson.select._LOGGER") as mock_logger:
            await entity.async_select_option("Invalid")

        mock_robot_coordinator.device.set_robot_power.assert_not_called()
        mock_logger.error.assert_called_once()

    def test_robot_power_360eye_state_mapping(self, mock_robot_coordinator):
        """Test 360 Eye robot state mapping."""
        # Test fullPower -> Deep Clean (Full Power)
        mock_robot_coordinator.device._state_data = {
            "product-state": {"fPwr": "fullPower"}
        }
        entity = DysonRobotPower360EyeSelect(mock_robot_coordinator)
        entity.async_write_ha_state = Mock()
        entity._handle_coordinator_update()
        assert entity._attr_current_option == "Deep Clean (Full Power)"

        # Test halfPower -> Quiet (Half Power)
        mock_robot_coordinator.device._state_data = {
            "product-state": {"fPwr": "halfPower"}
        }
        entity = DysonRobotPower360EyeSelect(mock_robot_coordinator)
        entity.async_write_ha_state = Mock()
        entity._handle_coordinator_update()
        assert entity._attr_current_option == "Quiet (Half Power)"

    def test_robot_power_heurist_state_mapping(self, mock_robot_coordinator):
        """Test Heurist robot state mapping."""
        # Test integer state mapping
        test_cases = [
            (1, "Quiet Mode"),
            (2, "High Mode"),
        ]

        for state_value, expected_option in test_cases:
            mock_robot_coordinator.device._state_data = {
                "product-state": {"fPwr": state_value}
            }
            entity = DysonRobotPowerHeuristSelect(mock_robot_coordinator)
            entity.async_write_ha_state = Mock()
            entity._handle_coordinator_update()
            assert entity._attr_current_option == expected_option

    def test_robot_power_vis_nav_state_mapping(self, mock_robot_coordinator):
        """Test Vis Nav robot state mapping."""
        # Test integer state mapping
        test_cases = [
            (1, "Auto Mode"),
            (2, "Quick Mode"),
            (3, "Quiet Mode"),
            (4, "Boost Mode"),
        ]

        for state_value, expected_option in test_cases:
            mock_robot_coordinator.device._state_data = {
                "product-state": {"fPwr": state_value}
            }
            entity = DysonRobotPowerVisNavSelect(mock_robot_coordinator)
            entity.async_write_ha_state = Mock()
            entity._handle_coordinator_update()
            assert entity._attr_current_option == expected_option

    def test_robot_power_generic_state_mapping(self, mock_robot_coordinator):
        """Test generic robot state mapping."""
        # Test integer state mapping
        test_cases = [
            (1, "Quiet Mode"),
            (2, "High Mode"),
        ]

        for state_value, expected_option in test_cases:
            mock_robot_coordinator.device._state_data = {
                "product-state": {"fPwr": state_value}
            }
            entity = DysonRobotPowerGenericSelect(mock_robot_coordinator)
            entity.async_write_ha_state = Mock()
            entity._handle_coordinator_update()
            assert entity._attr_current_option == expected_option

    @pytest.mark.asyncio
    async def test_robot_power_exception_handling(self, mock_robot_coordinator):
        """Test robot power exception handling."""
        mock_robot_coordinator.device.set_robot_power.side_effect = ConnectionError(
            "Connection failed"
        )

        entity = DysonRobotPower360EyeSelect(mock_robot_coordinator)

        with patch("custom_components.hass_dyson.select._LOGGER") as mock_logger:
            await entity.async_select_option("Deep Clean (Full Power)")

        mock_logger.error.assert_called_once()

    def test_robot_power_unknown_state_fallback(self, mock_robot_coordinator):
        """Test robot power unknown state fallback."""
        # Test unknown state handling - should use first option as fallback
        mock_robot_coordinator.device._state_data = {
            "product-state": {"fPwr": "unknown"}
        }

        entity = DysonRobotPower360EyeSelect(mock_robot_coordinator)
        entity.async_write_ha_state = Mock()
        entity._handle_coordinator_update()
        # Should use first option as fallback when unknown state
        assert (
            entity._attr_current_option == "Quiet (Half Power)"
        )  # First option in 360 Eye list

    def test_robot_power_entity_properties(self, mock_robot_coordinator):
        """Test robot power entity properties."""
        entity = DysonRobotPower360EyeSelect(mock_robot_coordinator)

        assert entity.name == "Power Level"
        assert entity.unique_id == "360EY-ABC-123456_robot_power_360_eye"
        assert entity.icon == "mdi:vacuum"
        assert entity.entity_category is None
        assert len(entity.options) > 0

    def test_all_robot_power_entities_have_options(self, mock_robot_coordinator):
        """Test that all robot power entities have options defined."""
        robot_classes = [
            DysonRobotPower360EyeSelect,
            DysonRobotPowerHeuristSelect,
            DysonRobotPowerVisNavSelect,
            DysonRobotPowerGenericSelect,
        ]

        for robot_class in robot_classes:
            entity = robot_class(mock_robot_coordinator)
            assert hasattr(entity, "options")
            assert len(entity.options) > 0
            assert all(isinstance(option, str) for option in entity.options)
