"""Write results/evaluation.json. The report quotes this file and does not recompute it."""

from __future__ import annotations

import json
from pathlib import Path

from routeplan import Chosen, NoFeasibleRoute, Policy, Report, evaluate, generate

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "results" / "evaluation.json"
SEEDS = (7, 11, 21, 42, 99)
SCENARIOS = 2_000
REALIZATIONS = 1_000


def main() -> None:
    payload = [
        _seed_row(seed)
        for seed in SEEDS
    ]
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {TARGET}")


def _seed_row(seed: int) -> dict[str, object]:
    report = evaluate(
        generate(seed, 30),
        scenarios=SCENARIOS,
        realizations=REALIZATIONS,
        seed=seed,
    )
    recommended_total = report.stats[Policy.RECOMMENDED].total_cost
    freight = _freight(report)
    policies: dict[str, object] = {}
    for policy in Policy:
        stats = report.stats[policy]
        policies[policy.value] = {
            "total_cost": round(stats.total_cost, 2),
            "cost_ratio": round(stats.cost_ratio, 4),
            "ratio_of_totals": round(stats.total_cost / recommended_total, 4),
            "on_time_rate": round(stats.on_time_rate, 4),
            "feasible_rate": round(stats.feasible_rate, 4),
            "pareto_rate": round(stats.pareto_rate, 4),
            "mean_regret": round(stats.mean_regret, 2),
            "freight_quote": round(freight[policy], 2),
        }
    return {
        "seed": seed,
        "scenarios": SCENARIOS,
        "realizations": REALIZATIONS,
        "stability": report.stability,
        "infeasible": report.infeasible,
        "feasible_shipment_count": len(report.rows) - report.infeasible,
        "fallback_is": "fastest scheduled route for the recommended and feasible policies on infeasible shipments; not a recommendation",
        "all_shipment_regret_reference": "unconstrained held-out mean-cost oracle",
        "feasible_only_regret_reference": "deadline-constrained held-out mean-cost oracle",
        "feasible_only": {
            policy.value: {
                "total_cost": round(stats.total_cost, 2),
                "cost_ratio": round(stats.cost_ratio, 4),
                "on_time_rate": round(stats.on_time_rate, 4),
                "feasible_rate": round(stats.feasible_rate, 4),
                "pareto_rate": round(stats.pareto_rate, 4),
                "mean_regret": round(stats.mean_regret, 2),
            }
            for policy, stats in report.feasible_stats.items()
        },
        "cost_ratio_is": "mean of per-shipment realized-cost ratios versus the recommended pick",
        "ratio_of_totals_is": "this policy's total realized cost divided by the recommended total",
        **policies,
    }


def _freight(report: Report) -> dict[Policy, float]:
    totals = {policy: 0.0 for policy in Policy}
    for row in report.rows:
        for policy, realized in row.realized.items():
            totals[policy] += _quote(row.recommendation, realized.pick)
    return totals


def _quote(recommendation: Chosen | NoFeasibleRoute, label: str) -> float:
    if isinstance(recommendation, Chosen):
        items = (recommendation.pick, *recommendation.alternatives, *recommendation.rejected)
    else:
        items = (recommendation.closest, *recommendation.others)
    for item in items:
        if item.label == label:
            return item.route.cost
    raise KeyError(label)


if __name__ == "__main__":
    main()
