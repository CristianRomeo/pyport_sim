"""
Summarize repeated simulation runs of the same case: mean, spread and range.

Trip assignment is random, so every run of garmin_scaling_experiment.py gives
slightly different numbers. Run the same command several times with different
--out-csv names, then:

    python summarize_runs.py rep_1.csv rep_2.csv rep_3.csv rep_4.csv rep_5.csv

Rows are grouped by boats + plant size. For each group the table shows the
number of runs, then mean, standard deviation, minimum and maximum of the
chosen indicators.

--excess-factor F re-prices the grid import above the power threshold at F
times the tariff, from the excess columns the runs stored, and recomputes
annual savings and NPV. No new simulation is needed (needs runs made with the
version of boats_scaling_experiment.py that writes those columns).

--peak-rate R models a power charge instead: R EUR per kW of weekly grid peak
above the threshold, per billing month. It uses the kW-months columns stored
by the run (peak above the threshold x months), so any R can be tried without
simulating again. Plant value = (scheduled - DER) kW-months x R; smart-charging
value = (baseline - scheduled) kW-months x R. Can be combined with
--excess-factor. Only one week per season is simulated, so the monthly peak is
approximated by that week's peak.

--lost-trip-eur V gives a value to every trip that cannot be served (grid cap
too low). Trips are counted from the *_trips_served columns: plant value gets
V x (DER served - scheduled served) trips per year, smart-charging value gets
V x (scheduled served - baseline served). Without it the table only counts
energy cost, so a scenario that drops trips looks cheaper than it is. The
output also prints the break-even V: what one recovered trip must be worth for
the plant NPV to reach zero.
"""

import argparse
import csv
import statistics
from collections import defaultdict

YEAR_WEEKS = 365.0 / 7.0


def num(row, key, default=0.0):
    v = row.get(key)
    return float(v) if v not in (None, "") else default


def peak_delta(row, peak_rate):
    """(extra plant savings, extra smart-charging savings) per year from a power charge of `peak_rate` EUR/kW-month."""
    if not peak_rate or row.get("der_peak_excess_kwmonths") in (None, ""):
        return 0.0, 0.0
    b = num(row, "baseline_peak_excess_kwmonths")
    s = num(row, "scheduled_peak_excess_kwmonths")
    d = num(row, "der_peak_excess_kwmonths")
    return peak_rate * (s - d), peak_rate * (b - s)


def trip_counts(row):
    """Served trips per (average) week for baseline, scheduled, DER; None if the run did not store them."""
    keys = ("baseline_trips_served", "scheduled_trips_served", "der_trips_served")
    if any(row.get(k) in (None, "") for k in keys):
        return None
    return tuple(num(row, k) for k in keys)


def trip_delta(row, trip_eur):
    """(extra plant value, extra smart-charging value) per year from valuing recovered trips at `trip_eur` each."""
    t = trip_counts(row)
    if not trip_eur or t is None:
        return 0.0, 0.0
    b, s, d = t
    return trip_eur * (d - s) * YEAR_WEEKS, trip_eur * (s - b) * YEAR_WEEKS


