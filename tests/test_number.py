"""Test the number platform."""

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
        # Mock the device_capabilities property to return a list
        coordinator.device_capabilities = ["Scheduling"]
        # Set device_category to not be an environment cleaner
        coordinator.device_category = ["other"]

        mock_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        # Should add sleep timer entity
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
        # Mock the device_capabilities property to return a list
        coordinator.device_capabilities = ["AdvanceOscillationDay1"]

        mock_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        # Should add 5 oscillation entities
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 4
        assert isinstance(entities[0], DysonOscillationLowerAngleNumber)
        assert isinstance(entities[1], DysonOscillationUpperAngleNumber)
        assert isinstance(entities[2], DysonOscillationCenterAngleNumber)
        assert isinstance(entities[3], DysonOscillationAngleSpanNumber)

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_oscillation_day0_capability(
        self, mock_hass, mock_config_entry
    ):
        """Test setting up entry with AdvanceOscillationDay0 capability."""
        coordinator = mock_hass.data["hass_dyson"]["NK6-EU-MHA0000A"]
        coordinator.device.device_info = {
            "product_type": "469",
            "capabilities": ["AdvanceOscillationDay0"],
        }
        # Mock the device_capabilities property to return a list
        coordinator.device_capabilities = ["AdvanceOscillationDay0"]

        mock_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        # Should add 4 Day0 oscillation entities including center angle control
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 4
        from custom_components.hass_dyson.number import (
            DysonOscillationDay0AngleSpanNumber,
            DysonOscillationDay0CenterAngleNumber,
            DysonOscillationDay0LowerAngleNumber,
            DysonOscillationDay0UpperAngleNumber,
        )

        assert isinstance(entities[0], DysonOscillationDay0LowerAngleNumber)
        assert isinstance(entities[1], DysonOscillationDay0UpperAngleNumber)
        assert isinstance(entities[2], DysonOscillationDay0CenterAngleNumber)
        assert isinstance(entities[3], DysonOscillationDay0AngleSpanNumber)

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_both_capabilities(
        self, mock_hass, mock_config_entry
    ):
        """Test setting up entry with both capabilities."""
        coordinator = mock_hass.data["hass_dyson"]["NK6-EU-MHA0000A"]
        coordinator.device.device_info = {
            "product_type": "469",
            "capabilities": ["Scheduling", "AdvanceOscillationDay1"],
        }
        # Mock the device_capabilities property to return a list
        coordinator.device_capabilities = ["Scheduling", "AdvanceOscillationDay1"]

        mock_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        # Should add all 5 entities
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 5
        assert isinstance(entities[0], DysonSleepTimerNumber)
        assert isinstance(entities[1], DysonOscillationLowerAngleNumber)

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_capabilities(
        self, mock_hass, mock_config_entry
    ):
        """Test setting up entry with no relevant capabilities."""
        coordinator = mock_hass.data["hass_dyson"]["NK6-EU-MHA0000A"]
        coordinator.device.device_info = {
            "product_type": "469",
            "capabilities": ["SomeOtherCapability"],
        }
        # Mock the device_capabilities property to return a list
        coordinator.device_capabilities = ["SomeOtherCapability"]
        # Mock device_category to NOT be an environment cleaner
        coordinator.device_category = ["other"]

        mock_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        # Should add no entities
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 0


