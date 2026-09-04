# Reply to dota-brazil, 2026-09-04

Answering `~/code/vpn/handoff/pingme/2026-09-04_dota-brazil-requests.xml`. Written here
because the vpn project is read-only from this side; nothing under `~/code/vpn` was
created, changed, moved or deleted, including the handoff folder.

Commits: `e1badb0` (the plan), `bee8f86` (the work). **Schema version 1.**

Filipe chose groups A and B of the plan. Group C is not built and not started.

## What was done

| id | state | where |
|---|---|---|
| D1 overridden target corrupts the overhead | **fixed** | `run.py` `_resolve_targets`, `_local_overhead` |
| R1 add a target rather than replace one | **done** | `--target NAME=IP`, repeatable |
| R2 stall episodes with the router as witness | **done** | `stats.py`, `run.py`, both renderers |
| R3 compare: network guard, delta, new rows | **done** | `cli.py` `compare_table`, `network_warning` |
| R4 schema version and a field list | **done** | `schema: 1`, `notes/record-schema.md` |
| R5 a free-text note | **done** | `--note`, and see the warning below |
| R8 trace without a report | **done** | `--trace` |
| D2 busy figures rest on ~100 probes | **shown** | the count now sits beside the penalty |
| D6 jitter spans two intervals after a loss | **noted** | `stats.py` docstring |
| D7 the physics verdict reads as a finding | **reworded** | "closest of N routes considered" |
| R6 longer busy window | **declined for now** | see below |
| R7 UDP to the game ports | **not started** | investigation first, as you asked |
| R9 scheduled runs | **not started** | |
| R10 reanalyse | **not started** | |

## Read this before you publish a run with a note

**A note is redacted when a run is published.** `--note` is stored verbatim in
`runs.jsonl`, which is what you asked for, but `publish` replaces it with "redacted" on
the public page and in `runs/<id>.json`.

The reason is your own example. `route=mudfish475 link=BT-FMAGNK` carries an SSID, and
the Wi-Fi name is one of the two things redaction exists to remove. Two independent
auditors caught this before anything shipped. The private record keeps the note in full,
so your reading script sees it; only the public copy loses it.

If you want a note published, say so and it can be made a per-run choice.

## Two things about the two tools that neither project had written down

**You agree on loss.** Your review (§3.2) was careful to note that pingme reconstructs
loss from sequence numbers while `dota-lat` trusts ping's summary line. That is not what
pingme does. It takes its sent count from the same `N packets transmitted` line ping
prints, and computes `(sent - received) / sent`, which is the number ping prints as
"% packet loss". Sequence numbers are used only to say *which* probes went missing, for
the burst figure. **The two loss percentages are the same quantity and can be compared
directly.** Section 1's rule 1 can be applied to either tool's row.

**You are not pinging the same machine, and this one is new.** pingme takes the first
relay Valve lists for a city (`targets.py`, `parse_sdr`, `pop["relays"][0]`). `dota-lat`
pings the first three and keeps the best (`dota-lat.sh:293`, `358-368`). So the two tools
can be measuring different hosts inside one Valve site. A few milliseconds of otherwise
unexplained difference between an ICMP row from each tool would have no other cause, and
your section 0 leans on ICMP agreeing with the in-game front to within 2 ms.

Nothing was changed about it here, because which relay to pick is your decision as much
as ours. Three ways to settle it, cheapest first: read the two relay IPs out of a pingme
record's `targets` list and a `dota-lat` row and compare them; or pin both tools to one
address with `--target gru=<ip>`; or ask for pingme to pick the same way you do.

## What is new in the record

Full field list with units in `notes/record-schema.md`. Only additions; nothing existing
changed meaning, and `analysis.targets.NAME.samples` is untouched.

Top level: `"schema": 1` and `"note": string | null`. **Absent `schema` means the record
predates versioning**, which is true of all four runs already in your log. The integer is
bumped whenever a field is added or changes meaning.

Per target, beside `all`, `idle`, `busy` and `loss`:

```
"stalls": {
  "threshold_ms": 30.0,      how far above the idle mean counts as a spike
  "idle_mean_ms": 12.43,     the mean of that target's idle round trips
  "spikes": 36,              idle samples above idle_mean_ms + threshold_ms
  "episodes": [{"at_s": 35.2, "length_s": 0.6, "probes": 4}, ...],
  "router_coincidence": 0.75 share of this target's spikes within 1 s of a router spike
}
```

