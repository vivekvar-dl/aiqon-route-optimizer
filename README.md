# Routeplan

Routeplan recommends one route for a shipment and explains the choice in dollars. A route wins when its schedule meets the deadline and its risk-adjusted landed cost is the lowest. A route that another eligible route beats on expected cost, expected hours, and the chance of being late is marked dominated. The lowest score still ships, including when that route is the dominated one. Landed cost is freight, cargo loss, holding, and lateness. The tail price blends that mean toward the mean of the worst 10% of simulated arrivals.

## Set up

Use Python 3.12 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[demo,test]"
```

## Run

Generate a catalog. The summary goes to stderr. The JSON goes to stdout.

```bash
python -m routeplan generate --seed 7 --shipments 30 > shipments.json
```

Recommend one shipment.

```bash
python -m routeplan recommend shipments.json SHP-007 --seed 7
```

Compare the recommendation with the cheapest quote, the fastest schedule, and a hindsight oracle.

```bash
python -m routeplan evaluate shipments.json --seed 7
```

Open the demo.

```bash
streamlit run src/routeplan/app.py
```

Run the tests.

```bash
pytest
```

`recommend` exits 0 when it ships a route, 2 when the file is invalid, and 3 when the named shipment has no route that meets the deadline. `generate` accepts 20 to 50 shipments.

## Assumptions

- The deadline constrains the scheduled hours on the quote. A route can still arrive late in simulation. That lateness is priced. It is not a second veto.
- Cheapest means the lowest freight quote. Fastest means the shortest scheduled time. Neither baseline checks the deadline.
- One dollar of freight equals one dollar of expected cargo loss. Holding and lateness are shares of cargo value per day. They are not weights that sum to 1.
- Congestion and geopolitical risk affect delay length, disruption, and cargo loss. They do not have separate score weights.
- The four priority profiles are fixed judgments. They are not estimated from bookings.
- Planning draws and evaluation draws use the same delay model and different random streams.
- Route letters are positions in the shipment. The first route is A.
- The catalog is synthetic. Lane numbers come from distance and port scores, as `docs/dataset.md` describes.

## Layout

`recommend` is the decision. `generate` builds the catalog. `evaluate` scores policies. `parse_shipments` is the only validator. The CLI and the Streamlit page call those functions and do not score routes themselves.

The report is `docs/report.md` and `docs/report.pdf`. The demo outline is `docs/demo-script.md`. Seed results are `results/evaluation.json`.
