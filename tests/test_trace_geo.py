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


def test_hop_rows_say_what_each_hop_adds_over_the_last_one_that_answered():
    from pingme.render_map import hop_rows

    entry = {
        "hops": [
            {"n": 1, "ip": "192.168.1.1", "avg_ms": 1.0, "loss_pct": 0.0},
            {"n": 2, "ip": None, "avg_ms": None, "loss_pct": None},
            {"n": 3, "ip": "10.0.0.1", "avg_ms": 9.0, "loss_pct": 66.7},
            {"n": 4, "ip": "1.2.3.4", "avg_ms": 48.0, "loss_pct": 0.0},
        ],
        "locations": [
            {"ip": "192.168.1.1", "lat": None, "lon": None, "city": None,
             "source": "private", "hostname": None},
            None,
            {"ip": "10.0.0.1", "lat": 51.5, "lon": -0.1, "city": "London",
             "source": "ripe-ipmap", "hostname": "core.example.net"},
            {"ip": "1.2.3.4", "lat": 40.4, "lon": -3.7, "city": "Madrid",
             "source": "ip-api", "hostname": None},
        ],
    }
    rows = hop_rows(entry)
    assert [r["n"] for r in rows] == [1, 2, 3, 4]
    assert rows[0]["step_ms"] is None  # nothing before it to add to
    assert rows[1]["ip"] is None and rows[1]["ms"] is None
    assert rows[2]["step_ms"] == 8.0  # 9.0 over the 1.0 of hop 1, skipping the silent hop
    assert rows[2]["place"] == "London" and rows[2]["hostname"] == "core.example.net"
    assert rows[2]["no_reply"] == 2  # two of the three traceroute probes went unanswered
    assert rows[3]["step_ms"] == 39.0  # the ocean, or in this case the Pyrenees
    assert rows[0]["place"] is None  # a private address is not placed on the map


def test_hop_rows_survive_a_trace_that_recorded_no_locations():
    from pingme.render_map import hop_rows

    rows = hop_rows({"hops": [{"n": 1, "ip": "1.1.1.1", "avg_ms": 2.0, "loss_pct": 0.0}]})
    assert rows[0]["place"] is None and rows[0]["ms"] == 2.0
    assert hop_rows({}) == []
