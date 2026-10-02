# eToll Rovinietă for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A custom [Home Assistant](https://www.home-assistant.io/) integration that tells you how many days of Romanian road tax (*rovinietă*) your vehicle has left, so you find out before the police do.

**No account, no password, no personal data.** The vignette is looked up the same anonymous way the public [portal.etoll.ro](https://portal.etoll.ro/web/guest/verificare-rovinieta) page does it — plate number, VIN and the registration-certificate series, nothing else. Integrations that log into your CNAIR account can read your name, CNP, phone number and home address; this one has no credentials to read them with.

> **Replaces the old eRovinieta integration.** CNAIR retired `erovinieta.ro` and moved the check to `portal.etoll.ro`, which uses a different API and now also requires the registration-certificate series. This is a new integration with the `etoll` domain — if you ran the previous `erovinieta` one, remove it and add this one per vehicle.

## Features

### Days remaining

One entity per vehicle:

| Entity | State | Unit |
|---|---|---|
| `sensor.rovinieta_<plate>_days_remaining` | Whole days until the vignette stops being valid | `d` |

with the vignette it is counting down on its attributes:

```yaml
plate_number: B123ABC
valid_from: "2026-03-12"
valid_until: "2027-03-11"
vignette_series: null
vehicle_category: Autoturism (maxim 8 + 1 locuri)
emission_standard: Nu se aplică
price: 254.78
```

That is the whole integration. One number is what an automation can threshold on natively and what a tile can show, and the dates that give it meaning travel with it.

### Zero means "no valid rovinietă", and it is not a guess

A vehicle with no vignette — expired, cancelled, or never bought — reads `0`, because zero is genuinely how many days of validity it has left. That matters more than it sounds: a `numeric_state` trigger does **not** fire on `unknown`, so a sensor that went blank in exactly that situation would stay silent in the one case you actually need shouting about.

`unavailable` is kept for what it means: the lookup failed. Silence from CNAIR is never reported as good news.

The portal returns every vignette on file, so the integration keeps the one that is in force right now (today falls between its start and end dates), and among those the one that runs longest.

### The countdown ticks at midnight, not at the poll

Days remaining is derived from a date. Asking CNAIR whether a day has passed would be absurd, so the sensor re-publishes itself at local midnight and the portal is only polled — twice a day — for the expiry date itself.

That also means the number changes at 00:00 Europe/Bucharest, which is when a reminder automation starts counting the new figure.

## Installation

### HACS (recommended)

1. In HACS, add this repository as a **custom repository** with category **Integration**.
2. Search for **eToll Rovinietă** and download it.
3. Restart Home Assistant.

### Manual

1. Copy `custom_components/etoll` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

## Configuration

Add the integration from **Settings → Devices & Services → Add Integration → eToll Rovinietă**, once per vehicle:

| Field | Description |
|---|---|
| Plate number | Registration plate, e.g. `B123ABC` |
| VIN | Chassis number, exactly as printed on the registration certificate |
| Registration certificate series | The series of the registration certificate (*talon*), e.g. `AB123456` |

All three are checked against the national vehicle registry (DGPCI), and all three must match — the plate finds the vehicle, the VIN and certificate series confirm it. If they do not match, the setup says so instead of guessing.

There are no options to set. The poll interval is fixed at 12 hours because a vignette changes a handful of times a year, and the reminder threshold belongs to the automation that does the reminding, not to the vehicle.

If the registry later stops recognising the stored details — for example after the certificate is reissued — the integration raises a repair/re-auth prompt asking for the certificate series again, rather than silently going `unavailable`. You can also edit any of the three fields from the integration's **Reconfigure** entry.

## Dashboard

Everything fits on one tile, because the dates are attributes of the countdown:

```yaml
type: tile
entity: sensor.rovinieta_b123abc_days_remaining
name: Rovinietă
state_content:
  - state
  - valid_from
  - valid_until
```

## Reminders

`blueprints/automation/rovinieta.yaml` ships with the repository: one automation per vehicle, which nags on a schedule while the vignette is running out and stops on its own the moment you pay — the number jumps back up, the condition goes false, nothing to reset.

| Input | Default | Meaning |
|---|---|---|
| Vignette sensor | – | The vehicle's `days_remaining` sensor |
| Vehicle name | – | What to call the car in the message |
| Notify targets | – | One or more `notify` entities |
| Remind below | `15` | Start reminding when fewer days than this are left |
| Escalate below | `5` | Below this, remind every hour instead of every three |

Reminders land between 09:00 and 20:00: at 09:00, 12:00, 15:00 and 18:00 normally, every hour once it is urgent. Both thresholds are *below* values, so the defaults mean "from 14 days out" and "hourly from 4 days out".

It also watches its own blind spot: if the sensor sits `unavailable` or `unknown` for 48 hours, it says so. A reminder system that goes quiet because it broke is worse than no reminder system.

## How the lookup works

All of this was established against the live service rather than inferred:

- The check is an Angular app inside a Liferay portlet. Every REST call goes to one resource URL with the real path and verb as query parameters: `GET …&rest_path=/api/captcha` returns the captcha image and arms the session, and `POST …&rest_path=/vignettes/search` reads the vehicle's vignette history back. `lang=en` makes the portal answer with English error messages, which the client classifies on.
- The captcha is five **case-sensitive** characters (`A-Z a-z 2-9`; the ambiguous `0 1 O I l o s` are not used) in a distorted, hand-drawn font. It is read on-device by a small nearest-neighbour matcher built into the integration — each captcha is split into its five glyphs and matched against a bundled gallery of labelled samples. **No dependencies** (Pillow and numpy already ship with Home Assistant), no OCR service, no API key; nothing leaves the machine. Per-character accuracy is ~87%.
- The portal scores each captcha image once and only caches a result for the exact same query for a short window, so a fresh captcha is solved on every poll. A full five-glyph read succeeds ~57% of the time, so a rejected captcha (`HTTP 400`) is retried with a fresh image up to ten times, which makes a successful read all but certain.
- A business error comes back as `HTTP 500` with a message: a plate/VIN/certificate mismatch is treated as "fix the details" (it triggers re-auth), while a transient registry outage is treated as a temporary failure and retried on the next poll.
- The `series` field on a record is the **vignette** series (often empty), not the registration-certificate series you enter at setup. They are not interchangeable.

## Privacy

The plate number, VIN and certificate series go to portal.etoll.ro and nowhere else, which is the same request your browser makes on the public page. Nothing is stored beyond the config entry, no credentials exist to be leaked, and both the VIN and the certificate series are redacted from diagnostics.

## Differences from the original

The original integration was built on the retired `erovinieta.ro` API and exposed four sensors built around the payment — days remaining, expiry date, payment total and payer name. This one keeps the countdown and drops the rest: the price travels as an attribute, and the payer name came back as `-` for one of my own vehicles, which is a sensor reporting punctuation.

Beyond the sensor set:

- Built on the current `portal.etoll.ro` API, with the registration-certificate series as a third required field, re-auth when the details stop matching, and a reconfigure step.
- Typed `entry.runtime_data` instead of `hass.data`, `DeviceInfo` instead of a hand-rolled dict, and translated entity names instead of f-strings.
- The captcha OCR runs locally in the executor rather than on the event loop or through a service.
- A proper numeric sensor instead of a custom event: a native `numeric_state` trigger does the thresholding, and it survives a restart.
- Tests, `ruff`, and the countdown's midnight recompute.

## Credits

Original integration by [@emanuelbesliu](https://github.com/emanuelbesliu). The anonymous lookup this is built on is the one [portal.etoll.ro](https://portal.etoll.ro/web/guest/verificare-rovinieta) offers publicly; this project is independent of CNAIR and not affiliated with it.

## License

[MIT](LICENSE), inherited from upstream and kept there — a fork cannot relicense the work it derives from, only its own modifications, and the upstream copyright line stays for that reason.
