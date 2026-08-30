from pingme.geo import _from_hostname, _is_private
from pingme.trace import parse_traceroute

REPORT = """traceroute to 162.254.196.66 (162.254.196.66), 40 hops max, 60 byte packets
 1  192.168.0.1  3.464 ms  2.936 ms  4.800 ms
 2  * * *
 3  162.254.196.66  71.8 ms  * 56.2 ms
"""


def test_parse_traceroute_keeps_hidden_hops():
    hops = parse_traceroute(REPORT)
    assert [h.ip for h in hops] == ["192.168.0.1", None, "162.254.196.66"]
    assert hops[0].avg_ms == 3.7 and hops[2].loss_pct == 33.3 and hops[2].avg_ms == 64.0
    assert hops[1].avg_ms is None


def test_hostname_city_code():
    assert _from_hostname("ae1-0.lhr2.core.example.net")[0] == "London"
    assert _from_hostname("be100.gru.br.example.com")[0] == "São Paulo"
    assert _from_hostname("router.example.com") is None
    assert _from_hostname("format.example.com") is None  # "for" must not match "format"


def test_private_ranges():
    assert _is_private("192.168.0.1") and _is_private("100.64.3.4") and _is_private("10.0.0.1")
    assert not _is_private("162.254.196.66")


def test_path_cities_collapses_repeats_and_marks_hidden_runs():
    from pingme.render_map import path_cities

    entry = {"locations": [
        {"city": "London", "lat": 51.5, "lon": -0.1}, {"city": "London", "lat": 51.5, "lon": -0.1},
        None, None, {"city": "Madrid", "lat": 40.4, "lon": -3.7},
        {"city": None, "lat": None, "lon": None},
        {"city": "São Paulo", "lat": -23.5, "lon": -46.6}]}
    assert path_cities(entry) == ["London", "…", "Madrid", "…", "São Paulo"]
