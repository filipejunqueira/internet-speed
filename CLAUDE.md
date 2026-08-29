# internet-speed

## Overview

`pingme`: a Python 3.14 command that measures the current internet connection
(ping, jitter, loss, download/upload, delay while the line is busy) against the
router and Valve's Dota relays in London, Madrid, US-East and São Paulo, draws the
results in the terminal, and appends every run to a log. `pingme --web` adds an
HTML report with the same charts, the statistics as tables, and a traced route map.
Design and evidence: `PLAN.md`; direction: `TODO.md`.

## Commands

- install deps: `uv sync`
- run (60 s): `uv run pingme --label <name>`; `--quick` 30 s, `--long` 2 min, `--longer` 10 min
- run + web report: `uv run pingme --label <name> --web`
- read the log back: `uv run pingme list`, `uv run pingme show [id]`, `uv run pingme compare A B`
- web report for a saved run: `uv run pingme web [id]` (`--no-map` skips the ~2 min trace)
- test all: `uv run pytest`; test one: `uv run pytest -k <name>`
- lint: `uv run ruff check .`
- put `pingme` on PATH (user's own terminal, not the container): `uv tool install --editable .`

## Success criteria conventions

"Done" needs, in the same message: `uv run ruff check .` clean, `uv run pytest`
green, and for anything that measures or draws, a real run on this machine with
the output shown. Pure functions get a test against hand-computed inputs before
they are wired in.

## Structure

- `src/pingme/` — one module per concern; `run.py` orchestrates, `cli.py` is typer.
- `tests/fixtures/run.json` — a real saved run, trimmed; the web-report tests use it.
- Runs go to `$XDG_DATA_HOME/pingme/runs.jsonl` (one JSON object per line);
  reports and maps next to it. Nothing measured is written inside the repo.
- `notes/reports/` — hand-copied reports for review, git-ignored.
- `PINGME_OVERRIDE="sao-paulo=192.0.2.1"` swaps a target's address (failure tests).

## Corrections log

- Claude's shell cannot start `claude remote-control`; the user runs it in their own
  terminal (2026-08-29).
- `mtr` stops at hop 2 on this Three line; `traceroute -I` reaches the target (2026-08-29).
- Cloudflare's `__down` refuses requests over 50 MB; ask for 25 MB and loop (2026-08-29).
- plotext 6 is a rewrite; the code targets 5.x, pinned `<6` (2026-08-29).
