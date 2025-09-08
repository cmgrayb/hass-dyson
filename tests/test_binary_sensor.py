"""Tests for the binary sensor platform."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import EntityCategory

from custom_components.hass_dyson.binary_sensor import (
    DysonFaultSensor,
    DysonFilterReplacementSensor,
    _is_fault_code_for_capability,
    _is_fault_code_for_category,
    _is_fault_code_relevant,
    _normalize_capabilities,
    _normalize_categories,
    async_setup_entry,
)
from custom_components.hass_dyson.const import CONF_HOSTNAME


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = Mock()
    coordinator.serial_number = "NK6-EU-MHA0000A"
    coordinator.device_name = "Test Device"
    coordinator.device_category = ["ec"]
    coordinator.device_capabilities = ["extended_aq", "heating"]
    coordinator.device = Mock()
    coordinator.data = {
        "product-state": {
            "filf": "2500",  # HEPA filter life
            "corf": "1000",  # Carbon filter life
            "fmod": "AUTO",  # Filter mode
        }
    }
    coordinator.config_entry = Mock()
    coordinator.config_entry.data = {CONF_HOSTNAME: "192.168.1.100"}
    return coordinator


class TestBinarySensorPlatformSetup:
    """Test binary sensor platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_basic_sensors(self, mock_coordinator):
        """Test setup creates basic binary sensors."""
        mock_add_entities = AsyncMock()
        mock_hass = Mock()
        mock_config_entry = Mock()
        mock_config_entry.entry_id = "test_entry"

        mock_hass.data = {"hass-dyson": {"test_entry": mock_coordinator}}

        with patch(
            "custom_components.hass_dyson.binary_sensor.FAULT_TRANSLATIONS",
            {"aqs": {"FAIL": "Air quality sensor failed"}},
        ):
            result = await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        assert result is True
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]

        # Should create filter replacement sensor + fault sensors
        assert len(entities) >= 1
        assert any(isinstance(entity, DysonFilterReplacementSensor) for entity in entities)

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_fault_sensors(self, mock_coordinator):
        """Test setup creates fault sensors for relevant fault codes."""
        mock_add_entities = AsyncMock()
        mock_hass = Mock()
        mock_config_entry = Mock()
        mock_config_entry.entry_id = "test_entry"

        mock_hass.data = {"hass-dyson": {"test_entry": mock_coordinator}}

        fault_translations = {
            "aqs": {"FAIL": "Air quality sensor failed"},
            "fltr": {"WORN": "Filter worn out"},
        }

        with patch("custom_components.hass_dyson.binary_sensor.FAULT_TRANSLATIONS", fault_translations):
            with patch("custom_components.hass_dyson.binary_sensor._is_fault_code_relevant", return_value=True):
                result = await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        assert result is True
        entities = mock_add_entities.call_args[0][0]

        # Should have filter replacement + 2 fault sensors
        fault_sensors = [e for e in entities if isinstance(e, DysonFaultSensor)]
        assert len(fault_sensors) == 2


