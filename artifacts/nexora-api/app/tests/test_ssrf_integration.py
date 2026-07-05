"""Integration tests: the SSRF guard is actually wired into every outbound
HTTP path (integration verification, monitoring ingestion, discovery adapters).

These confirm the refactor — a tenant-supplied internal/metadata URL is blocked
and mapped to each subsystem's customer-safe control-flow exception, with no
network egress. Allowed (public) hosts still flow through (proving backward
compatibility) using an injected mock transport.
"""

import ipaddress

import httpx
import pytest

from app.security import ssrf
from app.services import discovery_adapters as da
from app.services import integration_verification as iv
from app.services import monitoring_ingestion as mi
from app.services.monitoring_ingestion import IngestError


# ---------------- integration verification (_http_request / _aad_token) ----- #
@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data/",  # AWS/Azure/GCP metadata
    "http://127.0.0.1/admin",                     # loopback
    "http://10.0.0.5:8080/internal",              # private
    "http://localhost/",                          # localhost by name
    "file:///etc/passwd",                         # bad scheme
])
async def test_http_request_blocks_ssrf_targets(url):
    # _http_request maps a blocked target to the (non-retryable) _Failed control
    # exception — never a successful probe, never network egress.
    with pytest.raises(iv._Failed):
        await iv._http_request("GET", url)


async def test_http_request_allows_public_via_mock(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve", lambda h: [ipaddress.ip_address("93.184.216.34")])

    def handler(request):
        return httpx.Response(200, json={"login": "octocat"})

    # Wrap safe_http_client so the verifier's call uses a mock inner transport.
    real = ssrf.safe_http_client

    def _patched(**kwargs):
        kwargs.setdefault("transport", httpx.MockTransport(handler))
        return real(**kwargs)

    monkeypatch.setattr(iv, "safe_http_client", _patched)
    out = await iv._http_request("GET", "https://api.github.com/user")
    assert out["_status"] == 200 and out["_json"]["login"] == "octocat"


async def test_aad_token_blocks_ssrf(monkeypatch):
    # Force the (normally public) AAD token host to resolve to an internal IP to
    # prove the guard sits in the _aad_token path too. No network egress: the
    # validating transport raises before connecting.
    monkeypatch.setattr(ssrf, "_resolve", lambda h: [ipaddress.ip_address("10.0.0.1")])
    with pytest.raises(iv._Failed):
        await iv._aad_token("tenant", "client", "secret", "https://management.azure.com/.default")


# ---------------- monitoring ingestion (pollers) --------------------------- #
@pytest.mark.parametrize("endpoint", [
    "http://169.254.169.254",
    "http://10.0.0.9:9090",
    "http://localhost:9090",
])
async def test_prometheus_poller_blocks_ssrf(endpoint):
    with pytest.raises(IngestError):
        await mi.poll_prometheus({"endpoint": endpoint})


async def test_alertmanager_poller_blocks_ssrf():
    with pytest.raises(IngestError):
        await mi.poll_alertmanager({"endpoint": "http://192.168.0.10:9093"})


async def test_prometheus_poller_allows_public_via_mock(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve", lambda h: [ipaddress.ip_address("93.184.216.34")])

    def handler(request):
        return httpx.Response(200, json={"data": {"alerts": []}})

    real = ssrf.safe_http_client

    def _patched(**kwargs):
        kwargs.setdefault("transport", httpx.MockTransport(handler))
        return real(**kwargs)

    monkeypatch.setattr(mi, "safe_http_client", _patched)
    alerts = await mi.poll_prometheus({"endpoint": "https://prom.example.com"})
    assert alerts == []


# ---------------- discovery adapters (Azure ARM) --------------------------- #
async def test_discovery_arm_blocks_ssrf(monkeypatch):
    # Discovery's Azure AAD path: a blocked address becomes the adapter's
    # customer-safe AdapterError (here we force the AAD host to the metadata IP).
    monkeypatch.setattr(ssrf, "_resolve", lambda h: [ipaddress.ip_address("169.254.169.254")])
    with pytest.raises(da.AdapterError):
        await da._aad_token({"tenant_id": "t", "client_id": "c", "client_secret": "s"})
