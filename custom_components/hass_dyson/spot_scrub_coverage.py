"""Live position and clean coverage of a Spot+Scrub (RB05).

While cleaning, the robot streams the path it drives as ``cur_path`` batches
on ``status/jdm``: a flat ``[first point id, x, y, angle, update, ..., unix
time]`` array in metres, in the same map frame as the cloud's map geometry.
Point ids restart at each clean. ``update`` says what the robot did at the
point: 0 travelling, 1 vacuuming, 3 vacuuming and mopping (seen on RB05,
2026-10); 2 is taken to be mopping. The run's ``fullCleanAction`` rides the
state messages and is the fallback for other values.

The recorder keeps the current run's points, each tagged with what was done
there, so the coverage image can show what was vacuumed and what was
mopped. It also keeps the latest pose and the room it lies in.
Points are saved to storage so a restart mid-clean keeps the run.
"""

from __future__ import annotations

import io
import logging
import math
import time
import weakref
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .coordinator import DysonDataUpdateCoordinator, TTLCache

_LOGGER = logging.getLogger(__name__)

VACUUM = 1
MOP = 2
ACTION_BITS = {"VACUUMING": VACUUM, "MOPPING": MOP, "VACUUMING_AND_MOPPING": 3}

MAX_POINTS = 40000
# A batch whose first id is this far below the last one starts a new run.
RESET_GAP = 20
SAVE_DELAY = 60
STORAGE_VERSION = 1

# Cleaning width drawn for each path point, in metres (approximate).
BRUSH_WIDTH_M = 0.25
# Consecutive points further apart than this are not joined (relocation).
MAX_JOIN_M = 0.6

_geometry_cache = TTLCache(6 * 3600)


