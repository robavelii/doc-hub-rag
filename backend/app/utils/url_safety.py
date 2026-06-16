"""SSRF protection for URL fetching."""

import ipaddress
import socket
from urllib.parse import urlparse

from app.config import settings

BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.google",
    }
)

MAX_REDIRECTS = 3


class UnsafeUrlError(ValueError):
    pass


def _is_blocked_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
        or str(addr) == "169.254.169.254"
    )


def resolve_hostname(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"Cannot resolve hostname: {hostname}") from exc

    addresses: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if sockaddr:
            addresses.append(sockaddr[0])
    if not addresses:
        raise UnsafeUrlError(f"No addresses resolved for hostname: {hostname}")
    return addresses


def validate_url_for_fetch(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError(f"Unsupported URL scheme: {parsed.scheme}")

    if settings.APP_ENV == "production" and parsed.scheme != "https":
        raise UnsafeUrlError("Only HTTPS URLs are allowed in production")

    hostname = (parsed.hostname or "").lower().strip(".")
    if not hostname:
        raise UnsafeUrlError("URL must include a hostname")

    if hostname in BLOCKED_HOSTNAMES:
        raise UnsafeUrlError(f"Blocked hostname: {hostname}")

    for label in hostname.split("."):
        if label == "metadata" or label.endswith("internal"):
            raise UnsafeUrlError(f"Blocked hostname pattern: {hostname}")

    for addr_str in resolve_hostname(hostname):
        try:
            addr = ipaddress.ip_address(addr_str)
        except ValueError as exc:
            raise UnsafeUrlError(f"Invalid resolved address: {addr_str}") from exc
        if _is_blocked_ip(addr):
            raise UnsafeUrlError(f"URL resolves to blocked address: {addr_str}")

    return url
