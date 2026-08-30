"""Trace every target of a saved run and draw the routes on a map in the browser."""

from __future__ import annotations

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
# dataviz categorical slots 1-4 (validated for adjacent-pair colour-blind separation)
COLOURS = {"london": "#2a78d6", "madrid": "#eb6834", "us-east": "#1baf7a",
           "sao-paulo": "#eda100", "router": "#898781", "isp-hop": "#898781"}


def trace_run(run: dict, status=lambda msg: None) -> dict:
    """Trace and geolocate the route to every relay of a saved run."""
    origin = tuple(run["analysis"]["origin"])
    out = {}
    with httpx.Client() as client:
        for t in run["targets"]:
            if t["kind"] != "relay":
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
            out[t["name"]] = {"error": err, "hops": [h.as_dict() for h in hops],
                              "locations": [loc.as_dict() if loc else None for loc in located]}
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


def _segments(origin: tuple[float, float], target: dict, locs: list[Location | None]):
    """Turn the hop list into (lat, lon, label, hidden_before) points to draw."""
    pts = [(origin[0], origin[1], "you", 0)]
    hidden = 0
    for loc in locs:
        if loc is None or loc.lat is None:
            hidden += 1
            continue
        if abs(loc.lat - pts[-1][0]) < 0.05 and abs(loc.lon - pts[-1][1]) < 0.05:
            continue  # same place as the previous point, do not draw a zero-length hop
        label = f"{loc.city or '?'} ({loc.ip}, {loc.source})"
        pts.append((loc.lat, loc.lon, label, hidden))
        hidden = 0
    if target["lat"] is not None:
        last = pts[-1]
        if not (abs(target["lat"] - last[0]) < 0.05 and abs(target["lon"] - last[1]) < 0.05):
            pts.append((target["lat"], target["lon"], f"{target['name']} relay", hidden))
    return pts


def map_figure(run: dict, traces: dict) -> go.Figure:
    """The plotly map for a run whose routes were traced with `trace_run`."""
    run_targets = {t["name"]: t for t in run["targets"]}
    origin = tuple(run["analysis"]["origin"])
    fig = go.Figure()
    for name, tr in traces.items():
        locs = [Location(**loc) if loc else None for loc in tr["locations"]]
        pts = _segments(origin, run_targets[name], locs)
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
    fig.update_layout(title=f"pingme routes — {run['id']}<br><sup>{verdicts}</sup>",
                      margin={"l": 10, "r": 10, "t": 70, "b": 10}, legend={"x": 0.01, "y": 0.99})
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
    fig = map_figure(run, traces)
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