class TestFaultCodeRelevance:
    """Test fault code relevance checking functions."""

    def test_normalize_categories_with_enum_objects(self):
        """Test normalizing categories with enum-like objects."""
        mock_category = Mock()
        mock_category.value = "ec"

        result = _normalize_categories([mock_category])
        assert result == ["ec"]

    def test_normalize_categories_with_strings(self):
        """Test normalizing categories with string objects."""
        result = _normalize_categories(["ec", "robot"])
        assert result == ["ec", "robot"]

    def test_normalize_categories_single_enum(self):
        """Test normalizing single category with enum."""
        mock_category = Mock()
        mock_category.value = "vacuum"

        result = _normalize_categories(mock_category)
        assert result == ["vacuum"]

    def test_normalize_categories_single_string(self):
        """Test normalizing single category with string."""
        result = _normalize_categories("purifier")
        assert result == ["purifier"]

    def test_normalize_capabilities_with_enum_objects(self):
        """Test normalizing capabilities with enum-like objects."""
        mock_cap1 = Mock()
        mock_cap1.value = "extended_aq"
        mock_cap2 = Mock()
        mock_cap2.value = "heating"

        result = _normalize_capabilities([mock_cap1, mock_cap2])
        assert result == ["extended_aq", "heating"]

    def test_normalize_capabilities_with_strings(self):
        """Test normalizing capabilities with strings."""
        result = _normalize_capabilities(["extended_aq", "heating"])
        assert result == ["extended_aq", "heating"]

    def test_is_fault_code_for_category_match(self):
        """Test fault code category matching."""
        with patch("custom_components.hass_dyson.binary_sensor.DEVICE_CATEGORY_FAULT_CODES", {"ec": ["aqs", "fltr"]}):
            result = _is_fault_code_for_category("aqs", ["ec"])
            assert result is True

    def test_is_fault_code_for_category_no_match(self):
        """Test fault code category no match."""
        with patch("custom_components.hass_dyson.binary_sensor.DEVICE_CATEGORY_FAULT_CODES", {"ec": ["aqs", "fltr"]}):
            result = _is_fault_code_for_category("wifi", ["ec"])
            assert result is False

    def test_is_fault_code_for_capability_match(self):
        """Test fault code capability matching."""
        with patch(
            "custom_components.hass_dyson.binary_sensor.CAPABILITY_FAULT_CODES", {"extended_aq": ["aqs", "temp"]}
        ):
            result = _is_fault_code_for_capability("aqs", ["extended_aq"])
            assert result is True

    def test_is_fault_code_for_capability_no_match(self):
        """Test fault code capability no match."""
        with patch(
            "custom_components.hass_dyson.binary_sensor.CAPABILITY_FAULT_CODES", {"extended_aq": ["aqs", "temp"]}
        ):
            result = _is_fault_code_for_capability("wifi", ["extended_aq"])
            assert result is False

    def test_is_fault_code_relevant_category_match(self):
        """Test fault code relevance via category match."""
        with patch("custom_components.hass_dyson.binary_sensor._is_fault_code_for_category", return_value=True):
            with patch("custom_components.hass_dyson.binary_sensor._is_fault_code_for_capability", return_value=False):
                result = _is_fault_code_relevant("aqs", ["ec"], ["heating"])
                assert result is True

    def test_is_fault_code_relevant_capability_match(self):
        """Test fault code relevance via capability match."""
        with patch("custom_components.hass_dyson.binary_sensor._is_fault_code_for_category", return_value=False):
            with patch("custom_components.hass_dyson.binary_sensor._is_fault_code_for_capability", return_value=True):
                result = _is_fault_code_relevant("temp", ["unknown"], ["extended_aq"])
                assert result is True

    def test_is_fault_code_relevant_no_match(self):
        """Test fault code relevance with no matches."""
        with patch("custom_components.hass_dyson.binary_sensor._is_fault_code_for_category", return_value=False):
            with patch("custom_components.hass_dyson.binary_sensor._is_fault_code_for_capability", return_value=False):
                result = _is_fault_code_relevant("unknown", ["unknown"], ["unknown"])
                assert result is False

    def test_is_fault_code_relevant_exception_handling(self):
        """Test fault code relevance with exception returns True."""
        with patch(
            "custom_components.hass_dyson.binary_sensor._normalize_categories", side_effect=Exception("Test error")
        ):
            result = _is_fault_code_relevant("aqs", ["ec"], ["heating"])
            assert result is True


