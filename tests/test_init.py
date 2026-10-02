"""Tests for setting up and tearing down a vehicle entry."""

from unittest.mock import patch

from freezegun import freeze_time
from homeassistant.config_entries import ConfigEntryState

from custom_components.etoll.coordinator import EtollCoordinator
from custom_components.etoll.exceptions import (
    EtollConnectionError,
    EtollVehicleMismatchError,
)

from .conftest import NOW, setup_entry, vignette_record


@freeze_time(NOW)
async def test_the_entry_loads_and_keeps_its_coordinator(hass, config_entry):
    await setup_entry(hass, config_entry, [vignette_record()])

    assert config_entry.state is ConfigEntryState.LOADED
    assert isinstance(config_entry.runtime_data, EtollCoordinator)


@freeze_time(NOW)
async def test_the_entry_unloads(hass, config_entry):
    await setup_entry(hass, config_entry, [vignette_record()])

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_an_unreachable_portal_leaves_the_entry_retrying(hass, config_entry):
    config_entry.add_to_hass(hass)

    with patch(
        "custom_components.etoll.coordinator.EtollApi.async_get_vignettes",
        side_effect=EtollConnectionError("down"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_a_vehicle_mismatch_asks_for_reauth(hass, config_entry):
    config_entry.add_to_hass(hass)

    with patch(
        "custom_components.etoll.coordinator.EtollApi.async_get_vignettes",
        side_effect=EtollVehicleMismatchError("certificate does not match"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"]["source"] == "reauth" for flow in flows)
