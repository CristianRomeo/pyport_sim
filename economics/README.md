# economics/

Techno-economic layer for the marina electrification DSS (Master's thesis,
Cristian Romeo), built on top of PyPort Sim without modifying any of its
existing packages (`models/`, `simulation/`, `optimization/`, `database/`,
`forecasting/`, `weather/`, `config/`).

## Why a separate package

Reading PyPort's actual source (not just its published description)
confirmed three things that shape this design (see Chapter 3's footnotes
in the thesis):

1. `database/db_manager.py`'s `DEFAULT_METRICS` has no cost/CAPEX/OPEX/
   degradation metric at all — the economic layer needs new `metric` rows,
   added through the public `DatabaseManager.save_metric` /
   `get_connection()` API, never by editing `db_manager.py`.
2. `models/port.py`'s `get_tariff_price()` only understands a flat
   day-of-week/time-of-day JSON — no concept of EEM's seasonal Period
   I–IV quarters. Rather than adding season-awareness to `Port`, this
   package picks which of four pre-generated flat tariff JSONs to load,
   *before* `Port` is instantiated.
3. `models/bess.py` has zero degradation/cycle-counting logic. This
   package reconstructs BESS cycle throughput from the `bess_charge`/
   `bess_discharge` measurements PyPort already logs, as a post-processing
   step run after a simulation completes.

## Modules

| File | Purpose |
|---|---|
| `metrics.py` | New EAV `metric` definitions + `register_economic_metrics()` |
| `tariff_seasonal.py` | EEM Period I–IV resolution + seasonal tariff JSON generator/picker |
| `degradation.py` | BESS equivalent-cycles / SOH estimate from logged measurements |
| `capex_opex.py` | CAPEX/OPEX breakdowns + Levelized Cost of Storage (Chapter 2, Eq. lcos) |
| `run_economics.py` | CLI: turn one completed run's `.db` file into economic KPIs |

## Status

First working skeleton — the shapes/equations are correct, but several
numeric defaults are placeholders from the data inventory
(`data_variable_inventory_EN.xlsx`), marked `TODO` in the code, pending
real Funchal-specific quotes/data (several are already requested — see the
Research Log). Do not cite the default `CapexBreakdown`/`OpexBreakdown`
numbers as final figures.

## Running the tests

From the repo root (`pyport_sim/`), with `pytest` installed:

```bash
pytest tests/economics/ -v
```