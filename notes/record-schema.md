# What is in a saved pingme run

Every measurement pingme takes is appended as one line of JSON to

    $XDG_DATA_HOME/pingme/runs.jsonl        (usually ~/.local/share/pingme/runs.jsonl)

One line is one complete run. The file is only ever appended to, so a line written
months ago is still exactly as it was written. Read it a line at a time and parse each
line on its own; nothing spans two lines.

This page lists every field, what it holds, and what unit it is in. It is written for
somebody reading the log from another program without reading pingme's source.

## The version number

    "schema": 1

Every run written from 2026-09-04 onwards carries this. It is an integer and it says
which shape the rest of the line is in.

**No `schema` key at all means the run was saved before versioning existed.** Those
lines are still perfectly good; they simply lack the fields marked "new in 1" below.
Test for the key's absence rather than assuming a number.

The number goes up by one whenever a field is added or an existing field changes what
it means. When it does, the change is written at the bottom of this page. Fields are
only ever added: an existing field never gets a new meaning under the same name, and
`analysis.targets.NAME.samples` in particular never changes shape, because offline
checks are built on it.

## Nothing measured, versus a measurement that came out zero

This matters more than anything else on the page, so it comes first. Throughout the
record, `null` means *nobody could work this out*, and a number means *this was
measured, and it came out to this*. They are never blurred together.

Three places where the difference bites:

| you see | it means |
|---|---|
| `"loss": null` | this target never answered once, so there is no list of which probes went missing |
| `"longest_burst_probes": 0` | losses were counted, and nothing was lost |
| `"loss_pct": null` with `"silent": true` | the address ignores pings on purpose. It is not a line losing every packet |
| `"loss_pct": 100.0` with `"error"` set to a string | ping itself failed or timed out. Something did go wrong |
| `"stalls": null` | there were no idle samples to judge, so nobody could count the stalls |
| `"stalls": {"spikes": 0, …}` | stalls were counted, and there were none |

The `isp-hop` row of most runs on BT is the worked example: it is `"silent": true`
with every latency figure `null` and `"loss_pct": null`, while `"all": {"sent": 3000}`
still records that three thousand probes were sent to it.

## The top level of a line

| field | type | meaning |
|---|---|---|
| `id` | string | unique name of the run: the label with anything unusual replaced by `_`, then the UTC start time, e.g. `baseline-day-santander_2026-09-03T12-47-31Z` |
| `schema` | integer | the version above. Absent on runs saved before versioning |
| `label` | string or null | the name given on the command line with `--label`, before it was cleaned up for the `id` |
| `note` | string or null | *(new in 1)* free text given with `--note`, stored exactly as typed, never cleaned up. `null` when none was given. Use this rather than `label` for anything containing `=`, `/` or spaces, because those survive here and not in the `id` |
| `timestamp` | string | when the run started, ISO 8601 with a UTC offset |
| `duration_s` | number | how long the run lasted, in seconds |
| `phase_marks_s` | object | seconds from the start of the run to each moment the connection changed state: `download`, `upload`, `idle-again`. Before `download` and after `idle-again` the line was idle |
| `snapshot` | object | what the connection looked like at the start. See below |
| `relay_list_source` | string | where Valve's relay list came from: `network`, `cache`, `stale cache (…)` or `unavailable (…)` |
| `targets` | array of objects | what was pinged. See below |
| `speed` | array of objects | the download and upload tests. See below |
| `analysis` | object | every figure worked out from the probes. See below |
| `traces` | object | present **only** when the run was traced (`--web`, `--publish` or `--trace`). Absent otherwise; do not treat its absence as an error |

There is no `saved_to` field in the file. Runs handed straight back to the program that
made them carry one, holding the path they were written to, but it is added after the
line is written and never appears on disk.

## `snapshot`: the connection at the start of the run

