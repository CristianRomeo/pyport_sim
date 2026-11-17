# Marina Electrification Planner

Techno-economic extension of **PyPort Sim** for the electrification of recreational marinas, with a case study of the Funchal marina (Madeira).

This repository is a fork of PyPort Sim (T. Garcês, University of Madeira, 2026, MIT license), developed for the master's thesis *A Techno-Economic Analysis of the Electrification of Recreational Marinas: A Simulation-Based Approach with a Case Study in Funchal* (University of Bologna, Digital Transformation Management; research mobility at ITI/LARSyS, Funchal). It turns the engineering simulator into a planning tool: it adds an economic layer (CAPEX and OPEX, grid power charges, battery degradation, NPV and payback) and a dashboard in which a non-technical user chooses a simulated case, changes prices and assumptions and reads the financial result. The original PyPort README is kept in [`docs/PYPORT_README.md`](docs/PYPORT_README.md).

## What was added to PyPort

| Part | Where | What it does |
|---|---|---|
| Economic layer | `economics/` | CAPEX/OPEX, levelized cost of storage, battery degradation and replacements, EEM 2026 tariff handling, NPV, simple and discounted payback. Tested in `tests/economics/`. |
| Simulator changes | `simulation/`, `forecasting/` | Forecaster charging-window correction, number of daily trip slots from the configuration, EEM tariff files, price of exported energy, plant without smart charging (charging on arrival and a rule-based battery), measurement of the power in the peak hours. The validated asset models are unchanged. |
| Experiments | `boats_scaling_experiment.py`, `garmin_scaling_experiment.py`, `scripts/` | Run a case for four representative weeks and write one CSV row. The scripts run whole series of cases. |
| Dashboard | `dashboard/` | Static page (`index.html`) with its data files (`cases.js`, `plain.js`, `peakhour.js`): 180 simulated cases. |
| Results | `results_summary/` | Summary CSVs of every series used in the thesis. |

## Quick start

Python 3.11 or later; the optimizer needs the SCIP solver (PySCIPOpt is in `requirements.txt`).

Requirements to reproduce the results: Python 3.11 or later (3.12 tested), internet access (simulations with PV download the weather of the simulated days from Open-Meteo; without it the run stops with an error), and Windows PowerShell for the scripts in `scripts/`. The tests and the dashboard need neither.

```bash
python -m venv venv
venv\Scripts\activate            # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
pytest tests/economics           # tests of the economic layer
```

**Dashboard.** Open `dashboard/index.html` in a browser: it needs no server. *Findings* summarizes the simulated cases, *Calculator* gives the detail of one case with editable prices, *Next steps* lists what is still open.

**One simulation.** `python main.py` runs the PyPort example; `streamlit run streamlit_app.py` shows the time series of a run.

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
tests/                   tests (economics/ is new; the rest comes from PyPort)
models/ simulation/ optimization/ forecasting/ database/ weather/ config/ assets/
                         PyPort Sim packages and input data
boats_scaling_experiment.py, garmin_scaling_experiment.py, summarize_runs.py
                         experiment drivers
make_eem_tariffs.py, make_tariffs.py
                         tariff files (EEM 2026; sensitivity tariffs)
build_dashboard_cases.py, export_*.py
                         build the dashboard data files from the results
```

## Licence

MIT, as the original PyPort Sim (see `LICENSE`).
