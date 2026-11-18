"""Phase 5: REC ex post (shared energy, premium tariff, enterprise cap) and economics B/C.

Small hand-made instances (placeholder numbers built here); the base registry provides the
regulatory constants, overridden where a test needs other values.
"""

import numpy as np
import pandas as pd
import pytest

from wpvrec import economics, rec
from wpvrec.data.common import PROCESSED
from wpvrec.days import RepresentativeDays
from wpvrec.params import load_registry


@pytest.fixture
def reg():
    r = load_registry()
    r.values |= {"tip_fixed": 80.0, "tip_var_reference": 180.0, "tip_var_cap": 40.0,
                 "tip_regional_bonus": 4.0, "pi_arera": 8.0, "theta_enterprise": 55.0,
                 "beta_warehouse": 50.0, "theta_basis": "export",
                 "rec_member_set": "50 households + 3 tertiary businesses",
                 "offshift_standby_kw": 1.0}  # fmt: skip
    return r


def one_month(pv, hh_w, hh_n, price=100.0, working=2, non_working=1):
    z = np.zeros((1, 24))
    cal = pd.DataFrame({"month": [1], "days": [working + non_working],
                        "working_days": [working], "non_working_days": [non_working]})  # fmt: skip
    return RepresentativeDays(
        year=2025, calendar=cal, pv=np.asarray(pv, float).reshape(1, 24),
        price_working=z + price, price_non_working=z + price,
        business_working=z, business_non_working=z,
        household_working=np.asarray(hh_w, float).reshape(1, 24),
        household_non_working=np.asarray(hh_n, float).reshape(1, 24),
    )  # fmt: skip


def plan_with_export(x, pv=None, E=None, weight=2):
    t = np.arange(1, 25)
    return pd.DataFrame({"day": 0, "slot": t, "weight": weight, "x": np.asarray(x, float),
                         "pv": np.asarray(pv if pv is not None else x, float),
                         "E": np.asarray(E if E is not None else np.zeros(24), float)})  # fmt: skip


def test_tip_formula(reg):
    assert rec.tip(np.array([100.0, 160.0, 200.0]), reg) == pytest.approx([124.0, 104.0, 84.0])


def test_shared_is_min_of_export_and_load_with_weekend(reg):
    x = np.zeros(24)
    x[11], x[12] = 10.0, 3.0
    load = np.zeros(24)
    load[11], load[12] = 4.0, 6.0
    pv_nw = np.zeros(24)
    pv_nw[12] = 6.0  # non-working day: 6 kWh, stand-by uses 1 -> 5 exported, load 6 -> 5 shared
    rep = one_month(pv_nw, load, load)
    h = rec.hourly(plan_with_export(x), rep, reg)
    assert (h.shared <= h.x + 1e-12).all() and (h.shared <= h.W + 1e-12).all()
    r = rec.evaluate(plan_with_export(x), rep, reg)
    assert r["shared_kwh"] == pytest.approx(2 * (4 + 3) + 1 * 5)  # weights 2 and 1
    assert r["shared_non_working_kwh"] == pytest.approx(5.0)
    assert r["export_kwh"] == pytest.approx(2 * 13 + 5)
    assert r["incentive_eur"] == pytest.approx(19 * (124 + 8) / 1000)
    assert r["export_revenue_eur"] == pytest.approx(31 * 100 / 1000)


def test_enterprise_cap_export_and_shared_basis(reg):
    s = rec.split(10.0, 1.0, shared=100.0, export=150.0, reg=reg)  # eligible min(100, 82.5)
    assert s["tip_enterprise_eligible_eur"] == pytest.approx(8.25)
    assert s["warehouse_incentive_eur"] == pytest.approx(5.0 + 0.5)
    assert not s["warehouse_cap_binding"]
    reg.values["beta_warehouse"] = 100.0
    s = rec.split(10.0, 1.0, shared=100.0, export=100.0, reg=reg)  # eligible 55 of 100
    assert s["warehouse_incentive_eur"] == pytest.approx(5.5 + 1.0)
    assert s["warehouse_cap_binding"]
    assert s["tip_non_enterprise_or_social_eur"] == pytest.approx(4.5)
    reg.values["theta_basis"] = "shared"
    s = rec.split(10.0, 0.0, shared=100.0, export=1000.0, reg=reg)
    assert s["tip_enterprise_eligible_eur"] == pytest.approx(5.5)


