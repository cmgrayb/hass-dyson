"""Tests for legacy Dyson filf filter-life telemetry."""

from unittest.mock import MagicMock, patch

from custom_components.hass_dyson.binary_sensor import DysonFilterReplacementSensor
from custom_components.hass_dyson.sensor import DysonHEPAFilterTypeSensor


def test_legacy_filter_type_is_unknown() -> None:
    """Test omitted hflt is not reported as not installed."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-LEGACY-001"
    coordinator.data = {"product-state": {"filf": "4300"}}
    coordinator.device = MagicMock()
    sensor = DysonHEPAFilterTypeSensor(coordinator)

    with patch.object(sensor, "async_write_ha_state"):
        sensor._handle_coordinator_update()

    assert sensor._attr_native_value is None


def test_explicit_none_filter_type_is_not_installed() -> None:
    """Test explicit hflt NONE remains not installed."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-LEGACY-002"
    coordinator.data = {"product-state": {"hflt": "NONE", "filf": "4300"}}
    coordinator.device = MagicMock()
    sensor = DysonHEPAFilterTypeSensor(coordinator)

    with patch.object(sensor, "async_write_ha_state"):
        sensor._handle_coordinator_update()

    assert sensor._attr_native_value == "Not Installed"


def test_explicit_none_filter_type_skips_legacy_replacement_check() -> None:
    """Test an explicit no-filter type overrides stale legacy life telemetry."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-LEGACY-004"
    coordinator.data = {"product-state": {"hflt": "NONE", "filf": "0000"}}
    coordinator.device.hepa_filter_life = 0
    sensor = DysonFilterReplacementSensor(coordinator)

    with patch.object(sensor, "async_write_ha_state"):
        sensor._handle_coordinator_update()

    assert sensor.is_on is False


def test_legacy_filter_life_triggers_replacement() -> None:
    """Test legacy filf data is evaluated without an hflt field."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-LEGACY-003"
    coordinator.data = {"product-state": {"filf": "0000"}}
    coordinator.device.hepa_filter_life = 0
    sensor = DysonFilterReplacementSensor(coordinator)

    with patch.object(sensor, "async_write_ha_state"):
        sensor._handle_coordinator_update()

    assert sensor.is_on is True
