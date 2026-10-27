"""
economics_demo.py - step-by-step demo of the economic layer (no simulation needed).

It reads the weekly grid costs already produced by the scaling experiment
(garmin_scaling_results.csv) and walks through every economic calculation
with the same functions the thesis code uses, printing each step.

Run from the pyport_sim folder:
    python economics_demo.py                      # 2 boats, default prices
    python economics_demo.py --boats 3
    python economics_demo.py --pv-price 1.8 --bess-price 500   # what-if on prices
    python economics_demo.py --discount 0.05 --horizon 25      # what-if on finance

Prices, discount rate and horizon can be changed instantly. Changing the plant
size (kWp / kWh) or the fleet needs a new simulation: use
garmin_scaling_experiment.py for that.
"""

import argparse
import csv
import sys

from economics.capex_opex import CapexBreakdown, OpexBreakdown
from economics.payback import (
    evaluate_investment,
    bess_replacement_schedule,
    bess_price_decline_for_case,
    npv_sensitivity,
)

# Plant that was simulated to obtain the weekly costs in the CSV.
PV_KW = 100.0
BESS_KWH = 200.0


def eur(x):
    return f"{x:,.0f} EUR"


def reference_weekly(args, row):
    """Weekly cost the savings are measured against, and its name."""
    if args.reference == "scheduled" and row.get("scheduled_weekly_eur"):
        return float(row["scheduled_weekly_eur"]), "scheduled baseline"
    return float(row["baseline_weekly_eur"]), "baseline"


def battery_life_for(args, row):
    """Battery life in years: command line, else the CSV column, else 10."""
    if args.bess_life is not None:
        return args.bess_life
    if row.get("bess_life_years"):
        return float(row["bess_life_years"])
    return 10.0


def print_sensitivity(args, rows):
    """NPV for every boat count under different battery assumptions."""
    kwargs = {}
    if args.pv_price is not None:
        kwargs["pv_eur_per_wp"] = args.pv_price
    if args.bess_price is not None:
        kwargs["bess_eur_per_kwh"] = args.bess_price
    capex = CapexBreakdown(bess_kwh=BESS_KWH, pv_wp=PV_KW * 1000, **kwargs)
    bess_capex = BESS_KWH * capex.bess_eur_per_kwh
    opex = OpexBreakdown(bess_capex=bess_capex, pv_wp=PV_KW * 1000)

    boats = sorted(rows)
    table = {}
    for n in boats:
        r = rows[n]
        cashflow = (reference_weekly(args, r)[0] - float(r["der_weekly_eur"])) / 7 * 365 - opex.total()
        table[n] = npv_sensitivity(
            capex.total(), cashflow, bess_capex, battery_life_for(args, r),
            args.discount, args.horizon,
        )
    print(f"\nNPV in EUR ({args.discount:.0%}, {args.horizon} years), CAPEX {eur(capex.total())}")
    print(f"{'':<36}" + "".join(f"{str(n) + ' boats':>13}" for n in boats))
    for i, (label, _) in enumerate(table[boats[0]]):
        print(f"{label:<36}" + "".join(f"{table[n][i][1]:>13,.0f}" for n in boats))
    print("\nBattery price decline: NREL ATB 2024 (indicative). Only battery life and")
    print("replacement price change; no new simulation is needed.\n")


