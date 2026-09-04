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


def test_a_run_saved_before_bursts_were_counted_does_not_claim_a_clean_one():
    """The fixture predates burst counting: the tile must say so, not show a green 0."""
    html = build_report(json.loads(FIXTURE.read_text()))
    tile = html.split('<div class="label">longest burst</div>')[1][:220]
    assert "not counted on this run" in tile
    assert "badge good" not in tile


def test_an_old_records_silent_hop_no_longer_wins_worst_loss():
    """Runs saved before this marked a silent hop as the error "no replies" at 100 %."""
    from pingme.store import summary_row

    run = json.loads(FIXTURE.read_text())
    hop = json.loads(json.dumps(run["analysis"]["targets"]["router"]))  # a deep copy
    hop.update(samples=[], error="no replies")
    for phase in ("all", "idle", "busy"):
        hop[phase].update(received=0, loss_pct=100.0)
    run["analysis"]["targets"]["isp-hop"] = hop

    tile = build_report(run).split('<div class="label">worst packet loss</div>')[1][:150]
    assert "100.0%" not in tile
    assert summary_row(run)["worst_loss_pct"] != 100.0
    assert summary_row(run)["worst_burst_probes"] is None


def test_the_report_shows_every_hop_and_what_it_adds():
    run = json.loads(FIXTURE.read_text())
    traces = {"london": {"error": None,
                         "hops": [{"n": 1, "ip": "192.168.1.1", "avg_ms": 1.0, "loss_pct": 0.0},
                                  {"n": 2, "ip": None, "avg_ms": None, "loss_pct": None},
                                  {"n": 3, "ip": "1.2.3.4", "avg_ms": 12.0, "loss_pct": 0.0}],
                         "locations": [None, None,
                                       {"ip": "1.2.3.4", "lat": 51.5, "lon": -0.1,
                                        "city": "London", "source": "ip-api",
                                        "hostname": "edge.example.net"}]}}
    html = build_report(run, traces)
    assert "every hop, and where the time goes" in html
    assert "edge.example.net" in html
    assert "+11.0" in html  # 12.0 ms at hop 3, on top of the 1.0 ms at hop 1
    assert "no reply" in html  # hop 2 keeps its place in the numbering


def test_a_published_map_reads_the_world_from_the_site_not_a_cdn():
    """A report page sits in runs/, one level under the copy of the world beside plotly.js."""
    from pingme.render_web import PLOTLY_ASSET, _plot_config

    run = json.loads(FIXTURE.read_text())
    traces = {"london": {"error": None,
                         "hops": [{"n": 1, "ip": "1.2.3.4", "avg_ms": 9.0, "loss_pct": 0.0}],
                         "locations": [{"ip": "1.2.3.4", "lat": 51.5, "lon": -0.1,
                                        "city": "London", "source": "ip-api",
                                        "hostname": None}]}}
    published = build_report(run, traces, plotly="external")
    assert '"topojsonURL": "../assets/"' in published

    # A report written locally has no such copy beside it, and a map that does not draw is
    # worse than a map that is slow, so that one is left pointing at plotly's own default.
    # Quoted and followed by a colon: that is how the config is written into the page, and
    # unlike the bare word it does not also appear inside the embedded plotly bundle.
    assert '"topojsonURL":' not in build_report(run, traces)
    assert _plot_config(None).get("topojsonURL") is None
    assert _plot_config("../" + PLOTLY_ASSET)["topojsonURL"] == "../assets/"


def _with_stalls():
    """The fixture with a router that stalled twice, and a London that stalled with it."""
    run = json.loads(FIXTURE.read_text())
    targets = run["analysis"]["targets"]
    targets["router"]["stalls"] = {
        "threshold_ms": 30.0, "idle_mean_ms": 3.1, "spikes": 5,
        "episodes": [{"at_s": 8.0, "length_s": 0.6, "probes": 4},
                     {"at_s": 22.0, "length_s": 0.0, "probes": 1}],
        "router_coincidence": None}
    targets["london"]["stalls"] = {
        "threshold_ms": 30.0, "idle_mean_ms": 12.43, "spikes": 4,
        "episodes": [{"at_s": 8.2, "length_s": 0.4, "probes": 3}],
        "router_coincidence": 0.75}
    targets["us-east"]["stalls"] = {
        "threshold_ms": 30.0, "idle_mean_ms": 88.0, "spikes": 0, "episodes": [],
        "router_coincidence": None}
    targets["sao-paulo"]["stalls"] = {
        "threshold_ms": 30.0, "idle_mean_ms": 210.0, "spikes": 3,
        "episodes": [{"at_s": 5.0, "length_s": 0.2, "probes": 2}],
        "router_coincidence": 0.0}
    return run


def test_the_busy_p95_says_how_many_probes_it_rests_on():
    """A ten-minute run is busy for twenty seconds, so the penalty rests on a few dozen."""
    run = json.loads(FIXTURE.read_text())
    london = run["analysis"]["targets"]["london"]
    penalty = london["busy"]["p95_ms"] - london["idle"]["p95_ms"]
    assert (f"under-load penalty {penalty:+.0f} ms ({london['busy']['sent']} busy probes)"
            in build_report(run))


