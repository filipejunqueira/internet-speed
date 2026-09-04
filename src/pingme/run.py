"""One full measurement run: snapshot, probes with a speed test in the middle, stats, save."""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import re
import time
from dataclasses import dataclass

from . import speed
from .places import FORTALEZA, LONDON, MIAMI, NEW_YORK, SINES
from .probe import INTERVAL_S, Phase, ProbeResult, probe_all, send_offset, send_time
from .snapshot import route_for, take_snapshot
from .stats import (
    SPIKE_OVER_MS,
    RouteCandidate,
    coincidence,
    episodes,
    longest_burst,
    lost_seqs,
    physics_verdict,
    spike_times,
    summarise,
)
from .store import append_run
from .targets import Target, fetch_sdr, local_targets, parse_sdr

# Version of the saved record's shape. Bump it whenever a field is added or changes
# meaning, and say what changed in notes/record-schema.md. Records written before this
# existed have no "schema" key at all, which is how a reader tells them apart.
SCHEMA = 1

ROUTE_CANDIDATES: dict[str, list[RouteCandidate]] = {
    "sao-paulo": [
        RouteCandidate("straight line (hypothetical floor)", []),
        RouteCandidate("EllaLink: Sines → Fortaleza", [SINES, FORTALEZA]),
        RouteCandidate("via USA: New York → Miami", [NEW_YORK, MIAMI]),
    ],
    "us-east": [RouteCandidate("direct transatlantic", [])],
    "london": [RouteCandidate("direct", [])],
    "madrid": [RouteCandidate("direct", [])],
}


@dataclass
class Timing:
    total_s: float
    speed_s: float  # each direction

    @property
    def idle1_s(self) -> float:
        return max(10.0, self.total_s * 0.4)


def make_run_id(label: str | None, when: dt.datetime) -> str:
    stamp = when.strftime("%Y-%m-%dT%H-%M-%SZ")
    if not label:
        return stamp
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("_")
    return f"{clean}_{stamp}"


def _resolve_targets(status) -> tuple[list[Target], str]:
    targets = local_targets()
    try:
        cfg, source = fetch_sdr()
        targets += parse_sdr(cfg)
    except Exception as e:  # noqa: BLE001
        source = f"unavailable ({type(e).__name__}: {e})"
        status(f"[red]Valve relay list unavailable: {e}[/red]")
    # PINGME_OVERRIDE="sao-paulo=192.0.2.1,london=1.2.3.4" swaps a target's address (testing)
    for pair in filter(None, os.environ.get("PINGME_OVERRIDE", "").split(",")):
        name, _, ip = pair.partition("=")
        for t in targets:
            if t.name == name.strip() and ip:
                # The address changed but the slot kept its name, its city and its
                # coordinates, which made a London node answering in 12.6 ms look like
                # Madrid and dragged the local overhead from 9.1 ms down to 0.0. An
                # overridden slot is not where it says it is, so it stops being placed.
                t.ip = ip.strip()
                t.note = (f"overridden via PINGME_OVERRIDE, no longer the "
                          f"{t.kind} it is named after ({t.note})")
                t.kind, t.city, t.lat, t.lon = "custom", None, None, None
                status(f"[yellow]{t.name} overridden to {t.ip}[/yellow]")
    return targets, source


def add_extra_targets(targets: list[Target],
                      extra: list[tuple[str, str]] | None) -> list[Target]:
    """Append addresses asked for by hand: measured, but not placed on the map.

    We know what such an address answers in, not where it is, so it gets no physics
    block and takes no part in the local overhead. A name already in use is refused
    rather than quietly replaced: two rows under one name would ruin the log.
    """
    out = list(targets)
    for name, ip in extra or []:
        if any(t.name == name for t in out):
            raise ValueError(f"there is already a target called {name!r}; give {ip} a "
                             f"different name rather than replacing it")
        out.append(Target(name=name, ip=ip, kind="custom", city=None, lat=None, lon=None,
                          note="added with --target"))
    return out


def flag_odd_routes(targets: list[Target], default_dev: str | None, status,
                    route=route_for) -> list[str]:
    """Warn when a target would leave through an interface other than the default one."""
    odd = []
    for t in targets:
        r = route(t.ip)
        if r["dev"] and default_dev and r["dev"] != default_dev:
            odd.append(t.name)
            status(f"[yellow]{t.name} routes via {r['dev']}, not {default_dev}[/yellow]")
    return odd


