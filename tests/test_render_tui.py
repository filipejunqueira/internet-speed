"""Draw a run in the terminal. Nothing here checks pixels; it checks that it draws at all.

A shadowed variable once put the burst count where the busy p95 belonged, and the
crash only appeared after a two-minute measurement run. These tests draw the whole
thing so that mistake cannot reach the terminal again.
"""

import copy
import io
import json
from pathlib import Path

from rich.console import Console

from pingme.render_tui import render

FIXTURE = Path(__file__).parent / "fixtures" / "run.json"


def _draw(run: dict, width: int = 160) -> str:
    out = io.StringIO()
    render(run, Console(file=out, width=width, force_terminal=False, legacy_windows=False))
    return out.getvalue()


def _summary_row(drawn: str, name: str) -> list[str]:
    """The cells of one target's row in the summary table at the end of the output."""
    table = drawn.split("summary", 1)[1]
    row = next(line for line in table.splitlines()
               if f"│ {name}" in line and line.count("│") > 5)
    return [c.strip() for c in row.strip().strip("│").split("│")]


def test_a_run_saved_before_bursts_were_counted_still_draws():
    drawn = _draw(json.loads(FIXTURE.read_text()))
    assert "summary" in drawn
    for name in ("router", "london", "madrid", "us-east", "sao-paulo"):
        assert name in drawn


def test_the_summary_table_puts_every_number_in_its_own_column():
    """The busy p95 and the burst count are different things in adjacent columns."""
    run = json.loads(FIXTURE.read_text())
    london = run["analysis"]["targets"]["london"]
    london["silent"] = False
    london["loss"] = {"lost": [[40, 8.0], [41, 8.2], [42, 8.4]],
                      "longest_burst_probes": 3, "longest_burst_s": 0.6,
                      "longest_burst_at_s": 8.0}
    cells = _summary_row(_draw(run), "london")
    # target, loss, burst, best, median, p95, p99, jitter, busy p95, route
    assert cells[0] == "london"
    assert cells[2] == "3", "the burst count belongs in the burst column"
    assert cells[8] == f"{london['busy']['p95_ms']:.1f}", "and the busy p95 in its own"


def test_a_silent_target_draws_a_plain_panel_not_a_crash():
    run = json.loads(FIXTURE.read_text())
    quiet = copy.deepcopy(run["analysis"]["targets"]["madrid"])
    quiet.update(silent=True, samples=[], loss=None)
    for phase in ("all", "idle", "busy"):
        quiet[phase]["loss_pct"] = None
    quiet["all"]["received"] = 0
    run["analysis"]["targets"]["isp-hop"] = quiet
    drawn = _draw(run)
    assert "does not answer probes" in drawn


def _with_stalls(run: dict) -> dict:
    """The fixture with a router that stalled twice and a London that stalled with it.

    The fixture's samples span about 0 to 30 s, so the episodes are put inside that span:
    plotext folds a vertical line's position into the axis limits, and a band at 300 s
    would stretch the plot away from the data.
    """
    targets = run["analysis"]["targets"]
    targets["router"]["stalls"] = {
        "threshold_ms": 30.0, "idle_mean_ms": 3.1, "spikes": 5,
        "episodes": [{"at_s": 8.0, "length_s": 0.6, "probes": 4},
                     {"at_s": 22.0, "length_s": 0.0, "probes": 1}],
        "router_coincidence": None}
    if "london" in targets:
        targets["london"]["stalls"] = {
            "threshold_ms": 30.0, "idle_mean_ms": 12.43, "spikes": 4,
            "episodes": [{"at_s": 8.2, "length_s": 0.4, "probes": 3}],
            "router_coincidence": 0.75}
    return run


def test_where_the_router_stall_band_is_drawn():
    """Hand-computed: the band is a line per character column, a second either side.

    Over 0 to 100 s in 50 columns each column is 2 s wide. A stall of no length at 10 s
    is shaded from 9 to 11 s, which is two lines; one lasting 6 s from 20 s is shaded
    from 19 to 27 s, which is five.
    """
    from pingme.render_tui import _band_x

    assert _band_x([{"at_s": 10.0, "length_s": 0.0, "probes": 1}], 0.0, 100.0, 50) == [9.0, 11.0]
    assert _band_x([{"at_s": 20.0, "length_s": 6.0, "probes": 9}], 0.0, 100.0, 50) == [
        19.0, 21.0, 23.0, 25.0, 27.0]
    # a stall before the run's first sample would stretch the axis, so it is dropped
    assert _band_x([{"at_s": 0.2, "length_s": 0.0, "probes": 1}], 5.0, 100.0, 50) == []
    assert _band_x([], 0.0, 100.0, 50) == []


