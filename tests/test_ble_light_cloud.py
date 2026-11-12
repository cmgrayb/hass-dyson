"""Offline schema and HTTP-contract tests for the standalone LEC cloud reader."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx2 as httpx
import pytest

# Avoid importing the integration's HA/BLE entry point for these focused tests.
_SPEC = importlib.util.spec_from_file_location(
    "ble_light_cloud_under_test",
    Path(__file__).parents[1] / "custom_components/hass_dyson/ble_light_cloud.py",
)
assert _SPEC is not None and _SPEC.loader is not None
cloud = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cloud)

TOKEN = "offline-test-token"
SERIAL = "TEST-SERIAL"
BASE = "https://cloud.example.invalid"

# Independent order/value fixture, not generated from the implementation constant.
DST = {
    "StartMonth": 3,
    "StartRule": 2,
    "StartDate": 25,
    "StartDayOfWeek": 1,
    "StartTime": 2,
    "Adjustment": 60,
    "EndMonth": 10,
    "EndRule": 4,
    "EndDate": 31,
    "EndDayOfWeek": 7,
    "EndTime": 3,
}
DST_BYTES = bytes([3, 2, 25, 1, 2, 60, 10, 4, 31, 7, 3])


@pytest.fixture
def mocked_cloud(monkeypatch):
    """Use real httpx serialization and responses, but never a network transport."""
    requests = []
    clients = []
    handler = lambda request: httpx.Response(200, json={})
    async_client = httpx.AsyncClient

    def client_factory(**kwargs):
        assert kwargs["timeout"] == 30.0
        assert kwargs["follow_redirects"] is False

        def dispatch(request):
            assert request.method == "GET"
            assert request.headers["Authorization"] == f"Bearer {TOKEN}"
            assert request.headers["User-Agent"] == "HomeAssistantDyson/lec"
            assert request.content == b""
            requests.append(request)
            return handler(request)

        client = async_client(transport=httpx.MockTransport(dispatch), **kwargs)
        clients.append(client)
        return client

    def set_response(*, payload=None, body=None, status=200, headers=None, error=None):
        nonlocal handler

        def respond(request):
            if error is not None:
                raise error
            if body is not None:
                return httpx.Response(status, content=body, headers=headers)
            return httpx.Response(status, json=payload, headers=headers)

        handler = respond

    monkeypatch.setattr(cloud.httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(cloud, "get_api_hostname", lambda country: BASE + "/")
    yield cloud.DysonBLELightCloudClient(TOKEN, "DE"), set_response, requests
    assert all(client.is_closed for client in clients)


def location(**changes):
    return {
        "Name": "Test city",
        "Key": "test-key",
        "Latitude": 52.5,
        "Longitude": 13.4,
        **changes,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("latitude,longitude", [(52, "13.4"), (-90, -180), (90, 180)])
async def test_location_normalization(mocked_cloud, latitude, longitude):
    client, respond, requests = mocked_cloud
    respond(payload=location(Latitude=latitude, Longitude=longitude, Accuracy=10))
    result = await client.fetch_location(SERIAL)
    assert result == {
        "name": "Test city",
        "key": "test-key",
        "latitude": float(latitude),
        "longitude": float(longitude),
    }
    assert type(result["latitude"]) is float
    assert type(result["longitude"]) is float
    assert str(requests[0].url) == BASE + "/v1/environment/devices/TEST-SERIAL/location"
    assert requests[0].headers["Accept"] == "application/json"


@pytest.mark.asyncio
async def test_location_nullable_metadata_and_no_guessed_timezone(mocked_cloud):
    client, respond, requests = mocked_cloud
    respond(payload={"Latitude": 0, "Longitude": 0, "TimeZone": "Europe/Berlin"})
    assert await client.fetch_location(SERIAL) == {
        "name": None,
        "key": None,
        "latitude": 0.0,
        "longitude": 0.0,
    }
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["Latitude", "Longitude"])
@pytest.mark.parametrize(
    "value", [None, True, [], {}, "invalid", "NaN", "inf", "-inf", 10**400]
)
async def test_location_rejects_invalid_coordinates(mocked_cloud, field, value):
    client, respond, _ = mocked_cloud
    respond(payload=location(**{field: value}))
    with pytest.raises(cloud.DysonBLELightCloudError, match="coordinates"):
        await client.fetch_location(SERIAL)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("Latitude", -90.01),
        ("Latitude", 90.01),
        ("Longitude", -180.01),
        ("Longitude", 180.01),
    ],
)
async def test_location_rejects_out_of_range_coordinates(mocked_cloud, field, value):
    client, respond, _ = mocked_cloud
    respond(payload=location(**{field: value}))
    with pytest.raises(cloud.DysonBLELightCloudError, match="coordinates"):
        await client.fetch_location(SERIAL)


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["Name", "Key", "Latitude", "Longitude"])
async def test_location_missing_fields(mocked_cloud, field):
    client, respond, _ = mocked_cloud
    payload = location()
    del payload[field]
    respond(payload=payload)
    if field in ("Name", "Key"):
        assert (await client.fetch_location(SERIAL))[field.lower()] is None
    else:
        with pytest.raises(cloud.DysonBLELightCloudError):
            await client.fetch_location(SERIAL)


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["Name", "Key"])
@pytest.mark.parametrize("value", [False, 10, [], {}])
async def test_location_metadata_types(mocked_cloud, field, value):
    client, respond, _ = mocked_cloud
    respond(payload=location(**{field: value}))
    with pytest.raises(cloud.DysonBLELightCloudError):
        await client.fetch_location(SERIAL)


@pytest.mark.asyncio
@pytest.mark.parametrize("identifier", ["Europe/Berlin", "UTC", "Asia/Kathmandu"])
async def test_timezone_exact_model(mocked_cloud, identifier):
    client, respond, requests = mocked_cloud
    respond(payload={"timezone": identifier, "ignored": "not returned"})
    assert await client.fetch_timezone(SERIAL) == identifier
    assert str(requests[0].url) == BASE + "/v1/machine/TEST-SERIAL/timezone"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"TimeZone": "UTC"},
        {"timezone": None},
        {"timezone": ""},
        {"timezone": " "},
        {"timezone": False},
        {"timezone": 2},
        {"timezone": {"identifier": "UTC"}},
        {"timezone": ["UTC"]},
        {"timezone": "UTC\n"},
    ],
)
async def test_timezone_rejects_guessed_or_invalid_shapes(mocked_cloud, payload):
    client, respond, _ = mocked_cloud
    respond(payload=payload)
    with pytest.raises(cloud.DysonBLELightCloudError, match="timezone"):
        await client.fetch_timezone(SERIAL)


@pytest.mark.asyncio
async def test_dst_exact_order_and_url_encoding(mocked_cloud):
    client, respond, requests = mocked_cloud
    respond(payload=dict(reversed(list(DST.items()))))
    assert tuple(cloud.DST_FIELDS) == tuple(DST)
    assert await client.fetch_dst("Europe/Berlin&x=1") == DST_BYTES
    assert requests[0].url.query == b"timezone=Europe%2FBerlin%26x%3D1"


@pytest.mark.asyncio
@pytest.mark.parametrize("field", list(DST))
@pytest.mark.parametrize("value", [-1, 256, True, 1.0, "1", None, [], {}])
async def test_dst_rejects_every_invalid_field(mocked_cloud, field, value):
    client, respond, _ = mocked_cloud
    respond(payload={**DST, field: value})
    with pytest.raises(cloud.DysonBLELightCloudError, match="DST"):
        await client.fetch_dst("UTC")


@pytest.mark.asyncio
@pytest.mark.parametrize("field", list(DST))
async def test_dst_requires_all_fields(mocked_cloud, field):
    client, respond, _ = mocked_cloud
    respond(payload={key: value for key, value in DST.items() if key != field})
    with pytest.raises(cloud.DysonBLELightCloudError, match="DST"):
        await client.fetch_dst("UTC")


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [0, 255])
async def test_dst_uint8_boundaries_not_guessed_calendar_rules(mocked_cloud, value):
    client, respond, _ = mocked_cloud
    respond(payload=dict.fromkeys(DST, value))
    assert await client.fetch_dst("UTC") == bytes([value] * 11)


@pytest.mark.asyncio
async def test_account_key_is_validated_and_normalized(mocked_cloud):
    """Only a complete synthetic 16-byte key is returned to configuration."""
    client, respond, requests = mocked_cloud
    respond(payload={"ltk": bytes(range(16)).hex()})
    assert await client.fetch_ltk(SERIAL) == bytes(range(16)).hex().upper()
    assert str(requests[0].url) == BASE + "/v1/lec/TEST-SERIAL/ltk"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value", [None, True, [], {}, "invalid", "00", "00" * 15, "00" * 17]
)
async def test_invalid_key_is_never_stored(mocked_cloud, value):
    """Do not mistake an arbitrary cloud string for a Bluetooth key."""
    client, respond, _ = mocked_cloud
    respond(payload={"ltk": value})
    with pytest.raises(cloud.DysonBLELightCloudError, match="Bluetooth key"):
        await client.fetch_ltk(SERIAL)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [301, 302, 401, 403, 404, 429, 500])
async def test_http_failures_sanitized_and_redirects_not_followed(mocked_cloud, status):
    """Never expose a token, body or redirect location from a failed response."""
    client, respond, requests = mocked_cloud
    respond(
        body=b"synthetic-private-payload",
        status=status,
        headers={"Location": "https://elsewhere.example.invalid"},
    )
    with pytest.raises(cloud.DysonBLELightCloudError) as exc:
        await client.fetch_ltk(SERIAL)
    assert exc.value.status_code == status
    assert "synthetic-private-payload" not in str(exc.value)
    assert TOKEN not in str(exc.value)
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, httpx.ConnectError])
async def test_transport_errors_do_not_chain_private_contents(mocked_cloud, error_type):
    """HTTP-library messages can include headers/URLs; do not forward them."""
    client, respond, _ = mocked_cloud
    respond(error=error_type("synthetic-private-payload"))
    with pytest.raises(cloud.DysonBLELightCloudError) as exc:
        await client.fetch_ltk(SERIAL)
    assert "synthetic-private-payload" not in str(exc.value)
    assert exc.value.__suppress_context__


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [b"invalid-json", b"[]", b"null"])
async def test_invalid_json_has_only_static_error_labels(mocked_cloud, body):
    """Malformed responses are errors, not loosely interpreted device state."""
    client, respond, _ = mocked_cloud
    respond(body=body)
    with pytest.raises(cloud.DysonBLELightCloudError, match="Invalid Dyson"):
        await client.fetch_ltk(SERIAL)


@pytest.mark.asyncio
async def test_cancellation_propagates(mocked_cloud):
    """Configuration unload must not be swallowed as an ordinary cloud error."""
    import asyncio

    client, respond, _ = mocked_cloud
    respond(error=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await client.fetch_ltk(SERIAL)


@pytest.mark.asyncio
@pytest.mark.parametrize("library_name", ["httpx", "httpx2"])
@pytest.mark.parametrize(
    "failure", [None, "timeout", "connect", "redirect", "forbidden"]
)
async def test_managed_clients_from_both_ha_generations(
    monkeypatch, library_name, failure
):
    """Stable HA's httpx and newer HA's httpx2 share a safe request contract."""
    import importlib

    library = pytest.importorskip(library_name)
    library = importlib.import_module(library_name)
    requests = []

    def respond(request):
        requests.append(request)
        if failure == "timeout":
            raise library.ReadTimeout("synthetic-private-payload")
        if failure == "connect":
            raise library.ConnectError("synthetic-private-payload")
        status = (
            302 if failure == "redirect" else 403 if failure == "forbidden" else 200
        )
        return library.Response(status, json={"ltk": bytes(range(16)).hex()})

    monkeypatch.setattr(cloud, "get_api_hostname", lambda country: BASE)
    async with library.AsyncClient(transport=library.MockTransport(respond)) as managed:
        client = cloud.DysonBLELightCloudClient(TOKEN, "DE", client=managed)
        if failure is None:
            assert await client.fetch_ltk(SERIAL) == bytes(range(16)).hex().upper()
        else:
            with pytest.raises(cloud.DysonBLELightCloudError) as exc:
                await client.fetch_ltk(SERIAL)
            assert "synthetic-private-payload" not in str(exc.value)
            assert (
                exc.value.__suppress_context__
                if failure in ("timeout", "connect")
                else True
            )
        assert not managed.is_closed
        assert "authorization" not in managed.headers
        assert requests[0].headers["Authorization"] == f"Bearer {TOKEN}"
