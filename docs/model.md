# Model formulation

Approved model v2 (specification Section 5), as implemented in `src/wpvrec/model/` (Phase 3).
Source text: [spec/specification_v1.md](spec/specification_v1.md). Pure LP, all variables continuous.

## Time convention

Slot $t = 1,\dots,24$ covers the local clock interval $[t-1, t)$ (Europe/Rome). Work shifts 06:00–22:00 are
the slots $\mathcal{T}^{s} = \{7,\dots,22\}$. With the shipping cut-off $c = 16$, a pick in slot $t > c$ is late
by $t - c$ hours (a pallet picked 18:00–19:00, $t = 19$, counts 3). PVGIS and ELMAS timestamps (UTC) are
converted to local time; GME `Ora` is already local.

## Sets

| Symbol | Content | Base case |
|---|---|---|
| $\mathcal{T}$ | slots $1..24$; $\mathcal{T}^{s}$ shift slots | 7..22 |
| $\mathcal{D}$ | representative working days, weight $w_d$ | 12 months, $\sum_d w_d = 251$ (calendar 2025) |
| $\mathcal{G}$ | order groups $g$: arrival slot $a_g$, release slot $r_g$, size $n_g$ | 12 groups |
| $\mathcal{A}$ | internal missions | replenishment, re-slotting |
| $\mathcal{F}$ | forklifts | 4 |
| $\mathcal{L}$ | secant cuts of the queue curve | 4 |

Order groups: a share of the picks arrives the evening before and is available at shift start ($a_g = 7$); the
rest arrives with a parametric profile over $[8, 13)$ (uniform: slots 9–13). Each arrival group is split into a
predictable part (share $\sigma$) with $r_g = \max(a_g - H, 7)$ and a non-predictable part with $r_g = a_g$.

## Variables (index $d$ omitted)

$y_{g,t} \ge 0$ picks; $z_{a,t} \ge 0$ internal missions; $q_{f,t}, o_{f,t} \in [0,1]$ charging and dock
fractions of the hour; $SOC_{f,t}$ battery energy; $S_t$ picking-area stock; $B_t$ pre-picked buffer;
$\ell_t$ AVS/RS missions; $v_{\tau,t} \ge 0$ inbound pallets arrived in slot $\tau$ and stored in slot $t$; $W_t \ge 0$ waiting; $E_t$ site energy; $s_t, g_t, x_t \ge 0$ PV self-consumed,
grid import, PV export.

## Constraints

**V0** $\sum_{t=\tau}^{\tau+\Delta} v_{\tau,t} = u_\tau$ for every arrival slot $\tau$, with $t$ within shifts (the arrival slot
is always allowed); $\Delta$ = `inbound_storage_delay` (1: "within the following hour", Ema 18/11/2026; 0 gives
the first Phase 3 build). $U_t = \sum_\tau v_{\tau,t}$.

**V1** $\sum_t y_{g,t} = n_g$, with $y_{g,t} = 0$ for $t < r_g$ or $t \notin \mathcal{T}^{s}$ (implemented by
creating $y_{g,t}$ only on the allowed slots).

**V2** $\sum_t z_{a,t} = n_a$, $z_{a,t} = 0$ for $t \notin \mathcal{T}^{s}$.

**V3** $S_t = S_{t-1} + \kappa\, z_{repl,t} - \sum_g y_{g,t}$, $S_t \ge S^{min}$, $S_0 = S_{24} = S^{0}$.

**V4** $B_t = \sum_{g: a_g > t} \sum_{t' \le t} y_{g,t'} \le \bar B$ (actual arrival slot $a_g$).

**V5** $\ell_t = U_t + \sum_g y_{g,t} + \sum_a z_{a,t} \le \bar\rho\, C$.

**V6** $W_t \ge a_l \ell_t + b_l\ \ \forall l$, $W_t \ge 0$. With $\rho = \ell/C$, the M/M/1 waiting accumulated
in one hour is $L_q = \rho^2/(1-\rho)$ missions·h. The cuts are the secants between breakpoints
$\rho_k = \beta_k \bar\rho$, $\beta = (0, 0.5, 0.75, 0.9, 1)$; their maximum is the piecewise-linear interpolation,
exact at the breakpoints and slightly above the curve between them ([figures/queue_cuts.png](figures/queue_cuts.png)).

