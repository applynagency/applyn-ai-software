"""Sprint 53B — Executive ROI Calculator schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ROIRequest(BaseModel):
    """Inputs for an ROI calculation."""

    engineer_count: int = Field(..., gt=0, description="Number of engineers.")
    average_salary: float = Field(..., gt=0, description="Average annual fully-loaded salary (USD).")
    monthly_incidents: float = Field(..., ge=0, description="Incidents per month.")
    average_mttr_hours: float = Field(..., ge=0, description="Average mean-time-to-resolve in hours.")
    deployments_per_month: float = Field(..., ge=0, description="Deployments per month.")
    oncall_burden_hours_per_week: float = Field(
        ..., ge=0, description="On-call / toil hours per week, per engineer."
    )

    # Optional economics (sensible defaults applied when omitted).
    downtime_cost_per_hour: float | None = Field(default=None, ge=0)
    platform_annual_cost: float | None = Field(default=None, ge=0)

    # Optional improvement-factor overrides (fractions 0..1).
    mttr_reduction_pct: float | None = Field(default=None, ge=0, le=1)
    incident_reduction_pct: float | None = Field(default=None, ge=0, le=1)
    oncall_reduction_pct: float | None = Field(default=None, ge=0, le=1)
    deploy_hours_saved_each: float | None = Field(default=None, ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "engineer_count": 50,
                "average_salary": 165000,
                "monthly_incidents": 40,
                "average_mttr_hours": 4,
                "deployments_per_month": 120,
                "oncall_burden_hours_per_week": 6,
            }
        }
    )


class ROIOutputs(BaseModel):
    monthly_savings: float
    annual_savings: float
    roi_percentage: float
    payback_period_months: float | None = None


class ROIForecastRow(BaseModel):
    year: int
    gross_savings: float
    platform_cost: float
    net_savings: float
    cumulative_roi_percentage: float


class ROIResult(BaseModel):
    inputs: dict
    assumptions: dict
    calculations: dict
    outputs: ROIOutputs
    forecast: list[ROIForecastRow]
    executive_summary: str


class ROIAssumptions(BaseModel):
    mttr_reduction_pct: float
    incident_reduction_pct: float
    oncall_reduction_pct: float
    deploy_hours_saved_each: float
    downtime_cost_per_hour: float
    platform_cost_per_engineer_year: float
    responders_per_incident: int
    working_hours_per_year: int
    weeks_per_month: float