def parse_cur_path(values: Any) -> list[tuple[int, float, float, float, int]]:
    """Return (id, x, y, angle, update) per point of a ``cur_path`` batch."""
    if not isinstance(values, list) or len(values) < 6 or (len(values) - 2) % 4:
        return []
    try:
        first = int(values[0])
        body = [float(value) for value in values[1:-1]]
    except (TypeError, ValueError):
        return []
    return [
        (
            first + i,
            body[4 * i],
            body[4 * i + 1],
            body[4 * i + 2],
            int(body[4 * i + 3]),
        )
        for i in range(len(body) // 4)
    ]


def parse_global_position(value: Any) -> tuple[int, float, float, float, int] | None:
    """Return the latest (id, x, y, angle, update) of an RB05 ``globalPosition``."""
    if not isinstance(value, list) or not value or not isinstance(value[-1], dict):
        return None
    point = value[-1]
    try:
        return (
            int(point.get("id", 0)),
            float(point["x"]),
            float(point["y"]),
            float(point.get("angle") or 0.0),
            int(point.get("update") or 0),
        )
    except (KeyError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Map geometry (from GET /v2/{serial}/clean-maps-data/{cleanId})
# ---------------------------------------------------------------------------


def parse_geometry(data: dict[str, Any]) -> dict[str, Any] | None:
    """Keep the parts of a clean-maps-data response the coverage image uses."""
    if not isinstance(data, dict):
        return None
    zones = []
    for zone in data.get("zones") or []:
        if not isinstance(zone, dict):
            continue
        segments = []
        for seg in zone.get("presentation") or []:
            try:
                start, end = seg["start"], seg["end"]
                segments.append(
                    (
                        float(start["x"]),
                        float(start["y"]),
                        float(end["x"]),
                        float(end["y"]),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        label = zone.get("nameLocation") or {}
        try:
            label_xy = (float(label["x"]), float(label["y"]))
        except (KeyError, TypeError, ValueError):
            label_xy = None
        zones.append(
            {
                "id": str(zone.get("id", "")),
                "name": zone.get("name") or str(zone.get("id", "")),
                "segments": segments,
                "label": label_xy,
                "status": zone.get("cleanStatus"),
            }
        )
    dock = data.get("dockLocation") or {}
    try:
        dock_xy = (float(dock["x"]), float(dock["y"]))
    except (KeyError, TypeError, ValueError):
        dock_xy = None
    # The robot's path as the cloud recorded it, used when no live run exists.
    path = []
    for point in data.get("cleanPath") or []:
        try:
            path.append(
                (float(point["x"]), float(point["y"]), int(point.get("update") or 0))
            )
        except (KeyError, TypeError, ValueError):
            continue
    if not zones:
        return None
    return {
        "zones": zones,
        "dock": dock_xy,
        "orientation": int(data.get("orientation") or 0),
        "clean_path": path,
    }


def _inside(segments: list[tuple[float, float, float, float]], x: float, y: float):
    """Ray-cast point-in-outline test that does not need ordered segments."""
    crossings = 0
    for x1, y1, x2, y2 in segments:
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            crossings += 1
    return crossings % 2 == 1


def zone_at(geometry: dict[str, Any] | None, x: float, y: float):
    """Return the zone containing (x, y), or None."""
    for zone in (geometry or {}).get("zones", []):
        if zone["segments"] and _inside(zone["segments"], x, y):
            return zone
    return None


async def async_fetch_geometry(
    coordinator: DysonDataUpdateCoordinator,
) -> tuple[str, dict[str, Any]] | None:
    """Fetch the map geometry of the most recent clean (cached per clean)."""
    from libdyson_rest.exceptions import DysonAPIError, DysonAuthError

    from .vacuum import fetch_clean_maps

    cleans = await fetch_clean_maps(coordinator)
    if not cleans or not getattr(cleans[0], "clean_id", None):
        return None
    clean_id = cleans[0].clean_id
    key = f"{coordinator.serial_number}:geometry:{clean_id}"
    cached = _geometry_cache.get(key)
    if cached is not None:
        return (clean_id, cached) if cached else None
    async with coordinator.async_cloud_client() as client:
        if client is None:
            return None
        try:
            data = await client.get_clean_map_data(coordinator.serial_number, clean_id)
        except (DysonAPIError, DysonAuthError) as err:
            _LOGGER.debug("Coverage geometry fetch failed: %s", err)
            _geometry_cache.set(key, {})
            return None
    geometry = parse_geometry(data) if data else None
    _geometry_cache.set(key, geometry or {})
    return (clean_id, geometry) if geometry else None


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------


class CoverageRecorder:
    """The current run's path and the robot's latest pose."""

    def __init__(
        self, hass: HomeAssistant, coordinator: DysonDataUpdateCoordinator
    ) -> None:
        self.hass = hass
        self.coordinator = coordinator
        # [id, x, y, update, bits]; bits are 0 for points driven without working.
        self.points: list[list[Any]] = []
        self.pose: dict[str, Any] | None = None
        self.started: float | None = None
        self.updated: float | None = None
        self.revision = 0
        self.geometry: dict[str, Any] | None = None
        self.geometry_clean_id: str | None = None
        self._last_id = -1
        self._device: Any = None
        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.coverage_{coordinator.serial_number}"
        )
        self._loaded = False

    async def async_start(self) -> None:
        """Load the saved run and follow the robot's messages (idempotent)."""
        if not self._loaded:
            self._loaded = True
            saved = await self._store.async_load()
            if isinstance(saved, dict) and isinstance(saved.get("points"), list):
                self.points = saved["points"][-MAX_POINTS:]
                self.started = saved.get("started")
                self.updated = saved.get("updated")
                self._last_id = self.points[-1][0] if self.points else -1
                self.revision += 1
        device = self.coordinator.device
        if device is not None and device is not self._device:
            if self._device is not None:
                self._device.remove_message_callback(self._on_message)
            device.add_message_callback(self._on_message)
            self._device = device

    @callback
    def async_stop(self) -> None:
        """Stop following messages."""
        if self._device is not None:
            self._device.remove_message_callback(self._on_message)
            self._device = None

    async def async_refresh_geometry(self) -> bool:
        """Refresh the map geometry; True when it changed."""
        result = await async_fetch_geometry(self.coordinator)
        if result is None or result[0] == self.geometry_clean_id:
            return False
        self.geometry_clean_id, self.geometry = result
        return True

    def _on_message(self, topic: str, data: dict[str, Any]) -> None:
        """MQTT thread: hand the message to the event loop."""
        self.hass.loop.call_soon_threadsafe(self.ingest, data)

    @callback
    def ingest(self, data: dict[str, Any]) -> None:
        """Record path points and pose from one robot message."""
        if not isinstance(data, dict):
            return
        method = data.get("method")
        if method == "event.startClean.post":
            self.reset()
            return
        if method == "prop.post":
            points = parse_cur_path((data.get("params") or {}).get("cur_path"))
            if points:
                self.add_points(points, self._current_bits())
            return
        if data.get("msg") in ("CURRENT-STATE", "STATE-CHANGE"):
            # A state message only moves the marker: it can repeat an old
            # point (for example the last one of the previous run).
            point = parse_global_position(data.get("globalPosition"))
            if point is not None:
                self._set_pose(point)

    def _current_bits(self) -> int:
        device = self.coordinator.device
        action = getattr(device, "robot_full_clean_action", None)
        return ACTION_BITS.get(action, 0) if isinstance(action, str) else 0

    @callback
    def add_points(
        self, points: list[tuple[int, float, float, float, int]], bits: int
    ) -> None:
        """Append new points of the current run; a falling id starts a new run."""
        added = False
        for point_id, x, y, _angle, update in points:
            if self.points and point_id < self._last_id - RESET_GAP:
                self.reset()
            if self.points and point_id <= self._last_id:
                continue
            if not self.points:
                self.started = time.time()
            point_bits = update & 3 if update & 3 else (bits if update else 0)
            self.points.append([point_id, round(x, 3), round(y, 3), update, point_bits])
            self._last_id = point_id
            added = True
        if not added:
            return
        del self.points[:-MAX_POINTS]
        self._set_pose(points[-1])
        self.updated = time.time()
        self.revision += 1
        self._store.async_delay_save(self._data, SAVE_DELAY)

    @callback
    def reset(self) -> None:
        """Forget the previous run."""
        self.points = []
        self._last_id = -1
        self.started = None
        self.revision += 1

    def _set_pose(self, point: tuple[int, float, float, float, int]) -> None:
        _point_id, x, y, angle, _update = point
        zone = zone_at(self.geometry, x, y)
        self.pose = {
            "x": round(x, 3),
            "y": round(y, 3),
            "angle": round(angle, 3),
            "room_id": zone["id"] if zone else None,
            "room": zone["name"] if zone else None,
        }

    def _data(self) -> dict[str, Any]:
        return {"points": self.points, "started": self.started, "updated": self.updated}

    def path(self) -> tuple[str, list[tuple[float, float, int, int]]]:
        """The run to draw: the live recording, else the cloud's last path."""
        if self.points:
            return "live", [(p[1], p[2], p[0], p[4]) for p in self.points]
        cloud = (self.geometry or {}).get("clean_path") or []
        # The cloud path has no action; fall back to the update flag's bits.
        return "cloud", [
            (x, y, i, update & 3) for i, (x, y, update) in enumerate(cloud)
        ]


_RECORDERS: weakref.WeakKeyDictionary[Any, CoverageRecorder] = (
    weakref.WeakKeyDictionary()
)


def get_coverage_recorder(
    hass: HomeAssistant, coordinator: DysonDataUpdateCoordinator
) -> CoverageRecorder:
    """Return the one recorder for this robot."""
    recorder = _RECORDERS.get(coordinator)
    if recorder is None:
        recorder = _RECORDERS[coordinator] = CoverageRecorder(hass, coordinator)
    return recorder


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

PANELS = (
    ("Vacuumed", VACUUM, (30, 110, 230)),
    ("Mopped", MOP, (0, 165, 150)),
)


def _font(size: int):
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def render_coverage_png(
    geometry: dict[str, Any],
    path: list[tuple[float, float, int, int]],
    pose: dict[str, Any] | None = None,
    footer: str = "",
    target_px: int = 520,
) -> tuple[bytes, dict[str, float]] | None:
    """Draw a Vacuumed and a Mopped panel over the room outlines.

    ``path`` holds (x, y, point id, bits) in map metres. Returns the PNG and
    the approximate area covered in each panel, in square metres.
    """
    from PIL import Image, ImageDraw

    zones = geometry.get("zones") or []
    rotation = int(geometry.get("orientation") or 0) % 360
    cos_r = round(math.cos(math.radians(rotation)))
    sin_r = round(math.sin(math.radians(rotation)))

    def screen(x: float, y: float) -> tuple[float, float]:
        # Map Y points up; screen Y points down. Then turn clockwise to
        # match the app's display orientation.
        u, v = x, -y
        return (u * cos_r - v * sin_r, u * sin_r + v * cos_r)

    outline = [
        (screen(x1, y1), screen(x2, y2))
        for zone in zones
        for x1, y1, x2, y2 in zone["segments"]
    ]
    xs = [p[0] for seg in outline for p in seg]
    ys = [p[1] for seg in outline for p in seg]
    if not xs:
        return None
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y, 1.0)
    ppm = target_px / span
    margin, header = 16, 34
    width = int((max_x - min_x) * ppm) + 2 * margin
    height = int((max_y - min_y) * ppm) + 2 * margin

    def px(x: float, y: float) -> tuple[float, float]:
        sx, sy = screen(x, y)
        return ((sx - min_x) * ppm + margin, (sy - min_y) * ppm + margin)

    brush = max(2, int(BRUSH_WIDTH_M * ppm))
    title_font, label_font = _font(18), _font(12)
    panels = []
    areas: dict[str, float] = {}
    for label, bit, colour in PANELS:
        panel = Image.new("RGBA", (width, height + header), (255, 255, 255, 255))
        canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        mask = Image.new("L", (width, height), 0)
        mask_draw = ImageDraw.Draw(mask)
        # Travel path, thin and grey, so gaps in coverage read as unvisited.
        _draw_runs(draw, path, px, None, fill=(200, 200, 200, 255), width=1)
        _draw_runs(mask_draw, path, px, bit, fill=255, width=brush)
        covered = width * height - mask.histogram()[0]
        areas[label.lower()] = round(covered / (ppm * ppm), 1)
        tint = Image.new("RGBA", (width, height), colour + (255,))
        canvas.paste(tint, (0, 0), mask.point(lambda value: 150 if value else 0))
        draw = ImageDraw.Draw(canvas)
        for start, end in outline:
            draw.line(
                [
                    (
                        (start[0] - min_x) * ppm + margin,
                        (start[1] - min_y) * ppm + margin,
                    ),
                    ((end[0] - min_x) * ppm + margin, (end[1] - min_y) * ppm + margin),
                ],
                fill=(60, 60, 60, 255),
                width=2,
            )
        for zone in zones:
            if zone["label"]:
                lx, ly = px(*zone["label"])
                draw.text(
                    (lx, ly),
                    zone["name"],
                    fill=(90, 90, 90, 255),
                    font=label_font,
                    anchor="mm",
                )
        if geometry.get("dock"):
            dx, dy = px(*geometry["dock"])
            draw.ellipse([dx - 6, dy - 6, dx + 6, dy + 6], fill=(0, 190, 80, 255))
        if pose:
            rx, ry = px(pose["x"], pose["y"])
            draw.ellipse(
                [rx - 7, ry - 7, rx + 7, ry + 7],
                fill=(220, 40, 40, 255),
                outline=(255, 255, 255, 255),
                width=2,
            )
        panel.paste(canvas, (0, header))
        ImageDraw.Draw(panel).text(
            (margin, 8),
            f"{label}  ~{areas[label.lower()]:.1f} sq m",
            fill=colour + (255,),
            font=title_font,
        )
        panels.append(panel)

    gap, footer_h = 10, 24 if footer else 0
    out = Image.new(
        "RGB",
        (width * len(panels) + gap * (len(panels) - 1), height + header + footer_h),
        (255, 255, 255),
    )
    for i, panel in enumerate(panels):
        out.paste(panel, (i * (width + gap), 0))
    if footer:
        ImageDraw.Draw(out).text(
            (margin, height + header + 4), footer, fill=(110, 110, 110), font=label_font
        )
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), areas


def _draw_runs(draw, path, px, bit, *, fill, width) -> None:
    """Join consecutive points into lines; ``bit`` None draws every point."""
    run: list[tuple[float, float]] = []
    previous = None
    for x, y, point_id, bits in path:
        keep = bit is None or bits & bit
        joined = (
            previous is not None
            and keep
            and point_id - previous[2] <= 3
            and math.hypot(x - previous[0], y - previous[1]) <= MAX_JOIN_M
        )
        if not joined:
            _flush(draw, run, fill, width)
            run = []
        if keep:
            run.append(px(x, y))
        previous = (x, y, point_id) if keep else None
    _flush(draw, run, fill, width)


def _flush(draw, run, fill, width) -> None:
    if len(run) > 1:
        draw.line(run, fill=fill, width=width, joint="curve")
    if run and width > 2:
        r = width / 2
        for x, y in (run[0], run[-1]):
            draw.ellipse([x - r, y - r, x + r, y + r], fill=fill)
