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
$\ell_t$ AVS/RS missions; $W_t \ge 0$ waiting; $E_t$ site energy; $s_t, g_t, x_t \ge 0$ PV self-consumed,
grid import, PV export.

## Constraints

**V1** $\sum_t y_{g,t} = n_g$, with $y_{g,t} = 0$ for $t < r_g$ or $t \notin \mathcal{T}^{s}$ (implemented by
creating $y_{g,t}$ only on the allowed slots).

**V2** $\sum_t z_{a,t} = n_a$, $z_{a,t} = 0$ for $t \notin \mathcal{T}^{s}$.

**V3** $S_t = S_{t-1} + \kappa\, z_{repl,t} - \sum_g y_{g,t}$, $S_t \ge S^{min}$, $S_0 = S_{24} = S^{0}$.

**V4** $B_t = \sum_{g: a_g > t} \sum_{t' \le t} y_{g,t'} \le \bar B$ (actual arrival slot $a_g$).

**V5** $\ell_t = u_t + \sum_g y_{g,t} + \sum_a z_{a,t} \le \bar\rho\, C$.

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

- **Inbound** $u_t$: storage missions done in the slot of arrival (the spec's "within the following hour" is
  read as "in the same hourly slot"); fixed input.
- **Dock workload** $h_t$: `dock_share_inbound` (50%) proportional to $u_t$, the rest uniform over 06–16;
  the build fails if $h_t > |F|$ in some hour.
- **Fixed loads** $P^f_t$: flat in shifts (14.5 kW) and 2 kW outside, 248 kWh per working day; option ELMAS
  cluster shape with the same daily energy.
- **Non-working days** (outside the LP, spec Sect. 4.1): stand-by 2 kW, all PV exported. *For review:* if the
  stand-by load used PV in daylight, self-consumption on non-working days would be about 2.6 MWh/yr (of 30.4 MWh
  produced on those days); the spec's rule is kept until Ema decides.
- **Rounding**: missions are continuous; `balances.rounding_effect` recomputes F1 and F2 with integer missions per
  slot (base case: F1 +9 kWh/yr, F2 +14 missions·h/yr at min F2).

## REC evaluation (Phase 5)

To be documented with the interpretation of the enterprise cap $\theta$.
