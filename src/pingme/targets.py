"""What we measure against: the local hops plus Valve's Dota relays in four cities."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass

import httpx

from .store import cache_dir

SDR_URL = "https://api.steampowered.com/ISteamApps/GetSDRConfig/v1/?appid=570"
SDR_CACHE_SECONDS = 24 * 3600
# Valve "pop" codes → the short name we show. Nearest to Portugal is Madrid.
WANTED_POPS = {"lhr": "london", "iad": "us-east", "gru": "sao-paulo", "mad": "madrid"}
# Our own (lat, lon) per pop; Valve's file puts Madrid in the Mediterranean.
POP_COORDS = {"lhr": (51.51, -0.13), "iad": (39.01, -77.43), "gru": (-23.55, -46.63),
              "mad": (40.42, -3.70)}


@dataclass
class Target:
    name: str
    ip: str
    kind: str  # "gateway" | "isp-hop" | "relay"
    city: str | None = None
    lat: float | None = None
    lon: float | None = None
    note: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def parse_sdr(config: dict) -> list[Target]:
    """Pick one relay per wanted city out of Valve's published relay list."""
    out = []
    pops = config.get("pops", {})
    for code, name in WANTED_POPS.items():
        pop = pops.get(code)
        if not pop or not pop.get("relays"):
            continue
        lat, lon = POP_COORDS[code]
        out.append(Target(name=name, ip=pop["relays"][0]["ipv4"], kind="relay",
                          city=pop.get("desc"), lat=lat, lon=lon, note=f"valve relay {code}"))
    return out


def fetch_sdr(force: bool = False) -> tuple[dict, str]:
    """Return Valve's relay config and where it came from ("network" or "cache")."""
    cache = cache_dir() / "sdr.json"
    if not force and cache.exists() and time.time() - cache.stat().st_mtime < SDR_CACHE_SECONDS:
        return json.loads(cache.read_text()), "cache"
    try:
        r = httpx.get(SDR_URL, timeout=20)
        r.raise_for_status()
        cache.write_text(r.text)
        return r.json(), "network"
    except Exception as e:  # noqa: BLE001 - any failure falls back to the stale cache
        if cache.exists():
            return json.loads(cache.read_text()), f"stale cache ({type(e).__name__})"
        raise


def default_route() -> tuple[str | None, str | None]:
    """(gateway ip, interface name) of the default IPv4 route."""
    try:
        out = subprocess.run(["ip", "-j", "route", "show", "default"], capture_output=True,
                             text=True, timeout=5, check=False).stdout
        routes = json.loads(out or "[]")
    except (OSError, json.JSONDecodeError):
        return None, None
    if not routes:
        return None, None
    routes.sort(key=lambda r: r.get("metric", 0))
    return routes[0].get("gateway"), routes[0].get("dev")


def first_hop_beyond_gateway(probe_ip: str = "1.1.1.1") -> str | None:
    """Second hop on the way out, or None when the provider hides it."""
    try:
        out = subprocess.run(["mtr", "-4", "-r", "-n", "-c", "2", probe_ip], capture_output=True,
                             text=True, timeout=40, check=False).stdout
    except OSError:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) > 2 and parts[0].startswith("2.|--"):
            return None if parts[1] == "???" else parts[1]
    return None


def local_targets() -> list[Target]:
    out = []
    gw, dev = default_route()
    if gw:
        out.append(Target(name="router", ip=gw, kind="gateway", note=f"default gateway via {dev}"))
    hop = first_hop_beyond_gateway()
    if hop:
        out.append(Target(name="isp-hop", ip=hop, kind="isp-hop", note="first hop past the router"))
    return out
