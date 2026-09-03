# pingme: loss you can trust, silent targets, burst loss

Date: 2026-09-03. Started from `master` at 7f08bac. Finished the same day; every step
is ticked and every success criterion below was met, with the checks named. Archived
from `PLAN.md`.

Commits: 6b8b776 the plan, 9b9ec17 steps 1 and 2, 0cc944c step 3, 2e89b2b step 4,
a55d0d8 the ping flag fix that step 5's real run uncovered, and the one carrying this
file for step 6.

## Context

Two decisions from TODO.md Now, both answered yes on 2026-09-03:

1. A target that never answers (isp-hop on BT) must read "does not answer probes",
   not "100 % loss". The user added: measuring loss stays essential. So the rule is
   narrow: **zero replies over the whole run** is "silent". One reply or more keeps a
   real loss number, however bad.
2. Add burst loss: the longest run of consecutive lost probes per target, marked on
   the timeline. A percentage treats ten losses together and ten spread out the same;
   a Dota match feels the burst.

The review of the code before planning found two defects in the loss numbers that
ship today. They are fixed by the same change that burst loss needs, so they are in
this plan, not in TODO.md Later.

**Defect A: idle-phase loss is wrong in every saved run.** `ProbeResult.sent_in`
(`src/pingme/probe.py:34`) counts a phase's sent probes as `max(seq) - min(seq) + 1`
over the replies in that phase. The idle phase runs before and after the speed test,
so its span covers the busy probes too. Every run in both logs shows it, for example
`leeds_bt_2026-08-30T15-32-20Z`: router all 300/299 (0.33 %), idle 299/197 (34.11 %),
busy 102/102. The idle row of the stats table in every published report carries this
number. Nobody noticed because the table sits inside a collapsed `<details>`.

**Defect B: loss at the end of a run is invisible.** `sent` is the highest sequence
number that came back (`probe.py:89`). Probes sent after the last reply are never
counted, so a line that dies in the last seconds reports no loss for them. The fix:
let `ping` reach its own `-w` deadline and read its summary line
("300 packets transmitted, 299 received"). That count is exact and includes the tail.
The highest sequence number stays as the fallback.

A third, smaller one: a silent target today gets `idle 0/0 0 %` and `busy 0/0 0 %`
next to `all 300/0 100 %`. Same record, three answers.

## Assumptions stated before work starts

- "Silent" means zero replies in the whole run and no process error (ping missing,
  OSError). A target with one reply in 300 is 99.7 % loss, shown as such.
- A silent target's `loss_pct` becomes `None` in `all`, `idle` and `busy`. Every
  renderer already prints `None` as "—", and `max()` over the others gives the
  worst-loss tile and the site index a number that ignores it.
- Lost probes get a send time from ping's fixed schedule: probe `k` leaves at
  `offset + (k - 1) * INTERVAL_S`, where `offset` is the median over replies of
  `t - rtt_ms / 1000 - (seq - 1) * INTERVAL_S`. Replies keep the phase recorded at
  receive time; lost probes get a phase from their send time against `phase_marks_s`.
  Every sequence number then belongs to exactly one phase, which is what fixes A.
- Burst badge thresholds, pingme's own, stated in the report footnote like the others:
  warning at 2 consecutive lost probes (0.4 s), critical at 5 (1 s). Confirmed by the
  user on 2026-09-03. A burst of 1 probe gets no badge of its own; the loss badge
  below already flags it.
