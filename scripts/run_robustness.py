"""Write a fixed-catalog sampling audit and stress scorecards to results/robustness.json."""

from pathlib import Path

from routeplan import audit, evaluate, generate, to_json
from routeplan._audit import STRESS_CASES

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "results" / "robustness.json"
SEED = 7
RUNS = 20
SCENARIOS = 2_000
REALIZATIONS = 5_000


def main() -> None:
    shipments = generate(SEED, 30)
    audits = [audit(s, seed=SEED, runs=RUNS, scenarios=SCENARIOS, realizations=REALIZATIONS) for s in shipments]
    successful = [item for item in audits if item.reference_pick is not None]
    payload = {
        "catalog_seed": SEED,
        "planning_seed": SEED,
        "planning_scenarios": SCENARIOS,
        "audit_runs": RUNS,
        "realizations": REALIZATIONS,
        "method": "fixed catalog; planning seeds 8-27; frozen seed-7 picks in paired held-out stress scenarios",
        "interval_is": "95% Wilson sampling interval under each assumed simulator, not model-error coverage",
        "sampling_agreement": sum(item.sampling.reference_agreement for item in successful) / len(successful),
        "review_shipments": [item.shipment_id for item in successful if item.sampling.reference_agreement < 0.9],
        "audits": audits,
        "stress_scorecards": {
            name: {
                "environment": environment,
                "feasible_shipment_count": len(successful),
                "feasible_stats": evaluate(
                    shipments, seed=SEED, scenarios=SCENARIOS, realizations=REALIZATIONS,
                    environment=environment,
                ).feasible_stats,
            }
            for name, environment in STRESS_CASES.items()
        },
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(to_json(payload))
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
