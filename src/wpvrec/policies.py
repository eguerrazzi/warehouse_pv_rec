"""Reference policies: P0 current practice, P1 follow-the-sun, P* optimal.

Specification Section 5.8; all policies are solved on the same LP (V0-V9) and evaluated
with the same KPIs (``kpi.py``).

- **P0 current practice** (assumption): internal missions only in the first and last shift
  hours (shift start to ``p0_morning_end``, ``p0_evening_start`` to shift end), forklift
  charging only in the evening window, no pre-picking. If the rule is infeasible, activity
  may spill outside the windows. Instead of a large penalty (a number without a source),
  the spill is minimised first, lexicographically, weighted by the distance in hours from
  the nearest window (so spilled work stays as close as possible to the rule): first the
  internal missions, then the charging energy, then F2. The spill is reported.
- **P1 follow the sun**: first maximise the flexible energy placed inside the sunny window
  (``p1_sun_start``-``p1_sun_end``): internal missions and picks of predictable orders
  (e^n per mission) and forklift charging (P^ch per hour); then minimise F2 keeping it.
- **P\\***: the special points of the Pareto front (``pareto.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pyomo.environ as pyo

from wpvrec import balances
from wpvrec.model import lp, solve
from wpvrec.model.inputs import ModelInputs
from wpvrec.params import Registry


@dataclass
class PolicyResult:
    """``result.F1`` is recomputed with s = min(PV, E) (the last stage minimises F2 only)."""

    name: str
    model: object
    result: solve.SolveResult
    spill: dict = field(default_factory=dict)


def _result(m, inp: ModelInputs) -> solve.SolveResult:
    r = solve.result(m)
    r.F1 = balances.f1_recomputed(m, inp)
    return r


def slots(start_h: float, end_h: float) -> set[int]:
    """Slots t covering the clock interval [start_h, end_h) (slot t = [t-1, t))."""
    return set(range(int(start_h) + 1, int(end_h) + 1))


def distance(window: set[int], T: int) -> np.ndarray:
    """Hours from each slot 1..T to the nearest slot of ``window`` (0 inside)."""
    w = np.array(sorted(window))
    return np.array([np.abs(w - t).min() for t in range(1, T + 1)], dtype=float)


def p0(reg: Registry, inp: ModelInputs, solver="highs", threads=1) -> PolicyResult:
    v = reg.value
    start, end = v("shift_start"), v("shift_end")
    internal = slots(start, v("p0_morning_end")) | slots(v("p0_evening_start"), end)
    charging = slots(v("p0_evening_start"), end)
    return p0_plan(inp, internal, charging, v("lexicographic_tolerance"), solver, threads)


def p0_plan(inp: ModelInputs, internal: set[int], charging: set[int], tol: float,
            solver="highs", threads=1) -> PolicyResult:  # fmt: skip
    """P0 with explicit windows (slots) for internal missions and charging."""
    d_int, d_ch = distance(internal, inp.T), distance(charging, inp.T)
    m = lp.build_model(inp)
    for d, g, t in m.YI:  # no pre-picking: nothing picked before its order arrives
        if t < inp.groups[g].arrival:
            m.y[d, g, t].fix(0)
    w = inp.weights
    spill_int = sum(w[d] * d_int[t - 1] * m.z[d, a, t] for d in m.D for a in m.A for t in m.T)
    spill_ch = sum(
        w[d] * d_ch[t - 1] * inp.p_ch * m.q[d, f, t] for d in m.D for f in m.F for t in m.T
    )
    solve.optimise(m, spill_int, "min", (), solver, threads)
    b1 = solve.tighten(pyo.value(spill_int), tol, "min")
    solve.optimise(m, spill_ch, "min", [(spill_int, "<=", b1)], solver, threads)
    b2 = solve.tighten(pyo.value(spill_ch), tol, "min")
    solve.optimise(m, m.F2, "min", [(spill_int, "<=", b1), (spill_ch, "<=", b2)], solver, threads)
    out_int = sum(
        w[d] * pyo.value(m.z[d, a, t]) for d in m.D for a in m.A for t in m.T if t not in internal
    )
    out_ch = sum(
        w[d] * inp.p_ch * pyo.value(m.q[d, f, t])
        for d in m.D
        for f in m.F
        for t in m.T
        if t not in charging
    )
    spill = {
        "internal_missions_outside_per_yr": out_int,
        "charging_kwh_outside_per_yr": out_ch,
        "internal_missions_per_yr": float(w.sum() * (inp.n_repl + inp.n_reslot)),
        "charging_kwh_per_yr": sum(
            w[d] * inp.p_ch * pyo.value(m.q[d, f, t]) for d in m.D for f in m.F for t in m.T
        ),
    }
    return PolicyResult("P0", m, _result(m, inp), spill)


def sunny_energy(m, inp: ModelInputs, window: set[int]):
    """Flexible energy placed inside ``window`` [kWh/yr] (expression): internal missions and
    picks of predictable orders (e^n each) and forklift charging (P^ch per hour)."""
    pred = [g for g, grp in enumerate(inp.groups) if grp.predictable]

    def missions(d, t):
        return sum(m.z[d, a, t] for a in m.A) + sum(m.y[d, g, t] for g in pred if (d, g, t) in m.YI)

    return sum(
        inp.weights[d]
        * (inp.e_net_kwh * missions(d, t) + inp.p_ch * sum(m.q[d, f, t] for f in m.F))
        for d in m.D
        for t in window
    )


def p1(reg: Registry, inp: ModelInputs, solver="highs", threads=1) -> PolicyResult:
    v = reg.value
    window = slots(v("p1_sun_start"), v("p1_sun_end"))
    return p1_plan(inp, window, v("lexicographic_tolerance"), solver, threads)


def p1_plan(inp: ModelInputs, window: set[int], tol: float, solver="highs", threads=1):
    """P1 with an explicit sunny window (slots)."""
    m = lp.build_model(inp)
    flex = sunny_energy(m, inp, window)
    solve.optimise(m, flex, "max", (), solver, threads)
    b = solve.tighten(pyo.value(flex), tol, "max")
    solve.optimise(m, m.F2, "min", [(flex, ">=", b)], solver, threads)
    spill = {"flexible_kwh_in_window_per_yr": pyo.value(flex)}
    return PolicyResult("P1", m, _result(m, inp), spill)
