"""Coordinator for the eToll rovinietă integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EtollApi
from .const import (
    CONF_CERTIFICATE_SERIES,
    CONF_PLATE_NUMBER,
    CONF_VIN,
    DOMAIN,
    UPDATE_INTERVAL,
)
from .exceptions import (
    EtollApiError,
    EtollConnectionError,
    EtollVehicleMismatchError,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Vignette:
    """One vignette that is in force."""

    valid_from: datetime
    valid_until: datetime
    series: str | None
    category: str | None
    emission_standard: str | None
    price: float | None


class EtollCoordinator(DataUpdateCoordinator[Vignette | None]):
    """Keep the vignette in force for one vehicle up to date.

    ``data`` is ``None`` when the lookup succeeded and the vehicle simply has no
    vignette in force — an answer, not a failure.
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Set up the coordinator for the vehicle in this config entry."""
        self.plate_number: str = entry.data[CONF_PLATE_NUMBER]
        self._vin: str = entry.data[CONF_VIN]
        self._certificate_series: str = entry.data[CONF_CERTIFICATE_SERIES]
        # Own cookie jar: the portal's session cookie must not be shared.
        self._api = EtollApi(hass, async_create_clientsession(hass))

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {self.plate_number}",
            config_entry=entry,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> Vignette | None:
        """Fetch the vignette history and keep the one in force."""
        try:
            records = await self._api.async_get_vignettes(
                self.plate_number, self._vin, self._certificate_series
            )
        except EtollVehicleMismatchError as err:
            # The stored plate/VIN/series no longer identify the vehicle: ask again.
            raise ConfigEntryAuthFailed(f"Vehicle details no longer match: {err}") from err
        except EtollConnectionError as err:
            raise UpdateFailed(f"Cannot reach portal.etoll.ro: {err}") from err
        except EtollApiError as err:
            raise UpdateFailed(f"portal.etoll.ro refused the lookup: {err}") from err

        return _vignette_in_force(records)


def _parse_dt(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp from the portal into an aware UTC datetime."""
    if not value:
        return None
    parsed = dt_util.parse_datetime(str(value))
    if parsed is None:
        return None
    return dt_util.as_utc(parsed)


def _vignette_in_force(records: list[dict[str, Any]]) -> Vignette | None:
    """Return the vignette in force that runs longest, or None if there is none.

    The portal returns every vignette on file, so the validity window is checked
    rather than taking the first record, and among the ones valid right now the
    one that runs longest wins.
    """
    now = dt_util.utcnow()
    in_force: list[tuple[datetime, datetime, dict[str, Any]]] = []
    for record in records:
        start = _parse_dt(record.get("validityStartDate"))
        end = _parse_dt(record.get("validityEndDate"))
        if start is None or end is None:
            continue
        if start <= now <= end:
            in_force.append((end, start, record))

    if not in_force:
        return None

    end, start, record = max(in_force, key=lambda item: item[0])
    return Vignette(
        valid_from=start,
        valid_until=end,
        series=record.get("series"),
        category=record.get("vehicleCategory"),
        emission_standard=record.get("emissionStandardsCategory"),
        price=record.get("price"),
    )
