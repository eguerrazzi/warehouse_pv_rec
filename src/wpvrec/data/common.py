"""Shared helpers for the data pipelines: paths, downloads, checksums, metadata sidecars.

Every processed file gets a ``<name>.meta.yaml`` sidecar with source, URL, licence,
retrieval date, checksum of the raw input, processing steps and source type
(specification Section 3.3). ``data/SOURCES.md`` is regenerated from the sidecars.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
SOURCES_MD = ROOT / "data" / "SOURCES.md"
USER_AGENT = "wpvrec research tool (https://github.com/eguerrazzi/warehouse_pv_rec)"
TIMEZONE = "Europe/Rome"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path, force: bool = False, timeout: int = 300) -> Path:
    """Download ``url`` to ``dest`` unless it already exists (idempotent)."""
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.rename(dest)
    return dest


def write_meta(path: Path, **meta) -> Path:
    """Write the ``.meta.yaml`` sidecar of a processed file."""
    meta.setdefault("file", path.name)
    meta.setdefault("processed", dt.date.today().isoformat())
    meta["sha256"] = sha256(path)
    side = path.with_name(path.name + ".meta.yaml")
    with open(side, "w", encoding="utf-8") as f:
        yaml.safe_dump(meta, f, sort_keys=False, allow_unicode=True, width=100)
    return side


def read_meta(path: Path) -> dict:
    with open(path.with_name(path.name + ".meta.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_sources_md() -> Path:
    """Regenerate data/SOURCES.md from the sidecars in data/processed."""
    lines = [
        "# Data sources",
        "",
        "Generated from the `*.meta.yaml` sidecars in `data/processed/` by `wpvrec data sources`;",
        "do not edit by hand. Raw files live in `data/raw/` (not committed) and are recreated by",
        "`wpvrec data download`.",
        "",
        "| Processed file | Source | Licence | Retrieved | Raw SHA-256 | Source type |",
        "|---|---|---|---|---|---|",
    ]
    details = []
    for side in sorted(PROCESSED.glob("*.meta.yaml")):
        m = yaml.safe_load(side.read_text(encoding="utf-8"))
        raw_sha = m.get("raw_sha256", "—")
        raw_sha = raw_sha[:12] + "…" if isinstance(raw_sha, str) and len(raw_sha) > 12 else raw_sha
        lines.append(
            f"| `{m['file']}` | {m.get('source', '')} | {m.get('licence', '')} | "
            f"{m.get('retrieved', '')} | {raw_sha} | {m.get('source_type', '')} |"
        )
        steps = m.get("processing", [])
        details += [f"### `{m['file']}`", "", f"- URL: {m.get('url', '—')}"]
        details += [f"- {s}" for s in steps] + [""]
    text = "\n".join(lines + ["", "## Processing steps", ""] + details)
    SOURCES_MD.write_text(text + "\n", encoding="utf-8")
    return SOURCES_MD
