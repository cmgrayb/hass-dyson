"""Test configuration for Dyson integration."""

import asyncio
import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Apply comprehensive monkey patching to prevent Home Assistant plugin teardown errors
def _get_safe_event_loop():
    """Get event loop safely, handling RuntimeError."""
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        return None


def _patch_shutdown_executor(event_loop):
    """Patch the shutdown_default_executor to prevent errors."""
    from unittest.mock import patch as mock_patch

    def safe_shutdown():
        return None

    return mock_patch.object(
        event_loop, "shutdown_default_executor", return_value=safe_shutdown()
    )


def _cleanup_tasks(event_loop, tasks_before, expected_lingering_tasks):
    """Clean up asyncio tasks safely."""
    if event_loop.is_closed():
        return

    tasks = asyncio.all_tasks(event_loop) - tasks_before
    for task in tasks:
        if expected_lingering_tasks:
            task.cancel()
        else:
            task.cancel()

    if tasks:
        try:
            event_loop.run_until_complete(asyncio.wait(tasks, timeout=0.1))
        except (TimeoutError, RuntimeError, OSError):
            pass  # Ignore cleanup errors


def _cleanup_threads(threads_before):
    """Clean up threads safely."""
    import threading

    threads = frozenset(threading.enumerate()) - threads_before
    for thread in threads:
        # Allow certain system threads
        if hasattr(thread, "name") and (
            thread.name.startswith("waitpid-")
            or "_run_safe_shutdown_loop" in thread.name
            or isinstance(thread, threading._DummyThread)
        ):
            continue


# Configure warnings and event loop handling
@pytest.fixture(scope="session", autouse=True)
def configure_test_environment():
    """Configure the test environment to handle async teardown issues."""
    # Comprehensive warning suppression for all async/event loop related warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="asyncio")
    warnings.filterwarnings("ignore", message="Event loop is closed")
    warnings.filterwarnings("ignore", message="coroutine.*was never awaited")
    warnings.filterwarnings(
        "ignore", message=".*shutdown_default_executor.*was never awaited"
    )
    warnings.filterwarnings(
        "ignore", message=".*BaseEventLoop.shutdown_default_executor.*"
    )
    warnings.filterwarnings("ignore", message=".*unawaited coroutine.*")
    warnings.filterwarnings(
        "ignore", message=".*was never awaited.*", category=RuntimeWarning
    )
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="datetime")

    # Additional warnings for coverage and pytest internals
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="_pytest")
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="coverage")
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="unittest.mock")


def _cancel_pending_tasks(loop):
    """Cancel all pending tasks in the event loop."""
    pending = asyncio.all_tasks(loop)
    for task in pending:
        if not task.done():
            task.cancel()
    return pending


def _gather_cancelled_tasks(loop, pending):
    """Gather cancelled tasks with error handling."""
    if not pending:
        return

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except Exception:
        pass


def _shutdown_async_generators(loop):
    """Shutdown async generators safely."""
    try:
        loop.run_until_complete(loop.shutdown_asyncgens())
    except Exception:
        pass


def _perform_cleanup(loop):
    """Perform the main cleanup operations."""
    if not loop or loop.is_closed():
        return

    # Cancel all pending tasks
    pending = _cancel_pending_tasks(loop)

    # Give tasks a chance to clean up
    _gather_cancelled_tasks(loop, pending)

    # Try to shutdown async resources gracefully
    _shutdown_async_generators(loop)


@pytest.fixture(autouse=True, scope="function")
def handle_event_loop_cleanup():
    """Enhanced event loop cleanup without aggressive isolation."""
    import gc

    yield

    # Gentle cleanup after test
    try:
        # Get current loop if it exists
        loop = _get_safe_event_loop()
        _perform_cleanup(loop)
        # Don't close the loop - let pytest handle that

    except Exception:
        # Ignore all cleanup exceptions
        pass
    finally:
        # Force garbage collection with warning suppression
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            gc.collect()


@pytest.fixture(autouse=True, scope="function")
def suppress_runtime_warnings():
    """Suppress runtime warnings during test execution and cleanup."""
    import io
    import sys

    # Capture and suppress stderr during teardown
    original_stderr = sys.stderr

    yield

    # Temporarily redirect stderr to suppress teardown warnings
    try:
        sys.stderr = io.StringIO()
        # Force one final garbage collection
        import gc

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gc.collect()
    finally:
        sys.stderr = original_stderr


