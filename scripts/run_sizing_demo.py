"""End-to-end demo: size for a notional 1 GW state, dispatch on synthetic prices, check grid items."""
import sys; sys.path.insert(0, ".")
from datetime import date
from bess_sim import cost, sizing, dispatch, grid

nl = dispatch.synthetic_net_load(days=120, peak_mw=1000)
cap = 900.0
s = sizing.size_for_peak_shave(nl, cap)
print(f"Peak-shave to {cap:.0f} MW: {s['mw']:.0f} MW / {s['mwh_poi']:.0f} MWh ({s['duration_h']:.1f} h), "
      f"recharge feasible={s['recharge_feasible']}, days exceeding={s['days_exceeding']}")
print("Solar shift 300 MWac, 50% into 4h evening:", {k: round(v, 1) for k, v in sizing.size_for_solar_shift(300).items()})

dur = max(2.0, round(s["duration_h"] * 2) / 2)
mw = round(s["mw"], -1) or 100
prices = dispatch.synthetic_prices(days=120)
arb = dispatch.simulate_arbitrage(prices, mw, dur)
inp = cost.CostInputs(mw=mw, duration_h=dur)
be = cost.breakeven_tariff(inp)
print(f"\nStorage {mw:.0f} MW x {dur:.1f} h")
print(f"  merchant arbitrage (SYNTHETIC prices): {arb['equiv_monthly_lakh_per_mw']:.2f} lakh/MW/month, {arb['cycles_per_day']:.2f} cycles/day")
print(f"  break-even capacity charge: {be:.2f} lakh/MW/month  -> merchant covers {arb['equiv_monthly_lakh_per_mw']/be:.0%}")
print("  POI design:", {k: round(v, 1) for k, v in grid.poi_design(mw, dur).items()})
print("  ISTS waiver if standalone COD 2027-03:", grid.ists_waiver_pct(date(2027, 3, 1), False), "% | co-located:", grid.ists_waiver_pct(date(2027, 3, 1), True), "%")
