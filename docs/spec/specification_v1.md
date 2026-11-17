# Specification v1 — Warehouse + rooftop PV + Renewable Energy Community

> Original implementation brief ("mega-prompt") given by Ema to Claude Code on 17 November 2026,
> stored verbatim so that every development session works from the same approved text.
> Source documents: model v2 (approved 17/11), parameter sheet (approved 17/11), open-data sources,
> decisions log, shiftable activities, literature gap.
> Changes to the model or the parameters must be approved by Ema and recorded in `docs/decisions.md`.

---

## 0. How you must work

You are implementing an open-source research tool that will back a paper for the *Journal of Cleaner Production* (sole author: Emanuele Guerrazzi, "Ema"). Read this whole prompt before writing any code.

1. **Work in phases** (Section 11). At the end of each phase stop, run the tests, and give Ema a short summary in **Italian**: what you built, what passed, what is still open, and the questions you need answered. Do not start the next phase until Ema says ok.
2. **Never invent data.** Every number used by the model comes from the parameter registry (Section 3) with a source and a source type. If a value is missing, leave it `null`, mark it `status: to_be_derived` or `to_be_provided`, and ask Ema. Do not fill it with a "reasonable" guess.
3. **Keep it simple and realistic.** The model is a pure LP (no binaries). Prefer readable code to clever code. No metaheuristics.
4. **Language.** Code, comments, docstrings, README and docs in English. Messages to Ema in Italian.
5. **Do not change the model** in Section 5 on your own. If you find an inconsistency or a bug in the formulation, write it down, propose a fix, and wait for Ema.
6. **Reproducibility first.** Every run records the git commit, the parameter-file hash, the solver name and version, and the provenance summary of the parameters it used.
7. Commit often, with clear messages. Do not push to a remote until Ema gives you the repository URL.
8. **When in doubt, ask Ema for the paper.** If you are unsure about a value, a formula, a unit or how a source should be read, do not guess: ask Ema to send you the paper. Give the full reference (authors, year, title, venue, DOI if known), say what you need from it (for example "Table 3, mean dual-cycle time of the lifts") and why. Ema may or may not be able to provide it. If he does, put the PDF in `docs/papers/` (git-ignored, never committed, because of copyright), read the part you need, and record page, table or equation in the parameter's `source` field. If he cannot, keep the item flagged as `to_verify` or `to_be_provided`, write down what you would have checked, and continue with the rest of the phase. Keep a running list of requested papers and their status in `docs/papers/REQUESTS.md`, and repeat the open requests in every end-of-phase summary.

---

## 1. Context and goal

A warehouse with an automated storage system and a rooftop PV plant can move some of its internal work in time. Moving that work into the sunny hours (about 11:00–15:00) increases the PV it consumes on site, but those are also the hours when orders are picked for the afternoon shipping cut-off, so queues and late shipments grow. The tool measures this trade-off as a **Pareto front between two objectives**:

- **F1 (maximise):** PV energy consumed on site, kWh/year.
- **F2 (minimise):** lost productivity, missions·hour/year = lateness after the shipping cut-off + waiting time in the system queue.

**Decision levers (hourly, one working day):**
- shiftable missions of the automated system: pre-picking of predictable orders (a few hours ahead), replenishment of the picking area, re-slotting;
- charging of the lithium-ion forklift fleet that serves the loading docks (the docks must always be served).

**Renewable Energy Community (REC / CER):** not an objective. It is an *ex-post scenario*: every plan on the front is evaluated without and with REC, using the same hourly flows.

**Plant conditions:** (A) PV already installed — this is the condition inside the model; (B) PV to be installed with investment; (C) no own PV, the warehouse joins a REC with someone else's plant. B and C are a separate economic analysis, not part of the optimisation.

**Method, not a single case.** The tool must be a general method with interchangeable data: a user replaces the parameter file and the input profiles with their own warehouse and gets the same outputs. The **base case** is an SME with a pallet AVS/RS (autonomous vehicle storage and retrieval system) in Torrita di Siena (Tuscany, Italy), inspired by the Cassioli AVS/RS of Guerrazzi et al. (2019), *Sustainability* 11(14) 3817.

**Paper research questions (for context):**
- RQ1. How much energy can the internal logistics activities of an automated warehouse without on-board batteries move within the day, and at what lateness and congestion?
- RQ2. How do on-site PV use and productivity trade off? In which hours and for which activities is the trade-off steepest? (the shadow price of F1 answers "missions·hour of delay per extra kWh of PV used").
- RQ3. How much is REC membership or a PV investment worth for a logistics SME, and how much of that value depends on operational flexibility?

---

## 2. Repository architecture

Suggested name: `warehouse-pv-rec` (ask Ema to confirm). Python ≥ 3.11, managed with `uv` (or conda if Ema prefers; ask in Phase 0).