class TestDysonFilterReplacementSensor:
    """Test filter replacement binary sensor."""

    def test_initialization(self, mock_coordinator):
        """Test filter replacement sensor initialization."""
        sensor = DysonFilterReplacementSensor(mock_coordinator)

        assert sensor._attr_unique_id == "NK6-EU-MHA0000A_filter_replacement"
        assert sensor._attr_name == "Test Device Filter Replacement"
        assert sensor._attr_device_class == BinarySensorDeviceClass.PROBLEM
        assert sensor._attr_icon == "mdi:air-filter"

    def test_handle_coordinator_update_hepa_filter_low(self, mock_coordinator):
        """Test coordinator update with low HEPA filter."""
        mock_coordinator.data = {
            "product-state": {
                "hflr": "500",  # Low HEPA filter life (< 10%)
                "hflt": "GCOM",  # HEPA filter type
            }
        }

        # Mock the device filter life properties
        mock_coordinator.device.hepa_filter_life = 5  # 5% remaining

        sensor = DysonFilterReplacementSensor(mock_coordinator)
        sensor.hass = Mock()  # Mock the hass attribute to avoid RuntimeError
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_is_on is True
        # Filter replacement sensor doesn't provide detailed extra state attributes

    def test_handle_coordinator_update_carbon_filter_low(self, mock_coordinator):
        """Test coordinator update with low carbon filter (currently not supported)."""
        mock_coordinator.data = {
            "product-state": {
                "hflr": "5000",  # Good HEPA filter life
                "cflr": "100",  # Low carbon filter life (< 10%)
                "hflt": "GCOM",  # HEPA filter type
                "cflt": "GCOM",  # Carbon filter type
            }
        }

        # Mock device filter properties
        mock_coordinator.device.hepa_filter_life = 50  # 50% remaining
        mock_coordinator.device.carbon_filter_life = 5  # 5% remaining

        sensor = DysonFilterReplacementSensor(mock_coordinator)
        sensor.hass = Mock()  # Mock hass to avoid RuntimeError
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Since carbon filter support is commented out, only HEPA is checked
        # HEPA is at 50% so no replacement needed
        assert sensor._attr_is_on is False

    def test_handle_coordinator_update_both_filters_low(self, mock_coordinator):
        """Test coordinator update with both filters low (carbon filter not supported)."""
        mock_coordinator.data = {
            "product-state": {
                "hflr": "500",  # Low HEPA filter life
                "cflr": "100",  # Low carbon filter life
                "hflt": "GCOM",  # HEPA filter type
                "cflt": "GCOM",  # Carbon filter type
            }
        }

        # Mock device filter properties
        mock_coordinator.device.hepa_filter_life = 5  # 5% remaining
        mock_coordinator.device.carbon_filter_life = 1  # 1% remaining

        sensor = DysonFilterReplacementSensor(mock_coordinator)
        sensor.hass = Mock()
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_is_on is True
        # Filter replacement sensor doesn't provide detailed extra state attributes
        # Carbon filter support is commented out, so only HEPA will be mentioned

    def test_handle_coordinator_update_no_device(self, mock_coordinator):
        """Test coordinator update with no device."""
        mock_coordinator.device = None

        sensor = DysonFilterReplacementSensor(mock_coordinator)
        sensor.hass = Mock()
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_is_on is False
        # Filter replacement sensor doesn't set extra state attributes when no device

    def test_handle_coordinator_update_no_data(self, mock_coordinator):
        """Test coordinator update with no data."""
        mock_coordinator.data = None

        sensor = DysonFilterReplacementSensor(mock_coordinator)
        sensor.hass = Mock()
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_is_on is False

    def test_handle_coordinator_update_invalid_data_structure(self, mock_coordinator):
        """Test coordinator update with invalid data structure."""
        mock_coordinator.data = {"product-state": "invalid_string_not_dict"}

        sensor = DysonFilterReplacementSensor(mock_coordinator)
        sensor.hass = Mock()

        with patch("custom_components.hass_dyson.binary_sensor._LOGGER") as mock_logger:
            with patch.object(sensor, "async_write_ha_state"):
                sensor._handle_coordinator_update()
            mock_logger.warning.assert_called()

        assert sensor._attr_is_on is False

    def test_handle_coordinator_update_hepa_only_filter(self, mock_coordinator):
        """Test coordinator update with HEPA-only filter."""
        mock_coordinator.data = {
            "product-state": {
                "hflr": "500",  # Low HEPA filter life
                "hflt": "GCOM",  # HEPA filter type
            }
        }

        # Mock device filter properties
        mock_coordinator.device.hepa_filter_life = 5  # 5% remaining

        sensor = DysonFilterReplacementSensor(mock_coordinator)
        sensor.hass = Mock()
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_is_on is True
        # Filter replacement sensor doesn't provide detailed extra state attributes

    def test_handle_coordinator_update_filters_good(self, mock_coordinator):
        """Test coordinator update with good filter life."""
        mock_coordinator.data = {
            "product-state": {
                "filf": "5000",  # Good HEPA filter life
                "corf": "3000",  # Good carbon filter life
                "filt": "COMB.1",
            }
        }

        sensor = DysonFilterReplacementSensor(mock_coordinator)
        sensor.hass = Mock()
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_is_on is False


