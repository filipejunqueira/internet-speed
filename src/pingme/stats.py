"""Pure statistics over a list of round-trip times. No I/O here, so it is easy to test."""

from __future__ import annotations

import bisect
from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from math import asin, cos, radians, sin, sqrt

import numpy as np

# Light in glass fibre travels ~200 km per ms, so a round trip costs ~1 ms per 100 km.
KM_PER_MS_ROUND_TRIP = 100.0
# Real cables are not great circles; this is the usual allowance.
CABLE_DETOUR_FACTOR = 1.3
# A spike is an idle sample this far above that target's own idle mean. 30 ms is the
# same number as SPIKE_OVER in the vpn project's dota-lat.sh, on purpose: its rule
# "more than twice the control run's spike count" only means something if the two
# tools are counting the same thing.
SPIKE_OVER_MS = 30.0
# Two spikes no further apart than this belong to the same stall. Probes leave every
# 0.2 s, so this is ten intervals: wide enough to join a stall that happened to spare
# a probe in the middle, narrow enough to keep two separate stalls apart. On the
# 10-minute Santander run no two spikes fell between 1.9 s and 2.1 s apart, so the
# exact boundary never arises there and the choice of <= over < changes nothing.
EPISODE_GAP_S = 2.0
# How close a target's spike has to be to a router spike to count as the same stall.
COINCIDENCE_WINDOW_S = 1.0


@dataclass
class Summary:
    sent: int
    received: int
    loss_pct: float | None
    min_ms: float | None
    median_ms: float | None
    mean_ms: float | None
    p95_ms: float | None
    p99_ms: float | None
    max_ms: float | None
    stdev_ms: float | None
    jitter_ms: float | None

    def as_dict(self) -> dict:
        return asdict(self)

    def without_loss(self) -> Summary:
        """The same numbers with no loss figure, for a target that never answers at all."""
        return replace(self, loss_pct=None)


def summarise(rtts: list[float], sent: int) -> Summary:
    """Summarise the replies that came back out of `sent` probes."""
    received = len(rtts)
    loss = 0.0 if sent == 0 else 100.0 * (sent - received) / sent
    if received == 0:
        return Summary(sent, 0, loss, None, None, None, None, None, None, None, None)
    a = np.asarray(rtts, dtype=float)
    return Summary(
        sent=sent,
        received=received,
        loss_pct=round(loss, 2),
        min_ms=round(float(a.min()), 3),
        median_ms=round(float(np.median(a)), 3),
        mean_ms=round(float(a.mean()), 3),
        p95_ms=round(float(np.percentile(a, 95)), 3),
        p99_ms=round(float(np.percentile(a, 99)), 3),
        max_ms=round(float(a.max()), 3),
        stdev_ms=round(float(a.std(ddof=0)), 3),
        jitter_ms=round(jitter(rtts), 3),
    )


def lost_seqs(sent: int, replied: Iterable[int]) -> list[int]:
    """The sequence numbers among the first `sent` probes that never came back."""
    seen = set(replied)
    return [n for n in range(1, sent + 1) if n not in seen]


def longest_burst(lost: list[int]) -> tuple[int, int]:
    """Length and first sequence number of the longest run of consecutive losses.

    `lost` must be ascending. A burst is what a game actually feels: ten losses in a
    row freeze it, while ten spread over a minute pass unnoticed. Ties go to the
    earliest burst. Nothing lost gives (0, 0).
    """
    best: tuple[int, int] = (0, 0)
    start = 0
    previous = None
    for n in lost:
        if previous is None or n != previous + 1:
            start = n
        previous = n
        if n - start + 1 > best[0]:
            best = (n - start + 1, start)
    return best


def jitter(rtts: list[float]) -> float:
    """Mean absolute difference between consecutive round trips (the RFC 3550 idea).

    Consecutive *replies*, not consecutive probes: when the probe between two replies
    was lost, the jump spans two send intervals instead of one, so a lossy run reads
    slightly high.
    """
    if len(rtts) < 2:
        return 0.0
    a = np.asarray(rtts, dtype=float)
    return float(np.abs(np.diff(a)).mean())


