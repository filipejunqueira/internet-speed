"""The command line's own logic: the --target parser and what `compare` puts in its table.

The records here are built by hand rather than read from the log. A comparison has to
say the right thing about a run saved before stalls were counted, and about a target
that only one of the two runs measured, and the only way to have either in a test is
to write it out.
"""

import io

import pytest
from rich.console import Console
from typer.testing import CliRunner

import pingme.cli as cli
from pingme.cli import _change, _short, compare_table, network_warning, parse_target


def test_a_target_is_a_name_and_an_address_around_an_equals_sign():
    assert parse_target("n475=108.61.221.148") == ("n475", "108.61.221.148")
    assert parse_target(" n475 = 108.61.221.148 ") == ("n475", "108.61.221.148")


@pytest.mark.parametrize("value, complaint", [
    ("n475", "needs a name and an address"),
    ("=108.61.221.148", "has no name before the ="),
    ("n475=", "has no address after the ="),
])
def test_a_target_that_is_not_a_pair_is_refused_with_a_reason(value, complaint):
    with pytest.raises(ValueError) as caught:
        parse_target(value)
    assert complaint in str(caught.value)


def test_a_note_is_cut_to_the_column_with_an_ellipsis():
    assert _short(None) == "—"
    assert _short("") == "—"
    assert _short("route=mudfish475", 20) == "route=mudfish475"
    assert _short("route=mudfish475 link=BT", 10) == "route=mud…"


def test_the_change_column_is_the_second_run_less_the_first():
    assert _change(205.0, 190.0) == "-15.0"
    assert _change(190.0, 205.0) == "+15.0"
    assert _change(2, 5, nd=0) == "+3"
    assert _change(0.75, 0.20, nd=2) == "-0.55"
    # nobody measured one side, so there is no change to state
    assert _change(None, 190.0) == "—"  # nobody counted, said the way every other cell says it
    assert _change(190.0, None) == "—"


def _record(rid, *, note=None, ssid="SantanderGuest", dev="wlp1s0", isp="Vodafone",
            targets=None, download=90.0, upload=20.0, overhead=9.1):
    return {
        "id": rid,
        "note": note,
        "snapshot": {"interface": dev, "medium": "wifi", "wifi": {"ssid": ssid},
                     "public": {"isp": isp}},
        "speed": [{"direction": "download", "mbps": download},
                  {"direction": "upload", "mbps": upload}],
        "analysis": {"local_overhead_ms": overhead, "targets": targets or {}},
    }


def _entry(*, loss=0.0, best=95.0, median=100.0, p95=120.0, jitter=2.0,
           burst=None, stalls=None):
    """One target's analysis entry, cut down to what compare reads."""
    return {"all": {"loss_pct": loss, "min_ms": best, "median_ms": median,
                    "p95_ms": p95, "jitter_ms": jitter},
            "loss": None if burst is None else {"longest_burst_probes": burst},
            "stalls": stalls}


def _rows(ra, rb) -> dict[str, list[str]]:
    """The compare table drawn out, as {row name: the cells after it}."""
    out = io.StringIO()
    Console(file=out, width=200, force_terminal=False,
            legacy_windows=False).print(compare_table(ra, rb))
    rows = {}
    for line in out.getvalue().splitlines():
        if line.count("│") >= 4:
            cells = [c.strip() for c in line.strip().strip("│").split("│")]
            rows[cells[0]] = cells[1:]
    return rows


def test_compare_shows_both_runs_the_change_and_the_note():
    ra = _record("A", note="route=none (control)",
                 targets={"sao-paulo": _entry(median=205.0, p95=240.0, burst=1)})
    rb = _record("B", targets={"sao-paulo": _entry(median=190.0, p95=215.0, burst=3)})
    rows = _rows(ra, rb)
    assert rows["note"] == ["route=none (control)", "—", ""]  # text has no difference
    assert rows["download Mbit/s"] == ["90.0", "90.0", "+0.0"]
    assert rows["sao-paulo median_ms"] == ["205.0", "190.0", "-15.0"]
    assert rows["sao-paulo p95_ms"] == ["240.0", "215.0", "-25.0"]
    assert rows["sao-paulo burst"] == ["1", "3", "+2"]


