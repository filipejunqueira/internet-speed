"""Publish redacted reports to the public GitHub Pages repository.

The site is a clone of `internet-speed-reports` under the data directory: `index.html`
at the root, `runs/index.json` (newest first) and one `runs/<id>.html` per run. The
private log `runs.jsonl` is only ever read here, never written.
"""

from __future__ import annotations

import html
import json
import subprocess
from pathlib import Path

from plotly.offline import get_plotlyjs

from .render_map import traces_for
from .render_web import CHROME, PLOTLY_ASSET, _css, build_report
from .render_web import redact as redact_run
from .store import data_dir, summary_row

REPO_URL = "git@github.com:filipejunqueira/internet-speed-reports.git"
PAGE_BASE = "https://filipejunqueira.github.io/internet-speed-reports/"


def site_dir() -> Path:
    """The local clone of the reports repository; cloned on first use."""
    d = data_dir() / "site"
    if not (d / ".git").exists():
        subprocess.run(["git", "clone", REPO_URL, str(d)], check=True)
    return d


def _fmt(v, nd: int = 1) -> str:
    return "—" if v is None else f"{v:,.{nd}f}"


def _index_row(row: dict) -> str:
    cells = [
        f'<a href="{html.escape(row["page"])}">{html.escape(row.get("label") or row["id"])}</a>',
        html.escape(row["timestamp"][:16].replace("T", " ")),
        html.escape(row.get("isp") or "—"),
        html.escape(row.get("city") or "—"),
        html.escape(row.get("medium") or "—"),
        f'{_fmt(row["download_mbps"])} / {_fmt(row["upload_mbps"])}',
        _fmt(row.get("worst_loss_pct")),
        _fmt(row.get("worst_burst_probes"), 0),
        _fmt(row.get("sao_paulo_p95_ms"), 0),
        html.escape(row.get("sao_paulo_route") or "—"),
    ]
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def build_index(rows: list[dict]) -> str:
    """index.html: one table of published runs, newest first, each linking to its page."""
    heads = ("label", "date (UTC)", "ISP", "city", "medium", "down / up Mbit/s",
             "worst loss %", "worst burst", "São Paulo p95 ms", "route verdict")
    ordered = sorted(rows, key=lambda r: r["timestamp"], reverse=True)
    body = "".join(_index_row(r) for r in ordered)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>pingme — reports</title><style>{_css()}
.wrap{{overflow-x:auto}} table.stats td:first-child{{text-align:left}}
a{{color:{CHROME['light']['ink']}}}</style></head><body><main>
<h1>pingme — reports</h1><p class="meta">{len(ordered)} published runs, newest first</p>
<section class="card"><div class="wrap"><table class="stats"><thead><tr>
{''.join(f'<th>{html.escape(h)}</th>' for h in heads)}</tr></thead>
<tbody>{body}</tbody></table></div></section>
</main></body></html>"""


def publish(run: dict, *, status=lambda msg: None, redact: bool = True,
            with_map: bool = True) -> str:
    """Write the run's page and the index into the site clone, commit, push; return the URL."""
    record = redact_run(run) if redact else run
    traces = traces_for(record, status) if with_map else None
    status("building report")
    page = build_report(record, traces, plotly="external")

    site = site_dir()
    subprocess.run(["git", "pull", "--rebase", "--quiet"], cwd=site, check=True)
    asset = site / PLOTLY_ASSET
    if not asset.exists():  # the exact plotly.js this plotly emits figures for, written once
        asset.parent.mkdir(exist_ok=True)
        asset.write_text(get_plotlyjs(), encoding="utf-8")
    runs = site / "runs"
    runs.mkdir(exist_ok=True)
    row = summary_row(record)
    (runs / f"{record['id']}.html").write_text(page, encoding="utf-8")

    index_file = runs / "index.json"
    rows = json.loads(index_file.read_text(encoding="utf-8")) if index_file.exists() else []
    rows = [r for r in rows if r["id"] != row["id"]] + [row]
    rows.sort(key=lambda r: r["timestamp"], reverse=True)
    index_file.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    (site / "index.html").write_text(build_index(rows), encoding="utf-8")

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
