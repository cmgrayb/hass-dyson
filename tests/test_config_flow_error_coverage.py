"""Additional config flow error coverage tests to close coverage gaps.

This module focuses on uncovered error paths in config_flow.py to improve
coverage from 53% toward the 75% target. Tests cover:
- Lines 88-94: AttributeError/TypeError in _get_default_country_culture
- Lines 164-169: socket.gaierror fallback in mDNS discovery
- Lines 181-183: TimeoutError in asyncio.wait_for
- Lines 318-322: DysonAuthError exception handling
- Lines 369-371: Exception in _create_cloud_account_form
- Lines 411, 416-418: Empty email validation and error paths
"""

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hass_dyson.config_flow import (
    DysonConfigFlow,
    _discover_device_via_mdns,
    _get_default_country_culture,
)
from custom_components.hass_dyson.const import CONF_COUNTRY, CONF_CULTURE


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    return MagicMock(spec=HomeAssistant)


@pytest.fixture
def config_flow(mock_hass):
    """Create a DysonConfigFlow instance."""
    flow = DysonConfigFlow()
    flow.hass = mock_hass
    flow._abort_if_unique_id_configured = MagicMock()
    flow.context = {}
    return flow


class TestGetDefaultCountryCultureErrorHandling:
    """Test error handling in _get_default_country_culture function."""

    def test_get_default_country_culture_attribute_error(self):
        """Test AttributeError handling in _get_default_country_culture."""
        # Create mock hass where accessing config raises AttributeError
        mock_hass = MagicMock()
        # Delete config attribute to trigger AttributeError in try block
        del mock_hass.config

        # The getattr(hass, "config", None) will return None,
        # but we want to trigger the exception handler
        # Make ha_country.upper() raise AttributeError
        mock_hass.config = MagicMock()
        mock_hass.config.country = MagicMock()
        mock_hass.config.country.upper = MagicMock(
            side_effect=AttributeError("upper failed")
        )

        # Should return default values when exception occurs
        country, culture = _get_default_country_culture(mock_hass)
        assert country == "US"
        assert culture == "en-US"

    def test_get_default_country_culture_type_error(self):
        """Test TypeError handling in _get_default_country_culture."""
        # Create mock hass where string operations raise TypeError
        mock_hass = MagicMock()
        mock_config = MagicMock()
        mock_config.country = MagicMock()
        mock_config.language = MagicMock()
        # Make string concatenation raise TypeError
        mock_config.language.__str__ = MagicMock(side_effect=TypeError("Invalid type"))
        mock_hass.config = mock_config

        # Should return default values
        country, culture = _get_default_country_culture(mock_hass)
        assert country == "US"
        assert culture == "en-US"

    def test_get_default_country_culture_language_with_country(self):
        """Test language already includes country code."""
        mock_hass = MagicMock()
        mock_config = MagicMock()
        mock_config.country = "GB"
        mock_config.language = "en-GB"  # Already has country code
        mock_hass.config = mock_config

        country, culture = _get_default_country_culture(mock_hass)
        assert country == "GB"
        assert culture == "en-GB"  # Should use as-is

    def test_get_default_country_culture_language_without_country(self):
        """Test language without country code."""
        mock_hass = MagicMock()
        mock_config = MagicMock()
        mock_config.country = "DE"
        mock_config.language = "de"  # No country code
        mock_hass.config = mock_config

        country, culture = _get_default_country_culture(mock_hass)
        assert country == "DE"
        assert culture == "de-DE"  # Should combine


