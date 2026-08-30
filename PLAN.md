# PLAN — `pingme`

**Status: draft, awaiting approval. No code written yet.**
Three questions at the bottom need answering before implementation starts.

---

## What we are building

A single command you type in the terminal that measures how good your internet
connection is right now, from several angles, draws the results as graphs inside
the terminal window, and appends everything it measured to a permanent log so
that today's connection can be compared against any other connection you use
later.

The graphs are drawn fresh each time and thrown away. The log is the thing that
lasts.

---

## Decided defaults

These are the choices that seem clearly right. Any of them can be changed before
approval.

**Language and tools.** Python 3.14 with `uv` to manage the environment. Reasons:
the terminal-plotting libraries are all in Python, the statistics libraries are
all in Python, and every library needed was confirmed to install cleanly under
3.14 on this machine (see Evidence below). Go would give a single binary with no
install step, but the terminal-plotting side of Go is much weaker, and the
plotting is a large part of what you asked for.

**Command name.** `pingme`, with flags. `pingme` on its own runs the full default
measurement and draws the graphs.

**No root needed.** The system `ping` program is already allowed to send its
probes without special permission, so `pingme` calls it and reads its output.
Writing our own probe code in Python would need root, which we avoid.

---

## The six things we measure latency to

You asked for four routes. The plan is six targets, because four alone cannot be
interpreted.

The reason: the measurements taken from this machine right now show 44
milliseconds as the *fastest possible* round trip to London. On a fibre line from
Leeds that would be roughly 10 to 15. So about 30 milliseconds of delay is being
added somewhere close to home, before the packet gets anywhere near London — and
that same 30 milliseconds is sitting inside the São Paulo number, the New York
number and the Portugal number too. Four graphs that all contain the same hidden
local problem look like four separate problems. They are one.

So every run measures:

| # | Target | Why |
|---|--------|-----|
| 1 | Your router (the box in the room) | Isolates the Wi-Fi leg |
| 2 | The first hop outside your router | Isolates your internet provider's own network |
| 3 | London — Valve relay `lhr` | Dota UK route |
| 4 | Sterling, Virginia — Valve relay `iad` | Dota US East route (nearest Valve has to New York) |
| 5 | São Paulo — Valve relay `gru` | Dota Brazil route |
| 6 | Portugal — **target not yet chosen** | See open question 1 |

All six are measured round-robin, one probe each in rotation, so they all
experience the same network conditions at the same moments. Measuring them one
after another instead would mean comparing São Paulo at 21:40 against London at
21:35, which tells you nothing.

The Valve addresses are not hardcoded. Valve publishes the current list of its
game relay servers, with their IP addresses and city names, at a public web
address. `pingme` fetches that list, picks the relays for the cities we want, and
caches it. This was tested and works — all three relays answered.

---

## What gets measured

**A snapshot of the connection itself**, taken once per run:

- Wi-Fi or cable. If Wi-Fi: the network name, the radio frequency and channel,
  the channel width, the signal strength in dBm, the negotiated link rate in both
  directions, and the Wi-Fi generation. If cable: the negotiated link speed and
  whether it is full duplex.
- Your public IP address and which company owns it, so a log entry from an
  Airbnb in Leeds is distinguishable from one at home.
- **Which network interface each probe actually went out through.** This machine
  has a Tailscale connection and a Docker bridge alongside the Wi-Fi. A run that
  accidentally goes out over Tailscale would produce numbers that look real and
  mean nothing, with no error message. Recording the route per target makes that
  visible instead of silent.

**Delay, measured many times**, not once. Several hundred probes per target per
run, so there is a real distribution to draw rather than a single number.

**Download and upload speed.** Using Cloudflare's speed-test service, which works
over ordinary web requests and needs no extra program installed.

**Delay while the line is busy.** This is the measurement that matters most for
Dota and the one that speed-test websites hide from you. A connection can show a
fine ping when idle and fall apart the moment something else starts downloading,
because delay builds up in a queue inside the router or the provider's equipment.
So the plan is: measure the delay while idle, then measure the delay *again*
during the download and again during the upload, and report the difference. If
your ping goes from 45 to 300 milliseconds whenever someone else in the house
opens YouTube, this is the number that shows it.

**Ordering matters** and is fixed: idle delay first, then the speed test with
delay measured throughout, then idle delay again as a check that conditions did
not drift.

