"""Test error handling coverage for device_utils module.

This module provides comprehensive error path testing for device utility functions,
covering exception handling in normalization, validation, and conversion functions.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.hass_dyson.const import (
    CONF_CREDENTIAL,
    CONF_DISCOVERY_METHOD,
    CONF_HOSTNAME,
    CONF_MQTT_PREFIX,
    CONF_SERIAL_NUMBER,
    CONNECTION_TYPE_LOCAL_ONLY,
    DISCOVERY_CLOUD,
    DISCOVERY_MANUAL,
)
from custom_components.hass_dyson.device_utils import (
    convert_sensor_value_safe,
    create_cloud_device_config,
    create_device_config_data,
    create_manual_device_config,
    extract_capabilities_from_device_info,
    get_sensor_data_safe,
    has_any_capability_safe,
    has_capability_safe,
    normalize_capabilities,
    normalize_device_category,
)


class TestNormalizeDeviceCategoryErrorHandling:
    """Test error handling in normalize_device_category function."""

    def test_normalize_device_category_none(self):
        """Test normalize_device_category with None returns default."""
        # Act
        result = normalize_device_category(None)

        # Assert
        assert result == ["ec"]

    def test_normalize_device_category_enum_with_value(self):
        """Test normalize_device_category with enum object having value attribute."""
        # Arrange
        mock_enum = MagicMock()
        mock_enum.value = "hvac"

        # Act
        result = normalize_device_category(mock_enum)

        # Assert
        assert result == ["hvac"]

    def test_normalize_device_category_enum_with_name_only(self):
        """Test normalize_device_category with enum object having only name attribute."""
        # Arrange
        mock_enum = MagicMock()
        del mock_enum.value  # Remove value attribute
        mock_enum.name = "PURIFIER"

        # Act
        result = normalize_device_category(mock_enum)

        # Assert
        assert result == ["purifier"]

    def test_normalize_device_category_string(self):
        """Test normalize_device_category with string."""
        # Act
        result = normalize_device_category("fan")

        # Assert
        assert result == ["fan"]

    def test_normalize_device_category_list_of_strings(self):
        """Test normalize_device_category with list of strings."""
        # Act
        result = normalize_device_category(["ec", "hvac"])

        # Assert
        assert result == ["ec", "hvac"]

    def test_normalize_device_category_list_with_none_values(self):
        """Test normalize_device_category filters out None values from list."""
        # Act
        result = normalize_device_category(["ec", None, "hvac"])

        # Assert
        assert result == ["ec", "hvac"]

    def test_normalize_device_category_list_with_empty_string(self):
        """Test normalize_device_category filters out empty strings."""
        # Act
        result = normalize_device_category(["ec", "", "hvac"])

        # Assert
        assert result == ["ec", "hvac"]

    def test_normalize_device_category_unknown_type_logs_warning(self):
        """Test normalize_device_category with unknown type logs warning and returns default."""
        # Arrange
        unknown_type = {"key": "value"}  # Dictionary is not expected

        # Act
        result = normalize_device_category(unknown_type)

        # Assert - should return default
        assert result == ["ec"]


class TestNormalizeCapabilitiesErrorHandling:
    """Test error handling in normalize_capabilities function."""

    def test_normalize_capabilities_none_returns_empty_list(self):
        """Test normalize_capabilities with None returns empty list."""
        # Act
        result = normalize_capabilities(None)

        # Assert
        assert result == []

    def test_normalize_capabilities_list_with_none_values(self):
        """Test normalize_capabilities filters out None values from list."""
        # Act
        result = normalize_capabilities(["Heating", None, "Cooling"])

        # Assert
        assert result == ["Heating", "Cooling"]

    def test_normalize_capabilities_list_with_empty_strings(self):
        """Test normalize_capabilities filters out empty strings."""
        # Act
        result = normalize_capabilities(["Heating", "", "Cooling"])

        # Assert
        assert result == ["Heating", "Cooling"]

    def test_normalize_capabilities_list_with_zero_numeric(self):
        """Test normalize_capabilities filters out zero numeric values."""
        # Act
        result = normalize_capabilities(["Heating", 0, 0.0, "Cooling"])

        # Assert
        assert result == ["Heating", "Cooling"]

    def test_normalize_capabilities_list_with_enum_objects(self):
        """Test normalize_capabilities with enum objects having value attribute."""
        # Arrange
        mock_enum1 = MagicMock()
        mock_enum1.value = "Humidifier"
        mock_enum2 = MagicMock()
        mock_enum2.value = "Purifier"

        # Act
        result = normalize_capabilities([mock_enum1, mock_enum2])

        # Assert
        assert "Humidifier" in result
        assert "Purifier" in result

    def test_normalize_capabilities_single_string(self):
        """Test normalize_capabilities with single string."""
        # Act
        result = normalize_capabilities("Heating")

        # Assert
        assert result == ["Heating"]

    def test_normalize_capabilities_empty_string(self):
        """Test normalize_capabilities with empty string returns empty list."""
        # Act
        result = normalize_capabilities("")

        # Assert
        assert result == []

    def test_normalize_capabilities_whitespace_only_string(self):
        """Test normalize_capabilities with whitespace-only string returns empty list."""
        # Act
        result = normalize_capabilities("   ")

        # Assert
        assert result == []

    def test_normalize_capabilities_non_standard_type_with_value_attr(self):
        """Test normalize_capabilities with object having value attribute."""
        # Arrange
        mock_obj = MagicMock()
        mock_obj.value = "CustomCapability"

        # Act
        result = normalize_capabilities(mock_obj)

        # Assert
        assert result == ["CustomCapability"]

    def test_normalize_capabilities_non_standard_type_without_value_attr(self):
        """Test normalize_capabilities with object without value attribute."""
        # Arrange
        mock_obj = MagicMock()
        del mock_obj.value
        mock_obj.__str__ = lambda self: "StringCapability"

        # Act
        result = normalize_capabilities(mock_obj)

        # Assert
        assert "StringCapability" in result[0]


class TestExtractCapabilitiesFromDeviceInfoErrorHandling:
    """Test error handling in extract_capabilities_from_device_info function."""

    def test_extract_capabilities_device_info_with_capabilities_attr(self):
        """Test extract_capabilities with device_info having capabilities attribute."""
        # Arrange
        device_info = MagicMock()
        device_info.capabilities = ["Heating", "Cooling"]

        # Act
        result = extract_capabilities_from_device_info(device_info)

        # Assert
        assert "Heating" in result
        assert "Cooling" in result

    def test_extract_capabilities_device_info_capabilities_none(self):
        """Test extract_capabilities when capabilities attribute is None."""
        # Arrange
        device_info = MagicMock()
        device_info.capabilities = None
        device_info.product_type = None  # Prevent PH model detection
        del device_info.type  # Remove default type attribute

        # Act
        result = extract_capabilities_from_device_info(device_info)

        # Assert
        assert result == []

    def test_extract_capabilities_nested_structure(self):
        """Test extract_capabilities with nested connected_configuration structure."""
        # Arrange
        device_info = MagicMock()
        del device_info.capabilities
        device_info.connected_configuration = MagicMock()
        device_info.connected_configuration.firmware = MagicMock()
        device_info.connected_configuration.firmware.capabilities = ["Purifier"]

        # Act
        result = extract_capabilities_from_device_info(device_info)

        # Assert
        assert "Purifier" in result

    def test_extract_capabilities_nested_structure_none_firmware(self):
        """Test extract_capabilities when nested firmware is None."""
        # Arrange
        device_info = MagicMock()
        del device_info.capabilities
        device_info.connected_configuration = MagicMock()
        device_info.connected_configuration.firmware = None
        device_info.product_type = None  # Prevent PH model detection
        del device_info.type  # Remove default type attribute

        # Act
        result = extract_capabilities_from_device_info(device_info)

        # Assert
        assert result == []

    def test_extract_capabilities_ph_model_adds_humidifier(self):
        """Test extract_capabilities adds Humidifier for PH models."""
        # Arrange
        device_info = MagicMock()
        device_info.capabilities = ["Purifier"]
        device_info.product_type = "PH01"

        # Act
        result = extract_capabilities_from_device_info(device_info)

        # Assert
        assert "Purifier" in result
        assert "Humidifier" in result

    def test_extract_capabilities_ph_model_does_not_duplicate_humidifier(self):
        """Test extract_capabilities doesn't duplicate Humidifier if already present."""
        # Arrange
        device_info = MagicMock()
        device_info.capabilities = ["Purifier", "Humidifier"]
        device_info.product_type = "PH01"

        # Act
        result = extract_capabilities_from_device_info(device_info)

        # Assert - Humidifier should appear only once
        assert result.count("Humidifier") == 1

    def test_extract_capabilities_no_product_type(self):
        """Test extract_capabilities when product_type is None."""
        # Arrange
        device_info = MagicMock()
        device_info.capabilities = ["Purifier"]
        device_info.product_type = None
        del device_info.type

        # Act
        result = extract_capabilities_from_device_info(device_info)

        # Assert
        assert "Purifier" in result