class TestMdnsDiscoveryErrorPaths:
    """Test error paths in mDNS discovery function."""

    @pytest.mark.asyncio
    async def test_mdns_discovery_socket_gaierror_fallback(self, mock_hass):
        """Test socket.gaierror handling in gethostbyname fallback."""
        # Mock zeroconf to return None (no services found)
        with patch(
            "homeassistant.components.zeroconf.async_get_instance"
        ) as mock_zeroconf:
            mock_zc_instance = MagicMock()
            mock_zc_instance.get_service_info = MagicMock(return_value=None)
            mock_zeroconf.return_value = mock_zc_instance

            # Mock gethostbyname to raise socket.gaierror
            with patch(
                "socket.gethostbyname",
                side_effect=socket.gaierror("Name resolution failed"),
            ):
                result = await _discover_device_via_mdns(mock_hass, "TEST123456")
                # Should return None when both methods fail
                assert result is None

    @pytest.mark.asyncio
    async def test_mdns_discovery_general_exception_in_find(self, mock_hass):
        """Test general exception handling within _find_device."""
        with patch(
            "homeassistant.components.zeroconf.async_get_instance"
        ) as mock_zeroconf:
            mock_zc_instance = MagicMock()
            # Make get_service_info raise a general exception
            mock_zc_instance.get_service_info = MagicMock(
                side_effect=RuntimeError("Service info error")
            )
            mock_zeroconf.return_value = mock_zc_instance

            result = await _discover_device_via_mdns(mock_hass, "TEST123456")
            # Should catch exception and return None
            assert result is None

    @pytest.mark.asyncio
    async def test_mdns_discovery_timeout_in_wait_for(self, mock_hass):
        """Test TimeoutError handling in asyncio.wait_for."""
        with patch(
            "homeassistant.components.zeroconf.async_get_instance"
        ) as mock_zeroconf:
            mock_zeroconf.return_value = MagicMock()

            # Mock wait_for to raise TimeoutError
            with patch(
                "asyncio.wait_for", side_effect=TimeoutError("Discovery timeout")
            ):
                result = await _discover_device_via_mdns(
                    mock_hass, "TEST123456", timeout=5
                )
                # Should catch TimeoutError and return None
                assert result is None

    @pytest.mark.asyncio
    async def test_mdns_discovery_zeroconf_none(self, mock_hass):
        """Test when zeroconf instance is None."""
        with patch(
            "homeassistant.components.zeroconf.async_get_instance", return_value=None
        ):
            result = await _discover_device_via_mdns(mock_hass, "TEST123456")
            # Should return None when zeroconf unavailable
            assert result is None

    @pytest.mark.asyncio
    async def test_mdns_discovery_zeroconf_exception(self, mock_hass):
        """Test exception when getting zeroconf instance."""
        with patch(
            "homeassistant.components.zeroconf.async_get_instance",
            side_effect=Exception("Zeroconf error"),
        ):
            result = await _discover_device_via_mdns(mock_hass, "TEST123456")
            # Should catch exception and return None
            assert result is None


class TestInitiateOTPErrorPaths:
    """Test error paths in _initiate_otp_with_dyson_api."""

    @pytest.mark.asyncio
    async def test_initiate_otp_dyson_auth_error(self, config_flow):
        """Test DysonAuthError handling during provision."""
        from libdyson_rest.exceptions import DysonAuthError

        mock_client = AsyncMock()
        mock_client.provision = AsyncMock(
            side_effect=DysonAuthError("Invalid credentials")
        )
        config_flow.hass.async_add_executor_job = AsyncMock(return_value=mock_client)

        challenge_id, errors = await config_flow._initiate_otp_with_dyson_api(
            "test@example.com", "US", "en-US"
        )

        assert challenge_id is None
        assert errors["base"] == "auth_failed"
        # Verify cleanup was called
        assert config_flow._cloud_client is None

    @pytest.mark.asyncio
    async def test_initiate_otp_dyson_connection_error(self, config_flow):
        """Test DysonConnectionError handling during get_user_status."""
        from libdyson_rest.exceptions import DysonConnectionError

        mock_client = AsyncMock()
        mock_client.provision = AsyncMock()
        mock_client.get_user_status = AsyncMock(
            side_effect=DysonConnectionError("Network error")
        )
        config_flow.hass.async_add_executor_job = AsyncMock(return_value=mock_client)

        challenge_id, errors = await config_flow._initiate_otp_with_dyson_api(
            "test@example.com", "US", "en-US"
        )

        assert challenge_id is None
        assert errors["base"] == "connection_failed"
        assert config_flow._cloud_client is None

    @pytest.mark.asyncio
    async def test_initiate_otp_dyson_api_error(self, config_flow):
        """Test DysonAPIError handling during begin_login."""
        from libdyson_rest.exceptions import DysonAPIError

        mock_client = AsyncMock()
        mock_client.provision = AsyncMock()
        mock_client.get_user_status = AsyncMock(
            return_value=MagicMock(
                account_status=MagicMock(value="active"),
                authentication_method=MagicMock(value="otp"),
            )
        )
        mock_client.begin_login = AsyncMock(side_effect=DysonAPIError("API error"))
        config_flow.hass.async_add_executor_job = AsyncMock(return_value=mock_client)

        challenge_id, errors = await config_flow._initiate_otp_with_dyson_api(
            "test@example.com", "US", "en-US"
        )

        assert challenge_id is None
        assert errors["base"] == "cloud_api_error"
        assert config_flow._cloud_client is None

    @pytest.mark.asyncio
    async def test_initiate_otp_generic_exception(self, config_flow):
        """Test generic Exception handling in _initiate_otp_with_dyson_api."""
        mock_client = AsyncMock()
        mock_client.provision = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        config_flow.hass.async_add_executor_job = AsyncMock(return_value=mock_client)

        challenge_id, errors = await config_flow._initiate_otp_with_dyson_api(
            "test@example.com", "US", "en-US"
        )

        assert challenge_id is None
        assert errors["base"] == "auth_failed"
        assert config_flow._cloud_client is None

    @pytest.mark.asyncio
    async def test_initiate_otp_client_none(self, config_flow):
        """Test when client initialization returns None."""
        config_flow.hass.async_add_executor_job = AsyncMock(return_value=None)

        challenge_id, errors = await config_flow._initiate_otp_with_dyson_api(
            "test@example.com", "US", "en-US"
        )

        assert challenge_id is None
        assert errors["base"] == "auth_failed"