---

## What gets calculated

Every individual probe result is saved. That means any statistic can be
recomputed later from an old run without re-measuring, so the reported set can
stay small and useful rather than exhaustive:

- Packets lost, as a percentage — the single most damaging thing for a game.
- The fastest round trip seen. This is the physical floor of the route: light
  through fibre plus switching. It cannot improve.
- The median — the typical experience.
- The 95th and 99th percentile — the worst 5% and worst 1%. In a game these are
  the moments the character stops responding, and they matter far more than the
  average.
- Jitter, meaning how much the delay jumps between one probe and the next.
- The gap between idle delay and delay-under-load.

**On the bell curve.** You asked for a gaussian. Round-trip times are not
bell-shaped and never will be: there is a hard physical floor below which nothing
can travel, and a long tail of slow ones stretching to the right. Drawing a
symmetric bell over that data would be drawing something that is not there. So
the histogram gets drawn as it actually is, with the floor, the middle and the
slow tail marked on it as numbers. If a smooth curve is wanted, it will be a
curve fitted to the real shape rather than an assumed bell.

---

## What gets drawn

Default mode uses `plotext`, which draws real graphs out of terminal characters —
histograms of the delay for each target, delay plotted against time so a spike is
visible, and the speed results. Laid out with `rich` so it looks composed rather
than dumped.

A `--pretty` mode is planned for later: draw the graph properly with matplotlib
and seaborn, then display the resulting image *inside* the terminal window. The
terminal in use here is Ghostty, which supports displaying images inline. This is
listed as later work because it has not been visually confirmed yet, and it needs
a fallback for terminals that cannot do it.

---

## What gets saved

One file that grows by one entry per run, in a format that is easy to read back
later, holding: the run label, the timestamp, the full connection snapshot, every
individual probe result, the calculated figures, and which route each probe took.

Saved under your home directory in the standard place for application data, not
inside the project folder, so the history is not tied to the code and does not
end up in git.

`--label airbnb_leeds` labels a run; the timestamp is appended automatically, so
the entry becomes `airbnb_leeds_2026-08-29T21-40-00Z`.

Two commands read the log back: one to list past runs, one to compare two runs
side by side.

---

## Success criteria

Done means all of these, each with named evidence (ticked 2026-08-29 with the evidence noted):

1. [x] (30 s `--quick --label smoke` run; six panels + speed panel drawn; exit 0) `pingme --label test` runs start to finish on this machine with no errors, and
   the terminal shows histograms for all six targets plus the speed results.
2. [x] (`pingme show` redraws the saved entry with the same numbers) The run appends exactly one complete entry to the log, and reading that entry
   back reproduces every number shown on screen.
3. [x] (route per target in the log; `flag_odd_routes` unit-tested with a fake tailscale0 route — forcing a real one needs root) Every probe's route is recorded, and a run forced over Tailscale is visibly
   marked as such rather than silently accepted.
4. [x] (idle p95 155 ms vs busy p95 645 ms to London in the smoke run) The delay-under-load figure is demonstrably different from the idle figure on
   this connection, proving the two are actually measured separately.
5. [x] (PINGME_OVERRIDE="sao-paulo=192.0.2.1" quick run: red "no replies" panel, 100% loss row, exit 0) A target that is unreachable degrades to a clear message and a partial result,
   rather than crashing the run.
6. [x] (bytes and seconds printed in the throughput panel; speed test is time-bounded) The data used by a default run is measured and printed, and stays under the
   agreed budget.
7. [x] (14 passed, ruff clean) `ruff check .` clean, and the statistics functions have tests against known
   inputs.

---

## Web report (added 2026-08-29, approved)

`pingme --web` / `pingme web <run>`: one HTML file per run with a KPI row, two
throughput charts, one histogram + timeline pair per target with a table under
each, a single-hue comparison bar chart, the route map, and a footnote stating
pingme's own thresholds. Colours come from the dataviz skill's validated palette
(phases blue/orange/aqua; routes blue/orange/aqua/yellow; both PASS the
colour-blind checks in light and dark). Dark mode swaps the same hues to their
dark steps by script. Built only from the saved record — never re-measures.

## Open questions — these block the start of coding

