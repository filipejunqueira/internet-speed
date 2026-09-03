# internet-speed

## Overview

`pingme`: a Python 3.14 command that measures the current internet connection
(ping, jitter, loss, download/upload, delay while the line is busy) against the
router and Valve's Dota relays in London, Madrid, US-East and São Paulo, draws the
results in the terminal, and appends every run to a log. `pingme --web` adds an
HTML report with the same charts, the statistics as tables, and a traced route map;
`pingme --publish` puts a redacted copy on GitHub Pages.

Packet loss is counted from ping's own sent count and the sequence numbers that
come back, so a gap is real loss and a probe lost at the end of a run is not
missed. Each target also reports its longest burst: the most probes lost back to
back, which is what a game actually feels. An address that never answers at all,
like the ISP hop on BT, is reported as silent with its sent count, not as 100 %
loss. Note the limit: these are ICMP probes, not game traffic. Routers drop
ICMP first under load, so this can show loss a game would never feel.
Design and evidence: `notes/plans/2026-08-31_pingme-v1-and-pages.plan.md`;
direction: `TODO.md`.

## Commands

- install deps: `uv sync`
- run (60 s): `uv run pingme --label <name>`; `--quick` 30 s, `--long` 2 min, `--longer` 10 min
- run + web report: `uv run pingme --label <name> --web`
- read the log back: `uv run pingme list`, `uv run pingme show [id]`, `uv run pingme compare A B`
- web report for a saved run: `uv run pingme web [id]` (`--no-map` skips the map; runs made
  with `--web`/`--publish` carry their trace, older ones are traced now)
- publish to GitHub Pages: `uv run pingme --label <name> --publish`, or `uv run pingme publish [id]`
  (redacts IP and SSID by default; `--no-redact` to keep them; `--no-map` skips the map).
  Site: https://filipejunqueira.github.io/internet-speed-reports/
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
- Hidden hops depend on the provider: Three hides every hop (ICMP, UDP and TCP, even
  as root); BT shows most of them. `mtr` stops at hop 2 where `traceroute -I` gets
  through, so the tracer uses `traceroute -I` (2026-08-29, rechecked on BT 2026-08-30).
- `cdn.plot.ly` refuses the plotly.js version this plotly ships (7.0.0 → HTTP 403), so
  the site hosts its own copy under `assets/` (2026-08-30).
- Claude's shell reads the user's real home, so `/home/filipejunqueira/.local/share/pingme/`
  holds the runs made in their terminal; the container's own copy is elsewhere (2026-08-30).
- After a multi-part edit script, grep the file for each change. One edit silently did
  not apply and shipped a broken `run()` call (2026-08-30).
- Cloudflare's `__down` refuses requests over 50 MB; ask for 25 MB and loop (2026-08-29).
- `ping -c N -w D` does not send N probes: with a deadline, `-c` means "until N are
  answered", and at the deadline ping abandons the probe still in flight and counts it
  lost. Against Sao Paulo (210 ms answers, 200 ms between probes, so one always in
  flight) `-c 10 -w 4` reported 9 % loss where `-c 10 -W 2` reported 0 % in the same
  two seconds. Use `-c` with `-W` and no deadline (2026-09-03).
- `ping` in Claude's shell is an alias to `gping`, which the container does not have.
  Call `/usr/bin/ping` when testing by hand; the code uses `shutil.which`, which is
  unaffected (2026-09-03).
- A PostToolUse hook runs `ruff format` on every file written with Edit or Write. This
  codebase is not ruff-formatted (it uses hanging indents), so that would rewrite about
  993 lines across `src/pingme/`. Make Python edits through the shell instead, then run
  `uv run ruff check .`, which is the project's actual gate (2026-09-03).
- plotext 6 is a rewrite; the code targets 5.x, pinned `<6` (2026-08-29).
