"""Tests for the image platform (image.py).

Covers:
- async_setup_entry: BLE skip, non-robot skip, no-token skip, full setup
- _fetch_persist_map: cache hit, null client, API error, fresh fetch
- _apply_orientation: no rotation, 90-degree rotation
- _palette_from_floor_plan: white/black/gray pixel recolouring
- _render_dust_map_png: no Pillow, bad data, size mismatch, no floor plan,
  with floor plan, compositing with offset, fallback centering, rotation
- _render_presentation_png: no Pillow, bad PNG, valid PNG, rotation
- DysonDustMapImage: init attrs, _build scenarios, async_image, async_update
- DysonFloorPlanImage: init attrs, _build scenarios, async_image, async_update
"""

from __future__ import annotations

import base64
import builtins
import io
import zlib
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from custom_components.hass_dyson import image as image_module
from custom_components.hass_dyson.const import DEVICE_CATEGORY_ROBOT, DOMAIN
from custom_components.hass_dyson.image import (
    DysonDustMapImage,
    DysonFloorPlanImage,
    _apply_orientation,
    _palette_from_floor_plan,
    _render_dust_map_png,
    _render_presentation_png,
)

# ---------------------------------------------------------------------------
# Shared test-data factories
# ---------------------------------------------------------------------------


def _make_png(width: int = 6, height: int = 6) -> bytes:
    """Create a small RGBA PNG containing white, black, and gray pixels."""
    img = Image.new("RGBA", (width, height))
    px = img.load()
    for y in range(height):
        for x in range(width):
            if x == 0:
                px[x, y] = (255, 255, 255, 255)  # white
            elif x == 1:
                px[x, y] = (0, 0, 0, 255)  # black
            else:
                px[x, y] = (128, 128, 128, 255)  # gray
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_dust_map_dict(
    width: int = 4,
    height: int = 4,
    scale: int = 255,
    all_zero: bool = False,
) -> dict:
    """Return a well-formed dust_map dict for _render_dust_map_png."""
    if all_zero:
        raw = bytes(width * height)
    else:
        raw = bytes([i % 256 for i in range(width * height)])
    b64 = base64.b64encode(zlib.compress(raw)).decode()
    return {
        "width": width,
        "height": height,
        "resolution": 20,
        "dustData": [{"data": b64, "scaleFactor": scale}],
    }


def _make_clean_record(
    *,
    clean_id: str = "clean-001",
    pmap_id: str | None = "pmap-1",
    has_dust_map: bool = True,
    position: tuple[float, float] | None = (100.0, 200.0),
    footprint_b64: str | None = None,
) -> MagicMock:
    """Build a mock CleanRecord."""
    record = MagicMock()
    record.clean_id = clean_id
    record.persistent_map_id = pmap_id

    if has_dust_map:
        dust_map = MagicMock()
        dust_map.width = 4
        dust_map.height = 4
        dust_map.resolution = 20
        raw = bytes(range(16))
        dust_map.dust_data = [
            {
                "data": base64.b64encode(zlib.compress(raw)).decode(),
                "scaleFactor": 255,
            }
        ]
        record.dust_map = dust_map
    else:
        record.dust_map = None

    if position:
        pos = MagicMock()
        pos.x, pos.y = position
        record.clean_map_position = pos
    else:
        record.clean_map_position = None

    fp = MagicMock()
    fp.data = footprint_b64
    record.cleaned_footprint = fp

    return record


def _make_persistent_map(
    *,
    pmap_id: str = "pmap-1",
    presentation_data: str | None = None,
    orientation: int = 0,
    offset_x: float | None = 10.0,
    offset_y: float | None = 20.0,
) -> MagicMock:
    """Build a mock PersistentMap."""
    pmap = MagicMock()
    pmap.id = pmap_id
    pmap.presentation_map_data = presentation_data
    pmap.display_orientation = orientation
    pmap.offset_x = offset_x
    pmap.offset_y = offset_y
    return pmap


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_coordinator():
    """Mock DysonDataUpdateCoordinator for image tests."""
    coord = MagicMock()
    coord.serial_number = "VS9-GB-HJA0000A"
    coord.device_category = [DEVICE_CATEGORY_ROBOT]
    coord.config_entry = MagicMock()
    coord.config_entry.data = {"auth_token": "tok-abc"}
    coord.config_entry.entry_id = "entry-1"
    return coord


@pytest.fixture
def mock_hass():
    """Mock HomeAssistant instance."""
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    return hass


@pytest.fixture
def mock_config_entry():
    """Mock ConfigEntry."""
    entry = MagicMock()
    entry.entry_id = "entry-1"
    return entry


# ---------------------------------------------------------------------------
# Tests: async_setup_entry
# ---------------------------------------------------------------------------


