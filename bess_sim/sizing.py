"""MW / MWh sizing for the three common grid use cases."""
from __future__ import annotations

import numpy as np


def size_for_peak_shave(net_load_mw: np.ndarray, cap_mw: float,
                        rte: float = 0.85) -> dict:
    """Smallest (MW, MWh) that holds a (days x 24) net-load below cap_mw.

    Power = worst exceedance. Energy = worst single-day discharge energy needed
    above the cap, grossed up for round-trip loss on the recharge side being
    served from below-cap headroom (headroom feasibility is checked and reported).
    """
    x = np.asarray(net_load_mw, dtype=float).reshape(-1, 24)
    exc = np.clip(x - cap_mw, 0, None)
    head = np.clip(cap_mw - x, 0, None)
    mw = float(exc.max())
    daily_discharge = exc.sum(axis=1)
    mwh = float(daily_discharge.max())
    recharge_needed = daily_discharge / rte
    feasible = bool((head.sum(axis=1) >= recharge_needed).all())
    return {"mw": mw, "mwh_poi": mwh, "duration_h": mwh / mw if mw else 0.0,
            "recharge_feasible": feasible,
            "days_exceeding": int((exc.sum(axis=1) > 0).sum())}


def size_for_solar_shift(solar_mw_ac: float, shift_fraction: float = 0.5,
                         evening_hours: float = 4.0, rte: float = 0.85) -> dict:
    """Shift a fraction of a solar plant's daily energy into an evening window.

    solar_mw_ac * 5.5 equivalent full-load hours is a rough India yield used only
    when no profile is given; pass a profile to dispatch.py for precision.
    """
    daily_mwh = solar_mw_ac * 5.5
    shifted = daily_mwh * shift_fraction
    mwh_poi = shifted * rte ** 0.5          # energy deliverable after charge loss
    mw = mwh_poi / evening_hours
    return {"mw": mw, "mwh_poi": mwh_poi, "duration_h": evening_hours,
            "charge_mwh_needed": shifted}


def size_for_re_firming(profile_mw: np.ndarray, firm_mw: float,
                        rte: float = 0.85) -> dict:
    """Storage to firm a (days x 24) RE output to firm_mw in every hour.

    Deficits (profile < firm) must be covered by discharge; surplus above firm
    is the only charging source. Reports the energy to cover the worst day and
    the share of days that cannot be firmed even with infinite energy.
    """
    x = np.asarray(profile_mw, dtype=float).reshape(-1, 24)
    deficit = np.clip(firm_mw - x, 0, None)
    surplus = np.clip(x - firm_mw, 0, None) * rte
    mw = float(deficit.max())
    mwh = float(deficit.sum(axis=1).max())
    unfirmable = (deficit.sum(axis=1) > surplus.sum(axis=1) + 1e-9)
    return {"mw": mw, "mwh_poi": mwh, "duration_h": mwh / mw if mw else 0.0,
            "unfirmable_day_share": float(unfirmable.mean())}
