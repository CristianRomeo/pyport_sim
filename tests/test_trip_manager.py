"""
TripManager seasonal/holiday trip-count logic.

Replaces the previous weekday-based rule (2 trips Mon-Fri, 1 Saturday, 0
Sunday - a commercial-fleet pattern, backwards for a recreational marina)
with a season + public-holiday based rule: TRIPS_HIGH_SEASON if the date
falls in a high-season month OR is a Portugal/Madeira public holiday,
TRIPS_LOW_SEASON otherwise. No day of the week is ever zeroed out.
"""

from datetime import date, datetime

from simulation.trip_manager import TripManager


def test_num_trips_high_season_weekday():
    tm = TripManager()
    # Monday, 1 September 2025 - high season month.
    assert tm._num_trips_for_date(datetime(2025, 9, 1)) == TripManager.TRIPS_HIGH_SEASON


def test_num_trips_high_season_sunday_is_not_zero():
    # Regression test: Sunday, 7 September 2025 used to get 0 trips under the
    # old weekday rule (the "grid cost = EUR 0.00 on the last day" anomaly).
    tm = TripManager()
    assert tm._num_trips_for_date(datetime(2025, 9, 7)) == TripManager.TRIPS_HIGH_SEASON
    assert TripManager.TRIPS_HIGH_SEASON > 0


def test_num_trips_low_season_weekday():
    tm = TripManager()
    # Monday, 5 January 2026 - low season month, not a holiday.
    assert tm._num_trips_for_date(datetime(2026, 1, 5)) == TripManager.TRIPS_LOW_SEASON


def test_num_trips_low_season_public_holiday_is_boosted():
    tm = TripManager()
    # Christmas Day 2025 falls in a low-season month but is a national holiday.
    assert tm._num_trips_for_date(datetime(2025, 12, 25)) == TripManager.TRIPS_HIGH_SEASON


def test_num_trips_madeira_regional_holiday_is_recognized():
    tm = TripManager()
    # 1 July is "Dia da Regiao Autonoma da Madeira", a Madeira-only holiday
    # (not in mainland Portugal's national calendar).
    assert datetime(2026, 7, 1).date() in tm._holidays


def test_dia_da_autonomia_is_recognized_and_boosts_low_season():
    # 2 April: Madeira regional holiday instituted 27/11/2024, not yet in the
    # holidays library's data (v0.106) - manually patched in __init__. Check
    # both that it's recognized AND that it actually boosts a low-season date.
    tm = TripManager()
    assert date(2026, 4, 2) in tm._holidays
    assert tm._num_trips_for_date(datetime(2026, 4, 2)) == TripManager.TRIPS_HIGH_SEASON


def test_num_trips_never_zero_across_a_full_year():
    tm = TripManager()
    for month in range(1, 13):
        day = datetime(2026, month, 15)
        assert tm._num_trips_for_date(day) > 0