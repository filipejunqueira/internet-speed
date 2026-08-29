"""Hop-by-hop route to a target via `traceroute -I`, keeping hidden hops as hidden.

ICMP mode works without root here, and unlike `mtr` it keeps going through long
runs of silent hops until the target answers.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass

HOP_RE = re.compile(r"^\s*(\d+)\s+(.*)$")
IP_RE = re.compile(r"(\d+\.\d+\.\d+\.\d+|[0-9a-fA-F:]+:[0-9a-fA-F:]*)")
MS_RE = re.compile(r"([\d.]+)\s*ms")


@dataclass
class Hop:
    n: int
    ip: str | None  # None when the router did not answer
    avg_ms: float | None
    loss_pct: float | None

    def as_dict(self) -> dict:
        return asdict(self)


def parse_traceroute(output: str, queries: int = 3) -> list[Hop]:
    hops = []
    for line in output.splitlines():
        m = HOP_RE.match(line)
        if not m or line.startswith("traceroute"):
            continue
        n, rest = int(m.group(1)), m.group(2)
        ip = IP_RE.search(rest)
        times = [float(x) for x in MS_RE.findall(rest)]
        if ip is None or not times:
            hops.append(Hop(n, None, None, None))
        else:
            loss = 100.0 * (queries - len(times)) / queries
            hops.append(Hop(n, ip.group(1), round(sum(times) / len(times), 1), round(loss, 1)))
    return hops


def trace(ip: str, family: int = 4, queries: int = 3) -> tuple[list[Hop], str | None]:
    """Returns (hops, error). Everything after the hop where the target answered is dropped."""
    cmd = ["traceroute", f"-{family}", "-I", "-n", "-q", str(queries), "-w", "2", "-m", "40", ip]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    except FileNotFoundError:
        return [], "traceroute not installed"
    except subprocess.TimeoutExpired:
        return [], "traceroute timed out"
    if not p.stdout.strip():
        return [], (p.stderr.strip() or f"traceroute exit {p.returncode}")
    hops = parse_traceroute(p.stdout, queries)
    for i, h in enumerate(hops):
        if h.ip == ip:
            return hops[: i + 1], None
    return hops, None
