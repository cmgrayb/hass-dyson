"""Image platform for Dyson integration.

Currently provides:
 - DysonDustMapImage:   the dust-density heatmap for the most recent clean
                        (rendered as PNG with purple→white gradient over the
                        floor plan), refreshed when a new cleanId appears.
 - DysonFloorPlanImage: the persistent-map presentation image (the static
                        floor plan with zone boundaries and dock location).

v1 devices: dust map blob embedded in CleanRecord; floor plan from
  GET /v2/app/{serial}/persistent-maps/{id} (presentation_map_data field).
v2 devices (e.g. RB05 Spot+Scrub):
  Dust map strategy (priority order):
    1. Map Visualizer API: GET /v1/mapvisualizer/devices/{serial}/map/{cleanId}
       (Vis Nav only; returns 404 for RB05/804A — result cached for TTL).
    2. Clean Map Data API: GET /v2/{serial}/clean-maps-data/{cleanId}
       Returns JSON with {dimensions, dustMap, cleanPath, dockLocation, …}.
       Rendered client-side by _render_v2_map_png (purple→white heatmap +
       blue robot path + green dock icon).
  Floor plan strategy (priority order):
    1. Presentation bitmap in GET /v2/app/{serial}/persistent-maps/{id}
       (v1 Vis Nav only — not present for RB05).
    2. Map Visualizer API: GET /v1/mapvisualizer/devices/{serial}/map/{pmapId}
       (returns 404 for RB05).
    3. Zone boundary lines from GET /v2/{serial}/clean-maps-data/{cleanId}
       Rendered client-side by _render_v2_floor_plan_png (white background +
       dark zone boundary line segments + green dock icon).

Bitmap rendering ported from thoukydides/matterbridge-dyson-robot
(src/dyson-bitmap-octet.ts + src/dyson-device-360-map.ts).
"""

from __future__ import annotations

import base64
import io
import logging
import zlib
from datetime import datetime, timezone

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_CATEGORY_ROBOT, DOMAIN
from .coordinator import DysonDataUpdateCoordinator, TTLCache
from .entity import DysonEntity
from .vacuum import fetch_clean_maps

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
# Cloud fetch helpers.
#
# Recent cleaning runs (the clean-maps endpoint) are fetched via the SHARED
# `fetch_clean_maps` in vacuum.py — the cleaning-history sensors in sensor.py
# read the same blob, so one cache covers both consumers.
#
# The persistent-map endpoint (persistent-maps/{id}) is only consumed here, so
# the cache stays local. Persistent maps change rarely → generous TTL.
# ----------------------------------------------------------------------------

_persist_map_cache = TTLCache(6 * 3600)
_map_image_cache = TTLCache(10 * 60)
_floor_plan_cache = TTLCache(6 * 3600)


async def _fetch_map_image(
    coordinator: DysonDataUpdateCoordinator, map_id: str
) -> bytes | None:
    """Fetch a server-rendered map image from the Dyson Map Visualizer API.

    Uses the ``get_map_image(serial, map_id)`` method added in libdyson-rest
    v0.15.0b5.  ``map_id`` can be either a clean session UUID (for a dust map)
    or a persistent-map integer ID string (for a floor plan).

    Successful responses are cached for 10 minutes.  A ``b""`` sentinel is
    stored for known-missing results (e.g. 404 from the Map Visualizer for v2
    devices) so the endpoint is not retried on every poll cycle.
    Returns ``None`` on any API or network error.
    """
    from libdyson_rest.exceptions import DysonAPIError, DysonAuthError

    key = f"{coordinator.serial_number}:{map_id}"
    cached = _map_image_cache.get(key)
    if cached is not None:
        # b"" sentinel means a previous call confirmed no image is available.
        return cached if cached else None

    async with coordinator.async_cloud_client() as client:
        if client is None:
            return None
        try:
            image_bytes = await client.get_map_image(coordinator.serial_number, map_id)
        except (DysonAPIError, DysonAuthError) as err:
            _LOGGER.debug(
                "Map Visualizer fetch failed for %s map_id=%s: %s",
                coordinator.serial_number,
                map_id,
                err,
            )
            # Cache the miss so we don't retry on every poll cycle.
            _map_image_cache.set(key, b"")
            return None

    if image_bytes:
        _map_image_cache.set(key, image_bytes)
    else:
        _map_image_cache.set(key, b"")
    return image_bytes or None


