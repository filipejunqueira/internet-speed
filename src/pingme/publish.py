"""Publish redacted reports to the public GitHub Pages repository.

The site is a clone of `internet-speed-reports` under the data directory: `index.html`
at the root, `runs/index.json` (newest first), and per run both `runs/<id>.html`, the
finished report, and `runs/<id>.json`, the numbers behind it so the explorer page can
compare runs. `assets/` holds plotly, the world map its geographic charts are drawn on,
and the explorer's own JavaScript. The private log `runs.jsonl` is only ever read here,
never written.
"""

from __future__ import annotations

import json
import subprocess
from importlib.resources import files
from pathlib import Path

import httpx
from plotly.offline import get_plotlyjs

from .render_map import traces_for
from .render_web import (
    PLOTLY_ASSET,
    TOPOJSON_ASSET,
    _css,
    build_report,
    explorer_css,
    explorer_tokens,
)
from .render_web import redact as redact_run
from .store import data_dir, load_runs, summary_row

REPO_URL = "git@github.com:filipejunqueira/internet-speed-reports.git"
PAGE_BASE = "https://filipejunqueira.github.io/internet-speed-reports/"
TOPOJSON_URL = "https://cdn.plot.ly/un/world_110m.json"


def fetch_topojson() -> str:
    """Plotly's world map: the exact file every scattergeo asks its CDN for, 278 KB.

    The address matters. This plotly.js defaults `topojsonURL` to `https://cdn.plot.ly/un/`
    and builds the name as scope + resolution, so an unscoped map at the default resolution
    fetches `un/world_110m.json`. The older `cdn.plot.ly/world_110m.json` is a different,
    smaller file: serving that instead would quietly redraw the world's borders rather than
    only move where they come from.

    Its own function so that a test can put something else in its place rather than go
    near the network.
    """
    r = httpx.get(TOPOJSON_URL, timeout=30)
    r.raise_for_status()
    return r.text


def site_dir() -> Path:
    """The local clone of the reports repository; cloned on first use."""
    d = data_dir() / "site"
    if not (d / ".git").exists():
        subprocess.run(["git", "clone", REPO_URL, str(d)], check=True)
    return d


def site_files(site: Path) -> list[str]:
    """Copy the explorer's JavaScript into `<site>/assets/`, overwriting whatever is there.

    The modules ship with the package, so every publish puts the version that came with
    this release on the site. `importlib.resources` finds them from an installed package
    as well as from a source checkout. Returns the names written, newest copy each time.
    """
    assets = site / "assets"
    assets.mkdir(exist_ok=True)
    written = []
    for res in (files("pingme") / "site").iterdir():
        if res.name.endswith(".js"):
            (assets / res.name).write_text(res.read_text(encoding="utf-8"), encoding="utf-8")
            written.append(res.name)
    return sorted(written)


