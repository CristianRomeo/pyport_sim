# tests/economics/test_metrics.py
from database import DatabaseManager
from economics.metrics import ECONOMIC_METRICS, register_economic_metrics


def _make_db(tmp_path):
    db_path = tmp_path / "test.db"
    manager = DatabaseManager(str(db_path))
    manager.initialize_schema()
    manager.initialize_default_metrics()
    return manager


def test_register_economic_metrics_inserts_all(tmp_path):
    db = _make_db(tmp_path)
    register_economic_metrics(db)

    all_metrics = {row["metric_name"] for row in db.get_all_metrics()}
    for metric_name, _, _ in ECONOMIC_METRICS:
        assert metric_name in all_metrics


def test_register_economic_metrics_is_idempotent(tmp_path):
    db = _make_db(tmp_path)
    register_economic_metrics(db)
    register_economic_metrics(db)  # calling twice must not raise / duplicate

    all_metrics = [row["metric_name"] for row in db.get_all_metrics()]
    assert len(all_metrics) == len(set(all_metrics))  # no duplicates


def test_economic_metrics_do_not_collide_with_pyport_defaults():
    from database.db_manager import DEFAULT_METRICS

    pyport_names = {name for name, _, _ in DEFAULT_METRICS}
    economic_names = {name for name, _, _ in ECONOMIC_METRICS}
    assert pyport_names.isdisjoint(economic_names)