# TODO — internet-speed

Last updated: 2026-08-31

## Now

- [ ] Decide: label a silent `isp-hop` "does not answer probes" instead of "100 % loss"
      (on BT that router never replies, so a working line reads as a broken one)
- [ ] Decide: add burst loss — the longest run of consecutive lost probes per target,
      marked on the timeline. Bursts are what a Dota match actually feels; a percentage
      treats ten losses together and ten spread out as the same

## Next

- [ ] Run `pingme --label <place> --publish` on the next connection, then `pingme compare`
      against `leeds_bt_2026-08-30T15-32-20Z`
- [ ] Confirm which relay Dota actually uses in a match: `ss -unp | grep -i dota` during a game
- [ ] Probe over UDP to the relay's game ports, so loss matches what the game sees

## Later

- [ ] Physics route floors are too coarse near 190 ms (Madrid-side cable vs via USA); add candidate cables landing in Spain/Portugal, or drop the estimate when hops are visible
- [ ] Doubtful hop geolocation (RIPE IPmap put a Telefónica router in Saint Petersburg); show a confidence or prefer hostname codes

- [ ] Live refreshing display (htop-style) instead of run-draw-exit
- [ ] IPv6 traces (Three shows its IPv6 hops; the relays are IPv4 only)
- [ ] Read the Three router's 5G signal from its admin page
- [ ] Inline terminal images for `--pretty`
- [ ] Scheduled background runs

## Done

- 2026-08-31 — Packet loss counted from probe sequence numbers. The clock estimate invented ~0.3 % loss on every target; the BT line really lost 1 packet in 1,495.
- 2026-08-30 — `pingme` installed on PATH; first full 60 s run published from the user's terminal: https://filipejunqueira.github.io/internet-speed-reports/runs/leeds_bt_2026-08-30T15-32-20Z.html
- 2026-08-30 — Phase 2 done: `pingme publish` / `--publish` to GitHub Pages with redaction, self-hosted plotly.js, run-time traces saved in the record, traced city path in reports. Review findings fixed.

- 2026-08-29 — Remote Control running; GitHub repos `internet-speed` (code) and `internet-speed-reports` (Pages via Actions) live with placeholder index.
- 2026-08-29 — v1 built: measurement, terminal plots, log, web report with validated palette, route map, physics route verdict. 14 tests, ruff clean.
