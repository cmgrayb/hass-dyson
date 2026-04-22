"""Coverage boost tests for services.py targeting specific uncovered branches.

Covers:
- _handle_set_sleep_timer error paths (ConnectionError, ValueError, AttributeError, Exception)
- _handle_cancel_sleep_timer error paths (AttributeError, Exception)
- _handle_set_oscillation_angles error paths (ConnectionError, ValueError, AttributeError)
- _handle_get_cloud_devices with account_email filtering and exception handlers
- _find_cloud_coordinators DysonDataUpdateCoordinator and config_entry fallback paths
- async_handle_refresh_account_data with and without device_id
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from libdyson_rest import DysonAPIError, DysonAuthError, DysonConnectionError

from custom_components.hass_dyson.const import (
    CONF_DISCOVERY_METHOD,
    DISCOVERY_CLOUD,
    DOMAIN,
)
from custom_components.hass_dyson.services import (
    _find_cloud_coordinators,
    _handle_cancel_sleep_timer,
    _handle_get_cloud_devices,
    _handle_set_oscillation_angles,
    _handle_set_sleep_timer,
    async_handle_refresh_account_data,
)


@pytest.fixture
def mock_hass():
    """Create a minimal mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    hass.config_entries = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    return hass


@pytest.fixture
def mock_coordinator():
    """Create a mock device coordinator."""
    coordinator = MagicMock()
    coordinator.serial_number = "VS6-EU-HJA1234A"
    coordinator.device = MagicMock()
    coordinator.device.set_sleep_timer = AsyncMock()
    coordinator.device.set_oscillation_angles = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.async_refresh = AsyncMock()
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {
        CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD,
        "email": "test@example.com",
    }
    coordinator.config_entry.entry_id = "test_entry_id"
    return coordinator


# ===== Sleep timer error handler tests =====


