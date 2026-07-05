#!/usr/bin/env python3
"""Dependency-free async load test for Nexora (Sprint 61B).

Drives the key user journeys concurrently with ``httpx`` (already a project
dependency), measures p50/p95/p99 latency and throughput per scenario, and
prints a summary table. No external load tool required.

Scenarios: Login, Discovery, Dashboard, Copilot, API Keys, War Room, Incident.

Usage:
    python loadtest/run_load.py \
        --base-url http://localhost:8000 \
        --email admin@example.com --password 'secret' \
        --concurrency 20 --duration 30

Exit code is non-zero if any scenario's error rate exceeds --max-error-rate.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field

import httpx


@dataclass
class Result:
    name: str
    latencies: list[float] = field(default_factory=list)
    errors: int = 0
    count: int = 0

    def record(self, seconds: float, ok: bool) -> None:
        self.count += 1
        self.latencies.append(seconds)
        if not ok:
            self.errors += 1

    def percentile(self, p: float) -> float:
        if not self.latencies:
            return 0.0
        data = sorted(self.latencies)
        k = max(0, min(len(data) - 1, int(round(p / 100 * (len(data) - 1)))))
        return data[k]

    @property
    def error_rate(self) -> float:
        return self.errors / self.count if self.count else 0.0


async def _login(client: httpx.AsyncClient, base: str, email: str, password: str) -> str | None:
    try:
        r = await client.post(
            f"{base}/v1/auth/login", json={"email": email, "password": password}
        )
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception:
        pass
    return None


# Each scenario: (name, method, path, json_body, needs_auth)
def _scenarios(base: str) -> list[tuple]:
    return [
        ("login", "POST", "/v1/auth/login", "__login__", False),
        ("discovery", "GET", "/v1/discovery/summary", None, True),
        ("dashboard", "GET", "/v1/reliability/dashboard", None, True),
        ("copilot", "POST", "/v1/copilot/sessions", {}, True),
        ("api_keys", "GET", "/v1/api-keys", None, True),
        ("war_room", "GET", "/v1/war-room/incidents", None, True),
        ("incident", "GET", "/v1/incidents", None, True),
    ]


async def _worker(
    name: str, method: str, path: str, body, needs_auth: bool,
    base: str, token: str | None, deadline: float, result: Result,
    email: str, password: str,
) -> None:
    headers = {"Authorization": f"Bearer {token}"} if (needs_auth and token) else {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        while time.monotonic() < deadline:
            payload = {"email": email, "password": password} if body == "__login__" else body
            t0 = time.perf_counter()
            ok = False
            try:
                resp = await client.request(
                    method, f"{base}{path}", json=payload if method != "GET" else None,
                    headers=headers,
                )
                ok = resp.status_code < 500 and resp.status_code != 429
            except Exception:
                ok = False
            result.record(time.perf_counter() - t0, ok)


async def run(args) -> int:
    base = args.base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await _login(client, base, args.email, args.password)
    if token is None:
        print(f"WARNING: login failed for {args.email}; authed scenarios will 401")

    results: list[Result] = []
    for name, method, path, body, needs_auth in _scenarios(base):
        result = Result(name)
        deadline = time.monotonic() + args.duration
        started = time.monotonic()
        await asyncio.gather(*[
            _worker(name, method, path, body, needs_auth, base, token, deadline,
                    result, args.email, args.password)
            for _ in range(args.concurrency)
        ])
        result.elapsed = time.monotonic() - started  # type: ignore[attr-defined]
        results.append(result)

    _print_report(results)
    worst = max((r.error_rate for r in results), default=0.0)
    return 1 if worst > args.max_error_rate else 0


def _print_report(results: list[Result]) -> None:
    print("\n" + "=" * 88)
    print(f"{'scenario':<14}{'reqs':>8}{'rps':>10}{'p50 ms':>10}"
          f"{'p95 ms':>10}{'p99 ms':>10}{'err %':>10}")
    print("-" * 88)
    for r in results:
        elapsed = getattr(r, "elapsed", 1.0) or 1.0
        rps = r.count / elapsed
        print(f"{r.name:<14}{r.count:>8}{rps:>10.1f}"
              f"{r.percentile(50) * 1000:>10.1f}"
              f"{r.percentile(95) * 1000:>10.1f}"
              f"{r.percentile(99) * 1000:>10.1f}"
              f"{r.error_rate * 100:>10.2f}")
    print("=" * 88)
    total = sum(r.count for r in results)
    mean = statistics.mean([lat for r in results for lat in r.latencies] or [0])
    print(f"total requests: {total}   overall mean latency: {mean * 1000:.1f} ms\n")


def main() -> None:
    p = argparse.ArgumentParser(description="Nexora load test")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--email", default="admin@example.com")
    p.add_argument("--password", default="changeme")
    p.add_argument("--concurrency", type=int, default=20)
    p.add_argument("--duration", type=float, default=30.0, help="seconds per scenario")
    p.add_argument("--max-error-rate", type=float, default=0.05)
    args = p.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
