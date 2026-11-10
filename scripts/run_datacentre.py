"""Data-centre integration experiments on SYNTHETIC RE profiles. Run from repo root."""
import sys; sys.path.insert(0, ".")
from bess_sim import datacentre as dc

L = dc.dc_load(100)                      # 100 MW IT x PUE 1.4
print(f"Facility load {L.mean():.0f} MW, {L.sum()/1000:,.0f} GWh/yr; load factor = {L.mean()/L.max():.2f} (flat: weak demand-charge case)")
print("\n== Hourly CFE vs RE oversizing and 4h battery size (synthetic profiles) ==")
for sol, wind in ((250, 150), (400, 250), (500, 300), (600, 400)):
    re = dc.synthetic_re(sol, wind)
    base = dc.cfe_score(L, re)
    print(f"\nsolar {sol} + wind {wind} MW (RE energy = {re.sum()/L.sum():.2f}x load): CFE with no battery {base['cfe']:.1%}")
    for mwh in (450, 1000, 2000):
        r = dc.cfe_score(L, re, mwh / 4, mwh)
        print(f"   {mwh:5d} MWh: CFE {r['cfe']:.1%}  curtailed {r['curtailed_share_of_re']:.1%}  {r['cycles_per_year']:.0f} cycles/yr")
    for tg in (0.9, 0.95):
        m = dc.bess_mwh_for_cfe(L, re, tg)
        if m is None:
            print(f"   {tg:.0%} CFE: unreachable at this RE size (energy-limited, not storage-limited)")
        elif m == 0:
            print(f"   {tg:.0%} CFE: met without storage")
        else:
            f = dc.firming_cost(L, m)
            print(f"   {tg:.0%} CFE: {m:,.0f} MWh / {f['bess_mw']:.0f} MW, capex Rs {f['capex_cr']:,.0f} cr, "
                  f"adds Rs {f['inr_per_kwh_of_dc_load']:.2f}/kWh to the DC's energy cost (VGF: Rs {dc.firming_cost(L, m, vgf=True)['inr_per_kwh_of_dc_load']:.2f})")

print("\n== Spread a behind-the-meter battery must capture per discharged kWh ==")
for cyc in (1.0, 1.5, 2.0):
    print(f"  2h, {cyc} cycles/day: Rs {dc.required_spread(2, cyc):.2f}/kWh (with VGF Rs {dc.required_spread(2, cyc, True):.2f})")
print(f"\nUPS-class ride-through, 15 min at {L.mean():.0f} MW: {dc.ups_energy_mwh(L.mean()):.0f} MWh "
      f"(vs ~{L.mean()*2:.0f} MWh for a 2h grid battery of the same MW)")