def backfill_run_data(runs_dir: Path, rows: list[dict]) -> int:
    """Write the missing `runs/<id>.json` for the runs the site already lists.

    Earlier only the run being published got its numbers written, so every row the site
    already carried had nothing behind it: ticking one in the explorer said the numbers
    would not load, and the comparison stayed empty until that run was published again by
    hand. Returns how many were filled in.

    Only a run that already has a row in the index is ever written. A run sitting in the
    private log that was never published must not reach the site as a side effect of
    publishing another one: that is a privacy rule, not a saving. Walking the index rows
    rather than the files in `runs/` is what enforces it, and it is also why `index.json`
    itself can never be a candidate here: no run id is "index", the list is not a run.
    A file that already exists is left exactly as it is, and every copy written here is
    redacted whatever the flag on the publish that triggered it.
    """
    log = {r["id"]: r for r in load_runs()}
    written = 0
    for row in rows:
        dest = runs_dir / f"{row['id']}.json"
        if dest.exists():
            continue
        run = log.get(row["id"])
        if run is None:  # published from another machine, or since dropped from the log
            continue
        dest.write_text(json.dumps(redact_run(run), ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8")
        written += 1
    return written


def build_index(rows: list[dict], site: Path | None = None) -> str:
    """index.html: the shell of the explorer. Its table and charts are built by assets/app.js.

    Python only frames the page here: the report stylesheet, the block of colours, target
    order and thresholds the JavaScript reads so that nothing on the site hard-codes a hex,
    and an empty `<main>` for it to fill. The heading stays outside `<main>` so that the
    script can replace everything inside it without wiping the title. The list of runs
    itself is fetched from `runs/index.json`, so publishing one run never re-renders a row.

    `site` is passed through to `explorer_tokens()` only so that it can see whether the
    world map is really on the site before telling the page to use it.
    """
    tokens = json.dumps(explorer_tokens(site), ensure_ascii=False)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>pingme — reports</title><style>{_css()}{explorer_css()}
a{{color:var(--ink)}} header{{max-width:1180px;margin:0 auto;padding:20px 16px 0}}</style>
<script id="pingme-tokens" type="application/json">{tokens}</script></head><body>
<header>
<h1>pingme — reports</h1>
<p class="meta">{len(rows)} published runs. Every run measures ping, jitter, packet loss,
download and upload, and the extra delay while the line is busy, against the router and
Valve's Dota relays in London, Madrid, US-East and São Paulo.</p>
</header>
<main></main>
<noscript><p>This page builds itself with JavaScript, which is switched off here. The list
of runs is readable as it stands at <a href="runs/index.json">runs/index.json</a>, and each
run has its own page under <code>runs/</code>.</p></noscript>
<script src="{PLOTLY_ASSET}"></script>
<script type="module" src="assets/app.js"></script>
</body></html>"""


def publish(run: dict, *, status=lambda msg: None, redact: bool = True,
            with_map: bool = True) -> str:
    """Write the run's page and the index into the site clone, commit, push; return the URL."""
    record = redact_run(run) if redact else run
    traces = traces_for(record, status) if with_map else None
    if traces:  # a run traced now, not when it was measured, carries its map on the site too
        record = {**record, "traces": traces}
    status("building report")
    page = build_report(record, traces, plotly="external")

    site = site_dir()
    subprocess.run(["git", "pull", "--rebase", "--quiet"], cwd=site, check=True)
    asset = site / PLOTLY_ASSET
    if not asset.exists():  # the exact plotly.js this plotly emits figures for, written once
        asset.parent.mkdir(exist_ok=True)
        asset.write_text(get_plotlyjs(), encoding="utf-8")
    topo = site / TOPOJSON_ASSET
    if not topo.exists():  # the world the map is drawn on, written once, same as plotly.js
        topo.parent.mkdir(exist_ok=True)
        try:
            topo.write_text(fetch_topojson(), encoding="utf-8")
        except Exception as e:  # noqa: BLE001 - the map falls back to the CDN, so carry on
            status(f"could not download the world map ({type(e).__name__}); the map will "
                   "load it from plotly's CDN, the way it does today")
    runs = site / "runs"
    runs.mkdir(exist_ok=True)
    site_files(site)
    row = summary_row(record)
    (runs / f"{record['id']}.html").write_text(page, encoding="utf-8")
    # the page beside its own numbers: the explorer reads this to compare runs
    (runs / f"{record['id']}.json").write_text(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    index_file = runs / "index.json"
    rows = json.loads(index_file.read_text(encoding="utf-8")) if index_file.exists() else []
    rows = [r for r in rows if r["id"] != row["id"]] + [row]
    rows.sort(key=lambda r: r["timestamp"], reverse=True)
    index_file.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    filled = backfill_run_data(runs, rows)
    if filled:
        status(f"filled in the numbers for {filled} run{'s' if filled != 1 else ''} "
               "already on the site")
    (site / "index.html").write_text(build_index(rows, site), encoding="utf-8")

    status("pushing to GitHub")
    subprocess.run(["git", "add", "-A"], cwd=site, check=True)
    changed = subprocess.run(["git", "status", "--porcelain"], cwd=site, check=True,
                             capture_output=True, text=True).stdout.strip()
    if changed:
        subprocess.run(["git", "commit", "-q", "-m", f"report {record['id']}"], cwd=site,
                       check=True)
        subprocess.run(["git", "push", "--quiet"], cwd=site, check=True)
    else:
        status("nothing new to publish; site already up to date")
    return PAGE_BASE + row["page"]
