"""Draw a saved run in the terminal: header, one panel per target, speed panel, verdicts."""

from __future__ import annotations

import plotext as plt
from rich.columns import Columns
from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .stats import COINCIDENCE_WINDOW_S, SPIKE_OVER_MS
from .store import burst_probes, is_silent

TARGET_ORDER = ["router", "isp-hop", "london", "madrid", "us-east", "sao-paulo"]

# The router's stalls are shaded behind the points in a grey that belongs to no target and
# no phase, so a band can never be mistaken for data. plotext writes user-defined lines
# into the canvas before the samples, so the points always land on top of the band.
BAND_COLOUR = 240


def _fmt(v, unit: str = "", nd: int = 1) -> str:
    return "—" if v is None else f"{v:.{nd}f}{unit}"


def _plot_to_text(width: int, height: int, draw) -> Text:
    plt.clf()
    plt.theme("pro")
    plt.plotsize(width, height)
    draw()
    return Text.from_ansi(plt.build())


def _histogram(entry: dict, width: int, height: int) -> Text:
    idle = [s[1] for s in entry["samples"] if s[3] == "idle"]
    busy = [s[1] for s in entry["samples"] if s[3] in ("download", "upload")]

    def draw():
        if idle:
            plt.hist(idle, bins=30, label="idle", color="cyan")
        if busy:
            plt.hist(busy, bins=30, label="busy", color="orange")
        plt.xlabel("round trip (ms)")
        plt.title("histogram")

    return _plot_to_text(width, height, draw)


def _band_x(episodes: list[dict], x_from: float, x_to: float, width: int,
            window_s: float = COINCIDENCE_WINDOW_S) -> list[float]:
    """Where to draw the vertical lines that shade the router's stalls, in seconds.

    plotext has no rectangle behind a plot, so a band is a line in every character column
    the stall covers. Each stall is widened by `window_s` on both sides because that is
    how the coincidence share counts: a target spike a second *before* a router spike is
    counted alongside it, and it would look wrong sitting outside the shading. That also
    gives a single-spike stall, whose length is 0, a band two seconds wide.

    Lines outside the plotted range are dropped: plotext folds them into the axis limits,
    which would stretch the plot past the data.
    """
    step = (x_to - x_from) / width if width > 0 and x_to > x_from else 0.0
    out: set[float] = set()
    for ep in episodes or []:
        x, end = ep["at_s"] - window_s, ep["at_s"] + ep.get("length_s", 0.0) + window_s
        while True:
            if x_from <= x <= x_to:
                out.add(round(x, 3))
            if step <= 0 or x >= end:
                break
            x = min(x + step, end)
    return sorted(out)


def _timeline(entry: dict, width: int, height: int,
              episodes: list[dict] | None = None) -> Text:
    lost = (entry.get("loss") or {}).get("lost") or []
    times = [s[2] for s in entry["samples"]]
    band = _band_x(episodes, min(times), max(times), width) if episodes and times else []

    def draw():
        for x in band:
            plt.vertical_line(x, color=BAND_COLOUR)
        for phase, colour in (("idle", "cyan"), ("download", "orange"), ("upload", "red")):
            pts = [(s[2], s[1]) for s in entry["samples"] if s[3] == phase]
            if pts:
                plt.scatter([p[0] for p in pts], [p[1] for p in pts], label=phase,
                            color=colour, marker="dot")
        if lost:
            # draw every lost probe along the top, where it cannot hide among the replies
            top = max(s[1] for s in entry["samples"])
            plt.scatter([t for _, t in lost], [top] * len(lost), label="lost",
                        color="red", marker="x")
        plt.xlabel("seconds")
        plt.title("round trip over time" + ("  (grey: router stalls)" if band else ""))

    return _plot_to_text(width, height, draw)


def _burst_text(entry: dict) -> str:
    if "loss" not in entry:
        return "burst not counted"  # a run saved before bursts were measured
    loss = entry["loss"]
    if not loss:
        return "burst —"  # nothing came back, so there was no burst to find
    if not loss["longest_burst_probes"]:
        return "burst 0"  # counted, and nothing was lost back to back
    return (f"burst [bold]{loss['longest_burst_probes']}[/bold] probes "
            f"({loss['longest_burst_s']:.1f} s at {loss['longest_burst_at_s']:.0f} s)")


