"""Schematic figures of the case study (not to scale), for the paper and the guide.

Every number printed on a figure is read from the parameter registry, so the
figures stay consistent with the data. Run ``wpvrec figures schematics``.

- ``site_layout``: building, rooftop PV, AVS/RS, docks, forklifts, fixed loads,
  meter, grid and REC members, with the hourly energy flows of the model.
- ``avsrs_missions``: the AVS/RS and the five mission types, fixed vs shiftable.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

from wpvrec.params import Registry, load_registry  # noqa: E402

# Validated categorical palette (dataviz reference instance, light mode) and text inks.
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
MAGENTA, GREEN, VIOLET, RED = "#e87ba4", "#008300", "#6250d6", "#e34948"
INK, INK2, MUTED, LINE, FILL = "#0b0b0b", "#52514e", "#8a8984", "#c9c8c2", "#f1f0ec"

OUT_DIR = Path(__file__).resolve().parents[3] / "docs" / "figures"


def _box(ax, x, y, w, h, label="", fc=FILL, ec=LINE, fs=8, color=INK, lw=1.0, va="center"):
    ax.add_patch(
        FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.6", fc=fc, ec=ec, lw=lw)
    )
    if label:
        ty = y + h / 2 if va == "center" else y + h - 1.2
        ax.text(x + w / 2, ty, label, ha="center", va=va, fontsize=fs, color=color, wrap=True)


def _arrow(ax, p0, p1, color, label="", lw=2.0, ls="-", rad=0.0, fs=7.5, off=(0, 0.9), style="-|>"):
    ax.add_patch(
        FancyArrowPatch(
            p0,
            p1,
            arrowstyle=style,
            mutation_scale=11,
            lw=lw,
            color=color,
            ls=ls,
            connectionstyle=f"arc3,rad={rad}",
            shrinkA=2,
            shrinkB=2,
        )
    )
    if label:
        mx, my = (p0[0] + p1[0]) / 2 + off[0], (p0[1] + p1[1]) / 2 + off[1]
        ax.text(mx, my, label, ha="center", va="bottom", fontsize=fs, color=INK)


def _new(w=11, h=6.4, xmax=110, ymax=64):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def _rack(ax, x, y, w, h, tiers, cols=12):
    """AVS/RS rack seen from the front: tiers x channels grid, one shuttle per tier."""
    ax.add_patch(Rectangle((x, y), w, h, fc="white", ec=INK2, lw=1.2))
    th = h / tiers
    for i in range(1, tiers):
        ax.plot([x, x + w], [y + i * th, y + i * th], color=INK2, lw=0.8)
    for j in range(1, cols):
        ax.plot([x + j * w / cols] * 2, [y, y + h], color=LINE, lw=0.5)
    for i in range(tiers):  # one shuttle per tier, at a different channel
        sx = x + ((i * 5) % (cols - 1) + 0.15) * w / cols
        ax.add_patch(Rectangle((sx, y + i * th + 0.15 * th), 0.7 * w / cols, 0.3 * th, fc=VIOLET))


def site_layout(reg: Registry):
    v = reg.value
    fig, ax = _new(w=11.5, xmax=117)
    # Building and roof PV
    ax.add_patch(Rectangle((4, 6), 70, 36, fc="white", ec=INK, lw=1.4))
    ax.text(5, 43.2, "Warehouse (SME)", fontsize=9, color=INK, weight="bold")
    for k in range(10):
        ax.add_patch(Rectangle((12 + k * 5.4, 44.5), 4.6, 2.6, fc=YELLOW, ec="white", lw=1))
    ax.text(39, 48.4, f"Rooftop PV  {v('pv_kwp'):g} kWp", ha="center", fontsize=9, color=INK)

    # AVS/RS
    _rack(ax, 10, 12, 26, 24, int(v("n_tiers")))
    _box(ax, 6.5, 12, 3, 24, fc=FILL)
    _box(ax, 36.5, 12, 3, 24, fc=FILL)
    ax.text(8, 37.2, "out\nlift", ha="center", fontsize=7, color=INK2)
    ax.text(38, 37.2, "in\nlift", ha="center", fontsize=7, color=INK2)
    ax.text(
        23, 8.2, f"AVS/RS: {int(v('n_tiers'))} tiers, 2 lifts, shuttles + satellites",
        ha="center", fontsize=8, color=INK,
    )  # fmt: skip
    ax.text(
        23, 39.4, f"{v('missions_per_day'):,.0f} missions/day   C = {v('capacity_c'):.0f}/h",
        ha="center", fontsize=8, color=INK2,
    )  # fmt: skip

    # Picking area, docks, forklifts, fixed loads
    _box(ax, 43, 27, 13, 9, "Picking area\n(stock $S_t$)", fs=8)
    _box(ax, 43, 12, 13, 11, "Docks\n(inbound and\noutbound trucks)", fs=8)
    nf = int(v("n_forklifts"))
    _box(ax, 59, 12, 13, 11, "", fs=8)
    for k in range(nf):
        ax.add_patch(plt.Circle((61.5 + k * (9 / max(nf - 1, 1)), 19.6), 1.0, fc=AQUA, ec="white"))
    ax.text(
        65.5, 13.4, f"{nf} Li-ion forklifts\nchargers {v('charger_kw'):g} kW",
        ha="center", fontsize=7.5, color=INK,
    )  # fmt: skip
    shift_kw = v("avsrs_standby_kw") + v("lighting_kw") + v("offices_kw") + v("other_kw")
    _box(
        ax, 59, 27, 13, 9,
        f"Fixed loads\n{shift_kw:g} kW in shift\n{v('offshift_standby_kw'):g} kW off shift", fs=7.5,
    )  # fmt: skip

    # Meter, grid, REC
    _box(ax, 87, 21, 9, 8, "Site\nmeter", fs=8, fc="white", ec=INK2)
    _box(ax, 103, 21, 11, 8, "Public\ngrid", fs=8, fc="white", ec=INK2)
    _box(ax, 89, 44, 25, 12, "", fc="white", ec=INK2)
    ax.text(101.5, 53.4, "Renewable Energy Community", ha="center", fontsize=8, color=INK)
    ax.text(
        101.5, 46.0,
        f"{int(v('n_households'))} households\n{int(v('n_businesses'))} small businesses",
        ha="center", fontsize=8, color=INK2,
    )  # fmt: skip

    # Energy flows
    _arrow(ax, (66, 47), (91, 29.5), YELLOW, "PV", rad=-0.25, off=(3, 0))
    _arrow(ax, (87, 24), (74.5, 24), BLUE)
    ax.text(80.7, 22.6, "self-consumed\n$s_t$ (F1)", ha="center", va="top", fontsize=7.5, color=INK)
    _arrow(ax, (96.2, 26.5), (102.8, 26.5), ORANGE, "export $x_t$", off=(0, 0.6))
    _arrow(ax, (102.8, 23), (96.2, 23), INK2, "import $g_t$", off=(0, -3.4))
    _arrow(ax, (108.5, 29.2), (108.5, 43.8), ORANGE, "", ls="--")
    ax.text(110, 35.5, "shared\nenergy\n$Sh_t$\n(virtual)", fontsize=7.5, color=INK, va="center")

    ax.text(
        0.5, 1.0,
        "Schematic, not to scale. Arrows: hourly energy flows of the model. "
        "The REC is evaluated ex post on the same flows.",
        fontsize=7.5, color=MUTED,
    )  # fmt: skip
    return fig


def avsrs_missions(reg: Registry):
    v = reg.value
    fig, ax = _new(w=11, h=5.6, ymax=56)
    _rack(ax, 34, 14, 34, 28, int(v("n_tiers")), cols=14)
    _box(ax, 29.5, 14, 4, 28)
    _box(ax, 68.5, 14, 4, 28)
    ax.text(31.5, 43.2, "outbound\nlift", ha="center", fontsize=7.5, color=INK2)
    ax.text(70.5, 43.2, "inbound\nlift", ha="center", fontsize=7.5, color=INK2)
    ax.text(51, 9.0, "rack: deep lanes, one shuttle + satellite per tier", ha="center", fontsize=8)

    _box(ax, 82, 26, 18, 8, "Inbound docks\n(trucks)", fs=8)
    _box(
        ax, 2, 28, 18, 12,
        f"Outbound docks\ncut-off {v('cutoff_hour'):g}:00\nbuffer of pre-picked\n"
        f"pallets (max {v('buffer_max'):g})", fs=7.5,
    )  # fmt: skip
    _box(
        ax, 2, 12, 18, 10,
        f"Picking area\nforward stock $S_t$:\n-1 per pick, +{v('kappa'):g} per\nreplenishment",
        fs=7.5,
    )  # fmt: skip

    fixed, constrained, shift = MUTED, INK, BLUE
    _arrow(
        ax, (82, 30), (72.8, 30), fixed, f"inbound storage\n{v('n_inbound'):.0f}/day", off=(0, 0.9)
    )
    _arrow(ax, (29.3, 37), (20.2, 37), constrained, f"picking {v('n_picks'):.0f}/day", off=(0, 0.6))
    _arrow(ax, (29.3, 31), (20.2, 31), shift, "pre-picking", ls="--", off=(0, -3.2))
    _arrow(ax, (29.3, 17), (20.2, 17), shift, f"replenishment\n{v('n_replenishment'):.0f}/day",
           off=(0, 0.9))  # fmt: skip
    _arrow(ax, (40, 44), (60, 44), shift, f"re-slotting {v('n_reslotting'):.0f}/day",
           rad=-0.35, off=(0, 3.0))  # fmt: skip

    for x0, col, txt in (
        (2, fixed, "fixed: done in the hour after the truck arrives"),
        (40, constrained, "any time after the order is released; after cut-off = lateness (F2)"),
    ):
        ax.plot([x0, x0 + 3.5], [5, 5], color=col, lw=2)
        ax.text(x0 + 4.5, 5, txt, va="center", fontsize=7.5)
    ax.plot([2, 5.5], [1.5, 1.5], color=shift, lw=2)
    ax.text(6.5, 1.5, "shiftable within the shift: the model chooses the hour", va="center",
            fontsize=7.5)  # fmt: skip
    ax.text(
        4, 50,
        f"Each mission uses {v('e_mission_net'):.1f} Wh net "
        f"({v('e_mission_gross'):.1f} Wh gross, {v('regen_share'):g}% recovered by the lifts). "
        f"Predictable share of orders: {v('predictable_share'):g}%, picked up to "
        f"{v('prepick_lead'):g} h early.",
        fontsize=8, color=INK2,
    )  # fmt: skip
    return fig


FIGURES = {"site_layout": site_layout, "avsrs_missions": avsrs_missions}


def make_all(out_dir: Path = OUT_DIR, registry: Registry | None = None) -> list[Path]:
    reg = registry or load_registry()
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fn in FIGURES.items():
        fig = fn(reg)
        for ext in ("png", "pdf"):
            path = out_dir / f"{name}.{ext}"
            fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
            written.append(path)
        plt.close(fig)
    return written
