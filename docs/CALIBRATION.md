# Calibrating the cost model

**What this is and is not.** No vendor quotes were available to me, so inputs are anchored to *public* price
evidence: market indices, tender-tracker averages, a customs clarification and lender documents. Every anchor,
with source and confidence, is in [`data/calibration_anchors.csv`](../data/calibration_anchors.csv). When you have
real RFQ responses, fill [`data/vendor_quotes_template.csv`](../data/vendor_quotes_template.csv) and load it (see the end).

Re-run: `python scripts/run_calibration.py` (output in [`calibration_output.txt`](calibration_output.txt)).

## What changed

| Input | Before | After | Anchor | Confidence |
|---|---|---|---|---|
| DC block, USD/kWh | 69.4 | 69.4 (kept) | SMM container FOB, Sep 2026. Cross-check: CNESA H1-2026 2h and 4h system bids, fitted as energy part + power part, imply **$67.7/kWh**, within 3% | medium |
| Landed uplift | 15% (assumed) | 15% | 10% basic customs duty on stationary grid-scale Li-ion BESS confirmed by the finance ministry (Oct 2026); ~1% surcharge and ~4% logistics assumed; IGST treated as creditable | medium, part-assumed |
| PCS + MV, ₹/kW | 3,800 (assumed) | **3,570** | CNESA fit: $32.5/kW power-related system part, × 95.5, × 1.15 landed | low |
| BoS + EPC, ₹/kWh | **600** (assumed) | **4,840** | China EPC bids (TrendForce 2h 1.00–1.05, 4h 0.88–0.99 CNY/Wh) less the CNESA system price | low |
| Grid + land, ₹ lakh/MW | 15 (assumed) | **17.1** | Same EPC-less-system residual, power-related part | low |
| Equity hurdle | 14% | **15%** | Lenders reportedly want 15–20% returns (IEEFA/JMK press coverage; secondary) | low |
| Opex 1.5%, debt 9.5%, tenor, DSCR | as before | as before | Opex within published 1–2.5% spread; rate inside IREDA's 8.65–9.65% band (read from primary) | medium |
| Degradation, augmentation | assumed | assumed | Sources span 1% to 3% a year; no warranty terms found | not calibrated |

**The big move is BoS + EPC**, from ₹600 to ₹4,840 per kWh. My earlier figure was a placeholder that was far too
low next to what Chinese EPC tenders imply once system hardware is subtracted. Treat the new figure with caution:
it comes from a two-point split of noisy monthly averages (power-related part ranges from $34 to $67 per kW across
months), and it assumes India's civil and EPC cost equals China's (factor 1.0, an assumption).

## Does the calibrated model agree with the market?

Per **installed** MWh, the basis market prices use (INR crore):

| | 2h | 4h |
|---|---|---|
| Model | 1.45 | 1.35 |
| China EPC + Indian duty | 1.46–1.53 | 1.28–1.44 |
| Indian turnkey guides (vendor blogs) | 1.2–1.8 | 1.2–1.8 |
| NLC India pipeline (article) | 1.40 | – |
| CTUIL benchmark, Sep 2026 | 0.80 | 0.80 |

The model now sits inside the China and Indian ranges. NLC's 1.40 is identical across three projects, which looks
like a planning figure, not a measured cost; the article's USD conversion is also off by a factor of 1,000. CTUIL's
0.80 is the outlier on the low side.

**A basis trap I fell into.** The model also reports capex per *delivered* (POI) MWh, about 27% higher because the
battery is oversized for round-trip loss, depth of discharge and degradation. The first version of the tender note
compared a per-delivered figure with CTUIL's per-installed benchmark and concluded they agreed. They did not.

## What the calibration does to the verdict

2h tariff in ₹ lakh/MW/month, by cost per installed MWh:

| Cost case | cr/MWh | NPV break-even | with VGF | bankable (lender + equity) | with VGF |
|---|---|---|---|---|---|
| CTUIL benchmark | 0.80 | 2.93 | 2.18 | 3.09 | 2.31 |
| China EPC low end (0.74 CNY/Wh + duty) | 1.08 | 3.94 | 2.93 | 4.16 | 3.11 |
| **Calibrated** | 1.45 | 5.32 | 4.19 | 5.62 | 4.44 |
| Indian turnkey high end | 1.80 | 6.59 | 5.46 | 6.96 | 5.78 |

The awards (₹2.32–2.40) clear only in the first row with VGF (break-even 2.18, bankable 2.31 against bids of
2.32–2.40) and are not close in any other. So the entire viability question reduces to one number: what developers
actually pay per installed MWh. If it is near CTUIL's 0.80 and VGF is received, the awards work. If it is near the
public indices, they lose money. This repo cannot tell which; a quote can.

Candidate explanations for a cost far below public indices, none of them verified: bulk or captive cell supply at the
low end of China's range, cheaper Indian civil and EPC than China's, revenue beyond the 15-year term or extra
cycling, or returns below the hurdle. The competing explanation is that some bidders are underpricing, which
IEEFA/JMK and Mercom both suggest.

## Plugging in real quotes

```python
from bess_sim import calibration as cal, cost
inputs, changes = cal.cost_inputs_from_quotes("data/vendor_quotes_template.csv")
for c in changes: print(c["item"], c["old"], "->", c["new"], f"({c['n_quotes']} quotes, spread {c['spread']:.1f})")
print(cal.market_check(2.0, inputs))          # does it still sit inside the public anchors?
print(cost.breakeven_tariff(inputs))
```

Units are checked (a quote in the wrong unit raises), several quotes for one item are averaged, and an empty
template loads unchanged. Ask each vendor to state: DC block FOB per **nameplate** kWh with Incoterm, chemistry and warranty
terms (years, throughput, end-of-warranty state of health); PCS + MV delivered and duty-paid; EPC scope split from
interconnection; annual O&M and insurance separately; and, from a lender, rate, tenor, gearing, DSCR and DSRA terms.

## Still uncalibrated

Augmentation timing and price decline, degradation, availability penalties, decommissioning, working capital, and
the India-versus-China EPC factor. The first three matter most for a 15-year contract.
