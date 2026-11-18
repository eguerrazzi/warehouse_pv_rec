"""Household hourly load profile: bottom-up from an appliance table, or any documented CSV.

Bottom-up (registry ``household_profile = bottom_up``, Ema 18/11/2026), as in Mariuzzo et
al. (2023) Sect. 4.2: appliances, start times and durations of Nazemi et al. (2021) Table 1,
rated powers of Cruz et al. (2019) Table 2 (``data/manual/household_appliances.csv``, one
source per row), built minute by minute and summed per hourly slot:

- working days: start at the preferred time, or uniform over the operation range (spread);
- non-working days (households at home): chores start uniformly in a daytime window, one
  more stove use at lunch, the rest as on working days;
- base load: fridge (annual kWh, flat) and appliance stand-by (Cruz Table 2, flat);
- the appliance energy is scaled by one factor so that the calendar year gives the annual
  consumption ``household_kwh`` (the base load is not scaled).

Besagni, Premoli Vila, Borgarello (2020) cannot be digitised: Fig. 13 reproduces Fig. 12.

CSV layouts accepted by ``load_shape`` (comma separated, header required):
- ``slot,share`` with 24 rows: one daily shape for every month and day type;
- ``month,day_type,1,...,24``: shares per month and day type ("working", "non_working").
Shares are normalised so that each daily shape sums to 1; the daily energy is the annual
consumption divided by 365 (no seasonal modulation unless the CSV provides it).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from wpvrec.data.common import PROCESSED, ROOT, write_meta
from wpvrec.params import Registry
from wpvrec.units import HOURS_PER_DAY, WH_PER_KWH

DAY_TYPES = ("working", "non_working")
APPLIANCES = ROOT / "data" / "manual" / "household_appliances.csv"
PROFILE = PROCESSED / "household_profile.csv"
MIN_PER_H = 60
MIN_PER_DAY = HOURS_PER_DAY * MIN_PER_H


def load_shape(path: Path) -> pd.DataFrame:
    """Daily shapes indexed by (month, day_type), columns slot 1..24, rows summing to 1."""
    df = pd.read_csv(path)
    if {"slot", "share"} <= set(df.columns):
        s = df.set_index("slot")["share"].reindex(range(1, 25)).to_numpy(dtype=float)
        rows = [(m, d) for m in range(1, 13) for d in DAY_TYPES]
        out = pd.DataFrame(np.tile(s, (len(rows), 1)), columns=range(1, 25))
        out.index = pd.MultiIndex.from_tuples(rows, names=["month", "day_type"])
    elif {"month", "day_type"} <= set(df.columns):
        out = df.set_index(["month", "day_type"])
        out.columns = [int(c) for c in out.columns]
    else:
        raise ValueError(f"{path}: unknown household profile layout {list(df.columns)}")
    if np.isnan(out.to_numpy()).any() or (out.to_numpy() < 0).any():
        raise ValueError(f"{path}: missing or negative values")
    return out.div(out.sum(axis=1), axis=0)


# ---- bottom-up ------------------------------------------------------------------------------
def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * MIN_PER_H + int(m)


def _use(kw: float, starts: np.ndarray, duration: int) -> np.ndarray:
    """Expected kW in each minute of the day, start uniform over ``starts`` (wraps at 24 h)."""
    p = np.zeros(MIN_PER_DAY)
    for s0 in starts:
        p[(s0 + np.arange(duration)) % MIN_PER_DAY] += kw / len(starts)
    return p


def _window(start: int, end: int, duration: int) -> np.ndarray:
    return np.arange(start, max(end - duration, start) + 1)


def _hourly(p_kw_min: np.ndarray) -> np.ndarray:
    return p_kw_min.reshape(HOURS_PER_DAY, MIN_PER_H).sum(axis=1) / MIN_PER_H  # kWh per slot


def appliance_days(reg: Registry, table: pd.DataFrame | None = None) -> dict[str, np.ndarray]:
    """Unscaled appliance profiles [kWh per slot] of one household, by day type."""
    v = reg.value
    t = pd.read_csv(APPLIANCES) if table is None else table
    power = str(v("household_power_source"))
    timing = str(v("household_timing"))
    if power not in ("cruz", "nazemi") or timing not in ("preferred", "spread"):
        raise ValueError(f"unknown household_power_source {power!r} or timing {timing!r}")
    win = (
        round(v("household_nonworking_start") * MIN_PER_H),
        round(v("household_nonworking_end") * MIN_PER_H),
    )
    out = {d: np.zeros(MIN_PER_DAY) for d in DAY_TYPES}
    for r in t.itertuples():
        kw = r.nazemi_kw if power == "nazemi" or pd.isna(r.cruz_w) else r.cruz_w / WH_PER_KWH
        dur = int(r.duration_min)
        if timing == "preferred":
            work = np.array([_minutes(r.preferred_start)])
        else:
            work = _window(_minutes(r.range_start), _minutes(r.range_end), dur)
        out["working"] += _use(kw, work, dur)
        nonwork = _window(*win, dur) if r.non_working == "chore" else work
        out["non_working"] += _use(kw, nonwork, dur)
        if r.appliance == "electric_stove" and r.use == 1:
            lunch = np.array([round(v("household_lunch_start") * MIN_PER_H)])
            out["non_working"] += _use(kw, lunch, dur)
    return {d: _hourly(p) for d, p in out.items()}


def base_load(reg: Registry, days_in_year: int, table: pd.DataFrame | None = None) -> np.ndarray:
    """Fridge and stand-by of the appliances [kWh per slot], flat."""
    t = pd.read_csv(APPLIANCES) if table is None else table
    daily = reg.value("household_fridge_kwh") / days_in_year + t["cruz_standby_kwh_day"].sum()
    return np.full(HOURS_PER_DAY, daily / HOURS_PER_DAY)


def bottom_up(reg: Registry, calendar: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Profile of one household [kWh per slot] by (month, day type), annual = household_kwh."""
    app = appliance_days(reg)
    n_w = calendar["working_days"].sum()
    n_n = calendar["non_working_days"].sum()
    base = base_load(reg, int(calendar["days"].sum()))
    annual_app = n_w * app["working"].sum() + n_n * app["non_working"].sum()
    target = reg.value("household_kwh") - (n_w + n_n) * base.sum()
    if target <= 0:
        raise ValueError("base load alone exceeds household_kwh")
    k = target / annual_app
    prof = {d: base + k * app[d] for d in DAY_TYPES}
    rows = [
        {"month": m, "day_type": d, **{str(s): prof[d][s - 1] for s in range(1, 25)}}
        for m in range(1, 13)
        for d in DAY_TYPES
    ]
    report = {
        "scale": k,
        "unscaled_kwh_day": {d: float(app[d].sum() + base.sum()) for d in DAY_TYPES},
        "kwh_day": {d: float(prof[d].sum()) for d in DAY_TYPES},
        "base_kwh_day": float(base.sum()),
        "share_08_17": {d: float(prof[d][8:17].sum() / prof[d].sum()) for d in DAY_TYPES},
    }
    return pd.DataFrame(rows), report


