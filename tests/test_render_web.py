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


def _doctored():
    """The fixture with one target losing a burst of three, and one that never answers."""
    run = json.loads(FIXTURE.read_text())
    london = run["analysis"]["targets"]["london"]
    london["silent"] = False
    london["loss"] = {"lost": [[40, 8.0], [41, 8.2], [42, 8.4], [90, 18.0]],
                      "longest_burst_probes": 3, "longest_burst_s": 0.6,
                      "longest_burst_at_s": 8.0}
    quiet = run["analysis"]["targets"]["madrid"]
    quiet.update(silent=True, samples=[], loss=None)
    for phase in ("all", "idle", "busy"):
        quiet[phase]["loss_pct"] = None
    quiet["all"]["received"] = 0
    return run


def test_lost_probes_are_drawn_and_a_silent_target_gets_no_loss_figure():
    html = build_report(_doctored())
    assert html.count('"name":"lost"') == 1  # only the target that lost probes
    assert "longest burst 3 probes" in html
    assert "does not answer probes" in html
    assert 'id="target-madrid"' in html  # the silent one still gets its own section


def test_a_silent_target_never_becomes_the_worst_loss():
    """It answers nothing by design, so 100 % would drown out the real numbers."""
    html = build_report(_doctored())
    tile = html.split('<div class="label">worst packet loss</div>')[1][:200]
    assert "1.3%" in tile  # sao-paulo in the fixture, not the silent target
    assert "100.0%" not in tile


def test_a_single_lost_probe_is_not_a_green_tick():
    from pingme.render_web import _loss_status

    assert _loss_status(0, 0.0)[0] == "good"
    assert _loss_status(1, 0.67)[0] == "warning"
    assert _loss_status(15, 1.0)[0] == "serious"
    assert _loss_status(75, 5.0)[0] == "critical"
    assert _loss_status(None, None)[0] == "muted"
