"""Config flow for eToll rovinietă."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import EtollApi
from .const import (
    CONF_CERTIFICATE_SERIES,
    CONF_PLATE_NUMBER,
    CONF_VIN,
    DOMAIN,
)
from .exceptions import (
    EtollApiError,
    EtollConnectionError,
    EtollVehicleMismatchError,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATE_NUMBER): str,
        vol.Required(CONF_VIN): str,
        vol.Required(CONF_CERTIFICATE_SERIES): str,
    }
)

STEP_SERIES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CERTIFICATE_SERIES): str,
    }
)


class EtollConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the vehicle details, and check the lookup works."""

    VERSION = 1

    async def _async_lookup_fails(
        self, plate: str, vin: str, series: str, errors: dict[str, str]
    ) -> bool:
        """Run the lookup once, mapping any failure onto ``errors``."""
        api = EtollApi(self.hass, async_create_clientsession(self.hass))
        try:
            await api.async_get_vignettes(plate, vin, series)
        except EtollConnectionError as err:
            _LOGGER.debug("Cannot reach portal.etoll.ro: %s", err)
            errors["base"] = "cannot_connect"
        except EtollVehicleMismatchError as err:
            _LOGGER.debug("Vehicle details rejected: %s", err)
            errors["base"] = "vehicle_mismatch"
        except EtollApiError as err:
            _LOGGER.debug("Lookup refused: %s", err)
            errors["base"] = "lookup_failed"
        return bool(errors)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle adding a new vehicle."""
        errors: dict[str, str] = {}

        if user_input is not None:
            plate = user_input[CONF_PLATE_NUMBER].upper().strip()
            vin = user_input[CONF_VIN].upper().strip()
            series = user_input[CONF_CERTIFICATE_SERIES].upper().strip()

            await self.async_set_unique_id(plate)
            self._abort_if_unique_id_configured()

            if not await self._async_lookup_fails(plate, vin, series, errors):
                return self.async_create_entry(
                    title=f"Rovinietă {plate}",
                    data={
                        CONF_PLATE_NUMBER: plate,
                        CONF_VIN: vin,
                        CONF_CERTIFICATE_SERIES: series,
                    },
                )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start a re-auth when the stored details stop matching."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask only for the certificate series again and re-check the lookup."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            series = user_input[CONF_CERTIFICATE_SERIES].upper().strip()
            plate = entry.data[CONF_PLATE_NUMBER]
            vin = entry.data[CONF_VIN]

            if not await self._async_lookup_fails(plate, vin, series, errors):
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_CERTIFICATE_SERIES: series}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_SERIES_SCHEMA,
            errors=errors,
            description_placeholders={"plate": entry.data[CONF_PLATE_NUMBER]},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user correct the plate, VIN or series of an existing vehicle."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            plate = user_input[CONF_PLATE_NUMBER].upper().strip()
            vin = user_input[CONF_VIN].upper().strip()
            series = user_input[CONF_CERTIFICATE_SERIES].upper().strip()

            await self.async_set_unique_id(plate)
            self._abort_if_unique_id_mismatch(reason="wrong_vehicle")

            if not await self._async_lookup_fails(plate, vin, series, errors):
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_PLATE_NUMBER: plate,
                        CONF_VIN: vin,
                        CONF_CERTIFICATE_SERIES: series,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_SCHEMA, entry.data),
            errors=errors,
        )
