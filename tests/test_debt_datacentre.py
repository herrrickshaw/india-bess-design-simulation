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
