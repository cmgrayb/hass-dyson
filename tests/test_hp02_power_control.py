"""Test HP02-style power control detection and functionality."""

from unittest.mock import AsyncMock

import pytest

from custom_components.hass_dyson.device import DysonDevice


class TestHP02PowerControlDetection:
    """Test automatic detection of HP02-style (fmod-based) power control."""

    @pytest.fixture
    def hp02_device(self, mock_hass):
        """Create device configured for HP02-style testing."""
        return DysonDevice(
            hass=mock_hass,
            serial_number="HP02-TEST-001",
            host="192.168.1.100",
            credential="test_cred",
        )

    @pytest.fixture
    def modern_device(self, mock_hass):
        """Create device configured for modern fpwr-style testing."""
        return DysonDevice(
            hass=mock_hass,
            serial_number="MODERN-TEST-001",
            host="192.168.1.101",
            credential="test_cred",
        )

    def test_power_control_detection_insufficient_messages(self, hp02_device):
        """Test that detection returns unknown with no messages."""
        # 0 messages should still return unknown
        hp02_device._total_state_messages = 0
        hp02_device._fpwr_message_count = 0
        hp02_device._fmod_message_count = 0

        result = hp02_device._detect_power_control_type()
        assert result == "unknown"

        # But with even 1 message containing fmod data, detection should work
        hp02_device._total_state_messages = 1
        hp02_device._fmod_message_count = 1

        result = hp02_device._detect_power_control_type()
        assert result == "fmod"

    def test_power_control_detection_fpwr_device(self, modern_device):
        """Test detection of fpwr-based device (modern devices)."""
        # Simulate receiving 3 STATE-CHANGE messages with fpwr
        modern_device._total_state_messages = 3
        modern_device._fpwr_message_count = 3
        modern_device._fmod_message_count = 0

        result = modern_device._detect_power_control_type()
        assert result == "fpwr"

    def test_power_control_detection_fmod_device(self, hp02_device):
        """Test detection of fmod-based device (HP02-style)."""
        # Simulate receiving 3 STATE-CHANGE messages with fmod but no fpwr
        hp02_device._total_state_messages = 3
        hp02_device._fpwr_message_count = 0
        hp02_device._fmod_message_count = 3

        result = hp02_device._detect_power_control_type()
        assert result == "fmod"

    def test_power_control_detection_mixed_messages_prefer_fpwr(self, modern_device):
        """Test that any fpwr presence indicates fpwr-based device."""
        # If we see even one fpwr, it's an fpwr device
        modern_device._total_state_messages = 5
        modern_device._fpwr_message_count = 1  # Even one fpwr message
        modern_device._fmod_message_count = 4  # Mostly fmod but fpwr wins

        result = modern_device._detect_power_control_type()
        assert result == "fpwr"

    def test_power_control_detection_no_relevant_fields(self, hp02_device):
        """Test detection when no fpwr or fmod fields seen."""
        # 3 messages but no fpwr or fmod fields
        hp02_device._total_state_messages = 3
        hp02_device._fpwr_message_count = 0
        hp02_device._fmod_message_count = 0

        result = hp02_device._detect_power_control_type()
        assert result == "unknown"


