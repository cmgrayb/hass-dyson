#!/usr/bin/env python3
"""Test script for debugging fan control issues."""

import asyncio
import json
import logging


# Mock the Home Assistant dependencies
class MockCoordinator:
    def __init__(self):
        self.device_name = "Theater Fan"
        self.serial_number = "FJ7-GB-EAA2222A"

        # Mock device with the actual state data we saw in logs
        self.device = MockDevice()


class MockDevice:
    def __init__(self):
        # Simulate the product state we saw in the logs
        self._state_data = {
            "product-state": {
                "fpwr": "ON",  # Fan power ON
                "fnst": "FAN",  # Fan state FAN
                "fnsp": "0006",  # Fan speed setting 6
                "nmdv": "0006",  # Actual fan speed 6
            }
        }

    @property
    def fan_power(self) -> bool:
        """Return if fan power is on (fpwr)."""
        fpwr = self._state_data.get("product-state", {}).get("fpwr", "OFF")
        return fpwr == "ON"

    @property
    def fan_state(self) -> str:
        """Return fan state (fnst) - OFF/FAN."""
        return self._state_data.get("product-state", {}).get("fnst", "OFF")

    @property
    def fan_speed_setting(self) -> str:
        """Return fan speed setting (fnsp) - controllable setting."""
        return self._state_data.get("product-state", {}).get("fnsp", "0001")

    @property
    def fan_speed(self) -> int:
        """Return fan speed (nmdv)."""
        try:
            nmdv = self._state_data.get("product-state", {}).get("nmdv", "0000")
            return int(nmdv)
        except (ValueError, TypeError):
            return 0


# Test the fan update logic
def test_fan_update():
    """Test fan state update logic."""
    print("Testing fan state update logic...")

    coordinator = MockCoordinator()

    # Simulate the same logic from fan._handle_coordinator_update
    fan_power = coordinator.device.fan_power
    fan_state = coordinator.device.fan_state
    fan_speed_setting = coordinator.device.fan_speed_setting

    print(f"fan_power: {fan_power}")
    print(f"fan_state: {fan_state}")
    print(f"fan_speed_setting: {fan_speed_setting}")

    # Calculate is_on state
    is_on = fan_power and fan_state == "FAN"
    print(f"is_on calculated: {is_on}")

    # Calculate percentage
    if fan_speed_setting == "AUTO":
        actual_speed = coordinator.device.fan_speed
        percentage = min(100, max(0, actual_speed * 10))
    else:
        try:
            speed_int = int(fan_speed_setting)
            percentage = min(100, max(0, speed_int * 10))
        except (ValueError, TypeError):
            percentage = 0

    print(f"percentage calculated: {percentage}")

    print("\nExpected result:")
    print(f"- Fan should be ON: {is_on}")
    print(f"- Fan speed should be 60%: {percentage}")


if __name__ == "__main__":
    test_fan_update()
