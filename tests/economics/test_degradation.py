from datetime import datetime, timedelta

import pytest

from database import DatabaseManager
from economics.degradation import estimate_bess_degradation
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