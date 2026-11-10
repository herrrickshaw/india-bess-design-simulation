# bess-design-simulation

Design, sizing, cost and dispatch models for grid-scale battery storage in India, plus a sourced
dataset of recent tenders (SECI and others), PIB statements, and domestic assembly/cell capacity.

Start with [`docs/TENDER_ANALYSIS.md`](docs/TENDER_ANALYSIS.md).

## Modules (`bess_sim/`)

| Module | Does |
|---|---|
| `cost.py` | Bottom-up capex (DC block, PCS/MV, BoS, grid), opex, augmentation, post-tax NPV; **break-even capacity charge** (₹ lakh/MW/month, the tender metric), supportable capex for a given tariff, DC price implied by a tariff, LCOS in ₹/kWh |
| `sizing.py` | MW/MWh for peak shaving, solar shifting, RE firming |
| `dispatch.py` | Daily LP arbitrage (HiGHS) with RTE; synthetic duck-curve prices and net load |
| `grid.py` | PCS/transformer/land at the point of interconnection, ISTS waiver schedule, GUVNL-style RTE/availability checks |
| `tenders.py` | Loads `data/*.csv`, converts tariffs to ₹/kWh and per-MWh, compares each award to the model |

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python scripts/run_tender_analysis.py
.venv/bin/python scripts/run_sizing_demo.py
```

## Data (`data/`)

`tenders.csv`, `players.csv`, `pib_facts.csv`. Each row carries `source_url` and a `confidence` or
`verification` tag. `data/raw_pib/*.txt` holds extracted text of the three PIB releases read directly.
PIB blocks WebFetch; plain `curl` with a browser User-Agent works.

## Know before trusting any output

- Cost defaults tagged `ASSUMPTION` in `cost.py` (landed uplift, PCS price, BoS, finance terms, opex, augmentation) are placeholders. Replace with vendor quotes.
- Dispatch prices and net load are **synthetic**; the arbitrage revenue shown is illustrative, ignores cycle-wear cost by default, and is not a merchant forecast.
- ISTS waiver schedule for non-co-located plants is my reading of "graded steps of 25%"; confirm against the MoP order.
- Tender figures come mostly from trade press; PIB figures were read from the releases. Confidence is per row.
