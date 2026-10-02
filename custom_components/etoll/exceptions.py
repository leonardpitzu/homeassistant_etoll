"""Exceptions for the eToll rovinietă integration."""

from homeassistant.exceptions import HomeAssistantError


class EtollError(HomeAssistantError):
    """Base exception for the integration."""


class EtollApiError(EtollError):
    """The portal answered, but not with usable data."""


class EtollCaptchaError(EtollApiError):
    """The captcha was misread or rejected. Retriable with a fresh image."""


class EtollVehicleMismatchError(EtollApiError):
    """Plate, VIN and certificate series do not identify a single vehicle.

    Not retriable: the stored details are wrong, so the user has to fix them.
    """


class EtollConnectionError(EtollError):
    """portal.etoll.ro could not be reached."""
