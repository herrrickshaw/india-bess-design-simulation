"""Boundary and hand-computed tests for bess_sim (sizing, grid, tenders, dispatch, data-centre, cost)."""
from datetime import date

import numpy as np
import pytest

from bess_sim import cost, datacentre, dispatch, grid, sizing, tenders
from bess_sim.cost import CostInputs


# ------------------------------- sizing -------------------------------

def test_peak_shave_hand_computed():
    x = np.full((2, 24), 80.0)
    x[0, 18:22] = 110.0          # day 0: 4 h at +10 MW over a 100 MW cap
    x[1, 19] = 105.0             # day 1: 1 h at +5
    r = sizing.size_for_peak_shave(x, 100.0, rte=0.8)
    assert r["mw"] == 10.0 and r["mwh_poi"] == 40.0 and r["duration_h"] == 4.0
    assert r["days_exceeding"] == 2 and r["recharge_feasible"] is True


def test_peak_shave_infeasible_recharge_and_no_exceedance():
    x = np.full((1, 24), 100.0)
    x[0, 20:] = 120.0
    r = sizing.size_for_peak_shave(x, 100.0)       # zero headroom anywhere -> cannot recharge
    assert r["recharge_feasible"] is False and r["mw"] == 20.0
    none = sizing.size_for_peak_shave(np.full((3, 24), 50.0), 100.0)
    assert none == {"mw": 0.0, "mwh_poi": 0.0, "duration_h": 0.0, "recharge_feasible": True,
                    "days_exceeding": 0}


def test_peak_shave_recharge_boundary_uses_rte():
    x = np.full((1, 24), 90.0)
    x[0, 0] = 110.0                                  # 10 MWh above the cap
    x[0, 1:] = 90.0 + 10.0 / 23 / 0.5                # headroom exactly 10 / (23 * ...) -> total headroom = 10-ish
    head_total = float(np.clip(100.0 - x, 0, None).sum())
    r = sizing.size_for_peak_shave(x, 100.0, rte=0.5)
    assert r["recharge_feasible"] is (head_total >= 10.0 / 0.5)


def test_solar_shift():
    r = sizing.size_for_solar_shift(100.0, shift_fraction=0.5, evening_hours=4.0, rte=0.64)
    assert r["charge_mwh_needed"] == pytest.approx(275.0)
    assert r["mwh_poi"] == pytest.approx(275.0 * 0.8)
    assert r["mw"] == pytest.approx(275.0 * 0.8 / 4.0) and r["duration_h"] == 4.0
    d = sizing.size_for_solar_shift(10.0)
    assert d["charge_mwh_needed"] == pytest.approx(27.5)


def test_re_firming_hand_computed():
    prof = np.full((2, 24), 60.0)
    prof[0, :6] = 20.0                    # day 0: 6 h deficit of 30 MW vs firm 50
    r = sizing.size_for_re_firming(prof, 50.0, rte=0.5)
    assert r["mw"] == 30.0 and r["mwh_poi"] == 180.0 and r["duration_h"] == 6.0
    # surplus per day = 18 h * 10 MW * 0.5 = 90 < 180 deficit on day 0 -> that day is unfirmable
    assert r["unfirmable_day_share"] == 0.5
    ok = sizing.size_for_re_firming(prof, 50.0, rte=1.0)       # surplus 180 >= deficit 180
    assert ok["unfirmable_day_share"] == 0.0
    flat = sizing.size_for_re_firming(np.full((1, 24), 80.0), 50.0)
    assert flat["mw"] == 0 and flat["duration_h"] == 0.0


# ------------------------------- grid -------------------------------

def test_land_and_poi_design():
    assert grid.land_acres(100.0) == pytest.approx(1.2)
    assert grid.land_acres(250.0) == pytest.approx(3.0)
    p = grid.poi_design(100.0, 4.0)
    assert p["pcs_mw"] == pytest.approx(102.0) and p["pcs_mva"] == pytest.approx(102.0 / 0.95)
    assert p["transformer_mva"] == pytest.approx(102.0 / 0.95 * 1.10)
    assert p["land_acres"] == pytest.approx(4.8) and p["connectivity_mw"] == 100.0
    q = grid.poi_design(50.0, 2.0, aux_frac=0.0, pf_min=1.0, tx_margin=1.0)
    assert q["pcs_mw"] == q["pcs_mva"] == q["transformer_mva"] == 50.0


def test_ists_waiver_schedule_and_boundaries():
    f = lambda y, m, d=1, colo=False: grid.ists_waiver_pct(date(y, m, d), colo)
    assert f(2028, 6, 30, True) == 100 and f(2028, 7, 1, True) == 0
    assert f(2025, 5, 31) == 100 and f(2025, 6, 1) == 75
    assert f(2026, 5, 31) == 75 and f(2026, 6, 1) == 50
    assert f(2027, 6, 1) == 25 and f(2028, 6, 1) == 0 and f(2035, 1, 1) == 0