class TestDysonFaultSensor:
    """Test fault binary sensor."""

    def test_initialization(self, mock_coordinator):
        """Test fault sensor initialization."""
        fault_info = {"FAIL": "Air quality sensor failed"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)

        assert sensor._attr_unique_id == "NK6-EU-MHA0000A_fault_aqs"
        assert sensor._attr_name == "Test Device Fault Air Quality Sensor"
        assert sensor._attr_device_class == BinarySensorDeviceClass.PROBLEM
        assert sensor._attr_entity_category == EntityCategory.DIAGNOSTIC
        assert sensor._fault_code == "aqs"
        assert sensor._fault_info == fault_info

    def test_get_fault_friendly_name_known_codes(self, mock_coordinator):
        """Test friendly name generation for known fault codes."""
        fault_info = {"FAIL": "Failed"}

        test_cases = [
            ("aqs", "Air Quality Sensor"),
            ("fltr", "Filter"),
            ("hflr", "HEPA Filter"),
            ("temp", "Temperature Sensor"),
            ("wifi", "WiFi Connection"),
        ]

        for fault_code, expected_name in test_cases:
            sensor = DysonFaultSensor(mock_coordinator, fault_code, fault_info)
            assert sensor._get_fault_friendly_name() == expected_name

    def test_get_fault_friendly_name_unknown_code(self, mock_coordinator):
        """Test friendly name generation for unknown fault codes."""
        fault_info = {"FAIL": "Failed"}
        sensor = DysonFaultSensor(mock_coordinator, "xyz", fault_info)

        assert sensor._get_fault_friendly_name() == "XYZ"

    def test_get_fault_icon_air_quality_sensor(self, mock_coordinator):
        """Test icon selection for air quality sensor."""
        fault_info = {"FAIL": "Failed"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)

        # Normal state
        assert sensor._get_fault_icon(is_fault=False) == "mdi:air-purifier"
        # Fault state
        assert sensor._get_fault_icon(is_fault=True) == "mdi:air-purifier-off"

    def test_get_fault_icon_other_sensors(self, mock_coordinator):
        """Test icon selection for other sensor types."""
        fault_info = {"FAIL": "Failed"}

        test_cases = [
            ("fltr", "mdi:air-filter"),
            ("temp", "mdi:thermometer-alert"),
            ("wifi", "mdi:wifi-off"),
            ("pwr", "mdi:power-plug-off"),
            ("unknown", "mdi:alert"),
        ]

        for fault_code, expected_icon in test_cases:
            sensor = DysonFaultSensor(mock_coordinator, fault_code, fault_info)
            assert sensor._get_fault_icon() == expected_icon

    def test_icon_property(self, mock_coordinator):
        """Test icon property returns correct icon based on state."""
        fault_info = {"FAIL": "Failed"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)

        # Test with fault state
        sensor._attr_is_on = True
        assert sensor.icon == "mdi:air-purifier-off"

        # Test with normal state
        sensor._attr_is_on = False
        assert sensor.icon == "mdi:air-purifier"

    def test_handle_coordinator_update_no_device(self, mock_coordinator):
        """Test coordinator update with no device."""
        mock_coordinator.device = None
        fault_info = {"FAIL": "Failed"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)
        sensor.hass = Mock()

        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        assert sensor._attr_is_on is False
        assert sensor._attr_extra_state_attributes == {}

    def test_handle_coordinator_update_irrelevant_fault(self, mock_coordinator):
        """Test coordinator update with irrelevant fault code."""
        fault_info = {"FAIL": "Failed"}
        sensor = DysonFaultSensor(mock_coordinator, "irrelevant", fault_info)
        sensor.hass = Mock()

        with patch("custom_components.hass_dyson.binary_sensor._is_fault_code_relevant", return_value=False):
            with patch.object(sensor, "async_write_ha_state"):
                sensor._handle_coordinator_update()

        assert sensor._attr_available is False
        assert sensor._attr_is_on is False
        assert "Not applicable" in sensor._attr_extra_state_attributes["status"]

    def test_handle_coordinator_update_fault_detected(self, mock_coordinator):
        """Test coordinator update with fault detected."""
        mock_coordinator.device._faults_data = {"product-errors": {"aqs": "FAIL"}}

        fault_info = {"FAIL": "Air quality sensor failed"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)
        sensor.hass = Mock()

        with patch("custom_components.hass_dyson.binary_sensor._is_fault_code_relevant", return_value=True):
            with patch.object(sensor, "async_write_ha_state"):
                sensor._handle_coordinator_update()

        assert sensor._attr_available is True
        assert sensor._attr_is_on is True
        assert sensor._attr_extra_state_attributes["fault_code"] == "aqs"
        assert sensor._attr_extra_state_attributes["fault_value"] == "FAIL"
        assert sensor._attr_extra_state_attributes["description"] == "Air quality sensor failed"

    def test_handle_coordinator_update_fault_ok(self, mock_coordinator):
        """Test coordinator update with fault showing OK."""
        mock_coordinator.device._faults_data = {"product-errors": {"aqs": "OK"}}

        fault_info = {"FAIL": "Air quality sensor failed"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)
        sensor.hass = Mock()

        with patch("custom_components.hass_dyson.binary_sensor._is_fault_code_relevant", return_value=True):
            with patch.object(sensor, "async_write_ha_state"):
                sensor._handle_coordinator_update()

        assert sensor._attr_available is True
        assert sensor._attr_is_on is False
        assert sensor._attr_extra_state_attributes["status"] == "OK"

    def test_handle_coordinator_update_no_fault_data(self, mock_coordinator):
        """Test coordinator update with no fault data."""
        mock_coordinator.device._faults_data = None

        fault_info = {"FAIL": "Failed"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)
        sensor.hass = Mock()

        with patch("custom_components.hass_dyson.binary_sensor._is_fault_code_relevant", return_value=True):
            with patch.object(sensor, "async_write_ha_state"):
                sensor._handle_coordinator_update()

        assert sensor._attr_available is True
        assert sensor._attr_is_on is False
        assert sensor._attr_extra_state_attributes == {}

    def test_handle_coordinator_update_exception(self, mock_coordinator):
        """Test coordinator update with exception."""
        mock_coordinator.device._faults_data = {"test": "data"}  # Need data to trigger the exception path
        fault_info = {"FAIL": "Failed"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)
        sensor.hass = Mock()

        with patch("custom_components.hass_dyson.binary_sensor._is_fault_code_relevant", return_value=True):
            with patch.object(sensor, "_search_fault_in_data", side_effect=Exception("Test error")):
                with patch("custom_components.hass_dyson.binary_sensor._LOGGER") as mock_logger:
                    with patch.object(sensor, "async_write_ha_state"):
                        sensor._handle_coordinator_update()
                    mock_logger.warning.assert_called_once()

        assert sensor._attr_is_on is False
        assert sensor._attr_extra_state_attributes == {}

    def test_search_fault_in_data_product_errors(self, mock_coordinator):
        """Test searching fault in product-errors section."""
        fault_info = {"FAIL": "Failed"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)

        fault_data = {"product-errors": {"aqs": "FAIL"}}

        found, value = sensor._search_fault_in_data(fault_data)
        assert found is True
        assert value == "FAIL"

    def test_search_fault_in_data_module_warnings(self, mock_coordinator):
        """Test searching fault in module-warnings section."""
        fault_info = {"WARN": "Warning"}
        sensor = DysonFaultSensor(mock_coordinator, "temp", fault_info)

        fault_data = {"module-warnings": {"temp": "WARN"}}

        found, value = sensor._search_fault_in_data(fault_data)
        assert found is True
        assert value == "WARN"

    def test_search_fault_in_data_top_level(self, mock_coordinator):
        """Test searching fault in top-level data."""
        fault_info = {"FAIL": "Failed"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)

        fault_data = {"aqs": "FAIL"}

        found, value = sensor._search_fault_in_data(fault_data)
        assert found is True
        assert value == "FAIL"

    def test_search_fault_in_data_not_found(self, mock_coordinator):
        """Test searching fault when not found."""
        fault_info = {"FAIL": "Failed"}
        sensor = DysonFaultSensor(mock_coordinator, "missing", fault_info)

        fault_data = {"product-errors": {"aqs": "OK"}}

        found, value = sensor._search_fault_in_data(fault_data)
        assert found is False
        assert value == ""

    def test_get_fault_severity_critical(self, mock_coordinator):
        """Test fault severity classification for critical faults."""
        fault_info = {"FAIL": "Failed"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)

        assert sensor._get_fault_severity("FAIL") == "Critical"
        assert sensor._get_fault_severity("STLL") == "Critical"

    def test_get_fault_severity_warning(self, mock_coordinator):
        """Test fault severity classification for warnings."""
        fault_info = {"WARN": "Warning"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)

        assert sensor._get_fault_severity("WARN") == "Warning"
        assert sensor._get_fault_severity("HIGH") == "Warning"
        assert sensor._get_fault_severity("LOW") == "Warning"

    def test_get_fault_severity_maintenance(self, mock_coordinator):
        """Test fault severity classification for maintenance."""
        fault_info = {"WORN": "Worn"}
        sensor = DysonFaultSensor(mock_coordinator, "fltr", fault_info)

        assert sensor._get_fault_severity("CHNG") == "Maintenance"
        assert sensor._get_fault_severity("WORN") == "Maintenance"
        assert sensor._get_fault_severity("FULL") == "Maintenance"

    def test_get_fault_severity_unknown(self, mock_coordinator):
        """Test fault severity classification for unknown."""
        fault_info = {"UNKNOWN": "Unknown"}
        sensor = DysonFaultSensor(mock_coordinator, "aqs", fault_info)

        assert sensor._get_fault_severity("UNKNOWN") == "Unknown"


