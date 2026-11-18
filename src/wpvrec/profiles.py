"""Parametric hourly shapes for arrivals and workloads within a daily window.

A shape distributes a daily quantity over the slots t = 1..24 (slot t covers the clock
interval [t-1, t)) that fall inside a window [start, end) given in clock hours. Shapes:

- ``uniform``: equal share in every slot of the window;
- ``truncated_normal``: normal density with mean ``peak`` and standard deviation ``spread``
  (hours), truncated to the window and integrated slot by slot;
- ``beta``: beta(a, b) density rescaled to the window, integrated slot by slot.

The result sums to 1 over the window and is 0 outside it (Ema 18/11/2026: arrivals must be
parametric for the sensitivity analysis).
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from wpvrec.units import HOURS_PER_DAY

SLOTS = np.arange(1, HOURS_PER_DAY + 1)


def shape(
    kind: str,
    start: float,
    end: float,
    peak: float | None = None,
    spread: float | None = None,
    a: float | None = None,
    b: float | None = None,
) -> np.ndarray:
    """Hourly shares (length 24, index 0 = slot 1) of a quantity spread over [start, end)."""
    if not 0 <= start < end <= HOURS_PER_DAY:
        raise ValueError(f"invalid window [{start}, {end})")
    lo = np.clip(SLOTS - 1, start, end)  # slot t covers [t-1, t), clipped to the window
    hi = np.clip(SLOTS, start, end)
    if kind == "uniform":
        w = hi - lo
    elif kind == "truncated_normal":
        if peak is None or spread is None or spread <= 0:
            raise ValueError("truncated_normal needs peak and a positive spread")
        dist = stats.norm(loc=peak, scale=spread)
        w = dist.cdf(hi) - dist.cdf(lo)
    elif kind == "beta":
        if a is None or b is None or a <= 0 or b <= 0:
            raise ValueError("beta needs positive a and b")
        dist = stats.beta(a, b, loc=start, scale=end - start)
        w = dist.cdf(hi) - dist.cdf(lo)
    else:
        raise ValueError(f"unknown shape {kind!r}")
    total = w.sum()
    if total <= 0:
        raise ValueError(f"shape {kind!r} has no mass inside [{start}, {end})")
    return w / total


def distribute(total: float, shares: np.ndarray) -> np.ndarray:
    """Hourly quantities from a daily total and hourly shares (continuous, not rounded)."""
    return total * np.asarray(shares)
