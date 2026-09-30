"""
New EAV `metric` definitions for the economic layer.

PyPort's own DEFAULT_METRICS (database/db_manager.py) covers only technical
quantities (power flows, SOC, weather). None of them are cost-related -
confirmed by reading the actual DEFAULT_METRICS tuple grid-energy-only TCO. These are the new metric
rows the economic layer needs; they are inserted through
DatabaseManager.save_metric (public API), never by editing
DEFAULT_METRICS itself.

Each tuple follows the same shape PyPort already uses:
(metric_name, unit, data_type).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from database import DatabaseManager


ECONOMIC_METRICS = (
    # --- Energy cost / revenue (per timestep, matches PyPort's own timestep) ---
    ("grid_energy_cost", "EUR", "float"),          # P_grid(t) * tariff_price(t) * dt/3600
    ("export_revenue", "EUR", "float"),             # exported/curtailed PV valued at GRD-04
    ("pv_self_consumption_value", "EUR", "float"),  # PV used on-site, valued at avoided grid cost
    # --- CAPEX (one-off, logged at t=0 of a scenario run) ---
    ("capex_pv", "EUR", "float"),
    ("capex_bess", "EUR", "float"),
    ("capex_evse", "EUR", "float"),
    ("capex_total", "EUR", "float"),
    # --- OPEX (recurring, logged per accounting period - e.g. daily or yearly) ---
    ("opex_pv", "EUR", "float"),
    ("opex_bess", "EUR", "float"),
    ("opex_evse", "EUR", "float"),
    ("opex_total", "EUR", "float"),
    # --- BESS degradation / lifecycle ---
    ("bess_equivalent_full_cycles", "cycles", "float"),
    ("bess_soh", "%", "float"),
    ("bess_reinvestment_cost", "EUR", "float"),  # CAPEX_re,t in the LCOS formula (Ch.2, Eq. annualcost)
    # --- Lifecycle KPIs (typically one row per scenario, not per timestep) ---
    ("lcos", "EUR/kWh", "float"),
    ("tco_lifecycle", "EUR", "float"),   # broader than PyPort's native TCO (grid energy only)
    ("roi_pv", "%", "float"),
    ("roi_bess", "%", "float"),
)


def register_economic_metrics(db_manager: "DatabaseManager") -> None:
    """
    Insert all ECONOMIC_METRICS into the `metric` table, ignoring duplicates.

    Mirrors DatabaseManager.initialize_default_metrics() but for the new
    economic metrics, using only DatabaseManager's public get_connection()
    context manager - db_manager.py itself is never modified.

    Args:
        db_manager: An already-connected-capable DatabaseManager pointing at
            the SQLite database of a PyPort run (call after
            db_manager.initialize_schema()).
    """
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        for metric_name, unit, data_type in ECONOMIC_METRICS:
            cursor.execute(
                """
                INSERT OR IGNORE INTO metric (metric_name, unit, data_type)
                VALUES (?, ?, ?)
                """,
                (metric_name, unit, data_type),
            )
