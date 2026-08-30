"""Append-only log of runs: one JSON object per line under the XDG data directory."""

from __future__ import annotations

import json
import os
from pathlib import Path


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    d = Path(base) / "pingme"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    d = Path(base) / "pingme"
    d.mkdir(parents=True, exist_ok=True)
    return d


def runs_file() -> Path:
    return data_dir() / "runs.jsonl"


def append_run(run: dict) -> Path:
    p = runs_file()
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(run, ensure_ascii=False) + "\n")
    return p


def load_runs() -> list[dict]:
    p = runs_file()
    if not p.exists():
        return []
    runs = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                runs.append(json.loads(line))
    return runs


def find_run(ref: str | None) -> dict | None:
    """Find a run by its full id, by a unique prefix, or the latest one when ref is None."""
    runs = load_runs()
    if not runs:
        return None
    if ref is None:
        return runs[-1]
    exact = [r for r in runs if r["id"] == ref]
    if exact:
        return exact[-1]
    prefixed = [r for r in runs if r["id"].startswith(ref)]
    if len(prefixed) == 1:
        return prefixed[0]
    return None


def summary_row(run: dict) -> dict:
    """The one-line summary of a run: what `pingme list` shows and what the site index stores."""
    s = run["snapshot"]
    pub = s.get("public") or {}
    speed = {x["direction"]: x["mbps"] for x in run["speed"]}
    targets = run["analysis"]["targets"]
    sp = targets.get("sao-paulo") or {}
    return {
        "id": run["id"],
        "label": run.get("label"),
        "timestamp": run["timestamp"],
        "isp": pub.get("isp"),
        "city": pub.get("city"),
        "country": pub.get("country"),
        "medium": s.get("medium"),
        "download_mbps": speed.get("download", 0.0),
        "upload_mbps": speed.get("upload", 0.0),
        "worst_loss_pct": max((t["all"]["loss_pct"] for t in targets.values()), default=None),
        "local_overhead_ms": run["analysis"]["local_overhead_ms"],
        "sao_paulo_p95_ms": (sp.get("all") or {}).get("p95_ms"),
        "sao_paulo_route": (sp.get("physics") or {}).get("most_consistent"),
        "page": f"runs/{run['id']}.html",
    }
