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


def _two_target_results(router_slow: dict[int, float], london_slow: dict[int, float]):
    """Sixty idle probes each to the router and to london, with a few made slow.

    Probe k leaves at (k - 1) * 0.2 s and comes back a moment later, which is ping's
    own schedule; `router_slow` and `london_slow` say which probe answered slowly.
    """
    from pingme.probe import ProbeResult, Sample

    out = []
    for name, ip, base, slow in (("router", "10.0.0.1", 5.0, router_slow),
                                 ("london", "1.1.1.1", 20.0, london_slow)):
        r = ProbeResult(target=name, ip=ip)
        r.sent = 60
        r.samples = [Sample(seq, slow.get(seq, base), (seq - 1) * 0.2 + 0.01, "idle")
                     for seq in range(1, 61)]
        out.append(r)
    return out


def _analyse_targets(results, targets):
    from pingme.run import analyse

    no_route = {"dev": None, "src": None, "gateway": None}
    return analyse(results, targets, {}, {}, route=lambda ip: no_route)["targets"]


def test_stalls_count_the_spikes_and_say_how_many_the_router_shared():
    """Router slow on probes 51 and 52; london slow on probe 5 and on probe 52.

    Router: 58 replies of 5 ms and two of 100 gives a mean of 8.17 ms, so the cut is
    38.17 and both slow ones are spikes, 0.2 s apart, so one episode.
    London: 58 of 20 ms and two of 200 gives a mean of 26.0, so the cut is 56.0. Only
    the later of its two spikes lands beside a router spike, so its share is a half.
    """
    from pingme.targets import Target

    results = _two_target_results({51: 100.0, 52: 100.0}, {5: 200.0, 52: 200.0})
    entries = _analyse_targets(results, [Target("router", "10.0.0.1", "gateway"),
                                         Target("london", "1.1.1.1", "relay",
                                                lat=51.51, lon=-0.13)])
    router = entries["router"]["stalls"]
    assert router["threshold_ms"] == 30.0 and router["idle_mean_ms"] == 8.17
    assert router["spikes"] == 2
    assert router["episodes"] == [{"at_s": 10.01, "length_s": 0.2, "probes": 2}]
    assert router["router_coincidence"] is None  # the router cannot witness itself
    london = entries["london"]["stalls"]
    assert london["idle_mean_ms"] == 26.0 and london["spikes"] == 2
    assert london["episodes"] == [{"at_s": 0.81, "length_s": 0.0, "probes": 1},
                                  {"at_s": 10.21, "length_s": 0.0, "probes": 1}]
    assert london["router_coincidence"] == 0.5


def test_stalls_are_none_with_no_router_and_none_when_nothing_answered():
    from pingme.targets import Target

    results = _two_target_results({}, {5: 200.0, 52: 200.0})
    # the router renamed to something that is not a gateway: no witness left
    entries = _analyse_targets(results, [Target("router", "10.0.0.1", "relay",
                                                lat=51.51, lon=-0.13),
                                         Target("london", "1.1.1.1", "relay",
                                                lat=51.51, lon=-0.13)])
    assert entries["london"]["stalls"]["spikes"] == 2
    assert entries["london"]["stalls"]["router_coincidence"] is None
    # a silent address has no idle samples, so nobody could count: null, not zero
    silent = _analyse_one(_result(160, []), MARKS)
    assert silent["stalls"] is None


def test_a_target_with_no_coordinates_gets_no_physics_and_no_place_in_the_overhead():
    """The defect: an overridden Madrid slot answering in 12.6 ms zeroed the overhead.

    London answers in 20 ms from London itself, where a straight cable costs about
    nothing, so the overhead is the whole 20 ms. The unplaced target answers faster but
    is nowhere, so it cannot be measured against a cable and must not take part.
    """
    from pingme.probe import ProbeResult, Sample
    from pingme.run import analyse
    from pingme.targets import Target

    results = []
    for name, ip, rtt in (("london", "1.1.1.1", 20.0), ("madrid", "2.2.2.2", 12.6)):
        r = ProbeResult(target=name, ip=ip)
        r.sent = 3
        r.samples = [Sample(seq, rtt, (seq - 1) * 0.2 + 0.01, "idle") for seq in (1, 2, 3)]
        results.append(r)
    no_route = {"dev": None, "src": None, "gateway": None}
    out = analyse(results, [Target("london", "1.1.1.1", "relay", lat=51.51, lon=-0.13),
                            Target("madrid", "2.2.2.2", "custom")], {}, {},
                  route=lambda ip: no_route)
    assert out["local_overhead_ms"] == 20.0
    assert "london" in out["local_overhead_how"]
    assert "physics" not in out["targets"]["madrid"]
    assert "physics" in out["targets"]["london"]
    assert out["targets"]["madrid"]["kind"] == "custom"


def test_override_marks_the_slot_as_no_longer_being_where_it_says(monkeypatch):
    from pingme import run as run_module

    madrid = Target("madrid", "5.6.7.8", "relay", city="Madrid", lat=40.42, lon=-3.70,
                    note="valve relay mad")
    monkeypatch.setattr(run_module, "local_targets", lambda: [madrid])
    monkeypatch.setattr(run_module, "fetch_sdr", lambda: ({}, "cache"))
    monkeypatch.setattr(run_module, "parse_sdr", lambda cfg: [])
    monkeypatch.setenv("PINGME_OVERRIDE", "madrid=1.2.3.4")
    targets, _ = run_module._resolve_targets(lambda msg: None)
    t = targets[0]
    assert t.ip == "1.2.3.4" and t.kind == "custom"
    assert t.lat is None and t.lon is None and t.city is None
    assert "PINGME_OVERRIDE" in t.note and "no longer" in t.note
    assert "valve relay mad" in t.note  # the note it replaced is kept


def test_extra_targets_are_appended_as_addresses_with_no_place():
    from pingme.run import add_extra_targets

    existing = [Target("london", "1.1.1.1", "relay", lat=51.51, lon=-0.13)]
    out = add_extra_targets(existing, [("n475", "108.61.221.148")])
    assert [t.name for t in out] == ["london", "n475"]
    assert out[1].as_dict() == {"name": "n475", "ip": "108.61.221.148", "kind": "custom",
                                "city": None, "lat": None, "lon": None,
                                "note": "added with --target"}
    assert add_extra_targets(existing, None) == existing


def test_extra_target_will_not_take_a_name_that_is_already_in_use():
    import pytest

    from pingme.run import add_extra_targets

    existing = [Target("london", "1.1.1.1", "relay", lat=51.51, lon=-0.13)]
    with pytest.raises(ValueError, match="already a target called 'london'"):
        add_extra_targets(existing, [("london", "9.9.9.9")])
    with pytest.raises(ValueError, match="already a target called 'n475'"):
        add_extra_targets(existing, [("n475", "9.9.9.9"), ("n475", "8.8.8.8")])


def test_run_takes_a_note_and_extra_targets():
    import inspect

    from pingme.run import SCHEMA, run

    params = inspect.signature(run).parameters
    assert "note" in params and "extra" in params
    assert params["note"].default is None and params["extra"].default is None
    assert SCHEMA == 1
