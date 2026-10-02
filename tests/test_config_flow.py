"""Tests for the eToll rovinietă config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.etoll.const import (
    CONF_CERTIFICATE_SERIES,
    CONF_PLATE_NUMBER,
    CONF_VIN,
    DOMAIN,
)
from custom_components.etoll.exceptions import (
    EtollApiError,
    EtollConnectionError,
    EtollVehicleMismatchError,
)

from .conftest import PLATE, SERIES, VIN, vignette_record

USER_INPUT = {
    CONF_PLATE_NUMBER: "b123abc ",
    CONF_VIN: " wvwzzz1jzxw000001",
    CONF_CERTIFICATE_SERIES: "b00000000x ",
}


def _lookup(**kwargs):
    return patch("custom_components.etoll.config_flow.EtollApi.async_get_vignettes", **kwargs)


async def test_a_vehicle_is_added_with_normalised_details(hass):
    with _lookup(return_value=[vignette_record()]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Rovinietă {PLATE}"
    assert result["data"] == {
        CONF_PLATE_NUMBER: PLATE,
        CONF_VIN: VIN,
        CONF_CERTIFICATE_SERIES: SERIES,
    }


async def test_a_vehicle_without_a_vignette_can_still_be_added(hass):
    with _lookup(return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_an_unreachable_portal_is_reported(hass):
    with _lookup(side_effect=EtollConnectionError("boom")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_a_vehicle_mismatch_is_reported(hass):
    with _lookup(side_effect=EtollVehicleMismatchError("nope")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "vehicle_mismatch"}


async def test_a_refused_lookup_is_reported(hass):
    with _lookup(side_effect=EtollApiError("nope")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "lookup_failed"}


async def test_the_same_plate_cannot_be_added_twice(hass, config_entry):
    config_entry.add_to_hass(hass)

    with _lookup(return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=USER_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_the_certificate_series(hass, config_entry):
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": config_entry.entry_id},
        data=config_entry.data,
    )
    assert result["step_id"] == "reauth_confirm"

    with _lookup(return_value=[]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_CERTIFICATE_SERIES: "b99999999z"}
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert config_entry.data[CONF_CERTIFICATE_SERIES] == "B99999999Z"

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()


async def test_reconfigure_updates_the_vehicle(hass, config_entry):
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": config_entry.entry_id},
    )
    assert result["step_id"] == "reconfigure"

    with _lookup(return_value=[]):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert config_entry.data[CONF_VIN] == VIN

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
