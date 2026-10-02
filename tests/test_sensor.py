"""Tests for the days-remaining sensor."""

from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import PLATE, setup_entry, vignette_record

ENTITY_ID = "sensor.rovinieta_b123abc_days_remaining"


@pytest.fixture(autouse=True)
async def bucharest(hass: HomeAssistant):
    """Run every test in the timezone the road tax is issued in."""
    await hass.config.async_set_time_zone("Europe/Bucharest")


async def test_counts_calendar_days_to_the_expiry_date(hass, config_entry, freezer):
    freezer.move_to("2027-01-04 09:00:00+02:00")

    await setup_entry(hass, config_entry, [vignette_record()])

    assert hass.states.get(ENTITY_ID).state == "10"


async def test_attributes_describe_the_vignette(hass, config_entry, freezer):
    freezer.move_to("2027-01-04 09:00:00+02:00")

    await setup_entry(hass, config_entry, [vignette_record()])

    attributes = hass.states.get(ENTITY_ID).attributes
    assert attributes["plate_number"] == PLATE
    assert attributes["valid_from"] == "2026-01-15"
    assert attributes["valid_until"] == "2027-01-14"
    assert attributes["emission_standard"] == "Nu se aplică"
    assert attributes["price"] == 254.78


async def test_no_vignette_reads_zero_rather_than_unknown(hass, config_entry):
    await setup_entry(hass, config_entry, [])

    state = hass.states.get(ENTITY_ID)
    assert state.state == "0"
    assert state.attributes["valid_until"] is None


async def test_an_expired_vignette_reads_zero(hass, config_entry, freezer):
    freezer.move_to("2027-02-01 09:00:00+02:00")

    await setup_entry(hass, config_entry, [vignette_record()])

    assert hass.states.get(ENTITY_ID).state == "0"


async def test_the_last_day_of_validity_is_zero_not_negative(hass, config_entry, freezer):
    freezer.move_to("2027-01-14 09:00:00+02:00")

    await setup_entry(hass, config_entry, [vignette_record()])

    assert hass.states.get(ENTITY_ID).state == "0"


async def test_the_countdown_ticks_at_local_midnight_without_polling(hass, config_entry, freezer):
    freezer.move_to("2027-01-04 23:59:50+02:00")
    await setup_entry(hass, config_entry, [vignette_record()])
    assert hass.states.get(ENTITY_ID).state == "10"

    freezer.move_to("2027-01-05 00:00:01+02:00")
    async_fire_time_changed(hass, dt_util.now() + timedelta(seconds=1))
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == "9"
