import ipaddress
import socket

from urllib.parse import urlsplit

TRUSTED_URLS = {
    "https://example.com/",
    "https://github.com/",
    "https://www.python.org/",
    "https://opal.com/"

}

def is_public_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False

def resolve_ips(hostname: str) -> set[str]:
    try:
        results = socket.getaddrinfo(
            hostname,
            None,
            type=socket.SOCK_STREAM
        )
    except socket.gaierror:
        return set()

    ips = set()

    for result in results:
        ips.add(result[4][0])
    return ips

def is_public_hostname(hostname: str) -> bool:
    ips = resolve_ips(hostname)

    if ips == set():
        return False

    return all(is_public_ip(ip) for ip in ips)

def validate_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)

        if parsed.scheme not in ("http", "https"):
            return False

        if parsed.hostname is None:
            return False

        if parsed.username is not None or parsed.password is not None:
            return False

        if parsed.scheme == "http" and parsed.port not in (None, 80):
            return False

        if parsed.scheme == "https" and parsed.port not in (None, 443):
            return False

        return is_public_hostname(parsed.hostname)

    except ValueError:
        return False