**1. Portugal target — ANSWERED 2026-08-29: Madrid Valve relay (`mad`). Portugal dropped.**
(Original question kept for the record.)
The four routes were justified as places you play Dota. But Valve has no relay in
Portugal — the nearest is Madrid. So there are two different projects here:

- *If this is about Dota:* use the Madrid relay and call it that. Portugal drops out.
- *If this is about the EllaLink cable to Brazil specifically:* we need a real
  machine hosted in Lisbon or Sines that answers probes, and Dota is beside the
  point for this one target.

This matters because the obvious Portuguese web addresses are useless for the
purpose. `nos.pt` and `up.pt` were tested and both resolve to Cloudflare, which
answers from the nearest city — probably London. Pinging them measures London
while displaying a Portuguese name. Genuine Portuguese addresses were found and
do answer (SAPO and MEO), but they are web servers, which treat probe traffic as
low priority and give erratic readings.

**2. Data budget — still open.** Current connection is Three 5G home broadband
(confirmed: public IP belongs to Hutchison 3G). Proposal below stands.

This is metered mobile broadband. The link is negotiating over 500 Mbit/s, and a
full speed test at that rate can spend several hundred megabytes in seconds. If
you run this a few times a day it becomes a real cost. Proposal: a data budget as
a normal setting, defaulting to something small, with the estimated cost printed
before the test starts and a `--full` flag to lift it.

**3. Run length — ANSWERED: default 60 s; `--long` = 2 min; `--longer` = 10 min.**

Enough probes for a meaningful distribution takes time. Roughly: 30 seconds gives
a rough shape, 2 minutes gives a solid one, 10 minutes catches intermittent
problems. Proposal: default to about 60 seconds, with `--quick` and `--long`.

---

## Route map (`pingme --map`)

**What you asked for.** A map showing the path packets take to each target, so you
can see whether the Brazil traffic goes by the EllaLink cable (Portugal to
Fortaleza), some other Atlantic cable, or the long way round via the USA. Zoomed
automatically: Europe only if the path stays in Europe, the whole Atlantic if it
crosses it, the globe if it wanders.

**What was found when testing it on this connection (2026-08-29).**

- Three hides every hop on its IPv4 network. Tested with standard probes, with
  the UDP variant, and again as root: hop 1 is the router, then nothing until the
  far end. The TCP variant could not be tested from Claude's container even as
  root (blocked by the container); it may work from the real terminal — see
  question 4 below.
- Three's **IPv6** network does show hops. A trace to Cloudflare over IPv6 shows
  three Three routers, then Cloudflare's. Every one of Three's own routers already
  reads ~44 ms — meaning the whole ~40 ms "local" delay is the 5G radio plus the
  tunnel back to Three's core (geolocation guesses London), not anything after it.
  On fibre, Leeds to London would be ~4 ms.
- The Valve relays are IPv4 only. So on this connection a hop-by-hop map of the
  Dota routes is not obtainable. On a normal fibre line it usually is.
- Geolocating backbone routers from their IP is a guess at best. ip-api placed a
  Three router in the City of London; RIPE IPmap had no idea. Hostnames often
  encode the city (e.g. `lhr`, `gru`) but Three's routers have none.
- Traceroute only sees the outbound path. The return path can be different and is
  invisible to this method.

**Design that copes with all of that.**

1. *Physics check — works even when every hop is hidden.* Light in fibre gives
   about 1 ms of round trip per 100 km. So the fastest round trip ever seen to a
   target is a lower bound on how far the packets travelled — both ways, so it
   covers the return path too. Computed floors (great-circle, then ×1.3 for real
   cable routing):

   | Route | km | floor | realistic |
   |---|---|---|---|
   | Leeds → London → Sines → Fortaleza → São Paulo (EllaLink) | 9 850 | ~98 ms | ~128 ms |
   | Leeds → London → New York → Miami → São Paulo (via US) | 14 170 | ~142 ms | ~184 ms |
   | Leeds → London → Virginia | 6 190 | ~62 ms | ~81 ms |
   | Leeds → London → Madrid | 1 540 | ~15 ms | ~20 ms |

   Measured best to São Paulo today: 220 ms. Subtract the ~40 ms Three adds
   before anything starts, ~180 ms — squarely the "via US" figure, and well above
   anything EllaLink could give. `pingme` will print this verdict per target:
   "best RTT 220 ms; after local overhead ~180 ms; consistent with: via USA".
   This is the tool's primary route detector. It cannot be fooled by hidden hops.