```
warehouse-pv-rec/
├── README.md
├── LICENSE                     # MIT
├── CITATION.cff
├── pyproject.toml              # deps pinned via uv.lock
├── config/
│   ├── params/base.yaml        # parameter registry, base case (Section 3)
│   ├── params/schema.yaml      # allowed fields and source types
│   ├── scenarios/base.yaml     # scenario manifest for experiments (Section 7)
│   └── slurm/cluster.yaml      # partition, account, time, memory (from Ema)
├── data/
│   ├── raw/                    # downloaded files, NOT committed if the licence forbids it
│   ├── processed/              # hourly profiles, representative days
│   └── SOURCES.md              # one entry per dataset: URL, licence, date downloaded, checksum
├── src/wpvrec/
│   ├── params/                 # registry loader, validation, provenance gate
│   ├── data/                   # downloaders and preprocessing (PV, prices, load shapes, REC members)
│   ├── days.py                 # 12 representative working days + weekend/night accounting
│   ├── queueing.py             # M/M/1 waiting curve and its piecewise-linear cuts
│   ├── model/                  # Pyomo LP: sets, params, variables, constraints V1–V9, objectives
│   ├── pareto.py               # payoff table, AUGMECON ε-constraint, shadow prices, special points
│   ├── policies.py             # P0 current practice, P1 follow-the-sun, P* optimal
│   ├── kpi.py                  # common indicators for every plan
│   ├── rec.py                  # ex-post REC evaluation (shared energy, incentive)
│   ├── economics.py            # conditions B and C
│   ├── experiments/            # scenario expansion, single-scenario runner, aggregation
│   └── cli.py                  # `wpvrec ...` commands
├── slurm/                      # job-array templates and submit scripts
├── dashboard/app.py            # Streamlit app
├── tests/
├── notebooks/                  # only for exploration, never needed to reproduce results
└── docs/                       # model.md (formulation), data.md (provenance), howto.md
```

Core libraries: `pyomo`, `highspy` (HiGHS, open source; the code must also accept `gurobi` or `cplex` via a config switch if installed), `pandas`, `numpy`, `pyarrow`, `pydantic`, `pyyaml`, `pvlib`, `streamlit`, `plotly`, `pytest`, `ruff`. Add GitHub Actions for lint + tests (runs on small instances only).

---

## 3. Data and provenance (Ema's rule — non-negotiable)

**Every number in the code must carry its source and its source type.** This must be visible in the parameter file, in the results metadata, in the dashboard, and in the paper tables generated by the tool.

### 3.1 Source types

| Code | Italian label (used in the paper) | Meaning |
|---|---|---|
| `real` | Reale | measured value, public dataset or official regulation (PVGIS, ELMAS, DM 414/2023, GME) |
| `literature` | Letteratura | value published in a paper, even if obtained by simulation |
| `derived` | Derivato | computed from other registry entries; the formula is written in the entry and computed by code |
| `estimate` | Stima | our value, anchored to sources or orders of magnitude cited in the entry |
| `assumption` | Ipotesi | our value without a direct source; must always have a sensitivity range |
| `design_choice` | Scelta di progetto | study design decision (location, scenarios), not a measurable datum |
| `placeholder_test_only` | — | allowed **only** in `tests/fixtures/`; never in a run that produces results |

### 3.2 Registry entry schema

Each parameter in `config/params/*.yaml`:

```yaml
- id: e_mission_gross
  symbol: "e"
  description: "Gross energy per AVS/RS mission (pallet 100 kg)"
  value: 30
  unit: Wh/mission
  sensitivity: {low: 20, high: 41}      # or a list of discrete values
  source: "Ekren, Akpunar, Lerher (2016), MHI Colloquium: 0.0197–0.0406 kWh per transaction"
  source_type: literature
  status: confirmed                      # confirmed | to_verify | to_be_derived | to_be_provided
  notes: ""
```

Derived entries hold `formula:` (e.g. `e_mission_gross * (1 - regen_share)`) and the loader computes them; a derived value written by hand is an error.

### 3.3 Provenance gate

- The loader validates every entry with `pydantic`: unknown source type, missing source, missing unit or an `assumption` without sensitivity range → error.
- A run that writes into `results/` refuses to start if any parameter it needs has `value: null` or `source_type: placeholder_test_only`. The error message names the parameter and what Ema must provide.
- Entries with `status: to_verify` are allowed, but listed as warnings in `run_meta.json` and in the dashboard.
- **No magic numbers:** add a test that scans `src/wpvrec/model/`, `rec.py`, `economics.py` and fails on numeric literals other than 0, 1, 24, 100 and unit conversions defined in one `units.py`.
- Input time series (PV, prices, load shapes, household profiles) get the same metadata in `data/SOURCES.md` plus a sidecar `*.meta.yaml` next to each processed file (source, licence, retrieval date, processing steps, source type).
- `wpvrec params table --format latex|markdown|csv` exports the registry as the paper's parameter table with the source-type column.

### 3.4 Base-case parameter values

Transcribe **all** rows of Appendix A into `config/params/base.yaml`, keeping value, range, unit, source and type exactly as given. Do not round, do not "fix". If something in Appendix A looks inconsistent, ask.

### 3.5 Open items you must flag (do not guess)

| Item | Status | What to do |
|---|---|---|
| **Hourly capacity of the AVS/RS, C (missions/hour)** | `to_be_derived` | Derived from the cycle times in Guerrazzi et al. 2019 (bottleneck: the 2 lifts): C = n_lifts × 3600 / mean cycle time per lift [s]. Ask Ema for the mean single/dual cycle times, or for the paper itself (rule 8 of Section 0). The base case cannot run without it. Sanity check to report: 1,500 missions in 16 h is ≈ 94 missions/h on average, with inbound + picking peaks above that. |
| Queue curve cuts a_l, b_l | `derived` from C | computed by `queueing.py` (Section 5.4); later cross-checked with the AVS/RS simulator (Phase 8, optional). |
| Forklift consumption 4 kWh/h, battery 25 kWh, charger 8 kW | `to_verify` | estimates to be checked against VDI 2198 datasheets; keep as is, flagged. |
| Retail electricity price paid by the warehouse | **missing in the sheet** | needed only for the economic analysis (B, C) and cost KPIs. Ask Ema for the value and source (e.g. ARERA or Eurostat non-household prices). |
| Discount rate for NPV (condition B) | **missing** | ask Ema; until then report simple payback only. |
| Grid emission factor (for CO₂ avoided, optional KPI) | **missing** | ask Ema; KPI hidden until provided. |
| Household hourly profile | data not downloadable | Besagni et al. 2020 publish average profiles only in figures. Ask Ema whether to digitise them or use another documented profile; the tool must accept any CSV with 24 values per month/day-type. |
| Hourly dock workload profile h_t | **shape not fixed in the sheet** | total is 20 cart-hours/day (4 forklifts × 5 h). Proposed default (assumption, to confirm with Ema in Phase 1): half proportional to inbound arrivals u_t, half uniform over 06–16 (outbound before cut-off), capped at the number of forklifts per hour. |
| PV tilt and azimuth | partially fixed | azimuth south (assumption); tilt not fixed: default PVGIS optimal angle, recorded as `design_choice`, to confirm. |
| Condition C external plant | **missing** | size and profile of the other member's plant; ask Ema before Phase 5. |

