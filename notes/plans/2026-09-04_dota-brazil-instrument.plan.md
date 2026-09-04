# pingme as an instrument for dota-brazil

Date: 2026-09-04. Branch `master`, clean at b1e71e8.
Status: **approved 2026-09-04.** Groups A and B are being built; group C is not.
A spike means what it means in `dota-lat`: an idle sample more than 30 ms above that
target's own idle mean. The user chose that over pingme's percentile style so the two
tools' spike counts are the same kind of number, which is what their rule 2 needs.

Source of the request: `~/code/vpn/handoff/pingme/2026-09-04_dota-brazil-requests.xml`,
written by the vpn project's session on 2026-09-04 against pingme at 969e990. That
project is read-only from here: nothing under `~/code/vpn` is created, changed, moved or
deleted, ever, including its handoff folder. The reply goes in this repository, at
`notes/reply-to-dota-brazil-2026-09-04.md`, once work is done.

## Who is asking, and for what

The vpn project is choosing a network route from this laptop to Valve's Dota relay in São
Paulo. Its rule disqualifies a route on loss above 0.5 %, on any burst of three lost
probes, on a spike count more than twice the control's, on a p99 more than 40 ms above
the median, or on jitter more than twice the control's; only then does the lowest typical
latency win, and only by 10 ms or more. The control is always a no-tunnel run taken in
the same sitting on the same network.

pingme already measures nearly all of that in one run and keeps the raw samples. It is
also the only instrument either project has that pings the router at the same instant as
the relays, which is what makes the router usable as a witness.

## What I verified myself before proposing anything

Their ground rules ask for this, and the tree has moved since 969e990.

