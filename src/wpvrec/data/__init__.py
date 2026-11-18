"""Input data pipelines: PVGIS, GME zonal prices, ELMAS load shapes, households, calendar.

``wpvrec data download`` fetches raw files into ``data/raw/`` (idempotent, not committed);
``wpvrec data process`` writes the processed profiles into ``data/processed/`` with a
``.meta.yaml`` sidecar each, regenerates ``data/SOURCES.md`` and prints sanity checks.
"""

from __future__ import annotations

from wpvrec.data import calendar, common, elmas, gme, pvgis
from wpvrec.params import Registry

SOURCES = ("pvgis", "gme", "elmas")


def download(reg: Registry, which=SOURCES, force: bool = False) -> dict:
    out = {}
    if "pvgis" in which:
        out["pvgis"] = pvgis.download(reg, force)
    if "gme" in which:
        out["gme"] = gme.download(reg, force)
    if "elmas" in which:
        out["elmas"] = elmas.download(force)
    return out


def process(reg: Registry) -> dict:
    report = {"pvgis": pvgis.process(reg), "gme": gme.process(reg), "elmas": elmas.process()}
    year = int(reg.value("calendar_year"))
    table = calendar.month_table(year)
    path = common.PROCESSED / f"calendar_{year}.csv"
    table.to_csv(path, index=False)
    common.write_meta(
        path,
        source=f"Italian national public holidays, {year} (Law 260/1949 as amended)",
        url="https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1949-05-27;260",
        licence="public law",
        retrieved="computed",
        source_type="derived",
        processing=["Mon-Fri minus national holidays (Easter Monday from the Gregorian computus)",
                    "patron-saint holiday not included"],
    )  # fmt: skip
    report["calendar"] = {"working_days": int(table["working_days"].sum())}
    common.write_sources_md()
    return report
