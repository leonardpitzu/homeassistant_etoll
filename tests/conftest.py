"""Fixtures for the eToll rovinietă tests.

Every vehicle detail here is invented. Nothing real belongs in a public repo.
"""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.etoll.const import (
    CONF_CERTIFICATE_SERIES,
    CONF_PLATE_NUMBER,
    CONF_VIN,
    DOMAIN,
)

PLATE = "B123ABC"
VIN = "WVWZZZ1JZXW000001"
SERIES = "B00000000X"

pytest_plugins = "pytest_homeassistant_custom_component"

# A fixed "now" for the coordinator tests, with windows bracketing it.
NOW = "2026-06-01T12:00:00Z"
VALID_FROM = "2026-01-15T08:00:00Z"
VALID_UNTIL = "2027-01-14T21:59:59.999Z"
VALID_UNTIL_EARLIER = "2026-09-14T20:59:59.999Z"
PAST_UNTIL = "2026-03-14T21:59:59.999Z"
FUTURE_FROM = "2026-10-01T08:00:00Z"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom integrations in every test."""
    return


def vignette_record(
    start: str = VALID_FROM,
    stop: str = VALID_UNTIL,
    series: str | None = None,
    category: str = "Autoturism (maxim 8 + 1 locuri)",
    emission: str = "Nu se aplică",
    price: float = 254.78,
) -> dict:
    """Build a /vignettes/search record with the fields the parser reads."""
    return {
        "licensePlateNumber": PLATE,
        "vin": VIN,
        "validityStartDate": start,
        "validityEndDate": stop,
        "series": series,
        "vehicleCategory": category,
        "emissionStandardsCategory": emission,
        "price": price,
    }


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a config entry for one vehicle."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Rovinietă {PLATE}",
        unique_id=PLATE,
        data={
            CONF_PLATE_NUMBER: PLATE,
            CONF_VIN: VIN,
            CONF_CERTIFICATE_SERIES: SERIES,
        },
    )


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry, records: list[dict]) -> None:
    """Set up the integration with a canned search answer."""
    entry.add_to_hass(hass)
    with patch(
        "custom_components.etoll.coordinator.EtollApi.async_get_vignettes",
        return_value=records,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
