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
| 2026-11-18 | Arrival profiles parametric (Ema): inbound and same-day orders have a shape parameter (uniform base; truncated normal variant, mu = 12.5 h, sigma = 2 h for orders from Guerrazzi & Vandin 2026; morning peak 8 h for inbound). Beta shape can be added in Phase 2 if needed. | 1 |
| 2026-11-18 | Assumptions without a range in the sheet: +/-25% on magnitudes, +/-1 h on clock times (Ema: ok if parametrisable). P0/P1 windows stored as scalar start/end hours. | 1 |
| 2026-11-18 | Economic inputs (Ema: search ARERA/Eurostat): retail price = Eurostat nrg_pc_205 IT band 20-499 MWh excl. VAT, 2025 mean = 248.7 EUR/MWh; discount rate = ARERA WACC 2025-2027 electricity distribution 5.6% real (proxy, to_verify); CO2 factor = ISPRA 413/2025 Table 1.3, consumption 2023 = 234.7 g/kWh. | 1 |
| 2026-11-18 | Condition C external plant (Ema: hypothesise): 80 kWp, same site and PVGIS profile as condition A; range 40-200 kWp. | 1 |
| 2026-11-18 | PV tilt = PVGIS optimal (confirmed); PV size 80 kWp as design_choice (confirmed); household profile = Besagni et al. 2020, digitised in Phase 2 (confirmed). | 1 |
| 2026-11-18 | SBS/RS energy per mission source completed: Lerher, Ekren, Akpunar (2016), 14th IMHRC, Table 2 p. 10. | 1 |
| 2026-11-18 | Sensitivity range of the gross energy per mission from Akpunar, Ekren, Lerher (2017) Table 2 (20.0-37.1 Wh), replacing the unverified 0.0197-0.0406 kWh of the sheet. N = 1,500 anchored also to Lupi et al. (2024) (1,529 missions/day). C unchanged (Lupi fixed times give 289/h, within range). | 1 |
