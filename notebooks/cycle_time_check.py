"""Exploration: cycle times of the Cassioli deep-lane AVS/RS from Guerrazzi et al. (2019).

Not part of the model. Recomputes, from the input data published in the paper
(Appendix A, Tables A1-A3) and its travel-time model (eq. 1-2), the mean cycle
times of the shuttle/satellite part and of the lifts, and compares them with the
throughput implied by Table 2 (total energy / hourly energy = run duration).

Assumptions of this check (to be confirmed by Ema, not used by the model):
- channel, tier and cell drawn uniformly at random;
- the shuttle starts each mission where it ended the previous one on its tier;
- tier k (k = 1..5) sits at height (k - 1) * H or k * H (both reported);
- the lift needs one fixed transfer time t_f at the tier (3.s / 9.p), floor
  handling time not modelled (not reported in the paper).

Run: uv run python notebooks/cycle_time_check.py
"""

import numpy as np

rng = np.random.default_rng(0)
N = 200_000

# Table A1 (geometry)
NZ, NX, NY = 5, 21, 13
H, LX, LY = 1.65, 30.0, 27.0
W, D = LX / NX, (LY / 2) / NY
# Table A2 (kinematics): (v, a) per axis, j = 0 empty, 1 loaded
KIN = {
    ("x", 1): (2.0, 0.4),
    ("x", 0): (3.0, 0.8),
    ("y", 1): (0.67, 0.4),
    ("y", 0): (1.33, 0.8),
    ("z", 1): (1.33, 1.0),
    ("z", 0): (1.33, 1.0),
}
TF = 2.0  # Table A3: all fixed times are 2 s


def travel(d, axis, j):
    """Eq. (1): trapezoidal / triangular velocity profile."""
    v, a = KIN[(axis, j)]
    d = np.abs(d)
    return np.where(d < v**2 / a, 2 * np.sqrt(d / a), 2 * v / a + (d - v**2 / a) / v)


chan = rng.integers(1, NX + 1, N)
prev = rng.integers(1, NX + 1, N)
cell = rng.integers(1, NY + 1, N)
x_ch, x_prev = (chan - 0.5) * W, (prev - 0.5) * W
y_cell = (cell - 0.5) * D

# Storage, S_t = (2.s, 3.s, 5.s, 6.s, 7.s, 8.s, 9.s, 10.s); inbound lift at x = 0
ct_s = (
    travel(x_prev, "x", 0)  # 2.s shuttle to inbound lift, empty
    + travel(x_ch, "x", 1)  # 5.s shuttle to channel, loaded
    + travel(y_cell, "y", 1)  # 7.s satellite to cell, loaded
    + travel(y_cell, "y", 0)  # 9.s satellite back, empty
    + 4 * TF  # 3.s, 6.s, 8.s, 10.s
)
# Picking, P_t = (1.p .. 7.p, 9.p); outbound lift at x = LX
ct_p = (
    travel(x_ch - x_prev, "x", 0)  # 1.p shuttle to channel, empty
    + travel(y_cell, "y", 0)  # 3.p satellite to cell, empty
    + travel(y_cell, "y", 1)  # 5.p satellite back, loaded
    + travel(LX - x_ch, "x", 1)  # 7.p shuttle to outbound lift, loaded
    + 4 * TF  # 2.p, 4.p, 6.p, 9.p
)
print(
    f"Shuttle+satellite cycle (paper's CT, lift excluded): storage {ct_s.mean():.1f} s, "
    f"picking {ct_p.mean():.1f} s, mean {np.r_[ct_s, ct_p].mean():.1f} s"
)

for label, offset in (("tier k at (k-1)*H", 0), ("tier k at k*H", 1)):
    z = (rng.integers(1, NZ + 1, N) - 1 + offset) * H
    lift_s = travel(z, "z", 1) + TF + travel(z, "z", 0)  # up loaded, transfer, down empty
    lift_p = travel(z, "z", 0) + TF + travel(z, "z", 1)  # up empty, transfer, down loaded
    print(
        f"Lift cycle ({label}): storage {lift_s.mean():.1f} s, picking {lift_p.mean():.1f} s "
        f"-> {3600 / lift_s.mean():.0f} missions/h per dedicated lift"
    )

# Table 2: total energy 88,268 kJ, hourly energy 5,772 kJ/h; 600 + 600 ULs (Table A6)
hours = 88_268 / 5_772
print(
    f"Table 2 run duration {hours:.2f} h for 1,200 missions -> {1200 / hours:.1f} missions/h, "
    f"{hours * 3600 / 1200:.1f} s per mission (sequential, single command)"
)
print(
    f"Table 2 energy per UL: 75 kJ = {75 / 3.6:.1f} Wh gross, "
    f"net of recovery {(75 - 21) / 3.6:.1f} Wh"
)
