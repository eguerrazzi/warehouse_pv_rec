"""Pydantic models of registry entries and the per-entry provenance rules.

The allowed source types, statuses, groups and ``used_by`` values come from
``config/params/schema.yaml``; this module enforces the rules of specification
Section 3.2-3.3 on a single entry. Rules involving several entries (unique ids,
formula references, consistency expressions) live in :mod:`.registry`.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from wpvrec.params import formula as fx

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "config" / "params" / "schema.yaml"
_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@cache
def load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class Range(BaseModel):
    model_config = ConfigDict(extra="forbid")
    low: float
    high: float

    @model_validator(mode="after")
    def _ordered(self):
        if self.low > self.high:
            raise ValueError(f"sensitivity low {self.low} > high {self.high}")
        return self


class ScaleWith(BaseModel):
    """The entry is scaled proportionally with another entry in sensitivity runs."""

    model_config = ConfigDict(extra="forbid")
    scale_with: str


class ToBeDefined(BaseModel):
    """No range in the approved sheet; what is missing is stated, and flagged as a warning."""

    model_config = ConfigDict(extra="forbid")
    to_be_defined: str = Field(min_length=1)


Sensitivity = Range | ScaleWith | ToBeDefined | list[float | int | str]


class _Common(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_type: str | None = None
    status: str = "confirmed"
    notes: str = ""

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        if not _ID_RE.match(v):
            raise ValueError(f"id {v!r} must be snake_case")
        return v

    @field_validator("source", "unit")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v

    @field_validator("status")
    @classmethod
    def _status_known(cls, v: str) -> str:
        if v not in load_schema()["statuses"]:
            raise ValueError(f"unknown status {v!r}")
        return v

    @model_validator(mode="after")
    def _source_type_rules(self, info: ValidationInfo):
        types = load_schema()["source_types"]
        if self.source_type is None:
            if self.status != "to_be_provided":
                raise ValueError(f"{self.id}: source_type missing")
        elif self.source_type not in types:
            raise ValueError(f"{self.id}: unknown source_type {self.source_type!r}")
        elif types[self.source_type].get("fixtures_only"):
            ctx = info.context or {}
            if not ctx.get("fixtures"):
                raise ValueError(
                    f"{self.id}: source_type {self.source_type!r} "
                    "is allowed only in tests/fixtures/"
                )
        return self


class Parameter(_Common):
    group: str
    symbol: str = ""
    value: float | int | str | bool | list | None = None
    sensitivity: Sensitivity | None = None
    formula: str | None = None
    used_by: list[str] = Field(min_length=1)

    @field_validator("group")
    @classmethod
    def _group_known(cls, v: str) -> str:
        if v not in load_schema()["groups"]:
            raise ValueError(f"unknown group {v!r}")
        return v

    @field_validator("used_by")
    @classmethod
    def _used_by_known(cls, v: list[str]) -> list[str]:
        bad = set(v) - set(load_schema()["used_by"])
        if bad:
            raise ValueError(f"unknown used_by {sorted(bad)}")
        return v

    @model_validator(mode="after")
    def _provenance_rules(self):
        types = load_schema()["source_types"]
        st = types.get(self.source_type or "", {})
        if st.get("requires_sensitivity") and self.sensitivity is None:
            raise ValueError(f"{self.id}: an {self.source_type} needs a sensitivity range")
        if self.source_type == "derived":
            if self.value is not None:
                raise ValueError(
                    f"{self.id}: derived values are computed from the formula, "
                    "do not write them by hand (set value: null)"
                )
            if self.formula is None and self.status != "to_be_derived":
                raise ValueError(f"{self.id}: derived entry without formula must be to_be_derived")
            if self.formula is not None:
                fx.parse(self.formula)
        elif self.formula is not None:
            raise ValueError(f"{self.id}: only derived entries may have a formula")
        if (
            self.source_type != "derived"
            and self.value is None
            and self.status not in ("to_be_derived", "to_be_provided")
        ):
            raise ValueError(
                f"{self.id}: value is null, so status must be to_be_derived or to_be_provided"
            )
        return self


class Check(_Common):
    """A value used only to check results (e.g. expected annual consumption), never an input."""

    expected: float | int | str | list | dict | None = None
