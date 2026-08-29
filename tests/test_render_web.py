import json
from pathlib import Path

from pingme.render_web import build_report

FIXTURE = Path(__file__).parent / "fixtures" / "run.json"


def test_report_has_one_section_per_target_and_plotly_once():
    run = json.loads(FIXTURE.read_text())
    html = build_report(run)
    for name in run["analysis"]["targets"]:
        assert f'id="target-{name}"' in html
    figures = html.count('class="plotly-graph-div"')
    assert figures >= 2 * len(run["analysis"]["targets"])  # histogram + timeline each
    assert html.count("<script>") == figures + 2  # one per figure, plotly.js once, theme once
    assert '"color":"#2a78d6"' in html  # the validated idle hue reaches a figure


def test_report_is_deterministic():
    run = json.loads(FIXTURE.read_text())
    assert build_report(run) == build_report(run)