def main():
    p = argparse.ArgumentParser(description="Step-by-step economics demo")
    p.add_argument("--csv", default="garmin_scaling_results.csv")
    p.add_argument("--boats", type=int, default=2)
    p.add_argument("--pv-price", type=float, default=None, help="EUR per Wp (default 2.4)")
    p.add_argument("--bess-price", type=float, default=None, help="EUR per kWh (default 650)")
    p.add_argument("--discount", type=float, default=0.07)
    p.add_argument("--horizon", type=int, default=20)
    p.add_argument("--bess-life", type=float, default=None, help="years before the battery is replaced (0 = never). Default: value derived in the CSV, else 10")
    p.add_argument("--bess-decline", type=float, default=0.0, help="yearly fall of the battery price (0.03 = 3%%)")
    p.add_argument("--bess-decline-case", choices=["low", "mid", "high"], default=None,
                   help="named battery price decline (NREL ATB): low 1.5%%, mid 3.5%%, high 5.5%% a year")
    p.add_argument("--reference", choices=["scheduled", "plain"], default="scheduled",
                   help="baseline the savings are measured against: scheduled = grid only with smart "
                        "charging (credits PV+battery only with what they add); plain = no optimizer")
    p.add_argument("--sensitivity", action="store_true",
                   help="print the NPV of every boat count under different battery assumptions and exit")
    args = p.parse_args()
    if args.bess_decline_case:
        if args.bess_decline:
            sys.exit("Use either --bess-decline or --bess-decline-case, not both.")
        args.bess_decline = bess_price_decline_for_case(args.bess_decline_case)

    try:
        with open(args.csv, newline="", encoding="utf-8") as f:
            rows = {int(r["num_boats"]): r for r in csv.DictReader(f)}
    except FileNotFoundError:
        sys.exit(f"File not found: {args.csv}. Run garmin_scaling_experiment.py first.")
    # Plant size used in the run (columns written by boats_scaling_experiment.py)
    global PV_KW, BESS_KWH
    first = rows[sorted(rows)[0]]
    if first.get("pv_kwp"):
        PV_KW = float(first["pv_kwp"])
    if first.get("bess_kwh"):
        BESS_KWH = float(first["bess_kwh"])
    if args.sensitivity:
        print_sensitivity(args, rows)
        return
    if args.boats not in rows:
        sys.exit(f"No row for {args.boats} boats. Available: {sorted(rows)}")
    r = rows[args.boats]

    base_w, base_name = reference_weekly(args, r)
    plain_w = float(r["baseline_weekly_eur"])
    der_w = float(r["der_weekly_eur"])

    print(f"\n=== ECONOMIC DEMO - {args.boats} boats ===\n")

    print("STEP 1 - Grid energy bill of a week (power x time x tariff; average week if several seasons were simulated)")
    print(f"  Grid only, no optimizer (plain baseline): {plain_w:>10,.2f} EUR/week")
    if base_name != "baseline":
        print(f"  Grid only, smart charging (scheduled)   : {base_w:>10,.2f} EUR/week"
              f"   (scheduling alone saves {plain_w - base_w:,.2f})")
    print(f"  With PV+battery (DER)                   : {der_w:>10,.2f} EUR/week")

    weekly = base_w - der_w
    print(f"\nSTEP 2 - Weekly savings of the investment = {base_name} - DER")
    print(f"  {base_w:,.2f} - {der_w:,.2f} = {weekly:,.2f} EUR/week")

    seasons_csv = args.csv.rsplit(".", 1)[0] + "_seasons.csv"
    try:
        with open(seasons_csv, newline="", encoding="utf-8") as f:
            season_rows = [s for s in csv.DictReader(f) if int(s["num_boats"]) == args.boats]
    except FileNotFoundError:
        season_rows = []
    if season_rows:
        print("  The weeks simulated one by one (each counts for a quarter of the year):")
        for s in season_rows:
            ref, _ = reference_weekly(args, s)
            print(f"    {s['season']:<7} from {s['start_date']}: {base_name} {ref:>8,.2f}"
                  f"  DER {float(s['der_weekly_eur']):>8,.2f}  savings {ref - float(s['der_weekly_eur']):>8,.2f} EUR/week")
        print("  The figures above are the average week of the year (weighted by season).")

    daily = weekly / 7
    print("\nSTEP 3 - From week to year (daily x 365)")
    print(f"  {weekly:,.2f} / 7 = {daily:,.2f} EUR/day  ->  x 365 = {daily * 365:,.0f} EUR/year")

    kwargs = {}
    if args.pv_price is not None:
        kwargs["pv_eur_per_wp"] = args.pv_price
    if args.bess_price is not None:
        kwargs["bess_eur_per_kwh"] = args.bess_price
    capex = CapexBreakdown(bess_kwh=BESS_KWH, pv_wp=PV_KW * 1000, **kwargs)
    print("\nSTEP 4 - CAPEX (what we pay upfront; chargers already exist, so excluded)")
    print(f"  PV     : {PV_KW * 1000:,.0f} Wp x {capex.pv_eur_per_wp} EUR/Wp   = {eur(PV_KW * 1000 * capex.pv_eur_per_wp)}")
    print(f"  Battery: {BESS_KWH:,.0f} kWh x {capex.bess_eur_per_kwh} EUR/kWh = {eur(BESS_KWH * capex.bess_eur_per_kwh)}")
    print(f"  TOTAL CAPEX = {eur(capex.total())}")

    opex = OpexBreakdown(bess_capex=BESS_KWH * capex.bess_eur_per_kwh, pv_wp=PV_KW * 1000)
    print("\nSTEP 5 - OPEX (yearly upkeep)")
    print(f"  Battery: {opex.bess_rate_of_capex:.2%} of its CAPEX = {eur(opex.bess_capex * opex.bess_rate_of_capex)}")
    print(f"  PV     : {opex.pv_eur_per_wp_year} EUR/Wp/year       = {eur(opex.pv_wp * opex.pv_eur_per_wp_year)}")
    print(f"  TOTAL OPEX = {eur(opex.total())} per year")

    bess_life = battery_life_for(args, r)
    if args.bess_life is not None:
        life_source = "set on the command line"
    elif r.get("bess_life_years"):
        life_source = "derived from the simulated battery cycling"
    else:
        life_source = "default assumption"
    replacements = bess_replacement_schedule(
        BESS_KWH * capex.bess_eur_per_kwh, bess_life, args.horizon, args.bess_decline
    )
    replacements_extended = bess_replacement_schedule(
        BESS_KWH * capex.bess_eur_per_kwh, bess_life, args.horizon + 10, args.bess_decline
    )
    res = evaluate_investment(
        capex_eur=capex.total(),
        daily_savings_eur=daily,
        annual_opex_eur=opex.total(),
        discount_rate=args.discount,
        horizon_years=args.horizon,
        bess_replacements=replacements,
        bess_replacements_extended=replacements_extended,
    )
    print("\nSTEP 6 - Annual net cash flow = savings - OPEX")
    print(f"  {res.annual_savings_eur:,.0f} - {res.annual_opex_eur:,.0f} = {eur(res.annual_net_cashflow_eur)} per year")

    print("\nSTEP 7 - Simple payback = CAPEX / net cash flow")
    print(f"  {res.capex_eur:,.0f} / {res.annual_net_cashflow_eur:,.0f} = {res.simple_payback_years:.2f} years")

    factor = sum(1 / (1 + args.discount) ** t for t in range(1, args.horizon + 1))
    print(f"\nSTEP 8 - NPV at {args.discount:.0%} over {args.horizon} years")
    print(f"  Present value of the cash flows = {res.annual_net_cashflow_eur:,.0f} x {factor:.3f} = {eur(res.annual_net_cashflow_eur * factor)}")
    if replacements:
        print(f"  Battery life: {bess_life:.1f} years ({life_source})")
        for year, cost in replacements.items():
            print(f"  Battery replacement in year {year}: {eur(cost)} -> {eur(cost / (1 + args.discount) ** year)} in today's money")
        print(f"  NPV = {res.annual_net_cashflow_eur * factor:,.0f} - {res.capex_eur:,.0f} - {res.replacement_cost_pv_eur:,.0f} = {eur(res.npv_eur)}")
    else:
        print(f"  NPV = {res.annual_net_cashflow_eur * factor:,.0f} - {res.capex_eur:,.0f} = {eur(res.npv_eur)}  (no battery replacement)")
    verdict = "worth it" if res.npv_eur > 0 else "does NOT pay back within the horizon"
    print(f"  -> Investment {verdict}.")

    print("\nSTEP 9 - Discounted payback")
    if res.discounted_payback_years == float("inf"):
        print("  never within the horizon")
    else:
        print(f"  {res.discounted_payback_years:.2f} years")
    breakeven = res.annual_net_cashflow_eur * factor - res.replacement_cost_pv_eur
    if breakeven > 0:
        cut = 1 - breakeven / res.capex_eur
        if cut > 0:
            print(f"  Break-even CAPEX = {eur(breakeven)}: prices would need to fall by {cut:.0%}")
        else:
            print(f"  Break-even CAPEX = {eur(breakeven)}: there is {abs(cut):.0%} headroom on the price")

    print("\nSTEP 10 - Fairness check: service level and cost per served trip")
    if r.get("assigned_trips_week"):
        planned = float(r["assigned_trips_week"])  # average week over the simulated seasons
        print(f"  Planned trips in the average week: {planned:.1f}")
    else:
        planned = args.boats * 3 * 7  # 3 trips/day per boat, 7 days
        print(f"  Planned trips in the week: {args.boats} boats x 3 trips x 7 days = {planned}")
    for label, sl_key, cost_key in (
        ("baseline", "baseline_service_level", "baseline_eur_per_served_trip"),
        ("scheduled", "scheduled_service_level", "scheduled_eur_per_served_trip"),
        ("DER", "der_service_level", "der_eur_per_served_trip"),
    ):
        if r.get(sl_key):
            sl = float(r[sl_key])
            served = sl * planned
            line = f"  {label:<9}: service level {sl:.1%} -> {served:.1f} trips served, {planned - served:.1f} lost"
            if cost_key in r:
                line += f", {float(r[cost_key]):.2f} EUR per served trip"
            print(line)
    levels = {r.get(k) for k in ("baseline_service_level", "scheduled_service_level", "der_service_level") if r.get(k)}
    if len(levels) > 1:
        print("  Note: the baseline bill is lower partly because it serves fewer trips.")
    else:
        print("  Same service level in both scenarios: the savings compare like with like.")
    print("  Trip revenue is not counted, so the savings are a prudent estimate.")
    print()


if __name__ == "__main__":
    main()