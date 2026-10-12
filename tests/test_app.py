"""The demo calls recommend and shows the headline for the selected shipment."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "src" / "routeplan" / "app.py"


def test_demo_recommends_and_switches_shipment() -> None:
    app = AppTest.from_file(str(APP), default_timeout=90)
    app.run()
    assert not app.exception
    assert app.title[0].value == "Routeplan"
    assert app.subheader[0].value.startswith("Ship route ")
    app.selectbox[0].set_value("SHP-010").run()
    assert not app.exception
    assert app.subheader[0].value.startswith("No route meets the ")


def test_new_shipment_uses_its_own_default_priority() -> None:
    app = AppTest.from_file(str(APP), default_timeout=90).run()
    app.selectbox[1].set_value("risk-averse").run()
    app.selectbox[0].set_value("SHP-003").run()
    assert not app.exception
    assert app.selectbox[1].value == "time-critical"
    assert "Deadline" in app.caption[1].value
