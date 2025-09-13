#!/usr/bin/env python3
"""Quick test to verify AsyncDysonClient import and basic functionality."""

import asyncio


async def test_async_client_import():
    """Test that we can import and instantiate AsyncDysonClient."""
    try:
        from libdyson_rest import AsyncDysonClient

        print("✅ Successfully imported AsyncDysonClient")

        # Test instantiation
        client = AsyncDysonClient(email="test@example.com")
        print("✅ Successfully instantiated AsyncDysonClient")
        # Close the client to prevent resource warnings
        await client.close()

        # Test context manager support
        async with AsyncDysonClient(email="test@example.com") as ctx_client:
            print("✅ Successfully used AsyncDysonClient as context manager")
            # Verify the context manager client is valid
            assert ctx_client is not None, "Context manager client should not be None"
            # Context manager automatically closes the client

        print("✅ All async client tests passed!")
        return True

    except ImportError as e:
        print(f"❌ Failed to import AsyncDysonClient: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing AsyncDysonClient: {e}")
        return False


async def test_exception_imports():
    """Test that we can import exception classes."""
    try:
        # Just test that the exceptions module exists and can be imported
        from libdyson_rest import exceptions

        # Check that the expected exception classes exist
        assert hasattr(exceptions, "DysonAPIError"), "DysonAPIError not found"
        assert hasattr(exceptions, "DysonAuthError"), "DysonAuthError not found"
        assert hasattr(exceptions, "DysonConnectionError"), "DysonConnectionError not found"

        print("✅ Successfully imported exception classes")
        return True
    except ImportError as e:
        print(f"❌ Failed to import exception classes: {e}")
        return False
    except AssertionError as e:
        print(f"❌ Exception class missing: {e}")
        return False


async def main():
    """Run all tests."""
    print("Testing libdyson-rest 0.7.0b1 async functionality...")

    success = True
    success &= await test_async_client_import()
    success &= await test_exception_imports()

    if success:
        print("\n🎉 All tests passed! Migration to AsyncDysonClient should work correctly.")
    else:
        print("\n❌ Some tests failed. Check the libdyson-rest installation.")

    return success


if __name__ == "__main__":
    asyncio.run(main())
