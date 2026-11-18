"""Single-objective and lexicographic solves of the LP (Phase 3).

``solve(model, "min_F2")`` or ``solve(model, "max_F1")``; ``bound`` adds F1 >= value or
F2 <= value, which gives the lexicographic payoff solves used in Phase 4.
"""

from __future__ import annotations

from dataclasses import dataclass

import pyomo.environ as pyo

from wpvrec.solver import get_solver


@dataclass
class SolveResult:
    status: str
    F1: float
    F2: float
    F2_late: float
    F2_queue: float


def _clear(m):
    for name in ("obj", "bound_c"):
        if hasattr(m, name):
            m.del_component(name)


def solve(m, objective: str, bound: tuple[str, float] | None = None, solver: str = "highs"):
    """Optimise F1 or F2; ``bound`` = ("F1_min", v) or ("F2_max", v) adds that constraint."""
    _clear(m)
    if objective == "min_F2":
        m.obj = pyo.Objective(expr=m.F2, sense=pyo.minimize)
    elif objective == "max_F1":
        m.obj = pyo.Objective(expr=m.F1, sense=pyo.maximize)
    else:
        raise ValueError(f"unknown objective {objective!r}")
    if bound is not None:
        kind, value = bound
        if kind == "F1_min":
            m.bound_c = pyo.Constraint(expr=value <= m.F1)
        elif kind == "F2_max":
            m.bound_c = pyo.Constraint(expr=value >= m.F2)
        else:
            raise ValueError(f"unknown bound {kind!r}")
    res = get_solver(solver).solve(m)
    status = str(res.solver.termination_condition)
    if status != "optimal":
        raise RuntimeError(f"solver status {status} for {objective}")
    return SolveResult(
        status=status,
        F1=pyo.value(m.F1),
        F2=pyo.value(m.F2),
        F2_late=pyo.value(m.F2_late),
        F2_queue=pyo.value(m.F2_queue),
    )


def lexicographic(m, first: str, rel_tol: float, solver: str = "highs"):
    """Optimise ``first`` objective, then the other one keeping the first at its optimum."""
    r1 = solve(m, first, solver=solver)
    if first == "min_F2":
        cap = r1.F2 * (1 + rel_tol) + rel_tol
        return solve(m, "max_F1", ("F2_max", cap), solver=solver)
    floor = r1.F1 * (1 - rel_tol) - rel_tol
    return solve(m, "min_F2", ("F1_min", floor), solver=solver)
