# No text over text on the site, and every run named apart

Date: 2026-09-24. Branch `master`, clean at 6a6d2c5 apart from two untracked `.new` test files
that are not this plan's.

Covers two TODO.md Now items, "Fix the labels that collide" and "Tell two runs apart when
they share a label", and the Next item on the phone map. It grew from five known collisions
to nine kinds once they were measured; see "What the measurement found".

## Goal

No chart on the site prints text over text at desktop or phone width, every run in a
comparison has a name of its own, and the map fills its box on a phone.

## Why

Charts on the site print text over text: a legend over a threshold label, three run names on
one point of the map, "best 91" over "median 95" on every report histogram. And the three
Leeds runs are all called `leeds_bt`, so a legend, a tile or a map caption naming them cannot
say which is which. On a phone, the map fills a third of its box and the rest is blank.

## What the measurement found

`notes/site-walk-2026-09-24/overlaps.mjs` loads six states of the live site (four explorer
comparisons, two report pages) at 1280 px and 390 px. It lists every pair of text boxes in
one chart that overlap by at least 3 × 3 px, counts names repeated within one legend, the
tiles or the timeline titles, and says how much of its box each map fills. The 3 px floor
was calibrated: a legend under a title grazes by 1.3 to 2.0 px with no ink touching, and the
real collisions measured 11 to 14 px. Live baseline, saved in `overlaps-before.txt` beside
the script: **127 overlapping pairs, 60 repeated names, maps filling 0.32 and 0.33 of their
box at 390 px** (0.97 and 0.94 at 1280 px).

The nine kinds, with the code that draws each:

| # | Where | What overlaps | Code |
|---|---|---|---|
| 1 | explorer, busy-delay chart | legend over the `warning` label, and `critical` at 390 px | `figures.js` `penaltyFigure`, `baseLayout` |
| 2 | explorer, histogram | run names at each outline's peak, on each other and on the legend | `figures.js` `histogramFigure` |
| 3 | explorer, map | run names at a shared end point; run names over "New York"; "you" over "you" at 390 px | `map.js` `mapFigure` |
| 4 | explorer, timelines, 390 px | "download" over "upload" | `figures.js` `phaseBands` |
| 5 | explorer, map, 390 px | map fills 0.32 of its box | `map.js` layout height, `app.js` |
| 6 | report, every histogram | "best", "median" and "p95" labels over the legend and over each other | `render_web.py` `_hist`, `_layout` |
| 7 | report, every timeline, 390 px | "download" over "upload" | `render_web.py` `_phase_bands` |
| 8 | report, map | "us-east" over "New York" | `render_map.py` end-point labels |
| 9 | report, map, 390 px | map fills 0.33 of its box | `render_web.py` map section |

Kinds 1, 2, 3, 6 and 8 are the five in TODO.md. Kinds 4, 5, 7 and 9 are new, found by the
measurement.

How the page names a run today: `dom.runName(row)` returns `row.label || row.id`, and every
surface calls it: legends (`figures.js`, `map.js`), tiles (`dom.js`), timeline titles and
the "would not load" sentence (`app.js`), and the map caption (`map.js` `datedRoutes`).

## Decisions for you

1. **Name format when labels clash.** Recommendation: only when two or more ticked runs share
   a label, add the shortest part of their UTC start that tells them apart. That's the time
   when they share a date (`leeds_bt 13:59`, `leeds_bt 15:15`), the date when they don't
   (`leeds_bt 30 Aug`), and both when neither alone does (`leeds_bt 30 Aug 13:59`). A run
   whose label clashes with nothing keeps its plain label, and a run with no label keeps its
   id, which is already unique. The picker table is unchanged: it shows every run, with its
   own date column. The cost of this rule is that a run's name in a comparison depends on
   what else is ticked.
2. **Drop the explorer histogram's run names at the peaks.** The dataviz rule for converging
   series: "When end-labels collide, don't stack them … fall back to the legend + tooltip."
   Every Leeds run peaks in the same bin, so they always collide. The legend stays whenever
   two or more runs are drawn.
3. **Label a shared map end point once**, with the target's name, instead of once per run;
   and write "you" once when origins sit on top of each other. Runs stay named by the legend
   and on hover.
4. **Charts get taller.** Legend and line labels each get their own row above the plot, so
   report histograms and timelines grow by about one row (16 px) each.

