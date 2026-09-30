import pytest

from economics.capex_opex import annual_cost, lcos, CapexBreakdown, OpexBreakdown


def test_annual_cost_basic():
    a_t = annual_cost(opex_t=1000, capex_reinvestment_t=0, c_el=0.15, w_in_t=2000, recovery_value_t=0)
    assert a_t == pytest.approx(1000 + 0.15 * 2000)


def test_annual_cost_with_recovery():
    a_t = annual_cost(opex_t=500, capex_reinvestment_t=2000, c_el=0.1, w_in_t=1000, recovery_value_t=300)
    assert a_t == pytest.approx(500 + 2000 + 100 - 300)


def test_lcos_matches_flat_case():
    # With zero discount rate and constant annual cost/output, LCOS
    # collapses to (CAPEX + n*A) / (n*W).
    n = 5
    a = 1000.0
    w = 5000.0
    result = lcos(capex=10000, annual_costs=[a] * n, energy_outputs=[w] * n, discount_rate=0.0)
    expected = (10000 + n * a) / (n * w)
    assert result == pytest.approx(expected)


def test_lcos_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        lcos(capex=1000, annual_costs=[1, 2, 3], energy_outputs=[1, 2], discount_rate=0.05)


def test_lcos_rejects_zero_energy():
    with pytest.raises(ValueError):
        lcos(capex=1000, annual_costs=[0, 0], energy_outputs=[0, 0], discount_rate=0.05)


def test_capex_breakdown_total():
    capex = CapexBreakdown(bess_kwh=100, pv_wp=50000, evse_units=2)
    expected = 100 * capex.bess_eur_per_kwh + 50000 * capex.pv_eur_per_wp + 2 * capex.evse_eur_per_unit
    assert capex.total() == pytest.approx(expected)


def test_opex_breakdown_total():
    opex = OpexBreakdown(bess_capex=65000, pv_wp=50000, evse_units=2)
    expected = (
        65000 * opex.bess_rate_of_capex
        + 50000 * opex.pv_eur_per_wp_year
        + 2 * opex.evse_eur_per_unit_year
    )
    assert opex.total() == pytest.approx(expected)