class TestDysonSleepTimerNumber:
    """Test the Dyson sleep timer number entity."""

    def test_initialization(self, mock_coordinator):
        """Test sleep timer number initialization."""
        entity = DysonSleepTimerNumber(mock_coordinator)

        assert entity._attr_unique_id == "NK6-EU-MHA0000A_sleep_timer"
        assert entity._attr_translation_key == "sleep_timer"
        assert entity._attr_icon == "mdi:timer"
        assert entity._attr_mode == NumberMode.BOX
        assert entity._attr_native_min_value == 0
        assert entity._attr_native_max_value == 540
        assert entity._attr_native_step == 15
        assert entity._attr_native_unit_of_measurement == "min"

    def test_handle_coordinator_update_with_device(self, mock_coordinator):
        """Test handling coordinator update with device."""
        entity = DysonSleepTimerNumber(mock_coordinator)
        mock_coordinator.device.get_state_value.return_value = "60"

        # Mock super()._handle_coordinator_update to avoid HA state machinery
        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            with patch("asyncio.create_task") as mock_create_task:
                entity._handle_coordinator_update()

        assert entity._attr_native_value == 60
        # Verify task was created for timer polling
        mock_create_task.assert_called_once()

    def test_handle_coordinator_update_no_device(self, mock_coordinator):
        """Test handling coordinator update without device."""
        entity = DysonSleepTimerNumber(mock_coordinator)
        mock_coordinator.device = None

        # Mock super()._handle_coordinator_update to avoid HA state machinery
        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            with patch("asyncio.create_task"):
                entity._handle_coordinator_update()

        assert entity._attr_native_value is None

    def test_handle_coordinator_update_invalid_value(self, mock_coordinator):
        """Test handling coordinator update with invalid value."""
        entity = DysonSleepTimerNumber(mock_coordinator)
        mock_coordinator.device.get_state_value.return_value = "invalid"

        # Mock super()._handle_coordinator_update to avoid HA state machinery
        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            with patch("asyncio.create_task"):
                entity._handle_coordinator_update()

        assert entity._attr_native_value == 0

    @pytest.mark.asyncio
    async def test_async_set_native_value_success(self, mock_coordinator):
        """Test setting sleep timer value successfully."""
        entity = DysonSleepTimerNumber(mock_coordinator)

        with patch("custom_components.hass_dyson.number._LOGGER") as mock_logger:
            await entity.async_set_native_value(90.0)

        mock_coordinator.device.set_sleep_timer.assert_called_once_with(90)
        # Expect 2 debug calls: one for setting and one for waiting
        assert mock_logger.debug.call_count == 2

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
    """Test the Dyson oscillation lower angle number entity."""

    def test_initialization(self, mock_coordinator):
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

    def test_handle_coordinator_update_zero_value(self, mock_coordinator):
        """Test handling coordinator update with zero value."""
        entity = DysonOscillationLowerAngleNumber(mock_coordinator)
        mock_coordinator.device.get_state_value.return_value = "0000"

        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity._attr_native_value == 0

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

    @pytest.mark.asyncio
    async def test_async_set_native_value_boundary_adjustment(self, mock_coordinator):
        """Test setting lower angle that requires upper angle adjustment."""
        entity = DysonOscillationLowerAngleNumber(mock_coordinator)
        # Mock current upper angle that would create invalid range
        mock_coordinator.data = {"product-state": {"osau": "0050"}}

        await entity.async_set_native_value(100.0)

        # Should adjust to ensure minimum span
        mock_coordinator.device.set_oscillation_angles.assert_called_once_with(45, 50)


class TestDysonOscillationUpperAngleNumber:
    """Test the Dyson oscillation upper angle number entity."""

    def test_initialization(self, mock_coordinator):
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

    @pytest.mark.asyncio
    async def test_async_set_native_value_boundary_adjustment(self, mock_coordinator):
        """Test setting upper angle that requires lower angle adjustment."""
        entity = DysonOscillationUpperAngleNumber(mock_coordinator)
        # Mock current lower angle that would create invalid range
        mock_coordinator.data = {"product-state": {"osal": "0300"}}

        await entity.async_set_native_value(200.0)

        # Should adjust to maintain minimum span (actual implementation adds 5° to lower)
        mock_coordinator.device.set_oscillation_angles.assert_called_once_with(300, 305)


