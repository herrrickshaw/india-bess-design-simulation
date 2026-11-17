"""Tender dataset loading and normalisation."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .cost import CostInputs, breakeven_tariff, capex_breakdown, implied_capex_per_mwh
from .debt import DebtTerms, lender_view, max_gearing

DATA = Path(__file__).resolve().parent.parent / "data"


def load_tenders() -> pd.DataFrame:
    df = pd.read_csv(DATA / "tenders.csv")
    return df


def load_players() -> pd.DataFrame:
    return pd.read_csv(DATA / "players.csv")


def load_pib() -> pd.DataFrame:
    return pd.read_csv(DATA / "pib_facts.csv")


def inr_per_kwh(tariff_lakh_mw_month: float, duration_h: float, cycles_per_day: float) -> float:
    """Convert a capacity charge to INR per kWh discharged (comparable to PIB figures)."""
    kwh_per_month = 1000 * duration_h * cycles_per_day * 365 / 12
    return tariff_lakh_mw_month * 1e5 / kwh_per_month


def tariff_per_mwh_capacity(tariff: float, duration_h: float) -> float:
    """Capacity charge per MWh of energy capacity (INR lakh/MWh/month); equalises 2h vs 4h."""
    return tariff / duration_h


def analyse(vgf: bool = False, terms: DebtTerms | None = None) -> pd.DataFrame:
    """Awarded tenders with a tariff and duration, vs the bottom-up cost model.

    Adds the lender view (DSCR, equity IRR, DSRA, highest gearing a lender would accept)
    at each awarded tariff, using IREDA-style terms unless `terms` is given.
    """
    terms = terms or DebtTerms()
    df = load_tenders()
    df = df[df["tariff_lakh_per_mw_month"].notna() & df["duration_h"].notna()
            & df["status"].isin(["awarded"])].copy()
    rows = []
    for _, r in df.iterrows():
        dur = float(r["duration_h"])
        inp = CostInputs(duration_h=dur, vgf_inr_lakh_per_mwh=46.0 if vgf else 0.0)
        be = breakeven_tariff(inp)
        cap = capex_breakdown(inp)
        t = float(r["tariff_lakh_per_mw_month"])
        lv = lender_view(inp, terms, t)
        rows.append({
            "min_dscr": round(lv["min_dscr"], 2) if lv["min_dscr"] is not None else None,
            "avg_dscr": round(lv["avg_dscr"], 2) if lv["avg_dscr"] is not None else None,
            "equity_irr_pct": round(lv["equity_irr"] * 100, 1) if lv["equity_irr"] is not None else None,
            "bankable_at_70pct": lv["meets_dscr"],
            "max_gearing_pct": round(max_gearing(inp, terms, t) * 100),
            "dsra_cr_per_100mw": round(lv["dsra_peak_cr"], 1),
            "tender_id": r["tender_id"], "date": r["date"], "duration_h": dur,
            "tariff": t,
            "tariff_per_mwh_cap": round(t / dur, 3),
            "inr_per_kwh_2cyc": round(inr_per_kwh(t, dur, 2.0), 2),
            "inr_per_kwh_1.5cyc": round(inr_per_kwh(t, dur, 1.5), 2),
            "model_breakeven": round(be, 2),
            "gap_vs_breakeven_pct": round((t / be - 1) * 100, 1),
            "model_capex_cr_per_mwh": round(cap["per_poi_mwh_crore"], 3),
            "supportable_capex_cr_per_mwh": round(implied_capex_per_mwh(inp, t), 3),
        })
    return pd.DataFrame(rows)
