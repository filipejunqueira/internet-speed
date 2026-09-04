import json
from pathlib import Path

from pingme.stats import RouteCandidate, haversine_km, jitter, physics_verdict, summarise


def test_summarise_basic():
    s = summarise([10.0, 20.0, 30.0, 40.0], sent=5)
    assert s.sent == 5 and s.received == 4
    assert s.loss_pct == 20.0
    assert s.min_ms == 10.0 and s.max_ms == 40.0
    assert s.median_ms == 25.0 and s.mean_ms == 25.0


def test_summarise_no_replies():
    s = summarise([], sent=10)
    assert s.loss_pct == 100.0 and s.median_ms is None


def test_jitter_is_mean_abs_consecutive_difference():
    assert jitter([10.0, 12.0, 9.0]) == (2.0 + 3.0) / 2
    assert jitter([5.0]) == 0.0


def test_haversine_leeds_london():
    assert 260 < haversine_km((53.8, -1.55), (51.5, -0.13)) < 285


def test_physics_verdict_rules_out_too_long_route():
    leeds, sao_paulo = (53.8, -1.55), (-23.55, -46.63)
    ella = RouteCandidate("ellalink", [(37.95, -8.87), (-3.73, -38.52)])
    via_us = RouteCandidate("via-usa", [(40.71, -74.0), (25.77, -80.19)])
    # 180 ms effective: both possible, US is the closer realistic match
    eff, verdicts, best = physics_verdict(220.0, 40.0, leeds, sao_paulo, [ella, via_us])
    assert eff == 180.0 and best == "via-usa"
    assert not any(v.ruled_out for v in verdicts)
    # 120 ms effective: the US route's floor (~142 ms) is impossible
    _, verdicts, best = physics_verdict(160.0, 40.0, leeds, sao_paulo, [ella, via_us])
    assert best == "ellalink"
    assert [v.ruled_out for v in verdicts] == [False, True]


def test_lost_seqs_finds_the_gaps_in_the_sequence():
    from pingme.stats import lost_seqs

    assert lost_seqs(6, [1, 2, 4, 6]) == [3, 5]
    assert lost_seqs(4, [1, 2, 3, 4]) == []
    assert lost_seqs(3, []) == [1, 2, 3]
    assert lost_seqs(0, []) == []


def test_longest_burst_takes_the_longest_run_earliest_first():
    from pingme.stats import longest_burst

    assert longest_burst([]) == (0, 0)
    assert longest_burst([5]) == (1, 5)
    assert longest_burst([7, 8, 9, 20]) == (3, 7)
    assert longest_burst([2, 3, 10, 11]) == (2, 2)  # a tie goes to the earlier burst
    assert longest_burst([1, 4, 5, 6, 7, 30]) == (4, 4)


def test_summary_without_loss_keeps_every_other_number():
    from pingme.stats import summarise

    s = summarise([10.0, 20.0], sent=100).without_loss()
    assert s.loss_pct is None
    assert s.sent == 100 and s.received == 2 and s.median_ms == 15.0


def test_spike_times_uses_the_idle_mean_and_ignores_the_speed_test():
    """Four idle replies of 10 ms and one of 110: the mean is 30, so the cut is 60."""
    from pingme.stats import spike_times

    samples = [(1, 10.0, 0.0, "idle"), (2, 10.0, 0.2, "idle"), (3, 110.0, 0.4, "idle"),
               (4, 10.0, 0.6, "idle"), (5, 10.0, 0.8, "idle"),
               (6, 500.0, 1.0, "download")]  # slow on purpose, so not a stall
    times, mean = spike_times(samples)
    assert mean == 30.0
    assert times == [0.4]


def test_spike_times_takes_the_threshold_it_is_given():
    from pingme.stats import spike_times

    samples = [(i + 1, rtt, i * 0.5, "idle") for i, rtt in enumerate([10.0, 20.0, 30.0, 40.0])]
    assert spike_times(samples, threshold_ms=10.0)[0] == [1.5]  # mean 25, cut 35
    assert spike_times(samples, threshold_ms=4.0)[0] == [1.0, 1.5]  # cut 29


def test_spike_times_with_no_idle_samples_says_nobody_could_count():
    from pingme.stats import spike_times

    assert spike_times([]) == ([], None)
    assert spike_times([(1, 10.0, 0.0, "download")]) == ([], None)


