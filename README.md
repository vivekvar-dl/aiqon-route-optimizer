# Routeplan

Explainable shipment route selection for the Aiqon AI Internship assignment. Routeplan chooses the lowest risk-adjusted landed cost among schedules that meet a shipment's deadline. It explains the choice in dollars: freight and expected cargo loss, holding, expected lateness, and a premium for the worst 10% of simulated outcomes.

The submission includes a **30-shipment, 120-route synthetic catalog**, CLI, Streamlit demo, tests, **three-page PDF report**, five-seed evaluation, and a fixed-catalog uncertainty audit. ML is not required by the brief; this implementation uses simulation and decision optimization. No trained model or historical logistics results are claimed.

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

```bash
python -m routeplan recommend data/shipments.json SHP-005 --seed 7
python -m routeplan recommend data/shipments.json SHP-005 --priority balanced --seed 7
python -m routeplan recommend data/shipments.json SHP-010 --seed 7
```

SHP-005 chooses route D (air then sea) under cost-first and route B (air) under balanced. B pays more freight but saves enough holding, lateness, and tail cost to gain $3,915 on the balanced score. The explanation also shows schedule slack, estimated on-time arrivals, a 95% sampling interval, and 90th-percentile arrival time.

SHP-010 has no eligible schedule: the tool abstains and exits 3. `recommend` exits 0 for a successful single-shipment pick, 2 for invalid input, and 3 for an infeasible named shipment. Without a shipment ID it reports the whole catalog and exits 0 even when some shipments are infeasible. Use `--json` for structured recommendations and alternatives.

## Check uncertainty

```bash
python -m routeplan audit data/shipments.json SHP-018 --seed 7
python -m routeplan audit data/shipments.json SHP-005 --seed 7 --json
```

The audit keeps the catalog and preferences fixed, repeats planning with 20 independent seeds, then evaluates the original pick against five paired held-out environments: nominal, longer delays, more frequent events, shared regional holds, and their combination. It distinguishes three questions:

- **Preference sensitivity:** do different economic prices change the choice?
- **Sampling stability:** do independent Monte Carlo samples change the choice?
- **Model error:** does the frozen choice perform poorly when assumptions are wrong?

Seed-7 choices agree with repeated planning runs **86.85%** on average. Seven of 27 feasible shipments fall below the illustrative 90% review threshold. SHP-018's original D is selected only 6 of 20 times; B wins the other 14. SHP-005 retains D in all 20 runs. A narrow sampling interval for arrival probability does not imply a stable ranking or an accurate model.

The Streamlit demo exposes the same audit through **Check sampling stability and disruptions**. It warns on low agreement; it does not silently replace the original recommendation with a hindsight pick.

## Evaluate and demonstrate

```bash
python -m routeplan evaluate data/shipments.json --seed 7
streamlit run src/routeplan/app.py
pytest
```

Defaults: seed 7, 30 shipments, 2,000 planning scenarios. JSON upload accepts the schema in `data/shipments.json`.

On the **27 feasible shipments**, using 1,000 held-out scenarios per route:

| Policy | Total mean landed cost | On-time arrivals | Mean-cost regret | Risk-score regret |
| --- | ---: | ---: | ---: | ---: |
| Recommended | $213,799 | 98.30% | $14.80 | $52.11 |
| Cheapest-feasible | $1,067,449 | 76.00% | $31,631.48 | $80,816.17 |
| Fastest-feasible | $223,586 | 100.00% | $377.31 | $329.52 |
| Oracle-feasible (mean cost) | $213,399 | 97.11% | $0.00 | $80.89 |

All policies in this table check the same schedule deadline. Regret is averaged per shipment: mean-cost regret compares held-out expected landed cost; risk-score regret compares the held-out mean-CVaR objective actually optimized by the recommender. Each uses its own deadline-constrained hindsight reference. The mean-cost oracle can therefore have positive risk-score regret. Oracles are evaluation references with access to held-out samples, not deployable policies. Results are synthetic-model outcomes, not observed logistics savings. A sampled 100% rate is not certainty.

A separate 5,000-scenario stress experiment keeps the seed-7 recommendations frozen. Combined stress reduces on-time arrivals from **98.27% to 95.17%**, increases total mean cost from **$220,052 to $263,471** (19.73%), and raises mean risk-score regret from **$145.75 to $425.13**. Compare within each experiment: changing the evaluation sample changes estimates, especially for rare cargo-loss events.

Evaluation retains unconstrained cheapest/fastest baselines. On infeasible shipments, the full-catalog scorecard uses a flagged, evaluation-only fastest-schedule fallback; `feasible_stats` excludes those rows. Actual recommendation coverage is 27/30 (90%). `cost_ratio` averages per-shipment ratios, not policy total ratios. Summed risk-adjusted costs are sums of shipment scores, not portfolio CVaR. Pareto labels under stress remain nominal planning diagnostics.

## Reproduce the artifacts

```bash
python -m routeplan generate --seed 7 --shipments 30 > shipments.json
cmp data/shipments.json shipments.json
python scripts/run_evaluation.py
python scripts/run_robustness.py
python scripts/render_report.py
```

The CLI generator accepts 20-50 shipments and sends its summary to stderr. Evaluation uses seeds 7, 11, 21, 42, 99 at 2,000 planning and 1,000 held-out scenarios. Robustness uses the fixed seed-7 catalog, planning seeds 8-27 at 2,000 scenarios, and 5,000 held-out scenarios for each environment. The report renderer reads `docs/report.md` and enforces three PDF pages. GitHub Actions tests Python 3.12/3.13 and verifies that the catalog and both result artifacts reproduce.

## Assumptions and limits

- Eligibility constrains quoted scheduled hours. Stochastic deadline misses are priced; there is no minimum on-time probability constraint. Strict service levels would need a chance constraint and further abstentions.
- Priority prices and risk inputs are explicit assumptions, not learned coefficients or actual contracts. Cargo size is fixed implicitly; dollars are per illustrative consignment.
- Sea distances follow a coarse waypoint/corridor graph; air uses great-circle distance. Generated routes use sea, air, and transfers between them. Gateway cities abstract port-to-airport handling into dwell time. This is not a verified carrier/service network or a navigational chart.
- Congestion and geopolitical risk affect delay and loss; they are not separately charged again. Shared hops reuse draws within shipments. Regional stress events share a scenario across all shipments and apply once per touched region. Other leg events remain independent.
- Wilson intervals measure finite-sample arrival uncertainty under an assumed model, not uncertainty in event rates, real-world calibration, or a delivery guarantee. Twenty stability runs and hand-selected stress magnitudes are diagnostics, not certified robustness.
- Nominal held-out draws prevent reuse of planning outcomes but do not validate model accuracy. Rare tail events remain sample-sensitive. Capacity, timetables, closures, booking dates, and carrier quotes are omitted.

## Submission files

- [Technical report (PDF)](docs/report.pdf) and [source](docs/report.md)
- [Dataset construction and geography](docs/dataset.md), [catalog](data/shipments.json)
- [Five-seed evaluation](results/evaluation.json), [sampling and stress results](results/robustness.json)
- [Interview walkthrough and ML extension](docs/engineering-notes.md)
- [Optional demo outline, under five minutes](docs/demo-script.md)
- [Submission checklist and email draft](docs/submission.md)

Generation, simulation, pricing, explanation, evaluation, and input validation are separate modules. Both interfaces use the same engine. No API key or external data service is required to reproduce the submission.
