"""Commercial platform services (Sprint 61C).

* ``plans``          — plan catalog CRUD + clone + assignment
* ``defaults``       — default plan catalog (Free…Enterprise) seeding
* ``subscriptions``  — per-org subscription + lifecycle state machine
* ``metering``       — daily per-metric usage aggregation
* ``quota``          — quota resolution + enforcement (hard/soft/grace/warning)
* ``feature_flags``  — per-plan feature entitlement resolution (no hardcoding)
* ``licenses``       — SaaS/on-prem/offline license issue + signature validation
* ``usage_dashboard``— current/remaining/projected usage + overages
* ``providers``      — replaceable billing provider abstraction (Stripe/manual/enterprise)
* ``webhooks``       — commercial event emission (outbox + delivery)

Quota/limits are configurable on plans; nothing is hardcoded.
"""

from app.services.billing.quota import QuotaDecision, QuotaExceeded

__all__ = ["QuotaDecision", "QuotaExceeded"]
