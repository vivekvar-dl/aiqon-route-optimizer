# Demo recording outline

Target duration: 4 minutes 40 seconds. The recording is optional; this outline is ready to record. Run `streamlit run src/routeplan/app.py` first. Keep seed 7, 30 shipments, and 2,000 scenarios.

## 0:00-0:30 - Define the decision

"Routeplan compares supplied shipment routes under cost, time, and risk. It checks the schedule deadline, then minimizes landed cost with a premium for expensive tail outcomes. The explanation shows the trade-off in dollars."

## 0:30-1:15 - Show the catalog

Point to the committed `data/shipments.json`: 30 shipments with 3-5 multi-leg routes each. Show the app's origin, destination, cargo value, deadline, route table, and scheduled versus expected time. Mention that the risk scores and geography are synthetic; rail options illustrate an intermediate-speed alternative rather than a real carrier network.

## 1:15-2:30 - Change a real trade-off

Select **SHP-005**. Its default cost-first profile selects sea route A. Switch to **balanced**: route C wins via Istanbul. Read the explanation's dollar reconciliation: C pays $1,059 more in freight and expected loss, but saves $1,174 in holding, $547 in lateness, and $1,816 in tail risk. It comes out $2,478 ahead. The faster air route B costs $5,740 more on this score. Routes and random scenarios stay fixed when the profile changes.

## 2:30-3:10 - Handle an impossible deadline

Select **SHP-010**. Show the "No route meets" headline and the fastest schedule's shortfall. Explain that this is an abstention, not authorization to ship an infeasible route. The evaluation's forced-shipment fallback is labeled and excluded from feasible-only results.

## 3:10-4:10 - Show the fair evaluation

In a terminal, run:

```bash
python -m routeplan evaluate data/shipments.json --seed 7
```

Focus on the **feasible-only** section: 27 shipments. Recommended has 97.34% simulated on-time arrivals and $179,016 total mean landed cost. Cheapest-feasible has 85.70% and $401,667. Fastest-feasible has 99.93% and $223,713. All three obey the same schedule constraint; the comparison makes the cost/reliability trade-off visible.

## 4:10-4:40 - Limits and reproducibility

"These are synthetic-model results, not real-world savings. Independent evaluation draws use the same assumed delay physics. Contractual prices, valid carrier lanes, correlated shocks, and calibrated uncertainty would be required for production. The repository includes the three-page report, five-seed results, and tests."

Stop before five minutes. Check that the text is readable in the recording and that the microphone captured your explanation.
