"""M/M/1 waiting curve and its piecewise-linear secant cuts (constraint V6).

With hourly load l [missions/h] and capacity C [missions/h], utilisation rho = l / C and
the mean number of missions waiting is L_q = rho^2 / (1 - rho). Over one hour this
accumulates L_q x 1 h of waiting, in missions*h.

The LP uses W_t >= a_k l_t + b_k for the secants between consecutive breakpoints
rho_0 = 0 < ... < rho_L = rho_max. For a convex curve the maximum of the secants is the
piecewise-linear interpolation: exact at the breakpoints, slightly above the curve between
them, so minimising W_t gives the interpolated waiting time.
"""

from __future__ import annotations

import numpy as np


def waiting(load, capacity):
    """M/M/1 waiting time accumulated in one hour [missions*h] for hourly load [missions/h]."""
    rho = np.asarray(load, dtype=float) / capacity
    if np.any(rho >= 1):
        raise ValueError("utilisation must stay below 1")
    return rho**2 / (1 - rho)


def cuts(capacity: float, rho_max: float, breakpoints: list[float]) -> list[tuple[float, float]]:
    """Secant lines (a, b) in W >= a*l + b, l in missions/h; breakpoints as fractions of rho_max."""
    bp = np.asarray(breakpoints, dtype=float)
    if bp[0] != 0 or bp[-1] != 1 or np.any(np.diff(bp) <= 0):
        raise ValueError("breakpoints must increase from 0 to 1 (fractions of rho_max)")
    loads = bp * rho_max * capacity
    w = waiting(loads, capacity)
    slopes = np.diff(w) / np.diff(loads)
    return [
        (float(a), float(w0 - a * l0)) for a, w0, l0 in zip(slopes, w[:-1], loads[:-1], strict=True)
    ]


def piecewise(load, cut_list) -> np.ndarray:
    """Waiting time given by the cuts: max_k (a_k l + b_k), floored at 0."""
    lv = np.asarray(load, dtype=float)
    return np.maximum(0, np.max([a * lv + b for a, b in cut_list], axis=0))
