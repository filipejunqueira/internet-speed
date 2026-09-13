# pingme: one page to read any run and compare up to three

Date: 2026-09-03. Branch `master`, working tree clean after c6c9bd8.
Status: **done, with one thing left to decide.** Steps 0 to 6 are done. Step 5 was
walked on the live site on 2026-09-10 with a headless browser, and the run that had
no numbers was published from the container the same day. What the walk found, and
what the publish turned up, are under that step. `uv run ruff check .` clean and
`uv run pytest` green, 103 tests, on 2026-09-10.
Commits 7fdec1c (this plan), 52de17a (the feature), 1e66806 (the review round).
Mockup: https://claude.ai/code/artifact/fe5fdc5f-b0ca-44ba-a503-9f36f3822dec
(four screens: comparing two runs, one run ticked, nothing ticked, and a rejected
"one column per run" alternative, drawn from two real runs in the log).

## Context

Today the site publishes one finished HTML page per run and a static table that links
to them. The numbers that drew each page are thrown away after rendering, so two runs
can only be compared by opening two tabs. The user wants one page on GitHub Pages that
lists every published run, shows any one of them in full, and shows two or three of
them together, same chart, one colour per run, so a home Wi-Fi run and a wired run at a
friend's house can be read against each other in seconds, route map included.

The user's own words on what "compare" means: not several servers on one graph, but
the same measurement from different runs on one graph.

## Decisions, with the evidence behind them

**Colour means run, never target.** In the comparison view every coloured mark is a run.
Targets are text: axis labels, a selector, table rows. The first ticked run takes slot 1
(blue), the next slot 2 (orange), the next slot 3 (aqua). A run keeps its colour until
it is unticked; unticking one never repaints the others (dataviz: colour follows the
entity, not its rank). The run colours are the same three hues the run pages use for
London, Madrid and US-East. That is acceptable because the two views are never on
screen together, and the run tiles at the top of the comparison teach the mapping.

**Three runs at most.** The palette validator (`dataviz/scripts/validate_palette.js`)
passes four slots side by side in both modes but fails four on the map, where any two
routes can touch: yellow against orange measures 13.7, under the 15 floor for
full-colour vision. Three slots pass every check in both modes. The picker refuses a
fourth tick and says why in a sentence.

**Overlay only where the axes agree.** The histogram overlays: two distributions on one
axis is what a histogram is for, drawn as step outlines with a 10 % wash so neither run
hides the other, on bins shared across the ticked runs. Round trip over time does not
overlay: runs differ in length (the log holds 30 s, 60 s and 600 s runs) and the speed
test starts at a different second in each, so the panels sit side by side on one shared
vertical scale. Phase bands in those panels are grey, not orange and aqua, because the
run colour is the only identity channel there.

**One target selector scopes the drill-down.** Above the table, the histogram, the
timelines and the map sits one segmented control (router, London, Madrid, US-East, São
Paulo). Everything below follows it. The two overview charts above it show every target
at once: median with a p95 mark, and the under-load penalty with the warning and
critical lines drawn in. Default target: São Paulo when present, else the first relay.

**One ticked run shows today's run page.** The detail view is the existing
`runs/<id>.html` in a same-origin iframe sized to its content. That is the whole
detail view: nothing is reimplemented, so it cannot drift from the page the user
already knows, and the tiles, hop table, map and footnote come for free.

**The comparison charts are written once, in JavaScript.** There is no way round this
for an interactive page on static hosting. The Python side stays the single source of
truth for colours, target order and thresholds by emitting them into the page as a
JSON block; the JavaScript reads that block and never hard-codes a hex.

**The URL carries the state.** `?runs=<id>,<id>&target=sao-paulo`, so a comparison can
be bookmarked or sent to someone.

**Never counted and counted zero stay different.** A run published before bursts were
counted shows "—" for burst, not 0, in the picker, the tiles and the table.

## What gets published, and its size

Per run, next to the existing page: `runs/<id>.json`, the redacted record as
`publish()` already builds it for the page, samples and traces included. Measured on the
log: a 60 s run is 59 KB (15 KB as GitHub serves it, compressed); the 600 s run is
458 KB (110 KB). The page fetches only the runs that are ticked.