class TestAsyncSetupEntry:
    """Test image platform setup entry."""

    @pytest.mark.asyncio
    async def test_ble_device_skipped(self, mock_hass, mock_config_entry):
        """BLE devices skip image platform setup."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = {"is_ble": True}
        add_entities = MagicMock()
        await image_module.async_setup_entry(mock_hass, mock_config_entry, add_entities)
        add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_robot_device_skipped(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Non-robot devices skip image platform setup."""
        mock_coordinator.device_category = ["fan"]
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator
        add_entities = MagicMock()
        await image_module.async_setup_entry(mock_hass, mock_config_entry, add_entities)
        add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_robot_without_token_skipped(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Robot device without auth_token skips image platform setup."""
        mock_coordinator.config_entry.data = {}
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator
        add_entities = MagicMock()
        await image_module.async_setup_entry(mock_hass, mock_config_entry, add_entities)
        add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_device_category_skipped(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """None device_category skips image platform setup."""
        mock_coordinator.device_category = None
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator
        add_entities = MagicMock()
        await image_module.async_setup_entry(mock_hass, mock_config_entry, add_entities)
        add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_robot_with_token_creates_entities(
        self, mock_hass, mock_config_entry, mock_coordinator
    ):
        """Robot with auth_token creates DysonDustMapImage + DysonFloorPlanImage."""
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator
        add_entities = MagicMock()
        with (
            patch(
                "custom_components.hass_dyson.image.ImageEntity.__init__",
                return_value=None,
            ),
            patch(
                "custom_components.hass_dyson.image.DysonEntity.__init__",
                return_value=None,
            ),
        ):
            await image_module.async_setup_entry(
                mock_hass, mock_config_entry, add_entities
            )
        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        assert len(entities) == 2
        assert isinstance(entities[0], DysonDustMapImage)
        assert isinstance(entities[1], DysonFloorPlanImage)
        # Second arg to add_entities should be True (update before add)
        assert add_entities.call_args[0][1] is True


# ---------------------------------------------------------------------------
# Tests: _fetch_persist_map
# ---------------------------------------------------------------------------


class TestFetchPersistMap:
    """Test the _fetch_persist_map cloud helper."""

    @pytest.mark.asyncio
    async def test_returns_fresh_cached_value(self, mock_coordinator):
        """Returns immediately when a fresh cached entry exists."""
        from custom_components.hass_dyson.coordinator import TTLCache

        fresh_cache = TTLCache(3600)
        fake_pmap = MagicMock()
        fresh_cache.set("VS9-GB-HJA0000A:pmap-99", fake_pmap)

        with patch.object(image_module, "_persist_map_cache", fresh_cache):
            result = await image_module._fetch_persist_map(mock_coordinator, "pmap-99")

        assert result is fake_pmap

    @pytest.mark.asyncio
    async def test_returns_stale_cache_when_no_client(self, mock_coordinator):
        """Returns stale cache entry when cloud client yields None."""
        from custom_components.hass_dyson.coordinator import TTLCache

        fresh_cache = TTLCache(3600)
        stale_pmap = MagicMock()
        # Manually inject an expired entry: timestamp = 0 (always expired)
        fresh_cache._store["VS9-GB-HJA0000A:pmap-99"] = (0.0, stale_pmap)

        @asynccontextmanager
        async def null_client():
            yield None

        mock_coordinator.async_cloud_client = null_client

        with patch.object(image_module, "_persist_map_cache", fresh_cache):
            result = await image_module._fetch_persist_map(mock_coordinator, "pmap-99")

        assert result is stale_pmap

    @pytest.mark.asyncio
    async def test_api_error_returns_stale_cache(self, mock_coordinator):
        """Returns stale cache on DysonAPIError; returns None if no stale entry."""
        from libdyson_rest.exceptions import DysonAPIError

        from custom_components.hass_dyson.coordinator import TTLCache

        fresh_cache = TTLCache(3600)
        # No stale entry → get_stale returns None

        fake_client = AsyncMock()
        fake_client.get_persistent_map = AsyncMock(side_effect=DysonAPIError("boom"))

        @asynccontextmanager
        async def make_client():
            yield fake_client

        mock_coordinator.async_cloud_client = make_client

        with patch.object(image_module, "_persist_map_cache", fresh_cache):
            result = await image_module._fetch_persist_map(mock_coordinator, "pmap-99")

        assert result is None

    @pytest.mark.asyncio
    async def test_auth_error_returns_stale_cache(self, mock_coordinator):
        """Returns stale cache on DysonAuthError."""
        from libdyson_rest.exceptions import DysonAuthError

        from custom_components.hass_dyson.coordinator import TTLCache

        fresh_cache = TTLCache(3600)
        stale_pmap = MagicMock()
        fresh_cache._store["VS9-GB-HJA0000A:pmap-99"] = (0.0, stale_pmap)

        fake_client = AsyncMock()
        fake_client.get_persistent_map = AsyncMock(
            side_effect=DysonAuthError("unauthorized")
        )

        @asynccontextmanager
        async def make_client():
            yield fake_client

        mock_coordinator.async_cloud_client = make_client

        with patch.object(image_module, "_persist_map_cache", fresh_cache):
            result = await image_module._fetch_persist_map(mock_coordinator, "pmap-99")

        assert result is stale_pmap

    @pytest.mark.asyncio
    async def test_fetches_and_caches_new_entry(self, mock_coordinator):
        """Successfully fetched persistent map is stored in cache and returned."""
        from custom_components.hass_dyson.coordinator import TTLCache

        fresh_cache = TTLCache(3600)
        pmap = MagicMock()

        fake_client = AsyncMock()
        fake_client.get_persistent_map = AsyncMock(return_value=pmap)

        @asynccontextmanager
        async def make_client():
            yield fake_client

        mock_coordinator.async_cloud_client = make_client

        with patch.object(image_module, "_persist_map_cache", fresh_cache):
            result = await image_module._fetch_persist_map(mock_coordinator, "pmap-99")

        assert result is pmap
        assert fresh_cache.get("VS9-GB-HJA0000A:pmap-99") is pmap


# ---------------------------------------------------------------------------
# Tests: _apply_orientation
# ---------------------------------------------------------------------------


class TestApplyOrientation:
    """Test the _apply_orientation helper."""

    def test_no_rotation_preserves_dimensions(self):
        """Zero rotation only applies Y-flip; dimensions are unchanged."""
        img = Image.new("RGBA", (8, 4), (255, 0, 0, 255))
        result = _apply_orientation(img, 0)
        assert result.size == (8, 4)

    def test_90_degree_rotation_swaps_dimensions(self):
        """90-degree rotation with expand=True swaps width and height."""
        img = Image.new("RGBA", (8, 4), (0, 255, 0, 255))
        result = _apply_orientation(img, 90)
        assert result.size == (4, 8)

    def test_180_degree_rotation_preserves_dimensions(self):
        """180-degree rotation keeps the same width/height."""
        img = Image.new("RGBA", (6, 3), (0, 0, 255, 255))
        result = _apply_orientation(img, 180)
        assert result.size == (6, 3)

    def test_zero_rotation_flips_y_axis(self):
        """Y-axis flip is always applied; red top row should move to bottom."""
        img = Image.new("RGBA", (4, 4), (255, 255, 255, 255))
        px = img.load()
        for x in range(4):
            px[x, 0] = (255, 0, 0, 255)  # red row at top (y=0)
        result = _apply_orientation(img, 0)
        rpx = result.load()
        # After Y-flip, the red row should be at the bottom (y=3)
        for x in range(4):
            assert rpx[x, 3] == (255, 0, 0, 255)
            assert rpx[x, 0] == (255, 255, 255, 255)


# ---------------------------------------------------------------------------
# Tests: _palette_from_floor_plan
# ---------------------------------------------------------------------------


class TestPaletteFromFloorPlan:
    """Test the _palette_from_floor_plan recolouring helper."""

    def test_recolours_white_black_gray_pixels(self):
        """White → dark, black → cream, gray → near-white."""
        img = Image.new("RGBA", (3, 1))
        px = img.load()
        px[0, 0] = (255, 255, 255, 255)  # white (boundary)
        px[1, 0] = (0, 0, 0, 255)  # black (zone interior)
        px[2, 0] = (128, 128, 128, 255)  # gray (outside)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result = _palette_from_floor_plan(buf.getvalue())

        rpx = result.load()
        assert rpx[0, 0] == (60, 60, 90, 255)  # white → dark blue-grey
        assert rpx[1, 0] == (250, 248, 240, 255)  # black → cream
        assert rpx[2, 0] == (235, 235, 235, 255)  # gray → near-white

    def test_returns_rgba_image(self):
        """Returned image is RGBA mode."""
        buf = io.BytesIO()
        Image.new("RGBA", (2, 2), (100, 100, 100, 255)).save(buf, format="PNG")
        result = _palette_from_floor_plan(buf.getvalue())
        assert result.mode == "RGBA"


# ---------------------------------------------------------------------------
# Tests: _render_dust_map_png
# ---------------------------------------------------------------------------


class TestRenderDustMapPng:
    """Test the dust-map PNG renderer."""

    def test_no_pillow_returns_none(self):
        """Returns None when Pillow cannot be imported."""
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "PIL" in name:
                raise ImportError(f"mocked: {name}")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            result = _render_dust_map_png(_make_dust_map_dict(), None, None)
        assert result is None

    def test_missing_dust_data_key_returns_none(self):
        """Dust map dict without 'dustData' key returns None."""
        result = _render_dust_map_png({"width": 4, "height": 4}, None, None)
        assert result is None

    def test_empty_dust_data_list_returns_none(self):
        """Empty dustData list returns None (IndexError)."""
        dust_map = {"width": 4, "height": 4, "dustData": []}
        result = _render_dust_map_png(dust_map, None, None)
        assert result is None

    def test_invalid_base64_returns_none(self):
        """Invalid base64 in dustData entry returns None."""
        dust_map = {
            "width": 4,
            "height": 4,
            "dustData": [{"data": "===INVALID===", "scaleFactor": 255}],
        }
        result = _render_dust_map_png(dust_map, None, None)
        assert result is None

    def test_size_mismatch_returns_none(self):
        """Too few raw bytes after decompression returns None."""
        short_raw = bytes(2)  # 2 bytes for a 4×4=16 pixel map
        b64 = base64.b64encode(zlib.compress(short_raw)).decode()
        dust_map = {
            "width": 4,
            "height": 4,
            "dustData": [{"data": b64, "scaleFactor": 255}],
        }
        result = _render_dust_map_png(dust_map, None, None)
        assert result is None

    def test_all_zero_pixels_returns_transparent_png(self):
        """All-zero dust data creates a fully transparent PNG."""
        result = _render_dust_map_png(_make_dust_map_dict(all_zero=True), None, None)
        assert result is not None
        assert result[:4] == b"\x89PNG"

    def test_valid_dust_map_no_floor_plan(self):
        """Valid dust map without floor plan produces a PNG."""
        result = _render_dust_map_png(_make_dust_map_dict(), None, None)
        assert result is not None
        assert result[:4] == b"\x89PNG"

    def test_with_rotation(self):
        """Rotation argument is applied without error."""
        result = _render_dust_map_png(
            _make_dust_map_dict(), None, None, rotation_deg=90
        )
        assert result is not None
        assert result[:4] == b"\x89PNG"

    def test_scale_factor_zero_defaults_to_255(self):
        """scaleFactor=0 is treated as 255 to avoid divide-by-zero."""
        result = _render_dust_map_png(_make_dust_map_dict(scale=0), None, None)
        assert result is not None
        assert result[:4] == b"\x89PNG"

    def test_with_floor_plan_and_position(self):
        """Dust map is composited onto floor plan when position is known."""
        pmap_png = _make_png(32, 32)
        result = _render_dust_map_png(
            _make_dust_map_dict(),
            None,
            pmap_png,
            rotation_deg=0,
            map_offset_mm=(0.0, 0.0),
            clean_position_mm=(40.0, 40.0),  # (40-0)/20 = 2px offset
            map_resolution_mm_per_px=20,
        )
        assert result is not None
        assert result[:4] == b"\x89PNG"

    def test_with_floor_plan_fallback_centering(self):
        """Without position info the dust map is centred on the floor plan."""
        pmap_png = _make_png(32, 32)
        result = _render_dust_map_png(
            _make_dust_map_dict(),
            None,
            pmap_png,
        )
        assert result is not None
        assert result[:4] == b"\x89PNG"

    def test_bad_floor_plan_falls_back_to_dust_only(self):
        """Bad floor-plan bytes fall back to rendering the dust map alone."""
        result = _render_dust_map_png(_make_dust_map_dict(), None, b"not-a-png")
        assert result is not None
        assert result[:4] == b"\x89PNG"

    def test_with_floor_plan_and_rotation(self):
        """Floor plan composite with rotation produces a PNG."""
        pmap_png = _make_png(32, 32)
        result = _render_dust_map_png(
            _make_dust_map_dict(),
            None,
            pmap_png,
            rotation_deg=90,
            map_offset_mm=(0.0, 0.0),
            clean_position_mm=(20.0, 20.0),
            map_resolution_mm_per_px=20,
        )
        assert result is not None
        assert result[:4] == b"\x89PNG"


# ---------------------------------------------------------------------------
# Tests: _render_presentation_png
# ---------------------------------------------------------------------------


class TestRenderPresentationPng:
    """Test the floor-plan PNG renderer."""

    def test_no_pillow_returns_none(self):
        """Returns None when Pillow cannot be imported."""
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "PIL" in name:
                raise ImportError(f"mocked: {name}")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            result = _render_presentation_png(b"any")
        assert result is None

    def test_invalid_png_returns_none(self):
        """Invalid PNG bytes return None (exception handled gracefully)."""
        result = _render_presentation_png(b"not-a-png-at-all")
        assert result is None

    def test_valid_png_returns_bytes(self):
        """Valid floor-plan PNG is recoloured and returned as PNG bytes."""
        result = _render_presentation_png(_make_png())
        assert result is not None
        assert result[:4] == b"\x89PNG"

    def test_valid_png_with_rotation(self):
        """Rotation is applied to the rendered output."""
        result = _render_presentation_png(_make_png(12, 6), rotation_deg=90)
        assert result is not None
        assert result[:4] == b"\x89PNG"

    def test_small_image_is_upscaled(self):
        """Images smaller than 600px on any axis are scaled up."""
        small_png = _make_png(4, 4)
        result = _render_presentation_png(small_png)
        assert result is not None
        # Verify the result is larger than the original
        result_img = Image.open(io.BytesIO(result))
        assert result_img.size[0] >= 4


# ---------------------------------------------------------------------------
# Tests: DysonDustMapImage
# ---------------------------------------------------------------------------


class TestDysonDustMapImage:
    """Test the DysonDustMapImage entity."""

    _PATCH_IMAGE_INIT = patch(
        "custom_components.hass_dyson.image.ImageEntity.__init__",
        return_value=None,
    )
    _PATCH_DYSON_INIT = patch(
        "custom_components.hass_dyson.image.DysonEntity.__init__",
        return_value=None,
    )

    def _make_entity(self, coordinator) -> DysonDustMapImage:
        with self._PATCH_IMAGE_INIT, self._PATCH_DYSON_INIT:
            entity = DysonDustMapImage(MagicMock(), coordinator)
        entity.coordinator = coordinator
        return entity

    def test_init_sets_unique_id(self, mock_coordinator):
        """__init__ sets unique_id from serial number."""
        entity = self._make_entity(mock_coordinator)
        assert entity._attr_unique_id == "VS9-GB-HJA0000A_dust_map"

    def test_init_sets_name_and_icon(self, mock_coordinator):
        """__init__ sets name and icon."""
        entity = self._make_entity(mock_coordinator)
        assert entity._attr_name == "Dust Map"
        assert entity._attr_icon == "mdi:map-search"

    def test_init_content_type_and_poll(self, mock_coordinator):
        """Content type is image/png and polling is enabled."""
        entity = self._make_entity(mock_coordinator)
        assert entity._attr_content_type == "image/png"
        assert entity._attr_should_poll is True

    def test_init_cache_attrs_are_none(self, mock_coordinator):
        """Cache attributes start as None."""
        entity = self._make_entity(mock_coordinator)
        assert entity._cached_clean_id is None
        assert entity._cached_png is None

    @pytest.mark.asyncio
    async def test_build_returns_none_when_no_cleans(self, mock_coordinator):
        """_build returns None when fetch_clean_maps returns empty list."""
        entity = self._make_entity(mock_coordinator)
        with patch(
            "custom_components.hass_dyson.image.fetch_clean_maps",
            AsyncMock(return_value=[]),
        ):
            result = await entity._build()
        assert result is None

    @pytest.mark.asyncio
    async def test_build_returns_none_when_no_dust_map(self, mock_coordinator):
        """_build returns None when the latest clean has no dust_map."""
        entity = self._make_entity(mock_coordinator)
        record = _make_clean_record(has_dust_map=False)
        with patch(
            "custom_components.hass_dyson.image.fetch_clean_maps",
            AsyncMock(return_value=[record]),
        ):
            result = await entity._build()
        assert result is None

    @pytest.mark.asyncio
    async def test_build_uses_cached_png_for_same_clean_id(self, mock_coordinator):
        """_build returns the cached PNG when the clean_id has not changed."""
        entity = self._make_entity(mock_coordinator)
        entity._cached_clean_id = "clean-001"
        cached = b"\x89PNG fake"
        entity._cached_png = cached

        record = _make_clean_record(clean_id="clean-001")
        with patch(
            "custom_components.hass_dyson.image.fetch_clean_maps",
            AsyncMock(return_value=[record]),
        ):
            result = await entity._build()
        assert result is cached

    @pytest.mark.asyncio
    async def test_build_renders_without_persistent_map(self, mock_coordinator):
        """_build renders the dust map when no persistent map is available."""
        entity = self._make_entity(mock_coordinator)
        record = _make_clean_record(pmap_id=None, position=None)
        with (
            patch(
                "custom_components.hass_dyson.image.fetch_clean_maps",
                AsyncMock(return_value=[record]),
            ),
            patch(
                "custom_components.hass_dyson.image._render_dust_map_png",
                return_value=b"\x89PNG rendered",
            ),
        ):
            result = await entity._build()
        assert result == b"\x89PNG rendered"
        assert entity._cached_clean_id == "clean-001"
        assert entity._cached_png == b"\x89PNG rendered"

    @pytest.mark.asyncio
    async def test_build_updates_image_last_updated_on_success(self, mock_coordinator):
        """_build sets _attr_image_last_updated when PNG is produced."""
        entity = self._make_entity(mock_coordinator)
        record = _make_clean_record(pmap_id=None, position=None)
        with (
            patch(
                "custom_components.hass_dyson.image.fetch_clean_maps",
                AsyncMock(return_value=[record]),
            ),
            patch(
                "custom_components.hass_dyson.image._render_dust_map_png",
                return_value=b"\x89PNG ok",
            ),
        ):
            await entity._build()
        assert hasattr(entity, "_attr_image_last_updated")

    @pytest.mark.asyncio
    async def test_build_does_not_cache_when_render_returns_none(
        self, mock_coordinator
    ):
        """_build does not update cache when the renderer returns None."""
        entity = self._make_entity(mock_coordinator)
        record = _make_clean_record(pmap_id=None, position=None)
        with (
            patch(
                "custom_components.hass_dyson.image.fetch_clean_maps",
                AsyncMock(return_value=[record]),
            ),
            patch(
                "custom_components.hass_dyson.image._render_dust_map_png",
                return_value=None,
            ),
        ):
            result = await entity._build()
        assert result is None
        assert entity._cached_clean_id is None

    @pytest.mark.asyncio
    async def test_build_with_persistent_map_composites(self, mock_coordinator):
        """_build composites dust map onto the floor plan when pmap is available."""
        entity = self._make_entity(mock_coordinator)
        record = _make_clean_record(pmap_id="pmap-1")
        pmap = _make_persistent_map(
            presentation_data=base64.b64encode(_make_png()).decode()
        )
        with (
            patch(
                "custom_components.hass_dyson.image.fetch_clean_maps",
                AsyncMock(return_value=[record]),
            ),
            patch(
                "custom_components.hass_dyson.image._fetch_persist_map",
                AsyncMock(return_value=pmap),
            ),
            patch(
                "custom_components.hass_dyson.image._render_dust_map_png",
                return_value=b"\x89PNG composite",
            ),
        ):
            result = await entity._build()
        assert result == b"\x89PNG composite"

    @pytest.mark.asyncio
    async def test_build_with_footprint_data(self, mock_coordinator):
        """_build decodes cleaned_footprint.data when it is present."""
        entity = self._make_entity(mock_coordinator)
        fp_b64 = base64.b64encode(b"fake-footprint").decode()
        record = _make_clean_record(pmap_id=None, position=None, footprint_b64=fp_b64)
        render_call_args = {}
        with (
            patch(
                "custom_components.hass_dyson.image.fetch_clean_maps",
                AsyncMock(return_value=[record]),
            ),
            patch(
                "custom_components.hass_dyson.image._render_dust_map_png",
                side_effect=lambda dm, fp, pp, *a, **kw: (
                    render_call_args.update({"fp": fp}) or b"\x89PNG"
                ),
            ),
        ):
            await entity._build()
        assert render_call_args.get("fp") == b"fake-footprint"

    @pytest.mark.asyncio
    async def test_build_with_invalid_footprint_b64(self, mock_coordinator):
        """_build handles a footprint whose base64 raises ValueError gracefully.

        When the footprint b64 decode fails, cleaned_fp_png stays None and
        _render_dust_map_png is still called (with None as the footprint arg).
        """
        entity = self._make_entity(mock_coordinator)
        record = _make_clean_record(pmap_id=None, position=None, footprint_b64="bad!")
        with (
            patch(
                "custom_components.hass_dyson.image.fetch_clean_maps",
                AsyncMock(return_value=[record]),
            ),
            # Make the footprint b64 decode raise ValueError.
            patch(
                "custom_components.hass_dyson.image.base64.b64decode",
                side_effect=ValueError("bad padding"),
            ),
            patch(
                "custom_components.hass_dyson.image._render_dust_map_png",
                return_value=b"\x89PNG",
            ) as mock_render,
        ):
            result = await entity._build()
        assert result == b"\x89PNG"
        # cleaned_footprint_png (second positional arg) must be None
        assert mock_render.call_args[0][1] is None

    @pytest.mark.asyncio
    async def test_build_with_invalid_pmap_presentation_b64(self, mock_coordinator):
        """_build handles invalid pmap.presentation_map_data base64."""
        entity = self._make_entity(mock_coordinator)
        record = _make_clean_record(pmap_id="pmap-1")
        pmap = _make_persistent_map(presentation_data="!!!INVALID_B64!!!")
        with (
            patch(
                "custom_components.hass_dyson.image.fetch_clean_maps",
                AsyncMock(return_value=[record]),
            ),
            patch(
                "custom_components.hass_dyson.image._fetch_persist_map",
                AsyncMock(return_value=pmap),
            ),
            patch(
                "custom_components.hass_dyson.image._render_dust_map_png",
                return_value=b"\x89PNG",
            ),
        ):
            result = await entity._build()
        # Should still render (presentation_png will be None but render proceeds)
        assert result == b"\x89PNG"

    @pytest.mark.asyncio
    async def test_async_image_delegates_to_build(self, mock_coordinator):
        """async_image calls and returns result from _build."""
        entity = self._make_entity(mock_coordinator)
        with patch.object(entity, "_build", AsyncMock(return_value=b"\x89PNG")):
            result = await entity.async_image()
        assert result == b"\x89PNG"

    @pytest.mark.asyncio
    async def test_async_update_calls_build(self, mock_coordinator):
        """async_update triggers _build for HA polling cycle."""
        entity = self._make_entity(mock_coordinator)
        with patch.object(entity, "_build", AsyncMock(return_value=None)) as mock_build:
            await entity.async_update()
        mock_build.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: DysonFloorPlanImage
# ---------------------------------------------------------------------------


class TestDysonFloorPlanImage:
    """Test the DysonFloorPlanImage entity."""

    _PATCH_IMAGE_INIT = patch(
        "custom_components.hass_dyson.image.ImageEntity.__init__",
        return_value=None,
    )
    _PATCH_DYSON_INIT = patch(
        "custom_components.hass_dyson.image.DysonEntity.__init__",
        return_value=None,
    )

    def _make_entity(self, coordinator) -> DysonFloorPlanImage:
        with self._PATCH_IMAGE_INIT, self._PATCH_DYSON_INIT:
            entity = DysonFloorPlanImage(MagicMock(), coordinator)
        entity.coordinator = coordinator
        return entity

    def test_init_sets_unique_id(self, mock_coordinator):
        """__init__ sets unique_id from serial number."""
        entity = self._make_entity(mock_coordinator)
        assert entity._attr_unique_id == "VS9-GB-HJA0000A_floor_plan"

    def test_init_sets_name_and_icon(self, mock_coordinator):
        """__init__ sets name and icon."""
        entity = self._make_entity(mock_coordinator)
        assert entity._attr_name == "Floor Plan"
        assert entity._attr_icon == "mdi:floor-plan"

    def test_init_content_type_and_poll(self, mock_coordinator):
        """Content type is image/png and polling is enabled."""
        entity = self._make_entity(mock_coordinator)
        assert entity._attr_content_type == "image/png"
        assert entity._attr_should_poll is True

    def test_init_cache_attrs_are_none(self, mock_coordinator):
        """Cache attributes start as None."""
        entity = self._make_entity(mock_coordinator)
        assert entity._cached_pmap_id is None
        assert entity._cached_png is None

    @pytest.mark.asyncio
    async def test_build_returns_none_when_no_cleans(self, mock_coordinator):
        """_build returns None when fetch_clean_maps returns empty list."""
        entity = self._make_entity(mock_coordinator)
        with patch(
            "custom_components.hass_dyson.image.fetch_clean_maps",
            AsyncMock(return_value=[]),
        ):
            result = await entity._build()
        assert result is None

    @pytest.mark.asyncio
    async def test_build_returns_none_when_no_pmap_id(self, mock_coordinator):
        """_build returns None when the latest clean has no persistent_map_id."""
        entity = self._make_entity(mock_coordinator)
        record = _make_clean_record(pmap_id=None)
        with patch(
            "custom_components.hass_dyson.image.fetch_clean_maps",
            AsyncMock(return_value=[record]),
        ):
            result = await entity._build()
        assert result is None

    @pytest.mark.asyncio
    async def test_build_uses_cached_png_for_same_pmap_id(self, mock_coordinator):
        """_build returns the cached PNG when pmap_id has not changed."""
        entity = self._make_entity(mock_coordinator)
        entity._cached_pmap_id = "pmap-1"
        cached = b"\x89PNG cached"
        entity._cached_png = cached

        record = _make_clean_record(pmap_id="pmap-1")
        with patch(
            "custom_components.hass_dyson.image.fetch_clean_maps",
            AsyncMock(return_value=[record]),
        ):
            result = await entity._build()
        assert result is cached

    @pytest.mark.asyncio
    async def test_build_returns_none_when_fetch_persist_map_fails(
        self, mock_coordinator
    ):
        """_build returns None when _fetch_persist_map returns None."""
        entity = self._make_entity(mock_coordinator)
        record = _make_clean_record(pmap_id="pmap-2")
        with (
            patch(
                "custom_components.hass_dyson.image.fetch_clean_maps",
                AsyncMock(return_value=[record]),
            ),
            patch(
                "custom_components.hass_dyson.image._fetch_persist_map",
                AsyncMock(return_value=None),
            ),
        ):
            result = await entity._build()
        assert result is None

    @pytest.mark.asyncio
    async def test_build_returns_none_when_no_presentation_data(self, mock_coordinator):
        """_build returns None when persistent map has no presentation data."""
        entity = self._make_entity(mock_coordinator)
        record = _make_clean_record(pmap_id="pmap-2")
        pmap = _make_persistent_map(presentation_data=None)
        with (
            patch(
                "custom_components.hass_dyson.image.fetch_clean_maps",
                AsyncMock(return_value=[record]),
            ),
            patch(
                "custom_components.hass_dyson.image._fetch_persist_map",
                AsyncMock(return_value=pmap),
            ),
        ):
            result = await entity._build()
        assert result is None

    @pytest.mark.asyncio
    async def test_build_returns_none_for_invalid_base64(self, mock_coordinator):
        """_build returns None when presentation_map_data is invalid base64."""
        entity = self._make_entity(mock_coordinator)
        record = _make_clean_record(pmap_id="pmap-2")
        pmap = _make_persistent_map(presentation_data="!!!INVALID!!!")
        with (
            patch(
                "custom_components.hass_dyson.image.fetch_clean_maps",
                AsyncMock(return_value=[record]),
            ),
            patch(
                "custom_components.hass_dyson.image._fetch_persist_map",
                AsyncMock(return_value=pmap),
            ),
        ):
            with patch(
                "custom_components.hass_dyson.image.base64.b64decode",
                side_effect=ValueError("bad padding"),
            ):
                result = await entity._build()
        assert result is None

    @pytest.mark.asyncio
    async def test_build_renders_floor_plan_and_caches(self, mock_coordinator):
        """_build renders floor plan, caches result, and returns PNG bytes."""
        entity = self._make_entity(mock_coordinator)
        png_b64 = base64.b64encode(_make_png()).decode()
        record = _make_clean_record(pmap_id="pmap-2")
        pmap = _make_persistent_map(presentation_data=png_b64)
        with (
            patch(
                "custom_components.hass_dyson.image.fetch_clean_maps",
                AsyncMock(return_value=[record]),
            ),
            patch(
                "custom_components.hass_dyson.image._fetch_persist_map",
                AsyncMock(return_value=pmap),
            ),
            patch(
                "custom_components.hass_dyson.image._render_presentation_png",
                return_value=b"\x89PNG rendered",
            ),
        ):
            result = await entity._build()
        assert result == b"\x89PNG rendered"
        assert entity._cached_pmap_id == "pmap-2"
        assert entity._cached_png == b"\x89PNG rendered"

    @pytest.mark.asyncio
    async def test_build_does_not_cache_when_render_fails(self, mock_coordinator):
        """_build does not update cache when _render_presentation_png returns None."""
        entity = self._make_entity(mock_coordinator)
        png_b64 = base64.b64encode(_make_png()).decode()
        record = _make_clean_record(pmap_id="pmap-2")
        pmap = _make_persistent_map(presentation_data=png_b64)
        with (
            patch(
                "custom_components.hass_dyson.image.fetch_clean_maps",
                AsyncMock(return_value=[record]),
            ),
            patch(
                "custom_components.hass_dyson.image._fetch_persist_map",
                AsyncMock(return_value=pmap),
            ),
            patch(
                "custom_components.hass_dyson.image._render_presentation_png",
                return_value=None,
            ),
        ):
            result = await entity._build()
        assert result is None
        assert entity._cached_pmap_id is None

    @pytest.mark.asyncio
    async def test_build_updates_image_last_updated_on_success(self, mock_coordinator):
        """_build sets _attr_image_last_updated when PNG is produced."""
        entity = self._make_entity(mock_coordinator)
        png_b64 = base64.b64encode(_make_png()).decode()
        record = _make_clean_record(pmap_id="pmap-3")
        pmap = _make_persistent_map(presentation_data=png_b64)
        with (
            patch(
                "custom_components.hass_dyson.image.fetch_clean_maps",
                AsyncMock(return_value=[record]),
            ),
            patch(
                "custom_components.hass_dyson.image._fetch_persist_map",
                AsyncMock(return_value=pmap),
            ),
            patch(
                "custom_components.hass_dyson.image._render_presentation_png",
                return_value=b"\x89PNG ok",
            ),
        ):
            await entity._build()
        assert hasattr(entity, "_attr_image_last_updated")

    @pytest.mark.asyncio
    async def test_async_image_delegates_to_build(self, mock_coordinator):
        """async_image calls and returns result from _build."""
        entity = self._make_entity(mock_coordinator)
        with patch.object(entity, "_build", AsyncMock(return_value=b"\x89PNG")):
            result = await entity.async_image()
        assert result == b"\x89PNG"

    @pytest.mark.asyncio
    async def test_async_update_calls_build(self, mock_coordinator):
        """async_update triggers _build for HA polling cycle."""
        entity = self._make_entity(mock_coordinator)
        with patch.object(entity, "_build", AsyncMock(return_value=None)) as mock_build:
            await entity.async_update()
        mock_build.assert_called_once()