**V7** $\sum_f o_{f,t} = h_t$; $o_{f,t} + q_{f,t} \le 1$; $q_{f,t} \le \chi_t$;
$SOC_{f,t} = SOC_{f,t-1} + \eta P^{ch} q_{f,t} - k\, o_{f,t}$; $SOC^{min} Q \le SOC_{f,t} \le Q$;
$SOC_{f,24} = SOC_{f,0}$.

**V8** $E_t = P^{f}_t + e^{n} \ell_t + P^{ch} \sum_f q_{f,t}$.

**V9** $s_t \le PV_t$, $s_t \le E_t$, $g_t = E_t - s_t$, $x_t = PV_t - s_t$. Reports recompute
$s_t = \min(PV_t, E_t)$.

## Objectives

$$F_1 = \sum_d w_d \sum_t s_{d,t} \quad [\text{kWh/yr}],\qquad
F_2 = \sum_d w_d \Big[\sum_g \sum_{t > c} (t - c)\, y_{d,g,t} + \sum_t W_{d,t}\Big] \quad [\text{missions·h/yr}].$$

Lexicographic solves (`wpvrec solve`): optimise one objective, then the other with the first fixed at its
optimum within a relative tolerance (registry `lexicographic_tolerance`).

## Implementation notes and points for review

- **Inbound** $u_t$: pallets arriving in slot $t$ (fixed input); their storage $U_t$ is decided by V0, in the
  arrival slot or the next one. The dock workload $h_t$ follows the arrivals $u_t$ (unloading), not the storage.
- **Dock workload** $h_t$: `dock_share_inbound` (50%) proportional to $u_t$, the rest uniform over 06–16;
  the build fails if $h_t > |F|$ in some hour.
- **Fixed loads** $P^f_t$: flat in shifts (14.5 kW) and 2 kW outside, 248 kWh per working day; option ELMAS
  cluster shape with the same daily energy.
- **Non-working days** (outside the LP, spec Sect. 4.1, changed by Ema 18/11/2026): stand-by 2 kW, which uses the
  PV when there is sun, $\sum_t \min(PV_t, P^{sb})$: 2.6 MWh/yr of the 30.4 MWh produced on those days; the rest
  is exported. It is a constant: it enters the annual totals, not $F_1$ (which keeps the working days only).
- **Rounding**: missions are continuous; `balances.rounding_effect` recomputes F1 and F2 with integer missions per
  slot (base case: F1 +4 kWh/yr, F2 +11 missions·h/yr at min F2).

## Pareto front, policies and KPIs (Phase 4)

`wpvrec front` (code: `pareto.py`, `policies.py`, `kpi.py`, `study.py`).

**AUGMECON** (Mavrotas 2009, as in Mariuzzo et al. 2023): $\min F_2 - \varepsilon_{aug} S/\Delta$ s.t.
$F_1 - S = e_k$, $S \ge 0$, V0–V9, with $\Delta$ the F1 range of the lexicographic payoff table and $K$ =
`pareto_points` targets evenly spaced (the last one tightened by the lexicographic tolerance). The augmentation
also pushes $s_t$ up to $\min(PV_t, E_t)$, so the LP value of $F_1$ is the true one (checked on every point).

**Shadow price** of a point = dual of $F_1 - S = e_k$ = missions·h of $F_2$ per extra kWh of $F_1$. $F_2$ as a
function of the target is convex and piecewise linear (LP value function), so the dual must lie between the
slopes of the two adjacent segments; checked with relative tolerance `shadow_price_tolerance` plus
$\varepsilon_{aug}/\Delta$. Duplicates and dominated points are dropped and logged.

**Special points**: the extremes; the knee = maximum of $\tilde F_1 - \tilde F_2$ (objectives normalised to
[0, 1] between the extremes, i.e. the largest distance below the line joining them); the point with the same
$F_2$ as P0 ($\max F_1$ s.t. $F_2 \le F_2^{P0}$, then $\min F_2$).