`runs/index.json` keeps its rows and gains `duration_s` and `traced` (whether a map is
available). `assets/explorer.js` is written on every publish, like the page. `index.html`
becomes the explorer shell: the report's own CSS, the tokens block, one `<main>`, the
plotly script tag, and the explorer script tag.

## Success criteria

All named in one message at the end, per CLAUDE.md:

- `uv run ruff check .` clean; `uv run pytest` green, including the JavaScript tests it
  runs through `node --test` (skipped with a printed reason when node is missing).
- The live site, opened by the user (the container has no browser): the table lists
  every published run newest first, sortable by column; ticking one run shows that
  run's page below the table; ticking a second switches to the comparison; a fourth
  tick is refused with a message; each run keeps its colour on the tiles, both
  overview charts, the table header, the histogram, its timeline panel and the map;
  reloading the URL restores the same ticks and target.
- Runs published before bursts were counted show "—" for burst, not 0.
- The two runs in the mockup, republished, read the same numbers on the live page as
  on the mockup: Leeds 44.3/63.4 Mbit/s with a 236 ms São Paulo penalty against
  Santander 175.1/224.2 with 83.8 ms.
- The palette validator output for the three run slots is recorded in the plan
  (done, above) and the page never generates a fourth hue.

## Steps

Each step is one commit. Python edits go through the shell (the ruff format hook would
rewrite the file, see CLAUDE.md). After a multi-part edit, grep for each change.

### [x] Step 0: approval and bookkeeping (5 min)

- This file approved by the user. TODO.md Now points here.

### [x] Step 1: publish the data and the shell (45 min)

Files: `src/pingme/publish.py`, `src/pingme/render_web.py`, new
`src/pingme/explorer.js`, `tests/test_publish.py`.

- `publish()` writes `runs/<id>.json` (`json.dumps` of the redacted record, compact)
  beside the page, and copies `src/pingme/explorer.js` to `assets/explorer.js` on every
  publish (`importlib.resources` so the installed package finds it).
- `store.summary_row` gains `duration_s` and `traced` (`"traces" in run`).
- `render_web.explorer_tokens()` returns a dict: `LIGHT`, `DARK`, `STATUS`, the three
  run slots for each mode, `TARGET_ORDER`, the four thresholds, `INTERVAL_S`.
  `publish.build_index(rows)` becomes the explorer shell: `_css()` plus the explorer
  CSS, `<script id="pingme-tokens" type="application/json">`, an empty `<main>`, the
  plotly tag pointing at `PLOTLY_ASSET`, then `assets/explorer.js`. It no longer renders
  the table in Python; the script does, from `runs/index.json`.
- Tests: `publish()` into a temp site dir (the existing test does this) writes the
  `.json`, the `.js` and an `index.html` that contains the tokens block, the plotly tag
  and the explorer tag and no inline plotly; `explorer_tokens()` round-trips through
  JSON and carries exactly three run slots per mode.

### [x] Step 2: the picker and the detail view, in JavaScript (1 h)

File: `src/pingme/explorer.js`, plus `tests/explorer.test.js` and a pytest wrapper.

Structure the file so the pure parts are plain functions on one object that the test
file can import (`export` at the bottom guarded by `typeof module`), and the DOM code
runs only in a browser.

- Load `runs/index.json`. Render the table: tick, swatch, run, date, ISP, city, medium,
  duration, down/up, worst loss, worst burst, São Paulo p95. Click a header to sort;
  default newest first. Runs are named by label, else id.
- Ticks: `assignSlot(state, id)` gives the lowest free slot; `release(state, id)` frees
  it and leaves the others alone; the fourth tick is refused with the sentence
  "Three runs at most: a fourth colour cannot be told apart on the map."
- URL: `readState(search)` and `writeState(state)`; `history.replaceState` on every
  change; the page restores from the URL on load.
- One tick: an iframe of `runs/<id>.html` below the table, height set from
  `contentDocument.documentElement.scrollHeight` on load and on resize. The frame is
  same-origin, so this works on GitHub Pages and on a local file. The table stays
  above it.
- Zero ticks: the hint card from the mockup.
- Tests (node): slot assignment and release across tick, tick, untick, tick; the
  refusal at four; URL state round trip with and without a target; sort by each
  column with "—" values last.
