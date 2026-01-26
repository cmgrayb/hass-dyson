"""Test AQI sensor classes for Dyson integration.

Tests for the Air Quality Index (AQI) sensors including:
- DysonAQISensor (numeric AQI value)
- DysonAQICategorySensor (text category)
- DysonDominantPollutantSensor (pollutant identification)
- Helper functions for AQI calculation
"""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.hass_dyson.const import (
    AQI_CATEGORY_EXTREMELY_POOR,
    AQI_CATEGORY_FAIR,
    AQI_CATEGORY_GOOD,
    AQI_CATEGORY_POOR,
    AQI_CATEGORY_SEVERE,
    AQI_CATEGORY_VERY_POOR,
    AQI_PM25_RANGES,
)
from custom_components.hass_dyson.sensor import (
    DysonAQICategorySensor,
    DysonAQISensor,
    DysonDominantPollutantSensor,
    _calculate_overall_aqi,
    _calculate_pollutant_aqi,
    _get_environmental_value,
)


@pytest.fixture
def mock_sensor_with_hass(pure_mock_coordinator):
    """Helper to create sensor with mocked hass."""

    def _create_sensor(sensor_class):
        sensor = sensor_class(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        return sensor

    return _create_sensor


class TestAQIHelperFunctions:
    """Test AQI calculation helper functions."""

    def test_calculate_pollutant_aqi_good_range(self):
        """Test AQI calculation for good air quality."""
        # PM2.5 = 25 μg/m³ (in Good range: 0-35)
        aqi, category = _calculate_pollutant_aqi(25, AQI_PM25_RANGES)
        assert aqi is not None
        assert 0 <= aqi <= 50
        assert category == AQI_CATEGORY_GOOD

    def test_calculate_pollutant_aqi_fair_range(self):
        """Test AQI calculation for fair air quality."""
        # PM2.5 = 45 μg/m³ (in Fair range: 36-53)
        aqi, category = _calculate_pollutant_aqi(45, AQI_PM25_RANGES)
        assert aqi is not None
        assert 51 <= aqi <= 100
        assert category == AQI_CATEGORY_FAIR

    def test_calculate_pollutant_aqi_poor_range(self):
        """Test AQI calculation for poor air quality."""
        # PM2.5 = 60 μg/m³ (in Poor range: 54-70)
        aqi, category = _calculate_pollutant_aqi(60, AQI_PM25_RANGES)
        assert aqi is not None
        assert 101 <= aqi <= 150
        assert category == AQI_CATEGORY_POOR

    def test_calculate_pollutant_aqi_very_poor_range(self):
        """Test AQI calculation for very poor air quality."""
        # PM2.5 = 100 μg/m³ (in Very Poor range: 71-150)
        aqi, category = _calculate_pollutant_aqi(100, AQI_PM25_RANGES)
        assert aqi is not None
        assert 151 <= aqi <= 200
        assert category == AQI_CATEGORY_VERY_POOR

    def test_calculate_pollutant_aqi_extremely_poor_range(self):
        """Test AQI calculation for extremely poor air quality."""
        # PM2.5 = 200 μg/m³ (in Extremely Poor range: 151-250)
        aqi, category = _calculate_pollutant_aqi(200, AQI_PM25_RANGES)
        assert aqi is not None
        assert 201 <= aqi <= 300
        assert category == AQI_CATEGORY_EXTREMELY_POOR

    def test_calculate_pollutant_aqi_severe_range(self):
        """Test AQI calculation for severe air quality."""
        # PM2.5 = 300 μg/m³ (in Severe range: 251+)
        aqi, category = _calculate_pollutant_aqi(300, AQI_PM25_RANGES)
        assert aqi is not None
        assert 301 <= aqi <= 500
        assert category == AQI_CATEGORY_SEVERE

    def test_calculate_pollutant_aqi_none_value(self):
        """Test AQI calculation with None value."""
        aqi, category = _calculate_pollutant_aqi(None, AQI_PM25_RANGES)
        assert aqi is None
        assert category is None

    def test_calculate_pollutant_aqi_negative_value(self):
        """Test AQI calculation with negative value."""
        aqi, category = _calculate_pollutant_aqi(-10, AQI_PM25_RANGES)
        assert aqi is None
        assert category is None

    def test_calculate_pollutant_aqi_linear_interpolation(self):
        """Test that AQI uses linear interpolation correctly."""
        # PM2.5 = 0 should give AQI = 0
        aqi, _ = _calculate_pollutant_aqi(0, AQI_PM25_RANGES)
        assert aqi == 0

        # PM2.5 = 35 (upper bound of Good) should give AQI = 50
        aqi, _ = _calculate_pollutant_aqi(35, AQI_PM25_RANGES)
        assert aqi == 50

        # PM2.5 at midpoint should give midpoint AQI
        # Midpoint of range 36-53 is 44.5, midpoint of AQI 51-100 is 75.5
        aqi, _ = _calculate_pollutant_aqi(44.5, AQI_PM25_RANGES)
        assert 74 <= aqi <= 77  # Allow for rounding

    def test_get_environmental_value_first_key(self):
        """Test getting value with first priority key."""
        env_data = {"p25r": 50, "pm25": 40, "pact": 30}
        keys = ["p25r", "pm25", "pact"]
        value = _get_environmental_value(env_data, keys)
        assert value == 50  # Should return first match

    def test_get_environmental_value_fallback_key(self):
        """Test getting value with fallback key."""
        env_data = {"pm25": 40, "pact": 30}
        keys = ["p25r", "pm25", "pact"]
        value = _get_environmental_value(env_data, keys)
        assert value == 40  # Should return second priority

    def test_get_environmental_value_no_match(self):
        """Test getting value when no key matches."""
        env_data = {"other": 50}
        keys = ["p25r", "pm25", "pact"]
        value = _get_environmental_value(env_data, keys)
        assert value is None

    def test_calculate_overall_aqi_single_pollutant(self):
        """Test overall AQI with single pollutant."""
        env_data = {"p25r": 60}  # PM2.5 Poor
        aqi, category, dominant = _calculate_overall_aqi(env_data)
        assert aqi is not None
        assert 101 <= aqi <= 150
        assert category == AQI_CATEGORY_POOR
        assert dominant == ["PM2.5"]

    def test_calculate_overall_aqi_multiple_pollutants_different_levels(self):
        """Test overall AQI when pollutants have different AQI levels."""
        env_data = {
            "p25r": 60,  # PM2.5 Poor (~115)
            "p10r": 30,  # PM10 Good (~30)
            "va10": 2,  # VOC Good (~33)
        }
        aqi, category, dominant = _calculate_overall_aqi(env_data)
        assert aqi is not None
        assert 101 <= aqi <= 150  # Should be PM2.5's AQI
        assert category == AQI_CATEGORY_POOR
        assert dominant == ["PM2.5"]

    def test_calculate_overall_aqi_multiple_pollutants_same_level(self):
        """Test overall AQI when multiple pollutants have same AQI."""
        # Need to carefully choose values that result in same AQI
        env_data = {
            "p25r": 36,  # PM2.5 Fair (AQI = 51)
            "p10r": 51,  # PM10 Fair (AQI = 51)
        }
        aqi, category, dominant = _calculate_overall_aqi(env_data)
        assert aqi == 51
        assert category == AQI_CATEGORY_FAIR
        assert len(dominant) == 2
        assert "PM2.5" in dominant
        assert "PM10" in dominant

    def test_calculate_overall_aqi_all_pollutants(self):
        """Test overall AQI with all pollutant types."""
        env_data = {
            "p25r": 30,  # PM2.5 Good
            "p10r": 40,  # PM10 Good
            "va10": 2,  # VOC Good
            "noxl": 3,  # NO2 Good
            "co2r": 400,  # CO2 Good
            "hcho": 50,  # HCHO Good (0.05 ppm after conversion)
        }
        aqi, category, dominant = _calculate_overall_aqi(env_data)
        assert aqi is not None
        assert 0 <= aqi <= 50
        assert category == AQI_CATEGORY_GOOD
        assert len(dominant) >= 1

    def test_calculate_overall_aqi_no_data(self):
        """Test overall AQI with no environmental data."""
        env_data = {}
        aqi, category, dominant = _calculate_overall_aqi(env_data)
        assert aqi is None
        assert category is None
        assert dominant == []

    def test_calculate_overall_aqi_invalid_values(self):
        """Test overall AQI with invalid values."""
        env_data = {
            "p25r": "invalid",
            "p10r": None,
        }
        aqi, category, dominant = _calculate_overall_aqi(env_data)
        # Should handle errors gracefully
        assert aqi is None or aqi >= 0

    def test_calculate_overall_aqi_priority_keys(self):
        """Test that newer keys take priority over older keys."""
        env_data = {
            "p25r": 60,  # Newer key, should be used
            "pact": 30,  # Older key, should be ignored
        }
        aqi, category, dominant = _calculate_overall_aqi(env_data)
        assert aqi is not None
        assert 101 <= aqi <= 150  # Based on p25r=60
        assert category == AQI_CATEGORY_POOR


class TestDysonAQISensor:
    """Test DysonAQISensor class (numeric AQI)."""

    def test_init(self, pure_mock_coordinator):
        """Test sensor initialization."""
        sensor = DysonAQISensor(pure_mock_coordinator)
        assert sensor._attr_unique_id == f"{pure_mock_coordinator.serial_number}_aqi"
        assert sensor._attr_translation_key == "aqi"
        assert sensor._attr_icon == "mdi:air-filter"

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_good_aqi(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test update with good air quality data."""
        sensor = DysonAQISensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {
            "environmental-data": {
                "p25r": 25,  # Good
                "p10r": 30,  # Good
            }
        }

        sensor._handle_coordinator_update()

        assert sensor.native_value is not None
        assert 0 <= sensor.native_value <= 50
        assert sensor.extra_state_attributes["category"] == AQI_CATEGORY_GOOD
        assert "dominant_pollutants" in sensor.extra_state_attributes

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_poor_aqi(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test update with poor air quality data."""
        sensor = DysonAQISensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {
            "environmental-data": {
                "p25r": 60,  # Poor
            }
        }

        sensor._handle_coordinator_update()

        assert sensor.native_value is not None
        assert 101 <= sensor.native_value <= 150
        assert sensor.extra_state_attributes["category"] == AQI_CATEGORY_POOR

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_no_data(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test update with no environmental data."""
        sensor = DysonAQISensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {}

        sensor._handle_coordinator_update()

        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_none_coordinator_data(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test update when coordinator.data is None."""
        sensor = DysonAQISensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = None

        sensor._handle_coordinator_update()

        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_exception_handling(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test that exceptions are handled gracefully."""
        sensor = DysonAQISensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {"environmental-data": {"invalid": "data"}}

        # Should not raise exception
        sensor._handle_coordinator_update()

        # Should have None value on error
        assert sensor.native_value is None or isinstance(
            sensor.native_value, (int, float)
        )


class TestDysonAQICategorySensor:
    """Test DysonAQICategorySensor class (text category)."""

    def test_init(self, pure_mock_coordinator):
        """Test sensor initialization."""
        sensor = DysonAQICategorySensor(pure_mock_coordinator)
        assert (
            sensor._attr_unique_id
            == f"{pure_mock_coordinator.serial_number}_aqi_category"
        )
        assert sensor._attr_translation_key == "aqi_category"
        assert sensor._attr_icon == "mdi:air-filter"

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_good_category(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test update returns Good category."""
        sensor = DysonAQICategorySensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {
            "environmental-data": {
                "p25r": 25,  # Good
            }
        }

        sensor._handle_coordinator_update()

        assert sensor.native_value == AQI_CATEGORY_GOOD
        assert "aqi" in sensor.extra_state_attributes
        assert "dominant_pollutants" in sensor.extra_state_attributes

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_fair_category(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test update returns Fair category."""
        sensor = DysonAQICategorySensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {
            "environmental-data": {
                "p25r": 45,  # Fair
            }
        }

        sensor._handle_coordinator_update()

        assert sensor.native_value == AQI_CATEGORY_FAIR

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_poor_category(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test update returns Poor category."""
        sensor = DysonAQICategorySensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {
            "environmental-data": {
                "p25r": 60,  # Poor
            }
        }

        sensor._handle_coordinator_update()

        assert sensor.native_value == AQI_CATEGORY_POOR

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_severe_category(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test update returns Severe category."""
        sensor = DysonAQICategorySensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {
            "environmental-data": {
                "p25r": 300,  # Severe
            }
        }

        sensor._handle_coordinator_update()

        assert sensor.native_value == AQI_CATEGORY_SEVERE

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_no_data(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test update with no environmental data."""
        sensor = DysonAQICategorySensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {}

        sensor._handle_coordinator_update()

        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}


class TestDysonDominantPollutantSensor:
    """Test DysonDominantPollutantSensor class."""

    def test_init(self, pure_mock_coordinator):
        """Test sensor initialization."""
        sensor = DysonDominantPollutantSensor(pure_mock_coordinator)
        assert (
            sensor._attr_unique_id
            == f"{pure_mock_coordinator.serial_number}_dominant_pollutant"
        )
        assert sensor._attr_translation_key == "dominant_pollutant"
        assert sensor._attr_icon == "mdi:molecule"

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_single_dominant(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test update with single dominant pollutant."""
        sensor = DysonDominantPollutantSensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {
            "environmental-data": {
                "p25r": 60,  # Poor - highest
                "p10r": 30,  # Good - lower
            }
        }

        sensor._handle_coordinator_update()

        assert sensor.native_value == "PM2.5"
        assert "aqi" in sensor.extra_state_attributes
        assert "category" in sensor.extra_state_attributes
        assert sensor.extra_state_attributes["pollutant_count"] == 1

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_multiple_dominant(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test update with multiple pollutants at same level."""
        sensor = DysonDominantPollutantSensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {
            "environmental-data": {
                "p25r": 36,  # Fair (AQI = 51)
                "p10r": 51,  # Fair (AQI = 51)
            }
        }

        sensor._handle_coordinator_update()

        # Should list both pollutants
        assert "PM2.5" in sensor.native_value
        assert "PM10" in sensor.native_value
        assert "," in sensor.native_value  # Comma-separated
        assert sensor.extra_state_attributes["pollutant_count"] == 2

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_no_data(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test update with no environmental data."""
        sensor = DysonDominantPollutantSensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {}

        sensor._handle_coordinator_update()

        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_all_pollutants(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test with all pollutant types present."""
        sensor = DysonDominantPollutantSensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {
            "environmental-data": {
                "p25r": 30,  # Good
                "p10r": 40,  # Good
                "va10": 2,  # Good
                "noxl": 3,  # Good
                "co2r": 400,  # Good
                "hcho": 50,  # Good
            }
        }

        sensor._handle_coordinator_update()

        # Should have at least one dominant pollutant
        assert sensor.native_value is not None
        assert len(sensor.native_value) > 0

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_co2_dominant(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test with CO2 as dominant pollutant."""
        sensor = DysonDominantPollutantSensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {
            "environmental-data": {
                "p25r": 10,  # Good
                "co2r": 2000,  # Very Poor - highest
            }
        }

        sensor._handle_coordinator_update()

        assert "CO2" in sensor.native_value
        assert sensor.extra_state_attributes["category"] in [
            AQI_CATEGORY_VERY_POOR,
            AQI_CATEGORY_EXTREMELY_POOR,
        ]

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_exception_handling(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test that exceptions are handled gracefully."""
        sensor = DysonDominantPollutantSensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {"environmental-data": {"invalid": "data"}}

        # Should not raise exception
        sensor._handle_coordinator_update()

        # Should have safe state on error
        assert sensor.native_value is None or isinstance(sensor.native_value, str)

    @patch("custom_components.hass_dyson.entity.DysonEntity._handle_coordinator_update")
    def test_handle_coordinator_update_zero_aqi(
        self, mock_parent_update, pure_mock_coordinator
    ):
        """Test that AQI of 0 shows 'None' instead of listing all pollutants."""
        sensor = DysonDominantPollutantSensor(pure_mock_coordinator)
        sensor.hass = MagicMock()  # Mock hass to prevent state write errors
        pure_mock_coordinator.data = {
            "environmental-data": {
                "p25r": 0,  # Perfect air quality
                "p10r": 0,
                "co2r": 0,
            }
        }

        sensor._handle_coordinator_update()

        # When AQI is 0, should display "None" not a list of pollutants
        assert sensor.native_value == "None"
        assert sensor.extra_state_attributes["aqi"] == 0
        assert sensor.extra_state_attributes["category"] == AQI_CATEGORY_GOOD
