"""One-off facts about the connection at the moment of the run."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import httpx

from .targets import default_route


def _run(cmd: list[str], timeout: float = 5) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              check=False).stdout
    except OSError:
        return ""


def wifi_details(dev: str) -> dict | None:
    link = _run(["iw", "dev", dev, "link"])
    if "Connected to" not in link:
        return None
    info = _run(["iw", "dev", dev, "info"])
    d: dict = {"ssid": None, "freq_mhz": None, "channel": None, "width_mhz": None,
               "signal_dbm": None, "rx_bitrate_mbps": None, "tx_bitrate_mbps": None,
               "generation": None}
    m = re.search(r"SSID:\s*(.+)", link)
    d["ssid"] = m.group(1).strip() if m else None
    m = re.search(r"freq:\s*([\d.]+)", link)
    d["freq_mhz"] = float(m.group(1)) if m else None
    m = re.search(r"signal:\s*(-?\d+)\s*dBm", link)
    d["signal_dbm"] = int(m.group(1)) if m else None
    for key, label in (("rx_bitrate_mbps", "rx bitrate"), ("tx_bitrate_mbps", "tx bitrate")):
        m = re.search(label + r":\s*([\d.]+)\s*MBit/s(.*)", link)
        if m:
            d[key] = float(m.group(1))
            rest = m.group(2)
            if "EHT" in rest:
                d["generation"] = "Wi-Fi 7"
            elif "HE" in rest:
                d["generation"] = "Wi-Fi 6"
            elif "VHT" in rest:
                d["generation"] = "Wi-Fi 5"
            elif "MCS" in rest:  # plain "MCS n" with no HE/VHT prefix is 802.11n
                d["generation"] = "Wi-Fi 4"
    m = re.search(r"channel\s+(\d+)\s+\((\d+) MHz\),\s*width:\s*(\d+) MHz", info)
    if m:
        d["channel"] = int(m.group(1))
        d["width_mhz"] = int(m.group(3))
    return d


def ethernet_details(dev: str) -> dict | None:
    base = Path("/sys/class/net") / dev
    if not base.exists():
        return None
    try:
        speed = int((base / "speed").read_text().strip())
    except (OSError, ValueError):
        speed = None
    try:
        duplex = (base / "duplex").read_text().strip()
    except OSError:
        duplex = None
    return {"link_speed_mbps": speed, "duplex": duplex}


def is_wireless(dev: str) -> bool:
    return (Path("/sys/class/net") / dev / "wireless").exists()


def public_ip() -> dict:
    """Public address, provider and rough location. Empty dict if it cannot be looked up."""
    try:
        r = httpx.get("http://ip-api.com/json/?fields=query,isp,as,country,city,lat,lon",
                      timeout=10)
        r.raise_for_status()
        j = r.json()
        return {"ip": j.get("query"), "isp": j.get("isp"), "asn": j.get("as"),
                "country": j.get("country"), "city": j.get("city"),
                "lat": j.get("lat"), "lon": j.get("lon")}
    except Exception as e:  # noqa: BLE001
        return {"error": type(e).__name__}


def route_for(ip: str) -> dict:
    """Which interface a packet to `ip` leaves through, per the kernel."""
    out = _run(["ip", "-j", "route", "get", ip])
    try:
        r = json.loads(out or "[]")
    except json.JSONDecodeError:
        r = []
    if not r:
        return {"dev": None, "src": None, "gateway": None}
    return {"dev": r[0].get("dev"), "src": r[0].get("prefsrc"), "gateway": r[0].get("gateway")}


def take_snapshot() -> dict:
    gw, dev = default_route()
    snap: dict = {"interface": dev, "gateway": gw, "medium": None, "wifi": None,
                  "ethernet": None, "public": public_ip()}
    if dev:
        if is_wireless(dev):
            snap["medium"] = "wifi"
            snap["wifi"] = wifi_details(dev)
        else:
            snap["medium"] = "ethernet"
            snap["ethernet"] = ethernet_details(dev)
    return snap