class TestHP02PowerStateDetection:
    """Test power state detection for different device types."""

    @pytest.fixture
    def hp02_device(self, mock_hass):
        """Create HP02 device with fmod-based detection."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="HP02-TEST-001",
            host="192.168.1.100",
            credential="test_cred",
        )
        # Simulate HP02 detection
        device._power_control_type = "fmod"
        return device

    @pytest.fixture
    def modern_device(self, mock_hass):
        """Create modern device with fpwr-based detection."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="MODERN-TEST-001",
            host="192.168.1.101",
            credential="test_cred",
        )
        # Simulate modern device detection
        device._power_control_type = "fpwr"
        return device

    def test_hp02_fan_power_fmod_fan(self, hp02_device):
        """Test HP02 fan_power property when fmod is FAN."""
        hp02_device._state_data = {"product-state": {"fmod": "FAN"}}

        result = hp02_device.fan_power
        assert result is True

    def test_hp02_fan_power_fmod_auto(self, hp02_device):
        """Test HP02 fan_power property when fmod is AUTO."""
        hp02_device._state_data = {"product-state": {"fmod": "AUTO"}}

        result = hp02_device.fan_power
        assert result is True

    def test_hp02_fan_power_fmod_off(self, hp02_device):
        """Test HP02 fan_power property when fmod is OFF."""
        hp02_device._state_data = {"product-state": {"fmod": "OFF"}}

        result = hp02_device.fan_power
        assert result is False

    def test_hp02_fan_power_fmod_missing(self, hp02_device):
        """Test HP02 fan_power property when fmod is missing."""
        hp02_device._state_data = {"product-state": {"fnst": "FAN"}}

        result = hp02_device.fan_power
        assert result is False  # HP02 should use fmod, not fallback

    def test_modern_fan_power_fpwr_on(self, modern_device):
        """Test modern device fan_power property when fpwr is ON."""
        modern_device._state_data = {"product-state": {"fpwr": "ON"}}

        result = modern_device.fan_power
        assert result is True

    def test_modern_fan_power_fpwr_off(self, modern_device):
        """Test modern device fan_power property when fpwr is OFF."""
        modern_device._state_data = {"product-state": {"fpwr": "OFF"}}

        result = modern_device.fan_power
        assert result is False

    def test_modern_fan_power_fallback_to_fnst(self, modern_device):
        """Test modern device fan_power fallback to fnst when fpwr missing."""
        modern_device._state_data = {"product-state": {"fnst": "FAN"}}

        result = modern_device.fan_power
        assert result is True  # Should fallback to fnst


