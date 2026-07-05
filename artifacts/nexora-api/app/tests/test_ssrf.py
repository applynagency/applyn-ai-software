"""Unit tests for the shared SSRF guard (``app.security.ssrf``).

No real network/DNS is used: ``_resolve`` is monkeypatched where a hostname must
resolve. IP-literal and policy logic is exercised directly.
"""

import ipaddress

import httpx
import pytest

from app.security import ssrf
from app.security.ssrf import (
    SSRFError,
    SSRFPolicy,
    safe_http_client,
    validate_hostname,
    validate_ip,
    validate_url,
)

STRICT = SSRFPolicy(enabled=True, allow_private=False)
ONPREM = SSRFPolicy(enabled=True, allow_private=True)
OFF = SSRFPolicy(enabled=False)


# ----------------------------- validate_ip -------------------------------- #
@pytest.mark.parametrize(
    "addr",
    [
        "127.0.0.1",          # loopback
        "127.10.20.30",       # loopback /8
        "::1",                # loopback v6
        "10.0.0.1",           # private 10/8
        "172.16.5.4",         # private 172.16/12
        "192.168.1.1",        # private 192.168/16
        "169.254.0.5",        # link-local
        "169.254.169.254",    # AWS/Azure/GCP metadata
        "fd00:ec2::254",      # AWS metadata v6
        "fe80::1",            # link-local v6
        "fc00::1",            # unique-local v6
        "224.0.0.1",          # multicast
        "0.0.0.0",            # unspecified
        "::ffff:127.0.0.1",   # IPv4-mapped loopback
        "::ffff:10.0.0.1",    # IPv4-mapped private
    ],
)
def test_validate_ip_blocks_dangerous(addr):
    with pytest.raises(SSRFError):
        validate_ip(addr, policy=STRICT)


@pytest.mark.parametrize("addr", ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:4700:4700::1111"])
def test_validate_ip_allows_public(addr):
    assert validate_ip(addr, policy=STRICT) == ipaddress.ip_address(addr)


def test_validate_ip_invalid_literal():
    with pytest.raises(SSRFError):
        validate_ip("not-an-ip", policy=STRICT)


def test_onprem_allows_private_but_never_metadata_or_loopback():
    # On-prem policy permits RFC-1918...
    assert validate_ip("10.0.0.1", policy=ONPREM)
    assert validate_ip("192.168.1.1", policy=ONPREM)
    # ...but loopback / link-local / metadata are ALWAYS blocked.
    for addr in ("127.0.0.1", "169.254.0.1", "169.254.169.254", "fd00:ec2::254"):
        with pytest.raises(SSRFError):
            validate_ip(addr, policy=ONPREM)


def test_disabled_policy_allows_everything():
    assert validate_ip("169.254.169.254", policy=OFF)
    assert validate_ip("127.0.0.1", policy=OFF)


# --------------------------- validate_hostname ---------------------------- #
@pytest.mark.parametrize("name", ["localhost", "LOCALHOST", "foo.localhost", "metadata",
                                   "metadata.google.internal", "metadata.goog"])
def test_validate_hostname_blocks_known_names(name):
    with pytest.raises(SSRFError):
        validate_hostname(name, policy=STRICT)


def test_validate_hostname_ip_literal_private_blocked():
    with pytest.raises(SSRFError):
        validate_hostname("10.0.0.1", policy=STRICT)


def test_validate_hostname_dns_rebinding_blocked(monkeypatch):
    # A public-looking name that resolves to an internal IP must be rejected.
    monkeypatch.setattr(ssrf, "_resolve", lambda h: [ipaddress.ip_address("10.0.0.7")])
    with pytest.raises(SSRFError):
        validate_hostname("sneaky.example.com", policy=STRICT)


def test_validate_hostname_public_ok(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve", lambda h: [ipaddress.ip_address("93.184.216.34")])
    ips = validate_hostname("example.com", policy=STRICT)
    assert ipaddress.ip_address("93.184.216.34") in ips


def test_validate_hostname_blocks_if_any_resolved_ip_internal(monkeypatch):
    monkeypatch.setattr(
        ssrf, "_resolve",
        lambda h: [ipaddress.ip_address("93.184.216.34"), ipaddress.ip_address("127.0.0.1")],
    )
    with pytest.raises(SSRFError):
        validate_hostname("mixed.example.com", policy=STRICT)


def test_validate_hostname_unresolvable(monkeypatch):
    def _boom(h):
        raise SSRFError("Hostname could not be resolved.")
    monkeypatch.setattr(ssrf, "_resolve", _boom)
    with pytest.raises(SSRFError):
        validate_hostname("nope.invalid", policy=STRICT)


# ----------------------------- validate_url ------------------------------- #
@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://example.com/x",
    "gopher://example.com/",
    "ssh://example.com/",
])
def test_validate_url_blocks_bad_schemes(url):
    with pytest.raises(SSRFError):
        validate_url(url, policy=STRICT)


