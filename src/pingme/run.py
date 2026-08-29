"""One full measurement run: snapshot, probes with a speed test in the middle, stats, save."""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import re
import time
from dataclasses import dataclass

from . import speed
from .probe import Phase, ProbeResult, probe_all
from .snapshot import route_for, take_snapshot
from .stats import RouteCandidate, physics_verdict, summarise
from .store import append_run
from .targets import Target, fetch_sdr, local_targets, parse_sdr

# Cable landing points used by the physics check (lat, lon).
SINES = (37.95, -8.87)
FORTALEZA = (-3.73, -38.52)
NEW_YORK = (40.71, -74.0)
MIAMI = (25.77, -80.19)
LONDON = (51.51, -0.13)

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
                t.ip, t.note = ip.strip(), f"overridden via PINGME_OVERRIDE ({t.note})"
                status(f"[yellow]{t.name} overridden to {t.ip}[/yellow]")
    return targets, source


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
        if not t or t.kind != "relay" or t.lat is None or not r.samples:
            continue
        floor = haversine_km(origin, (t.lat, t.lon)) / KM_PER_MS_ROUND_TRIP * CABLE_DETOUR_FACTOR
        gap = min(r.rtts()) - floor
        if best_gap is None or gap < best_gap:
            best_gap, how = gap, f"best RTT to {r.target} minus a direct cable's ~{floor:.0f} ms"
    if best_gap is None:
        return 0.0, how
    return round(max(best_gap, 0.0), 1), how


def analyse(results: list[ProbeResult], targets: list[Target], snapshot: dict) -> dict:
    by_name = {t.name: t for t in targets}
    origin = _origin(snapshot)
    overhead, overhead_how = _local_overhead(results, by_name, origin)
    per_target = {}
    for r in results:
        t = by_name[r.target]
        entry: dict = {
            "ip": r.ip, "kind": t.kind, "error": r.error,
            "route": route_for(r.ip),
            "all": summarise(r.rtts(), r.sent).as_dict(),
            "idle": summarise(r.rtts("idle"), r.sent_in("idle")).as_dict(),
            "busy": summarise(r.rtts("download") + r.rtts("upload"),
                              r.sent_in("download") + r.sent_in("upload")).as_dict(),
            "samples": [(s.seq, s.rtt_ms, round(s.t, 3), s.phase) for s in r.samples],
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


def run(label: str | None, timing: Timing, status=lambda msg: None) -> dict:
    when = dt.datetime.now(dt.UTC)
    status("reading connection details …")
    snapshot = take_snapshot()
    targets, sdr_source = _resolve_targets(status)
    if not targets:
        raise RuntimeError("no targets at all: no default route and no relay list")
    flag_odd_routes(targets, snapshot.get("interface"), status)
    phase = Phase()
    results, speeds, marks = asyncio.run(_orchestrate(targets, timing, phase, status))
    status("crunching numbers …")
    analysis = analyse(results, targets, snapshot)
    record = {
        "id": make_run_id(label, when),
        "label": label,
        "timestamp": when.isoformat(),
        "duration_s": timing.total_s,
        "phase_marks_s": {k: round(v, 2) for k, v in marks.items()},
        "snapshot": snapshot,
        "relay_list_source": sdr_source,
        "targets": [t.as_dict() for t in targets],
        "speed": [s.as_dict() for s in speeds],
        "analysis": analysis,
    }
    record["saved_to"] = str(append_run(record))
    return record