class TestHP02PowerControlCommands:
    """Test power control commands for different device types."""

    @pytest.fixture
    def hp02_device(self, mock_hass):
        """Create HP02 device with fmod-based control."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="HP02-TEST-001",
            host="192.168.1.100",
            credential="test_cred",
        )
        # Simulate HP02 detection
        device._power_control_type = "fmod"
        return device

    @pytest.fixture
    def modern_device(self, mock_hass):
        """Create modern device with fpwr-based control."""
        device = DysonDevice(
            hass=mock_hass,
            serial_number="MODERN-TEST-001",
            host="192.168.1.101",
            credential="test_cred",
        )
        # Simulate modern device detection
        device._power_control_type = "fpwr"
        return device

    @pytest.mark.asyncio
    async def test_hp02_set_fan_power_on(self, hp02_device):
        """Test HP02 set_fan_power(True) uses fmod FAN command."""
        # Mock send_command
        hp02_device.send_command = AsyncMock()

        await hp02_device.set_fan_power(True)

        hp02_device.send_command.assert_called_once_with("STATE-SET", {"fmod": "FAN"})

    @pytest.mark.asyncio
    async def test_hp02_set_fan_power_off(self, hp02_device):
        """Test HP02 set_fan_power(False) uses fmod OFF command."""
        # Mock send_command
        hp02_device.send_command = AsyncMock()

        await hp02_device.set_fan_power(False)

        hp02_device.send_command.assert_called_once_with("STATE-SET", {"fmod": "OFF"})

    @pytest.mark.asyncio
    async def test_modern_set_fan_power_on(self, modern_device):
        """Test modern set_fan_power(True) uses fpwr ON command."""
        # Mock send_command
        modern_device.send_command = AsyncMock()

        await modern_device.set_fan_power(True)

        modern_device.send_command.assert_called_once_with("STATE-SET", {"fpwr": "ON"})

    @pytest.mark.asyncio
    async def test_modern_set_fan_power_off(self, modern_device):
        """Test modern set_fan_power(False) uses fpwr OFF command."""
        # Mock send_command
        modern_device.send_command = AsyncMock()

        await modern_device.set_fan_power(False)

        modern_device.send_command.assert_called_once_with("STATE-SET", {"fpwr": "OFF"})


class TestAutomaticDetectionFromMessages:
    """Test automatic detection from real MQTT message flow."""

    @pytest.fixture
    def detecting_device(self, mock_hass):
        """Create device in detection phase (no type set yet)."""
        return DysonDevice(
            hass=mock_hass,
            serial_number="DETECT-TEST-001",
            host="192.168.1.102",
            credential="test_cred",
        )

    def test_hp02_detection_from_state_change_messages(self, detecting_device):
        """Test HP02 detection from actual STATE-CHANGE messages."""
        # Simulate 3 STATE-CHANGE messages like HP02 sends (no fpwr, has fmod)
        hp02_messages = [
            {
                "msg": "STATE-CHANGE",
                "product-state": {"fmod": ["OFF", "FAN"], "fnst": ["OFF", "FAN"]},
            },
            {
                "msg": "STATE-CHANGE",
                "product-state": {"fmod": ["FAN", "OFF"], "fnst": ["FAN", "OFF"]},
            },
            {
                "msg": "STATE-CHANGE",
                "product-state": {"fmod": ["OFF", "AUTO"], "fnst": ["OFF", "AUTO"]},
            },
        ]

        for i, message_data in enumerate(hp02_messages):
            detecting_device._process_message_data(message_data, f"test/topic/{i}")

        # Should detect as fmod-based after 3 messages
        assert detecting_device._power_control_type == "fmod"
        assert detecting_device._fpwr_message_count == 0
        assert detecting_device._fmod_message_count == 3
        assert detecting_device._total_state_messages == 3

    def test_modern_detection_from_state_change_messages(self, detecting_device):
        """Test modern device detection from STATE-CHANGE messages with fpwr."""
        # Simulate modern device STATE-CHANGE messages (has fpwr)
        modern_messages = [
            {
                "msg": "STATE-CHANGE",
                "product-state": {"fpwr": ["OFF", "ON"], "fnst": ["OFF", "FAN"]},
            },
            {
                "msg": "STATE-CHANGE",
                "product-state": {"fpwr": ["ON", "OFF"], "fnst": ["FAN", "OFF"]},
            },
            {
                "msg": "STATE-CHANGE",
                "product-state": {"fpwr": ["OFF", "ON"], "auto": ["OFF", "ON"]},
            },
        ]

        for i, message_data in enumerate(modern_messages):
            detecting_device._process_message_data(message_data, f"test/topic/{i}")

        # Should detect as fpwr-based after seeing fpwr in messages
        assert detecting_device._power_control_type == "fpwr"
        assert detecting_device._fpwr_message_count == 3
        assert detecting_device._fmod_message_count == 0
        assert detecting_device._total_state_messages == 3

    def test_gradual_detection_with_mixed_messages(self, detecting_device):
        """Test that detection works with mixed message types and triggers after first STATE-CHANGE."""
        # First message: no detection yet
        detecting_device._process_message_data(
            {"msg": "CURRENT-STATE", "product-state": {"fmod": "FAN"}},
            "test/topic/current",
        )
        assert detecting_device._power_control_type is None  # Not a STATE-CHANGE

        # First STATE-CHANGE message should trigger immediate detection (optimized fallback)
        detecting_device._process_message_data(
            {"msg": "STATE-CHANGE", "product-state": {"fmod": ["OFF", "FAN"]}},
            "test/topic/change1",
        )
        assert (
            detecting_device._power_control_type == "fmod"
        )  # 1 message now triggers detection

        # Verify counters are correct
        assert detecting_device._fpwr_message_count == 0
        assert detecting_device._fmod_message_count == 1
        assert detecting_device._total_state_messages == 1
