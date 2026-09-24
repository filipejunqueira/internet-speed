"""Build a local copy of the published site with the code as it stands, to test before publishing.

usage: uv run python notes/site-walk-2026-09-24/build_local.py <dir>

Copies the site clone (without its .git), writes this checkout's JavaScript into assets/,
rebuilds index.html, and rebuilds every report page from the redacted JSON beside it, which
is the record a publish would draw it from. Nothing is committed, pushed or published. Serve
the folder with `python3 -m http.server 8765 --bind 127.0.0.1` and point the .mjs checks at it.
"""
import json
import shutil
import sys
from pathlib import Path

from pingme.publish import build_index, site_dir, site_files
from pingme.render_web import build_report


def main(out: Path) -> None:
    shutil.copytree(site_dir(), out, ignore=shutil.ignore_patterns(".git"), dirs_exist_ok=True)
    print("modules:", ", ".join(site_files(out)))
    rows = json.loads((out / "runs" / "index.json").read_text(encoding="utf-8"))
    (out / "index.html").write_text(build_index(rows, out), encoding="utf-8")
    for row in rows:
        data = out / "runs" / f"{row['id']}.json"
        if not data.exists():
            print("no data for", row["id"])
            continue
        rec = json.loads(data.read_text(encoding="utf-8"))
        page = build_report(rec, rec.get("traces"), plotly="external")
        (out / "runs" / f"{row['id']}.html").write_text(page, encoding="utf-8")
        print("rebuilt", row["id"])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
