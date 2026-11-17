"""
Boat-count scaling experiment using ONLY the two real Garmin boat tracks
(assets/trips_garmin/route_9.csv, route_10.csv) and a configurable charger
power. The grid-import limit scales with the fleet (boats x charger kW, see
boats_scaling_experiment.py).

This is a thin wrapper: it reuses boats_scaling_experiment.py unchanged
(same PV/BESS sizing, tariff, economics, representative weeks), and only
overrides
  1. the trips directory  -> assets/trips_garmin   (the other routes are untouched)
  2. the charger power    -> --charger-kw (default 50 kW)
and then adds two extra columns to the results: trips served per week and
grid cost per served trip, so Base and DER are comparable even when their
service levels differ.

By default it simulates four representative weeks (winter, spring, summer,
autumn). Use --seasons to choose, e.g. --seasons summer for a quick test.

Usage:
    python garmin_scaling_experiment.py
    python garmin_scaling_experiment.py --boat-counts 2 3 4 5 --charger-kw 50
    python garmin_scaling_experiment.py --seasons summer --boat-counts 2
    python garmin_scaling_experiment.py --charger-kw 22 --out-csv garmin_22kw.csv
"""

import argparse
import csv
import sys
from pathlib import Path

import boats_scaling_experiment as b
from simulation import SimulationEngine

GARMIN_TRIPS_DIR = "assets/trips_garmin"


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--charger-kw", type=float, default=50.0)
    parser.add_argument("--trips-dir", default=GARMIN_TRIPS_DIR)
    parser.add_argument("--out-csv", default="garmin_scaling_results.csv")
    parser.add_argument("--boat-counts", type=int, nargs="+", default=[2, 3, 4, 5])
    own, rest = parser.parse_known_args()

    if not list(Path(own.trips_dir).glob("route_*.csv")):
        sys.exit(f"ERROR: no route_*.csv found in {own.trips_dir} - "
                 f"run this script from the pyport_sim folder.")

    # 1) charger power (read by build_port() at call time)
    b.CHARGER_KW = own.charger_kw

    # 2) trips directory (SimulationEngine defaults to assets/trips)
    orig_init = SimulationEngine.__init__

    def init_with_garmin(self, *args, **kwargs):
        kwargs.setdefault("trips_directory", own.trips_dir)
        orig_init(self, *args, **kwargs)

    SimulationEngine.__init__ = init_with_garmin

    print(f"Garmin experiment: trips from {own.trips_dir}, charger = {own.charger_kw:.0f} kW, "
          "grid limit = boats x charger kW")

    sys.argv = [sys.argv[0], "--boat-counts", *map(str, own.boat_counts),
                "--out-csv", own.out_csv, *rest]
    b.main()

    # 3) extra columns: trips served per (average) week and grid cost per served trip
    with open(own.out_csv, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        assigned = float(r["assigned_trips_week"])
        for tag in ("baseline", "scheduled", "der"):
            if not r.get(f"{tag}_weekly_eur"):
                continue
            served = float(r[f"{tag}_service_level"]) * assigned
            r[f"{tag}_trips_served"] = round(served, 1)
            r[f"{tag}_eur_per_served_trip"] = (
                round(float(r[f"{tag}_weekly_eur"]) / served, 2) if served else ""
            )
    with open(own.out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    print("\nBoats  Base served  Base EUR/trip  Sched EUR/trip   DER served  DER EUR/trip   (average week)")
    for r in rows:
        print(f"{r['num_boats']:<7}{r['baseline_trips_served']:>8}{r['baseline_eur_per_served_trip']:>14}"
              f"{r.get('scheduled_eur_per_served_trip', '-'):>15}"
              f"{r['der_trips_served']:>12}{r['der_eur_per_served_trip']:>14}")
    print(f"\nSaved (with extra columns) to {own.out_csv}")


if __name__ == "__main__":
    main()