def reprice(row, factor, rate, horizon, peak_rate=0.0, trip_eur=0.0):
    """Annual savings, savings from smart charging and NPV when the excess is priced at `factor`."""
    used = num(row, "excess_factor", 1.0)
    has_excess = row.get("der_excess_eur_week") not in (None, "")
    sx = num(row, "scheduled_excess_eur_week")
    dx = num(row, "der_excess_eur_week")
    bx = num(row, "baseline_excess_eur_week")
    d_sav = (factor - used) * (sx - dx) * YEAR_WEEKS if has_excess else 0.0
    d_smart = (factor - used) * (bx - sx) * YEAR_WEEKS if has_excess else 0.0
    p_sav, p_smart = peak_delta(row, peak_rate)
    t_sav, t_smart = trip_delta(row, trip_eur)
    d_sav += p_sav + t_sav
    d_smart += p_smart + t_smart
    savings = num(row, "annual_savings_eur") + d_sav
    smart = num(row, "scheduling_savings_eur_week") * YEAR_WEEKS + d_smart
    net = num(row, "annual_net_cashflow_eur") + d_sav
    annuity = (1 - (1 + rate) ** -horizon) / rate
    npv = net * annuity - num(row, "capex_eur") - num(row, "bess_replacement_pv_eur")
    return savings, smart, npv, net


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="+", help="summary CSVs of repeated runs (not *_seasons.csv)")
    ap.add_argument("--excess-factor", type=float, default=None,
                    help="re-price the import above the threshold at this multiple of the tariff")
    ap.add_argument("--peak-rate", type=float, default=0.0,
                    help="power charge in EUR per kW of weekly peak above the threshold, per month")
    ap.add_argument("--lost-trip-eur", type=float, default=0.0,
                    help="value in EUR of each trip that can be served only thanks to smart charging / the plant")
    ap.add_argument("--discount-rate", type=float, default=0.07)
    ap.add_argument("--horizon-years", type=int, default=20)
    ap.add_argument("--out", default=None, help="also write the table to this CSV")
    args = ap.parse_args()

    groups = defaultdict(list)
    for path in args.csv:
        if path.endswith("_seasons.csv"):
            continue
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                key = (int(r["num_boats"]), float(r.get("pv_kwp") or 100), float(r.get("bess_kwh") or 200))
                groups[key].append(r)

    metrics = [
        ("annual_savings_eur", "Plant savings EUR/yr"),
        ("smart_savings_eur", "Smart charging EUR/yr"),
        ("npv_eur", "NPV EUR"),
        ("bess_life_years", "Battery life y"),
    ]
    out_rows = []
    for key in sorted(groups):
        runs = groups[key]
        series = defaultdict(list)
        for r in runs:
            if args.excess_factor is None and not args.peak_rate and not args.lost_trip_eur:
                sav = num(r, "annual_savings_eur")
                smart = num(r, "scheduling_savings_eur_week") * YEAR_WEEKS
                npv = num(r, "npv_eur")
            else:
                sav, smart, npv, _ = reprice(r, args.excess_factor if args.excess_factor is not None else num(r, "excess_factor", 1.0),
                                       args.discount_rate, args.horizon_years, args.peak_rate, args.lost_trip_eur)
            series["annual_savings_eur"].append(sav)
            series["smart_savings_eur"].append(smart)
            series["npv_eur"].append(npv)
            series["bess_life_years"].append(num(r, "bess_life_years"))
        boats, pv, bess = key
        print(f"\n{boats} boats, {pv:.0f} kWp, {bess:.0f} kWh  ({len(runs)} runs"
              + (f", excess priced x{args.excess_factor:g}" if args.excess_factor is not None else "")
              + (f", power charge {args.peak_rate:g} EUR/kW-month" if args.peak_rate else "")
              + (f", lost trip valued {args.lost_trip_eur:g} EUR" if args.lost_trip_eur else "") + ")")
        counts = [trip_counts(r) for r in runs]
        counts = [c for c in counts if c]
        if counts:
            assigned = statistics.mean(num(r, "assigned_trips_week") for r in runs)
            avg = [statistics.mean(c[i] for c in counts) for i in range(3)]
            print(f"  trips served per week (of {assigned:.0f} assigned): baseline {avg[0]:.1f}, "
                  f"scheduled {avg[1]:.1f}, DER {avg[2]:.1f}")
            print(f"  trips not served per year: baseline {(assigned - avg[0]) * YEAR_WEEKS:,.0f}, "
                  f"scheduled {(assigned - avg[1]) * YEAR_WEEKS:,.0f}, DER {(assigned - avg[2]) * YEAR_WEEKS:,.0f}")
            gained = (avg[2] - avg[1]) * YEAR_WEEKS
            if gained > 0:
                npvs = [reprice(r, args.excess_factor if args.excess_factor is not None else num(r, "excess_factor", 1.0),
                                args.discount_rate, args.horizon_years, args.peak_rate, args.lost_trip_eur)[2]
                        for r in runs]
                annuity = (1 - (1 + args.discount_rate) ** -args.horizon_years) / args.discount_rate
                be = -statistics.mean(npvs) / (annuity * gained)
                print(f"  plant recovers {gained:,.0f} trips/year; break-even value per recovered trip "
                      f"(on top of the value set above): {be:,.0f} EUR" if be > 0 else
                      f"  plant recovers {gained:,.0f} trips/year; NPV already positive")
        if args.peak_rate:
            for lbl, k in (("baseline", "baseline"), ("scheduled", "scheduled"), ("DER", "der")):
                pk = [num(r, f"{k}_peak_kw") for r in runs]
                print(f"  peak {lbl:10}{statistics.mean(pk):>8.1f} kW (highest weekly peak, mean of runs)")
        print(f"  {'':24}{'mean':>12}{'std':>10}{'min':>12}{'max':>12}")
        for k, label in metrics:
            v = series[k]
            sd = statistics.stdev(v) if len(v) > 1 else float("nan")
            print(f"  {label:24}{statistics.mean(v):>12,.1f}{sd:>10,.1f}{min(v):>12,.1f}{max(v):>12,.1f}")
            out_rows.append({"num_boats": boats, "pv_kwp": pv, "bess_kwh": bess, "runs": len(v), "metric": k,
                             "mean": round(statistics.mean(v), 2), "std": round(sd, 2) if v[1:] else "",
                             "min": round(min(v), 2), "max": round(max(v), 2)})
    if args.out and out_rows:
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=out_rows[0].keys())
            w.writeheader()
            w.writerows(out_rows)
        print(f"\nSaved to {args.out}")


if __name__ == "__main__":
    main()