"""Operator commands. The shell parses flags and prints. Scoring stays in recommend."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from routeplan._decide import recommend
from routeplan._audit import audit
from routeplan._evaluate import DEFAULT_REALIZATIONS, evaluate
from routeplan._generate import generate
from routeplan._io import parse_shipments, to_json
from routeplan.model import Chosen, DatasetError, NoFeasibleRoute, Priority, Shipment


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="routeplan")
    sub = parser.add_subparsers(dest="command", required=True)

    generate_cmd = sub.add_parser("generate", help="write a seeded catalog to stdout")
    generate_cmd.add_argument("--seed", type=int, default=0)
    generate_cmd.add_argument("--shipments", type=int, default=30)

    recommend_cmd = sub.add_parser("recommend", help="recommend a route")
    recommend_cmd.add_argument("file")
    recommend_cmd.add_argument("shipment_id", nargs="?")
    recommend_cmd.add_argument("--priority", default=None)
    recommend_cmd.add_argument("--json", action="store_true")
    recommend_cmd.add_argument("--scenarios", type=int, default=2_000)
    recommend_cmd.add_argument("--seed", type=int, default=0)

    evaluate_cmd = sub.add_parser("evaluate", help="compare policies on a catalog")
    evaluate_cmd.add_argument("file")
    evaluate_cmd.add_argument("--json", action="store_true")
    evaluate_cmd.add_argument("--scenarios", type=int, default=2_000)
    evaluate_cmd.add_argument("--realizations", type=int, default=DEFAULT_REALIZATIONS)
    evaluate_cmd.add_argument("--seed", type=int, default=0)

    audit_cmd = sub.add_parser("audit", help="check sampling stability and model-error stresses")
    audit_cmd.add_argument("file")
    audit_cmd.add_argument("shipment_id")
    audit_cmd.add_argument("--priority")
    audit_cmd.add_argument("--seed", type=int, default=7)
    audit_cmd.add_argument("--runs", type=int, default=20)
    audit_cmd.add_argument("--scenarios", type=int, default=2_000)
    audit_cmd.add_argument("--realizations", type=int, default=5_000)
    audit_cmd.add_argument("--json", action="store_true")

    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "generate":
            return _generate(args.seed, args.shipments)
        if args.command == "recommend":
            return _recommend(args)
        if args.command == "audit":
            return _audit(args)
        return _evaluate(args)
    except (DatasetError, ValueError, OSError) as err:
        problems = getattr(err, "problems", None)
        if problems:
            print(f"error: {len(problems)} problems", file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
        else:
            print(f"error: {err}", file=sys.stderr)
        return 2


def _generate(seed: int, count: int) -> int:
    if not 20 <= count <= 50:
        raise ValueError("shipments must be from 20 to 50")
    shipments = generate(seed, count)
    routes = sum(len(shipment.routes) for shipment in shipments)
    print(to_json(shipments), end="")
    print(f"Generated {count} shipments with {routes} routes (seed {seed}).", file=sys.stderr)
    return 0


def _recommend(args: argparse.Namespace) -> int:
    shipments = _load(args.file)
    weights = None
    if args.priority is not None:
        weights = Priority.from_slug(args.priority).weights
    chosen = shipments
    if args.shipment_id is not None:
        match = [shipment for shipment in shipments if shipment.id == args.shipment_id]
        if not match:
            raise ValueError(f"unknown shipment {args.shipment_id}")
        chosen = match
    exit_code = 0
    shown: list[tuple[Shipment, Chosen | NoFeasibleRoute]] = []
    for shipment in chosen:
        result = recommend(shipment, weights, scenarios=args.scenarios, seed=args.seed)
        shown.append((shipment, result))
        if args.shipment_id is not None and isinstance(result, NoFeasibleRoute):
            exit_code = 3
    if args.json:
        payload = shown[0][1] if args.shipment_id is not None else [item[1] for item in shown]
        print(to_json(payload), end="")
        return exit_code
    for shipment, result in shown:
        _print_recommendation(shipment, result, weights)
    return exit_code


def _evaluate(args: argparse.Namespace) -> int:
    shipments = _load(args.file)
    report = evaluate(
        shipments,
        scenarios=args.scenarios,
        realizations=args.realizations,
        seed=args.seed,
    )
    if args.json:
        print(to_json(report), end="")
        return 0
    print(
        f"{len(report.rows)} shipments, {report.infeasible} with no feasible route."
    )
    print(
        "All shipments: recommended and feasible baselines use "
        "fastest-schedule fallback when no route qualifies."
    )
    print(
        f"{'policy':<20}{'realized $':>14}{'mean ratio':>16}"
        f"{'on time':>10}{'feasible':>12}{'Pareto':>10}{'regret $':>12}"
    )
    for policy, stats in report.stats.items():
        print(
            f"{policy.value:<20}{stats.total_cost:14,.0f}{stats.cost_ratio:16.2f}"
            f"{stats.on_time_rate:10.0%}{stats.feasible_rate:12.0%}"
            f"{stats.pareto_rate:10.0%}{stats.mean_regret:12,.0f}"
        )
    print(f"Recommended picks hold under {report.stability:.0%} of single-price changes.")
    print(
        f"\nFeasible shipments only: {len(report.rows) - report.infeasible}; "
        "regret versus the deadline-constrained mean-cost oracle."
    )
    if not report.feasible_stats:
        print("No feasible shipments to evaluate.")
    for policy, stats in report.feasible_stats.items():
        print(
            f"{policy.value:<20} cost ${stats.total_cost:,.0f}, "
            f"on time {stats.on_time_rate:.1%}, mean regret ${stats.mean_regret:,.0f}, "
            f"risk-score regret ${stats.mean_risk_regret:,.0f}"
        )
    return 0


def _audit(args: argparse.Namespace) -> int:
    shipments = _load(args.file)
    shipment = next((item for item in shipments if item.id == args.shipment_id), None)
    if shipment is None:
        raise ValueError(f"unknown shipment {args.shipment_id}")
    weights = Priority.from_slug(args.priority).weights if args.priority else None
    result = audit(
        shipment, weights, seed=args.seed, runs=args.runs,
        scenarios=args.scenarios, realizations=args.realizations,
    )
    if args.json:
        print(to_json(result), end="")
    elif result.reference_pick is None:
        print("No schedule-feasible recommendation to audit.")
    else:
        print(f"{shipment.id}: frozen route {result.reference_pick}.")
        print(
            f"Independent planning runs agree with it {result.sampling.reference_agreement:.1%} "
            f"of the time: {result.sampling.picks}."
        )
        print("Stresses change the assumed environment; the original pick stays fixed.")
        for case in result.stresses:
            print(
                f"{case.name:<24} on time {case.on_time:.1%}, mean cost ${case.mean_cost:,.0f}, "
                f"risk-score regret ${case.risk_regret:,.0f} (hindsight best {case.best_risk_route})"
            )
        print("Sampling intervals and seed agreement do not measure real-world model accuracy.")
    return 0 if result.reference_pick is not None else 3


def _load(path: str) -> tuple[Shipment, ...]:
    if path == "-":
        return parse_shipments(sys.stdin.read())
    with open(path, encoding="utf-8") as handle:
        return parse_shipments(handle.read())


def _print_recommendation(
    shipment: Shipment,
    result: Chosen | NoFeasibleRoute,
    weights: object,
) -> None:
    print(
        f"{shipment.id}  {shipment.origin} to {shipment.destination}  "
        f"{_profile_label(shipment, weights)}  deadline {shipment.deadline:g} h  "
        f"cargo ${shipment.cargo_value:,.0f}"
    )
    print()
    print(result.explanation.headline)
    for line in result.explanation.details:
        print(f"  {line}")
    print()


def _profile_label(shipment: Shipment, weights: object) -> str:
    if weights is None:
        return shipment.priority.slug
    for priority in Priority:
        if priority.weights == weights:
            if priority is shipment.priority:
                return priority.slug
            return f"{priority.slug} (shipment says {shipment.priority.slug})"
    return "custom"


if __name__ == "__main__":
    sys.exit(main())
