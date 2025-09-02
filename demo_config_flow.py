#!/usr/bin/env python3
"""
Test script to demonstrate the new Dyson configuration flow menu functionality.

This script demonstrates how the new menu system works in the configuration flow:
1. User starts setup -> Gets menu to choose cloud account or manual device
2. Cloud account -> Goes to existing cloud authentication flow
3. Manual device -> Goes to new manual device setup flow

This is a demonstration script and doesn't run real Home Assistant code.
"""

import logging


# Mock the config flow behavior for demonstration
class MockConfigFlow:
    """Mock config flow to demonstrate the new menu functionality."""

    def __init__(self):
        self.step_history = []

    async def async_step_user(self, user_input=None):
        """Initial step - setup method selection."""
        self.step_history.append(("user", user_input))

        if user_input is not None:
            setup_method = user_input.get("setup_method")

            if setup_method == "cloud_account":
                return await self.async_step_cloud_account()
            elif setup_method == "manual_device":
                return await self.async_step_manual_device()
            else:
                return {"errors": {"base": "invalid_setup_method"}}

        # Return form schema
        return {
            "type": "form",
            "step_id": "user",
            "data_schema": {
                "setup_method": {
                    "cloud_account": "Dyson Cloud Account (Recommended)",
                    "manual_device": "Manual Device Setup",
                }
            },
            "errors": {},
        }

    async def async_step_cloud_account(self, user_input=None):
        """Cloud account authentication step."""
        self.step_history.append(("cloud_account", user_input))

        if user_input is not None:
            email = user_input.get("email")
            password = user_input.get("password")

            if email and password:
                # Would proceed to verification step
                return {"type": "next_step", "step": "verify"}
            else:
                return {"errors": {"base": "auth_failed"}}

        return {
            "type": "form",
            "step_id": "cloud_account",
            "data_schema": {"email": "Email Address", "password": "Password"},
            "errors": {},
        }

    async def async_step_manual_device(self, user_input=None):
        """Manual device setup step."""
        self.step_history.append(("manual_device", user_input))

        if user_input is not None:
            serial_number = user_input.get("serial_number", "").strip()
            credential = user_input.get("credential", "").strip()
            hostname = user_input.get("hostname", "").strip()
            device_name = user_input.get("device_name", f"Dyson {serial_number}").strip()

            errors = {}
            if not serial_number:
                errors["serial_number"] = "required"
            if not credential:
                errors["credential"] = "required"

            if not errors:
                # Create entry
                config_data = {
                    "serial_number": serial_number,
                    "credential": credential,
                    "discovery_method": "manual",
                    "connection_type": "local_only",
                    "device_name": device_name,
                }

                if hostname:
                    config_data["hostname"] = hostname

                return {"type": "create_entry", "title": device_name, "data": config_data}
            else:
                return {"type": "form", "step_id": "manual_device", "errors": errors}

        return {
            "type": "form",
            "step_id": "manual_device",
            "data_schema": {
                "serial_number": "Device Serial Number",
                "credential": "Device WiFi Password",
                "hostname": "Device IP Address (Optional)",
                "device_name": "Device Name (Optional)",
            },
            "errors": {},
        }


async def demo_config_flows():
    """Demonstrate the different configuration flow paths."""

    print("🔧 Dyson Alternative Integration - Configuration Flow Demo")
    print("=" * 60)

    # Test 1: Initial menu
    print("\n📋 Test 1: Initial Setup Menu")
    print("-" * 30)

    flow = MockConfigFlow()
    result = await flow.async_step_user()
    print(f"Step: {result['step_id']}")
    print(f"Options: {list(result['data_schema']['setup_method'].keys())}")
    print(f"Display: {list(result['data_schema']['setup_method'].values())}")

    # Test 2: Cloud account selection
    print("\n☁️  Test 2: Cloud Account Path")
    print("-" * 30)

    flow = MockConfigFlow()
    # User selects cloud account
    await flow.async_step_user({"setup_method": "cloud_account"})
    print("Step taken: user -> cloud_account")
    print("→ Proceeds to cloud authentication (email/password)")

    # Test 3: Manual device selection
    print("\n🔧 Test 3: Manual Device Path")
    print("-" * 30)

    flow = MockConfigFlow()
    # User selects manual device
    result = await flow.async_step_user({"setup_method": "manual_device"})
    print(f"Step: {result['step_id']}")
    print(f"Required fields: {[k for k, v in result['data_schema'].items() if 'Optional' not in v]}")
    print(f"Optional fields: {[k for k, v in result['data_schema'].items() if 'Optional' in v]}")

    # Test 4: Manual device completion
    print("\n✅ Test 4: Manual Device Entry Creation")
    print("-" * 30)

    flow = MockConfigFlow()
    # Complete manual setup
    result = await flow.async_step_manual_device(
        {
            "serial_number": "123-AB-CD456789",
            "credential": "MyWiFiPassword123",
            "hostname": "192.168.1.100",
            "device_name": "Living Room Air Purifier",
        }
    )

    print(f"Result: {result['type']}")
    print(f"Device Name: {result['title']}")
    print(f"Configuration: {result['data']}")

    # Test 5: Step history
    print("\n📊 Test 5: Configuration Flow History")
    print("-" * 30)

    print("Steps taken:")
    for i, (step, input_data) in enumerate(flow.step_history, 1):
        print(f"  {i}. {step}: {input_data is not None}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(demo_config_flows())