---

## 4. Input data pipelines

Write one downloader per source, idempotent, with checksum and a `*.meta.yaml` sidecar. If a source needs registration or manual download, print clear instructions and read the file from `data/raw/`.

1. **PV — PVGIS (JRC).** Use `pvlib.iotools.get_pvgis_hourly` with `pvcalculation=True`, `peakpower` from the registry (80 kWp), `loss` 14%, mounting and angles from the registry. Location Torrita di Siena: about 43.17 N, 11.77 E — verify the coordinates and store the source. Produce:
   - **base "typical year"**: hourly PV per kWp averaged over all available PVGIS years, per month and hour (this is how we implement the approved "PVGIS typical year"; tell Ema in the Phase 2 summary);
   - **control year**: the most recent complete year available, same processing.
   - Sanity check to print: specific yield ≈ 1,200–1,350 kWh/kWp/year (Centre Italy). The sheet's 1,300 kWh/kWp is an `estimate` to be replaced by the PVGIS value.
2. **Zonal prices — GME** (Centre-North zone, last complete year). Hourly €/MWh. Used for the variable part of the REC premium tariff and the revenue of exported energy. GME data may require manual download and may not be redistributable: do not commit raw files unless the licence allows it.
3. **Load shapes — ELMAS** (Scientific Data 2023, CC BY 4.0, figshare DOI 10.6084/m9.figshare.23889780). Tertiary/logistics cluster for the optional hourly shape of the warehouse fixed load; tertiary clusters for the 3 small businesses in the REC. Credit the authors in README.
4. **Households.** 2,700 kWh/year per household (ARERA typical customer, `real`) × hourly shape (see 3.5). 50 households.
5. **Calendar.** 250 working days/year, Monday–Friday excluding Italian public holidays of a stated reference year; the per-month working-day counts are the weights w_d (`derived`).

### 4.1 Representative days (`days.py`)

- The year is represented by **12 typical working days d ∈ D, one per month**, with weight w_d = working days in that month (Σ w_d = 250).
- PV_{d,t} = monthly-mean hourly PV profile of month d (from the typical year).
- Prices and member loads: monthly-mean hourly profile of working days; separately, of weekend days.
- **Weekends and holidays have no decisions:** they are accounted for outside the LP with the stand-by load only (2 kW); all their PV is exported. They count for annual totals and for the REC scenario.
- Night hours of working days are inside the 24-hour LP (decisions are zero there by the shift constraints).

---

## 5. Mathematical model (approved version 2 — implement exactly)

Pure LP, one working day of 24 hours, solved jointly for the 12 representative days (the days are independent except through F1 in the ε-constraint, which is annual). All variables are continuous; missions are rounded only in reporting (report the rounding effect on F1 and F2).

### 5.1 Time convention

t = 1, …, 24 and slot t covers the interval [t−1, t). Work shifts 06:00–22:00 are the slots t = 7, …, 22. The cut-off c = 16 (16:00). A pick done in slot t > c is late by (t − c) hours: a pallet picked 18:00–19:00 (t = 19) counts 3. Write this convention in `docs/model.md` and in docstrings.

### 5.2 Sets

| Symbol | Content | Base case |
|---|---|---|
| T | hours t = 1..24 | shifts 06–22 |
| D | representative working days, weight w_d | 12, one per month, Σ w_d = 250 |
| A | mission types | inbound storage, picking, pre-picking, replenishment, re-slotting |
| Aˢ ⊂ A | shiftable types | pre-picking, replenishment, re-slotting |
| G | order groups g: orders arriving in the same hour, split into a predictable part (share σ) and a non-predictable part | from the arrival profile |
| F | lithium forklifts | 4 |
| L | linear pieces of the congestion curve | 4 |

### 5.3 Parameters

See Appendix A for values and provenance. Symbols used below: N, n_a, e, ϱ, eⁿ = e(1−ϱ), C, ρ̄, a_l, b_l, P^f_t, c, r_g, n_g, σ, H, u_t, B̄, S_0, S^min, κ, |F|, k, h_t, Q, SOC^min, P^ch, η, χ_t, PV_t.

- Order arrivals: half of the 650 daily picks arrive the evening before and are available at 06:00 (release slot t = 7); half arrive uniformly in the slots 08–09 … 12–13. For each arrival group, the predictable share σ = 30% has its release anticipated by H = 4 h, but never before the shift start; the rest is released at arrival. Note for Ema (report it in Phase 3): orders released at 06:00 cannot be anticipated inside the day, so the effective pre-picking volume is smaller than the nominal 30% of 650; report the effective number.
- κ = picks covered by one replenishment = 650/100 = 6.5 (`derived`).
- Inbound arrivals u_t: 650 storage missions uniform over 06–14, to be done within the following hour (fixed, not a decision).

### 5.4 Variables

