"""BESS capex / opex / levelised-tariff model.

Every default carries a tag: SOURCED (with where) or ASSUMPTION (my placeholder,
replace with a vendor quote). The tender metric in India is a *capacity charge*
in INR lakh per MW per month, so the headline output is the break-even value of
that number for a given capex, not a LCOE.

Simplifications (deliberate, stated):
  * Procurer supplies charging energy (true of GUVNL-style tenders), so no
    energy purchase cost; round-trip losses only show up as sizing oversize.
  * Post-tax FCFF discounted at WACC; straight-line depreciation over life.
  * Augmentation modelled as spend in named years at a declining price.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

LAKH = 1e5
CRORE = 1e7


@dataclass(frozen=True)
class CostInputs:
    # --- technical ---
    mw: float = 100.0
    duration_h: float = 2.0
    rte_ac: float = 0.85            # SOURCED: GUVNL tender, 85% monthly AC-AC
    availability: float = 0.95      # SOURCED: GUVNL tender, 95% annual
    eol_soh: float = 0.90           # ASSUMPTION: SOH the day-1 block is sized to; augmentation (below) restores the rest
    usable_dod: float = 0.95        # ASSUMPTION
    life_years: int = 15            # SOURCED: MSEDCL 15-yr agreements
    # --- capex (INR) ---
    fx_inr_per_usd: float = 95.5    # SOURCED (derived): JMK 2.38 lakh = USD 2,493 -> 95.5
    dc_block_usd_per_kwh: float = 69.4   # SOURCED: SMM, 5 MWh container DC FOB, Sep 2026
    landed_uplift: float = 0.15     # ASSUMPTION: freight+duty+insurance on DC block
    pcs_mv_inr_per_kw: float = 3800.0    # ASSUMPTION: PCS + MV transformer + switchgear
    bos_epc_inr_per_kwh: float = 600.0   # ASSUMPTION: civil, EMS, fire, EPC margin
    grid_land_inr_lakh_per_mw: float = 15.0  # ASSUMPTION: bay, line, land
    # --- opex ---
    opex_pct_capex: float = 0.015   # ASSUMPTION: O&M + insurance, yr-1 share of capex
    opex_escalation: float = 0.03   # ASSUMPTION
    # --- augmentation ---
    augment_years: tuple = (6, 11)  # ASSUMPTION
    augment_frac_of_dc: float = 0.12  # ASSUMPTION: share of original DC block added each time
    dc_price_decline_pa: float = 0.04  # ASSUMPTION: annual fall in DC block price
    # --- finance ---
    debt_share: float = 0.70        # ASSUMPTION
    debt_rate: float = 0.095        # ASSUMPTION
    equity_return: float = 0.14     # ASSUMPTION
    tax_rate: float = 0.2517        # SOURCED: Indian corporate rate (new regime, incl. cess)
    vgf_inr_lakh_per_mwh: float = 0.0  # PIB: Rs 46 lakh/MWh cap or 30% of capex, whichever lower

    @property
    def wacc(self) -> float:
        return (self.debt_share * self.debt_rate * (1 - self.tax_rate)
                + (1 - self.debt_share) * self.equity_return)


def required_dc_mwh(c: CostInputs) -> float:
    """DC-side nameplate energy so POI discharge = mw*duration until the first augmentation.

    Sized to eol_soh (not 0.80) because augmentation spend is modelled separately;
    using both would double count.
    """
    poi_mwh = c.mw * c.duration_h
    eta_discharge = c.rte_ac ** 0.5          # symmetric split of round-trip loss
    return poi_mwh / eta_discharge / c.usable_dod / c.eol_soh


def capex_breakdown(c: CostInputs) -> dict:
    """INR crore by component. Oversize at COD sized for end-of-life SOH."""
    dc_mwh = required_dc_mwh(c)
    dc = dc_mwh * 1000 * c.dc_block_usd_per_kwh * c.fx_inr_per_usd * (1 + c.landed_uplift)
    pcs = c.mw * 1000 * c.pcs_mv_inr_per_kw
    bos = dc_mwh * 1000 * c.bos_epc_inr_per_kwh
    grid = c.mw * c.grid_land_inr_lakh_per_mw * LAKH
    out = {"dc_block": dc, "pcs_mv": pcs, "bos_epc": bos, "grid_land": grid}
    out = {k: v / CRORE for k, v in out.items()}
    out["total"] = sum(out.values())
    out["dc_mwh_nameplate"] = dc_mwh
    out["per_poi_mwh_crore"] = out["total"] / (c.mw * c.duration_h)
    return out


def vgf_crore(c: CostInputs, total_capex_cr: float) -> float:
    """VGF = min(Rs 46 lakh/MWh (PIB Apr 2025), 30% of capex). Only if enabled."""
    if c.vgf_inr_lakh_per_mwh <= 0:
        return 0.0
    cap = c.vgf_inr_lakh_per_mwh * c.mw * c.duration_h * LAKH / CRORE
    return min(cap, 0.30 * total_capex_cr)


def cashflows(c: CostInputs, tariff_lakh_per_mw_month: float):
    """Yearly post-tax free cash flow to firm (INR crore), index 0 = capex year."""
    cb = capex_breakdown(c)
    capex = cb["total"] - vgf_crore(c, cb["total"])
    dc0 = cb["dc_block"]
    flows = [-capex]
    dep = capex / c.life_years
    for y in range(1, c.life_years + 1):
        rev = tariff_lakh_per_mw_month * 12 * c.mw * LAKH / CRORE
        rev *= c.availability / 0.95 if c.availability < 0.95 else 1.0
        opex = cb["total"] * c.opex_pct_capex * (1 + c.opex_escalation) ** (y - 1)
        aug = 0.0
        if y in c.augment_years:
            aug = dc0 * c.augment_frac_of_dc * (1 - c.dc_price_decline_pa) ** y
        ebitda = rev - opex
        tax = max(0.0, (ebitda - dep) * c.tax_rate)
        flows.append(ebitda - tax - aug)
    return flows


def operating_lines(c: CostInputs, tariff_lakh_per_mw_month: float) -> dict:
    """Per-year revenue, opex and augmentation (INR crore) plus net capex and depreciation.

    Shared by the unlevered NPV (cashflows) and the lender view (debt.py) so the two
    cannot drift apart.
    """
    cb = capex_breakdown(c)
    capex = cb["total"] - vgf_crore(c, cb["total"])
    rev, opex, aug = [], [], []
    for y in range(1, c.life_years + 1):
        r = tariff_lakh_per_mw_month * 12 * c.mw * LAKH / CRORE
        r *= c.availability / 0.95 if c.availability < 0.95 else 1.0
        rev.append(r)
        opex.append(cb["total"] * c.opex_pct_capex * (1 + c.opex_escalation) ** (y - 1))
        aug.append(cb["dc_block"] * c.augment_frac_of_dc * (1 - c.dc_price_decline_pa) ** y
                   if y in c.augment_years else 0.0)
    return {"capex": capex, "dep": capex / c.life_years, "rev": rev, "opex": opex, "aug": aug}


def npv(rate: float, flows) -> float:
    return sum(f / (1 + rate) ** i for i, f in enumerate(flows))


def breakeven_tariff(c: CostInputs, rate: float | None = None) -> float:
    """Capacity charge (INR lakh/MW/month) at which post-tax NPV at WACC = 0."""
    r = c.wacc if rate is None else rate
    lo, hi = 0.0, 50.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if npv(r, cashflows(c, mid)) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def implied_capex_per_mwh(c: CostInputs, tariff: float) -> float:
    """Total installed INR crore per POI MWh that a given tariff can just support.

    Scales every capex line proportionally to find the multiplier k s.t. NPV=0.
    Returns the supportable total capex in crore/MWh.
    """
    base = capex_breakdown(c)["total"]
    lo, hi = 0.05, 5.0
    for _ in range(80):
        k = (lo + hi) / 2
        scaled = replace(
            c,
            dc_block_usd_per_kwh=c.dc_block_usd_per_kwh * k,
            pcs_mv_inr_per_kw=c.pcs_mv_inr_per_kw * k,
            bos_epc_inr_per_kwh=c.bos_epc_inr_per_kwh * k,
            grid_land_inr_lakh_per_mw=c.grid_land_inr_lakh_per_mw * k,
        )
        # opex is a % of (scaled) capex, so it scales with k automatically
        if npv(c.wacc, cashflows(scaled, tariff)) > 0:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2
    return base * k / (c.mw * c.duration_h)


def lcos_inr_per_kwh(c: CostInputs, cycles_per_day: float = 1.0) -> float:
    """Levelised cost per kWh discharged at POI for a given cycling intensity.

    Uses the break-even capacity charge spread over delivered energy; this is the
    number comparable to PIB's INR/kWh figures (2.1 at 2 cycles, 2.8 at 1.5).
    """
    t = breakeven_tariff(c)
    annual_inr = t * 12 * c.mw * LAKH
    kwh = c.mw * 1000 * c.duration_h * cycles_per_day * 365 * c.availability
    return annual_inr / kwh


def dc_price_for_tariff(c: CostInputs, tariff: float) -> float:
    """DC block price (USD/kWh FOB) at which `tariff` is exactly break-even, other inputs fixed."""
    lo, hi = 5.0, 200.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if breakeven_tariff(replace(c, dc_block_usd_per_kwh=mid)) > tariff:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2
