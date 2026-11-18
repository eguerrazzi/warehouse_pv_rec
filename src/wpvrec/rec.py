"""Ex-post Renewable Energy Community evaluation: shared energy, premium tariff,
incentive split with the enterprise cap theta (specification Section 6.1).

The REC does not change the decisions; it changes the value of the PV the warehouse does
not use. For every hour of the 12 representative working days (weights w_d) and of the
12 representative non-working days (stand-by only):

    Sh_t  = min(x_t, W_t)                      shared energy, W_t = other members' load
    TIP_t = fixed + min(cap, max(0, ref - Pz_t)) + regional bonus     [EUR/MWh]
    incentive = sum (TIP_t + pi_ARERA) Sh_t;   export revenue = sum Pz_t x_t (both cases)

Enterprise cap (DM 414/2023, flagged for Ema): the premium on the shared energy above
theta (55%) of the reference energy goes only to non-enterprise members or to social
purposes. Reference energy = energy fed into the grid by the REC plant (``theta_basis =
export``, reading of the decree summaries) or the shared energy itself (``shared``, the
literal text of the spec). Checked on annual totals. The warehouse receives beta of the
incentive, but never more premium than the enterprise-eligible premium (the other
enterprise members are assumed to receive no premium; the ARERA valorisation is not
capped). With ``rec_member_set = enterprises only`` the same cap applies and the excess
goes to social purposes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from wpvrec.days import RepresentativeDays
from wpvrec.params import Registry
from wpvrec.units import HOURS_PER_DAY, KWH_PER_MWH, PERCENT

ENTERPRISES_ONLY = "enterprises only"


def tip(price: np.ndarray, reg: Registry) -> np.ndarray:
    """Premium tariff [EUR/MWh] for the hourly zonal price ``price`` [EUR/MWh]."""
    v = reg.value
    var = np.minimum(v("tip_var_cap"), np.maximum(0.0, v("tip_var_reference") - price))
    return v("tip_fixed") + var + v("tip_regional_bonus")


def other_members(rep: RepresentativeDays, reg: Registry) -> tuple[np.ndarray, np.ndarray]:
    """Hourly load of the members other than the warehouse, (12, 24) working and non-working."""
    if str(reg.value("rec_member_set")) == ENTERPRISES_ONLY:
        return rep.business_working, rep.business_non_working
    return (
        rep.household_working + rep.business_working,
        rep.household_non_working + rep.business_non_working,
    )


def nonworking_export(rep: RepresentativeDays, standby_kw: float) -> np.ndarray:
    """PV exported on non-working days [kWh per slot], (12, 24): PV minus the stand-by use."""
    return rep.pv - np.minimum(rep.pv, standby_kw)


def hourly(plan: pd.DataFrame, rep: RepresentativeDays, reg: Registry,
           export_nw: np.ndarray | None = None) -> pd.DataFrame:  # fmt: skip
    """One row per (day type, month, slot): export x, other load W, shared, price, TIP, weight."""
    w_work, w_nw = other_members(rep, reg)
    if export_nw is None:
        export_nw = nonworking_export(rep, reg.value("offshift_standby_kw"))
    rows = []
    for (d, t), r in plan.set_index(["day", "slot"]).iterrows():
        rows.append(("working", d, t, r["weight"], r["x"], w_work[d, t - 1],
                     rep.price_working[d, t - 1]))  # fmt: skip
    for d in range(len(rep.non_working)):
        for t in range(1, HOURS_PER_DAY + 1):
            rows.append(("non_working", d, t, rep.non_working[d], export_nw[d, t - 1],
                         w_nw[d, t - 1], rep.price_non_working[d, t - 1]))  # fmt: skip
    h = pd.DataFrame(rows, columns=["day_type", "day", "slot", "weight", "x", "W", "price"])
    h["shared"] = np.minimum(h["x"], h["W"])
    h["tip"] = tip(h["price"].to_numpy(), reg)
    return h


def evaluate(plan: pd.DataFrame, rep: RepresentativeDays, reg: Registry) -> dict:
    """Annual REC indicators for one plan of the warehouse (the only producer)."""
    v = reg.value
    h = hourly(plan, rep, reg)
    w = h["weight"]
    export = float((h["x"] * w).sum())
    shared = float((h["shared"] * w).sum())
    tip_eur = float((h["tip"] * h["shared"] * w).sum()) / KWH_PER_MWH
    arera_eur = v("pi_arera") * shared / KWH_PER_MWH
    revenue = float((h["price"] * h["x"] * w).sum()) / KWH_PER_MWH
    return {
        "export_kwh": export,
        "shared_kwh": shared,
        "shared_non_working_kwh": float((h["shared"] * w)[h["day_type"] == "non_working"].sum()),
        "shared_share_of_export_pct": PERCENT * shared / export if export > 0 else 0.0,
        "export_revenue_eur": revenue,
        "tip_eur": tip_eur,
        "arera_eur": arera_eur,
        "incentive_eur": tip_eur + arera_eur,
        **split(tip_eur, arera_eur, shared, export, reg),
    }


def split(tip_eur: float, arera_eur: float, shared: float, export: float, reg: Registry) -> dict:
    """Warehouse share of the incentive with the enterprise cap (annual totals)."""
    v = reg.value
    theta = v("theta_enterprise") / PERCENT
    basis = str(v("theta_basis"))
    if basis == "export":
        eligible = min(shared, theta * export)
    elif basis == "shared":
        eligible = theta * shared
    else:
        raise ValueError(f"unknown theta_basis {basis!r}")
    tip_enterprises = tip_eur * eligible / shared if shared > 0 else 0.0
    beta = v("beta_warehouse") / PERCENT
    tip_wh = min(beta * tip_eur, tip_enterprises)
    return {
        "tip_enterprise_eligible_eur": tip_enterprises,
        "tip_non_enterprise_or_social_eur": tip_eur - tip_enterprises,
        "warehouse_incentive_eur": tip_wh + beta * arera_eur,
        "warehouse_cap_binding": bool(beta * tip_eur > tip_enterprises),
    }
