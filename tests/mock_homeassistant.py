"""Mock Home Assistant components for testing and development."""

import sys
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock


class MockConfigEntry:
    """Mock config entry for testing."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.entry_id = "test_entry_id"
        self.domain = "hass_dyson"
        self.title = "Test Dyson Device"


class MockHomeAssistant:
    """Mock Home Assistant core for testing."""

    def __init__(self):
        self.bus = MagicMock()
        self.bus.async_fire = AsyncMock()


class MockDataUpdateCoordinator:
    """Mock DataUpdateCoordinator for testing."""

    def __init__(self, hass, logger, name, update_interval=None):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = {}

    async def async_config_entry_first_refresh(self):
        """Mock first refresh."""
        pass

    async def async_request_refresh(self):
        """Mock refresh request."""
        pass


class MockEntity:
    """Mock entity base class."""

    def __init__(self):
        self._available = True
        self._name = "Mock Entity"


class MockFanEntity(MockEntity):
    """Mock fan entity."""

    def __init__(self):
        super().__init__()
        self._is_on = False
        self._speed = None


class MockSensorEntity(MockEntity):
    """Mock sensor entity."""

    def __init__(self):
        super().__init__()
        self._state = None


class MockPlatform:
    """Mock platform constants."""

    FAN = "fan"
    SENSOR = "sensor"


# Mock Home Assistant modules
homeassistant_mock = MagicMock()
homeassistant_mock.core.HomeAssistant = MockHomeAssistant
homeassistant_mock.config_entries.ConfigEntry = MockConfigEntry
homeassistant_mock.const.Platform = MockPlatform
homeassistant_mock.helpers.update_coordinator.DataUpdateCoordinator = MockDataUpdateCoordinator
homeassistant_mock.helpers.entity.Entity = MockEntity
homeassistant_mock.components.fan.FanEntity = MockFanEntity
homeassistant_mock.components.sensor.SensorEntity = MockSensorEntity

# Install mocks in sys.modules
sys.modules["homeassistant"] = homeassistant_mock
sys.modules["homeassistant.core"] = homeassistant_mock.core
sys.modules["homeassistant.config_entries"] = homeassistant_mock.config_entries
sys.modules["homeassistant.const"] = homeassistant_mock.const
sys.modules["homeassistant.helpers"] = homeassistant_mock.helpers
sys.modules["homeassistant.helpers.update_coordinator"] = homeassistant_mock.helpers.update_coordinator
sys.modules["homeassistant.helpers.entity"] = homeassistant_mock.helpers.entity
sys.modules["homeassistant.components"] = homeassistant_mock.components
sys.modules["homeassistant.components.fan"] = homeassistant_mock.components.fan
sys.modules["homeassistant.components.sensor"] = homeassistant_mock.components.sensor
sys.modules["homeassistant.exceptions"] = MagicMock()

# Mock libdyson libraries for testing
libdyson_rest_mock = MagicMock()
paho_mqtt_mock = MagicMock()

sys.modules["libdyson_rest"] = libdyson_rest_mock
sys.modules["paho"] = paho_mqtt_mock
sys.modules["paho.mqtt"] = paho_mqtt_mock
sys.modules["paho.mqtt.client"] = paho_mqtt_mock