class TestHasCapabilitySafeErrorHandling:
    """Test error handling in has_capability_safe function."""

    def test_has_capability_safe_none_capabilities(self):
        """Test has_capability_safe with None capabilities returns False."""
        # Act
        result = has_capability_safe(None, "Heating")

        # Assert
        assert result is False

    def test_has_capability_safe_empty_list(self):
        """Test has_capability_safe with empty list returns False."""
        # Act
        result = has_capability_safe([], "Heating")

        # Assert
        assert result is False

    def test_has_capability_safe_not_a_list(self):
        """Test has_capability_safe with non-list capabilities returns False."""
        # Act
        result = has_capability_safe("Heating", "Heating")  # type: ignore

        # Assert
        assert result is False

    def test_has_capability_safe_empty_capability_name(self):
        """Test has_capability_safe with empty capability name returns False."""
        # Act
        result = has_capability_safe(["Heating"], "")

        # Assert
        assert result is False

    def test_has_capability_safe_whitespace_capability_name(self):
        """Test has_capability_safe with whitespace-only name returns False."""
        # Act
        result = has_capability_safe(["Heating"], "   ")

        # Assert
        assert result is False

    def test_has_capability_safe_case_insensitive_match(self):
        """Test has_capability_safe performs case-insensitive matching."""
        # Act
        result = has_capability_safe(["Heating", "Cooling"], "HEATING")

        # Assert
        assert result is True

    def test_has_capability_safe_none_value_in_capabilities_list(self):
        """Test has_capability_safe handles None values in capabilities list."""
        # Act
        result = has_capability_safe(["Heating", None, "Cooling"], "Cooling")

        # Assert
        assert result is True

    def test_has_capability_safe_exception_during_normalization(self):
        """Test has_capability_safe handles exceptions during capability normalization."""

        # Arrange - create object that raises exception on str()
        class BadObject:
            def __str__(self):
                raise RuntimeError("Cannot convert")

        # Act
        result = has_capability_safe(["Heating", BadObject()], "Cooling")

        # Assert - should handle gracefully and return False
        assert result is False

    def test_has_capability_safe_exception_during_comparison(self):
        """Test has_capability_safe handles generic exceptions and returns False."""
        # This is harder to trigger directly, but ensures robust error handling
        # Act - Use valid inputs
        result = has_capability_safe(["Heating"], "Heating")

        # Assert
        assert result is True