- The pytest wrapper: `tests/test_explorer_js.py` runs `node --test tests/` with
  `subprocess`, fails on a non-zero exit, and `pytest.skip`s with the reason when
  `shutil.which("node")` is None. CLAUDE.md gets one line saying the JS tests need
  node.

### [x] Step 3: the comparison view (2 h)

File: `src/pingme/explorer.js`, `tests/explorer.test.js`.

Fetch each ticked run's JSON (cache in memory; hold the previous render at reduced
opacity while fetching, never a blank). Then, top to bottom as in the mockup:

- Run tiles: swatch and name, date, ISP, city, medium, duration; download and upload;
  probes lost across all non-silent targets with the loss badge (zero is the only
  green). These are the legend for every chart below.
- Overview pair (plotly, `barmode: "group"`, bars 14 px, `cornerradius: 4`):
  median per target with the p95 as a short vertical marker in the same colour; the
  under-load penalty per target with hairlines at 50 and 200 labelled warning and
  critical. Targets on the y axis in `TARGET_ORDER`, silent targets omitted.
- The target selector. Default São Paulo.
- The table for the selected target: loss %, probes lost, longest burst, best, median,
  p95, p99, jitter, under-load penalty, then download, upload, local overhead. The
  better value per row in bold (lower wins, except throughput). "—" where a run lacks
  the figure.
- Histogram: `sharedBins(runs, target, n=30)` from the union of the runs' minimum to
  the largest p99; one `scatter` per run with `line.shape: "hv"`, 2 px, `fill:
  "tozeroy"` at 10 % opacity; direct label at each run's peak, legend from the tiles.
- Timelines: one plotly div per run in a two-column grid, `yaxis.range` shared and
  computed once from the union; grey phase bands with labels; lost probes as red
  crosses on the floor; the run name and date as the panel title with its swatch.
- Dark mode: the same restyle-on-theme-change script the run pages use, driving from
  the tokens block, so the run slots swap to their dark steps.
- Tests (node): `sharedBins` on hand-made samples (edges, counts, a value at the top
  edge lands in the last bin); `diffRows` marks the lower value best for latency and
  the higher for throughput, and never marks a lone value; `penalty` is busy p95 minus
  idle p95 or null; `sharedYRange` covers every run's p99 with 5 % slack.

### [x] Step 4: the map (45 min)

File: `src/pingme/explorer.js`.

- For the selected target, one `scattergeo` line per run in its colour, dashed on a
  segment that crosses hidden hops (the same rule as `render_map._segments`), a marker
  at every placed hop with the city and delay on hover, the run name as a direct label
  at the far end, and a star at each run's origin. Reference cable landing points as
  today. `fitbounds: "locations"`.
- A run without a trace gets no line and a one-line note under the map naming it.
- No new test beyond a node test for `routePoints(trace)` (collapse same-place hops,
  count hidden hops between drawn points), which mirrors the Python function.

### [x] Step 5: publish, backfill, look (45 min)

- From the container: `uv run pingme publish leeds_bt_2026-08-30T13-59` republishes the
  run the container made, which writes the new `index.html`, `explorer.js` and that
  run's `.json`.
- The user, from their own terminal: `pingme publish leeds_bt_2026-08-30T15-32` and
  `pingme publish 2026-09-03T13-14` so both mockup runs carry their data.
- The user opens https://filipejunqueira.github.io/internet-speed-reports/ and walks
  the success criteria above. Whatever reads wrong gets fixed in this step, with the
  observation written into the plan.

#### What the walk found (2026-09-10)

Walked with a headless Chromium driving the live site, not by hand: every state was
reached by clicking, and the colours were read out of plotly's own trace objects rather
than judged from a picture. The four published runs were the whole sample, and three of
them are the same Leeds line, so nothing here tests a big list.

Passed, each with what was actually observed:

- The table lists all four runs newest first and sorts by every column that carries a
  key. Four columns do not change order when clicked: `isp` and `medium` because all
  four rows hold the same value, `duration_s` and `worst_burst_probes` because one row
  has a figure and three have none. That is `sortRows` doing what its comment says: a
  missing figure sorts last in both directions and equal rows keep the order they came
  in. Correct, not a defect.
- One tick shows that run's own page in a frame, `data-run` matching, sized to 3,896 px
  so there is no scrollbar inside a scrollbar.
