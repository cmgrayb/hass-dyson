"""Read-only cloud location, timezone and DST data for Dyson BLE lights."""

from __future__ import annotations

import importlib
import math
from types import ModuleType
from typing import Any, Protocol, TypedDict
from urllib.parse import quote

from libdyson_rest.utils import get_api_hostname

REQUEST_TIMEOUT = 30.0


def _http_libraries() -> tuple[ModuleType, ...]:
    libraries = []
    for name in ("httpx2", "httpx"):
        try:
            libraries.append(importlib.import_module(name))
        except ImportError:
            continue
    if not libraries:
        raise ImportError("A Home Assistant HTTP client is required")
    return tuple(libraries)


_HTTP_LIBRARIES = _http_libraries()
httpx = _HTTP_LIBRARIES[0]
_HTTP_ERRORS = tuple(library.HTTPError for library in _HTTP_LIBRARIES)
_TIMEOUT_ERRORS = tuple(library.TimeoutException for library in _HTTP_LIBRARIES)


class _Response(Protocol):
    status_code: int

    @property
    def is_success(self) -> bool: ...

    def json(self) -> Any: ...


class _AsyncClient(Protocol):
    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout: float,
        follow_redirects: bool,
    ) -> _Response: ...


# DysonLighting's DaylightSaving model, in its serialized UInt8 field order.
DST_FIELDS = (
    "StartMonth",
    "StartRule",
    "StartDate",
    "StartDayOfWeek",
    "StartTime",
    "Adjustment",
    "EndMonth",
    "EndRule",
    "EndDate",
    "EndDayOfWeek",
    "EndTime",
)


class _LocationTimezone(TypedDict, total=False):
    timezone: str


class DysonBLELightLocation(_LocationTimezone):
    """Normalized location; timezone is only added by the caller, if available."""

    name: str | None
    key: str | None
    latitude: float
    longitude: float


class DysonBLELightCloudError(RuntimeError):
    """A cloud failure safe to log without a response body, URL or credentials."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        """Keep only a safe public label and optional HTTP status."""
        super().__init__(message)
        self.status_code = status_code


def _identifier(value: object, label: str) -> str:
    """Validate request identifiers without echoing their contents in errors."""
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError(f"Invalid {label}")
    return value


def _segment(value: str) -> str:
    value = _identifier(value, "URL segment")
    if value in (".", ".."):
        raise ValueError("Invalid URL segment")
    return quote(value, safe="")


def _invalid(label: str) -> DysonBLELightCloudError:
    return DysonBLELightCloudError(f"Invalid Dyson LEC {label} response")


def _optional_text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is not None and not isinstance(value, str):
        raise _invalid("location")
    return value


def _coordinate(value: object, limit: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise _invalid("location coordinates")
    try:
        coordinate = float(value)
    except (ValueError, OverflowError):
        raise _invalid("location coordinates") from None
    if not math.isfinite(coordinate) or not -limit <= coordinate <= limit:
        raise _invalid("location coordinates")
    return coordinate


class DysonBLELightCloudClient:
    """Fetch saved lamp data using the existing LEC Bearer authentication pattern.

    A caller may supply its managed HTTP client; otherwise each call owns a
    short-lived client. Only GET is supported;
    redirects are not followed. Errors expose only a static label and, for HTTP
    failures, status_code. The coordinator owns refresh policy and persistence.
    """

    def __init__(
        self, auth_token: str, country: str, *, client: _AsyncClient | None = None
    ) -> None:
        """Use regional routing and per-request authentication, not global headers."""
        token = _identifier(auth_token, "authentication token")
        region = _identifier(country, "country").upper()
        self._base_url = get_api_hostname(region).rstrip("/")
        self._client = client
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "HomeAssistantDyson/lec",
        }

    async def _get(self, path: str, *, binary: bool = False) -> _Response:
        headers = self._headers.copy()
        if binary:
            headers["Accept"] = "application/octet-stream"
        try:
            if self._client is not None:
                response = await self._client.get(
                    f"{self._base_url}{path}",
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                    follow_redirects=False,
                )
            else:
                async with httpx.AsyncClient(
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                    follow_redirects=False,
                ) as client:
                    response = await client.get(f"{self._base_url}{path}")
        except _TIMEOUT_ERRORS:
            raise DysonBLELightCloudError("Dyson LEC cloud request timed out") from None
        except _HTTP_ERRORS:
            raise DysonBLELightCloudError("Dyson LEC cloud request failed") from None
        if not response.is_success:
            raise DysonBLELightCloudError(
                f"Dyson LEC cloud request failed (HTTP {response.status_code})",
                status_code=response.status_code,
            )
        return response

    async def _get_object(self, path: str) -> dict[str, Any]:
        response = await self._get(path)
        try:
            payload = response.json()
        except ValueError:
            raise _invalid("JSON") from None
        if not isinstance(payload, dict):
            raise _invalid("JSON object")
        return payload

    async def fetch_location(self, serial: str) -> DysonBLELightLocation:
        """Return name/key (nullable) and required, finite, in-range floats.

        The exact lighting response has no timezone identifier. No guessed
        TimeZone alias is consumed and no implicit second request is made.
        """
        payload = await self._get_object(
            f"/v1/environment/devices/{_segment(serial)}/location"
        )
        return {
            "name": _optional_text(payload, "Name"),
            "key": _optional_text(payload, "Key"),
            "latitude": _coordinate(payload.get("Latitude"), 90.0),
            "longitude": _coordinate(payload.get("Longitude"), 180.0),
        }

    async def fetch_ltk(self, serial: str) -> str:
        """Fetch this account's lamp key; never return an unvalidated payload."""
        payload = await self._get_object(f"/v1/lec/{_segment(serial)}/ltk")
        value = payload.get("ltk")
        if not isinstance(value, str):
            raise _invalid("Bluetooth key")
        try:
            raw = bytes.fromhex(value)
        except ValueError:
            raise _invalid("Bluetooth key") from None
        if len(raw) != 16:
            raise _invalid("Bluetooth key")
        return raw.hex().upper()

    async def fetch_timezone(self, serial: str) -> str:
        """Read the identifier from the established {"timezone": string} model.

        No local timezone database or offset conversion is applied here.
        """
        payload = await self._get_object(f"/v1/machine/{_segment(serial)}/timezone")
        try:
            return _identifier(payload.get("timezone"), "timezone")
        except ValueError:
            raise _invalid("timezone") from None

    async def fetch_dst(self, timezone: str) -> bytes:
        """Return all eleven UInt8 fields in DST_FIELDS order, without guessing rules.

        Zero and 255 are valid wire values. Calendar/rule semantics narrower than
        UInt8 have not been established and are deliberately not imposed.
        """
        timezone = _identifier(timezone, "timezone")
        payload = await self._get_object(
            f"/v1/environment/location/dst?timezone={quote(timezone, safe='')}"
        )
        values = [payload.get(field) for field in DST_FIELDS]
        if any(type(value) is not int or not 0 <= value <= 255 for value in values):
            raise _invalid("DST")
        return bytes(values)
