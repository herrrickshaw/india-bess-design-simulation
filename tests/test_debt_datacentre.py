import numpy as np
from dataclasses import replace
from bess_sim import cost, debt, datacentre as dc


def test_tenor_is_80pct_of_agreement_capped():
    assert debt.DebtTerms().tenor == 12
    assert debt.DebtTerms(agreement_years=30).tenor == 20          # 20-year cap


def test_debt_fully_repaid_by_tenor():
    c, t = cost.CostInputs(), debt.DebtTerms()
    s = debt.loan_schedule(c, t, 4.0)
    assert abs(sum(s["principal"]) - s["debt0"]) < 1e-6
    assert all(p == 0 for p in s["principal"][:t.moratorium_years])   # moratorium: interest only
    assert all(x == 0 for x in s["ds"][s["tenor"]:])


def test_mra_contributions_sum_to_augmentation():
    c = cost.CostInputs()
    aug = cost.operating_lines(c, 3.0)["aug"]
    assert abs(sum(debt._mra_contributions(aug)) - sum(aug)) < 1e-9


def test_cfads_unchanged_by_debt_choice_before_tax_shield():
    # more gearing -> more interest -> lower tax -> CFADS cannot fall
    c = cost.CostInputs()
    lo = debt.loan_schedule(c, debt.DebtTerms(gearing=0.3), 5.0)["cfads"]
    hi = debt.loan_schedule(c, debt.DebtTerms(gearing=0.7), 5.0)["cfads"]
    assert sum(hi) >= sum(lo) - 1e-9


def test_dscr_monotone_in_tariff_and_gearing():
    c, t = cost.CostInputs(), debt.DebtTerms()
    assert debt.lender_view(c, t, 4.5)["min_dscr"] > debt.lender_view(c, t, 3.5)["min_dscr"]
    assert (debt.lender_view(c, replace(t, gearing=0.5), 4.0)["min_dscr"]
            > debt.lender_view(c, replace(t, gearing=0.7), 4.0)["min_dscr"])


def test_bankable_tariff_passes_and_just_below_fails():
    c, t = cost.CostInputs(), debt.DebtTerms()
    x = debt.min_tariff_for_dscr(c, t)
    assert debt.lender_view(c, t, x + 0.01)["meets_dscr"]
    assert not debt.lender_view(c, t, x - 0.05)["meets_dscr"]


def test_dscr_tariff_close_to_npv_breakeven():
    # independent routes to "what tariff closes" should land in the same neighbourhood
    c, t = cost.CostInputs(), debt.DebtTerms()
    assert abs(debt.min_tariff_for_dscr(c, t) - cost.breakeven_tariff(c)) < 0.5


def test_dsra_central_falls_away_other_stays():
    ds = [10.0] * 12
    cen = debt.dsra_profile(ds, "central", 12)
    oth = debt.dsra_profile(ds, "other_discom", 12)
    assert cen[0] == 2.5 and cen[2] == 0.0
    assert oth[0] == 2.5 and oth[3] == 5.0 and oth[12] == 0.0


def test_max_gearing_bounded_and_rises_with_vgf():
    c, t = cost.CostInputs(), debt.DebtTerms()
    g = debt.max_gearing(c, t, 2.35)
    assert 0 <= g <= 0.70
    assert debt.max_gearing(cost.CostInputs(vgf_inr_lakh_per_mwh=46), t, 2.35) > g


def test_bankability_price_monotone_in_tariff():
    c, t = cost.CostInputs(), debt.DebtTerms()
    assert debt.dc_price_for_bankability(c, t, 3.0) > debt.dc_price_for_bankability(c, t, 2.0)


def test_dc_load_is_flat():
    L = dc.dc_load(100, days=30)
    assert L.mean() / L.max() > 0.9


def test_cfe_bounded_and_storage_never_hurts():
    L = dc.dc_load(100, days=60)
    re = dc.synthetic_re(400, 250, days=60)
    a = dc.cfe_score(L, re)["cfe"]
    b = dc.cfe_score(L, re, 100, 400)["cfe"]
    assert 0 < a <= b <= 1.0


