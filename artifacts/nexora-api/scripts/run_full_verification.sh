#!/usr/bin/env bash
# Nexora full platform verification (Python 3.11+, Node 20+, PostgreSQL, Redis).
# Set SKIP_DOCKER_VERIFY=1 in CI to skip the local docker compose build/start step.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PYTHONDONTWRITEBYTECODE=1
export ENVIRONMENT="${ENVIRONMENT:-test}"
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-test-secret-key-for-verification-only}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://nexora:nexora@localhost:5432/nexora}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
export SMOKE_BASE_URL="${SMOKE_BASE_URL:-http://localhost:8000/nexora-api}"

log() {
  printf '\n==> %s\n' "$1"
}

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

require_python() {
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON=python3.11
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
  else
    fail "Python 3.11+ is required"
  fi
  export PYTHON

  "$PYTHON" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(f"Python 3.11+ required, found {sys.version}")
print(f"Python {sys.version.split()[0]}")
PY
}

require_node() {
  if ! command -v node >/dev/null 2>&1; then
    fail "Node.js 20+ is required"
  fi
  node - <<'JS'
const major = Number(process.versions.node.split('.')[0]);
if (major < 20) {
  console.error(`Node.js 20+ required, found ${process.versions.node}`);
  process.exit(1);
}
console.log(`Node ${process.versions.node}`);
JS
}

verify_docker_runtime() {
  if [[ "${SKIP_DOCKER_VERIFY:-0}" == "1" ]]; then
    log "Skipping docker runtime parity (SKIP_DOCKER_VERIFY=1)"
    return 0
  fi

  if ! command -v docker >/dev/null 2>&1; then
    fail "Docker is required for verification runtime parity"
  fi

  log "Building API container (Python 3.11 / Node 20)"
  docker compose build api

  log "Starting PostgreSQL and Redis services"
  docker compose up -d db redis

  log "Starting API service"
  docker compose up -d api
}

install_dependencies() {
  log "Installing Python dependencies"
  if [[ ! -d .venv ]]; then
    "$PYTHON" -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip >/dev/null
  python -m pip install -r requirements.txt -r requirements-dev.txt >/dev/null
}

run_migrations() {
  log "Running Alembic migrations"
  alembic upgrade head
}

run_lint_and_types() {
  log "Running Ruff lint checks"
  ruff check app

  log "Running mypy type checks"
  mypy app

  log "Running Python compile checks"
  "$PYTHON" -m compileall -q app
}

run_backend_tests() {
  log "Running full pytest with coverage"
  pytest app/tests -q \
    --cov=app \
    --cov-report=term-missing:skip-covered \
    --cov-report=json:coverage.json \
    --cov-report=xml:coverage.xml \
    --cov-report=html:coverage_html
}

run_frontend_tests() {
  log "Validating frontend chunks"
  node scripts/validate-frontend.js

  log "Running full frontend test suite"
  npm test
}

start_api_for_smoke() {
  if [[ "${SKIP_DOCKER_VERIFY:-0}" != "1" ]]; then
    log "Using docker-compose API for smoke tests"
    return 0
  fi

  log "Starting API for smoke tests"
  uvicorn app.main:app --host 0.0.0.0 --port 8000 &
  echo $! > /tmp/nexora_api.pid
  "$PYTHON" - <<'PY'
import time
import urllib.request

for _ in range(60):
    try:
        with urllib.request.urlopen("http://localhost:8000/nexora-api/health", timeout=2):
            break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("API failed to become healthy")
print("API healthy")
PY
}

stop_api_for_smoke() {
  if [[ -f /tmp/nexora_api.pid ]]; then
    kill "$(cat /tmp/nexora_api.pid)" 2>/dev/null || true
    rm -f /tmp/nexora_api.pid
  fi
}

run_smoke_tests() {
  log "Running Python API smoke test"
  "$PYTHON" scripts/smoke_test.py

  log "Running lazy-route API smoke"
  node scripts/smoke-lazy-routes.mjs

  log "Running P0–P2 API smoke"
  node scripts/smoke-p0-p2-pass.mjs

  log "Running P3 operational evidence smoke"
  node scripts/smoke-p3-pass.mjs

  log "Running P4 catalog and federation smoke"
  node scripts/smoke-p4-pass.mjs

  if [[ "${SKIP_DOCKER_VERIFY:-0}" == "1" ]]; then
    log "Running Playwright Phase 1 UI smoke (CI verify job)"
    export NEXORA_UI_BASE="${NEXORA_UI_BASE:-http://127.0.0.1:8000}"
    npx playwright install chromium --with-deps
    node scripts/smoke-phase1-ui.mjs
  fi
}

enforce_coverage() {
  log "Enforcing coverage gates"
  "$PYTHON" scripts/check_coverage_thresholds.py coverage.json
}

main() {
  log "Nexora full verification"
  require_python
  require_node
  verify_docker_runtime
  install_dependencies
  run_migrations
  run_lint_and_types
  run_backend_tests
  run_frontend_tests
  start_api_for_smoke
  trap stop_api_for_smoke EXIT
  run_smoke_tests
  enforce_coverage
  trap - EXIT
  stop_api_for_smoke
  log "Verification completed successfully"
}

main "$@"
