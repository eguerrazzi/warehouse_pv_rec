"""Hourly zonal prices of the Italian day-ahead market (GME, MGP).

GME publishes yearly workbooks ("Dati storici", ``AnnoYYYY.zip``). The ``*_60.xlsx`` file
holds hourly prices; from 1 October 2025 MGP clears every 15 minutes and GME reports the
hourly values of that period as an ex-post statistical re-elaboration (workbook disclaimer).
``Ora`` 1..24 is the local clock hour [Ora-1, Ora), i.e. our slot t. On the day with 25
hours (end of daylight saving time) the 25th value is dropped; on the 23-hour day slot 24
is missing and is left out of the means.

Product: ``prices_<zone>_<year>.csv`` = mean price by (month, day type, slot), day type
"working" or "non_working" from the Italian calendar of the same year. Raw GME files are not
committed (GME terms of use); only these aggregated profiles are.
"""

from __future__ import annotations

import datetime as dt
import zipfile

import pandas as pd

from wpvrec.data.calendar import is_working_day
from wpvrec.data.common import INTERIM, PROCESSED, RAW, sha256, write_meta
from wpvrec.params import Registry

PAGE = "https://www.mercatoelettrico.org/it-it/Home/Esiti/Elettricita/MGP/Statistiche/DatiStorici"
URL = (
    PAGE
    + "/moduleId/10874/controller/GmeDatiStoriciItem/action/DownloadFile?fileName=Anno{year}.zip"
)
LICENCE = (
    "GME terms of use (www.mercatoelettrico.org, 'Condizioni generali di utilizzo'); "
    "raw files not redistributed, aggregated profiles only"
)


def raw_path(year: int):
    return RAW / "gme" / f"Anno{year}.zip"


def download(reg: Registry, force: bool = False):
    from wpvrec.data.common import download as dl

    year = int(reg.value("gme_year"))
    return dl(URL.format(year=year), raw_path(year), force=force, timeout=900)


def read_hourly(zip_path, zone: str) -> pd.DataFrame:
    """Hourly prices [EUR/MWh] of ``zone`` with columns date, slot, price."""
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.endswith("_60.xlsx"))
        with z.open(name) as f:
            df = pd.read_excel(f, sheet_name="Prezzi-Prices", engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    date_col = next(c for c in df.columns if c.startswith("Data"))
    hour_col = next(c for c in df.columns if c.startswith("Ora"))
    if zone not in df.columns:
        raise KeyError(f"zone {zone!r} not in GME workbook columns {list(df.columns)}")
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col].astype(int).astype(str), format="%Y%m%d"),
            "slot": df[hour_col].astype(int),
            "price": df[zone].astype(float),
        }
    )
    return out[out["slot"] <= 24]


def profiles(hourly: pd.DataFrame) -> pd.DataFrame:
    h = hourly.assign(
        month=hourly["date"].dt.month,
        day_type=is_working_day(hourly["date"]).map({True: "working", False: "non_working"}).values,
    )
    return h.groupby(["month", "day_type", "slot"])["price"].mean().unstack("slot").round(3)


def process(reg: Registry) -> dict:
    year, zone = int(reg.value("gme_year")), str(reg.value("gme_zone"))
    path = raw_path(year)
    hourly = read_hourly(path, zone)
    INTERIM.mkdir(parents=True, exist_ok=True)
    hourly.to_parquet(INTERIM / f"prices_{zone.lower()}_{year}_hourly.parquet")
    prof = profiles(hourly)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    p = PROCESSED / f"prices_{zone.lower()}_{year}.csv"
    prof.to_csv(p)
    write_meta(
        p,
        source=f"GME, MGP zonal prices, zone {zone}, year {year} "
        "(file *_60.xlsx, sheet Prezzi-Prices)",
        url=URL.format(year=year),
        licence=LICENCE,
        retrieved=dt.date.fromtimestamp(path.stat().st_mtime).isoformat(),
        raw_file=str(path.relative_to(path.parents[2])),
        raw_sha256=sha256(path),
        source_type="real",
        unit="EUR/MWh",
        processing=[
            "Ora 1..24 = local slot t; 25th hour of the DST day dropped",
            "Oct-Dec values are GME hourly re-elaborations of 15-minute prices",
            f"mean by (month, day type, slot); day type from the Italian {year} calendar",
        ],
    )
    return {"mean": round(float(hourly["price"].mean()), 2), "hours": int(len(hourly))}