@pytest.fixture
def mock_dyson_device():
    """Create a mock Dyson device for testing."""
    device = MagicMock()
    device.serial_number = "TEST-SERIAL-123"
    device.hostname = "test-device.local"
    device.username = "TEST-SERIAL-123"
    device.password = "test-password"
    device.is_connected = True
    device.connect = AsyncMock(return_value=True)
    device.disconnect = AsyncMock()
    device.send_command = AsyncMock()
    device.get_state = AsyncMock(return_value={})
    device.get_faults = AsyncMock(return_value=[])

    # Add fan control methods
    device.set_fan_power = AsyncMock()
    device.set_fan_speed = AsyncMock()
    device.set_oscillation = AsyncMock()
    device.set_direction = AsyncMock()

    return device


@pytest.fixture
def mock_cloud_devices():
    """Create mock cloud device data for testing."""
    return [
        {
            "serial": "TEST-DEVICE-001",
            "name": "Living Room Fan",
            "model": "DP04",
            "category": "ec",
            "capabilities": ["AdvanceOscillationDay1", "ExtendedAQ"],
            "hostname": "192.168.1.100",
            "username": "TEST-DEVICE-001",
            "password": "mqtt-password-001",
        },
        {
            "serial": "TEST-DEVICE-002",
            "name": "Bedroom Purifier",
            "model": "HP04",
            "category": "ec",
            "capabilities": ["Scheduling", "EnvironmentalData"],
            "hostname": "192.168.1.101",
            "username": "TEST-DEVICE-002",
            "password": "mqtt-password-002",
        },
    ]


@pytest.fixture
def mock_libdyson_rest():
    """Mock libdyson-rest library."""
    with patch("libdyson_rest.DysonCloudClient") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.authenticate = AsyncMock(return_value=True)
        mock_instance.get_devices = AsyncMock()
        yield mock_instance