- **Zero loss is the only clean pass** (user, 2026-09-03: "ideally we want to have no
  loss whatsoever"). Today `_status` returns a green tick for anything under 1 %, so
  1 packet lost in 1,495 reads as perfect. The loss badge becomes:
  0 lost is good, above 0 and under 1 % is warning, 1 % to 5 % is serious, 5 % and
  above is critical. `STATUS["serious"]` already exists and is unused. This changes
  `render_web._status` calls for loss only, plus the footnote, in step 4, and the
  terminal head line in step 3.
- Old records keep their stored analysis. `pingme show` on an old run still prints the
  old idle number. Renderers must tolerate records without the new fields. A
  `pingme reanalyse` command that recomputes from the saved samples goes to TODO.md
  Later, not this plan.

## Success criteria

All in one message at the end, per CLAUDE.md:

- `uv run ruff check .` clean and `uv run pytest` green (22 today plus the new tests).
- A real `uv run pingme --quick --label container_check` in the container, output
  shown. In it: the idle row's loss is close to the all row's loss (not ~34 %); if
  isp-hop is silent it reads "does not answer probes (N sent, 0 back)" and the summary
  table shows "—" for its loss; the verdict table has a burst column.
- The web report for that run (`uv run pingme web --no-map`) contains a "lost" trace
  only when probes were lost, and the worst-loss tile ignores the silent target.
  Checked with grep on the written HTML.
- A test with hand-built samples proves: idle 1–5 and 11–15, busy 6–10, lost seq 8
  gives idle 10 sent / 10 received / 0 %, busy 5 sent / 4 received / 20 %,
  longest burst 1 at seq 8. A second case with lost 7, 8, 9 gives burst 3 starting at
  seq 7, 0.6 s long.
- A test proves the ping summary parser: "300 packets transmitted, 299 received" → 300.

## Steps

Each step is one commit. Grep the file for every change after a multi-part edit
(corrections log, 2026-08-30).

### [x] Step 0: bookkeeping (5 min)

- Copy this plan to `PLAN.md` at the project root.
- TODO.md: move the two Now items into this plan's scope (they stay listed as Now
  with `→ PLAN.md`); add to Later: `pingme reanalyse` (recompute analysis from saved
  samples), upload over-count (see review notes), snapshots `.gitignore` decision.

### [x] Step 1: exact sent count from ping itself (25 min)

Done 2026-09-03, committed with step 2: removing `sent_in` in step 1 breaks the one
caller in `run.py`, and a commit that does not run is worse than a large one.
Checked against the real `ping` here: a normal run prints
"10 packets transmitted, 10 received" and exits 0; a target that ignores probes prints
its summary and exits 1; an unknown host exits 2 with a message on stderr. `-c` turned
out to mean "probes answered", not "probes sent", so a lossy line keeps probing into
the 2 s grace tail instead of having its last probe cut short.

File: `src/pingme/probe.py`.

- Add `SUMMARY_RE = re.compile(r"(\d+) packets transmitted")` and
  `parse_summary(line) -> int | None`.
- In `_ping_one`: pass `-w` as `str(int(duration))` (no `+ 1`) and read lines until
  EOF instead of breaking at the deadline; keep a safety `wait_for` of
  `duration + 5` seconds before `terminate()`. When a line parses as the summary, set
  `result.sent` to it. Keep `result.sent = max(result.sent, seq)` on every reply as
  the fallback for a ping that was killed before its summary.
- Remove the `"no replies"` error. Silence is a measurement, not an error. Keep the
  clock estimate for `sent` only when neither summary nor reply gave a number.
- Delete `ProbeResult.sent_in`; step 2 replaces it.
- Test in `tests/test_parsers.py`: `parse_summary` on the real summary line and on a
  reply line (None).

Note for the executor: ping with `-w 30` sends its last probe at about 29.8 s and
exits at 30 s, so `_orchestrate`'s `await probes` returns at the same moment as
before. If a run shows the process lingering, the safety timeout above ends it.

### [x] Step 2: per-probe accounting in the analysis (60 min)

Files: `src/pingme/stats.py`, `src/pingme/probe.py`, `src/pingme/run.py`.

Pure functions first, each with a test against hand-computed inputs:

- `stats.lost_seqs(sent: int, replied: Iterable[int]) -> list[int]`: sequence
  numbers in `1..sent` with no reply, ascending.
- `stats.longest_burst(lost: list[int]) -> tuple[int, int]`: `(length, start_seq)` of
  the longest run of consecutive numbers; `(0, 0)` when nothing was lost. Ties go to
  the earliest.
- `probe.send_offset(samples: list[Sample]) -> float`: the median described in the
  assumptions; `0.0` with no samples. `probe.send_time(seq, offset) -> float`.
- `run.phase_at(t: float, marks: dict) -> str`: `"download"` from `marks["download"]`
  up to `marks["upload"]`, `"upload"` up to `marks["idle-again"]`, otherwise
  `"idle"`. Missing marks mean idle.

