# Lender checks and data-centre integration

Re-run: `python scripts/run_tender_analysis.py` (lender sections at the end) and
`python scripts/run_datacentre.py`. Code: `bess_sim/debt.py`, `bess_sim/datacentre.py`.

## 1. Lending criteria as implemented

Source: IREDA financing norms, issue 33, updated 12 Jun 2026 ([PDF](https://www.ireda.in/IredaWebPortal/documents/loan-products/financing-norms.pdf);
BESS policy table at the document's p. 92). The text extract is kept local only (third-party document); re-create it with `curl` and `pdftotext -layout`. It is the only lender document I could read in full.
No published BESS terms from SBI, PFC or REC turned up.

| Term | IREDA | In the model |
|---|---|---|
| Loan / promoter | ≤ 70% loan, ≥ 30% promoter, equity upfront | `DebtTerms.gearing = 0.70` |
| Tenor | ≤ 80% of agreement period, cap 20 y | 15-y agreement gives **12 y** (`tenor`) |
| Moratorium | up to 1.5 y | 1 y interest-only (whole years only) |
| Rate | 8.65–9.65% by grade for storage > 200 MWh qualifying as infrastructure; +0.50% if merchant or < 200 MWh | 9.5% (ASSUMPTION inside the band) |
| DSRA | highest quarter of interest + principal; 1 quarter in year 1, then 2 quarters, but none after 1.5 y if the offtaker is SECI/NTPC/central utility or an A+ discom; DSRA is not part of project cost | `dsra_profile`; promoters fund it on top |
| DSCR | **no BESS figure published.** General: 1.2 (80% leverage), 1.25–1.3 (new clients), 1.4 (manufacturing) | min 1.20, average 1.30 (ASSUMPTION) |
| Fee | 0.25% of loan, ₹10–25 lakh, because BESS is a "new technology" | not modelled |
| Extra security | corporate/personal guarantee, 51% share pledge, or 20% of the loan as BG/FD | not modelled |

RBI's Project Finance Directions 2025 (in force 1 Oct 2025) add construction-phase provisioning
(1%) and extra provisioning for each quarter COD slips. I read only law-firm summaries and found no
BESS-specific rate; check circular RBI/2025-26/59 before relying on it.

**Modelling choices that matter:** augmentation is pre-funded through a maintenance reserve
accrued evenly to the year of spend (lumpy augmentation otherwise fakes a DSCR breach in years 6 and
11); DSRA sized as max annual debt service ÷ 4; 1.5 y rounded up to 2; no tax-loss carry-forward;
interest during construction ignored.

## 2. What the lender view says about the awards (2h unless stated)

Costs calibrated to public price anchors ([CALIBRATION.md](CALIBRATION.md)); 70% gearing, 12-year tenor.

| Case | Result |
|---|---|
| Tariff that passes DSCR at 70% gearing | **5.09** lakh/MW/month (2h), 9.48 (4h) |
| Tariff that also meets the 15% equity hurdle | **5.62** (2h), 10.49 (4h); the equity hurdle binds, not DSCR |
| Same with VGF ₹46 lakh/MWh | 4.02 / 4.44 (2h); 7.39 / 8.13 (4h) |
| Awarded 2h tariffs (2.32–2.40), no VGF | minimum DSCR 0.44–0.46, equity IRR ≈ −20% |
| Same, with VGF | minimum DSCR 0.58–0.62, equity IRR ≈ −12% to −13% |
| Highest gearing a lender would accept at those tariffs | ≈ 25–27% (no VGF), ≈ 34–36% (VGF) |
| Total installed capex at which the 2h awards pass DSCR at 70% | ≈ ₹0.66–0.69 crore/MWh (no VGF), ≈ ₹0.88–0.91 (VGF); calibrated cost is 1.45, CTUIL benchmark 0.80 |

**How to read this.** Projects are being financed at these tariffs, so either real costs sit near or below CTUIL's
₹0.80 crore/MWh benchmark (with VGF the awards then clear DSCR at ≈ ₹0.9), or lenders and sponsors are accepting
terms far looser than IREDA-style norms. The table says what must be true, not that the awards fail. An earlier
version of this table used uncalibrated, lower costs and looked far more benign (minimum DSCR ≈ 0.7); the calibration
removed that comfort. Replace the public-price anchors with real RFQ responses and a lender term sheet before using
these numbers for a bid.

## 3. Data-centre integration

### Demand side (read directly from the [SBI Apr 2026 report](https://sbi.bank.in/documents/57189647/58231607/Sector+Report+DataCentre.pdf/f1919592-ee66-b50b-ea20-75fbb27c9bb5?t=1779885206866) and [Invest India Oct 2026 paper](https://static.investindia.gov.in/s3fs-public/2026-10/latest-news-India-Data-Centre-Growth-Story.pdf); facts in `data/datacentre_facts.csv`; full-text extracts kept local only)

- Operational capacity ≈ 1.8 GW (H1 2026), 3.9 GW under development, 5.6 GW by 2030 (base) or ≈ 8 GW
  (accelerated). Other forecasts: SBI > 6.5 GW, Cushman & Wakefield ≈ 4.2 GW, Jefferies ≈ 8 GW.
- Hubs: Mumbai, Noida, Hyderabad, Chennai; new campuses at **Visakhapatnam (4 GW+), Jamnagar (1 GW+),
  Dholera (250 MW)**. Hyperscalers are 60–70% of new co-location demand.
- These hubs sit in states that already ran storage tenders: **Andhra Pradesh** (APTRANSCO, 1 GW, ₹1.48 lakh
  record low), **Gujarat** (GUVNL; Reliance's 40 GWh cell/BESS gigafactory is in Jamnagar), **Maharashtra**
  (MSEDCL, 2 GW). That overlap is the strongest structural argument for co-development.
- Policy: consumers may now own, lease or operate storage (Electricity Rules amendment, Sep 2025, PIB
  2246898); ISTS waiver for co-located BESS commissioned by June 2028 (PIB 2204118); MeitY AI-cloud
  tenders require PUE < 1.35.

### What storage can and cannot do for a data centre (modelled, synthetic RE profiles)

100 MW IT load × PUE 1.4 = 140 MW, 1.23 TWh/yr, load factor ≈ 0.96. Hourly CFE (carbon-free energy
matched hour by hour), 4h battery, ₹ figures use this repo's calibrated break-even capacity charge:

| RE built (solar + wind) | RE energy ÷ load | CFE, no battery | 90% CFE needs | Adds to DC energy cost |
|---|---|---|---|---|
| 250 + 150 MW | 0.75x | 62% | unreachable (caps near 73%) | – |
| 400 + 250 MW | 1.22x | 77% | 586 MWh / 146 MW | ₹1.42/kWh (₹1.10 with VGF) |
| 500 + 300 MW | 1.50x | 82% | 371 MWh / 93 MW | ₹0.90/kWh (₹0.69) |
| 600 + 400 MW | 1.89x | 88% | 87 MWh / 22 MW | ₹0.21/kWh (₹0.16) |

1. **Storage cannot beat the energy cap.** With RE at 0.75x of load, even 4 GWh of storage stalls near 73%.
   Hitting 90%+ means oversizing RE, which then curtails 17–46% of its output. The real decision is how to
   split spend between RE oversizing and storage, and the model makes that trade explicit.
2. **A widely quoted rule of thumb (≈ 450 MWh with 250 MW solar + 150 MW wind per 100 MW of data centre)**
   reaches only ≈ 71% in this synthetic test. It is a secondary-source figure with no stated definition of
   "24x7"; treat it as unverified.
3. **Demand-charge shaving is weak.** Data-centre load is almost flat, so there is little peak to shave.
4. **Pure behind-the-meter arbitrage needs a large spread.** A 2h battery must capture ₹9.2/kWh at one cycle
   a day, ₹4.6 at two (₹7.3 and ₹3.6 with VGF) on every discharged kWh. State ToD spreads are usually smaller;
   I found no state tariff schedule, so this is a threshold to compare against, not a conclusion.
5. **UPS-class storage is small.** 15 minutes of ride-through at 140 MW is ≈ 41 MWh, about 15% of a 2h
   battery of equal power. It adds resilience value but will not carry a project.

### Opportunities, ranked by how well they are supported

| # | Opportunity | Evidence | Status |
|---|---|---|---|
| 1 | Firm renewable supply for hourly CFE (FDRE plus BESS) at hyperscale campuses | operator statement (STT GDC, evening-peak FDRE+BESS from CY2026); model above | sourced + modelled |
| 2 | Co-locate storage at Vizag, Jamnagar, Dholera, Mumbai-Pune where RE, tendering and campuses overlap | Invest India hub map; tender table | sourced |
| 3 | Data centre as capacity-charge offtaker, replacing a discom: bankable 2h tariff ≈ ₹5.6 lakh/MW/month vs ≈ ₹2.3–2.4 discoms bid; works out at roughly ₹0.2–1.4/kWh of load at 90% CFE | model | modelled, assumption-heavy |
| 4 | Resilience: UPS augmentation and diesel-generator avoidance | SBI notes on-site solar and storage in hyperscale design; ride-through maths | qualitative |
| 5 | Grid services and demand response from campus storage | secondary sources disagree on whether market rules recognise it | uncertain |
| 6 | Financing angle: IREDA treats data-centre offtake as "third party", needing 2 quarters of DSRA instead of 1, so the lender view is worse than for SECI/NTPC offtake unless a rated hyperscaler or parent guarantee changes the credit | IREDA norms | sourced inference |
| 7 | Anchor load to de-risk merchant BESS where PPA signing has stalled | none found | hypothesis only |

## 4. Gaps

No state ToD or demand-charge schedules, no data-centre-linked BESS tender volumes, no SBI/PFC/REC BESS terms,
and no real hourly RE profiles. The CFE results are shape-level, not site-level; replace `synthetic_re`
with PVGIS/NIWE or developer data before using them.
