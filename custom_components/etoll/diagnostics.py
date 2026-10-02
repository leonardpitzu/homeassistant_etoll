"""Diagnostics for eToll rovinietă."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from . import EtollConfigEntry
from .const import CONF_CERTIFICATE_SERIES, CONF_VIN

TO_REDACT = {CONF_VIN, CONF_CERTIFICATE_SERIES, "series"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: EtollConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    vignette = coordinator.data

    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "vignette": async_redact_data(asdict(vignette), TO_REDACT) if vignette else None,
    }