def _stall_cells(entry: dict) -> tuple[str, str]:
    """The spikes cell and the with-router cell for one row of the summary table.

    "—" means nobody counted: a record saved before stalls were measured, a target with
    no idle samples, or a share that cannot be taken (the router itself is the witness,
    and a target that never spiked has no share to give). A counted zero stays 0.
    """
    stalls = entry.get("stalls")
    if stalls is None:
        return "—", "—"
    share = stalls.get("router_coincidence")
    return str(stalls["spikes"]), "—" if share is None else f"{share * 100:.0f}%"


def _target_panel(name: str, entry: dict, width: int, trace_entry: dict | None = None,
                  episodes: list[dict] | None = None) -> Panel:
    a, idle, busy = entry["all"], entry["idle"], entry["busy"]
    head = (f"[bold]{escape(name)}[/bold]  {escape(str(entry['ip']))}   "
            f"loss [bold]{_fmt(a['loss_pct'], '%')}[/bold] "
            f"({a['sent'] - a['received']} of {a['sent']})  {_burst_text(entry)}  "
            f"best {_fmt(a['min_ms'])}  median {_fmt(a['median_ms'])}  "
            f"p95 {_fmt(a['p95_ms'])}  p99 {_fmt(a['p99_ms'])}  jitter {_fmt(a['jitter_ms'])} ms")
    if idle["median_ms"] is not None and busy["median_ms"] is not None:
        # The speed test is the same length whatever the run length, so on a long run the
        # busy figures rest on a few dozen probes out of thousands. Say how many.
        head += (f"\nidle median {_fmt(idle['median_ms'])} / p95 {_fmt(idle['p95_ms'])}   "
                 f"busy median {_fmt(busy['median_ms'])} / p95 {_fmt(busy['p95_ms'])} "
                 f"({busy['sent']} probes)   "
                 f"[bold]under-load penalty {busy['p95_ms'] - idle['p95_ms']:+.1f} ms[/bold]")
    route = entry.get("route") or {}
    if route.get("dev"):
        head += f"\nroute: {route['dev']}"
    if trace_entry:
        from .render_map import traced_path

        path = traced_path(trace_entry)
        if path:
            head += f"\ntraced path: [bold]{path}[/bold]"
    if entry.get("physics"):
        p = entry["physics"]
        # The verdict is whichever candidate route comes closest, not a route anybody
        # traced, so it says how many it was picked from.
        n = len(p.get("candidates") or [])
        picked = (f" (closest of {n} route{'s' if n != 1 else ''} considered)"
                  if p["most_consistent"] and n else "")
        head += (f"   timing estimate: ~{_fmt(p['effective_ms'], '', 0)} ms after local overhead → "
                 f"[bold]{p['most_consistent'] or 'faster than any known route?'}[/bold]{picked}")
    if is_silent(entry):
        return Panel(Text(f"{name}  {entry['ip']}  — does not answer probes "
                          f"({a['sent']} sent, 0 back)", style="dim"), border_style="grey50")
    if entry.get("error") and not entry["samples"]:
        return Panel(Text(f"{name}  {entry['ip']}  — {entry['error']}", style="red"),
                     border_style="red")
    half = max(30, (width - 8) // 2)
    plots = Columns([_histogram(entry, half, 12), _timeline(entry, half, 12, episodes)],
                    padding=(0, 1), equal=True, expand=True)
    return Panel(Group(Text.from_markup(head), plots), border_style="blue")


def _header(run: dict) -> Panel:
    s = run["snapshot"]
    pub = s.get("public") or {}
    lines = [f"[bold]{run['id']}[/bold]   {run['timestamp']}   {run['duration_s']:.0f}s run"]
    if s.get("medium") == "wifi" and s.get("wifi"):
        w = s["wifi"]
        rx, tx = _fmt(w.get("rx_bitrate_mbps"), "", 0), _fmt(w.get("tx_bitrate_mbps"), "", 0)
        lines.append(f"Wi-Fi  {w.get('ssid')}  {w.get('generation') or ''}  "
                     f"{_fmt(w.get('freq_mhz'), ' MHz', 0)} ch{w.get('channel')} "
                     f"{w.get('width_mhz')} MHz wide  signal {w.get('signal_dbm')} dBm  "
                     f"link ↓{rx} ↑{tx} Mbit/s  on {s.get('interface')}")
    elif s.get("medium") == "ethernet" and s.get("ethernet"):
        e = s["ethernet"]
        lines.append(f"Ethernet  {e.get('link_speed_mbps')} Mbit/s {e.get('duplex')} duplex  "
                     f"on {s.get('interface')}")
    else:
        lines.append(f"medium unknown  on {s.get('interface')}")
    lines.append(f"public {pub.get('ip')}  {pub.get('isp')}  "
                 f"{pub.get('city')}, {pub.get('country')}")
    a = run["analysis"]
    lines.append(f"local overhead ≈ {a['local_overhead_ms']} ms  ({a['local_overhead_how']})")
    if run.get("note"):
        # Whatever --note was given, as it was typed. Escaped only so that a note with
        # square brackets in it is not read as rich's own markup.
        lines.append(f"note: {escape(str(run['note']))}")
    return Panel(Text.from_markup("\n".join(lines)), title="pingme", border_style="green")


def _speed_panel(run: dict, width: int) -> Panel:
    rows = []
    plots = []
    for sp in run["speed"]:
        mb = sp["bytes_total"] / 1e6
        rows.append(f"[bold]{sp['direction']:8s}[/bold] {sp['mbps']:7.1f} Mbit/s   "
                    f"{mb:6.1f} MB in {sp['seconds']:.1f}s   server {sp['server']}"
                    + (f"   [red]{sp['error']}[/red]" if sp.get("error") else ""))
        samples = sp["samples_mbps"]
        if samples:
            def draw(samples=samples, d=sp["direction"]):
                plt.plot([i * 0.25 for i in range(len(samples))], samples,
                         color="green" if d == "download" else "magenta")
                plt.title(f"{d} Mbit/s over time")
                plt.xlabel("seconds")
            plots.append(_plot_to_text(max(30, (width - 8) // 2), 10, draw))
    body = [Text.from_markup("\n".join(rows))]
    if plots:
        body.append(Columns(plots, padding=(0, 1), equal=True, expand=True))
    return Panel(Group(*body), title="throughput", border_style="green")


def _verdict_table(run: dict) -> Table:
    t = Table(title="summary", show_lines=False)
    for col in ("target", "loss", "burst", "best", "median", "p95", "p99", "jitter",
                "busy p95", "spikes", "with router", "route"):
        t.add_column(col, justify="right" if col != "target" and col != "route" else "left")
    targets = run["analysis"]["targets"]
    for name in sorted(targets, key=lambda n: TARGET_ORDER.index(n) if n in TARGET_ORDER else 99):
        e = targets[name]
        a, busy = e["all"], e["busy"]
        verdict = (e.get("physics") or {}).get("most_consistent") or ""
        # "—" means nobody counted; a measured run with nothing lost says 0
        longest = burst_probes(e)
        burst = "—" if longest is None else str(longest)
        spikes, with_router = _stall_cells(e)
        t.add_row(name, _fmt(a["loss_pct"], "%"), burst,
                  _fmt(a["min_ms"]), _fmt(a["median_ms"]),
                  _fmt(a["p95_ms"]), _fmt(a["p99_ms"]), _fmt(a["jitter_ms"]),
                  _fmt(busy["p95_ms"]), spikes, with_router, verdict)
    return t


def _router_episodes(run: dict) -> list[dict]:
    """When the local link itself stalled, taken from the router's own stalls block.

    Empty when the run has no router, or was saved before stalls were counted: then no
    band is drawn and nothing is claimed.
    """
    for entry in run["analysis"]["targets"].values():
        if entry.get("kind") == "gateway":
            return (entry.get("stalls") or {}).get("episodes") or []
    return []


def render(run: dict, console: Console | None = None) -> None:
    console = console or Console()
    width = console.width
    console.print(_header(run))
    targets = run["analysis"]["targets"]
    episodes = _router_episodes(run)
    for name in sorted(targets, key=lambda n: TARGET_ORDER.index(n) if n in TARGET_ORDER else 99):
        trace_entry = (run.get("traces") or {}).get(name)
        # The router's own panel gets no band: shading its stalls behind its own spikes
        # would say nothing, and the question the band answers is about the other targets.
        band = None if targets[name].get("kind") == "gateway" else episodes
        console.print(_target_panel(name, targets[name], width, trace_entry, band))
    console.print(_speed_panel(run, width))
    console.print(_verdict_table(run))
    console.print(
        f"spikes: idle probes more than {SPIKE_OVER_MS:g} ms above that target's own idle "
        f"average; \"with router\" is the share of them within {COINCIDENCE_WINDOW_S:g} s of a "
        f"router spike, and the grey band on each timeline is where the router stalled. "
        f"\"route\" is whichever candidate route the timing comes closest to, not a traced one.",
        style="dim")
    console.print(f"saved to {run.get('saved_to', '?')}", style="dim")