- A second tick switches to the comparison; a third adds the green slot; a fourth is
  refused with "3 runs at most: a fourth colour cannot be told apart on the map."
- Colour follows the run everywhere: `#2a78d6`, `#eb6834`, `#1baf7a` read straight off
  the traces of `fig-overview`, `fig-penalty`, `fig-histogram`, each `fig-timeline-N`
  and `fig-map`, and off the swatch in each table row and tile.
- Unticking the middle of three runs left the other two on their original hues, and the
  next run ticked took the freed orange slot. No repaint.
- Only three run hues ever appear. The fourth colour on the page, `#898781`, is the
  muted grey the tokens block gives the cable landing points and the origin marker.
- The URL carries both `runs=` and `target=`, and reloading it restores the same three
  ticks and the same target. Changing the target took about 2 seconds each time.
- A figure nobody measured is U+2014 exactly, checked by code point, in the table's
  burst column and in the "longest burst" row of the São Paulo table.
- The mockup numbers hold on the live page: Leeds 44.3/63.4 Mbit/s with a 236.4 ms São
  Paulo penalty, Santander 175.1/224.2 with 83.8 ms.

Five things read wrong. None of them break the page; all five are written into TODO.md.

1. **`runs/leeds_bt_2026-08-30T13-59-15Z.json` is 404**, so that run is listed but has
   no numbers on the site. Ticking it alone still works, because that view is the
   published HTML in a frame; in a comparison the page says "The numbers behind leeds_bt
   would not load, so that run is missing from the charts below. Its own report page
   still works." and draws the rest. The handling is right; the gap is real. Cause: that
   run exists only in the container's log, and `backfill_run_data` can only write a run
   its own machine still holds.

2. **The table says a Leeds run lost 100.0 % while its tile says "6 probes lost,
   warning"**, on the same screen. Both are honest about their own source. The table
   column reads `worst_loss_pct` out of the row in `runs/index.json`, and those three
   rows were written on 2026-08-30, when the silent ISP hop still counted as total loss.
   `publish` replaces only the row of the run being published, so an old row keeps its
   old numbers for ever. The same cause leaves the duration column showing an em dash
   for runs whose record does carry 60 s.

3. **Two runs share the label `leeds_bt`**, so every legend, every tile heading, the
   comparison table header and the "would not load" sentence print the same name twice.
   Colour separates them; the words do not.

4. **Labels collide on three charts.** On "Extra delay while the line is busy" the
   `warning` threshold text sits underneath the first legend entry. The histogram prints
   all three run names stacked in its top-left corner, over the plot and over each
   other, and repeats what the legend already says. On the map all three run names print
   on the same point at São Paulo, and "You" prints twice over the UK.

5. **`favicon.ico` is 404**, one console error on every page load. Cosmetic.

One thing worth writing down that is not a defect in the page. The three Leeds records
published on 2026-08-30 carry the old per-phase accounting: for São Paulo, `idle.sent`
299 and `busy.sent` 102 against `all.sent` 300, so the idle span counts the busy probes
and `idle.loss_pct` reads 34.11 %. The under-load penalty was checked against this and is
sound: `idle.received` 197 plus `busy.received` 102 comes to `all.received` 299, so the
replies were split between the phases correctly and only the sent counts overlap. The
percentiles either phase reports, and the 236.4 ms penalty drawn from them, are therefore
real. The explorer never shows a per-phase loss figure either: `stats.js` reads loss out
of `entry.all` alone. So the stale figure is invisible on the site but sits in
`runs/<id>.json` for anyone reading the published record directly. Those records carry no
`schema` key, which `notes/record-schema.md` already defines as "before versioning", so a
reader outside the project is warned. Republishing cannot mend it, because the record in
the private log holds the same old numbers; `pingme reanalyse`, in TODO.md Later, is what
would.

#### What the publish turned up (2026-09-10)

`uv run pingme publish leeds_bt_2026-08-30T13-59-15Z` from the container, with the user's
yes, after fast-forwarding the container's site clone five commits. It fixed finding 1:
the 404 has gone, all four runs now compare with no "would not load" sentence, and the
run's own index row was rewritten by today's code, from 100.0 % worst loss and no
duration to 0.7 % and 30 s. Nothing private reached the site: `backfill_run_data` walks
the index rows, and the container's own runs are not on it.

