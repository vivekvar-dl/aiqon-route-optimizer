# Route selection under cost, time, and risk

A logistics planner does not want a score with no unit. They want to know what they pay, what they save, and which alternative they turned down. This note defines a dollar notion of optimal for a synthetic catalog, states the choices that notion forces, and reports how it behaves against the cheapest quote and the fastest schedule.

## What optimal means

A route is eligible when its scheduled hours meet the shipment deadline. That check uses the quote, not a random draw, so eligibility does not move when the sample gets larger. Every eligible route is scored. Dominance is a label the explanation reports. A route is dominated when another eligible route is no worse on expected cost, expected hours, and the chance of missing the deadline, and better on at least one. Expected cost here is the freight quote plus expected cargo loss. A dominated route can still win when its dollar score is lower. The explanation says so.

For each simulated arrival the landed cost is freight, plus cargo loss, plus holding, plus lateness. Holding and lateness are shares of cargo value per day. The score is the mean landed cost, blended toward the mean of the worst 10% of arrivals. The blend weight is the profile's tail weight. At 0 the score is the mean. At 1 it is that worst-10% mean, a CVaR at 90%. The recommended route is the eligible route with the lowest score. Ties break on expected cost, then on the route letter.

Each priority is those three prices and nothing else.

| Priority | Holding per day | Lateness per day | Tail weight |
| --- | --- | --- | --- |
| Cost-first | 0.03% | 0.2% | 0.10 |
| Balanced | 0.10% | 1% | 0.30 |
| Time-critical | 0.30% | 5% | 0.30 |
| Risk-averse | 0.10% | 2% | 0.90 |

Congestion and geopolitical risk are not extra weights. Congestion lengthens a delay. Geopolitical risk raises the chance of a 96-hour disruption, which can destroy 30% of intact cargo. Those effects already sit inside hours and loss. Pricing them again would count the same event twice.

The explanation compares freight quotes and scheduled hours, then reconciles the dollar score. The stated lead is the gap between the rounded parts, so the parts add up to the lead. Each price is scaled by 0.5, 0.67, 0.8, 1.25, 1.5, and 2, and the same arrivals are re-ranked. A scale that lands on a price already probed is skipped. That is what happens when a tail weight near 1 is raised and then capped at 1. A flip is a price change, not a new sample.

## How the catalog forces a trade-off

The catalog has 30 shipments and 120 routes at seed 7. Lane cost and time come from great-circle distance. Sea is 32 km/h and $0.045 per km. Air is 780 km/h and $0.55 per km. Rail sits between them. The same port pair and mode always produce the same leg, and the parser rejects a file that breaks that rule. Each shipment's cheap route is sea through the nearest hub. Its fast route is air through that hub. A longer sea detour is available on some shipments. Every tenth shipment sets the deadline below the fastest schedule, so three shipments in 30 have no feasible route. Cargo value is log-uniform from $80,000 to $1,500,000. The construction is written out in `docs/dataset.md`.

Two consequences follow. A route that is cheaper, faster, and safer at once is rare, because air buys speed with freight and sea buys freight with time and disruption. And a shared hop uses one random stream, so two routes that share a hop see the same draw.

## What the evaluation shows

`evaluate` replays four policies on a held-out sample of 1,000 arrivals per route. The planner used a separate sample of 2,000. Cheapest is the lowest freight quote. Fastest is the shortest schedule. The oracle picks the route with the lowest mean held-out landed cost after the fact, with no tail premium. Regret is the policy's held-out landed cost minus the oracle's. `cost_ratio` is the mean of the per-shipment ratios against the recommended pick. The ratio of the two policy totals is a different number, and both are stored in `results/evaluation.json`.

On seed 7 the recommended policy realizes $209,473, is on time for 87.6% of held-out arrivals, meets the schedule on 90% of shipments, and is Pareto-optimal on 100% of picks. Mean regret against the oracle is $143 per shipment. The pick holds under 97.7% of single-price changes. Three shipments have no feasible route. Recommended freight on those picks is $145,842.

The cheapest quote realizes $2,454,826. The mean of the per-shipment ratios is 8.19. The ratio of the two totals is 11.72. It is on time for 29.7% of arrivals. Freight on those cheapest quotes totals $33,971. The extra realized cost is lateness and cargo loss on slow sea routes, especially under the time-critical price of 5% of cargo value per day. The mean ratio and the ratio of totals disagree because a few shipments carry very large dollar misses, and those misses weigh more in the totals than in an average of ratios. The fastest schedule realizes $254,170. Its mean ratio is 1.46 and its ratio of totals is 1.21, with an on-time rate of 89.9% and regret of $1,633 per shipment.

Five seeds, 7, 11, 21, 42, and 99, keep the same shape. Recommended on-time rates run from 86.9% to 87.8%. Cheapest on-time rates run from 26.3% to 34.7%. The cheapest mean ratio runs from 5.24 to 8.19, and the cheapest ratio of totals runs from 6.31 to 11.72. The fastest mean ratio runs from 1.41 to 1.61. Recommended regret runs from $143 to $373 per shipment. Stability runs from 95.7% to 97.7%. Pareto rate for the recommended pick is 100% on four seeds and 96.7% on seed 42, which is 29 of 30 shipments. On that seed, shipment SHP-015 is time-critical and ships route E even though route B dominates it on expected cost, expected hours, and delay risk. E's risk-adjusted cost is $546 lower because the tail of B is expensive. The infeasible count is 3 on every seed.

Recommended on-time stays near 88% because three shipments, 10% of the set, have no schedule that meets the deadline, and the policy still has to name a route for the scorecard. On seed 7 the feasible rate is 90% and the on-time rate is 87.6%, so 2.4 points are held-out arrivals that were scheduled to make the deadline and missed it. The cost ratio moves with how often a time-critical cargo is paired with a slow sea quote. Seed 11's mean ratio is 5.24. Seed 7's is 8.19.

## Limitations

The prices are a judgment, not a fit to a contract. A real penalty clause would replace `lateness_per_day`. Dominance uses three summaries, while the score uses the full distribution, so the two can disagree. The explanation names that disagreement when the winning route is dominated. The dominance label compares simulated means, so a larger sample can change a near tie. Planning and evaluation share one delay model. The held-out stream changes the draws, not the physics, so the regret measures the value of pricing risk inside this model. It does not measure a wrong model. The probe list is one axis at a time, and capped prices are not repeated. The network is twelve ports. The catalog uses sea, rail, and air. Road is a legal mode the generator does not emit.

## Reproduce

```bash
pip install -e ".[demo,test]"
pytest
python -m routeplan generate --seed 7 --shipments 30 > shipments.json
python -m routeplan recommend shipments.json SHP-007 --seed 7
python -m routeplan evaluate shipments.json --seed 7
python scripts/run_evaluation.py
streamlit run src/routeplan/app.py
```

The five-seed file is `results/evaluation.json`. A five-minute spoken outline is `docs/demo-script.md`.
