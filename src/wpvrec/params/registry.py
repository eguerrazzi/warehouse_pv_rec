"""Parameter registry: load a YAML file, validate it, compute derived entries, gate runs.

Usage::

    reg = load_registry("config/params/base.yaml")
    reg.value("capacity_c")          # number, derived entries already computed
    reg.gate("model")                # raises ProvenanceGateError if the model cannot run
    reg.provenance_summary()         # for run_meta.json

Rules (specification Section 3): every entry has a source, a unit and a source
type; derived entries are computed here from their formula, never written by hand;
a run refuses to start if an entry it uses is null or a test placeholder.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from wpvrec.params import formula as fx
from wpvrec.params.schema import Check, Parameter, ScaleWith, ToBeDefined, load_schema

DEFAULT_REGISTRY = Path(__file__).resolve().parents[3] / "config" / "params" / "base.yaml"


class RegistryError(ValueError):
    """The registry file violates the schema or the provenance rules."""


class ProvenanceGateError(RuntimeError):
    """A run needs entries that are missing or are test placeholders."""


@dataclass
class Registry:
    path: Path
    meta: dict[str, Any]
    params: dict[str, Parameter]
    checks: dict[str, Check]
    consistency: list[str]
    sha256: str
    values: dict[str, Any] = field(default_factory=dict)

    # ---- access -------------------------------------------------------------------------
    def __getitem__(self, pid: str) -> Parameter:
        return self.params[pid]

    def value(self, pid: str):
        """Value of ``pid`` (derived entries computed); raises if the value is missing."""
        v = self.values[pid]
        if v is None:
            p = self.params[pid]
            raise ProvenanceGateError(f"{pid} has no value ({p.status}): {p.source}")
        return v

    def source_type_label(self, pid: str, lang: str = "it") -> str:
        st = self.params[pid].source_type
        if st is None:
            return "—"
        return load_schema()["source_types"][st][f"label_{lang}"]

    # ---- provenance ---------------------------------------------------------------------
    def blocking(self, kind: str) -> list[tuple[str, str]]:
        """Entries used by ``kind`` that block a run, with the reason."""
        out = []
        for pid, p in self.params.items():
            if kind not in p.used_by:
                continue
            if p.source_type == "placeholder_test_only":
                out.append((pid, "test placeholder, not allowed in a results run"))
            elif self.values.get(pid) is None:
                missing = [
                    n for n in (fx.names(p.formula) if p.formula else []) if self.values[n] is None
                ]
                why = f"needs {', '.join(missing)}" if missing else p.source
                out.append((pid, f"{p.status}: {why}"))
        return out

    def gate(self, kind: str = "model") -> None:
        """Refuse a run of ``kind`` (model, rec, economics, data) if any needed entry is missing."""
        if kind not in load_schema()["used_by"]:
            raise ValueError(f"unknown run kind {kind!r}")
        blocked = self.blocking(kind)
        if blocked:
            lines = "\n".join(f"  - {pid}: {why}" for pid, why in blocked)
            raise ProvenanceGateError(
                f"Cannot start a '{kind}' run from {self.path.name}; "
                f"these entries must be provided first:\n{lines}"
            )

    def warnings(self) -> list[str]:
        """Entries allowed in a run but to be reviewed (status to_verify, ranges to define)."""
        out = []
        for pid, p in self.params.items():
            if p.status == "to_verify":
                out.append(f"{pid}: to_verify — {p.notes or p.source}")
            if isinstance(p.sensitivity, ToBeDefined):
                out.append(f"{pid}: sensitivity range to define — {p.sensitivity.to_be_defined}")
        return out

    def provenance_summary(self) -> dict[str, Any]:
        """Compact provenance record for ``run_meta.json``."""
        return {
            "registry_file": str(self.path),
            "registry_sha256": self.sha256,
            "counts_by_source_type": dict(
                Counter(p.source_type or "none" for p in self.params.values())
            ),
            "parameters": {
                pid: {
                    "value": self.values.get(pid),
                    "unit": p.unit,
                    "source_type": p.source_type,
                    "status": p.status,
                }
                for pid, p in self.params.items()
            },
            "warnings": self.warnings(),
        }


def _validate(cls, raw: dict, fixtures: bool):
    try:
        return cls.model_validate(raw, context={"fixtures": fixtures})
    except ValidationError as err:
        msgs = "; ".join(
            (f"{'.'.join(map(str, e['loc']))}: " if e["loc"] else "")
            + e["msg"].removeprefix("Value error, ")
            for e in err.errors()
        )
        raise RegistryError(f"entry {raw.get('id', '?')!r}: {msgs}") from err


def load_registry(path: str | Path = DEFAULT_REGISTRY) -> Registry:
    """Load, validate and compute a registry file."""
    path = Path(path).resolve()
    data = path.read_bytes()
    doc = yaml.safe_load(data) or {}
    unknown = set(doc) - {"meta", "parameters", "checks", "consistency"}
    if unknown:
        raise RegistryError(f"unknown top-level keys {sorted(unknown)}")
    fixtures = "fixtures" in path.parts and "tests" in path.parts

    params: dict[str, Parameter] = {}
    for raw in doc.get("parameters") or []:
        p = _validate(Parameter, raw, fixtures)
        if p.id in params:
            raise RegistryError(f"duplicate id {p.id!r}")
        params[p.id] = p
    checks: dict[str, Check] = {}
    for raw in doc.get("checks") or []:
        c = _validate(Check, raw, fixtures)
        if c.id in checks or c.id in params:
            raise RegistryError(f"duplicate id {c.id!r}")
        checks[c.id] = c

    # cross-entry references
    for p in params.values():
        if isinstance(p.sensitivity, ScaleWith) and p.sensitivity.scale_with not in params:
            raise RegistryError(f"{p.id}: scale_with {p.sensitivity.scale_with!r} is not an id")
        if p.formula:
            unknown_names = fx.names(p.formula) - params.keys()
            if unknown_names:
                raise RegistryError(f"{p.id}: formula uses unknown ids {sorted(unknown_names)}")

    reg = Registry(
        path=path,
        meta=doc.get("meta") or {},
        params=params,
        checks=checks,
        consistency=list(doc.get("consistency") or []),
        sha256=hashlib.sha256(data).hexdigest(),
    )
    _compute(reg)
    _check_consistency(reg)
    return reg


def _compute(reg: Registry) -> None:
    graph = {pid: (fx.names(p.formula) if p.formula else set()) for pid, p in reg.params.items()}
    try:
        order = list(TopologicalSorter(graph).static_order())
    except CycleError as err:
        raise RegistryError(f"circular formulas: {err.args[1]}") from err
    for pid in order:
        p = reg.params[pid]
        if p.formula is None:
            reg.values[pid] = p.value
            continue
        inputs = {n: reg.values[n] for n in fx.names(p.formula)}
        # A derived value is missing as long as any of its inputs is missing.
        reg.values[pid] = (
            None if any(v is None for v in inputs.values()) else fx.evaluate(p.formula, inputs)
        )


def _check_consistency(reg: Registry) -> None:
    for expr in reg.consistency:
        used = fx.names(expr)
        unknown = used - reg.params.keys()
        if unknown:
            raise RegistryError(f"consistency rule {expr!r} uses unknown ids {sorted(unknown)}")
        vals = {n: reg.values[n] for n in used}
        if any(v is None for v in vals.values()):
            continue  # cannot be checked until the values exist
        if not fx.evaluate(expr, vals):
            shown = ", ".join(f"{k}={v}" for k, v in sorted(vals.items()))
            raise RegistryError(f"consistency rule violated: {expr} ({shown})")
