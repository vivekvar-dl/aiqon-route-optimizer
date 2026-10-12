# Optional demo recording outline

Target: 4 minutes 45 seconds. Run `streamlit run src/routeplan/app.py`. Keep seed 7, 30 shipments, and 2,000 scenarios. This is an outline, not an included video.

## 0:00-0:30 - Define the decision

"Routeplan compares shipment routes under cost, time, and uncertain risk. It filters quoted schedules by deadline, then minimizes landed cost with a premium for expensive tail outcomes. Its explanations reconcile the trade-off in dollars."

## 0:30-1:00 - Show the catalog

Show 30 shipments with 3-5 two-leg options. Sea follows coarse maritime corridors; air and mixed-mode transfers provide faster alternatives. State that prices, service availability, and risk estimates are illustrative assumptions.

## 1:00-2:00 - Change a priority

Select **SHP-005**. Cost-first chooses D, air then sea via Shanghai. Despite 233.81 hours of schedule slack, estimated on-time arrival is only 82.8%; show the interval and 90th-percentile arrival. Switch to **balanced**: B, air via Hamburg, wins. It pays $3,993 extra freight plus expected loss but saves holding, lateness, and tail cost for a $3,915 score advantage. Read the score reconciliation. The arrivals stay fixed while economic preferences change.

## 2:00-2:25 - Handle an impossible deadline

Select **SHP-010**. Show abstention and schedule shortfall. An evaluation-only fallback is not an approved recommendation.

## 2:25-3:25 - Show uncertainty honestly

Select **SHP-018**, keep its balanced profile, and click **Check sampling stability and disruptions**. The seed-7 D recurs in only 6/20 independent planning runs; B wins 14/20. Show the review warning. Explain that price probes, sampling uncertainty, and changed-world stress are separate experiments. The stress table evaluates the original choice without re-optimizing it in hindsight. Sampling intervals cover assumed-model sampling error, not real-world calibration.

## 3:25-4:10 - Show matching evaluation

Run:

```bash
python -m routeplan evaluate data/shipments.json --seed 7
```

Focus on 27 feasible shipments: recommended mean cost $213,799 and 98.30% on-time versus cheapest-feasible $1,067,449 and 76.00%. Fastest-feasible has $223,586 and 100% observed on-time in this sample. Every policy checks the same schedule deadline. Explain that risk-score regret compares the objective actually optimized, while mean-cost regret exposes any reliability premium.

## 4:10-4:45 - Limits and next step

"Under combined stress, the frozen recommendations' mean cost rises 19.73% and simulated on-time arrivals fall to 95.17%. These results are synthetic, not measured logistics savings. A practical next step is calibrated arrival estimates from compatible historical records, verified carrier services, and service-level constraints. The repository includes a three-page report, reproducible results, and tests."

Stop before five minutes. Check readable text and audio before sharing the recording.