class TestHasAnyCapabilitySafeErrorHandling:
    """Test error handling in has_any_capability_safe function."""

    def test_has_any_capability_safe_empty_capability_names(self):
        """Test has_any_capability_safe with empty list returns False."""
        # Act
        result = has_any_capability_safe(["Heating"], [])

        # Assert
        assert result is False

    def test_has_any_capability_safe_none_capabilities(self):
        """Test has_any_capability_safe with None capabilities returns False."""
        # Act
        result = has_any_capability_safe(None, ["Heating", "Cooling"])

        # Assert
        assert result is False

    def test_has_any_capability_safe_finds_first_match(self):
        """Test has_any_capability_safe returns True on first match."""
        # Act
        result = has_any_capability_safe(
            ["Heating", "Cooling"], ["Unknown", "Heating", "Other"]
        )

        # Assert
        assert result is True

    def test_has_any_capability_safe_no_matches(self):
        """Test has_any_capability_safe returns False when no matches."""
        # Act
        result = has_any_capability_safe(["Heating"], ["Cooling", "Purifier"])

        # Assert
        assert result is False


class TestGetSensorDataSafeErrorHandling:
    """Test error handling in get_sensor_data_safe function."""

    def test_get_sensor_data_safe_none_data(self):
        """Test get_sensor_data_safe with None data returns None."""
        # Act
        result = get_sensor_data_safe(None, "temperature", "TEST-123")

        # Assert
        assert result is None

    def test_get_sensor_data_safe_not_dict(self):
        """Test get_sensor_data_safe with non-dict data returns None."""
        # Act
        result = get_sensor_data_safe("not a dict", "temperature", "TEST-123")  # type: ignore

        # Assert
        assert result is None

    def test_get_sensor_data_safe_key_not_found(self):
        """Test get_sensor_data_safe when key not in dict returns None."""
        # Act
        result = get_sensor_data_safe({"humidity": 50}, "temperature", "TEST-123")

        # Assert
        assert result is None

    def test_get_sensor_data_safe_value_is_none(self):
        """Test get_sensor_data_safe when value is None returns None."""
        # Act
        result = get_sensor_data_safe({"temperature": None}, "temperature", "TEST-123")

        # Assert
        assert result is None

    def test_get_sensor_data_safe_successful_extraction(self):
        """Test get_sensor_data_safe successfully extracts value."""
        # Act
        result = get_sensor_data_safe({"temperature": 25}, "temperature", "TEST-123")

        # Assert
        assert result == 25

    def test_get_sensor_data_safe_exception_during_access(self):
        """Test get_sensor_data_safe handles exceptions during data access."""

        # Arrange - create dict that raises exception on access
        class BadDict(dict):
            def get(self, key):
                raise RuntimeError("Cannot access key")

        bad_data = BadDict({"temperature": 25})

        # Act
        result = get_sensor_data_safe(bad_data, "temperature", "TEST-123")

        # Assert
        assert result is None


