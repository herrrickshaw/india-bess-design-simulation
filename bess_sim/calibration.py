"""Cross-checks of the capex model against published market prices.

Nothing here is a vendor quote. Anchors are public price indices and trade-press figures,
recorded with sources in data/calibration_anchors.csv. Compare on ONE basis: per installed
(nameplate DC) MWh, which is how market prices and the CTUIL benchmark are quoted. The model
also reports per delivered (POI) MWh, which is higher by the sizing oversize; mixing the two
bases overstates how cheap tender-implied costs look.
"""
from __future__ import annotations

from dataclasses import replace

from .cost import CostInputs, capex_breakdown, implied_capex_per_mwh

CNY_PER_USD = 599.3 / 84.0          # CNESA's own implied rate (the $84 is rounded)

# CNY per Wh of nameplate energy, full EPC, China tenders (TrendForce via EnergyTrend)
CHINA_EPC_CNY_WH = {2.0: (1.00, 1.05), 4.0: (0.88, 0.99)}      # (Oct 2026, Jul 2026)
# Indian turnkey estimates, INR crore per MWh (vendor/blog ranges, indicative)
INDIA_TURNKEY_CR_PER_MWH = (1.2, 1.8)
CTUIL_BENCHMARK_CR_PER_MWH = 0.80   # CTUIL, Sep 2026 (basis not stated; read as per installed MWh)


def china_epc_in_inr_cr_per_mwh(duration_h: float, c: CostInputs | None = None,
                                duty_on_system: bool = True) -> tuple:
    """China EPC range converted to INR crore/MWh nameplate, plus Indian duty on the
    imported system share (about 58% of EPC, from CNESA/TrendForce system vs EPC prices)."""
    c = c or CostInputs()
    lo, hi = CHINA_EPC_CNY_WH[min(CHINA_EPC_CNY_WH, key=lambda d: abs(d - duration_h))]
    lo, hi = sorted((lo, hi))
    def conv(cny_wh):
        inr_per_kwh = cny_wh * 1000 / CNY_PER_USD * c.fx_inr_per_usd
        if duty_on_system:
            inr_per_kwh *= 1 + 0.58 * c.landed_uplift
        return inr_per_kwh * 1000 / 1e7      # INR/kWh -> INR/MWh -> crore/MWh
    return conv(lo), conv(hi)


def market_check(duration_h: float = 2.0, c: CostInputs | None = None) -> dict:
    """Model capex against every public anchor, all per installed MWh."""
    c = replace(c or CostInputs(), duration_h=duration_h)
    cb = capex_breakdown(c)
    lo, hi = china_epc_in_inr_cr_per_mwh(duration_h, c)
    m = cb["per_nameplate_mwh_crore"]
    return {"duration_h": duration_h, "model_cr_per_installed_mwh": m,
            "model_cr_per_delivered_mwh": cb["per_poi_mwh_crore"],
            "china_epc_plus_duty_range": (lo, hi),
            "india_turnkey_range": INDIA_TURNKEY_CR_PER_MWH,
            "ctuil_benchmark": CTUIL_BENCHMARK_CR_PER_MWH,
            "within_china_range": lo * 0.95 <= m <= hi * 1.05,
            "within_india_range": INDIA_TURNKEY_CR_PER_MWH[0] <= m <= INDIA_TURNKEY_CR_PER_MWH[1]}


def tariff_implied_installed_capex(duration_h: float, tariff: float, c: CostInputs | None = None) -> float:
    """Capex per INSTALLED MWh that a tariff can just support (same basis as market quotes)."""
    c = replace(c or CostInputs(), duration_h=duration_h)
    per_delivered = implied_capex_per_mwh(c, tariff)
    return per_delivered * (c.mw * c.duration_h) / capex_breakdown(c)["dc_mwh_nameplate"]


def scaled_to_installed_capex(c: CostInputs, target_cr_per_installed_mwh: float) -> CostInputs:
    """Scale every capex line by one factor so total capex per installed MWh hits the target."""
    k = target_cr_per_installed_mwh / capex_breakdown(c)["per_nameplate_mwh_crore"]
    return replace(c, dc_block_usd_per_kwh=c.dc_block_usd_per_kwh * k,
                   pcs_mv_inr_per_kw=c.pcs_mv_inr_per_kw * k,
                   bos_epc_inr_per_kwh=c.bos_epc_inr_per_kwh * k,
                   grid_land_inr_lakh_per_mw=c.grid_land_inr_lakh_per_mw * k)


