"""Enterprise-grade SSRF protection for all outbound HTTP from Nexora.

Every outbound HTTP request the platform makes on behalf of a tenant uses a
*customer-supplied* URL (integration ``base_url``/``endpoint``, OAuth token
hosts, etc.). Without guards, an authenticated tenant could coerce the server
into requesting internal/metadata endpoints (classic SSRF). This module is the
single, shared chokepoint that makes those requests safe.

What it enforces
----------------
* **Scheme allow-list** — only ``http``/``https`` (blocks ``file://``,
  ``gopher://``, ``ftp://`` and friends).
* **Port validation** — rejects port 0/out-of-range and a denylist of sensitive
  service ports; an explicit allow-list may be supplied for stricter policies.
* **DNS resolution + IP validation** — the hostname is resolved and *every*
  resolved A/AAAA address is checked. IP literals are checked directly.
* **Blocked address space** — loopback (127.0.0.0/8, ::1), link-local
  (169.254.0.0/16, fe80::/10), private RFC-1918 (10/8, 172.16/12, 192.168/16),
  unique-local (fc00::/7), multicast, reserved, unspecified, and the cloud
  metadata endpoints (AWS/Azure/GCP ``169.254.169.254`` and ``fd00:ec2::254``).
* **Redirect validation** — redirects are disabled by default; when a caller
  explicitly opts in, the validating transport re-checks *every* redirect hop,
  so an allowed first host cannot bounce the request to an internal target.

Public API (per the security spec)
-----------------------------------
* :func:`validate_ip` — validate a single IP (str or ``ipaddress`` object).
* :func:`validate_hostname` — validate a hostname (DNS-resolve + check IPs).
* :func:`validate_url` — full URL validation (scheme/port/host/DNS/IP).
* :func:`safe_http_client` — an ``httpx.AsyncClient`` that enforces all of the
  above on the initial request and on every redirect hop.

The functions are dependency-free (``ipaddress``/``socket``) except
``safe_http_client``/transport which use ``httpx``. ``SSRFError`` messages are
deliberately generic and never echo secret material.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from app.core.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    import httpx

logger = get_logger(__name__)

# --------------------------------------------------------------------------- #
# Policy primitives
# --------------------------------------------------------------------------- #
_IpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

# Hostnames that must never be resolved/contacted regardless of what they
# resolve to (defence in depth; the IP checks below also catch these).
_BLOCKED_HOSTNAMES: frozenset[str] = frozenset(
    {
        "localhost",
        "metadata",                  # common short metadata alias
        "metadata.google.internal",  # GCP metadata
        "metadata.goog",             # GCP metadata (alt)
    }
)

# Cloud instance-metadata service addresses (AWS, Azure, GCP all use the
# IMDS link-local address; AWS additionally exposes an IPv6 metadata address).
_CLOUD_METADATA_IPS: frozenset[_IpAddress] = frozenset(
    {
        ipaddress.ip_address("169.254.169.254"),  # AWS / Azure / GCP IMDS
        ipaddress.ip_address("fd00:ec2::254"),    # AWS IMDS over IPv6
    }
)

# Sensitive service ports that should never be the target of an outbound probe.
# (IP-range blocking already covers internal hosts; this is defence in depth for
# an internal service that happens to live on a public IP.)
_DEFAULT_BLOCKED_PORTS: frozenset[int] = frozenset(
    {
        22,     # SSH
        23,     # Telnet
        25,     # SMTP
        135,    # MSRPC
        445,    # SMB
        1433,   # MSSQL
        3306,   # MySQL
        3389,   # RDP
        5432,   # PostgreSQL
        5984,   # CouchDB
        6379,   # Redis
        9200,   # Elasticsearch
        11211,  # Memcached
        27017,  # MongoDB
    }
)

_DEFAULT_ALLOWED_SCHEMES: tuple[str, ...] = ("http", "https")
_SCHEME_DEFAULT_PORTS = {"http": 80, "https": 443}


class SSRFError(Exception):
    """Raised when a URL/host/IP fails SSRF validation.

    The message is intentionally generic and never contains secret material or
    the precise internal address that was blocked.
    """


@dataclass(frozen=True)
class SSRFPolicy:
    """Bundle of SSRF rules. Defaults are safe for a multi-tenant SaaS."""

    enabled: bool = True
    # On-prem / self-hosted deployments can set this so legitimate internal
    # targets (a customer's private GitLab/Prometheus) remain reachable. Even
    # when True, loopback / link-local / metadata are *always* blocked.
    allow_private: bool = False
    allowed_schemes: tuple[str, ...] = _DEFAULT_ALLOWED_SCHEMES
    # ``None`` => any port that is not in ``blocked_ports`` is allowed (keeps
    # self-hosted Prometheus:9090 / GitLab:8443 working). Provide a set to
    # enforce a strict allow-list instead.
    allowed_ports: frozenset[int] | None = None
    blocked_ports: frozenset[int] = field(default=_DEFAULT_BLOCKED_PORTS)


def default_policy() -> SSRFPolicy:
    """Build the active policy from application settings (lazy import)."""
    try:
        from app.core.config import settings

        return SSRFPolicy(
            enabled=getattr(settings, "SSRF_PROTECTION_ENABLED", True),
            allow_private=getattr(settings, "SSRF_ALLOW_PRIVATE_NETWORKS", False),
        )
    except Exception:  # noqa: BLE001 - never let config import break safety defaults
        return SSRFPolicy()


@dataclass(frozen=True)
class ValidatedURL:
    """Result of a successful :func:`validate_url`."""

    url: str
    scheme: str
    hostname: str
    port: int
    ip_addresses: tuple[_IpAddress, ...]


# --------------------------------------------------------------------------- #
# IP validation
# --------------------------------------------------------------------------- #
def _block_reason(ip: _IpAddress, *, allow_private: bool) -> str | None:
    """Return a generic reason string if ``ip`` is not permitted, else None."""
    # Unwrap IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) and re-check the IPv4.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _block_reason(ip.ipv4_mapped, allow_private=allow_private)

    if ip in _CLOUD_METADATA_IPS:
        return "cloud-metadata"
    if ip.is_unspecified:
        return "unspecified"
    if ip.is_loopback:
        return "loopback"
    if ip.is_link_local:
        return "link-local"
    if ip.is_multicast:
        return "multicast"
    if ip.is_reserved:
        return "reserved"
    # IPv6 unique-local (fc00::/7) — site-internal, treat like private.
    if getattr(ip, "is_site_local", False):
        return "site-local"
    if not allow_private and ip.is_private:
        return "private"
    return None


def validate_ip(ip: str | _IpAddress, *, policy: SSRFPolicy | None = None) -> _IpAddress:
    """Validate a single IP address.

    Returns the parsed ``ipaddress`` object, or raises :class:`SSRFError` if the
    address falls in any blocked range.
    """
    policy = policy or default_policy()
    if isinstance(ip, str):
        try:
            parsed = ipaddress.ip_address(ip.strip())
        except ValueError as exc:
            raise SSRFError("Invalid IP address.") from exc
    else:
        parsed = ip

    if not policy.enabled:
        return parsed

    reason = _block_reason(parsed, allow_private=policy.allow_private)
    if reason is not None:
        raise SSRFError(f"Request to a non-routable/disallowed address is blocked ({reason}).")
    return parsed


# --------------------------------------------------------------------------- #
# Hostname validation (DNS resolution + per-IP checks)
# --------------------------------------------------------------------------- #
def _resolve(hostname: str) -> list[_IpAddress]:
    """Resolve ``hostname`` to all A/AAAA addresses.

    Isolated for testability (tests monkeypatch this). Raises ``SSRFError`` on
    resolution failure.
    """
    try:
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SSRFError("Hostname could not be resolved.") from exc
    addresses: list[_IpAddress] = []
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        try:
            addresses.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:  # pragma: no cover - getaddrinfo always returns valid IPs
            continue
    if not addresses:
        raise SSRFError("Hostname did not resolve to any address.")
    return addresses


def _normalize_hostname(hostname: str) -> str:
    return hostname.strip().rstrip(".").lower()


def validate_hostname(hostname: str, *, policy: SSRFPolicy | None = None) -> list[_IpAddress]:
    """Validate a hostname or IP literal.

    For an IP literal the address is checked directly. For a DNS name it is
    resolved and *every* resolved address must pass :func:`validate_ip`. Returns
    the list of validated IP addresses; raises :class:`SSRFError` otherwise.
    """
    policy = policy or default_policy()
    if not hostname or not hostname.strip():
        raise SSRFError("Empty hostname.")

    name = _normalize_hostname(hostname)

    if policy.enabled:
        if name in _BLOCKED_HOSTNAMES or name.endswith(".localhost"):
            raise SSRFError("Request to a disallowed hostname is blocked.")

    # IP literal? validate directly (no DNS).
    try:
        literal = ipaddress.ip_address(name)
    except ValueError:
        literal = None
    if literal is not None:
        return [validate_ip(literal, policy=policy)]

    if not policy.enabled:
        # Still resolve so callers get addresses, but don't block.
        return _resolve(name)

    resolved = _resolve(name)
    for addr in resolved:
        validate_ip(addr, policy=policy)  # raises on first blocked address
    return resolved


# --------------------------------------------------------------------------- #
# URL validation
# --------------------------------------------------------------------------- #
def _validate_port(port: int, policy: SSRFPolicy) -> None:
    if port < 1 or port > 65535:
        raise SSRFError("Invalid port.")
    if policy.allowed_ports is not None and port not in policy.allowed_ports:
        raise SSRFError("Request to a disallowed port is blocked.")
    if port in policy.blocked_ports:
        raise SSRFError("Request to a sensitive port is blocked.")


def validate_url(url: str, *, policy: SSRFPolicy | None = None) -> ValidatedURL:
    """Fully validate an outbound URL (scheme, port, host, DNS, IPs).

    Returns a :class:`ValidatedURL` (including the resolved IPs) or raises
    :class:`SSRFError`.
    """
    policy = policy or default_policy()
    if not isinstance(url, str) or not url.strip():
        raise SSRFError("Empty URL.")

    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "").lower()

    if policy.enabled and scheme not in policy.allowed_schemes:
        raise SSRFError("URL scheme is not permitted.")

    hostname = parts.hostname
    if not hostname:
        raise SSRFError("URL has no host.")

    try:
        explicit_port = parts.port  # may raise ValueError for malformed ports
    except ValueError as exc:
        raise SSRFError("Invalid port.") from exc
    port = explicit_port if explicit_port is not None else _SCHEME_DEFAULT_PORTS.get(scheme, 0)

    if policy.enabled:
        _validate_port(port, policy)

    ip_addresses = validate_hostname(hostname, policy=policy)
    return ValidatedURL(
        url=url,
        scheme=scheme,
        hostname=_normalize_hostname(hostname),
        port=port,
        ip_addresses=tuple(ip_addresses),
    )


# --------------------------------------------------------------------------- #
# SSRF-safe httpx client
# --------------------------------------------------------------------------- #
class _SSRFAsyncTransport:
    """An ``httpx.AsyncBaseTransport`` that validates every request it sends.

    Because httpx invokes the transport once per hop, this validates the initial
    request *and* every redirect target (when redirects are enabled), closing the
    "allowed first host → redirect to internal" bypass.
    """

    def __init__(self, inner: httpx.AsyncBaseTransport, policy: SSRFPolicy):
        self._inner = inner
        self._policy = policy

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self._policy.enabled:
            url = str(request.url)
            # DNS resolution is blocking — run it off the event loop.
            await asyncio.to_thread(validate_url, url, policy=self._policy)
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()

    async def __aenter__(self) -> _SSRFAsyncTransport:
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()


def safe_http_client(
    *,
    policy: SSRFPolicy | None = None,
    allow_redirects: bool = False,
    timeout=None,
    verify: bool = True,
    transport: httpx.AsyncBaseTransport | None = None,
    **kwargs,
) -> httpx.AsyncClient:
    """Return an ``httpx.AsyncClient`` hardened against SSRF.

    * TLS verification is on by default (``verify=True``).
    * Automatic redirects are **disabled by default**; pass
      ``allow_redirects=True`` to opt in — every hop is still SSRF-validated.
    * ``transport`` may be supplied to wrap a custom inner transport (used by
      tests, e.g. ``httpx.MockTransport``).

    Use as an async context manager, exactly like ``httpx.AsyncClient``.
    """
    import httpx

    policy = policy or default_policy()
    inner = transport if transport is not None else httpx.AsyncHTTPTransport(verify=verify)
    guarded = _SSRFAsyncTransport(inner, policy)
    return httpx.AsyncClient(
        transport=guarded,
        follow_redirects=allow_redirects,
        timeout=timeout,
        **kwargs,
    )
