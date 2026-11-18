"""Checks and reports on a solved plan (Phase 3).

- ``plan_frame``: hourly decisions and flows per day and slot, with s recomputed as
  min(PV, E) as required by the specification (Sect. 5.5, V9);
- ``verify``: maximum violation of every balance (energy, missions, SOC, stock, buffer, queue);
- ``rounding_effect``: F1 and F2 with missions rounded to integers (spec Sect. 5);
- ``annual_summary``: annual energy totals, including non-working days outside the LP
  (stand-by load only; the stand-by uses the PV when there is sun, Ema 18/11/2026, which
  replaces the spec's "all PV exported"; the rest is exported).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyomo.environ as pyo

from wpvrec.days import RepresentativeDays
from wpvrec.model.inputs import ModelInputs
from wpvrec.queueing import piecewise
from wpvrec.units import HOURS_PER_DAY

TOL = 1e-6


def plan_frame(m, inp: ModelInputs) -> pd.DataFrame:
    rows = []
    v = pyo.value
    for d in m.D:
        for t in m.T:
            picks = early = 0.0
            for g, grp in enumerate(inp.groups):
                if (d, g, t) in m.YI:
                    yv = v(m.y[d, g, t])
                    picks += yv
                    if grp.arrival > t:
                        early += yv
            pv, e = inp.days[d].pv[t - 1], v(m.E[d, t])
            rows.append(
                {
                    "day": d,
                    "label": inp.labels[d] if inp.labels else str(d),
                    "weight": inp.weights[d],
                    "slot": t,
                    "pv": pv,
                    "E": e,
                    "s_lp": v(m.s[d, t]),
                    "s": min(pv, e),
                    "g": max(e - pv, 0.0),
                    "x": max(pv - e, 0.0),
                    "fixed": inp.days[d].pf[t - 1],
                    "missions_kwh": inp.e_net_kwh * v(m.ell[d, t]),
                    "charging_kwh": inp.p_ch * sum(v(m.q[d, f, t]) for f in m.F),
                    "inbound_arrived": inp.days[d].u[t - 1],
                    "inbound": v(m.U[d, t]),
                    "picks": picks,
                    "prepicks": early,
                    "late_picks": picks if t > inp.cutoff else 0.0,
                    "repl": v(m.z[d, "repl", t]),
                    "reslot": v(m.z[d, "reslot", t]),
                    "ell": v(m.ell[d, t]),
                    "W": v(m.W[d, t]),
                    "S": v(m.S[d, t]),
                    "B": v(m.B[d, t]),
                    "soc_mean": float(np.mean([v(m.soc[d, f, t]) for f in m.F])),
                    "dock": inp.days[d].h[t - 1],
                }
            )
    return pd.DataFrame(rows)


def f1_recomputed(m, inp: ModelInputs) -> float:
    """F1 of the plan with s = min(PV, E) (spec V9): the LP variable s is only bounded above,
    so it equals min(PV, E) only when F1 is maximised (or rewarded, as in AUGMECON)."""
    v = pyo.value
    return float(
        sum(
            inp.weights[d] * min(inp.days[d].pv[t - 1], v(m.E[d, t]))
            for d in m.D
            for t in m.T
        )
    )


def verify(m, inp: ModelInputs) -> dict[str, float]:
    """Largest violation of each check (0 means satisfied); keys ending in '_ok' are booleans."""
    v = pyo.value
    out = {}
    out["energy_E_eq_s_plus_g"] = max(
        abs(v(m.E[d, t]) - v(m.s[d, t]) - v(m.g[d, t])) for d in m.D for t in m.T
    )
    out["energy_PV_eq_s_plus_x"] = max(
        abs(inp.days[d].pv[t - 1] - v(m.s[d, t]) - v(m.x[d, t])) for d in m.D for t in m.T
    )
    out["picks_done"] = max(
        abs(sum(v(m.y[d, g, t]) for t in m.T if (d, g, t) in m.YI) - grp.n)
        for d in m.D
        for g, grp in enumerate(inp.groups)
    ) if inp.groups else 0.0  # fmt: skip
    out["inbound_done"] = max(
        (abs(sum(v(m.ui[d, a, t]) for t in m.T if (d, a, t) in m.UI) - inp.days[d].u[a - 1])
         for d in m.D for a in m.T if inp.days[d].u[a - 1] > 0),
        default=0.0,
    )  # fmt: skip
    out["internal_done"] = max(
        abs(sum(v(m.z[d, a, t]) for t in m.T) - n)
        for d in m.D
        for a, n in (("repl", inp.n_repl), ("reslot", inp.n_reslot))
    )
    lo, hi = inp.soc_min * inp.q_cap, inp.q_cap
    out["soc_bounds"] = max(
        max(lo - v(m.soc[d, f, t]), v(m.soc[d, f, t]) - hi, 0)
        for d in m.D
        for f in m.F
        for t in m.T0
    )
    out["stock_min"] = max(max(inp.smin - v(m.S[d, t]), 0) for d in m.D for t in m.T0)
    out["buffer_max"] = max(max(v(m.B[d, t]) - inp.bmax, 0) for d in m.D for t in m.T)
    out["capacity"] = max(
        max(v(m.ell[d, t]) - inp.rho_max * inp.capacity, 0) for d in m.D for t in m.T
    )
    out["queue_cuts"] = max(
        max(float(piecewise(v(m.ell[d, t]), inp.cut_list)) - v(m.W[d, t]), 0)
        for d in m.D
        for t in m.T
    )
    out["docks_covered"] = max(
        abs(sum(v(m.o[d, f, t]) for f in m.F) - inp.days[d].h[t - 1]) for d in m.D for t in m.T
    )
    out["all_ok"] = all(val <= TOL * max(1.0, 1e3) for val in out.values())
    return out


def _round_preserving(values: np.ndarray) -> np.ndarray:
    """Round to integers keeping the (rounded) total: largest-remainder method."""
    floor = np.floor(values + TOL)
    missing = int(round(values.sum())) - int(floor.sum())
    order = np.argsort(-(values - floor))
    out = floor.copy()
    if missing > 0:
        out[order[:missing]] += 1
    return out


def rounding_effect(m, inp: ModelInputs) -> dict[str, float]:
    """F1 and F2 recomputed with integer missions per slot (s = min(PV, E))."""
    v = pyo.value
    f1 = f2_late = f2_queue = 0.0
    for d in m.D:
        ell = np.zeros(len(m.T))
        for a in m.T:
            ts = [t for t in m.T if (d, a, t) in m.UI]
            if ts:
                r = _round_preserving(np.array([v(m.ui[d, a, t]) for t in ts]))
                for t, val in zip(ts, r, strict=True):
                    ell[t - 1] += val
        late = 0.0
        for g, _ in enumerate(inp.groups):
            ts = [t for t in m.T if (d, g, t) in m.YI]
            r = _round_preserving(np.array([v(m.y[d, g, t]) for t in ts]))
            for t, val in zip(ts, r, strict=True):
                ell[t - 1] += val
                if t > inp.cutoff:
                    late += (t - inp.cutoff) * val
        for a in ("repl", "reslot"):
            r = _round_preserving(np.array([v(m.z[d, a, t]) for t in m.T]))
            ell += r
        charging = np.array([inp.p_ch * sum(v(m.q[d, f, t]) for f in m.F) for t in m.T])
        E = inp.days[d].pf + inp.e_net_kwh * ell + charging
        w = inp.weights[d]
        f1 += w * np.minimum(inp.days[d].pv, E).sum()
        f2_late += w * late
        f2_queue += w * piecewise(ell, inp.cut_list).sum()
    return {"F1": f1, "F2": f2_late + f2_queue, "F2_late": f2_late, "F2_queue": f2_queue}


def nonworking_self_consumption(rep: RepresentativeDays, offshift_kw: float) -> float:
    """PV used by the stand-by load on non-working days [kWh/yr], constant (no decisions)."""
    per_day = np.minimum(rep.pv, offshift_kw).sum(axis=1)  # kWh per day, by month
    return float((per_day * rep.non_working).sum())


def annual_summary(plan: pd.DataFrame, rep: RepresentativeDays, offshift_kw: float) -> dict:
    """Annual energy [kWh]: working days (LP) and non-working days (stand-by only)."""
    w = plan["weight"]
    work_E = float((plan["E"] * w).sum())
    work_s = float((plan["s"] * w).sum())
    work_pv = float((plan["pv"] * w).sum())
    nonwork_days = rep.non_working
    nonwork_E = float(nonwork_days.sum() * offshift_kw * HOURS_PER_DAY)
    nonwork_pv = float((rep.pv.sum(axis=1) * nonwork_days).sum())
    nonwork_s = nonworking_self_consumption(rep, offshift_kw)
    pv = work_pv + nonwork_pv
    cons = work_E + nonwork_E
    s = work_s + nonwork_s
    return {
        "pv_kwh": pv,
        "consumption_kwh": cons,
        "self_consumed_kwh": s,
        "self_consumed_working_kwh": work_s,
        "self_consumed_non_working_kwh": nonwork_s,
        "export_kwh": pv - s,
        "export_non_working_kwh": nonwork_pv - nonwork_s,
        "import_kwh": cons - s,
        "self_consumption_pct": 100 * s / pv,
        "self_sufficiency_pct": 100 * s / cons,
        "working_day_kwh": float((plan.groupby("day")["E"].sum()).mean()),
    }
