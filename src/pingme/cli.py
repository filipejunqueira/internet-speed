"""Command line entry point: `pingme` runs a measurement; subcommands read the log back."""

from __future__ import annotations

import typer
from rich.console import Console

from . import __version__
from .render_tui import render
from .run import Timing, run
from .store import burst_probes, find_run, load_runs, summary_row

app = typer.Typer(add_completion=False, invoke_without_command=True, no_args_is_help=False,
                  help="Measure, plot and log the quality of the current internet connection.")
console = Console()


def _status(msg: str) -> None:
    console.print(f"[dim]•[/dim] {msg}")


@app.callback()
def main(
    ctx: typer.Context,
    label: str | None = typer.Option(None, "--label", "-l",
                                     help="Name for this run, e.g. airbnb_leeds."),
    quick: bool = typer.Option(False, "--quick", help="30 s run, 5 s speed tests."),
    long: bool = typer.Option(False, "--long", help="2 min run."),
    longer: bool = typer.Option(False, "--longer", help="10 min run."),
    web: bool = typer.Option(False, "--web", "--map",
                             help="Afterwards, open the full web report (charts, tables, map)."),
    publish: bool = typer.Option(False, "--publish",
                                 help="Afterwards, publish the redacted report to GitHub Pages."),
    version: bool = typer.Option(False, "--version"),
) -> None:
    if version:
        console.print(f"pingme {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is not None:
        return
    total, speed_s = 60.0, 10.0
    if quick:
        total, speed_s = 30.0, 5.0
    elif long:
        total = 120.0
    elif longer:
        total = 600.0
    record = run(label, Timing(total, speed_s), status=_status, trace=web or publish)
    render(record, console)
    if web:
        from .render_web import write_report
        path = write_report(record, status=_status)
        console.print(f"report written to {path}")
    if publish:
        from .publish import publish as publish_run
        url = publish_run(record, status=_status)
        console.print(f"published at {url}")


@app.command("show")
def show(run_ref: str | None = typer.Argument(None, help="Run id or prefix; latest if omitted.")):
    """Redraw a saved run."""
    rec = find_run(run_ref)
    if rec is None:
        console.print("[red]no such run[/red]")
        raise typer.Exit(1)
    render(rec, console)


def _metric(rec: dict, n: str, metric: str) -> str:
    e = rec["analysis"]["targets"].get(n)
    v = None if e is None else e["all"][metric]
    return "—" if v is None else f"{v:.1f}"


def _burst(rec: dict, n: str) -> str:
    """The longest run of consecutive lost probes; "—" when there is none to count."""
    b = burst_probes(rec["analysis"]["targets"].get(n) or {})
    return "—" if b is None else str(b)


@app.command("list")
def list_runs():
    """List saved runs."""
    from rich.table import Table

    t = Table()
    for c in ("id", "medium", "isp", "down", "up", "sao-paulo p95", "verdict"):
        t.add_column(c)
    for r in load_runs():
        row = summary_row(r)
        p95 = row["sao_paulo_p95_ms"]
        t.add_row(row["id"], row["medium"] or "?", row["isp"] or "?",
                  f"{row['download_mbps']:.1f}", f"{row['upload_mbps']:.1f}",
                  "—" if p95 is None else f"{p95:.0f}", row["sao_paulo_route"] or "")
    console.print(t)


@app.command("compare")
def compare(a: str, b: str):
    """Show two saved runs side by side."""
    from rich.table import Table

    ra, rb = find_run(a), find_run(b)
    if ra is None or rb is None:
        console.print("[red]run not found[/red]")
        raise typer.Exit(1)
    t = Table(title="compare")
    t.add_column("metric")
    t.add_column(ra["id"], justify="right")
    t.add_column(rb["id"], justify="right")

    def row(name, fa, fb):
        t.add_row(name, fa, fb)

    sa = {x["direction"]: x["mbps"] for x in ra["speed"]}
    sb = {x["direction"]: x["mbps"] for x in rb["speed"]}
    row("download Mbit/s", f"{sa.get('download', 0):.1f}", f"{sb.get('download', 0):.1f}")
    row("upload Mbit/s", f"{sa.get('upload', 0):.1f}", f"{sb.get('upload', 0):.1f}")
    row("local overhead ms", str(ra["analysis"]["local_overhead_ms"]),
        str(rb["analysis"]["local_overhead_ms"]))
    names = sorted(set(ra["analysis"]["targets"]) | set(rb["analysis"]["targets"]))
    for n in names:
        for metric in ("loss_pct", "min_ms", "median_ms", "p95_ms", "jitter_ms"):
            row(f"{n} {metric}", _metric(ra, n, metric), _metric(rb, n, metric))
        row(f"{n} burst", _burst(ra, n), _burst(rb, n))
    console.print(t)


@app.command("web")
def web_cmd(
    run_ref: str | None = typer.Argument(None, help="Run id or prefix; latest if omitted."),
    no_map: bool = typer.Option(False, "--no-map", help="Skip the route trace and the map."),
):
    """Build the web report (charts, tables, route map) for a saved run and open it."""
    from .render_web import write_report

    rec = find_run(run_ref)
    if rec is None:
        console.print("[red]no such run[/red]")
        raise typer.Exit(1)
    path = write_report(rec, status=_status, with_map=not no_map)
    console.print(f"report written to {path}")


@app.command("publish")
def publish_cmd(
    run_ref: str | None = typer.Argument(None, help="Run id or prefix; latest if omitted."),
    no_redact: bool = typer.Option(False, "--no-redact",
                                   help="Keep the public IP and Wi-Fi name in the published page."),
    no_map: bool = typer.Option(False, "--no-map", help="Skip the route trace and the map."),
):
    """Publish the report of a saved run to the public GitHub Pages site."""
    from .publish import REPO_URL
    from .publish import publish as publish_run

    rec = find_run(run_ref)
    if rec is None:
        console.print("[red]no such run[/red]")
        raise typer.Exit(1)
    if no_redact:
        console.print(f"[yellow]warning:[/yellow] publishing the public IP and Wi-Fi name "
                      f"to the public repository {REPO_URL}")
    url = publish_run(rec, status=_status, redact=not no_redact, with_map=not no_map)
    console.print(f"published at {url}")


@app.command("map")
def map_cmd(
    run_ref: str | None = typer.Argument(None, help="Run id or prefix; latest if omitted."),
):
    """Trace the routes of a saved run and open them on a map in the browser."""
    from .render_map import build_map

    rec = find_run(run_ref)
    if rec is None:
        console.print("[red]no such run[/red]")
        raise typer.Exit(1)
    path = build_map(rec, status=_status)
    console.print(f"map written to {path}")


if __name__ == "__main__":
    app()
