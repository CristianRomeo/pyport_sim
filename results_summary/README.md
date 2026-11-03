# results_summary/

Summary CSVs of the simulation series used in the thesis (the logs and the
SQLite databases are not kept: they are about 1.2 GB and can be regenerated).
Each run writes `<name>.csv` (one row per fleet) and `<name>_seasons.csv`
(the weeks one by one). All series use the two Garmin routes, a 50 kW charger
per boat unless stated, the placeholder tariff (0.12 / 0.20 / 0.30 EUR/kWh) and
seeds 1, 2 and 3. Weekly figures are the average week of the year.

| Folder | What it is | Thesis |
|---|---|---|
| `fleet/` | Fleet size (2-6 boats) under grid caps of 80, 100, 120 and 150 kW; battery 200 kWh / 100 kW and PV 100 kWp + 200 kWh | Ch. 7, scenario results |
| `sizing/` | Battery sizing at an 80 kW cap, 4-6 boats | Ch. 7, sizing |
| `sizing120/` | The same sizing at 120 kW, 4-6 boats | Ch. 7, sizing at 120 kW |
| `tariff/` | Shape of the tariff: flat, narrow, default, wide; limits 100 and 200 kW; 4 boats | Ch. 7, shape of the tariff |
| `months/` | Twelve monthly weeks instead of four seasonal ones (`--seasons m01 ... m12`) | Ch. 7, four or twelve weeks |
| `b1/`, `b1b/` | Optimiser with the soft next-morning readiness constraint (tested on a copy of the optimiser, not part of the main code) | Ch. 7, verification |
| `term/` | Test with a fixed terminal reward for the boats' charge (discarded: it distorts the arbitrage) | Ch. 7, verification |
| `fix/`, `slack/` | Diagnostic runs of the charging-window fix and of the slack test (confirm before citing) | not cited |
| `mix/` | Mixed fleets (rib, tourist catamaran, luxury catamaran), experimental, boat types are assumptions | not in the thesis yet |
| top level | `garmin_seasons3` (reference plant, four seasons), `size_pv*_b*` (plant size at 4 boats), `rep_base_*`, `seed_*`, `peak_base_*` (repeated runs, seeds, peak-power charge) | Ch. 7 |

`python build_dashboard_cases.py` rebuilds `dashboard/cases.js` from the
files in `results/` (same layout as here).