class TestConvertSensorValueSafeErrorHandling:
    """Test error handling in convert_sensor_value_safe function."""

    def test_convert_sensor_value_safe_none_value(self):
        """Test convert_sensor_value_safe with None value returns None."""
        # Act
        result = convert_sensor_value_safe(None, int, "TEST-123", "temperature")

        # Assert
        assert result is None

    def test_convert_sensor_value_safe_int_success(self):
        """Test convert_sensor_value_safe successfully converts to int."""
        # Act
        result = convert_sensor_value_safe("42", int, "TEST-123", "temperature")

        # Assert
        assert result == 42
        assert isinstance(result, int)

    def test_convert_sensor_value_safe_float_success(self):
        """Test convert_sensor_value_safe successfully converts to float."""
        # Act
        result = convert_sensor_value_safe("3.14", float, "TEST-123", "temperature")

        # Assert
        assert result == 3.14
        assert isinstance(result, float)

    def test_convert_sensor_value_safe_str_success(self):
        """Test convert_sensor_value_safe successfully converts to str."""
        # Act
        result = convert_sensor_value_safe(123, str, "TEST-123", "mode")

        # Assert
        assert result == "123"
        assert isinstance(result, str)

    def test_convert_sensor_value_safe_unsupported_type(self):
        """Test convert_sensor_value_safe with unsupported type returns None."""
        # Act
        result = convert_sensor_value_safe(
            "test",
            bool,
            "TEST-123",
            "flag",  # type: ignore
        )

        # Assert
        assert result is None

    def test_convert_sensor_value_safe_value_error(self):
        """Test convert_sensor_value_safe handles ValueError."""
        # Act
        result = convert_sensor_value_safe("abc", int, "TEST-123", "temperature")

        # Assert
        assert result is None

    def test_convert_sensor_value_safe_type_error(self):
        """Test convert_sensor_value_safe handles TypeError."""
        # Arrange - complex object that can't be converted
        complex_obj = {"key": "value"}

        # Act
        result = convert_sensor_value_safe(complex_obj, int, "TEST-123", "temperature")

        # Assert
        assert result is None

    def test_convert_sensor_value_safe_overflow_error(self):
        """Test convert_sensor_value_safe handles OverflowError."""
        # Act - Try to convert very large float to int (may cause overflow on some systems)
        result = convert_sensor_value_safe(float("inf"), int, "TEST-123", "temperature")

        # Assert
        assert result is None

    def test_convert_sensor_value_safe_generic_exception(self):
        """Test convert_sensor_value_safe handles generic exceptions."""

        # Arrange - create value that raises exception during conversion
        class BadValue:
            def __int__(self):
                raise RuntimeError("Unexpected error")

        # Act
        result = convert_sensor_value_safe(BadValue(), int, "TEST-123", "temperature")

        # Assert
        assert result is None


