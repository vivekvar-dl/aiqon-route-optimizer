"""Operator sentences. Numbers come from the decision. This module does not rescore."""

from __future__ import annotations

from routeplan.model import (
    Chosen,
    Criteria,
    Dominated,
    Explanation,
    Infeasible,
    NoFeasibleRoute,
    Option,
    Priority,
    Sensitivity,
    Weights,
)

MATERIAL_CHANGE = 0.05
Candidate = Option | Infeasible | Dominated


def explain_choice(
    deadline: float,
    weights: Weights,
    pick: Option,
    alternatives: tuple[Option, ...],
    rejected: tuple[Dominated | Infeasible, ...],
    sensitivity: Sensitivity,
    dominated_by_label: str | None = None,
) -> Explanation:
    featured = _featured(pick, (*alternatives, *rejected))
    if featured:
        role, other = featured[0]
        headline = f"Ship {_name(pick)}. {_tradeoff(pick, role, other)}"
    elif any(isinstance(item, Dominated) for item in rejected):
        headline = f"Ship {_name(pick)}. It has the lowest risk-adjusted cost among routes that meet the deadline."
    else:
        headline = f"Ship {_name(pick)}. It is the only route that meets the deadline."
    details: list[str] = []
    reconciled: set[str] = set()
    for _role, other in featured:
        if isinstance(other, Option):
            details.append(_reconcile(pick, other, weights))
            reconciled.add(other.label)
    if alternatives and alternatives[0].label not in reconciled:
        details.append(_reconcile(pick, alternatives[0], weights))
        reconciled.add(alternatives[0].label)
    if dominated_by_label is not None:
        details.append(
            f"{pick.label} is dominated by {dominated_by_label} on expected cost, "
            "expected hours, and delay risk. Its risk-adjusted cost is still lower, so it ships."
        )
    if len(featured) > 1:
        role, other = featured[1]
        details.append(_from_their_side(pick, role, other))
    known: dict[str, Option] = {pick.label: pick}
    known.update({option.label: option for option in alternatives})
    for item in rejected:
        if isinstance(item, Dominated):
            details.append(_dominated_sentence(item, known[item.by]))
    for item in rejected:
        if isinstance(item, Infeasible):
            details.append(_infeasible_sentence(item, deadline))
    details.append(_robustness(sensitivity, weights))
    details.append(_other_profiles(sensitivity, weights, pick.label))
    return Explanation(headline, tuple(details))


def explain_infeasible(deadline: float, closest: Infeasible) -> Explanation:
    headline = (
        f"No route meets the {_whole(deadline)}-hour deadline. "
        f"The fastest, {_name(closest)}, is scheduled to arrive {_whole(closest.shortfall)} hours late."
    )
    return Explanation(headline, ())


def _featured(
    pick: Option, others: tuple[Candidate, ...]
) -> tuple[tuple[str, Candidate], ...]:
    pool: tuple[Candidate, ...] = (pick, *others)
    cheapest = min(pool, key=lambda item: (item.route.cost, item.label))
    fastest = min(pool, key=lambda item: (item.route.hours, item.label))
    chosen: list[tuple[str, Candidate]] = []
    if cheapest.label != pick.label:
        chosen.append(("the cheapest route", cheapest))
    if fastest.label != pick.label and fastest.label != cheapest.label:
        chosen.append(("the fastest route", fastest))
    if not chosen:
        runner = next((item for item in others if isinstance(item, Option)), None)
        if runner is not None:
            chosen.append(("the runner-up", runner))
    return tuple(chosen)


def _tradeoff(pick: Option, role: str, other: Candidate) -> str:
    worse, better = _clauses(pick, other)
    if worse and better:
        return f"It {_lead(worse, role, other)}, but {_join(better)}."
    if worse:
        return f"It {_lead(worse, role, other)}."
    if better:
        return f"It {_lead(better, role, other)}."
    return f"It matches {role}, {other.label}, on cost, time, and delay risk."


def _from_their_side(pick: Option, role: str, other: Candidate) -> str:
    worse, better = _clauses(other, pick)
    body = _predicate(worse, better, pick.label)
    if body is None:
        return f"{_title(other)}, {role}, matches {pick.label} on the quote, the schedule, and delay risk."
    return f"{_title(other)}, {role}, {body}."


