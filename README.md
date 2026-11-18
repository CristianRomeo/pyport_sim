# Marina Electrification Planner

Techno-economic extension (plugin) of **[PyPort Sim](https://github.com/AHEAD-EU/pyport_sim)** for the electrification of recreational marinas, with a case study of the Funchal marina (Madeira).

PyPort Sim (T. Garcês, University of Madeira, 2026, MIT license) is included as a git submodule in `external/pyport_sim`, at a version that adds a few backward-compatible extension points (rule-based battery, price of exported energy, any number of trip slots, hooks for the trip pattern); this repository adds the economic layer, the planner dashboard and the experiments of the master's thesis *A Techno-Economic Analysis of the Electrification of Recreational Marinas: A Simulation-Based Approach with a Case Study in Funchal* (University of Bologna, Digital Transformation Management; research mobility at ITI/LARSyS, Funchal). It turns the engineering simulator into a planning tool: it adds an economic layer (CAPEX and OPEX, grid power charges, battery degradation, NPV and payback) and a dashboard in which a non-technical user chooses a simulated case, changes prices and assumptions and reads the financial result. The documentation of the simulator itself is in the PyPort Sim repository.

## What was added to PyPort

| Part | Where | What it does |
|---|---|---|
| Economic layer | `economics/` | CAPEX/OPEX, levelized cost of storage, battery degradation and replacements, EEM 2026 tariff handling, NPV, simple and discounted payback. Tested in `tests/economics/`. |
| Funchal case study | `marina_planner/` | The usage pattern of the boats (trips per day from the season and the public holidays) as a subclass of PyPort's `TripManager`, and the engine that uses it. The extension points it relies on (rule-based battery, price of exported energy, any number of trip slots) are generic changes of PyPort Sim. |
| Tariffs | `assets/tariff/`, `make_eem_tariffs.py` | EEM 2026 tariff files, one per simulated week, and the sensitivity tariffs. |
| Experiments | `boats_scaling_experiment.py`, `garmin_scaling_experiment.py`, `scripts/` | Run a case for four representative weeks and write one CSV row. The scripts run whole series of cases. |
| Dashboard | `dashboard/` | Static page (`index.html`) with its data files (`cases.js`, `plain.js`, `peakhour.js`): 180 simulated cases. |
| Results | `results_summary/` | Summary CSVs of every series used in the thesis. |

## Quick start

Python 3.11 or later (3.12 tested). The optimizer needs the SCIP solver (PySCIPOpt is in `requirements.txt`).

```bash
git clone --recurse-submodules <url of this repository>
cd <folder of the repository>
python -m venv venv
venv\Scripts\activate            # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
pytest                            # 72 tests of the economic layer and of the Funchal case study
```

If the clone was made without `--recurse-submodules`, the folder `external/pyport_sim` is empty: run `git submodule update --init`. To use another copy of PyPort Sim, set the environment variable `PYPORT_PATH` to its folder.

What each part needs:

| To do | You need |
|---|---|
| Open the dashboard | A browser. Nothing else: no installation, no PyPort Sim. |
| Run the tests | The steps above. No internet. |
| Run a simulation | The steps above, and internet access: simulations with PV download the weather of the simulated days from Open-Meteo, and without it the run stops with an error. |
| Run whole series of simulations | The same, and Windows PowerShell for the scripts in `scripts/`. |

**Check the installation.** This runs one week of the case study (four boats, 100 kWp of PV, a 200 kWh / 50 kW battery, grid connection limited to 100 kW) and takes a few minutes:

```bash
python garmin_scaling_experiment.py --boat-counts 4 --pv-kwp 100 --bess-kwh 200 --bess-kw 50 --grid-limit-kw 100 --seed 1 --tariff-json "assets/tariff/eem_mt_{season}.json" --export-price 0.05 --seasons winter --out-csv check_winter.csv
```

In `check_winter_seasons.csv` the winter row must show `baseline_weekly_eur` 529.97, `scheduled_weekly_eur` 367.86, `der_weekly_eur` 178.25, `der_export_kwh` 742.8 and `weekly_savings_eur` 189.61, the values stored in `results_summary/`.

**Dashboard.** Open `dashboard/index.html` in a browser: it needs no server. *Findings* summarizes the simulated cases, *Calculator* gives the detail of one case with editable prices, *Next steps* lists what is still open.

**One simulation.** The PyPort example is in `external/pyport_sim/main.py`.

**One case of the thesis.**

```bash
python garmin_scaling_experiment.py --help
python economics_demo.py          # step-by-step walk through the economic calculation
```

## Reproducing the results

1. Build the tariff files: `python make_eem_tariffs.py` (writes `assets/tariff/eem_*.json`).
2. Run a series of simulations from the repo root, on Windows PowerShell, for example `.\scripts\run_grid.ps1 1` (see [`scripts/README.md`](scripts/README.md) for the scripts, their order and the folders they write). A full series takes many hours and about 1.2 GB of logs, which are not versioned.
3. Rebuild the dashboard data:

```bash
python build_dashboard_cases.py   # dashboard/cases.js
python export_plain_data.py       # dashboard/plain.js
python export_peakhour_data.py    # dashboard/peakhour.js
```

The scripts of step 3 read `results/`. To rebuild the dashboard from the summaries kept in this repository without simulating again, copy them first: `Copy-Item results_summary results -Recurse` (Windows) or `cp -r results_summary results`.

## Assumptions and limits

- Prices are benchmarks, not supplier quotes: the PV price is 1.0 EUR/Wp (commercial plants of 10-100 kWp in Spain, 2023, IEA PVPS), the battery 650 EUR/kWh. Every price can be changed in the planner.
- The trips come from two real boat tracks recorded in Funchal and the vessel is the PyPort reference vessel.
- The annual figures come from four representative weeks, one per season. Most cases are a single seeded run.
- The tariff is the EEM 2026 medium-voltage tariff (ERSE Directive 10/2025). The revenue of a trip and the cost of a larger grid connection are not known and are left to the user.
- The repository does not implement a Digital Twin: there is no live data and no closed-loop control.

The thesis explains the model and discusses the results; the economic layer is described in [`economics/README.md`](economics/README.md).

## Layout

```
economics/               economic layer (CAPEX/OPEX, degradation, tariffs, payback) and its CLI
dashboard/               planner: index.html and data files
scripts/                 PowerShell scripts that run series of simulations
results_summary/         summary CSVs of the series (logs and databases are not kept)
marina_planner/           Funchal case study (trip pattern and engine, as extensions of PyPort Sim)
tests/                   tests of the economic layer and of the Funchal case study
external/pyport_sim/      PyPort Sim (git submodule)
assets/                  trips of the case study and EEM tariff files
boats_scaling_experiment.py, garmin_scaling_experiment.py, summarize_runs.py
                         experiment drivers
make_eem_tariffs.py, make_tariffs.py
                         tariff files (EEM 2026; sensitivity tariffs)
build_dashboard_cases.py, export_*.py
                         build the dashboard data files from the results
```

## License

MIT (see `LICENSE`), as PyPort Sim.
