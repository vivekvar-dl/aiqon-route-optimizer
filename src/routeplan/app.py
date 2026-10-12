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
)
from routeplan.model import DatasetError


def main() -> None:
    st.set_page_config(page_title="Routeplan", layout="wide")
    st.title("Routeplan")
    st.caption("Pick a shipment route in dollars an operator can check.")

    with st.sidebar:
        seed = int(st.number_input("Seed", min_value=0, max_value=10_000, value=7, step=1))
        count = int(st.slider("Shipments", min_value=20, max_value=50, value=20))
        scenarios = int(st.select_slider("Scenarios", options=(200, 500, 2_000), value=500))
        uploaded = st.file_uploader("Catalog JSON", type="json")

    if uploaded is not None:
        try:
            shipments = parse_shipments(uploaded.getvalue().decode())
        except DatasetError as err:
            st.error(str(err))
            return
    else:
        shipments = generate(seed, count)

    labels = [shipment.id for shipment in shipments]
    shipment_id = st.selectbox("Shipment", labels)
    shipment = next(item for item in shipments if item.id == shipment_id)
    profile_names = [priority.slug for priority in Priority]
    selected = st.selectbox(
        "Priority",
        profile_names,
        index=profile_names.index(shipment.priority.slug),
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
        "status": status,
        "freight $": round(option.route.cost),
        "expected hours": round(option.criteria.hours, 1),
        "late %": round(option.criteria.late * 100, 1),
        "risk-adjusted $": round(option.breakdown.total),
    }


def _rejected_row(item: Dominated | Infeasible, status: str | None = None) -> dict[str, object]:
    if status is None:
        status = "dominated" if isinstance(item, Dominated) else "infeasible"
    priced = round(item.breakdown.total) if isinstance(item, Dominated) else None
    return {
        "route": item.label,
        "via": ", ".join(item.route.hubs) or "direct",
        "status": status,
        "freight $": round(item.route.cost),
        "expected hours": round(item.criteria.hours, 1),
        "late %": round(item.criteria.late * 100, 1),
        "risk-adjusted $": priced,
    }


if __name__ == "__main__":
    main()
