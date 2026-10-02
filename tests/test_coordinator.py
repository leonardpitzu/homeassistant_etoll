"""Tests for picking the vignette in force."""

from freezegun import freeze_time

from custom_components.etoll.coordinator import _vignette_in_force

from .conftest import (
    FUTURE_FROM,
    NOW,
    PAST_UNTIL,
    VALID_FROM,
    VALID_UNTIL,
    VALID_UNTIL_EARLIER,
    vignette_record,
)


@freeze_time(NOW)
def test_no_records_means_no_vignette():
    assert _vignette_in_force([]) is None


@freeze_time(NOW)
def test_an_expired_record_is_not_in_force():
    assert _vignette_in_force([vignette_record(stop=PAST_UNTIL)]) is None


@freeze_time(NOW)
def test_a_future_record_is_not_in_force():
    assert _vignette_in_force([vignette_record(start=FUTURE_FROM)]) is None


@freeze_time(NOW)
def test_longest_running_in_force_record_wins():
    records = [
        vignette_record(start=VALID_FROM, stop=VALID_UNTIL_EARLIER, series="older"),
        vignette_record(start=VALID_FROM, stop=VALID_UNTIL, series="newer"),
    ]

    vignette = _vignette_in_force(records)

    assert vignette is not None
    assert vignette.series == "newer"


@freeze_time(NOW)
def test_record_without_dates_is_ignored():
    incomplete = vignette_record()
    del incomplete["validityEndDate"]

    assert _vignette_in_force([incomplete]) is None


@freeze_time(NOW)
def test_descriptive_fields_are_carried_over():
    vignette = _vignette_in_force([vignette_record()])

    assert vignette is not None
    assert vignette.category == "Autoturism (maxim 8 + 1 locuri)"
    assert vignette.emission_standard == "Nu se aplică"
    assert vignette.price == 254.78