| field | type | meaning |
|---|---|---|
| `interface` | string or null | the network interface packets left through, e.g. `wlan0` |
| `gateway` | string or null | the router's IP address |
| `medium` | string or null | `wifi`, `ethernet`, or null when neither could be worked out |
| `wifi` | object or null | null on a wired connection. Holds `ssid` (string), `freq_mhz`, `channel`, `width_mhz` (MHz), `signal_dbm` (dBm, negative, closer to zero is stronger), `rx_bitrate_mbps` and `tx_bitrate_mbps` (megabits per second, the link rate the card negotiated, not a measured speed), `generation` (e.g. `Wi-Fi 6`). Any of them can be null |
| `ethernet` | object or null | null on wifi. Holds `link_speed_mbps` (megabits per second) and `duplex` |
| `public` | object or null | the public address as seen from outside: `ip`, `isp`, `asn`, `country`, `city` (strings), `lat` and `lon` (degrees). If the lookup failed the object holds a single `error` field naming the failure |

## `targets`: the addresses that were pinged

One object per address, in the order they were probed.

| field | type | meaning |
|---|---|---|
| `name` | string | short name, e.g. `router`, `isp-hop`, `london`, `us-east`, `sao-paulo`, `madrid`, or whatever `--target` was given |
| `ip` | string | the address that was pinged |
| `kind` | string | `gateway` (the router), `isp-hop` (the first hop past it), `relay` (a Valve Dota relay), or `custom` |
| `city` | string or null | the city Valve names for a relay; null for everything else |
| `lat`, `lon` | numbers or null | where that relay is, in degrees. Null means the target is **not placed anywhere** |
| `note` | string or null | how the target came to be in the list, in plain words |

`"kind": "custom"` *(new in 1)* means an address that is measured but not placed: we
know what it answers in, not where it is. Two things make one, and both set `lat` and
`lon` to null:

- `--target NAME=IP` on the command line, which gets the note `added with --target`.
- `PINGME_OVERRIDE`, which swaps the address behind an existing name for testing. An
  overridden slot keeps its name but is no longer the machine that name refers to, so
  it stops being placed and its note says so.

A target with no coordinates gets no `physics` block, and takes no part in
`local_overhead_ms`. Before schema 1 an overridden slot kept the coordinates of the
relay whose name it borrowed, which could drive `local_overhead_ms` to `0.0` and make
every physics figure in that run wrong. If you are reading a run without a `schema` key
that also has `PINGME_OVERRIDE` mentioned in a target's note, distrust its
`local_overhead_ms` and its `physics` blocks.

## `speed`: the two throughput tests

One object per direction, download first.

| field | type | meaning |
|---|---|---|
| `direction` | string | `download` or `upload` |
| `bytes_total` | integer | bytes transferred |
| `seconds` | number | how long the transfer took, in seconds |
| `mbps` | number | megabits per second over the whole transfer |
| `samples_mbps` | array of numbers | megabits per second in each short slice of the transfer, in order, so the shape over time can be drawn |
| `server` | string or null | which server answered, when it says |
| `error` | string or null | why the test failed, when it did. Null when it worked |

## `analysis`

| field | type | meaning |
|---|---|---|
| `local_overhead_ms` | number | milliseconds the connection adds before the packet has really gone anywhere. Worked out as the smallest gap between a relay's fastest reply and the time a straight cable to that relay would need. `0.0` also stands for "could not be worked out" |
| `local_overhead_how` | string | which target and which distance that figure came from, in words. `unknown` when nothing qualified |
| `origin` | array of two numbers | latitude and longitude the distances were measured from, in degrees: the public IP's location, or London when that lookup failed |
| `targets` | object | one entry per target, keyed by the target's `name`. See below |

## `analysis.targets.NAME`