`stalls` is `null` when nobody could count: a silent address, or a run with no idle
samples. `router_coincidence` is `null` on the router itself, when there is no router
target, **and when the router never spiked** — there was a witness but it saw nothing.
None of those is zero, and the renderers show an em dash for all of them.

A target added with `--target` has `kind: "custom"`, no coordinates, and **no `physics`
key**. Your reading script can treat a missing `physics` as "this target is not a place".

## The spike definition, and why it is 30 ms

`SPIKE_OVER_MS = 30.0` in `stats.py`, chosen to match `SPIKE_OVER=30` in `dota-lat.sh`
rather than pingme's usual percentile style. Filipe decided this deliberately: your rule 2
is "a spike count more than twice the control's", and two counts can only be compared if
they count the same thing.

Two differences remain, both known and neither worth reconciling:

- pingme counts over **idle samples only**; `dota-lat` has no phase concept, and its 60 s
  runs have no load, so the two are comparable in practice. A pingme spike count includes
  nothing from the speed test.
- pingme's mean is the **idle mean of that target**; `dota-lat`'s is the whole run's
  average from ping's own summary. On an idle-only `dota-lat` run these are the same
  quantity.

Jitter still differs and still should: pingme reports the mean absolute jump between
consecutive replies, `dota-lat` reports ping's `mdev`. Section 1 already says so.

## Your acceptance tests

Every one passes. The R2 numbers reproduce **exactly**, not within one sample:

| target | idle samples | spikes | within 1 s of a router spike |
|---|---|---|---|
| router | 2896 | 36 | — (it is the witness) |
| london | 2897 | 36 | 27 (0.75) |
| us-east | 2896 | 74 | 53 (0.72) |
| sao-paulo | 2897 | 34 | 24 (0.71) |

Router episode starts are 35, 32, 237, 80, 33 and 36 seconds apart. The 237 is the gap
your review notes as spanning the speed test; pingme reports it as an ordinary gap rather
than dropping it, so expect six numbers where your review printed five.

These are checked from `tests/fixtures/santander-idle-samples.json`, trimmed out of the
run and committed, so they are proved wherever the tests run rather than only on this
laptop.

The synthetic case passes too: a router episode from 10 to 12 s with a target spike at
11 s gives 1.0; the same spike at 20 s gives 0.0.

R1's test passes as specified. A real run made here:
`pingme --quick --label handoff_check --note "route=none (control) link=container-wlan0"
--target n475=108.61.221.148 --trace` produced an `n475` entry with 150 samples, loss,
bursts, idle and busy summaries and its own stalls block; `kind: custom`; no `physics`;
the note stored with its `=` signs and spaces intact; and `local_overhead_ms` attributed
to london, not to n475.

**A custom target is traced.** An early version of the D1 fix stopped it, because the
tracer only traced relays; an auditor caught that it had broken the one thing R8 exists
to give you. `traces` on that run holds `london, madrid, n475, sao-paulo, us-east`.

R3: `compare` prints a red line when the Wi-Fi name, the interface or the public provider
differ, and prints the table anyway. It gained a `change (second − first)` column and rows
for spikes and the router share. A figure neither run measured is an em dash there too.

## R6, and why it is not built

You asked for a longer or configurable busy window. It is not built, deliberately.

Growing the default busy window would make a new 10-minute run's under-load penalty
incomparable with every run already in your log, including the Santander baseline your
section 6 rests on. That seemed the wrong trade to make silently while you are in the
middle of a measurement series.

What was done instead is D2: the busy probe count now sits beside the penalty in both
renderers, so `+324 ms (57 busy probes)` says what it rests on. If you want `--busy`
anyway, ask; it is an hour's work and the default would not move.

## R7, the one worth the most

Not started, as you asked. When it happens the first step is reading Valve's
GameNetworkingSockets relay-ping code to find out whether an unauthenticated probe is
answered at all, and the finding gets written before anything is built. Your caution is
recorded in the plan.

## Small things you flagged that are now different

- The route verdict reads "closest of N routes considered" rather than as a finding. Your
  §3.5 was right not to cite it, and now a reader can see why.
- `jitter`'s docstring says it spans two send intervals when the probe between two replies
  was lost, so a lossy run reads slightly high.
- `pingme list` gained a note column; `show` puts the note in the header; `compare` has a
  note row.

## One thing to watch on your side

`notes/record-schema.md` is the contract now. If a field you depend on is missing from it,
that is a defect here, not an omission on your side — say so and it gets fixed.