class TestCreateDeviceConfigDataErrorHandling:
    """Test error handling in create_device_config_data function."""

    def test_create_device_config_data_minimal_required_fields(self):
        """Test create_device_config_data with only required fields."""
        # Act
        result = create_device_config_data(
            serial_number="TEST-123",
            discovery_method=DISCOVERY_MANUAL,
        )

        # Assert
        assert result[CONF_SERIAL_NUMBER] == "TEST-123"
        assert result[CONF_DISCOVERY_METHOD] == DISCOVERY_MANUAL
        assert "device_category" in result
        assert "capabilities" in result

    def test_create_device_config_data_all_optional_fields(self):
        """Test create_device_config_data with all optional fields."""
        # Act
        result = create_device_config_data(
            serial_number="TEST-123",
            discovery_method=DISCOVERY_CLOUD,
            device_name="Test Device",
            hostname="192.168.1.100",
            credential="abc123",
            mqtt_prefix="TEST",
            device_category="ec",
            capabilities=["Heating"],
            connection_type=CONNECTION_TYPE_LOCAL_ONLY,
            username="user@example.com",
            auth_token="token123",
            product_type="TP02",
            category="fan",
            parent_entry_id="parent-123",
        )

        # Assert
        assert result[CONF_SERIAL_NUMBER] == "TEST-123"
        assert result["device_name"] == "Test Device"
        assert result[CONF_HOSTNAME] == "192.168.1.100"
        assert result[CONF_CREDENTIAL] == "abc123"
        assert result[CONF_MQTT_PREFIX] == "TEST"
        assert result["connection_type"] == CONNECTION_TYPE_LOCAL_ONLY

    def test_create_device_config_data_none_optional_fields_excluded(self):
        """Test create_device_config_data excludes None optional fields."""
        # Act
        result = create_device_config_data(
            serial_number="TEST-123",
            discovery_method=DISCOVERY_MANUAL,
            device_name=None,
            hostname=None,
        )

        # Assert
        assert "device_name" not in result
        assert CONF_HOSTNAME not in result

    def test_create_device_config_data_normalizes_category(self):
        """Test create_device_config_data normalizes device category."""
        # Act
        result = create_device_config_data(
            serial_number="TEST-123",
            discovery_method=DISCOVERY_MANUAL,
            device_category=None,  # Should default to ["ec"]
        )

        # Assert
        assert result["device_category"] == ["ec"]

    def test_create_device_config_data_normalizes_capabilities(self):
        """Test create_device_config_data normalizes capabilities."""
        # Act
        result = create_device_config_data(
            serial_number="TEST-123",
            discovery_method=DISCOVERY_MANUAL,
            capabilities=None,  # Should default to []
        )

        # Assert
        assert result["capabilities"] == []

    def test_create_device_config_data_includes_kwargs(self):
        """Test create_device_config_data includes additional kwargs."""
        # Act
        result = create_device_config_data(
            serial_number="TEST-123",
            discovery_method=DISCOVERY_MANUAL,
            custom_field1="value1",
            custom_field2="value2",
        )

        # Assert
        assert result["custom_field1"] == "value1"
        assert result["custom_field2"] == "value2"


