"""Lender view: tenor, amortisation, DSCR, DSRA and equity return.

Terms follow IREDA's financing norms (issue 33, 12 Jun 2026; data/raw_lending/):
  * loan <= 70% of project cost, promoter >= 30%, equity brought in upfront
  * BESS repayment <= 80% of the agreement period, capped at 20 years, moratorium <= 1.5 y
  * DSRA = highest quarter of interest+principal: 1 quarter in year 1, then 2 quarters,
    except SECI/NTPC/central utility or A+ discom offtake, where it falls away after 1.5 y
  * DSRA does not form part of project cost, so promoters fund it on top
IREDA publishes NO BESS-specific DSCR. dscr_min / dscr_avg below are ASSUMPTIONS taken from
its lowest general figures (1.2 for 80% leverage; 1.3 for new clients in "other sectors").

Simplifications: augmentation is pre-funded through a maintenance reserve (MRA) accrued evenly
up to the year of spend, so CFADS is net of MRA contributions; annual periods; DSRA sized as max annual debt service / 4; 1.5 y rounded
up to year 2; no interest on DSRA; no tax-loss carry-forward; no cash lock-up; interest
during construction ignored (capex treated as paid at COD).
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .cost import CostInputs, npv, operating_lines


@dataclass(frozen=True)
class DebtTerms:
    gearing: float = 0.70                 # SOURCED: IREDA max 70% loan
    rate: float = 0.095                   # ASSUMPTION: inside IREDA ESS band 8.65-9.65% (+0.50% if merchant or <200 MWh)
    agreement_years: int = 15             # SOURCED: MSEDCL-style 15-year agreements
    tenor_frac_of_agreement: float = 0.80  # SOURCED: IREDA BESS policy
    max_tenor_years: int = 20             # SOURCED: IREDA BESS policy cap
    moratorium_years: int = 1             # SOURCED: IREDA allows up to 1.5 y; whole years used
    offtaker: str = "central"             # central | other_discom | third_party
    dscr_min: float = 1.20                # ASSUMPTION (see module docstring)
    dscr_avg: float = 1.30                # ASSUMPTION (see module docstring)

    @property
    def tenor(self) -> int:
        return int(min(self.max_tenor_years, self.agreement_years * self.tenor_frac_of_agreement))


def _irr(flows, lo=-0.9, hi=2.0):
    f_lo, f_hi = npv(lo, flows), npv(hi, flows)
    if f_lo > 0 and f_hi > 0:
        return hi            # IRR above the bracket
    if f_lo < 0 and f_hi < 0:
        return lo            # equity never recovered
    for _ in range(100):
        mid = (lo + hi) / 2
        if npv(mid, flows) * f_lo > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _mra_contributions(aug: list) -> list:
    """Maintenance/augmentation reserve: each augmentation spend is accrued evenly over the
    years before it falls due, so CFADS is not hit by a lump. Contributions sum to the spend."""
    out = [0.0] * len(aug)
    for y, amt in enumerate(aug, start=1):
        if amt > 0:
            for k in range(y):               # years 1..y (spend year included)
                out[k] += amt / y
    return out


def loan_schedule(c: CostInputs, t: DebtTerms, tariff: float) -> dict:
    """Year-by-year debt, CFADS and DSCR (INR crore). Index 0 of lists = year 1."""
    ol = operating_lines(c, tariff)
    n = min(t.tenor, c.life_years)
    debt0 = t.gearing * ol["capex"]
    amort_years = max(1, n - t.moratorium_years)
    r = t.rate
    annuity = debt0 * r / (1 - (1 + r) ** -amort_years) if r > 0 else debt0 / amort_years
    bal = debt0
    mra = _mra_contributions(ol["aug"])
    interest, principal, tax, cfads, ds = [], [], [], [], []
    for y in range(1, c.life_years + 1):
        i = bal * r if y <= n else 0.0
        if y <= t.moratorium_years or y > n:
            p = 0.0
        else:
            p = min(bal, annuity - i)
        ebitda = ol["rev"][y - 1] - ol["opex"][y - 1]
        tx = max(0.0, (ebitda - ol["dep"] - i) * c.tax_rate)
        interest.append(i); principal.append(p); tax.append(tx)
        cfads.append(ebitda - tx - mra[y - 1])
        ds.append(i + p)
        bal -= p
    dscr = [cfads[k] / ds[k] if ds[k] > 1e-12 else None for k in range(c.life_years)]
    return {"debt0": debt0, "capex": ol["capex"], "tenor": n, "interest": interest,
            "principal": principal, "ds": ds, "cfads": cfads, "dscr": dscr, "tax": tax}


def dsra_profile(ds: list, offtaker: str, tenor: int) -> list:
    """Required DSRA balance at the end of year 0..life (INR crore); year 0 = funded at COD."""
    q = max(ds) / 4.0
    life = len(ds)
    bal = [0.0] * (life + 1)
    bal[0] = q                                   # 1 quarter from COD
    for y in range(1, life + 1):
        if offtaker == "central":
            bal[y] = q if y < 2 else 0.0         # not required after 1.5 y (rounded up to 2)
        else:
            bal[y] = 2 * q if (2 <= y < tenor) else (q if y < 2 else 0.0)
    return bal


def lender_view(c: CostInputs, t: DebtTerms, tariff: float) -> dict:
    s = loan_schedule(c, t, tariff)
    n = s["tenor"]
    d = [x for x in s["dscr"][:n] if x is not None]
    min_d = min(d) if d else None
    avg_d = sum(d) / len(d) if d else None
    dsra = dsra_profile(s["ds"], t.offtaker, n)
    equity0 = s["capex"] - s["debt0"]
    flows = [-(equity0 + dsra[0])]
    for y in range(1, c.life_years + 1):
        flows.append(s["cfads"][y - 1] - s["ds"][y - 1] - (dsra[y] - dsra[y - 1]))
    irr = _irr(flows)
    ok = bool(min_d is not None and min_d >= t.dscr_min and avg_d >= t.dscr_avg)
    return {"debt_cr": s["debt0"], "equity_cr": equity0, "dsra_peak_cr": max(dsra),
            "dsra_at_cod_cr": dsra[0], "tenor_years": n, "min_dscr": min_d, "avg_dscr": avg_d,
            "equity_irr": irr, "meets_dscr": ok,
            "breach_years": [k + 1 for k, x in enumerate(s["dscr"][:n]) if x is not None and x < t.dscr_min]}


def _solve(fn, lo=0.0, hi=50.0):
    """Smallest x in [lo, hi] with fn(x) True, assuming fn is monotone False->True."""
    for _ in range(70):
        mid = (lo + hi) / 2
        if fn(mid):
            hi = mid
        else:
            lo = mid
    return hi


def min_tariff_for_dscr(c: CostInputs, t: DebtTerms) -> float:
    """Lowest capacity charge (INR lakh/MW/month) that passes both DSCR tests."""
    return _solve(lambda x: lender_view(c, t, x)["meets_dscr"])


def tariff_for_equity_irr(c: CostInputs, t: DebtTerms, target: float | None = None) -> float:
    tgt = c.equity_return if target is None else target

    def ok(x):
        irr = lender_view(c, t, x)["equity_irr"]
        return irr is not None and irr >= tgt
    return _solve(ok)


def bankable_tariff(c: CostInputs, t: DebtTerms) -> dict:
    """Tariff that satisfies the lender (DSCR) AND the sponsor (equity IRR); larger one binds."""
    a, b = min_tariff_for_dscr(c, t), tariff_for_equity_irr(c, t)
    return {"dscr_tariff": a, "equity_irr_tariff": b, "bankable": max(a, b),
            "binding": "DSCR" if a >= b else "equity IRR"}


def max_gearing(c: CostInputs, t: DebtTerms, tariff: float) -> float:
    """Highest gearing (<= t.gearing) a lender would accept at this tariff; 0 if none."""
    if lender_view(c, replace(t, gearing=0.05), tariff)["meets_dscr"] is False:
        return 0.0
    lo, hi = 0.05, t.gearing
    if lender_view(c, t, tariff)["meets_dscr"]:
        return t.gearing
    for _ in range(50):
        mid = (lo + hi) / 2
        if lender_view(c, replace(t, gearing=mid), tariff)["meets_dscr"]:
            lo = mid
        else:
            hi = mid
    return lo


def dc_price_for_bankability(c: CostInputs, t: DebtTerms, tariff: float,
                             require_equity_irr: bool = False) -> float:
    """DC block price (USD/kWh FOB) at or below which `tariff` passes the DSCR tests at
    t.gearing (and, optionally, the sponsor's equity-IRR target). All other inputs fixed.

    This answers the practical question the tender table raises: what equipment price would
    have to hold for this award to be financeable?
    """
    def ok(price):
        cc = replace(c, dc_block_usd_per_kwh=price)
        v = lender_view(cc, t, tariff)
        if not v["meets_dscr"]:
            return False
        return (not require_equity_irr) or (v["equity_irr"] is not None and v["equity_irr"] >= c.equity_return)
    lo, hi = 1.0, 200.0
    if not ok(lo):
        return 0.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if ok(mid):
            lo = mid
        else:
            hi = mid
    return lo
