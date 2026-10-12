# Shipment route selection under cost, time, and risk

Aiqon AI Internship | Technical report | 12 October 2026

Repository: https://github.com/vivekvar-dl/aiqon-route-optimizer

## 1. Decision framework

Routeplan selects among supplied candidate routes. Optimal means the lowest risk-adjusted landed cost among routes whose quoted schedule meets the shipment deadline. Inputs include origin, destination, cargo value, priority, deadline, and leg-level freight, time, delay probability, congestion, and geopolitical risk. A CLI and Streamlit interface share the same Python engine.

For scenario s, F is freight, V cargo value, L(s) cargo loss, T(s) transit hours, and D the deadline. Holding price h and lateness price p are fractions of cargo value per day:

```
C(s) = F + L(s) + h * V * T(s) / 24
                  + p * V * max(T(s) - D, 0) / 24
Score = mean(C) + a * [CVaR90(C) - mean(C)]
```

CVaR90 is the mean of the worst 10% of simulated costs. Tail weight a blends expected cost toward this tail mean. Lowest score wins; ties break on freight plus expected loss, then route letter. All score components are dollars, so explanations reconcile extra freight against holding, lateness, and tail savings. Unlike alternative-dependent normalization, these prices retain their economic meaning when a candidate is added.

| Priority | Holding / day | Lateness / day | Tail weight |
| --- | --- | --- | --- |
| Cost-first | 0.03% of V | 0.2% of V | 0.10 |
| Balanced | 0.10% of V | 1% of V | 0.30 |
| Time-critical | 0.30% of V | 5% of V | 0.30 |
| Risk-averse | 0.10% of V | 2% of V | 0.90 |

Prices are explicit judgments, not learned coefficients or contractual quotes. Eligibility uses scheduled hours; stochastic lateness is priced. If every schedule misses the deadline, the engine abstains and reports the fastest schedule's shortfall. There is no minimum on-time probability constraint or delivery guarantee.

## 2. Synthetic data and outcome model

The seed-7 catalog contains 30 shipments and 120 two-leg routes, cycling through 3-5 options. Twelve origin/destination cities and six maritime gateways form a coarse sea-corridor graph. Sea distances follow manually specified waypoints with a 5% allowance; air distances use great-circle geometry. Candidates include sea, air, sea-air, and air-sea alternatives, with transfer hubs chosen by distance rules. No ocean-crossing rail is generated. Port-to-airport handling is abstracted into dwell time. These are illustrative corridors, not verified carrier services or navigational charts; construction and source context are in docs/dataset.md.

Sea costs $350 + $0.045/km per leg at 32 km/h plus 16 hours dwell; air costs $900 + $0.55/km at 780 km/h plus 5 hours dwell. Cargo values range from $80,000 to $1,500,000. Every tenth shipment deliberately has an impossible deadline. Risk scores and prices are synthetic per-consignment assumptions, with fixed cargo size implicit.

Each leg draws a delay at its supplied probability, with exponential delay length averaging leg hours * (0.15 + 0.60 * congestion). A disruption occurs with probability 0.08 * geopolitical risk, adds 96 hours, and damages 30% of remaining cargo with conditional probability 0.25. Risk labels affect time and loss rather than being charged again. Shared hops reuse draws within a shipment; nominal unrelated legs are independent. Seeded planning and held-out evaluation use separate streams.

<!-- pagebreak -->

## 3. Explanations and reliability

The interface names hubs and modes; the explanation contrasts quotes and schedules and reconciles the score in dollars. It reports deadline slack, simulated on-time probability, a 95% Wilson sampling interval, and 90th-percentile arrival time. An interval covers sampling error under the assumed simulator; it does not cover model error. Pareto labels compare freight plus expected loss, expected hours, and late probability. They are diagnostics, not vetoes: those summaries do not capture tail severity.

For SHP-005, Dubai to Los Angeles, cargo is $86,947 and deadline 669 hours. Cost-first selects D, air then sea via Shanghai. D has 233.81 hours of scheduled slack, yet only 82.8% simulated on-time arrivals (interval 81.1%-84.4%); its 90th-percentile arrival is 798.3 hours. Balanced instead chooses air route B via Hamburg. B pays $3,993 more in freight plus expected loss but saves $1,884 in holding, $1,548 in lateness, and $4,476 in tail risk: a rounded $3,915 score advantage. The example separates schedule eligibility from delivery reliability and shows how preference changes alter a valid choice.

Price sensitivity independently scales each economic price by 0.5, 0.67, 0.8, 1.25, 1.5, and 2, reusing outcomes; duplicate capped tail weights are skipped. Profile overrides expose different business priorities. These probes measure preference sensitivity, not Monte Carlo ranking uncertainty.

## 4. Evaluation with matching constraints