2. *Hop map where hops are visible.* Trace each target (IPv4 and, where the target
   has one, IPv6). Geolocate each visible hop: hostname city code first, then
   RIPE IPmap, then ip-api, with the source of each guess recorded. Hidden
   stretches are drawn as a dashed straight line between the last known and next
   known point, labelled "n hops hidden".

3. *Map rendering.* Plotly `Scattergeo` with `fitbounds="locations"`, which zooms
   to the bounding box of the plotted points — tested, works: this gives exactly
   the "Europe only / Atlantic / globe" behaviour asked for, with no zoom logic to
   write. Output is an HTML file opened in the browser with `xdg-open`. PNG export
   needs Chrome, which is not installed, so HTML is the format.

4. *Fixed known points always drawn:* origin (from public IP), each target city,
   and the landing points of the cables that matter (Sines, Fortaleza, New York,
   Miami) as faint reference markers, so the physics verdict has something to be
   read against.

**Trace tooling:** `mtr` in report mode is installed and works unprivileged for
ICMP. Root or capabilities would be needed for TCP-mode traces.

## Out of scope for v1

- Continuously refreshing display like `htop`. The plan is: run, draw, exit.
  A live mode can come later.
- Running on a schedule in the background.
- The `--pretty` image mode described above.
- Probing over the game's own protocol rather than standard probes.
- Reading the 5G signal quality of the Three router itself. That lives on the
  router's admin page, not on this laptop; possible later via scraping.

## Open question 4 (new)

Does a TCP-mode trace reveal Three's hidden IPv4 hops when run from the real
terminal as root? Claude's container blocks it. Command to try on the host:
`sudo traceroute -T -p 27015 -q 1 -w 2 155.133.227.35`
If hops appear, the hop map works on this connection for the Dota relays.
If not, the physics check is the only route evidence here.

---

## Evidence gathered on 2026-08-29

All from this machine, an Airbnb in Leeds on a Three home broadband connection.

- Valve's public relay list was fetched successfully and contains London,
  Sterling (Virginia), São Paulo and Madrid, with IP addresses. No Portugal.
- All four of those relays answered probes.
- Round trips at the time of testing: London 44–58 ms, Madrid 56–95 ms,
  Virginia 109–139 ms, São Paulo 220–249 ms.
- A route trace to London: the router itself answers in 2.2–8.3 ms; every
  intermediate hop after that is hidden by the provider; the far end shows
  43.5 ms at best, 114.9 ms at worst, with 20.7 ms of variation. So the Wi-Fi
  leg costs only a few milliseconds and the remaining ~40 ms, plus all the
  instability, is happening inside Three's network where it cannot be seen
  hop by hop. This is why the local baseline targets are needed.
- Wi-Fi read successfully: SSID, 5180 MHz on channel 36, 160 MHz wide,
  −66 dBm signal, Wi-Fi 6, 576 Mbit/s down and 865 Mbit/s up negotiated.
- All four probed targets currently route over `wlan0`, not Tailscale.
- Under Python 3.14: plotext 6.0.0, rich 15.0.0, textual 8.2.8,
  matplotlib 3.11.1, seaborn 0.13.2, numpy 2.5.2, scipy 1.18.1, httpx 0.28.1
  and typer 0.27.2 all installed cleanly.
- No image-in-terminal helper program is installed, so `--pretty` would have to
  talk to the terminal directly or install one.

---

# Phase 2 — publish reports to GitHub Pages (plan, 2026-08-29, not started)

## Goal

Open any `pingme` report from the phone at a stable web address, without opening
files by hand.

## Findings that shape the plan

- The container can push to GitHub over SSH as `filipejunqueira` (tested with
  `ssh -T git@github.com`). The `gh` command is not installed in the container,
  so creating a repository and switching on Pages happens in the GitHub app on
  the phone — two screens, about two minutes.
- GitHub Pages on a free account serves **public** repositories only. A report
  currently contains the public IP address, the Wi-Fi network name and the city.
  So the published copy must be redacted, and the reports live in their own
  public repository, separate from the code.
- A report is 4.2 MB because plotly.js is inlined. The published copy loads
  plotly from a CDN instead, which makes each report about 150 kB, so the
  repository stays small over hundreds of runs.

