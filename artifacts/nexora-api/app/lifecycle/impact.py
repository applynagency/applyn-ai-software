from app.models.lifecycle import RegenerationScope

FRONTEND_AGENT_CHAIN = [
    "uiux_designer",
    "frontend_architect",
    "frontend_v1",
    "frontend_v2",
    "frontend_v3",
    "frontend_code_review",
    "frontend_execution",
]

BACKEND_AGENT_CHAIN = [
    "backend_architect",
    "backend_v1",
    "backend_v2",
    "backend_v3",
    "backend_code_review",
    "backend_execution",
]

QA_AGENT_CHAIN = [
    "qa_architect",
    "unit_test_generator",
    "integration_test",
    "security_test",
    "performance_test",
    "qa_approval",
]

FINALIZATION_CHAIN = ["fullstack_assembly", "approval", "deployment"]


class ImpactAnalysisEngine:
    """Rule-based impact analyzer for post-deployment changes."""

    def analyze(
        self,
        *,
        change_request_title: str,
        change_request_description: str,
        scope: RegenerationScope,
    ) -> dict:
        text = f"{change_request_title}\n{change_request_description}".lower()
        frontend_terms = {
            "ui",
            "frontend",
            "dashboard",
            "report",
            "layout",
            "theme",
            "component",
            "react",
            "next",
        }
        backend_terms = {
            "backend",
            "api",
            "migration",
            "database",
            "model",
            "endpoint",
            "fastapi",
            "service",
        }
        bug_terms = {"bug", "fix", "error", "regression", "issue"}

        frontend_hits = sum(1 for t in frontend_terms if t in text)
        backend_hits = sum(1 for t in backend_terms if t in text)
        bug_hits = sum(1 for t in bug_terms if t in text)

        if scope == RegenerationScope.FRONTEND_ONLY:
            affected_agents = FRONTEND_AGENT_CHAIN + QA_AGENT_CHAIN + FINALIZATION_CHAIN
            affected_frontend_modules = ["ui", "routing", "state", "views"]
            affected_backend_modules = []
        elif scope == RegenerationScope.BACKEND_ONLY:
            affected_agents = BACKEND_AGENT_CHAIN + QA_AGENT_CHAIN + FINALIZATION_CHAIN
            affected_frontend_modules = []
            affected_backend_modules = ["api", "models", "repositories", "services"]
        else:
            affected_agents = (
                BACKEND_AGENT_CHAIN + FRONTEND_AGENT_CHAIN + QA_AGENT_CHAIN + FINALIZATION_CHAIN
            )
            affected_frontend_modules = ["ui", "routing", "state", "views"]
            affected_backend_modules = ["api", "models", "repositories", "services"]

        if frontend_hits > 0 and scope != RegenerationScope.BACKEND_ONLY:
            affected_frontend_modules.append("feature-change")
        if backend_hits > 0 and scope != RegenerationScope.FRONTEND_ONLY:
            affected_backend_modules.append("feature-change")

        estimated_effort_hours = max(2.0, float(len(affected_agents)))
        risk_score = min(100.0, 20.0 + frontend_hits * 8 + backend_hits * 8 + bug_hits * 6)

        return {
            "affected_frontend_modules": sorted(set(affected_frontend_modules)),
            "affected_backend_modules": sorted(set(affected_backend_modules)),
            "affected_agents": affected_agents,
            "affected_workflows": ["PRODUCT"],
            "estimated_effort_hours": round(estimated_effort_hours, 1),
            "risk_score": round(risk_score, 1),
            "scope": scope.value,
        }


__all__ = [
    "FRONTEND_AGENT_CHAIN",
    "BACKEND_AGENT_CHAIN",
    "QA_AGENT_CHAIN",
    "FINALIZATION_CHAIN",
    "ImpactAnalysisEngine",
]