def _predicate(worse: list[str], better: list[str], label: str) -> str | None:
    if worse and better:
        return f"{_against(worse, label)}, but {_join(better)}"
    if worse:
        return _against(worse, label)
    if better:
        return _against(better, label)
    return None


def _against(clauses: list[str], label: str) -> str:
    head = f"{clauses[0]} than {label}"
    if len(clauses) == 1:
        return head
    return head + ", and " + _join(clauses[1:])


def _clauses(subject: Candidate, other: Candidate) -> tuple[list[str], list[str]]:
    worse: list[str] = []
    better: list[str] = []

    def put(delta: float, loss: str, gain: str) -> None:
        if delta > 0:
            worse.append(loss)
        elif delta < 0:
            better.append(gain)

    cost_delta = _relative(subject.route.cost, other.route.cost)
    if cost_delta is not None and abs(cost_delta) >= MATERIAL_CHANGE:
        percent = _percent(cost_delta)
        put(cost_delta, f"costs {percent} more", f"costs {percent} less")

    hour_delta = _relative(subject.route.hours, other.route.hours)
    if hour_delta is not None and abs(hour_delta) >= MATERIAL_CHANGE:
        percent = _percent(hour_delta)
        pair = _time_pair(subject.route.hours, other.route.hours)
        put(hour_delta, f"takes {percent} longer ({pair})", f"takes {percent} less time ({pair})")

    _late_clause(subject.criteria, other.criteria, worse, better)
    return worse, better


def _late_clause(subject: Criteria, other: Criteria, worse: list[str], better: list[str]) -> None:
    if other.late == 0 and subject.late == 0:
        return
    if other.late == 0:
        if subject.late >= MATERIAL_CHANGE:
            worse.append(f"adds a {_percent(subject.late)} chance of missing the deadline")
        return
    if subject.late == 0:
        if other.late >= MATERIAL_CHANGE:
            better.append(f"avoids a {_percent(other.late)} chance of missing the deadline")
        return
    delta = (subject.late - other.late) / other.late
    if abs(delta) < MATERIAL_CHANGE:
        return
    pair = f"({_percent(subject.late)} vs {_percent(other.late)})"
    if delta > 0:
        worse.append(f"is {_percent(delta)} more likely to miss the deadline {pair}")
    else:
        better.append(f"is {_percent(delta)} less likely to miss the deadline {pair}")


def _lead(clauses: list[str], role: str, other: Candidate) -> str:
    head = f"{clauses[0]} than {role}, {other.label}"
    if len(clauses) == 1:
        return head
    return head + ", and " + _join(clauses[1:])


