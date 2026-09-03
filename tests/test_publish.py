import json
import re
import subprocess
from pathlib import Path

import pytest

from pingme import publish as pub
from pingme.render_web import PLOTLY_ASSET, build_report, redact
from pingme.store import summary_row

FIXTURE = Path(__file__).parent / "fixtures" / "run.json"


def _run() -> dict:
    return json.loads(FIXTURE.read_text())


@pytest.fixture
def site(tmp_path, monkeypatch):
    """Data dir under tmp, a copy of the fixture as the private log, and git stubbed out."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    log = tmp_path / "pingme" / "runs.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text(json.dumps(_run()) + "\n", encoding="utf-8")
    site_dir = tmp_path / "pingme" / "site"
    site_dir.mkdir()
    (site_dir / ".git").mkdir()  # looks cloned already, so site_dir() never calls git clone
    calls = []
    def fake_git(cmd, **kw):
        calls.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, stdout="M index.html\n", stderr="")

    monkeypatch.setattr(pub.subprocess, "run", fake_git)
    return {"dir": site_dir, "log": log, "git": calls}


def test_publish_never_touches_the_private_log(site):
    before = site["log"].read_bytes()
    url = pub.publish(_run(), with_map=False)
    assert site["log"].read_bytes() == before
    assert url == pub.PAGE_BASE + "runs/smoke_2026-08-29T21-02-51Z.html"
    verbs = [c[0][1] for c in site["git"]]
    assert verbs[0] == "pull" and verbs[-1] == "push" and "commit" in verbs
    assert not any("--force" in c[0] or "-f" in c[0] for c in site["git"])
    assert all(c[1]["cwd"] == site["dir"] and c[1]["check"] is True for c in site["git"])
    assert "--force" not in " ".join(" ".join(c[0]) for c in site["git"])


def test_redaction_removes_ip_and_ssid_and_nothing_else_is_pretended():
    run = _run()
    ip, ssid = run["snapshot"]["public"]["ip"], run["snapshot"]["wifi"]["ssid"]
    redacted = build_report(redact(run), plotly="external")
    assert ip not in redacted and ssid not in redacted
    plain = build_report(run, plotly="external")
    assert ip in plain and ssid in plain
    assert run["snapshot"]["public"]["ip"] == ip  # the input record is untouched


def test_republishing_keeps_ids_unique(site):
    pub.publish(_run(), with_map=False)
    pub.publish(_run(), with_map=False)
    rows = json.loads((site["dir"] / "runs" / "index.json").read_text())
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)) == 1
    index = (site["dir"] / "index.html").read_text()
    # the shell links no run pages at all: app.js builds the table from runs/index.json
    assert "smoke_2026-08-29T21-02-51Z.html" not in index
    page = (site["dir"] / "runs" / "smoke_2026-08-29T21-02-51Z.html").read_text()
    assert _run()["snapshot"]["public"]["ip"] not in page


def test_cdn_report_is_small():
    html = build_report(_run(), plotly="external")
    assert len(html.encode()) < 300_000
    assert '<script src="../assets/plotly-' in html


def test_summary_row_matches_fixture():
    row = summary_row(_run())
    assert row["id"] == "smoke_2026-08-29T21-02-51Z"
    assert row["download_mbps"] == 18.6 and row["upload_mbps"] == 2.4
    assert row["sao_paulo_p95_ms"] == 833.75
    assert row["page"] == "runs/smoke_2026-08-29T21-02-51Z.html"
    assert row["duration_s"] == 30.0


def _tokens(index_html: str) -> dict:
    """The colours and thresholds Python hands the JavaScript, read back out of the page."""
    block = re.search(r'<script id="pingme-tokens" type="application/json">(.*?)</script>',
                      index_html, re.S)
    assert block, "the index carries no tokens block"
    return json.loads(block.group(1))


def test_publish_writes_the_numbers_beside_the_page(site):
    pub.publish(_run(), with_map=False)
    saved = json.loads((site["dir"] / "runs" / "smoke_2026-08-29T21-02-51Z.json").read_text())
    assert saved["id"] == _run()["id"]
    assert saved["analysis"]["targets"].keys() == _run()["analysis"]["targets"].keys()
    assert saved["snapshot"]["public"]["ip"] == "redacted"


def test_publish_backfills_the_numbers_for_runs_already_listed(site):
    """A row on the site with no numbers file leaves the explorer nothing to compare.

    The site here is what the earlier code left behind: an older run has its row in
    `runs/index.json` but no `runs/<id>.json`, so ticking it said the numbers would not
    load. A third run sits in the private log with no row at all, and must stay off the
    site: publishing one run never publishes another as a side effect.
    """
    older, current, unpublished = _run(), _run(), _run()
    older["id"], older["timestamp"] = "older_2026-08-28T10-00-00Z", "2026-08-28T10:00:00Z"
    current["id"], current["timestamp"] = "current_2026-08-30T10-00-00Z", "2026-08-30T10:00:00Z"
    unpublished["id"] = "private_2026-08-31T10-00-00Z"
    unpublished["timestamp"] = "2026-08-31T10:00:00Z"
    site["log"].write_text(
        "".join(json.dumps(r) + "\n" for r in (older, current, unpublished)), encoding="utf-8")
    runs = site["dir"] / "runs"
    runs.mkdir(parents=True)
    (runs / "index.json").write_text(json.dumps([summary_row(redact(older))]), encoding="utf-8")

    pub.publish(current, with_map=False)

    assert (runs / f"{current['id']}.json").exists()
    assert (runs / f"{older['id']}.json").exists(), "the row already on the site got no numbers"
    filled = json.loads((runs / f"{older['id']}.json").read_text())
    assert filled["id"] == older["id"]
    # backfilled copies are redacted whatever the flag on the publish that triggered them
    assert filled["snapshot"]["public"]["ip"] == "redacted"
    assert not (runs / f"{unpublished['id']}.json").exists()
    assert unpublished["id"] not in (runs / "index.json").read_text()


def test_a_traced_publish_carries_its_route_and_says_so(site, monkeypatch):
    """A run traced at publish time keeps the trace on the site, so the map can be drawn."""
    trace = {"sao-paulo": {"error": None, "hops": [], "locations": []}}  # the shape a trace has
    monkeypatch.setattr(pub, "traces_for", lambda record, status: trace)
    run = _run()
    pub.publish(run)
    saved = json.loads((site["dir"] / "runs" / "smoke_2026-08-29T21-02-51Z.json").read_text())
    assert "sao-paulo" in saved["traces"]
    assert "traces" not in run  # the record handed in is never written to


def test_publish_ships_every_explorer_module(site):
    pub.publish(_run(), with_map=False)
    assets = site["dir"] / "assets"
    # publish() copies whatever the package carries rather than a list it keeps in step by
    # hand, so the test reads the same directory instead of naming the modules again
    packaged = sorted((Path(pub.__file__).parent / "site").glob("*.js"))
    # with no modules the loop below would check nothing and still pass
    assert packaged, "the package carries no explorer modules, so publish shipped none"
    for module in packaged:
        copied = assets / module.name
        assert copied.exists(), f"{module.name} was not copied to the site"
        assert copied.read_text() == module.read_text()


def test_index_is_the_explorer_shell(site):
    pub.publish(_run(), with_map=False)
    index = (site["dir"] / "index.html").read_text()
    assert f'<script src="{PLOTLY_ASSET}"></script>' in index
    assert '<script type="module" src="assets/app.js"></script>' in index
    # <main> is left empty on purpose: app.js fills it, and would wipe a heading put inside
    assert "<main></main>" in index and "<table" not in index
    assert "runs/index.json" in index  # the noscript fallback names where the list lives
    assert _tokens(index)["targetOrder"][0] == "router"


def test_the_tokens_block_carries_three_run_slots_and_every_key(site):
    pub.publish(_run(), with_map=False)
    tokens = _tokens((site["dir"] / "index.html").read_text())
    assert set(tokens) == {"runSlots", "chrome", "status", "targetOrder", "thresholds",
                           "intervalS", "maxRuns", "font"}
    # three is the cap because a fourth hue fails the colour-blindness check on the map
    assert len(tokens["runSlots"]["light"]) == len(tokens["runSlots"]["dark"]) == 3
    assert tokens["maxRuns"] == 3
    assert len(set(tokens["runSlots"]["light"])) == 3
    assert set(tokens["chrome"]) == {"light", "dark"}
    assert set(tokens["status"]) == {"good", "warning", "serious", "critical"}
    assert set(tokens["thresholds"]) == {"lossWarn", "lossCrit", "penaltyWarn", "penaltyCrit",
                                         "burstWarn", "burstCrit"}
    assert tokens["intervalS"] == 0.2
