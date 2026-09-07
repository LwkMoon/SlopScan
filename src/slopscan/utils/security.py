"""SSRF protection for the URL/website target (spec section 33).

The core idea: never let SlopScan become a proxy that fetches arbitrary
internal/private resources on the caller's behalf. This means checking not
just the hostname string, but the IP address(es) it actually resolves to
-- including on every redirect hop, since "resolve once, fetch elsewhere"
(DNS rebinding) is exactly the kind of thing naive SSRF guards miss.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}


class UnsafeURLError(Exception):
    pass


@dataclass
class ResolvedTarget:
    hostname: str
    port: int
    scheme: str
    ip_addresses: list[str]


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # can't parse it -> treat as unsafe
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        return True
    if ip.is_unspecified:
        return True
    # IPv4-mapped IPv6 / 6to4 that unwrap to private ranges
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return _is_blocked_ip(str(ip.ipv4_mapped))
    # Cloud metadata endpoint (also covered by link-local, but explicit for clarity)
    if ip_str == "169.254.169.254":
        return True
    return False


def validate_url(url: str) -> ResolvedTarget:
    """Raise UnsafeURLError if the URL is unsafe to fetch; otherwise return
    the resolved target info (used for logging/evidence, and so callers can
    pin the connection to a checked IP if desired)."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Unsupported URL scheme: {parsed.scheme!r} (only http/https are allowed)")
    if not parsed.hostname:
        raise UnsafeURLError("URL has no hostname")

    hostname = parsed.hostname.lower()
    if hostname in ("localhost", "localhost.localdomain") or hostname.endswith(".local"):
        raise UnsafeURLError(f"Refusing to fetch local/loopback host: {hostname}")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    try:
        infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve host: {hostname} ({exc})") from exc

    ip_addresses: list[str] = sorted({str(info[4][0]) for info in infos})
    if not ip_addresses:
        raise UnsafeURLError(f"Host resolved to no addresses: {hostname}")

    for ip_str in ip_addresses:
        if _is_blocked_ip(ip_str):
            raise UnsafeURLError(
                f"Refusing to fetch {hostname}: resolves to a private/internal/reserved address ({ip_str})"
            )

    return ResolvedTarget(hostname=hostname, port=port, scheme=parsed.scheme, ip_addresses=ip_addresses)
