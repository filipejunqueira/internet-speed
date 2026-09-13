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

from pingme.render_map import TRACE_WITH_RUN_GRACE_S, trace_note

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