def test_episodes_group_spikes_that_are_close_together():
    from pingme.stats import episodes

    assert episodes([]) == []
    assert episodes([10.0, 10.4, 10.8, 12.9, 20.0]) == [
        {"at_s": 10.0, "length_s": 0.8, "probes": 3},  # 12.9 is 2.1 s later, so a new one
        {"at_s": 12.9, "length_s": 0.0, "probes": 1},
        {"at_s": 20.0, "length_s": 0.0, "probes": 1},
    ]


def test_episodes_take_the_gap_they_are_given():
    from pingme.stats import episodes

    assert episodes([10.0, 12.9], gap_s=5.0) == [{"at_s": 10.0, "length_s": 2.9, "probes": 2}]


def test_coincidence_is_the_share_of_spikes_a_router_spike_sat_beside():
    from pingme.stats import coincidence

    # a router stall from 10 s to 12 s, and one target spike in the middle of it
    router = [10.0, 10.5, 11.0, 11.5, 12.0]
    assert coincidence([11.0], router) == 1.0
    assert coincidence([20.0], router) == 0.0
    # 1.0 is 0.5 s from a router spike; 5.0 and 9.0 are nowhere near one
    assert coincidence([1.0, 5.0, 9.0], [1.5, 100.0]) == 0.33


def test_coincidence_is_none_when_there_is_nothing_to_count_or_no_witness():
    from pingme.stats import coincidence

    assert coincidence([], [1.0, 2.0]) is None  # this target never spiked
    assert coincidence([1.0], []) is None  # the router never spiked, so it saw nothing
    assert coincidence([], []) is None


# The 10-minute run this whole feature was built to explain, trimmed to the idle samples
# of the four targets that answered and committed as a fixture. It lives in the repository
# rather than being read out of the user's own log, because these are the numbers the work
# was accepted on: a test that skips when the log is absent would report green on any other
# machine with the acceptance evidence quietly not run.
SANTANDER_FIXTURE = Path(__file__).parent / "fixtures" / "santander-idle-samples.json"
SANTANDER_ID = "baseline-day-santander_2026-09-03T12-47-31Z"


def _santander_record() -> dict:
    record = json.loads(SANTANDER_FIXTURE.read_text())
    assert record["id"] == SANTANDER_ID, "the fixture is not the run these numbers came from"
    return {"analysis": {"targets": record["targets"]}}


def _idle_spikes(record: dict) -> dict[str, list[float]]:
    from pingme.stats import spike_times

    return {name: spike_times(entry["samples"])[0]
            for name, entry in record["analysis"]["targets"].items()}


def test_santander_run_shows_the_wifi_link_stalling_about_every_35_seconds():
    """The 10-minute run this whole feature was built to explain.

    Every target spikes, and about three quarters of each one's spikes sit within a
    second of a router spike, which says the local link stalled and the relays merely
    inherited it. The counts are what the plan recorded on 2026-09-04.
    """
    from pingme.stats import coincidence

    spikes = _idle_spikes(_santander_record())
    assert {n: len(t) for n, t in spikes.items() if n in
            ("router", "london", "us-east", "sao-paulo")} == {
        "router": 36, "london": 36, "us-east": 74, "sao-paulo": 34}
    assert coincidence(spikes["london"], spikes["router"]) == 0.75
    assert coincidence(spikes["us-east"], spikes["router"]) == 0.72
    assert coincidence(spikes["sao-paulo"], spikes["router"]) == 0.71


def test_santander_router_stalls_come_in_episodes_seconds_apart():
    from pingme.stats import episodes

    eps = episodes(_idle_spikes(_santander_record())["router"])
    starts = [e["at_s"] for e in eps]
    gaps = [round(b - a) for a, b in zip(starts, starts[1:], strict=False)]
    assert gaps == [35, 32, 237, 80, 33, 36]
    assert sum(e["probes"] for e in eps) == 36


def test_santander_silent_isp_hop_has_no_idle_samples_to_count():
    """It never answers, so nobody could count its spikes. That is not zero spikes."""
    from pingme.stats import spike_times

    entry = _santander_record()["analysis"]["targets"]["isp-hop"]
    assert entry["samples"] == []
    assert spike_times(entry["samples"]) == ([], None)