| claim | verdict | what I ran |
|---|---|---|
| D1: an override zeroes the local overhead | **true** | `_local_overhead` gives an honest figure (9.1 ms on my synthetic case, 8.9 on the Santander record's own numbers); point the Madrid slot at a London node answering in 12.6 ms and it gives **0.0**, blaming "madrid minus a direct cable's ~19 ms" |
| D2: a 600 s run is busy for 20 s | **true** | `Timing(600, 10)` is 3.3 % busy; the Santander record shows busy sent of 103 or 104 per target against idle sent of 2,896 |
| D3/R2: the spikes are the link, on a rhythm | **true, exactly** | router 36 spikes, london 36, us-east 74, sao-paulo 34; 75 %, 72 % and 71 % within one second of a router spike; router episode starts 35, 32, 237, 80, 33, 36 s apart |
| D4: compare ignores the network | **true** | `cli.py` compare never reads `snapshot` |
| D5: no trace without `--web` | **true** | `cli.py:48`, `trace=web or publish` |
| every cited file:line | **still accurate** | checked each one at HEAD |

## Two things about the two tools that nobody has written down

**They agree on loss, and that is worth knowing.** A note in their review worried that
pingme reconstructs loss from sequence numbers while `dota-lat` trusts ping's summary
line. Not so: pingme takes its sent count from the same `N packets transmitted` line
(`probe.py:108-112`) and computes `(sent - received) / sent`, which is what ping prints.
Sequence numbers are used only to say *which* probes went missing, for the burst figure.
The two loss percentages are the same quantity and can be compared directly.

**They do not agree on which machine they are pinging, and nobody noticed.** pingme takes
the first relay Valve lists for a city (`targets.py`, `parse_sdr`, `pop["relays"][0]`).
`dota-lat` pings the first three and keeps the best (`dota-lat.sh:293, 358-368`). So the
two tools can be measuring different hosts inside the same Valve site, and a few
milliseconds of unexplained difference between them would have no other cause. This is
new: it is not in their review. Cheap to settle, and it belongs in the reply whatever
else is built.

Jitter genuinely differs — pingme is the mean absolute jump between consecutive replies,
`dota-lat` reports ping's `mdev`, a spread about the mean — but their plan already says
so in section 1 and asks for no change.

## What I propose, and how it differs from their order

Their priorities are R1 to R10. I propose three groups. Take, drop or reorder any of it.

### Group A — make the record trustworthy and self-describing (about 4 hours)

Small, and everything else builds on it. Their Phase K script is blocked on R4 today.

| item | what | why here |
|---|---|---|
| **D1 + R1** | a repeatable `--target NAME=IP`, kind `custom`, no coordinates, no physics block, excluded from local overhead; `PINGME_OVERRIDE` marks its slot `custom` too | one change fixes the defect and adds the feature: both come down to a target that is measured but not placed on the map |
| **R4** | `"schema": 1` on every new record, plus `notes/record-schema.md` naming every field and its unit | their reading script breaks silently without it, and it is the cheapest item on the list |
| **R5** | `--note`, stored verbatim, shown by `show`, `list` and `compare` | `--label` is sanitised into the run id, so `route=mudfish475` is mangled today |
| **R8** | `--trace`, which traces and stores without building a report | one flag; every 10-minute run should carry its hop table |

### Group B — the measurement only pingme can make (about 5 hours)

| item | what | why here |
|---|---|---|
| **R2** | per target: spike count, the episodes they form, and for every non-router target the share of its spikes within one second of a router spike; stored, shown in the summary table, and drawn as a faint band on every timeline | this is the link-or-route question their whole method rests on, and pingme is the only tool that can answer it because it probes concurrently |
| **R3** | `compare`: a red warning when SSID, interface or provider differ, a delta column, and rows for the R2 figures | prevents the one mistake that ruins a series, and it is what their verdict reads |
| **D2** | show the busy sample count beside the busy p95 in both renderers | a +144 ms headline resting on 104 probes should say so |

### Group C — NOT being built now (2026-09-04)

Left for a later decision. R6 `--busy` is held back deliberately: growing the default busy
window would make a new 10-minute run's under-load penalty incomparable with every run
already in the log. R7 stays investigation-first whenever it happens.

<details>
<summary>what group C would have been</summary>



| item | what | my view |
|---|---|---|
| **R6** | `--busy SECONDS`, and scale the default with run length | worth doing, but see the open question below: changing the default silently makes old and new penalties incomparable |
| **R10** | `pingme reanalyse ID` | worth more after R2 than before it: it would give the two old BT runs a spike figure |
| **R9** | scheduled runs | I can write the systemd unit and timer, but I cannot install them: anything reaching your real home has to be run by you |
| **R7** | UDP to the relays' game ports | **investigation only.** Read Valve's GameNetworkingSockets relay-ping code, find out whether an unauthenticated probe is answered at all, write the finding, and build nothing until you have read it |

</details>

### Small things folded in for free

- **D6**: one sentence in the `jitter` docstring saying it spans two send intervals when
  the probe between was lost, so a lossy run reads slightly high.
- **D7**: the physics line to read "closest of 3 candidates", so nobody takes a guess for
  a measurement. Their review already refuses to cite it as evidence.

## What I am not proposing

The four suggestions marked "not needed by dota-brazil" in the request: `--minutes N`, a
per-target verdict line, a network column in `list`, and data-driven physics candidates.
They are reasonable and they are already yours to want; none of them serves this request,
so they belong in TODO.md rather than in this plan.

## Open questions, which change what gets built

1. **A spike means mean + 30 ms over idle samples.** Settled 2026-09-04: the same
   definition `dota-lat` uses (`SPIKE_OVER=30`), so their rule 2, "more than twice the
   control's", compares two numbers of the same kind. Deliberately not pingme's usual
   percentile style, and the reason is written into the code.
2. **`--busy` is not being built**, so the default busy window does not move and every
   run already in the log stays comparable with every new one.
3. **Schema version and old records.** Settled: no existing record has one, so absent
   means "before versioning" and new records start at 1. Their script handles both.
4. **Scope.** Settled: groups A and B.

## Success criteria

Per this project's CLAUDE.md, named in one message at the end: `uv run ruff check .`
clean, `uv run pytest` green including the JavaScript tests, and a real run on this
machine with its output shown for anything that measures or draws. Pure functions get a
test against hand-computed inputs before they are wired in. Specific to this work:

- The R2 figures reproduce the numbers in the table above from the Santander record,
  within one sample.
- A synthetic case: a router episode at 10 to 12 s and a target spike at 11 s gives
  coincidence 1.0; the same spike at 20 s gives 0.0.
- `--target n475=IP` produces an entry with loss, burst, idle and busy summaries and
  samples, no `physics` key, and `local_overhead_ms` unchanged from a run without it.
- `compare` on two SantanderGuest runs prints no warning; against a BT-FMAGNK run it
  prints the warning and still prints the table.
- Every run in the log still renders in `show`, `web` and the explorer, and a figure
  nobody measured is still an em dash while a measured zero is still 0.

## Ground rules carried from both sides

- Python edits through the shell: the ruff format hook would rewrite about 993 lines of
  hanging indents.
- Add fields, never repurpose one. Never reshape `analysis.targets.NAME.samples`.
- A lesson from their CLAUDE.md worth heeding here: they were bitten by a `link=` tag
  stamped from the network current at write time rather than the one the reading was
  taken on. If R10 lands, a recomputed record keeps the original snapshot.
- Nothing under `~/code/vpn` is written to, in any circumstance.
