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
comparisons, two report pages) at 1280 px and 390 px. It does four things:
- lists every pair of text boxes in one chart that overlap by at least 3 × 3 px;
- counts names repeated within one legend, the run tiles, the timeline titles, the
  comparison table's column heads, or the map caption's route-date sentences;
- says how much of its box each map fills;
- fails, rather than reporting a clean 0, when a page did not draw (one load did, while the
  baseline was being taken).

The 3 px floor was calibrated. A legend under a title grazes by 1.3 to 2.0 px with no ink
touching, and the real collisions measured 11 to 14 px. The floor also drops one pair of
axis tick labels at 390 px that a looser rule counted. Live baseline, saved in
`overlaps-before.txt` beside the script: **127 overlapping pairs, 80 repeated names, maps
filling 0.32 and 0.33 of their box at 390 px** (0.97 and 0.94 at 1280 px).

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

How the page names a run today: `dom.runName(row)` returns `row.label || row.id`. It is
called for:
- the legends (`figures.js`, `map.js`);
- the tiles (`dom.js`);
- the timeline titles and the "would not load" sentence (`app.js`, through `nameOf`);
- the map caption (`map.js` `datedRoutes`).

The comparison table's column heads use a second function, `dom.shortName(row)`, which
returns `label || id.slice(0, 10)` and so would miss a fix made only in `runName`.

## Decisions for you

Approved 2026-09-24 as recommended: decisions 1 to 3 as written, and decision 4 serial.

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
4. **Serial, or two branches at once.** Once step 11 has put `labelSide` in place, the
   JavaScript steps (2 to 7) and the Python steps (8 and 9) touch no file in common. They
   could run as two agents, one in a git worktree, each serving its own local build on its
   own port. That would save about an hour of waiting, at the cost of two agents that
   write files. My default is serial in this session: each step is look, adjust and look
   again, which works better with one pair of eyes on one build. Say yes if you want the
   two branches instead.

## Data first

- `displayName`: a field the explorer sets on its own in-memory copy of a ticked run. It is
  never written to a record, the log or the site's JSON. `dom.runName(row)` becomes
  `row.displayName || row.label || row.id` and `dom.shortName(row)` reads `displayName`
  first too, so every existing caller picks it up with no change of its own. Checked:
  `displayName` is used nowhere today; records use `name` for targets, so that key is
  avoided.
- `labelSide`: per target, which side of its end point the map label goes, e.g.
  `{"us-east": "middle left"}` with `middle right` for the rest. Defined once in
  `render_map.py`, used there by the report map, and emitted in the tokens block for the
  explorer, per the project's rule that the site's JavaScript holds no copies of Python's
  constants.

## Interfaces

- `dom.distinctNames(rows) -> Map(id -> name)`: pure; rows carry `id`, `label` and
  `timestamp`. Tested against hand-worked cases.
- `map.mapHeight(width) -> px`: pure; the map box height for a given width.
- Label rows: `baseLayout` (JS) and `_layout` (Python) gain a way to reserve a label row
  between the legend and the plot. The exact shape is settled in steps 4 and 8, and each is
  held by a test on the layout it returns.

## Steps

### Part A — measuring

**Step 1. A local copy of the site to test against — DONE**
- Done: `build_local.py` rebuilt all four report pages and the index into the scratchpad;
  `overlaps.mjs` on it gave 127 pairs and 80 repeated names, the live baseline exactly.
  `ONLY=<words>` now limits a run to the states named, for the quick looks between steps.
- Needs: the container's site clone; `overlaps.mjs`; the build used for the contrast check
  earlier today, turned into `notes/site-walk-2026-09-24/build_local.py`, which copies the
  clone without its `.git`
- Thinking: light — main session
- Check: `uv run python notes/site-walk-2026-09-24/build_local.py <dir>`, serve it, then
  `node notes/site-walk-2026-09-24/overlaps.mjs http://127.0.0.1:8765/` runs and prints its
  totals; that is the local baseline, recorded here
- Parallel: no — every later check uses it

**Step 11. `labelSide`, in Python and in the tokens block — DONE**
- Done: `render_map.LABEL_SIDE`, all four relays named, us-east `middle left`; emitted as
  `labelSide`. The tokens test lives in `tests/test_publish.py`, not the file named below;
  it now checks the key and that it is the Python table. 13 passed, ruff clean.
- Needs: `render_map.py` (the constant); `render_web.py` `explorer_tokens`;
  `tests/test_render_web.py`
- Thinking: light — main session
- Check: `uv run pytest tests/test_render_web.py -q` with a test that the tokens block
  carries `labelSide` and that it is the same object `render_map.py` uses
- Parallel: no — both branches read it, so it lands before either starts

### Part B — names

**Step 2. `distinctNames`, tested first — DONE**
- Done: `dom.distinctNames` with six hand-worked cases, written and failing before the
  function existed. One case beyond the plan's list: two runs in one minute beside a third
  on another day get the day and the seconds. `node --test "tests/js/*.test.js"`: 170 passed.
- Needs: decision 1; `dom.js`; `tests/js/dom.test.js`
- Thinking: medium — main session
- Check: `node --test "tests/js/dom.test.js"`, with cases for three runs on one day, two on
  different days, two at the same time on different days, an unlabelled run beside a
  labelled one, and no clash at all
- Parallel: yes, beside steps 8 and 9 — `dom.js` and its test are touched by no Python
  step. Runs as a branch only on your yes (decision 4)

