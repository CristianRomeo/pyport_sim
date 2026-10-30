"""
Export the simulation results to dashboard/cases.js, the data file read by
dashboard/index.html (Marina DSS Explorer).

Usage (from the repo root):
    python export_dashboard_data.py garmin_seasons3.csv size_*.csv

Each CSV row written by garmin_scaling_experiment.py becomes one case:
  sav   = annual_savings_eur   (scheduled baseline - DER, EUR per year)
  smart = scheduling_savings_eur_week * 365 / 7 (plain - scheduled baseline)
  life  = bess_life_years      (0 when there is no battery)
  xsav / xsmart = EUR per year of grid import above the power threshold, at the
          normal tariff, that the plant (xsav) and smart charging (xsmart) avoid.
          With a surcharge factor f the savings grow by (f - 1) times these.
          Savings in the CSV may already include a surcharge (column
          excess_factor): it is removed so the case holds the savings at the
          normal tariff. null when the run did not store the excess columns.
  thr   = excess_threshold_kw
  cap   = contracted_power_kw (grid-import limit of the run, kW). A cap below
          boats x charger kW (--charger-kw, default 50) makes a separate case,
          named "... · 80 kW cap"; the same boats + plant at different caps are
          different cases.
  bkw   = bess_kw (battery charge/discharge power, kW). A power different from
          the default (the smaller of 50 kW and a quarter of the kWh) makes a
          separate case, named "... · 100 kW battery". Runs from before the
          column existed are read as the default power.
  tb / ts / td = trips served per week without plant and without smart
          charging (tb), with smart charging only (ts), with the plant (td);
          asg = trips assigned per week. The dashboard values the trips the
          plant or smart charging recovers (slider "Value per recovered trip").
          null when the run did not store the served-trip columns.
CSVs from before the plant-size options have no pv_kwp / bess_kwh columns:
those rows are read as 100 kWp / 200 kWh. A later file replaces an earlier row
for the same boats + plant size, unless --average is given (use it for repeated
runs of the same case: the dashboard then holds their mean).
"""
import argparse
import csv
import json
import os

YEAR_WEEKS = 365.0 / 7.0


def parse_row(r):
    boats = int(r["num_boats"])
    pv = float(r.get("pv_kwp") or 100)
    bess = float(r.get("bess_kwh") or 200)
    sched = r.get("scheduling_savings_eur_week")
    used = float(r.get("excess_factor") or 1.0)
    has_x = r.get("der_excess_eur_week") not in (None, "")
    bx = float(r.get("baseline_excess_eur_week") or 0)
    sx = float(r.get("scheduled_excess_eur_week") or 0)
    dx = float(r.get("der_excess_eur_week") or 0)
    xsav = (sx - dx) * YEAR_WEEKS if has_x else None
    xsmart = (bx - sx) * YEAR_WEEKS if has_x else None
    sav = float(r["annual_savings_eur"]) - ((used - 1.0) * xsav if has_x else 0.0)
    smart = (float(sched) * YEAR_WEEKS if sched not in (None, "") else 0.0) - (
        (used - 1.0) * xsmart if has_x else 0.0)
    cap = float(r.get("contracted_power_kw") or 0)
    trips = [r.get(k) for k in ("baseline_trips_served", "scheduled_trips_served", "der_trips_served")]
    trips = [float(t) for t in trips] if all(t not in (None, "") for t in trips) else [None] * 3
    asg = r.get("assigned_trips_week")
    default_kw = min(50.0, bess / 4.0) if bess > 0 else 0.0
    bkw = float(r.get("bess_kw") or default_kw) if bess > 0 else 0.0
    return (boats, pv, bess, cap, bkw), {
        "boats": boats,
        "pv": round(pv),
        "b": round(bess),
        "sav": sav,
        "smart": smart,
        "xsav": xsav,
        "xsmart": xsmart,
        "thr": float(r.get("excess_threshold_kw") or 80),
        "cap": round(cap),
        "bkw": round(bkw),
        "tb": trips[0], "ts": trips[1], "td": trips[2],
        "asg": float(asg) if asg not in (None, "") else None,
        "life": float(r.get("bess_life_years") or 0) if bess > 0 else 0.0,
    }


def mean_or_none(values):
    return None if any(v is None for v in values) else sum(values) / len(values)


def read_rows(paths, average=False):
    """Rows of the same boats + plant size: the last one wins, or their mean with average=True."""
    groups = {}
    for path in paths:
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                key, case = parse_row(r)
                groups.setdefault(key, []).append(case)
    cases = []
    for rows in groups.values():
        if not average:
            rows = rows[-1:]
        c = dict(rows[0])
        for k in ("sav", "smart", "xsav", "xsmart", "life", "tb", "ts", "td", "asg"):
            c[k] = mean_or_none([x[k] for x in rows])
        c["runs"] = len(rows)
        for k in ("sav", "smart", "xsav", "xsmart"):
            c[k] = None if c[k] is None else round(c[k])
        for k in ("tb", "ts", "td", "asg"):
            c[k] = None if c[k] is None else round(c[k], 2)
        c["life"] = round(c["life"], 1)
        cases.append(c)
    return cases


CHARGER_KW = 50.0


def capped(c):
    return c["cap"] > 0 and c["cap"] < c["boats"] * CHARGER_KW - 1e-6


def custom_power(c):
    return c["b"] > 0 and abs(c["bkw"] - min(50.0, c["b"] / 4.0)) > 0.5


def label(c):
    parts = []
    if c["pv"] > 0:
        parts.append(f'{c["pv"]} kWp')
    if c["b"] > 0:
        parts.append(f'{c["b"]} kWh')
    plant = " + ".join(parts) if parts else "no plant"
    only = ""
    if c["b"] == 0:
        only = " only"
    elif c["pv"] == 0:
        only = " only"
    cap = f' · {c["cap"]} kW cap' if capped(c) else ""
    power = f' · {c["bkw"]} kW battery' if custom_power(c) else ""
    return f'{c["boats"]} boats · {plant}{only}{power}{cap}'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="+", help="result CSVs (summary files, not *_seasons.csv)")
    ap.add_argument("--average", action="store_true",
                    help="average the rows of the same boats + plant size (repeated runs) instead of "
                         "letting the last file replace the earlier ones")
    ap.add_argument("--charger-kw", type=float, default=50.0,
                    help="charger power used in the runs: a grid limit below boats x this is a capped case")
    ap.add_argument("--out", default=os.path.join("dashboard", "cases.js"))
    args = ap.parse_args()
    paths = [p for p in args.csv if not p.endswith("_seasons.csv")]
    global CHARGER_KW
    CHARGER_KW = args.charger_kw
    cases = read_rows(paths, args.average)
    cases.sort(key=lambda c: (c["boats"], c["pv"], c["b"], c["bkw"], -c["cap"]))
    for c in cases:
        c["name"] = label(c)
        c["id"] = f'b{c["boats"]}_pv{c["pv"]}_b{c["b"]}' + (f'_p{c["bkw"]}' if custom_power(c) else "") + (f'_cap{c["cap"]}' if capped(c) else "")
        c["g"] = f'{c["boats"]} boats'
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("// Generated by export_dashboard_data.py. Do not edit by hand.\n")
        f.write("window.CASES_DATA = " + json.dumps(cases, ensure_ascii=False, indent=1) + ";\n")
    print(f"Wrote {len(cases)} cases to {args.out}")


if __name__ == "__main__":
    main()