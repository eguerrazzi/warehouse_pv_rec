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


def _cmd_data(args: argparse.Namespace) -> int:
    import wpvrec.data as data
    from wpvrec.params import load_registry

    reg = load_registry(args.file)
    if args.data_command == "download":
        for name, path in data.download(reg, args.sources, args.force).items():
            print(f"{name}: {path}")
    elif args.data_command == "process":
        rep = data.process(reg)
        pv = rep["pvgis"]
        print(
            f"PV specific yield, typical year: {pv['typical_yield']:.0f} kWh/kWp/yr "
            f"(expected 1,200-1,350 for Centre Italy); control year: {pv['control_yield']:.0f}"
        )
        print(f"PVGIS optimal slope: {pv['optimal_slope']}")
        print(
            f"GME {reg.value('gme_zone')} {int(reg.value('gme_year'))}: mean "
            f"{rep['gme']['mean']} EUR/MWh over {rep['gme']['hours']} hours"
        )
        print(f"ELMAS: {rep['elmas']['clusters']} clusters, {rep['elmas']['hours']} hours")
        print(
            f"Calendar {int(reg.value('calendar_year'))}: "
            f"{rep['calendar']['working_days']} working days"
        )
        hh = rep["households"]
        if "kwh_day" in hh:
            print(
                f"Households (bottom-up): {hh['kwh_day']['working']:.2f} kWh per working day, "
                f"{hh['kwh_day']['non_working']:.2f} per non-working day; appliance energy "
                f"x {hh['scale']:.2f} (unscaled {hh['unscaled_kwh_day']['working']:.1f} kWh/day); "
                f"share 08-17: {100 * hh['share_08_17']['working']:.0f}% / "
                f"{100 * hh['share_08_17']['non_working']:.0f}%"
            )
    elif args.data_command == "sources":
        from wpvrec.data.common import write_sources_md

        print(write_sources_md())
    return 0


def _cmd_solve(args: argparse.Namespace) -> int:
    import time

    from wpvrec import balances, days, runmeta
    from wpvrec.model import inputs, lp, solve
    from wpvrec.params import load_registry

    reg = load_registry(args.file)
    reg.gate("model")
    t0 = time.time()
    rep = days.build(reg, args.pv)
    inp = inputs.build(reg, rep)
    m = lp.build_model(inp)
    solver = str(reg.value("solver"))
    res = solve.lexicographic(m, args.objective, reg.value("lexicographic_tolerance"), solver)
    wall = time.time() - t0
    plan = balances.plan_frame(m, inp)
    chk = balances.verify(m, inp)
    rnd = balances.rounding_effect(m, inp)
    ann = balances.annual_summary(plan, rep, reg.value("offshift_standby_kw"))
    pre = float((plan["prepicks"] * plan["weight"]).sum())
    print(
        f"Objective {args.objective} (lexicographic), PV {args.pv} year, solver {solver}, "
        f"{wall:.1f} s"
    )
    print(f"  F1 = {res.F1:,.0f} kWh/yr PV self-consumed")
    print(
        f"  F2 = {res.F2:,.1f} missions*h/yr (lateness {res.F2_late:,.1f}, "
        f"queue {res.F2_queue:,.1f}); pallets after cut-off: "
        f"{(plan['late_picks'] * plan['weight']).sum():,.1f}/yr"
    )
    print(
        f"  rounding missions to integers: F1 {rnd['F1'] - res.F1:+,.1f} kWh, "
        f"F2 {rnd['F2'] - res.F2:+,.1f} missions*h"
    )
    print(
        f"  pre-picking: potential {inp.prepick_potential():.1f} picks/day "
        f"(nominal {reg.value('n_picks') * reg.value('predictable_share') / 100:.1f}), "
        f"done {pre / inp.weights.sum():.1f} picks/day on average"
    )
    print(
        f"  fixed loads {inp.days[0].pf.sum():.1f} kWh per working day; site "
        f"{ann['working_day_kwh']:.1f} kWh per working day"
    )
    print(
        f"  non-working days: stand-by uses {ann['self_consumed_non_working_kwh']:,.0f} kWh/yr "
        f"of PV (constant, not in F1), exports {ann['export_non_working_kwh']:,.0f} kWh/yr"
    )
    print(
        f"  annual: PV {ann['pv_kwh'] / 1000:.1f} MWh, consumption "
        f"{ann['consumption_kwh'] / 1000:.1f} MWh, self-consumption "
        f"{ann['self_consumption_pct']:.1f}%, self-sufficiency {ann['self_sufficiency_pct']:.1f}%"
    )
    bad = {k: v for k, v in chk.items() if k != "all_ok" and v > balances.TOL}
    print("  balances: all satisfied" if chk["all_ok"] and not bad else f"  balances: {bad}")
    if args.out:
        from pathlib import Path

        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        plan.to_parquet(out / "plan.parquet")
        meta = runmeta.run_meta(reg, solver, wall, {"objective": args.objective, "F1": res.F1,
                                "F2": res.F2, "F2_late": res.F2_late, "F2_queue": res.F2_queue,
                                "checks": chk, "annual": ann})  # fmt: skip
        print(f"  written {runmeta.write(out / 'run_meta.json', meta)}")
    return 0 if chk["all_ok"] else 1