# Named cost cases per installed MWh (INR crore), each tied to an anchor
SCENARIOS = {
    "CTUIL benchmark": CTUIL_BENCHMARK_CR_PER_MWH,
    "China EPC low end (2h, 0.74 CNY/Wh + duty)": 0.74 * 1000 / CNY_PER_USD * 95.5 * (1 + 0.58 * 0.15) * 1000 / 1e7,
    "Calibrated (model default)": None,
    "Indian turnkey high end": INDIA_TURNKEY_CR_PER_MWH[1],
}


def installed_capex_for_bankability(duration_h: float, tariff: float, c: CostInputs | None = None,
                                    terms=None, vgf: bool = False) -> float:
    """Highest total capex per INSTALLED MWh (INR crore) at which `tariff` passes the lender's
    DSCR tests at the debt terms' gearing, scaling all capex lines together. 0.0 if none."""
    from .debt import DebtTerms, lender_view
    terms = terms or DebtTerms()
    base = replace(c or CostInputs(), duration_h=duration_h,
                   vgf_inr_lakh_per_mwh=46.0 if vgf else 0.0)
    lo, hi = 0.05, 4.0
    if not lender_view(scaled_to_installed_capex(base, lo), terms, tariff)["meets_dscr"]:
        return 0.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if lender_view(scaled_to_installed_capex(base, mid), terms, tariff)["meets_dscr"]:
            lo = mid
        else:
            hi = mid
    return lo


# Quote items the loader understands: item -> (CostInputs field, expected unit)
QUOTE_ITEMS = {
    "dc_block": ("dc_block_usd_per_kwh", "USD/kWh"),            # DC block, FOB, per nameplate kWh
    "pcs_mv": ("pcs_mv_inr_per_kw", "INR/kW"),                  # PCS + MV transformer + switchgear, landed
    "bos_epc": ("bos_epc_inr_per_kwh", "INR/kWh"),              # civil, EMS, install, EPC margin, per nameplate kWh
    "grid_land": ("grid_land_inr_lakh_per_mw", "INR lakh/MW"),  # bay, line, land
    "landed_uplift": ("landed_uplift", "fraction"),             # duty + freight + insurance on DC block
    "opex_pct_capex": ("opex_pct_capex", "fraction"),           # O&M + insurance, year 1
    "debt_rate": ("debt_rate", "fraction"),                     # lender term sheet
    "debt_share": ("debt_share", "fraction"),                   # lender term sheet
    "fx_inr_per_usd": ("fx_inr_per_usd", "INR/USD"),
}


def cost_inputs_from_quotes(path, base: CostInputs | None = None, min_quotes: int = 1):
    """Build CostInputs from a CSV of vendor quotes and report what moved.

    CSV columns: item, value, unit, vendor, date, notes. Several quotes for one item are
    averaged (so three RFQ responses become one input). Units must match QUOTE_ITEMS exactly;
    a mismatch raises instead of silently mis-scaling. Rows with an empty value are skipped,
    so the shipped template can be loaded unchanged.
    """
    import pandas as pd
    base = base or CostInputs()
    df = pd.read_csv(path)
    df = df[df["value"].notna() & (df["value"].astype(str).str.strip() != "")].copy()
    if df.empty:
        return base, []
    changes, overrides = [], {}
    for item, g in df.groupby("item"):
        if item not in QUOTE_ITEMS:
            raise ValueError(f"unknown quote item {item!r}; known: {sorted(QUOTE_ITEMS)}")
        field, unit = QUOTE_ITEMS[item]
        bad = g[g["unit"].str.strip() != unit]
        if len(bad):
            raise ValueError(f"{item}: expected unit {unit!r}, got {sorted(set(bad['unit']))}")
        if len(g) < min_quotes:
            raise ValueError(f"{item}: need at least {min_quotes} quote(s)")
        val = float(g["value"].astype(float).mean())
        overrides[field] = val
        changes.append({"item": item, "field": field, "old": getattr(base, field), "new": val,
                        "n_quotes": len(g), "spread": float(g["value"].astype(float).max() - g["value"].astype(float).min())})
    return replace(base, **overrides), changes
