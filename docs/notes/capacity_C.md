# Hourly capacity C of the AVS/RS — reading of Guerrazzi et al. (2019)

Status: **open, decision needed from Ema** (2026-11-18). Nothing here is used by the model yet.

Source: Guerrazzi E., Mininno V., Aloini D., Dulmin R., Scarpelli C., Sabatini M. (2019).
Energy Evaluation of Deep-Lane Autonomous Vehicle Storage and Retrieval System.
*Sustainability* 11(14), 3817. doi:10.3390/su11143817 (CC BY 4.0).

## What the paper reports

- **No numerical cycle times** are reported. Section 4.3 (p. 6–7) defines the cycle time with eq. (2),
  and the sets S_t, P_t **exclude the lift** (activities 1.s, 4.s, 8.p, 10.p) "because a lift is often a
  bottleneck and is not always sold together with the other components".
- The 2 lifts are **dedicated**: one inbound (storage), one outbound (retrieval) (Section 4.1, p. 5).
- Simulation is **single command with no concurrent use of the shuttles** (end of Section 4.2, p. 6).
- Scenario: 600 storages + 600 retrievals (Table A6, p. 13); "each run covers 15/16 h" (Section 5.1, p. 9).
- Table 2 (p. 9): total energy 88,268 kJ, hourly energy 5,772 kJ/h → run length 15.29 h.

## What can be derived

Script: `notebooks/cycle_time_check.py` (eq. 1–2 with Tables A1–A3; uniform random channel, tier, cell).

| Quantity | Value | How |
|---|---|---|
| Mean time per mission in the simulation | 45.9 s | Table 2: 15.29 h × 3600 / 1,200 missions |
| Same, recomputed from eq. (2) | 46.2 s (storage 47.2, picking 45.3) | Tables A1–A3, Monte Carlo |
| Throughput of the simulated system | 78.5 missions/h | 1,200 / 15.29 h |
| Lift cycle (up, transfer, down) | 9.1–12.1 s → 300–400 missions/h per lift | eq. (1), Table A2; tier height convention unknown |
| Shuttle+satellite with 5 tiers in parallel | ≈ 5 × 3600 / 46.2 ≈ 390 missions/h | not simulated in the paper |

The agreement 45.9 s vs 46.2 s confirms that the paper's run is sequential: throughput is set by the
shuttle + satellite cycle, **not by the lifts**.

## Consequences for the specification

1. The formula of spec Section 3.5, C = n_lifts × 3600 / lift cycle time, does not match the paper:
   the lifts are dedicated (storage vs retrieval) and are not the bottleneck with the published data.
2. With C = 78.5 missions/h (sequential, as simulated) the base case is infeasible: ρ̄C = 70.6 /h, while
   inbound alone is 650 / 8 h = 81.3 /h, and 1,500 missions need ≥ 94 /h over 16 h.
3. With concurrent tier shuttles (C ≈ 390 /h) the average utilisation is ≈ 0.24 and the M/M/1 queue term
   in F2 becomes very small; also, parallel shuttles are closer to M/M/c than M/M/1.

## Other differences with the registry (to review, not changed)

| Item | Registry (spec App. A) | Paper | Where |
|---|---|---|---|
| Pallet mass | 100 kg (Ekren et al. 2016) | 1,200 kg (M_UL) | Table A5, p. 13 |
| Gross energy per mission | 30 Wh (Ekren et al. 2016) | 75 kJ/UL = 20.8 Wh | Table 2, p. 9 |
| Net energy per mission | 21.6 Wh | (75 − 21) kJ = 15.0 Wh | Tables 2–3, p. 9–10 |
| Shuttles | 6 | 1 per tier, 5 tiers (p. 5); installed power counts 6 shuttles (p. 9) | Sections 4.1, 5.1 |

Confirmed by the paper: 2,730 locations, 5 tiers, 2 lifts (p. 9, Table A1); installed power 44.6 kW
(p. 9); recovery 28.3% (p. 11); 15–16 active hours (p. 9); ≈ 1,200 missions/day (Table A6).
