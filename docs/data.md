# Data and provenance

Every number used by the model comes from the parameter registry (`config/params/base.yaml`) with a
source and a source type (specification Section 3). Source types, as labelled in the paper:

| Code | Paper label | Meaning |
|---|---|---|
| `real` | Reale | measured value, public dataset or official regulation |
| `literature` | Letteratura | value published in a paper, even if obtained by simulation |
| `derived` | Derivato | computed by code from other entries with the stated formula |
| `estimate` | Stima | our value, anchored to cited sources or orders of magnitude |
| `assumption` | Ipotesi | our value without a direct source; always with a sensitivity range |
| `design_choice` | Scelta di progetto | study design decision |

## Base-case parameter table

Generated from the registry, never edited by hand:
[params_base.md](params_base.md) (`wpvrec params table --format markdown -o docs/params_base.md`).
The same table for the paper: `wpvrec params table --format latex` (needs `\usepackage{longtable}`).

## Commands

- `wpvrec params validate` — validate the registry, show which run kinds are blocked and the warnings.
- `wpvrec params gate model|rec|economics|data` — exit 1 with the list of missing entries.
- `wpvrec params show <id>` — one entry with its computed value.

## Input time series

Documented from Phase 2 in [../data/SOURCES.md](../data/SOURCES.md), with a `*.meta.yaml` sidecar next to
each processed file.
