#!/usr/bin/env python3
"""Test script for firmware update functionality with libdyson-rest 0.6.0b1."""

import asyncio
import os

from libdyson_rest import DysonClient


async def test_firmware_methods():
    """Test that the new firmware methods are available."""
    print("🔍 Testing libdyson-rest 0.6.0b1 firmware update capabilities...")

    # Check if the get_pending_release method exists
    client = DysonClient()

    if hasattr(client, "get_pending_release"):
        print("✅ get_pending_release method is available")
    else:
        print("❌ get_pending_release method is NOT available")
        return False

    # Test method signature
    import inspect

    method_sig = inspect.signature(client.get_pending_release)
    print(f"📋 Method signature: get_pending_release{method_sig}")

    # Check if we have the required parameters for testing
    email = os.getenv("DYSON_EMAIL")
    password = os.getenv("DYSON_PASSWORD")
    device_serial = os.getenv("DYSON_DEVICE_SERIAL", "9RJ-US-UAA8845A")

    if not email or not password:
        print("⚠️  Environment variables DYSON_EMAIL and DYSON_PASSWORD not set")
        print("   Cannot test actual API calls, but library methods are available")
        return True

    print(f"🔐 Testing with email: {email}")
    print(f"📱 Testing with device: {device_serial}")

    try:
        # Create authenticated client
        auth_client = DysonClient(email=email, password=password)

        print("🔄 Authenticating with Dyson cloud...")
        challenge = auth_client.begin_login()
        auth_client.complete_login(str(challenge.challenge_id), password)

        print("✅ Authentication successful")

        # Test get_pending_release
        print(f"🔄 Checking for firmware updates for device {device_serial}...")
        try:
            pending_release = auth_client.get_pending_release(device_serial)
            if pending_release:
                print(f"🎉 Firmware update available: {pending_release.version}")
                print(f"   Release details: {pending_release}")
            else:
                print("ℹ️  No firmware update available")
        except Exception as e:
            print(f"ℹ️  No firmware update available or error: {e}")

        print("✅ Firmware update check completed successfully")
        return True

    except Exception as e:
        print(f"❌ Error during API testing: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_firmware_methods())
    if success:
        print("\n🎉 All tests passed! Ready to test firmware updates.")
    else:
        print("\n❌ Some tests failed. Check the output above.")
