"""SSRF guard for user-supplied agent endpoint URLs.

The "bring your own agent" flow accepts an HTTP endpoint from the client and the
server then makes outbound requests to it. Without a guard that is a classic
server-side request forgery (SSRF) surface — a caller could point DUAT at
internal services, cloud metadata, or loopback. `validate_public_url` resolves
the host and rejects anything that is not a public address.

Stdlib only. DNS resolution is the one external touch; tests monkeypatch
`socket.getaddrinfo` to stay networkless.
"""

import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}


def _is_blocked(ip: ipaddress._BaseAddress) -> bool:
    """True if `ip` is anything other than a normal public address.

    Unwraps IPv4-mapped IPv6 first so a mapped loopback/private address cannot
    slip through as a "v6" address.
    """
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_public_url(url: str) -> str:
    """Return the URL if it targets a public host, else raise ValueError.

    Rejects non-http(s) schemes, missing hosts, unresolvable hosts, and any host
    that resolves to a loopback/private/link-local/reserved/multicast address
    (including cloud metadata at 169.254.169.254).
    """
    if not url or not isinstance(url, str):
        raise ValueError("endpoint must be a non-empty URL")

    parsed = urlparse(url.strip())
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError("endpoint must use the http or https scheme")

    host = parsed.hostname
    if not host:
        raise ValueError("endpoint must include a host")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"endpoint host could not be resolved: {host}") from exc

    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise ValueError(f"endpoint host could not be resolved: {host}")

    for address in addresses:
        if _is_blocked(ipaddress.ip_address(address)):
            raise ValueError(
                f"endpoint resolves to a non-public address ({address}); "
                "loopback, private, and metadata hosts are not allowed"
            )

    return url.strip()
