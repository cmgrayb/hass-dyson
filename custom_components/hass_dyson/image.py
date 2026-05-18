"""Image platform for Dyson integration.

Currently provides:
 - DysonDustMapImage:   the dust-density heatmap for the most recent clean
                        (rendered as PNG with purple→white gradient over the
                        floor plan), refreshed when a new cleanId appears.
 - DysonFloorPlanImage: the persistent-map presentation image (the static
                        floor plan with zone boundaries and dock location).

Source: /v1/{serial}/clean-maps?dustMap=total  +  /v1/app/{serial}/persistent-maps/{mapId}
Bitmap format ported from thoukydides/matterbridge-dyson-robot
(src/dyson-bitmap-octet.ts + src/dyson-device-360-map.ts).
"""

from __future__ import annotations

import base64
import io
import logging
import time
import zlib
from datetime import datetime, timezone
from typing import Any

import aiohttp

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_CATEGORY_ROBOT, DOMAIN
from .coordinator import DysonDataUpdateCoordinator
from .entity import DysonEntity

_LOGGER = logging.getLogger(__name__)


# Dust-density colour gradient ported from matterbridge-dyson-robot
# (DUST_COLOURS, ANSI 256 IDs translated to RGB hex). Purple → orange → white.
_DUST_GRADIENT_RGB: list[tuple[int, int, int]] = [
    (0x5F, 0x00, 0x87),  # 54  deep purple
    (0x87, 0x00, 0xAF),  # 89  purple
    (0xAF, 0x00, 0xD7),  # 124 magenta
    (0xD7, 0x5F, 0x00),  # 166 burnt orange
    (0xFF, 0x87, 0x00),  # 208 orange
    (0xFF, 0xAF, 0x00),  # 214 amber
    (0xFF, 0xD7, 0x00),  # 220 yellow
    (0xFF, 0xFF, 0x00),  # 226 bright yellow
    (0xFF, 0xFF, 0x5F),  # 227 pale yellow
    (0xFF, 0xFF, 0x87),
    (0xFF, 0xFF, 0xAF),
    (0xFF, 0xFF, 0xD7),
    (0xFF, 0xFF, 0xFF),  # 231 white
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dyson image platform."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    if isinstance(entry_data, dict) and entry_data.get("is_ble"):
        return
    coordinator: DysonDataUpdateCoordinator = entry_data

    # Only for robot devices with a cloud auth token.
    is_robot = any(
        cat == DEVICE_CATEGORY_ROBOT for cat in (coordinator.device_category or [])
    )
    has_token = bool(coordinator.config_entry.data.get("auth_token"))
    if not (is_robot and has_token):
        return

    entities: list[ImageEntity] = [
        DysonDustMapImage(hass, coordinator),
        DysonFloorPlanImage(hass, coordinator),
    ]
    async_add_entities(entities, True)
    _LOGGER.info(
        "Created dust-map + floor-plan image entities for %s",
        coordinator.serial_number,
    )


# ----------------------------------------------------------------------------
# Cloud fetch helpers (module-level caches, shared across image instances)
# ----------------------------------------------------------------------------

_CLEAN_MAPS_TTL_S = 30 * 60   # 30 minutes
_PERSIST_MAP_TTL_S = 6 * 3600  # 6 hours
_clean_maps_cache: dict[str, tuple[float, list[dict]]] = {}
_persist_map_cache: dict[str, tuple[float, dict]] = {}


async def _fetch_clean_maps(coordinator: DysonDataUpdateCoordinator) -> list[dict]:
    serial = coordinator.serial_number
    now = time.monotonic()
    cached = _clean_maps_cache.get(serial)
    if cached and (now - cached[0]) < _CLEAN_MAPS_TTL_S:
        return cached[1]
    auth_token = coordinator.config_entry.data.get("auth_token")
    if not auth_token:
        return []
    url = f"https://appapi.cp.dyson.com/v1/{serial}/clean-maps?dustMap=total"
    data = await _http_get_json(url, auth_token)
    if isinstance(data, list):
        # newest-first defensive sort
        data.sort(
            key=lambda c: (
                min(
                    (e.get("time") for e in (c.get("cleanTimeline") or []) if e.get("time")),
                    default="",
                )
            ),
            reverse=True,
        )
        _clean_maps_cache[serial] = (now, data)
        return data
    return cached[1] if cached else []


async def _fetch_persist_map(
    coordinator: DysonDataUpdateCoordinator, map_id: str
) -> dict:
    serial = coordinator.serial_number
    key = f"{serial}:{map_id}"
    now = time.monotonic()
    cached = _persist_map_cache.get(key)
    if cached and (now - cached[0]) < _PERSIST_MAP_TTL_S:
        return cached[1]
    auth_token = coordinator.config_entry.data.get("auth_token")
    if not auth_token:
        return {}
    url = f"https://appapi.cp.dyson.com/v1/app/{serial}/persistent-maps/{map_id}"
    data = await _http_get_json(url, auth_token)
    if isinstance(data, dict):
        _persist_map_cache[key] = (now, data)
        return data
    return cached[1] if cached else {}


async def _http_get_json(url: str, auth_token: str) -> Any:
    """GET an auth'd JSON endpoint. Returns parsed JSON or None on failure."""
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "User-Agent": "android client",
        "Accept": "application/json",
    }
    timeout = aiohttp.ClientTimeout(total=20)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    _LOGGER.warning(
                        "Dyson cloud GET %s → HTTP %d", url, resp.status
                    )
                    return None
                return await resp.json()
    except aiohttp.ClientError as err:
        _LOGGER.warning("Dyson cloud GET %s failed: %s", url, err)
        return None


