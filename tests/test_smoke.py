"""Phase 0 smoke tests: the package imports, the CLI runs, HiGHS solves an LP via Pyomo."""

import pyomo.environ as pyo
import pytest

import wpvrec
from wpvrec.cli import main
from wpvrec.solver import get_solver, solver_version


def test_package_imports():
    assert isinstance(wpvrec.__version__, str)


def test_cli_info_runs(capsys):
    assert main(["info"]) == 0
    assert "HiGHS" in capsys.readouterr().out


def test_cli_planned_command_says_not_implemented(capsys):
    assert main(["params"]) == 2
    assert "not implemented yet" in capsys.readouterr().err


def test_highs_solves_trivial_lp():
    # max x + y  s.t.  x + 2y <= 4,  3x + y <= 6,  x, y >= 0  ->  x = 1.6, y = 1.2
    m = pyo.ConcreteModel()
    m.x = pyo.Var(domain=pyo.NonNegativeReals)
    m.y = pyo.Var(domain=pyo.NonNegativeReals)
    m.c1 = pyo.Constraint(expr=m.x + 2 * m.y <= 4)
    m.c2 = pyo.Constraint(expr=3 * m.x + m.y <= 6)
    m.obj = pyo.Objective(expr=m.x + m.y, sense=pyo.maximize)
    get_solver("highs").solve(m)
    assert pyo.value(m.obj) == pytest.approx(2.8)
    assert solver_version("highs")


def test_unknown_solver_rejected():
    with pytest.raises(ValueError):
        get_solver("not-a-solver")