Then in `run.analyse`:

- New signature `analyse(results, targets, snapshot, marks, route=route_for)`. The
  `route` parameter exists so the test can pass a lambda; `flag_odd_routes` already
  does this. Update the one caller in `run()`.
- Per target: `lost = lost_seqs(r.sent, (s.seq for s in r.samples))`, each with a send
  time and a phase. Sent per phase = replies with that phase + lost probes attributed
  to it. `busy` = download + upload as today.
- `silent = not r.samples and r.error is None`. When silent: `loss_pct` set to `None`
  in all three summaries after `summarise` (a one-line helper in `stats`, e.g.
  `Summary.without_loss()`), `entry["silent"] = True`, `entry["loss"] = None`.
- Otherwise `entry["silent"] = False` and

  ```
  entry["loss"] = {"lost": [[seq, round(t, 3)], ...],
                   "longest_burst_probes": n, "longest_burst_s": round(n * INTERVAL_S, 1),
                   "longest_burst_at_s": send time of the burst's first probe, or None}
  ```

- Test in `tests/test_run.py`: the two hand-built cases from the success criteria,
  through `analyse` with `route=lambda ip: {"dev": None, "src": None, "gateway": None}`
  and `marks={"download": 1.1, "upload": 2.1, "idle-again": 3.1}` with samples at
  `t = seq * 0.2`. Also a silent target: `sent=300`, no samples, `error=None` gives
  `silent=True` and `loss_pct is None` in all three summaries; a target with
  `error="ping not found"` is not silent.

### [x] Step 3: show it in the terminal (30 min)

File: `src/pingme/render_tui.py`.

- `_target_panel`: a silent target gets a plain (not red) panel:
  `"{name}  {ip}  — does not answer probes ({sent} sent, 0 back)"`. A real `error`
  keeps the red panel. Old records with `error == "no replies"` count as silent.
- Head line: after loss, add `lost {received-sent}/{sent}` and, when `entry["loss"]`
  exists, `burst {n} ({s} s at {at} s)`; `burst —` when nothing was lost.
- `_timeline`: when `entry.get("loss")` has lost probes, scatter them as red `x`
  markers at the top of the plot (`y = max rtt` of the target) labelled `lost`.
- `_verdict_table`: add a `burst` column after `loss`, showing the probe count.
- `cli.compare`: add a `longest_burst_probes` row per target.

### [x] Step 4: show it in the web report and the site index (45 min)

Files: `src/pingme/render_web.py`, `src/pingme/store.py`, `src/pingme/publish.py`.

- `BURST_WARN, BURST_CRIT = 2, 5` next to the other thresholds; footnote sentence
  added: "burst ≥2 probes (0.4 s) warning, ≥5 (1 s) critical".
- Loss badge: replace `LOSS_WARN, LOSS_CRIT = 1.0, 5.0` and the `_status` call for
  loss with a `_loss_status(lost_probes, loss_pct)` that returns good only when
  `lost_probes == 0`. Above 0 and under 1 % warning, 1 % to 5 % serious, 5 % and above
  critical. Footnote: "any lost probe is flagged; loss ≥1 % serious, ≥5 % critical".
  `_status` keeps its shape for the under-load penalty and the burst.
- `_target_section`: silent target shows `<p class="muted">does not answer probes
  (N sent, 0 back)</p>` instead of the error paragraph and gets no loss badge. Facts
  line gains `lost N of M` and `longest burst n probes (s s) at t s` with a badge.
- `_timeline`: add a `go.Scatter` trace named `lost`, `mode="markers"`, symbol `x`,
  colour `STATUS["critical"]`, `y = 0` for each lost probe, `meta={"role": "lost"}`
  (add `"lost"` to `LIGHT`/`DARK` with the critical red so the theme swap leaves it
  alone or maps it; either is fine as long as it stays red). Add a `vrect` over the
  longest burst when it is 2 probes or more, annotated `longest burst`.
- Tiles: add `longest burst` = worst across non-silent targets, with its badge.
- `worst_loss` (both in `build_report` and `store.summary_row`) already ignores
  `None`; keep it that way. `summary_row` gains `worst_burst_probes`.
