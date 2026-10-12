# Explaining the engineering choices in an interview

Start with the business decision: select a supplied route for a shipment under a deadline, balancing freight, time, and uncertain loss. The brief explicitly permits synthetic data and scoring or optimization; it does not require training an ML model.

## Why this design

Economic scoring keeps units interpretable. Each simulated shipment outcome has freight, cargo loss, holding, and lateness in dollars. A mean-CVaR blend lets a risk-averse operator pay more to reduce costly tail outcomes. Priorities are economic assumptions that can be changed and explained, rather than coefficients claimed to have been learned from this small catalog.

A hard quoted-schedule deadline filters candidates. An infeasible shipment returns an abstention. This does not guarantee delivery: stochastic misses are priced. An operator demanding 99% on-time arrival would need a chance constraint, calibrated estimates, and a policy for rejecting all insufficiently reliable routes.

The explanation comes directly from the score components. No LLM is needed to justify the choice. The same simulated outcomes are reused when prices change, keeping preference comparisons fair.

## What the evaluation establishes

Baselines must obey the same constraints. Compare to cheapest-feasible and fastest-feasible, and use held-out draws the planner has not seen. Compare both expected cost and the risk-adjusted objective: accepting a higher mean for lower tail loss can be the correct decision. Hindsight references are useful diagnostic lower bounds, not policies deployable with foreknowledge.

Synthetic evaluation demonstrates consistency under stated assumptions. It does not establish commercial savings or accurate risk prediction. Tests include closed-form choices, abstention, shared events, monotonic paired stress outcomes, fragile rankings, and a risk-optimal route with positive mean-cost regret.

## Three kinds of uncertainty

Price probes change the operator's preferences. Repeated planning seeds expose Monte Carlo estimation noise. Stress tests change the assumed world while freezing the decision. These are different experiments and should not be collapsed into one stability number.

For example, seed-7 price-probe stability is 96.09%, while agreement across independent planning samples is 86.85%. SHP-018 keeps its original D in only 6/20 runs; B wins 14/20. Report the weakness, examine its tail drivers, and increase simulation effort or request review before acting. The 90% review threshold is a prototype heuristic, not a formal statistical acceptance rule.

Wilson intervals quantify arrival-probability sampling error under a simulator. They do not cover uncertainty in the underlying probabilities, and they are not intervals for the score or ranking. More simulation reduces sampling noise; it cannot repair a wrong model.

Regional shocks create shared events across routes and shipments. The implementation sums per-shipment scores; it does not claim to optimize a correlated portfolio tail objective. Such an objective would require joint cost arrays and another optimizer.

## Where ML would fit later

Use historical data to estimate delay probability or an arrival-time distribution using information available at booking: origin, destination, mode, carrier, planned departure date, and known congestion. Keep the optimizer separate so contract prices, deadlines, and risk preferences remain explicit.

Before training, confirm the dataset has matching multimodal route legs, timestamps, and observed outcomes. A shipment-level late-delivery table may support a late-delivery demonstration but cannot establish unobserved alternatives' performance or maritime disruption risk. Do not invent outcomes for alternatives and call them historical evidence.

Use time-based splits and, when appropriate, hold out lanes or carriers. Exclude actual delivery duration/status from booking-time inputs. Compare against simple historical-rate baselines. Assess probability calibration and distribution coverage, then compare routing decisions using outcome data with defensible coverage of candidate actions. Offline data from the previously chosen route alone needs treatment of selection bias; naive replay of unobserved alternatives is insufficient.

A model trained on synthetic outcomes can test integration, clearly labeled synthetic. It learns the authored simulator and supplies no independent evidence of real-world accuracy. For this three-day submission, stronger decision logic and honest evaluation are more defensible than adding an unrelated model just to say ML was used.
