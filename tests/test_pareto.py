"""Phase 4: Pareto front, shadow prices, special points, policies P0 and P1.

Tiny instances use placeholder numbers built here (test fixtures), never the registry.
"""

import numpy as np
import pyomo.environ as pyo
import pytest

from test_model import RESTOCK, TOL, tiny
from wpvrec import balances, pareto, policies, queueing
from wpvrec.data.common import PROCESSED
from wpvrec.model import lp, solve
from wpvrec.model.inputs import Group

REL = 1e-6
EPS = 1e-3


def three_slot():
    """120 picks over 3 slots, PV only in slot 2 (plenty), 1 kWh per mission.

    F1 = picks in slot 2 (x); best service splits the rest evenly: F2 = W(x) + 2 W((120-x)/2).
    """
    g = Group("g", arrival=1, release=1, n=120.0, predictable=False)
    return tiny(3, pv=[0, 500, 0], groups=[g], e_net_kwh=1.0, **RESTOCK)


def brute_f2(inp, x):
    return float(
        queueing.piecewise(x, inp.cut_list) + 2 * queueing.piecewise((120 - x) / 2, inp.cut_list)
    )


@pytest.fixture(scope="module")
def tiny_front():
    inp = three_slot()
    m = lp.build_model(inp)
    return inp, m, pareto.front(m, 9, REL, EPS, 0.01)


def test_front_extremes_equal_payoff(tiny_front):
    _, _, fr = tiny_front
    pts = fr.points
    assert pts.F1.iloc[0] == pytest.approx(fr.payoff["min_F2"].F1, rel=1e-5)
    assert pts.F2.iloc[0] == pytest.approx(fr.payoff["min_F2"].F2, rel=1e-5)
    assert pts.F1.iloc[-1] == pytest.approx(fr.payoff["max_F1"].F1, rel=1e-5)
    assert pts.F2.iloc[-1] == pytest.approx(fr.payoff["max_F1"].F2, rel=1e-4)
    assert pytest.approx(90.0, abs=1e-4) == fr.payoff["max_F1"].F1  # rho_max * C in slot 2


def test_front_monotone_and_matches_brute_force(tiny_front):
    inp, _, fr = tiny_front
    pts = fr.points
    assert (np.diff(pts.F1) > 0).all() and (np.diff(pts.F2) >= -1e-6).all()
    for f1, f2 in zip(pts.F1, pts.F2, strict=True):
        assert f2 == pytest.approx(brute_f2(inp, f1), rel=1e-5, abs=1e-5)
    assert not fr.warnings


def test_shadow_price_matches_finite_differences(tiny_front):
    _, _, fr = tiny_front
    pts = fr.points
    assert pts.shadow_ok.all()
    assert (pts.shadow_price >= -1e-9).all()  # more PV never improves service here
    inner = pts.iloc[1:-1]
    lo = np.minimum(inner.fd_left, inner.fd_right)
    hi = np.maximum(inner.fd_left, inner.fd_right)
    assert ((inner.shadow_price >= lo - 1e-3) & (inner.shadow_price <= hi + 1e-3)).all()


def test_knee_and_inside_checks(tiny_front):
    _, _, fr = tiny_front
    pts = fr.points
    k = pareto.knee(pts)
    assert 0 < k < len(pts) - 1
    mid = pts.iloc[k]
    assert pareto.is_on_or_inside(pts, mid.F1, mid.F2, REL)  # on the front
    assert pareto.is_on_or_inside(pts, mid.F1, mid.F2 + 5, REL)  # inside
    assert not pareto.is_on_or_inside(pts, mid.F1, mid.F2 - 5, REL)  # would dominate
    assert not pareto.is_on_or_inside(pts, pts.F1.iloc[-1] + 5, 0.0, REL)


