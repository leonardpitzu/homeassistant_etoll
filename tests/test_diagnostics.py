"""Tests for the diagnostics download."""

from freezegun import freeze_time
from homeassistant.components.diagnostics import REDACTED

from custom_components.etoll.diagnostics import async_get_config_entry_diagnostics

from .conftest import NOW, PLATE, setup_entry, vignette_record


@freeze_time(NOW)
async def test_identifiers_never_leave_the_instance(hass, config_entry):
    await setup_entry(hass, config_entry, [vignette_record(series="1234567890")])

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    assert diagnostics["config_entry"]["vin"] == REDACTED
    assert diagnostics["config_entry"]["certificate_series"] == REDACTED
    assert diagnostics["config_entry"]["plate_number"] == PLATE
    assert diagnostics["vignette"]["series"] == REDACTED


@freeze_time(NOW)
async def test_a_vehicle_without_a_vignette_reports_none(hass, config_entry):
    await setup_entry(hass, config_entry, [])

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    assert diagnostics["vignette"] is None
    assert diagnostics["last_update_success"] is True
