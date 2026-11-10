"""Print the tender-vs-model table and a sensitivity to cell price. Run from repo root."""
import sys; sys.path.insert(0, ".")
import pandas as pd
from bess_sim import cost, tenders
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)

print("== Bottom-up capex, 100 MW x 2h (INR crore) ==")
for k, v in cost.capex_breakdown(cost.CostInputs()).items(): print(f"  {k:22s} {v:9.3f}")
print("  CTUIL benchmark (crore/MWh): 0.80")

print("\n== Awarded tenders vs model (no VGF) ==")
print(tenders.analyse().to_string(index=False))
print("\n== Same, with VGF Rs 46 lakh/MWh ==")
print(tenders.analyse(vgf=True)[["tender_id","tariff","model_breakeven","gap_vs_breakeven_pct"]].to_string(index=False))

print("\n== Break-even 2h tariff vs DC block price (USD/kWh) ==")
for p in (45, 55, 60, 69.4, 80):
    c = cost.CostInputs(dc_block_usd_per_kwh=p)
    print(f"  {p:5.1f} -> {cost.breakeven_tariff(c):5.2f} lakh/MW/mo, capex {cost.capex_breakdown(c)['per_poi_mwh_crore']:.3f} cr/MWh")
print("\nLCOS at 1.5 and 2 cycles/day (INR/kWh):",
      round(cost.lcos_inr_per_kwh(cost.CostInputs(), 1.5), 2), round(cost.lcos_inr_per_kwh(cost.CostInputs(), 2.0), 2),
      "| PIB: 2.8 and 2.1")

print("\n== DC block price (USD/kWh) each awarded tariff implies, all else as modelled ==")
for _, r in tenders.analyse().iterrows():
    c = cost.CostInputs(duration_h=r["duration_h"])
    print(f"  {r['tender_id']:26s} {r['tariff']:5.2f} lakh -> {cost.dc_price_for_tariff(c, r['tariff']):5.1f} USD/kWh"
          f"  (with VGF: {cost.dc_price_for_tariff(cost.CostInputs(duration_h=r['duration_h'], vgf_inr_lakh_per_mwh=46.0), r['tariff']):5.1f})")

# ---- lender view (IREDA-style terms, see bess_sim/debt.py) ----
from bess_sim import debt
cols = ["tender_id", "tariff", "min_dscr", "avg_dscr", "equity_irr_pct", "bankable_at_70pct", "max_gearing_pct", "dsra_cr_per_100mw"]
print("\n== Lender view at each awarded tariff, no VGF (70% gearing, 12y tenor, 1y moratorium) ==")
print(tenders.analyse()[cols].to_string(index=False))
print("\n== Same, with VGF Rs 46 lakh/MWh ==")
print(tenders.analyse(vgf=True)[cols].to_string(index=False))
print("\n== Tariff a lender AND sponsor would need (lakh/MW/month) ==")
for dur in (2.0, 4.0):
    for v in (False, True):
        b = debt.bankable_tariff(cost.CostInputs(duration_h=dur, vgf_inr_lakh_per_mwh=46.0 if v else 0.0), debt.DebtTerms())
        print(f"  {dur:.0f}h {'VGF   ' if v else 'no VGF'}: DSCR-only {b['dscr_tariff']:.2f} | 14% equity IRR {b['equity_irr_tariff']:.2f} | binding: {b['binding']}")

print("\n== DC block price (USD/kWh) at which each award passes DSCR at 70% gearing ==")
print("   (modelled Sep-2026 price: 69.4; China LFP cell alone: 54.4)")
for _, r in tenders.analyse().iterrows():
    d = r["duration_h"]
    a = debt.dc_price_for_bankability(cost.CostInputs(duration_h=d), debt.DebtTerms(), r["tariff"])
    b = debt.dc_price_for_bankability(cost.CostInputs(duration_h=d, vgf_inr_lakh_per_mwh=46.0), debt.DebtTerms(), r["tariff"])
    print(f"  {r['tender_id']:26s} no VGF {a:5.1f} | VGF {b:5.1f}")