def _cmd_figures(args: argparse.Namespace) -> int:
    from wpvrec.params import load_registry

    reg = load_registry(args.file)
    if args.which in ("schematics", "all"):
        from wpvrec.figures.schematics import make_all

        for p in make_all(registry=reg):
            print(p)
    if args.which in ("illustration", "all"):
        from wpvrec.figures.illustration import make_all as make_ill

        for p in make_ill(registry=reg):
            print(p)
    if args.which in ("model", "all"):
        from wpvrec.figures.model_figures import make_all as make_model

        for p in make_model(registry=reg):
            print(p)
    if args.which in ("data", "all"):
        from wpvrec.figures.data_figures import make_all as make_data

        for p in make_data(registry=reg):
            print(p)
    return 0


def _add_data_and_figures(sub) -> None:
    from wpvrec.params import DEFAULT_REGISTRY

    d = sub.add_parser("data", help="download and process input data")
    dsub = d.add_subparsers(dest="data_command", required=True)
    dl = dsub.add_parser("download", help="fetch raw files into data/raw (idempotent)")
    dl.add_argument("sources", nargs="*", default=["pvgis", "gme", "elmas"])
    dl.add_argument("--force", action="store_true", help="download again")
    dsub.add_parser("process", help="write processed profiles and sanity checks")
    dsub.add_parser("sources", help="regenerate data/SOURCES.md from the sidecars")
    for q in (d,):
        q.add_argument("--file", default=DEFAULT_REGISTRY, help="registry YAML file")
    d.set_defaults(func=_cmd_data)
    s = sub.add_parser("solve", help="solve the LP once (lexicographic) and check the balances")
    s.add_argument("--objective", choices=["min_F2", "max_F1"], default="min_F2")
    s.add_argument("--pv", choices=["typical", "control"], default="typical")
    s.add_argument("--out", help="directory for plan.parquet and run_meta.json")
    s.add_argument("--file", default=DEFAULT_REGISTRY, help="registry YAML file")
    s.set_defaults(func=_cmd_solve)
    f = sub.add_parser("figures", help="generate figures into docs/figures")
    f.add_argument(
        "which",
        nargs="?",
        default="all",
        choices=["illustration", "schematics", "data", "model", "all"],
    )
    f.add_argument("--file", default=DEFAULT_REGISTRY, help="registry YAML file")
    f.set_defaults(func=_cmd_figures)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wpvrec", description=__doc__)
    parser.add_argument("--version", action="version", version=f"wpvrec {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("info", help="print package and solver versions").set_defaults(func=_cmd_info)
    _add_params(sub)
    _add_data_and_figures(sub)
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
