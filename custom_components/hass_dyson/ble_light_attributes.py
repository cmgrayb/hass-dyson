"""Confirmed optional settings on the existing authenticated BLE light link."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError

from .ble_light_protocol import (
    MODE_ATTRIBUTES,
    READABLE_ATTRIBUTES,
    LightAttribute,
    decode_birth_year,
    encode_birth_year,
    parse_attribute_message,
)
from .const import (
    BLE_APP_STATUS_FOREGROUND_ACTIVE,
    BLE_APP_STATUS_INACTIVE,
    BLE_CHAR_11006_UUID,
    BLE_CHAR_11007_UUID,
    BLE_MSG_TYPE_APP_ACTIVE_STATUS,
    BLE_MSG_TYPE_PUSH_ATTRIBUTE,
    BLE_MSG_TYPE_PUSH_ATTRIBUTE_ACK,
    BLE_MSG_TYPE_PUSH_ATTRIBUTE_REQUEST,
    BLE_MSG_TYPE_READ_ATTRIBUTE_REQUEST,
    BLE_MSG_TYPE_READ_ATTRIBUTE_RESPONSE,
    BLE_MSG_TYPE_WRITE_ATTRIBUTE_REQUEST,
    BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE,
    BLE_PUSH_STATUS_ACTIVE,
    BLE_WRITE_ATTR_CHAR_UUID,
)

if TYPE_CHECKING:
    from .ble_device import DysonBLEDevice

_REQUEST_TIMEOUT = 3.0
_READBACK_TIMEOUT = 2.0
_READBACK_INTERVAL = 0.15
_LOGGER = logging.getLogger(__name__)
_REFRESH_INTERVAL = 60.0
_SENSOR_CHARACTERISTICS = {
    "auto_brightness": BLE_CHAR_11006_UUID,
    "movement_sensor": BLE_CHAR_11007_UUID,
}


class BLELightAttributeError(HomeAssistantError):
    """A rejected setting, without including private response contents."""


class BLELightAttributes:
    """Reuse a light's client, fragment codec, lock and state-change callbacks.

    Authentication and reconnection remain owned by DysonBLEDevice. Optional
    settings cannot prevent basic light setup. Requests have no transaction ID;
    after a timeout, pause this channel until reconnect rather than accepting a
    delayed reply as confirmation of a later command.
    """

    def __init__(self, device: DysonBLEDevice) -> None:
        """Keep raw settings private to the device, not on HA's event bus."""
        from .ble_device import DysonFragmentAssembler

        self._device = device
        self.attributes: dict[int, bytes] = {}
        self._assembler = DysonFragmentAssembler()
        self._pending: dict[tuple[int, int], asyncio.Future[bytes]] = {}
        self._unsupported: set[int] = set()
        self._subscriptions: set[int] = set()
        self._push_supported = True
        self._ready = False
        self._timed_out = False
        self._generation = 0
        self._task: asyncio.Task[None] | None = None

    @property
    def available(self) -> bool:
        """Return whether this session can still confirm attribute operations."""
        return self._ready and not self._timed_out and self._device.is_connected

    @property
    def birth_year(self) -> int | None:
        """Decode sensitive state only on demand; never log or publish the key."""
        if not self.available:
            return None
        value = self.attributes.get(LightAttribute.YEAR_OF_BIRTH, b"")
        try:
            return decode_birth_year(value, bytes.fromhex(self._device._ltk_hex))
        except ValueError:
            return None

    def start(self) -> None:
        """Start optional discovery without blocking the light's setup."""
        self.reset()
        self._task = asyncio.create_task(self._run(), name="dyson-light-settings")

    def reset(self) -> None:
        """Discard session state and fail waiters on any disconnect."""
        self._generation += 1
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None
        for future in self._pending.values():
            if not future.done():
                future.set_exception(BLELightAttributeError("Lamp disconnected"))
        self._pending.clear()
        self._assembler.reset()
        self.attributes.clear()
        self._unsupported.clear()
        self._subscriptions.clear()
        self._push_supported = True
        self._ready = False
        self._timed_out = False
        self._device.state.auto_brightness = None
        self._device.state.movement_sensor = None

    async def close(self) -> None:
        """Cancel and await the owned worker before the GATT client is closed."""
        task = self._task
        client = self._device._client
        ready = self._ready
        self.reset()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        if ready and client is not None and getattr(client, "is_connected", False):
            try:
                async with asyncio.timeout(_REQUEST_TIMEOUT):
                    await self._send(
                        BLE_MSG_TYPE_APP_ACTIVE_STATUS,
                        bytes((BLE_APP_STATUS_INACTIVE,)),
                    )
            except Exception as err:
                _LOGGER.debug(
                    "Optional lamp channel cleanup failed (%s)", type(err).__name__
                )

    async def _send(self, opcode: int, body: bytes) -> None:
        from .ble_device import fragment_dyson_message

        client = self._device._client
        if client is None:
            raise BLELightAttributeError("Lamp disconnected")
        if opcode == BLE_MSG_TYPE_WRITE_ATTRIBUTE_REQUEST:
            await self._device._wait_for_light_write()
        for fragment in fragment_dyson_message(opcode, body):
            await client.write_gatt_char(
                BLE_WRITE_ATTR_CHAR_UUID,
                fragment,
                response=self._device._wants_write_request(
                    BLE_WRITE_ATTR_CHAR_UUID, default=False
                ),
            )
        if opcode == BLE_MSG_TYPE_WRITE_ATTRIBUTE_REQUEST:
            self._device._last_light_write = asyncio.get_running_loop().time()

    def _cache(self, attribute: int, value: bytes) -> None:
        self.attributes[attribute] = value
        if attribute == LightAttribute.DAYLIGHT_MODE and value in (b"\0", b"\1"):
            self._device.state.daylight_mode = value == b"\1"
            self._device._manual_mode_valid_until = 0.0
        self._device.state.lighting_revision += 1
        self._device._fire_state_change()

    def _on_message(self, _sender: Any, data: bytearray) -> None:
        try:
            message = self._assembler.feed(bytes(data))
            if message is None:
                return
            attribute, status, value = parse_attribute_message(
                message.type_id, message.payload
            )
        except ValueError:
            return
        future = self._pending.get((message.type_id, attribute))
        if status:
            if future is not None and not future.done():
                future.set_exception(BLELightAttributeError("Lamp rejected setting"))
            return
        if message.type_id in (
            BLE_MSG_TYPE_READ_ATTRIBUTE_RESPONSE,
            BLE_MSG_TYPE_PUSH_ATTRIBUTE,
        ):
            if attribute in READABLE_ATTRIBUTES:
                self._cache(attribute, value)
        if future is not None and not future.done():
            future.set_result(value)

    async def _request(
        self, opcode: int, reply: int, attribute: int, value: bytes = b""
    ) -> bytes:
        if not self._ready or self._timed_out or not self._device.is_connected:
            raise BLELightAttributeError("Lamp settings channel unavailable")
        key = (reply, attribute)
        generation = self._generation
        future: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()
        self._pending[key] = future
        body = int(attribute).to_bytes(2, "little")
        if opcode == BLE_MSG_TYPE_WRITE_ATTRIBUTE_REQUEST:
            body += len(value).to_bytes(2, "little") + value
        elif opcode == BLE_MSG_TYPE_PUSH_ATTRIBUTE_REQUEST:
            body += bytes((BLE_PUSH_STATUS_ACTIVE,))
        try:
            async with asyncio.timeout(_REQUEST_TIMEOUT):
                await self._send(opcode, body)
                return await future
        except TimeoutError:
            if (
                generation == self._generation
                and opcode != BLE_MSG_TYPE_PUSH_ATTRIBUTE_REQUEST
            ):
                self._timed_out = True
                self._device.state.lighting_revision += 1
                self._device._fire_state_change()
            raise BLELightAttributeError("Lamp settings request timed out") from None
        except asyncio.CancelledError:
            if (
                generation == self._generation
                and opcode != BLE_MSG_TYPE_PUSH_ATTRIBUTE_REQUEST
            ):
                self._timed_out = True
            raise
        finally:
            if self._pending.get(key) is future:
                self._pending.pop(key, None)
            if not future.done():
                future.cancel()

    async def _read(self, attribute: int) -> bytes:
        return await self._request(
            BLE_MSG_TYPE_READ_ATTRIBUTE_REQUEST,
            BLE_MSG_TYPE_READ_ATTRIBUTE_RESPONSE,
            attribute,
        )

    async def _write(self, attribute: int, value: bytes) -> None:
        await self._request(
            BLE_MSG_TYPE_WRITE_ATTRIBUTE_REQUEST,
            BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE,
            attribute,
            value,
        )
        deadline = asyncio.get_running_loop().time() + _READBACK_TIMEOUT
        while True:
            if await self._read(attribute) == value:
                return
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise BLELightAttributeError("Lamp setting readback mismatch")
            _LOGGER.debug("Waiting for lamp attribute %04x confirmation", attribute)
            # The Bluetooth MCU can acknowledge before the lamp MCU applies
            # the value. Retry reads only; repeating a write restarts modes.
            await asyncio.sleep(min(_READBACK_INTERVAL, remaining))

    async def _run(self) -> None:
        client = self._device._client
        if client is None:
            return
        try:
            async with self._device._lock:

                def handler(sender: Any, data: bytearray) -> None:
                    """Ignore notifications arriving from a previous GATT client."""
                    if client is self._device._client:
                        self._on_message(sender, data)

                try:
                    await client.start_notify(BLE_WRITE_ATTR_CHAR_UUID, handler)
                    self._ready = True
                    await self._send(
                        BLE_MSG_TYPE_APP_ACTIVE_STATUS,
                        bytes((BLE_APP_STATUS_FOREGROUND_ACTIVE,)),
                    )
                    await self._send(0x80, int(time.time()).to_bytes(4, "little"))
                except Exception:
                    self._ready = False
            while client is self._device._client and self._device.is_connected:
                await self.refresh()
                if self._timed_out:
                    return
                await asyncio.sleep(_REFRESH_INTERVAL)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Unsupported optional GATT services never take basic control offline.
            self._ready = False

    async def refresh(self) -> None:
        """Read each optional setting independently, releasing the control lock."""
        for sensor, uuid in _SENSOR_CHARACTERISTICS.items():
            try:
                async with self._device._lock:
                    client = self._device._client
                    if client is None:
                        return
                    async with asyncio.timeout(_REQUEST_TIMEOUT):
                        raw = bytes(await client.read_gatt_char(uuid))
                    if raw in (b"\0", b"\1"):
                        setattr(self._device.state, sensor, raw == b"\1")
                        self._device._fire_state_change()
            except Exception as err:
                _LOGGER.debug(
                    "Optional lamp sensor setting unavailable (%s)", type(err).__name__
                )
                continue
        for attribute in READABLE_ATTRIBUTES:
            if not self._ready or self._timed_out:
                return
            if attribute in self._unsupported:
                continue
            try:
                async with self._device._lock:
                    await self._read(attribute)
                    if self._push_supported and attribute not in self._subscriptions:
                        try:
                            await self._request(
                                BLE_MSG_TYPE_PUSH_ATTRIBUTE_REQUEST,
                                BLE_MSG_TYPE_PUSH_ATTRIBUTE_ACK,
                                attribute,
                            )
                            self._subscriptions.add(attribute)
                        except BLELightAttributeError:
                            self._push_supported = False
            except BLELightAttributeError:
                self._unsupported.add(attribute)
            if self._timed_out:
                return

    async def set_sensor(self, sensor: str, enabled: bool) -> None:
        """Set sensor enablement, not a lux or occupancy reading."""
        if sensor not in _SENSOR_CHARACTERISTICS or type(enabled) is not bool:
            raise ValueError("Invalid lamp sensor setting")
        async with self._device._lock:
            client = self._device._client
            if client is None or not self._device.is_connected:
                raise BLELightAttributeError("Lamp disconnected")
            target = bytes((enabled,))
            uuid = _SENSOR_CHARACTERISTICS[sensor]
            async with asyncio.timeout(_REQUEST_TIMEOUT):
                await self._device._write_light_characteristic(
                    uuid,
                    target,
                    response=self._device._wants_write_request(uuid, default=False),
                )
                await asyncio.sleep(0.25)
                deadline = asyncio.get_running_loop().time() + _READBACK_TIMEOUT
                while bytes(await client.read_gatt_char(uuid)) != target:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise BLELightAttributeError("Lamp sensor readback mismatch")
                    _LOGGER.debug("Waiting for lamp sensor %s confirmation", sensor)
                    await asyncio.sleep(min(_READBACK_INTERVAL, remaining))
            setattr(self._device.state, sensor, enabled)
            self._device._fire_state_change()

    async def set_attribute(self, attribute: int, value: bytes) -> None:
        """Write a confirmed setting without optimistically claiming success."""
        await self.set_attributes({attribute: value})

    async def set_attributes(self, values: Mapping[int, bytes]) -> None:
        """Apply a validated setting group in order; no implicit rollback."""
        async with self._device._lock:
            for attribute, value in values.items():
                await self._write(attribute, value)
            for attribute in MODE_ATTRIBUTES.values():
                if attribute not in self._unsupported:
                    try:
                        await self._read(attribute)
                    except BLELightAttributeError:
                        self._unsupported.add(attribute)
                    if self._timed_out:
                        break

    async def set_mode(self, mode: str) -> None:
        """Select the actual built-in mode, not a brightness approximation."""
        values: dict[int, bytes]
        if mode == "manual":
            values = dict.fromkeys(MODE_ATTRIBUTES.values(), b"\0")
        elif mode in MODE_ATTRIBUTES:
            values = {MODE_ATTRIBUTES[mode]: b"\1"}
        else:
            raise ValueError("Invalid lamp lighting mode")
        await self.set_attributes(values)

    async def set_birth_year(self, year: int) -> None:
        """Encrypt age-adjustment data using the distinct sensitive-state key."""
        await self.set_attributes(
            {
                LightAttribute.YEAR_OF_BIRTH: encode_birth_year(
                    year, bytes.fromhex(self._device._ltk_hex)
                ),
                LightAttribute.AGE_TIMESTAMP: int(time.time()).to_bytes(4, "little"),
            }
        )

    async def reset_daylight_times(self) -> None:
        """Restore the native unset sentinel for personal sunrise and sunset."""
        await self.set_attributes(
            {
                LightAttribute.SUNRISE_TIME: b"\xff\xff",
                LightAttribute.SUNSET_TIME: b"\xff\xff",
            }
        )