def test_enterprises_only_member_set(reg):
    reg.values["rec_member_set"] = rec.ENTERPRISES_ONLY
    rep = one_month(np.zeros(24), np.ones(24), np.ones(24))
    rep.business_working = np.full((1, 24), 0.25)
    w, _ = rec.other_members(rep, reg)
    assert w.sum() == pytest.approx(6.0)  # businesses only


def test_npv_irr_payback():
    assert economics.npv(0.0, 100.0, 10.0, 20) == pytest.approx(100.0)
    r = economics.irr(100.0, 10.0, 20)
    assert economics.npv(r, 100.0, 10.0, 20) == pytest.approx(0.0, abs=1e-8)
    assert 0.07 < r < 0.08  # annuity factor 10 over 20 years: about 7.75%
    assert economics.irr(100.0, 4.0, 20) is None  # never pays back


def test_condition_b_flows(reg):
    reg.values |= {"pv_kwp": 10.0, "pv_cost": 1000.0, "pv_om": 10.0, "pv_insurance": 0.0,
                   "pv_life": 20, "discount_rate": 0.0, "investment_incentive": 0.0}  # fmt: skip
    price = reg.value("retail_price")
    rec_res = {"export_revenue_eur": 100.0, "warehouse_incentive_eur": 50.0}
    b = economics.condition_b(10_000.0, rec_res, reg)
    flow = 10 * price + 100 - 100  # 10 MWh x retail price + export revenue - O&M
    assert b["no_rec_annual_flow_eur"] == pytest.approx(flow)
    assert b["rec_annual_flow_eur"] == pytest.approx(flow + 50)
    assert b["no_rec_payback_yr"] == pytest.approx(10_000 / flow)
    assert b["rec_npv_eur"] == pytest.approx(-10_000 + 20 * (flow + 50))
    b30 = economics.condition_b(10_000.0, rec_res, reg, investment_incentive_pct=30)
    assert b30["investment_eur"] == pytest.approx(7_000)


def test_condition_c_pro_rata(reg):
    reg.values |= {"ext_plant_kwp": 70.0, "pv_kwp": 70.0, "c_consumer_share": 50.0, "rec_fee": 10.0,
                   "beta_warehouse": 50.0}  # fmt: skip
    pv = np.zeros(24)
    pv[12] = 10.0
    hh = np.zeros(24)
    hh[12] = 2.0
    E = np.zeros(24)
    E[12] = 6.0  # warehouse 6 + households 2 = 8 < 10 exported by the external plant
    rep = one_month(np.zeros(24), hh, np.zeros(24))
    c = economics.condition_c(plan_with_export(np.zeros(24), pv=pv, E=E), rep, reg)
    assert c["shared_kwh"] == pytest.approx(2 * 8)
    assert c["warehouse_shared_kwh"] == pytest.approx(2 * 6)
    tip_wh = 0.5 * 12 * 124 / 1000  # well below the enterprise cap
    assert c["benefit_eur"] == pytest.approx(tip_wh + 0.5 * 12 * 8 / 1000 - 10)


@pytest.mark.skipif(not (PROCESSED / "pv_typical_year.csv").exists(), reason="run wpvrec data")
def test_base_case_rec_and_economics_small_grid():
    from wpvrec import study

    r = load_registry()
    r.values["pareto_points"] = 3
    st = study.front_study(r)
    f = st.front
    assert (f.rec_shared_kwh <= f.rec_export_kwh + 1e-6).all()
    assert (np.diff(f.rec_export_kwh) <= 1e-6).all()  # more F1, less export
    eb, ec = study.economics_study(st, r)
    assert (eb.rec_annual_flow_eur >= eb.no_rec_annual_flow_eur).all()
    assert set(ec.plan) == {"P0", "P1", "same_F2_as_P0"}
    assert (ec.warehouse_shared_kwh <= ec.shared_kwh + 1e-6).all()
