from datetime import date
import json

import pytest

from economics.tariff_seasonal import (
    get_eem_period,
    get_seasonal_tariff_path,
    generate_tariff_json,
    EEM_PERIODS,
)


@pytest.mark.parametrize(
    "d,expected_period",
    [
        (date(2026, 1, 15), "I"),
        (date(2026, 3, 31), "I"),
        (date(2026, 4, 1), "II"),
        (date(2026, 6, 30), "II"),
        (date(2026, 7, 1), "III"),
        (date(2026, 9, 27), "III"),  # the day of the Seaborn/TRP-01 recording
        (date(2026, 10, 1), "IV"),
        (date(2026, 12, 31), "IV"),
    ],
)
def test_get_eem_period(d, expected_period):
    assert get_eem_period(d) == expected_period


def test_all_periods_covered():
    # every month 1-12 must resolve to exactly one period
    months_covered = set()
    for start, end in EEM_PERIODS.values():
        months_covered.update(range(start, end + 1))
    assert months_covered == set(range(1, 13))


def test_generate_and_load_tariff_json(tmp_path):
    out_path = tmp_path / "tariff_period_III.json"
    generate_tariff_json(
        period_prices={
            "peak": 0.1530,
            "full": 0.1408,
            "normal_off_peak": 0.1170,
            "super_off_peak": 0.1029,
        },
        time_bands={
            "peak": [("10:30", "13:00"), ("20:30", "22:00")],
            "super_off_peak": [("02:00", "06:00")],
            "normal_off_peak": [("06:00", "09:00"), ("23:00", "23:59")],
        },
        out_path=str(out_path),
    )

    assert out_path.exists()
    with open(out_path) as f:
        data = json.load(f)

    # Monday, peak band
    assert data["tariff"]["0"]["pricing"]["11:00"] == 0.153
    # Monday, super off-peak band
    assert data["tariff"]["0"]["pricing"]["03:00"] == 0.1029


def test_get_seasonal_tariff_path_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        get_seasonal_tariff_path(date(2026, 7, 1), tariff_dir=str(tmp_path))