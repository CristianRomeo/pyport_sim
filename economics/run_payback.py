"""
Orchestrator: turn two run_economics.py results (a baseline and a DER
scenario) plus a CAPEX/OPEX assumption into investment payback KPIs.

Typical use: after running the baseline and the DER-enabled scenario and
computing their grid_energy_cost with run_economics.py, pass both totals
here together with the installed PV/BESS sizing:

    python -m economics.run_payback \\
        --baseline-daily-cost 42.13 --der-daily-cost 6.64 \\
        --bess-kwh 100 --pv-wp 10000 \\
        --discount-rate 0.07 --horizon-years 20

This does not touch any PyPort database - it is pure arithmetic over the
numbers already printed by run_economics.py, using the CapexBreakdown /
OpexBreakdown defaults from capex_opex.py (overridable via CLI flags).
"""

import argparse

from .capex_opex import CapexBreakdown, OpexBreakdown
from .payback import evaluate_investment


def main():
    parser = argparse.ArgumentParser(
        description="Compute investment payback KPIs from two run_economics.py results"
    )
    parser.add_argument("--baseline-daily-cost", type=float, required=True,
                         help="Grid energy cost (EUR) for one simulated day WITHOUT PV/BESS")
    parser.add_argument("--der-daily-cost", type=float, required=True,
                         help="Grid energy cost (EUR) for one simulated day WITH PV/BESS")
    parser.add_argument("--days-per-year", type=float, default=365,
                         help="Operating days per year (default 365)")

    parser.add_argument("--bess-kwh", type=float, default=0.0, help="Installed BESS capacity (kWh)")
    parser.add_argument("--pv-wp", type=float, default=0.0, help="Installed PV capacity (Wp)")
    parser.add_argument("--evse-units", type=int, default=0, help="New EVSE/charger units (if any)")

    parser.add_argument("--bess-eur-per-kwh", type=float, default=None,
                         help="Override CapexBreakdown.bess_eur_per_kwh default (EUR/kWh)")
    parser.add_argument("--pv-eur-per-wp", type=float, default=None,
                         help="Override CapexBreakdown.pv_eur_per_wp default (EUR/Wp)")

    parser.add_argument("--discount-rate", type=float, default=0.07,
                         help="Discount rate i, e.g. 0.07 for 7%% (default 0.07)")
    parser.add_argument("--horizon-years", type=int, default=20,
                         help="Investment horizon / asset lifetime for NPV (default 20)")
    args = parser.parse_args()

    daily_savings = args.baseline_daily_cost - args.der_daily_cost

    capex = CapexBreakdown(
        bess_kwh=args.bess_kwh,
        pv_wp=args.pv_wp,
        evse_units=args.evse_units,
        **({"bess_eur_per_kwh": args.bess_eur_per_kwh} if args.bess_eur_per_kwh is not None else {}),
        **({"pv_eur_per_wp": args.pv_eur_per_wp} if args.pv_eur_per_wp is not None else {}),
    )
    opex = OpexBreakdown(
        bess_capex=args.bess_kwh * capex.bess_eur_per_kwh,
        pv_wp=args.pv_wp,
        evse_units=args.evse_units,
    )

    result = evaluate_investment(
        capex_eur=capex.total(),
        daily_savings_eur=daily_savings,
        annual_opex_eur=opex.total(),
        discount_rate=args.discount_rate,
        horizon_years=args.horizon_years,
        days_per_year=args.days_per_year,
    )

    print(f"Daily savings (baseline - DER):  EUR {daily_savings:.2f}")
    print(f"CAPEX (PV + BESS + EVSE):        EUR {capex.total():,.2f}")
    print(f"Annual OPEX:                     EUR {opex.total():,.2f}")
    print(f"Annual gross savings:            EUR {result.annual_savings_eur:,.2f}")
    print(f"Annual net cash flow:            EUR {result.annual_net_cashflow_eur:,.2f}")
    print(f"Simple payback:                  {result.simple_payback_years:.2f} years")
    print(f"Discounted payback (i={args.discount_rate:.0%}):       {result.discounted_payback_years:.2f} years")
    print(f"NPV over {args.horizon_years} years (i={args.discount_rate:.0%}): EUR {result.npv_eur:,.2f}")


if __name__ == "__main__":
    main()