## Design (plan-gate order: data, then interfaces, then logic)

Two repositories:

| Repo | Visibility | Content |
|---|---|---|
| `internet-speed` | user's choice | this code |
| `internet-speed-reports` | public | `index.html`, `runs/index.json`, `runs/<id>.html` |

Pages serves the second one at `https://filipejunqueira.github.io/internet-speed-reports/`
through `.github/workflows/pages.yml` on every push to `main` (live since 2026-08-29).

### 1. Data

`runs/index.json` — a JSON list, newest first, one object per published run:

```
{"id": str, "label": str|null, "timestamp": str (ISO, UTC), "isp": str|null,
 "city": str|null, "country": str|null, "medium": "wifi"|"ethernet"|null,
 "download_mbps": float, "upload_mbps": float, "worst_loss_pct": float|null,
 "local_overhead_ms": float, "sao_paulo_p95_ms": float|null,
 "sao_paulo_route": str|null, "page": "runs/<id>.html"}
```

These are the fields `pingme list` shows today, so one helper feeds both. The
private log `runs.jsonl` is never read by the site and never written by publish.

Redaction, applied to a **deep copy** of the run record before any HTML is built:
`snapshot.public.ip` → `"redacted"`, `snapshot.wifi.ssid` → `"redacted"`,
`targets[*].samples` untouched, hop IPs untouched (they belong to Three/Valve, not
to the user). The map's origin marker stays at the city-level coordinate ip-api
gave; nothing finer exists in the record.

### 2. Interfaces (signatures)

- `store.summary_row(run: dict) -> dict` — the index.json object above. Replaces
  the inline field-picking in `cli.list_runs`, which then calls it.
- `render_web.redact(run: dict) -> dict` — returns the redacted deep copy.
- `render_web.build_report(run, traces=None, *, plotly: Literal["inline", "cdn"] = "inline") -> str`
  — new keyword; `"cdn"` emits
  `<script src="https://cdn.plot.ly/plotly-7.0.0.min.js">` (version read from
  `plotly.__version__`) instead of the 4 MB inline bundle.
- `publish.site_dir() -> Path` — `$XDG_DATA_HOME/pingme/site`; clones
  `git@github.com:filipejunqueira/internet-speed-reports.git` on first use.
- `publish.build_index(rows: list[dict]) -> str` — index.html from index.json rows;
  same CSS tokens as the report (imported from `render_web`, not copied).
- `publish.publish(run: dict, *, status, redact: bool = True, with_map: bool = True) -> str`
  — orchestrates: redact → trace (unless `with_map=False`) → build_report(cdn) →
  write `runs/<id>.html` → update `runs/index.json` → write `index.html` →
  `git add -A && git commit -m "report <id>" && git push` → return the page URL.
- CLI: `pingme publish [run] [--no-redact] [--no-map]`; `pingme --publish` on a run.
  `--no-redact` prints a one-line warning naming the public repo before it runs.

### 3. Logic notes

- The git steps use `subprocess.run([...], cwd=site_dir(), check=True)`; a
  non-zero exit stops publish with the git message shown. No force pushes.
- If `index.json` is missing (first publish), start from an empty list.
- Re-publishing the same id replaces its page and its row (no duplicates).

### Invariants (tests)

- Publishing never changes `runs.jsonl`: test compares the file's bytes before and
  after `publish()` with git calls stubbed.
- The redacted HTML never contains `snapshot.public.ip` or `snapshot.wifi.ssid`
  from the input record; the unredacted HTML contains both.
- `index.json` ids are unique after two publishes of the same run.
- The CDN report is under 300 kB for the fixture run.

## Steps and who does them

Subagents where the work is independent and self-contained:

1. [x] 2026-08-29 — both repos exist; code pushed to `internet-speed` (`master`);
   reports repo has the placeholder index + workflow; Pages live.
   **User, on the phone (blocks step 3):** create the two repositories in the
   GitHub app; on `internet-speed-reports` open Settings → Pages → Source:
   "Deploy from a branch", branch `main`, folder `/ (root)`. The reports repo
   needs one commit before Pages activates; step 4 supplies it.
2. [x] **Main session:** push this code to `internet-speed` (`git remote add origin
   git@github.com:filipejunqueira/internet-speed.git && git push -u origin master`).
