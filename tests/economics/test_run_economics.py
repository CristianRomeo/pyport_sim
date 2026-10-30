"""Tests for the grid-cost helpers in economics/run_economics.py (price above a power threshold)."""

import json

import pytest

from economics.run_economics import compute_grid_energy_cost, grid_cost_split, grid_peak_kw


class FakeDb:
    """Just the three DatabaseManager calls the cost helpers use."""

    def __init__(self, powers, start="2025-01-13T00:00:00"):
        from datetime import datetime, timedelta

        t0 = datetime.fromisoformat(start)
        self.rows = [
            {"timestamp": (t0 + timedelta(minutes=15 * i)).isoformat(), "value": str(p)}
            for i, p in enumerate(powers)
        ]

    def get_source(self, source_name):
        return {"source_id": 1} if source_name == "Funchal" else None

    def get_metric_id(self, name):
        return 7

    def get_records(self, table, source_id, metric_id):
        return self.rows


@pytest.fixture
def tariff_path(tmp_path):
    """Flat 0.20 EUR/kWh every day (the 2025-01-13 test week starts on a Monday)."""
    slots = {f"{h:02d}:{m:02d}": 0.20 for h in range(24) for m in (0, 15, 30, 45)}
    data = {"tariff": {str(d): {"pricing": slots} for d in range(7)}}
    path = tmp_path / "flat.json"
    path.write_text(json.dumps(data))
    return str(path)


# Powers 60, 100, 160 kW for 15 minutes each (the last row only closes the third interval).
POWERS = [60, 100, 160, 0]


def test_cost_without_threshold_is_plain_energy_times_price(tariff_path):
    series = compute_grid_energy_cost(FakeDb(POWERS), "Funchal", tariff_path)
    assert sum(c for _, c in series) == pytest.approx((60 + 100 + 160) * 0.25 * 0.20)


def test_split_reports_energy_and_cost_above_threshold(tariff_path):
    total, excess_cost, excess_kwh = grid_cost_split(FakeDb(POWERS), "Funchal", tariff_path, 80)
    assert total == pytest.approx(16.0)
    assert excess_kwh == pytest.approx((0 + 20 + 80) * 0.25)
    assert excess_cost == pytest.approx(excess_kwh * 0.20)


def test_surcharge_factor_applies_only_above_threshold(tariff_path):
    series = compute_grid_energy_cost(
        FakeDb(POWERS), "Funchal", tariff_path, excess_threshold_kw=80, excess_price_factor=2.0)
    assert sum(c for _, c in series) == pytest.approx(16.0 + 5.0)


def test_one_split_answers_every_factor(tariff_path):
    total, excess_cost, _ = grid_cost_split(FakeDb(POWERS), "Funchal", tariff_path, 80)
    for factor in (1.0, 1.5, 3.0):
        direct = sum(c for _, c in compute_grid_energy_cost(
            FakeDb(POWERS), "Funchal", tariff_path, 80, factor))
        assert total + (factor - 1.0) * excess_cost == pytest.approx(direct)


def test_factor_one_changes_nothing(tariff_path):
    plain = sum(c for _, c in compute_grid_energy_cost(FakeDb(POWERS), "Funchal", tariff_path))
    same = sum(c for _, c in compute_grid_energy_cost(
        FakeDb(POWERS), "Funchal", tariff_path, 80, 1.0))
    assert plain == pytest.approx(same)


def test_unknown_source_raises(tariff_path):
    with pytest.raises(ValueError):
        grid_cost_split(FakeDb(POWERS), "Nope", tariff_path, 80)


def test_peak_is_highest_logged_power(tariff_path):
    assert grid_peak_kw(FakeDb(POWERS), "Funchal", tariff_path) == 160.0


def test_peak_unknown_source_raises(tariff_path):
    with pytest.raises(ValueError):
        grid_peak_kw(FakeDb(POWERS), "Nope", tariff_path)