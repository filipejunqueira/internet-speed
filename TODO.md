# TODO — internet-speed

Last updated: 2026-09-24

## Now

No plan is open. The site was walked on 2026-09-24; what it found is in
`notes/site-walk-2026-09-24/README.md`, with the new problems under Next.

- [ ] Decide what to do about an old row in `runs/index.json` keeping numbers the code
      no longer agrees with. The table shows 100.0 % worst loss for the three Leeds runs
      while their tiles say "6 probes lost, warning", because `publish` replaces only
      the row of the run it is publishing. Two ways: rewrite every row the machine still
      has a record for on each publish, or leave old rows alone and republish by hand.
      Publishing the 13:59 run on 2026-09-10 rewrote its own row, which now reads 0.7 %
      and 30 s beside two sibling rows still reading 100.0 % and an em dash, so the
      three Leeds runs now disagree with each other in the same table. The other two are
      in the user's log: `pingme publish leeds_bt_2026-08-30T15-32` and `...15-15` from
      their terminal would bring them into line.
      Since 2026-09-24 that also brings their report pages in line with the explorer.
      Those pages were built before the route date and say nothing under the map, while
      the explorer says "When this route was traced was not recorded." for the same runs.
      `pingme publish 2026-09-03T13-14` (also in the user's log) needs the same. Publish
      from a clone level with master: the desktop, at 3ac048c, lacks only the `.note`
      style (78e7a8f), so its pages would carry the sentence unstyled. The same three
      republishes carry the contrast fix (433bff8) to those pages; until then the
      2026-09-03 report measures 2.19:1 in dark mode and 3.41:1 in light, and the 15:15 and
      15:32 pages, built by the same old code, should read the same (not measured).
      The same cause shows an em dash in the duration column for runs whose record does
      carry 60 s. Separate from this, the records themselves hold the old per-phase sent
      counts (São Paulo idle reads 34 % loss on the Leeds runs). The site never shows a
      per-phase loss figure, so nothing on the page is wrong, and the penalty is sound
      because the replies were split between the phases correctly. Only `pingme
      reanalyse`, in Later, can mend the record. blocked-by: `pingme reanalyse`

- [ ] Fix the labels that collide on three charts: the `warning` threshold text sits
      under the first legend entry on the busy-delay chart; the histogram stacks all
      three run names in its top-left corner over the plot and repeats the legend; the
      map prints all three run names on one point at São Paulo and "You" twice over the
      UK. Two more of the same kind, found 2026-09-24: on every report page's histogram
      the "median" and "p95" labels print on top of the legend, and on the report map the
      US-East label prints over New York's

- [ ] Tell two runs apart when they share a label. Three runs are all called
      `leeds_bt`, so the legends, the tile headings, the comparison header and the
      "numbers would not load" sentence all read the same name twice. Colour separates
      them, the words do not. Candidate: label plus the run's date and time. Since
      2026-09-24 the map caption's route-date sentences read "leeds_bt: Traced on …
      leeds_bt: When this route was traced was not recorded.", so they cannot say which
      run they are about either

## Next

- [ ] Run `pingme --label <place> --publish` on the next connection, then `pingme compare`
      against `leeds_bt_2026-08-30T15-32-20Z`
- [ ] Confirm which relay Dota actually uses in a match: `ss -unp | grep -i dota` during a game
- [ ] Probe over UDP to the relay's game ports, so loss matches what the game sees

Found by the site walk on 2026-09-24; evidence in `notes/site-walk-2026-09-24/`.

- [ ] Phone: the explorer's map keeps its desktop height, so two thirds of its card is blank
- [ ] Throughput: the 13:59 report's upload line sits at zero for its last two seconds, and
      the 2026-09-03 one ends on a zero; both read as the line failing. Cause, found
      2026-09-24 and still in today's code (`route-date-check` ends `…12.54, 0.0, 0.0`):
      `speed._upload` stops counting bytes at the deadline, but each `client.post` only
      returns once the bytes already queued have left and Cloudflare has answered, and the
      sampler runs until all three have returned (`speed.py:51-60`, `89-91`). Download
      stops counting and receiving at the same moment, so it has no tail. The zeros are
      bytes still leaving, uncounted, not a dead line. Two effects now pull the stored
      upload figure opposite ways: counting at queue entry inflates it (the Later item on
      over-counting), and dividing by a time that includes the drain deflates it. Which
      wins wants a measurement before the chart or the figure changes. The download axis
      starting near 15 is plotly fitting its range to data with no zeros in it
- [ ] A ticked run's box fills solid ink with no check mark and reads as blacked out.
      Minor, a matter of taste

## Later

- [ ] `--busy SECONDS` for a longer speed test (vpn project's R6). Held back on purpose:
      growing the default would make a new 10-minute run's under-load penalty
      incomparable with every run already in the log. The default must not move.
- [ ] UDP probes to the relays' game ports (their R7): read Valve's GameNetworkingSockets
      relay-ping code first and write the finding; build only if the relays answer

- [ ] Decide with the vpn project which relay to ping. pingme takes the first relay
      Valve lists for a city; `dota-lat.sh` pings the first three and keeps the best, so
      the two tools can be measuring different machines inside one Valve site, which is
      the only possible cause of a few ms of otherwise unexplained difference. Three
      ways to settle it are in `notes/reply-to-dota-brazil-2026-09-04.md`; only the
      third changes any code here (`parse_sdr`). blocked-by: the vpn project's answer

- [ ] Physics route floors are too coarse near 190 ms (Madrid-side cable vs via USA); add candidate cables landing in Spain/Portugal, or drop the estimate when hops are visible
- [ ] Doubtful hop geolocation (RIPE IPmap put a Telefónica router in Saint Petersburg); show a confidence or prefer hostname codes.
      Now on a published page: the 13:59 run's route, re-traced 2026-09-24, goes London →
      Serra Talhada (Brazil) → Canary Wharf for the London relay
- [ ] Write the route traced at publish time back into the private log, so a run with no
      trace stops being re-traced, somewhere new, on every publish. It changes the log
      record of a run already measured, so it is a decision first. Left out of the
      route-date plan on purpose
- [ ] Give a published record from before versioning a `schema` it can be read by. The
      13:59 run's JSON on the site has no `schema` key, yet its routes carry `traced_at`
      since the 2026-09-24 republish, because `publish` splices fresh traces into an old
      record. A reader trusting the tag would not look for the field. Found 2026-09-24

- [ ] `pingme reanalyse [id]`: every record stores its samples, so old runs can be
      recomputed with the fixed loss accounting and appended as a new record
- [ ] Upload speed over-counts: `speed._upload` counts a block when it enters httpx's
      buffer, not when it leaves the machine. Three streams × 64 KB at the deadline is
      ~8 % on a 2 Mbit/s uplink over 10 s, noise on a fast line. Pulls against the drain
      time in the throughput item under Next; settle the two together
- [ ] Decide: `.gitignore` ignores `notes/snapshots/` but the snapshot skill treats
      snapshots as tracked history. Pick a side. Both GitHub repos are public
      (checked 2026-09-03 via the API). Recommendation: leave it ignored. CLAUDE.md
      already ranks TODO.md and PLAN.md above snapshots, and the wrap-up copies each
      decision with its reasoning into `notes/plans/`, which is tracked
- [ ] Move the route-date grace period into the tokens block. `TRACE_WITH_RUN_GRACE_S`
      is written as a literal in `map.js` as well as in `render_map.py`, hand-copied from
      Python like `COLLAPSE_DEG` and `REFERENCE_POINTS` beside it, against the tokens
      rule. Drift cannot go unseen (the shared cases in
      `tests/fixtures/trace-note-cases.json` test both sides of the boundary), but moving
      it changes `traceNote`'s arguments, which every shared case calls. Found 2026-09-22
- [ ] Add a favicon to the site. `favicon.ico` is 404 on every load, one console error
- [ ] Live refreshing display (htop-style) instead of run-draw-exit
- [ ] IPv6 traces (Three shows its IPv6 hops; the relays are IPv4 only)
- [ ] Read the Three router's 5G signal from its admin page
- [ ] Inline terminal images for `--pretty`
- [ ] Scheduled background runs

## Done
- 2026-09-24 — Chart text follows the theme, and captions pass 4.5:1 (433bff8, live in
  site 8467e68). Dark mode left legends and axis titles at 2.19:1, because text given a
  colour of its own ignored the theme repaint; light mode set every caption at 3.5:1. The
  lowest text outside the map, measured on the live explorer and the 13:59 report in both
  themes by `notes/site-walk-2026-09-24/contrast.mjs`, is now 4.85:1. The other three
  report pages wait on the user's republish. The same session diagnosed the upload
  chart's zero tail, written into its item under Next.

- 2026-09-24 — The route date is live, and its plan is archived
  (`notes/plans/2026-09-24_route-date.plan.md`). A real `--quick --web` run in the
  container drew its map with no sentence; republishing `leeds_bt_2026-08-30T13-59-15Z`
  put "Traced on 2026-09-24, 25 days after this run, so it may not be the path the run
  took." under its map, read back on the live report page and in the explorer. That
  settles the two route-date items that led Now, and closes the explorer plan's step 5,
  whose one open question was this map. The same walk looked at the whole site in light,
  dark and phone views: `notes/site-walk-2026-09-24/`, new problems under Next.

- 2026-09-23 — The two config fixes agreed last session. CLAUDE.md's corrections log now
  names the three run logs and which runs each holds. The global `rules/python.md` no longer
  says to edit Python through the shell; it names the Bash hook and the
  `[tool.ruff.format] exclude` fix instead (claude-config repo).

- 2026-09-22 — The route date, steps 3 and 4 of PLAN.md. Every trace entry carries
  `traced_at` (schema 2), and a route traced later than its run says so under the map on
  the report page, on the map-only page and in the explorer caption. The code had landed
  untested in the 2026-09-13 wip commit; tests added (dd870f8), including one showing
  a with-the-run trace adds no bytes to the report (checked once by `cmp` against the
  pre-plan code, before the `.note` style was added). A global hook now runs `ruff format`
  after shell edits too, which rewrote two test files; `[tool.ruff.format] exclude` stops
  it for this project and the files were restored (3ac048c). A review pass found the note
  unstyled on the report page, fixed with a test (78e7a8f). The desktop clone was pulled.

- 2026-09-13 — Claude switched this repository to SSH on 2026-09-13. Outstanding work was committed as-is so nothing was left uncommitted.
  Why: an HTTPS remote cannot push from the claude-sandbox container, which has no git credential helper and does not read the host's git config. SSH works there with no setup. Original remote URLs are recorded in the claude-config repo at notes/remote-urls-before-2026-09-13.txt.

- 2026-09-10 — Walked the published explorer on the live site with a headless browser
  and did the looking half of step 5 of `notes/plans/2026-09-03_run-explorer.plan.md`.
  The step stays open: its publishing half is the first item under Now. Every state was reached by clicking and every colour was read out of
  plotly's own trace objects, not judged from a picture. Eleven checks passed: sorting,
  one tick opening the report in a frame with no inner scrollbar, two and three ticks
  comparing, the fourth refused, one colour per run held across the tiles, both overview
  charts, the histogram, every timeline and the map, unticking the middle run repainting
  nothing, only ever three run hues, the URL restoring both ticks and target, the em
  dash as U+2014 by code point, and the mockup's own numbers. Five things read wrong,
  each now an item under Now. The findings are written into the plan. The missing run
  data was then published from the container, which fixed the 404 and rewrote that run's
  index row, and turned up one more thing: publishing a run whose record has no trace
  re-traces the route on today's network without saying so on the page.

- 2026-09-10 — Wrap-up corrections, no code changed. CLAUDE.md said `PINGME_OVERRIDE`
  only swapped an address; since bee8f86 it also marks the slot custom, drops its
  coordinates and removes its physics block, so anyone writing a failure test that
  expected a physics verdict on an overridden slot would have been surprised. The
  corrections log gained the reason the map topology is fetched from `cdn.plot.ly/un/`
  rather than the older path. The ruff-format lesson moved out of auto-memory into the
  global `rules/python.md`.

- 2026-09-04 — pingme became an instrument for the vpn project's dota-brazil work
  (commit bee8f86, record schema 1). `--target NAME=IP` adds a target for one run,
  measured and traced but never placed on the map, which also fixes a defect: an
  overridden slot kept the coordinates of the target it replaced, so pointing the unused
  Madrid slot at a London node collapsed the local overhead to zero and made every
  physics verdict in that run wrong without a word of warning. Every target now reports
  its spikes, the episodes they form, and how many land within a second of a router
  spike; on the Santander run three quarters of London's spikes sit inside a router
  stall, so the wifi link is stalling and everything inherits it. Also `--note` stored as
  typed and redacted on publish, `--trace` without a report, a schema integer and
  `notes/record-schema.md`, the busy probe count beside the under-load penalty, and a
  same-network warning with a change column on `compare`. Reply to the asking project:
  `notes/reply-to-dota-brazil-2026-09-04.md`.
- 2026-09-04 — Two things about the two tools that neither project had written down: they
  agree on loss (both take ping's own transmitted count), and they are not pinging the
  same machine — pingme takes the first relay Valve lists for a city while `dota-lat`
  pings three and keeps the best, which is the only possible cause of a few ms of
  unexplained difference between them. Left for the vpn side to decide; it is in the reply.

- 2026-09-03 — The reports site became one page. It publishes `runs/<id>.json` beside each
  report and backfills the runs already listed, so ticking a run in the table opens it and
  ticking two or three compares them on shared axes, one colour per run, map included.
  Six JavaScript modules under `src/pingme/site/`, 131 node tests inside the pytest gate.
  Built and reviewed by 24 agents; the audit found a stylesheet variable that was never
  defined, which made the tick box invisible, and a y-axis capped at p99, which hid the
  worst probes while the run's own page showed them.
  Mockup of the three screens: https://claude.ai/code/artifact/fe5fdc5f-b0ca-44ba-a503-9f36f3822dec

- 2026-09-03 — Loss you can trust. ping now sends an exact number of probes and waits
  for the last replies, so nothing is invented and nothing at the end is missed; the
  wrong flag pair had it reporting 0.7 % loss to São Paulo on a clean line. Per-phase
  loss was wrong in every saved run (idle read ~34 %) because the idle span covered
  the busy probes; each probe now belongs to exactly one phase. A target that never
  answers reads as silent instead of 100 % loss. Every target reports its longest
  burst of consecutive losses, drawn on both timelines. Any lost probe at all now
  fails the green badge, and a figure nobody measured shows "—" rather than a clean
  zero, which also stopped the silent hop in already-published runs from winning the
  worst-loss tile at 100 %. 16 tests added, 38 in total.
- 2026-08-31 — Packet loss counted from probe sequence numbers. The clock estimate invented ~0.3 % loss on every target; the BT line really lost 1 packet in 1,495.
- 2026-08-30 — `pingme` installed on PATH; first full 60 s run published from the user's terminal: https://filipejunqueira.github.io/internet-speed-reports/runs/leeds_bt_2026-08-30T15-32-20Z.html
- 2026-08-30 — Phase 2 done: `pingme publish` / `--publish` to GitHub Pages with redaction, self-hosted plotly.js, run-time traces saved in the record, traced city path in reports. Review findings fixed.

- 2026-08-29 — Remote Control running; GitHub repos `internet-speed` (code) and `internet-speed-reports` (Pages via Actions) live with placeholder index.
- 2026-08-29 — v1 built: measurement, terminal plots, log, web report with validated palette, route map, physics route verdict. 14 tests, ruff clean.
