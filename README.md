# Routeplan

Explainable shipment route selection for the Aiqon AI Internship assignment. Routeplan chooses the lowest risk-adjusted landed cost among schedules that meet a shipment's deadline. It explains the choice in dollars: freight and expected cargo loss, holding, expected lateness, and a premium for the worst 10% of simulated outcomes.

The submission includes a **30-shipment, 120-route synthetic catalog**, a CLI, a Streamlit demo, tests, a **three-page PDF report**, and reproducible results across five seeds.

## Set up

Use Python 3.12 or newer. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[demo,test,report]"
```

For the CLI alone, install with `pip install -e .`.

## Try the committed catalog

Recommend one shipment and compare priorities:

```bash
python -m routeplan recommend data/shipments.json SHP-005 --seed 7
python -m routeplan recommend data/shipments.json SHP-005 --priority balanced --seed 7
```

The first command picks sea route A; balanced picks route C. The explanation reconciles C's $2,478 score advantage over A. All amounts and risk estimates come from the synthetic model.

Show an infeasible shipment:

```bash
python -m routeplan recommend data/shipments.json SHP-010 --seed 7
```

The tool reports no feasible route and exits 3. It does not recommend shipping the closest route. `recommend` exits 0 for a successful single-shipment pick, 2 for invalid input, and 3 when the named shipment has no eligible schedule. Without a shipment ID, it reports the whole catalog and exits 0 even when some shipments are infeasible. Use `--json` for structured recommendations, including alternatives and explanations.

## Evaluate and demonstrate

```bash
python -m routeplan evaluate data/shipments.json --seed 7
streamlit run src/routeplan/app.py
pytest
```

The demo defaults to seed 7, 30 shipments, and 2,000 planning scenarios. Select SHP-005 and change its priority from cost-first to balanced to see a different choice. Select SHP-010 to see the deadline miss. JSON upload supports your own catalog in the same schema as `data/shipments.json`.

On the **27 feasible shipments** at seed 7:

| Policy | Total mean landed cost | On-time arrivals | Mean regret |
| --- | ---: | ---: | ---: |
| Recommended | $179,016 | 97.34% | $159 |
| Cheapest-feasible | $401,667 | 85.70% | $8,405 |
| Fastest-feasible | $223,713 | 99.93% | $1,814 |
| Oracle-feasible | $174,733 | 96.62% | $0 |

Every policy in this table checks the same deadline. Regret compares held-out mean landed cost with the deadline-constrained hindsight oracle; it excludes the tail premium. These are model-based results, not observed logistics savings.

Evaluation also retains unconstrained cheapest and fastest baselines. In the all-shipment scorecard, recommended and the feasible baselines use the fastest schedule as an explicit **evaluation-only fallback** on infeasible shipments. JSON rows flag this with `fallback: true`; `feasible_stats` excludes those rows. Thus the full-catalog 87.60% on-time rate and the feasible-only 97.34% rate answer different questions. Actual recommendation coverage is 90%.

`cost_ratio` averages per-shipment ratios relative to recommended; it is not the ratio of policy cost totals. `stability` averages the fraction of price probes that preserve each successful recommendation. Planning and evaluation use independent random streams under the same delay model.

## Reproduce the artifacts

```bash
python -m routeplan generate --seed 7 --shipments 30 > shipments.json
python scripts/run_evaluation.py
python scripts/render_report.py
```

`generate` accepts 20 to 50 shipments, writes JSON to stdout, and writes its summary to stderr. The evaluation script writes five seeds (7, 11, 21, 42, 99) at 2,000 planning and 1,000 evaluation scenarios per route. The report renderer reads `docs/report.md` and writes a three-page PDF. GitHub Actions runs the tests on Python 3.12 and 3.13 and verifies that the seeded catalog and evaluation results reproduce.

## Assumptions and limits

- The deadline constrains quoted scheduled hours. An eligible route can still arrive late; that outcome is priced rather than vetoed.
- The score blends mean landed cost toward CVaR90. Priority profiles are assumed economic prices, not learned weights or actual penalty contracts.
- Congestion lengthens delays. Geopolitical risk raises disruption and cargo-loss probabilities. They are not separately penalized again.
- Pareto dominance is reported on expected freight plus loss, expected time, and late probability. It does not veto a route with a better tail-adjusted score.
- The network, prices, and risk scores are illustrative. Great-circle distances are not shipping paths, and rail-priced intercontinental routes do not imply physical rail connectivity. Real use requires mode-valid carrier lanes and calibrated data.
- Shared hops within a shipment reuse draws. Other hops are independent; the model omits correlated regional disruptions, capacities, and booking-specific quotes.
- Price probes measure preference sensitivity. Held-out simulation does not validate model accuracy or produce confidence intervals.

## Submission files

- [Technical report (PDF)](docs/report.pdf) and [editable source](docs/report.md)
- [Dataset and construction](docs/dataset.md), with [committed catalog](data/shipments.json)
- [Five-seed results](results/evaluation.json)
- [Demo recording outline, under five minutes](docs/demo-script.md)
- [Submission checklist and email draft](docs/submission.md)

The package separates generation, simulation, pricing, explanation, evaluation, and JSON validation. Both interfaces use the same decision engine. No API key, external data service, or trained model is required.