class TestDysonOscillationCenterAngleNumber:
    """Test the Dyson oscillation center angle number entity."""

    def test_initialization(self, mock_coordinator):
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

    @pytest.mark.asyncio
    async def test_async_set_native_value_success(self, mock_coordinator):
        """Test setting center angle value successfully."""
        entity = DysonOscillationCenterAngleNumber(mock_coordinator)
        # Mock current angles: lower=45°, upper=315°, span=270°
        mock_coordinator.device.get_state_value.side_effect = ["0045", "0315"]

        await entity.async_set_native_value(200.0)

        # Should maintain span of 270° around new center of 200°
        # New lower: 200 - 135 = 65°, New upper: 200 + 135 = 335°
        mock_coordinator.device.set_oscillation_angles.assert_called_once_with(65, 335)

    @pytest.mark.asyncio
    async def test_async_set_native_value_boundary_lower(self, mock_coordinator):
        """Test setting center angle that hits lower boundary."""
        entity = DysonOscillationCenterAngleNumber(mock_coordinator)
        # Mock current span of 180°
        mock_coordinator.device.get_state_value.side_effect = ["0090", "0270"]

        await entity.async_set_native_value(50.0)

        # Should adjust to boundaries: lower=0°, upper=180°
        mock_coordinator.device.set_oscillation_angles.assert_called_once_with(0, 180)

    @pytest.mark.asyncio
    async def test_async_set_native_value_boundary_upper(self, mock_coordinator):
        """Test setting center angle that hits upper boundary."""
        entity = DysonOscillationCenterAngleNumber(mock_coordinator)
        # Mock current span of 180°
        mock_coordinator.device.get_state_value.side_effect = ["0090", "0270"]

        await entity.async_set_native_value(320.0)

        # Should adjust to boundaries: lower=170°, upper=350°
        mock_coordinator.device.set_oscillation_angles.assert_called_once_with(170, 350)


class TestDysonOscillationAngleSpanNumber:
    """Test the Dyson oscillation angle span number entity."""

    def test_initialization(self, mock_coordinator):
        """Test angle span number initialization."""
        entity = DysonOscillationAngleSpanNumber(mock_coordinator)

        assert entity._attr_unique_id == "NK6-EU-MHA0000A_oscillation_angle_span"
        assert entity._attr_translation_key == "oscillation_angle_span"
        assert entity._attr_icon == "mdi:angle-acute"

    def test_handle_coordinator_update_with_device(self, mock_coordinator):
        """Test handling coordinator update with device."""
        entity = DysonOscillationAngleSpanNumber(mock_coordinator)
        # Mock lower and upper angles: 45° and 315°, span should be 270°
        mock_coordinator.device.get_state_value.side_effect = ["0045", "0315"]

        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity._attr_native_value == 270  # 315 - 45

    @pytest.mark.asyncio
    async def test_async_set_native_value_success(self, mock_coordinator):
        """Test setting angle span value successfully."""
        entity = DysonOscillationAngleSpanNumber(mock_coordinator)
        # Mock current angles: lower=45°, upper=315°, center=180°
        mock_coordinator.device.get_state_value.side_effect = ["0045", "0315"]

        await entity.async_set_native_value(180.0)

        # Should maintain center of 180° with new span of 180°
        # New lower: 180 - 90 = 90°, New upper: 180 + 90 = 270°
        mock_coordinator.device.set_oscillation_angles.assert_called_once_with(90, 270)

    @pytest.mark.asyncio
    async def test_async_set_native_value_boundary_lower(self, mock_coordinator):
        """Test setting span that hits lower boundary."""
        entity = DysonOscillationAngleSpanNumber(mock_coordinator)
        # Mock current center at 50°
        mock_coordinator.device.get_state_value.side_effect = ["0030", "0070"]

        await entity.async_set_native_value(200.0)

        # Should adjust to boundaries: lower=0°, upper=200°
        mock_coordinator.device.set_oscillation_angles.assert_called_once_with(0, 200)

    @pytest.mark.asyncio
    async def test_async_set_native_value_boundary_upper(self, mock_coordinator):
        """Test setting span that hits upper boundary."""
        entity = DysonOscillationAngleSpanNumber(mock_coordinator)
        # Mock current center at 300°
        mock_coordinator.device.get_state_value.side_effect = ["0280", "0320"]

        await entity.async_set_native_value(200.0)

        # Should adjust to boundaries: lower=150°, upper=350°
        mock_coordinator.device.set_oscillation_angles.assert_called_once_with(150, 350)