def _join(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def _reconcile(pick: Option, other: Option, weights: Weights) -> str:
    profile = _profile_name(weights)
    pays: list[tuple[int, str]] = []
    saves: list[tuple[int, str]] = []
    freight_gap = round(
        (pick.breakdown.freight + pick.breakdown.expected_loss)
        - (other.breakdown.freight + other.breakdown.expected_loss)
    )
    if freight_gap > 0:
        pays.append((freight_gap, f"${_money(freight_gap)} more in freight and expected loss"))
    elif freight_gap < 0:
        saves.append((-freight_gap, f"${_money(-freight_gap)} in freight and expected loss"))
    for gap, name in (
        (round(other.breakdown.holding - pick.breakdown.holding), "holding"),
        (round(other.breakdown.lateness - pick.breakdown.lateness), "expected lateness"),
        (round(other.breakdown.tail - pick.breakdown.tail), "tail risk"),
    ):
        if gap > 0:
            saves.append((gap, f"${_money(gap)} in {name}"))
        elif gap < 0:
            pays.append((-gap, f"${_money(-gap)} more in {name}"))
    ahead = sum(amount for amount, _text in saves) - sum(amount for amount, _text in pays)
    if ahead > 0:
        lead = f"{pick.label} comes out ${_money(ahead)} ahead of {other.label}"
    elif ahead < 0:
        lead = f"{pick.label} comes out ${_money(-ahead)} behind {other.label}"
    else:
        lead = f"{pick.label} ties {other.label} on risk-adjusted cost"
    pieces: list[str] = []
    if pays:
        pieces.append(f"{pick.label} pays {_join([text for _amount, text in pays])}")
    if saves:
        who = "" if pays else f"{pick.label} "
        pieces.append(f"{who}saves {_join([text for _amount, text in saves])}")
    if not pieces:
        extra = "."
    elif len(pieces) == 1:
        extra = f". {pieces[0]}."
    else:
        extra = f". {pieces[0]}, and {pieces[1]}."
    priced = (
        f"Priced for a {profile} shipment"
        if profile != "custom prices"
        else "Priced with custom prices"
    )
    return f"{priced}, {lead}{extra}"


def _dominated_sentence(item: Dominated, winner: Option) -> str:
    bits: list[str] = []
    if item.route.cost > winner.route.cost:
        bits.append("costs more")
    if item.route.hours > winner.route.hours:
        bits.append("takes longer")
    if item.criteria.late > winner.criteria.late:
        bits.append("is likelier to miss the deadline")
    reason = _join(bits) if bits else "matches the winner on the reported numbers"
    return f"{_title(item)} is dominated by {item.by}. It {reason}."


def _infeasible_sentence(item: Infeasible, deadline: float) -> str:
    return (
        f"{_title(item)} misses the {_whole(deadline)}-hour deadline "
        f"by {_whole(item.shortfall)} hours on its schedule."
    )


def _robustness(sensitivity: Sensitivity, weights: Weights) -> str:
    count = len(sensitivity.probes)
    holds = sum(probe.switches_to is None for probe in sensitivity.probes)
    if holds == count:
        return "The pick holds under every probed price change."
    nearest: dict[str, tuple[float, str]] = {}
    for probe in sensitivity.probes:
        if probe.switches_to is None:
            continue
        distance = abs(probe.factor - 1)
        current = nearest.get(probe.axis.value)
        if current is None or distance < abs(current[0] - 1):
            nearest[probe.axis.value] = (probe.factor, probe.switches_to)
    ordered = sorted(nearest.items(), key=lambda item: abs(item[1][0] - 1))[:2]
    profile = _profile_name(weights)
    sentences = []
    for axis, (factor, label) in ordered:
        price = _axis_phrase(axis)
        sentences.append(
            f"It switches to {label} if {price} is priced at {factor:g}x the {profile} rate."
        )
    body = " ".join(sentences)
    return f"The pick holds under {holds} of {count} single-price changes. {body}"


def _other_profiles(sensitivity: Sensitivity, weights: Weights, pick: str) -> str:
    parts: list[str] = []
    for priority in Priority:
        if priority.weights == weights:
            continue
        label = sensitivity.by_priority[priority]
        verb = "would also ship" if label == pick else "would ship"
        parts.append(f"{priority.slug.capitalize()} {verb} {label}.")
    return " ".join(parts)


def _profile_name(weights: Weights) -> str:
    for priority in Priority:
        if priority.weights == weights:
            return priority.slug
    return "custom prices"


def _axis_phrase(axis: str) -> str:
    return {
        "holding_per_day": "holding",
        "lateness_per_day": "lateness",
        "tail_weight": "tail risk",
    }[axis]


def _name(item: Candidate) -> str:
    hubs = item.route.hubs
    if not hubs:
        via = "direct"
    elif len(hubs) == 1:
        via = f"via {hubs[0]}"
    elif len(hubs) == 2:
        via = f"via {hubs[0]} and {hubs[1]}"
    else:
        via = "via " + ", ".join(hubs[:-1]) + f", and {hubs[-1]}"
    return f"route {item.label} ({via})"


def _title(item: Candidate) -> str:
    text = _name(item)
    return text[0].upper() + text[1:]


def _relative(subject: float, other: float) -> float | None:
    if other == 0:
        return None
    return (subject - other) / other


def _percent(fraction: float) -> str:
    return f"{round(abs(fraction) * 100):.0f}%"


def _time_pair(subject: float, other: float) -> str:
    if subject >= 72 and other >= 72:
        return f"{subject / 24:.1f} vs {other / 24:.1f} days"
    if subject < 72 and other < 72:
        return f"{subject:.0f} vs {other:.0f} hours"
    return f"{_one_time(subject)} vs {_one_time(other)}"


def _one_time(hours: float) -> str:
    if hours >= 72:
        return f"{hours / 24:.1f} days"
    return f"{hours:.0f} hours"


def _whole(hours: float) -> str:
    if float(hours).is_integer():
        return str(int(hours))
    return f"{hours:g}"


def _money(amount: float) -> str:
    return f"{int(amount):,}"
