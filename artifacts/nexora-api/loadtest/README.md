# Nexora Load Testing (Sprint 61B)

Two interchangeable tools that exercise the key user journeys and report
**p50/p95/p99** latency and throughput:

| Tool | When to use |
|---|---|
| `run_load.py` | Zero extra deps (uses `httpx`). CI gate + quick local runs. |
| `locustfile.py` | Distributed load + web UI (`pip install locust`). |

## Scenarios

Login · Discovery · Dashboard · Copilot · API Keys · War Room · Incident.

## Quick start

```bash
# Built-in harness (fails CI if any scenario error rate > 5%):
python loadtest/run_load.py \
  --base-url http://localhost:8000 \
  --email admin@example.com --password 'secret' \
  --concurrency 20 --duration 30

# Locust (web UI at http://localhost:8089):
LOAD_EMAIL=admin@example.com LOAD_PASSWORD=secret \
  locust -f loadtest/locustfile.py --host http://localhost:8000
```

## Reading results

```
scenario          reqs       rps    p50 ms    p95 ms    p99 ms     err %
----------------------------------------------------------------------------
login             1240      41.3      45.1      98.7     142.0      0.00
discovery         3110     103.6      18.2      41.5      66.0      0.00
dashboard         2980      99.3      22.0      55.0      88.0      0.00
copilot           1450      48.3      62.0     130.0     210.0      0.10
api_keys          4020     134.0       9.5      21.0      35.0      0.00
war_room          2700      90.0      20.0      48.0      77.0      0.00
incident          2650      88.0      21.0      50.0      80.0      0.00
```

## Documenting throughput

Record results per release in `THROUGHPUT.md` (sample numbers above are
illustrative — replace with measurements from your environment). Compare against
the previous release to catch regressions. The HPA targets 70% CPU, so sustained
RPS scales roughly linearly with API replica count up to the database's ceiling.

## Tuning notes

- Run against a representative dataset (seed a demo org first).
- Disable client-side rate-limit 429s skew by testing with a service-account API
  key or by raising `RATE_LIMIT_*` in the test environment.
- Watch `/metrics` during the run: `nexora_http_request_duration_seconds`,
  `nexora_cache_events_total` (hit ratio), `nexora_queue_depth`,
  `nexora_database_query_duration_seconds`.
