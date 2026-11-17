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
    "params": 1,
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wpvrec", description=__doc__)
    parser.add_argument("--version", action="version", version=f"wpvrec {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("info", help="print package and solver versions").set_defaults(func=_cmd_info)
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