async def _orchestrate(targets: list[Target], timing: Timing, phase: Phase, status
                       ) -> tuple[list[ProbeResult], list[speed.SpeedResult], dict]:
    t0 = time.monotonic()
    marks: dict[str, float] = {}
    probes = asyncio.create_task(
        probe_all([(t.name, t.ip) for t in targets], timing.total_s, phase, t0))

    async def until(t: float) -> None:
        await asyncio.sleep(max(0.0, t0 + t - time.monotonic()))

    speeds: list[speed.SpeedResult] = []
    status(f"idle probes for {timing.idle1_s:.0f}s …")
    await until(timing.idle1_s)
    for direction, fn in (("download", speed.download), ("upload", speed.upload)):
        phase.name = direction
        marks[direction] = time.monotonic() - t0
        status(f"{direction} for {timing.speed_s:.0f}s while still probing …")
        speeds.append(await fn(timing.speed_s))
    phase.name = "idle"
    marks["idle-again"] = time.monotonic() - t0
    status("idle probes again until the end …")
    results = await probes
    return results, speeds, marks


def _origin(snapshot: dict) -> tuple[float, float]:
    pub = snapshot.get("public") or {}
    if pub.get("lat") is not None and pub.get("lon") is not None:
        return (pub["lat"], pub["lon"])
    return LONDON


def _local_overhead(results: list[ProbeResult], targets: dict[str, Target],
                    origin: tuple[float, float]) -> tuple[float, str]:
    """How much delay the connection adds before the packet has really gone anywhere.

    Best guess: the smallest gap between a remote target's best round trip and what
    a direct cable to it would need. On a hidden-hop provider this is all we have.
    """
    from .stats import CABLE_DETOUR_FACTOR, KM_PER_MS_ROUND_TRIP, haversine_km

    best_gap, how = None, "unknown"
    for r in results:
        t = targets.get(r.target)
        # An overridden slot is kept out of this by being marked "custom" upstream in
        # _resolve_targets, not here: without coordinates, "its round trip minus a
        # straight cable to it" has no meaning, so it cannot set the overhead.
        if not t or t.kind != "relay" or t.lat is None or not r.samples:
            continue
        floor = haversine_km(origin, (t.lat, t.lon)) / KM_PER_MS_ROUND_TRIP * CABLE_DETOUR_FACTOR
        gap = min(r.rtts()) - floor
        if best_gap is None or gap < best_gap:
            best_gap, how = gap, f"best RTT to {r.target} minus a direct cable's ~{floor:.0f} ms"
    if best_gap is None:
        return 0.0, how
    return round(max(best_gap, 0.0), 1), how


def phase_at(t: float, marks: dict) -> str:
    """What the connection was doing `t` seconds into the run."""
    download, upload, back = (marks.get("download"), marks.get("upload"),
                              marks.get("idle-again"))
    if download is not None and upload is not None and download <= t < upload:
        return "download"
    if upload is not None and back is not None and upload <= t < back:
        return "upload"
    return "idle"


def account_for_probes(r: ProbeResult, marks: dict) -> tuple[dict, dict[str, int]]:
    """Which probes never came back, and how many went out in each phase.

    A reply counts towards the phase it arrived in. A lost probe has no arrival, so it
    counts towards the phase it was sent in, worked out from ping's fixed schedule.
    Every probe therefore belongs to exactly one phase, which is what makes the
    per-phase loss figures add up.
    """
    offset = send_offset(r.samples)
    lost = lost_seqs(r.sent, (s.seq for s in r.samples))
    sent_in: dict[str, int] = {"idle": 0, "download": 0, "upload": 0}
    for s in r.samples:
        sent_in[s.phase] = sent_in.get(s.phase, 0) + 1
    lost_at = []
    for seq in lost:
        left = send_time(seq, offset)
        phase = phase_at(left, marks)
        sent_in[phase] = sent_in.get(phase, 0) + 1
        lost_at.append([seq, round(left, 3)])
    length, start = longest_burst(lost)
    detail = {
        "lost": lost_at,
        "longest_burst_probes": length,
        "longest_burst_s": round(length * INTERVAL_S, 2),
        "longest_burst_at_s": round(send_time(start, offset), 3) if length else None,
    }
    return detail, sent_in


def _stalls(samples: list[tuple], router_spikes: list[float], is_router: bool) -> dict | None:
    """How often this target stalled while the line was idle, and who stalled with it.

    None when there are no idle samples to judge: a silent address, or a run too short
    to have an idle phase. Nobody could count, which is not the same as no stalls.
    """
    times, idle_mean = spike_times(samples)
    if idle_mean is None:
        return None
    return {
        "threshold_ms": SPIKE_OVER_MS,
        "idle_mean_ms": round(idle_mean, 2),
        "spikes": len(times),
        "episodes": episodes(times),
        "router_coincidence": None if is_router else coincidence(times, router_spikes),
    }


