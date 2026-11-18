"""Phase 2: calendar, parametric profiles, data parsers (offline fixtures), representative days."""

import datetime as dt
import io
import json
import zipfile

import numpy as np
import pandas as pd
import pytest

from wpvrec import days, profiles
from wpvrec.data import calendar, elmas, gme, households, pvgis
from wpvrec.data.common import PROCESSED
from wpvrec.params import load_registry


# ---- calendar ------------------------------------------------------------------------------
def test_italian_calendar_2025():
    hol = calendar.italian_holidays(2025)
    assert dt.date(2025, 4, 21) in hol  # Easter Monday 2025
    assert len(hol) == 11
    table = calendar.month_table(2025)
    assert table["working_days"].sum() == 251  # 261 weekdays - 10 holidays on weekdays
    assert (table["working_days"] + table["non_working_days"] == table["days"]).all()


def test_french_calendar_2018():
    hol = calendar.french_holidays(2018)
    assert {dt.date(2018, 4, 2), dt.date(2018, 5, 10), dt.date(2018, 5, 21)} <= hol


# ---- profiles ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "kind,kw",
    [
        ("uniform", {}),
        ("truncated_normal", {"peak": 12.5, "spread": 2}),
        ("beta", {"a": 2, "b": 3}),
    ],
)
def test_shapes_sum_to_one_inside_window(kind, kw):
    s = profiles.shape(kind, 8, 13, **kw)
    assert s.sum() == pytest.approx(1)
    assert (s[:8] == 0).all() and (s[13:] == 0).all()  # slots 9..13 cover [8, 13)
    assert (s[8:13] > 0).all()


def test_uniform_shape_inbound():
    s = profiles.shape("uniform", 6, 14)
    assert np.allclose(s[6:14], 1 / 8)
    assert profiles.distribute(650, s)[6] == pytest.approx(81.25)


def test_truncated_normal_peaks_at_peak_slot():
    s = profiles.shape("truncated_normal", 7, 20, peak=12.5, spread=2)
    assert s.argmax() + 1 == 13  # slot 13 covers [12, 13); peak at 12.5 is shared 12-13


@pytest.mark.parametrize(
    "bad", [dict(start=10, end=10), dict(start=-1, end=5), dict(start=3, end=25)]
)
def test_shape_rejects_bad_window(bad):
    with pytest.raises(ValueError):
        profiles.shape("uniform", **bad)


# ---- PVGIS -------------------------------------------------------------------------------
def test_pvgis_utc_to_local_slots(tmp_path):
    rows = [
        {"time": "20230715:1010", "P": 500.0},  # 10:00-11:00 UTC = 12:00-13:00 CEST -> slot 13
        {"time": "20230115:1010", "P": 300.0},  # 10:00-11:00 UTC = 11:00-12:00 CET  -> slot 12
    ]
    f = tmp_path / "pvgis.json"
    f.write_text(json.dumps({"inputs": {"x": 1}, "outputs": {"hourly": rows}}))
    energy, _ = pvgis.parse(f)
    prof = pvgis.monthly_profile(energy)
    assert prof.loc[7, 13] == pytest.approx(0.5)  # kWh per kWp
    assert prof.loc[1, 12] == pytest.approx(0.3)
    assert prof.loc[7].sum() == pytest.approx(0.5)


def test_specific_yield_counts_days():
    prof = pd.DataFrame(1.0 / 24, index=range(1, 13), columns=range(1, 25))  # 1 kWh/kWp/day
    assert pvgis.specific_yield(prof, 2025) == pytest.approx(365)


# ---- GME ---------------------------------------------------------------------------------
def _gme_zip(path):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Prezzi-Prices"
    ws.append(["   Data/Date\n(YYYYMMDD)", "Ora\n/Hour", "PUN INDEX GME", "CNOR"])
    for h in range(1, 26):  # 2025-10-26 has 25 hours (end of DST); a Sunday
        ws.append([20251026, h, 100.0, 50.0 + h])
    for h in range(1, 25):  # 2025-10-27, Monday working day
        ws.append([20251027, h, 100.0, 10.0 * h])
    buf = io.BytesIO()
    wb.save(buf)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Anno 2025_12_60.xlsx", buf.getvalue())
        z.writestr("Anno 2025_12_15.xlsx", b"ignored")


