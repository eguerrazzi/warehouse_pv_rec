"""Reproducibility metadata of a run (specification Section 0.6): ``run_meta.json``."""

from __future__ import annotations

import datetime as dt
import json
import platform
import subprocess
from pathlib import Path

from wpvrec import __version__
from wpvrec.params import Registry
from wpvrec.solver import solver_version

ROOT = Path(__file__).resolve().parents[2]


def git_state() -> dict:
    def run(*args):
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                                  check=True).stdout.strip()  # fmt: skip
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}


def run_meta(reg: Registry, solver: str, wall_time_s: float, extra: dict | None = None) -> dict:
    return {
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "wpvrec_version": __version__,
        "git": git_state(),
        "python": platform.python_version(),
        "solver": {"name": solver, "version": solver_version(solver)},
        "wall_time_s": round(wall_time_s, 3),
        "provenance": reg.provenance_summary(),
        **(extra or {}),
    }


def write(path: Path, meta: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    return path
