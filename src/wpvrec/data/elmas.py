"""Hourly load shapes of tertiary and logistics customers from the ELMAS dataset.

Bellinguer K., Girard R., Bocquet A., Chevalier A. (2023). ELMAS dataset. figshare,
doi:10.6084/m9.figshare.23889780 (CC BY 4.0); Scientific Data 10, 2023. 18 cluster load
profiles of French industrial and tertiary customers, hourly, year 2018 (8,736 hours, no
daylight-saving gaps: timestamps read as UTC and converted to Europe/Rome local time).

Product: ``elmas_shapes.csv`` = share of the annual energy in each (cluster, month,
day type, slot), averaged per day: multiplying by the annual consumption [kWh] gives the
mean hourly consumption [kWh] of a day of that month and type. Day types follow the French
2018 calendar (the year the data were measured).
"""

from __future__ import annotations

import datetime as dt
import io
import zipfile

import pandas as pd

from wpvrec.data.calendar import is_working_day
from wpvrec.data.common import PROCESSED, RAW, TIMEZONE, sha256, write_meta

URL = "https://ndownloader.figshare.com/files/41895786"
DOI = "10.6084/m9.figshare.23889780"
MD5 = "fc38bad0a32e1734b3e0def13b8de6a6"  # published by figshare for ELMAS_dataset.zip
LICENCE = "CC BY 4.0 (Bellinguer, Girard, Bocquet, Chevalier 2023)"


def raw_path():
    return RAW / "elmas" / "ELMAS_dataset.zip"


def download(force: bool = False):
    from wpvrec.data.common import download as dl

    return dl(URL, raw_path(), force=force)


def read_clusters(zip_path) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.endswith("Time_series_18_clusters.csv"))
        df = pd.read_csv(io.BytesIO(z.read(name)), sep=";", decimal=",")
    t = pd.to_datetime(df.pop("Time")).dt.tz_localize("UTC").dt.tz_convert(TIMEZONE)
    df.index = pd.DatetimeIndex(t)
    df.columns = [int(c) for c in df.columns]
    return df


def shapes(df: pd.DataFrame) -> pd.DataFrame:
    """Share of annual energy per hour, averaged by (cluster, month, day type, slot)."""
    share = df / df.sum()
    idx = share.index
    long = share.assign(
        month=idx.month,
        slot=idx.hour + 1,
        day_type=is_working_day(pd.Series(idx.tz_localize(None).normalize()), "FR")
        .map({True: "working", False: "non_working"})
        .values,
    ).melt(id_vars=["month", "slot", "day_type"], var_name="cluster", value_name="share")
    return long.groupby(["cluster", "month", "day_type", "slot"])["share"].mean().unstack("slot")


def process() -> dict:
    path = raw_path()
    df = read_clusters(path)
    out = shapes(df)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    p = PROCESSED / "elmas_shapes.csv"
    out.to_csv(p, float_format="%.8g")
    write_meta(
        p,
        source="ELMAS dataset (Bellinguer et al. 2023), Time_series_18_clusters.csv, France 2018",
        url=f"https://doi.org/{DOI} (file {URL})",
        licence=LICENCE,
        retrieved=dt.date.fromtimestamp(path.stat().st_mtime).isoformat(),
        raw_file=str(path.relative_to(path.parents[2])),
        raw_sha256=sha256(path),
        source_type="real",
        unit="share of the cluster's annual energy in one hour (mean over days of the group)",
        processing=[
            "UTC timestamps (no DST gaps) converted to Europe/Rome local time",
            "each cluster normalised to its 2018 annual energy",
            "mean by (cluster, month, day type, slot); day type from the French 2018 calendar",
        ],
    )
    return {"clusters": int(df.shape[1]), "hours": int(df.shape[0])}
