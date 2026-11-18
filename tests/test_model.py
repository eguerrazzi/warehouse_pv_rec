"""Phase 3: LP V1-V9 on tiny instances with known solutions, and the base case balances.

Tiny instances use placeholder numbers built here (test fixtures), never the registry.
"""

import numpy as np
import pyomo.environ as pyo
import pytest

from wpvrec import balances, days, queueing
from wpvrec.data.common import PROCESSED
from wpvrec.model import inputs, lp, solve
from wpvrec.model.inputs import DayInputs, Group, ModelInputs
from wpvrec.params import load_registry

TOL = 1e-6
RESTOCK = {
    "n_repl": 1e-6,
    "kappa": 1.2e8,
}  # negligible replenishment restoring 120 picks (cyclic V3)


def tiny(T, pv, groups=(), h=None, cutoff=None, capacity=100.0, n_forklifts=1, **kw):
    zeros = np.zeros(T)
    base = dict(
        T=T,
        shift=list(range(1, T + 1)),
        cutoff=cutoff if cutoff is not None else T,
        days=[
            DayInputs(
                pv=np.asarray(pv, float),
                u=zeros,
                h=np.asarray(h if h is not None else zeros, float),
                pf=zeros,
                chi=np.ones(T),
            )
        ],  # fmt: skip
        weights=np.array([1.0]),
        groups=list(groups),
        n_repl=0.0,
        n_reslot=0.0,
        kappa=1.0,
        s0=1000.0,
        smin=0.0,
        bmax=1000.0,
        capacity=capacity,
        rho_max=0.9,
        cut_list=queueing.cuts(capacity, 0.9, [0, 0.5, 0.75, 0.9, 1]),
        e_net_kwh=0.0,
        n_forklifts=n_forklifts,
        k=4.0,
        q_cap=25.0,
        soc_min=0.2,
        p_ch=8.0,
        eta=1.0,
    )
    base.update(kw)
    return ModelInputs(**base)


# ---- queueing --------------------------------------------------------------------------
def test_cuts_exact_at_breakpoints_and_above_between():
    C, rho = 100.0, 0.9
    cl = queueing.cuts(C, rho, [0, 0.5, 0.75, 0.9, 1])
    bps = np.array([0, 0.5, 0.75, 0.9, 1]) * rho * C
    assert np.allclose(queueing.piecewise(bps, cl), queueing.waiting(bps, C))
    mid = np.linspace(1, rho * C - 1, 50)
    assert (queueing.piecewise(mid, cl) >= queueing.waiting(mid, C) - 1e-12).all()


# ---- tiny instances --------------------------------------------------------------------
def test_charging_moves_to_the_sunny_hour():
    # 4 hours, 1 forklift used in hours 1 and 4 (8 kWh), PV only in hour 2
    inp = tiny(4, pv=[0, 20, 0, 0], h=[1, 0, 0, 1])
    m = lp.build_model(inp)
    r = solve.solve(m, "max_F1")
    q = [pyo.value(m.q[0, 0, t]) for t in range(1, 5)]
    assert q[1] == pytest.approx(1.0, abs=TOL)
    assert sum(q) == pytest.approx(1.0, abs=TOL)
    assert pytest.approx(8.0, abs=TOL) == r.F1
    assert balances.verify(m, inp)["all_ok"]


def test_split_load_gives_the_piecewise_waiting_time():
    # 120 picks over 2 hours, no lateness. The curve is linear between breakpoints (45 and
    # 67.5 here): any split inside that piece is optimal and costs the same as 60/60.
    g = Group("g", arrival=1, release=1, n=120.0, predictable=False)
    inp = tiny(2, pv=[0, 0], groups=[g], **RESTOCK)
    m = lp.build_model(inp)
    r = solve.solve(m, "min_F2")
    ell = np.array([pyo.value(m.ell[0, t]) for t in (1, 2)])
    assert ((ell >= 45 - 1e-4) & (ell <= 67.5 + 1e-4)).all()
    assert pytest.approx(2 * float(queueing.piecewise(60.0, inp.cut_list)), rel=1e-6) == r.F2
    assert pytest.approx(queueing.piecewise(ell, inp.cut_list).sum(), rel=1e-6) == r.F2


def test_lateness_trades_against_queue_as_brute_force():
    # cut-off after slot 1: picks in slot 2 cost 1 missions*h each
    g = Group("g", arrival=1, release=1, n=120.0, predictable=False)
    inp = tiny(2, pv=[0, 0], groups=[g], cutoff=1, **RESTOCK)
    m = lp.build_model(inp)
    r = solve.solve(m, "min_F2")
    grid = np.linspace(120 - 0.9 * 100, 90, 30001)  # slot-1 picks, capacity 90/h each slot
    cost = queueing.piecewise(grid, inp.cut_list) + queueing.piecewise(120 - grid, inp.cut_list)
    cost += 120 - grid
    assert pytest.approx(cost.min(), abs=1e-3) == r.F2
    assert r.F2_late == pytest.approx(pyo.value(m.y[0, 0, 2]), abs=TOL)


def test_prepicking_respects_buffer_and_arrival():
    # predictable group arrives in slot 3 but may be released in slot 1; buffer of 5 pallets
    gp = Group("p", arrival=3, release=1, n=30.0, predictable=True)
    inp = tiny(3, pv=[50, 0, 0], groups=[gp], bmax=5.0, e_net_kwh=1.0, n_repl=1e-6, kappa=3e7)
    m = lp.build_model(inp)
    solve.solve(m, "max_F1")  # PV only in slot 1 pulls picks early, buffer limits them
    early = pyo.value(m.y[0, 0, 1]) + pyo.value(m.y[0, 0, 2])
    assert pyo.value(m.y[0, 0, 1]) == pytest.approx(5.0, abs=1e-5)
    assert early <= 5.0 + 1e-6
    assert max(pyo.value(m.B[0, t]) for t in (1, 2, 3)) <= 5.0 + 1e-6


def test_stock_never_below_minimum():
    g = Group("g", arrival=1, release=1, n=10.0, predictable=False)
    inp = tiny(4, pv=[0, 0, 0, 0], groups=[g], n_repl=10.0, kappa=1.0, s0=3.0, smin=2.0)
    m = lp.build_model(inp)
    solve.solve(m, "min_F2")
    assert min(pyo.value(m.S[0, t]) for t in range(0, 5)) >= 2.0 - 1e-6
    assert balances.verify(m, inp)["all_ok"]


# ---- base case ----------------------------------------------------------------------------
@pytest.mark.skipif(not (PROCESSED / "pv_typical_year.csv").exists(), reason="run wpvrec data")
def test_base_case_balances_and_payoff_order():
    reg = load_registry()
    rep = days.build(reg)
    inp = inputs.build(reg, rep)
    m = lp.build_model(inp)
    tol = reg.value("lexicographic_tolerance")
    a = solve.lexicographic(m, "min_F2", tol)
    assert balances.verify(m, inp)["all_ok"]
    b = solve.lexicographic(m, "max_F1", tol)
    assert balances.verify(m, inp)["all_ok"]
    assert a.F2 <= b.F2 + 1e-6 and b.F1 >= a.F1 - 1e-6  # the two extremes of the front
    assert inp.prepick_potential() == pytest.approx(97.5)  # 5 same-day groups x 30% x 65
