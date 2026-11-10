"""Data-centre integration: what storage can do for a flat 24x7 load, and what it costs.

Three questions, each answerable without market data:
  1. How much storage does a given renewable mix need to hit a carbon-free-energy (CFE)
     target on an hourly basis?            -> cfe_score / bess_mwh_for_cfe
  2. What spread must a behind-the-meter battery capture to pay for itself?
                                           -> required_spread
  3. How much energy must a UPS-class battery hold for N minutes of ride-through?
                                           -> ups_energy_mwh

RE profiles here are SYNTHETIC shapes (solar bell, night-biased wind), not site data. Swap in
hourly generation from PVGIS / NIWE / the developer for a real project. Tariff-side inputs
(ToD spread, demand charge) are state-specific and are passed in, never defaulted silently.
"""
from __future__ import annotations

import numpy as np

from .cost import CostInputs, breakeven_tariff, capex_breakdown

HOURS_PER_YEAR = 8760


def dc_load(it_mw: float, pue: float = 1.4, days: int = 365, seed: int = 3) -> np.ndarray:
    """(days*24,) facility load in MW: flat IT load x PUE with a mild afternoon cooling bump.

    PUE default 1.4 sits between the <1.35 MeitY has required in AI-cloud tenders since 2024
    and the <1.5 SBI cites for sector leaders (SBI Data Centres report, Apr 2026). The bump moves total load +-4% only: data-centre load is nearly flat, which is
    the key difference from the duck-curve loads in dispatch.py.
    """
    rng = np.random.default_rng(seed)
    h = np.tile(np.arange(24), days)
    bump = 1.0 + 0.04 * np.sin(2 * np.pi * (h - 9) / 24)
    noise = 1.0 + rng.normal(0, 0.005, size=h.size)
    return it_mw * pue * bump * noise


def synthetic_re(solar_mw: float, wind_mw: float, days: int = 365, seed: int = 5) -> np.ndarray:
    """(days*24,) hourly RE output in MW. Solar CUF ~25%, wind CUF ~30% with monsoon peak."""
    rng = np.random.default_rng(seed)
    h = np.tile(np.arange(24), days)
    d = np.repeat(np.arange(days), 24)
    clear = np.clip(rng.normal(0.9, 0.12, size=days), 0.2, 1.0)[d]
    bell = np.exp(-((h - 12.5) ** 2) / (2 * 2.6 ** 2))
    solar = solar_mw * bell * clear          # ~24% CUF (AC)
    season = 1.0 + 0.55 * np.sin(2 * np.pi * (d - 140) / 365)          # peaks around June-July
    night = 1.0 + 0.25 * np.cos(2 * np.pi * (h - 2) / 24)
    persist = np.repeat(np.clip(rng.normal(1.0, 0.45, size=days), 0.05, 2.0), 24)
    wind = np.clip(wind_mw * 0.30 * season * night * persist, 0, wind_mw)
    return solar + wind


def cfe_score(load_mw: np.ndarray, re_mw: np.ndarray, bess_mw: float = 0.0,
              bess_mwh: float = 0.0, rte: float = 0.85) -> dict:
    """Hourly-matched CFE with a greedy battery (charge from surplus, discharge into deficit).

    CFE = sum(min(supply, load)) / sum(load), where supply = RE + battery discharge.
    State of charge carries across days. No grid charging, no export credit.
    """
    eta = rte ** 0.5
    soc = 0.0
    matched = 0.0
    curtailed = 0.0
    throughput = 0.0
    for ld, re in zip(load_mw, re_mw):
        if re >= ld:
            matched += ld
            surplus = re - ld
            if bess_mwh > 0:
                chg = min(surplus, bess_mw, (bess_mwh - soc) / eta)
                soc += chg * eta
                surplus -= chg
            curtailed += surplus
        else:
            matched += re
            deficit = ld - re
            if bess_mwh > 0 and soc > 0:
                dis = min(deficit, bess_mw, soc * eta)
                soc -= dis / eta
                matched += dis
                throughput += dis
    total = float(load_mw.sum())
    return {"cfe": matched / total, "curtailed_share_of_re": curtailed / float(re_mw.sum()),
            "cycles_per_year": (throughput / (bess_mwh * eta) if bess_mwh else 0.0)
            / (len(load_mw) / HOURS_PER_YEAR)}


def bess_mwh_for_cfe(load_mw: np.ndarray, re_mw: np.ndarray, target: float,
                     duration_h: float = 4.0, rte: float = 0.85, max_mwh: float = 20000.0):
    """Smallest battery energy (MWh) at fixed duration reaching `target` CFE, or None."""
    if cfe_score(load_mw, re_mw)["cfe"] >= target:
        return 0.0
    if cfe_score(load_mw, re_mw, max_mwh / duration_h, max_mwh, rte)["cfe"] < target:
        return None
    lo, hi = 0.0, max_mwh
    for _ in range(40):
        mid = (lo + hi) / 2
        if cfe_score(load_mw, re_mw, mid / duration_h, mid, rte)["cfe"] >= target:
            hi = mid
        else:
            lo = mid
    return hi


def firming_cost(load_mw: np.ndarray, bess_mwh: float, duration_h: float = 4.0,
                 vgf: bool = False) -> dict:
    """Cost of the battery spread over the data centre's annual energy (excludes RE cost)."""
    mw = bess_mwh / duration_h
    c = CostInputs(mw=max(mw, 1e-6), duration_h=duration_h,
                   vgf_inr_lakh_per_mwh=46.0 if vgf else 0.0)
    tariff = breakeven_tariff(c)
    annual_cr = tariff * 12 * mw * 1e5 / 1e7
    annual_mwh = float(load_mw.sum()) * HOURS_PER_YEAR / len(load_mw)
    return {"bess_mw": mw, "breakeven_lakh_per_mw_month": tariff,
            "annual_cost_cr": annual_cr,
            "capex_cr": capex_breakdown(c)["total"],
            "inr_per_kwh_of_dc_load": annual_cr * 1e7 / (annual_mwh * 1000)}


def required_spread(duration_h: float = 2.0, cycles_per_day: float = 1.0,
                    vgf: bool = False) -> float:
    """INR/kWh spread a behind-the-meter battery must capture on every discharged kWh.

    Compare with the state's ToD peak-vs-off-peak difference: if the ToD spread is smaller,
    arbitrage alone cannot pay and the case rests on other value (resilience, DG avoidance,
    firming a PPA, demand charge).
    """
    c = CostInputs(duration_h=duration_h, vgf_inr_lakh_per_mwh=46.0 if vgf else 0.0)
    annual_inr = breakeven_tariff(c) * 12 * c.mw * 1e5
    kwh = c.mw * 1000 * duration_h * cycles_per_day * 365 * c.availability
    return annual_inr / kwh


def ups_energy_mwh(load_mw: float, minutes: float = 15.0, usable_dod: float = 0.9,
                   inverter_eff: float = 0.96) -> float:
    """Battery energy for `minutes` of ride-through at full facility load."""
    return load_mw * minutes / 60.0 / usable_dod / inverter_eff
