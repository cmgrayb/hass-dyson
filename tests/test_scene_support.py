"""Test scene support implementation."""

from unittest.mock import MagicMock

import pytest

from custom_components.hass_dyson.climate import DysonClimateEntity
from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator
from custom_components.hass_dyson.fan import DysonFan
from custom_components.hass_dyson.number import DysonSleepTimerNumber
from custom_components.hass_dyson.select import (
    DysonHeatingModeSelect,
    DysonOscillationModeSelect,
)
from custom_components.hass_dyson.switch import (
    DysonContinuousMonitoringSwitch,
    DysonHeatingSwitch,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator with device data."""
    coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
    coordinator.serial_number = "TEST-DEVICE-001"
    coordinator.device_name = "Test Dyson Device"
    coordinator.device_category = ["ec"]
    coordinator.device_capabilities = [
        "Heating",
        "ExtendedAQ",
        "AdvanceOscillationDay1",
        "Scheduling",
    ]

    # Mock device
    device = MagicMock()
    device._get_current_value = MagicMock()
    coordinator.device = device

    # Mock device data
    coordinator.data = {
        "product-state": {
            "fpwr": "ON",  # Fan power
            "fnst": "FAN",  # Fan state
            "fnsp": "0005",  # Fan speed
            "auto": "OFF",  # Auto mode
            "nmod": "ON",  # Night mode
            "oson": "ON",  # Oscillation
            "osal": "0045",  # Lower angle
            "osau": "0315",  # Upper angle
            "ancp": "0180",  # Center angle
            "hmod": "HEAT",  # Heating mode
            "hmax": "2930",  # Target temp (20°C in Kelvin)
            "tmp": "2900",  # Current temp (19°C in Kelvin)
            "sltm": "120",  # Sleep timer (2 hours)
            "rhtm": "ON",  # Continuous monitoring
        }
    }

    return coordinator


class TestFanSceneSupport:
    """Test fan entity scene support."""

    def test_fan_extra_state_attributes(self, mock_coordinator):
        """Test fan entity exposes all properties for scene support."""
        # Setup device mock return values
        mock_coordinator.device._get_current_value.side_effect = (
            lambda data, key, default: {
                "fpwr": "ON",
                "fnst": "FAN",
                "fnsp": "0005",
                "auto": "OFF",
                "nmod": "ON",
                "oson": "ON",
                "osal": "0045",
                "osau": "0315",
                "sltm": "120",
            }.get(key, default)
        )

        fan = DysonFan(mock_coordinator)
        fan._attr_percentage = 50
        fan._attr_preset_mode = "Manual"
        fan._attr_current_direction = "forward"
        fan._attr_is_on = True

        attributes = fan.extra_state_attributes

        # Verify core fan properties are exposed
        assert attributes["fan_speed"] == 50
        assert attributes["preset_mode"] == "Manual"
        assert attributes["direction"] == "forward"
        assert attributes["is_on"] is True

        # Verify device state properties
        assert attributes["fan_power"] is True
        assert attributes["fan_state"] == "FAN"
        assert attributes["fan_speed_setting"] == "0005"
        assert attributes["auto_mode"] is False
        assert attributes["night_mode"] is True

        # Verify oscillation properties
        assert attributes["oscillation_enabled"] is True
        assert attributes["angle_low"] == 45
        assert attributes["angle_high"] == 315
        assert attributes["oscillation_span"] == 270

        # Verify sleep timer
        assert attributes["sleep_timer"] == 120


class TestClimateSceneSupport:
    """Test climate entity scene support."""

    def test_climate_extra_state_attributes(self, mock_coordinator):
        """Test climate entity exposes all properties for scene support."""
        # Setup device mock return values
        mock_coordinator.device._get_current_value.side_effect = (
            lambda data, key, default: {
                "hmod": "HEAT",
                "auto": "OFF",
                "fnsp": "0005",
                "fnst": "FAN",
            }.get(key, default)
        )

        climate = DysonClimateEntity(mock_coordinator)
        climate._attr_target_temperature = 22.5
        climate._attr_hvac_mode = "auto"

        attributes = climate.extra_state_attributes

        # Verify core climate properties
        assert attributes["target_temperature"] == 22.5
        assert attributes["hvac_mode"] == "auto"

        # Verify device state properties
        assert attributes["heating_mode"] == "HEAT"
        assert attributes["auto_mode"] is False
        assert attributes["fan_power"] is True

        # Verify temperature in Kelvin for device commands
        assert attributes["target_temperature_kelvin"] == "2956"


class TestSwitchSceneSupport:
    """Test switch entities scene support."""

    def test_heating_switch_extra_state_attributes(self, mock_coordinator):
        """Test heating switch exposes properties for scene support."""
        # Setup device mock return values
        mock_coordinator.device._get_current_value.side_effect = (
            lambda data, key, default: {
                "hmod": "HEAT",
                "hmax": "2930",
            }.get(key, default)
        )

        switch = DysonHeatingSwitch(mock_coordinator)
        attributes = switch.extra_state_attributes

        assert attributes["heating_mode"] == "HEAT"
        assert attributes["heating_enabled"] is True
        assert (
            round(attributes["target_temperature"], 1) == 19.9
        )  # 2930/10 - 273.15 = 19.85
        assert attributes["target_temperature_kelvin"] == "2930"

    def test_continuous_monitoring_switch_extra_state_attributes(
        self, mock_coordinator
    ):
        """Test continuous monitoring switch exposes properties for scene support."""
        # Setup device mock return values
        mock_coordinator.device._get_current_value.side_effect = (
            lambda data, key, default: {"rhtm": "ON"}.get(key, default)
        )

        switch = DysonContinuousMonitoringSwitch(mock_coordinator)
        attributes = switch.extra_state_attributes

        assert attributes["continuous_monitoring"] is True
        assert attributes["monitoring_mode"] == "ON"


class TestSelectSceneSupport:
    """Test select entities scene support."""

    def test_oscillation_mode_select_extra_state_attributes(self, mock_coordinator):
        """Test oscillation mode select exposes properties for scene support."""
        # Setup device mock return values
        mock_coordinator.device._get_current_value.side_effect = (
            lambda data, key, default: {
                "oson": "ON",
                "osal": "0045",
                "osau": "0315",
                "ancp": "0180",
            }.get(key, default)
        )

        select = DysonOscillationModeSelect(mock_coordinator)
        select._attr_current_option = "Wide"

        attributes = select.extra_state_attributes

        assert attributes["oscillation_mode"] == "Wide"
        assert attributes["oscillation_enabled"] is True
        assert attributes["oscillation_angle_low"] == 45
        assert attributes["oscillation_angle_high"] == 315
        assert attributes["oscillation_center"] == 180
        assert attributes["oscillation_span"] == 270

    def test_heating_mode_select_extra_state_attributes(self, mock_coordinator):
        """Test heating mode select exposes properties for scene support."""
        # Setup device mock return values
        mock_coordinator.device._get_current_value.side_effect = (
            lambda data, key, default: {
                "hmod": "HEAT",
                "hmax": "2930",
            }.get(key, default)
        )

        select = DysonHeatingModeSelect(mock_coordinator)
        select._attr_current_option = "Heating"

        attributes = select.extra_state_attributes

        assert attributes["heating_mode"] == "Heating"
        assert attributes["heating_mode_raw"] == "HEAT"
        assert attributes["heating_enabled"] is True
        assert (
            round(attributes["target_temperature"], 1) == 19.9
        )  # 2930/10 - 273.15 = 19.85
        assert attributes["target_temperature_kelvin"] == "2930"


class TestNumberSceneSupport:
    """Test number entities scene support."""

    def test_sleep_timer_extra_state_attributes(self, mock_coordinator):
        """Test sleep timer number exposes properties for scene support."""
        # Setup device mock return values
        mock_coordinator.device._get_current_value.side_effect = (
            lambda data, key, default: {"sltm": "120"}.get(key, default)
        )

        number = DysonSleepTimerNumber(mock_coordinator)
        number._attr_native_value = 120

        attributes = number.extra_state_attributes

        assert attributes["sleep_timer_minutes"] == 120
        assert attributes["sleep_timer_raw"] == "120"
        assert attributes["sleep_timer_enabled"] is True


class TestSceneIntegrationSupport:
    """Test scene integration capabilities."""

    def test_comprehensive_device_state_exposure(self, mock_coordinator):
        """Test that all settable device properties are exposed across entities."""
        # Setup device mock return values for comprehensive state
        mock_coordinator.device._get_current_value.side_effect = (
            lambda data, key, default: {
                "fpwr": "ON",  # Fan power - fan entity
                "fnst": "FAN",  # Fan state - fan entity
                "fnsp": "0005",  # Fan speed - fan & climate entities
                "auto": "OFF",  # Auto mode - fan & climate entities
                "nmod": "ON",  # Night mode - fan entity
                "oson": "ON",  # Oscillation - switch & select entities
                "osal": "0045",  # Lower angle - multiple entities
                "osau": "0315",  # Upper angle - multiple entities
                "ancp": "0180",  # Center angle - select entity
                "hmod": "HEAT",  # Heating mode - climate, switch & select entities
                "hmax": "2930",  # Target temp - climate & heating entities
                "tmp": "2900",  # Current temp - climate entity
                "sltm": "120",  # Sleep timer - number entity
                "rhtm": "ON",  # Continuous monitoring - switch entity
            }.get(key, default)
        )

        # Test that all major settable properties are exposed somewhere

        # Fan entity covers: power, speed, auto mode, night mode, oscillation angles, sleep timer
        fan = DysonFan(mock_coordinator)
        fan._attr_percentage = 50
        fan._attr_preset_mode = "Manual"
        fan._attr_current_direction = "forward"
        fan._attr_is_on = True
        fan_attrs = fan.extra_state_attributes

        # Climate entity covers: heating mode, target temperature, HVAC mode, fan mode
        climate = DysonClimateEntity(mock_coordinator)
        climate._attr_target_temperature = 20.0
        climate._attr_hvac_mode = "heat"
        climate_attrs = climate.extra_state_attributes

        # Switch entities cover: heating, continuous monitoring
        # Note: Oscillation is now handled by the fan platform, not switch entities

        heat_switch = DysonHeatingSwitch(mock_coordinator)
        heat_attrs = heat_switch.extra_state_attributes

        mon_switch = DysonContinuousMonitoringSwitch(mock_coordinator)
        mon_attrs = mon_switch.extra_state_attributes

        # Select entities cover: oscillation modes, heating modes
        osc_select = DysonOscillationModeSelect(mock_coordinator)
        osc_select._attr_current_option = "Wide"
        osc_select_attrs = osc_select.extra_state_attributes

        heat_select = DysonHeatingModeSelect(mock_coordinator)
        heat_select._attr_current_option = "Heating"
        heat_select_attrs = heat_select.extra_state_attributes

        # Number entity covers: sleep timer
        timer_number = DysonSleepTimerNumber(mock_coordinator)
        timer_number._attr_native_value = 120
        timer_attrs = timer_number.extra_state_attributes

        # Verify all major device properties are covered
        covered_properties = set()

        # Collect all exposed properties
        for attrs in [
            fan_attrs,
            climate_attrs,
            heat_attrs,
            mon_attrs,
            osc_select_attrs,
            heat_select_attrs,
            timer_attrs,
        ]:
            if attrs:
                covered_properties.update(attrs.keys())

        # Essential properties that should be covered for comprehensive scene support
        essential_properties = {
            "fan_power",
            "fan_speed",
            "auto_mode",
            "night_mode",
            "oscillation_enabled",
            "oscillation_angle_low",
            "oscillation_angle_high",
            "heating_mode",
            "heating_enabled",
            "target_temperature",
            "continuous_monitoring",
            "sleep_timer_minutes",
        }

        # Verify all essential properties are exposed
        missing_properties = essential_properties - covered_properties
        assert not missing_properties, (
            f"Missing essential scene properties: {missing_properties}"
        )

        # Verify specific critical properties exist
        assert "fan_power" in fan_attrs
        assert "heating_enabled" in heat_attrs
        assert "oscillation_enabled" in fan_attrs  # Oscillation is now in fan platform
        assert "target_temperature" in climate_attrs
        assert "sleep_timer_minutes" in timer_attrs
