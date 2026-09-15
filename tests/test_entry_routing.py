"""Tests for the config-entry routing table.

The bug this module exists to prevent: a BLE vacuum entry reaching a platform
that had no vacuum branch fell through to the MQTT path and raised
``'dict' object has no attribute ...`` at runtime, while entry setup still
reported success.  The routing table makes an unimplemented platform a no-op.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hass_dyson.const import DOMAIN
from custom_components.hass_dyson.entry_routing import (
    _BLE_PLATFORM_MODULES,
    BLE_PLATFORMS,
    DEVICE_KIND_BLE_LIGHT,
    DEVICE_KIND_BLE_VACUUM,
    DEVICE_KIND_MQTT,
    async_ble_coordinator,
    async_entry_kind,
    async_route_ble_platform,
)

ENTRY_ID = "entry-1"


def _hass(entry_data):
    hass = MagicMock()
    hass.data = {DOMAIN: {ENTRY_ID: entry_data}}
    return hass


def _entry():
    entry = MagicMock()
    entry.entry_id = ENTRY_ID
    return entry


class TestEntryKind:
    """Classifying an entry from what setup stored for it."""

    def test_vacuum(self):
        hass = _hass({"is_ble_vacuum": True, "ble_vacuum_coordinator": "c"})
        assert async_entry_kind(hass, ENTRY_ID) == DEVICE_KIND_BLE_VACUUM

    def test_light(self):
        hass = _hass({"is_ble": True, "ble_coordinator": "c"})
        assert async_entry_kind(hass, ENTRY_ID) == DEVICE_KIND_BLE_LIGHT

    def test_mqtt_coordinator_is_not_a_dict(self):
        hass = _hass(MagicMock())  # MQTT stores the coordinator directly
        assert async_entry_kind(hass, ENTRY_ID) == DEVICE_KIND_MQTT

    def test_unknown_entry_defaults_to_mqtt(self):
        hass = MagicMock()
        hass.data = {DOMAIN: {}}
        assert async_entry_kind(hass, "missing") == DEVICE_KIND_MQTT

    def test_domain_absent_entirely(self):
        hass = MagicMock()
        hass.data = {}
        assert async_entry_kind(hass, ENTRY_ID) == DEVICE_KIND_MQTT


class TestCoordinatorLookup:
    """The coordinator comes back for BLE entries only."""

    def test_vacuum_coordinator(self):
        hass = _hass({"is_ble_vacuum": True, "ble_vacuum_coordinator": "vac"})
        assert async_ble_coordinator(hass, ENTRY_ID) == "vac"

    def test_light_coordinator(self):
        hass = _hass({"is_ble": True, "ble_coordinator": "lamp"})
        assert async_ble_coordinator(hass, ENTRY_ID) == "lamp"

    def test_mqtt_returns_none(self):
        assert async_ble_coordinator(_hass(MagicMock()), ENTRY_ID) is None


class TestPlatformRouting:
    """Routing decides who owns a platform for a given entry."""

    @pytest.mark.asyncio
    async def test_mqtt_entry_is_not_claimed(self):
        """None tells the caller to continue with its own MQTT setup."""
        routed = await async_route_ble_platform(
            _hass(MagicMock()), _entry(), MagicMock(), "sensor"
        )
        assert routed is None

    @pytest.mark.asyncio
    async def test_light_entry_is_not_claimed(self):
        """The BLE light still builds entities inline in each platform."""
        hass = _hass({"is_ble": True, "ble_coordinator": "lamp"})
        routed = await async_route_ble_platform(
            hass, _entry(), MagicMock(), "binary_sensor"
        )
        assert routed is None

    @pytest.mark.asyncio
    async def test_vacuum_platform_is_dispatched(self):
        hass = _hass({"is_ble_vacuum": True, "ble_vacuum_coordinator": "vac"})
        add = MagicMock()
        entry = _entry()
        with patch(
            "custom_components.hass_dyson.ble_vacuum_select.async_setup_entry",
            new=AsyncMock(return_value=True),
        ) as setup:
            routed = await async_route_ble_platform(hass, entry, add, "select")
        assert routed is True
        setup.assert_awaited_once_with(hass, entry, add)

    @pytest.mark.asyncio
    async def test_unimplemented_platform_is_a_noop_not_a_fallthrough(self):
        """The actual regression guard.

        'fan' has no vacuum module.  The router must claim it (True) so the
        entry never reaches the MQTT branch, which would raise on the dict.
        """
        hass = _hass({"is_ble_vacuum": True, "ble_vacuum_coordinator": "vac"})
        routed = await async_route_ble_platform(hass, _entry(), MagicMock(), "fan")
        assert routed is True

    @pytest.mark.asyncio
    async def test_module_returning_none_is_normalised_to_true(self):
        hass = _hass({"is_ble_vacuum": True, "ble_vacuum_coordinator": "vac"})
        with patch(
            "custom_components.hass_dyson.ble_vacuum_update.async_setup_entry",
            new=AsyncMock(return_value=None),
        ):
            routed = await async_route_ble_platform(
                hass, _entry(), MagicMock(), "update"
            )
        assert routed is True


class TestTableConsistency:
    """The table and the forwarded platform list must not drift apart."""

    def test_every_forwarded_vacuum_platform_has_a_module(self):
        forwarded = set(BLE_PLATFORMS[DEVICE_KIND_BLE_VACUUM])
        mapped = set(_BLE_PLATFORM_MODULES[DEVICE_KIND_BLE_VACUUM])
        assert forwarded == mapped, (
            "a platform is forwarded at setup but has no module to handle it "
            "(or vice versa)"
        )

    def test_every_vacuum_module_is_importable_and_has_setup(self):
        import importlib

        for platform, name in _BLE_PLATFORM_MODULES[DEVICE_KIND_BLE_VACUUM].items():
            module = importlib.import_module(f"custom_components.hass_dyson.{name}")
            assert hasattr(module, "async_setup_entry"), f"{name} ({platform})"


class TestTranslationsNotClobbered:
    """Adding entities must not drop translations for existing ones.

    A section of translations/en.json was once replaced wholesale rather than
    merged, silently deleting the names of nine MQTT select entities that have
    nothing to do with BLE. Nothing failed: the entities kept working, they
    just lost their friendly names.
    """

    @staticmethod
    def _entity_section(platform):
        import json
        import pathlib

        import custom_components.hass_dyson as pkg

        path = pathlib.Path(pkg.__file__).parent / "translations" / "en.json"
        return json.loads(path.read_text(encoding="utf-8"))["entity"][platform]

    def test_mqtt_select_names_survive(self):
        """These predate the BLE work and must stay."""
        selects = self._entity_section("select")
        for key in (
            "fan_control_mode",
            "oscillation_mode",
            "tilt_oscillation_mode",
            "heating_mode",
            "water_hardness",
            "robot_power_360_eye",
            "robot_power_heurist",
            "robot_power_vis_nav",
            "robot_power_generic",
        ):
            assert key in selects, f"translation for select.{key} was dropped"

    def test_ble_vacuum_selects_are_present_too(self):
        selects = self._entity_section("select")
        for key in (
            "ble_vacuum_brush_bar_speed_select",
            "ble_vacuum_dust_illumination_select",
            "ble_vacuum_ui_language_select",
        ):
            assert key in selects

    def test_every_ble_vacuum_entity_has_a_name(self):
        """Each translation_key used by the BLE modules must resolve."""
        import glob
        import json
        import pathlib
        import re

        import custom_components.hass_dyson as pkg

        root = pathlib.Path(pkg.__file__).parent
        table = json.loads(
            (root / "translations" / "en.json").read_text(encoding="utf-8")
        )["entity"]
        known = {k for section in table.values() for k in section}

        used = set()
        for path in glob.glob(str(root / "ble_vacuum*.py")):
            used |= set(
                re.findall(
                    r'_attr_translation_key\s*=\s*"([^"]+)"',
                    pathlib.Path(path).read_text(),
                )
            )
        assert used, "no translation keys found — the scan is broken"
        missing = sorted(used - known)
        assert not missing, f"entities with no translation: {missing}"
