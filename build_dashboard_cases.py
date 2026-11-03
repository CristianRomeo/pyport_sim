"""Rebuild dashboard/cases.js from all the result files (run from the repo root).

    python build_dashboard_cases.py

It reproduces the 45 existing cases exactly and adds the nine 120 kW sizing
cases (4, 5 and 6 boats). The 4-boat runs of results/sizing120 that repeat a
case already in results/fleet (200 kWh 100 kW, and the PV 100 kWp plants) are
skipped so that no case is counted twice.
"""
import glob
import subprocess
import sys


def summaries(pattern):
    return [f for f in sorted(glob.glob(pattern)) if not f.endswith("_seasons.csv")]


files = (
    summaries("results/fleet/*.csv")
    + summaries("results/sizing/*.csv")
    + ["results/garmin_seasons3.csv"]
    + summaries("results/size_pv*.csv")
    + summaries("results/rep_base_*.csv")
    + [f for f in summaries("results/sizing120/*.csv")
       if "pv100" not in f and "b200p100_n4" not in f]
)
print(len(files), "result files")
sys.exit(subprocess.call([sys.executable, "export_dashboard_data.py", "--average"] + files))
