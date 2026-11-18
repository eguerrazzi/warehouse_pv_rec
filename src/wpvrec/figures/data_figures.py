"""Figures of the processed input data (Phase 2): PV and price heatmaps, a working day.

All numbers come from ``data/processed`` and the registry. Run ``wpvrec figures data``.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from wpvrec import days as days_mod  # noqa: E402
from wpvrec.figures.schematics import (  # noqa: E402
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
from wpvrec.params import Registry, load_registry  # noqa: E402

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SEQ_SUN = LinearSegmentedColormap.from_list("sun", ["#fdf8ec", "#f3c95a", "#eda100", "#7a5200"])
SEQ_BLUE = LinearSegmentedColormap.from_list("blue", ["#f2f6fc", "#9cc0ee", "#2a78d6", "#123e73"])

plt.rcParams.update(
    {
        "font.size": 8.5,
        "axes.edgecolor": LINE,
        "axes.labelcolor": INK2,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def _heatmap(values, title, unit, cmap, note):
    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    im = ax.imshow(values, aspect="auto", cmap=cmap, origin="upper",
                   extent=(0, 24, 12, 0))  # fmt: skip
    ax.set_yticks(np.arange(12) + 0.5, MONTHS)
    ax.set_xticks(range(0, 25, 3), [f"{h:02d}:00" for h in range(0, 25, 3)])
    ax.set_xlabel("local clock time (slot t covers [t-1, t))")
    ax.set_title(title, loc="left", fontsize=10, color=INK)
    cb = fig.colorbar(im, ax=ax, pad=0.015)
    cb.set_label(unit, color=INK2)
    cb.outline.set_edgecolor(LINE)
    fig.text(0.01, -0.02, note, fontsize=7, color=MUTED)
    return fig


def pv_heatmap(reg: Registry, d):
    return _heatmap(
        d.pv,
        f"PV production of the {reg.value('pv_kwp'):g} kWp plant, typical year "
        f"({d.annual_pv() / 1000:.0f} MWh/yr)",
        "kWh in the hour",
        SEQ_SUN,
        f"Source: PVGIS-SARAH3 {int(reg.value('pvgis_start_year'))}-"
        f"{int(reg.value('pvgis_end_year'))}, "
        "mean per month and hour (real). South, PVGIS optimal tilt, 14% losses.",
    )


def price_heatmap(reg: Registry, d):
    return _heatmap(
        d.price_working,
        f"Day-ahead zonal price {reg.value('gme_zone')}, working days {int(reg.value('gme_year'))}",
        "EUR/MWh",
        SEQ_BLUE,
        "Source: GME, MGP 'Dati storici' (real); mean per month and hour of working days. "
        "Oct-Dec: hourly re-elaboration of 15-min prices.",
    )


def working_day(reg: Registry, d):
    v = reg.value
    hours = np.arange(24) + 0.5  # centre of slot t
    fig, axes = plt.subplots(3, 1, figsize=(8.2, 6.6), sharex=True,
                             gridspec_kw={"height_ratios": [2.2, 1.9, 1.6]})  # fmt: skip
    a1, a2, a3 = axes

    for m, col, name in ((0, BLUE, "January"), (6, ORANGE, "July")):
        a1.plot(hours, d.pv[m], color=col, lw=2, label=name)
    a1.set_ylabel("PV, kWh in the hour")
    a1.set_title("A working day of the case study", loc="left", fontsize=10, color=INK)
    a1.legend(frameon=False, loc="upper left")
    a1.grid(axis="y", color=LINE, lw=0.5)

    rows = [
        ("Work shifts", v("shift_start"), v("shift_end"), INK2),
        ("Inbound trucks (storage)", v("inbound_start"), v("inbound_end"), MUTED),
        (
            f"Order arrivals (dot: {v('order_share_previous_evening'):g}% ready at start)",
            v("order_arrival_start"),
            v("order_arrival_end"),
            VIOLET,
        ),
        ("P1: follow the sun", v("p1_sun_start"), v("p1_sun_end"), YELLOW),
        ("P0: internal work (morning)", v("shift_start"), v("p0_morning_end"), BLUE),
        ("P0: internal work + charging", v("p0_evening_start"), v("shift_end"), BLUE),
    ]
    for i, (lab, s, e, col) in enumerate(rows):
        y = len(rows) - i
        a2.barh(y, e - s, left=s, height=0.55, color=col)
        a2.text(-0.3, y, lab, ha="right", va="center", fontsize=7.8, color=INK)
    a2.scatter([v("shift_start")], [len(rows) - 2], s=30, color=VIOLET, zorder=3)
    a2.set_yticks([])
    a2.spines["left"].set_visible(False)
    a2.set_ylim(0.3, len(rows) + 0.7)

    a3.plot(hours, d.price_working[0], color=BLUE, lw=2, label="January")
    a3.plot(hours, d.price_working[6], color=ORANGE, lw=2, label="July")
    a3.legend(frameon=False, loc="upper left", ncol=2)
    a3.set_ylabel(f"price {v('gme_zone')}, EUR/MWh")
    a3.grid(axis="y", color=LINE, lw=0.5)
    a3.set_xlim(0, 24)
    a3.set_xticks(range(0, 25, 2), [f"{h:02d}" for h in range(0, 25, 2)])
    a3.set_xlabel("local clock hour")

    for ax in axes:
        ax.axvline(v("cutoff_hour"), color=INK, lw=1, ls="--")
    a1.text(v("cutoff_hour") + 0.2, a1.get_ylim()[1] * 0.97,
            f"shipping cut-off {v('cutoff_hour'):g}:00",
            fontsize=7.5, color=INK)  # fmt: skip
    fig.text(0.01, 0.0, "PV: PVGIS typical year (real). Windows: registry (assumptions). "
             "Prices: GME 2025, working days (real).", fontsize=7, color=MUTED)  # fmt: skip
    fig.subplots_adjust(left=0.30, hspace=0.18)
    return fig


FIGURES = {"pv_heatmap": pv_heatmap, "price_heatmap": price_heatmap, "working_day": working_day}


def make_all(out_dir: Path = OUT_DIR, registry: Registry | None = None) -> list[Path]:
    reg = registry or load_registry()
    d = days_mod.build(reg)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fn in FIGURES.items():
        fig = fn(reg, d)
        for ext in ("png", "pdf"):
            path = out_dir / f"{name}.{ext}"
            fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
            written.append(path)
        plt.close(fig)
    return written
