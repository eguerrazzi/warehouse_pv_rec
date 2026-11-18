"""Isometric 3D illustration of the case study (exploded axonometric view, not to scale).

The roof with the PV array is lifted above the building and the two walls facing the
viewer are cut away, so that the AVS/RS, the picking area, the docks, the forklifts and the
offices are visible. Labels read the registry. Run ``wpvrec figures illustration``.

Projection: (x, y, z) -> (X, Y) = ((x - y) cos 30, (x + y) sin 30 + z). The viewer stands at
the corner x = y = 0: faces at the minimum x and minimum y of a box, and its top, are
visible; objects are drawn from the farthest (largest x + y) to the nearest.
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import to_rgb  # noqa: E402
from matplotlib.patches import FancyArrowPatch, Polygon  # noqa: E402

from wpvrec.figures.schematics import (  # noqa: E402
    AQUA,
    BLUE,
    INK,
    INK2,
    MUTED,
    ORANGE,
    OUT_DIR,
    VIOLET,
    YELLOW,
)
from wpvrec.params import Registry, load_registry  # noqa: E402

C30, S30 = math.cos(math.radians(30)), math.sin(math.radians(30))
WALL, FLOOR, ROOF = "#e9e7e1", "#f4f3ef", "#d9d7cf"
PALLET, PANEL, STEEL = "#d8b98a", "#1f3d66", "#8d8b85"


def iso(x, y, z=0.0):
    return ((x - y) * C30, (x + y) * S30 + z)


def shade(color, f):
    r, g, b = to_rgb(color)
    return (r * f, g * f, b * f)


class Scene:
    def __init__(self, ax):
        self.ax = ax
        self.z = 1.0

    def quad(self, pts, fc, ec="white", lw=0.4, alpha=1.0, ls="-"):
        self.ax.add_patch(
            Polygon(
                [iso(*p) for p in pts],
                closed=True,
                fc=fc,
                ec=ec,
                lw=lw,
                alpha=alpha,
                ls=ls,
                zorder=self.z,
                joinstyle="round",
            )  # fmt: skip
        )
        self.z += 0.01

    def box(self, x, y, z, dx, dy, dz, color, ec="white", lw=0.4, alpha=1.0, top=True):
        """Box with its visible faces: x-face (x = x0), y-face (y = y0) and top."""
        self.quad([(x, y, z), (x, y + dy, z), (x, y + dy, z + dz), (x, y, z + dz)],
                  shade(color, 0.86), ec, lw, alpha)  # fmt: skip
        self.quad([(x, y, z), (x + dx, y, z), (x + dx, y, z + dz), (x, y, z + dz)],
                  shade(color, 0.72), ec, lw, alpha)  # fmt: skip
        if top:
            self.quad([(x, y, z + dz), (x + dx, y, z + dz), (x + dx, y + dy, z + dz),
                       (x, y + dy, z + dz)], color, ec, lw, alpha)  # fmt: skip

    def line(self, p0, p1, color=INK2, lw=0.8, ls="-", alpha=1.0):
        (a, b), (c, d) = iso(*p0), iso(*p1)
        self.ax.plot([a, c], [b, d], color=color, lw=lw, ls=ls, alpha=alpha, zorder=self.z,
                     solid_capstyle="round")  # fmt: skip
        self.z += 0.01

    def house(self, x, y, w, d, h, color, roof="#b5543c"):
        """Gabled house; ridge along x."""
        self.box(x, y, 0, w, d, h, color, top=False)
        r = h + d * 0.45
        # roof slope facing -y, gable triangle at x = x0
        self.quad([(x, y, h), (x + w, y, h), (x + w, y + d / 2, r), (x, y + d / 2, r)],
                  shade(roof, 0.85))  # fmt: skip
        self.quad([(x, y, h), (x, y + d / 2, r), (x, y + d, h)], shade(color, 0.86))
        self.quad([(x, y + d / 2, r), (x + w, y + d / 2, r), (x + w, y + d, h), (x, y + d, h)],
                  roof)  # fmt: skip

    def text(self, p, s, dx=0.0, dy=0.0, fs=8, color=INK, ha="center", weight="normal", bg=True):
        X, Y = iso(*p)
        self.ax.text(
            X + dx,
            Y + dy,
            s,
            fontsize=fs,
            color=color,
            ha=ha,
            va="center",
            weight=weight,
            zorder=200,
            bbox=dict(fc="white", ec="none", alpha=0.85, pad=1.2) if bg else None,
        )

    def label(self, p, s, dx, dy, fs=8, ha="left"):
        """Text with a leader line to point p."""
        X, Y = iso(*p)
        self.ax.plot([X, X + dx], [Y, Y + dy], color=INK2, lw=0.6, zorder=199)
        self.ax.plot([X], [Y], marker="o", ms=2.5, color=INK2, zorder=199)
        off = 0.4 if ha == "left" else -0.4
        self.ax.text(X + dx + off, Y + dy, s, fontsize=fs, color=INK, ha=ha, va="center",
                     zorder=200)  # fmt: skip

    def arrow(self, p0, p1, color, lw=2.6, ls="-", rad=0.0):
        self.ax.add_patch(
            FancyArrowPatch(iso(*p0), iso(*p1), arrowstyle="-|>", mutation_scale=15, lw=lw,
                            color=color, ls=ls, connectionstyle=f"arc3,rad={rad}", zorder=150)
        )  # fmt: skip


def overview(reg: Registry):
    v = reg.value
    fig, ax = plt.subplots(figsize=(12, 11))
    ax.set_aspect("equal")
    ax.axis("off")
    s = Scene(ax)
    L, W, H = 44.0, 28.0, 11.0  # building footprint and height

    # ground and yard
    s.quad([(-4, -19, 0), (80, -19, 0), (80, 40, 0), (-4, 40, 0)], "#f6f6f2", ec="none")
    s.quad([(24, -18, 0), (L + 1, -18, 0), (L + 1, -1, 0), (24, -1, 0)], "#e4e3dd", ec="none")

    # REC members behind and to the right (farthest first)
    for i, (hx, hy) in enumerate([(72, 31), (65, 31), (72, 23), (65, 23), (58, 31), (72, 15)]):
        s.house(hx, hy, 5, 5, 3.2, "#f2ead9" if i % 2 else "#ece4d2")
    s.box(57, 21, 0, 6, 5, 3.6, "#cfe0f3")  # office
    s.box(57, 13, 0, 6, 5, 3.0, "#f6d8c5")  # bar
    s.box(65, 6, 0, 7, 5, 3.4, "#d7ecd9")  # shop

    # building: far walls (inner sides) and floor
    s.quad([(0, W, 0), (L, W, 0), (L, W, H), (0, W, H)], WALL, ec="#c9c7bf", lw=0.8)
    s.quad([(L, 0, 0), (L, W, 0), (L, W, H), (L, 0, H)], shade(WALL, 0.93), ec="#c9c7bf", lw=0.8)
    s.quad([(0, 0, 0), (L, 0, 0), (L, W, 0), (0, W, 0)], FLOOR, ec="#c9c7bf", lw=0.8)

    # offices in the back corner, picking area, chargers
    s.box(31, 22, 0, 12, 5.5, 4.2, "#dde6f0", ec="#b6c2cf")
    for i in range(3):
        s.box(30 + i * 4.3, 12, 0, 3.3, 6.5, 2.4, "#cfcbbf", ec="#a9a69c", lw=0.4)
        s.box(30.3 + i * 4.3, 12.4, 2.4, 2.7, 2.6, 1.2, PALLET)
    s.box(41, 5, 0, 2.4, 5, 2.4, "#4e5d6c")

    # AVS/RS: far lane block, shuttles in the aisle, near lane block translucent, two lifts
    rx0, rx1, rz = 4.0, 25.0, 9.0
    tiers = int(v("n_tiers"))
    lane_a, aisle, lane_b = (5.0, 11.5), (11.5, 14.0), (14.0, 20.5)
    s.box(rx1, aisle[0], 0, 2.2, aisle[1] - aisle[0], rz + 1.4, "#a9a69c")  # inbound lift

    def lanes(y0, y1, alpha):
        s.box(rx0, y0, 0, rx1 - rx0, y1 - y0, rz, "#c9c6bd", ec="#9c9a93", lw=0.5, alpha=alpha)
        for k in range(tiers):
            zz = k * rz / tiers
            if k:
                s.line((rx0, y0, zz), (rx0, y1, zz), "#8f8d86", 0.7, alpha=alpha)
                s.line((rx0, y0, zz), (rx1, y0, zz), "#8f8d86", 0.7, alpha=alpha)
            for j in range(9):
                if (j + 2 * k) % 3:
                    s.box(rx0 + 0.6 + j * 2.25, y0 - 0.01, zz + 0.15, 1.5, 0.01, rz / tiers * 0.62,
                          PALLET, ec="none", top=False, alpha=alpha)  # fmt: skip
            for j in range(3):  # lane cross-section on the end face
                if (j + k) % 2 == 0:
                    s.box(rx0 - 0.01, y0 + 0.4 + j * 2.0, zz + 0.15, 0.01, 1.6, rz / tiers * 0.62,
                          PALLET, ec="none", top=False, alpha=alpha)  # fmt: skip

    lanes(*lane_b, 1.0)
    for k in range(tiers):  # one shuttle per tier, at different channels
        sx = rx0 + 2 + (k * 4.3) % 16
        s.box(sx, aisle[0] + 0.25, k * rz / tiers + 0.1, 2.2, aisle[1] - aisle[0] - 0.5, 0.8,
              VIOLET, ec="white")  # fmt: skip
    lanes(*lane_a, 0.42)
    s.box(rx0 - 2.4, aisle[0], 0, 2.2, aisle[1] - aisle[0], rz + 1.4, "#a9a69c")  # outbound lift

    # forklifts near the docks
    for k in range(int(v("n_forklifts"))):
        fx, fy = 27.5 + k * 3.6, 3.0 + (k % 2) * 2.6
        s.box(fx, fy, 0, 2.0, 1.2, 1.3, AQUA)
        s.line((fx, fy, 1.3), (fx, fy, 3.3), INK2, 1.6)
        s.box(fx - 1.4, fy + 0.1, 0.3, 1.2, 1.0, 0.9, PALLET)

    # cut-away near walls (outlines) and dock doors on the near long wall
    for p0, p1 in [((0, 0, 0), (L, 0, 0)), ((0, 0, 0), (0, W, 0)), ((0, 0, H), (L, 0, H)),
                   ((0, 0, H), (0, W, H)), ((0, 0, 0), (0, 0, H)), ((L, 0, 0), (L, 0, H)),
                   ((0, W, 0), (0, W, H))]:  # fmt: skip
        s.line(p0, p1, "#9c9a93", 1.0, "--")
    for dx in (29.0, 36.0):
        s.quad([(dx, 0, 0), (dx + 5, 0, 0), (dx + 5, 0, 4.5), (dx, 0, 4.5)], "#b9c3cc",
               ec="#8a96a1", alpha=0.6)  # fmt: skip

    # trucks at the docks
    for tx in (29.2, 36.2):
        s.box(tx, -12.5, 0.6, 4.6, 11.5, 4.0, "#f3f2ee", ec="#b9b7b0")
        s.box(tx + 0.4, -15.7, 0.4, 3.8, 3.0, 2.8, "#7c8a99")

    # meter and grid
    s.box(48, -3, 0, 1.6, 1.0, 2.2, "#ffffff", ec=INK2, lw=0.8)
    px, py = 54.0, -12.0
    for a, b in [
        ((px - 1.2, py - 1.2, 0), (px, py, 13)),
        ((px + 1.2, py + 1.2, 0), (px, py, 13)),
        ((px - 1.2, py + 1.2, 0), (px, py, 13)),
        ((px + 1.2, py - 1.2, 0), (px, py, 13)),
        ((px - 3, py, 10), (px + 3, py, 10)),
        ((px - 2.2, py, 7), (px + 2.2, py, 7)),
    ]:
        s.line(a, b, "#6f6d67", 1.1)  # fmt: skip

    # exploded roof with the PV array, lifted to clear the interior
    rz0 = 44.0
    for cx, cy in ((0, 0), (L, 0), (0, W), (L, W)):
        s.line((cx, cy, H), (cx, cy, rz0), "#b9b7b0", 0.7, ":")
    s.quad([(0, 0, rz0), (L, 0, rz0), (L, W, rz0), (0, W, rz0)], ROOF, ec="#b0aea6", lw=0.8)
    for i in range(6):
        for j in range(10):
            x0, y0 = 4 + j * 3.7, 3 + i * 3.9
            s.quad([(x0, y0, rz0 + 0.05), (x0 + 3.2, y0, rz0 + 0.05),
                    (x0 + 3.2, y0 + 2.6, rz0 + 0.6), (x0, y0 + 2.6, rz0 + 0.6)],
                   PANEL, ec="#6f8db3", lw=0.5)  # fmt: skip

    # energy flows
    s.arrow((L, 2, rz0 - 0.5), (48.8, -2.5, 2.8), YELLOW, rad=-0.12)
    s.arrow((47.6, -2.6, 1.1), (42, 3, 1.0), BLUE)
    s.arrow((49.8, -3.4, 1.6), (px - 0.6, py + 1.4, 9.0), ORANGE, rad=0.25)
    s.arrow((px + 1.0, py + 2.0, 11.0), (57, 15, 5.0), ORANGE, ls="--", rad=-0.2)

    # sun
    sx, sy = iso(-6, 30, 52)
    ax.add_patch(plt.Circle((sx, sy), 2.2, color=YELLOW, zorder=5))
    for k in range(12):
        a = k * math.pi / 6
        ax.plot([sx + 2.8 * math.cos(a), sx + 3.9 * math.cos(a)],
                [sy + 2.8 * math.sin(a), sy + 3.9 * math.sin(a)], color=YELLOW, lw=1.6)  # fmt: skip

    # numbered markers on the objects, explained in the key below the scene
    items = [
        ((22, 14, rz0 + 0.6), f"Rooftop PV, {v('pv_kwp'):g} kWp (roof lifted to show the inside)"),
        ((rx0 + 6, lane_a[0], rz * 0.55),
         f"AVS/RS: {int(v('n_tiers'))} tiers, {v('missions_per_day'):,.0f} missions/day, "
         f"C = {v('capacity_c'):.0f}/h"),
        ((rx0 + 13, aisle[0] + 0.5, rz * 0.8 + 1.0), "Shuttle + satellite, one per tier"),
        ((rx0 - 1.3, aisle[0], rz + 2.6), "Outbound lift (picking, replenishment)"),
        ((rx1 + 1.1, aisle[0], rz + 2.6), "Inbound lift (storage of incoming pallets)"),
        ((37, 24, 5.6), "Offices, IT, lighting: fixed loads"),
        ((34, 15, 5.2), "Picking area (forward stock)"),
        ((42.2, 7.5, 3.6), f"Chargers, {v('charger_kw'):g} kW per forklift"),
        ((31, 4.5, 4.4), f"{int(v('n_forklifts'))} Li-ion forklifts serving the docks"),
        ((33, -7, 6.0), "Trucks at the docks (inbound and outbound)"),
        ((48.8, -2.5, 3.6), "Site meter: PV used, exported, imported each hour"),
        ((px, py, 14.6), "Public grid"),
        ((66, 27, 8.0), f"Renewable Energy Community: {int(v('n_households'))} households, "
         "bar, shop, office"),
    ]  # fmt: skip
    for n, (pt, _) in enumerate(items, 1):
        X, Y = iso(*pt)
        ax.add_patch(plt.Circle((X, Y), 1.55, fc="white", ec=INK, lw=1.0, zorder=300))
        ax.text(X, Y, str(n), ha="center", va="center", fontsize=8 if n < 10 else 6.5,
                weight="bold", color=INK,
                zorder=301)  # fmt: skip
    kx, ky = -30.0, -18.0
    for n, (_, txt) in enumerate(items, 1):
        col, row = divmod(n - 1, 7)
        X, Y = kx + col * 52.0, ky - row * 2.6
        ax.add_patch(plt.Circle((X, Y), 1.05, fc="white", ec=INK, lw=0.8, zorder=300))
        ax.text(
            X,
            Y,
            str(n),
            ha="center",
            va="center",
            fontsize=6.5 if n < 10 else 5,
            weight="bold",
            zorder=301,
        )
        ax.text(X + 1.8, Y, txt, fontsize=7.8, va="center", color=INK, zorder=301)

    # flow legend
    lgx, lgy = -54.0, 50.0
    for k, (col, ls, txt) in enumerate([
        (YELLOW, "-", "PV production"),
        (BLUE, "-", "PV used on site (F1)"),
        (ORANGE, "-", "PV exported to the grid"),
        (ORANGE, "--", "shared energy in the REC (virtual)"),
    ]):  # fmt: skip
        yy = lgy - 2.4 * k
        ax.plot([lgx, lgx + 3.5], [yy, yy], color=col, lw=2.6, ls=ls, zorder=210)
        ax.text(lgx + 4.3, yy, txt, fontsize=8, va="center", color=INK, zorder=210)
    ax.set_title("The case study: a logistics SME with automated storage, rooftop PV and a REC",
                 loc="left", fontsize=11, color=INK)  # fmt: skip
    ax.text(0.0, 0.0, "Illustrative, not to scale. Numbers from the parameter registry.",
            transform=ax.transAxes, fontsize=7.5, color=MUTED)  # fmt: skip
    ax.autoscale_view()
    return fig


FIGURES = {"case_study_3d": overview}


def make_all(out_dir: Path = OUT_DIR, registry: Registry | None = None) -> list[Path]:
    reg = registry or load_registry()
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fn in FIGURES.items():
        fig = fn(reg)
        for ext in ("png", "pdf"):
            path = out_dir / f"{name}.{ext}"
            fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
            written.append(path)
        plt.close(fig)
    return written
