# India BESS tenders, players and assembly capacity — snapshot to 10 Nov 2026

Everything here traces to a row in `data/*.csv` with a source URL and a confidence tag.
Numbers marked *model* come from `bess_sim` and rest on placeholder assumptions listed in
`bess_sim/cost.py` (each tagged SOURCED or ASSUMPTION). Re-run: `python scripts/run_tender_analysis.py`.

## 1. What the tenders say

| Tender | When | Size | Tariff (₹ lakh/MW/month) | Winner |
|---|---|---|---|---|
| SECI pilot | Aug 2022 | – | 10.84 | – |
| SECI | Mar 2024 | – | 4.49 | – |
| SECI | Sep 2024 | – | 3.81 | – |
| APTRANSCO (duration not stated) | Dec 2025 | 1,000 MW | 1.48 (record low) | SVR Electro |
| NVVN 2h | Feb 2026 | 250 MW / 500 MWh | 1.81 | – |
| **SECI Odisha 4h** | Mar 2026 | 125 MW / 500 MWh | 3.04 / 3.05 / 3.75 | Coal India (80 MW), Onward Solar (45 MW) |
| GUVNL 2h | Aug 2026 | 450 MW / 900 MWh | 2.32 | NLC India Renewables, Sun Drops (KP Group) |
| WBSEDCL 4h | Aug 2026 | 200 MW / 800 MWh | 4.35 | NTPC Green |
| MSEDCL 2h | Sep 2026 | 2,000 MW / 4,000 MWh | 2.38 (1,500 MW), 2.40 (500 MW) | Oriana Power 900 MW + five others |
| SJVN 2h | Sep 2026 | 265 MW / 530 MWh | 2.35 | NLC Renewables |

**SECI specifically.** The only SECI standalone award I could confirm in 2026 is Odisha (Mar).
SECI's **800 MW / 3,200 MWh 4h** tender closed 30 Oct, bids opened 4 Nov; **I found no result**.
Also pending: SECI Pang (Ladakh) 1 GW solar + 1 GW/4 GWh storage (site-visit stage), and a SECI
1,200 MW solar + 600 MW/3,600 MWh tranche where CERC adopted ₹3.12–3.13/kWh (blended, not a capacity charge).

**Read-across.** Tariffs fell ~78% from Aug 2022 to Sep 2026 (10.84 → 2.38). Normalise 2h vs 4h by
dividing by duration: Odisha 4h ≈ 0.76–0.94 lakh/MWh/month, GUVNL/MSEDCL 2h ≈ 1.16–1.20, so the 4h
bids are *cheaper per MWh* and the headline gap (3.0 vs 2.3) is mostly duration. JMK also reports
57% of September's issuance was re-tendered, and Mercom says only ~9 GW of 28 GW tendered in H1 2026 was auctioned.

## 2. Do the tariffs close? (model, calibrated: see [CALIBRATION.md](CALIBRATION.md))

Inputs are anchored to public prices (no vendor quotes were available): DC block $69.4/kWh (SMM, Sep 2026),
China EPC bids plus Indian duty, ₹95.5/$, IREDA-band debt at 9.5%, 15% equity hurdle, 15-year term,
procurer supplies charging energy. All capex figures below are **per installed MWh**, the basis market
prices and CTUIL use; the model's per-delivered-MWh figure is about 27% higher.

| Check | Result |
|---|---|
| Model capex, 2h / 4h | ₹1.45 / ₹1.35 crore per installed MWh, inside the China-EPC-plus-duty range (1.46–1.53 / 1.28–1.44) and Indian turnkey guides (1.2–1.8) |
| CTUIL benchmark (Sep 2026) | ₹0.80 crore/MWh, about 45% below the market-calibrated cost |
| Break-even 2h tariff, no VGF | **5.32** lakh/MW/month; 2h awards (2.32–2.40) are 55–56% below it |
| Break-even 2h tariff, VGF ₹46 lakh/MWh | 4.19; awards still 43–45% below |
| Break-even 4h tariff | 9.92 (VGF 7.65); 4h awards are 56–69% below |
| Capex each 2h award can just support (NPV at WACC) | ₹0.63–0.66 crore per installed MWh, below even CTUIL's 0.80 |