class TestErrorHandling:
    """Test error handling across all number entities."""

    @pytest.mark.asyncio
    async def test_all_entities_handle_missing_device_gracefully(
        self, mock_coordinator
    ):
        """Test that all entities handle missing device gracefully."""
        mock_coordinator.device = None

        entities = [
            DysonSleepTimerNumber(mock_coordinator),
            DysonOscillationLowerAngleNumber(mock_coordinator),
            DysonOscillationUpperAngleNumber(mock_coordinator),
            DysonOscillationCenterAngleNumber(mock_coordinator),
            DysonOscillationAngleSpanNumber(mock_coordinator),
        ]

        # Set hass attribute for all entities to avoid RuntimeError
        for entity in entities:
            entity.hass = MagicMock()

        # All should handle coordinator update without device
        for entity in entities:
            with patch.object(entity, "_handle_coordinator_update_safe"):
                with patch(
                    "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
                ):
                    entity._handle_coordinator_update()
            assert entity._attr_native_value is None

        # All should handle async_set_native_value without device
        for entity in entities:
            await entity.async_set_native_value(
                100.0
            )  # Should return early without errors

    def test_all_entities_handle_invalid_coordinator_data(self, mock_coordinator):
        """Test that all entities handle invalid coordinator data."""
        entities = [
            DysonSleepTimerNumber(mock_coordinator),
            DysonOscillationLowerAngleNumber(mock_coordinator),
            DysonOscillationUpperAngleNumber(mock_coordinator),
            DysonOscillationCenterAngleNumber(mock_coordinator),
            DysonOscillationAngleSpanNumber(mock_coordinator),
        ]

        # Set up invalid data that can't be converted to int
        mock_coordinator.device.get_state_value.return_value = "invalid_number"

        # All should handle invalid data gracefully by returning None
        for entity in entities:
            assert entity.native_value is None


