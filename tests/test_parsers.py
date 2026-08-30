from pingme.probe import parse_reply
from pingme.targets import parse_sdr


def test_parse_ping_reply():
    line = "64 bytes from 162.254.196.66: icmp_seq=7 ttl=54 time=48.3 ms"
    assert parse_reply(line) == (7, 48.3)
    assert parse_reply("PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.") is None


def test_parse_sdr_picks_one_relay_per_wanted_city():
    cfg = {"pops": {
        "lhr": {"desc": "London (England)", "geo": [-0.13, 51.51],
                "relays": [{"ipv4": "1.1.1.1"}, {"ipv4": "1.1.1.2"}]},
        "gru": {"desc": "Sao Paulo (Brazil)", "geo": [-46.6, -23.5],
                "relays": [{"ipv4": "2.2.2.2"}]},
        "ams": {"desc": "Amsterdam", "geo": [4.9, 52.4], "relays": [{"ipv4": "3.3.3.3"}]},
    }}
    ts = parse_sdr(cfg)
    assert [t.name for t in ts] == ["london", "sao-paulo"]
    assert ts[0].ip == "1.1.1.1" and ts[0].lat == 51.51 and ts[0].lon == -0.13
    assert ts[1].lon < 0  # Sao Paulo west of Greenwich, from our own table


def test_loss_counts_only_probes_that_were_really_sent():
    """A gap in the sequence is real loss; the clock estimate must not invent one."""
    from pingme.probe import ProbeResult, Sample
    from pingme.stats import summarise

    r = ProbeResult(target="t", ip="1.1.1.1")
    r.samples = [Sample(seq, 10.0, seq * 0.2, "idle") for seq in (1, 2, 4, 5)]
    r.sent = max(s.seq for s in r.samples)
    s = summarise(r.rtts(), r.sent)
    assert s.sent == 5 and s.received == 4 and s.loss_pct == 20.0

    perfect = ProbeResult(target="t", ip="1.1.1.1")
    perfect.samples = [Sample(seq, 10.0, seq * 0.2, "idle") for seq in range(1, 300)]
    perfect.sent = max(s.seq for s in perfect.samples)
    assert summarise(perfect.rtts(), perfect.sent).loss_pct == 0.0
