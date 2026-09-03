"""Draw a saved run in the terminal: header, one panel per target, speed panel, verdicts."""

from __future__ import annotations

import plotext as plt
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

TARGET_ORDER = ["router", "isp-hop", "london", "madrid", "us-east", "sao-paulo"]


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


def _timeline(entry: dict, width: int, height: int) -> Text:
    lost = (entry.get("loss") or {}).get("lost") or []

    def draw():
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
        plt.title("round trip over time")

    return _plot_to_text(width, height, draw)


def _is_silent(entry: dict) -> bool:
    """Nothing came back and ping itself did not fail: the target ignores probes."""
    if entry.get("silent") is not None:
        return bool(entry["silent"])
    return not entry["samples"] and entry.get("error") in (None, "no replies")  # older runs


def _burst_text(entry: dict) -> str:
    loss = entry.get("loss")
    if not loss or not loss["longest_burst_probes"]:
        return "burst —"
    return (f"burst [bold]{loss['longest_burst_probes']}[/bold] probes "
            f"({loss['longest_burst_s']:.1f} s at {loss['longest_burst_at_s']:.0f} s)")


def _target_panel(name: str, entry: dict, width: int, trace_entry: dict | None = None) -> Panel:
    a, idle, busy = entry["all"], entry["idle"], entry["busy"]
    head = (f"[bold]{name}[/bold]  {entry['ip']}   "
            f"loss [bold]{_fmt(a['loss_pct'], '%')}[/bold] "
            f"({a['sent'] - a['received']} of {a['sent']})  {_burst_text(entry)}  "
            f"best {_fmt(a['min_ms'])}  median {_fmt(a['median_ms'])}  "
            f"p95 {_fmt(a['p95_ms'])}  p99 {_fmt(a['p99_ms'])}  jitter {_fmt(a['jitter_ms'])} ms")
    if idle["median_ms"] is not None and busy["median_ms"] is not None:
        head += (f"\nidle median {_fmt(idle['median_ms'])} / p95 {_fmt(idle['p95_ms'])}   "
                 f"busy median {_fmt(busy['median_ms'])} / p95 {_fmt(busy['p95_ms'])}   "
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
        head += (f"   timing estimate: ~{_fmt(p['effective_ms'], '', 0)} ms after local overhead → "
                 f"[bold]{p['most_consistent'] or 'faster than any known route?'}[/bold]")
    if _is_silent(entry):
        return Panel(Text(f"{name}  {entry['ip']}  — does not answer probes "
                          f"({a['sent']} sent, 0 back)", style="dim"), border_style="grey50")
    if entry.get("error") and not entry["samples"]:
        return Panel(Text(f"{name}  {entry['ip']}  — {entry['error']}", style="red"),
                     border_style="red")
    half = max(30, (width - 8) // 2)
    plots = Columns([_histogram(entry, half, 12), _timeline(entry, half, 12)], padding=(0, 1),
                    equal=True, expand=True)
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
                "busy p95", "route"):
        t.add_column(col, justify="right" if col != "target" and col != "route" else "left")
    targets = run["analysis"]["targets"]
    for name in sorted(targets, key=lambda n: TARGET_ORDER.index(n) if n in TARGET_ORDER else 99):
        e = targets[name]
        a, b = e["all"], e["busy"]
        verdict = (e.get("physics") or {}).get("most_consistent") or ""
        burst = (e.get("loss") or {}).get("longest_burst_probes")
        t.add_row(name, _fmt(a["loss_pct"], "%"), "—" if not burst else str(burst),
                  _fmt(a["min_ms"]), _fmt(a["median_ms"]),
                  _fmt(a["p95_ms"]), _fmt(a["p99_ms"]), _fmt(a["jitter_ms"]),
                  _fmt(b["p95_ms"]), verdict)
    return t


def render(run: dict, console: Console | None = None) -> None:
    console = console or Console()
    width = console.width
    console.print(_header(run))
    targets = run["analysis"]["targets"]
    for name in sorted(targets, key=lambda n: TARGET_ORDER.index(n) if n in TARGET_ORDER else 99):
        trace_entry = (run.get("traces") or {}).get(name)
        console.print(_target_panel(name, targets[name], width, trace_entry))
    console.print(_speed_panel(run, width))
    console.print(_verdict_table(run))
    console.print(f"saved to {run.get('saved_to', '?')}", style="dim")
