"""What a page says about when a route was traced.

The cases live in `tests/fixtures/trace-note-cases.json` rather than in this file, because
`tests/js/map.test.js` reads the same file and asserts the same answers: the sentence is
written twice, once in Python for the report and once in JavaScript for the explorer, and
a shared list of hand-worked cases is what stops the two drifting apart. Add a case there
and both suites fail until both sides handle it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pingme.render_map import (
    LABEL_SIDE,
    REFERENCE_POINTS,
    TRACE_WITH_RUN_GRACE_S,
    map_figure,
    trace_note,
)

CASES = json.loads((Path(__file__).parent / "fixtures" / "trace-note-cases.json")
                   .read_text(encoding="utf-8"))["cases"]


def test_the_cases_file_is_not_empty():
    """A missing or emptied fixture would make every parametrised test below vanish silently."""
    assert len(CASES) >= 15


@pytest.mark.parametrize("case", CASES, ids=[c["why"][:60] for c in CASES])
def test_trace_note_matches_the_hand_worked_cases(case):
    assert trace_note(case["run_started"], case["duration_s"], case["traced_at"]) == case["note"]


def test_the_window_is_a_quarter_of_an_hour_beyond_the_run():
    """The threshold is a decision, not an accident, so it is asserted rather than assumed."""
    assert TRACE_WITH_RUN_GRACE_S == 900


def test_trace_run_stamps_every_route_with_one_moment(monkeypatch):
    """One call is one act of tracing, so every entry it writes carries the same `traced_at`.

    The network is stubbed: what is under test is the stamp, not traceroute.
    """
    import datetime as dt

    from pingme import render_map
    from pingme.trace import Hop

    monkeypatch.setattr(render_map, "trace",
                        lambda ip: ([Hop(n=1, ip=None, avg_ms=None, loss_pct=None)], None))
    monkeypatch.setattr(render_map, "locate", lambda *a: None)
    run = {"analysis": {"origin": [53.8, -1.76]},
           "targets": [{"name": "router", "ip": "192.168.1.1", "kind": "gateway"},
                       {"name": "isp-hop", "ip": "10.0.0.1", "kind": "isp-hop"},
                       {"name": "london", "ip": "192.0.2.1", "kind": "relay"},
                       {"name": "madrid", "ip": "192.0.2.2", "kind": "relay"}]}

    before = dt.datetime.now(dt.UTC)
    traces = render_map.trace_run(run)
    after = dt.datetime.now(dt.UTC)

    assert list(traces) == ["london", "madrid"]  # the local hops are still not traced
    stamps = {entry["traced_at"] for entry in traces.values()}
    assert len(stamps) == 1
    when = dt.datetime.fromisoformat(stamps.pop())
    assert when.utcoffset() == dt.timedelta(0)  # an offset is written, and it is UTC
    assert before <= when <= after


def _trace_via_london() -> dict:
    """A route with one hop placed in London, so the map has a leg to draw and an end."""
    return {"error": None, "hops": [{"n": 1, "ip": "1.2.3.4", "avg_ms": 9.0, "loss_pct": 0.0}],
            "locations": [{"ip": "1.2.3.4", "lat": 51.5, "lon": -0.1, "city": "London",
                           "source": "ip-api", "hostname": None}]}


def test_map_labels_take_their_side_from_the_table_and_the_legend_sits_under_the_map():
    """The report map places its names as the explorer's does, from the one table.

    US-East's end point sits about four pixels from New York on a phone, so the two names
    go to opposite sides; every other end keeps "middle right" and every other landing
    "bottom center". The legend goes under the map, where it cannot cover North America.
    """
    run = json.loads((Path(__file__).parent / "fixtures" / "run.json").read_text())
    fig = map_figure(run, {"london": _trace_via_london(), "us-east": _trace_via_london()})

    ends = {t.meta["role"]: t.textposition for t in fig.data
            if t.mode == "markers+text" and t.meta and t.meta.get("role") in LABEL_SIDE}
    assert ends == {"london": "middle right", "us-east": "top left"}

    landings = next(t for t in fig.data if t.name == "cable landing points")
    sides = dict(zip(landings.text, landings.textposition, strict=True))
    assert sides == {name: LABEL_SIDE.get(name, "bottom center") for name in REFERENCE_POINTS}
    assert sides["New York"] == "bottom right"

    legend = fig.layout.legend
    assert (legend.orientation, legend.x, legend.xanchor, legend.y, legend.yanchor) == \
        ("h", 0, "left", 0, "top")
