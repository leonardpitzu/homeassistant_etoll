"""Constants for the eToll rovinietă integration."""

from datetime import timedelta

DOMAIN = "etoll"

# The vignette check is an Angular app inside a Liferay portlet. Every REST call
# goes to this single resource URL, with the real path and verb passed as query
# parameters (?rest_path=…&rest_method=…). lang=en makes the portal answer with
# English error messages, which the client classifies on.
PORTLET_ID = "digitalizeportlet_WAR_digitalizeportlet_INSTANCE_xhif"
API_URL = (
    "https://portal.etoll.ro/web/guest/verificare-rovinieta"
    f"?p_p_id={PORTLET_ID}"
    "&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view"
    "&p_p_cacheability=cacheLevelPage"
)
REST_CAPTCHA = "/api/captcha"
REST_SEARCH = "/vignettes/search"

CONF_PLATE_NUMBER = "plate_number"
CONF_VIN = "vin"
CONF_CERTIFICATE_SERIES = "certificate_series"

# A vehicle has a handful of vignettes at most, so one page covers it.
PAGE_SIZE = 50

UPDATE_INTERVAL = timedelta(hours=12)

# A miss costs only another captcha image, and the local OCR reads a full
# five-glyph captcha right ~57% of the time, so retry generously.
MAX_CAPTCHA_ATTEMPTS = 10

ATTRIBUTION = "Data provided by portal.etoll.ro (CNAIR Romania)"