| Variable | Meaning | Unit |
|---|---|---|
| y_{g,t} ≥ 0 | picks of group g in slot t; if t is before the arrival of g it is pre-picking | missions |
| z_{a,t} ≥ 0 | internal missions of type a ∈ {replenishment, re-slotting} in slot t | missions |
| q_{f,t} ∈ [0,1] | fraction of slot t in which forklift f is charging | – |
| o_{f,t} ∈ [0,1] | fraction of slot t in which forklift f works at the docks | – |
| SOC_{f,t} | battery energy of forklift f at the end of slot t | kWh |
| S_t | stock in the picking area, in picks covered | missions |
| B_t | pallets already picked for orders not yet arrived (buffer) | pallets |
| ℓ_t | total AVS/RS missions in slot t | missions |
| W_t ≥ 0 | waiting time in queue in slot t | missions·h |
| E_t | site energy use | kWh |
| s_t, g_t, x_t ≥ 0 | PV self-consumed, grid import, PV export | kWh |

(Every variable also has the index d; omitted below for readability.)

### 5.5 Constraints

**V1. Each order is picked once, not before its release.**
Σ_t y_{g,t} = n_g; y_{g,t} = 0 if t < r_g or t outside shifts; ∀g. (For predictable groups r_g is already anticipated by H.) Picks after the cut-off are allowed but are lateness in F2.

**V2. All internal missions are done, within shifts.**
Σ_t z_{a,t} = n_a; z_{a,t} = 0 outside shifts; ∀a ∈ {replenishment, re-slotting}.

**V3. The picking area never runs empty.**
S_t = S_{t−1} + κ z_{repl,t} − Σ_g y_{g,t}; S_t ≥ S^min; S_24 = S_0. (S_0 and S^min are given in days of consumption: convert with 650 picks/day.)

**V4. Limited buffer for orders picked in advance.**
B_t = Σ_{g: r_g^{arrival} > t} Σ_{t' ≤ t} y_{g,t'} ≤ B̄, ∀t. (Use the actual arrival hour of g, not the anticipated release.)

**V5. Hourly capacity of the AVS/RS.**
ℓ_t = u_t + Σ_g y_{g,t} + Σ_a z_{a,t} ≤ ρ̄ C, ∀t.

**V6. Congestion (piecewise-linear queue).**
W_t ≥ a_l ℓ_t + b_l, ∀t, l ∈ L; W_t ≥ 0.
`queueing.py` computes a_l, b_l from the M/M/1 queue with utilisation ρ = ℓ/C: waiting time accumulated in one hour = L_q · 1 h = ρ²/(1−ρ) missions·h. Build L = 4 secant (or tangent) cuts on ρ ∈ [0, ρ̄] so the LP lower bound is tight at the breakpoints; expose L and the breakpoints as parameters; plot the curve and the cuts in a test artefact. Mark a_l, b_l as `derived` with the formula.

**V7. Forklifts always cover the docks and never run flat.**
Σ_f o_{f,t} = h_t; o_{f,t} + q_{f,t} ≤ 1; q_{f,t} ≤ χ_t;
SOC_{f,t} = SOC_{f,t−1} + η P^ch q_{f,t} − k o_{f,t}; SOC^min·Q ≤ SOC_{f,t} ≤ Q; SOC_{f,24} = SOC_{f,0}.
Charging therefore never causes dock delays; it moves freely within these limits. Charging allowed only in shift hours (χ_t = 1 in 06–22) in the base case; night charging is a sensitivity.

**V8. Site energy.**
E_t = P^f_t + eⁿ ℓ_t + P^ch Σ_f q_{f,t}, ∀t.
P^f_t = fixed loads: AVS/RS stand-by 3 kW, lighting 4 kW, offices/IT 5 kW, other 2.5 kW during shifts; 2 kW stand-by outside shifts (≈ 225–250 kWh/day; print the exact value). Default shape is flat within shifts; optional ELMAS shape normalised to the same daily energy (switch in the registry).

**V9. PV goes to the site first, the rest to the grid.**
s_t ≤ PV_t; s_t ≤ E_t; g_t = E_t − s_t; x_t = PV_t − s_t, ∀t.
In reporting always recompute s_t = min(PV_t, E_t) (F1 pushes s_t up, but lexicographic or rule-based solves might not).

### 5.6 Objectives

- **F1 (max)** = Σ_d w_d Σ_t s_{d,t} [kWh/year]. Since all work is fixed by V1, V2, V7, total consumption is fixed: maximising F1 means buying less from the grid, not consuming more. Also report self-consumption % (F1 / PV) and self-sufficiency % (F1 / consumption).
- **F2 (min)** = Σ_d w_d [ Σ_g Σ_{t>c} (t − c) y_{d,g,t} + Σ_t W_{d,t} ] [missions·h/year]. Always report the two terms separately, plus the number of pallets shipped after the cut-off. Forklift charging is not in F2 (V7 guarantees the docks).

Why they conflict: sun peaks at 11–15, orders arrive until 13 and must ship by 16; moving internal missions into the sunny hours raises F1 but loads the lifts exactly when picks need them. Charging raises F1 almost for free while forklifts are available.

### 5.7 Pareto front (`pareto.py`)

Augmented ε-constraint (AUGMECON, as in Mariuzzo et al. 2023):

min F2 − ε_aug · S / Δ  s.t.  F1 − S = e_k,  S ≥ 0,  V1–V9.

1. **Payoff table, lexicographic:** min F2 (then max F1 at that F2); max F1 (then min F2 at that F1). This gives the range Δ of F1.
2. **Grid:** K = 25 values e_k evenly spaced in the F1 range (K configurable, 20–30). One LP per point.
3. **Shadow price:** for each point store the dual of the F1 constraint, in missions·h of F2 per extra kWh of F1 — the "delay cost of one kWh". Cross-check against finite differences between adjacent points; warn if they disagree beyond a tolerance.
4. **Special points:** the two extremes, the knee (maximum distance from the line joining the extremes, in normalised objectives), and the point with the same F2 as policy P0 (answers "at equal service, how much more PV?").
5. Check that the stored front is non-dominated and monotone; drop and log duplicates.

