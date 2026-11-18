"""Export the registry as the paper's parameter table (LaTeX, Markdown or CSV).

Columns: group, parameter, symbol, value, unit, sensitivity, source, source type
(Italian label, as in the paper), status.
"""

from __future__ import annotations

import csv
import io

from wpvrec.params.registry import Registry
from wpvrec.params.schema import Range, ScaleWith, ToBeDefined, load_schema

COLUMNS = [
    "Group",
    "Parameter",
    "Symbol",
    "Value",
    "Unit",
    "Sensitivity",
    "Source",
    "Type",
    "Status",
]


def _fmt_value(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.4g}"
    if isinstance(v, list):
        return ", ".join(_fmt_value(x) for x in v)
    return str(v)


def _fmt_sens(s) -> str:
    match s:
        case None:
            return "—"
        case Range(low=lo, high=hi):
            return f"{_fmt_value(lo)}–{_fmt_value(hi)}"
        case ScaleWith(scale_with=other):
            return f"scaled with {other}"
        case ToBeDefined():
            return "to be defined"
        case list():
            return "; ".join(_fmt_value(x) for x in s)
    return str(s)


def rows(reg: Registry, lang: str = "it") -> list[list[str]]:
    groups = load_schema()["groups"]
    order = {g: i for i, g in enumerate(groups)}
    out = []
    for pid, p in sorted(reg.params.items(), key=lambda kv: order[kv[1].group]):
        source = p.source + (f" [formula: {p.formula}]" if p.formula else "")
        out.append(
            [
                groups[p.group],
                p.description,
                p.symbol,
                _fmt_value(reg.values.get(pid)),
                p.unit,
                _fmt_sens(p.sensitivity),
                source,
                reg.source_type_label(pid, lang),
                p.status,
            ]
        )
    return out


def to_csv(reg: Registry, lang: str = "it") -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUMNS)
    w.writerows(rows(reg, lang))
    return buf.getvalue()


def to_markdown(reg: Registry, lang: str = "it") -> str:
    def cell(x: str) -> str:
        return x.replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(COLUMNS) + " |",
        "|" + "---|" * len(COLUMNS),
    ]
    lines += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows(reg, lang)]
    return "\n".join(lines) + "\n"


_LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _tex(s: str) -> str:
    return "".join(_LATEX_ESCAPES.get(ch, ch) for ch in s)


def to_latex(reg: Registry, lang: str = "it") -> str:
    """A ``longtable`` (needs ``\\usepackage{longtable}``); the group column is a row header."""
    cols = COLUMNS[1:]
    spec = r"p{3.2cm}lp{1.6cm}lp{1.6cm}p{4.2cm}ll"
    out = [
        r"\begin{longtable}{" + spec + "}",
        r"\hline",
        " & ".join(_tex(c) for c in cols) + r" \\",
        r"\hline",
        r"\endhead",
    ]
    current = None
    for r in rows(reg, lang):
        if r[0] != current:
            current = r[0]
            out.append(
                r"\multicolumn{" + str(len(cols)) + r"}{l}{\textbf{" + _tex(current) + r"}} \\"
            )
        out.append(" & ".join(_tex(c) for c in r[1:]) + r" \\")
    out += [r"\hline", r"\end{longtable}"]
    return "\n".join(out) + "\n"


FORMATS = {"csv": to_csv, "markdown": to_markdown, "latex": to_latex}