| field | type | meaning |
|---|---|---|
| `ip` | string | the address pinged |
| `kind` | string | same as in the top-level `targets` list |
| `error` | string or null | what ping said when it failed. Null when it ran normally |
| `silent` | boolean | true when nothing came back and ping did not fail: the address ignores pings by policy. Its loss figures are null rather than 100 % |
| `route` | object | how packets to it left this machine: `dev` (interface), `src` (our address on it), `gateway`. Any can be null |
| `all` | object | summary over the whole run. See below |
| `idle` | object | summary over just the part of the run with nothing else using the line |
| `busy` | object | summary over just the part with the speed test running |
| `loss` | object or null | which probes went missing. Null when the target never answered at all |
| `stalls` | object or null | *(new in 1)* brief freezes while the line was idle. Null when there were no idle replies to judge |
| `samples` | array | every reply, in the order they arrived. See below |
| `physics` | object | present only for a relay that has coordinates and answered at least once. See below |

### `all`, `idle` and `busy`: the same eleven figures

| field | type | meaning |
|---|---|---|
| `sent` | integer | probes sent in that part of the run |
| `received` | integer | replies that came back |
| `loss_pct` | number or null | percent of `sent` that never came back, `0` to `100`. Null on a silent address |
| `min_ms`, `median_ms`, `mean_ms`, `p95_ms`, `p99_ms`, `max_ms` | numbers or null | round-trip time in milliseconds. `p95` is the value 95 % of replies came in under. All null when nothing came back |
| `stdev_ms` | number or null | spread of the round trips about their mean, in milliseconds |
| `jitter_ms` | number or null | mean size of the jump from one reply to the next, in milliseconds. Note this is consecutive *replies*, not consecutive probes: where the probe between two replies was lost the jump covers two sending slots instead of one, so a run with a lot of loss reads a little high |

`busy` rests on far fewer probes than `idle`, because the speed test is a small slice of
the run: on a ten-minute run, roughly 103 probes against roughly 2,896. `busy.sent`
tells you how many, and any figure taken from `busy` should be read with that in mind.

### `loss`

| field | type | meaning |
|---|---|---|
| `lost` | array of `[seq, seconds]` | one pair per missing probe: its sequence number and when it was sent, in seconds from the start of the run. Empty when nothing was lost |
| `longest_burst_probes` | integer | most probes lost one after another with none in between. `0` means nothing was lost |
| `longest_burst_s` | number | how long that run of losses lasted, in seconds (probes leave every 0.2 s) |
| `longest_burst_at_s` | number or null | when the longest burst began, in seconds from the start of the run. Null when nothing was lost |

Loss is counted from ping's own "N packets transmitted" line and the sequence numbers
that came back, so a probe lost at the very end of a run is still counted. Sequence
numbers say only *which* probes went missing.

The oldest runs in the log (before 2026-09-03) have no `loss` key at all, and no
`silent` key either. Treat a missing burst figure as "not counted", not as zero, and
reach for these with a lookup that tolerates a missing key rather than indexing.

### `stalls` *(new in 1)*

A **spike** is one idle reply that came back more than 30 ms slower than that target's
own average idle reply. A **stall** is a group of spikes close together in time.

| field | type | meaning |
|---|---|---|
| `threshold_ms` | number | how far above the average counts as a spike. Currently always `30.0` |
| `idle_mean_ms` | number | the average of that target's idle round trips, in milliseconds, which is what the threshold is measured from |
| `spikes` | integer | how many idle replies were above `idle_mean_ms + threshold_ms` |
| `episodes` | array of objects | the spikes grouped into stalls. Spikes no more than 2 s apart are one stall. Each holds `at_s` (when it started, seconds from the start of the run), `length_s` (last spike minus first, so a lone spike is `0.0`) and `probes` (how many spikes it holds) |
| `router_coincidence` | number or null | of this target's spikes, the share that happened within one second of a spike at the router, from `0` to `1`, rounded to two decimals |

`stalls` is `null` when the target has no idle replies at all: a silent address, or a
run too short to have an idle stretch. Nobody could count, which is not zero spikes.

On a run with no `schema` key the `stalls` key is **missing entirely**, rather than
null. Reach for it with a lookup that tolerates a missing key; missing and null both
mean the same thing here, which is that nobody counted.