def test_compare_tells_a_counted_zero_from_a_figure_nobody_counted():
    """A run saved before stalls were counted must not read as a run with no stalls."""
    counted = _entry(stalls={"threshold_ms": 30.0, "idle_mean_ms": 12.43, "spikes": 36,
                             "episodes": [], "router_coincidence": 0.75})
    quiet = _entry(stalls={"threshold_ms": 30.0, "idle_mean_ms": 12.43, "spikes": 0,
                           "episodes": [], "router_coincidence": None})
    fewer = _entry(stalls={"threshold_ms": 30.0, "idle_mean_ms": 12.43, "spikes": 20,
                           "episodes": [], "router_coincidence": 0.20})
    old = _entry()  # a record from before stalls existed: "stalls" is None
    rows = _rows(_record("A", targets={"london": counted, "madrid": quiet,
                                       "us-east": counted}),
                 _record("B", targets={"london": old, "madrid": quiet,
                                       "us-east": fewer}))
    assert rows["london spikes"] == ["36", "—", "—"]
    assert rows["london router-shared spikes"] == ["75%", "—", "—"]
    assert rows["madrid spikes"] == ["0", "0", "+0"]
    assert rows["madrid router-shared spikes"] == ["—", "—", "—"]
    # the share is shown as a percentage, so its change is in percentage points
    assert rows["us-east spikes"] == ["36", "20", "-16"]
    assert rows["us-east router-shared spikes"] == ["75%", "20%", "-55"]


def test_compare_survives_a_target_only_one_of_the_two_runs_measured():
    """--target adds a name the other run has never heard of; the table still draws."""
    rows = _rows(_record("A", targets={"sao-paulo": _entry(median=205.0)}),
                 _record("B", targets={"sao-paulo": _entry(median=200.0),
                                       "n475": _entry(median=150.0, burst=0)}))
    assert rows["n475 median_ms"] == ["—", "150.0", "—"]
    assert rows["n475 burst"] == ["—", "0", "—"]
    assert rows["sao-paulo median_ms"] == ["205.0", "200.0", "-5.0"]


def test_two_runs_on_the_same_network_draw_no_warning():
    assert network_warning(_record("A"), _record("B")) is None


def test_a_different_wifi_name_interface_or_provider_is_named_in_the_warning():
    said = network_warning(_record("A"), _record("B", ssid="BT-FMAGNK"))
    assert said is not None
    assert "SantanderGuest against BT-FMAGNK" in said
    assert "not comparable" in said
    both = network_warning(_record("A"), _record("B", ssid="BT-FMAGNK", isp="BT"))
    assert "Vodafone against BT" in both
    assert "wlp1s0" not in both  # the interface matched, so it is not part of the complaint
    assert "interface" in network_warning(_record("A"), _record("B", dev="enp2s0"))


def _fake_run(captured):
    def run(label, timing, status=None, trace=False, note=None, extra=None):
        captured.update(label=label, total_s=timing.total_s, trace=trace, note=note,
                        extra=extra)
        return {"id": "fake"}

    return run


def test_the_new_flags_reach_the_run(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(cli, "run", _fake_run(captured))
    monkeypatch.setattr(cli, "render", lambda record, console=None: None)
    result = CliRunner().invoke(cli.app, ["--quick", "--label", "n475", "--trace",
                                          "--note", "route=mudfish475 link=SantanderGuest",
                                          "--target", "n475=108.61.221.148",
                                          "--target", "n476=1.2.3.4"])
    assert result.exit_code == 0, result.output
    assert captured["note"] == "route=mudfish475 link=SantanderGuest"
    assert captured["trace"] is True
    assert captured["extra"] == [("n475", "108.61.221.148"), ("n476", "1.2.3.4")]


def test_without_the_flags_nothing_is_traced_and_no_target_is_added(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(cli, "run", _fake_run(captured))
    monkeypatch.setattr(cli, "render", lambda record, console=None: None)
    result = CliRunner().invoke(cli.app, ["--quick"])
    assert result.exit_code == 0, result.output
    assert captured["trace"] is False
    assert captured["note"] is None
    assert captured["extra"] == []


def test_a_malformed_target_stops_before_anything_is_measured(monkeypatch):
    def must_not_run(*a, **k):
        raise AssertionError("the run started despite a malformed --target")

    monkeypatch.setattr(cli, "run", must_not_run)
    result = CliRunner().invoke(cli.app, ["--quick", "--target", "n475"])
    assert result.exit_code == 1
    assert "needs a name and an address" in result.output
