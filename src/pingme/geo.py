"""Best-effort location of a router from its IP address, with the source of the guess kept."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import asdict, dataclass

import httpx

# City codes that often appear in router hostnames, e.g. "ae1.lhr2.core.example.net".
CITY_CODES = {
    "lhr": ("London", 51.51, -0.13), "lon": ("London", 51.51, -0.13),
    "man": ("Manchester", 53.48, -2.24), "ams": ("Amsterdam", 52.37, 4.9),
    "fra": ("Frankfurt", 50.11, 8.68), "par": ("Paris", 48.86, 2.35),
    "cdg": ("Paris", 48.86, 2.35),
    "mad": ("Madrid", 40.42, -3.7), "lis": ("Lisbon", 38.72, -9.14),
    "mrs": ("Marseille", 43.3, 5.37),
    "nyc": ("New York", 40.71, -74.0), "jfk": ("New York", 40.71, -74.0),
    "ewr": ("Newark", 40.74, -74.17), "iad": ("Ashburn", 39.04, -77.49),
    "dca": ("Washington", 38.9, -77.04), "mia": ("Miami", 25.77, -80.19),
    "atl": ("Atlanta", 33.75, -84.39), "ord": ("Chicago", 41.88, -87.63),
    "dfw": ("Dallas", 32.78, -96.8), "lax": ("Los Angeles", 34.05, -118.24),
    "sjc": ("San Jose", 37.34, -121.89), "sea": ("Seattle", 47.61, -122.33),
    "gru": ("São Paulo", -23.55, -46.63), "gig": ("Rio de Janeiro", -22.91, -43.17),
    "for": ("Fortaleza", -3.73, -38.52), "eze": ("Buenos Aires", -34.6, -58.38),
    "scl": ("Santiago", -33.45, -70.67), "bog": ("Bogotá", 4.71, -74.07),
}


@dataclass
class Location:
    ip: str
    lat: float | None
    lon: float | None
    city: str | None
    source: str  # "private", "hostname:<code>", "ripe-ipmap", "ip-api", "unknown"
    hostname: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def _is_private(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    cgnat = a.version == 4 and a in ipaddress.ip_network("100.64.0.0/10")
    return a.is_private or a.is_link_local or cgnat


def _hostname(ip: str) -> str | None:
    try:
        return socket.gethostbyaddr(ip)[0]
    except (OSError, socket.herror):
        return None


def _from_hostname(host: str) -> tuple[str, float, float, str] | None:
    parts = host.lower().replace("-", ".").replace("_", ".").split(".")
    for part in parts:
        for code, (city, lat, lon) in CITY_CODES.items():
            if part == code or (part.startswith(code) and part[len(code):].isdigit()):
                return city, lat, lon, code
    return None


def _ripe_ipmap(client: httpx.Client, ip: str) -> tuple[str | None, float, float] | None:
    try:
        r = client.get(f"https://ipmap-api.ripe.net/v1/locate/{ip}/best", timeout=10)
        loc = r.json().get("location")
        if loc and loc.get("latitude") is not None:
            return loc.get("cityName"), float(loc["latitude"]), float(loc["longitude"])
    except (httpx.HTTPError, ValueError):
        pass
    return None


def _ip_api(client: httpx.Client, ip: str) -> tuple[str | None, float, float] | None:
    try:
        r = client.get(f"http://ip-api.com/json/{ip}?fields=status,city,lat,lon", timeout=10)
        j = r.json()
        if j.get("status") == "success":
            return j.get("city"), float(j["lat"]), float(j["lon"])
    except (httpx.HTTPError, ValueError, KeyError):
        pass
    return None


def locate(ip: str, origin: tuple[float, float], client: httpx.Client | None = None) -> Location:
    if _is_private(ip):
        return Location(ip, origin[0], origin[1], "local network", "private")
    host = _hostname(ip)
    if host:
        hit = _from_hostname(host)
        if hit:
            city, lat, lon, code = hit
            return Location(ip, lat, lon, city, f"hostname:{code}", host)
    own = client is None
    client = client or httpx.Client()
    try:
        for source, fn in (("ripe-ipmap", _ripe_ipmap), ("ip-api", _ip_api)):
            hit = fn(client, ip)
            if hit:
                city, lat, lon = hit
                return Location(ip, lat, lon, city, source, host)
    finally:
        if own:
            client.close()
    return Location(ip, None, None, None, "unknown", host)
