# bess-design-simulation

Design, sizing, cost and dispatch models for grid-scale battery storage in India, plus a sourced
dataset of recent tenders (SECI and others), PIB statements, and domestic assembly/cell capacity.

Start with [`docs/TENDER_ANALYSIS.md`](docs/TENDER_ANALYSIS.md), then [`docs/CALIBRATION.md`](docs/CALIBRATION.md) and [`docs/LENDING_AND_DATACENTRES.md`](docs/LENDING_AND_DATACENTRES.md).

## Modules (`bess_sim/`)

| Module | Does |
|---|---|
| `cost.py` | Bottom-up capex (DC block, PCS/MV, BoS, grid), opex, augmentation, post-tax NPV; **break-even capacity charge** (₹ lakh/MW/month, the tender metric), supportable capex for a given tariff, DC price implied by a tariff, LCOS in ₹/kWh |
| `sizing.py` | MW/MWh for peak shaving, solar shifting, RE firming |
| `dispatch.py` | Daily LP arbitrage (HiGHS) with RTE; synthetic duck-curve prices and net load |
| `calibration.py` | Checks capex against public price anchors on the installed-MWh basis, scenario scaling, tariff-implied capex, and a loader that turns vendor quotes into `CostInputs` |
| `debt.py` | Lender view: IREDA-style tenor (80% of agreement), moratorium, annuity, DSCR (min and average), DSRA by offtaker type, maintenance reserve, equity IRR; bankable tariff, highest acceptable gearing, equipment price at which an award is financeable |
| `datacentre.py` | Flat data-centre load, synthetic RE, hourly CFE with a battery, battery size for a CFE target, firming cost per kWh of load, required arbitrage spread, UPS ride-through energy |
| `grid.py` | PCS/transformer/land at the point of interconnection, ISTS waiver schedule, GUVNL-style RTE/availability checks |
| `tenders.py` | Loads `data/*.csv`, converts tariffs to ₹/kWh and per-MWh, compares each award to the model |

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python scripts/run_tender_analysis.py
.venv/bin/python scripts/run_sizing_demo.py
.venv/bin/python scripts/run_datacentre.py
.venv/bin/python scripts/run_calibration.py
```

## Data (`data/`)

`tenders.csv`, `players.csv`, `pib_facts.csv`, `datacentre_facts.csv`, `calibration_anchors.csv`, `vendor_quotes_template.csv` (fill with real RFQ responses). Each row carries `source_url` and a `confidence` or
`verification` tag. `data/raw_pib/*.txt` holds extracted text of the three PIB releases read directly.
Full-text extracts of third-party reports (IREDA, SBI, Invest India) are deliberately not committed; the facts taken from them are in the CSVs with page-level URLs. PIB blocks WebFetch; plain `curl` with a browser User-Agent works.

## Know before trusting any output

- Cost defaults are calibrated to *public* price anchors, not vendor quotes (see `docs/CALIBRATION.md`). BoS/EPC and grid costs are derived from noisy China tender averages; replace with real quotes via `vendor_quotes_template.csv`. Degradation and augmentation remain assumptions.
- Dispatch prices and net load are **synthetic**; the arbitrage revenue shown is illustrative, ignores cycle-wear cost by default, and is not a merchant forecast.
- ISTS waiver schedule for non-co-located plants is my reading of "graded steps of 25%"; confirm against the MoP order.
- DSCR thresholds are assumptions: IREDA publishes no BESS-specific figure. Data-centre RE profiles are synthetic.
- Tender figures come mostly from trade press; PIB figures were read from the releases. Confidence is per row.