Planning uses 2,000 scenarios per route. Nominal evaluation uses 1,000 held-out scenarios per route; competing policies share outcomes. Cheapest-feasible and fastest-feasible obey the same scheduled deadline. Hindsight references separately minimize held-out mean cost and the mean-CVaR score among eligible routes. Mean-cost regret and risk-score regret are averaged per shipment against their corresponding references. Oracles see held-out samples and are diagnostic bounds, not deployable policies.

| Policy, 27 feasible shipments | Total mean cost | On-time | Mean regret | Risk regret |
| --- | --- | --- | --- | --- |
| Recommended | $213,799 | 98.30% | $14.80 | $52.11 |
| Cheapest-feasible | $1,067,449 | 76.00% | $31,631.48 | $80,816.17 |
| Fastest-feasible | $223,586 | 100.00% | $377.31 | $329.52 |
| Mean-cost oracle-feasible | $213,399 | 97.11% | $0.00 | $80.89 |

The mean-cost oracle has positive risk-score regret because it optimizes a different objective. Likewise, paying a mean-cost premium can be justified by tail savings. Sampled 100% arrivals do not establish certainty. Results demonstrate the authored decision model, not observed commercial savings.

Coverage is 27/30 (90%). The full-catalog scorecard flags a fastest-schedule fallback for infeasible shipments; this is evaluation-only and excluded above. Unconstrained baselines remain separate. Summed risk scores are shipment-score totals, not portfolio CVaR; cost_ratio is a mean of per-shipment ratios. Across five catalogs (seeds 7, 11, 21, 42, 99), recommended on-time rates are 95.35%-98.30%, with mean risk-score regret $14.68-$118.45. Tests cover closed-form choices, abstention, shared draws, fragile rankings, stress monotonicity, and interface behavior. CI verifies seeded result reproduction on Python 3.12 and 3.13.

<!-- pagebreak -->

## 5. Sampling stability and model-error stress

A second experiment keeps the seed-7 catalog fixed. Twenty independent planning seeds (8-27), each with 2,000 scenarios, reproduce the original seed-7 pick 86.85% of the time on average across 27 feasible shipments. Seven fall below a heuristic 90% agreement threshold: SHP-003, 006, 009, 012, 015, 018, and 027. SHP-018 selects its original D in only 6/20 runs; B wins 14/20. SHP-005 retains D in all runs. The interface exposes counts and flags low agreement for review. It does not claim statistical certification or silently replace a choice.

Seed-7 price-probe stability is 96.09%, higher than sampling agreement. The measures answer different questions. Rare cargo-loss draws can change tail scores, particularly for nearly tied routes; a narrow on-time interval alone cannot establish ranking stability. More scenarios or operator review are warranted before relying on such a choice.

Stress freezes the original recommendations and uses 5,000 paired held-out scenarios per route. Longer delays multiply delay length by 1.5. Underestimated events multiply delay probability by 1.5 and disruption probability by 2. Regional stress adds a 72-hour hold with 10% probability per touched region, shared across routes and shipments and applied once per unique region. Different regions remain independent. Combined stress applies all changes; event probabilities cap at 1. The nominal planner never sees these changed environments.

| Environment | Total mean cost | On-time | Mean risk regret |
| --- | --- | --- | --- |
| Nominal | $220,052 | 98.27% | $145.75 |
| Longer delays | $223,285 | 97.25% | $272.91 |
| Underestimated events | $241,737 | 97.36% | $151.09 |
| Regional holds | $236,398 | 97.80% | $217.53 |
| Combined | $263,471 | 95.17% | $425.13 |

Combined stress raises mean cost 19.73% and reduces on-time arrivals by 3.10 percentage points. These are diagnostic stress assumptions, not calibrated forecasts. Compare within this experiment: its nominal estimates differ from the 1,000-scenario evaluation because rare-event sampling differs. Stress Pareto labels retain nominal planning criteria. Full results are in results/robustness.json and results/evaluation.json.

## 6. Limits and practical extension

Synthetic outcomes cannot validate real-world accuracy. Prices and probabilities are assumed; capacity, timetables, closures, customs, cargo dimensions, and carrier-specific booking quotes are omitted. Identical-hop fields assume one booking context. Regional holds introduce correlation but no event timeline, and per-shipment optimization does not optimize a joint portfolio tail objective. Wilson intervals do not cover uncertainty in estimated model parameters or scores. Twenty sampling runs and hand-selected stresses expose weaknesses without proving robustness.

The assignment permits optimization without ML. A useful extension would learn booking-time delay probabilities or arrival distributions from compatible historical legs, validate on later dates and unseen lanes, check leakage and calibration, and feed predictions into the existing optimizer. A model trained on synthetic outcomes only learns the authored simulator. Strict service-level contracts would also require chance constraints and an explicit escalation policy.

## 7. Reproduction and deliverables

README.md provides installation and CLI/demo instructions. Run pytest, scripts/run_evaluation.py, and scripts/run_robustness.py after installing the test extras. Generate the PDF with scripts/render_report.py using the report extra. The repository includes catalog, code, tests, both result artifacts, and this three-page report. docs/demo-script.md gives an optional recording outline under five minutes; no video is included.
