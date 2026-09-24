"""Unit tests for BLE vacuum entity modules (sensors, binary sensors, selects, switches)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hass_dyson import (
    ble_vacuum_binary_sensor as bs_mod,
    ble_vacuum_select as sel_mod,
    ble_vacuum_sensor as sen_mod,
    ble_vacuum_switch as sw_mod,
)
from custom_components.hass_dyson.const import (
    BLE_VACUUM_ATTR_BATTERY_LEVEL,
    BLE_VACUUM_ATTR_BRUSH_BAR_SPEED,
    BLE_VACUUM_ATTR_DUST_ILLUMINATION,
    BLE_VACUUM_ATTR_TASK_DETECTION,
    DOMAIN,
)

SERIAL = "7RD-EU-TEST0000X"


def fake_coordinator(data=None, connected=True):
    """Coordinator stand-in with the interface the entities touch."""
    c = MagicMock()
    c.serial_number = SERIAL
    c.is_connected = connected
    c.last_update_success = True
    c.data = data or {}
    c.ble_device = None
    return c


FULL_DATA = {
    "attributes": {
        "power_mode": "auto",
        "blockage": "not_blocked",
        "battery_temperature": "ok",
        "filter_present": "filter_present",
        "filter_wash": "filter_ok",
        "system_error": False,
        "charge_required": "no_charge_required",
        "battery_level": 95,
        "actively_charging": False,
        "charger_present": False,
        "ui_language": "czech",
        "battery_care_setting": False,
        "battery_authenticity": "dyson",
        "task_detection": False,
        "dust_illumination": "on",
        "brush_bar_speed": "high",
        "brush_bar_type": "row_768",
        "session_active": "active",
        "dust_illumination_auto": True,
    },
    "attributes_raw": {BLE_VACUUM_ATTR_BATTERY_LEVEL.hex(): "5f"},
    "session_active": True,
    "session_started_at": 1000.0,
    "last_session_ended_at": 1_757_800_000.0,
    "last_session_duration_seconds": 600.0,
}


# ─── Sensors ────────────────────────────────────────────────────────────────


class TestVacuumSensors:
    def test_battery_level(self):
        s = sen_mod.DysonBleVacuumBatteryLevelSensor(fake_coordinator(FULL_DATA))
        assert s.native_value == 95
        assert s.available

    def test_battery_level_missing(self):
        s = sen_mod.DysonBleVacuumBatteryLevelSensor(fake_coordinator({}))
        assert s.native_value is None

    def test_power_mode(self):
        s = sen_mod.DysonBleVacuumPowerModeSensor(fake_coordinator(FULL_DATA))
        assert s.native_value == "auto"
        assert s.options == ["eco", "med", "auto", "boost"]
        assert s.icon == "mdi:fan-auto"

    def test_brush_bar_type(self):
        s = sen_mod.DysonBleVacuumBrushBarTypeSensor(fake_coordinator(FULL_DATA))
        assert s.native_value == "row_768"

    def test_battery_temperature_icon(self):
        s = sen_mod.DysonBleVacuumBatteryTemperatureSensor(fake_coordinator(FULL_DATA))
        assert s.native_value == "ok"
        assert s.icon == "mdi:thermometer-check"

    def test_writable_attributes_have_no_readonly_mirror(self):
        """Brush-bar speed / dust illumination / UI language are selects only."""
        for gone in (
            "DysonBleVacuumBrushBarSpeedSensor",
            "DysonBleVacuumDustIlluminationSensor",
            "DysonBleVacuumUiLanguageSensor",
        ):
            assert not hasattr(sen_mod, gone), f"{gone} duplicates a writable entity"

    def test_ldi_bitmask_is_not_a_number_sensor(self):
        """0x0243 is a capability bitmask, exposed as a binary sensor."""
        assert not hasattr(sen_mod, "DysonBleVacuumLdiStateSensor")

    def test_no_session_history_sensors(self):
        """Durations/history cannot be derived reliably, so they are gone.

        They required HA to be connected across both edges of a clean; a
        handheld vacuum may be out of BLE range during one.  Only the live
        session-active binary sensor, read straight from 0x0740, remains.
        """
        for gone in (
            "DysonBleVacuumSessionDurationSensor",
            "DysonBleVacuumLastSessionDurationSensor",
            "DysonBleVacuumLastSessionEndSensor",
        ):
            assert not hasattr(sen_mod, gone), f"{gone} reports underivable data"
        assert hasattr(bs_mod, "DysonBleVacuumSessionActiveSensor")

    def test_entities_unavailable_when_disconnected(self):
        s = sen_mod.DysonBleVacuumBatteryLevelSensor(
            fake_coordinator(FULL_DATA, connected=False)
        )
        assert not s.available

    def test_enum_guard_out_of_options_value(self, caplog):
        """Unmapped wire values degrade to None instead of ValueError.

        HA validates ENUM native_value against options and raises otherwise;
        the guard must swallow those to None.
        """
        import logging

        data = dict(FULL_DATA)
        attrs = dict(FULL_DATA["attributes"])
        attrs["brush_bar_type"] = "unknown (ac)"
        data["attributes"] = attrs
        s = sen_mod.DysonBleVacuumBrushBarTypeSensor(fake_coordinator(data))
        with caplog.at_level(logging.DEBUG):
            assert s.native_value is None

    def test_enum_normal_label_still_passes(self):
        s = sen_mod.DysonBleVacuumBrushBarTypeSensor(fake_coordinator(FULL_DATA))
        assert s.native_value == "row_768"
        assert s.options == ["erp_768", "row_768", "none_attached"]


# ─── Binary sensors ─────────────────────────────────────────────────────────


class TestVacuumBinarySensors:
    def test_charging_states(self):
        for cls_name, key, on_val, off_val, exp_on, exp_off in [
            (
                "DysonBleVacuumActivelyChargingSensor",
                "actively_charging",
                True,
                False,
                True,
                False,
            ),
            (
                "DysonBleVacuumChargerPresentSensor",
                "charger_present",
                True,
                False,
                True,
                False,
            ),
            (
                "DysonBleVacuumBatteryAuthenticitySensor",
                "battery_authenticity",
                "non_dyson",
                "dyson",
                True,
                False,
            ),
        ]:
            cls = getattr(bs_mod, cls_name)
            sensor = cls(fake_coordinator({"attributes": {key: on_val}}))
            assert sensor.is_on is exp_on, cls_name
            sensor = cls(fake_coordinator({"attributes": {key: off_val}}))
            assert sensor.is_on is exp_off, cls_name

    def test_blockage_problem_states(self):
        sensor = bs_mod.DysonBleVacuumBlockageSensor(
            fake_coordinator({"attributes": {"blockage": "inlet_blocked"}})
        )
        assert sensor.is_on is True
        sensor = bs_mod.DysonBleVacuumBlockageSensor(
            fake_coordinator({"attributes": {"blockage": "not_blocked"}})
        )
        assert sensor.is_on is False

    def test_filter_present_problem(self):
        sensor = bs_mod.DysonBleVacuumFilterPresentSensor(
            fake_coordinator({"attributes": {"filter_present": "filter_not_present"}})
        )
        assert sensor.is_on is True
        sensor = bs_mod.DysonBleVacuumFilterPresentSensor(
            fake_coordinator({"attributes": {"filter_present": "filter_present"}})
        )
        assert sensor.is_on is False

    def test_filter_wash_problem(self):
        sensor = bs_mod.DysonBleVacuumFilterWashSensor(
            fake_coordinator({"attributes": {"filter_wash": "filter_needs_cleaning"}})
        )
        assert sensor.is_on is True

    def test_system_error(self):
        sensor = bs_mod.DysonBleVacuumSystemErrorSensor(
            fake_coordinator({"attributes": {"system_error": True}})
        )
        assert sensor.is_on is True
        assert sensor.extra_state_attributes["state"] is True

    def test_charge_required(self):
        sensor = bs_mod.DysonBleVacuumChargeRequiredSensor(
            fake_coordinator({"attributes": {"charge_required": "place_on_charge"}})
        )
        assert sensor.is_on is True

    def test_session_active_uses_top_level_state(self):
        sensor = bs_mod.DysonBleVacuumSessionActiveSensor(
            fake_coordinator({"session_active": True})
        )
        assert sensor.is_on is True
        assert "vacuum" in sensor.icon


# ─── Selects ────────────────────────────────────────────────────────────────


class TestVacuumSelects:
    def _coordinator_with_device(self):
        c = fake_coordinator(FULL_DATA)
        device = MagicMock()
        device.write_attribute = AsyncMock(return_value=True)
        device.device_info = None
        c.ble_device = device
        return c

    def test_current_option(self):
        c = self._coordinator_with_device()
        s = sel_mod.DysonBleVacuumBrushBarSpeedSelect(c)
        assert s.current_option == "high"
        assert s.options == ["low", "high", "auto"]

    async def test_select_brush_speed_sends_wire_value(self):
        c = self._coordinator_with_device()
        s = sel_mod.DysonBleVacuumBrushBarSpeedSelect(c)
        await s.async_select_option("auto")
        c.ble_device.write_attribute.assert_awaited_once_with(
            BLE_VACUUM_ATTR_BRUSH_BAR_SPEED, bytes([2])
        )

    async def test_select_dust_illumination_sends_wire_value(self):
        c = self._coordinator_with_device()
        s = sel_mod.DysonBleVacuumDustIlluminationSelect(c)
        assert s.current_option == "on"
        await s.async_select_option("off")
        c.ble_device.write_attribute.assert_awaited_once_with(
            BLE_VACUUM_ATTR_DUST_ILLUMINATION, bytes([0])
        )

    async def test_unknown_option_raises(self):
        c = self._coordinator_with_device()
        s = sel_mod.DysonBleVacuumBrushBarSpeedSelect(c)
        with pytest.raises(ValueError):
            await s.async_select_option("turbo")


# ─── Switch ─────────────────────────────────────────────────────────────────


class TestVacuumSwitch:
    def test_is_on(self):
        sw = sw_mod.DysonBleVacuumTaskDetectionSwitch(fake_coordinator(FULL_DATA))
        assert sw.is_on is False
        assert sw.icon == "mdi:motion-sensor-off"

    async def test_turn_on_writes_1(self):
        c = fake_coordinator(FULL_DATA)
        device = MagicMock()
        device.write_attribute = AsyncMock(return_value=True)
        device.device_info = None
        c.ble_device = device
        sw = sw_mod.DysonBleVacuumTaskDetectionSwitch(c)
        await sw.async_turn_on()
        device.write_attribute.assert_awaited_once_with(
            BLE_VACUUM_ATTR_TASK_DETECTION, bytes([1])
        )

    async def test_turn_off_writes_0(self):
        c = fake_coordinator(FULL_DATA)
        device = MagicMock()
        device.write_attribute = AsyncMock(return_value=True)
        device.device_info = None
        c.ble_device = device
        sw = sw_mod.DysonBleVacuumTaskDetectionSwitch(c)
        await sw.async_turn_off()
        device.write_attribute.assert_awaited_once_with(
            BLE_VACUUM_ATTR_TASK_DETECTION, bytes([0])
        )


class TestCoverageEdges:
    def test_base_unavailable_when_update_failed(self):
        c = fake_coordinator(FULL_DATA)
        c.last_update_success = False
        for ent in (
            sen_mod.DysonBleVacuumBatteryLevelSensor(c),
            bs_mod.DysonBleVacuumSessionActiveSensor(c),
            sel_mod.DysonBleVacuumBrushBarSpeedSelect(c),
            sw_mod.DysonBleVacuumTaskDetectionSwitch(c),
        ):
            assert not ent.available

    def test_device_info_none_without_ble_device(self):
        c = fake_coordinator(FULL_DATA)
        for ent in (
            sen_mod.DysonBleVacuumBatteryLevelSensor(c),
            bs_mod.DysonBleVacuumSessionActiveSensor(c),
            sel_mod.DysonBleVacuumBrushBarSpeedSelect(c),
            sw_mod.DysonBleVacuumTaskDetectionSwitch(c),
        ):
            assert ent.device_info is None

    async def test_write_rejected_is_logged_not_fatal(self, caplog):
        import logging

        for mod_attr in (
            (
                sel_mod.DysonBleVacuumBrushBarSpeedSelect,
                sel_mod.DysonBleVacuumBrushBarSpeedSelect.async_select_option,
                "auto",
            ),
            (
                sw_mod.DysonBleVacuumTaskDetectionSwitch,
                sw_mod.DysonBleVacuumTaskDetectionSwitch.async_turn_on,
                None,
            ),
        ):
            cls, action, opt = mod_attr
            c = fake_coordinator(FULL_DATA)
            device = MagicMock()
            device.write_attribute = AsyncMock(return_value=False)
            device.device_info = None
            c.ble_device = device
            ent = cls(c)
            with caplog.at_level(logging.WARNING):
                if opt is None:
                    await action(ent)
                else:
                    await action(ent, opt)

    def test_switch_icon_follows_state(self):
        c = fake_coordinator(FULL_DATA)
        c.data["attributes"]["task_detection"] = True
        sw = sw_mod.DysonBleVacuumTaskDetectionSwitch(c)
        assert sw.is_on is True
        assert sw.icon == "mdi:motion-sensor"

    def test_setup_branches_run(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "x1"
        coord = fake_coordinator(FULL_DATA)
        hass.data = {DOMAIN: {"x1": {"ble_vacuum_coordinator": coord}}}
        added = []

        async def run(mod):
            await mod.async_setup_entry(hass, entry, lambda ents: added.extend(ents))

        import asyncio

        from custom_components.hass_dyson import ble_vacuum_update as upd_mod

        for mod in (sen_mod, bs_mod, sel_mod, sw_mod, upd_mod):
            asyncio.run(run(mod))
        # 4 sensors + 10 binary sensors + 3 selects + 2 switches + 1 update
        assert len(added) == 20, [type(e).__name__ for e in added]


class TestBatteryCareSwitch:
    """Battery care setting (0x0841) is writable over BLE — app class lq/a."""

    def test_reads_the_setting_attribute(self):
        c = fake_coordinator({"attributes": {"battery_care_setting": True}})
        sw = sw_mod.DysonBleVacuumBatteryCareSwitch(c)
        assert sw.is_on is True
        assert sw.icon == "mdi:shield-check"

    def test_current_gets_no_entity_of_its_own(self):
        """0x1340 only mirrors the setting, so it is not exposed.

        The switch already reports device-confirmed state — is_on reads the
        pushed attribute rather than an optimistic local value — so a second
        entity for 0x1340 would duplicate it roughly 100 ms late.
        """
        assert not hasattr(bs_mod, "DysonBleVacuumBatteryCareCurrentSensor")
        assert not hasattr(bs_mod, "DysonBleVacuumBatteryCareSettingSensor")

    @pytest.mark.asyncio
    async def test_turn_on_writes_the_setting_attribute(self):
        from custom_components.hass_dyson.const import (
            BLE_VACUUM_ATTR_BATTERY_CARE_SETTING,
        )

        c = fake_coordinator(FULL_DATA)
        c.ble_device = MagicMock()
        c.ble_device.write_attribute = AsyncMock(return_value=True)
        await sw_mod.DysonBleVacuumBatteryCareSwitch(c).async_turn_on()
        c.ble_device.write_attribute.assert_awaited_once_with(
            BLE_VACUUM_ATTR_BATTERY_CARE_SETTING, b"\x01"
        )

    @pytest.mark.asyncio
    async def test_turn_off_writes_zero(self):
        c = fake_coordinator(FULL_DATA)
        c.ble_device = MagicMock()
        c.ble_device.write_attribute = AsyncMock(return_value=True)
        await sw_mod.DysonBleVacuumBatteryCareSwitch(c).async_turn_off()
        assert c.ble_device.write_attribute.await_args.args[1] == b"\x00"


class TestUiLanguageSelect:
    """UI language (0x0241) is writable over BLE — app class lq/b."""

    def test_options_and_current(self):
        sel = sel_mod.DysonBleVacuumUiLanguageSelect(fake_coordinator(FULL_DATA))
        assert sel.current_option == "czech"
        assert "english" in sel.options
        assert "czech" in sel.options
        assert len(sel.options) == 30

    @pytest.mark.asyncio
    async def test_select_writes_language_byte(self):
        from custom_components.hass_dyson.const import BLE_VACUUM_ATTR_UI_LANGUAGE

        c = fake_coordinator(FULL_DATA)
        c.ble_device = MagicMock()
        c.ble_device.write_attribute = AsyncMock(return_value=True)
        await sel_mod.DysonBleVacuumUiLanguageSelect(c).async_select_option("czech")
        # Czech is wire value 12 per BleProductUILanguage
        c.ble_device.write_attribute.assert_awaited_once_with(
            BLE_VACUUM_ATTR_UI_LANGUAGE, bytes((12,))
        )

    @pytest.mark.asyncio
    async def test_unknown_language_rejected(self):
        c = fake_coordinator(FULL_DATA)
        c.ble_device = MagicMock()
        c.ble_device.write_attribute = AsyncMock(return_value=True)
        with pytest.raises(ValueError):
            await sel_mod.DysonBleVacuumUiLanguageSelect(c).async_select_option(
                "Klingon"
            )
        c.ble_device.write_attribute.assert_not_awaited()


class TestFirmwareUpdateEntity:
    """Read-only firmware reporting; installing over BLE is not supported."""

    @staticmethod
    def _entity(data):
        from custom_components.hass_dyson import ble_vacuum_update as upd_mod

        return upd_mod.DysonBleVacuumFirmwareUpdate(fake_coordinator(data))

    def test_declares_no_install_support(self):
        ent = self._entity({"firmware_version": "2.13.2"})
        assert not ent.supported_features

    def test_nothing_staged_reports_unknown_not_up_to_date(self):
        """The machine has no internet, so "up to date" is unknowable.

        pending_fw only tells us whether an image has been pushed to the
        machine over BLE by the phone app.  Falling back to installed_version
        would make HA claim the firmware is current, which nothing here knows.
        """
        ent = self._entity(
            {"firmware_version": "2.13.2", "pending_firmware_version": None}
        )
        assert ent.installed_version == "2.13.2"
        assert ent.latest_version is None
        assert ent.state is None  # HA renders this as unknown

    def test_reports_pending_as_latest(self):
        ent = self._entity(
            {"firmware_version": "2.13.2", "pending_firmware_version": "2.14.0"}
        )
        assert ent.latest_version == "2.14.0"

    def test_available_while_offline_when_version_known(self):
        from custom_components.hass_dyson import ble_vacuum_update as upd_mod

        c = fake_coordinator({"firmware_version": "2.13.2"}, connected=False)
        assert upd_mod.DysonBleVacuumFirmwareUpdate(c).available is True

    def test_unavailable_when_no_version_yet(self):
        assert self._entity({}).available is False

    def test_diagnostics_attributes(self):
        ent = self._entity(
            {
                "firmware_version": "2.13.2",
                "recovery_firmware_version": "2.12.11",
                "ota_status": 0,
            }
        )
        assert ent.extra_state_attributes["recovery_firmware_version"] == "2.12.11"
        assert ent.extra_state_attributes["ota_status"] == 0


class TestDustIlluminationCapability:
    """0x0243 is a bitmask the app reduces to one boolean (iq/b.java)."""

    def test_binary_sensor_reads_the_flag(self):
        on = bs_mod.DysonBleVacuumDustIlluminationAutoSensor(
            fake_coordinator({"attributes": {"dust_illumination_auto": True}})
        )
        off = bs_mod.DysonBleVacuumDustIlluminationAutoSensor(
            fake_coordinator({"attributes": {"dust_illumination_auto": False}})
        )
        missing = bs_mod.DysonBleVacuumDustIlluminationAutoSensor(
            fake_coordinator({"attributes": {}})
        )
        assert on.is_on is True
        assert off.is_on is False
        assert missing.is_on is None

    def test_select_hides_auto_when_unavailable(self):
        c = fake_coordinator(
            {
                "attributes": {
                    "dust_illumination": "on",
                    "dust_illumination_auto": False,
                }
            }
        )
        sel = sel_mod.DysonBleVacuumDustIlluminationSelect(c)
        assert sel.options == ["off", "on"]

    def test_select_offers_auto_when_available(self):
        c = fake_coordinator(
            {
                "attributes": {
                    "dust_illumination": "on",
                    "dust_illumination_auto": True,
                }
            }
        )
        sel = sel_mod.DysonBleVacuumDustIlluminationSelect(c)
        assert sel.options == ["off", "on", "auto"]

    def test_auto_kept_when_it_is_the_current_value(self):
        """HA errors if current_option is outside options — never hide it."""
        c = fake_coordinator(
            {
                "attributes": {
                    "dust_illumination": "auto",
                    "dust_illumination_auto": False,
                }
            }
        )
        sel = sel_mod.DysonBleVacuumDustIlluminationSelect(c)
        assert sel.current_option == "auto"
        assert "auto" in sel.options

    @pytest.mark.asyncio
    async def test_selecting_unavailable_auto_is_rejected(self):
        """HA's own @final wrapper rejects it before we ever see the call.

        Exercised through async_handle_select_option (the real service path)
        rather than async_select_option, so this tests actual behaviour and
        not a redundant guard of our own.
        """
        from homeassistant.exceptions import ServiceValidationError

        c = fake_coordinator(
            {
                "attributes": {
                    "dust_illumination": "on",
                    "dust_illumination_auto": False,
                }
            }
        )
        c.ble_device = MagicMock()
        c.ble_device.write_attribute = AsyncMock(return_value=True)
        entity = sel_mod.DysonBleVacuumDustIlluminationSelect(c)
        assert "auto" not in entity.options
        with pytest.raises(ServiceValidationError):
            await entity.async_handle_select_option("auto")
        c.ble_device.write_attribute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_available_option_passes_the_wrapper_and_writes(self):
        """The same real path lets a currently-available option through."""
        c = fake_coordinator(
            {
                "attributes": {
                    "dust_illumination": "on",
                    "dust_illumination_auto": True,
                }
            }
        )
        c.ble_device = MagicMock()
        c.ble_device.write_attribute = AsyncMock(return_value=True)
        await sel_mod.DysonBleVacuumDustIlluminationSelect(
            c
        ).async_handle_select_option("auto")
        c.ble_device.write_attribute.assert_awaited_once()


class TestLanguageOptionOrdering:
    """A 30-item dropdown is ordered for humans, not by Dyson's enum."""

    def test_options_are_alphabetical(self):
        sel = sel_mod.DysonBleVacuumUiLanguageSelect(fake_coordinator(FULL_DATA))
        assert sel.options == sorted(sel.options)
        assert len(sel.options) == 30

    def test_small_selects_keep_wire_order(self):
        """off/on/auto reads better in wire order than alphabetically."""
        sel = sel_mod.DysonBleVacuumDustIlluminationSelect(
            fake_coordinator(
                {"attributes": {"dust_illumination_auto": True}},
            )
        )
        assert sel.options == ["off", "on", "auto"]

    @pytest.mark.asyncio
    async def test_display_order_does_not_affect_the_written_byte(self):
        from custom_components.hass_dyson.const import BLE_VACUUM_ATTR_UI_LANGUAGE

        c = fake_coordinator(FULL_DATA)
        c.ble_device = MagicMock()
        c.ble_device.write_attribute = AsyncMock(return_value=True)
        await sel_mod.DysonBleVacuumUiLanguageSelect(c).async_select_option("czech")
        c.ble_device.write_attribute.assert_awaited_once_with(
            BLE_VACUUM_ATTR_UI_LANGUAGE, bytes((12,))
        )
