# Put a date on every route, and say it on every map

Date: 2026-09-10. Branch `master`, clean at c2fd266 apart from TODO.md and the explorer
plan, both edited today and not yet committed.

Covers the first two items under TODO.md Now: the map on `leeds_bt_2026-08-30T13-59-15Z`,
and storing the trace date in the record.

## Why

Publishing `leeds_bt_2026-08-30T13-59-15Z` on 2026-09-10 re-traced its route, because the
record carries no trace, and the trace ran on the container's network that day rather than
the Leeds BT line the run measured eleven days earlier. The page drew that route with
nothing to say when it was measured. Its first hops read
192.168.1.1 → 192.168.0.1 → 10.53.38.165 where its sibling run from the same afternoon
reads 192.168.1.254 → 172.16.13.221 → 109.159.255.101, the real BT path.

A trace entry holds `hops`, `locations` and `error` and nothing else, so this is not a
mistake in one page: no page and no reader can tell a route measured with a run from one
measured weeks later somewhere else. A route traced later is still worth drawing. It is
only misleading when the page keeps quiet about it.

## What the code showed

- `render_map.trace_run` (line 23) builds every entry; it is the one place to stamp. It
  is called from two sites: `run.py:322` during a `--web`, `--publish` or `--trace` run,
  and `render_map.traces_for` (line 188) when a saved run has no trace and a report or
  map is built later. Both go through the same function, so one stamp covers both.
- **A trace is never taken during the measurement.** `run.py` calls `trace_run` after
  `analyse`, once the probes have stopped. So even the normal case has `traced_at` later
  than run start plus `duration_s`, by the minute or two the four traceroutes take. "With
  the run" therefore has to be a window, not an instant. See the threshold below.
- Three things draw a map and each needs the sentence: the report page
  (`render_web.build_report`, map section at line 659), the standalone map page
  (`render_map.build_map`, whose only text is the figure title with a `<sup>` subtitle at
  line 183), and the explorer's comparison map (`app.js:506 mapNoteText`, one paragraph
  under the map, rebuilt on every target change at lines 369 and 420).
- The explorer already has the full record per run (`run.timestamp`, `run.duration_s`,
  `run.traces[target]`), so the JavaScript twin needs nothing new from Python.
- `traces` is keyed by relay name and every reader iterates it as such, so the stamp must
  live inside each entry, not beside them: a top-level key would be read as a relay.
- Publishing never writes to the private log (`tests/test_publish.py:155` asserts it), so
  the 13:59 run will be re-traced again on republish. That is fine now: the page will say
  when. Writing the publish-time trace back is a separate decision, out of scope below.
- The three other published runs carry traces made with the run but no stamp, because
  the field did not exist. Their pages will say the date was not recorded. That is true,
  and it is the only honest reading of a published JSON copy, which cannot be told apart
  from the 13:59 case.
- `tests/fixtures/run.json` has no `traces`, so report tests build a trace by hand
  (`tests/test_render_web.py:94`); the new tests do the same.

## Data first

One new field, on every entry of `traces`:

| field | type | meaning |
|---|---|---|
| `traced_at` | string | when the route was traced, ISO 8601 with a UTC offset, the same value on every entry of one `trace_run` call. Absent on traces made before schema 2 |

`SCHEMA` goes 1 → 2. `notes/record-schema.md` gains the row and a version-history entry.
Nothing is renamed or given a new meaning.

## Interfaces

One pure function, written twice, fed by one shared cases file so the two cannot drift.

- Python: `render_map.trace_note(run_started: str, duration_s: float | None,
  traced_at: str | None) -> str | None`.
- JavaScript: `map.js` exports `traceNote(runStarted, durationS, tracedAt)` returning a
  string or `null`.
- `tests/fixtures/trace-note-cases.json`: a list of `{run_started, duration_s, traced_at,
  note}` objects, hand-written, every expected sentence a literal. The pytest and the node
  test both read it and assert every case. Adding a case to the file tests both sides.

The three cases the function decides:

1. `traced_at` absent → `"When this route was traced was not recorded."`
2. traced within the window → `None`. The normal case needs no words.
3. traced after the window → `"Traced on 2026-09-10, 11 days after this run, so it may
   not be the path the run took."` The gap is a whole number in the largest unit that is
   at least 1: days, else hours, else minutes. Never "recently" or "later".

**The window, a human threshold to approve:** `traced_at − run_started ≤ duration_s +
15 minutes`. Four traceroutes take one to two minutes on this machine; a 10-minute
`--longer` run plus tracing still fits. Anything past that was a separate act.

## Wiring

- `trace_run`: take `stamp = dt.datetime.now(dt.UTC).isoformat()` once before the loop;
  put `"traced_at": stamp` in every entry.
- Report page: under the map, one `<p class="note">` holding the distinct notes across
  the run's entries, in relay order, joined by a space. In practice one sentence or none.
- Standalone map page: the same text appended to the title's `<sup>` line in `build_map`.
- Explorer: `mapNoteText` appends, per drawn run, the run's name and its note for the
  chosen target, so a comparison of a fresh run and a re-traced one names which is which.

## Invariants

Conditions the change must never break, each with the check that holds it:

