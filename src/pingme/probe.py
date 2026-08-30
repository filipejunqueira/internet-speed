"""Send many probes to every target at once using the system `ping`, and keep every reply."""

from __future__ import annotations

import asyncio
import re
import shutil
import time
from dataclasses import dataclass, field

REPLY_RE = re.compile(r"icmp_seq=(\d+).*?time=([\d.]+)\s*ms")
INTERVAL_S = 0.2  # smallest interval allowed without root


@dataclass
class Sample:
    seq: int
    rtt_ms: float
    t: float  # seconds since the run started
    phase: str


@dataclass
class ProbeResult:
    target: str
    ip: str
    samples: list[Sample] = field(default_factory=list)
    sent: int = 0
    error: str | None = None

    def rtts(self, phase: str | None = None) -> list[float]:
        return [s.rtt_ms for s in self.samples if phase is None or s.phase == phase]

    def sent_in(self, phase: str | None) -> int:
        if phase is None:
            return self.sent
        seqs = [s.seq for s in self.samples if s.phase == phase]
        if not seqs:
            return 0
        # every sequence number in the phase's span was sent, replied or not
        return max(seqs) - min(seqs) + 1


def parse_reply(line: str) -> tuple[int, float] | None:
    m = REPLY_RE.search(line)
    if not m:
        return None
    return int(m.group(1)), float(m.group(2))


class Phase:
    """Shared, mutable label saying what the connection is doing right now."""

    def __init__(self) -> None:
        self.name = "idle"


async def _ping_one(target: str, ip: str, duration: float, phase: Phase,
                    t0: float, result: ProbeResult) -> None:
    exe = shutil.which("ping")
    if exe is None:
        result.error = "ping not found"
        return
    cmd = [exe, "-n", "-i", str(INTERVAL_S), "-w", str(int(duration) + 1), ip]
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE)
    except OSError as e:
        result.error = str(e)
        return
    assert proc.stdout is not None
    deadline = t0 + duration
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                raw = await asyncio.wait_for(proc.stdout.readline(), timeout=remaining)
            except TimeoutError:
                break
            if not raw:
                break
            line = raw.decode(errors="replace")
            parsed = parse_reply(line)
            if parsed:
                seq, rtt = parsed
                result.samples.append(Sample(seq, rtt, time.monotonic() - t0, phase.name))
                result.sent = max(result.sent, seq)
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)
            except TimeoutError:
                proc.kill()
    # Count what was really sent, from the highest sequence number that came back.
    # An estimate from the clock (duration / INTERVAL_S) overshoots by one probe or
    # more, which invents packet loss on a perfect line. With nothing back at all
    # there is no sequence to read, so the clock estimate is the only option.
    if not result.samples:
        result.sent = int(duration / INTERVAL_S)
        if result.error is None:
            result.error = "no replies"


async def probe_all(targets: list[tuple[str, str]], duration: float, phase: Phase,
                    t0: float) -> list[ProbeResult]:
    results = [ProbeResult(target=n, ip=ip) for n, ip in targets]
    await asyncio.gather(*(_ping_one(r.target, r.ip, duration, phase, t0, r) for r in results))
    return results
