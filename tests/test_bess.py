from datetime import date
import numpy as np
from bess_sim import cost, sizing, dispatch, grid, tenders


def test_capex_positive_and_scales_with_duration():
    a = cost.capex_breakdown(cost.CostInputs(duration_h=2))
    b = cost.capex_breakdown(cost.CostInputs(duration_h=4))
    assert a["total"] > 0
    assert b["per_poi_mwh_crore"] < a["per_poi_mwh_crore"]   # PCS amortised over more MWh


def test_breakeven_zero_npv():
    c = cost.CostInputs()
    t = cost.breakeven_tariff(c)
    assert abs(cost.npv(c.wacc, cost.cashflows(c, t))) < 1e-4


def test_cheaper_cells_lower_breakeven():
    hi = cost.breakeven_tariff(cost.CostInputs(dc_block_usd_per_kwh=90))
    lo = cost.breakeven_tariff(cost.CostInputs(dc_block_usd_per_kwh=55))
    assert lo < hi


def test_vgf_reduces_breakeven():
    assert cost.breakeven_tariff(cost.CostInputs(vgf_inr_lakh_per_mwh=46)) < cost.breakeven_tariff(cost.CostInputs())


def test_implied_capex_monotone_in_tariff():
    c = cost.CostInputs()
    assert cost.implied_capex_per_mwh(c, 3.0) > cost.implied_capex_per_mwh(c, 2.0)


def test_pib_unit_conversion():
    # 2.38 lakh at 2 cycles of 2h: ~Rs 1.96/kWh; PIB quotes ~2.1 for recent bids
    assert 1.8 < tenders.inr_per_kwh(2.38, 2, 2.0) < 2.2


def test_peak_shave_exact():
    x = np.full((2, 24), 80.0); x[0, 19:22] = 120.0
    r = sizing.size_for_peak_shave(x, 100.0)
    assert r["mw"] == 20.0 and r["mwh_poi"] == 60.0 and r["recharge_feasible"]


def test_firming_unfirmable_when_no_surplus():
    x = np.full((1, 24), 10.0)
    r = sizing.size_for_re_firming(x, 20.0)
    assert r["unfirmable_day_share"] == 1.0


def test_arbitrage_respects_rte_and_nonneg():
    p = dispatch.synthetic_prices(days=6)
    r = dispatch.simulate_arbitrage(p, 10, 2)
    assert r["annual_revenue_inr_lakh_per_mw"] > 0
    assert 0 < r["cycles_per_day"] <= 2.5          # multi-cycle is legitimate with two price peaks
    eta = 0.85 ** 0.5
    c, d, _ = dispatch._solve_day(p[0], 10, 20, eta, eta, 0.0)
    assert d.sum() <= c.sum() * 0.85 + 1e-6          # energy out cannot exceed energy in x RTE
    assert c.max() <= 10 + 1e-9 and d.max() <= 10 + 1e-9
    flat = np.full((3, 24), 5.0)
    assert dispatch.simulate_arbitrage(flat, 10, 2)["annual_revenue_inr_lakh_per_mw"] < 1e-6


def test_ists_waiver():
    assert grid.ists_waiver_pct(date(2027, 3, 1), True) == 100
    assert grid.ists_waiver_pct(date(2029, 1, 1), True) == 0
    assert grid.ists_waiver_pct(date(2025, 1, 1), False) == 100
    assert grid.ists_waiver_pct(date(2026, 1, 1), False) == 75
    assert grid.ists_waiver_pct(date(2026, 7, 1), False) == 50


def test_compliance():
    assert grid.check_tender_compliance(0.86, 0.96) == []
    assert len(grid.check_tender_compliance(0.80, 0.90)) == 2


def test_tender_analysis_runs():
    df = tenders.analyse()
    assert len(df) >= 8 and df["model_breakeven"].gt(0).all()
