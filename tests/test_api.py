"""Tests for the anonymous portal.etoll.ro client."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from custom_components.etoll.api import EtollApi
from custom_components.etoll.const import MAX_CAPTCHA_ATTEMPTS
from custom_components.etoll.exceptions import (
    EtollApiError,
    EtollCaptchaError,
    EtollConnectionError,
    EtollVehicleMismatchError,
)

from .conftest import PLATE, SERIES, VIN, vignette_record

# Both the captcha (GET) and the search (POST) hit this one portlet URL; the
# matcher ignores the query string, so method alone tells them apart.
PORTAL = "https://portal.etoll.ro/web/guest/verificare-rovinieta"


def _captcha_calls(aioclient_mock) -> int:
    return sum(call[0] == "GET" for call in aioclient_mock.mock_calls)


@pytest.fixture
async def api(hass: HomeAssistant, aioclient_mock) -> EtollApi:
    """Return a client bound to the mocked session."""
    return EtollApi(hass, async_create_clientsession(hass))


@pytest.fixture(autouse=True)
def solved_captcha():
    """Skip the OCR itself — ddddocr is not what these tests cover."""
    with patch("custom_components.etoll.api.solve_captcha", return_value="bjtQR"):
        yield


async def test_returns_the_record_list(api, aioclient_mock):
    aioclient_mock.get(PORTAL, content=b"image")
    aioclient_mock.post(PORTAL, json={"content": [vignette_record()]})

    records = await api.async_get_vignettes(PLATE, VIN, SERIES)

    assert len(records) == 1


async def test_no_vignettes_is_an_empty_list_not_an_error(api, aioclient_mock):
    aioclient_mock.get(PORTAL, content=b"image")
    aioclient_mock.post(PORTAL, json={"content": []})

    assert await api.async_get_vignettes(PLATE, VIN, SERIES) == []


async def test_a_rejected_captcha_is_retried(api):
    attempt = patch.object(
        EtollApi,
        "_async_attempt",
        side_effect=[EtollCaptchaError("misread"), [vignette_record()]],
    )
    with attempt as mocked:
        records = await api.async_get_vignettes(PLATE, VIN, SERIES)

    assert len(records) == 1
    assert mocked.call_count == 2


async def test_giving_up_after_the_retry_budget(api, aioclient_mock):
    aioclient_mock.get(PORTAL, content=b"image")
    aioclient_mock.post(PORTAL, json={"message": "Captcha incorrect or expired."}, status=400)

    with pytest.raises(EtollApiError):
        await api.async_get_vignettes(PLATE, VIN, SERIES)

    assert _captcha_calls(aioclient_mock) == MAX_CAPTCHA_ATTEMPTS


async def test_a_mismatch_is_reported_and_not_retried(api, aioclient_mock):
    aioclient_mock.get(PORTAL, content=b"image")
    aioclient_mock.post(
        PORTAL,
        json={"message": "Vehicle registration certificate does not match the vehicle records."},
        status=500,
    )

    with pytest.raises(EtollVehicleMismatchError):
        await api.async_get_vignettes(PLATE, VIN, SERIES)

    assert _captcha_calls(aioclient_mock) == 1


async def test_a_transient_server_error_is_not_a_mismatch(api, aioclient_mock):
    aioclient_mock.get(PORTAL, content=b"image")
    aioclient_mock.post(PORTAL, json={"message": "Service temporarily unavailable."}, status=500)

    with pytest.raises(EtollApiError) as caught:
        await api.async_get_vignettes(PLATE, VIN, SERIES)

    assert not isinstance(caught.value, EtollVehicleMismatchError)
    assert _captcha_calls(aioclient_mock) == 1


async def test_an_unreachable_portal_raises_a_connection_error(api, aioclient_mock):
    aioclient_mock.get(PORTAL, status=503)

    with pytest.raises(EtollConnectionError):
        await api.async_get_vignettes(PLATE, VIN, SERIES)
