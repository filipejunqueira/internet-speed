"""Send many probes to every target at once using the system `ping`, and keep every reply."""

from __future__ import annotations

import asyncio
import re
import shutil
import time
from dataclasses import dataclass, field

REPLY_RE = re.compile(r"icmp_seq=(\d+).*?time=([\d.]+)\s*ms")
SUMMARY_RE = re.compile(r"(\d+) packets transmitted")
INTERVAL_S = 0.2  # smallest interval allowed without root
REPLY_WAIT_S = 2  # how long ping waits for the last replies once it has sent everything


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


def parse_reply(line: str) -> tuple[int, float] | None:
    m = REPLY_RE.search(line)
    if not m:
        return None
    return int(m.group(1)), float(m.group(2))


def parse_summary(line: str) -> int | None:
    """How many probes ping says it sent, from its closing statistics line."""
    m = SUMMARY_RE.search(line)
    return int(m.group(1)) if m else None


def send_offset(samples: list[Sample]) -> float:
    """When probe 1 left, in seconds since the run started.

    ping sends on a fixed schedule, so probe k leaves at offset + (k - 1) * INTERVAL_S.
    Every reply gives one estimate of that offset: the moment it came back, less its own
    round trip, less its place in the schedule. The median ignores the odd late one.
    """
    if not samples:
        return 0.0
    est = sorted(s.t - s.rtt_ms / 1000.0 - (s.seq - 1) * INTERVAL_S for s in samples)
    mid = len(est) // 2
    return est[mid] if len(est) % 2 else (est[mid - 1] + est[mid]) / 2.0


def send_time(seq: int, offset: float) -> float:
    """When probe `seq` left, in seconds since the run started."""
    return offset + (seq - 1) * INTERVAL_S


def probe_count(duration: float) -> int:
    """How many probes a run of this length sends to each target."""
    return max(1, int(duration / INTERVAL_S))


def ping_command(exe: str, ip: str, duration: float) -> list[str]:
    """The ping to run for one target.

    -c on its own means "send exactly this many, then wait for the replies still on
    their way". Do not add -w: with a deadline, -c instead means "until this many are
    answered", and ping abandons the probe still in flight. Sao Paulo answers in 210 ms
    while probes leave every 200 ms, so one is always in flight, and a run that lost
    nothing reported 0.7 % loss. Checked both ways on 2026-09-03.
    """
    return [exe, "-n", "-c", str(probe_count(duration)), "-i", str(INTERVAL_S),
            "-W", str(REPLY_WAIT_S), ip]


class Phase:
    """Shared, mutable label saying what the connection is doing right now."""

    def __init__(self) -> None:
        self.name = "idle"


async def _read(stdout: asyncio.StreamReader, phase: Phase, t0: float,
                result: ProbeResult) -> None:
    """Read ping to the end of its output, keeping every reply and its own sent count."""
    while True:
        raw = await stdout.readline()
        if not raw:
            return
        line = raw.decode(errors="replace")
        parsed = parse_reply(line)
        if parsed:
            seq, rtt = parsed
            result.samples.append(Sample(seq, rtt, time.monotonic() - t0, phase.name))
            result.sent = max(result.sent, seq)  # stands in until the summary arrives
            continue
        transmitted = parse_summary(line)
        if transmitted is not None:
            # ping's own count is exact, and unlike the highest sequence number that
            # came back it also counts the probes sent after the last reply.
            result.sent = transmitted


async def _stop(proc: asyncio.subprocess.Process) -> None:
    """Wait for ping to exit, and end it if it will not."""
    try:
        await asyncio.wait_for(proc.wait(), timeout=3)
    except TimeoutError:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=3)
        except TimeoutError:
            proc.kill()


async def _note_failure(proc: asyncio.subprocess.Process, result: ProbeResult) -> None:
    """Say why ping gave up. Exit code 1 is "nothing answered", which is a measurement."""
    if result.error is not None or proc.returncode is None or proc.returncode < 2:
        return
    if proc.stderr is None:
        result.error = f"ping exited {proc.returncode}"
        return
    try:
        raw = await asyncio.wait_for(proc.stderr.read(), timeout=3)
    except TimeoutError:
        raw = b""
    lines = [ln.strip() for ln in raw.decode(errors="replace").splitlines() if ln.strip()]
    result.error = lines[-1] if lines else f"ping exited {proc.returncode}"


async def _ping_one(target: str, ip: str, duration: float, phase: Phase,
                    t0: float, result: ProbeResult) -> None:
    exe = shutil.which("ping")
    if exe is None:
        result.error = "ping not found"
        return
    count = probe_count(duration)
    cmd = ping_command(exe, ip, duration)
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE)
    except OSError as e:
        result.error = str(e)
        return
    assert proc.stdout is not None
    try:
        await asyncio.wait_for(_read(proc.stdout, phase, t0, result),
                               timeout=duration + REPLY_WAIT_S + 5)
    except TimeoutError:
        result.error = "ping did not finish in time"
    finally:
        await _stop(proc)
    await _note_failure(proc, result)
    if result.sent == 0:
        # Neither a summary line nor a reply: fall back to what we asked ping for.
        result.sent = count


async def probe_all(targets: list[tuple[str, str]], duration: float, phase: Phase,
                    t0: float) -> list[ProbeResult]:
    results = [ProbeResult(target=n, ip=ip) for n, ip in targets]
    await asyncio.gather(*(_ping_one(r.target, r.ip, duration, phase, t0, r) for r in results))
    return results