**Correction to an earlier version of this note.** It said the tariff-implied capex (≈ ₹0.80–0.83 crore/MWh)
matched CTUIL's benchmark and called that "the check I trust most". That compared a per-*delivered*-MWh figure with a
per-*installed*-MWh benchmark. On a like-for-like basis the awards support about ₹0.64 crore per installed MWh, 20%
below CTUIL's benchmark and well under half the market-calibrated cost. The earlier agreement was an artefact.

**Reading.** Two cost worlds disagree: public price indices say about ₹1.45 crore/MWh; CTUIL's benchmark and the
awards imply ₹0.8 or less. The awards are viable only if developers' real cost is near CTUIL's figure and VGF
is received (with VGF the 2h break-even at ₹0.80 crore/MWh is 2.18, under the 2.3–2.4 bids), or if bidders accept
sub-hurdle returns. This matches IEEFA/JMK's view that much of 2025's pricing may be unviable, but a model on
public indices cannot settle it; actual quotes can (use `data/vendor_quotes_template.csv`). Oriana's ~₹324 cr
VGF on its MSEDCL share is the one concrete subsidy datapoint.

## 3. PIB (primary, read directly)

| Release | Date | Key content |
|---|---|---|
| [2204118](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2204118) | 15 Dec 2025 | ₹10.18/kWh (2022-23) → ~₹2.1/kWh at 2 cycles, ₹2.8 at 1.5 cycles; VGF-1 13,220 MWh/₹3,760 cr; VGF-2 30 GWh/₹5,400 cr (PSDF); ISTS waiver; ACC PLI 50 GWh |
| [2118325](https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2118325) | 3 Apr 2025 | VGF per MWh cut ₹96 → ₹46 lakh (or 30% of capex); no project had reached financial close in 2024-25; NEP: 236 GWh by 2031-32 |
| [2246898](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2246898&lang=2&reg=3) | 30 Mar 2026 | 35.8 GWh under construction; 798 MWh existing (Bihar 282, Karnataka 150, Chhattisgarh 120); NEP 208 GWh by 2030 |

**Not verified:** the 4 Nov 2026 Cabinet scheme (₹14,500 cr, 92 GWh, 40% DCR) exists only in secondary reports;
I did not read the PIB release. Treat as unconfirmed.

**Data disagreement to know about:** PIB's 798 MWh (Mar 2026) vs Mercom's 8.2 GWh added in H1 2026 vs JMK's
10.2 GWh cumulative operational (Sep 2026) — different dates, different thresholds, unreconciled.

## 4. Players and assembly plants

Cell dependence is the story: Tata Power says >80% of cells are imported; Indian landed LFP cells run
14–23% above China's post-tax price (JMK); container prices rose ~22% from the Q4-2025 low ($57) to $69.4/kWh (Sep 2026).

| Segment | Operating / commissioned | Announced or ramping |
|---|---|---|
| Container/pack assembly | JSW Energy 5 GWh (Pune), Tata AutoComp-Gotion 6, GoodEnough 7 (Noida), Waaree 5.15 (Gujarat) ≈ **23 GWh/yr** | Aare Solar 10 GWh (Odisha, approved), Powertrac 10 (Ahmedabad), VSL PowerHive 5 |
| Cells | Exide 6 GWh phase 1 (Karnataka), Ola ~1 GWh | Reliance 40 GWh phase 1 Jamnagar (commissioning), Amara Raja 2 GWh in 2027, Waaree 16 GWh |
| Policy | ACC PLI: 50 GWh target, ~40 GWh awarded; only ~2.8% of awarded commissioned (IEEFA, Sep 2026) | rebid of remaining 10 GWh grid-scale, Jul 2026 |

Do not add operating and announced figures. Sources conflict on Reliance's long-term target (100 vs 120 GWh)
and Exide's scale (6 GWh done vs up to 12 planned).

## 5. Gaps I could not close

- SECI 800 MW/3.2 GWh result; PIB state-wise VGF allocation; APTRANSCO duration; per-winner MSEDCL split.
- Tata/Agratas and Premier Energies: searches returned nothing usable, so they are absent from `players.csv`.
- Real hourly IEX prices / state net load: dispatch uses **synthetic** shapes until real CSVs are supplied.