class TestCreateCloudAccountFormErrorPath:
    """Test error path in _create_cloud_account_form."""

    def test_create_cloud_account_form_exception(self, config_flow):
        """Test exception handling in _create_cloud_account_form."""
        # Mock _get_default_country_culture to raise an exception
        with patch(
            "custom_components.hass_dyson.config_flow._get_default_country_culture",
            side_effect=RuntimeError("Config error"),
        ):
            with pytest.raises(RuntimeError, match="Config error"):
                config_flow._create_cloud_account_form({})

    def test_create_cloud_account_form_async_show_form_exception(self, config_flow):
        """Test exception when async_show_form fails."""
        # Mock async_show_form to raise an exception
        config_flow.async_show_form = MagicMock(side_effect=ValueError("Form error"))

        with pytest.raises(ValueError, match="Form error"):
            config_flow._create_cloud_account_form({})


class TestCloudAccountStepErrorPaths:
    """Test error paths in async_step_cloud_account."""

    @pytest.mark.asyncio
    async def test_cloud_account_empty_email(self, config_flow):
        """Test empty email validation."""
        # Don't set _email to simulate empty email
        config_flow._email = None

        result = await config_flow.async_step_cloud_account(
            {"email": "", CONF_COUNTRY: "US", CONF_CULTURE: "en-US"}
        )

        assert result["type"] == FlowResultType.FORM
        assert "errors" in result
        assert result["errors"]["base"] == "auth_failed"

    @pytest.mark.asyncio
    async def test_cloud_account_missing_country_culture(self, config_flow):
        """Test fallback to default country/culture when not provided."""
        config_flow._email = "test@example.com"

        # Mock successful OTP initiation
        mock_client = AsyncMock()
        mock_client.provision = AsyncMock()
        mock_client.get_user_status = AsyncMock(
            return_value=MagicMock(
                account_status=MagicMock(value="active"),
                authentication_method=MagicMock(value="otp"),
            )
        )
        mock_challenge = MagicMock()
        mock_challenge.challenge_id = "test_challenge_123"
        mock_client.begin_login = AsyncMock(return_value=mock_challenge)
        config_flow.hass.async_add_executor_job = AsyncMock(return_value=mock_client)

        # Mock _get_default_country_culture
        with patch(
            "custom_components.hass_dyson.config_flow._get_default_country_culture",
            return_value=("GB", "en-GB"),
        ):
            # Don't provide country/culture in input
            result = await config_flow.async_step_cloud_account(
                {"email": "test@example.com"}
            )

            # Should use defaults and proceed to verify step
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "verify"

    @pytest.mark.asyncio
    async def test_cloud_account_top_level_exception(self, config_flow):
        """Test top-level exception handler in async_step_cloud_account."""
        config_flow._email = "test@example.com"

        # Mock to raise an exception at the top level
        with patch(
            "custom_components.hass_dyson.config_flow._get_default_country_culture",
            side_effect=RuntimeError("Top level error"),
        ):
            with pytest.raises(RuntimeError, match="Top level error"):
                await config_flow.async_step_cloud_account(
                    {"email": "test@example.com"}
                )


class TestCleanupCloudClient:
    """Test _cleanup_cloud_client error handling."""

    @pytest.mark.asyncio
    async def test_cleanup_cloud_client_exception(self, config_flow):
        """Test exception handling during cloud client cleanup."""
        mock_client = AsyncMock()
        mock_client.close = AsyncMock(side_effect=RuntimeError("Close error"))
        config_flow._cloud_client = mock_client

        # Should handle exception and set client to None
        await config_flow._cleanup_cloud_client()
        assert config_flow._cloud_client is None

    @pytest.mark.asyncio
    async def test_cleanup_cloud_client_none(self, config_flow):
        """Test cleanup when cloud client is None."""
        config_flow._cloud_client = None

        # Should handle gracefully
        await config_flow._cleanup_cloud_client()
        assert config_flow._cloud_client is None
