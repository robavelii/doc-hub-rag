"""Widget domain allowlist validation."""

from urllib.parse import urlparse


def extract_hostname(origin_or_url: str) -> str | None:
    value = origin_or_url.strip()
    if not value:
        return None
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower().strip(".")
    return hostname or None


def is_domain_allowed(origin: str, allowed_domains: list[str]) -> bool:
    if not allowed_domains:
        return True

    hostname = extract_hostname(origin)
    if not hostname:
        return False

    for allowed in allowed_domains:
        domain = allowed.lower().strip().strip(".")
        if not domain:
            continue
        if domain.startswith("*."):
            suffix = domain[2:]
            if hostname == suffix or hostname.endswith(f".{suffix}"):
                return True
        elif hostname == domain or hostname.endswith(f".{domain}"):
            return True

    return False