### 5.8 Policies (`policies.py`) — same KPIs for all

| Policy | Rule | How to implement |
|---|---|---|
| P0 current practice (assumption) | internal missions in the first and last shift hours (06–08, 20–22), forklift charging at end of shift, no pre-picking | LP with the rule windows as bounds, objective min F2; if the rule is infeasible (capacity or SOC), allow activity outside the windows with a large penalty and report how much spilled |
| P1 follow the sun | shiftable missions and charging in 11–15 as far as capacity allows | lexicographic: max flexible work inside 11–15 subject to V1–V9, then min F2 |
| P* optimal | the special points of the front | from `pareto.py` |

### 5.9 Common KPIs (`kpi.py`)

PV used and self-consumption %; self-sufficiency %; energy imported and exported; lateness and pallets after cut-off; queue time; delay cost per kWh (shadow price); with REC also shared energy, total incentive and warehouse share; with prices also energy cost (only when the retail price is provided).

---

## 6. Scenarios

### 6.1 REC scenario, ex post (`rec.py`)

The REC does not change the decisions; it changes the value of the PV the warehouse does not use.
- **Without REC:** exported energy x_t is sold at the hourly zonal price Pz_t (dedicated withdrawal).
- **With REC:** members = the warehouse (only producer, simple member) + 50 households + 3 small businesses (bar, shop, office, 20 MWh/year each, ELMAS shapes). For each hour, shared energy Sh_t = min(x_t, W^REC_t), where W^REC_t is the hourly consumption of the other members. On weekends all PV is exported and counts.
  - Premium tariff TIP_t = 80 + min(40, max(0, 180 − Pz_t)) + 4 (Centre) €/MWh (DM 414/2023, DM 127/2025).
  - Incentive = Σ_d w_d Σ_t (TIP_t + π^ARERA) Sh_t, plus the weekend contribution. Exported energy is still sold at Pz_t.
  - Enterprise rule: enterprises may receive the incentive on at most θ = 55% of the shared energy; the rest goes to non-enterprise members or social purposes. The warehouse receives β (base 50%, range 0–100%) of the incentive, capped by the θ rule. Implement the cap explicitly and document the interpretation in `docs/model.md`; flag it for Ema's review.
- Alternative member set: "enterprises only" (scenario switch).
- Expected effect to show: more F1 means less export, hence less shared energy. Report the incentive given up per extra kWh used on site.

### 6.2 Economic analysis — conditions B and C (`economics.py`)

- **B, PV to be installed:** investment = cost €/kWp × kWp (base 1,000 €/kWp, range 700–1,200), O&M 12 €/kWp/yr, insurance 3 €/kWp/yr, life 20 years, investment incentive 0% base with 20/30/40% scenarios. Annual flows from the model (F1, export, REC share). Output: simple payback; NPV and IRR only once Ema provides the discount rate and the retail price.
- **C, no own PV, joining someone else's REC:** no optimisation needed; estimate the economic benefit from the warehouse's consumption profile, the external plant (to be provided) and the membership fee (0–100 €/yr). Ask Ema before implementing the inputs.

### 6.3 Optional extensions (only after Ema's ok, Phase 8)

- **S4 cluster:** 2–4 logistics or industrial SMEs with different profiles in the same REC (the multi-site case of Perotti et al. 2027).
- **Validation with the AVS/RS simulator** of Guerrazzi & Vandin (open source, Zenodo DOI 10.5281/zenodo.21822783): replay chosen plans to check queues and delays without the LP simplifications, and calibrate C and the queue curve. The simulator has no energy data; the energy layer comes from this tool.
- Re-slotting effect on picking capacity (removed in v2 because it needed an unsourced parameter).

---

## 7. Experiments and sensitivity

Scenario manifest `config/scenarios/base.yaml`: a base scenario plus overrides. Each scenario = one full Pareto front + policies P0/P1 + REC with/without + KPIs.

**One-at-a-time sensitivity** around the base, using the ranges in Appendix A. At minimum:
missions/day 800–3,000; shiftable share 10–40%; gross energy per mission 20–41 Wh; regeneration 0–35%; AVS/RS base load 1.5–4 kW; ρ̄ 0.8–0.95; forklifts 2–8; forklift consumption 3–5 kWh/h; use 3–8 h/day; battery 20–40 kWh; charger 4–12 kW; SOC min 10–30%; charging efficiency 0.85–0.95; night charging allowed; PV 40–200 kWp; losses 10–18%; east-west orientation; control year instead of typical year; location North / South; cut-off 14:00 / 18:00; predictable share 10–50%; pre-picking lead 2–6 h; buffer 20–80 pallets; minimum stock 0.1–0.5 days; inbound concentrated in the morning; household consumption 2,000–3,500 kWh/yr and profile ±20%; business consumption 10–40 MWh/yr; enterprises-only REC; zonal prices ±30%; ARERA valorisation 6–11 €/MWh; warehouse incentive share 0–100%; economic ranges of condition B.

Also a few **combined scenarios** (to discuss with Ema in Phase 6), e.g. high-flexibility summer case, low-PV case, SBS/RS tote variant (0.7 Wh/mission).

The SBS/RS variant uses the same model with different parameters: this demonstrates the "general method with interchangeable data".

