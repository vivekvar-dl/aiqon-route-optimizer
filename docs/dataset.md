# Synthetic catalog construction

The committed `data/shipments.json` uses seed 7: 30 shipments with 120 routes, each containing two legs and one cargo transfer. The seed chooses origin, destination, cargo value, and priority. Lane cost, schedule, and risk depend on mode, distance, and ports rather than independent random draws. Identical ordered hops share identical fields; the parser rejects conflicting values within a catalog.

## Geography and mode compatibility

Twelve origin/destination cities span Europe, the Gulf, the Indian Ocean, East Asia, and the Americas. Six additional maritime gateways support navigation and sea transfers: Algeciras, Port Said, Salalah, Hong Kong, Honolulu, and Cape Town. Each node has manually assigned congestion and geopolitical scores from 0 to 1. Origins and destinations come from different regions.

Air distances use great-circle distance. Sea distances use Dijkstra's shortest path over 20 bidirectional corridors in `src/routeplan/_network.py`. Each edge sums great-circle distances along manually specified waypoints, then adds 5% sailing allowance. Waypoints represent navigation rather than cargo transfers. Thus a sea leg can traverse several gateways without adding dwell at every one.

Major corridors use the Suez and Panama connections. Their geographic role is supported by the [Suez Canal Authority](https://www.suezcanal.gov.eg/English/About/SuezCanal/Pages/AboutSuezCanal.aspx) and [Panama Canal Authority](https://pancanal.com/en/connectivity/). Those sources do not supply this catalog's distances, prices, risk scores, or service availability. The coordinates and graph are coarse authored approximations; segments are not checked against a coastline mesh or current closures.

The generator emits sea and air legs only. It never assigns rail across oceans. Port cities abstract colocated airports; each leg's dwell includes local handling, with no separate terminal-transfer model. Uploaded road/rail legs remain supported by the generic schema, but the user must supply physically valid lanes.

## Lane formulas

| Mode | Speed | USD/km | Base USD | Dwell | Delay base | Congestion slope | Geo scale |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Sea | 32 km/h | 0.045 | 350 | 16 h | 0.18 | 0.40 | 1.00 |
| Air | 780 km/h | 0.55 | 900 | 5 h | 0.05 | 0.10 | 0.35 |

Freight = base + distance * USD/km; schedule = distance / speed + dwell. These are illustrative per-consignment prices, not rates tied to cargo weight. Congestion is the mean endpoint score. Delay probability = base + slope * congestion, capped at 0.90. Geopolitical risk = maximum endpoint risk * mode scale, capped at 1. Freight and hours round to 0.01; probabilities and risk scores round to four decimals.

Nominal leg risk uses endpoints; it does not infer hazard at every intermediate navigation point. Regional stress additionally covers the regions of maritime gateway nodes traversed along the sea path, but not every coordinate's coastline region.

## Alternatives and trade-offs

- A: sea then sea, transferring at a gateway near the midpoint of the shortest maritime path.
- B: air then air, through the original city adding the least air distance.
- C: sea then air. Choose an outward hub near half the sea journey, with a smaller penalty for onward air distance. The sea path cannot visit the final destination first.
- D, on shipments with four or five alternatives: air then sea, using the analogous inward hub. Its sea path cannot revisit the origin.
- E, on shipments with five alternatives: air then air through the second-best air hub.

The mixed-hub rule minimizes `abs(sea_distance_to_or_from_hub - direct_sea_distance/2) + 0.1 * air_distance`. These routes offer slow/cheap, fast/expensive, and intermediate transport choices while avoiding navigation loops. They are candidate constructions, not proven globally optimal multimodal paths. Shipments cycle through 3, 4, and 5 options.

Cargo value is log-uniform from $80,000 to $1,500,000. Priority cycles through cost-first, balanced, time-critical, and risk-averse. Nine of ten deadlines equal the sorted schedule at index `len(routes)//2` (the upper median for four routes), times 1.2, 1.5, or 2.1, then rounded to whole hours. Every tenth deadline is 75% of the fastest schedule, creating three deliberate abstentions in the 30-shipment catalog.

## Outcomes and stress environments

Nominally, each leg delays with its stated probability; delay length is exponential with mean `leg_hours * (0.15 + 0.60 * congestion)`. Disruption probability is `0.08 * geopolitical_risk`, adding 96 hours. Conditional on disruption, damage occurs with probability 0.25 and destroys 30% of remaining cargo. These outcomes enter time and dollar loss; risk labels have no additional score penalty.

Local streams are keyed by seed, planning/evaluation stream, shipment ID, and ordered hop/mode. Shared hops within a shipment reuse draws; unrelated legs remain independent. Planning and evaluation streams are distinct.

Stress cases multiply delay length by 1.5, event probabilities by 1.5 for delays and 2 for disruptions, or add 72 hours with 10% probability per touched region. Probabilities are capped at 1. Combined stress applies all changes. A regional event is keyed by region and scenario, independent of route/shipment ID, and applied once per unique touched region. It therefore affects competing routes and shipments together. Different regions have independent shocks; no seasonal timeline is modeled.

Stress changes only held-out outcomes. The original nominal recommendation stays frozen, so the planner cannot use stressed hindsight to choose its evaluated route. Stress magnitudes are transparent diagnostic assumptions, not measured forecasts.

## Scope

No historical data is used. Coordinates, congestion/risk scores, prices, speeds, and delay physics are synthetic assumptions. No capacity, timetables, bookings, customs, service closures, cargo dimensions, or carrier-specific quotes are modeled. The identical-hop rule assumes one booking context. Real deployment needs verified services and calibrated event/arrival distributions. All artifacts reproduce offline after installing the package.