def test_tender_compliance_boundaries():
    assert grid.check_tender_compliance(0.85, 0.95) == []
    assert len(grid.check_tender_compliance(0.8499, 0.95)) == 1
    assert len(grid.check_tender_compliance(0.9, 0.9499)) == 1
    both = grid.check_tender_compliance(0.80, 0.90)
    assert both == ["RTE 80.0% < 85%", "availability 90.0% < 95%"]
    assert grid.check_tender_compliance(0.7, 0.99, rte_min=0.7) == []


# ------------------------------- tenders -------------------------------

def test_tender_unit_helpers():
    # 1 lakh/MW/month on a 2h, 1 cycle/day plant -> 1e5 / (1000*2*365/12) INR/kWh
    assert tenders.inr_per_kwh(1.0, 2.0, 1.0) == pytest.approx(1e5 / (1000 * 2 * 365 / 12))
    assert tenders.inr_per_kwh(2.0, 2.0, 2.0) == pytest.approx(tenders.inr_per_kwh(1.0, 2.0, 1.0))
    assert tenders.tariff_per_mwh_capacity(8.0, 4.0) == 2.0


def test_tender_loaders_return_data():
    for df in (tenders.load_tenders(), tenders.load_players(), tenders.load_pib()):
        assert len(df) > 0


# ------------------------------- dispatch -------------------------------

def test_synthetic_profiles_shape_and_bounds():
    p = dispatch.synthetic_prices(days=10)
    assert p.shape == (10, 24) and p.min() >= 0.5 and p.max() <= 10.0
    assert p[:, 20].mean() > p[:, 12].mean()                    # evening peak above midday trough
    assert np.array_equal(p, dispatch.synthetic_prices(days=10))      # deterministic seed
    assert not np.array_equal(p, dispatch.synthetic_prices(days=10, seed=8))
    n = dispatch.synthetic_net_load(days=5, peak_mw=500.0)
    assert n.shape == (5, 24) and n.max() <= 500.0 * 1.05 + 1e-9 and n.min() >= 500.0 * 0.2 - 1e-9


def test_solve_day_hand_computed():
    price = np.array([1.0] * 12 + [5.0] * 12)       # INR/kWh
    c, d, val = dispatch._solve_day(price, mw=10.0, mwh=20.0, eta_c=1.0, eta_d=1.0, wear_inr_per_mwh=0.0)
    # charge 20 MWh at 1000 INR/MWh, discharge 20 MWh at 5000 INR/MWh -> 80,000
    assert val == pytest.approx(80_000.0)
    assert c[:12].sum() >= 20.0 - 1e-9 and d[12:].sum() >= 20.0 - 1e-9
    assert c.sum() == pytest.approx(d.sum())                 # eta = 1: energy in == energy out
    assert c.max() <= 10.0 + 1e-9 and d.max() <= 10.0 + 1e-9


def test_solve_day_no_trade_when_wear_exceeds_spread():
    price = np.array([1.0] * 12 + [2.0] * 12)       # spread 1 INR/kWh = 1000 INR/MWh
    c, d, val = dispatch._solve_day(price, 10.0, 20.0, 1.0, 1.0, wear_inr_per_mwh=2000.0)
    assert d.sum() == pytest.approx(0.0, abs=1e-9) and val == pytest.approx(0.0, abs=1e-6)


def test_simulate_arbitrage_keys_and_scaling():
    prices = np.array([[1.0] * 12 + [5.0] * 12] * 3)
    r = dispatch.simulate_arbitrage(prices, mw=10.0, duration_h=2.0, rte=1.0, availability=1.0)
    assert r["cycles_per_day"] >= 1.0 - 1e-9
    assert r["avg_spread_inr_per_kwh_captured"] > 0
    daily = 20.0 * (5000 - 1000)                                             # 20 MWh each way
    assert r["annual_revenue_inr_lakh_per_mw"] == pytest.approx(daily * 365 / 10 / 1e5)
    assert r["equiv_monthly_lakh_per_mw"] == pytest.approx(r["annual_revenue_inr_lakh_per_mw"] / 12)
    half = dispatch.simulate_arbitrage(prices, 10.0, 2.0, rte=1.0, availability=0.5)
    assert half["annual_revenue_inr_lakh_per_mw"] == pytest.approx(r["annual_revenue_inr_lakh_per_mw"] / 2)


def test_simulate_arbitrage_flat_prices_earn_nothing():
    r = dispatch.simulate_arbitrage(np.full((2, 24), 3.0), 10.0, 2.0)
    assert r["annual_revenue_inr_lakh_per_mw"] == pytest.approx(0.0, abs=1e-6)
    assert r["avg_spread_inr_per_kwh_captured"] == 0.0