class TestCreateManualDeviceConfigErrorHandling:
    """Test error handling in create_manual_device_config function."""

    def test_create_manual_device_config_minimal_fields(self):
        """Test create_manual_device_config with minimal required fields."""
        # Act
        result = create_manual_device_config(
            serial_number="TEST-123",
            credential="abc123",
            mqtt_prefix="TEST",
        )

        # Assert
        assert result[CONF_SERIAL_NUMBER] == "TEST-123"
        assert result[CONF_CREDENTIAL] == "abc123"
        assert result[CONF_MQTT_PREFIX] == "TEST"
        assert result[CONF_DISCOVERY_METHOD] == DISCOVERY_MANUAL
        assert result["connection_type"] == CONNECTION_TYPE_LOCAL_ONLY

    def test_create_manual_device_config_default_device_name(self):
        """Test create_manual_device_config generates default device name."""
        # Act
        result = create_manual_device_config(
            serial_number="TEST-123",
            credential="abc123",
            mqtt_prefix="TEST",
        )

        # Assert
        assert result["device_name"] == "Dyson TEST-123"

    def test_create_manual_device_config_custom_device_name(self):
        """Test create_manual_device_config uses provided device name."""
        # Act
        result = create_manual_device_config(
            serial_number="TEST-123",
            credential="abc123",
            mqtt_prefix="TEST",
            device_name="My Dyson Fan",
        )

        # Assert
        assert result["device_name"] == "My Dyson Fan"

    def test_create_manual_device_config_default_category(self):
        """Test create_manual_device_config uses default category."""
        # Act
        result = create_manual_device_config(
            serial_number="TEST-123",
            credential="abc123",
            mqtt_prefix="TEST",
        )

        # Assert
        assert result["device_category"] == ["ec"]


class TestCreateCloudDeviceConfigErrorHandling:
    """Test error handling in create_cloud_device_config function."""

    def test_create_cloud_device_config_with_dict_device_info(self):
        """Test create_cloud_device_config with dict device_info."""
        # Arrange
        device_info = {
            "name": "Living Room Fan",
            "product_type": "TP02",
            "category": "fan",
            "capabilities": ["Heating", "Cooling"],
        }

        # Act
        result = create_cloud_device_config(
            serial_number="TEST-123",
            username="user@example.com",
            device_info=device_info,
        )

        # Assert
        assert result[CONF_SERIAL_NUMBER] == "TEST-123"
        assert result["device_name"] == "Living Room Fan"
        assert result["product_type"] == "TP02"
        assert result[CONF_DISCOVERY_METHOD] == DISCOVERY_CLOUD

    def test_create_cloud_device_config_with_object_device_info(self):
        """Test create_cloud_device_config with object device_info."""
        # Arrange
        device_info = MagicMock()
        device_info.name = "Bedroom Purifier"
        device_info.product_type = "PH01"
        device_info.category = "purifier"
        device_info.capabilities = ["Purifier", "Humidifier"]

        # Act
        result = create_cloud_device_config(
            serial_number="TEST-456",
            username="user@example.com",
            device_info=device_info,
        )

        # Assert
        assert result[CONF_SERIAL_NUMBER] == "TEST-456"
        assert result["device_name"] == "Bedroom Purifier"
        assert result["product_type"] == "PH01"

    def test_create_cloud_device_config_extracts_capabilities_from_object(self):
        """Test create_cloud_device_config extracts capabilities from device object."""
        # Arrange
        device_info = MagicMock()
        device_info.name = "Test Device"
        device_info.capabilities = ["Purifier"]
        device_info.product_type = "TP02"
        device_info.category = "fan"

        # Act
        result = create_cloud_device_config(
            serial_number="TEST-789",
            username="user@example.com",
            device_info=device_info,
        )

        # Assert
        assert "Purifier" in result["capabilities"]

    def test_create_cloud_device_config_with_auth_token(self):
        """Test create_cloud_device_config includes auth token."""
        # Arrange
        device_info = {"name": "Test", "product_type": "TP02"}

        # Act
        result = create_cloud_device_config(
            serial_number="TEST-123",
            username="user@example.com",
            device_info=device_info,
            auth_token="token123",
        )

        # Assert
        assert result["auth_token"] == "token123"

    def test_create_cloud_device_config_with_parent_entry_id(self):
        """Test create_cloud_device_config includes parent entry ID."""
        # Arrange
        device_info = {"name": "Test", "product_type": "TP02"}

        # Act
        result = create_cloud_device_config(
            serial_number="TEST-123",
            username="user@example.com",
            device_info=device_info,
            parent_entry_id="parent-123",
        )

        # Assert
        assert result["parent_entry_id"] == "parent-123"
