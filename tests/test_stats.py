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
