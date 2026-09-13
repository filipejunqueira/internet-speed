# TODO — internet-speed

Last updated: 2026-09-10

## Now

- [ ] Decide what to do about the map on `leeds_bt_2026-08-30T13-59-15Z`. Publishing it
      on 2026-09-10 re-traced the route, because the record carries no trace, and the
      trace ran on the container's network today rather than the Leeds BT line the run
      measured on 2026-08-30. The page says nothing about this. Its first hops are now
      192.168.1.1 → 192.168.0.1 → 10.53.38.165, where its sibling run from the same
      afternoon shows 192.168.1.254 → 172.16.13.221 → 109.159.255.101, the real BT path.
      Two ways out: republish it with `--no-map`, so a run whose route was never recorded
      gets no map instead of somebody else's, or keep the map and put the trace date on
      the page beside it. The second is the better fix for every run, because a route
      traced later is worth something as long as the page says when it was traced

- [ ] Store the trace date in the record, and show it on any page that draws a map. A
      trace made at publish time carries no timestamp at all, so nothing downstream can
      tell a route measured during the run from one measured weeks later somewhere else.
      Found by publishing the 13:59 run on 2026-09-10

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
      UK

- [ ] Tell two runs apart when they share a label. Three runs are all called
      `leeds_bt`, so the legends, the tile headings, the comparison header and the
      "numbers would not load" sentence all read the same name twice. Colour separates
      them, the words do not. Candidate: label plus the run's date and time

## Next

- [ ] Run `pingme --label <place> --publish` on the next connection, then `pingme compare`
      against `leeds_bt_2026-08-30T15-32-20Z`
- [ ] Confirm which relay Dota actually uses in a match: `ss -unp | grep -i dota` during a game
- [ ] Probe over UDP to the relay's game ports, so loss matches what the game sees

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
- [ ] Doubtful hop geolocation (RIPE IPmap put a Telefónica router in Saint Petersburg); show a confidence or prefer hostname codes

- [ ] `pingme reanalyse [id]`: every record stores its samples, so old runs can be
      recomputed with the fixed loss accounting and appended as a new record
- [ ] Upload speed over-counts: `speed._upload` counts a block when it enters httpx's
      buffer, not when it leaves the machine. Three streams × 64 KB at the deadline is
      ~8 % on a 2 Mbit/s uplink over 10 s, noise on a fast line
- [ ] Decide: `.gitignore` ignores `notes/snapshots/` but the snapshot skill treats
      snapshots as tracked history. Pick a side. Both GitHub repos are public
      (checked 2026-09-03 via the API). Recommendation: leave it ignored. CLAUDE.md
      already ranks TODO.md and PLAN.md above snapshots, and the wrap-up copies each
      decision with its reasoning into `notes/plans/`, which is tracked
- [ ] Add a favicon to the site. `favicon.ico` is 404 on every load, one console error
- [ ] Live refreshing display (htop-style) instead of run-draw-exit
- [ ] IPv6 traces (Three shows its IPv6 hops; the relays are IPv4 only)
- [ ] Read the Three router's 5G signal from its admin page
- [ ] Inline terminal images for `--pretty`
- [ ] Scheduled background runs

## Done
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
