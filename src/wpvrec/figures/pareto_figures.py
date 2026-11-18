"""Figures of Phase 4: the Pareto front with policies and special points, the shadow price,
and a July day under P0 and under the optimal plan with the same service.

Written by ``wpvrec front`` (they need a solved study).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from wpvrec import balances  # noqa: E402
from wpvrec.figures.data_figures import MONTHS  # noqa: E402  (also sets rcParams)
from wpvrec.figures.model_figures import FIXED  # noqa: E402
from wpvrec.figures.schematics import (  # noqa: E402
    AQUA,
    BLUE,
    INK,
    INK2,
    LINE,
    MUTED,
    ORANGE,
    OUT_DIR,
    VIOLET,
    YELLOW,
)
from wpvrec.units import KWH_PER_MWH  # noqa: E402


def _marker(ax, f1, f2, mk, col, lab):
    ax.scatter(f1 / KWH_PER_MWH, f2, marker=mk, s=60, color=col, edgecolor="white", lw=1.5,
               zorder=4, label=lab)  # fmt: skip


def front_figure(st):
    pts, pol, sp = st.front, st.policies.set_index("policy"), st.special.set_index("point")
    fig, (a0, a1, a2) = plt.subplots(
        1, 3, figsize=(13, 4.2), gridspec_kw={"width_ratios": [1.2, 1, 0.9]}
    )
    x = pts.F1 / KWH_PER_MWH
    # (a) overview: the policies against the front
    a0.plot(x, pts.F2, color=INK, lw=2, label="Pareto front")
    best = sp.loc["same_F2_as_P0"]
    _marker(a0, pol.loc["P0", "F1_kwh"], pol.loc["P0", "F2_missions_h"], "s", ORANGE,
            "P0 current practice")  # fmt: skip
    _marker(a0, pol.loc["P1", "F1_kwh"], pol.loc["P1", "F2_missions_h"], "^", VIOLET,
            "P1 follow the sun")  # fmt: skip
    _marker(a0, best.F1_kwh, best.F2_missions_h, "D", AQUA, "optimum, same service as P0")
    gain = (best.F1_kwh - pol.loc["P0", "F1_kwh"]) / KWH_PER_MWH
    a0.annotate("", xy=(best.F1_kwh / KWH_PER_MWH, best.F2_missions_h),
                xytext=(pol.loc["P0", "F1_kwh"] / KWH_PER_MWH, pol.loc["P0", "F2_missions_h"]),
                arrowprops={"arrowstyle": "->", "color": INK2, "lw": 1.2})  # fmt: skip
    a0.text((pol.loc["P0", "F1_kwh"] / KWH_PER_MWH + best.F1_kwh / KWH_PER_MWH) / 2,
            best.F2_missions_h + 0.04 * (pts.F2.max() - pts.F2.min()),
            f"+{gain:,.1f} MWh/yr of PV,\nsame service", ha="center", fontsize=8,
            color=INK)  # fmt: skip
    a0.set_xlabel("F1, PV self-consumed, working days (MWh/yr) →")
    a0.set_ylabel("F2, lost productivity (missions·h/yr) ↓")
    a0.set_title("Policies against the front", loc="left", fontsize=10, color=INK)
    a0.legend(frameon=False, fontsize=7.5, loc="upper left")
    # (b) zoom on the front
    a1.plot(x, pts.F2, color=INK, lw=2)
    a1.scatter(x, pts.F2, color=INK, s=12, zorder=3)
    for name, mk, col, lab in (("min_F2", "o", INK2, "best service"),
                               ("knee", "o", BLUE, "knee"),
                               ("max_F1", "o", YELLOW, "most PV")):  # fmt: skip
        r = sp.loc[name]
        _marker(a1, r.F1_kwh, r.F2_missions_h, mk, col, lab)
    a1.set_xlabel("F1 (MWh/yr)")
    a1.set_title(f"The front, zoomed: +{(pts.F1.iloc[-1] - pts.F1.iloc[0]):,.0f} kWh/yr",
                 loc="left", fontsize=10, color=INK)  # fmt: skip
    a1.legend(frameon=False, fontsize=7.5, loc="upper left")
    # (c) shadow price
    a2.step(x, pts.shadow_price, where="mid", color=BLUE, lw=2)
    a2.scatter(x, pts.shadow_price, color=BLUE, s=12, zorder=3)
    a2.set_xlabel("F1 (MWh/yr)")
    a2.set_ylabel("missions·h of F2 per extra kWh")
    a2.set_title("Delay cost of one more kWh", loc="left", fontsize=10, color=INK)
    for ax in (a0, a1, a2):
        ax.grid(color=LINE, lw=0.5)
    fig.text(0.01, -0.03, f"Base case, {len(pts)} AUGMECON points; shadow price = dual of the F1 "
             "constraint, checked against the slopes between points. P0, P1: same LP, rule-based. "
             "F1 with s = min(PV, E).", fontsize=7, color=MUTED)  # fmt: skip
    fig.tight_layout()
    return fig


def day_figure(st, month: int = 7):
    inp = st.inputs
    d = month - 1
    hours = np.arange(1, inp.T + 1) - 0.5
    plans = (("P0", "P0 current practice"), ("same_F2_as_P0", "Optimum, same service as P0"))
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9), sharey=True)
    for ax, (key, title) in zip(axes, plans, strict=True):
        m = st.plans[key]
        p = balances.plan_frame(m, inp)
        p = p[p["day"] == d]
        layers = [("fixed loads", p["fixed"], FIXED), ("AVS/RS missions", p["missions_kwh"], BLUE),
                  ("forklift charging", p["charging_kwh"], AQUA)]  # fmt: skip
        ax.stackplot(hours, *[ly[1] for ly in layers], colors=[ly[2] for ly in layers],
                     labels=[ly[0] for ly in layers], step="mid", edgecolor="white",
                     lw=0.6)  # fmt: skip
        ax.plot(hours, p["pv"], color=YELLOW, lw=2.2, label="PV production", drawstyle="steps-mid")
        ax.set_title(title, loc="left", fontsize=9.5, color=INK)
        ax.set_xticks(range(0, 25, 3), [f"{h:02d}" for h in range(0, 25, 3)])
        ax.set_xlim(0, 24)
        ax.grid(axis="y", color=LINE, lw=0.5)
        ax.axvline(inp.cutoff, color=INK2, lw=1, ls="--")
        ax.set_xlabel("local clock hour")
    axes[0].set_ylabel(f"kWh in the hour ({MONTHS[d]})")
    axes[1].legend(frameon=False, loc="upper right", fontsize=8)
    fig.text(0.01, -0.03, "Same work and same lost productivity in both plans; the optimum moves "
             "charging into the sunny hours. Dashed line: shipping cut-off.",
             fontsize=7, color=MUTED)  # fmt: skip
    fig.tight_layout()
    return fig


def value_figure(eb, ec, base_incentive: float):
    """Annual value for the warehouse: condition B (own PV) and condition C (external REC)."""
    plans = [("P0", "P0 current\npractice"), ("P1", "P1 follow\nthe sun"),
             ("same_F2_as_P0", "Optimum,\nsame service")]  # fmt: skip
    b = eb[eb.investment_incentive_pct == base_incentive].set_index("plan")
    c = ec.set_index("plan")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.9), gridspec_kw={"width_ratios": [1.4, 1]})
    xs = np.arange(len(plans))
    parts = [("savings_eur", "avoided purchase (self-consumption)", BLUE),
             ("export_revenue_eur", "export sold at the zonal price", MUTED),
             ("rec_incentive", "warehouse share of the REC incentive", AQUA)]  # fmt: skip
    bottom = np.zeros(len(plans))
    for col, lab, colr in parts:
        if col == "rec_incentive":
            val = np.array([b.loc[p, "rec_annual_flow_eur"] - b.loc[p, "no_rec_annual_flow_eur"]
                            for p, _ in plans])  # fmt: skip
        else:
            val = np.array([b.loc[p, col] for p, _ in plans])
        a1.bar(xs, val / KWH_PER_MWH, bottom=bottom / KWH_PER_MWH, color=colr, width=0.55,
               label=lab, edgecolor="white", lw=2)  # fmt: skip
        bottom += val
    for x in xs:
        a1.text(x, bottom[x] / KWH_PER_MWH + 0.3, f"{bottom[x] / KWH_PER_MWH:,.1f}", ha="center",
                fontsize=8, color=INK)  # fmt: skip
    a1.set_xticks(xs, [lab for _, lab in plans], fontsize=8)
    a1.set_ylabel("k EUR per year (before O&M)")
    a1.set_title("Condition B: own PV, with REC", loc="left", fontsize=10, color=INK)
    a1.legend(frameon=False, fontsize=7.5, loc="upper left")
    a1.set_ylim(0, bottom.max() / KWH_PER_MWH * 1.35)
    vals = np.array([c.loc[p, "benefit_eur"] for p, _ in plans])
    a2.bar(xs, vals, color=AQUA, width=0.55)
    for x, val in zip(xs, vals, strict=True):
        a2.text(x, val + vals.max() * 0.02, f"{val:,.0f}", ha="center", fontsize=8, color=INK)
    a2.set_xticks(xs, [lab for _, lab in plans], fontsize=8)
    a2.set_ylabel("EUR per year")
    a2.set_title("Condition C: member of an external REC", loc="left", fontsize=10, color=INK)
    for ax in (a1, a2):
        ax.grid(axis="y", color=LINE, lw=0.5)
    fig.text(0.01, -0.03, "Constant 2025 prices: retail Eurostat, zonal GME CNOR; premium tariff "
             "DM 414/2023; REC split: beta (B) and consumer share pro rata (C), both assumptions.",
             fontsize=7, color=MUTED)  # fmt: skip
    fig.tight_layout()
    return fig


def make_all(st, out_dir: Path = OUT_DIR, economics=None) -> list[Path]:
    """``economics`` = (eb, ec, base investment incentive) adds the value figure."""
    figs = {"pareto_front": front_figure(st)}
    if economics is not None:
        figs["value_by_plan"] = value_figure(*economics)
    if st.plans:
        figs["plan_p0_vs_optimum"] = day_figure(st)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fig in figs.items():
        for ext in ("png", "pdf"):
            path = out_dir / f"{name}.{ext}"
            fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
            written.append(path)
        plt.close(fig)
    return written
