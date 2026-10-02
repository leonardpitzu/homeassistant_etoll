"""Client for the anonymous portal.etoll.ro vignette (rovinietă) lookup.

No account, no credentials: a captcha is solved to open a session, then the
vignette history for one plate + VIN + registration-certificate series is read
back. Every request costs one captcha, and the portal only re-serves a cached
answer for the exact same query within a short window, so each poll solves a
fresh image. Validation runs captcha → plate → VIN/certificate, so an HTTP 400
always means the captcha and an HTTP 500 means the vehicle details.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

import aiohttp
from homeassistant.core import HomeAssistant

from .captcha_ocr import solve_captcha
from .const import (
    API_URL,
    MAX_CAPTCHA_ATTEMPTS,
    PAGE_SIZE,
    REST_CAPTCHA,
    REST_SEARCH,
)
from .exceptions import (
    EtollApiError,
    EtollCaptchaError,
    EtollConnectionError,
    EtollVehicleMismatchError,
)

_LOGGER = logging.getLogger(__name__)

# portal.etoll.ro sits behind a bot-aware front end; a browser-like UA keeps the
# request looking like the one the public page makes.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

# HTTP 500 messages (lang=en) that mean the registry is briefly down — retry later.
_TRANSIENT_MARKERS = (
    "unavailable",
    "timeout",
    "timed out",
    "temporar",
    "try again",
)
# HTTP 500 messages that mean the stored vehicle details are wrong — ask the user.
_MISMATCH_MARKERS = (
    "does not match",
    "no vehicle found",
    "not found",
)


class EtollApi:
    """Read vignette records for a single vehicle."""

    def __init__(self, hass: HomeAssistant, session: aiohttp.ClientSession) -> None:
        """Store the session whose cookie jar carries the captcha session."""
        self._hass = hass
        self._session = session

    async def async_get_vignettes(
        self, plate_number: str, vin: str, certificate_series: str
    ) -> list[dict[str, Any]]:
        """Return every vignette the portal knows for this vehicle.

        An empty list means the lookup succeeded and the vehicle has no vignettes
        on record — not that the lookup failed.
        """
        last_error: Exception | None = None

        for attempt in range(1, MAX_CAPTCHA_ATTEMPTS + 1):
            try:
                return await self._async_attempt(plate_number, vin, certificate_series)
            except EtollCaptchaError as err:
                _LOGGER.debug("Captcha attempt %d/%d failed: %s", attempt, MAX_CAPTCHA_ATTEMPTS, err)
                last_error = err

        raise EtollApiError(f"Captcha not solved in {MAX_CAPTCHA_ATTEMPTS} attempts: {last_error}")

    async def _async_attempt(
        self, plate_number: str, vin: str, certificate_series: str
    ) -> list[dict[str, Any]]:
        """Solve one captcha and run the search with it."""
        image = await self._async_fetch_captcha()
        try:
            captcha = await self._hass.async_add_executor_job(solve_captcha, image)
        except ValueError as err:
            raise EtollCaptchaError(f"OCR failed: {err}") from err

        if len(captcha) < 3:
            raise EtollCaptchaError(f"OCR returned unusable text: {captcha!r}")

        body = {
            "licensePlateNumber": plate_number,
            "vin": vin,
            "registrationDocumentSeries": certificate_series,
            "startDate": None,
            "stopDate": None,
            "captchaCode": captcha,
        }
        return await self._async_search(body)

    async def _async_fetch_captcha(self) -> bytes:
        """Fetch a captcha image, which also (re)arms the session cookies."""
        url = self._rest_url(REST_CAPTCHA, "GET")
        try:
            async with self._session.get(url, headers=_HEADERS) as response:
                response.raise_for_status()
                return await response.read()
        except aiohttp.ClientError as err:
            raise EtollConnectionError(f"Could not fetch captcha: {err}") from err

    async def _async_search(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        """POST the search and turn the portal's answer into a record list."""
        url = self._rest_url(REST_SEARCH, "POST", page="0", size=str(PAGE_SIZE))
        try:
            async with self._session.post(url, json=body, headers=_HEADERS) as response:
                status = response.status
                text = await response.text()
        except aiohttp.ClientError as err:
            raise EtollConnectionError(f"Search request failed: {err}") from err

        payload: dict[str, Any] = {}
        if text:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    payload = parsed
            except ValueError:
                payload = {}

        if status == 200:
            return payload.get("content") or []

        message = str(payload.get("message", "")).strip()

        # Validation order guarantees a 400 is always the captcha.
        if status == 400:
            raise EtollCaptchaError(message or "Captcha rejected")

        lowered = message.lower()
        if any(marker in lowered for marker in _TRANSIENT_MARKERS):
            raise EtollApiError(f"Registry temporarily unavailable: {message}")
        if any(marker in lowered for marker in _MISMATCH_MARKERS):
            raise EtollVehicleMismatchError(message)
        # Unknown 5xx: retrying next poll is safer than forcing the user to reauth.
        raise EtollApiError(message or f"Lookup failed (HTTP {status})")

    @staticmethod
    def _rest_url(rest_path: str, rest_method: str, **extra: str) -> str:
        """Build the portlet resource URL for one REST call."""
        params = {"rest_path": rest_path, "rest_method": rest_method, "lang": "en", **extra}
        query = "&".join(f"{key}={quote(str(value), safe='')}" for key, value in params.items())
        return f"{API_URL}&{query}"
