"""Optional Lightcycle controls, backed only by the lamp coordinator API."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, time
from typing import TYPE_CHECKING, Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.components.date import DateEntity
from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.components.select import SelectEntity
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.util import dt as dt_util

from .ble_light_entity import DysonBLELightSettingEntity
from .ble_light_protocol import (
    MODE_ATTRIBUTES,
    LightAttribute,
    decode_away_date,
    encode_away_date,
)

if TYPE_CHECKING:
    from .coordinator import DysonBLEDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class LightcycleSwitchDescription(SwitchEntityDescription):
    """Either a direct sensor setting or a one-byte Boolean attribute."""

    attribute: LightAttribute | None = None
    sensor_key: str | None = None


SWITCH_DESCRIPTIONS = (
    LightcycleSwitchDescription(
        key="auto_brightness",
        name="Auto-brightness sensor",
        icon="mdi:brightness-auto",
        sensor_key="auto_brightness",
    ),
    LightcycleSwitchDescription(
        key="movement_sensor",
        name="Movement sensor",
        icon="mdi:motion-sensor",
        sensor_key="movement_sensor",
    ),
    LightcycleSwitchDescription(
        key="age_adjustment",
        name="Age adjustment",
        icon="mdi:account",
        attribute=LightAttribute.AGE_ADJUST_MODE,
    ),
    LightcycleSwitchDescription(
        key="sleep_mode",
        name="Sleep mode",
        icon="mdi:sleep",
        attribute=LightAttribute.DND_MODE,
    ),
    LightcycleSwitchDescription(
        key="away_mode",
        name="Away mode",
        icon="mdi:home-export-outline",
        attribute=LightAttribute.AWAY_MODE,
    ),
    LightcycleSwitchDescription(
        key="personal_daylight",
        name="Personal daylight times",
        icon="mdi:weather-sunset",
        attribute=LightAttribute.PERSONAL_DAYLIGHT_MODE,
    ),
    LightcycleSwitchDescription(
        key="wake_up_schedule",
        name="Wake-up schedule",
        icon="mdi:alarm",
        attribute=LightAttribute.WAKE_UP_SCHEDULE_TOGGLE,
    ),
)


class DysonBLELightSwitch(DysonBLELightSettingEntity, SwitchEntity):
    """A physical sensor toggle or optional lamp mode toggle."""

    entity_description: LightcycleSwitchDescription

    def __init__(
        self,
        coordinator: DysonBLEDataUpdateCoordinator,
        description: LightcycleSwitchDescription,
    ) -> None:
        """Configure one native Boolean attribute or physical sensor toggle."""
        super().__init__(
            coordinator,
            description.key,
            description.name if isinstance(description.name, str) else None,
        )
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return confirmed enablement, not a raw lux or motion measurement."""
        if self.coordinator.data is None:
            return None
        if self.entity_description.sensor_key is not None:
            value = self.coordinator.data.get(self.entity_description.sensor_key)
            return value if isinstance(value, bool) else None
        return self.attribute_bool(self.entity_description.attribute)

    @property
    def available(self) -> bool:
        """Require an independently decoded value for this feature."""
        return super().available and self.is_on is not None

    async def _async_set_enabled(self, enabled: bool) -> None:
        description = self.entity_description
        if description.sensor_key is not None:
            await self.lighting.set_sensor(description.sensor_key, enabled)
        else:
            await self.lighting.set_attribute(
                description.attribute, bytes((int(enabled),))
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the setting and wait for device confirmation."""
        await self._async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the setting and wait for device confirmation."""
        await self._async_set_enabled(False)


@dataclass(frozen=True, kw_only=True)
class LightcycleNumberDescription(NumberEntityDescription):
    """An unsigned 16-bit setting, except for the encrypted birth year."""

    attribute: LightAttribute | None = None


NUMBER_DESCRIPTIONS = (
    LightcycleNumberDescription(
        key="baseline_brightness",
        name="After-sunset brightness",
        icon="mdi:brightness-6",
        attribute=LightAttribute.BASELINE_BRIGHTNESS,
        native_min_value=1,
        native_max_value=1000,
        native_unit_of_measurement="lm",
    ),
    LightcycleNumberDescription(
        key="baseline_colour_temperature",
        name="After-sunset colour temperature",
        icon="mdi:thermometer",
        attribute=LightAttribute.BASELINE_COLOUR_TEMPERATURE,
        native_min_value=2700,
        native_max_value=6500,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
    ),
    LightcycleNumberDescription(
        key="wake_up_brightness",
        name="Wake-up brightness",
        icon="mdi:alarm",
        attribute=LightAttribute.WAKE_UP_BRIGHTNESS,
        native_min_value=1,
        native_max_value=1000,
        native_unit_of_measurement="lm",
    ),
    LightcycleNumberDescription(
        key="birth_year",
        name="Year of birth",
        icon="mdi:account-clock",
        native_min_value=1900,
    ),
)


class DysonBLELightNumber(DysonBLELightSettingEntity, NumberEntity):
    """A persistent lamp setting rather than a preview of current output."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1
    entity_description: LightcycleNumberDescription

    def __init__(
        self,
        coordinator: DysonBLEDataUpdateCoordinator,
        description: LightcycleNumberDescription,
    ) -> None:
        """Configure setting bounds and make the sensitive birth year opt-in."""
        super().__init__(
            coordinator,
            description.key,
            description.name if isinstance(description.name, str) else None,
        )
        self.entity_description = description
        if description.key == "birth_year":
            self._attr_entity_registry_enabled_default = False

    @property
    def native_max_value(self) -> float:
        """Use the current year as the birth-year limit."""
        if self.entity_description.key == "birth_year":
            return dt_util.now().year
        return self.entity_description.native_max_value

    @property
    def native_value(self) -> int | None:
        """Return the validated stored lumen, Kelvin or birth-year setting."""
        if self.coordinator.data is None or self.coordinator.ble_device is None:
            return None
        value = (
            self.lighting.birth_year
            if self.entity_description.key == "birth_year"
            else self.attribute_uint16(self.entity_description.attribute)
        )
        if not isinstance(value, int) or isinstance(value, bool):
            return None
        return (
            value if self.native_min_value <= value <= self.native_max_value else None
        )

    @property
    def available(self) -> bool:
        """Allow supported-but-unset birth year without inventing a value."""
        if self.entity_description.key == "birth_year":
            return super().available and (
                self.native_value is not None
                or self.attribute_bytes(LightAttribute.YEAR_OF_BIRTH, 64) is not None
            )
        return super().available and self.native_value is not None

    async def async_set_native_value(self, value: float) -> None:
        """Validate whole-number bounds before sending a confirmed setting."""
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or int(value) != value
            or not self.native_min_value <= value <= self.native_max_value
        ):
            raise ValueError(
                "Lightcycle setting must be a whole number within its bounds"
            )
        if self.entity_description.key == "birth_year":
            await self.lighting.set_birth_year(int(value))
        else:
            await self.lighting.set_attribute(
                self.entity_description.attribute, int(value).to_bytes(2, "little")
            )


class DysonBLELightModeSelect(DysonBLELightSettingEntity, SelectEntity):
    """The lamp's actual built-in mode, not a Kelvin/brightness approximation."""

    _attr_options = ["manual", *MODE_ATTRIBUTES]
    _attr_icon = "mdi:desk-lamp"

    def __init__(self, coordinator: DysonBLEDataUpdateCoordinator) -> None:
        """Identify the native lighting-mode selector on the existing device."""
        super().__init__(coordinator, "lighting_mode", "Lighting mode")

    @property
    def current_option(self) -> str | None:
        """Return a mode only when every required mode flag is known."""
        modes = {
            mode: self.attribute_bool(attr) for mode, attr in MODE_ATTRIBUTES.items()
        }
        if any(value is None for value in modes.values()):
            return None
        return next((mode for mode, enabled in modes.items() if enabled), "manual")

    @property
    def available(self) -> bool:
        """Require a decoded mode rather than an optimistic default."""
        return super().available and self.current_option is not None

    async def async_select_option(self, option: str) -> None:
        """Select one of the validated built-in lamp modes."""
        if option not in self.options:
            raise ValueError("Unsupported Lightcycle lighting mode")
        await self.lighting.set_mode(option)


TIME_DESCRIPTIONS = (
    ("sunrise_time", "Sunrise time", LightAttribute.SUNRISE_TIME),
    ("sunset_time", "Sunset time", LightAttribute.SUNSET_TIME),
    ("sleep_start_time", "Sleep start time", LightAttribute.DND_START_TIME),
    ("sleep_end_time", "Sleep end time", LightAttribute.DND_END_TIME),
)


class DysonBLELightTime(DysonBLELightSettingEntity, TimeEntity):
    """A lamp-local wall-clock setting encoded as a LE16 minute count."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        coordinator: DysonBLEDataUpdateCoordinator,
        key: str,
        name: str,
        attribute: LightAttribute,
    ) -> None:
        """Configure an optional lamp-local wall-clock attribute."""
        super().__init__(coordinator, key, name)
        self._attribute = attribute

    @property
    def native_value(self) -> time | None:
        """Decode valid minute counts; keep the unset sentinel unknown."""
        minutes = self.attribute_uint16(self._attribute)
        if minutes is None or not 0 <= minutes < 24 * 60:
            return None
        return time(minutes // 60, minutes % 60)

    @property
    def available(self) -> bool:
        """Keep supported but unset time fields editable."""
        return (
            super().available and self.attribute_bytes(self._attribute, 2) is not None
        )

    async def async_set_value(self, value: time) -> None:
        """Write local hours and whole minutes without a timezone conversion."""
        if value.tzinfo is not None or value.second or value.microsecond:
            raise ValueError("Lightcycle times require local hours and whole minutes")
        await self.lighting.set_attribute(
            self._attribute, (value.hour * 60 + value.minute).to_bytes(2, "little")
        )


class DysonBLELightAwayDate(DysonBLELightSettingEntity, DateEntity):
    """Away start date encoded as numeric DDMMYYYY, never as a timestamp."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:calendar-start"

    def __init__(self, coordinator: DysonBLEDataUpdateCoordinator) -> None:
        """Identify the native away-mode start-date setting."""
        super().__init__(coordinator, "away_start_date", "Away start date")

    @property
    def native_value(self) -> date | None:
        """Return a decoded date without substituting today's date for unset."""
        value = self.attribute_bytes(LightAttribute.AWAY_MODE_START_DATE, 4)
        return decode_away_date(value) if value is not None else None

    @property
    def available(self) -> bool:
        """Keep a supported but unset date editable."""
        return (
            super().available
            and self.attribute_bytes(LightAttribute.AWAY_MODE_START_DATE, 4) is not None
        )

    async def async_set_value(self, value: date) -> None:
        """Write the native date representation and await confirmation."""
        await self.lighting.set_attribute(
            LightAttribute.AWAY_MODE_START_DATE, encode_away_date(value)
        )


BUTTON_DESCRIPTIONS = (
    ButtonEntityDescription(
        key="sync_location",
        name="Sync cloud location",
        icon="mdi:map-marker-sync",
    ),
    ButtonEntityDescription(
        key="reset_daylight_times",
        name="Reset daylight times",
        icon="mdi:weather-sunset",
    ),
)


class DysonBLELightButton(DysonBLELightSettingEntity, ButtonEntity):
    """Explicit configuration actions; no cloud/private data is exposed."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: DysonBLEDataUpdateCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Identify an explicit lamp configuration action."""
        super().__init__(
            coordinator,
            description.key,
            description.name if isinstance(description.name, str) else None,
        )
        self.entity_description = description

    async def async_press(self) -> None:
        """Run the selected configuration action without exposing cloud data."""
        if self.entity_description.key == "sync_location":
            await self.coordinator.async_sync_light_location()
        else:
            await self.lighting.reset_daylight_times()

    @property
    def available(self) -> bool:
        """Only offer actions when the attribute channel can confirm them."""
        device = self.coordinator.ble_device
        return super().available and device is not None and device.lighting.available


def lightcycle_switches(
    coordinator: DysonBLEDataUpdateCoordinator,
) -> list[DysonBLELightSwitch]:
    """Create optional switches without duplicating the existing daylight entity."""
    return [
        DysonBLELightSwitch(coordinator, description)
        for description in SWITCH_DESCRIPTIONS
    ]


def lightcycle_numbers(
    coordinator: DysonBLEDataUpdateCoordinator,
) -> list[DysonBLELightNumber]:
    """Create persistent lamp settings, including the opt-in birth-year entity."""
    return [
        DysonBLELightNumber(coordinator, description)
        for description in NUMBER_DESCRIPTIONS
    ]


def lightcycle_buttons(
    coordinator: DysonBLEDataUpdateCoordinator,
) -> list[DysonBLELightButton]:
    """Create explicit configuration actions on the existing lamp device."""
    return [
        DysonBLELightButton(coordinator, description)
        for description in BUTTON_DESCRIPTIONS
    ]


def lightcycle_times(
    coordinator: DysonBLEDataUpdateCoordinator,
) -> list[DysonBLELightTime]:
    """Create the lamp-local sunrise, sunset and sleep-window controls."""
    return [
        DysonBLELightTime(coordinator, *description)
        for description in TIME_DESCRIPTIONS
    ]