- `publish._index_row` / `build_index`: add a `worst burst` column after
  `worst loss %`. Old rows in `runs/index.json` lack the key; `row.get` handles it.
- Tests in `tests/test_render_web.py`: load the fixture, set one target's
  `entry["loss"]` by hand with two lost probes and mark another target silent
  (`samples=[]`, `silent=True`, `loss_pct=None`); assert the HTML has one `"name":"lost"`
  trace, the text `does not answer probes`, and no `critical` loss badge for the
  silent one. Keep the determinism test.

### [x] Step 5: real run and report (15 min)

Done 2026-09-03. The first real run failed its own criterion and was worth the
whole step: Sao Paulo reported 0.7 % loss with the missing probe at the very last
second. `-c` alongside `-w` means "until N are answered", so ping walked away from
the probe still in flight, and Sao Paulo always has one in flight because it answers
in 210 ms while probes leave every 200 ms. Checked directly: `-c 10 -w 4` reports
"11 packets transmitted, 10 received, 9.09 % packet loss" where `-c 10 -W 2` reports
"10 packets transmitted, 10 received, 0 %", in the same 2 s. The fix is `-W` and no
deadline, with `ping_command` pulled out so a test can hold the line.

- `uv run ruff check .` and `uv run pytest`.
- `uv run pingme --quick --label container_check` in the container; paste the target
  panels' head lines and the summary table into the final message.
- `uv run pingme web --no-map` for that run; `grep -c '"name":"lost"'` and
  `grep -c 'does not answer probes'` on the written HTML.
- Do not publish from the container in this step. The user publishes the next real
  run from their own terminal (TODO.md Next).

### [x] Step 6: docs and wrap (10 min)

- CLAUDE.md Overview: the loss sentence becomes "Packet loss is counted from ping's
  own sent count and the sequence numbers that come back, so a gap is real loss and
  loss at the end of a run is not missed. A target with no replies at all is reported
  as silent, not as 100 % loss."
- TODO.md: Done entries for the two decisions and defects A and B; Now emptied.
- Tick every item in `PLAN.md`, then archive it under `notes/plans/` with today's date
  like the previous one.

## After the plan was finished

A review of the completed work found one more of the same kind of mistake and two
gaps, fixed in commit 38f79ba:

- The burst tile showed a green 0 on runs saved before bursts were counted. Missing
  and zero must not look alike. Both now read "—" against 0. The same distinction
  stopped the silent ISP hop in already-published runs from winning the worst-loss
  tile with its stored 100 %: the report for `leeds_bt_2026-08-30T15-32-20Z` now
  reads 0.7 %, its real worst.
- The rules for "silent address" and "longest burst" had four copies across the
  renderers. They live once in `store.py` now.
- `_read`, which the whole exact-sent-count claim rests on, had no test. It now reads
  a canned ping transcript where two probes go out after the last reply. `pingme
  compare` had been changed without being run once; running it showed the burst row
  label wrapping onto two lines.

## Review notes: what the code review found beyond the two decisions

Kept here so the findings survive even if they are not acted on now.

1. **Idle-phase loss wrong in every run** (defect A above). Fixed in step 2.
2. **Tail loss invisible** (defect B above). Fixed in step 1.
3. **Silent target inconsistency** (0 % idle next to 100 % all). Fixed in step 2.
4. **Upload speed over-count.** `speed._upload` counts a block as sent when the
   generator yields it into httpx's buffer, not when it leaves the machine. Three
   streams × 64 KB sits in buffers at the deadline. On a 2 Mbit/s uplink that is about
   0.8 s of data over a 10 s test, an over-count of roughly 8 %. On a fast line it is
   noise. Goes to TODO.md Later.
5. **Old runs can be recomputed.** Every record stores its samples, so a
   `pingme reanalyse [id]` could rebuild the analysis with the fixed accounting and
   append the result as a new record. TODO.md Later.
6. **Snapshots are git-ignored** (`.gitignore:7`) while the snapshot skill treats them
   as tracked history. Not code. Needs the user's decision; goes to TODO.md so it is
   not lost again.
7. **No test covers `analyse`.** The `route=` parameter in step 2 makes it testable
   without `ip route`.

Time: about 3 hours of execution in total, plus the real run.
