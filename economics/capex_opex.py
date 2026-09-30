"""
CAPEX/OPEX and Levelized Cost of Storage (LCOS)

    LCOS = (CAPEX + sum_t A_t/(1+i)^t) / sum_t (W_out,t / (1+i)^t)
    A_t  = OPEX_t + CAPEX_re,t + c_el * W_in - R_t

"""

from dataclasses import dataclass
from typing import List, Optional


def annual_cost(
    opex_t: float,
    capex_reinvestment_t: float,
    c_el: float,
    w_in_t: float,
    recovery_value_t: float = 0.0,
) -> float:
    """
    Annual cost A_t for year t (Chapter 2, Eq. annualcost).

    Args:
        opex_t: Operational expenditure in year t (EUR).
        capex_reinvestment_t: Reinvestment in storage components in year t
            (EUR).
        c_el: Cost of electricity supply (EUR/kWh) in year t.
        w_in_t: Energy charged into storage in year t (kWh).
        recovery_value_t: Residual/recovery value realized in year t (EUR),
           
    Returns:
        A_t (EUR).
    """
    return opex_t + capex_reinvestment_t + c_el * w_in_t - recovery_value_t


def lcos(
    capex: float,
    annual_costs: List[float],
    energy_outputs: List[float],
    discount_rate: float,
) -> float:
    """
    Levelized Cost of Storage (Chapter 2, Eq. lcos).

    Args:
        capex: Upfront capital expenditure (EUR).
        annual_costs: [A_1, ..., A_n] (EUR), e.g. from annual_cost() per year.
        energy_outputs: [W_out,1, ..., W_out,n] (kWh) discharged from storage
            per year. Must be the same length as annual_costs.
        discount_rate: i, e.g. 0.07 for 7% (ECO-01: indicative 6-8%).

    Returns:
        LCOS in EUR/kWh.

    Raises:
        ValueError: If annual_costs and energy_outputs have different
            lengths, or if the discounted energy denominator is zero.
    """
    if len(annual_costs) != len(energy_outputs):
        raise ValueError("annual_costs and energy_outputs must have the same length")

    discounted_costs = sum(
        a_t / (1 + discount_rate) ** t for t, a_t in enumerate(annual_costs, start=1)
    )
    discounted_energy = sum(
        w_t / (1 + discount_rate) ** t for t, w_t in enumerate(energy_outputs, start=1)
    )
    if discounted_energy == 0:
        raise ValueError("Discounted energy output is zero - cannot compute LCOS")

    return (capex + discounted_costs) / discounted_energy


@dataclass
class CapexBreakdown:
    """
    CAPEX line items for one asset class. All values in EUR.

    TODO: the *_per_unit defaults below are order-of-magnitude references
    from the inventory, not Funchal quotes:
      - bess_eur_per_kwh: BES-09/10 (~550-700 USD/kWh installed, generic
        US-market source)
      - pv_eur_per_wp: PV-08 (~1.8-3.0 EUR/Wp, DOE/NREL benchmark)
      - evse_eur_per_unit: EVS-05 (~USD 28,000/50kW unit, US commercial
        DC fast charger, non-marine)
    Replace with real supplier quotes once available (several are already
    requested - see the Research Log).
    """

    bess_kwh: float = 0.0
    bess_eur_per_kwh: float = 650.0       # TODO: BES-09/10, confirm with quote
    pv_wp: float = 0.0
    pv_eur_per_wp: float = 2.4            # TODO: PV-08, confirm with quote
    evse_units: int = 0
    evse_eur_per_unit: float = 26000.0    # TODO: EVS-05, confirm with quote

    def total(self) -> float:
        """Sum of PV + BESS + EVSE CAPEX (EUR)."""
        return (
            self.bess_kwh * self.bess_eur_per_kwh
            + self.pv_wp * self.pv_eur_per_wp
            + self.evse_units * self.evse_eur_per_unit
        )


@dataclass
class OpexBreakdown:
    """
    OPEX line items for one asset class, per year. All values in EUR/year.

    TODO: the *_rate defaults are order-of-magnitude references, not
    Funchal-specific:
      - bess_rate_of_capex: BES-11 (~2-2.5%/year of CAPEX, generic benchmark)
      - pv_eur_per_wp_year: PV-09 (~35-60 EUR/kWp/year, DOE/NREL)
      - evse_eur_per_unit_year: EVS-06 (~USD 400/year/charger, US DOE)
    """

    bess_capex: float = 0.0
    bess_rate_of_capex: float = 0.0225   # TODO: BES-11
    pv_wp: float = 0.0
    pv_eur_per_wp_year: float = 0.045    # TODO: PV-09 (45 EUR/kWp/year -> EUR/Wp/year)
    evse_units: int = 0
    evse_eur_per_unit_year: float = 370.0  # TODO: EVS-06

    def total(self) -> float:
        """Sum of PV + BESS + EVSE OPEX for one year (EUR)."""
        return (
            self.bess_capex * self.bess_rate_of_capex
            + self.pv_wp * self.pv_eur_per_wp_year
            + self.evse_units * self.evse_eur_per_unit_year
        )
