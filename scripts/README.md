# scripts/

PowerShell scripts that run series of simulations. Run them **from the repository root**, once per window (each window works in its own copy of the repository, so the database files do not collide), for example:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python make_eem_tariffs.py            # once, before the series that use the EEM tariff
.\scripts\run_grid.ps1 1
.\scripts\run_grid.ps1 2
.\scripts\run_grid.ps1 3
```

A run whose CSV already exists is skipped, so a script can be restarted. Results go to `results\<folder>` (not versioned: the CSVs are kept in `results_summary/`).

| Script | Results folder | What it runs | Feeds |
|---|---|---|---|
| `run_grid.ps1` | `grid_mv` | 2 to 10 boats, solar 0 or 100 kWp, battery none / 200 kWh at 50 kW / at 100 kW, three grid limits | `dashboard/cases.js` |
| `run_plain_grid.ps1` | `plain_grid` | the same cases without smart charging (charging on arrival, rule-based battery) | `dashboard/plain.js` |
| `run_sweep_cap.ps1` | `sweep_mv` | grid connection sweep for four boats: smallest connection that serves every trip | `dashboard/cases.js`, `peakhour.js`, `plain.js` |
| `run_eem_full.ps1`, `run_eem_series.ps1` | `eem_mv` | cases with the EEM 2026 medium-voltage tariff (`run_eem_series.ps1` first, `run_eem_full.ps1` completes the set so that every dashboard case has an EEM version) | `dashboard/cases.js` |
| `run_peakhour_series.ps1`, `run_peakhour_series2.ps1` | `peakhour_mv` | average grid power in the peak hours (basis of the peak-hour power charge) | `dashboard/peakhour.js`, `plain.js` |
| `run_export_series.ps1` | `export` | placeholder tariff plus a price for the exported solar energy (earlier series) | thesis tables |
| `run_plain_series.ps1` | `plain` | plant without smart charging (earlier series) | thesis tables |

The "earlier series" (`export`, `plain`) were run before the grid scripts and are kept so that every number in the thesis can be traced to a script and a CSV. `results_summary/README.md` lists what each folder contains.