1. A trace made with the run adds no text anywhere: a report built from a record whose
   `traced_at` sits inside the window is byte-identical to the report before this change.
   Test in `tests/test_render_web.py`.
2. An absent `traced_at` never crashes a renderer and never renders as silence, `0` or a
   blank: it renders the "not recorded" sentence. Test on the report page and in
   `tests/js/map.test.js`. Same rule as the em dash: a figure nobody recorded is never
   shown as good news.
3. Every expected sentence is a literal in the cases file. No test computes its own
   expectation.
4. Python and JavaScript agree on every case in the file. Both test files read it.
5. Publishing still never writes to the private log. The existing assertion at
   `tests/test_publish.py:155` stays and must stay green.

## Out of scope

- Writing a publish-time trace back into the private log so a run stops being re-traced
  on every publish. It changes the log record of a run already measured; a separate
  decision, to be added to TODO.md Later when this plan closes.
- The two Leeds index rows still reading 100.0 %; they need a publish from the user's
  terminal, not code. Already in TODO.md Now.
- The colliding chart labels, the duplicate `leeds_bt` names, the favicon. In TODO.md.

## Risks and rollback

- Step 5 republishes the 13:59 run, which writes to the live site. Approving this plan is
  the yes for that one publish. Rollback: `git revert HEAD` in the site clone at
  `~/.local/share/pingme/site` (container copy) and push.
- Python edits: since 3ac048c `pyproject.toml` excludes this project from `ruff format`,
  so the hooks no longer rewrite a file whichever tool edits it (CLAUDE.md corrections log).
- The 13:59 run's fresh trace will again be the container's route, not Leeds. The page
  will now say so, which is the point.

## Success criteria

Named together in one message when they are all true, per CLAUDE.md:

- [ ] `uv run ruff check .` clean.
- [ ] `uv run pytest` green, count shown, node tests included.
- [ ] `trace_note` tested against the cases file before it is wired in; the file covers
      all three cases, the window boundary on both sides, and each unit of gap.
- [ ] `traceNote` tested against the same file; a case added to the file fails both tests
      until both sides handle it.
- [ ] Invariant 1 held by a byte-identity test; invariant 2 by a test on each side.
- [ ] A real run on this machine, output shown: `uv run pingme --quick --web` whose map
      carries no sentence, and the republished 13:59 run whose page says the date and gap.
- [ ] The live page for the 13:59 run, read in the headless browser, shows the sentence,
      and the explorer with that run ticked shows it under the map with the run's name.
- [ ] `notes/record-schema.md` describes `traced_at`; `SCHEMA` is 2; the fixture run in
      `tests/fixtures/run.json` is left as it is (it has no traces and stays a schema-1
      record on purpose, so old-record paths keep a test).

## Steps

- [x] 1. `tests/fixtures/trace-note-cases.json`, then `trace_note` in `render_map.py` and
        its pytest. Hand-computed, wired to nothing yet. 18 cases; `uv run pytest
        tests/test_render_map.py` 20 passed. The gap is measured from the end of the run,
        the same point the window ends at, so the two can never disagree about a trace.
- [x] 2. `traceNote` in `map.js` and its node test reading the same file. 163 node tests.
        Discovery: a stamp with no offset means UTC to Python but the reader's own local
        time to `new Date`, so `map.js` names the zone before parsing. The first check
        written for this passed with that guard removed, because it compared one parse
        against another and both sides shifted together. Replaced by two cases either side
        of midnight UTC, plus `tests/test_explorer_js.py` running the node suite under
        UTC+14 and UTC-11. Removing the guard now fails the gate; checked both ways.
- [x] 3. `trace_run` stamps `traced_at`; `SCHEMA = 2`; `notes/record-schema.md`.
        The code landed in the 2026-09-13 wip commit e9d375b unticked; ticked 2026-09-22
        once `test_trace_run_stamps_every_route_with_one_moment` held it (network stubbed:
        one stamp across every relay entry, UTC offset written, local hops still skipped).
- [x] 4. Wire the report page, the standalone map page and the explorer caption, with the
        invariant tests. Wiring also from e9d375b. Tests added 2026-09-22 in
        `tests/test_render_web.py` (invariant 1 by byte identity, invariant 2, the late
        sentence, the map page's subtitle) and a `datedRoutes` node test. Invariant 1 was
        also checked once against the code as it stood at c2fd266: the same fixture and a
        with-the-run trace built a 4,353,693-byte report, identical under `cmp`. Gate:
        ruff clean, pytest 130 passed, node 164 passed. `mapNoteText` in `app.js` has no
        test of its own; the live explorer read in step 5 is its check. A review pass
        found the report page's `.note` had no style (only the explorer's stylesheet had
        the rule); fixed with a test in 78e7a8f. That rule is unconditional, so reports are no
        longer byte-identical to c2fd266; invariant 1 now means identical to the same code with
        the note switched off, which the committed test holds.
- [ ] 5. Gate; a real `--quick --web` run; republish the 13:59 run; read the live page;
        archive this plan and write TODO.md.

About two hours of session work. Steps 1 and 2 can run in parallel with step 3: they touch
different files (`render_map.py` is shared by 1 and 3, so 3 waits for 1). Step 4 waits
for all of them.
