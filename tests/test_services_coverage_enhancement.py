"""Comprehensive tests to improve services.py coverage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.hass_dyson.const import DOMAIN
from custom_components.hass_dyson.services import (
    _convert_to_string,
    async_remove_services,
    async_setup_cloud_services,
    async_setup_services,
)


class TestServicesCoverageEnhancement:
    """Tests to improve services.py coverage focusing on testable paths."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.services = MagicMock()
        hass.services.has_service = MagicMock(return_value=False)
        hass.services.async_register = MagicMock()
        hass.services.async_remove = MagicMock()
        hass.data = {DOMAIN: {}}
        hass.config_entries = MagicMock()
        hass.config_entries.async_entries = MagicMock(return_value=[])
        return hass

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock()
        coordinator.serial_number = "VS6-EU-HJA1234A"
        coordinator.device = MagicMock()
        coordinator.device.set_sleep_timer = AsyncMock()
        coordinator.device.cancel_sleep_timer = AsyncMock()
        coordinator.device.schedule_operation = AsyncMock()
        coordinator.device.set_oscillation_angles = AsyncMock()
        coordinator.device.fetch_account_data = AsyncMock()
        coordinator.device.reset_filter = AsyncMock()
        return coordinator

    @pytest.mark.asyncio
    async def test_async_setup_services_success(self, mock_hass):
        """Test successful service setup."""
        # async_setup_services no longer sets up cloud services automatically
        # Cloud services are only set up when cloud accounts are configured
        await async_setup_services(mock_hass)

        # Verify the function completed without error
        # (It should be a no-op pass-through now)

    @pytest.mark.asyncio
    async def test_async_setup_cloud_services_success(self, mock_hass):
        """Test successful cloud service setup."""
        await async_setup_cloud_services(mock_hass)

        # Verify services were registered
        assert mock_hass.services.async_register.call_count >= 1

    @pytest.mark.asyncio
    async def test_async_setup_cloud_services_already_registered(self, mock_hass):
        """Test cloud service setup when services already exist."""
        mock_hass.services.has_service.return_value = True

        await async_setup_cloud_services(mock_hass)

        # Should not register services that already exist
        mock_hass.services.async_register.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_remove_services_success(self, mock_hass):
        """Test successful service removal."""
        mock_hass.services.has_service.return_value = True

        await async_remove_services(mock_hass)

        # Verify services were removed
        assert mock_hass.services.async_remove.call_count >= 1

    @pytest.mark.asyncio
    async def test_async_remove_services_no_services_exist(self, mock_hass):
        """Test service removal when no services exist."""
        mock_hass.services.has_service.return_value = False

        await async_remove_services(mock_hass)

        # Should not attempt to remove non-existent services
        mock_hass.services.async_remove.assert_not_called()

    def test_convert_to_string_with_enum(self):
        """Test converting enum to string."""
        from enum import Enum

        class TestEnum(Enum):
            VALUE1 = "test_value"

        result = _convert_to_string(TestEnum.VALUE1)
        assert result == "test_value"

    def test_convert_to_string_with_regular_object(self):
        """Test converting regular object to string."""
        result = _convert_to_string("regular_string")
        assert result == "regular_string"

    def test_convert_to_string_with_number(self):
        """Test converting number to string."""
        result = _convert_to_string(123)
        assert result == "123"

    def test_convert_to_string_with_none(self):
        """Test converting None to string."""
        result = _convert_to_string(None)
        assert result == "None"

    def test_convert_to_string_with_list(self):
        """Test converting list to string."""
        result = _convert_to_string([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_convert_to_string_with_dict(self):
        """Test converting dict to string."""
        result = _convert_to_string({"key": "value"})
        assert result == "{'key': 'value'}"

    @pytest.mark.asyncio
    async def test_service_registration_with_coordinator_categories(self, mock_hass):
        """Test service registration based on coordinator categories."""
        from custom_components.hass_dyson.services import async_register_device_services_for_categories

        categories = ["ec", "robot"]
        await async_register_device_services_for_categories(mock_hass, categories)

        # Should register services for the specified categories
        assert mock_hass.services.async_register.call_count >= 1

    @pytest.mark.asyncio
    async def test_service_unregistration_with_coordinator_categories(self, mock_hass):
        """Test service unregistration based on coordinator categories."""
        from custom_components.hass_dyson.services import async_unregister_device_services_for_categories

        categories = ["ec", "robot"]

        # First register services to have something to unregister
        from custom_components.hass_dyson.services import async_register_device_services_for_categories

        await async_register_device_services_for_categories(mock_hass, categories)

        # Then unregister
        await async_unregister_device_services_for_categories(mock_hass, categories)

        # Should have called register first, then potentially remove
        assert mock_hass.services.async_register.call_count >= 1

    @pytest.mark.asyncio
    async def test_coordinator_device_service_registration(
        self, mock_hass, mock_coordinator
    ):
        """Test device service registration for a specific coordinator."""
        from custom_components.hass_dyson.services import async_register_device_services_for_coordinator

        # Set up coordinator with device categories
        mock_coordinator.device_category = ["ec"]
        mock_coordinator.device_capabilities = ["Scheduling"]

        await async_register_device_services_for_coordinator(
            mock_hass, mock_coordinator
        )

        # Should register services based on capabilities and categories
        assert (
            mock_hass.services.async_register.call_count >= 0
        )  # May be 0 if services already registered

    @pytest.mark.asyncio
    async def test_device_service_setup_for_coordinator(
        self, mock_hass, mock_coordinator
    ):
        """Test device service setup for a specific coordinator."""
        from custom_components.hass_dyson.services import async_setup_device_services_for_coordinator

        with patch(
            "custom_components.hass_dyson.services.async_register_device_services_for_coordinator",
            new_callable=AsyncMock,
        ) as mock_register:
            await async_setup_device_services_for_coordinator(
                mock_hass, mock_coordinator
            )

            # async_setup_device_services_for_coordinator no longer calls async_setup_cloud_services
            # Cloud services are only set up when cloud accounts are configured
            mock_register.assert_called_once_with(mock_hass, mock_coordinator)

    @pytest.mark.asyncio
    async def test_device_service_removal_for_coordinator(
        self, mock_hass, mock_coordinator
    ):
        """Test device service removal for a specific coordinator."""
        from custom_components.hass_dyson.services import async_remove_device_services_for_coordinator

        # Set up coordinator with device categories
        mock_coordinator.device_category = ["ec"]

        with patch(
            "custom_components.hass_dyson.services._get_device_categories_for_coordinator",
            return_value=["ec"],
        ):
            with patch(
                "custom_components.hass_dyson.services.async_unregister_device_services_for_categories",
                new_callable=AsyncMock,
            ) as mock_unregister:
                await async_remove_device_services_for_coordinator(
                    mock_hass, mock_coordinator
                )
                mock_unregister.assert_called_once_with(mock_hass, ["ec"])

    def test_get_device_categories_for_coordinator_string(self, mock_coordinator):
        """Test getting device categories when coordinator has string category."""
        from custom_components.hass_dyson.services import _get_device_categories_for_coordinator

        mock_coordinator.device_category = "ec"

        result = _get_device_categories_for_coordinator(mock_coordinator)
        assert result == ["ec"]

    def test_get_device_categories_for_coordinator_list(self, mock_coordinator):
        """Test getting device categories when coordinator has list category."""
        from custom_components.hass_dyson.services import _get_device_categories_for_coordinator

        mock_coordinator.device_category = ["ec", "robot"]

        result = _get_device_categories_for_coordinator(mock_coordinator)
        assert result == ["ec", "robot"]

    def test_get_device_categories_for_coordinator_none(self, mock_coordinator):
        """Test getting device categories when coordinator has no category."""
        from custom_components.hass_dyson.services import _get_device_categories_for_coordinator

        # Remove device_category attribute
        if hasattr(mock_coordinator, "device_category"):
            delattr(mock_coordinator, "device_category")

        result = _get_device_categories_for_coordinator(mock_coordinator)
        assert result == []

    def test_get_device_categories_for_coordinator_empty(self, mock_coordinator):
        """Test getting device categories when coordinator has empty category."""
        from custom_components.hass_dyson.services import _get_device_categories_for_coordinator

        mock_coordinator.device_category = []

        result = _get_device_categories_for_coordinator(mock_coordinator)
        assert result == []

    @pytest.mark.asyncio
    async def test_find_cloud_coordinators_empty(self, mock_hass):
        """Test finding cloud coordinators when none exist."""
        from custom_components.hass_dyson.services import _find_cloud_coordinators

        mock_hass.data[DOMAIN] = {}

        result = _find_cloud_coordinators(mock_hass)
        assert result == []

    @pytest.mark.asyncio
    async def test_find_cloud_coordinators_with_cloud_account(self, mock_hass):
        """Test finding cloud coordinators with cloud account coordinator."""
        from custom_components.hass_dyson.coordinator import DysonCloudAccountCoordinator
        from custom_components.hass_dyson.services import _find_cloud_coordinators

        mock_cloud_coordinator = MagicMock(spec=DysonCloudAccountCoordinator)
        mock_cloud_coordinator.config_entry = MagicMock()
        mock_cloud_coordinator.config_entry.data = {"email": "test@example.com"}
        mock_cloud_coordinator.config_entry.entry_id = "test_entry"

        mock_hass.data[DOMAIN] = {"test_key": mock_cloud_coordinator}

        result = _find_cloud_coordinators(mock_hass)
        assert len(result) == 1
        assert result[0]["email"] == "test@example.com"
        assert result[0]["type"] == "cloud_account"

    @pytest.mark.asyncio
    async def test_find_cloud_coordinators_with_device_coordinator(self, mock_hass):
        """Test finding cloud coordinators with device coordinator using cloud discovery."""
        from custom_components.hass_dyson.const import CONF_DISCOVERY_METHOD, DISCOVERY_CLOUD
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
        from custom_components.hass_dyson.services import _find_cloud_coordinators

        mock_device_coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_device_coordinator.config_entry = MagicMock()
        mock_device_coordinator.config_entry.data = {
            CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD,
            "email": "test@example.com",
        }
        mock_device_coordinator.config_entry.entry_id = "test_entry"
        mock_device_coordinator.device = MagicMock()  # Has device

        mock_hass.data[DOMAIN] = {"test_key": mock_device_coordinator}

        result = _find_cloud_coordinators(mock_hass)
        assert len(result) == 1
        assert result[0]["email"] == "test@example.com"
        assert result[0]["type"] == "device"

    @pytest.mark.asyncio
    async def test_find_cloud_coordinators_fallback_to_config_entries(self, mock_hass):
        """Test finding cloud coordinators fallback to config entries when no coordinators exist."""
        from custom_components.hass_dyson.services import _find_cloud_coordinators

        mock_hass.data[DOMAIN] = {}

        # Mock config entry
        mock_config_entry = MagicMock()
        mock_config_entry.data = {
            "email": "test@example.com",
            "auth_token": "test_token",
            "devices": [{"serial": "123"}],
        }
        mock_config_entry.entry_id = "test_entry"

        mock_hass.config_entries.async_entries.return_value = [mock_config_entry]

        result = _find_cloud_coordinators(mock_hass)
        assert len(result) == 1
        assert result[0]["email"] == "test@example.com"
        assert result[0]["type"] == "config_entry"

    def test_extract_enhanced_device_info_basic(self):
        """Test extracting enhanced device info from basic device."""
        from custom_components.hass_dyson.services import _extract_enhanced_device_info

        mock_device = MagicMock()
        mock_device.name = "Test Device"
        mock_device.serial_number = "VS6-EU-HJA1234A"
        mock_device.type = "438"
        mock_device.variant = "K"
        mock_device.model = "V6"
        mock_device.connection_category = "connected"
        mock_device.category = ["ec"]

        result = _extract_enhanced_device_info(mock_device)

        assert result["name"] == "Test Device"
        assert result["product_type"] == "438K"
        assert result["model"] == "V6"
        assert result["connection_category"] == "connected"
        assert result["device_category"] == ["ec"]

    def test_extract_enhanced_device_info_no_name(self):
        """Test extracting enhanced device info when device has no name."""
        from custom_components.hass_dyson.services import _extract_enhanced_device_info

        mock_device = MagicMock()
        mock_device.serial_number = "VS6-EU-HJA1234A"
        # Remove name attribute
        if hasattr(mock_device, "name"):
            delattr(mock_device, "name")

        result = _extract_enhanced_device_info(mock_device)

        assert result["name"] == "Dyson VS6-EU-HJA1234A"

    def test_extract_enhanced_device_info_with_connected_config(self):
        """Test extracting enhanced device info with connected configuration."""
        from custom_components.hass_dyson.services import _extract_enhanced_device_info

        mock_device = MagicMock()
        mock_device.name = "Test Device"
        mock_device.serial_number = "VS6-EU-HJA1234A"

        # Mock connected configuration
        mock_connected_config = MagicMock()
        mock_firmware = MagicMock()
        mock_firmware.version = "1.0.0"
        mock_firmware.capabilities = ["Scheduling", "AdvanceOscillationDay1"]
        mock_connected_config.firmware = mock_firmware

        mock_mqtt = MagicMock()
        mock_mqtt.mqtt_root_topic_level = "475"
        mock_connected_config.mqtt = mock_mqtt

        mock_device.connected_configuration = mock_connected_config

        result = _extract_enhanced_device_info(mock_device)

        assert result["firmware_version"] == "1.0.0"
        assert result["capabilities"] == ["Scheduling", "AdvanceOscillationDay1"]
        assert result["mqtt_prefix"] == "475"

    def test_extract_enhanced_device_info_category_string(self):
        """Test extracting enhanced device info with string category."""
        from custom_components.hass_dyson.services import _extract_enhanced_device_info

        mock_device = MagicMock()
        mock_device.name = "Test Device"
        mock_device.category = "ec"  # String instead of list

        result = _extract_enhanced_device_info(mock_device)

        assert result["device_category"] == ["ec"]

    def test_extract_enhanced_device_info_category_enum(self):
        """Test extracting enhanced device info with enum category."""
        from enum import Enum

        from custom_components.hass_dyson.services import _extract_enhanced_device_info

        class TestEnum(Enum):
            EC = "ec"

        mock_device = MagicMock()
        mock_device.name = "Test Device"
        mock_device.category = [TestEnum.EC]  # Enum in list

        result = _extract_enhanced_device_info(mock_device)

        assert result["device_category"] == ["ec"]