## Data first

- `displayName`: a field the explorer sets on its own in-memory copy of a ticked run. It is
  never written to a record, the log or the site's JSON. `dom.runName(row)` becomes
  `row.displayName || row.label || row.id`, so every existing caller picks it up with no
  change of its own. Checked: `displayName` is used nowhere today; records use `name` for
  targets, so that key is avoided.
- `labelSide`: per target, which side of its end point the map label goes, e.g.
  `{"us-east": "middle left"}` with `middle right` for the rest. Defined once in Python and
  emitted in the tokens block, per the project's rule that the site's JavaScript does not
  hold its own copies of Python's constants.

## Interfaces

- `dom.distinctNames(rows) -> Map(id -> name)`: pure; rows carry `id`, `label` and
  `timestamp`. Tested against hand-worked cases.
- `map.mapHeight(width) -> px`: pure; the map box height for a given width.
- Label rows: `baseLayout` (JS) and `_layout` (Python) gain a way to reserve a label row
  between the legend and the plot. The exact shape is settled in steps 4 and 8, and each is
  held by a test on the layout it returns.

## Steps

### Part A — measuring

**Step 1. A local copy of the site to test against**
- Needs: the container's site clone; `overlaps.mjs`; the build used for the contrast check
  earlier today, turned into `notes/site-walk-2026-09-24/build_local.py`
- Thinking: light — main session
- Check: `uv run python notes/site-walk-2026-09-24/build_local.py <dir>`, serve it, then
  `node notes/site-walk-2026-09-24/overlaps.mjs http://127.0.0.1:8765/` runs and prints its
  totals; that is the local baseline, recorded here
- Parallel: no — every later check uses it

### Part B — names

**Step 2. `distinctNames`, tested first**
- Needs: decision 1; `dom.js`; `tests/js/dom.test.js`
- Thinking: medium — main session
- Check: `node --test "tests/js/dom.test.js"`, with cases for three runs on one day, two on
  different days, two at the same time on different days, an unlabelled run beside a
  labelled one, and no clash at all
- Parallel: no — runs in the main session one step at a time, because every check shares
  the one local build and port. `dom.js` is touched by no other step

**Step 3. Wire the names into every surface**
- Needs: step 2; `app.js` (where the ticked runs are loaded, and `nameOf`); `dom.runName`
- Thinking: medium — main session
- Check: `node overlaps.mjs <local>` prints `repeated names in total: 0` (baseline 60), and
  `node --test "tests/js/*.test.js"` is green
- Parallel: no — `app.js` is touched again in step 7

### Part C — explorer charts

**Step 4. Label rows: the busy-delay thresholds and the timeline phase names**
- Needs: step 1; `figures.js` `baseLayout`, `penaltyFigure`, `phaseBands`;
  `tests/js/figures.test.js`
- Thinking: medium — main session
- Check: a node test that the legend sits above the label row, and "upload" a row below
  "download"; `overlaps.mjs` shows 0 pairs in "Extra delay…" and "Round trip … through
  each run" at both widths
- Parallel: no — `figures.js` again in step 5

**Step 5. Histogram without the peak labels**
- Needs: decision 2; `figures.js` `histogramFigure`
- Thinking: light — main session
- Check: a node test that the histogram's traces carry no text and the legend is shown for
  two or more runs; `overlaps.mjs` shows 0 pairs in "Where the round trips … fell"
- Parallel: no — same file as step 4

**Step 6. Map labels: a shared end point once, "you" once, us-east to the west**
- Needs: decision 3; `map.js` `mapFigure`; `labelSide` added to the tokens block in
  `render_web.py`; `tests/js/map.test.js`
- Thinking: medium — main session
- Check: node tests for one label at a shared end point, one "you" for collapsed origins,
  and the side taken from the tokens; `overlaps.mjs` shows 0 pairs in "The route to…" at
  both widths
- Parallel: no — `render_web.py` is also step 8's

**Step 7. The explorer map's height follows its width**
- Needs: `map.js` (`mapHeight`); `app.js` draws the map and redraws it on resize
- Thinking: medium — main session
- Check: a node test of `mapHeight` against hand-worked widths; `overlaps.mjs` shows the
  explorer map filling at least 0.8 of its box at 390 px and at least 0.9 at 1280 px
- Parallel: no — `app.js` was step 3's, `map.js` step 6's

