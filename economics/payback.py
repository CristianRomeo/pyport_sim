"""
Investment payback analysis: connects the operational grid-cost savings
measured by run_economics.py (grid_energy_cost, from a simulated day) to the
CAPEX/OPEX layer in capex_opex.py, producing the stakeholder-facing KPIs a
techno-economic DSS needs: simple payback, discounted (NPV) payback, and NPV
over a chosen investment horizon.

This module does not re-simulate anything and does not touch PyPort's own
tables; it only combines numbers already computed elsewhere:
  - a daily (or annual) EUR savings figure, typically
    baseline_grid_cost - der_grid_cost from two run_economics.py runs
  - a CapexBreakdown / OpexBreakdown (or a bare CAPEX/OPEX float)

Everything here is deterministic arithmetic, no I/O and no dependency on
DatabaseManager, so it is trivial to unit test and to reuse from a future
Streamlit "what-if" dashboard.
"""

from dataclasses import dataclass
from typing import List, Optional


def annualize_daily_value(daily_value: float, days_per_year: int = 365) -> float:
    """
    Scale a one-day simulation result to an annual figure.

    Args:
        daily_value: EUR (or kWh) measured for one simulated day.
        days_per_year: Operating days per year (365 by default; lower this
            for a marina with a closed season).

    Returns:
        daily_value * days_per_year.
    """
    return daily_value * days_per_year


def simple_payback_years(
    capex_eur: float,
    annual_net_savings_eur: float,
) -> float:
    """
    Simple (non-discounted) payback period in years.

    Args:
        capex_eur: Upfront investment (EUR).
        annual_net_savings_eur: Annual operational savings MINUS annual OPEX
            (EUR/year). Must be positive for a finite payback to exist.

    Returns:
        Years to recover the CAPEX, or float("inf") if annual_net_savings_eur
        is zero or negative (the investment never pays back).
    """
    if annual_net_savings_eur <= 0:
        return float("inf")
    return capex_eur / annual_net_savings_eur


def npv(
    capex_eur: float,
    annual_net_cashflow_eur: float,
    discount_rate: float,
    years: int,
) -> float:
    """
    Net Present Value of the investment over a fixed horizon, assuming a
    constant annual net cash flow (savings - OPEX) every year.

    Args:
        capex_eur: Upfront investment (EUR), paid at year 0.
        annual_net_cashflow_eur: Constant annual savings minus OPEX (EUR/year).
        discount_rate: i, e.g. 0.07 for 7% (same convention as capex_opex.lcos).
        years: Investment horizon / asset lifetime (years).

    Returns:
        NPV in EUR. Positive means the investment is worthwhile over that
        horizon at that discount rate.
    """
    discounted = sum(
        annual_net_cashflow_eur / (1 + discount_rate) ** t
        for t in range(1, years + 1)
    )
    return discounted - capex_eur


def discounted_payback_years(
    capex_eur: float,
    annual_net_cashflow_eur: float,
    discount_rate: float,
    max_years: int = 30,
) -> float:
    """
    Discounted payback period: the year in which cumulative discounted cash
    flows first cover the CAPEX, linearly interpolated within that year for
    a fractional result.

    Args:
        capex_eur: Upfront investment (EUR).
        annual_net_cashflow_eur: Constant annual savings minus OPEX (EUR/year).
        discount_rate: i, e.g. 0.07 for 7%.
        max_years: Stop searching after this many years (default 30).

    Returns:
        Years to recover the CAPEX on a discounted basis, or float("inf") if
        it is not recovered within max_years (including when
        annual_net_cashflow_eur <= 0).
    """
    if annual_net_cashflow_eur <= 0:
        return float("inf")

    cumulative = -capex_eur
    for t in range(1, max_years + 1):
        discounted_cf = annual_net_cashflow_eur / (1 + discount_rate) ** t
        previous_cumulative = cumulative
        cumulative += discounted_cf
        if cumulative >= 0:
            # Linearly interpolate within year t for a fractional year.
            fraction = -previous_cumulative / discounted_cf
            return (t - 1) + fraction

    return float("inf")


@dataclass
class PaybackResult:
    """Bundle of payback KPIs for a single investment scenario."""

    capex_eur: float
    annual_savings_eur: float
    annual_opex_eur: float
    annual_net_cashflow_eur: float
    simple_payback_years: float
    discounted_payback_years: float
    npv_eur: float
    discount_rate: float
    horizon_years: int


def evaluate_investment(
    capex_eur: float,
    daily_savings_eur: float,
    annual_opex_eur: float = 0.0,
    discount_rate: float = 0.07,
    horizon_years: int = 20,
    days_per_year: int = 365,
) -> PaybackResult:
    """
    One-call convenience wrapper: turn a daily operational saving plus a
    CAPEX/OPEX pair into the full set of payback KPIs.

    Args:
        capex_eur: Upfront investment, e.g. CapexBreakdown(...).total().
        daily_savings_eur: baseline_grid_cost - der_grid_cost for one
            simulated day (EUR), as printed by run_economics.py.
        annual_opex_eur: Annual OPEX, e.g. OpexBreakdown(...).total().
        discount_rate: i, e.g. 0.07 for 7% (ECO-01: indicative 6-8%).
        horizon_years: Investment horizon / asset lifetime for NPV (years).
        days_per_year: Operating days per year (365 by default).

    Returns:
        A PaybackResult with simple payback, discounted payback, and NPV.
    """
    annual_savings_eur = annualize_daily_value(daily_savings_eur, days_per_year)
    annual_net_cashflow_eur = annual_savings_eur - annual_opex_eur

    return PaybackResult(
        capex_eur=capex_eur,
        annual_savings_eur=annual_savings_eur,
        annual_opex_eur=annual_opex_eur,
        annual_net_cashflow_eur=annual_net_cashflow_eur,
        simple_payback_years=simple_payback_years(capex_eur, annual_net_cashflow_eur),
        discounted_payback_years=discounted_payback_years(
            capex_eur, annual_net_cashflow_eur, discount_rate, max_years=horizon_years + 10
        ),
        npv_eur=npv(capex_eur, annual_net_cashflow_eur, discount_rate, horizon_years),
        discount_rate=discount_rate,
        horizon_years=horizon_years,
    )