class TestSleepTimerErrorHandlers:
    """Test _handle_set_sleep_timer exception paths."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_set_sleep_timer_connection_error(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test sleep timer raises HomeAssistantError on ConnectionError."""
        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=ConnectionError("Network unreachable")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device", "minutes": 60}

        with pytest.raises(HomeAssistantError, match="Device communication failed"):
            await _handle_set_sleep_timer(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_set_sleep_timer_timeout_error(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test sleep timer raises HomeAssistantError on TimeoutError."""
        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=TimeoutError("Request timed out")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device", "minutes": 30}

        with pytest.raises(HomeAssistantError, match="Device communication failed"):
            await _handle_set_sleep_timer(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_set_sleep_timer_value_error(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test sleep timer raises HomeAssistantError on ValueError."""
        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=ValueError("Invalid timer value")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device", "minutes": 60}

        with pytest.raises(HomeAssistantError, match="Invalid timer value"):
            await _handle_set_sleep_timer(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_set_sleep_timer_type_error(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test sleep timer raises HomeAssistantError on TypeError."""
        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=TypeError("Wrong type")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device", "minutes": 60}

        with pytest.raises(HomeAssistantError, match="Invalid timer value"):
            await _handle_set_sleep_timer(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_set_sleep_timer_attribute_error(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test sleep timer raises HomeAssistantError on AttributeError."""
        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=AttributeError("Method not available")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device", "minutes": 60}

        with pytest.raises(HomeAssistantError, match="Sleep timer not supported"):
            await _handle_set_sleep_timer(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_set_sleep_timer_generic_exception(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test sleep timer raises HomeAssistantError on unexpected Exception."""
        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=RuntimeError("Unexpected failure")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device", "minutes": 60}

        with pytest.raises(HomeAssistantError, match="Failed to set sleep timer"):
            await _handle_set_sleep_timer(mock_hass, call)


# ===== Cancel sleep timer error handler tests =====


class TestCancelSleepTimerErrorHandlers:
    """Test _handle_cancel_sleep_timer exception paths."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_cancel_sleep_timer_connection_error(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test cancel sleep timer raises HomeAssistantError on ConnectionError."""
        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=ConnectionError("Network unreachable")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device"}

        with pytest.raises(HomeAssistantError, match="Device communication failed"):
            await _handle_cancel_sleep_timer(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_cancel_sleep_timer_attribute_error(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test cancel sleep timer raises HomeAssistantError on AttributeError."""
        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=AttributeError("Method not available")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device"}

        with pytest.raises(HomeAssistantError, match="Sleep timer not supported"):
            await _handle_cancel_sleep_timer(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_cancel_sleep_timer_generic_exception(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test cancel sleep timer raises HomeAssistantError on unexpected Exception."""
        mock_coordinator.device.set_sleep_timer = AsyncMock(
            side_effect=RuntimeError("Unexpected failure")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device"}

        with pytest.raises(HomeAssistantError, match="Failed to cancel sleep timer"):
            await _handle_cancel_sleep_timer(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_cancel_sleep_timer_device_not_found(self, mock_get_coord, mock_hass):
        """Test cancel sleep timer raises ServiceValidationError when device not found."""
        mock_get_coord.return_value = None

        call = MagicMock()
        call.data = {"device_id": "nonexistent_device"}

        with pytest.raises(ServiceValidationError, match="not found or not available"):
            await _handle_cancel_sleep_timer(mock_hass, call)


# ===== Oscillation angles error handler tests =====


class TestOscillationAnglesErrorHandlers:
    """Test _handle_set_oscillation_angles exception paths."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_oscillation_angles_connection_error(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test oscillation angles raises HomeAssistantError on ConnectionError."""
        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ConnectionError("Network unreachable")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device", "lower_angle": 45, "upper_angle": 135}

        with pytest.raises(HomeAssistantError, match="Device communication failed"):
            await _handle_set_oscillation_angles(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_oscillation_angles_timeout_error(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test oscillation angles raises HomeAssistantError on TimeoutError."""
        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=TimeoutError("Request timed out")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device", "lower_angle": 45, "upper_angle": 135}

        with pytest.raises(HomeAssistantError, match="Device communication failed"):
            await _handle_set_oscillation_angles(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_oscillation_angles_value_error(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test oscillation angles raises HomeAssistantError on ValueError."""
        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=ValueError("Invalid angle")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device", "lower_angle": 45, "upper_angle": 135}

        with pytest.raises(HomeAssistantError, match="Invalid angle values"):
            await _handle_set_oscillation_angles(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_oscillation_angles_attribute_error(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test oscillation angles raises HomeAssistantError on AttributeError."""
        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=AttributeError("Method not available")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device", "lower_angle": 45, "upper_angle": 135}

        with pytest.raises(HomeAssistantError, match="not supported"):
            await _handle_set_oscillation_angles(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_oscillation_angles_generic_exception(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test oscillation angles raises HomeAssistantError on unexpected Exception."""
        mock_coordinator.device.set_oscillation_angles = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device", "lower_angle": 45, "upper_angle": 135}

        with pytest.raises(HomeAssistantError, match="Failed to set oscillation"):
            await _handle_set_oscillation_angles(mock_hass, call)

    @pytest.mark.asyncio
    async def test_oscillation_angles_lower_exceeds_upper(self, mock_hass):
        """Test oscillation angles raises ServiceValidationError when lower > upper."""
        call = MagicMock()
        call.data = {"device_id": "test_device", "lower_angle": 180, "upper_angle": 45}

        with pytest.raises(ServiceValidationError, match="Lower angle must not exceed"):
            await _handle_set_oscillation_angles(mock_hass, call)


# ===== _handle_get_cloud_devices tests =====


class TestGetCloudDevicesAccountEmail:
    """Test _handle_get_cloud_devices with account_email filtering."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._find_cloud_coordinators")
    @patch(
        "custom_components.hass_dyson.services._get_cloud_device_data_from_coordinator"
    )
    async def test_account_email_found(
        self, mock_get_data, mock_find_coords, mock_hass
    ):
        """Test account_email selects the correct coordinator."""
        mock_find_coords.return_value = [
            {"email": "first@example.com", "coordinator": MagicMock()},
            {"email": "second@example.com", "coordinator": MagicMock()},
        ]
        mock_get_data.return_value = {
            "devices": [],
            "summary": {"total_devices": 0},
        }

        call = MagicMock()
        call.data = {"account_email": "second@example.com", "sanitize": True}

        result = await _handle_get_cloud_devices(mock_hass, call)

        assert result["account_email"] == "second@example.com"
        # Verify the second coordinator was selected
        selected = mock_get_data.call_args[0][0]
        assert selected["email"] == "second@example.com"

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._find_cloud_coordinators")
    async def test_account_email_not_found_raises(self, mock_find_coords, mock_hass):
        """Test account_email not found raises ServiceValidationError."""
        mock_find_coords.return_value = [
            {"email": "only@example.com", "coordinator": MagicMock()},
        ]

        call = MagicMock()
        call.data = {"account_email": "nothere@example.com", "sanitize": False}

        with pytest.raises(ServiceValidationError, match="not found"):
            await _handle_get_cloud_devices(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._find_cloud_coordinators")
    @patch(
        "custom_components.hass_dyson.services._get_cloud_device_data_from_coordinator"
    )
    async def test_sanitize_true_excludes_summary(
        self, mock_get_data, mock_find_coords, mock_hass
    ):
        """Test sanitize=True excludes the summary from response."""
        mock_find_coords.return_value = [
            {"email": "user@example.com", "coordinator": MagicMock()},
        ]
        mock_get_data.return_value = {
            "devices": [],
            "summary": {"total_devices": 0, "source": "live_api"},
        }

        call = MagicMock()
        call.data = {"sanitize": True}

        result = await _handle_get_cloud_devices(mock_hass, call)

        assert "summary" not in result
        assert result["sanitized"] is True

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._find_cloud_coordinators")
    @patch(
        "custom_components.hass_dyson.services._get_cloud_device_data_from_coordinator"
    )
    async def test_sanitize_false_includes_summary(
        self, mock_get_data, mock_find_coords, mock_hass
    ):
        """Test sanitize=False includes the summary in response."""
        mock_find_coords.return_value = [
            {"email": "user@example.com", "coordinator": MagicMock()},
        ]
        mock_get_data.return_value = {
            "devices": [],
            "summary": {"total_devices": 0, "source": "live_api"},
        }

        call = MagicMock()
        call.data = {"sanitize": False}

        result = await _handle_get_cloud_devices(mock_hass, call)

        assert "summary" in result
        assert result["sanitized"] is False

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._find_cloud_coordinators")
    @patch(
        "custom_components.hass_dyson.services._get_cloud_device_data_from_coordinator"
    )
    async def test_dyson_auth_error_raises_ha_error(
        self, mock_get_data, mock_find_coords, mock_hass
    ):
        """Test DysonAuthError from coordinator raises HomeAssistantError."""
        mock_find_coords.return_value = [
            {"email": "user@example.com", "coordinator": MagicMock()},
        ]
        mock_get_data.side_effect = DysonAuthError("Auth failed")

        call = MagicMock()
        call.data = {"sanitize": False}

        with pytest.raises(HomeAssistantError, match="Dyson service error"):
            await _handle_get_cloud_devices(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._find_cloud_coordinators")
    @patch(
        "custom_components.hass_dyson.services._get_cloud_device_data_from_coordinator"
    )
    async def test_dyson_connection_error_raises_ha_error(
        self, mock_get_data, mock_find_coords, mock_hass
    ):
        """Test DysonConnectionError from coordinator raises HomeAssistantError."""
        mock_find_coords.return_value = [
            {"email": "user@example.com", "coordinator": MagicMock()},
        ]
        mock_get_data.side_effect = DysonConnectionError("Connection failed")

        call = MagicMock()
        call.data = {"sanitize": False}

        with pytest.raises(HomeAssistantError, match="Dyson service error"):
            await _handle_get_cloud_devices(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._find_cloud_coordinators")
    @patch(
        "custom_components.hass_dyson.services._get_cloud_device_data_from_coordinator"
    )
    async def test_dyson_api_error_raises_ha_error(
        self, mock_get_data, mock_find_coords, mock_hass
    ):
        """Test DysonAPIError from coordinator raises HomeAssistantError."""
        mock_find_coords.return_value = [
            {"email": "user@example.com", "coordinator": MagicMock()},
        ]
        mock_get_data.side_effect = DysonAPIError("API failed")

        call = MagicMock()
        call.data = {"sanitize": False}

        with pytest.raises(HomeAssistantError, match="Dyson service error"):
            await _handle_get_cloud_devices(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._find_cloud_coordinators")
    @patch(
        "custom_components.hass_dyson.services._get_cloud_device_data_from_coordinator"
    )
    async def test_unexpected_error_raises_ha_error(
        self, mock_get_data, mock_find_coords, mock_hass
    ):
        """Test unexpected Exception from coordinator raises HomeAssistantError."""
        mock_find_coords.return_value = [
            {"email": "user@example.com", "coordinator": MagicMock()},
        ]
        mock_get_data.side_effect = RuntimeError("Unexpected failure")

        call = MagicMock()
        call.data = {"sanitize": False}

        with pytest.raises(HomeAssistantError, match="Unexpected error"):
            await _handle_get_cloud_devices(mock_hass, call)


# ===== _find_cloud_coordinators tests =====


class TestFindCloudCoordinators:
    """Test _find_cloud_coordinators with various coordinator types."""

    def test_find_data_update_coordinator_with_discovery_cloud(self, mock_hass):
        """Test finding DysonDataUpdateCoordinator with DISCOVERY_CLOUD method."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

        mock_coord = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coord.config_entry = MagicMock()
        mock_coord.config_entry.data = {
            CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD,
            "email": "user@example.com",
        }
        mock_coord.config_entry.entry_id = "test_entry"
        mock_coord.device = MagicMock()  # Has device

        mock_hass.data = {DOMAIN: {"test_key": mock_coord}}
        mock_hass.config_entries.async_entries.return_value = []

        result = _find_cloud_coordinators(mock_hass)

        # Should find the DysonDataUpdateCoordinator with cloud discovery
        emails = [c["email"] for c in result]
        assert "user@example.com" in emails

    def test_find_config_entry_fallback(self, mock_hass):
        """Test fallback to config entries when no active coordinators found."""
        # No data in hass.data
        mock_hass.data = {DOMAIN: {}}

        # But there's a config entry with devices
        mock_entry = MagicMock()
        mock_entry.data = {
            "devices": [{"serial_number": "VS6-EU-HJA1234A"}],
            "email": "fallback@example.com",
            "auth_token": "token123",
        }
        mock_hass.config_entries.async_entries.return_value = [mock_entry]

        result = _find_cloud_coordinators(mock_hass)

        emails = [c["email"] for c in result]
        assert "fallback@example.com" in emails
        assert result[0]["type"] == "config_entry"
        assert result[0]["coordinator"] is None  # No active coordinator

    def test_config_entry_fallback_skips_no_email(self, mock_hass):
        """Test config entry fallback skips entries without email."""
        mock_hass.data = {DOMAIN: {}}

        mock_entry = MagicMock()
        mock_entry.data = {
            "devices": [{"serial_number": "VS6-EU-HJA1234A"}],
            # No "email" key
            "auth_token": "token123",
        }
        mock_hass.config_entries.async_entries.return_value = [mock_entry]

        result = _find_cloud_coordinators(mock_hass)

        assert result == []

    def test_config_entry_fallback_skips_no_auth_token(self, mock_hass):
        """Test config entry fallback skips entries without auth_token."""
        mock_hass.data = {DOMAIN: {}}

        mock_entry = MagicMock()
        mock_entry.data = {
            "devices": [{"serial_number": "VS6-EU-HJA1234A"}],
            "email": "user@example.com",
            # No "auth_token" key
        }
        mock_hass.config_entries.async_entries.return_value = [mock_entry]

        result = _find_cloud_coordinators(mock_hass)

        assert result == []

    def test_data_update_coordinator_no_device_skipped(self, mock_hass):
        """Test DysonDataUpdateCoordinator without device is skipped."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

        mock_coord = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coord.config_entry = MagicMock()
        mock_coord.config_entry.data = {
            CONF_DISCOVERY_METHOD: DISCOVERY_CLOUD,
            "email": "user@example.com",
        }
        mock_coord.device = None  # No device

        mock_hass.data = {DOMAIN: {"test_key": mock_coord}}
        mock_hass.config_entries.async_entries.return_value = []

        result = _find_cloud_coordinators(mock_hass)

        # Should not find coordinator without device
        emails = [c["email"] for c in result]
        assert "user@example.com" not in emails


# ===== async_handle_refresh_account_data tests =====


class TestRefreshAccountData:
    """Test async_handle_refresh_account_data with specific device and all devices."""

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_refresh_specific_device_success(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test refreshing a specific device by device_id."""
        mock_coordinator.async_refresh = AsyncMock()
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device"}

        await async_handle_refresh_account_data(mock_hass, call)

        mock_coordinator.async_refresh.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_refresh_specific_device_not_found(self, mock_get_coord, mock_hass):
        """Test refreshing specific device that doesn't exist raises error."""
        mock_get_coord.return_value = None

        call = MagicMock()
        call.data = {"device_id": "nonexistent_device"}

        with pytest.raises(ServiceValidationError, match="not found"):
            await async_handle_refresh_account_data(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_refresh_specific_device_connection_error(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test refreshing specific device with ConnectionError raises HomeAssistantError."""
        mock_coordinator.async_refresh = AsyncMock(
            side_effect=ConnectionError("Connection failed")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device"}

        with pytest.raises(HomeAssistantError, match="Device communication failed"):
            await async_handle_refresh_account_data(mock_hass, call)

    @pytest.mark.asyncio
    @patch("custom_components.hass_dyson.services._get_coordinator_from_device_id")
    async def test_refresh_specific_device_generic_error(
        self, mock_get_coord, mock_hass, mock_coordinator
    ):
        """Test refreshing specific device with generic Exception raises HomeAssistantError."""
        mock_coordinator.async_refresh = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )
        mock_get_coord.return_value = mock_coordinator

        call = MagicMock()
        call.data = {"device_id": "test_device"}

        with pytest.raises(HomeAssistantError, match="Failed to refresh"):
            await async_handle_refresh_account_data(mock_hass, call)

    @pytest.mark.asyncio
    async def test_refresh_all_devices_success(self, mock_hass, mock_coordinator):
        """Test refreshing all devices when no device_id provided."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

        mock_coordinator_spec = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coordinator_spec.serial_number = "VS6-EU-HJA1234A"
        mock_coordinator_spec.async_refresh = AsyncMock()

        mock_hass.data = {DOMAIN: {"key1": mock_coordinator_spec}}

        call = MagicMock()
        call.data = {}  # No device_id

        await async_handle_refresh_account_data(mock_hass, call)

        mock_coordinator_spec.async_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_all_devices_connection_error_continues(self, mock_hass):
        """Test refreshing all devices continues past ConnectionError."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

        mock_coord1 = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coord1.serial_number = "DEVICE_1"
        mock_coord1.async_refresh = AsyncMock(
            side_effect=ConnectionError("Device 1 failed")
        )

        mock_coord2 = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coord2.serial_number = "DEVICE_2"
        mock_coord2.async_refresh = AsyncMock()

        mock_hass.data = {DOMAIN: {"k1": mock_coord1, "k2": mock_coord2}}

        call = MagicMock()
        call.data = {}

        # Should not raise - errors are logged and skipped
        await async_handle_refresh_account_data(mock_hass, call)

        mock_coord2.async_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_all_devices_generic_error_continues(self, mock_hass):
        """Test refreshing all devices continues past generic Exception."""
        from custom_components.hass_dyson.coordinator import DysonDataUpdateCoordinator

        mock_coord = MagicMock(spec=DysonDataUpdateCoordinator)
        mock_coord.serial_number = "DEVICE_1"
        mock_coord.async_refresh = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )

        mock_hass.data = {DOMAIN: {"k1": mock_coord}}

        call = MagicMock()
        call.data = {}

        # Should not raise
        await async_handle_refresh_account_data(mock_hass, call)
