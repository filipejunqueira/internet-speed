"""Trace every target of a saved run and draw the routes on a map in the browser."""

from __future__ import annotations

import datetime as dt
import shutil
import subprocess

import httpx
import plotly.graph_objects as go

from .geo import Location, locate
from .places import FORTALEZA, MIAMI, NEW_YORK, SINES
from .store import data_dir
from .trace import trace

REFERENCE_POINTS = {"Sines (EllaLink)": SINES, "Fortaleza (EllaLink)": FORTALEZA,
                    "New York": NEW_YORK, "Miami": MIAMI}
# Which side of its end point each relay's name is written, on the report map and the
# explorer's (emitted in the tokens block). US-East sits four degrees south-west of New
# York, so its name goes west, away from New York's.
LABEL_SIDE = {"london": "middle right", "madrid": "middle right", "us-east": "middle left",
              "sao-paulo": "middle right"}
# dataviz categorical slots 1-4 (validated for adjacent-pair colour-blind separation)
COLOURS = {"london": "#2a78d6", "madrid": "#eb6834", "us-east": "#1baf7a",
           "sao-paulo": "#eda100", "router": "#898781", "isp-hop": "#898781"}


def trace_run(run: dict, status=lambda msg: None) -> dict:
    """Trace and geolocate the route to every relay of a saved run.

    Every entry carries the same `traced_at`, taken once before the first traceroute rather
    than per target, because one call is one act of tracing: the targets are minutes apart
    at most, and a reader comparing two entries of one run should not have to wonder why.
    It matters because this runs at two quite different moments. During a `--web`,
    `--publish` or `--trace` run it records the route the run took. Called later, from
    `traces_for`, it records the route from wherever the machine is sitting that day, which
    may be a different network in a different city. `trace_note` is what tells the two
    apart, and it can only do that if the date is written down.
    """
    origin = tuple(run["analysis"]["origin"])
    traced_at = dt.datetime.now(dt.UTC).isoformat()
    out = {}
    with httpx.Client() as client:
        for t in run["targets"]:
            # Custom targets are traced too. They are the whole reason somebody adds one:
            # a proxy node's hop table is the only thing that shows where a proxied route
            # spends its time after the node. Only the local hops are skipped, because a
            # traceroute to your own router says nothing anybody needs.
            if t["kind"] in ("gateway", "isp-hop"):
                continue
            status(f"tracing {t['name']} ({t['ip']}) …")
            hops, err = trace(t["ip"])
            located = []
            for h in hops:
                if h.ip is None:
                    located.append(None)
                else:
                    located.append(locate(h.ip, origin, client))
            hidden = sum(1 for h in hops if h.ip is None)
            placed = sum(1 for loc in located if loc and loc.lat is not None)
            status(f"  {len(hops)} hops, {hidden} hidden, {placed} placed on the map")
            out[t["name"]] = {"error": err, "traced_at": traced_at,
                              "hops": [h.as_dict() for h in hops],
                              "locations": [loc.as_dict() if loc else None for loc in located]}
    return out


# A trace runs after the probes stop, so even a route traced with its own run is a minute
# or two late: "with the run" has to be a window, not an instant. Four traceroutes take one
# to two minutes on this machine, and the window has to hold for a --longer run as well, so
# it is the run's own length plus a quarter of an hour. Anything past that was a separate
# act, on a network that may no longer be the one the run measured.
TRACE_WITH_RUN_GRACE_S = 15 * 60


def _stamp(value: str | None) -> dt.datetime | None:
    """An ISO 8601 stamp as an aware UTC datetime, or None when missing or unreadable.

    A stamp nobody can parse is treated as a stamp nobody wrote: the caller says so rather
    than raising, because a corrupt field in one old record must not take a whole page down.
    """
    if not isinstance(value, str):
        return None
    try:
        when = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=dt.UTC)


