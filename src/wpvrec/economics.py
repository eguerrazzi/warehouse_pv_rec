"""Economic analysis of plant conditions B (PV to be installed) and C (joining an
external REC), specification Section 6.2. Constant prices (real discount rate).

**B, PV to be installed.** Investment I = pv_cost x kWp x (1 - investment incentive).
Annual cash flow = PV self-consumed x retail price (avoided purchase) + export x Pz
(dedicated withdrawal) + warehouse share of the REC incentive (with REC only)
- (O&M + insurance) x kWp. Output: simple payback, NPV over the useful life at the
discount rate, IRR. Prices of the reference year are kept constant (no PV degradation, no
price escalation: neither is in the registry).

**C, no own PV, member of someone else's REC.** The external plant (``ext_plant_kwp``,
same site and profile) feeds all its energy into the grid; the members' shared energy is
Sh_t = min(X_ext_t, W_wh_t + W_others_t). The REC returns ``c_consumer_share`` of the
incentive to the consumers, pro rata to each one's contribution to the shared energy in
the hour; the warehouse is an enterprise, so its premium is capped as in ``rec.split``.
Benefit = warehouse share - membership fee. The warehouse's own load profile is the one of
the plan given (e.g. P0 or the optimum), so the value of scheduling is visible in C too.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from wpvrec import rec
from wpvrec.days import RepresentativeDays
from wpvrec.params import Registry
from wpvrec.units import KWH_PER_MWH, PERCENT


def npv(rate: float, invest: float, flow: float, years: int) -> float:
    t = np.arange(1, years + 1)
    return float(-invest + (flow / (1 + rate) ** t).sum())


def irr(invest: float, flow: float, years: int) -> float | None:
    """Internal rate of return of a constant annual flow; None if it does not exist.

    NPV = 0 is a polynomial in u = 1 / (1 + r): flow (u + ... + u^n) - invest = 0; its
    root in (0, 1) gives r > 0 (one sign change: at most one positive root).
    """
    if flow <= 0 or flow * years <= invest:
        return None
    roots = np.roots([flow] * years + [-invest])
    u = [z.real for z in roots if abs(z.imag) < np.sqrt(np.finfo(float).eps) and 0 < z.real < 1]
    return 1 / max(u) - 1 if u else None


def condition_b(self_consumed_kwh: float, rec_result: dict, reg: Registry,
                investment_incentive_pct: float | None = None) -> dict:  # fmt: skip
    """Condition B for one plan: ``self_consumed_kwh`` annual (working + non-working days),
    ``rec_result`` from ``rec.evaluate`` (export, revenue, warehouse incentive)."""
    v = reg.value
    kwp = v("pv_kwp")
    inc = (
        v("investment_incentive") if investment_incentive_pct is None else investment_incentive_pct
    )
    invest = v("pv_cost") * kwp * (1 - inc / PERCENT)
    savings = self_consumed_kwh / KWH_PER_MWH * v("retail_price")
    costs = (v("pv_om") + v("pv_insurance")) * kwp
    years = int(v("pv_life"))
    rate = v("discount_rate") / PERCENT
    out = {
        "investment_incentive_pct": inc,
        "investment_eur": invest,
        "savings_eur": savings,
        "export_revenue_eur": rec_result["export_revenue_eur"],
        "om_insurance_eur": costs,
    }
    for case, extra in (("no_rec", 0.0), ("rec", rec_result["warehouse_incentive_eur"])):
        flow = savings + rec_result["export_revenue_eur"] + extra - costs
        r = irr(invest, flow, years)
        out |= {
            f"{case}_annual_flow_eur": flow,
            f"{case}_payback_yr": invest / flow if flow > 0 else None,
            f"{case}_npv_eur": npv(rate, invest, flow, years),
            f"{case}_irr_pct": PERCENT * r if r is not None else None,
        }
    return out


def condition_c(plan: pd.DataFrame, rep: RepresentativeDays, reg: Registry) -> dict:
    """Condition C for the warehouse load of ``plan`` (columns day, slot, weight, E)."""
    v = reg.value
    scale = v("ext_plant_kwp") / v("pv_kwp")
    ext = plan[["day", "slot", "weight"]].copy()
    ext["x"] = plan["pv"] * scale  # external plant: all its energy is fed in
    standby = v("offshift_standby_kw")
    h = rec.hourly(ext, rep, reg, export_nw=rep.pv * scale)
    wh_work = plan.set_index(["day", "slot"])["E"]
    wh = np.where(h["day_type"] == "working",
                  [wh_work.get((d, t), 0.0) for d, t in zip(h["day"], h["slot"], strict=True)],
                  standby)  # fmt: skip
    h["W"] = h["W"] + wh
    h["shared"] = np.minimum(h["x"], h["W"])
    share_wh = np.divide(wh, h["W"], out=np.zeros(len(h)), where=h["W"] > 0)
    w = h["weight"]
    shared = float((h["shared"] * w).sum())
    shared_wh = float((h["shared"] * share_wh * w).sum())
    export = float((h["x"] * w).sum())
    tip_all = float((h["tip"] * h["shared"] * w).sum()) / KWH_PER_MWH
    tip_wh_raw = float((h["tip"] * h["shared"] * share_wh * w).sum()) / KWH_PER_MWH
    arera_wh = v("pi_arera") * shared_wh / KWH_PER_MWH
    c = v("c_consumer_share") / PERCENT
    # enterprise cap on the premium, as in rec.split (the warehouse is the enterprise here)
    cap = rec.split(tip_all, 0.0, shared, export, reg)["tip_enterprise_eligible_eur"]
    tip_wh = min(c * tip_wh_raw, cap)
    benefit = tip_wh + c * arera_wh - v("rec_fee")
    return {
        "ext_export_kwh": export,
        "shared_kwh": shared,
        "warehouse_shared_kwh": shared_wh,
        "warehouse_incentive_eur": tip_wh + c * arera_wh,
        "rec_fee_eur": v("rec_fee"),
        "benefit_eur": benefit,
    }
