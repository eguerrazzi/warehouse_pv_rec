"""PV production per kWp from PVGIS (JRC), hourly, all available years.

Products (specification Section 4.1):
- ``pv_typical_year.csv``: mean energy per kWp for each (month, local slot) over all PVGIS
  years — the approved "PVGIS typical year";
- ``pv_control_year.csv``: same processing for the most recent complete PVGIS year.

PVGIS timestamps are UTC and mark hourly values (e.g. 07:10 = the hour 07:00-08:00 UTC).
Each value P [W per kWp installed] is the mean power of that hour, i.e. Wh per kWp. Values
are converted to Europe/Rome local time; slot t covers the local clock hour [t-1, t).
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd

from wpvrec.data.common import INTERIM, PROCESSED, RAW, TIMEZONE, sha256, write_meta
from wpvrec.params import Registry
from wpvrec.units import WH_PER_KWH

API = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"
PVGIS_LICENCE = (
    "PVGIS (c) European Union, 2001-2026; reuse authorised with acknowledgement "
    "(Commission Decision 2011/833/EU)"
)


def _azimuth(value: str) -> int:
    """PVGIS 'aspect': 0 = south, -90 = east, 90 = west."""
    mapping = {"south": 0}
    if value not in mapping:
        raise ValueError(
            f"orientation {value!r} not supported yet (east-west is a Phase 6 variant)"
        )
    return mapping[value]


def request_url(reg: Registry) -> str:
    v = reg.value
    params = {
        "lat": v("site_latitude"),
        "lon": v("site_longitude"),
        "startyear": int(v("pvgis_start_year")),
        "endyear": int(v("pvgis_end_year")),
        "pvcalculation": 1,
        "peakpower": 1,  # per kWp; scaled by pv_kwp in the model
        "loss": v("pv_losses"),
        "mountingplace": v("pv_mounting"),
        "aspect": _azimuth(v("pv_azimuth")),
        "outputformat": "json",
    }
    if v("pv_tilt") == "PVGIS optimal angle":
        params["optimalinclination"] = 1
    else:
        params["angle"] = float(v("pv_tilt"))
    return API + "?" + "&".join(f"{k}={val}" for k, val in params.items())


def raw_path(reg: Registry):
    v = reg.value
    years = f"{int(v('pvgis_start_year'))}_{int(v('pvgis_end_year'))}"
    tag = f"{v('site_latitude')}_{v('site_longitude')}_{years}"
    return RAW / "pvgis" / f"pvgis_seriescalc_{tag}.json"


def download(reg: Registry, force: bool = False):
    from wpvrec.data.common import download as dl

    return dl(request_url(reg), raw_path(reg), force=force, timeout=600)


def parse(path) -> tuple[pd.Series, dict]:
    """Hourly energy per kWp [kWh/kWp] indexed by local time, plus the PVGIS input block."""
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    rows = doc["outputs"]["hourly"]
    t = pd.to_datetime([r["time"] for r in rows], format="%Y%m%d:%H%M", utc=True)
    t = t.floor("h").tz_convert(TIMEZONE)  # hh:10 -> start of the hour
    energy = pd.Series([r["P"] for r in rows], index=t, name="kwh_per_kwp") / WH_PER_KWH
    return energy, doc["inputs"]


def monthly_profile(energy: pd.Series) -> pd.DataFrame:
    """Mean energy per kWp by (month, slot), slot = local hour + 1."""
    df = pd.DataFrame(
        {"e": energy.values, "month": energy.index.month, "slot": energy.index.hour + 1}
    )
    out = df.groupby(["month", "slot"])["e"].mean().unstack("slot").reindex(columns=range(1, 25))
    return out.fillna(0.0)


def specific_yield(profile: pd.DataFrame, year: int) -> float:
    """Annual kWh/kWp of a monthly mean daily profile applied to every day of ``year``."""
    days = pd.Series(pd.date_range(f"{year}-01-01", f"{year}-12-31")).dt.month.value_counts()
    return float((profile.sum(axis=1) * days.sort_index()).sum())


def process(reg: Registry) -> dict:
    path = raw_path(reg)
    energy, inputs = parse(path)
    INTERIM.mkdir(parents=True, exist_ok=True)
    energy.to_frame().to_parquet(INTERIM / "pv_hourly_per_kwp.parquet")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    common = {
        "source": "PVGIS v5.3 (JRC), seriescalc, " + inputs["meteo_data"]["radiation_db"],
        "url": request_url(reg),
        "licence": PVGIS_LICENCE,
        "retrieved": dt.date.fromtimestamp(path.stat().st_mtime).isoformat(),
        "raw_file": str(path.relative_to(path.parents[2])),
        "raw_sha256": sha256(path),
        "source_type": "real",
        "pvgis_inputs": inputs,
    }
    out = {}
    first, last = int(reg.value("pvgis_start_year")), int(reg.value("pvgis_end_year"))
    typical = monthly_profile(energy)
    p = PROCESSED / "pv_typical_year.csv"
    typical.round(6).to_csv(p)
    write_meta(
        p, **common, unit="kWh per kWp in each local clock hour (slot t = [t-1, t))",
        processing=[
            "UTC hourly PVGIS values (W per kWp) converted to Europe/Rome local time",
            f"mean over all days of {first}-{last} for each (month, slot): the 'typical year'",
            "rows = month 1-12, columns = slot 1-24",
        ],
    )  # fmt: skip
    out["typical_yield"] = specific_yield(typical, int(reg.value("calendar_year")))
    ctrl_year = int(reg.value("pv_control_year"))
    control = monthly_profile(energy[energy.index.year == ctrl_year])
    p = PROCESSED / "pv_control_year.csv"
    control.round(6).to_csv(p)
    write_meta(
        p, **common, unit="kWh per kWp in each local clock hour (slot t = [t-1, t))",
        processing=[
            "UTC hourly PVGIS values (W per kWp) converted to Europe/Rome local time",
            f"mean over the days of {ctrl_year} for each (month, slot): the control year",
        ],
    )  # fmt: skip
    out["control_yield"] = specific_yield(control, ctrl_year)
    yearly = energy.groupby(energy.index.year).sum()
    out["yield_by_year"] = (
        yearly[(yearly.index >= first) & (yearly.index <= last)].round(1).to_dict()
    )
    out["optimal_slope"] = inputs["mounting_system"]["fixed"]["slope"]
    return out
