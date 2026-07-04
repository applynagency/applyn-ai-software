import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import NexoraException
from app.core.logging import configure_logging, get_logger
from app.middleware.audit import RequestLoggingMiddleware
from app.middleware.body_limit import BodyLimitMiddleware
from app.middleware.error_handler import (
    nexora_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.middleware.metrics import MetricsMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.security.secrets import ensure_master_key
from app.tenancy.backfill import backfill_organization_data
from app.web import static_assets

configure_logging()
logger = get_logger(__name__)

BASE_PATH = os.environ.get("BASE_PATH", settings.BASE_PATH).rstrip("/")
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _cors_middleware_kwargs() -> dict:
    """Resolve CORS settings safe for production (never ``*`` + credentials)."""
    origins = list(settings.CORS_ALLOWED_ORIGINS)
    allow_credentials = settings.CORS_ALLOW_CREDENTIALS
    if not origins:
        if settings.ENVIRONMENT.lower() == "production":
            logger.warning(
                "cors_restrictive_default",
                detail=(
                    "CORS_ALLOWED_ORIGINS unset in production; "
                    "cross-origin browser access is disabled"
                ),
            )
            origins = []
            allow_credentials = False
        else:
            origins = ["*"]
            allow_credentials = False
    elif "*" in origins:
        allow_credentials = False
    return {
        "allow_origins": origins,
        "allow_credentials": allow_credentials,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("nexora_startup", version=settings.APP_VERSION, env=settings.ENVIRONMENT)
    # Sprint 35A: refuse to start without the credential encryption key so we can
    # never run in a state where customer secrets would be handled unencrypted.
    ensure_master_key()
    # Prometheus metrics: build the registry and attach DB query timing. No-op
    # when prometheus_client is not installed.
    from app.observability import metrics as metrics_mod

    metrics_mod.init_metrics()
    metrics_mod.instrument_database()
    # Schema is owned by Alembic — verify the DB is migrated to head and fail
    # fast otherwise. Skipped for sqlite (tests / local dev create the schema
    # directly) and when explicitly disabled.
    if settings.DB_MIGRATION_CHECK_ENABLED and "sqlite" not in settings.DATABASE_URL:
        from app.database.migration_check import verify_migrations_or_raise

        await verify_migrations_or_raise()
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            await backfill_organization_data(session)
            # Sprint 61C: seed the default plan catalog (idempotent) so every org
            # has a plan to be placed on. No-op once plans exist.
            if settings.BILLING_ENABLED and settings.BILLING_SEED_DEFAULT_PLANS:
                from app.services.billing.plans import PlanService

                created = await PlanService(session).seed_defaults()
                if created:
                    logger.info("billing_plans_seeded", count=created)
            # Sprint 61D: seed default global prompts (idempotent) so the prompt
            # registry has a baseline every org can override.
            if settings.AI_PLATFORM_ENABLED:
                from app.ai.seed import seed_default_prompts

                seeded = await seed_default_prompts(session)
                if seeded:
                    logger.info("ai_prompts_seeded", count=seeded)
            # Sprint 62A: register event subscribers (activity feed) + seed the
            # plugin catalog (idempotent). Importing activity wires the "*"
            # subscriber that mirrors every domain event into the activity feed.
            if settings.PLATFORM_CONVERGENCE_ENABLED:
                import app.platform.activity  # noqa: F401 - registers subscribers
                if settings.PRODUCT_EXCELLENCE_ENABLED:
                    import app.platform.product  # noqa: F401 - inbox subscriber
                if settings.AUTONOMOUS_SRE_ENABLED:
                    import app.platform.sre  # noqa: F401 - ops center subscriber
                if settings.AI_OPERATOR_ENABLED:
                    import app.platform.operator_events  # noqa: F401 - operator subscriber
                from app.platform.plugins import PluginService

                plugins_seeded = await PluginService(session).seed_catalog()
                if plugins_seeded:
                    logger.info("plugins_seeded", count=plugins_seeded)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    # Background periodic work. When the async job queue is enabled the Arq
    # worker drives these via cron jobs instead, so the in-process loops are not
    # started here (avoids double-execution across the API and the worker).
    scheduler_task = None
    monitoring_task = None
    escalation_task = None
    integration_pipeline_task = None
    integration_gitops_task = None
    universal_discovery_task = None
    integration_health_task = None
    if not settings.JOB_QUEUE_ENABLED:
        # Sprint 38B: workflow scheduler loop (time-based triggering only).
        if settings.WORKFLOW_SCHEDULER_ENABLED:
            from app.services.workflow_scheduler import workflow_scheduler_loop

            scheduler_task = asyncio.create_task(workflow_scheduler_loop())

        # Sprint 42A: continuous monitoring loop (read-only polling that
        # auto-creates incidents and notifies humans; no autonomous remediation).
        if settings.MONITORING_ENABLED:
            from app.services.monitoring_scheduler import monitoring_loop

            monitoring_task = asyncio.create_task(monitoring_loop())

        # Sprint 42B: escalation loop (pages the next on-call target when an
        # incident is not acknowledged in time). Approval-gated; no remediation.
        if settings.ESCALATION_ENABLED:
            from app.services.monitoring_scheduler import escalation_loop

            escalation_task = asyncio.create_task(escalation_loop())

        # Universal Discovery loop (read-only discovery across every connected
        # integration, maintaining the inventory + Knowledge Graph).
        if settings.UNIVERSAL_DISCOVERY_ENABLED:
            from app.services.discovery_scheduler import universal_discovery_loop

            universal_discovery_task = asyncio.create_task(universal_discovery_loop())

        if settings.INTEGRATION_READINESS_ENABLED:
            from app.services.integration_health_scheduler import integration_health_loop

            integration_health_task = asyncio.create_task(integration_health_loop())

        if settings.INTEGRATION_PIPELINE_SYNC_ENABLED:
            from app.services.integration_pipeline_scheduler import integration_pipeline_loop

            integration_pipeline_task = asyncio.create_task(integration_pipeline_loop())

        if settings.INTEGRATION_GITOPS_SYNC_ENABLED:
            from app.services.integration_gitops_scheduler import integration_gitops_loop

            integration_gitops_task = asyncio.create_task(integration_gitops_loop())

    # Outbound notification queue drainer (opt-in). Runs in the API process and
    # delivers buffered incident notifications out-of-band. Independent of the
    # job-queue mode; LPOP is atomic so multiple replicas drain safely.
    notification_stop = asyncio.Event()
    notification_task = None
    if settings.NOTIFICATION_QUEUE_ENABLED:
        from app.redis import notifications

        notification_task = asyncio.create_task(
            notifications.drain_loop(notifications.default_handler, notification_stop)
        )

    # Sprint 62B: durable, leader-elected domain-event consumer. Only the elected
    # leader across replicas drains the outbox, so delivery is exactly-once even
    # under horizontal scaling. Opt-in (EVENT_CONSUMER_ENABLED).
    event_consumer_stop = asyncio.Event()
    event_consumer_task = None
    if settings.HARDENING_ENABLED and settings.EVENT_CONSUMER_ENABLED:
        from app.platform.events import run_event_consumer

        event_consumer_task = asyncio.create_task(
            run_event_consumer(event_consumer_stop)
        )

    # Slow-query logging (opt-in via DB_SLOW_QUERY_MS).
    if settings.HARDENING_ENABLED:
        from app.observability.slow_query import install_slow_query_logging

        install_slow_query_logging()

    # Expose background task handles + flip the startup gate for the K8s probes.
    from app.core import health

    health.register_background_tasks(
        {
            "workflow_scheduler": scheduler_task,
            "monitoring": monitoring_task,
            "escalation": escalation_task,
            "integration_pipeline": integration_pipeline_task,
            "integration_gitops": integration_gitops_task,
            "discovery": universal_discovery_task,
            "integration_health": integration_health_task,
        }
    )
    health.mark_startup_complete()

    logger.info("nexora_ready")
    yield
    health.reset_startup_state()
    health.clear_background_tasks()
    notification_stop.set()
    event_consumer_stop.set()
    for task in (scheduler_task, monitoring_task, escalation_task,
                 integration_pipeline_task, integration_gitops_task, universal_discovery_task, integration_health_task,
                 notification_task, event_consumer_task):
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    from app.security.rate_limit import close_rate_limit_backend

    await close_rate_limit_backend()
    from app.jobs.queue import close_arq_pool

    await close_arq_pool()
    from app.redis.client import close_redis

    await close_redis()
    from app.observability.tracing import shutdown_tracing

    shutdown_tracing()
    logger.info("nexora_shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url=f"{BASE_PATH}/docs",
    redoc_url=f"{BASE_PATH}/redoc",
    openapi_url=f"{BASE_PATH}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CORSMiddleware, **_cors_middleware_kwargs())
# Distributed rate limiting on abuse-prone endpoints (auth/connect/webhooks).
# Registered before the security-headers middleware so that 429 responses still
# pass back out through it and receive the standard security headers.
app.add_middleware(RateLimitMiddleware)
# Enterprise security headers (HSTS/CSP/X-Frame-Options/...). Registered last so
# it runs outermost and stamps headers on every response, including the docs and
# the served dashboard. The docs routes get a relaxed CSP so Swagger UI keeps
# working.
app.add_middleware(
    SecurityHeadersMiddleware,
    production=settings.ENVIRONMENT.lower() == "production",
    base_path=BASE_PATH,
    enabled=settings.SECURITY_HEADERS_ENABLED,
    hsts_max_age=settings.HSTS_MAX_AGE,
    csp_nonce=settings.CSP_NONCE_ENABLED,
    trusted_types=settings.TRUSTED_TYPES_ENABLED,
)
# Prometheus request metrics (count/duration/status). Placed just inside the
# body-size guard so it observes route responses including rate-limit 429s.
app.add_middleware(MetricsMiddleware)

# Global request body size limits. Added last so it runs outermost and rejects
# oversized payloads with 413 before any other middleware buffers them.
app.add_middleware(
    BodyLimitMiddleware,
    json_limit=settings.MAX_JSON_BODY_BYTES,
    multipart_limit=settings.MAX_MULTIPART_BODY_BYTES,
    enabled=settings.BODY_LIMIT_ENABLED,
)

# Maintenance mode (Sprint 62B). Registered last so it runs outermost and can
# short-circuit business traffic with 503 during planned windows while leaving
# health/docs/ops endpoints reachable. Config-backed toggle (cached); off unless
# explicitly enabled at runtime.
if settings.HARDENING_ENABLED:
    from app.middleware.maintenance import MaintenanceModeMiddleware

    app.add_middleware(MaintenanceModeMiddleware, enabled=True)

app.add_exception_handler(NexoraException, nexora_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


# SCIM endpoints return the RFC 7644 error envelope (application/scim+json)
# rather than the platform's default error shape.
from app.services.scim.errors import ScimError  # noqa: E402


async def _scim_exception_handler(request, exc: ScimError):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        content=exc.to_body(),
        status_code=exc.status_code,
        media_type="application/scim+json",
    )


app.add_exception_handler(ScimError, _scim_exception_handler)

# Distributed tracing (OpenTelemetry). Opt-in via TRACING_ENABLED; instruments
# FastAPI/SQLAlchemy/httpx/Redis. No-op when disabled or the SDK is absent.
from app.observability.tracing import init_tracing  # noqa: E402

init_tracing(app)

app.include_router(api_router, prefix=BASE_PATH)


@app.get(f"{BASE_PATH}/health", tags=["Health"])
async def health():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


def _probe_meta() -> dict:
    from app.core import health as health_mod

    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "uptime_seconds": round(health_mod.uptime_seconds(), 3),
    }


@app.get("/livez", tags=["Health"])
async def livez():
    """Liveness probe: the process is up and the event loop is responsive.

    Deliberately performs no dependency checks so transient DB/Redis blips never
    trigger a pod restart.
    """
    return JSONResponse({"status": "alive", **_probe_meta()})


@app.get("/readyz", tags=["Health"])
async def readyz():
    """Readiness probe: can this replica serve traffic right now?

    Runs all dependency checks. A failing *critical* check (database) returns
    503; non-critical degradation (redis/scheduler/storage/AI) reports
    ``degraded`` but stays in rotation (HTTP 200).
    """
    from app.core import health as health_mod

    overall, results = await health_mod.run_checks(
        [
            health_mod.check_database,
            health_mod.check_redis,
            health_mod.check_scheduler,
            health_mod.check_storage,
            health_mod.check_ai_providers,
        ]
    )
    body = {
        "status": overall,
        **_probe_meta(),
        "checks": [r.to_dict() for r in results],
    }
    status_code = 503 if overall == "fail" else 200
    return JSONResponse(body, status_code=status_code)


@app.get("/startupz", tags=["Health"])
async def startupz():
    """Startup probe: has one-time startup finished and is the DB reachable?

    Returns 503 until the application lifespan has completed initialization, so
    Kubernetes can hold liveness/readiness during slow boots.
    """
    from app.core import health as health_mod

    if not health_mod.is_startup_complete():
        return JSONResponse(
            {"status": "starting", **_probe_meta()}, status_code=503
        )
    db = await health_mod.check_database()
    body = {
        "status": "started" if db.status != health_mod.FAIL else "starting",
        **_probe_meta(),
        "checks": [db.to_dict()],
    }
    status_code = 200 if db.status != health_mod.FAIL else 503
    return JSONResponse(body, status_code=status_code)


@app.get("/metrics", tags=["Health"], include_in_schema=False)
async def metrics_endpoint():
    """Prometheus metrics in the text exposition format."""
    from app.observability import metrics as metrics_mod

    if not metrics_mod.METRICS_AVAILABLE:
        return JSONResponse(
            {"detail": "metrics unavailable: prometheus_client not installed"},
            status_code=503,
        )
    await metrics_mod.refresh_runtime_gauges()
    return Response(content=metrics_mod.render(), media_type=metrics_mod.CONTENT_TYPE_LATEST)


def _setup_dashboard() -> None:
    if not STATIC_DIR.exists():
        @app.get("/", include_in_schema=False)
        async def root_without_dashboard():
            return RedirectResponse(url=f"{BASE_PATH}/docs")

        return

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="dashboard-static")

    # Always revalidate the SPA shell so customers receive UI updates
    # immediately instead of a stale, browser-cached bundle.
    _no_cache_headers = {"Cache-Control": static_assets.NO_CACHE}

    # When a production build is present (static/dist/index.html), serve the
    # optimized, content-hashed bundle. Otherwise fall back to the raw dev files.
    dist_dir = STATIC_DIR / "dist"

    def _index_file() -> Path:
        built = dist_dir / "index.html"
        return built if built.is_file() else STATIC_DIR / "index.html"

    @app.get("/assets/{filename}", include_in_schema=False)
    async def hashed_asset(filename: str, request: Request):
        """Serve a content-hashed asset with immutable caching and precompressed
        (brotli/gzip) negotiation."""
        if not static_assets.is_safe_asset_name(filename):
            raise HTTPException(status_code=404)
        base = dist_dir / filename
        if not base.is_file():
            raise HTTPException(status_code=404)

        available = {
            token
            for token, suffix in (("br", ".br"), ("gzip", ".gz"))
            if (dist_dir / f"{filename}{suffix}").is_file()
        }
        encoding = static_assets.choose_encoding(
            request.headers.get("accept-encoding"), available
        )
        served = base
        if encoding:
            served = dist_dir / f"{filename}{static_assets.encoding_suffix(encoding)}"

        return FileResponse(
            served,
            media_type=static_assets.media_type_for(filename),
            headers=static_assets.asset_headers(encoding, immutable=True),
        )

    @app.get("/", include_in_schema=False)
    async def dashboard_root():
        return FileResponse(_index_file(), headers=_no_cache_headers)

    @app.get("/styles.css", include_in_schema=False)
    async def dashboard_styles():
        return FileResponse(STATIC_DIR / "styles.css", headers=_no_cache_headers)

    @app.get("/app.js", include_in_schema=False)
    async def dashboard_script():
        return FileResponse(STATIC_DIR / "app.js", headers=_no_cache_headers)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def dashboard_fallback(full_path: str):
        if full_path.startswith("nexora-api"):
            raise HTTPException(status_code=404)

        if full_path == "health":
            return RedirectResponse(url=f"{BASE_PATH}/health", status_code=307)

        if full_path == "v1" or full_path.startswith("v1/"):
            raise HTTPException(
                status_code=404,
                detail=(
                    f"API routes are served under {BASE_PATH}/v1/. "
                    f"Use {BASE_PATH}/{full_path} instead of /{full_path}."
                ),
            )

        candidate = STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate, headers=_no_cache_headers)

        return FileResponse(_index_file(), headers=_no_cache_headers)


_setup_dashboard()
