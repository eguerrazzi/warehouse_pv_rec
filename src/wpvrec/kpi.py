"""Common indicators computed identically for every plan (specification Section 5.9).

PV used, self-consumption and self-sufficiency (annual, with the non-working days);
energy imported and exported; lateness, pallets after the cut-off and queue time; delay
cost per kWh (shadow price, front points only); energy cost when the retail price exists.
REC indicators (``rec.evaluate``, prefix ``rec_``): export, shared energy, export revenue,
incentive and the warehouse share (with the enterprise cap).
"""

from __future__ import annotations

from wpvrec import balances, rec
from wpvrec.days import RepresentativeDays
from wpvrec.model import solve
from wpvrec.model.inputs import ModelInputs
from wpvrec.params import ProvenanceGateError, Registry
from wpvrec.units import KWH_PER_MWH


def kpis(m, inp: ModelInputs, rep: RepresentativeDays, reg: Registry, shadow_price=None,
         plan=None) -> dict:  # fmt: skip
    r = solve.result(m)
    plan = balances.plan_frame(m, inp) if plan is None else plan
    ann = balances.annual_summary(plan, rep, reg.value("offshift_standby_kw"))
    w = plan["weight"]
    out = {
        "F1_kwh": ann["self_consumed_working_kwh"],  # s = min(PV, E), spec V9
        "F2_missions_h": r.F2,
        "F2_late": r.F2_late,
        "F2_queue": r.F2_queue,
        "pallets_after_cutoff": float((plan["late_picks"] * w).sum()),
        "prepicks_per_yr": float((plan["prepicks"] * w).sum()),
        "pv_kwh": ann["pv_kwh"],
        "pv_used_kwh": ann["self_consumed_kwh"],
        "self_consumption_pct": ann["self_consumption_pct"],
        "self_sufficiency_pct": ann["self_sufficiency_pct"],
        "import_kwh": ann["import_kwh"],
        "export_kwh": ann["export_kwh"],
        "delay_cost_per_kwh": shadow_price,
    }
    try:
        price = reg.value("retail_price")  # EUR/MWh
        out["energy_cost_eur"] = ann["import_kwh"] / KWH_PER_MWH * price
    except ProvenanceGateError:
        out["energy_cost_eur"] = None
    out |= {f"rec_{k}": val for k, val in rec.evaluate(plan, rep, reg).items()}
    return out
