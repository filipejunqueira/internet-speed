"""Command line entry point: `pingme` runs a measurement; subcommands read the log back."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.markup import escape

from . import __version__
from .render_tui import render
from .run import Timing, run
from .store import burst_probes, find_run, load_runs, summary_row

if TYPE_CHECKING:  # only for the return annotation; the table is imported where it is built
    from rich.table import Table

app = typer.Typer(add_completion=False, invoke_without_command=True, no_args_is_help=False,
                  help="Measure, plot and log the quality of the current internet connection.")
console = Console()


def _status(msg: str) -> None:
    console.print(f"[dim]•[/dim] {msg}")


def parse_target(value: str) -> tuple[str, str]:
    """Turn one --target value, "n475=108.61.221.148", into a (name, address) pair.

    Nothing here checks that the address answers. An address that stays silent is a
    measurement in its own right, and a run already reports it as silent, with the
    count of what it was sent, rather than as total loss.
    """
    name, sep, ip = value.partition("=")
    name, ip = name.strip(), ip.strip()
    if not sep:
        raise ValueError(f"--target {value!r} needs a name and an address joined by an =, "
                         f"as in --target n475=108.61.221.148")
    if not name:
        raise ValueError(f"--target {value!r} has no name before the =; the name is what "
                         f"the target is called in the report")
    if not ip:
        raise ValueError(f"--target {value!r} has no address after the =; give the host "
                         f"or IP to measure")
    return name, ip


def _short(text: str | None, width: int = 28) -> str:
    """A note squeezed into a table column: cut with an ellipsis rather than wrapped.

    Escaped, because a note is free text and rich reads square brackets as markup: an
    unescaped "[check this]" disappears from the table, and a malformed one would take
    `pingme list` down for the whole log.
    """
    if not text:
        return "—"
    cut = text if len(text) <= width else text[:width - 1] + "…"
    return escape(cut)


# A repeatable option is a list, and ruff's B008 objects to a call in a mutable-typed
# default, so this one is built once out here rather than in the signature.
TARGET_OPTION = typer.Option(None, "--target", metavar="NAME=ADDRESS",
                             help="Also measure this address, e.g. n475=108.61.221.148. "
                                  "Repeatable. Measured, but not placed on the map: no "
                                  "physics, and no part in the local overhead.")


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
    trace_flag: bool = typer.Option(False, "--trace",
                                    help="Trace the route to every target and keep it in the "
                                         "record, without building a report. Costs a minute or "
                                         "so: one traceroute per relay."),
    target: list[str] | None = TARGET_OPTION,
    note: str | None = typer.Option(None, "--note",
                                    help="Free text kept with the run exactly as typed. The "
                                         "label becomes part of the run id, so anything with "
                                         "an = or a / in it belongs here instead."),
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
    # Both failures a --target can cause are reported the same way: a malformed value is
    # caught here, and a name that clashes with one of the six built-in targets is caught
    # by run() once the relay list is known. Neither should reach the user as a traceback.
    try:
        extra = [parse_target(v) for v in target or []]
        record = run(label, Timing(total, speed_s), status=_status,
                     trace=web or publish or trace_flag, note=note, extra=extra)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
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


def _metric(rec: dict, n: str, metric: str) -> float | None:
    """One summary figure over the whole run, or None when this run has no such target."""
    e = rec["analysis"]["targets"].get(n)
    return None if e is None else e["all"][metric]


def _burst(rec: dict, n: str) -> int | None:
    """The longest run of consecutive lost probes; None when there is none to count."""
    return burst_probes(rec["analysis"]["targets"].get(n) or {})


def _stall(rec: dict, n: str, key: str) -> float | None:
    """One stall figure, or None when nobody could count it.

    None covers a record saved before stalls were measured, a target with no idle
    samples to judge, and, for the coincidence, the router itself or a target that
    never spiked. A counted zero is a 0 and must not look like any of those.
    """
    stalls = (rec["analysis"]["targets"].get(n) or {}).get("stalls")
    return None if stalls is None else stalls.get(key)


def _num(v: float | None, nd: int = 1) -> str:
    return "—" if v is None else f"{v:.{nd}f}"


def _pct(v: float | None) -> str:
    """A share of 0 to 1 written as a percentage, the way `show` writes the same figure."""
    return "—" if v is None else f"{v * 100:.0f}%"


def _change(a: float | None, b: float | None, nd: int = 1) -> str:
    """The second run less the first, an em dash when either side never measured it.

    An em dash rather than a blank, so this column says what every other column on the
    table says: nobody counted this. A blank cell reads as nothing to say.
    """
    return "—" if a is None or b is None else f"{b - a:+.{nd}f}"


def network_of(rec: dict) -> tuple[str | None, str | None, str | None]:
    """Which network a run was taken on: Wi-Fi name, interface, public provider."""
    s = rec.get("snapshot") or {}
    return ((s.get("wifi") or {}).get("ssid"), s.get("interface"),
            (s.get("public") or {}).get("isp"))


def network_warning(ra: dict, rb: dict) -> str | None:
    """Say so when two runs were not taken on the same network; None when they match.

    The rule this serves is that a figure measured on one network is never compared
    with a figure measured on another. A warning is enough and the table is still
    printed: refusing to show the runs would be worse than showing them with a caveat.
    """
    differ = [f"{what} {x or 'none'} against {y or 'none'}"
              for what, x, y in zip(("Wi-Fi", "interface", "provider"),
                                    network_of(ra), network_of(rb), strict=True)
              if x != y]
    if not differ:
        return None
    return f"different networks: {'; '.join(differ)}. These numbers are not comparable."


def compare_table(ra: dict, rb: dict) -> Table:
    """Both runs side by side, with the change from the first to the second.

    The change column is what a verdict is read off. Where one of the two runs never
    measured a figure it holds an em dash, the same as every other cell in the table, so
    "nobody counted this" never reads as a difference of nothing. The note row is the one
    exception: it is text, and text has no difference to take.
    """
    from rich.table import Table

    t = Table(title="compare")
    t.add_column("metric")
    t.add_column(ra["id"], justify="right")
    t.add_column(rb["id"], justify="right")
    t.add_column("change (second − first)", justify="right")

    def row(name: str, va: float | None, vb: float | None, nd: int = 1) -> None:
        t.add_row(name, _num(va, nd), _num(vb, nd), _change(va, vb, nd))

    t.add_row("note", _short(ra.get("note"), 40), _short(rb.get("note"), 40), "")
    sa = {x["direction"]: x["mbps"] for x in ra["speed"]}
    sb = {x["direction"]: x["mbps"] for x in rb["speed"]}
    row("download Mbit/s", sa.get("download"), sb.get("download"))
    row("upload Mbit/s", sa.get("upload"), sb.get("upload"))
    row("local overhead ms", ra["analysis"]["local_overhead_ms"],
        rb["analysis"]["local_overhead_ms"])
    names = sorted(set(ra["analysis"]["targets"]) | set(rb["analysis"]["targets"]))
    for n in names:
        for metric in ("loss_pct", "min_ms", "median_ms", "p95_ms", "jitter_ms"):
            row(f"{n} {metric}", _metric(ra, n, metric), _metric(rb, n, metric))
        row(f"{n} burst", _burst(ra, n), _burst(rb, n), nd=0)
        row(f"{n} spikes", _stall(ra, n, "spikes"), _stall(rb, n, "spikes"), nd=0)
        # The record keeps the share as 0 to 1; both terminal views show a percentage, so
        # the same figure cannot be read as two different measurements. Its change is
        # therefore in percentage points.
        sa_share, sb_share = (_stall(ra, n, "router_coincidence"),
                              _stall(rb, n, "router_coincidence"))
        change = ("—" if sa_share is None or sb_share is None
                  else f"{(sb_share - sa_share) * 100:+.0f}")
        t.add_row(f"{n} router-shared spikes", _pct(sa_share), _pct(sb_share), change)
    return t


@app.command("list")
def list_runs():
    """List saved runs."""
    from rich.table import Table

    t = Table()
    for c in ("id", "medium", "isp", "down", "up", "sao-paulo p95", "verdict", "note"):
        t.add_column(c)
    for r in load_runs():
        row = summary_row(r)
        p95 = row["sao_paulo_p95_ms"]
        # the note comes off the record itself: summary_row is the site index's row
        # and does not carry it
        t.add_row(row["id"], row["medium"] or "?", row["isp"] or "?",
                  f"{row['download_mbps']:.1f}", f"{row['upload_mbps']:.1f}",
                  "—" if p95 is None else f"{p95:.0f}", row["sao_paulo_route"] or "",
                  _short(r.get("note")))
    console.print(t)


@app.command("compare")
def compare(a: str, b: str):
    """Show two saved runs side by side."""
    ra, rb = find_run(a), find_run(b)
    if ra is None or rb is None:
        console.print("[red]run not found[/red]")
        raise typer.Exit(1)
    warning = network_warning(ra, rb)
    if warning:
        console.print(f"[red]{warning}[/red]")
    console.print(compare_table(ra, rb))


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