**Outputs per scenario** in `results/<scenario_id>/`: `front.parquet` (one row per point: F1, F2 split, shadow price, KPIs), `plans.parquet` (hourly decisions per point, day, activity), `policies.parquet`, `rec.parquet`, `kpis.json`, `run_meta.json` (git commit, param hash, solver + version, wall time, provenance summary with every parameter's source type, warnings for `to_verify`). `wpvrec aggregate` merges all scenarios into `results/summary.parquet` and produces the paper figures and tables (PDF + PNG, vector where possible) in `results/figures/`.

---

## 8. SLURM (Ema's server)

- Ask Ema in Phase 6 for: partition, account, max wall time, cores and memory per node, module system or container policy, scratch path. Store them in `config/slurm/cluster.yaml`; never hard-code.
- `wpvrec experiments expand config/scenarios/base.yaml` → `results/manifest.csv` (one line per scenario, stable id = hash of overrides).
- `slurm/run_array.sbatch`: job array over the manifest; each task runs `wpvrec run --scenario-id $ID`; threads for HiGHS from `SLURM_CPUS_PER_TASK`; logs to `results/logs/`.
- Tasks are idempotent: skip if `run_meta.json` exists with the same param hash; `--force` to rerun.
- `slurm/submit.sh` submits the array and a dependent aggregation job (`--dependency=afterok`).
- `wpvrec run-local --max-workers N` runs the same manifest without SLURM (for laptops and CI).
- Estimate and print the expected runtime from a pilot of 3 scenarios before submitting the full array.

---

## 9. Dashboard (`dashboard/app.py`, Streamlit + Plotly)

Purpose: let Ema, reviewers and practitioners see the effect of policies easily. It reads `results/` and can also re-solve one scenario live (the LP is small).

Pages:
1. **Pareto front:** F1 vs F2 per scenario, P0 and P1 overlaid, special points marked; hover shows KPIs; clicking a point opens its plan.
2. **Hourly plan:** for a chosen point and month: PV curve, stacked load (fixed, missions by type, charging), import/export, queue time, picks after cut-off, forklift SOC.
3. **Policy comparison:** KPI table and bars for P0, P1, P* (extremes, knee, same-F2-as-P0).
4. **REC:** with/without, shared energy, incentive, warehouse share, incentive given up per kWh self-consumed.
5. **Sensitivity:** tornado charts of F1 range, knee position and shadow price; parameter sweep plots.
6. **Economics:** condition B payback (and NPV when available), condition C.
7. **Parameters and provenance:** the full registry with filters by source type and status, colour badge per type; every chart shows a footnote with the source types it depends on.
8. **What-if:** edit a few parameters (missions/day, PV size, cut-off, forklifts) and recompute one front live; edited values are marked as user overrides, never saved into the registry.

Accessible colours (colour-blind safe), works in light and dark mode, export of every chart as PNG/SVG and of every table as CSV.

---

## 10. Tests and verification

- **Registry:** schema validation, provenance gate, derived formulas, no-magic-numbers test.
- **Tiny instances with known solutions** (fixtures with `placeholder_test_only` values): e.g. 4 hours, 1 forklift, PV only in hour 2 — check the LP moves charging to hour 2; capacity-binding case where moving a mission creates exactly the expected waiting time.
- **Balances:** for every solved plan, energy balance closes per hour (E = s + g, PV = s + x) within 1e-6; all missions done; SOC within bounds; stock ≥ minimum; buffer ≤ B̄.
- **Front properties:** monotone, non-dominated, extremes equal to payoff table; shadow price sign and magnitude consistent with finite differences.
- **Policies:** P0 and P1 lie on or inside the front (never dominate it).
- **REC:** Sh_t ≤ x_t and Sh_t ≤ W^REC_t; weekend accounting; θ cap respected.
- **Regression:** once C is provided, a base-case snapshot test with tolerances.
- CI runs only fixtures; full base case runs on Ema's server.

---

## 11. Phases (stop after each one and report to Ema in Italian)

| Phase | Deliverable | Done when |
|---|---|---|
| 0 | Repo skeleton, environment, licence, CI, `docs/` stubs | `pytest` and `ruff` green on an empty test |
| 1 | Parameter registry from Appendix A, schema, loader, provenance gate, LaTeX/CSV table export | all rows present with source and type; gate blocks missing C with a clear message; questions of Section 3.5 sent to Ema |
| 2 | Data pipelines (PVGIS, GME, ELMAS, households, calendar) and representative days | profiles plotted, sanity checks printed, `SOURCES.md` and sidecars complete |
| 3 | LP model V1–V9, single-objective solves (min F2, max F1), balances | tiny-instance tests pass; base case solves once C is given; effective pre-picking volume reported |
| 4 | Pareto front, shadow prices, special points, policies P0/P1, KPIs | front tests pass; first base-case figures for Ema |
| 5 | REC ex post and economics B/C | REC tests pass; open economic inputs listed |
| 6 | Scenario manifest, local runner, SLURM array, aggregation, paper figures | pilot run on the server, runtime estimate, full array submitted only after Ema's ok |
| 7 | Dashboard | all pages working on the base-case results |
| 8 | README, docs, reproducibility guide, CITATION, optional extensions on request | a new user can reproduce the paper figures from a clean clone with the documented commands |

---

## 12. Licence, README and reproducibility

- Code under **MIT**. Third-party data keep their own licences (ELMAS CC BY 4.0 with attribution; PVGIS and GME per their terms): list them in README and `data/SOURCES.md`; do not commit data that cannot be redistributed, provide the download script instead.
- README: purpose, the two objectives in plain words, quick start (install, download data, run base case, open dashboard), how to plug in your own warehouse (replace the parameter file and profiles), the provenance rule and source types, how to run on SLURM, how to cite, licence.
- `docs/model.md`: the full formulation of Section 5 in LaTeX, with the time convention and the REC/θ interpretation; `docs/data.md`: provenance tables generated from the registry.
- Pin dependencies (`uv.lock`), record solver versions, fix random seeds if any randomness is ever introduced. A `make paper-figures` (or `wpvrec paper`) target regenerates every figure and table used in the paper.

---

## Appendix A — Base-case parameter registry (approved by Ema, 17/11/2026)

Source types in Italian as in the paper: Reale = `real`, Letteratura = `literature`, Derivato = `derived`, Stima = `estimate`, Ipotesi = `assumption`, Scelta di progetto = `design_choice`.

### A.1 Warehouse

| Parameter | Base | Sensitivity | Unit | Source | Type |
|---|---|---|---|---|---|
| System type | pallet AVS/RS, 2,730 locations, 5 levels, 2 lifts, 6 shuttles with satellite | SBS/RS for totes | – | Guerrazzi et al. 2019 (Cassioli) | literature |
| Installed AVS/RS power | 44.6 | – | kW | Guerrazzi et al. 2019 | literature |
| Location | Torrita di Siena (SI) | North, South | – | Ema's decision 17/11 | design_choice |
| Shifts | 2 shifts, 06–22, Mon–Fri, 250 working days/yr | 1 shift; 3 shifts | – | 15–16 active hours in Guerrazzi et al. 2019 | estimate |
| Missions per day N | 1,500 | 800–3,000 | missions/day | Guerrazzi et al. 2019 (≈1,200), raised by Ema's decision 17/11 | estimate |
| Mission split n_a | 650 inbound, 650 picks (30% predictable), 100 replenishment, 100 re-slotting; nominal shiftable 395 (26%) | – | missions/day | from the 25% shiftable share; confirmed by Ema 17/11 | assumption |
| Shiftable share | 25% | 10–40% | % | shiftable-activities document | assumption |
| Pallet mass | 100 | – | kg | Ekren, Akpunar, Lerher 2016 | literature |
| Gross energy per mission e | 30 | 20–41 | Wh/mission | Ekren, Akpunar, Lerher 2016 (0.0197–0.0406 kWh) | literature |
| Regenerative braking ϱ | 28 | 0–35 | % of consumed energy | Guerrazzi et al. 2019 (28.3%) | literature |
| Net energy per mission eⁿ | 21.6 = 30 × (1 − 0.28) | 14–41 | Wh/mission | formula; confirmed by Ema 17/11 (missions ≈ 32 kWh/day) | derived |
| Energy per mission, SBS/RS tote variant | 0.7 | 0.65–0.71 | Wh/mission | Lerher, Ekren, Akpunar | literature |
| AVS/RS base (stand-by) load | 3 | 1.5–4 | kW | Ertl & Günthner 2016 (0.5–1.25 kW per machine) | estimate |
| Hourly capacity C | **to be derived** | – | missions/h | cycle times of Guerrazzi et al. 2019 (bottleneck: 2 lifts) | literature (to_be_derived) |
| Maximum utilisation ρ̄ | 0.9 | 0.8–0.95 | – | common practice for queueing systems | assumption |
| Queue curve a_l, b_l | M/M/1 cuts from mean cycle time | – | missions·h | standard queueing formula, later checked with the AVS/RS simulator | derived |
| Lithium forklifts \|F\| | 4 | 2–8 | forklifts | – | assumption |
| Forklift consumption k | 4 | 3–5 | kWh per hour of use | order of magnitude for 2–2.5 t trucks, to verify on VDI 2198 sheets | estimate (to_verify) |
| Forklift use | 5 | 3–8 | h/day per forklift (total h_t = 20 cart-h/day) | – | assumption |
| Battery capacity Q | 25 | 20–40 | kWh | datasheets of 2–2.5 t lithium forklifts, to verify | estimate (to_verify) |
| Charger power P^ch | 8 | 4–12 | kW | datasheets, to verify | estimate (to_verify) |
| Minimum SOC | 20 | 10–30 | % | – | assumption |
| Charging efficiency η | 0.92 | 0.85–0.95 | – | – | estimate |
| Charging hours χ_t | shifts 06–22 | also at night | – | "within shifts", confirmed by Ema 17/11 | design_choice |
| Fixed loads P^f_t | stand-by AVS/RS 3 kW, lighting 4 kW, offices/IT/HVAC 5 kW, other (doors, conveyors, wrappers, compressor) 2.5 kW in shifts; 2 kW stand-by outside shifts and on weekends | see rows | kW | lighting: estimate checked with Perotti & Dobers split; offices and other: assumption; stand-by: assumption | estimate / assumption |
| Hourly shape of fixed load | flat in shifts (default); ELMAS tertiary/logistics shape (option) | – | hourly profile | ELMAS (Scientific Data 2023), French data adapted | real (shape) |
| Site consumption split (check only) | 29% lighting, 14% handling, 57% other | ambient: lighting + handling > 60% | % | Perotti & Dobers, Polimi green warehousing benchmark | real |
| Annual site consumption | ≈ 100 (sum of the balance) | 70–150 | MWh/yr | sum of the base-case balance | derived |

Base-case daily balance (for checks): AVS/RS missions ≈ 32 kWh net (45 gross); AVS/RS base 48; forklift charging 80; lighting 60; offices/IT 80; other 40 kWh per working day; nights and weekends stand-by ≈ 9 MWh/yr. Shiftable ≈ 90 kWh/day.

### A.2 Photovoltaics

| Parameter | Base | Sensitivity | Unit | Source | Type |
|---|---|---|---|---|---|
| Hourly profile | PVGIS typical year (multi-year average, see 4) | a recent real year | kWh/kWp per hour | PVGIS (JRC) | real |
| Installed power | 80 | 40–200 | kWp | 100 MWh/yr ÷ 1,300 kWh/kWp, rounded (Ema's decision 17/11) | derived |
| Specific yield (check) | ≈ 1,300 | 1,000–1,550 (North–South) | kWh/kWp/yr | solareindustriale.it 2026; replaced by the PVGIS value | estimate |
| System losses | 14 | 10–18 | % | PVGIS default | estimate |
| Orientation | south, roof pitch | east-west | – | – | assumption |
| Tilt | PVGIS optimal (to confirm) | – | ° | – | design_choice |

### A.3 Orders and service

| Parameter | Base | Sensitivity | Unit | Source | Type |
|---|---|---|---|---|---|
| Shipping cut-off c | 16:00 | 14:00, 18:00 | h | Ema's decision 17/11 | assumption |
| Order arrival profile r_t | synthetic: half the evening before (available 06:00), half uniform 08–13 | more or less predictable | % per hour | no open dataset found | assumption |
| Predictable share σ | 30 | 10–50 | % | – | assumption |
| Maximum pre-picking lead H | 4 | 2–6 | h | Ema's decision ("a few hours") | design_choice |
| Inbound arrivals u_t | uniform 06–14 | concentrated in the morning | % per hour | – | assumption |
| Pre-picked buffer B̄ | 40 | 20–80 | pallets | – | assumption |
| Picking-area stock S_0, S^min | initial 1, minimum 0.3 | minimum 0.1–0.5 | days of consumption | – | assumption |
| Picks per replenishment κ | 6.5 = 650/100 | – | picks | formula | derived |

### A.4 Renewable energy community

| Parameter | Base | Sensitivity | Unit | Source | Type |
|---|---|---|---|---|---|
| Members | warehouse + 50 households + 3 tertiary businesses | enterprises only | – | Ema's decision 17/11 | design_choice |
| Household profile | Italian average profiles | ±20% | kWh per hour | Besagni et al. 2020 (67 measured households) | literature |
| Business profile | ELMAS profiles | other ELMAS clusters | kWh per hour | ELMAS 2023 | real |
| Household annual consumption | 2,700 | 2,000–3,500 | kWh/yr | ARERA typical domestic customer (2,700 kWh/yr, 3 kW) | real |
| Business annual consumption | 20 | 10–40 | MWh/yr each | – | assumption |
| Other members' load W^REC_t | ≈ 195 | – | MWh/yr | sum of the rows above | derived |

### A.5 Incentives and prices

| Parameter | Base | Sensitivity | Unit | Source | Type |
|---|---|---|---|---|---|
| Premium tariff, fixed part | 80 | – | €/MWh | DM 414/2023 and DM 127/2025 | real |
| Premium tariff, variable part | max(0, 180 − Pz), at most 40 | – | €/MWh | same | real |
| Centre-region bonus | 4 | 0 (South), 10 (North) | €/MWh | same | real |
| Incentivised share for enterprises θ | 55% of shared energy | – | % | same | real |
| Energy price Pz_t | hourly zonal prices Centre-North, last complete year | ±30% | €/MWh | GME | real |
| ARERA valorisation fee π^ARERA | 8 | 6–11 | €/MWh | rule: TRASe component in low voltage, updated by ARERA (TIAD); "about 8 €/MWh" in literature (PoliTo thesis). The exact monthly value may be read from ARERA tables | estimate |
| Warehouse share of incentive β | 50 | 0–100 | % | REC by-laws, not known | assumption |

### A.6 Investment costs (conditions B and C)

| Parameter | Base | Sensitivity | Unit | Source | Type |
|---|---|---|---|---|---|
| Turnkey PV cost, 100–250 kW | 1,000 | 700–1,200 | €/kWp | between IEA PVPS Italy 2023 (1,100–1,350, typical 1,180) and 2026 commercial prices (675–750) | estimate |
| O&M | 12 | 8–15 | €/kWp/yr | solareindustriale.it 2026 (commercial) | estimate |
| Insurance | 3 | 2–4 | €/kWp/yr | same | estimate |
| Useful life | 20 | 20–25 | years | equal to the REC incentive duration (DM 414/2023) | design_choice |
| Investment incentive | 0 | 20, 30, 40 | % of cost | hypothetical future scheme (PNRR excluded), Ema's decision 17/11 | assumption |
| REC membership fee (condition C) | 0 | 0–100 | €/yr | – | assumption |
| Retail electricity price | **to be provided** | – | €/MWh | – | – |
| Discount rate | **to be provided** | – | % | – | – |

---

## Appendix B — Key references (for docstrings and docs)

- Guerrazzi E. et al. (2019). Energy assessment of an AVS/RS (Cassioli). *Sustainability* 11(14), 3817.
- Guerrazzi E., Vandin A. (2027). Reliable and explainable analysis of AVS/RS by SMC and process mining. *Expert Systems with Applications* 335, 135055; simulator on Zenodo, DOI 10.5281/zenodo.21822783.
- Ekren B.Y., Akpunar A., Lerher T. (2016). Energy per transaction in AVS/RS. MHI International Colloquium on Material Handling Research.
- Ertl R., Günthner W. (2016). Energy meta-model for stacker cranes. *Logistics Journal*.
- Fresia M. et al. (2024). Optimal operation of an industrial microgrid within a REC. *Energies* 17(14), 3567.
- Mariuzzo I., Fioriti D., Guerrazzi E. et al. (2023). Multi-objective planning method for RECs (A-AUGMECON2). *IJEPES* 153, 109331.
- Perotti S., Cannava L., Bodria, Indio (2027). From Green Warehouses to Sustainable Logistics Ecosystems. IFIP AICT 812.
- ELMAS dataset (2023). *Scientific Data*; figshare DOI 10.6084/m9.figshare.23889780.
- Besagni G., Premoli Vilà L., Borgarello M. (2020). Italian household load profiles. *Buildings* 10(12), 217.
- DM 414/2023 and DM 127/2025 (Italian REC incentives); ARERA TIAD; GME zonal prices; PVGIS (JRC).