class TestNumberCoverageEnhancement:
    """Test class to enhance number coverage to 95%+."""

    def test_sleep_timer_device_exception_handling(self, mock_coordinator):
        """Test sleep timer handles device exceptions properly."""
        mock_coordinator.device.get_state_value.side_effect = Exception("Device error")

        sleep_timer = DysonSleepTimerNumber(mock_coordinator)
        with patch.object(sleep_timer, "_handle_coordinator_update_safe"):
            with patch(
                "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
            ):
                sleep_timer._handle_coordinator_update()

        # Should catch exception and set value to 0
        assert sleep_timer._attr_native_value == 0

    def test_sleep_timer_invalid_data_conversion(self, mock_coordinator):
        """Test sleep timer handles invalid data conversion properly."""
        mock_coordinator.device.get_state_value.return_value = "invalid_data"

        sleep_timer = DysonSleepTimerNumber(mock_coordinator)
        # Mock the hass attribute
        sleep_timer.hass = MagicMock()

        with patch.object(sleep_timer, "_handle_coordinator_update_safe"):
            with patch(
                "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
            ):
                sleep_timer._handle_coordinator_update()

        # Should handle invalid data and set value to 0
        assert sleep_timer._attr_native_value == 0

        with patch.object(sleep_timer, "_handle_coordinator_update_safe"):
            with patch(
                "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
            ):
                sleep_timer._handle_coordinator_update()

        # Should catch ValueError/TypeError and set value to 0
        assert sleep_timer._attr_native_value == 0

    def test_sleep_timer_extra_state_attributes_with_device(self, mock_coordinator):
        """Test sleep timer extra_state_attributes with device."""
        mock_coordinator.device.get_state_value.return_value = "0120"

        sleep_timer = DysonSleepTimerNumber(mock_coordinator)
        sleep_timer._attr_native_value = 120

        attributes = sleep_timer.extra_state_attributes

        assert attributes is not None
        assert attributes["sleep_timer_minutes"] == 120
        assert attributes["sleep_timer_raw"] == "0120"
        assert attributes["sleep_timer_enabled"] is True

    def test_sleep_timer_extra_state_attributes_no_device(self, mock_coordinator):
        """Test sleep timer extra_state_attributes without device."""
        mock_coordinator.device = None

        sleep_timer = DysonSleepTimerNumber(mock_coordinator)

        attributes = sleep_timer.extra_state_attributes

        assert attributes is None

    def test_sleep_timer_extra_state_attributes_off_timer(self, mock_coordinator):
        """Test sleep timer extra_state_attributes with OFF timer."""
        mock_coordinator.device.get_state_value.return_value = "OFF"

        sleep_timer = DysonSleepTimerNumber(mock_coordinator)
        sleep_timer._attr_native_value = 0

        attributes = sleep_timer.extra_state_attributes

        assert attributes is not None
        assert attributes["sleep_timer_minutes"] == 0
        assert attributes["sleep_timer_raw"] == "OFF"
        assert attributes["sleep_timer_enabled"] is False

    def test_sleep_timer_value_error_conversion_path(self, mock_coordinator):
        """Test sleep timer ValueError path in conversion."""
        # Set up device to return non-OFF value that can't be converted to int
        mock_coordinator.device.get_state_value.return_value = "not_off_but_invalid"

        sleep_timer = DysonSleepTimerNumber(mock_coordinator)
        # Mock the hass attribute
        sleep_timer.hass = MagicMock()

        with patch.object(sleep_timer, "_handle_coordinator_update_safe"):
            with patch(
                "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
            ):
                sleep_timer._handle_coordinator_update()

        # Should handle ValueError and set value to 0
        assert sleep_timer._attr_native_value == 0

        with patch.object(sleep_timer, "_handle_coordinator_update_safe"):
            with patch(
                "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
            ):
                sleep_timer._handle_coordinator_update()

        # Should catch ValueError/TypeError and set value to 0 (line 80)
        assert sleep_timer._attr_native_value == 0


