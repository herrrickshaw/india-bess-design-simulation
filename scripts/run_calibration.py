"""Calibration checks and cost-scenario sensitivity. Run from repo root."""
import sys; sys.path.insert(0, ".")
from bess_sim import calibration as cal, cost, debt, tenders
import pandas as pd

print("== Model vs public anchors, INR crore per INSTALLED MWh ==")
for d in (2.0, 4.0):
    r = cal.market_check(d)
    lo, hi = r["china_epc_plus_duty_range"]
    print(f"{d:.0f}h: model {r['model_cr_per_installed_mwh']:.2f} (delivered-MWh basis {r['model_cr_per_delivered_mwh']:.2f}) | "
          f"China EPC + Indian duty {lo:.2f}-{hi:.2f} | Indian turnkey {r['india_turnkey_range'][0]}-{r['india_turnkey_range'][1]} | CTUIL benchmark {r['ctuil_benchmark']}")
print("\nComponent split, 100 MW x 2h (INR crore):", {k: round(v, 1) for k, v in cost.capex_breakdown(cost.CostInputs()).items() if k in ("dc_block", "pcs_mv", "bos_epc", "grid_land", "total")})

base = cost.CostInputs()
print("\n== Break-even and bankable 2h tariff by cost scenario (lakh/MW/month) ==")
print(f"{'scenario':46s} {'cr/MWh':>7s} {'NPV b/e':>8s} {'+VGF':>6s} {'bankable':>9s} {'+VGF':>6s}")
for name, tgt in cal.SCENARIOS.items():
    c = base if tgt is None else cal.scaled_to_installed_capex(base, tgt)
    cv = cost.CostInputs(**{**c.__dict__, "vgf_inr_lakh_per_mwh": 46.0})
    m = cost.capex_breakdown(c)["per_nameplate_mwh_crore"]
    t = debt.DebtTerms()
    print(f"{name:46s} {m:7.2f} {cost.breakeven_tariff(c):8.2f} {cost.breakeven_tariff(cv):6.2f} "
          f"{debt.bankable_tariff(c, t)['bankable']:9.2f} {debt.bankable_tariff(cv, t)['bankable']:6.2f}")

print("\n== Installed capex (INR crore/MWh) each 2h award can just support (NPV at WACC) vs anchors ==")
aw = tenders.analyse()
for _, r in aw.iterrows():
    a = cal.tariff_implied_installed_capex(r["duration_h"], r["tariff"])
    print(f"  {r['tender_id']:26s} tariff {r['tariff']:5.2f} -> supports {a:5.2f} cr/installed MWh "
          f"(CTUIL 0.80, turnkey 1.2-1.8, model {cost.capex_breakdown(cost.CostInputs(duration_h=r['duration_h']))['per_nameplate_mwh_crore']:.2f})")
