"""CLI exit codes follow the operator contract."""

import json

from routeplan import to_json
from routeplan.cli import main

from test_decisions import _priced


def test_recommend_prints_the_headline_and_exits_zero(tmp_path, capsys) -> None:
    path = tmp_path / "shipments.json"
    path.write_text(to_json((_priced(),)))
    code = main(["recommend", str(path), "SHP-1", "--scenarios", "32", "--seed", "0"])
    captured = capsys.readouterr()
    assert code == 0
    assert "Ship route B (via Singapore)." in captured.out
    assert captured.err == ""


def test_bad_json_exits_two(tmp_path, capsys) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{")
    code = main(["recommend", str(path), "SHP-1"])
    captured = capsys.readouterr()
    assert code == 2
    assert "invalid JSON" in captured.err


def test_no_feasible_route_exits_three(tmp_path, capsys) -> None:
    shipment = _priced()
    tight = type(shipment)(
        shipment.id,
        shipment.origin,
        shipment.destination,
        shipment.priority,
        10,
        shipment.cargo_value,
        shipment.routes,
    )
    path = tmp_path / "tight.json"
    path.write_text(to_json((tight,)))
    code = main(["recommend", str(path), "SHP-1", "--scenarios", "8"])
    captured = capsys.readouterr()
    assert code == 3
    assert "No route meets the 10-hour deadline." in captured.out


def test_generate_writes_a_catalog(tmp_path, capsys) -> None:
    code = main(["generate", "--seed", "7", "--shipments", "20"])
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert len(payload) == 20
    assert "Generated 20 shipments" in captured.err