async def _fetch_clean_map_data_image(
    coordinator: DysonDataUpdateCoordinator, clean_id: str
) -> bytes | None:
    """Try to fetch/render a dust map image via the v2 clean-maps-data endpoint.

    Calls ``GET /v2/{serial}/clean-maps-data/{clean_id}`` (libdyson-rest
    ``get_clean_map_data``).  The response structure is logged at DEBUG level
    for diagnostics.  If the payload contains a renderable dust-map grid
    (``width``, ``height``, ``dustData`` keys) it is rendered to a PNG with
    the existing ``_render_dust_map_png`` helper.

    Results are cached in ``_map_image_cache`` under the ``clean_id`` key
    (shared with ``_fetch_map_image``).  A ``b""`` sentinel is stored on
    failure to suppress repeated API calls within the TTL.
    """
    from libdyson_rest.exceptions import DysonAPIError, DysonAuthError

    key = f"{coordinator.serial_number}:{clean_id}"
    # If a previous attempt already succeeded (or confirmed no image), reuse it.
    cached = _map_image_cache.get(key)
    if cached is not None:
        return cached if cached else None

    async with coordinator.async_cloud_client() as client:
        if client is None:
            return None
        try:
            data = await client.get_clean_map_data(coordinator.serial_number, clean_id)
        except (DysonAPIError, DysonAuthError) as err:
            _LOGGER.debug(
                "clean_map_data fetch failed for %s clean_id=%s: %s",
                coordinator.serial_number,
                clean_id,
                err,
            )
            _map_image_cache.set(key, b"")
            return None

    if not data:
        _LOGGER.debug(
            "clean_map_data empty for %s clean_id=%s",
            coordinator.serial_number,
            clean_id,
        )
        _map_image_cache.set(key, b"")
        return None

    _LOGGER.debug(
        "clean_map_data keys for %s clean_id=%s: %s  (first 300 chars: %s)",
        coordinator.serial_number,
        clean_id,
        sorted(data.keys()),
        str(data)[:300],
    )

    # Strategy 1: v2 format — {dimensions, dustMap, cleanPath, …}
    # (returned by GET /v2/{serial}/clean-maps-data/{cleanId} for RB05/804A)
    if "dimensions" in data and "dustMap" in data:
        rotation = int(data.get("orientation") or 0)
        png = _render_v2_map_png(data, rotation)
        if png:
            _map_image_cache.set(key, png)
            return png

    # Strategy 2: v1 format — {width, height, dustData}
    if "width" in data and "height" in data and "dustData" in data:
        png = _render_dust_map_png(data, None, None)
        if png:
            _map_image_cache.set(key, png)
            return png

    # Nothing renderable — cache the miss.
    _map_image_cache.set(key, b"")
    return None


async def _fetch_v2_floor_plan_image(
    coordinator: DysonDataUpdateCoordinator, clean_id: str
) -> bytes | None:
    """Render a v2 floor plan from the clean-maps-data endpoint.

    Calls ``GET /v2/{serial}/clean-maps-data/{cleanId}`` and renders the zone
    boundary lines via ``_render_v2_floor_plan_png``.  Results are cached in
    ``_floor_plan_cache`` with a 6-hour TTL (floor plans change infrequently).
    A ``b""`` sentinel is stored on failure to suppress repeated API calls.
    """
    from libdyson_rest.exceptions import DysonAPIError, DysonAuthError

    key = f"{coordinator.serial_number}:fp:{clean_id}"
    cached = _floor_plan_cache.get(key)
    if cached is not None:
        return cached if cached else None

    async with coordinator.async_cloud_client() as client:
        if client is None:
            return None
        try:
            data = await client.get_clean_map_data(coordinator.serial_number, clean_id)
        except (DysonAPIError, DysonAuthError) as err:
            _LOGGER.debug(
                "v2 floor plan fetch failed for %s clean_id=%s: %s",
                coordinator.serial_number,
                clean_id,
                err,
            )
            _floor_plan_cache.set(key, b"")
            return None

    if not data:
        _floor_plan_cache.set(key, b"")
        return None

    rotation = int(data.get("orientation") or 0)
    png = _render_v2_floor_plan_png(data, rotation)
    _floor_plan_cache.set(key, png if png else b"")
    return png


