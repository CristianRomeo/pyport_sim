from datetime import datetime, timedelta

import pytest

from database import DatabaseManager
from economics.degradation import estimate_bess_degradation, bess_life_years_from_run
from economics.metrics import register_economic_metrics


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_run.db"
    manager = DatabaseManager(str(db_path))
    manager.initialize_schema()
    manager.initialize_default_metrics()
    register_economic_metrics(manager)
    return manager


def _log_constant_power(db, source_name, metric_name, power_kw, n_steps, dt_seconds=900):
    source_id = db.get_or_create_source(source_name, "bess")
    metric_id = db.get_metric_id(metric_name)
    start = datetime(2026, 9, 1, 0, 0, 0)
    records = []
    for i in range(n_steps):
        ts = (start + timedelta(seconds=i * dt_seconds)).isoformat()
        records.append((ts, source_id, metric_id, str(power_kw)))
    db.save_records_batch("measurements", records)


def test_estimate_bess_degradation_basic(db):
    # 10 kW discharge for 10 steps of 15 min = 10 * (10*0.25) = 25 kWh discharged
    _log_constant_power(db, "Battery_Storage_1", "bess_discharge", power_kw=10.0, n_steps=10)
    _log_constant_power(db, "Battery_Storage_1", "bess_charge", power_kw=0.0, n_steps=10)

    result = estimate_bess_degradation(db, "Battery_Storage_1", capacity_kwh=100.0)

    assert result.total_discharge_kwh == pytest.approx(9 * 0.25 * 10.0)  # 9 intervals between 10 points
    assert result.equivalent_full_cycles > 0
    assert 0.0 < result.estimated_soh <= 1.0
    assert result.remaining_cycles_to_eol >= 0


def test_estimate_bess_degradation_missing_source_raises(db):
    with pytest.raises(ValueError):
        estimate_bess_degradation(db, "NoSuchBattery", capacity_kwh=100.0)


def test_bess_life_is_capped_by_calendar_life_when_barely_used(db):
    _log_constant_power(db, "Funchal", "bess_discharge", power_kw=1.0, n_steps=10)
    _log_constant_power(db, "Funchal", "bess_charge", power_kw=0.0, n_steps=10)
    life = bess_life_years_from_run(db, "Funchal", 200.0, days_simulated=7, calendar_life_years=15.0)
    assert life == pytest.approx(15.0)


def test_bess_life_is_shorter_with_heavier_cycling(db):
    # 100 kW over 9 intervals of 15 min = 225 kWh = 2.25 cycles of 100 kWh in "7 days"
    _log_constant_power(db, "Funchal", "bess_discharge", power_kw=100.0, n_steps=10)
    _log_constant_power(db, "Funchal", "bess_charge", power_kw=0.0, n_steps=10)
    heavy = bess_life_years_from_run(db, "Funchal", 100.0, days_simulated=7, calendar_life_years=50.0)
    # 2.25 cycles/week -> ~117 cycles/year -> 3000 cycles to 80% health -> ~25.6 years
    assert heavy == pytest.approx(3000 / (2.25 * 365 / 7), rel=1e-6)
    assert heavy < 50.0


def test_bess_life_without_any_cycling_is_calendar_life(db):
    _log_constant_power(db, "Funchal", "bess_discharge", power_kw=0.0, n_steps=10)
    _log_constant_power(db, "Funchal", "bess_charge", power_kw=0.0, n_steps=10)
    assert bess_life_years_from_run(db, "Funchal", 200.0, calendar_life_years=12.0) == pytest.approx(12.0)


def test_bess_life_from_weeks_matches_single_week(db):
    from economics.degradation import bess_life_years_from_weeks

    _log_constant_power(db, "Funchal", "bess_discharge", power_kw=100.0, n_steps=10)
    _log_constant_power(db, "Funchal", "bess_charge", power_kw=0.0, n_steps=10)
    single_week = bess_life_years_from_run(db, "Funchal", 100.0, days_simulated=7, calendar_life_years=50.0)
    year_weeks = 365.0 / 7.0
    # the same week standing for the whole year, or split into two halves
    assert bess_life_years_from_weeks([(db, year_weeks)], "Funchal", 100.0, 50.0) == pytest.approx(single_week)
    assert bess_life_years_from_weeks(
        [(db, year_weeks / 2), (db, year_weeks / 2)], "Funchal", 100.0, 50.0
    ) == pytest.approx(single_week)


def test_bess_life_from_weeks_without_cycling_is_calendar_life(db):
    from economics.degradation import bess_life_years_from_weeks

    _log_constant_power(db, "Funchal", "bess_discharge", power_kw=0.0, n_steps=10)
    _log_constant_power(db, "Funchal", "bess_charge", power_kw=0.0, n_steps=10)
    assert bess_life_years_from_weeks([(db, 52.0)], "Funchal", 200.0, 12.0) == pytest.approx(12.0)