def test_gme_hourly_and_profiles(tmp_path):
    f = tmp_path / "Anno2025.zip"
    _gme_zip(f)
    hourly = gme.read_hourly(f, "CNOR")
    assert len(hourly) == 48  # 25th hour dropped
    prof = gme.profiles(hourly)
    assert prof.loc[(10, "working"), 3] == pytest.approx(30.0)
    assert prof.loc[(10, "non_working"), 24] == pytest.approx(74.0)
    with pytest.raises(KeyError):
        gme.read_hourly(f, "XXXX")


# ---- ELMAS --------------------------------------------------------------------------------
def test_elmas_shapes_normalised(tmp_path):
    t = pd.date_range("2018-01-01", periods=24 * 14, freq="h")
    df = pd.DataFrame(
        {"Time": t.strftime("%Y-%m-%d %H:%M:%S"), "1": 2.0, "2": np.arange(len(t)) + 1.0}
    )
    csv = df.to_csv(sep=";", decimal=",", index=False)
    f = tmp_path / "elmas.zip"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("ELMAS_dataset/Time_series_18_clusters.csv", csv)
    sh = elmas.shapes(elmas.read_clusters(f))
    flat = sh.loc[(1, 1, "working")]
    assert np.allclose(flat, 1 / len(t))  # constant load: every hour has the same share
    assert set(sh.index.get_level_values("day_type")) == {"working", "non_working"}


# ---- households ---------------------------------------------------------------------------
def test_household_loader_single_shape(tmp_path):
    f = tmp_path / "hh.csv"
    pd.DataFrame({"slot": range(1, 25), "share": np.arange(1, 25)}).to_csv(f, index=False)
    s = households.load_shape(f)
    assert s.shape == (24, 24)
    assert np.allclose(s.sum(axis=1), 1)


def test_household_loader_rejects_unknown_layout(tmp_path):
    f = tmp_path / "hh.csv"
    pd.DataFrame({"hour": [1], "kw": [1]}).to_csv(f, index=False)
    with pytest.raises(ValueError, match="unknown household profile layout"):
        households.load_shape(f)


# ---- representative days (uses the committed processed profiles) --------------------------
@pytest.mark.skipif(not (PROCESSED / "pv_typical_year.csv").exists(), reason="run wpvrec data")
def test_representative_days():
    reg = load_registry()
    d = days.build(reg)
    assert d.pv.shape == (12, 24) and d.price_working.shape == (12, 24)
    assert d.weights.sum() == 251
    yield_ = d.annual_pv() / reg.value("pv_kwp")
    assert 1300 < yield_ < 1500  # PVGIS-SARAH3 Torrita di Siena: about 1,400 kWh/kWp
    assert d.pv[:, :5].sum() == 0  # no PV before 05:00 local
    assert d.annual_business() == pytest.approx(3 * 20_000, rel=0.01)
    assert d.annual_households() == pytest.approx(50 * 2700, rel=1e-4)


def test_household_bottom_up_annual_and_shape():
    reg = load_registry()
    cal = calendar.month_table(int(reg.value("calendar_year")))
    df, rep = households.bottom_up(reg, cal)
    per_day = df.set_index(["month", "day_type"]).sum(axis=1)
    annual = sum(per_day.loc[(1, d)] * cal[f"{d}_days"].sum() for d in households.DAY_TYPES)
    assert annual == pytest.approx(reg.value("household_kwh"))
    assert (df.drop(columns=["month", "day_type"]).to_numpy() > 0).all()  # base load
    # occupants away 08-17 on working days (Nazemi), at home on non-working days
    assert rep["share_08_17"]["working"] < 0.1 < rep["share_08_17"]["non_working"]


def test_household_spread_keeps_energy():
    reg = load_registry()
    a = households.appliance_days(reg)
    reg.values["household_timing"] = "spread"
    b = households.appliance_days(reg)
    assert a["working"].sum() == pytest.approx(b["working"].sum())
    assert b["working"].max() < a["working"].max()  # desynchronised starts flatten the peak
