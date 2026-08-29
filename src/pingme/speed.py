"""Download and upload throughput against Cloudflare for a fixed number of seconds."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import httpx

DOWN_URL = "https://speed.cloudflare.com/__down?bytes={n}"
UP_URL = "https://speed.cloudflare.com/__up"
STREAMS = 3
SAMPLE_EVERY_S = 0.25
CHUNK = 64 * 1024
REQUEST_BYTES = 25_000_000  # Cloudflare refuses anything over 50 MB per request


@dataclass
class SpeedResult:
    direction: str
    bytes_total: int
    seconds: float
    mbps: float
    samples_mbps: list[float] = field(default_factory=list)  # throughput over time
    server: str | None = None
    error: str | None = None

    def as_dict(self) -> dict:
        return {"direction": self.direction, "bytes_total": self.bytes_total,
                "seconds": self.seconds, "mbps": self.mbps,
                "samples_mbps": [round(x, 2) for x in self.samples_mbps],
                "server": self.server, "error": self.error}


class _Counter:
    def __init__(self) -> None:
        self.n = 0


async def _download(client: httpx.AsyncClient, c: _Counter, deadline: float) -> None:
    while time.monotonic() < deadline:
        async with client.stream("GET", DOWN_URL.format(n=REQUEST_BYTES)) as r:
            r.raise_for_status()
            async for chunk in r.aiter_bytes(CHUNK):
                c.n += len(chunk)
                if time.monotonic() >= deadline:
                    return


async def _upload(client: httpx.AsyncClient, c: _Counter, deadline: float) -> None:
    block = b"\0" * CHUNK

    async def gen():
        while time.monotonic() < deadline:
            c.n += len(block)
            yield block

    while time.monotonic() < deadline:
        await client.post(UP_URL, content=gen())


async def _sample(c: _Counter, stop: asyncio.Event, out: list[float]) -> None:
    last_n, last_t = 0, time.monotonic()
    while not stop.is_set():
        await asyncio.sleep(SAMPLE_EVERY_S)
        now, n = time.monotonic(), c.n
        dt = now - last_t
        if dt > 0:
            out.append((n - last_n) * 8 / dt / 1e6)
        last_n, last_t = n, now


async def _run(direction: str, seconds: float) -> SpeedResult:
    c, stop, samples = _Counter(), asyncio.Event(), []
    worker = _download if direction == "download" else _upload
    server = None
    t0 = time.monotonic()
    deadline = t0 + seconds
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=15)) as client:
            try:
                trace = await client.get("https://speed.cloudflare.com/cdn-cgi/trace")
                for line in trace.text.splitlines():
                    if line.startswith("colo="):
                        server = line.split("=", 1)[1]
            except httpx.HTTPError:
                pass
            sampler = asyncio.create_task(_sample(c, stop, samples))
            await asyncio.gather(*(worker(client, c, deadline) for _ in range(STREAMS)))
            stop.set()
            await sampler
    except Exception as e:  # noqa: BLE001
        stop.set()
        secs = time.monotonic() - t0
        return SpeedResult(direction, c.n, round(secs, 2), 0.0, samples, server,
                           error=f"{type(e).__name__}: {e}")
    secs = time.monotonic() - t0
    mbps = c.n * 8 / secs / 1e6 if secs > 0 else 0.0
    return SpeedResult(direction, c.n, round(secs, 2), round(mbps, 1), samples, server)


async def download(seconds: float) -> SpeedResult:
    return await _run("download", seconds)


async def upload(seconds: float) -> SpeedResult:
    return await _run("upload", seconds)
