# Decisions log

Decisions taken with Ema during development that change or clarify the specification.

| Date | Decision | Phase |
|---|---|---|
| 2026-11-17 | Repository name `warehouse_pv_rec` (existing GitHub remote); Python package `wpvrec`. | 0 |
| 2026-11-18 | Environment: conda env `wpvrec` for daily use (`environment.yml`), packages pinned from `uv.lock` via `requirements.lock.txt`; `uv.lock` stays the reference (CI). | 0 |
| 2026-11-18 | CITATION: affiliation Scuola Superiore Sant'Anna, ORCID 0000-0002-6545-2089. Push to `eguerrazzi/warehouse_pv_rec` only when Ema says so. | 0 |
| 2026-11-18 | Energy per mission and pallet mass from Guerrazzi et al. 2019 instead of Ekren et al. 2016 (Ema: prefer the more recent source): e = 75 kJ = 20.83 Wh gross (Table 2), regeneration 28.3% (p. 11), net 14.94 Wh; pallet 1,200 kg (Table A5). Ekren range kept as sensitivity. | 1 |
| 2026-11-18 | Capacity C (delegated by Ema): C = n_active_shuttles × 3600 / mission time, mission time 45.9 s from Guerrazzi et al. 2019 Table 2 (sequential run), 5 tier shuttles in parallel → 392 missions/h; sensitivity n_active_shuttles 1–5. Replaces spec 3.5 formula (lifts dedicated, not the bottleneck). Details: docs/notes/capacity_C.md. Status to_verify. | 1 |
| 2026-11-18 | Prototype rule (Ema): values may be hypotheses as long as each has its source; better data will replace them later and the scripts will be re-run. | 1 |
| 2026-11-18 | Registry conventions: PV size 80 kWp recorded as design_choice (rounded choice, not computed); check-only values (consumption split, daily balance, specific yield) kept in a separate `checks` section; assumptions without a range in the sheet carry `sensitivity: {to_be_defined: ...}` and are listed as warnings. | 1 |
