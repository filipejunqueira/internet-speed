import json
import subprocess
from pathlib import Path

import pytest

from pingme import publish as pub
from pingme.render_web import build_report, redact
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
    assert index.count('href="runs/') == 1
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
