# TODO — internet-speed

Last updated: 2026-09-03

## Now

- [ ] Run explorer on GitHub Pages → PLAN.md (draft, awaiting approval 2026-09-03):
      one page listing every published run; tick one to read it, two or three to compare
      with one colour per run, map included. Mockup:
      https://claude.ai/code/artifact/fe5fdc5f-b0ca-44ba-a503-9f36f3822dec

## Next

- [ ] Run `pingme --label <place> --publish` on the next connection, then `pingme compare`
      against `leeds_bt_2026-08-30T15-32-20Z`
- [ ] Confirm which relay Dota actually uses in a match: `ss -unp | grep -i dota` during a game
- [ ] Probe over UDP to the relay's game ports, so loss matches what the game sees

## Later

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
- [ ] Live refreshing display (htop-style) instead of run-draw-exit
- [ ] IPv6 traces (Three shows its IPv6 hops; the relays are IPv4 only)
- [ ] Read the Three router's 5G signal from its admin page
- [ ] Inline terminal images for `--pretty`
- [ ] Scheduled background runs

## Done

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
