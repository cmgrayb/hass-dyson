"""Date settings for Dyson BLE lights."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Register only the lamp-local away start date."""
    data = hass.data[DOMAIN][entry.entry_id]
    if isinstance(data, dict) and data.get("is_ble"):
        from .ble_light_entities import DysonBLELightAwayDate

        async_add_entities([DysonBLELightAwayDate(data["ble_coordinator"])])
