"""Price-arbitrage dispatch via daily LP (HiGHS), plus synthetic India-style profiles.

Synthetic profiles are NOT market data: they reproduce the shape (solar-hour
trough, evening peak) so the model runs end to end. Pass real IEX DAM prices or
a state net-load series to replace them.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import linprog


def synthetic_prices(days: int = 365, seed: int = 7) -> np.ndarray:
    """(days x 24) INR/kWh with midday trough and 18-22h peak."""
    rng = np.random.default_rng(seed)
    h = np.arange(24)
    base = (4.5
            - 2.2 * np.exp(-((h - 12.5) ** 2) / 8.0)
            + 4.0 * np.exp(-((h - 20.0) ** 2) / 5.0)
            + 1.0 * np.exp(-((h - 7.5) ** 2) / 4.0))
    season = 1.0 + 0.15 * np.sin(2 * np.pi * (np.arange(days) - 120) / 365)
    noise = rng.normal(0, 0.35, size=(days, 24))
    return np.clip(base[None, :] * season[:, None] + noise, 0.5, 10.0)


def synthetic_net_load(days: int = 365, peak_mw: float = 1000.0, seed: int = 11) -> np.ndarray:
    """(days x 24) duck-curve net load for a notional state, MW."""
    rng = np.random.default_rng(seed)
    h = np.arange(24)
    demand = 0.62 + 0.18 * np.exp(-((h - 11) ** 2) / 20) + 0.38 * np.exp(-((h - 20.5) ** 2) / 6)
    solar = 0.30 * np.exp(-((h - 12.5) ** 2) / 6)
    shape = demand - solar
    shape = shape / shape.max()
    return peak_mw * np.clip(shape[None, :] + rng.normal(0, 0.02, size=(days, 24)), 0.2, 1.05)


def _solve_day(price, mw, mwh, eta_c, eta_d, wear_inr_per_mwh):
    """Maximise sum(price*(d-c)) - wear*d for one 24h cycle. Prices INR/kWh -> *1000 per MWh."""
    n = 24
    p = np.asarray(price) * 1000.0                       # INR/MWh
    # vars: c[0..n-1], d[0..n-1], s[0..n] (soc, MWh)
    nv = 3 * n + 1
    cost = np.zeros(nv)
    cost[:n] = p                                          # charging costs money
    cost[n:2 * n] = -p + wear_inr_per_mwh                 # discharging earns, minus wear
    A_eq = np.zeros((n + 1, nv)); b_eq = np.zeros(n + 1)
    for t in range(n):
        A_eq[t, 2 * n + t + 1] = 1
        A_eq[t, 2 * n + t] = -1
        A_eq[t, t] = -eta_c
        A_eq[t, n + t] = 1.0 / eta_d
    A_eq[n, 2 * n] = 1; b_eq[n] = 0.0                     # start empty
    bounds = ([(0, mw)] * n + [(0, mw)] * n + [(0, mwh)] * (n + 1))
    r = linprog(cost, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if not r.success:
        raise RuntimeError(r.message)
    c = r.x[:n]; d = r.x[n:2 * n]
    return c, d, -r.fun


def simulate_arbitrage(prices: np.ndarray, mw: float, duration_h: float,
                       rte: float = 0.85, wear_inr_per_mwh: float = 0.0,
                       availability: float = 0.95) -> dict:
    """Run every day; returns annualised merchant revenue per MW (INR lakh)."""
    mwh = mw * duration_h
    eta = rte ** 0.5
    rev = 0.0; thr = 0.0; cycles = 0.0
    for day in prices:
        c, d, v = _solve_day(day, mw, mwh, eta, eta, wear_inr_per_mwh)
        rev += v; thr += d.sum(); cycles += d.sum() / mwh
    ndays = len(prices)
    scale = 365.0 / ndays * availability
    annual_inr = rev * scale
    return {
        "annual_revenue_inr_lakh_per_mw": annual_inr / mw / 1e5,
        "equiv_monthly_lakh_per_mw": annual_inr / mw / 1e5 / 12,
        "cycles_per_day": cycles / ndays,
        "avg_spread_inr_per_kwh_captured": (rev / thr / 1000) if thr else 0.0,
    }
