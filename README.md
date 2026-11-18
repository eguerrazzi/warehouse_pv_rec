# warehouse_pv_rec

Open-source research tool (Python package `wpvrec`) that measures, for an automated warehouse with a
rooftop PV plant, the trade-off between:

- **F1 — PV used on site** (kWh/year, to maximise), and
- **F2 — lost productivity** (missions·hour/year, to minimise: lateness after the shipping cut-off +
  waiting time in the storage system's queue),

when internal work (pre-picking, replenishment, re-slotting) and forklift charging are moved into the
sunny hours. The result is a Pareto front from a pure linear program. Every plan is then evaluated
ex post without and with membership of a Renewable Energy Community (REC / CER).

The base case is an SME with a pallet AVS/RS in Torrita di Siena (Tuscany), inspired by
Guerrazzi et al. (2019), *Sustainability* 11(14) 3817. The method is general: replace the parameter
file and the input profiles to study another warehouse.

> **Status:** Phase 0 (skeleton). The approved specification is in
> [docs/spec/specification_v1.md](docs/spec/specification_v1.md).

## Quick start

With conda (Python from conda, packages at the exact versions of `uv.lock`):

```bash
conda env create -f environment.yml
conda activate wpvrec
pytest                  # tests
wpvrec info             # package and solver versions
```

With uv (used by CI; `uv.lock` is the reference lock file):

```bash
uv sync && uv run pytest && uv run wpvrec info
```

Dashboard (later phases): `uv sync --extra dashboard && uv run streamlit run dashboard/app.py`.

## Provenance rule

Every number used by the model comes from the parameter registry (`config/params/`) with a source and
a source type: `real`, `literature`, `derived`, `estimate`, `assumption`, `design_choice`. Runs refuse
to start if a needed value is missing. See specification Section 3.

## Data licences

Third-party data keep their own licences and are downloaded by scripts, not committed when
redistribution is not allowed. See [data/SOURCES.md](data/SOURCES.md). ELMAS load shapes: CC BY 4.0,
figshare DOI 10.6084/m9.figshare.23889780 (credit to the ELMAS authors, *Scientific Data* 2023).

## Licence and citation

Code: MIT ([LICENSE](LICENSE)). How to cite: [CITATION.cff](CITATION.cff).
