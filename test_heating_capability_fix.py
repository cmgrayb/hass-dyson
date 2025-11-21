#!/usr/bin/env python3
"""Test script to verify heating capability detection fix."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

# Configure logging to see our debug messages
logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

async def test_heating_capability_detection():
    """Test that heating capability is properly detected from device state."""

    # Mock Home Assistant and config entry
    mock_hass = MagicMock()
    mock_hass.data = {}
    mock_hass.loop = asyncio.get_event_loop()
    mock_hass.async_create_task = lambda coro: asyncio.create_task(coro)
    mock_hass.add_job = lambda func: asyncio.create_task(func() if asyncio.iscoroutinefunction(func) else asyncio.coroutine(func)())

    mock_config_entry = MagicMock()
    mock_config_entry.data = {
        "serial_number": "TEST-HP-001",
        "discovery_method": "cloud",
        "capabilities": [],  # Start with empty capabilities like cloud discovery does
    }
    mock_config_entry.entry_id = "test_entry_id"

    # Mock device with heating state
    mock_device = MagicMock()
    mock_device.is_connected = True
    mock_device.send_command = AsyncMock()
    mock_device.get_state = AsyncMock(return_value={
        "product-state": {
            "hmod": "OFF",  # This key indicates heating capability
            "fmod": "FAN",
            "oson": "ON"
        }
    })

    # Test the coordinator
    print("Testing coordinator capability detection...")

    with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

        # Create coordinator
        coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
        coordinator.hass = mock_hass
        coordinator.config_entry = mock_config_entry
        coordinator.device = mock_device
        coordinator._device_capabilities = []  # Start empty like cloud discovery

        # Test capability refinement
        await coordinator._refine_capabilities_from_device_state()

        # Check that Heating capability was added
        print(f"Capabilities after refinement: {coordinator._device_capabilities}")
        assert "Heating" in coordinator._device_capabilities, f"Heating capability not found in {coordinator._device_capabilities}"
        print("✓ Heating capability correctly detected from 'hmod' key")

        # Test platform determination
        from custom_components.hass_dyson import _get_platforms_for_device

        # Mock device category
        coordinator._device_category = ["ec"]  # Environment Cleaner

        platforms = _get_platforms_for_device(coordinator)
        print(f"Platforms to setup: {platforms}")
        assert "climate" in platforms, f"Climate platform not found in {platforms}"
        print("✓ Climate platform correctly included based on Heating capability")


async def test_no_heating_capability():
    """Test that devices without 'hmod' key don't get heating capability."""

    # Mock Home Assistant and config entry
    mock_hass = MagicMock()
    mock_hass.data = {}
    mock_hass.loop = asyncio.get_event_loop()
    mock_hass.async_create_task = lambda coro: asyncio.create_task(coro)
    mock_hass.add_job = lambda func: asyncio.create_task(func() if asyncio.iscoroutinefunction(func) else asyncio.coroutine(func)())

    mock_config_entry = MagicMock()
    mock_config_entry.data = {
        "serial_number": "TEST-FAN-001",
        "discovery_method": "cloud",
        "capabilities": [],  # Start with empty capabilities
    }
    mock_config_entry.entry_id = "test_entry_id"

    # Mock device without heating state
    mock_device = MagicMock()
    mock_device.is_connected = True
    mock_device.send_command = AsyncMock()
    mock_device.get_state = AsyncMock(return_value={
        "product-state": {
            "fmod": "FAN",  # No 'hmod' key = no heating
            "oson": "ON"
        }
    })

    print("Testing device without heating capability...")

    with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

        # Create coordinator
        coordinator = DysonDataUpdateCoordinator.__new__(DysonDataUpdateCoordinator)
        coordinator.hass = mock_hass
        coordinator.config_entry = mock_config_entry
        coordinator.device = mock_device
        coordinator._device_capabilities = []  # Start empty

        # Test capability refinement
        await coordinator._refine_capabilities_from_device_state()

        # Check that Heating capability was NOT added
        print(f"Capabilities after refinement: {coordinator._device_capabilities}")
        assert "Heating" not in coordinator._device_capabilities, f"Heating capability incorrectly added: {coordinator._device_capabilities}"
        print("✓ Heating capability correctly NOT detected (no 'hmod' key)")

        # Test platform determination
        from custom_components.hass_dyson import _get_platforms_for_device

        # Mock device category
        coordinator._device_category = ["ec"]  # Environment Cleaner

        platforms = _get_platforms_for_device(coordinator)
        print(f"Platforms to setup: {platforms}")
        assert "climate" not in platforms, f"Climate platform incorrectly included: {platforms}"
        print("✓ Climate platform correctly NOT included (no Heating capability)")


async def main():
    """Run the tests."""
    print("=== Testing Heating Capability Detection Fix ===")
    print()

    try:
        await test_heating_capability_detection()
        print()
        await test_no_heating_capability()
        print()
        print("🎉 All tests passed! The fix is working correctly.")
        print()
        print("Summary:")
        print("- Devices with 'hmod' key in state get Heating capability")
        print("- Devices with Heating capability get climate platform")
        print("- Devices without 'hmod' key don't get Heating capability")
        print("- Devices without Heating capability don't get climate platform")
        print()
        print("This should fix the cloud discovery issue where heater-equipped")
        print("devices weren't getting climate entities created.")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