def analyse(results: list[ProbeResult], targets: list[Target], snapshot: dict,
            marks: dict, route=route_for) -> dict:
    by_name = {t.name: t for t in targets}
    origin = _origin(snapshot)
    overhead, overhead_how = _local_overhead(results, by_name, origin)
    stored = {r.target: [(s.seq, s.rtt_ms, round(s.t, 3), s.phase) for s in r.samples]
              for r in results}
    # Every target is probed at the same instant, which makes the router the one witness
    # we have for "the local link stalled" against "the route stalled". Find it once.
    router = next((r.target for r in results if by_name[r.target].kind == "gateway"), None)
    router_spikes = spike_times(stored[router])[0] if router is not None else []
    per_target = {}
    for r in results:
        t = by_name[r.target]
        detail, sent_in = account_for_probes(r, marks)
        # Nothing at all came back and ping itself did not fail: the target ignores
        # probes, which is not the same as a line losing 100 % of them. Report no loss
        # figure rather than a frightening one; the sent count still says what we tried.
        silent = not r.samples and r.error is None
        summaries = [summarise(r.rtts(), r.sent),
                     summarise(r.rtts("idle"), sent_in["idle"]),
                     summarise(r.rtts("download") + r.rtts("upload"),
                               sent_in["download"] + sent_in["upload"])]
        if silent:
            summaries = [x.without_loss() for x in summaries]
        entry: dict = {
            "ip": r.ip, "kind": t.kind, "error": r.error, "silent": silent,
            "route": route(r.ip),
            "all": summaries[0].as_dict(),
            "idle": summaries[1].as_dict(),
            "busy": summaries[2].as_dict(),
            "loss": detail if r.samples else None,
            "stalls": _stalls(stored[r.target], router_spikes, is_router=r.target == router),
            "samples": stored[r.target],
        }
        if t.kind == "relay" and r.samples and t.lat is not None:
            eff, verdicts, best = physics_verdict(
                min(r.rtts()), overhead, origin, (t.lat, t.lon),
                ROUTE_CANDIDATES.get(t.name, [RouteCandidate("direct", [])]))
            entry["physics"] = {"effective_ms": round(eff, 1), "most_consistent": best,
                                "candidates": [v.__dict__ for v in verdicts]}
        per_target[r.target] = entry
    return {"local_overhead_ms": overhead, "local_overhead_how": overhead_how,
            "origin": list(origin), "targets": per_target}


def run(label: str | None, timing: Timing, status=lambda msg: None,
        trace: bool = False, note: str | None = None,
        extra: list[tuple[str, str]] | None = None) -> dict:
    """Measure, analyse, optionally trace the routes, then append to the log.

    Tracing at run time keeps the map honest: a report built later from the saved
    record shows the network the run was measured on, not today's.
    """
    when = dt.datetime.now(dt.UTC)
    status("reading connection details …")
    snapshot = take_snapshot()
    targets, sdr_source = _resolve_targets(status)
    targets = add_extra_targets(targets, extra)
    if not targets:
        raise RuntimeError("no targets at all: no default route and no relay list")
    flag_odd_routes(targets, snapshot.get("interface"), status)
    phase = Phase()
    results, speeds, marks = asyncio.run(_orchestrate(targets, timing, phase, status))
    status("crunching numbers …")
    analysis = analyse(results, targets, snapshot, marks)
    record = {
        "id": make_run_id(label, when),
        "schema": SCHEMA,
        "label": label,
        # Stored exactly as it was typed. The label is scrubbed into the run id, which
        # mangles anything with an = or a / in it; the note is where that survives.
        "note": note or None,
        "timestamp": when.isoformat(),
        "duration_s": timing.total_s,
        "phase_marks_s": {k: round(v, 2) for k, v in marks.items()},
        "snapshot": snapshot,
        "relay_list_source": sdr_source,
        "targets": [t.as_dict() for t in targets],
        "speed": [s.as_dict() for s in speeds],
        "analysis": analysis,
    }
    if trace:
        from .render_map import trace_run

        try:
            record["traces"] = trace_run(record, status)
        except BaseException:  # Ctrl-C or a trace failure must not lose the measurement
            record["saved_to"] = str(append_run(record))
            raise
    record["saved_to"] = str(append_run(record))
    return record
