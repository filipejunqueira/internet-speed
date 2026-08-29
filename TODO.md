# TODO — internet-speed

## Now

- [ ] User runs `claude remote-control --name internet-speed` in `~/code/internet-speed` (phone access)
- [ ] User opens `notes/reports/smoke_2026-08-29T21-02-51Z.html` and reviews the web report design
- [ ] Full 60 s run into the real log from the user's terminal: `uv run pingme --label airbnb_leeds --web`

## Next

- [ ] `uv tool install --editable .` so `pingme` is on PATH
- [ ] Compare the Leeds Airbnb run against the next connection with `pingme compare`
- [ ] Confirm which relay Dota actually uses in a match: `ss -unp | grep -i dota` during a game

## Later

- [ ] Live refreshing display (htop-style) instead of run-draw-exit
- [ ] IPv6 traces (Three shows its IPv6 hops; the relays are IPv4 only)
- [ ] Read the Three router's 5G signal from its admin page
- [ ] Inline terminal images for `--pretty`
- [ ] Scheduled background runs

## Done

- 2026-08-29 — v1 built: measurement, terminal plots, log, web report with validated palette, route map, physics route verdict. 14 tests, ruff clean.
