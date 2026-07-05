"""Sprint 35B — Bring Your Own Infrastructure (BYOI) onboarding.

Connection testing / validation for customer-supplied infrastructure. This
package only validates connectivity & permissions for onboarding; it does NOT
modify or call the deployment providers, agents, QA, or DevOps chain.
"""

from app.infrastructure.validator import (
    CheckResult,
    InfrastructureValidator,
    ValidationReport,
)

__all__ = ["CheckResult", "InfrastructureValidator", "ValidationReport"]