def spike_times(samples: list[tuple], threshold_ms: float = SPIKE_OVER_MS
                ) -> tuple[list[float], float | None]:
    """When this target stalled while the line was idle, and the mean it is judged against.

    `samples` is the stored form: (seq, rtt_ms, seconds since the run began, phase).
    Only idle samples count, because the speed test slows everything down on purpose
    and those milliseconds are not a stall. Returns the spike times in ascending order
    and the mean of the idle round trips. No idle samples at all gives ([], None):
    nobody could count, which is not the same as counting none.
    """
    idle = [(float(t), float(rtt)) for _seq, rtt, t, phase in samples if phase == "idle"]
    if not idle:
        return [], None
    mean = float(np.asarray([rtt for _t, rtt in idle], dtype=float).mean())
    return sorted(t for t, rtt in idle if rtt > mean + threshold_ms), mean


def episodes(times: list[float], gap_s: float = EPISODE_GAP_S) -> list[dict]:
    """Group spike times into stalls: spikes no further apart than gap_s are one stall.

    `times` must be ascending. Each episode says when it started, how long it lasted
    and how many spikes it holds; a lone spike is an episode of length 0.0 holding one.
    """
    out: list[dict] = []
    group: list[float] = []
    for t in times:
        if group and t - group[-1] > gap_s:
            out.append(_episode(group))
            group = []
        group.append(t)
    if group:
        out.append(_episode(group))
    return out


def _episode(group: list[float]) -> dict:
    return {"at_s": round(group[0], 2), "length_s": round(group[-1] - group[0], 2),
            "probes": len(group)}


def coincidence(target_times: list[float], router_times: list[float],
                window_s: float = COINCIDENCE_WINDOW_S) -> float | None:
    """The share of this target's spikes that a router spike happened alongside, 0 to 1.

    The router is pinged at the same instant as every relay, so it is the one witness
    we have. Near 1 means the local link stalled and this target merely inherited it;
    near 0 means the stall was further out, on the route. None when there is nothing to
    take a share of (this target never spiked) or no witness (the router never spiked,
    or there is no router in the run). Never raises.
    """
    if not target_times or not router_times:
        return None
    ordered = sorted(router_times)
    near = 0
    for t in target_times:
        i = bisect.bisect_left(ordered, t)
        # only the router spike either side of t can be the nearest one
        if any(abs(ordered[j] - t) <= window_s for j in (i - 1, i) if 0 <= j < len(ordered)):
            near += 1
    return round(near / len(target_times), 2)


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between two (lat, lon) points in km."""
    la1, lo1 = map(radians, a)
    la2, lo2 = map(radians, b)
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(h))


def path_km(points: list[tuple[float, float]]) -> float:
    return sum(haversine_km(points[i], points[i + 1]) for i in range(len(points) - 1))


@dataclass
class RouteCandidate:
    name: str
    waypoints: list[tuple[float, float]]  # (lat, lon), origin and target are added by the caller


@dataclass
class RouteVerdict:
    name: str
    km: float
    floor_ms: float
    realistic_ms: float
    ruled_out: bool


def physics_verdict(
    best_rtt_ms: float,
    local_overhead_ms: float,
    origin: tuple[float, float],
    target: tuple[float, float],
    candidates: list[RouteCandidate],
) -> tuple[float, list[RouteVerdict], str | None]:
    """Compare the best round trip seen with how long each candidate route would take.

    Returns (effective_ms, verdicts, name of the most consistent route or None).
    A route is ruled out when even its physical floor is slower than what we measured.
    """
    effective = max(best_rtt_ms - local_overhead_ms, 0.0)
    verdicts = []
    for c in candidates:
        km = path_km([origin, *c.waypoints, target])
        floor = km / KM_PER_MS_ROUND_TRIP
        realistic = floor * CABLE_DETOUR_FACTOR
        verdicts.append(RouteVerdict(c.name, round(km), round(floor, 1), round(realistic, 1),
                                     ruled_out=floor > effective))
    possible = [v for v in verdicts if not v.ruled_out]
    if not possible:
        return effective, verdicts, None
    closest = min(possible, key=lambda v: abs(v.realistic_ms - effective))
    return effective, verdicts, closest.name