async def _fetch_persist_map(coordinator: DysonDataUpdateCoordinator, map_id: str):
    """Fetch a persistent map via libdyson-rest (cached 6 h).

    Returns a ``PersistentMap`` object or the stale cached value on failure.
    """
    from libdyson_rest.exceptions import DysonAPIError, DysonAuthError

    key = f"{coordinator.serial_number}:{map_id}"
    fresh = _persist_map_cache.get(key)
    if fresh is not None:
        return fresh

    async with coordinator.async_cloud_client() as client:
        if client is None:
            return _persist_map_cache.get_stale(key)
        try:
            pmap = await client.get_persistent_map(
                coordinator.serial_number,
                map_id,
                api_version=await coordinator.async_discover_map_api_version(client),
            )
        except (DysonAPIError, DysonAuthError) as err:
            _LOGGER.debug(
                "Failed to fetch persistent map %s for %s: %s",
                map_id,
                coordinator.serial_number,
                err,
            )
            return _persist_map_cache.get_stale(key)

    _persist_map_cache.set(key, pmap)
    return pmap


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
    img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if rotation_deg:
        # PIL.rotate is counter-clockwise; negate to match app convention
        img = img.rotate(-rotation_deg, expand=True, resample=Image.Resampling.NEAREST)
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
            rgba_pixel: tuple[int, int, int, int] = pixels[x, y]  # type: ignore[assignment]
            r, g, b, _ = rgba_pixel
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
    map_offset_mm: tuple[float, float] | None = None,
    clean_position_mm: tuple[float, float] | None = None,
    map_resolution_mm_per_px: int = 20,
) -> bytes | None:
    """Render the dust map as a PNG, correctly positioned over the floor plan.

    Critical alignment math (ported from matterbridge-dyson-robot map.ts):
        dust_origin_in_pres_pixels = (cleanMapPosition - mapOffset) / mmPerPixel

    The dust map is a CROP of the world in clean-coordinates, smaller than the
    presentation map. To overlay it correctly we paste it onto a copy of the
    presentation map at the computed pixel offset. Just resizing the dust map
    to the presentation map's dimensions (the old approach) stretched it and
    made every pixel land in the wrong room.
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

    # Build the dust heatmap as RGBA in its native (clean-coordinate) space.
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
        rgba[i * 4 + 3] = 220
    dust_img = Image.frombytes("RGBA", (width, height), bytes(rgba))

    # No floor plan → render dust map alone with orientation
    if not presentation_png:
        composite = _apply_orientation(dust_img, rotation_deg)
    else:
        try:
            bg = _palette_from_floor_plan(presentation_png)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Floor plan palette failed: %s", err)
            composite = _apply_orientation(dust_img, rotation_deg)
        else:
            # Composite the dust map onto the presentation canvas at the right offset.
            # Apply orientation AFTER compositing so both layers transform together.
            if map_offset_mm is not None and clean_position_mm is not None:
                ox = int(
                    round(
                        (clean_position_mm[0] - map_offset_mm[0])
                        / map_resolution_mm_per_px
                    )
                )
                oy = int(
                    round(
                        (clean_position_mm[1] - map_offset_mm[1])
                        / map_resolution_mm_per_px
                    )
                )
            else:
                # Fallback: centre the dust map on the presentation map
                ox = max(0, (bg.size[0] - width) // 2)
                oy = max(0, (bg.size[1] - height) // 2)

            canvas = bg.copy()
            # Pillow alpha_composite needs a transparent backing the same size.
            # We use paste with the dust map's own alpha as mask for in-place
            # compositing at an offset (alpha_composite has no offset variant).
            canvas.paste(dust_img, (ox, oy), dust_img)
            composite = _apply_orientation(canvas, rotation_deg)

    # Scale up for legibility
    max_dim = max(composite.size)
    if max_dim < 800:
        factor = max(1, 800 // max_dim)
        composite = composite.resize(
            (composite.size[0] * factor, composite.size[1] * factor),
            resample=Image.Resampling.NEAREST,
        )

    buf = io.BytesIO()
    composite.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_v2_map_png(data: dict, rotation_deg: int = 0) -> bytes | None:
    """Render a v2 clean-maps-data response as a PNG image.

    The JSON returned by ``GET /v2/{serial}/clean-maps-data/{cleanId}``
    (reverse-engineered from the MyDyson APK ``sp0.CleanMapResponse``) has
    the following fields used here:

    .. code-block:: json

        {
          "dimensions": {"width": int, "height": int,
                         "resolution": float,     /* metres per cell */
                         "offsetX": float,         /* world-space origin X */
                         "offsetY": float},        /* world-space origin Y */
          "dustMap":   [{"type": "total", "data": [int, …]}],
          "cleanPath": [{"x": float, "y": float, "update": int}],
          "dockLocation": {"x": float, "y": float, "angle": float},
          "orientation": int
        }

    The ``dustMap.data`` list is a flat grid of *width × height* integer dust
    values (index ``i = row * width + col``, row 0 = world bottom row).
    The ``cleanPath`` and ``dockLocation`` coordinates are in the same world
    units as ``dimensions.resolution`` / ``offsetX`` / ``offsetY``.

    Renders the dust heatmap in the purple→white gradient, overlays the robot
    path as a blue line and the dock as a green circle, then applies the
    ``orientation`` rotation.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        _LOGGER.warning("Pillow not available — cannot render v2 map PNG")
        return None

    try:
        dims = data.get("dimensions") or {}
        width = int(dims.get("width") or 0)
        height = int(dims.get("height") or 0)
        resolution = float(dims.get("resolution") or 0.0)
        offset_x = float(dims.get("offsetX") or 0.0)
        offset_y = float(dims.get("offsetY") or 0.0)

        if width <= 0 or height <= 0:
            _LOGGER.debug("v2 map: invalid dimensions %dx%d", width, height)
            return None

        # --- Find the dust data layer (prefer "total", fall back to first) ---
        dust_data: list[int] = []
        for dm in data.get("dustMap") or []:
            if not isinstance(dm, dict):
                continue
            dm_type = (dm.get("type") or "").lower()
            dm_vals = dm.get("data") or []
            if dm_type in ("total", "areavisited") and dm_vals:
                dust_data = [int(v) for v in dm_vals]
                break
        if not dust_data:
            for dm in data.get("dustMap") or []:
                if isinstance(dm, dict) and dm.get("data"):
                    dust_data = [int(v) for v in dm["data"]]
                    break

        if not dust_data:
            _LOGGER.debug(
                "v2 map: dustMap present but no renderable data layer — types: %s",
                [dm.get("type") for dm in (data.get("dustMap") or [])],
            )
            return None

        # --- Render the dust heatmap onto a width×height RGBA canvas ---
        max_val = max(dust_data) or 1
        n_levels = len(_DUST_GRADIENT_RGB)
        rgba = bytearray(width * height * 4)
        for i in range(min(len(dust_data), width * height)):
            level = dust_data[i]
            if level == 0:
                continue
            normalized = min(1.0, level / max_val)
            idx = min(n_levels - 1, int(normalized * n_levels))
            r, g, b = _DUST_GRADIENT_RGB[idx]
            rgba[i * 4] = r
            rgba[i * 4 + 1] = g
            rgba[i * 4 + 2] = b
            rgba[i * 4 + 3] = 220

        img = Image.frombytes("RGBA", (width, height), bytes(rgba))
        draw = ImageDraw.Draw(img)

        def _world_to_px(wx: float, wy: float) -> tuple[int, int]:
            """Map world coordinates to dust-grid pixel coordinates."""
            if resolution <= 0:
                return (width // 2, height // 2)
            px = int((wx - offset_x) / resolution)
            py = int((wy - offset_y) / resolution)
            return (max(0, min(width - 1, px)), max(0, min(height - 1, py)))

        # --- Robot path (blue semi-transparent line) ---
        clean_path = data.get("cleanPath") or []
        if clean_path and resolution > 0:
            pts = [
                _world_to_px(float(p.get("x") or 0), float(p.get("y") or 0))
                for p in clean_path
                if isinstance(p, dict)
            ]
            if len(pts) > 1:
                draw.line(pts, fill=(30, 144, 255, 200), width=2)

        # --- Dock location (solid green circle) ---
        dock = data.get("dockLocation")
        if isinstance(dock, dict) and dock.get("x") is not None:
            dx, dy = _world_to_px(float(dock.get("x") or 0), float(dock.get("y") or 0))
            draw.ellipse([dx - 4, dy - 4, dx + 4, dy + 4], fill=(0, 200, 80, 255))

    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("v2 map rendering failed: %s", err)
        return None

    # Apply orientation (Y-flip always, then rotation)
    img = _apply_orientation(img, rotation_deg)

    # Scale up for legibility
    max_dim = max(img.size)
    if max_dim < 800:
        factor = max(1, 800 // max_dim)
        img = img.resize(
            (img.size[0] * factor, img.size[1] * factor),
            resample=Image.Resampling.NEAREST,
        )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_v2_floor_plan_png(data: dict, rotation_deg: int = 0) -> bytes | None:
    """Render zone boundary lines from a v2 clean-maps-data response as a floor plan PNG.

    Uses the same response as ``_render_v2_map_png`` (``GET /v2/{serial}/clean-maps-data/
    {cleanId}``) but draws only the zone boundary line segments and dock location on a
    white canvas — no dust heatmap.  This gives a usable floor plan for v2 devices
    (e.g. RB05 Spot+Scrub) where ``GET /v2/app/{serial}/persistent-maps/{id}``
    returns structured JSON instead of a pre-rendered PNG.

    JSON fields used:

    .. code-block:: json

        {
          "dimensions": {"width": int, "height": int,
                         "resolution": float,     /* metres per cell */
                         "offsetX": float,
                         "offsetY": float},
          "zones": [
            {"presentation": [{"start": {"x": float, "y": float},
                               "end":   {"x": float, "y": float},
                               "type":   int}]}
          ],
          "dockLocation": {"x": float, "y": float, "angle": float},
          "orientation": int
        }
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        _LOGGER.warning("Pillow not available — cannot render v2 floor plan PNG")
        return None

    try:
        dims = data.get("dimensions") or {}
        width = int(dims.get("width") or 0)
        height = int(dims.get("height") or 0)
        resolution = float(dims.get("resolution") or 0.0)
        offset_x = float(dims.get("offsetX") or 0.0)
        offset_y = float(dims.get("offsetY") or 0.0)

        if width <= 0 or height <= 0:
            _LOGGER.debug("v2 floor plan: invalid dimensions %dx%d", width, height)
            return None

        # White background
        img = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)

        def _world_to_px(wx: float, wy: float) -> tuple[int, int]:
            if resolution <= 0:
                return (width // 2, height // 2)
            px = int((wx - offset_x) / resolution)
            py = int((wy - offset_y) / resolution)
            return (max(0, min(width - 1, px)), max(0, min(height - 1, py)))

        # Draw zone boundary lines
        # Line.type: 0 = outer wall (thick dark), other = room separator (thin gray)
        zones = data.get("zones") or []
        has_lines = False
        for zone in zones:
            if not isinstance(zone, dict):
                continue
            for seg in zone.get("presentation") or []:
                if not isinstance(seg, dict):
                    continue
                start = seg.get("start") or {}
                end = seg.get("end") or {}
                sx, sy = _world_to_px(
                    float(start.get("x") or 0), float(start.get("y") or 0)
                )
                ex, ey = _world_to_px(
                    float(end.get("x") or 0), float(end.get("y") or 0)
                )
                line_type = seg.get("type", 0)
                # Type 0 → outer wall (thicker, darker); others → room separator
                if line_type == 0:
                    draw.line([sx, sy, ex, ey], fill=(40, 40, 40, 255), width=2)
                else:
                    draw.line([sx, sy, ex, ey], fill=(130, 130, 130, 255), width=1)
                has_lines = True

        # Dock location — green filled circle
        dock = data.get("dockLocation")
        has_dock = isinstance(dock, dict) and dock.get("x") is not None
        if has_dock:
            dx, dy = _world_to_px(float(dock.get("x") or 0), float(dock.get("y") or 0))
            draw.ellipse(
                [dx - 5, dy - 5, dx + 5, dy + 5],
                fill=(0, 200, 80, 255),
                outline=(0, 120, 40, 255),
            )

        if not has_lines and not has_dock:
            _LOGGER.debug("v2 floor plan: no zones or dock location in response")
            return None

    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("v2 floor plan rendering failed: %s", err)
        return None

    # Apply orientation (Y-flip always, then rotation)
    img = _apply_orientation(img, rotation_deg)

    # Scale up for legibility
    max_dim = max(img.size)
    if max_dim < 800:
        factor = max(1, 800 // max_dim)
        img = img.resize(
            (img.size[0] * factor, img.size[1] * factor),
            resample=Image.Resampling.NEAREST,
        )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
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
            resample=Image.Resampling.NEAREST,
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

    @property
    def should_poll(self) -> bool:
        # _attr_should_poll is inert on CoordinatorEntity subclasses (#408).
        return True

    async def _build(self) -> bytes | None:
        cleans = await fetch_clean_maps(self.coordinator)
        if not cleans:
            return None
        latest = cleans[0]
        clean_id = latest.clean_id
        if clean_id and clean_id == self._cached_clean_id and self._cached_png:
            return self._cached_png

        dust_map_model = getattr(latest, "dust_map", None)
        download_url = getattr(latest, "download_url", None)

        _LOGGER.debug(
            "Dust map build for %s: clean_id=%s, has_dust_map=%s, has_download_url=%s",
            self.coordinator.serial_number,
            clean_id,
            dust_map_model is not None,
            download_url is not None,
        )

        # -------------------------------------------------------------------
        # v2 path: no embedded dust map blob — use the cloud APIs to get or
        # render a map image for the clean session.
        # Triggered for any record that has a clean_id but no embedded dust
        # map, regardless of whether a download_url is present.
        # -------------------------------------------------------------------
        if not dust_map_model and clean_id:
            # Strategy 1: Map Visualizer API (works for Vis Nav, 404 for RB05).
            png = await _fetch_map_image(self.coordinator, clean_id)
            # Strategy 2: v2 clean-maps-data endpoint (logs response for diagnostics).
            if png is None:
                png = await _fetch_clean_map_data_image(self.coordinator, clean_id)
            if png is None:
                _LOGGER.debug(
                    "Dust map for %s: no image available for clean_id=%s"
                    " (map visualizer and clean-maps-data both returned nothing);"
                    " check DEBUG logs for clean_map_data response structure",
                    self.coordinator.serial_number,
                    clean_id,
                )
                return None
            self._cached_clean_id = clean_id
            self._cached_png = png
            self._attr_image_last_updated = datetime.now(timezone.utc)
            return png

        # -------------------------------------------------------------------
        # v1 path: dust map blob embedded in the CleanRecord.
        # -------------------------------------------------------------------
        if not dust_map_model:
            return None

        # Convert DustMapData to the dict shape expected by _render_dust_map_png.
        dust_map_dict = {
            "width": dust_map_model.width,
            "height": dust_map_model.height,
            "resolution": dust_map_model.resolution,
            "dustData": dust_map_model.dust_data,
        }

        # Coordinate info for correctly positioning the dust crop on the
        # presentation map. Both maps quote positions in world mm; resolution
        # is mm/pixel (typically 20 for Vis Nav).
        resolution_mm_per_px = dust_map_model.resolution
        clean_position_mm: tuple[float, float] | None = None
        map_offset_mm: tuple[float, float] | None = None
        if latest.clean_map_position:
            pos = latest.clean_map_position
            clean_position_mm = (pos.x, pos.y)

        presentation_png: bytes | None = None
        rotation_deg = 0
        pmap_id = latest.persistent_map_id
        if pmap_id:
            pmap = await _fetch_persist_map(self.coordinator, pmap_id)
            if pmap and pmap.presentation_map_data:
                try:
                    presentation_png = base64.b64decode(pmap.presentation_map_data)
                except (ValueError, TypeError):
                    presentation_png = None
            if pmap:
                rotation_deg = pmap.display_orientation
                if pmap.offset_x is not None and pmap.offset_y is not None:
                    map_offset_mm = (pmap.offset_x, pmap.offset_y)

        cleaned_fp_png: bytes | None = None
        if latest.cleaned_footprint and latest.cleaned_footprint.data:
            try:
                cleaned_fp_png = base64.b64decode(latest.cleaned_footprint.data)
            except (ValueError, TypeError):
                cleaned_fp_png = None

        png = _render_dust_map_png(
            dust_map_dict,
            cleaned_fp_png,
            presentation_png,
            rotation_deg,
            map_offset_mm=map_offset_mm,
            clean_position_mm=clean_position_mm,
            map_resolution_mm_per_px=resolution_mm_per_px,
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
    """Floor plan image entity — rendered from the persistent map or v2 zone boundaries.

    For v1 devices (Vis Nav): uses the pre-rendered presentation PNG embedded in
    ``GET /v2/app/{serial}/persistent-maps/{id}``.
    For v2 devices (e.g. RB05 Spot+Scrub): renders zone boundary lines from
    ``GET /v2/{serial}/clean-maps-data/{cleanId}`` via ``_render_v2_floor_plan_png``.
    """

    coordinator: DysonDataUpdateCoordinator
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

    @property
    def should_poll(self) -> bool:
        # _attr_should_poll is inert on CoordinatorEntity subclasses (#408).
        return True

    async def _build(self) -> bytes | None:
        cleans = await fetch_clean_maps(self.coordinator)
        if not cleans:
            return None
        pmap_id = cleans[0].persistent_map_id
        if not pmap_id:
            _LOGGER.warning(
                "Floor plan for %s: most recent clean record has no"
                " persistent_map_id — cannot render floor plan",
                self.coordinator.serial_number,
            )
            return None
        if pmap_id == self._cached_pmap_id and self._cached_png:
            return self._cached_png

        pmap = await _fetch_persist_map(self.coordinator, pmap_id)
        if not pmap:
            _LOGGER.warning(
                "Floor plan for %s: persistent map %s could not be fetched"
                " (API error or unsupported endpoint for this device model)",
                self.coordinator.serial_number,
                pmap_id,
            )
            return None
        if not pmap.presentation_map_data:
            # For some device models (e.g. RB05/Spot+Scrub) the v1
            # persistent-maps endpoint returns a stub with no embedded image.
            # Fall back to the Map Visualizer API which renders the floor plan
            # server-side.
            _LOGGER.debug(
                "Floor plan for %s: persistent map %s has no presentation_map_data;"
                " trying Map Visualizer API",
                self.coordinator.serial_number,
                pmap_id,
            )
            png = await _fetch_map_image(self.coordinator, pmap_id)
            if png is None:
                _LOGGER.debug(
                    "Floor plan for %s: map visualizer returned no image for"
                    " persistent_map_id=%s — trying v2 zone-boundary renderer",
                    self.coordinator.serial_number,
                    pmap_id,
                )
                # v2 devices (e.g. RB05): no pre-rendered floor plan bitmap
                # exists anywhere.  Render the zone boundary lines from the
                # most recent clean-maps-data response instead.
                clean_id = cleans[0].clean_id
                if clean_id:
                    png = await _fetch_v2_floor_plan_image(self.coordinator, clean_id)
                if png is None:
                    _LOGGER.debug(
                        "Floor plan for %s: no floor plan image available for"
                        " persistent_map_id=%s (v1 Map Visualizer 404, v2"
                        " zone-boundary render returned nothing)",
                        self.coordinator.serial_number,
                        pmap_id,
                    )
                    return None
            self._cached_pmap_id = pmap_id
            self._cached_png = png
            self._attr_image_last_updated = datetime.now(timezone.utc)
            return png
        try:
            png_in = base64.b64decode(pmap.presentation_map_data)
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Floor plan for %s: could not base64-decode presentation_map_data: %s",
                self.coordinator.serial_number,
                err,
            )
            return None

        png = _render_presentation_png(png_in, pmap.display_orientation)
        if png:
            self._cached_pmap_id = pmap_id
            self._cached_png = png
            self._attr_image_last_updated = datetime.now(timezone.utc)
        return png

    async def async_image(self) -> bytes | None:
        return await self._build()

    async def async_update(self) -> None:
        await self._build()
