"""Working-day calendar: Monday-Friday minus national public holidays.

Italian national holidays (Law 260/1949 and later amendments): 1 Jan, 6 Jan, Easter Monday,
25 Apr, 1 May, 2 Jun, 15 Aug, 1 Nov, 8 Dec, 25 Dec, 26 Dec. The local patron-saint holiday
is not included. French holidays are used only to classify the ELMAS (France 2018) days.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
from dateutil.easter import easter


def italian_holidays(year: int) -> set[dt.date]:
    fixed = [(1, 1), (1, 6), (4, 25), (5, 1), (6, 2), (8, 15), (11, 1), (12, 8), (12, 25), (12, 26)]
    days = {dt.date(year, m, d) for m, d in fixed}
    days.add(easter(year) + dt.timedelta(days=1))  # Easter Monday
    return days


def french_holidays(year: int) -> set[dt.date]:
    fixed = [(1, 1), (5, 1), (5, 8), (7, 14), (8, 15), (11, 1), (11, 11), (12, 25)]
    e = easter(year)
    days = {dt.date(year, m, d) for m, d in fixed}
    days |= {e + dt.timedelta(days=1), e + dt.timedelta(days=39), e + dt.timedelta(days=50)}
    return days


def is_working_day(dates: pd.DatetimeIndex | pd.Series, country: str = "IT") -> pd.Series:
    """True for Monday-Friday that are not national holidays."""
    d = pd.to_datetime(pd.Series(dates))
    hol_fn = italian_holidays if country == "IT" else french_holidays
    hols = set().union(*(hol_fn(y) for y in d.dt.year.unique()))
    return (d.dt.day_of_week < 5) & ~d.dt.date.isin(hols)


def month_table(year: int) -> pd.DataFrame:
    """Working and non-working days per month of ``year`` (the weights w_d of the 12 days)."""
    days = pd.Series(pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D"))
    work = is_working_day(days, "IT")
    out = pd.DataFrame({"month": days.dt.month, "working": work.astype(int)})
    out = out.groupby("month").agg(days=("working", "size"), working_days=("working", "sum"))
    out["non_working_days"] = out["days"] - out["working_days"]
    return out.reset_index()