`router_coincidence` is `null` in four cases, all of them "there is no share to give":
on the router's own entry, because it cannot witness itself; when the run has no router
target at all; when the run does have one but the router itself never spiked, so there
was nothing to witness with; and when this target had no spikes of its own to take a
share of. None of these is the same as `0.0`, which means the spikes were counted and
none of them lined up with a router spike.

What it is for: every target is pinged at the same instant, so the router is a witness.
A coincidence near 1 says the local link froze and this target merely inherited it; near
0 says the freeze was further out along the route. On the ten-minute run of 2026-09-03
on hotel wifi, the router spiked 36 times and about three quarters of London's, US-East's
and São Paulo's spikes sat within a second of one of those, with the router's stalls
starting roughly 35 seconds apart. That is one wifi link stalling on a rhythm, not four
separate network problems.

Only idle replies count, on purpose: the speed test slows everything down deliberately
and those milliseconds are not a fault. Everything in this block can be recomputed from
`samples` alone, which is why `samples` is never reshaped.

The 30 ms threshold is deliberately the same number the `dota-lat` script in the vpn
project uses, so the two tools' spike counts can be compared directly.

### `samples`

An array of four-element arrays, one per reply, in the order the replies arrived:

    [seq, rtt_ms, seconds_since_run_start, phase]

- `seq` — integer, ping's sequence number, counting from 1.
- `rtt_ms` — number, the round trip in milliseconds.
- `seconds_since_run_start` — number, when the reply arrived, rounded to 3 decimals.
- `phase` — string, what the connection was doing when the reply arrived: `idle`,
  `download` or `upload`.

This is the raw data. Every figure above can be rebuilt from it, and its shape will not
change. Probes that never came back are not in here; they are in `loss.lost`.

### `physics`

Present only on a relay that has coordinates and answered at least once. Absent for the
router, for the ISP hop, for a `custom` target, and for anything that never answered.
It compares the fastest reply seen against how long each candidate undersea route would
physically need.

| field | type | meaning |
|---|---|---|
| `effective_ms` | number | fastest reply less `local_overhead_ms`, in milliseconds: roughly the part of the delay spent out on the wider network |
| `most_consistent` | string or null | the candidate route whose realistic time is closest to `effective_ms`. Null when every candidate was ruled out |
| `candidates` | array of objects | each with `name`, `km` (great-circle distance in kilometres), `floor_ms` (the fastest that distance could possibly be), `realistic_ms` (the same allowing 30 % for cables not running straight) and `ruled_out` (true when even the floor is slower than what was measured) |

These candidates are a short hand-written list, not a measurement. Read `most_consistent`
as "of the few routes we thought to compare", never as "this is the route".

## `traces`

Present only on a traced run. Keyed by relay name, so `traces.london` and so on. Only
relays are traced. Each entry holds:

| field | type | meaning |
|---|---|---|
| `error` | string or null | why the trace failed, when it did |
| `hops` | array of objects | one per hop, each with `n` (hop number from 1), `ip` (string, or null when that router did not answer), `avg_ms` (number or null) and `loss_pct` (number or null) |
| `locations` | array | same length and order as `hops`. Each entry is null, or an object with `ip`, `lat`, `lon` (degrees, either can be null when the hop could not be placed), `city`, `hostname` and `source` saying how it was located: `private`, `hostname:<airport code>`, `ripe-ipmap`, `ip-api` or `unknown` |

Hop locations come from public databases and airport codes in hostnames. They are
guesses, sometimes wrong ones, and are best treated as decoration on a map rather than
as evidence.

## Version history

**1** (2026-09-04) — the first numbered version. Added `schema` and `note` at the top
level, `stalls` on every target, and the `custom` target kind, which also stopped an
address swapped in with `PINGME_OVERRIDE` from keeping the coordinates of the relay
whose name it borrowed. Nothing existing was renamed or given a new meaning.

**absent** — anything saved before 2026-09-04. The same shape without those fields:
no `schema`, no `note`, no `stalls` on any target, and no target of kind `custom`. Runs
from before 2026-09-03 additionally have no `loss` key and no `silent` key at all.
