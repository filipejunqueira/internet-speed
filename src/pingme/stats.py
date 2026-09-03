"""Pure statistics over a list of round-trip times. No I/O here, so it is easy to test."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from math import asin, cos, radians, sin, sqrt

import numpy as np

# Light in glass fibre travels ~200 km per ms, so a round trip costs ~1 ms per 100 km.
KM_PER_MS_ROUND_TRIP = 100.0
# Real cables are not great circles; this is the usual allowance.
CABLE_DETOUR_FACTOR = 1.3


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
    """Mean absolute difference between consecutive round trips (the RFC 3550 idea)."""
    if len(rtts) < 2:
        return 0.0
    a = np.asarray(rtts, dtype=float)
    return float(np.abs(np.diff(a)).mean())


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
