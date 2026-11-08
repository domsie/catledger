"""Command line interface, safe output handling and explicit error codes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from catledger import __version__
from catledger.model import InputError, load_json, load_problem
from catledger.render import as_csv, as_svg, as_text
from catledger.solver import solve
from catledger.verify import verify_plan


def _output(value: str, destination: str | None, overwrite: bool) -> None:
    if destination is None or destination == "-":
        sys.stdout.write(value)
        return
    path = Path(destination)
    if path.exists() and not overwrite:
        raise InputError(f"refusing to overwrite existing file: {path}; pass --overwrite")
    if not path.parent.is_dir():
        raise InputError(f"output directory does not exist: {path.parent}")
    # Exclusive creation prevents accidentally replacing an existing file.
    if not overwrite:
        with path.open("x", encoding="utf-8", newline="") as stream:
            stream.write(value)
    else:
        path.write_text(value, encoding="utf-8", newline="")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local kerf-aware 1D cutting stock and offcut planner")
    parser.add_argument("--version", action="version", version=f"catledger {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="create a new plan from a JSON job")
    plan.add_argument("job", help="path to job JSON")
    plan.add_argument("--mode", choices=["auto", "exact", "heuristic"], default="auto")
    plan.add_argument("--node-budget", type=int, default=150_000)
    plan.add_argument("--format", choices=["json", "text", "csv"], default="json")
    plan.add_argument("--output", help="output file (default: stdout)")
    plan.add_argument("--svg", help="optional additional static SVG cut diagram path")
    plan.add_argument("--overwrite", action="store_true", help="permit overwriting output files")
    check = commands.add_parser("verify", help="independently check a saved plan's physical consistency")
    check.add_argument("job")
    check.add_argument("plan")
    compare = commands.add_parser("compare", help="verify and compare two plans for the same job")
    compare.add_argument("job")
    compare.add_argument("first")
    compare.add_argument("second")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        problem = load_problem(args.job)
        if args.command == "plan":
            plan = solve(problem, mode=args.mode, node_budget=args.node_budget)
            verify_plan(problem, plan)
            value = (json.dumps(plan, indent=2, sort_keys=True) + "\n" if args.format == "json"
                     else as_csv(plan) if args.format == "csv" else as_text(plan))
            if args.svg and args.output and Path(args.svg).resolve() == Path(args.output).resolve():
                raise InputError("--svg and --output must be different files")
            _output(value, args.output, args.overwrite)
            if args.svg:
                _output(as_svg(plan), args.svg, args.overwrite)
        elif args.command == "verify":
            totals = verify_plan(problem, load_json(args.plan))
            sys.stdout.write(json.dumps({"valid": True, "objective": totals}, sort_keys=True) + "\n")
        elif args.command == "compare":
            first, second = load_json(args.first), load_json(args.second)
            a, b = verify_plan(problem, first), verify_plan(problem, second)
            keys = ("material_cost_cents", "unrecoverable_mm", "boards_used", "total_leftover_mm")
            score_a = tuple(a[key] for key in keys)
            score_b = tuple(b[key] for key in keys)
            winner = "first" if score_a < score_b else "second" if score_b < score_a else "tie"
            sys.stdout.write(json.dumps({"winner": winner, "first": a, "second": b,
                                         "first_proven_optimal_claim": first["proven_optimal"],
                                         "second_proven_optimal_claim": second["proven_optimal"]},
                                        indent=2, sort_keys=True) + "\n")
        return 0
    except (InputError, OSError, UnicodeError) as exc:
        print(f"catledger: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