def test_the_band_reaches_the_timeline_but_never_the_routers_own_panel():
    from pingme.render_tui import _timeline

    run = _with_stalls(json.loads(FIXTURE.read_text()))
    london = run["analysis"]["targets"]["london"]
    episodes = run["analysis"]["targets"]["router"]["stalls"]["episodes"]
    assert str(_timeline(london, 60, 12, episodes)) != str(_timeline(london, 60, 12, None))

    # the router's own panel: same record with and without its stalls block draws the same
    only_router = json.loads(FIXTURE.read_text())
    only_router["analysis"]["targets"] = {"router": only_router["analysis"]["targets"]["router"]}
    plain = _draw(only_router).split("summary")[0]
    banded = _draw(_with_stalls(only_router)).split("summary")[0]
    assert plain == banded


def test_the_busy_p95_says_how_many_probes_it_rests_on():
    """A ten-minute run is busy for twenty seconds, so the penalty rests on a few dozen."""
    run = json.loads(FIXTURE.read_text())
    sent = run["analysis"]["targets"]["london"]["busy"]["sent"]
    assert f"({sent} probes)" in _draw(run)


def test_the_summary_table_counts_spikes_and_says_who_stalled_with_them():
    drawn = _draw(_with_stalls(json.loads(FIXTURE.read_text())))
    # target, loss, burst, best, median, p95, p99, jitter, busy p95, spikes, with router, route
    assert _summary_row(drawn, "london")[9:11] == ["4", "75%"]
    # the router is the witness, so it has no share of its own
    assert _summary_row(drawn, "router")[9:11] == ["5", "—"]
    # a record saved before stalls were counted claims nothing for either column
    assert _summary_row(drawn, "madrid")[9:11] == ["—", "—"]


def test_a_counted_zero_is_not_an_em_dash():
    """Nothing spiked, and the router did not spike with it: both are findings, not gaps."""
    run = _with_stalls(json.loads(FIXTURE.read_text()))
    run["analysis"]["targets"]["us-east"]["stalls"] = {
        "threshold_ms": 30.0, "idle_mean_ms": 88.0, "spikes": 0, "episodes": [],
        "router_coincidence": None}
    run["analysis"]["targets"]["sao-paulo"]["stalls"] = {
        "threshold_ms": 30.0, "idle_mean_ms": 210.0, "spikes": 3,
        "episodes": [{"at_s": 5.0, "length_s": 0.2, "probes": 2}],
        "router_coincidence": 0.0}
    drawn = _draw(run)
    assert _summary_row(drawn, "us-east")[9:11] == ["0", "—"]
    assert _summary_row(drawn, "sao-paulo")[9:11] == ["3", "0%"]


def test_a_target_added_by_hand_gets_no_route_verdict():
    """It was measured, not placed, so it has no physics block and must claim no route."""
    run = json.loads(FIXTURE.read_text())
    custom = copy.deepcopy(run["analysis"]["targets"]["london"])
    custom.update(kind="custom", ip="108.61.221.148")
    custom.pop("physics")
    run["analysis"]["targets"]["n475"] = custom
    drawn = _draw(run)
    assert "n475" in drawn
    assert _summary_row(drawn, "n475")[11] == ""


def test_the_route_verdict_says_it_is_the_closest_guess_not_a_measurement():
    drawn = _draw(json.loads(FIXTURE.read_text()))
    assert "closest of 3 routes considered" in drawn  # sao-paulo has three candidates
    assert "closest of 1 route considered" in drawn  # london has one


def test_the_run_note_is_shown_as_typed():
    """--label is scrubbed into the run id; the note is what survives it, verbatim."""
    run = json.loads(FIXTURE.read_text())
    run["note"] = "route=mudfish475 [check this]"
    assert "note: route=mudfish475 [check this]" in _draw(run)
    assert "note:" not in _draw(json.loads(FIXTURE.read_text()))