class TestBinarySensorIntegration:
    """Test binary sensor integration scenarios."""

    def test_all_binary_sensor_types_inherit_correctly(self, mock_coordinator):
        """Test that all binary sensor types inherit from correct base classes."""
        from homeassistant.components.binary_sensor import BinarySensorEntity

        from custom_components.hass_dyson.entity import DysonEntity

        filter_sensor = DysonFilterReplacementSensor(mock_coordinator)
        fault_sensor = DysonFaultSensor(mock_coordinator, "aqs", {"FAIL": "Failed"})

        assert isinstance(filter_sensor, BinarySensorEntity)
        assert isinstance(filter_sensor, DysonEntity)
        assert isinstance(fault_sensor, BinarySensorEntity)
        assert isinstance(fault_sensor, DysonEntity)

    def test_unique_ids_are_unique(self, mock_coordinator):
        """Test that all binary sensors have unique IDs."""
        filter_sensor = DysonFilterReplacementSensor(mock_coordinator)
        fault_sensor1 = DysonFaultSensor(mock_coordinator, "aqs", {"FAIL": "Failed"})
        fault_sensor2 = DysonFaultSensor(mock_coordinator, "fltr", {"WORN": "Worn"})

        unique_ids = [
            filter_sensor._attr_unique_id,
            fault_sensor1._attr_unique_id,
            fault_sensor2._attr_unique_id,
        ]

        assert len(unique_ids) == len(set(unique_ids))

    def test_coordinator_type_annotation(self, mock_coordinator):
        """Test coordinator type annotations are correct."""
        filter_sensor = DysonFilterReplacementSensor(mock_coordinator)
        fault_sensor = DysonFaultSensor(mock_coordinator, "aqs", {"FAIL": "Failed"})

        # Check type annotations exist
        assert hasattr(filter_sensor, "coordinator")
        assert hasattr(fault_sensor, "coordinator")