### Part D — report pages

**Step 8. Report histograms and timelines: label rows**
- Needs: step 1; `render_web.py` `_layout`, `_hist`, `_phase_bands`; `tests/test_render_web.py`
- Thinking: medium — main session
- Check: `uv run pytest tests/test_render_web.py -q` with a test that "median" sits on a
  different row from "best" and "p95", "upload" below "download", and the legend above both;
  `overlaps.mjs` shows 0 pairs in the report's target sections at both widths
- Parallel: no — `render_web.py` again in step 9

**Step 9. Report map: us-east to the west, height from width**
- Needs: step 6's `labelSide`; `render_map.py` end-point labels; the map section and page
  script in `render_web.py`
- Thinking: medium — main session
- Check: `uv run pytest tests/test_render_map.py -q`; `overlaps.mjs` shows 0 pairs in
  "route map" and the report map filling at least 0.8 of its box at 390 px
- Parallel: no — `render_web.py` was step 8's

### Part E — close

**Step 10. Gate, look, publish, record**
- Needs: steps 1 to 9
- Thinking: medium — main session
- Check: `uv run ruff check .` and `uv run pytest tests -q` and
  `node --test "tests/js/*.test.js"` all green; on the local build, `overlaps.mjs` totals 0
  pairs and 0 repeated names, and `contrast.mjs` stays at or above 4.5:1; screenshots of
  every changed chart read at 1280 px light and dark and at 390 px; then republish 13:59 from
  the container and rerun `overlaps.mjs` on the live site; archive this plan, update TODO.md
- Parallel: no — last

## Success criteria

- [ ] `overlaps.mjs` on the local build: 0 overlapping pairs at 1280 and 390 px across all
      six page states (live baseline 127).
- [ ] 0 repeated names in any legend, tile row or timeline title set (baseline 60).
- [ ] Both maps fill at least 0.8 of their box at 390 px (baseline 0.32 and 0.33) and at
      least 0.9 at 1280 px (now 0.97 and 0.94).
- [ ] `contrast.mjs`: lowest text outside the map still at or above 4.5:1, both themes.
- [ ] Tests written before wiring for `distinctNames`, `mapHeight`, the label rows on both
      pages, the histogram without peak text, and the map's end-point labels.
- [ ] `uv run ruff check .` clean, `uv run pytest tests -q` green, node green, counts shown.
- [ ] After publishing: the live explorer states and the 13:59 report show 0 pairs. The
      other three report pages follow when the user republishes them from their terminal.

## Invariants

Each is a rule already set elsewhere; the source is named.

1. A run keeps its colour however the others are ticked or unticked (explorer plan; the
   `toggleRun` and slot tests stay green).
2. Two or more series always have a legend, so identity never rests on colour alone (the
   dataviz rule, and the comment above `showlegend` in `map.js`).
3. The site's JavaScript holds no copy of a Python constant: new constants go through the
   tokens block (CLAUDE.md, Structure).
4. Drawing only: no stored number, record or log line changes. `displayName` is never
   written anywhere. Publishing still never writes to the private log
   (`tests/test_publish.py`).
5. A figure nobody measured shows "—", never 0 (the em-dash rule, `notes/record-schema.md`).
6. Text contrast stays at or above 4.5:1 (433bff8, today).

## Out of scope

- The upload chart's zero tail (its TODO item wants a decision on what the chart claims).
- The São Paulo route leaving the top edge of the report map, and hop geolocation.
- The favicon, the tick box, the `schema` tag, the route-date grace period in the tokens
  block, `REFERENCE_POINTS` and `COLLAPSE_DEG` still hand-copied in `map.js` (TODO Later).
- The three republishes from the user's terminal; they will carry this work to those pages.

## Risks and rollback

- Label rows make charts taller; if a page reads worse for it, step 10's screenshots are
  where that shows. Rollback is `git revert` of the step's commit.
- Plotly places a legend in paper units, not pixels, so a label row depends on the figure's
  height. Each figure's height is fixed in code, and the rows are worked out from it; the
  overlap measurement at two widths is what proves it.
- Step 10 republishes 13:59 to the live site, re-tracing it again. Rollback: `git revert
  HEAD` in the container's site clone at
  `/home/filipejunqueira/containers/claude-home/.local/share/pingme/site`, then push.

About three to four hours of session work.
