# results_summary/

Summary CSVs of the simulation series used in the thesis (the logs and the
SQLite databases are not kept: they are about 1.2 GB and can be regenerated).
Each run writes `<name>.csv` (one row per fleet) and `<name>_seasons.csv`
(the weeks one by one). All series use the two Garmin routes and a 50 kW charger
per boat unless stated. The older series (everything except `export/`, `eem/`,
`plain/` and `peakhour/`) use the placeholder tariff (0.12 / 0.20 / 0.30 EUR/kWh)
and seeds 1, 2 and 3. The four newer series are listed at the end of the table.
Weekly figures are the average week of the year.

| Folder | What it is | Thesis |
|---|---|---|
| `fleet/` | Fleet size (2-6 boats) under grid caps of 80, 100, 120 and 150 kW; battery 200 kWh / 100 kW and PV 100 kWp + 200 kWh | Ch. 7, scenario results |
| `sizing/` | Battery sizing at an 80 kW cap, 4-6 boats | Ch. 7, sizing |
| `sizing120/` | The same sizing at 120 kW, 4-6 boats | Ch. 7, sizing at 120 kW |
| `tariff/` | Shape of the tariff: flat, narrow, default, wide; limits 100 and 200 kW; 4 boats | Ch. 7, shape of the tariff |
| `months/` | Twelve monthly weeks instead of four seasonal ones (`--seasons m01 ... m12`) | Ch. 7, four or twelve weeks |
| `b1/`, `b1b/` | Optimiser with the soft next-morning readiness constraint (tested on a copy of the optimiser, not part of the main code) | Ch. 7, verification |
| `term/` | Test with a fixed terminal reward for the boats' charge (discarded: it distorts the arbitrage) | Ch. 7, verification |
| `mix/` | Mixed fleets (rib, tourist catamaran, luxury catamaran), experimental, boat types are assumptions | not in the thesis yet |
| `export/` | Placeholder tariff plus a price of 0.05 EUR/kWh for the PV energy sent to the grid: seven solar/battery sizes (4 boats, seeds 1-3), 100 kWp + 200 kWh under grid limits of 80-150 kW (seeds 1-3) and with 2-10 boats (seed 1). Script: `run_export_series.ps1` | Ch. 7, export price |
| `eem/` | EEM 2026 tariff (medium voltage `mt_*`, `mtcap120_*`, `f_*`; special low voltage `bte_*`), export at 0.05 EUR/kWh, with the optimiser. Seeds 1-3 for four boats, seed 1 for other fleet sizes. Scripts: `run_eem_series.ps1`, `run_eem_full.ps1`. Some cases (limits of 100 and 150 kW, 300-400 kWh batteries) are no longer shown in the dashboard | Dashboard, Ch. 7 |
| `plain/` | Plant without smart charging (charging on arrival + rule-based battery), EEM 2026 medium voltage, export at 0.05 EUR/kWh. Seeds 1-2. Script: `run_plain_series.ps1`. Feeds `dashboard/plain.js` | Dashboard, Ch. 7 |
| `peakhour/` | Average grid power in the peak hours (basis of the peak-hour power charge), EEM 2026 medium voltage, seed 1. `opt_*` with the optimiser (charging on arrival, smart charging, plant), `plain_*` without smart charging. 25 cases. Scripts: `run_peakhour_series.ps1`, `run_peakhour_series2.ps1`. Feeds `dashboard/peakhour.js` | Dashboard, Ch. 7 |
| top level | `garmin_seasons3` (reference plant, four seasons), `size_pv*_b*` (plant size at 4 boats), `rep_base_*`, `seed_*`, `peak_base_*` (repeated runs, seeds, peak-power charge) | Ch. 7 |

`python build_dashboard_cases.py` rebuilds `dashboard/cases.js` from the
files in `results/` (same layout as here). `python export_plain_data.py` and
`python export_peakhour_data.py` rebuild `dashboard/plain.js` and
`dashboard/peakhour.js` from `results/plain` and `results/peakhour`.