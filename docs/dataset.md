# How the catalog builds a trade-off

`generate` does not draw cost, time, and risk as independent random fields. Independent draws can invent a route that is cheaper, faster, and safer at once, and then there is nothing to decide. Each lane is a function of distance and of the two ports it touches. The seed chooses origins, destinations, hubs, cargo value, and priority. It does not redraw a lane that another route already uses.

## Ports

Twelve ports sit in five regions: Europe, the Gulf, the Indian Ocean, East Asia, and the Americas. Each port has a congestion score and a geopolitical score from 0 to 1. A shipment's origin and destination are in different regions.

## Lane formula

Distance is the great-circle distance. The same ordered pair of ports and the same mode always produce the same leg. `parse_shipments` rejects a file in which one hop has two sets of numbers.

| Mode | Speed | Dollars per km | Base dollars | Dwell | Delay base | Delay per congestion point | Geopolitical scale |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Sea | 32 km/h | 0.045 | 350 | 16 h | 0.18 | 0.40 | 1.00 |
| Rail | 75 km/h | 0.14 | 250 | 8 h | 0.10 | 0.22 | 0.60 |
| Air | 780 km/h | 0.55 | 900 | 5 h | 0.05 | 0.10 | 0.35 |

Delay probability is the delay base plus the slope times the average congestion of the two ports, capped at 0.90. Geopolitical risk is the worse port's score times the mode scale, capped at 1. Congestion on the leg is the average of the two ports, capped at 1. Hours and dollars are rounded to cents and to 0.01 hour.

Sea is the cheap, slow, high-risk mode. Air is the fast, expensive, lower-risk mode. Rail sits between them. A dollar of air freight buys time and a lower disruption rate. A dollar saved on sea freight buys a longer schedule and a higher chance of delay and loss.

## Routes on one shipment

Every route has at least one hub.

- Route A is sea through the hub that adds the least distance.
- Route B is air through that same hub. It is the same geography at the air price and the air speed, so it costs more and takes less scheduled time than route A.
- Route C is rail through the next-shortest hub.
- When the shipment has four or five routes, one is sea through the nearest hub and then the farthest hub. The extra leg adds freight and hours on top of route A.
- When the shipment has five routes, one is air through the farthest hub.

Shipment `i` has `3 + (i mod 3)` routes, so the catalog cycles through 3, 4, and 5.

## Deadline, cargo, and priority

The deadline is a whole number of hours. For nine shipments out of ten it is the median scheduled time times 1.2, 1.5, or 2.1, cycling with the shipment index. Every tenth shipment, indexes 9, 19, and 29 in a catalog of 30, sets the deadline at 75% of the fastest schedule. No route meets that deadline. Cargo value is log-uniform between $80,000 and $1,500,000. Priority cycles through cost-first, balanced, time-critical, and risk-averse.

## What the simulation then does with those fields

Congestion does not have its own price. It lengthens a delay after a delay happens. Geopolitical risk does not have its own price. It raises the chance of a 96-hour disruption, and a disruption damages cargo with probability 0.25, destroying 30% of the cargo that is still intact. Those outcomes show up as expected hours, a chance of missing the deadline, and dollars of loss. The scorer prices those dollars. It does not price the risk labels a second time.

## Scope of the synthetic geography

The port coordinates, congestion scores, geopolitical scores, speeds, and prices are illustrative model inputs, not measured carrier data. Great-circle distance provides a reproducible scale for cost and time; it does not trace navigable sea lanes. Rail-priced routes are an abstract intermediate-speed option and can connect ports with no physical rail link, including intercontinental pairs. These options exercise the decision framework and must be replaced with mode-valid carrier routes before operational use.

The model has no cargo weight or volume, capacity, sailing calendars, border checks, or carrier-specific quotes. A lane's fixed fields assume one booking context. The committed `data/shipments.json` is generated with seed 7 and 30 shipments; the generator and evaluator require no network access.
