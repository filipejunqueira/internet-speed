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