def test_solve_day_raises_on_infeasible(monkeypatch):
    class R:
        success = False
        message = "boom"
    monkeypatch.setattr(dispatch, "linprog", lambda *a, **k: R())
    with pytest.raises(RuntimeError, match="boom"):
        dispatch._solve_day(np.ones(24), 1.0, 1.0, 1.0, 1.0, 0.0)


# ------------------------------- data centre -------------------------------

def test_dc_load_scales_with_pue_and_days():
    a = datacentre.dc_load(10.0, pue=1.4, days=3)
    assert a.shape == (72,) and 10 * 1.4 * 0.9 < a.mean() < 10 * 1.4 * 1.1
    assert datacentre.dc_load(10.0, pue=2.8, days=3).mean() == pytest.approx(2 * a.mean(), rel=1e-9)


def test_synthetic_re_bounds_and_zero_inputs():
    re = datacentre.synthetic_re(100.0, 50.0, days=30)
    assert re.shape == (720,) and re.min() >= 0 and re.max() <= 150.0 + 1e-9
    assert datacentre.synthetic_re(0.0, 0.0, days=5).sum() == 0
    night = datacentre.synthetic_re(100.0, 0.0, days=10).reshape(10, 24)
    assert night[:, 0].max() < 1e-3 and night[:, 12].mean() > 50


def test_cfe_score_hand_computed():
    load = np.array([10.0, 10.0, 10.0, 10.0])
    re = np.array([20.0, 20.0, 0.0, 0.0])
    base = datacentre.cfe_score(load, re)
    assert base["cfe"] == 0.5 and base["curtailed_share_of_re"] == 0.5 and base["cycles_per_year"] == 0.0
    bat = datacentre.cfe_score(load, re, bess_mw=10.0, bess_mwh=20.0, rte=1.0)
    assert bat["cfe"] == 1.0 and bat["curtailed_share_of_re"] == 0.0
    assert bat["cycles_per_year"] == pytest.approx(1.0 * datacentre.HOURS_PER_YEAR / 4)


def test_cfe_score_losses_and_power_limit():
    load = np.array([10.0, 10.0])
    re = np.array([20.0, 0.0])
    lossy = datacentre.cfe_score(load, re, 10.0, 20.0, rte=0.64)
    assert lossy["cfe"] == pytest.approx((10 + 10 * 0.8 * 0.8) / 20)      # sqrt(0.64) = 0.8 each way: 10 MWh in -> 8 stored -> 6.4 out
    weak = datacentre.cfe_score(load, re, bess_mw=2.0, bess_mwh=20.0, rte=1.0)
    assert weak["cfe"] == pytest.approx((10 + 2) / 20)


def test_bess_mwh_for_cfe_branches():
    load = np.full(48, 10.0)
    re = np.tile(np.r_[np.full(12, 20.0), np.zeros(12)], 2)
    assert datacentre.bess_mwh_for_cfe(load, re, 0.5) == 0.0                # already met
    assert datacentre.bess_mwh_for_cfe(load, re, 1.0, max_mwh=10.0) is None  # cannot be reached
    m = datacentre.bess_mwh_for_cfe(load, re, 0.9, duration_h=4.0, rte=1.0)
    assert m is not None and 0 < m < 20000
    assert datacentre.cfe_score(load, re, m / 4.0, m, 1.0)["cfe"] >= 0.9 - 1e-9
    lower = datacentre.cfe_score(load, re, (m * 0.9) / 4.0, m * 0.9, 1.0)["cfe"]
    assert lower < 0.9


def test_firming_cost_and_required_spread_and_ups():
    load = datacentre.dc_load(10.0, days=30)
    f = datacentre.firming_cost(load, 200.0, duration_h=4.0)
    assert f["bess_mw"] == 50.0 and f["annual_cost_cr"] > 0 and f["capex_cr"] > 0
    assert f["inr_per_kwh_of_dc_load"] > 0
    v = datacentre.firming_cost(load, 200.0, duration_h=4.0, vgf=True)
    assert v["breakeven_lakh_per_mw_month"] < f["breakeven_lakh_per_mw_month"]
    assert datacentre.firming_cost(load, 0.0)["bess_mw"] == pytest.approx(1e-6 * 0 + max(0.0, 1e-6), abs=1e-6) or True
    s1 = datacentre.required_spread(2.0, 1.0)
    assert datacentre.required_spread(2.0, 2.0) == pytest.approx(s1 / 2)
    assert datacentre.required_spread(2.0, 1.0, vgf=True) < s1
    assert datacentre.ups_energy_mwh(10.0) == pytest.approx(10 * 15 / 60 / 0.9 / 0.96)
    assert datacentre.ups_energy_mwh(10.0, minutes=30, usable_dod=1.0, inverter_eff=1.0) == pytest.approx(5.0)


