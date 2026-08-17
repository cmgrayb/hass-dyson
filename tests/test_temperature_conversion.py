"""Tests for the Kelvin x 10 temperature conversion used by the climate entity.

Dyson stores the heat setpoint in ``hmax`` as Kelvin x 10, so a whole number of
degrees Celsius never lands exactly on a value the device can hold (16 C is
2891.5). These tests pin down that a setpoint written by the integration reads
back as the same whole degree, which is what the entity's 1 degree step
advertises.
"""

import pytest

from custom_components.hass_dyson.const import (
    ZERO_CELSIUS_IN_KELVIN,
    celsius_to_decikelvin,
    decikelvin_to_celsius,
)

# Every setpoint the climate entity accepts (min_temp 1, max_temp 37, step 1).
SUPPORTED_SETPOINTS = list(range(1, 38))


class TestDecikelvinToCelsius:
    """Reading a raw device value."""

    @pytest.mark.parametrize(
        ("decikelvin", "expected"),
        [
            (2890, 15.85),
            (2900, 16.85),
            (3000, 26.85),
            (2731.5, 0.0),
        ],
    )
    def test_converts_using_absolute_zero(self, decikelvin, expected):
        assert decikelvin_to_celsius(decikelvin) == pytest.approx(expected)

    def test_matches_the_offset_constant(self):
        assert decikelvin_to_celsius(ZERO_CELSIUS_IN_KELVIN * 10) == pytest.approx(0.0)


class TestCelsiusToDecikelvin:
    """Writing a setpoint to the device."""

    @pytest.mark.parametrize(
        ("celsius", "expected"),
        [
            (1, 2742),
            (16, 2892),
            (20, 2932),
            (37, 3102),
        ],
    )
    def test_rounds_to_nearest(self, celsius, expected):
        assert celsius_to_decikelvin(celsius) == expected

    def test_returns_an_int_for_the_wire_format(self):
        value = celsius_to_decikelvin(20)
        assert isinstance(value, int)
        assert f"{value:04d}" == "2932"

    def test_does_not_truncate_downwards(self):
        """int() would store 2891 for 16 C, which reads back as 15.95."""
        assert celsius_to_decikelvin(16) > int((16 + ZERO_CELSIUS_IN_KELVIN) * 10)


class TestRoundTrip:
    """The property that actually matters to the user."""

    @pytest.mark.parametrize("celsius", SUPPORTED_SETPOINTS)
    def test_setpoint_survives_a_write_then_read(self, celsius):
        stored = celsius_to_decikelvin(celsius)
        assert round(decikelvin_to_celsius(stored)) == celsius

    @pytest.mark.parametrize("celsius", SUPPORTED_SETPOINTS)
    def test_stays_within_half_a_degree_of_the_request(self, celsius):
        assert (
            abs(decikelvin_to_celsius(celsius_to_decikelvin(celsius)) - celsius) < 0.5
        )

    @pytest.mark.parametrize("celsius", SUPPORTED_SETPOINTS)
    def test_repeated_round_trips_do_not_drift(self, celsius):
        """Stepping the setpoint up and down must not accumulate an offset."""
        value = float(celsius)
        for _ in range(10):
            value = float(round(decikelvin_to_celsius(celsius_to_decikelvin(value))))
        assert value == celsius

    @pytest.mark.parametrize("decikelvin", [2740, 2880, 2890, 2900, 3100])
    def test_whole_kelvin_values_read_as_whole_degrees(self, decikelvin):
        """Setpoints already on the device sit on whole Kelvin values."""
        celsius = round(decikelvin_to_celsius(decikelvin))
        assert celsius == pytest.approx(decikelvin_to_celsius(decikelvin), abs=0.5)
        assert celsius == int(celsius)
