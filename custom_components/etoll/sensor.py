"""Sensor platform for eToll rovinietă."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import EtollConfigEntry
from .const import ATTRIBUTION, DOMAIN
from .coordinator import EtollCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EtollConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the vignette sensor for this vehicle."""
    async_add_entities([DaysRemainingSensor(entry.runtime_data)])


class DaysRemainingSensor(CoordinatorEntity[EtollCoordinator], SensorEntity):
    """Days of road-tax validity left for one vehicle.

    Zero means the vehicle has no valid rovinietă right now — that is the true
    number of days left, and it keeps a numeric_state automation working in the
    case that matters most. ``unavailable`` is reserved for a failed lookup.
    """

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "days_remaining"

    def __init__(self, coordinator: EtollCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        plate = coordinator.plate_number
        self._attr_unique_id = f"{plate}_days_remaining"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, plate)},
            name=f"Rovinietă {plate}",
            manufacturer="CNAIR",
            model="eToll",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Re-publish the countdown at local midnight.

        The value is derived from a date, so a new day changes it without the
        portal having anything new to say.
        """
        await super().async_added_to_hass()
        self.async_on_remove(async_track_time_change(self.hass, self._handle_midnight, hour=0, minute=0, second=0))

    @callback
    def _handle_midnight(self, now: Any) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        """Return whole days until the vignette stops being valid."""
        vignette = self.coordinator.data
        if vignette is None:
            return 0
        expiry = dt_util.as_local(vignette.valid_until).date()
        return max(0, (expiry - dt_util.now().date()).days)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the vignette this countdown belongs to."""
        vignette = self.coordinator.data
        return {
            "plate_number": self.coordinator.plate_number,
            "valid_from": _as_local_date(vignette.valid_from) if vignette else None,
            "valid_until": _as_local_date(vignette.valid_until) if vignette else None,
            "vignette_series": vignette.series if vignette else None,
            "vehicle_category": vignette.category if vignette else None,
            "emission_standard": vignette.emission_standard if vignette else None,
            "price": vignette.price if vignette else None,
        }


def _as_local_date(value: Any) -> str:
    """Render a moment as the local calendar date it falls on."""
    return dt_util.as_local(value).date().isoformat()
