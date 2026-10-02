import pytest

from economics.payback import (
    annualize_daily_value,
    simple_payback_years,
    npv,
    discounted_payback_years,
    evaluate_investment,
)


def test_annualize_daily_value():
    assert annualize_daily_value(10.0, days_per_year=365) == pytest.approx(3650.0)
    assert annualize_daily_value(10.0, days_per_year=300) == pytest.approx(3000.0)


def test_simple_payback_years_basic():
    assert simple_payback_years(capex_eur=1000, annual_net_savings_eur=100) == pytest.approx(10.0)


def test_simple_payback_years_nonpositive_cashflow_is_infinite():
    assert simple_payback_years(capex_eur=1000, annual_net_savings_eur=0) == float("inf")
    assert simple_payback_years(capex_eur=1000, annual_net_savings_eur=-50) == float("inf")


def test_npv_zero_discount_rate_is_linear():
    # With 0% discount, NPV over n years = n * cashflow - capex.
    result = npv(capex_eur=1000, annual_net_cashflow_eur=100, discount_rate=0.0, years=20)
    assert result == pytest.approx(20 * 100 - 1000)


def test_npv_positive_discount_rate_is_lower_than_undiscounted():
    undiscounted = npv(capex_eur=1000, annual_net_cashflow_eur=100, discount_rate=0.0, years=20)
    discounted = npv(capex_eur=1000, annual_net_cashflow_eur=100, discount_rate=0.07, years=20)
    assert discounted < undiscounted


def test_discounted_payback_years_matches_simple_at_zero_discount():
    simple = simple_payback_years(capex_eur=1000, annual_net_savings_eur=100)
    discounted = discounted_payback_years(
        capex_eur=1000, annual_net_cashflow_eur=100, discount_rate=0.0, max_years=30
    )
    assert discounted == pytest.approx(simple)


def test_discounted_payback_years_longer_than_simple_with_positive_rate():
    simple = simple_payback_years(capex_eur=1000, annual_net_savings_eur=100)
    discounted = discounted_payback_years(
        capex_eur=1000, annual_net_cashflow_eur=100, discount_rate=0.07, max_years=30
    )
    assert discounted > simple


def test_discounted_payback_years_infinite_when_never_recovered():
    # Tiny cashflow relative to CAPEX within the search horizon.
    result = discounted_payback_years(
        capex_eur=1_000_000, annual_net_cashflow_eur=100, discount_rate=0.07, max_years=10
    )
    assert result == float("inf")


def test_discounted_payback_years_nonpositive_cashflow_is_infinite():
    assert discounted_payback_years(capex_eur=1000, annual_net_cashflow_eur=0, discount_rate=0.05) == float("inf")
    assert discounted_payback_years(capex_eur=1000, annual_net_cashflow_eur=-10, discount_rate=0.05) == float("inf")


def test_evaluate_investment_end_to_end():
    result = evaluate_investment(
        capex_eur=50000,
        daily_savings_eur=35.49,
        annual_opex_eur=1500,
        discount_rate=0.07,
        horizon_years=20,
    )
    assert result.annual_savings_eur == pytest.approx(35.49 * 365)
    assert result.annual_net_cashflow_eur == pytest.approx(35.49 * 365 - 1500)
    assert result.simple_payback_years == pytest.approx(
        50000 / (35.49 * 365 - 1500)
    )
    assert result.npv_eur > 0  # strongly profitable investment in this example
    assert result.discounted_payback_years > result.simple_payback_years


def test_evaluate_investment_unprofitable_case_has_infinite_payback():
    result = evaluate_investment(
        capex_eur=50000,
        daily_savings_eur=0.50,   # tiny savings
        annual_opex_eur=1500,     # OPEX alone exceeds savings
        discount_rate=0.07,
        horizon_years=20,
    )
    assert result.annual_net_cashflow_eur < 0
    assert result.simple_payback_years == float("inf")
    assert result.discounted_payback_years == float("inf")
    assert result.npv_eur < 0