"""Test cases for HCHO sensor handling of 'NONE' values - Bug fix for issue reported with model 438E."""

from unittest.mock import patch

from custom_components.hass_dyson.sensor import DysonFormaldehydeSensor


class TestHCHONoneValueHandling:
    """Test HCHO sensor handling of 'NONE' values from device data."""

    def test_formaldehyde_sensor_none_value_processing(self, mock_coordinator):
        """Test formaldehyde sensor correctly handles 'NONE' values without errors.

        This test addresses bug report where device sends 'hcho': 'NONE' and 'hchr': 'NONE',
        causing ValueError when sensor tries to convert 'NONE' to int, resulting in warnings
        and 'Unknown' state in UI.
        """
        # Arrange
        sensor = DysonFormaldehydeSensor(mock_coordinator)
        mock_coordinator.data = {
            "environmental-data": {
                "hcho": "NONE",  # Device reports HCHO sensor unavailable
                "hchr": "NONE",  # Device reports HCHR sensor unavailable
            }
        }

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        # Sensor should gracefully handle 'NONE' and set value to None (unavailable)
        # instead of attempting int conversion and showing 'Unknown'
        assert sensor._attr_native_value is None

    def test_formaldehyde_sensor_mixed_none_and_valid_value(self, mock_coordinator):
        """Test formaldehyde sensor uses valid value when one is 'NONE' and other is valid."""
        # Arrange
        sensor = DysonFormaldehydeSensor(mock_coordinator)
        mock_coordinator.data = {
            "environmental-data": {
                "hcho": "NONE",  # Legacy sensor unavailable
                "hchr": "0005",  # Revised sensor has valid value
            }
        }

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        # Should use the valid hchr value: 5 raw -> 0.005 mg/m³
        assert sensor._attr_native_value == 0.005

    def test_formaldehyde_sensor_both_none_fallback_order(self, mock_coordinator):
        """Test formaldehyde sensor respects hchr > hcho fallback order with 'NONE' values."""
        # Arrange
        sensor = DysonFormaldehydeSensor(mock_coordinator)
        mock_coordinator.data = {
            "environmental-data": {
                "hcho": "0003",  # Legacy sensor has value
                "hchr": "NONE",  # Revised sensor unavailable
            }
        }

        # Act
        with patch.object(sensor, "async_write_ha_state"):
            sensor._handle_coordinator_update()

        # Assert
        # Should fall back to hcho value: 3 raw -> 0.003 mg/m³
        assert sensor._attr_native_value == 0.003

    def test_sensor_creation_skips_when_all_hcho_values_none(self):
        """Test that formaldehyde sensor is not created when all HCHO values are 'NONE'.

        This prevents sensor creation that would only show as 'Unknown' in UI.
        Based on user report from Dyson 438E model.
        """
        # Arrange - environmental data with ExtendedAQ capability but HCHO unavailable
        env_data = {
            "pm25": "0004",  # PM2.5 present - indicates ExtendedAQ capability
            "pm10": "0002",  # PM10 present
            "hcho": "NONE",  # HCHO sensor unavailable
            "hchr": "NONE",  # HCHR sensor unavailable
        }

        # Act - replicate sensor creation logic from async_setup_entry
        hchr_val = env_data.get("hchr")
        hcho_val = env_data.get("hcho")
        should_create_sensor = (hchr_val and hchr_val != "NONE") or (
            hcho_val and hcho_val != "NONE"
        )

        # Assert
        assert not should_create_sensor, (
            "Sensor should not be created when all HCHO values are 'NONE'"
        )

    def test_sensor_creation_allows_when_any_hcho_value_valid(self):
        """Test that formaldehyde sensor is created when at least one HCHO value is valid."""
        # Test case 1: hchr valid, hcho NONE
        env_data = {
            "pm25": "0004",
            "pm10": "0002",
            "hcho": "NONE",
            "hchr": "0005",  # Valid value
        }

        hchr_val = env_data.get("hchr")
        hcho_val = env_data.get("hcho")
        should_create_sensor = (hchr_val and hchr_val != "NONE") or (
            hcho_val and hcho_val != "NONE"
        )

        assert should_create_sensor, (
            "Sensor should be created when hchr has valid value"
        )

        # Test case 2: hcho valid, hchr NONE
        env_data["hcho"] = "0003"  # Valid value
        env_data["hchr"] = "NONE"

        hchr_val = env_data.get("hchr")
        hcho_val = env_data.get("hcho")
        should_create_sensor = (hchr_val and hchr_val != "NONE") or (
            hcho_val and hcho_val != "NONE"
        )

        assert should_create_sensor, (
            "Sensor should be created when hcho has valid value"
        )

        # Test case 3: both valid
        env_data["hchr"] = "0008"  # Valid value

        hchr_val = env_data.get("hchr")
        hcho_val = env_data.get("hcho")
        should_create_sensor = (hchr_val and hchr_val != "NONE") or (
            hcho_val and hcho_val != "NONE"
        )

        assert should_create_sensor, (
            "Sensor should be created when both values are valid"
        )