# ----------------------------------------------------------------------------
# Rendering helpers
# ----------------------------------------------------------------------------


def _apply_orientation(img, rotation_deg: int):
    """Apply Y-invert + rotation to match MyDyson app orientation.

    Matches matterbridge-dyson-robot rendering:
      renderer.invertY = true (always for Vis Nav)
      renderer.rotation = persistentMapDisplayOrientation
    """
    from PIL import Image

    # Y-flip first (raw bitmaps use Y=0 at bottom-left; PIL uses top-left)
    img = img.transpose(Image.FLIP_TOP_BOTTOM)
    if rotation_deg:
        # PIL.rotate is counter-clockwise; negate to match app convention
        img = img.rotate(-rotation_deg, expand=True, resample=Image.NEAREST)
    return img


def _palette_from_floor_plan(presentation_png: bytes):
    """Open the floor-plan PNG and recolour for clear display.

    Source palette:
      Black  (zone interior)
      White  (zone boundary / walls)
      Gray   (outside any zone)
    Re-paint to a soft, high-contrast palette so it reads clearly under the
    transparent dust overlay.
    """
    from PIL import Image

    img = Image.open(io.BytesIO(presentation_png)).convert("RGBA")
    pixels = img.load()
    w, h = img.size
    # Repaint: zones → light cream, boundaries → dark blue-grey, outside → near-white
    for y in range(h):
        for x in range(w):
            r, g, b, _ = pixels[x, y]
            if r > 200 and g > 200 and b > 200:
                # white = boundary
                pixels[x, y] = (60, 60, 90, 255)
            elif r < 50 and g < 50 and b < 50:
                # black = zone interior
                pixels[x, y] = (250, 248, 240, 255)
            else:
                # gray = outside
                pixels[x, y] = (235, 235, 235, 255)
    return img


