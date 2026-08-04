"""Regression tests for issue #408.

_attr_should_poll = True is inert on CoordinatorEntity subclasses: the
coordinator base overrides should_poll as a cached_property returning False,
so polling requires an explicit property override. These assert the override
is effective on every entity that relies on HA's polling cycle to refresh
its TTL-cached cloud data (DysonLastCleanSensor is the pre-existing control).
"""

from unittest.mock import MagicMock, patch

from custom_components.hass_dyson.image import DysonDustMapImage, DysonFloorPlanImage
from custom_components.hass_dyson.sensor import (
    DysonLastCleanSensor,
    DysonRecommendedCleanSensor,
)

_PATCH_IMAGE_INIT = patch(
    "homeassistant.components.image.ImageEntity.__init__", return_value=None
)
_PATCH_DYSON_INIT = patch(
    "custom_components.hass_dyson.image.DysonEntity.__init__", return_value=None
)


def _coordinator() -> MagicMock:
    coordinator = MagicMock()
    coordinator.serial_number = "VS9-GB-HJA0000A"
    coordinator.device_name = "Vis Nav"
    return coordinator


def test_last_clean_sensor_polls():
    assert DysonLastCleanSensor(_coordinator(), 0).should_poll is True


def test_recommended_clean_sensor_polls():
    assert DysonRecommendedCleanSensor(_coordinator()).should_poll is True


def test_dust_map_image_polls():
    with _PATCH_IMAGE_INIT, _PATCH_DYSON_INIT:
        entity = DysonDustMapImage(MagicMock(), _coordinator())
    assert entity.should_poll is True


def test_floor_plan_image_polls():
    with _PATCH_IMAGE_INIT, _PATCH_DYSON_INIT:
        entity = DysonFloorPlanImage(MagicMock(), _coordinator())
    assert entity.should_poll is True
