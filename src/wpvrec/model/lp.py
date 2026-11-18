"""Pyomo LP of specification Section 5 (approved model v2): constraints V1-V9, F1 and F2.

One working day of T slots for each representative day d; the days are independent except
through the annual objectives. All variables are continuous.

    F1 = sum_d w_d sum_t s_dt                                        [kWh/yr], maximise
    F2 = sum_d w_d [ sum_g sum_{t>c} (t-c) y_dgt + sum_t W_dt ]      [missions*h/yr], minimise
"""

from __future__ import annotations

import pyomo.environ as pyo

from wpvrec.model.inputs import ModelInputs

INTERNAL = ("repl", "reslot")


def build_model(inp: ModelInputs) -> pyo.ConcreteModel:
    m = pyo.ConcreteModel(name="warehouse_pv_rec")
    T = list(range(1, inp.T + 1))
    T0 = [0] + T
    shift = set(inp.shift)
    m.D = pyo.Set(initialize=range(inp.D))
    m.T = pyo.Set(initialize=T)
    m.T0 = pyo.Set(initialize=T0)
    m.G = pyo.Set(initialize=range(len(inp.groups)))
    m.A = pyo.Set(initialize=INTERNAL)
    m.F = pyo.Set(initialize=range(inp.n_forklifts))
    m.L = pyo.Set(initialize=range(len(inp.cut_list)))
    grp = inp.groups

    # V1 index: picks of group g in slot t allowed only within shifts and from the release slot
    allowed = [(d, g, t) for d in m.D for g in m.G for t in T if t in shift and t >= grp[g].release]
    m.YI = pyo.Set(initialize=allowed)
    m.y = pyo.Var(m.YI, domain=pyo.NonNegativeReals)
    m.z = pyo.Var(m.D, m.A, m.T, domain=pyo.NonNegativeReals)
    m.q = pyo.Var(m.D, m.F, m.T, bounds=(0, 1))
    m.o = pyo.Var(m.D, m.F, m.T, bounds=(0, 1))
    m.soc = pyo.Var(m.D, m.F, m.T0, bounds=(inp.soc_min * inp.q_cap, inp.q_cap))
    m.S = pyo.Var(m.D, m.T0, bounds=(inp.smin, None))
    m.B = pyo.Var(m.D, m.T, bounds=(0, inp.bmax))
    m.ell = pyo.Var(m.D, m.T, bounds=(0, inp.rho_max * inp.capacity))
    m.W = pyo.Var(m.D, m.T, domain=pyo.NonNegativeReals)
    m.E = pyo.Var(m.D, m.T, domain=pyo.NonNegativeReals)
    m.s = pyo.Var(m.D, m.T, domain=pyo.NonNegativeReals)
    m.g = pyo.Var(m.D, m.T, domain=pyo.NonNegativeReals)
    m.x = pyo.Var(m.D, m.T, domain=pyo.NonNegativeReals)

    by_group = {}
    for d, g, t in allowed:
        by_group.setdefault((d, g), []).append(t)

    def picks(d, t):
        return sum(m.y[d, g, t] for g in m.G if (d, g, t) in m.YI)

    # V1 each order picked once, not before its release (index restriction above)
    m.v1 = pyo.Constraint(
        m.D, m.G, rule=lambda m, d, g: sum(m.y[d, g, t] for t in by_group[d, g]) == grp[g].n
    )

    # V2 internal missions all done, within shifts
    n_int = {"repl": inp.n_repl, "reslot": inp.n_reslot}
    m.v2 = pyo.Constraint(m.D, m.A, rule=lambda m, d, a: sum(m.z[d, a, t] for t in T) == n_int[a])
    m.v2_shift = pyo.Constraint(
        m.D,
        m.A,
        m.T,
        rule=lambda m, d, a, t: pyo.Constraint.Skip if t in shift else m.z[d, a, t] == 0,
    )

    # V3 picking-area stock never below the minimum; cyclic over the day
    m.v3_init = pyo.Constraint(m.D, rule=lambda m, d: m.S[d, 0] == inp.s0)
    m.v3 = pyo.Constraint(
        m.D,
        m.T,
        rule=lambda m, d, t: (
            m.S[d, t] == m.S[d, t - 1] + inp.kappa * m.z[d, "repl", t] - picks(d, t)
        ),
    )
    m.v3_end = pyo.Constraint(m.D, rule=lambda m, d: m.S[d, T[-1]] == inp.s0)

    # V4 buffer of pallets picked for orders not yet arrived (actual arrival slot)
    def v4(m, d, t):
        early = [
            m.y[d, g, tt]
            for g in m.G
            if grp[g].arrival > t
            for tt in by_group.get((d, g), [])
            if tt <= t
        ]
        return m.B[d, t] == sum(early) if early else m.B[d, t] == 0

    m.v4 = pyo.Constraint(m.D, m.T, rule=v4)

    # V5 hourly capacity of the AVS/RS (upper bound rho_max * C on ell)
    m.v5 = pyo.Constraint(
        m.D,
        m.T,
        rule=lambda m, d, t: (
            m.ell[d, t] == inp.days[d].u[t - 1] + picks(d, t) + sum(m.z[d, a, t] for a in m.A)
        ),
    )

    # V6 congestion: waiting time above every secant of the M/M/1 curve
    m.v6 = pyo.Constraint(
        m.D,
        m.T,
        m.L,
        rule=lambda m, d, t, k: m.W[d, t] >= inp.cut_list[k][0] * m.ell[d, t] + inp.cut_list[k][1],
    )

    # V7 forklifts always cover the docks, never run flat, cyclic state of charge
    m.v7_dock = pyo.Constraint(
        m.D, m.T, rule=lambda m, d, t: sum(m.o[d, f, t] for f in m.F) == inp.days[d].h[t - 1]
    )
    m.v7_time = pyo.Constraint(
        m.D, m.F, m.T, rule=lambda m, d, f, t: m.o[d, f, t] + m.q[d, f, t] <= 1
    )
    m.v7_chi = pyo.Constraint(
        m.D, m.F, m.T, rule=lambda m, d, f, t: m.q[d, f, t] <= inp.days[d].chi[t - 1]
    )
    m.v7_soc = pyo.Constraint(
        m.D,
        m.F,
        m.T,
        rule=lambda m, d, f, t: (
            m.soc[d, f, t]
            == m.soc[d, f, t - 1] + inp.eta * inp.p_ch * m.q[d, f, t] - inp.k * m.o[d, f, t]
        ),
    )
    m.v7_cyc = pyo.Constraint(m.D, m.F, rule=lambda m, d, f: m.soc[d, f, T[-1]] == m.soc[d, f, 0])

    # V8 site energy
    m.v8 = pyo.Constraint(
        m.D,
        m.T,
        rule=lambda m, d, t: (
            m.E[d, t]
            == inp.days[d].pf[t - 1]
            + inp.e_net_kwh * m.ell[d, t]
            + inp.p_ch * sum(m.q[d, f, t] for f in m.F)
        ),
    )

    # V9 PV goes to the site first, the rest to the grid
    m.v9_pv = pyo.Constraint(m.D, m.T, rule=lambda m, d, t: m.s[d, t] <= inp.days[d].pv[t - 1])
    m.v9_e = pyo.Constraint(m.D, m.T, rule=lambda m, d, t: m.s[d, t] <= m.E[d, t])
    m.v9_g = pyo.Constraint(m.D, m.T, rule=lambda m, d, t: m.g[d, t] == m.E[d, t] - m.s[d, t])
    m.v9_x = pyo.Constraint(
        m.D, m.T, rule=lambda m, d, t: m.x[d, t] == inp.days[d].pv[t - 1] - m.s[d, t]
    )

    # objectives as expressions (activated by the solve functions)
    w = inp.weights
    m.F1 = pyo.Expression(expr=sum(w[d] * m.s[d, t] for d in m.D for t in T))
    m.F2_late = pyo.Expression(
        expr=sum(w[d] * (t - inp.cutoff) * m.y[d, g, t] for (d, g, t) in allowed if t > inp.cutoff)
    )
    m.F2_queue = pyo.Expression(expr=sum(w[d] * m.W[d, t] for d in m.D for t in T))
    m.F2 = pyo.Expression(expr=m.F2_late + m.F2_queue)
    return m