It also did something the command line does not warn about. The record carries no route
trace, so publishing traced the route again — on the container's network on 2026-09-10,
not the Leeds BT line the run measured on 2026-08-30 — and put that route on the page
with nothing to say when it was measured. The run's first hops now read
192.168.1.1 → 192.168.0.1 → 10.53.38.165 where its sibling from the same afternoon reads
192.168.1.254 → 172.16.13.221 → 109.159.255.101, which is the real BT path. The private
log was not touched: the fresh trace went only into the published copy.

The deeper cause is that a trace carries no date. `traces.<target>` holds `hops`,
`locations` and `error`, and nothing else, so no page and no reader can tell a route
measured during the run from one measured weeks later somewhere else. Both the immediate
choice and the fix are in TODO.md Now.

Side effect worth naming: rewriting one row made the table less consistent, not more. The
three Leeds runs now show 0.7 %, 100.0 % and 100.0 % side by side, because only the row
of the run being published is ever rewritten. The other two are in the user's log, so
publishing them from their terminal would bring all three into line.

### [x] Step 6: docs and wrap (15 min)

- CLAUDE.md: Commands gain the JS test note; Structure gains `explorer.js` and the
  `runs/<id>.json` files; Overview mentions the comparison page.
- TODO.md: Done entry; Now emptied. Archive this file under `notes/plans/`.

## What actually differed from this plan

Written down because the plan is the record of why, and these are the places where the
plan and the code disagree.

- **One `explorer.js` became six modules** under `src/pingme/site/`: `state.js`,
  `stats.js`, `dom.js`, `figures.js`, `map.js` and `app.js`. The split was made so seven
  agents could write in parallel without two of them ever opening the same file, and it
  paid off twice over: five of the six are pure, so 131 node tests cover them without a
  browser, and only `app.js` needs a person to read it.
- **`assignSlot` and `release` became one `toggleRun(state, id, maxRuns)`** returning
  `{state, refused}`. The refusal has to come back to the caller, which the plan's pair
  of functions had nowhere to put.
- **The tokens block is camelCase** (`runSlots`, `targetOrder`, `intervalS`), not the
  Python constants' names.
- **`traced` was added to the index row and then removed.** Nothing read it: the page
  works out which runs lack a map from the full records. An unread field with two test
  assertions propping it up is dead weight.
- **The backfill was not in the plan.** An audit pointed out that only the run being
  published got its data file, so every run already on the site would have had a row in
  the table and nothing behind it. Publishing now writes the data file for every run
  already listed, and only for those.
- **The hop table under the map was not in the plan either.** Every hop delay and address
  was reachable only by hovering, and the rule this project follows, which the single-run
  report pages already satisfy, is that a tooltip enhances and never gates.
- **Step 5 was not done from the container**, contrary to what the plan said. The
  container's private log holds different runs from the user's, so a publish from there
  would write the new page but leave the user's two published runs without their data
  until the user published again. Better to do it once, from the machine that has the log.

  Since overtaken, and the reason is worth keeping so the two paragraphs do not read as a
  contradiction. `backfill_run_data` now writes the numbers for every run the index
  already lists, so a publish from the container no longer strands the user's runs: they
  have their JSON either way. The objection has gone, and with it the reason not to
  publish from the container. What is left is the opposite problem, found by the walk:
  `leeds_bt_2026-08-30T13-59-15Z` exists only in the container's log, so the container is
  now the only machine that can fill in its numbers.

## Risks named up front

- **Two implementations of the same charts.** Only the comparison charts are in
  JavaScript, and they take colours, order and thresholds from Python. The detail view
  is the Python page itself. Drift is confined to chart shape, and both use plotly.
- **plotly's map data.** The run pages already draw the map with the site's own plotly
  copy; the explorer uses the same copy and the same map type, so nothing new is
  fetched. If the map fails to draw on the live page, that is a pre-existing condition
  to record, not a regression of this plan.
- **Iframe height.** A same-origin frame can be measured; a wrong height shows as a
  nested scrollbar, which the user will see in step 5. Fallback: a generous fixed
  height with the frame's own scrollbar.
- **Node on the user's machine.** The JS tests skip without it and say so. The
  container has node 26, so the suite runs fully here.

## Effort

About five hours: the comparison view is the bulk, the rest is plumbing.
