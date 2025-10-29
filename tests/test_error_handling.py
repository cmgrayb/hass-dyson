"""Test error handling improvements for capability detection and sensor data."""

from unittest.mock import MagicMock

import pytest

from custom_components.hass_dyson.device_utils import (
    convert_sensor_value_safe,
    get_sensor_data_safe,
    has_any_capability_safe,
    has_capability_safe,
    normalize_capabilities,
)


class TestCapabilityErrorHandling:
    """Test capability detection error handling."""

    def test_normalize_capabilities_with_none(self):
        """Test capability normalization with None input."""
        result = normalize_capabilities(None)
        assert result == []

    def test_normalize_capabilities_with_empty_list(self):
        """Test capability normalization with empty list."""
        result = normalize_capabilities([])
        assert result == []

    def test_normalize_capabilities_with_mixed_valid_invalid(self):
        """Test capability normalization with mix of valid and invalid entries."""
        capabilities = ["ValidCap", None, "", 0, "AnotherValidCap", 123]
        result = normalize_capabilities(capabilities)
        # Should only include valid string capabilities and convert numbers to strings
        assert "ValidCap" in result
        assert "AnotherValidCap" in result
        assert "123" in result
        assert None not in result
        assert "" not in result
        assert "0" not in result  # Zero should be filtered out

    def test_normalize_capabilities_with_enum_like_objects(self):
        """Test capability normalization with enum-like objects."""

        class MockEnum:
            def __init__(self, value):
                self.value = value

        capabilities = [MockEnum("EnumCap1"), "StringCap", MockEnum("EnumCap2")]
        result = normalize_capabilities(capabilities)
        assert "EnumCap1" in result
        assert "StringCap" in result
        assert "EnumCap2" in result

    def test_normalize_capabilities_with_malformed_objects(self):
        """Test capability normalization with objects that cause errors."""

        class BadObject:
            @property
            def value(self):
                raise ValueError("Bad object")

        capabilities = ["GoodCap", BadObject(), "AnotherGoodCap"]
        result = normalize_capabilities(capabilities)
        # Should skip the bad object but include good ones
        assert "GoodCap" in result
        assert "AnotherGoodCap" in result
        assert len(result) == 2

    def test_has_capability_safe_with_none_capabilities(self):
        """Test safe capability checking with None capabilities."""
        result = has_capability_safe(None, "TestCap")
        assert result is False

    def test_has_capability_safe_with_malformed_capabilities(self):
        """Test safe capability checking with non-list capabilities."""
        result = has_capability_safe("not_a_list", "TestCap")
        assert result is False

    def test_has_capability_safe_case_insensitive(self):
        """Test safe capability checking is case insensitive."""
        capabilities = ["ExtendedAQ", "Heating"]
        assert has_capability_safe(capabilities, "extendedAQ") is True
        assert has_capability_safe(capabilities, "HEATING") is True
        assert (
            has_capability_safe(capabilities, "extended_aq") is False
        )  # Exact match needed

    def test_has_capability_safe_with_malformed_capability_entries(self):
        """Test safe capability checking with malformed entries in capabilities list."""
        capabilities = ["ValidCap", None, "", Exception("bad"), "AnotherValidCap"]
        assert has_capability_safe(capabilities, "validcap") is True
        assert has_capability_safe(capabilities, "anothervalidcap") is True
        assert has_capability_safe(capabilities, "NonExistent") is False

    def test_has_any_capability_safe(self):
        """Test safe any-capability checking."""
        capabilities = ["ExtendedAQ", "Heating"]

        # Should find existing capability
        assert (
            has_any_capability_safe(capabilities, ["ExtendedAQ", "NonExistent"]) is True
        )
        assert has_any_capability_safe(capabilities, ["heating", "NonExistent"]) is True

        # Should not find non-existing capabilities
        assert (
            has_any_capability_safe(capabilities, ["NonExistent1", "NonExistent2"])
            is False
        )

        # Should handle empty search list
        assert has_any_capability_safe(capabilities, []) is False


