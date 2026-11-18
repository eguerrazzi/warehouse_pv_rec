"""Figures of the LP (Phase 3): queue curve and cuts, an optimised day at the two extremes.

Run ``wpvrec figures model``.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from wpvrec import balances, days, queueing  # noqa: E402
from wpvrec.figures.data_figures import MONTHS  # noqa: E402  (also sets rcParams)
from wpvrec.figures.schematics import (  # noqa: E402
    AQUA,
    BLUE,
    INK,
    INK2,
    LINE,
    MUTED,
    OUT_DIR,
    YELLOW,
)
from wpvrec.model import inputs, lp, solve  # noqa: E402
from wpvrec.params import Registry, load_registry  # noqa: E402

FIXED = "#b9b7b0"


def queue_cuts(reg: Registry, inp):
    C, rho = inp.capacity, inp.rho_max
    load = np.linspace(0, rho * C, 400)
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.plot(load, queueing.waiting(load, C), color=INK, lw=2, label="M/M/1 waiting time")
    ax.plot(
        load,
        queueing.piecewise(load, inp.cut_list),
        color=BLUE,
        lw=2,
        ls="--",
        label=f"LP: {len(inp.cut_list)} secant cuts",
    )
    bps = np.asarray(reg.value("queue_breakpoints")) * rho * C
    ax.scatter(bps, queueing.waiting(bps, C), color=BLUE, s=25, zorder=3)
    ax.set_xlabel("missions in the hour, l_t")
    ax.set_ylabel("waiting, missions·h")
    ax.set_title(
        f"Congestion of the AVS/RS (C = {C:.0f}/h, max utilisation {rho:g})",
        loc="left",
        fontsize=10,
        color=INK,
    )
    ax.legend(frameon=False)
    ax.grid(color=LINE, lw=0.5)
    return fig


def plan_day(reg: Registry, inp, month: int = 7):
    m = lp.build_model(inp)
    tol = reg.value("lexicographic_tolerance")
    d = month - 1
    hours = np.arange(1, inp.T + 1) - 0.5
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9), sharey=True)
    for ax, (obj, title) in zip(
        axes,
        (("min_F2", "Best service (min F2)"), ("max_F1", "Most PV used (max F1)")),
        strict=True,
    ):
        r = solve.lexicographic(m, obj, tol)
        p = balances.plan_frame(m, inp)
        p = p[p["day"] == d]
        layers = [
            ("fixed loads", p["fixed"], FIXED),
            ("AVS/RS missions", p["missions_kwh"], BLUE),
            ("forklift charging", p["charging_kwh"], AQUA),
        ]
        ax.stackplot(
            hours,
            *[ly[1] for ly in layers],
            colors=[ly[2] for ly in layers],
            labels=[ly[0] for ly in layers],
            step="mid",
            edgecolor="white",
            lw=0.6,
        )
        ax.plot(hours, p["pv"], color=YELLOW, lw=2.2, label="PV production", drawstyle="steps-mid")
        ax.set_title(
            f"{title}: F1 {r.F1 / 1000:,.2f} MWh/yr, F2 {r.F2:,.0f} missions·h/yr",
            loc="left",
            fontsize=9,
            color=INK,
        )
        ax.set_xticks(range(0, 25, 3), [f"{h:02d}" for h in range(0, 25, 3)])
        ax.set_xlim(0, 24)
        ax.grid(axis="y", color=LINE, lw=0.5)
        ax.axvline(inp.cutoff, color=INK2, lw=1, ls="--")
        ax.set_xlabel("local clock hour")
    axes[0].set_ylabel(f"kWh in the hour ({MONTHS[d]})")
    axes[1].legend(frameon=False, loc="upper right", fontsize=8)
    fig.text(
        0.01,
        -0.03,
        "Same work in both plans; only its timing changes. Dashed line: shipping "
        "cut-off. PV: PVGIS typical year (real); loads: registry.",
        fontsize=7,
        color=MUTED,
    )
    fig.tight_layout()
    return fig


def make_all(out_dir: Path = OUT_DIR, registry: Registry | None = None) -> list[Path]:
    reg = registry or load_registry()
    inp = inputs.build(reg, days.build(reg))
    figs = {"queue_cuts": queue_cuts(reg, inp), "plan_july": plan_day(reg, inp)}
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fig in figs.items():
        for ext in ("png", "pdf"):
            path = out_dir / f"{name}.{ext}"
            fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
            written.append(path)
        plt.close(fig)
    return written
