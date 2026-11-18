"""Command-line interface: ``wpvrec <command> ...``.

Commands are added phase by phase; the ones not yet implemented say so and exit
with a non-zero status.
"""

from __future__ import annotations

import argparse
import sys

from wpvrec import __version__

# Planned commands and the phase that implements them (specification Section 11).
_PLANNED = {
    "data": 2,
    "solve": 3,
    "front": 4,
    "run": 6,
    "run-local": 6,
    "experiments": 6,
    "aggregate": 6,
    "paper": 8,
}


def _cmd_info(_args: argparse.Namespace) -> int:
    from wpvrec.solver import solver_version

    print(f"wpvrec {__version__}")
    try:
        print(f"HiGHS {solver_version('highs')}")
    except RuntimeError as err:
        print(f"HiGHS not available: {err}")
        return 1
    return 0


def _cmd_params_validate(args: argparse.Namespace) -> int:
    from wpvrec.params import load_registry

    reg = load_registry(args.file)
    print(
        f"{reg.path.name}: {len(reg.params)} parameters, {len(reg.checks)} checks, "
        f"sha256 {reg.sha256[:12]}"
    )
    for kind in ("model", "rec", "economics", "data"):
        blocked = reg.blocking(kind)
        state = "ready" if not blocked else f"blocked by {', '.join(b[0] for b in blocked)}"
        print(f"  {kind:<10} {state}")
    warnings = reg.warnings()
    if warnings:
        print(f"{len(warnings)} warnings:")
        for w in warnings:
            print(f"  - {w}")
    return 0


def _cmd_params_gate(args: argparse.Namespace) -> int:
    from wpvrec.params import ProvenanceGateError, load_registry

    try:
        load_registry(args.file).gate(args.kind)
    except ProvenanceGateError as err:
        print(err, file=sys.stderr)
        return 1
    print(f"'{args.kind}' run allowed")
    return 0


def _cmd_params_table(args: argparse.Namespace) -> int:
    from wpvrec.params import load_registry
    from wpvrec.params.table import FORMATS

    text = FORMATS[args.format](load_registry(args.file), args.lang)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0


def _cmd_params_show(args: argparse.Namespace) -> int:
    from wpvrec.params import load_registry

    reg = load_registry(args.file)
    p = reg[args.id]
    print(p.model_dump_json(indent=2, exclude_defaults=True))
    if p.formula:
        print(f"computed value: {reg.values[args.id]}")
    return 0


def _add_params(sub) -> None:
    from wpvrec.params import DEFAULT_REGISTRY

    p = sub.add_parser("params", help="parameter registry: validate, gate, table, show")
    psub = p.add_subparsers(dest="params_command", required=True)

    def with_file(q):
        q.add_argument("--file", default=DEFAULT_REGISTRY, help="registry YAML file")
        return q

    with_file(psub.add_parser("validate", help="validate and summarise")).set_defaults(
        func=_cmd_params_validate
    )
    g = with_file(psub.add_parser("gate", help="check whether a run can start"))
    g.add_argument(
        "kind", nargs="?", default="model", choices=["model", "rec", "economics", "data"]
    )
    g.set_defaults(func=_cmd_params_gate)
    t = with_file(psub.add_parser("table", help="export the paper parameter table"))
    t.add_argument("--format", choices=["latex", "markdown", "csv"], default="markdown")
    t.add_argument("--lang", choices=["it", "en"], default="it", help="source-type labels")
    t.add_argument("--output", "-o", help="write to file instead of stdout")
    t.set_defaults(func=_cmd_params_table)
    s = with_file(psub.add_parser("show", help="show one entry"))
    s.add_argument("id")
    s.set_defaults(func=_cmd_params_show)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wpvrec", description=__doc__)
    parser.add_argument("--version", action="version", version=f"wpvrec {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("info", help="print package and solver versions").set_defaults(func=_cmd_info)
    _add_params(sub)
    for name, phase in _PLANNED.items():
        p = sub.add_parser(name, help=f"(not implemented yet, Phase {phase})")
        p.set_defaults(func=lambda _a, n=name, ph=phase: _not_yet(n, ph))
    return parser


def _not_yet(name: str, phase: int) -> int:
    print(f"'wpvrec {name}' is not implemented yet (planned in Phase {phase}).", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