@pytest.fixture
def mock_paho_mqtt():
    """Mock paho-mqtt library."""
    with patch("paho.mqtt.client.Client") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.connect = MagicMock(return_value=0)  # CONNACK_ACCEPTED
        mock_instance.disconnect = MagicMock()
        mock_instance.publish = MagicMock()
        mock_instance.subscribe = MagicMock()
        mock_instance.loop_start = MagicMock()
        mock_instance.loop_stop = MagicMock()
        yield mock_instance


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance for testing."""
    hass = MagicMock()
    hass.data = {}

    # Add config attributes for country/culture detection
    mock_config = MagicMock()
    mock_config.country = "US"
    mock_config.language = "en"
    hass.config = mock_config

    # Add attributes needed for config flow tests
    hass.config_entries = MagicMock()
    hass.config_entries.async_entries.return_value = []

    # Add missing attributes for frame helper
    import threading

    hass.loop_thread_id = threading.get_ident()  # Use current thread ID
    hass.loop = MagicMock()  # Mock event loop

    return hass


@pytest.fixture
def mock_coordinator():
    """Create a centralized mock coordinator with proper async cleanup."""
    coordinator = MagicMock()
    coordinator.serial_number = "TEST-SERIAL-123"  # Restored to match existing tests
    coordinator.device_name = "Test Dyson"
    coordinator.device = MagicMock()
    coordinator.device.is_connected = True
    coordinator.device_capabilities = ["Heating", "EnvironmentalData", "ExtendedAQ"]
    coordinator.device_category = ["ec"]  # Add device category for WiFi sensor tests

    # Complete coordinator.data structure for dynamic sensor detection
    coordinator.data = {
        "product-state": {
            "hmod": "OFF",  # Add heating mode key for heating-capable devices
            "pm25": "0010",
            "pm10": "0015",
            "hmax": "0030",
            "cflt": "CARF",  # Carbon filter type for carbon filter sensors
        },
        "environmental-data": {
            "pm25": "10",
            "pm10": "15",
            "co2": "800",  # CO2 data for CO2 sensor
            "no2": "25",  # NO2 data for NO2 sensor
            "hcho": "5",  # HCHO data for formaldehyde sensor
            "tact": "2950",  # Temperature actual in Kelvin * 10 (295.0K = 21.85°C)
            "hact": "0045",  # Humidity actual as percentage (45%)
        },
    }

    coordinator.async_send_command = AsyncMock()
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {"connection_type": "cloud"}
    coordinator.last_update_success = True

    # Firmware-specific attributes
    coordinator.firmware_version = "1.0.0"
    coordinator.firmware_latest_version = "1.0.1"
    coordinator.firmware_update_in_progress = False
    coordinator.async_check_firmware_update = AsyncMock(return_value=True)
    coordinator.async_install_firmware_update = AsyncMock(return_value=True)

    # Ensure proper cleanup after each test
    yield coordinator

    # Clean up any async resources and mocks
    try:
        # Reset all mock calls
        coordinator.reset_mock()
        if hasattr(coordinator, "device") and coordinator.device:
            coordinator.device.reset_mock()
        if hasattr(coordinator, "async_send_command"):
            coordinator.async_send_command.reset_mock()
        if hasattr(coordinator, "async_check_firmware_update"):
            coordinator.async_check_firmware_update.reset_mock()
        if hasattr(coordinator, "async_install_firmware_update"):
            coordinator.async_install_firmware_update.reset_mock()
    except Exception:
        pass


# ============================================================================
# PURE PYTEST FIXTURES - Phase 1 Migration Infrastructure
# ============================================================================
# These fixtures provide pure pytest alternatives to pytest-homeassistant-custom-component
# They can run alongside the existing plugin during the migration period


@pytest.fixture
def pure_mock_hass():
    """Pure pytest version of Home Assistant mock without plugin dependencies."""
    import asyncio
    import threading

    from homeassistant.config_entries import ConfigEntries
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceRegistry
    from homeassistant.helpers.entity_registry import EntityRegistry

    # Create mock Home Assistant instance
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}

    # Mock config object with realistic attributes - don't import Config class
    mock_config = MagicMock()
    mock_config.country = "US"
    mock_config.language = "en"
    mock_config.time_zone = "UTC"
    mock_config.elevation = 0
    mock_config.latitude = 0.0
    mock_config.longitude = 0.0
    mock_config.location_name = "Test Location"
    mock_config.units = MagicMock()
    mock_config.units.name = "metric"
    hass.config = mock_config

    # Mock event loop and threading
    hass.loop = asyncio.new_event_loop()
    hass.loop_thread_id = threading.get_ident()
    hass.is_running = True
    hass.is_stopping = False

    # Mock core Home Assistant methods
    hass.async_create_task = MagicMock(
        side_effect=lambda coro: asyncio.create_task(coro)
    )
    hass.add_job = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.async_block_till_done = AsyncMock()

    # Mock event bus
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.bus.async_listen = MagicMock()
    hass.bus.async_listen_once = MagicMock()

    # Mock config entries
    hass.config_entries = MagicMock(spec=ConfigEntries)
    hass.config_entries.async_entries = MagicMock(return_value=[])
    hass.config_entries.async_get_entry = MagicMock(return_value=None)
    hass.config_entries.async_update_entry = AsyncMock()
    hass.config_entries.async_reload = AsyncMock()

    # Mock registries
    hass.helpers = MagicMock()
    hass.helpers.entity_registry = MagicMock(spec=EntityRegistry)
    hass.helpers.device_registry = MagicMock(spec=DeviceRegistry)

    # Mock state machine
    hass.states = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    hass.states.async_set = MagicMock()
    hass.states.async_remove = MagicMock()

    return hass


@pytest.fixture
def pure_mock_config_entry():
    """Pure pytest version of config entry mock."""
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

    from custom_components.hass_dyson.const import (
        CONF_CONNECTION_TYPE,
        CONF_DEVICE_TYPE,
        CONF_SERIAL_NUMBER,
    )

    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test-entry-id-12345"
    config_entry.title = "Test Dyson Device"
    config_entry.version = 1
    config_entry.minor_version = 1
    config_entry.source = "user"
    config_entry.state = "loaded"

    # Mock standard config data
    config_entry.data = {
        CONF_SERIAL_NUMBER: "TEST-DEVICE-001",
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "TEST-DEVICE-001",
        CONF_PASSWORD: "test-password-123",
        CONF_CONNECTION_TYPE: "cloud",
        CONF_DEVICE_TYPE: "DP04",
    }

    # Mock options
    config_entry.options = {}

    # Mock methods
    config_entry.add_update_listener = MagicMock()
    config_entry.async_on_unload = MagicMock()

    return config_entry


@pytest.fixture
def pure_mock_coordinator(pure_mock_hass):
    """Pure pytest version of coordinator mock without plugin dependencies."""
    from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

    # Mock coordinator instance
    coordinator = MagicMock(spec=DysonDataUpdateCoordinator)

    # Add hass reference that entities need
    coordinator.hass = pure_mock_hass

    # Essential attributes
    coordinator.serial_number = "TEST-DEVICE-001"
    coordinator.device_name = "Living Room Fan"
    coordinator.device_type = "DP04"
    coordinator.is_connected = True
    coordinator.last_update_success = True
    coordinator.update_interval = 30

    # Mock device capabilities
    coordinator.device_capabilities = [
        "AdvanceOscillationDay1",
        "ExtendedAQ",
        "EnvironmentalData",
        "Heating",
    ]
    coordinator.device_category = ["ec"]

    # Mock device data structure
    coordinator.data = {
        "product-state": {
            "fpwr": "ON",  # Fan power
            "fnsp": "0005",  # Fan speed
            "fdir": "ON",  # Direction
            "oson": "ON",  # Oscillation
            "hmod": "OFF",  # Heating mode
            "hmax": "0030",  # Heating target temp
            "pm25": "0010",  # PM2.5 filter life
            "pm10": "0015",  # PM10 filter life
            "cflt": "CARF",  # Carbon filter type
        },
        "environmental-data": {
            "pm25": "0010",  # PM2.5 reading
            "pm10": "0015",  # PM10 reading
            "co2": "0800",  # CO2 reading
            "no2": "0025",  # NO2 reading
            "hcho": "0005",  # Formaldehyde reading
            "tact": "2950",  # Temperature (Kelvin * 10)
            "hact": "0045",  # Humidity percentage
        },
        "faults": [],
    }

    # Mock device object
    coordinator.device = MagicMock()
    coordinator.device.is_connected = True
    coordinator.device.serial_number = coordinator.serial_number
    coordinator.device.hostname = "192.168.1.100"
    coordinator.device.username = coordinator.serial_number
    coordinator.device.password = "test-password-123"

    # Mock device methods
    coordinator.device.connect = AsyncMock(return_value=True)
    coordinator.device.disconnect = AsyncMock()
    coordinator.device.get_state = AsyncMock(return_value=coordinator.data)
    coordinator.device.send_command = AsyncMock()

    # Add get_state_value method for switch entities
    def mock_get_state_value(data_dict, key, default=None):
        """Mock implementation of device get_state_value method."""
        return data_dict.get(key, default)

    coordinator.device.get_state_value = MagicMock(side_effect=mock_get_state_value)

    # Fan control methods
    coordinator.device.set_fan_power = AsyncMock()
    coordinator.device.set_fan_speed = AsyncMock()
    coordinator.device.set_oscillation = AsyncMock()
    coordinator.device.set_direction = AsyncMock()
    coordinator.device.set_sleep_timer = AsyncMock()

    # Heating control methods
    coordinator.device.set_heating = AsyncMock()
    coordinator.device.set_heating_target = AsyncMock()

    # Mock coordinator methods
    coordinator.async_update_data = AsyncMock(return_value=coordinator.data)
    coordinator.async_send_command = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()

    # Mock config entry reference
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {
        "connection_type": "cloud",
        "serial_number": coordinator.serial_number,
    }

    # Firmware update capabilities
    coordinator.firmware_version = "1.0.0"
    coordinator.firmware_latest_version = "1.0.1"
    coordinator.firmware_update_in_progress = False
    coordinator.async_check_firmware_update = AsyncMock(return_value=True)
    coordinator.async_install_firmware_update = AsyncMock(return_value=True)

    return coordinator


@pytest.fixture
def pure_mock_sensor_entity():
    """Create a mock for testing sensor entities that bypasses HA framework calls."""

    def create_sensor_with_mock(sensor_class, coordinator, *args, **kwargs):
        """Create a sensor instance with mocked HA framework dependencies."""
        # Create sensor instance with any additional arguments
        sensor = sensor_class(coordinator, *args, **kwargs)

        # Mock HA framework attributes that entities try to access
        sensor.hass = coordinator.hass
        sensor.platform_data = MagicMock()
        sensor.platform_data.platform_name = "sensor"
        sensor.platform_data.domain = "hass_dyson"

        # Mock entity properties to avoid HA framework calls
        sensor._attr_has_entity_name = True
        sensor.entity_registry_enabled_default = True
        sensor.entity_registry_visible_default = True

        # Mock methods that trigger HA framework calls
        sensor.async_write_ha_state = MagicMock()
        sensor._async_verify_state_writable = MagicMock()

        return sensor

    return create_sensor_with_mock


@pytest.fixture
def pure_mock_binary_sensor_entity():
    """Create a mock for testing binary sensor entities that bypasses HA framework calls."""

    def create_binary_sensor_with_mock(
        binary_sensor_class, coordinator, *args, **kwargs
    ):
        """Create a binary sensor instance with mocked HA framework dependencies."""
        # Create binary sensor instance with any additional arguments
        binary_sensor = binary_sensor_class(coordinator, *args, **kwargs)

        # Mock HA framework attributes that entities try to access
        binary_sensor.hass = coordinator.hass
        binary_sensor.platform_data = MagicMock()
        binary_sensor.platform_data.platform_name = "binary_sensor"
        binary_sensor.platform_data.domain = "hass_dyson"

        # Mock entity properties to avoid HA framework calls
        binary_sensor._attr_has_entity_name = True
        binary_sensor.entity_registry_enabled_default = True
        binary_sensor.entity_registry_visible_default = True

        # Mock methods that trigger HA framework calls
        binary_sensor.async_write_ha_state = MagicMock()
        binary_sensor._async_verify_state_writable = MagicMock()

        # Mock async_on_remove which might be called during cleanup
        binary_sensor.async_on_remove = MagicMock()

        # Initialize the entity by calling _handle_coordinator_update
        binary_sensor._handle_coordinator_update()

        return binary_sensor

    return create_binary_sensor_with_mock


@pytest.fixture
def pure_mock_entity_registry():
    """Pure pytest version of entity registry mock."""
    from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntry

    registry = MagicMock(spec=EntityRegistry)
    registry.entities = {}
    registry.async_get = MagicMock(return_value=None)
    registry.async_get_entity_id = MagicMock(return_value=None)
    registry.async_update_entity = AsyncMock()
    registry.async_remove = AsyncMock()

    # Mock registry entry creation
    def create_mock_entry(entity_id, unique_id=None, platform=DOMAIN):
        entry = MagicMock(spec=RegistryEntry)
        entry.entity_id = entity_id
        entry.unique_id = unique_id or f"{DOMAIN}_{entity_id}"
        entry.platform = platform
        entry.name = entity_id.replace("_", " ").title()
        return entry

    registry.async_register = MagicMock(side_effect=create_mock_entry)

    return registry


@pytest.fixture
def pure_mock_device_registry():
    """Pure pytest version of device registry mock."""
    from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry

    registry = MagicMock(spec=DeviceRegistry)
    registry.devices = {}
    registry.async_get = MagicMock(return_value=None)
    registry.async_get_device = MagicMock(return_value=None)
    registry.async_update_device = AsyncMock()

    # Mock device entry creation
    def create_mock_device(identifiers, **kwargs):
        device = MagicMock(spec=DeviceEntry)
        device.identifiers = identifiers
        device.name = kwargs.get("name", "Mock Device")
        device.model = kwargs.get("model", "Mock Model")
        device.manufacturer = kwargs.get("manufacturer", "Dyson")
        device.sw_version = kwargs.get("sw_version", "1.0.0")
        device.id = f"mock_device_{hash(str(identifiers))}"
        return device

    registry.async_get_or_create = AsyncMock(side_effect=create_mock_device)

    return registry


# Import domain constant for fixtures
try:
    from custom_components.hass_dyson.const import DOMAIN
except ImportError:
    DOMAIN = "hass_dyson"
