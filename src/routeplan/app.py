"""Small operator demo. The page calls recommend and does not score routes itself."""

from __future__ import annotations

import streamlit as st

from routeplan import (
    Chosen,
    Dominated,
    Infeasible,
    NoFeasibleRoute,
    Option,
    Priority,
    generate,
    parse_shipments,
    recommend,
    audit,
)
from routeplan.model import DatasetError


def main() -> None:
    st.set_page_config(page_title="Routeplan", layout="wide")
    st.title("Routeplan")
    st.caption("Pick a shipment route in dollars an operator can check.")

    with st.sidebar:
        seed = int(st.number_input("Seed", min_value=0, max_value=10_000, value=7, step=1))
        count = int(st.slider("Shipments", min_value=20, max_value=50, value=30))
        scenarios = int(st.select_slider("Scenarios", options=(200, 500, 2_000), value=2_000))
        uploaded = st.file_uploader("Catalog JSON", type="json")

    if uploaded is not None:
        try:
            shipments = parse_shipments(uploaded.getvalue().decode())
        except (DatasetError, UnicodeDecodeError) as err:
            st.error(str(err))
            return
    else:
        shipments = generate(seed, count)

    labels = [shipment.id for shipment in shipments]
    shipment_id = st.selectbox("Shipment", labels)
    shipment = next(item for item in shipments if item.id == shipment_id)
    st.caption(
        f"{shipment.origin} to {shipment.destination} | "
        f"Deadline {shipment.deadline:g} h | Cargo ${shipment.cargo_value:,.0f}"
    )
    profile_names = [priority.slug for priority in Priority]
    selected = st.selectbox(
        "Priority",
        profile_names,
        index=profile_names.index(shipment.priority.slug),
        key=f"priority-{shipment.id}",
    )
    result = recommend(
        shipment,
        Priority.from_slug(str(selected)).weights,
        scenarios=scenarios,
        seed=seed,
    )
    st.subheader(result.explanation.headline)
    for line in result.explanation.details:
        st.write(line)
    st.dataframe(_rows(result), width="stretch")
    st.caption(
        "Eligibility checks the quoted schedule. On-time estimates and intervals come from "
        "the synthetic simulator and do not guarantee delivery."
    )
    if isinstance(result, Chosen) and st.button("Check sampling stability and disruptions"):
        with st.spinner("Rechecking independent samples and worse disruption assumptions..."):
            checked = audit(
                shipment, result.weights, seed=seed, runs=20, scenarios=scenarios, realizations=5_000,
            )
        st.write(
            f"Route {checked.reference_pick} was selected in "
            f"{checked.sampling.reference_agreement:.1%} of 20 independent planning runs. "
            f"Pick counts: {checked.sampling.picks}."
        )
        if checked.sampling.reference_agreement < 0.9:
            st.warning("The choice changes across simulation samples. Review the alternatives before booking.")
        st.dataframe([
            {
                "assumption": case.name,
                "on time %": round(case.on_time * 100, 1),
                "90th-percentile hours": round(case.p90_hours, 1),
                "mean cost $": round(case.mean_cost),
                "risk-adjusted $": round(case.risk_adjusted_cost),
                "risk-score regret $": round(case.risk_regret),
                "hindsight best": case.best_risk_route,
            } for case in checked.stresses
        ], width="stretch")
        st.caption(
            "The original route stays fixed. Longer delays increase delay length by 50%; "
            "underestimated events increase delay probability by 50% and disruption probability by 100%; "
            "regional shocks add 72 h with 10% probability per touched region. Combined applies all three."
        )


def _rows(result: Chosen | NoFeasibleRoute) -> list[dict[str, object]]:
    if isinstance(result, Chosen):
        rows = [_option_row(result.pick, "pick")]
        rows.extend(_option_row(option, "alternative") for option in result.alternatives)
        rows.extend(_rejected_row(item) for item in result.rejected)
        return rows
    rows = [_rejected_row(result.closest, "closest")]
    rows.extend(_rejected_row(item, "infeasible") for item in result.others)
    return rows


def _option_row(option: Option, status: str) -> dict[str, object]:
    return {
        "route": option.label,
        "via": ", ".join(option.route.hubs) or "direct",
        "modes": " + ".join(leg.mode.value for leg in option.route.legs),
        "status": status,
        "freight $": round(option.route.cost),
        "scheduled hours": round(option.route.hours, 1),
        "expected hours": round(option.criteria.hours, 1),
        "late %": round(option.criteria.late * 100, 1),
        "on-time interval %": " to ".join(f"{p * 100:.1f}" for p in option.criteria.on_time_interval95),
        "90th-percentile hours": round(option.criteria.p90_hours, 1),
        "risk-adjusted $": round(option.breakdown.total),
    }


def _rejected_row(item: Dominated | Infeasible, status: str | None = None) -> dict[str, object]:
    if status is None:
        status = "dominated" if isinstance(item, Dominated) else "infeasible"
    priced = round(item.breakdown.total) if isinstance(item, Dominated) else None
    return {
        "route": item.label,
        "via": ", ".join(item.route.hubs) or "direct",
        "modes": " + ".join(leg.mode.value for leg in item.route.legs),
        "status": status,
        "freight $": round(item.route.cost),
        "scheduled hours": round(item.route.hours, 1),
        "expected hours": round(item.criteria.hours, 1),
        "late %": round(item.criteria.late * 100, 1),
        "on-time interval %": " to ".join(f"{p * 100:.1f}" for p in item.criteria.on_time_interval95),
        "90th-percentile hours": round(item.criteria.p90_hours, 1),
        "risk-adjusted $": priced,
    }


if __name__ == "__main__":
    main()
