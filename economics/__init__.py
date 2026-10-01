"""
Economic layer for the PyPort Sim extension (Master's thesis, Cristian Romeo).

This package is deliberately kept OUTSIDE PyPort's own packages (models/,
simulation/, optimization/, database/, forecasting/, weather/, config/). It
only ever imports from them or reads/writes through DatabaseManager's public
methods (save_metric, save_records_batch, get_records, get_connection, ...);
it never edits their source. This mirrors the non-invasive / extensibility
NFR described in Chapter 4 and the three integration points identified by
reading the actual pyport_sim source (see the thesis's Chapter 3 footnotes):

1. metrics.py        -> new EAV `metric` rows (CAPEX/OPEX/degradation/tariff
                         cost), inserted via DatabaseManager.save_metric,
                         never by editing database/db_manager.py.
2. tariff_seasonal.py -> picks which seasonal tariff JSON to pass as
                         Port(tariff_path=...) BEFORE instantiating Port,
                         instead of modifying Port._load_tariff /
                         get_tariff_price (which only understand a flat
                         day-of-week/time-of-day JSON, not EEM's Period
                         I-IV quarters).
3. degradation.py     -> a post-processor that reads BESS charge/discharge
                         history back out of the `measurements` table after
                         a run and estimates cycle-based degradation, since
                         models/bess.py has no degradation logic at all.

Everything here is a *first working skeleton*: the physics/finance are
correct in shape (same equations as Chapter 2), but several numeric
parameters are placeholders pulled from the data inventory
(data_variable_inventory_EN.xlsx) and are marked TODO where a Funchal-
specific / quoted value should replace them.
"""

from .metrics import ECONOMIC_METRICS, register_economic_metrics
from .capex_opex import lcos, annual_cost
from .tariff_seasonal import get_seasonal_tariff_path, EEM_PERIODS
from .degradation import estimate_bess_degradation

__all__ = [
    "ECONOMIC_METRICS",
    "register_economic_metrics",
    "lcos",
    "annual_cost",
    "get_seasonal_tariff_path",
    "EEM_PERIODS",
    "estimate_bess_degradation",
]