class TestSensorDataErrorHandling:
    """Test sensor data access error handling."""

    def test_get_sensor_data_safe_with_none_data(self):
        """Test safe sensor data access with None data."""
        result = get_sensor_data_safe(None, "test_key", "device123")
        assert result is None

    def test_get_sensor_data_safe_with_non_dict_data(self):
        """Test safe sensor data access with non-dictionary data."""
        result = get_sensor_data_safe("not_a_dict", "test_key", "device123")
        assert result is None

        result = get_sensor_data_safe(123, "test_key", "device123")
        assert result is None

    def test_get_sensor_data_safe_with_missing_key(self):
        """Test safe sensor data access with missing key."""
        data = {"other_key": "value"}
        result = get_sensor_data_safe(data, "missing_key", "device123")
        assert result is None

    def test_get_sensor_data_safe_with_valid_data(self):
        """Test safe sensor data access with valid data."""
        data = {"temperature": 25.5, "humidity": 60}
        result = get_sensor_data_safe(data, "temperature", "device123")
        assert result == 25.5

    def test_get_sensor_data_safe_with_exception_prone_data(self):
        """Test safe sensor data access with data that might cause exceptions."""

        class BadDict(dict):
            def get(self, key, default=None):
                raise ValueError("Bad dict access")

        bad_data = BadDict()
        result = get_sensor_data_safe(bad_data, "test_key", "device123")
        assert result is None

    def test_convert_sensor_value_safe_with_none(self):
        """Test safe sensor value conversion with None value."""
        result = convert_sensor_value_safe(None, int, "device123", "test_sensor")
        assert result is None

    def test_convert_sensor_value_safe_valid_conversions(self):
        """Test safe sensor value conversion with valid conversions."""
        # Int conversion
        assert convert_sensor_value_safe("42", int, "device123", "test_sensor") == 42
        assert convert_sensor_value_safe(42.7, int, "device123", "test_sensor") == 42

        # Float conversion
        assert (
            convert_sensor_value_safe("42.5", float, "device123", "test_sensor") == 42.5
        )
        assert convert_sensor_value_safe(42, float, "device123", "test_sensor") == 42.0

        # String conversion
        assert convert_sensor_value_safe(42, str, "device123", "test_sensor") == "42"
        assert (
            convert_sensor_value_safe(42.5, str, "device123", "test_sensor") == "42.5"
        )

    def test_convert_sensor_value_safe_invalid_conversions(self):
        """Test safe sensor value conversion with invalid conversions."""
        # Invalid int conversion
        result = convert_sensor_value_safe(
            "not_a_number", int, "device123", "test_sensor"
        )
        assert result is None

        # Invalid float conversion
        result = convert_sensor_value_safe(
            "not_a_float", float, "device123", "test_sensor"
        )
        assert result is None

        # Unsupported target type
        result = convert_sensor_value_safe("test", list, "device123", "test_sensor")
        assert result is None

    def test_convert_sensor_value_safe_overflow_handling(self):
        """Test safe sensor value conversion with overflow scenarios."""
        # Very large number that might cause overflow
        large_value = "9" * 1000
        result = convert_sensor_value_safe(large_value, int, "device123", "test_sensor")
        # Should either convert successfully or return None, not crash
        assert result is None or isinstance(result, int)


