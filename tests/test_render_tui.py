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
