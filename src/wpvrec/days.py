"""Twelve representative working days (one per month) and non-working-day accounting.

Specification Section 4.1: the year is represented by 12 typical working days d, one per
month, with weight w_d = working days of that month in the reference calendar year. PV is
the monthly-mean hourly profile; prices and REC members' loads are monthly-mean hourly
profiles of working days and, separately, of non-working days (weekends and holidays),
which have no decisions and are accounted for outside the LP.

Slot convention: column t = 1..24 covers the local clock hour [t-1, t).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from wpvrec.data import calendar as cal
from wpvrec.data import households
from wpvrec.data.common import PROCESSED
from wpvrec.params import Registry
from wpvrec.units import KWH_PER_MWH

SLOT_COLS = [str(t) for t in range(1, 25)]


@dataclass
class RepresentativeDays:
    """Hourly inputs of the 12 days (arrays of shape (12, 24) unless noted)."""

    year: int
    calendar: pd.DataFrame  # month, days, working_days, non_working_days
    pv: np.ndarray  # kWh produced in each slot by the installed PV
    price_working: np.ndarray  # EUR/MWh
    price_non_working: np.ndarray
    business_working: np.ndarray  # kWh, all small businesses together
    business_non_working: np.ndarray
    household_working: np.ndarray  # kWh, all households together
    household_non_working: np.ndarray

    @property
    def weights(self) -> np.ndarray:
        return self.calendar["working_days"].to_numpy()

    @property
    def non_working(self) -> np.ndarray:
        return self.calendar["non_working_days"].to_numpy()

    def annual_pv(self) -> float:
        days = self.calendar["days"].to_numpy()
        return float((self.pv.sum(axis=1) * days).sum())

    def annual_households(self) -> float:
        return float(
            (self.household_working.sum(axis=1) * self.weights).sum()
            + (self.household_non_working.sum(axis=1) * self.non_working).sum()
        )

    def annual_business(self) -> float:
        return float(
            (self.business_working.sum(axis=1) * self.weights).sum()
            + (self.business_non_working.sum(axis=1) * self.non_working).sum()
        )


def _matrix(df: pd.DataFrame) -> np.ndarray:
    return df.reindex(range(1, 13))[SLOT_COLS].to_numpy(dtype=float)


def _by_type(df: pd.DataFrame, day_type: str) -> np.ndarray:
    return _matrix(df[df["day_type"] == day_type].set_index("month"))


def build(reg: Registry, pv_variant: str = "typical") -> RepresentativeDays:
    v = reg.value
    year = int(v("calendar_year"))
    calendar = cal.month_table(year)

    pv_file = {"typical": "pv_typical_year.csv", "control": "pv_control_year.csv"}[pv_variant]
    pv = pd.read_csv(PROCESSED / pv_file).set_index("month")
    pv = _matrix(pv) * v("pv_kwp")

    prices = pd.read_csv(
        PROCESSED / f"prices_{str(v('gme_zone')).lower()}_{int(v('gme_year'))}.csv"
    )

    shapes = pd.read_csv(PROCESSED / "elmas_shapes.csv")
    annual_kwh = v("business_mwh") * KWH_PER_MWH
    clusters = [
        int(v(k)) for k in ("elmas_cluster_bar", "elmas_cluster_shop", "elmas_cluster_office")
    ]
    if len(clusters) != int(v("n_businesses")):
        raise ValueError("one ELMAS cluster per small business is required")
    bw = np.zeros((12, 24))
    bn = np.zeros((12, 24))
    for c in clusters:
        s = shapes[shapes["cluster"] == c]
        bw += _by_type(s, "working") * annual_kwh
        bn += _by_type(s, "non_working") * annual_kwh

    hh = households.profile(reg, calendar)
    n_hh = v("n_households")

    return RepresentativeDays(
        year=year,
        calendar=calendar,
        pv=pv,
        price_working=_by_type(prices, "working"),
        price_non_working=_by_type(prices, "non_working"),
        business_working=bw,
        business_non_working=bn,
        household_working=hh["working"] * n_hh,
        household_non_working=hh["non_working"] * n_hh,
    )
