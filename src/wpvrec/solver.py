"""Solver selection and version reporting.

HiGHS (via ``highspy``) is the default open-source solver. Gurobi or CPLEX can be
selected by name if installed; the choice comes from configuration, never from
code. Every run records the solver name and version (specification Section 0.6).
"""

from __future__ import annotations

import pyomo.environ as pyo

# Pyomo plugin names for the supported solvers.
_PYOMO_NAMES = {
    "highs": "appsi_highs",
    "gurobi": "gurobi_direct",
    "cplex": "cplex_direct",
}


def get_solver(name: str = "highs"):
    """Return a Pyomo solver object for ``name`` ("highs", "gurobi" or "cplex")."""
    try:
        plugin = _PYOMO_NAMES[name]
    except KeyError as err:
        raise ValueError(f"Unknown solver {name!r}; choose one of {sorted(_PYOMO_NAMES)}") from err
    solver = pyo.SolverFactory(plugin)
    if not solver.available(exception_flag=False):
        raise RuntimeError(f"Solver {name!r} (Pyomo plugin {plugin!r}) is not available")
    return solver


def solver_version(name: str = "highs") -> str:
    """Return the solver version as a dotted string, for ``run_meta.json``."""
    ver = get_solver(name).version()
    return ".".join(str(v) for v in ver) if isinstance(ver, tuple) else str(ver)
