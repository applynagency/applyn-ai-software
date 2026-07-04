import secrets

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Nexora AI Development Team"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Multi-agent software delivery platform powered by AI"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    BASE_PATH: str = "/nexora-api"

    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600

    JWT_SECRET_KEY: str = secrets.token_urlsafe(64)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    ANTHROPIC_MAX_TOKENS: int = 16000

    # --- Sprint 37D: Team Knowledge Base (RAG) ---
    # OpenAI is used only for document/query embeddings. When unset, a
    # deterministic, network-free hashing embedding is used so the feature and
    # tests work offline (mirrors the LLM runner's "simulated when not configured").
    OPENAI_API_KEY: str | None = None
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 256
    KB_CHUNK_SIZE: int = 1000
    KB_CHUNK_OVERLAP: int = 150
    KB_TOP_K: int = 4
    KB_MAX_FILE_BYTES: int = 10 * 1024 * 1024

    # --- Sprint 39A: Agent Memory System ---
    # How many of an agent's most relevant memories are injected into a prompt.
    MEMORY_TOP_K: int = 3
    # Importance (1–10) nudges ranking; similarity stays dominant.
    MEMORY_IMPORTANCE_WEIGHT: float = 0.02

    # --- Copilot (app.services.grounded_copilot) — the single AI assistant ---
    # The unified Copilot at /v1/copilot: a grounded LLM assistant over the
    # platform's reliability data (RAG + knowledge graph + read-only tool calling
    # + conversation memory) with citations, confidence scoring, and hallucination
    # prevention. It internally composes the deterministic reliability/SRE
    # retrieval engine. When ANTHROPIC_API_KEY is unset (tests/CI) it produces a
    # deterministic, grounded answer synthesized from the retrieved evidence (no
    # network); the same deterministic path is the live fallback. Always on.
    # Live generation model (falls back to ANTHROPIC_MODEL when blank).
    COPILOT_MODEL: str = ""
    COPILOT_MAX_TOKENS: int = 1500
    COPILOT_TEMPERATURE: float = 0.2
    # Retry/backoff for transient LLM failures before falling back deterministically.
    COPILOT_MAX_RETRIES: int = 2
    COPILOT_RETRY_BASE_DELAY_SECONDS: float = 0.5
    # Whether the SSE streaming endpoint is enabled.
    COPILOT_STREAMING_ENABLED: bool = True
    # RAG: number of knowledge chunks retrieved, and how many recent records to
    # build the per-request semantic corpus from.
    COPILOT_RAG_TOP_K: int = 5
    COPILOT_RAG_CORPUS_LIMIT: int = 200
    # How many prior conversation turns are replayed as memory.
    COPILOT_MEMORY_TURNS: int = 8
    # Answers below this confidence (0-100) are flagged low-confidence.
    COPILOT_MIN_CONFIDENCE: int = 40

    # --- Collaborative War Room (app.services.war_room_collab) ---
    # Real-time incident response: WebSocket live messages, human + AI
    # participants, mentions, threads, uploads/evidence, approvals, typing
    # indicators and presence. Broadcast uses Redis pub/sub across workers when
    # available, falling back to in-process fan-out (single worker / tests).
    # Default OFF: the shipped UI consumes only the advisory war room; the
    # real-time collaboration surface is opt-in until a client uses it.
    WAR_ROOM_REALTIME_ENABLED: bool = False
    # --- Opt-in surfaces not yet wired into the shipped UI (default OFF) ---
    # ROI calculator API.
    ROI_ENABLED: bool = False
    # Directory where uploaded war-room files are stored (served via an
    # org-scoped download endpoint, never the public /static mount). Resolved
    # relative to :data:`LOCAL_DATA_DIR`.
    WAR_ROOM_UPLOAD_DIR: str = "uploads/war_room"
    WAR_ROOM_MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024
    WAR_ROOM_ALLOWED_UPLOAD_TYPES: list[str] = [
        "image/png", "image/jpeg", "image/gif", "image/webp",
        "application/pdf", "text/plain", "text/csv",
        "application/json", "application/zip", "application/octet-stream",
    ]
    # AI participant streams its grounded answer in chunks of this size.
    WAR_ROOM_AI_STREAM_CHUNK: int = 48
    # Redis pub/sub channel prefix for war-room broadcast.
    WAR_ROOM_PUBSUB_PREFIX: str = "warroom"

    # --- Sprint 38B: Scheduled workflow runs ---
    # Background loop that triggers due workflow schedules. Disabled by default
    # under tests/CI; enabled in real deployments. The tick cadence controls how
    # often due schedules are polled (the spec calls for once per minute).
    WORKFLOW_SCHEDULER_ENABLED: bool = True
    WORKFLOW_SCHEDULER_INTERVAL_SECONDS: int = 60

    # --- Sprint 42A: Continuous monitoring & auto incident creation ---
    # Background loop that polls connected monitoring providers, deduplicates
    # alerts, auto-creates incidents (reusing the investigation engine), and
    # notifies humans. Disabled by default under tests/CI; enable in real
    # deployments. The spec calls for a 60s cadence.
    MONITORING_ENABLED: bool = False
    MONITORING_INTERVAL_SECONDS: int = 60
    # Window (minutes) within which repeated firings of the same logical alert
    # collapse onto one incident (occurrence_count++) instead of creating a new.
    MONITORING_DEDUP_WINDOW_MINUTES: int = 30
    # Outbound incident notifications. When a Slack webhook is configured the
    # notifier posts there; otherwise it degrades to a recorded (audited) send so
    # local/dev/test environments keep working unchanged. No secrets are logged.
    NOTIFICATIONS_ENABLED: bool = True
    SLACK_WEBHOOK_URL: str | None = None
    NOTIFICATION_EMAIL_FROM: str | None = None
    INCIDENT_LINK_BASE_URL: str = ""

    # --- Sprint 62A: Platform convergence -----------------------------------
    # Single switch for the converged platform APIs (events/notifications/search/
    # activity/config/plugins/execution). On by default; degrades offline.
    PLATFORM_CONVERGENCE_ENABLED: bool = True
    # Unified notification platform channels. All degrade to deterministic,
    # network-free "simulated" delivery when their endpoint is not configured.
    TEAMS_WEBHOOK_URL: str | None = None
    DISCORD_WEBHOOK_URL: str | None = None
    SMS_PROVIDER_URL: str | None = None
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_USE_TLS: bool = True

    # --- Sprint 42B: Intelligent on-call & escalation ---
    # Background loop that advances unacknowledged incidents through their
    # escalation ladder (0/10/20/30 min …). Disabled by default under tests/CI.
    ESCALATION_ENABLED: bool = False
    ESCALATION_INTERVAL_SECONDS: int = 60

    # Universal Discovery loop: read-only discovery across EVERY
    # connected integration (GitHub/GitLab/Jira/Slack/Teams + the infrastructure
    # providers), maintaining the Platform Knowledge Graph. Disabled by default
    # under tests/CI; enable in real deployments. Minimum cadence is 60s.
    INTEGRATION_PIPELINE_SYNC_ENABLED: bool = True
    JOB_CRON_INTEGRATION_PIPELINE_SYNC_SECONDS: int = 300
    INTEGRATION_GITOPS_SYNC_ENABLED: bool = True
    JOB_CRON_INTEGRATION_GITOPS_SYNC_SECONDS: int = 300

    UNIVERSAL_DISCOVERY_ENABLED: bool = False
    UNIVERSAL_DISCOVERY_INTERVAL_SECONDS: int = 600

    # --- HTTP security headers (app.middleware.security_headers) ---
    # Adds HSTS / CSP / X-Frame-Options / X-Content-Type-Options / Referrer-Policy
    # / Permissions-Policy / Cache-Control to every response. HSTS and
    # ``upgrade-insecure-requests`` are emitted only in production (ENVIRONMENT
    # == "production"); the Swagger/ReDoc routes receive a relaxed CSP so the API
    # docs keep working.
    SECURITY_HEADERS_ENABLED: bool = True
    HSTS_MAX_AGE: int = 63072000  # 2 years (seconds), production only

    # --- CORS (app.main) ---
    # Comma-separated list of allowed browser origins (e.g.
    # ``https://app.example.com,https://admin.example.com``). In production an
    # empty list disables cross-origin access. Development falls back to ``*``
    # without credentials (browsers reject ``*`` with ``allow_credentials``).
    CORS_ALLOWED_ORIGINS: list[str] = []
    CORS_ALLOW_CREDENTIALS: bool = True

    # Writable local data root (uploads, health probes). Must be writable in
    # production; static assets may be mounted read-only in containers.
    LOCAL_DATA_DIR: str = "data"

    # --- SSRF protection (app.security.ssrf) ---
    # Guards every outbound HTTP request made on behalf of a tenant (integration
    # verification, monitoring ingestion, discovery) against server-side request
    # forgery. Enabled by default. ``ALLOW_PRIVATE_NETWORKS`` is for on-prem /
    # self-hosted deployments where legitimate targets live on private ranges;
    # even when True, loopback / link-local / cloud-metadata are always blocked.
    SSRF_PROTECTION_ENABLED: bool = True
    SSRF_ALLOW_PRIVATE_NETWORKS: bool = False

    # --- Distributed rate limiting (app.middleware.rate_limit) ---
    # Sliding-window rate limiting on sensitive endpoints (auth, integration
    # connect, webhooks). Backed by Redis so limits are shared across every API
    # replica; when ``REDIS_URL`` is unset (or the redis client is unavailable)
    # the limiter transparently falls back to an in-process window so single-node
    # deployments and tests still work.
    #
    # Each limit is expressed as ``"<max_requests>/<window_seconds>"``. They are
    # applied independently to each in-scope identity (IP / organization / user);
    # the most restrictive scope wins. ``RATE_LIMIT_FAIL_OPEN`` controls whether a
    # backend outage allows traffic through (availability) or blocks it (strict).
    RATE_LIMIT_ENABLED: bool = True
    REDIS_URL: str | None = None
    RATE_LIMIT_TRUST_FORWARDED_FOR: bool = True
    RATE_LIMIT_FAIL_OPEN: bool = True
    RATE_LIMIT_KEY_PREFIX: str = "nexora:rl"

    RATE_LIMIT_AUTH_LOGIN: str = "5/60"
    RATE_LIMIT_AUTH_REGISTER: str = "5/300"
    RATE_LIMIT_AUTH_REFRESH: str = "30/60"
    RATE_LIMIT_INTEGRATIONS_CONNECT: str = "20/60"
    RATE_LIMIT_WEBHOOKS: str = "240/60"

    # --- Global request body size limits (app.middleware.body_limit) ---
    # Rejects oversized payloads with HTTP 413 before they reach a route. The
    # limit is chosen by Content-Type: multipart uploads get a larger budget than
    # JSON/other bodies. Individual routes may override the limit (see
    # app.middleware.body_limit.set_route_body_limit).
    BODY_LIMIT_ENABLED: bool = True
    MAX_JSON_BODY_BYTES: int = 5 * 1024 * 1024  # 5 MB (JSON + default)
    MAX_MULTIPART_BODY_BYTES: int = 100 * 1024 * 1024  # 100 MB (file uploads)

    # --- Distributed tracing (app.observability.tracing, OpenTelemetry) ---
    # Opt-in (disabled by default). When enabled, instruments FastAPI, SQLAlchemy,
    # httpx, Redis and adds custom spans for LLM calls + background schedulers,
    # exporting to an OTLP / Jaeger / Zipkin / console backend. The OTLP and
    # Zipkin exporters ship in requirements; the Jaeger exporter is an optional
    # extra (``pip install opentelemetry-exporter-jaeger``). All imports are lazy
    # so the app boots without any OpenTelemetry packages installed.
    TRACING_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "nexora-api"
    TRACING_EXPORTER: str = "otlp"  # otlp | jaeger | zipkin | console | none
    TRACING_ENDPOINT: str | None = None  # exporter endpoint (defaults per exporter)
    TRACING_SAMPLE_RATIO: float = 1.0  # 0.0..1.0 (parent-based ratio sampler)

    # --- Async job queue (app.jobs, Arq + Redis) ---
    # Moves long-running work (AI Teams, AI workflows, discovery, monitoring,
    # report generation) out of the request/response cycle onto an Arq worker.
    # Disabled by default: when off, the trigger endpoints keep running the work
    # synchronously in-request (and the in-process scheduler loops drive periodic
    # work) so single-node deployments and the test suite behave unchanged. When
    # ``JOB_QUEUE_ENABLED`` is on, trigger endpoints enqueue a job and return
    # 202 + a job id, and the Arq worker (``arq app.jobs.worker.WorkerSettings``)
    # runs the work and the periodic cron jobs instead of the in-process loops.
    JOB_QUEUE_ENABLED: bool = False
    # Redis DSN for the queue; falls back to ``REDIS_URL`` when unset.
    JOB_QUEUE_REDIS_URL: str | None = None
    JOB_QUEUE_NAME: str = "nexora:jobs"
    # Priority queues: deploy a dedicated worker per queue (high drains first).
    # Select which queue a worker drains via JOB_WORKER_QUEUE (defaults to the
    # standard queue). Producers route jobs by ``priority`` (see app.jobs.submit).
    JOB_QUEUE_NAME_HIGH: str = "nexora:jobs:high"
    JOB_QUEUE_NAME_LOW: str = "nexora:jobs:low"
    JOB_WORKER_QUEUE: str | None = None
    # Whether THIS worker process registers the periodic cron jobs. Set true on a
    # single dedicated scheduler node and false on the job-processing workers, so
    # cron is owned by one Deployment. (Even if multiple register it, Arq's
    # cron(unique=True) + the Redis scheduler lock keep execution exactly-once.)
    JOB_CRON_ENABLED: bool = True
    # Retry policy: total attempts per job and the exponential backoff base.
    JOB_MAX_TRIES: int = 3
    JOB_RETRY_BASE_DELAY_SECONDS: float = 5.0
    # Hard per-job timeout and how long Arq keeps a result in Redis.
    JOB_TIMEOUT_SECONDS: int = 900
    JOB_KEEP_RESULT_SECONDS: int = 3600
    # Worker concurrency (max jobs running at once).
    JOB_MAX_CONCURRENCY: int = 10
    # Cron cadences (seconds) for the periodic jobs the worker drives in place of
    # the in-process loops. Each respects its subsystem's *_ENABLED flag.
    JOB_CRON_WORKFLOW_SECONDS: int = 60
    JOB_CRON_MONITORING_SECONDS: int = 60
    JOB_CRON_ESCALATION_SECONDS: int = 60
    JOB_CRON_UNIVERSAL_DISCOVERY_SECONDS: int = 600

    # --- Unified Redis integration (app.redis) ---
    # A single shared async Redis client (built from REDIS_URL above) powers the
    # cache, server-side session store, JWT denylist, distributed/scheduler locks
    # and the notification queue. Every feature degrades to an equivalent
    # in-process fallback when REDIS_URL is unset (or redis is unavailable), so
    # single-node deployments and the test suite keep working unchanged. Keys are
    # namespaced under ``REDIS_KEY_PREFIX``.
    REDIS_KEY_PREFIX: str = "nexora"
    REDIS_MAX_CONNECTIONS: int = 50

    # Cache (app.redis.cache): TTL'd key/value cache with get_or_set.
    CACHE_ENABLED: bool = True
    CACHE_DEFAULT_TTL_SECONDS: int = 300
    # Per-domain cache TTLs (seconds). Each namespace is versioned so writes
    # invalidate it in O(1); the TTL is a backstop.
    GRAPH_CACHE_TTL_SECONDS: int = 300
    ORG_SETTINGS_CACHE_TTL_SECONDS: int = 300

    # Server-side session store (app.redis.sessions): records active sessions
    # keyed by the access-token jti so they can be listed and revoked.
    SESSION_STORE_ENABLED: bool = True

    # JWT denylist (app.redis.denylist): revoked access-token jtis are rejected
    # by ``get_current_user`` until they would have expired anyway. Enables real
    # server-side logout / "revoke session" despite stateless JWTs.
    JWT_DENYLIST_ENABLED: bool = True

    # Distributed locks (app.redis.locks): mutual exclusion across replicas. Used
    # to ensure only one instance runs each scheduler tick when multiple API
    # workers each run the in-process loops.
    DISTRIBUTED_LOCK_ENABLED: bool = True
    SCHEDULER_LOCK_TTL_SECONDS: int = 300

    # Notification queue (app.redis.notifications): when enabled, outbound
    # incident notifications are buffered on a Redis list and drained by a
    # background worker instead of being sent inline in the request/tick. When
    # disabled (default) notifications are sent inline as before.
    NOTIFICATION_QUEUE_ENABLED: bool = False
    NOTIFICATION_QUEUE_POLL_SECONDS: int = 5
    NOTIFICATION_QUEUE_MAX_ATTEMPTS: int = 5

    # --- Enterprise SSO (app.services.sso) ---
    # OIDC/OAuth2 (Microsoft Entra, Okta, Google Workspace, Ping, generic OIDC)
    # and SAML 2.0 single sign-on. Identity-provider connections are configured
    # at runtime (per organization or tenant-wide) and stored in the database;
    # these settings are process-level toggles and defaults.
    SSO_ENABLED: bool = True
    # Absolute public origin (scheme://host[:port]) used to build IdP-facing
    # redirect/callback/ACS/metadata URLs. When unset the incoming request's
    # base URL is used (works for single-origin deployments and tests).
    SSO_PUBLIC_BASE_URL: str | None = None
    # TTL for the short-lived OIDC state/nonce/PKCE record (CSRF protection).
    SSO_STATE_TTL_SECONDS: int = 600
    # Default org role granted to JIT-provisioned SSO users when no role mapping
    # matches. One of the OrganizationRole values.
    SSO_DEFAULT_ROLE: str = "VIEWER"
    # Allow SAML responses without a verifiable signature (DEV ONLY — never in
    # production; signed assertions are required by default).
    SSO_ALLOW_UNSIGNED_SAML: bool = False

    # --- SCIM 2.0 provisioning (app.services.scim) ---
    # Automated user/group provisioning from an IdP (Okta, Microsoft Entra, ...).
    # SCIM requests authenticate with a per-organization bearer token; all
    # operations are scoped to that token's organization (multi-tenant safe).
    SCIM_ENABLED: bool = True
    # Org role assigned to SCIM-provisioned members with no mapping-bearing group.
    SCIM_DEFAULT_ROLE: str = "VIEWER"
    # Maximum operations accepted in a single /Bulk request.
    SCIM_BULK_MAX_OPERATIONS: int = 1000

    # --- Audit logging (tamper-evident, app.services.audit) ---
    # Audit events are append-only and chained with a per-organization SHA-256
    # hash chain so tampering (modification, deletion, reordering) is detectable
    # via the integrity-verification endpoint.
    # Retention purge removes entries older than this many days (0 = keep
    # forever). Purge is the only sanctioned deletion path.
    AUDIT_RETENTION_DAYS: int = 0
    # Upper bound on rows returned by a single export (CSV/JSON) to bound memory.
    AUDIT_EXPORT_MAX_ROWS: int = 50000

    # --- Enterprise identity & access (Sprint 61A, app.services.identity) ---
    # API keys (organization/personal/service-account), service accounts,
    # database-backed sessions, organization security policies and MFA (TOTP).
    IDENTITY_ENABLED: bool = True
    # Issuer label shown in authenticator apps for TOTP enrollment.
    MFA_ISSUER: str = "Nexora"
    # Record database-backed sessions on login (device history, refresh rotation,
    # concurrent-session limits). Independent of the Redis access-token denylist.
    DB_SESSIONS_ENABLED: bool = True

    # --- Sprint 61C: Commercial platform (billing / licensing / quotas) ---
    # Organization-scoped plans, usage metering, quota enforcement, billing
    # providers, subscription lifecycle, license engine, feature flags and
    # webhooks. All limits are configurable (stored on plans); nothing hardcoded.
    BILLING_ENABLED: bool = True
    # Seed the default plan catalog (Free…Enterprise) on startup if absent.
    BILLING_SEED_DEFAULT_PLANS: bool = True
    # Plan slug new organizations are placed on by default.
    BILLING_DEFAULT_PLAN_SLUG: str = "free"
    # When true, quota checks raise; when false they only warn/meter (useful for
    # gradual rollout). Per-plan policy can still set enforcement="soft".
    BILLING_QUOTA_ENFORCEMENT: bool = True
    # HMAC secret for offline license signing/verification (independent of any
    # billing provider). Falls back to JWT_SECRET_KEY when unset.
    LICENSE_SIGNING_KEY: str | None = None
    # Stripe (optional). When unset the Stripe provider runs in stub mode so dev
    # and tests work without network/credentials.
    STRIPE_API_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    # Cron cadences (seconds) for the commercial background jobs.
    JOB_CRON_QUOTA_RESET_SECONDS: int = 3600
    JOB_CRON_USAGE_AGGREGATION_SECONDS: int = 3600
    JOB_CRON_LICENSE_EXPIRATION_SECONDS: int = 86400
    JOB_CRON_BILLING_LIFECYCLE_SECONDS: int = 3600

    # --- Sprint 61D: Unified AI Platform & Agent Runtime ---
    # One runtime powers every AI capability. Providers are pluggable; with no
    # keys the platform runs deterministically offline (dev/test).
    AI_PLATFORM_ENABLED: bool = True
    AI_PLATFORM_DEFAULT_PROVIDER: str = "anthropic"
    # Default org routing policy: cheapest|fastest|highest_quality|deterministic|custom
    AI_PLATFORM_DEFAULT_ROUTING: str = "highest_quality"
    AI_PLATFORM_CACHE_ENABLED: bool = True
    AI_PLATFORM_CACHE_TTL_SECONDS: int = 600
    AI_PLATFORM_MAX_RETRIES: int = 2
    AI_PLATFORM_RETRY_BASE_DELAY_SECONDS: float = 0.25
    AI_PLATFORM_FALLBACK_ENABLED: bool = True
    AI_TOOL_DEFAULT_TIMEOUT_SECONDS: float = 20.0
    AI_TOOL_MAX_RETRIES: int = 1
    AI_AGENT_MAX_STEPS: int = 12
    AI_MEMORY_TOP_K: int = 5
    # Additional pluggable provider credentials (Anthropic/OpenAI already exist).
    AZURE_OPENAI_API_KEY: str | None = None
    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_API_VERSION: str = "2024-10-21"
    GEMINI_API_KEY: str | None = None
    OLLAMA_BASE_URL: str | None = None
    OPENROUTER_API_KEY: str | None = None
    AWS_BEDROCK_REGION: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    # Cron cadences for AI platform maintenance jobs.
    JOB_CRON_AI_EVALUATION_SECONDS: int = 3600
    JOB_CRON_AI_MEMORY_CONSOLIDATION_SECONDS: int = 86400

    # --- Database migrations (app.database.migration_check) ---
    # The schema is owned by Alembic; the app no longer runs create_all() at
    # startup. When enabled, startup verifies the database is migrated to head
    # and refuses to start otherwise. Automatically skipped for sqlite (used by
    # the test suite / local dev, which create the schema directly).
    DB_MIGRATION_CHECK_ENABLED: bool = True

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # --- Sprint 35A: Enterprise credential & secret management ---
    # AES-256-GCM master key for encrypting customer infrastructure credentials.
    # Startup fails when this is missing (see app.security.secrets.ensure_master_key).
    MASTER_ENCRYPTION_KEY: str | None = None

    # --- Sprint 33B: Real Azure Container Apps deployment ---
    # When all required values below are set, deployments build a real container
    # image with ACR Build Tasks and ship it to Azure Container Apps. When any are
    # missing, the platform transparently falls back to the simulated provider so
    # local/dev/test environments keep working unchanged.
    AZURE_SUBSCRIPTION_ID: str | None = None
    AZURE_TENANT_ID: str | None = None
    AZURE_CLIENT_ID: str | None = None
    AZURE_CLIENT_SECRET: str | None = None

    AZURE_RESOURCE_GROUP: str = "applyn-rg"
    AZURE_REGION: str = "eastus"

    ACR_NAME: str | None = None
    ACR_LOGIN_SERVER: str | None = None

    CONTAINER_APPS_ENVIRONMENT: str | None = None
    APP_BASE_DOMAIN: str | None = None

    DEPLOYMENT_TIMEOUT_SECONDS: int = 600
    DEPLOYMENT_HEALTH_POLL_INTERVAL_SECONDS: int = 10
    DEPLOYMENT_HEALTH_PATH: str = "/health"

    # --- Sprint 62B: Enterprise Production Hardening & Scale ---
    # Master switch for the hardening additions (event consumer, execution
    # recovery, search indexing, anomaly detection, archive). Everything below is
    # additive and degrades to the previous behaviour when disabled.
    HARDENING_ENABLED: bool = True

    # Event bus hardening (app.platform.events). A leader-elected consumer drains
    # the durable outbox (PENDING/FAILED events) across replicas so delivery is
    # exactly-once even with multiple workers. Disabled by default so the test
    # suite and inline publish path are unaffected; enable in production.
    EVENT_CONSUMER_ENABLED: bool = False
    EVENT_CONSUMER_POLL_SECONDS: float = 2.0
    EVENT_CONSUMER_BATCH: int = 100
    EVENT_CONSUMER_LOCK_TTL_SECONDS: int = 30

    # AI platform hardening (app.ai.health / budget / cache). Provider circuit
    # breaker: after N consecutive failures a provider is disabled for a cooldown
    # so routing skips it (auto-recovers via a half-open probe).
    AI_PROVIDER_CB_THRESHOLD: int = 3
    AI_PROVIDER_CB_COOLDOWN_SECONDS: float = 30.0
    # Per-organization daily token budget (0 = unlimited). Enforced before a live
    # call when AI_TOKEN_BUDGET_ENABLED is on.
    AI_TOKEN_BUDGET_ENABLED: bool = False
    AI_DAILY_TOKEN_BUDGET: int = 0
    # Embedding + semantic response caches (read-through, versioned per org).
    AI_EMBEDDING_CACHE_ENABLED: bool = True
    AI_EMBEDDING_CACHE_TTL_SECONDS: int = 86400
    AI_SEMANTIC_CACHE_ENABLED: bool = False
    AI_SEMANTIC_CACHE_THRESHOLD: float = 0.95

    # Search platform (app.platform.search). Index-backed incremental search with
    # ranking profiles, synonyms, typo tolerance and analytics. Background
    # indexing keeps the index warm without full rebuilds.
    SEARCH_INDEX_ENABLED: bool = True
    SEARCH_ANALYTICS_ENABLED: bool = True
    SEARCH_TYPO_TOLERANCE: bool = True
    JOB_CRON_SEARCH_INDEX_SECONDS: int = 900

    # Execution engine (app.platform.execution). Leases + heartbeats let exactly
    # one worker own a run; stalled runs (expired lease) are recovered and runs
    # exceeding their timeout are failed/retried by the recovery cron.
    EXECUTION_LEASE_TTL_SECONDS: int = 120
    EXECUTION_DEFAULT_TIMEOUT_SECONDS: int = 1800
    EXECUTION_DEAD_RETENTION_DAYS: int = 7
    JOB_CRON_EXECUTION_RECOVERY_SECONDS: int = 60

    # Database optimization. Queries slower than this (ms) are logged with the
    # statement and duration (0 disables). Bulk/batch helpers live in
    # app.database.bulk; keyset pagination in app.database.pagination.
    DB_SLOW_QUERY_MS: int = 0

    # Archive strategy (app.services.archive). Old terminal jobs and processed
    # domain events beyond the retention window are archived/purged by a cron.
    ARCHIVE_ENABLED: bool = False
    ARCHIVE_EVENT_RETENTION_DAYS: int = 30
    JOB_CRON_ARCHIVE_SECONDS: int = 86400

    # Security hardening. CSP nonce + Trusted Types are opt-in (they alter the
    # CSP and can affect inline scripts / DOM-XSS sinks, so default off until the
    # SPA is verified against them). Anomaly detection flags suspicious logins.
    CSP_NONCE_ENABLED: bool = False
    TRUSTED_TYPES_ENABLED: bool = False
    LOGIN_ANOMALY_DETECTION_ENABLED: bool = True
    LOGIN_FAILURE_LOCK_THRESHOLD: int = 0  # 0 = no lockout, only audit
    # Additional accepted (retired) JWT signing secrets for rotation. New tokens
    # are always signed with JWT_SECRET_KEY; tokens signed with a previous secret
    # still verify until they expire. Comma-separated.
    JWT_SECRET_KEYS_RETIRED: str = ""
    JOB_CRON_API_KEY_ROTATION_SECONDS: int = 86400
    JOB_CRON_AUDIT_VERIFY_SECONDS: int = 86400

    # Multi-region readiness. Logical region for this deployment; clock-skew
    # tolerance bounds replication-event acceptance. Object storage + CDN are
    # abstractions (local/dev fallback) — no active-active logic.
    REGION: str = "default"
    CLOCK_SKEW_TOLERANCE_SECONDS: int = 300
    OBJECT_STORE_BACKEND: str = "local"  # local | s3
    OBJECT_STORE_BUCKET: str | None = None
    OBJECT_STORE_LOCAL_DIR: str = "/tmp/nexora-objects"
    CDN_BASE_URL: str | None = None

    # Operations. Maintenance mode short-circuits the API with 503 (health +
    # admin still reachable). Kill switches + feature rollout are config-backed.
    MAINTENANCE_MODE_ENABLED: bool = False
    MAINTENANCE_MODE_MESSAGE: str = "Nexora is undergoing scheduled maintenance."
    OPS_STATE_CACHE_TTL_SECONDS: int = 5

    # --- Sprint 63A: Product Excellence ---
    PRODUCT_EXCELLENCE_ENABLED: bool = True
    # Inbox notifications are created from domain events for org members.
    INBOX_FROM_EVENTS_ENABLED: bool = True
    # Product analytics: persist events (privacy-aware; no email/name in properties).
    PRODUCT_ANALYTICS_ENABLED: bool = True
    # Report schedule cron interval (seconds).
    JOB_CRON_REPORT_SCHEDULE_SECONDS: int = 3600

    # --- Sprint 63B: Autonomous SRE ---
    AUTONOMOUS_SRE_ENABLED: bool = True

    # --- Sprint 64A: GA Readiness ---
    GA_READINESS_ENABLED: bool = True

    # --- Sprint 63A: Multi-Cloud & Kubernetes Control Plane ---
    CONTROL_PLANE_ENABLED: bool = True

    # --- Sprint 63B: DevOps Delivery Platform ---
    DELIVERY_ENABLED: bool = True

    # --- Sprint 63C: DevOps & SRE Workspace ---
    OPS_WORKSPACE_ENABLED: bool = True

    # --- Sprint 64A: Platform Engineering (IaC) ---
    PLATFORM_ENGINEERING_ENABLED: bool = True

    # --- Sprint 64B: AI Platform Operator ---
    AI_OPERATOR_ENABLED: bool = True

    # --- Sprint 65B: Enterprise Observability Platform ---
    OBSERVABILITY_PLATFORM_ENABLED: bool = True

    # --- Sprint 65C: Enterprise Incident Response & On-Call Platform ---
    INCIDENT_RESPONSE_PLATFORM_ENABLED: bool = True

    # --- Sprint 65D: Enterprise DevSecOps & Cloud Security Platform ---
    SECURITY_PLATFORM_ENABLED: bool = True

    # --- Sprint 65G: Production integrations & operational readiness ---
    INTEGRATION_READINESS_ENABLED: bool = True
    INTEGRATION_HEALTH_INTERVAL_SECONDS: int = 300
    INTEGRATION_HEALTH_FAILURE_THRESHOLD: int = 3
    INTEGRATION_VALIDATION_FRESHNESS_HOURS: int = 24
    INTEGRATION_DESTROY_FRESHNESS_HOURS: int = 4

    # --- Sprint 66A: Production pilot readiness ---
    PILOT_MODE_ENABLED: bool = False
    PILOT_MODE_ALL_ORGS: bool = True
    PILOT_ORGANIZATION_IDS: list[str] = []
    PILOT_OPERATION_LIMIT: int = 5
    PILOT_MUTATION_COOLDOWN_MINUTES: int = 30
    PILOT_APPROVAL_EXPIRY_HOURS: int = 24
    JOB_CRON_CUSTOMER_PILOT_APPROVAL_REMINDERS_SECONDS: int = 300
    # Sprint 66C/66D — internal pilot integration scope (optional overrides)
    PILOT_INTERNAL_K8S_NAMESPACE: str = "nexora-pilot"
    PILOT_INTERNAL_GITHUB_REPO: str = "pilot-admin/pilot-test"
    PILOT_INTERNAL_PROMETHEUS_ENDPOINT: str = "http://pilot-prometheus:9090"
    PILOT_INTERNAL_K8S_REGISTRY_ID: str | None = None
    PILOT_INTERNAL_GITHUB_REGISTRY_ID: str | None = None
    PILOT_INTERNAL_PROMETHEUS_REGISTRY_ID: str | None = None
    # Sprint 67G — alerting & notification go-live validation
    PILOT_EMAIL_NOTIFICATIONS_ENABLED: bool = False
    PILOT_ALERT_TEST_ENABLED: bool = False
    PILOT_ALERT_WEBHOOK_URL: str | None = None
    PILOT_ALERT_EMAIL: str | None = None
    PILOT_CUSTOMER_PILOT_PROMETHEUS_ENDPOINT: str = "http://customer-pilot-prometheus:9090"

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def convert_postgres_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://") and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        # asyncpg doesn't accept sslmode in the URL — strip it
        import re
        v = re.sub(r"[?&]sslmode=[^&]*", "", v)
        v = re.sub(r"\?&", "?", v)
        v = v.rstrip("?")
        return v


settings = Settings()