**P0 current practice** (assumption): internal missions only in slots of [shift start, `p0_morning_end`) and
[`p0_evening_start`, shift end), charging only in the evening window, no pre-picking ($y_{g,t}=0$ for $t<a_g$).
When the rule is infeasible, work spills outside the windows. Instead of an arbitrary large penalty, three
lexicographic stages: (1) min $\sum w_d\,\delta_t z$; (2) min $\sum w_d\,\delta_t P^{ch} q$; (3) min $F_2$, where
$\delta_t$ is the distance in hours from the nearest allowed slot (spilled work stays as close as possible to the
rule). Spill is reported (missions/yr and kWh/yr outside the windows).

**P1 follow the sun**: (1) max flexible energy inside [`p1_sun_start`, `p1_sun_end`): $e^n$ × (internal
missions + picks of predictable orders) + $P^{ch}$ × charging hours; (2) min $F_2$ keeping it.

**Policies vs front**: for each policy an exact solve $\min F_2$ s.t. $F_1 \ge F_1^{P}$ gives the front at the
same $F_1$; the policy must not be below it. Linear interpolation between front points is not used for this
check, because chords lie above a convex front.

**F1 of a plan**: when the last stage only minimises $F_2$ (policies), the LP variable $s_t$ is not pushed to
$\min(PV_t, E_t)$; every reported F1 is therefore recomputed with $s_t = \min(PV_t, E_t)$ (spec V9).

**KPIs** (same for all plans): F1, F2 (lateness, queue), pallets after cut-off, pre-picks, PV, PV used,
self-consumption and self-sufficiency (annual, with non-working days), import, export, delay cost per kWh
(front points), energy cost = import × `retail_price`.

**Solver threads**: `solver_threads` (1). HiGHS otherwise starts one thread per two cores.

## REC evaluation (Phase 5)

Ex post, on every plan (code: `rec.py`, KPIs with prefix `rec_`). The warehouse is the only producer.

- Export $x_t = \max(PV_t - E_t, 0)$ on working days (from the plan) and $PV_t - \min(PV_t, P^{sb})$ on
  non-working days; other members' load $W_t$ = households (bottom-up profile, × 50) + 3 businesses (ELMAS), by
  month and day type; `rec_member_set = enterprises only` keeps the businesses only.
- Shared energy $Sh_t = \min(x_t, W_t)$; premium tariff $TIP_t = 80 + \min(40, \max(0, 180 - P^z_t)) + 4$ €/MWh;
  incentive $= \sum (TIP_t + \pi^{ARERA}) Sh_t$; export always sold at $P^z_t$ (both with and without REC).
- **Enterprise cap (interpretation, for Ema's review).** DM 414/2023 (as summarised by Assolombarda and
  Unioncamere): the premium on the shared energy above 55% (45% with a capital grant) goes only to members other
  than enterprises or to social purposes. Reference energy = energy fed in by the REC plant (`theta_basis =
  export`, default) or the shared energy (`shared`, literal spec text). Annual totals. The warehouse receives
  $\beta$ of the incentive but no more premium than the enterprise-eligible premium; the other enterprise members
  are assumed to receive no premium; the ARERA valorisation is not capped. Base case: not binding.
- **Incentive given up per extra kWh used on site** = $-\Delta$incentive$/\Delta F_1$ between adjacent front
  points (`rec_incentive_lost_eur_per_kwh`).

## Economics (Phase 5)

Code: `economics.py`, tables `economics_b.csv`, `economics_c.csv` written by `wpvrec front`. Constant 2025 prices,
real discount rate, no PV degradation (not in the registry).

- **B, own PV**: $I = c^{PV}\,kWp\,(1-\text{incentive})$; annual flow = PV used (working + non-working days) ×
  retail price + export × $P^z$ + warehouse REC share (with REC) − (O&M + insurance) × kWp; simple payback, NPV over
  the life, IRR (closed form: root of the annuity polynomial). Investment incentive 0% and 20/30/40%.
- **C, member of an external REC**: external plant of `ext_plant_kwp`, same profile, all fed in;
  $Sh_t = \min(X^{ext}_t, W^{wh}_t + W_t)$; the REC returns `c_consumer_share` of the incentive to consumers, pro rata
  to their hourly contribution; the warehouse premium is capped as above; benefit = share − fee. Evaluated for
  the load of P0, P1 and the optimum with P0's service.
