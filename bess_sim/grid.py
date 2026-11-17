"""Grid-integration checks: connection sizing, land, ISTS waiver, tender compliance."""
from __future__ import annotations

from datetime import date

ACRES_PER_100MWH = 1.2        # SOURCED: CTUIL land requirement for GNA (JMK Oct 2026)
CTUIL_BENCH_CR_PER_MWH = 0.80  # SOURCED: CTUIL revised standalone BESS benchmark (JMK Oct 2026)


def land_acres(mwh: float) -> float:
    return mwh / 100.0 * ACRES_PER_100MWH


def ists_waiver_pct(cod: date, colocated: bool) -> int:
    """ISTS charge waiver percent.

    PIB (15 Dec 2025): co-located BESS commissioned by June 2028 -> waived.
    Non-co-located: waived if commissioned before June 2025; thereafter reduced
    annually in graded steps of 25%. The 25%-per-year schedule below is MY READING
    of that sentence; confirm against the MoP order before bidding.
    """
    if colocated:
        return 100 if cod <= date(2028, 6, 30) else 0
    if cod < date(2025, 6, 1):
        return 100
    steps = (cod.year - 2025) - (1 if cod.month < 6 else 0) + 1   # 1 for Jun-2025..May-2026
    return max(0, 100 - 25 * steps)


def poi_design(mw_contracted: float, duration_h: float, aux_frac: float = 0.02,
               pf_min: float = 0.95, tx_margin: float = 1.10) -> dict:
    """Connection-side sizing for a standalone plant.

    PCS must cover contracted MW plus auxiliary load and reactive support.
    """
    pcs_mw = mw_contracted * (1 + aux_frac)
    pcs_mva = pcs_mw / pf_min
    return {
        "pcs_mw": pcs_mw,
        "pcs_mva": pcs_mva,
        "transformer_mva": pcs_mva * tx_margin,
        "land_acres": land_acres(mw_contracted * duration_h),
        "connectivity_mw": mw_contracted,
    }


def check_tender_compliance(rte_ac_monthly: float, availability_annual: float,
                            rte_min: float = 0.85, avail_min: float = 0.95) -> list:
    """Return list of breached obligations (GUVNL-style thresholds)."""
    out = []
    if rte_ac_monthly < rte_min:
        out.append(f"RTE {rte_ac_monthly:.1%} < {rte_min:.0%}")
    if availability_annual < avail_min:
        out.append(f"availability {availability_annual:.1%} < {avail_min:.0%}")
    return out