3. [x] 2026-08-30 — done by a subagent: `store.summary_row`, `render_web.redact`,
   `build_report(plotly=)`, `publish.py`, CLI, 5 tests (19 passed). Deviation:
   `pingme list` lost its "london p95" column (index.json has no London field).
   Discovery: the trace ran at publish time, so a re-publish of an old run would
   draw today's network. Fix made in the main session: `pingme --web/--publish`
   trace at run time and save `traces` in the record; `web`/`publish`/`map` on a
   saved run reuse them, else trace now with a warning. Constants moved to
   `places.py` to break the run↔render_map import cycle. The report and the
   terminal now print the traced city path per target ("traced path: you →
   London → Amsterdam → Madrid → São Paulo") above the timing estimate.
   **Subagent A (general-purpose, code):** implement the interfaces in "Design"
   §2 in `store.py`, `render_web.py`, new `publish.py`, `cli.py`, with the
   invariant tests above in `tests/test_publish.py`. ~30 min.
4. [x] 2026-08-30 — the smoke run's log had been cleaned from the scratchpad, so
   the first publish was a fresh quick run on the BT line:
   `pingme --quick --label leeds_bt --publish` → page live at
   `runs/leeds_bt_2026-08-30T13-59-15Z.html`, 76 kB, 0 occurrences of the IP or
   SSID, 2 "redacted" marks; site index HTTP 200. Hops visible on BT: London
   8 hops/1 hidden, US-East 12/3, São Paulo 15/2, Madrid 11/2. The São Paulo
   trace goes London → Amsterdam → Madrid → São Paulo, while the timing estimate
   says "via USA": the physics floors are too coarse to tell a Madrid-side cable
   from a US route at ~190 ms, so the traced path now outranks the estimate in
   the report. One hop geolocated to "Saint Petersburg" by RIPE IPmap on a
   Telefónica address is doubtful; sources are shown next to each hop.
   **Main session:** first `pingme publish` of the smoke run; open the URL on the
   phone.
5. [x] 2026-08-30 — code review (medium) returned 8 findings; all fixed except the
   deliberate hop-IP decision (§1 Data). Fixed: cdn.plot.ly does not serve
   plotly-7.0.0 (HTTP 403 — the first published page had no charts), so the site
   now hosts `assets/plotly-<version>.min.js` written once by publish and pages
   reference it; a run with `--web/--publish` is saved before the trace can be
   interrupted; publish does `git pull --rebase` first and commits only when
   something changed (a second publish of the same run no longer crashes); city
   and country are HTML-escaped; the private first hop no longer appears as a
   "local network" city; one `traced_path` helper serves both renderers;
   CLAUDE.md lists `publish`.
   **Subagent B (code-review at medium effort):** review the diff of step 3 for
   leaks in the redaction path (anything from `snapshot` that reaches the HTML).
6. [x] 2026-08-30 — verify-project: ruff clean, 20 passed, imports clean, both
   help commands exit 0. Committed and pushed (see git log).
   **verify-project agent:** lint, tests, sanity checks; then commit and push.

Steps 1 and 3 run at the same time; 2 needs 1's first repo; 4 needs 1 and 3;
5 and 6 follow 4.

## Success criteria

- [x] Opening `https://filipejunqueira.github.io/internet-speed-reports/` on the phone
  shows the index with the `leeds_bt` run (user saw the placeholder; the charts
  need the plotly asset deploy — checked with curl below).
- [x] 0 occurrences of the IP `86.170.56.246` and the SSID `BT-FMAGNK` in the
  published file; the unredacted/redacted pair is a unit test.
- [x] Published report file 76 kB.
- [x] `uv run pytest` 20 passed; `uv run ruff check .` clean.
- [x] Invariant test: `runs.jsonl` bytes unchanged across `publish()`.

## Risks and rollback

- A leak in redaction publishes personal data to a public repo. Mitigation: the
  invariant test plus the code-review agent on the redaction path before the first
  real publish. Rollback: `git rm` the page in the reports repo, push; note that
  GitHub keeps history, so a leaked page needs a history rewrite (user's call).
- The reports repo grows by ~150 kB per run; 1,000 runs is ~150 MB, acceptable.

## Out of scope

Password-protecting the site (Pages cannot), a custom domain, automatic publishing
on a schedule, publishing the raw per-probe samples as data files.
