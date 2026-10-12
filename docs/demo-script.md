# Demo script

Five minutes. Use seed 7 and the Streamlit page. The spoken lines are cues, not a transcript to read verbatim.

## 0:00 The decision

Open with one sentence. A cheaper sailing can miss the deadline, and a faster flight can cost more than the cargo can justify. The tool prices that choice in dollars and says which alternative it beat.

## 0:40 Show the catalog

Run `python -m routeplan generate --seed 7 --shipments 30`. Say that each shipment has three to five routes, and that sea, rail, and air prices come from distance rather than from independent random fields. Point at `docs/dataset.md` if someone asks how a cheap route became the risky one.

## 1:20 One recommendation

Run `python -m routeplan recommend shipments.json SHP-007`. Read the headline only. It should name the route, the cost gap against the cheapest quote, and the change in delay risk. Then read one detail line that splits the dollar gap into freight, holding, lateness, and tail risk.

## 2:20 Priority changes the pick

In the Streamlit page, keep the same shipment and switch the priority from the shipment's own profile to time-critical, then to cost-first. Say that the routes and the simulated delays stay fixed. Only the prices change. If the headline route changes, read the new comparison. If it does not, say the pick held, and point at the line that names the price change that would flip it.

## 3:20 A shipment with no feasible route

Select SHP-010. The page should say that no route meets the deadline and name how late the fastest schedule is. A saved frame of that page is `docs/streamlit-shp010.png`. Say that the tool refuses to pretend a late schedule is on time, and that lateness is still priced when a planner has to ship anyway.

## 4:10 The scorecard

Run `python -m routeplan evaluate shipments.json --seed 7`. Read three numbers from the table. Recommended on-time rate, the cheapest policy's mean per-shipment cost ratio, and the share of price probes that keep the pick. Say that the mean ratio is not the ratio of the two totals. Stop on the limitation. The held-out arrivals use the same delay model the planner used, so the regret is the value of pricing risk inside that model, not proof against a wrong model.