**Step 3. Wire the names into every surface — DONE**
- Done: `rebuildBody` names the ticked runs from their index rows before any record arrives
  and sets `displayName` on the page's copy; `nameOf` reads the same names. Discovery:
  `figures.js` and `map.js` each keep a private copy of `runName` (the modules import only
  `stats.js`), so both copies got the same rule rather than a new import. Local build: 0
  repeated names (80 before). `failed-load.mjs` with 15:15's JSON blocked: "The numbers
  behind leeds_bt 15:15 would not load", beside tiles "leeds_bt 13:59" and "leeds_bt 15:32".
  Overlaps rose 56 to 63 on the explorer states, longer names colliding more; steps 4 to 7.
  Node: 171 passed.
- Needs: step 2; `app.js` (where the ticked runs are loaded, and `nameOf`); `dom.runName`
  and `dom.shortName`; `map.js` `datedRoutes`
- Thinking: medium — main session
- Check: `node overlaps.mjs <local>` prints `repeated names in total: 0` (baseline 80); a
  node test that `datedRoutes` gives two runs sharing a label two different names; one
  browser load with a run's JSON blocked (`page.route`) shows the "would not load"
  sentence with that run's distinct name; `node --test "tests/js/*.test.js"` green
- Parallel: yes, beside steps 8 and 9 — JavaScript files only. Inside the JavaScript branch
  it waits on step 2, and `app.js` is touched again in step 7

### Part C — explorer charts

**Step 4. Label rows: the busy-delay thresholds and the timeline phase names**
- Needs: step 1; `figures.js` `baseLayout`, `penaltyFigure`, `phaseBands`;
  `tests/js/figures.test.js`
- Thinking: medium — main session
- Check: a node test that the legend sits above the label row, and "upload" a row below
  "download"; `overlaps.mjs` shows 0 pairs in "Extra delay…" and "Round trip … through
  each run" at both widths
- Parallel: yes, beside steps 8 and 9 — JavaScript files only; inside its branch,
  `figures.js` is step 5's next

**Step 5. Histogram without the peak labels**
- Needs: decision 2; `figures.js` `histogramFigure`
- Thinking: light — main session
- Check: a node test that the histogram's traces carry no text and the legend is shown for
  two or more runs; `overlaps.mjs` shows 0 pairs in "Where the round trips … fell"
- Parallel: yes, beside steps 8 and 9 — JavaScript only; after step 4, same file

**Step 6. Map labels: a shared end point once, "you" once, us-east to the west**
- Needs: decision 3; step 11's `labelSide` in the tokens; `map.js` `mapFigure`, whose
  comment "so identity never rests on colour alone" is rewritten to say the legend now
  does that; `tests/js/map.test.js`
- Thinking: medium — main session
- Check: node tests for one label at a shared end point, one "you" for collapsed origins,
  and the side taken from the tokens; `overlaps.mjs` shows 0 pairs in "The route to…" at
  both widths
- Parallel: yes, beside steps 8 and 9 — JavaScript only, since step 11 already wrote the
  Python half

**Step 7. The explorer map's height follows its width**
- Needs: `map.js` (`mapHeight`); `app.js` draws the map and redraws it on resize
- Thinking: medium — main session
- Check: a node test of `mapHeight` against hand-worked widths; `overlaps.mjs` shows the
  explorer map filling at least 0.8 of its box at 390 px and at least 0.9 at 1280 px
- Parallel: yes, beside steps 8 and 9 — JavaScript only; after step 3 (`app.js`) and step 6
  (`map.js`)

### Part D — report pages

**Step 8. Report histograms and timelines: label rows**
- Needs: step 1; `render_web.py` `_layout`, `_hist`, `_phase_bands`; `tests/test_render_web.py`
- Thinking: medium — main session
- Check: `uv run pytest tests/test_render_web.py -q` with a test that "median" sits on a
  different row from "best" and "p95", "upload" below "download", and the legend above both;
  `overlaps.mjs` shows 0 pairs in the report's target sections at both widths
- Parallel: yes, beside steps 2 to 7 — Python files only, after step 11; inside its branch,
  `render_web.py` is step 9's next

**Step 9. Report map: us-east to the west, height from width**
- Needs: step 11's `labelSide`; `render_map.py` end-point labels; the map section and page
  script in `render_web.py`
- Thinking: medium — main session
- Check: `uv run pytest tests/test_render_map.py -q`; `overlaps.mjs` shows 0 pairs in
  "route map" and the report map filling at least 0.8 of its box at 390 px
- Parallel: yes, beside steps 2 to 7 — Python only; after step 8, same file

### Part E — close

**Step 10. Gate, look, publish, record**
- Needs: steps 1 to 9 and 11
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
- [ ] 0 repeated names in any legend, the tiles, the timeline titles, the comparison table's
      heads or the map caption (baseline 80); the "would not load" sentence names a blocked
      run by its distinct name.
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

- Charts get taller. The legend and the line labels each get their own row above the plot,
  so report histograms and timelines grow by about one row (16 px) each. If a page reads
  worse for it, step 10's screenshots are where that shows. Rollback is `git revert` of the
  step's commit.
- The explorer map's legend sits inside the map area (`x: 0.01, y: 0.99`). At 390 px it
  lands in today's blank space above the map; once step 7 makes the map fill its box, three
  legend entries will sit over North America. That is text over land, not text over text,
  so `overlaps.mjs` will not see it. Step 10's phone screenshot is the check, and moving
  the legend out of the map at narrow widths is the likely fix.
- Plotly places a legend in paper units, not pixels, so a label row depends on the figure's
  height. Each figure's height is fixed in code, and the rows are worked out from it; the
  overlap measurement at two widths is what proves it.
- Step 10 republishes 13:59 to the live site, re-tracing it again. Rollback: `git revert
  HEAD` in the container's site clone at
  `/home/filipejunqueira/containers/claude-home/.local/share/pingme/site`, then push.

About three to four hours of session work.
