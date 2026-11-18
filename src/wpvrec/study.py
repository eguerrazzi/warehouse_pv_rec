"""Phase 4 study of one scenario: Pareto front, special points, policies P0 and P1.

``front_study(reg)`` returns three tables with the common KPIs (``kpi.py``):

- ``front``: the AUGMECON points (with shadow price and finite-difference check);
- ``special``: extremes, knee and the point with the same F2 as P0 ("at equal service,
  how much more PV?");
- ``policies``: P0 and P1, with their spill / window energy, the F2 of the front at the
  same F1 (exact solve: "at equal PV, how much service could be recovered?") and whether
  they lie on or inside the front (they must never dominate it).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from wpvrec import days, kpi, pareto, policies
from wpvrec.model import inputs, lp
from wpvrec.params import Registry


@dataclass
class Study:
    front: pd.DataFrame
    special: pd.DataFrame
    policies: pd.DataFrame
    payoff: dict
    warnings: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    plans: dict = field(default_factory=dict)  # name -> solved model, for figures
    inputs: object = None  # ModelInputs of the scenario


def front_study(reg: Registry, pv_variant: str = "typical", keep_models: bool = False) -> Study:
    v = reg.value
    solver, threads = str(v("solver")), int(v("solver_threads"))
    tol = v("lexicographic_tolerance")
    rep = days.build(reg, pv_variant)
    inp = inputs.build(reg, rep)
    m = lp.build_model(inp)

    def collect(model, lam):
        return kpi.kpis(model, inp, rep, reg, shadow_price=lam)

    fr = pareto.front(m, int(v("pareto_points")), tol, v("augmecon_eps"),
                      v("shadow_price_tolerance"), solver, threads, collect)  # fmt: skip
    pts = fr.points

    pol_rows, plans = [], {}
    for fn in (policies.p0, policies.p1):
        pr = fn(reg, inp, solver, threads)
        row = {"policy": pr.name, **kpi.kpis(pr.model, inp, rep, reg), **pr.spill}
        ref = pareto.equal_pv_point(m, pr.result.F1, tol, solver, threads)  # exact front
        row["front_F2_at_same_F1"] = ref.F2
        row["on_or_inside_front"] = ref.F2 - tol * (abs(ref.F2) + 1) <= pr.result.F2
        pol_rows.append(row)
        if keep_models:
            plans[pr.name] = pr.model
    pol = pd.DataFrame(pol_rows)

    special = []
    for name, idx in (("min_F2", 0), ("knee", pareto.knee(pts)), ("max_F1", len(pts) - 1)):
        special.append({"point": name, "k": int(pts.k[idx]), **pts.iloc[idx].to_dict()})
    f2_p0 = float(pol.loc[pol.policy == "P0", "F2_missions_h"].iloc[0])
    pareto.equal_service_point(m, f2_p0, tol, solver, threads)
    special.append({"point": "same_F2_as_P0", **kpi.kpis(m, inp, rep, reg)})
    # front rows: F1 is the LP value (s pushed to min(PV, E) by the augmentation); check it
    gap = (pts.F1 - pts.F1_kwh).abs().max()
    if gap > tol * (pts.F1.abs().max() + 1) + 1e-3:
        warnings_f1 = [f"front F1 differs from min(PV, E) by up to {gap:.3f} kWh/yr"]
    else:
        warnings_f1 = []
    sp = pd.DataFrame(special)
    if keep_models:
        plans["same_F2_as_P0"] = m
    warnings = list(fr.warnings) + warnings_f1
    if not pol.on_or_inside_front.all():
        warnings.append("a policy dominates the front: check the solves")
    return Study(pts, sp, pol, fr.payoff, warnings, fr.dropped, plans, inp)