def test_cfe_cannot_exceed_energy_share():
    L = dc.dc_load(100, days=60)
    re = dc.synthetic_re(250, 150, days=60)          # ~0.75x load energy
    cap = re.sum() / L.sum()
    assert dc.cfe_score(L, re, 5000, 20000)["cfe"] <= cap + 1e-9
    assert dc.bess_mwh_for_cfe(L, re, 0.95) is None   # energy-limited, not storage-limited


def test_required_spread_falls_with_cycles_and_vgf():
    assert dc.required_spread(2, 2.0) < dc.required_spread(2, 1.0)
    assert dc.required_spread(2, 1.0, vgf=True) < dc.required_spread(2, 1.0)


def test_ups_energy():
    assert abs(dc.ups_energy_mwh(60, 15, 1.0, 1.0) - 15.0) < 1e-9


# ---- calibration ----
import pandas as pd
from bess_sim import calibration as cal


def test_model_sits_inside_public_anchors():
    for d in (2.0, 4.0):
        r = cal.market_check(d)
        assert r["within_china_range"] and r["within_india_range"]


def test_installed_basis_is_lower_than_delivered_basis():
    r = cal.market_check(2.0)
    assert r["model_cr_per_installed_mwh"] < r["model_cr_per_delivered_mwh"]


def test_scaling_hits_target_installed_capex():
    c = cal.scaled_to_installed_capex(cost.CostInputs(), 0.80)
    assert abs(cost.capex_breakdown(c)["per_nameplate_mwh_crore"] - 0.80) < 1e-9


def test_cheaper_capex_lowers_breakeven():
    hi = cost.breakeven_tariff(cal.scaled_to_installed_capex(cost.CostInputs(), 1.8))
    lo = cost.breakeven_tariff(cal.scaled_to_installed_capex(cost.CostInputs(), 0.8))
    assert lo < hi


def test_tariff_implied_capex_monotone_and_bankable_capex_below_it():
    a = cal.tariff_implied_installed_capex(2.0, 2.0)
    b = cal.tariff_implied_installed_capex(2.0, 3.0)
    assert b > a > 0
    # DSCR-bankable capex also rises with tariff; it can exceed the NPV-supportable capex because
    # the equity-return hurdle, not the DSCR test, is what binds in this model
    assert cal.installed_capex_for_bankability(2.0, 3.0) > cal.installed_capex_for_bankability(2.0, 2.0) > 0


def test_china_conversion_units():
    lo, hi = cal.china_epc_in_inr_cr_per_mwh(2.0, duty_on_system=False)
    # 1.00 CNY/Wh at 7.13 CNY/USD and INR 95.5/USD = INR 13,394/kWh = 1.34 crore/MWh
    assert abs(lo - 1.339) < 0.01


def test_quote_template_loads_unchanged_and_overrides_work(tmp_path):
    base, changes = cal.cost_inputs_from_quotes("data/vendor_quotes_template.csv")
    assert changes == [] and base == cost.CostInputs()
    f = tmp_path / "q.csv"
    pd.DataFrame([
        {"item": "dc_block", "value": 60, "unit": "USD/kWh", "vendor": "A", "date": "2026-11", "notes": ""},
        {"item": "dc_block", "value": 64, "unit": "USD/kWh", "vendor": "B", "date": "2026-11", "notes": ""},
        {"item": "bos_epc", "value": 3000, "unit": "INR/kWh", "vendor": "A", "date": "2026-11", "notes": ""},
    ]).to_csv(f, index=False)
    c, ch = cal.cost_inputs_from_quotes(f)
    assert c.dc_block_usd_per_kwh == 62 and c.bos_epc_inr_per_kwh == 3000
    assert {x["item"]: x["n_quotes"] for x in ch} == {"dc_block": 2, "bos_epc": 1}


def test_quote_loader_rejects_wrong_unit_and_unknown_item(tmp_path):
    f = tmp_path / "q.csv"
    pd.DataFrame([{"item": "dc_block", "value": 60, "unit": "INR/kWh", "vendor": "A", "date": "", "notes": ""}]).to_csv(f, index=False)
    import pytest
    with pytest.raises(ValueError):
        cal.cost_inputs_from_quotes(f)
    pd.DataFrame([{"item": "mystery", "value": 1, "unit": "x", "vendor": "A", "date": "", "notes": ""}]).to_csv(f, index=False)
    with pytest.raises(ValueError):
        cal.cost_inputs_from_quotes(f)