def _gap_words(seconds: float) -> str:
    """'11 days', '4 hours', '15 minutes': the largest whole unit that is at least one.

    Always rounded down. "11 days" is still true at eleven days and a half, where "12 days"
    would not be, so flooring is the only direction that cannot overstate the gap.
    """
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        n = int(seconds // size)
        if n >= 1:
            return f"{n} {unit}" if n == 1 else f"{n} {unit}s"
    return "less than a minute"


def trace_note(run_started: str | None, duration_s: float | None,
               traced_at: str | None) -> str | None:
    """What a page has to say about when this route was traced, or None when nothing.

    Three answers, and the quiet one is the common one. A route traced with its own run
    needs no words: that is what a reader already assumes when they see a map on a run's
    page. A route traced later is still worth drawing, because the path is real and the
    cable has not moved, but the page has to say so or it will be read as the route the run
    took. A trace with no date cannot be told apart from either, and silence would let it
    pass for the first, so it says exactly what it knows: nothing.

    This is the same rule as the em dash on a figure nobody measured. A blank is not an
    honest stand-in for a fact nobody recorded.
    """
    started, traced = _stamp(run_started), _stamp(traced_at)
    if started is None or traced is None:
        return "When this route was traced was not recorded."
    # A record from before durations were stored leaves the window as the grace alone. That
    # can call a with-the-run trace late, never a late trace with-the-run, which is the way
    # round this should fail.
    length = float(duration_s) if isinstance(duration_s, int | float) else 0.0
    if (traced - started).total_seconds() <= length + TRACE_WITH_RUN_GRACE_S:
        return None
    gap = (traced - started - dt.timedelta(seconds=length)).total_seconds()
    return (f"Traced on {traced.astimezone(dt.UTC).date().isoformat()}, {_gap_words(gap)} "
            "after this run, so it may not be the path the run took.")


def trace_notes(run: dict, traces: dict | None) -> list[str]:
    """What this run's routes need said about when they were traced, in relay order.

    Distinct sentences only. One `trace_run` call stamps every entry with the same moment,
    so in practice this is one sentence or none; it is a list because a record can hold
    entries from more than one call, and two routes traced weeks apart should each say so.
    """
    out: list[str] = []
    for entry in (traces or {}).values():
        note = trace_note(run.get("timestamp"), run.get("duration_s"),
                          (entry or {}).get("traced_at"))
        if note and note not in out:
            out.append(note)
    return out


def path_cities(trace_entry: dict) -> list[str]:
    """Placed hop cities in order, consecutive repeats collapsed, hidden runs as '…'."""
    out: list[str] = []
    for loc in trace_entry.get("locations") or []:
        if loc is not None and loc.get("source") == "private":
            continue  # your own router, drawn as the origin already
        city = None if loc is None or loc.get("lat") is None else (loc.get("city") or "?")
        token = "…" if city is None else city
        if not out or out[-1] != token:
            out.append(token)
    return out


def traced_path(trace_entry: dict) -> str | None:
    """'you → London → … → São Paulo' when at least two hops were placed, else None."""
    cities = path_cities(trace_entry)
    if len([c for c in cities if c != "…"]) < 2:
        return None
    return "you → " + " → ".join(cities)


TRACE_QUERIES = 3  # traceroute -q 3: how many probes each hop gets


def hop_rows(trace_entry: dict) -> list[dict]:
    """One row per hop: where it is, how long it took, and what it added over the last one.

    `step_ms` is the delay this hop added on top of the previous hop that answered. It is
    what tells you which link the time goes into. Each figure is a single measurement, so
    it wobbles, and a negative step means noise rather than a router giving time back.
    """
    rows: list[dict] = []
    previous_ms = None
    hops = trace_entry.get("hops") or []
    locs = trace_entry.get("locations") or []
    for i, hop in enumerate(hops):
        loc = locs[i] if i < len(locs) else None
        ms = hop.get("avg_ms")
        step = None if ms is None or previous_ms is None else round(ms - previous_ms, 1)
        placed = bool(loc) and loc.get("lat") is not None
        missing = hop.get("loss_pct")
        rows.append({
            "n": hop["n"],
            "ip": hop.get("ip"),
            "hostname": (loc or {}).get("hostname"),
            "place": (loc.get("city") or "?") if placed else None,
            "source": (loc or {}).get("source") if placed else None,
            "ms": ms,
            "step_ms": step,
            "no_reply": None if missing is None else round(TRACE_QUERIES * missing / 100),
        })
        if ms is not None:
            previous_ms = ms
    return rows


def _hop_ms(trace_entry: dict) -> dict[str, float]:
    """Delay per hop address, so the map can say how long each point took to reach."""
    return {h["ip"]: h["avg_ms"] for h in (trace_entry.get("hops") or [])
            if h.get("ip") and h.get("avg_ms") is not None}


def _segments(origin: tuple[float, float], target: dict, locs: list[Location | None],
              hop_ms: dict[str, float] | None = None):
    """Turn the hop list into (lat, lon, label, hidden_before) points to draw."""
    hop_ms = hop_ms or {}
    pts = [(origin[0], origin[1], "you", 0)]
    hidden = 0
    for loc in locs:
        if loc is None or loc.lat is None:
            hidden += 1
            continue
        if abs(loc.lat - pts[-1][0]) < 0.05 and abs(loc.lon - pts[-1][1]) < 0.05:
            continue  # same place as the previous point, do not draw a zero-length hop
        ms = hop_ms.get(loc.ip)
        reached = "" if ms is None else f", {ms:.0f} ms in"
        label = f"{loc.city or '?'} ({loc.ip}, {loc.source}{reached})"
        pts.append((loc.lat, loc.lon, label, hidden))
        hidden = 0
    if target["lat"] is not None:
        last = pts[-1]
        if not (abs(target["lat"] - last[0]) < 0.05 and abs(target["lon"] - last[1]) < 0.05):
            pts.append((target["lat"], target["lon"], f"{target['name']} relay", hidden))
    return pts


def map_figure(run: dict, traces: dict, note: str | None = None) -> go.Figure:
    """The plotly map for a run whose routes were traced with `trace_run`.

    `note` goes under the subtitle, for a caller with nowhere else to put a sentence: the
    map-only page is a bare figure with no prose around it. The report page leaves this
    alone and writes its own paragraph under the map instead, where it can be selected and
    read at any width.
    """
    run_targets = {t["name"]: t for t in run["targets"]}
    origin = tuple(run["analysis"]["origin"])
    fig = go.Figure()
    for name, tr in traces.items():
        locs = [Location(**loc) if loc else None for loc in tr["locations"]]
        pts = _segments(origin, run_targets[name], locs, _hop_ms(tr))
        colour = COLOURS.get(name, "#333")
        physics = (run["analysis"]["targets"].get(name) or {}).get("physics") or {}
        verdict = physics.get("most_consistent") or "no verdict"
        for i in range(1, len(pts)):
            a, b = pts[i - 1], pts[i]
            hidden = b[3]
            fig.add_trace(go.Scattergeo(
                lat=[a[0], b[0]], lon=[a[1], b[1]], mode="lines",
                line={"width": 2, "color": colour, "dash": "dash" if hidden else "solid"},
                name=name, legendgroup=name, showlegend=(i == 1),
                hovertext=(f"{name}: {hidden} hidden hop(s)" if hidden else f"{name}"),
                hoverinfo="text", meta={"role": name}))
        # direct label at the far end so identity never rests on colour alone
        fig.add_trace(go.Scattergeo(
            lat=[p[0] for p in pts], lon=[p[1] for p in pts], mode="markers+text",
            text=[""] * (len(pts) - 1) + [name], textposition="middle right",
            textfont={"size": 11}, marker={"size": 7, "color": colour},
            legendgroup=name, showlegend=False, meta={"role": name},
            hovertext=[f"{p[2]}<br>{name}: physics says {verdict}" for p in pts],
            hoverinfo="text"))
    fig.add_trace(go.Scattergeo(
        lat=[v[0] for v in REFERENCE_POINTS.values()],
        lon=[v[1] for v in REFERENCE_POINTS.values()],
        mode="markers+text", text=list(REFERENCE_POINTS), textposition="bottom center",
        marker={"size": 6, "color": "rgba(137,135,129,0.6)", "symbol": "diamond"},
        textfont={"size": 10, "color": "#898781"}, name="cable landing points",
        hoverinfo="text"))
    fig.add_trace(go.Scattergeo(lat=[origin[0]], lon=[origin[1]], mode="markers+text",
                                text=["you"], textposition="top center",
                                marker={"size": 11, "color": "#0b0b0b", "symbol": "star"},
                                name="origin", hoverinfo="text"))
    fig.update_geos(fitbounds="locations", showcountries=True, showland=True,
                    landcolor="#f2efe9", oceancolor="#dbe9f6", showocean=True,
                    countrycolor="#bbb", coastlinecolor="#999", projection_type="natural earth")
    analysed = run["analysis"]["targets"]
    verdicts = "; ".join(
        f"{n}: {((analysed.get(n) or {}).get('physics') or {}).get('most_consistent') or '—'}"
        for n in traces)
    subtitle = f"{verdicts}<br>{note}" if note else verdicts
    fig.update_layout(title=f"pingme routes — {run['id']}<br><sup>{subtitle}</sup>",
                      margin={"l": 10, "r": 10, "t": 90 if note else 70, "b": 10},
                      legend={"x": 0.01, "y": 0.99})
    return fig


def traces_for(run: dict, status=lambda msg: None) -> dict:
    """Traces saved with the run; otherwise trace now and say so."""
    if run.get("traces"):
        return run["traces"]
    status("[yellow]no route trace saved with this run; "
           "tracing now, on the current network[/yellow]")
    return trace_run(run, status)


def build_map(run: dict, status=lambda msg: None) -> str:
    """Draw and open the map-only page."""
    traces = traces_for(run, status)
    fig = map_figure(run, traces, note=" ".join(trace_notes(run, traces)) or None)
    maps = data_dir() / "maps"
    maps.mkdir(exist_ok=True)
    path = maps / f"{run['id']}.html"
    fig.write_html(str(path), include_plotlyjs=True)
    run.setdefault("traces", traces)
    opener = shutil.which("xdg-open")
    if opener:
        try:
            subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except OSError:
            pass
    return str(path)