def test_the_spike_fact_keeps_a_counted_zero_apart_from_an_uncounted_one():
    from pingme.render_web import _stall_fact

    counted = {"threshold_ms": 30.0, "idle_mean_ms": 12.43, "spikes": 36,
               "episodes": [], "router_coincidence": 0.75}
    assert _stall_fact({"stalls": counted}) == "spikes 36 (with a router stall: 75 %)"
    # the router is the witness, so it has no share of its own
    assert _stall_fact({"stalls": {**counted, "router_coincidence": None}}) == \
        "spikes 36 (with a router stall: —)"
    # it spiked and the router did not: a finding, and it must not read as a gap
    assert _stall_fact({"stalls": {**counted, "router_coincidence": 0.0}}) == \
        "spikes 36 (with a router stall: 0 %)"
    assert _stall_fact({"stalls": {**counted, "spikes": 0}}) == \
        "spikes 0 (with a router stall: 75 %)"
    # a record saved before stalls were counted claims nothing at all
    assert _stall_fact({}) is None
    assert _stall_fact({"stalls": None}) is None


def test_an_older_record_says_nothing_about_spikes():
    html = build_report(json.loads(FIXTURE.read_text()))
    assert "(with a router stall:" not in html


def test_the_spike_figures_reach_the_target_sections():
    html = build_report(_with_stalls())
    assert "spikes 4 (with a router stall: 75 %)" in html
    assert "spikes 3 (with a router stall: 0 %)" in html
    assert "spikes 0 (with a router stall: —)" in html


def test_the_router_stall_band_is_drawn_behind_the_points():
    """Hand-computed: each band runs a second either side of the stall it marks."""
    from pingme.render_web import _timeline

    run = _with_stalls()
    episodes = run["analysis"]["targets"]["router"]["stalls"]["episodes"]
    # no phase marks, so the only shapes on this figure are the stall bands
    shapes = _timeline(run["analysis"]["targets"]["london"], {}, episodes).layout.shapes
    assert [(s.x0, s.x1) for s in shapes] == [(7.0, 9.6), (21.0, 23.0)]
    assert all(s.layer == "below" for s in shapes)
    assert not _timeline(run["analysis"]["targets"]["london"], {}, None).layout.shapes


def test_a_stall_in_the_first_second_does_not_push_the_axis_before_zero():
    """Plotly widens an axis to fit a shape, so the band is trimmed to the samples' span.

    A real 30 s run had the router stall 0.06 s in; widened by the coincidence window
    that band starts at -0.94 s, and the timeline would have opened on a negative second.
    """
    from pingme.render_web import _timeline

    run = json.loads(FIXTURE.read_text())
    london = run["analysis"]["targets"]["london"]
    first = min(s[2] for s in london["samples"])
    last = max(s[2] for s in london["samples"])
    shapes = _timeline(london, {}, [{"at_s": first + 0.02, "length_s": 0.0, "probes": 1},
                                    {"at_s": last - 0.02, "length_s": 0.0, "probes": 1}]
                       ).layout.shapes
    assert [(s.x0, s.x1) for s in shapes] == [(first, first + 1.02), (last - 1.02, last)]
    # a stall wholly outside this target's samples shades nothing at all
    assert not _timeline(london, {}, [{"at_s": last + 50, "length_s": 0.0, "probes": 1}]
                         ).layout.shapes


def test_every_target_but_the_router_gets_the_band():
    """The router's own stalls behind its own spikes would say nothing."""
    run = _with_stalls()
    targets = run["analysis"]["targets"]
    html = build_report(run)
    assert html.count('"fillcolor":"#898781"') == 2 * (len(targets) - 1)  # two stalls each
    # and the one section without a band is the router's, not somebody else's
    router = html.split('id="target-router"')[1].split("</section>")[0]
    assert '"fillcolor":"#898781"' not in router
    assert build_report(json.loads(FIXTURE.read_text())).count('"fillcolor":"#898781"') == 0


def test_the_run_note_is_shown_and_escaped():
    """--label is scrubbed into the run id; the note is what survives it, verbatim."""
    run = json.loads(FIXTURE.read_text())
    run["note"] = "route=mudfish475 <check this>"
    html = build_report(run)
    assert "note: route=mudfish475 &lt;check this&gt;" in html
    assert "<check this>" not in html
    assert "note:" not in build_report(json.loads(FIXTURE.read_text()))


def test_a_target_added_by_hand_claims_no_route():
    """It was measured, not placed, so it has no physics block and must claim no route."""
    run = json.loads(FIXTURE.read_text())
    custom = json.loads(json.dumps(run["analysis"]["targets"]["london"]))
    custom.update(kind="custom", ip="108.61.221.148")
    custom.pop("physics")
    run["analysis"]["targets"]["n475"] = custom
    html = build_report(run)
    section = html.split('id="target-n475"')[1].split("</section>")[0]
    assert "timing estimate" not in section
    assert "108.61.221.148" in section


def test_the_route_verdict_says_it_is_the_closest_guess_not_a_measurement():
    from pingme.render_web import _closest_of

    assert _closest_of({"candidates": [1, 2, 3]}) == "closest of 3 routes considered"
    assert _closest_of({"candidates": [1]}) == "closest of 1 route considered"
    assert _closest_of({}) == "closest of 0 routes considered"
    html = build_report(json.loads(FIXTURE.read_text()))
    assert "closest of 3 routes considered" in html  # sao-paulo, in its section and its tile
