"""Rebuild dashboard/cases.js from the medium-voltage result files (run from the repo root).

    python build_dashboard_cases.py

Reads results/eem_mv (the cases of the dashboard, with the EEM 2026 tariff and its power charges) and
results/sweep_mv (the sweep of the grid connection for four boats). The runs of results/peakhour_mv repeat
cases of results/eem_mv and are only read by export_peakhour_data.py and export_plain_data.py.
Cases run with two seeds are averaged.
"""
import glob
import subprocess
import sys


def summaries(pattern):
    return [f for f in sorted(glob.glob(pattern)) if not f.endswith("_seasons.csv")]


files = summaries("results/eem_mv/*.csv") + summaries("results/sweep_mv/sw_*.csv") + summaries("results/grid_mv/g_*.csv")
print(len(files), "result files")
sys.exit(subprocess.call([sys.executable, "export_dashboard_data.py", "--average"] + files))