import datetime as dt

from pingme.run import flag_odd_routes, make_run_id
from pingme.targets import Target


def test_flag_odd_routes_names_the_target_on_the_wrong_interface():
    targets = [Target("london", "1.1.1.1", "relay"), Target("sao-paulo", "2.2.2.2", "relay")]
    routes = {"1.1.1.1": {"dev": "wlan0"}, "2.2.2.2": {"dev": "tailscale0"}}
    messages = []
    odd = flag_odd_routes(targets, "wlan0", messages.append, route=lambda ip: routes[ip])
    assert odd == ["sao-paulo"]
    assert "tailscale0" in messages[0] and "sao-paulo" in messages[0]


def test_run_id_is_label_plus_utc_stamp():
    when = dt.datetime(2026, 8, 29, 21, 0, 0, tzinfo=dt.UTC)
    assert make_run_id("airbnb leeds!", when) == "airbnb_leeds_2026-08-29T21-00-00Z"
    assert make_run_id(None, when) == "2026-08-29T21-00-00Z"


def test_run_accepts_trace_flag():
    import inspect

    from pingme.run import run

    assert "trace" in inspect.signature(run).parameters


def _result(sent: int, replied, phase_of=lambda seq: "idle"):
    """A probe result on ping's schedule: probe k leaves at (k-1)*0.2 s, back 10 ms later."""
    from pingme.probe import ProbeResult, Sample

    r = ProbeResult(target="london", ip="1.1.1.1")
    r.sent = sent
    r.samples = [Sample(seq, 10.0, (seq - 1) * 0.2 + 0.01, phase_of(seq)) for seq in replied]
    return r


def _analyse_one(result, marks):
    from pingme.run import analyse
    from pingme.targets import Target

    no_route = {"dev": None, "src": None, "gateway": None}
    out = analyse([result], [Target("london", "1.1.1.1", "relay")], {}, marks,
                  route=lambda ip: no_route)
    return out["targets"]["london"]


# the speed test runs from 1.1 s to 3.1 s, so probes 7 to 11 come back while it is busy
MARKS = {"download": 1.1, "upload": 2.1, "idle-again": 3.1}


def _phase_of(seq: int) -> str:
    return "download" if 7 <= seq <= 11 else "idle"


def test_idle_loss_ignores_the_probes_sent_during_the_speed_test():
    """The idle phase runs before and after the busy one, so its span is not its count."""
    replied = [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15]  # probe 8 lost, at 1.4 s
    entry = _analyse_one(_result(15, replied, _phase_of), MARKS)
    assert entry["idle"]["sent"] == 10 and entry["idle"]["received"] == 10
    assert entry["idle"]["loss_pct"] == 0.0
    assert entry["busy"]["sent"] == 5 and entry["busy"]["received"] == 4
    assert entry["busy"]["loss_pct"] == 20.0
    assert entry["all"]["sent"] == 15 and entry["all"]["received"] == 14
    assert entry["loss"]["lost"] == [[8, 1.4]]
    assert entry["loss"]["longest_burst_probes"] == 1
    assert entry["loss"]["longest_burst_at_s"] == 1.4


def test_a_burst_of_three_is_reported_with_its_length_and_start():
    replied = [1, 2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 15]  # 7, 8, 9 lost together
    entry = _analyse_one(_result(15, replied, _phase_of), MARKS)
    assert entry["loss"]["longest_burst_probes"] == 3
    assert entry["loss"]["longest_burst_s"] == 0.6
    assert entry["loss"]["longest_burst_at_s"] == 1.2
    assert [seq for seq, _ in entry["loss"]["lost"]] == [7, 8, 9]
    assert entry["busy"]["sent"] == 5 and entry["busy"]["received"] == 2
    assert entry["idle"]["sent"] == 10 and entry["idle"]["loss_pct"] == 0.0


def test_a_target_that_never_answers_reports_no_loss_figure():
    entry = _analyse_one(_result(160, []), MARKS)
    assert entry["silent"] is True
    assert entry["all"]["sent"] == 160 and entry["all"]["received"] == 0
    assert all(entry[phase]["loss_pct"] is None for phase in ("all", "idle", "busy"))
    assert entry["loss"] is None


def test_a_target_whose_ping_failed_is_not_silent():
    result = _result(160, [])
    result.error = "ping not found"
    entry = _analyse_one(result, MARKS)
    assert entry["silent"] is False
    assert entry["all"]["loss_pct"] == 100.0