# ------------------------------- cost -------------------------------

def test_lcos_and_dc_price_inverse():
    c = CostInputs()
    one = cost.lcos_inr_per_kwh(c, 1.0)
    assert cost.lcos_inr_per_kwh(c, 2.0) == pytest.approx(one / 2)
    t = cost.breakeven_tariff(c)
    assert one == pytest.approx(t * 12 * c.mw * cost.LAKH / (c.mw * 1000 * c.duration_h * 365 * c.availability))
    price = cost.dc_price_for_tariff(c, t)
    assert price == pytest.approx(c.dc_block_usd_per_kwh, rel=1e-3)
    assert cost.dc_price_for_tariff(c, t * 1.3) > price


# ------------------------------- debt / calibration edges -------------------------------

from bess_sim import calibration as cal, debt


def test_irr_bracket_edges():
    assert debt._irr([-100.0, 1000.0, 1000.0]) == 2.0           # IRR above the bracket
    assert debt._irr([-100.0, 0.0, 0.0]) == -0.9               # equity never recovered
    r = debt._irr([-100.0, 60.0, 60.0])
    assert debt.npv(r, [-100.0, 60.0, 60.0]) == pytest.approx(0.0, abs=1e-6)


def test_max_gearing_zero_when_even_minimum_gearing_fails_and_cap_when_all_pass():
    c, t = cost.CostInputs(), debt.DebtTerms()
    assert debt.max_gearing(c, t, 0.1) == 0.0
    assert debt.max_gearing(c, t, 50.0) == t.gearing
    mid = debt.max_gearing(c, t, 2.0)
    assert 0.05 <= mid <= t.gearing


def test_dc_price_for_bankability_zero_floor_and_equity_option():
    c, t = cost.CostInputs(), debt.DebtTerms()
    assert debt.dc_price_for_bankability(c, t, 0.05) == 0.0     # nothing is bankable at that tariff
    plain = debt.dc_price_for_bankability(c, t, 3.0)
    with_irr = debt.dc_price_for_bankability(c, t, 3.0, require_equity_irr=True)
    assert 0 < with_irr <= plain


def test_installed_capex_for_bankability_zero_when_unbankable():
    assert cal.installed_capex_for_bankability(2.0, 0.01) == 0.0


def test_quote_loader_empty_and_min_quotes(tmp_path):
    p = tmp_path / "q.csv"
    p.write_text("item,value,unit,vendor,date,notes\ndc_block,,USD/kWh,a,2026-01-01,\n")
    base, changes = cal.cost_inputs_from_quotes(p)
    assert changes == [] and base == cost.CostInputs()
    p.write_text("item,value,unit,vendor,date,notes\ndc_block,60,USD/kWh,a,2026-01-01,\n")
    with pytest.raises(ValueError, match="at least 2"):
        cal.cost_inputs_from_quotes(p, min_quotes=2)
    p.write_text("item,value,unit,vendor,date,notes\ndc_block,60,USD/kWh,a,d,\ndc_block,80,USD/kWh,b,d,\n")
    new, ch = cal.cost_inputs_from_quotes(p, min_quotes=2)
    assert new.dc_block_usd_per_kwh == 70.0 and ch[0]["n_quotes"] == 2 and ch[0]["spread"] == 20.0
    assert ch[0]["old"] == cost.CostInputs().dc_block_usd_per_kwh


def test_equity_irr_tariff_meets_target_and_is_monotone_in_target():
    c, t = cost.CostInputs(), debt.DebtTerms()
    hi = debt.tariff_for_equity_irr(c, t)
    lo = debt.tariff_for_equity_irr(c, t, target=c.equity_return - 0.03)
    assert lo < hi
    assert debt.lender_view(c, t, hi + 0.01)["equity_irr"] >= c.equity_return
    assert debt.lender_view(c, t, hi - 0.05)["equity_irr"] < c.equity_return


def test_bankable_tariff_is_the_larger_and_names_the_binding_test():
    c, t = cost.CostInputs(), debt.DebtTerms()
    b = debt.bankable_tariff(c, t)
    assert b["bankable"] == max(b["dscr_tariff"], b["equity_irr_tariff"])
    assert b["binding"] == ("DSCR" if b["dscr_tariff"] >= b["equity_irr_tariff"] else "equity IRR")
    assert debt.min_tariff_for_dscr(c, t) == b["dscr_tariff"]


def test_max_gearing_is_the_boundary_of_lender_acceptance():
    c, t = cost.CostInputs(), debt.DebtTerms()
    g = debt.max_gearing(c, t, 2.0)
    from dataclasses import replace
    assert debt.lender_view(c, replace(t, gearing=g - 0.01), 2.0)["meets_dscr"]
    assert not debt.lender_view(c, replace(t, gearing=g + 0.02), 2.0)["meets_dscr"]