def _render_dust_map_png(
    dust_map: dict,
    cleaned_footprint_png: bytes | None,
    presentation_png: bytes | None,
    rotation_deg: int = 0,
) -> bytes | None:
    """Render the dust-level bitmap as a PNG, overlaying it on the floor plan.

    The dust map is a zlib-compressed raw octet bitmap (one byte per pixel,
    0-255 dust level). We convert to a colour gradient. If a presentation map
    PNG is supplied, we composite it underneath as a clearly-visible floor
    plan; the dust overlay rides on top with full opacity for dusty regions
    and transparent for clean ones.
    """
    try:
        from PIL import Image
    except ImportError:
        _LOGGER.warning("Pillow not available — cannot render dust map PNG")
        return None

    try:
        width = int(dust_map["width"])
        height = int(dust_map["height"])
        dust_data = dust_map["dustData"][0]
        scale = max(1, int(dust_data.get("scaleFactor") or 255))
        raw = zlib.decompress(base64.b64decode(dust_data["data"]))
    except (KeyError, ValueError, TypeError, zlib.error, IndexError) as err:
        _LOGGER.warning("Malformed dust map data: %s", err)
        return None

    if len(raw) < width * height:
        _LOGGER.warning(
            "Dust map size mismatch: declared %dx%d but only %d bytes",
            width,
            height,
            len(raw),
        )
        return None

    # Build the dust heatmap as RGBA. Zero dust → transparent so the floor plan
    # background shows through.
    rgba = bytearray(width * height * 4)
    n_levels = len(_DUST_GRADIENT_RGB)
    for i in range(width * height):
        level = raw[i]
        if level == 0:
            rgba[i * 4 + 3] = 0
            continue
        normalized = min(1.0, level / scale)
        idx = min(n_levels - 1, int(normalized * n_levels))
        r, g, b = _DUST_GRADIENT_RGB[idx]
        rgba[i * 4] = r
        rgba[i * 4 + 1] = g
        rgba[i * 4 + 2] = b
        rgba[i * 4 + 3] = 200  # slightly transparent so floor plan shows through
    dust_img = Image.frombytes("RGBA", (width, height), bytes(rgba))
    dust_img = _apply_orientation(dust_img, rotation_deg)

    # Floor-plan background — recoloured for clarity, sized to match dust map
    composite = dust_img
    if presentation_png:
        try:
            bg = _palette_from_floor_plan(presentation_png)
            bg = _apply_orientation(bg, rotation_deg)
            if bg.size != dust_img.size:
                bg = bg.resize(dust_img.size, resample=Image.NEAREST)
            composite = Image.alpha_composite(bg, dust_img)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Presentation map overlay skipped: %s", err)

    # Scale up small bitmaps for legibility
    max_dim = max(composite.size)
    if max_dim < 600:
        factor = max(1, 600 // max_dim)
        composite = composite.resize(
            (composite.size[0] * factor, composite.size[1] * factor),
            resample=Image.NEAREST,
        )

    buf = io.BytesIO()
    composite.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_presentation_png(
    presentation_png: bytes, rotation_deg: int = 0
) -> bytes | None:
    """Render the floor-plan PNG with the same orientation as the dust map."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        img = _palette_from_floor_plan(presentation_png)
        img = _apply_orientation(img, rotation_deg)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Failed to render presentation PNG: %s", err)
        return None
    max_dim = max(img.size)
    if max_dim < 600:
        factor = max(1, 600 // max_dim)
        img = img.resize(
            (img.size[0] * factor, img.size[1] * factor),
            resample=Image.NEAREST,
        )
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ----------------------------------------------------------------------------
# Entities
# ----------------------------------------------------------------------------


class DysonDustMapImage(DysonEntity, ImageEntity):
    """Dust-density heatmap of the most recent clean, rendered as PNG."""

    coordinator: DysonDataUpdateCoordinator
    _attr_should_poll = True
    _attr_content_type = "image/png"

    def __init__(
        self, hass: HomeAssistant, coordinator: DysonDataUpdateCoordinator
    ) -> None:
        ImageEntity.__init__(self, hass)
        DysonEntity.__init__(self, coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_dust_map"
        self._attr_name = "Dust Map"
        self._attr_icon = "mdi:map-search"
        self._cached_clean_id: str | None = None
        self._cached_png: bytes | None = None

    async def _build(self) -> bytes | None:
        cleans = await _fetch_clean_maps(self.coordinator)
        if not cleans:
            return None
        latest = cleans[0]
        clean_id = latest.get("cleanId")
        if clean_id and clean_id == self._cached_clean_id and self._cached_png:
            return self._cached_png

        dust_map = latest.get("dustMap")
        if not dust_map:
            return None

        # Fetch presentation map for overlay if persistentMap is referenced.
        presentation_png: bytes | None = None
        rotation_deg = 0
        persistent = latest.get("persistentMap") or {}
        pmap_id = persistent.get("id")
        if pmap_id:
            pmap = await _fetch_persist_map(self.coordinator, pmap_id)
            pres = (pmap.get("presentationMap") or {}).get("data")
            if pres:
                try:
                    presentation_png = base64.b64decode(pres)
                except (ValueError, TypeError):
                    presentation_png = None
            # persistentMapDisplayOrientation is the rotation in degrees
            # set by the user in MyDyson when they orient the map.
            rotation_deg = int(
                (pmap.get("zonesDefinition") or {}).get(
                    "persistentMapDisplayOrientation"
                )
                or 0
            )

        cleaned_fp_png: bytes | None = None
        fp = (latest.get("cleanedFootprint") or {}).get("data")
        if fp:
            try:
                cleaned_fp_png = base64.b64decode(fp)
            except (ValueError, TypeError):
                cleaned_fp_png = None

        png = _render_dust_map_png(
            dust_map, cleaned_fp_png, presentation_png, rotation_deg
        )
        if png:
            self._cached_clean_id = clean_id
            self._cached_png = png
            self._attr_image_last_updated = datetime.now(timezone.utc)
        return png

    async def async_image(self) -> bytes | None:
        return await self._build()

    async def async_update(self) -> None:
        # Trigger a refresh on HA's polling cycle so image_last_updated is fresh.
        await self._build()


class DysonFloorPlanImage(DysonEntity, ImageEntity):
    """The Vis Nav's static persistent-map presentation image (floor plan)."""

    coordinator: DysonDataUpdateCoordinator
    _attr_should_poll = True
    _attr_content_type = "image/png"

    def __init__(
        self, hass: HomeAssistant, coordinator: DysonDataUpdateCoordinator
    ) -> None:
        ImageEntity.__init__(self, hass)
        DysonEntity.__init__(self, coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_floor_plan"
        self._attr_name = "Floor Plan"
        self._attr_icon = "mdi:floor-plan"
        self._cached_pmap_id: str | None = None
        self._cached_png: bytes | None = None

    async def _build(self) -> bytes | None:
        cleans = await _fetch_clean_maps(self.coordinator)
        if not cleans:
            return None
        persistent = (cleans[0].get("persistentMap") or {})
        pmap_id = persistent.get("id")
        if not pmap_id:
            return None
        if pmap_id == self._cached_pmap_id and self._cached_png:
            return self._cached_png

        pmap = await _fetch_persist_map(self.coordinator, pmap_id)
        pres_b64 = (pmap.get("presentationMap") or {}).get("data")
        if not pres_b64:
            return None
        try:
            png_in = base64.b64decode(pres_b64)
        except (ValueError, TypeError):
            return None

        rotation_deg = int(
            (pmap.get("zonesDefinition") or {}).get(
                "persistentMapDisplayOrientation"
            )
            or 0
        )
        png = _render_presentation_png(png_in, rotation_deg)
        if png:
            self._cached_pmap_id = pmap_id
            self._cached_png = png
            self._attr_image_last_updated = datetime.now(timezone.utc)
        return png

    async def async_image(self) -> bytes | None:
        return await self._build()

    async def async_update(self) -> None:
        await self._build()
