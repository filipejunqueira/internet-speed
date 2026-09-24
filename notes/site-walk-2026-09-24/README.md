# The live site, walked 2026-09-24

Walked right after republishing `leeds_bt_2026-08-30T13-59-15Z` (site commit 20c7796),
the last step of `notes/plans/2026-09-24_route-date.plan.md`. `walk.mjs` drove headless
Chromium through seven states (the index; one run ticked; 13:59 with 15:32 on São Paulo;
the three Leeds runs on São Paulo; three mixed runs on London; the 13:59 and 2026-09-03
report pages), each at 1280 px light, 1280 px dark and 390 px. Every state was set by its
URL. Text colours were read from the computed styles, and the contrast ratios below were
worked out from those values, not judged from a picture. The PNGs here are the evidence;
the other 143 of the 150 taken stayed in the session's scratchpad.

## What reads well

- A calm, restrained page. Each run keeps one colour across the table dot, the tiles, every
  chart and the map, and there are never more than three.
- Dark mode is designed rather than inverted: page, cards, grid and map land all switch.
- Nothing scrolls sideways at 390 px on any page, and the report opens inside the explorer
  with no scrollbar of its own.
- Every chart has one plain sentence under it saying how to read it, and the tables
  right-align their numbers and put the best value per row in bold.
- The route-date sentence sits under the map in the same quiet style as every other
  caption, so it informs without shouting.

## New problems

1. **Dark mode, the explorer's charts.** Legend text and axis titles are drawn in
   `#52514e` on the `#1a1a19` card, a contrast of 2.2:1, so they almost disappear
   (`histogram-dark.png`). Light mode uses the same colour on a light card, 7.7:1, so the
   charts keep their light-mode text colour in dark mode. On the report pages the legend
   does switch to white, but the axis titles look just as dim (seen, not measured).
   **Fixed the same day (433bff8)**, with problem 2. `contrast.mjs` measured every text
   element outside the map on both pages in both themes: the lowest went from 2.19:1 (the
   report's "seconds" and the explorer's legends, dark) to 4.85:1.
2. **Light mode, every caption.** The muted colour `#898781` at 12 px on the `#fcfcfb` card
   is 3.5:1, under the 4.5:1 floor the web accessibility guidelines (WCAG, level AA) set
   for small text. Every note under a chart is
   in it, the new route-date sentence included. Dark mode passes at 4.85:1.
   **Fixed the same day (433bff8):** light muted is now `#6f6d68`, 5.03:1 on the card and
   4.90:1 on the page.
3. **Report pages, every histogram.** The "median" and "p95" labels at the top of the two
   dashed lines print on top of the legend (`report-histogram.png`). Same family as the
   three collisions already in TODO.md.
4. **Report page, the map.** The US-East marker label and the New York city label print
   over each other, and the first leg of the São Paulo route arcs off the top edge of the
   map (`report-map.png`).
5. **Phone, the explorer's map.** The map shrinks to fit the width but the card keeps its
   desktop height, so about two thirds of it is blank (`phone-map.png`).
6. **A ticked run's box** fills solid black (white in dark mode) with no check mark. It
   reads as blacked out rather than chosen (`ticked-rows.png`). Minor, and a matter of
   taste.
7. **Throughput.** On the 13:59 report the upload line sits at zero for its last two
   seconds, and on the 2026-09-03 report the last upload point drops to zero; both read as
   the line failing (`throughput.png`). The download axis starts near 15 while the upload
   axis starts at 0. Cause found the same day and written into the TODO.md item: the
   upload counter stops at the deadline while the uploads are still draining.

## Already in TODO.md, seen again

- The `warning` threshold label under a legend entry on the busy-delay chart, on desktop
  and phone (`busy-delay.png`).
- The histogram's three run names stacked in its top-left corner, and the run name printed
  on the São Paulo point of the comparison map.
- Three runs called `leeds_bt`. The map caption now reads "leeds_bt: Traced on 2026-09-24,
  25 days after this run … leeds_bt: When this route was traced was not recorded.", so the
  new route-date sentence cannot say which run it is about either.
- The index rows still reading 100.0 % worst loss and an em dash for duration.
- `favicon.ico` 404 on first load.
- Hop geolocation. The 13:59 route, traced today on a Virgin Media line, is drawn London →
  Serra Talhada (Brazil) → Canary Wharf for the London relay, and via Seattle, Washington
  and Madrid for São Paulo. The page now says honestly that the route was traced 25 days
  later, but the path itself is wrong in a way a reader will notice.
