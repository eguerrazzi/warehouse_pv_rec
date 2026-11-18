"""Payoff table, AUGMECON epsilon-constraint front, shadow prices, special points.

Specification Section 5.7 (augmented epsilon-constraint, Mavrotas 2009, as in Mariuzzo et
al. 2023):

    min F2 - eps_aug * S / Delta   s.t.   F1 - S = e_k,  S >= 0,  V0-V9

1. payoff table by lexicographic solves (min F2 then max F1; max F1 then min F2), which
   gives the range Delta of F1;
2. K targets e_k evenly spaced over that range, one LP each;
3. shadow price of each point = dual of the F1 constraint, in missions*h of F2 per extra kWh
   of F1 (the "delay cost of one kWh"), checked against the finite differences of the front:
   F2 as a function of F1 is convex and piecewise linear, so the dual must lie between the
   slopes of the two adjacent segments;
4. special points: the extremes, the knee (largest distance from the line joining the
   extremes, objectives normalised to [0, 1]) and the point with the same F2 as policy P0;
5. duplicates and dominated points are dropped and logged; the front must be monotone.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pyomo.environ as pyo

from wpvrec.model import solve

log = logging.getLogger(__name__)


@dataclass
class Front:
    payoff: dict[str, solve.SolveResult]
    points: pd.DataFrame  # one row per kept point, sorted by F1
    dropped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def delta(self) -> float:
        return self.payoff["max_F1"].F1 - self.payoff["min_F2"].F1


def payoff(m, rel_tol: float, solver: str = "highs", threads: int | None = 1) -> dict:
    """The two lexicographic extremes of the front."""
    return {
        "min_F2": solve.lexicographic(m, "min_F2", rel_tol, solver, threads),
        "max_F1": solve.lexicographic(m, "max_F1", rel_tol, solver, threads),
    }


def _ensure_aug(m) -> None:
    if not hasattr(m, "aug_S"):
        m.aug_S = pyo.Var(domain=pyo.NonNegativeReals)
    if not hasattr(m, "dual"):
        m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)


def augmecon_point(m, target, delta, eps, solver="highs", threads=1):
    """Solve one AUGMECON point; returns (result, slack S, shadow price dF2/de)."""
    _ensure_aug(m)
    solve.optimise(
        m,
        m.F2 - eps * m.aug_S / delta,
        "min",
        [(m.F1 - m.aug_S, "==", target)],
        solver,
        threads,
    )
    dual = float(m.dual[m.extra[1]])
    return solve.result(m), pyo.value(m.aug_S), dual


def equal_service_point(m, f2_cap, rel_tol, solver="highs", threads=1):
    """Most PV at a service no worse than ``f2_cap`` (then the best service at that PV)."""
    solve.optimise(m, m.F1, "max", [(m.F2, "<=", f2_cap)], solver, threads)
    f1 = solve.tighten(pyo.value(m.F1), rel_tol, "max")
    solve.optimise(m, m.F2, "min", [(m.F2, "<=", f2_cap), (m.F1, ">=", f1)], solver, threads)
    return solve.result(m)


def equal_pv_point(m, f1, rel_tol, solver="highs", threads=1):
    """Best service with at least ``f1`` of PV: the exact front at that F1."""
    floor = solve.tighten(f1, rel_tol, "max")
    solve.optimise(m, m.F2, "min", [(m.F1, ">=", floor)], solver, threads)
    return solve.result(m)


def _clean(df: pd.DataFrame, tol: float) -> tuple[pd.DataFrame, list[str]]:
    """Drop duplicates and dominated points (F1 larger is better, F2 smaller is better)."""
    df = df.sort_values(["F1", "F2"], ascending=[True, True]).reset_index(drop=True)
    keep, dropped = [], []
    for i, r in df.iterrows():
        dup = any(
            abs(r.F1 - df.F1[j]) <= tol * (abs(r.F1) + 1)
            and abs(r.F2 - df.F2[j]) <= tol * (abs(r.F2) + 1)
            for j in keep
        )
        dominated = any(
            df.F1[j] >= r.F1 - tol * (abs(r.F1) + 1) and df.F2[j] <= r.F2 - tol * (abs(r.F2) + 1)
            for j in df.index
            if j != i
        )
        if dup or dominated:
            why = "duplicate" if dup else "dominated"
            dropped.append(f"k={int(r.k)} F1={r.F1:.3f} F2={r.F2:.3f} ({why})")
        else:
            keep.append(i)
    return df.loc[keep].reset_index(drop=True), dropped


def _slopes(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    f1, f2 = df.F1.to_numpy(), df.F2.to_numpy()
    seg = np.diff(f2) / np.diff(f1) if len(df) > 1 else np.array([])
    left = np.concatenate([[np.nan], seg])
    right = np.concatenate([seg, [np.nan]])
    return left, right


def front(
    m,
    K: int,
    rel_tol: float,
    eps: float,
    sp_tol: float,
    solver: str = "highs",
    threads: int | None = 1,
    collect=None,
) -> Front:
    """Build the front; ``collect(m, shadow_price)`` may add indicators to each point."""
    pay = payoff(m, rel_tol, solver, threads)
    lo, hi = pay["min_F2"].F1, pay["max_F1"].F1
    delta = hi - lo
    if delta <= rel_tol * (abs(hi) + 1):  # no trade-off: the front is a single point
        r = solve.lexicographic(m, "min_F2", rel_tol, solver, threads)
        row = {"k": 0, "target": lo, "F1": r.F1, "F2": r.F2, "F2_late": r.F2_late,
               "F2_queue": r.F2_queue, "slack": 0.0, "shadow_price": 0.0}  # fmt: skip
        if collect is not None:
            row |= collect(m, 0.0)
        pts = pd.DataFrame([row])
        return Front(pay, pts, warnings=["no trade-off: min F2 and max F1 coincide"])
    targets = np.linspace(lo, hi, K)
    targets[-1] = solve.tighten(hi, rel_tol, "max")  # keep the last target feasible
    rows = []
    for k, e in enumerate(targets):
        r, slack, dual = augmecon_point(m, e, delta, eps, solver, threads)
        row = {"k": k, "target": e, "F1": r.F1, "F2": r.F2, "F2_late": r.F2_late,
               "F2_queue": r.F2_queue, "slack": slack, "shadow_price": dual}  # fmt: skip
        if collect is not None:
            row |= collect(m, dual)
        rows.append(row)
    pts, dropped = _clean(pd.DataFrame(rows), rel_tol)
    for d in dropped:
        log.info("front: dropped %s", d)
    warnings = []
    left, right = _slopes(pts)
    pts["fd_left"], pts["fd_right"] = left, right
    slack_abs = eps / delta + rel_tol  # the augmentation term shifts the dual by up to eps/Delta
    ok = []
    for lam, a, b in zip(pts.shadow_price, left, right, strict=True):
        lo_b = np.nanmin([a, b]) if not (np.isnan(a) and np.isnan(b)) else lam
        hi_b = np.nanmax([a, b]) if not (np.isnan(a) and np.isnan(b)) else lam
        if np.isnan(a):  # first point: dual between 0 and the right slope
            lo_b = 0.0
        if np.isnan(b):  # last point: dual at least the left slope
            hi_b = np.inf
        ok.append(lo_b * (1 - sp_tol) - slack_abs <= lam <= hi_b * (1 + sp_tol) + slack_abs)
    pts["shadow_ok"] = ok
    if not all(ok):
        bad = pts.loc[~pts.shadow_ok, "k"].tolist()
        warnings.append(f"shadow price outside the finite-difference bracket at k={bad}")
    if (np.diff(pts.F2) < -rel_tol * (pts.F2.abs().max() + 1)).any():
        warnings.append("front not monotone: F2 decreases while F1 increases")
    for w in warnings:
        log.warning("front: %s", w)
    return Front(pay, pts, dropped, warnings)


def knee(points: pd.DataFrame) -> int:
    """Index of the knee: largest distance from the line joining the extremes (normalised)."""
    f1, f2 = points.F1.to_numpy(), points.F2.to_numpy()
    if len(points) < 3:
        return 0
    n1 = (f1 - f1[0]) / (f1[-1] - f1[0])
    n2 = (f2 - f2[0]) / (f2[-1] - f2[0]) if f2[-1] > f2[0] else np.zeros_like(f2)
    return int(np.argmax(n1 - n2))  # below the line: more PV for less service lost


def f2_on_front(points: pd.DataFrame, f1: float) -> float:
    """F2 of the front at ``f1`` (linear between points); +inf beyond the PV extreme."""
    if f1 > points.F1.iloc[-1]:
        return np.inf
    return float(np.interp(f1, points.F1, points.F2))


def is_on_or_inside(points: pd.DataFrame, f1: float, f2: float, rel_tol: float) -> bool:
    """A plan never dominates the front: its F2 is not below the front at the same F1."""
    ref = f2_on_front(points, f1 - rel_tol * (abs(f1) + 1))
    return f2 >= ref - rel_tol * (abs(ref) + 1) if np.isfinite(ref) else False