class TestDysonOscillationDay0CenterAngleNumber:
    """Test Day0 center angle number entity."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock()
        coordinator.serial_number = "TEST-123"
        coordinator.device = MagicMock()
        coordinator.data = {"product-state": {}}

        # Mock device state values
        coordinator.device.get_state_value = MagicMock()

        def mock_get_state_value(state, key, default):
            if key == "osal":  # lower angle
                return "0160"  # 160°
            elif key == "osau":  # upper angle
                return "0200"  # 200°
            return default

        coordinator.device.get_state_value.side_effect = mock_get_state_value

        return coordinator

    def test_initialization(self, mock_coordinator):
        """Test Day0 center angle number entity initialization."""
        from custom_components.hass_dyson.number import (
            DysonOscillationDay0CenterAngleNumber,
        )

        entity = DysonOscillationDay0CenterAngleNumber(mock_coordinator)

        # Check attributes
        assert entity._attr_unique_id == "TEST-123_oscillation_day0_center_angle"
        assert entity._attr_translation_key == "oscillation_day0_center_angle"
        assert entity._attr_icon == "mdi:crosshairs"
        assert entity._attr_native_min_value == 147  # 142 + 5 (min half-span)
        assert entity._attr_native_max_value == 207  # 212 - 5 (min half-span)
        assert entity._attr_native_step == 1
        assert entity._attr_native_unit_of_measurement == "°"

    def test_handle_coordinator_update_with_device(self, mock_coordinator):
        """Test coordinator update with valid device data."""
        from custom_components.hass_dyson.number import (
            DysonOscillationDay0CenterAngleNumber,
        )

        entity = DysonOscillationDay0CenterAngleNumber(mock_coordinator)
        entity.hass = MagicMock()  # Mock hass for state updates

        # Mock parent class method
        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            entity._handle_coordinator_update()

        # Should calculate center as (160 + 200) // 2 = 180
        assert entity._attr_native_value == 180

    def test_handle_coordinator_update_no_device(self, mock_coordinator):
        """Test coordinator update with no device."""
        from custom_components.hass_dyson.number import (
            DysonOscillationDay0CenterAngleNumber,
        )

        mock_coordinator.device = None
        entity = DysonOscillationDay0CenterAngleNumber(mock_coordinator)
        entity.hass = MagicMock()

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            entity._handle_coordinator_update()

        # Should be None when no device
        assert entity._attr_native_value is None

    def test_handle_coordinator_update_invalid_data(self, mock_coordinator):
        """Test coordinator update with invalid data."""
        from custom_components.hass_dyson.number import (
            DysonOscillationDay0CenterAngleNumber,
        )

        # Mock invalid data
        def mock_invalid_state_value(state, key, default):
            if key == "osal":
                return "invalid"
            elif key == "osau":
                return "also_invalid"
            return default

        mock_coordinator.device.get_state_value.side_effect = mock_invalid_state_value
        entity = DysonOscillationDay0CenterAngleNumber(mock_coordinator)
        entity.hass = MagicMock()

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            entity._handle_coordinator_update()

        # Should default to 177° when data is invalid
        assert entity._attr_native_value == 177

    def test_handle_coordinator_update_boundary_values(self, mock_coordinator):
        """Test coordinator update with boundary values."""
        from custom_components.hass_dyson.number import (
            DysonOscillationDay0CenterAngleNumber,
        )

        # Mock boundary values (142° - 212°)
        def mock_boundary_state_value(state, key, default):
            if key == "osal":
                return "0142"  # 142°
            elif key == "osau":
                return "0212"  # 212°
            return default

        mock_coordinator.device.get_state_value.side_effect = mock_boundary_state_value
        entity = DysonOscillationDay0CenterAngleNumber(mock_coordinator)
        entity.hass = MagicMock()

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity._handle_coordinator_update"
        ):
            entity._handle_coordinator_update()

        # Should calculate center as (142 + 212) // 2 = 177
        assert entity._attr_native_value == 177

    @pytest.mark.asyncio
    async def test_async_set_native_value_success(self, mock_coordinator):
        """Test setting center angle successfully."""
        from custom_components.hass_dyson.number import (
            DysonOscillationDay0CenterAngleNumber,
        )

        mock_coordinator.device.set_oscillation_angles_day0 = AsyncMock()
        entity = DysonOscillationDay0CenterAngleNumber(mock_coordinator)

        # Set center to 180° with current span of 40° (160° - 200°)
        await entity.async_set_native_value(180.0)

        # Should maintain span and adjust to new center: 160° - 200°
        mock_coordinator.device.set_oscillation_angles_day0.assert_called_once_with(
            160, 200
        )

    @pytest.mark.asyncio
    async def test_async_set_native_value_boundary_adjustment_lower(
        self, mock_coordinator
    ):
        """Test setting center angle with lower boundary adjustment."""
        from custom_components.hass_dyson.number import (
            DysonOscillationDay0CenterAngleNumber,
        )

        # Mock current state: narrow span near lower boundary
        def mock_lower_boundary_state_value(state, key, default):
            if key == "osal":
                return "0145"  # 145°
            elif key == "osau":
                return "0155"  # 155° (10° span)
            return default

        mock_coordinator.device.get_state_value.side_effect = (
            mock_lower_boundary_state_value
        )
        mock_coordinator.device.set_oscillation_angles_day0 = AsyncMock()

        entity = DysonOscillationDay0CenterAngleNumber(mock_coordinator)

        # Try to set center to 145° (would result in 140°-150°, but 140° < 142°)
        await entity.async_set_native_value(145.0)

        # Should adjust: lower clamped to 142°, upper adjusted to 152°
        mock_coordinator.device.set_oscillation_angles_day0.assert_called_once_with(
            142, 152
        )

    @pytest.mark.asyncio
    async def test_async_set_native_value_boundary_adjustment_upper(
        self, mock_coordinator
    ):
        """Test setting center angle with upper boundary adjustment."""
        from custom_components.hass_dyson.number import (
            DysonOscillationDay0CenterAngleNumber,
        )

        # Mock current state: narrow span near upper boundary
        def mock_upper_boundary_state_value(state, key, default):
            if key == "osal":
                return "0205"  # 205°
            elif key == "osau":
                return "0215"  # 215° (10° span) - but 215° > 212°
            return default

        mock_coordinator.device.get_state_value.side_effect = (
            mock_upper_boundary_state_value
        )
        mock_coordinator.device.set_oscillation_angles_day0 = AsyncMock()

        entity = DysonOscillationDay0CenterAngleNumber(mock_coordinator)

        # Try to set center to 210° (would result in 205°-215°, but 215° > 212°)
        await entity.async_set_native_value(210.0)

        # Should adjust: upper clamped to 212°, lower adjusted to 202°
        mock_coordinator.device.set_oscillation_angles_day0.assert_called_once_with(
            202, 212
        )

    @pytest.mark.asyncio
    async def test_async_set_native_value_no_device(self, mock_coordinator):
        """Test setting center angle with no device."""
        from custom_components.hass_dyson.number import (
            DysonOscillationDay0CenterAngleNumber,
        )

        mock_coordinator.device = None
        entity = DysonOscillationDay0CenterAngleNumber(mock_coordinator)

        # Should not raise an exception
        await entity.async_set_native_value(180.0)

    @pytest.mark.asyncio
    async def test_async_set_native_value_connection_error(self, mock_coordinator):
        """Test setting center angle with connection error."""
        from custom_components.hass_dyson.number import (
            DysonOscillationDay0CenterAngleNumber,
        )

        mock_coordinator.device.set_oscillation_angles_day0 = AsyncMock(
            side_effect=ConnectionError("Connection failed")
        )
        entity = DysonOscillationDay0CenterAngleNumber(mock_coordinator)

        # Should not raise an exception
        await entity.async_set_native_value(180.0)

    @pytest.mark.asyncio
    async def test_async_set_native_value_key_error(self, mock_coordinator):
        """Test setting center angle with KeyError."""
        from custom_components.hass_dyson.number import (
            DysonOscillationDay0CenterAngleNumber,
        )

        # Mock missing data
        mock_coordinator.data = {}
        entity = DysonOscillationDay0CenterAngleNumber(mock_coordinator)

        # Should not raise an exception
        await entity.async_set_native_value(180.0)

    @pytest.mark.asyncio
    async def test_async_set_native_value_value_error(self, mock_coordinator):
        """Test setting center angle with ValueError."""
        from custom_components.hass_dyson.number import (
            DysonOscillationDay0CenterAngleNumber,
        )

        mock_coordinator.device.set_oscillation_angles_day0 = AsyncMock(
            side_effect=ValueError("Invalid value")
        )
        entity = DysonOscillationDay0CenterAngleNumber(mock_coordinator)

        # Should not raise an exception
        await entity.async_set_native_value(180.0)

    @pytest.mark.asyncio
    async def test_async_set_native_value_generic_exception(self, mock_coordinator):
        """Test setting center angle with generic exception."""
        from custom_components.hass_dyson.number import (
            DysonOscillationDay0CenterAngleNumber,
        )

        mock_coordinator.device.set_oscillation_angles_day0 = AsyncMock(
            side_effect=Exception("Generic error")
        )
        entity = DysonOscillationDay0CenterAngleNumber(mock_coordinator)

        # Should not raise an exception
        await entity.async_set_native_value(180.0)
