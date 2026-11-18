"""Inputs of the LP: from the registry and the representative days to hourly arrays.

Time convention (spec Sect. 5.1): slot t = 1..T covers the clock interval [t-1, t). Work
shifts from ``shift_start`` to ``shift_end`` are the slots shift_start+1 .. shift_end
(06:00-22:00 -> slots 7..22). A pick in slot t > c (cut-off, clock hour) is late by t - c.

Order groups (spec Sect. 5.3): the share of picks that arrive the evening before is
available at shift start (arrival slot = first shift slot); the rest arrives with the
parametric profile over [order_arrival_start, order_arrival_end). Each arrival group is
split into a predictable part (share sigma), whose release is anticipated by H hours but
never before the first shift slot, and a non-predictable part released at arrival.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from wpvrec import profiles
from wpvrec.days import RepresentativeDays
from wpvrec.params import Registry
from wpvrec.queueing import cuts
from wpvrec.units import HOURS_PER_DAY, PERCENT, WH_PER_KWH


@dataclass
class Group:
    """Orders arriving in the same slot, predictable or not."""

    name: str
    arrival: int  # slot in which the orders arrive (actual arrival, used in V4)
    release: int  # first slot in which they may be picked (anticipated if predictable)
    n: float  # picks
    predictable: bool


@dataclass
class DayInputs:
    pv: np.ndarray  # kWh produced in each slot
    u: np.ndarray  # inbound storage missions in each slot (fixed)
    h: np.ndarray  # dock workload, forklift-hours in each slot
    pf: np.ndarray  # fixed loads, kWh in each slot
    chi: np.ndarray  # 1 if charging is allowed in the slot


@dataclass
class ModelInputs:
    T: int
    shift: list[int]  # slots of the work shifts
    cutoff: int  # clock hour of the shipping cut-off
    days: list[DayInputs]
    weights: np.ndarray  # w_d, working days represented by each day
    groups: list[Group]
    n_repl: float
    n_reslot: float
    kappa: float
    s0: float
    smin: float
    bmax: float
    capacity: float  # C, missions/h
    rho_max: float
    cut_list: list[tuple[float, float]]  # (a_l, b_l) of V6
    e_net_kwh: float  # net energy per mission
    n_forklifts: int
    k: float  # forklift consumption, kWh per hour of use
    q_cap: float  # battery capacity, kWh
    soc_min: float  # fraction of q_cap
    p_ch: float  # charger power, kW
    eta: float  # charging efficiency
    labels: list[str] = field(default_factory=list)  # names of the days (months)

    @property
    def D(self) -> int:
        return len(self.days)

    def prepick_potential(self) -> float:
        """Picks per day that may be picked before their arrival (release < arrival)."""
        return float(sum(g.n for g in self.groups if g.release < g.arrival))


def _slot_window(start: float, end: float) -> np.ndarray:
    return profiles.shape("uniform", start, end)


def order_groups(reg: Registry) -> list[Group]:
    v = reg.value
    first = int(v("shift_start")) + 1
    picks = v("n_picks")
    prev = picks * v("order_share_previous_evening") / PERCENT
    sigma = v("predictable_share") / PERCENT
    lead = int(v("prepick_lead"))
    shares = profiles.shape(
        str(v("order_profile_shape")),
        v("order_arrival_start"),
        v("order_arrival_end"),
        peak=v("order_peak_hour"),
        spread=v("order_spread"),
    )
    arrivals = [(first, prev)] + [
        (t, (picks - prev) * sh) for t, sh in zip(profiles.SLOTS, shares, strict=True) if sh > 0
    ]
    out = []
    for t, n in arrivals:
        t = int(t)
        out.append(Group(f"a{t}p", t, max(t - lead, first), n * sigma, True))
        out.append(Group(f"a{t}n", t, t, n * (1 - sigma), False))
    return [g for g in out if g.n > 0]


def inbound(reg: Registry) -> np.ndarray:
    v = reg.value
    shape = profiles.shape(
        str(v("inbound_profile_shape")),
        v("inbound_start"),
        v("inbound_end"),
        peak=v("inbound_peak_hour"),
        spread=v("inbound_spread"),
    )
    return v("n_inbound") * shape


def dock_workload(reg: Registry, u: np.ndarray) -> np.ndarray:
    """h_t: share proportional to inbound arrivals, rest uniform over the outbound window."""
    v = reg.value
    share_in = v("dock_share_inbound") / PERCENT
    out = _slot_window(v("dock_outbound_start"), v("dock_outbound_end"))
    h = v("dock_hours_total") * (share_in * u / u.sum() + (1 - share_in) * out)
    if np.any(h > v("n_forklifts")):
        raise ValueError(
            f"dock workload exceeds the {int(v('n_forklifts'))} forklifts in some hour: "
            f"max {h.max():.2f}; change dock_* or forklift parameters"
        )
    return h


def fixed_loads(reg: Registry, shift_mask: np.ndarray, month: int, elmas=None) -> np.ndarray:
    """P^f_t [kWh per slot]: flat in shifts (default) or ELMAS shape with the same daily energy."""
    v = reg.value
    in_shift = v("avsrs_standby_kw") + v("lighting_kw") + v("offices_kw") + v("other_kw")
    flat = np.where(shift_mask, in_shift, v("offshift_standby_kw")).astype(float)
    if v("fixed_load_shape") == "flat":
        return flat
    if elmas is None:
        raise ValueError("ELMAS shapes are needed for fixed_load_shape != 'flat'")
    s = elmas[(elmas["cluster"] == int(v("elmas_cluster_warehouse"))) & (elmas["month"] == month)]
    s = s[s["day_type"] == "working"][[str(t) for t in profiles.SLOTS]].to_numpy()[0]
    return flat.sum() * s / s.sum()


def build(reg: Registry, rep: RepresentativeDays, elmas=None) -> ModelInputs:
    v = reg.value
    T = HOURS_PER_DAY
    shift = list(range(int(v("shift_start")) + 1, int(v("shift_end")) + 1))
    mask = np.isin(profiles.SLOTS, shift)
    chi = mask.astype(float) if v("charging_hours") == "shifts" else np.ones(T)
    u = inbound(reg)
    h = dock_workload(reg, u)
    days = [
        DayInputs(pv=rep.pv[m], u=u, h=h, pf=fixed_loads(reg, mask, m + 1, elmas), chi=chi)
        for m in range(len(rep.pv))
    ]
    capacity = v("capacity_c")
    breaks = list(v("queue_breakpoints"))
    if len(breaks) - 1 != int(v("n_pwl_cuts")):
        raise ValueError("queue_breakpoints must have n_pwl_cuts + 1 values")
    return ModelInputs(
        T=T,
        shift=shift,
        cutoff=int(v("cutoff_hour")),
        days=days,
        weights=np.asarray(rep.weights, dtype=float),
        groups=order_groups(reg),
        n_repl=v("n_replenishment"),
        n_reslot=v("n_reslotting"),
        kappa=v("kappa"),
        s0=v("stock_initial"),
        smin=v("stock_min"),
        bmax=v("buffer_max"),
        capacity=capacity,
        rho_max=v("rho_max"),
        cut_list=cuts(capacity, v("rho_max"), breaks),
        e_net_kwh=v("e_mission_net") / WH_PER_KWH,
        n_forklifts=int(v("n_forklifts")),
        k=v("forklift_kwh_per_h"),
        q_cap=v("battery_kwh"),
        soc_min=v("soc_min") / PERCENT,
        p_ch=v("charger_kw"),
        eta=v("charge_efficiency"),
        labels=[f"m{m + 1:02d}" for m in range(len(rep.pv))],
    )
