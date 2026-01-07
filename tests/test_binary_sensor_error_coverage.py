"""Error coverage tests for binary sensor platform.

This module focuses on testing error handling paths in binary sensor entities
to improve code coverage for binary_sensor.py module.
"""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.hass_dyson.binary_sensor import (
    DysonFaultSensor,
    DysonFilterReplacementSensor,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for binary sensor tests."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-SERIAL-123"
    coordinator.device = MagicMock()
    coordinator.data = {"product-state": {}}
    coordinator.device_capabilities = []
    coordinator.device_category = "ec"
    return coordinator


class TestFilterReplacementSensorErrorHandling:
    """Test error handling in filter replacement sensor."""

    def test_handle_coordinator_update_no_device(self, mock_coordinator):
        """Test _handle_coordinator_update when device is None."""
        sensor = DysonFilterReplacementSensor(mock_coordinator)
        mock_coordinator.device = None

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor.is_on is False

    def test_handle_coordinator_update_no_coordinator_data(self, mock_coordinator):
        """Test _handle_coordinator_update with no coordinator data."""
        sensor = DysonFilterReplacementSensor(mock_coordinator)
        mock_coordinator.data = None

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor.is_on is False

    def test_handle_coordinator_update_non_dict_product_state(self, mock_coordinator):
        """Test _handle_coordinator_update with non-dict product-state."""
        sensor = DysonFilterReplacementSensor(mock_coordinator)
        mock_coordinator.data = {"product-state": "invalid"}

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor.is_on is False

    def test_handle_coordinator_update_invalid_hepa_life_type(self, mock_coordinator):
        """Test _handle_coordinator_update with invalid HEPA filter life type."""
        sensor = DysonFilterReplacementSensor(mock_coordinator)
        mock_coordinator.data = {"product-state": {"hflt": "COMB"}}
        mock_coordinator.device.hepa_filter_life = "invalid"  # String instead of number

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Should handle invalid data gracefully
        assert sensor.is_on is False

    def test_handle_coordinator_update_none_hepa_life(self, mock_coordinator):
        """Test _handle_coordinator_update with None HEPA filter life."""
        sensor = DysonFilterReplacementSensor(mock_coordinator)
        mock_coordinator.data = {"product-state": {"hflt": "COMB"}}
        mock_coordinator.device.hepa_filter_life = None

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor.is_on is False

    def test_handle_coordinator_update_exception_getting_hepa_life(
        self, mock_coordinator
    ):
        """Test _handle_coordinator_update with exception accessing HEPA filter life."""
        sensor = DysonFilterReplacementSensor(mock_coordinator)
        mock_coordinator.data = {"product-state": {"hflt": "COMB"}}

        # Configure device to raise exception when accessing hepa_filter_life
        type(mock_coordinator.device).hepa_filter_life = property(
            lambda self: (_ for _ in ()).throw(AttributeError("Property not available"))
        )

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Should handle exception gracefully
        assert sensor.is_on is False

    def test_handle_coordinator_update_generic_exception(self, mock_coordinator):
        """Test _handle_coordinator_update with generic exception."""
        sensor = DysonFilterReplacementSensor(mock_coordinator)

        # Make coordinator.device raise exception
        mock_coordinator.device = MagicMock(side_effect=Exception("Unexpected error"))

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Should handle exception gracefully and set to False
        assert sensor.is_on is False

    def test_handle_coordinator_update_hepa_filter_below_threshold(
        self, mock_coordinator
    ):
        """Test _handle_coordinator_update with HEPA filter below 10%."""
        sensor = DysonFilterReplacementSensor(mock_coordinator)
        mock_coordinator.data = {"product-state": {"hflt": "COMB"}}
        mock_coordinator.device.hepa_filter_life = 5

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor.is_on is True

    def test_handle_coordinator_update_hepa_filter_above_threshold(
        self, mock_coordinator
    ):
        """Test _handle_coordinator_update with HEPA filter above 10%."""
        sensor = DysonFilterReplacementSensor(mock_coordinator)
        mock_coordinator.data = {"product-state": {"hflt": "COMB"}}
        mock_coordinator.device.hepa_filter_life = 50

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor.is_on is False

    def test_handle_coordinator_update_no_filters_installed(self, mock_coordinator):
        """Test _handle_coordinator_update with no filters installed."""
        sensor = DysonFilterReplacementSensor(mock_coordinator)
        mock_coordinator.data = {"product-state": {"hflt": "NONE"}}

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor.is_on is False


class TestFaultSensorErrorHandling:
    """Test error handling in fault sensor."""

    def test_handle_coordinator_update_no_device(self, mock_coordinator):
        """Test _handle_coordinator_update when device is None."""
        fault_info = {"FAIL": "Air quality sensor failure"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)
        mock_coordinator.device = None

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor.is_on is False
        assert sensor.extra_state_attributes == {}

    def test_handle_coordinator_update_fault_not_relevant(self, mock_coordinator):
        """Test _handle_coordinator_update with non-relevant fault code."""
        fault_info = {"FAIL": "Brush motor failure"}
        sensor = DysonFaultSensor(mock_coordinator, "brsh", fault_info)
        mock_coordinator.device_category = "ec"  # EC devices don't have brushes

        with (
            patch.object(sensor, "async_write_ha_state"),
            patch(
                "custom_components.hass_dyson.binary_sensor._is_fault_code_relevant",
                return_value=False,
            ),
        ):
            sensor._handle_coordinator_update()

        assert sensor._attr_available is False
        assert sensor.is_on is False
        assert "Not applicable" in sensor.extra_state_attributes.get("status", "")

    def test_handle_coordinator_update_no_faults_data(self, mock_coordinator):
        """Test _handle_coordinator_update with no faults data."""
        fault_info = {"FAIL": "Air quality sensor failure"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)
        mock_coordinator.device._faults_data = None

        with (
            patch.object(sensor, "async_write_ha_state"),
            patch(
                "custom_components.hass_dyson.binary_sensor._is_fault_code_relevant",
                return_value=True,
            ),
        ):
            sensor._handle_coordinator_update()

        assert sensor.is_on is False

    def test_handle_coordinator_update_exception_during_update(self, mock_coordinator):
        """Test _handle_coordinator_update with exception."""
        fault_info = {"FAIL": "Sensor failure"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)

        # Make _faults_data a property that doesn't exist (AttributeError)
        del mock_coordinator.device._faults_data

        with (
            patch.object(sensor, "async_write_ha_state"),
            patch(
                "custom_components.hass_dyson.binary_sensor._is_fault_code_relevant",
                return_value=True,
            ),
        ):
            sensor._handle_coordinator_update()

        assert sensor.is_on is False
        # When exception occurs, attributes should be empty or have status "No data"
        # The actual behavior sets status to "No data" when fault not found
        assert (
            sensor.extra_state_attributes.get("status") in ["No data", None]
            or sensor.extra_state_attributes == {}
        )

    def test_handle_coordinator_update_fault_found_fail(self, mock_coordinator):
        """Test _handle_coordinator_update with FAIL fault found."""
        fault_info = {"FAIL": "Air quality sensor failure"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)
        mock_coordinator.device._faults_data = {"product-errors": {"aqs": "FAIL"}}

        with (
            patch.object(sensor, "async_write_ha_state"),
            patch(
                "custom_components.hass_dyson.binary_sensor._is_fault_code_relevant",
                return_value=True,
            ),
        ):
            sensor._handle_coordinator_update()

        assert sensor.is_on is True
        assert sensor.extra_state_attributes["fault_value"] == "FAIL"
        assert sensor.extra_state_attributes["severity"] == "Critical"

    def test_handle_coordinator_update_fault_found_warn(self, mock_coordinator):
        """Test _handle_coordinator_update with WARN fault found."""
        fault_info = {"WARN": "Temperature sensor warning"}
        sensor = DysonFaultSensor(mock_coordinator, "temp", fault_info)
        mock_coordinator.device._faults_data = {"product-warnings": {"temp": "WARN"}}

        with (
            patch.object(sensor, "async_write_ha_state"),
            patch(
                "custom_components.hass_dyson.binary_sensor._is_fault_code_relevant",
                return_value=True,
            ),
        ):
            sensor._handle_coordinator_update()

        assert sensor.is_on is True
        assert sensor.extra_state_attributes["fault_value"] == "WARN"
        assert sensor.extra_state_attributes["severity"] == "Warning"

    def test_handle_coordinator_update_fault_found_chng(self, mock_coordinator):
        """Test _handle_coordinator_update with CHNG (change/maintenance) fault."""
        fault_info = {"CHNG": "Filter needs changing"}
        sensor = DysonFaultSensor(mock_coordinator, "fltr", fault_info)
        mock_coordinator.device._faults_data = {"product-warnings": {"fltr": "CHNG"}}

        with (
            patch.object(sensor, "async_write_ha_state"),
            patch(
                "custom_components.hass_dyson.binary_sensor._is_fault_code_relevant",
                return_value=True,
            ),
        ):
            sensor._handle_coordinator_update()

        assert sensor.is_on is True
        assert sensor.extra_state_attributes["fault_value"] == "CHNG"
        assert sensor.extra_state_attributes["severity"] == "Maintenance"

    def test_handle_coordinator_update_fault_value_ok(self, mock_coordinator):
        """Test _handle_coordinator_update with OK fault value."""
        fault_info = {"OK": "System OK"}
        sensor = DysonFaultSensor(mock_coordinator, "sys", fault_info)
        mock_coordinator.device._faults_data = {"product-errors": {"sys": "OK"}}

        with (
            patch.object(sensor, "async_write_ha_state"),
            patch(
                "custom_components.hass_dyson.binary_sensor._is_fault_code_relevant",
                return_value=True,
            ),
        ):
            sensor._handle_coordinator_update()

        assert sensor.is_on is False
        assert sensor.extra_state_attributes["status"] == "OK"

    def test_handle_coordinator_update_fault_value_none(self, mock_coordinator):
        """Test _handle_coordinator_update with NONE fault value."""
        fault_info = {"NONE": "No fault"}
        sensor = DysonFaultSensor(mock_coordinator, "sys", fault_info)
        mock_coordinator.device._faults_data = {"product-errors": {"sys": "NONE"}}

        with (
            patch.object(sensor, "async_write_ha_state"),
            patch(
                "custom_components.hass_dyson.binary_sensor._is_fault_code_relevant",
                return_value=True,
            ),
        ):
            sensor._handle_coordinator_update()

        assert sensor.is_on is False

    def test_handle_coordinator_update_fault_not_found(self, mock_coordinator):
        """Test _handle_coordinator_update with fault code not in data."""
        fault_info = {"FAIL": "Sensor failure"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)
        mock_coordinator.device._faults_data = {"product-errors": {"other": "FAIL"}}

        with (
            patch.object(sensor, "async_write_ha_state"),
            patch(
                "custom_components.hass_dyson.binary_sensor._is_fault_code_relevant",
                return_value=True,
            ),
        ):
            sensor._handle_coordinator_update()

        assert sensor.is_on is False
        assert sensor.extra_state_attributes["status"] == "No data"

    def test_search_fault_in_data_product_errors(self, mock_coordinator):
        """Test _search_fault_in_data finding fault in product-errors."""
        fault_info = {"FAIL": "Fault"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)

        fault_data = {"product-errors": {"aqs": "FAIL"}}
        found, value = sensor._search_fault_in_data(fault_data)

        assert found is True
        assert value == "FAIL"

    def test_search_fault_in_data_module_warnings(self, mock_coordinator):
        """Test _search_fault_in_data finding fault in module-warnings."""
        fault_info = {"WARN": "Warning"}
        sensor = DysonFaultSensor(mock_coordinator, "temp", fault_info)

        fault_data = {"module-warnings": {"temp": "WARN"}}
        found, value = sensor._search_fault_in_data(fault_data)

        assert found is True
        assert value == "WARN"

    def test_search_fault_in_data_top_level(self, mock_coordinator):
        """Test _search_fault_in_data finding fault at top level."""
        fault_info = {"FAIL": "Fault"}
        sensor = DysonFaultSensor(mock_coordinator, "sys", fault_info)

        fault_data = {"sys": "FAIL"}
        found, value = sensor._search_fault_in_data(fault_data)

        assert found is True
        assert value == "FAIL"

    def test_search_fault_in_data_not_found(self, mock_coordinator):
        """Test _search_fault_in_data when fault not found."""
        fault_info = {"FAIL": "Fault"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)

        fault_data = {"product-errors": {"other": "FAIL"}}
        found, value = sensor._search_fault_in_data(fault_data)

        assert found is False
        assert value == ""

    def test_get_fault_severity_critical(self, mock_coordinator):
        """Test _get_fault_severity for critical faults."""
        fault_info = {"FAIL": "Fault"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)

        assert sensor._get_fault_severity("FAIL") == "Critical"
        assert sensor._get_fault_severity("STLL") == "Critical"

    def test_get_fault_severity_warning(self, mock_coordinator):
        """Test _get_fault_severity for warning faults."""
        fault_info = {"WARN": "Warning"}
        sensor = DysonFaultSensor(mock_coordinator, "temp", fault_info)

        assert sensor._get_fault_severity("WARN") == "Warning"
        assert sensor._get_fault_severity("HIGH") == "Warning"
        assert sensor._get_fault_severity("LOW") == "Warning"

    def test_get_fault_severity_maintenance(self, mock_coordinator):
        """Test _get_fault_severity for maintenance faults."""
        fault_info = {"CHNG": "Change"}
        sensor = DysonFaultSensor(mock_coordinator, "fltr", fault_info)

        assert sensor._get_fault_severity("CHNG") == "Maintenance"
        assert sensor._get_fault_severity("FULL") == "Maintenance"
        assert sensor._get_fault_severity("WORN") == "Maintenance"

    def test_get_fault_severity_unknown(self, mock_coordinator):
        """Test _get_fault_severity for unknown fault values."""
        fault_info = {"UNKNOWN": "Unknown"}
        sensor = DysonFaultSensor(mock_coordinator, "sys", fault_info)

        assert sensor._get_fault_severity("UNKNOWN") == "Unknown"

    def test_get_fault_icon_aqs_fault(self, mock_coordinator):
        """Test _get_fault_icon for AQS sensor with fault."""
        fault_info = {"FAIL": "Fault"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)

        icon = sensor._get_fault_icon(is_fault=True)
        assert icon == "mdi:air-purifier-off"

    def test_get_fault_icon_aqs_no_fault(self, mock_coordinator):
        """Test _get_fault_icon for AQS sensor without fault."""
        fault_info = {"OK": "OK"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)

        icon = sensor._get_fault_icon(is_fault=False)
        assert icon == "mdi:air-purifier"

    def test_get_fault_icon_filter(self, mock_coordinator):
        """Test _get_fault_icon for filter faults."""
        fault_info = {"FAIL": "Fault"}
        sensor = DysonFaultSensor(mock_coordinator, "fltr", fault_info)

        icon = sensor._get_fault_icon(is_fault=True)
        assert icon == "mdi:air-filter"

    def test_get_fault_icon_unknown_fault(self, mock_coordinator):
        """Test _get_fault_icon for unknown fault codes."""
        fault_info = {"FAIL": "Fault"}
        sensor = DysonFaultSensor(mock_coordinator, "unknown", fault_info)

        icon = sensor._get_fault_icon(is_fault=True)
        assert icon == "mdi:alert"

    def test_icon_property_with_fault(self, mock_coordinator):
        """Test icon property when sensor has fault."""
        fault_info = {"FAIL": "Fault"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)
        sensor._attr_is_on = True

        icon = sensor.icon
        assert icon == "mdi:air-purifier-off"

    def test_icon_property_without_fault(self, mock_coordinator):
        """Test icon property when sensor has no fault."""
        fault_info = {"OK": "OK"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)
        sensor._attr_is_on = False

        icon = sensor.icon
        assert icon == "mdi:air-purifier"

    def test_icon_property_none_state(self, mock_coordinator):
        """Test icon property when sensor state is None."""
        fault_info = {"UNKNOWN": "Unknown"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)
        sensor._attr_is_on = None

        icon = sensor.icon
        assert icon == "mdi:air-purifier"

    def test_get_fault_friendly_name_known_codes(self, mock_coordinator):
        """Test _get_fault_friendly_name for known fault codes."""
        known_codes = {
            "aqs": "Air Quality Sensor",
            "fltr": "Filter",
            "brsh": "Brush",
            "wifi": "WiFi Connection",
        }

        for code, expected_name in known_codes.items():
            fault_info = {"FAIL": "Fault"}
            sensor = DysonFaultSensor(mock_coordinator, code, fault_info)
            assert sensor._get_fault_friendly_name() == expected_name

    def test_get_fault_friendly_name_unknown_code(self, mock_coordinator):
        """Test _get_fault_friendly_name for unknown fault code."""
        fault_info = {"FAIL": "Fault"}
        sensor = DysonFaultSensor(mock_coordinator, "xyz", fault_info)

        name = sensor._get_fault_friendly_name()
        assert name == "XYZ"