def test_equal_service_point(tiny_front):
    inp, m, fr = tiny_front
    cap = fr.points.F2.iloc[len(fr.points) // 2]
    r = pareto.equal_service_point(m, cap, REL)
    assert cap + 1e-6 >= r.F2
    assert brute_f2(inp, r.F1) == pytest.approx(cap, rel=1e-4)  # binding: most PV at that F2


def test_no_tradeoff_gives_one_point():
    inp = tiny(3, pv=[0, 0, 0], groups=[Group("g", 1, 1, 120.0, False)], **RESTOCK)
    fr = pareto.front(lp.build_model(inp), 5, REL, EPS, 0.01)
    assert len(fr.points) == 1 and fr.warnings


# ---- policies --------------------------------------------------------------------------------
def test_p0_spills_charging_to_the_nearest_free_hour():
    # forklift busy in slots 1 and 3 (10 kWh at k = 5); evening window = slot 4 gives 8 kWh:
    # 2 kWh must spill; slot 3 is busy, so it goes to slot 2 (2 hours from the window)
    inp = tiny(4, pv=[0, 0, 0, 0], h=[1, 0, 1, 0], k=5.0)
    pr = policies.p0_plan(inp, internal={1}, charging={4}, tol=REL)
    q = [pyo.value(pr.model.q[0, 0, t]) for t in range(1, 5)]
    assert q[3] == pytest.approx(1.0, abs=TOL)
    assert q[1] == pytest.approx(0.25, abs=TOL)
    assert pr.spill["charging_kwh_outside_per_yr"] == pytest.approx(2.0, abs=1e-5)
    assert balances.verify(pr.model, inp)["all_ok"]


def test_p0_forbids_prepicking_and_keeps_internal_in_window():
    gp = Group("p", arrival=3, release=1, n=10.0, predictable=True)
    inp = tiny(4, pv=[50, 0, 0, 0], groups=[gp], n_reslot=6.0, e_net_kwh=1.0, n_repl=1e-6,
               kappa=1e7)  # fmt: skip
    pr = policies.p0_plan(inp, internal={1, 4}, charging={4}, tol=REL)
    m = pr.model
    assert pyo.value(m.y[0, 0, 1]) + pyo.value(m.y[0, 0, 2]) == pytest.approx(0, abs=TOL)
    assert sum(pyo.value(m.z[0, "reslot", t]) for t in (2, 3)) == pytest.approx(0, abs=TOL)
    assert pr.spill["internal_missions_outside_per_yr"] == pytest.approx(0, abs=1e-5)


def test_p1_puts_flexible_work_in_the_window():
    inp = tiny(3, pv=[0, 50, 0], n_reslot=10.0, e_net_kwh=1.0)
    pr = policies.p1_plan(inp, window={2}, tol=REL)
    assert pyo.value(pr.model.z[0, "reslot", 2]) == pytest.approx(10.0, abs=TOL)
    assert pr.spill["flexible_kwh_in_window_per_yr"] == pytest.approx(10.0, abs=1e-5)


def test_policies_never_dominate_the_front(tiny_front):
    inp, _, fr = tiny_front
    for pr in (policies.p0_plan(inp, {1}, {3}, REL), policies.p1_plan(inp, {2}, REL)):
        assert pareto.is_on_or_inside(fr.points, pr.result.F1, pr.result.F2, 1e-5)


def test_optimise_rejects_unknown_operator():
    m = lp.build_model(three_slot())
    with pytest.raises(ValueError, match="operator"):
        solve.optimise(m, m.F2, "min", [(m.F1, "<", 1.0)])


# ---- base case --------------------------------------------------------------------------------
@pytest.mark.skipif(not (PROCESSED / "pv_typical_year.csv").exists(), reason="run wpvrec data")
def test_base_case_study_small_grid():
    from wpvrec import study
    from wpvrec.params import load_registry

    reg = load_registry()
    reg.values["pareto_points"] = 5  # small grid to keep the test short
    st = study.front_study(reg)
    assert not st.warnings
    assert st.policies.on_or_inside_front.all()
    assert (np.diff(st.front.F1) > 0).all()
    assert set(st.special.point) == {"min_F2", "knee", "max_F1", "same_F2_as_P0"}
    p0 = st.policies.set_index("policy").loc["P0"]
    same = st.special.set_index("point").loc["same_F2_as_P0"]
    assert same.F1_kwh >= p0.F1_kwh - 1e-3  # at equal service, the optimum uses at least as much PV
