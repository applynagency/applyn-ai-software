"""Sprint 53D - Sales & Demo Enablement schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ValuePropositionRequest(BaseModel):
    persona: str = Field(..., description="CTO | VP_ENGINEERING | DEVOPS_MANAGER | STARTUP_FOUNDER")
    company_name: str | None = Field(default=None, max_length=200)


class ProposalRequest(BaseModel):
    company_name: str = Field(..., max_length=200)
    engineer_count: int = Field(..., gt=0)
    tier: str | None = Field(default=None, description="STARTER | GROWTH | SCALE | ENTERPRISE")
    term_months: int = Field(default=12, gt=0, le=120)
    contact_name: str | None = Field(default=None, max_length=200)
    prepared_by: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)

    model_config = {
        "json_schema_extra": {
            "example": {
                "company_name": "Acme Corp",
                "engineer_count": 40,
                "tier": "GROWTH",
                "term_months": 12,
            }
        }
    }