class TestSensorImplementationErrorHandling:
    """Test error handling in actual sensor implementations."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator for testing."""
        coordinator = MagicMock()
        coordinator.serial_number = "TEST-DEVICE-123"
        coordinator.device_name = "Test Device"
        coordinator.device = MagicMock()
        coordinator.data = {}
        return coordinator

    def test_pm25_sensor_with_invalid_device_value(self, mock_coordinator):
        """Test PM2.5 sensor handles invalid device values gracefully."""
        from unittest.mock import patch

        from custom_components.hass_dyson.sensor import DysonPM25Sensor

        # Test with invalid PM2.5 value (negative)
        mock_coordinator.device.pm25 = -1
        sensor = DysonPM25Sensor(mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to avoid RuntimeError

        # Mock async_write_ha_state to prevent Home Assistant framework calls
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            assert sensor._attr_native_value is None

        # Test with invalid PM2.5 value (over 999)
        mock_coordinator.device.pm25 = 1500
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            assert sensor._attr_native_value is None

    def test_pm25_sensor_with_valid_values(self, mock_coordinator):
        """Test PM2.5 sensor works correctly with valid values."""
        from unittest.mock import patch

        from custom_components.hass_dyson.sensor import DysonPM25Sensor

        # Set up coordinator data with environmental data structure
        mock_coordinator.data = {"environmental-data": {"pm25": 25}}
        sensor = DysonPM25Sensor(mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to avoid RuntimeError

        # Mock async_write_ha_state to prevent Home Assistant framework calls
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            assert sensor._attr_native_value == 25

    def test_pm25_sensor_with_no_device(self, mock_coordinator):
        """Test PM2.5 sensor handles missing device gracefully."""
        from unittest.mock import patch

        from custom_components.hass_dyson.sensor import DysonPM25Sensor

        mock_coordinator.device = None
        sensor = DysonPM25Sensor(mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to avoid RuntimeError

        # Mock async_write_ha_state to prevent Home Assistant framework calls
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            assert sensor._attr_native_value is None

    def test_filter_life_sensor_with_invalid_values(self, mock_coordinator):
        """Test filter life sensor handles invalid values gracefully."""
        from unittest.mock import patch

        from custom_components.hass_dyson.sensor import DysonHEPAFilterLifeSensor

        # Test with invalid filter life (negative)
        mock_coordinator.device.hepa_filter_life = -1
        sensor = DysonHEPAFilterLifeSensor(mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to avoid RuntimeError

        # Mock async_write_ha_state to prevent Home Assistant framework calls
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            assert sensor._attr_native_value is None

        # Test with invalid filter life (over 100%)
        mock_coordinator.device.hepa_filter_life = 150
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            assert sensor._attr_native_value is None

    def test_filter_life_sensor_with_valid_values(self, mock_coordinator):
        """Test filter life sensor works correctly with valid values."""
        from unittest.mock import patch

        from custom_components.hass_dyson.sensor import DysonHEPAFilterLifeSensor

        mock_coordinator.device.hepa_filter_life = 75
        sensor = DysonHEPAFilterLifeSensor(mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to avoid RuntimeError

        # Mock async_write_ha_state to prevent Home Assistant framework calls
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            assert sensor._attr_native_value == 75

    def test_humidity_sensor_with_malformed_data(self, mock_coordinator):
        """Test humidity sensor handles malformed coordinator data."""
        from unittest.mock import patch

        from custom_components.hass_dyson.sensor import DysonHumiditySensor

        # Test with non-dict coordinator data
        mock_coordinator.data = "not_a_dict"
        sensor = DysonHumiditySensor(mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to avoid RuntimeError

        # Mock async_write_ha_state to prevent Home Assistant framework calls
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            assert sensor._attr_native_value is None

        # Test with missing key in data
        mock_coordinator.data = {"other_key": "value"}
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            assert sensor._attr_native_value is None

        # Test with invalid humidity value
        mock_coordinator.data = {"hact": "not_a_number"}
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            assert sensor._attr_native_value is None

    def test_carbon_filter_type_sensor_with_malformed_data(self, mock_coordinator):
        """Test carbon filter type sensor handles malformed data gracefully."""
        from unittest.mock import patch

        from custom_components.hass_dyson.sensor import DysonCarbonFilterTypeSensor

        # Test with non-dict product-state
        mock_coordinator.data = {"product-state": "not_a_dict"}
        sensor = DysonCarbonFilterTypeSensor(mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to avoid RuntimeError

        # Mock async_write_ha_state to prevent Home Assistant framework calls
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            assert sensor._attr_native_value == "Unknown"

        # Test with missing product-state
        mock_coordinator.data = {}
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            assert sensor._attr_native_value == "Unknown"

        # Test with valid data
        mock_coordinator.data = {"product-state": {"cflt": "CARBON_TYPE_A"}}
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            assert sensor._attr_native_value == "CARBON_TYPE_A"


class TestBinarySensorErrorHandling:
    """Test error handling in binary sensor implementations."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator for testing."""
        coordinator = MagicMock()
        coordinator.serial_number = "TEST-DEVICE-123"
        coordinator.device = MagicMock()
        coordinator.data = {"product-state": {"hflt": "HEPA_TYPE_A"}}
        return coordinator

    def test_filter_replacement_sensor_with_malformed_data(self, mock_coordinator):
        """Test filter replacement sensor handles malformed data gracefully."""
        from unittest.mock import patch

        from custom_components.hass_dyson.binary_sensor import (
            DysonFilterReplacementSensor,
        )

        # Test with non-dict coordinator data
        mock_coordinator.data = "not_a_dict"
        mock_coordinator.device.hepa_filter_life = 5  # Should trigger replacement

        sensor = DysonFilterReplacementSensor(mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to avoid RuntimeError

        # Mock async_write_ha_state to prevent Home Assistant framework calls
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            # Should not crash and should have some reasonable state
            assert isinstance(sensor._attr_is_on, bool)

    def test_filter_replacement_sensor_with_invalid_filter_life(self, mock_coordinator):
        """Test filter replacement sensor handles invalid filter life values."""
        from unittest.mock import patch

        from custom_components.hass_dyson.binary_sensor import (
            DysonFilterReplacementSensor,
        )

        # Test with non-numeric filter life
        mock_coordinator.device.hepa_filter_life = "not_a_number"

        sensor = DysonFilterReplacementSensor(mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to avoid RuntimeError

        # Mock async_write_ha_state to prevent Home Assistant framework calls
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            # Should not crash and should default to False
            assert sensor._attr_is_on is False

    def test_filter_replacement_sensor_with_no_device(self, mock_coordinator):
        """Test filter replacement sensor handles missing device gracefully."""
        from unittest.mock import patch

        from custom_components.hass_dyson.binary_sensor import (
            DysonFilterReplacementSensor,
        )

        mock_coordinator.device = None

        sensor = DysonFilterReplacementSensor(mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to avoid RuntimeError

        # Mock async_write_ha_state to prevent Home Assistant framework calls
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()
            assert sensor._attr_is_on is False

    def test_fault_sensor_relevance_checking_with_errors(self):
        """Test fault sensor relevance checking with malformed capabilities."""
        from custom_components.hass_dyson.binary_sensor import _is_fault_code_relevant

        # Test with malformed device categories
        result = _is_fault_code_relevant("TEST_FAULT", "not_a_list", ["ValidCap"])
        # Should not crash and should return a boolean
        assert isinstance(result, bool)

        # Test with malformed capabilities
        result = _is_fault_code_relevant("TEST_FAULT", ["ec"], "not_a_list")
        assert isinstance(result, bool)

        # Test with both malformed
        result = _is_fault_code_relevant(
            "TEST_FAULT", Exception("bad"), Exception("bad")
        )
        assert isinstance(result, bool)