def test_validate_url_requires_host():
    with pytest.raises(SSRFError):
        validate_url("https:///nohost", policy=STRICT)


def test_validate_url_blocks_sensitive_port():
    # Port denylist is checked before DNS, so no resolution needed.
    with pytest.raises(SSRFError):
        validate_url("http://example.com:22/", policy=STRICT)
    with pytest.raises(SSRFError):
        validate_url("https://example.com:6379/", policy=STRICT)


def test_validate_url_allowlist_ports():
    pol = SSRFPolicy(allowed_ports=frozenset({443}))
    with pytest.raises(SSRFError):
        validate_url("https://example.com:8443/", policy=pol)


def test_validate_url_metadata_ip_blocked():
    with pytest.raises(SSRFError):
        validate_url("http://169.254.169.254/latest/meta-data/", policy=STRICT)


def test_validate_url_public_ok(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve", lambda h: [ipaddress.ip_address("93.184.216.34")])
    res = validate_url("https://api.example.com/v1/x", policy=STRICT)
    assert res.scheme == "https" and res.port == 443 and res.hostname == "api.example.com"


def test_validate_url_default_port_derivation(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve", lambda h: [ipaddress.ip_address("93.184.216.34")])
    assert validate_url("http://example.com/x", policy=STRICT).port == 80


def test_validate_url_self_hosted_high_port_allowed(monkeypatch):
    # Backward compat: self-hosted Prometheus:9090 on a public IP must still work.
    monkeypatch.setattr(ssrf, "_resolve", lambda h: [ipaddress.ip_address("93.184.216.34")])
    assert validate_url("http://prom.example.com:9090/api/v1/alerts", policy=STRICT).port == 9090


# --------------------- safe_http_client (transport) ----------------------- #
def _mock_inner(handler):
    return httpx.MockTransport(handler)


async def test_safe_client_blocks_before_reaching_network():
    called = {"n": 0}

    def handler(request):
        called["n"] += 1
        return httpx.Response(200, json={"ok": True})

    async with safe_http_client(policy=STRICT, transport=_mock_inner(handler)) as c:
        with pytest.raises(SSRFError):
            await c.get("http://169.254.169.254/latest/meta-data/")
    assert called["n"] == 0  # inner transport never invoked


async def test_safe_client_allows_public(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve", lambda h: [ipaddress.ip_address("93.184.216.34")])

    def handler(request):
        return httpx.Response(200, json={"ok": True})

    async with safe_http_client(policy=STRICT, transport=_mock_inner(handler)) as c:
        resp = await c.get("https://api.example.com/v1/ping")
    assert resp.status_code == 200 and resp.json() == {"ok": True}


async def test_safe_client_does_not_follow_redirects_by_default(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve", lambda h: [ipaddress.ip_address("93.184.216.34")])

    def handler(request):
        return httpx.Response(302, headers={"location": "http://169.254.169.254/"})

    async with safe_http_client(policy=STRICT, transport=_mock_inner(handler)) as c:
        resp = await c.get("https://api.example.com/start")
    assert resp.status_code == 302  # not followed -> internal target never hit


async def test_safe_client_validates_redirect_hops_when_enabled(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve", lambda h: [ipaddress.ip_address("93.184.216.34")])

    def handler(request):
        # First hop allowed; it tries to bounce to the metadata endpoint.
        if request.url.host == "api.example.com":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/"})
        return httpx.Response(200)  # pragma: no cover - should never be reached

    async with safe_http_client(policy=STRICT, allow_redirects=True, transport=_mock_inner(handler)) as c:
        with pytest.raises(SSRFError):
            await c.get("https://api.example.com/start")


async def test_safe_client_disabled_policy_passes_through():
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    async with safe_http_client(policy=OFF, transport=_mock_inner(handler)) as c:
        resp = await c.get("http://127.0.0.1:6379/")  # would be blocked under STRICT
    assert resp.status_code == 200