def process(reg: Registry, calendar: pd.DataFrame) -> dict:
    """Write data/processed/household_profile.csv (one household, kWh per slot)."""
    if reg.value("household_profile") != "bottom_up":
        return {"profile": str(reg.value("household_profile"))}
    df, rep = bottom_up(reg, calendar)
    df.to_csv(PROFILE, index=False, float_format="%.6f")
    write_meta(
        PROFILE,
        source="Bottom-up from Nazemi et al. (2021) Buildings 11(6) 237, Table 1 (appliances, "
        "times, durations) and Cruz et al. (2019) Sensors 19(18) 3973, Table 2 (rated powers, "
        "stand-by), as in Mariuzzo et al. (2023) IJEPES 153:109331",
        url="data/manual/household_appliances.csv",
        licence="values transcribed from CC BY 4.0 papers (MDPI)",
        retrieved="2026-11-18",
        source_type="derived",
        processing=[
            f"power source {reg.value('household_power_source')}, timing "
            f"{reg.value('household_timing')}, minute resolution, hourly slots (local time)",
            f"non-working days: chores uniform {reg.value('household_nonworking_start')}-"
            f"{reg.value('household_nonworking_end')} h, extra stove use at "
            f"{reg.value('household_lunch_start')} h",
            f"base load {rep['base_kwh_day']:.3f} kWh/day (fridge "
            f"{reg.value('household_fridge_kwh')} kWh/yr + stand-by), not scaled",
            f"appliance energy x {rep['scale']:.3f} so that the calendar year gives "
            f"{reg.value('household_kwh')} kWh",
            "same profile in every month (no seasonal data in the sources)",
        ],
    )
    return rep


def profile(reg: Registry, calendar: pd.DataFrame) -> dict[str, np.ndarray]:
    """One household [kWh per slot], arrays (12, 24) by day type, from the registry choice."""
    choice = str(reg.value("household_profile"))
    if choice == "bottom_up":
        if not PROFILE.exists():
            raise FileNotFoundError(f"{PROFILE} missing: run wpvrec data process")
        df = pd.read_csv(PROFILE).set_index(["month", "day_type"])
    else:  # CSV of shares: daily energy = annual consumption / days of the year
        daily = reg.value("household_kwh") / calendar["days"].sum()
        df = load_shape(ROOT / choice) * daily
    df.columns = [int(c) for c in df.columns]
    return {
        d: np.vstack([df.loc[(m, d)].reindex(range(1, 25)).to_numpy(float) for m in range(1, 13)])
        for d in DAY_TYPES
    }
