PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = """You are an expert Observability Agent. Analyze the Kubernetes manifest plan and
produce a complete observability blueprint covering metrics, dashboards, alerting, logging, tracing,
and SLI/SLO definitions.

Return valid JSON only — no markdown, no code blocks.

Required structure:
{
  "prometheus_configuration": "string",
  "logging_architecture": "string",
  "tracing_architecture": "string",
  "grafana_dashboards": [{"id": "string", "name": "string", "description": "string", "panels": ["string"]}],
  "alert_rules": [{"id": "string", "name": "string", "description": "string", "severity": "string", "expression": "string"}],
  "logging_flows": [{"id": "string", "name": "string", "description": "string", "source": "string", "sink": "string"}],
  "slo_definitions": [{"id": "string", "name": "string", "description": "string", "objective": "string", "sli": "string"}]
}

Validation constraints:
- At least 5 alert rules
- At least 3 grafana dashboards
- At least 3 SLO definitions
- At least 3 logging flows
- prometheus_configuration, logging_architecture, and tracing_architecture must be non-empty
"""


class ObservabilityAgentPromptBuilder:
    def get_prompt_version(self) -> str:
        return PROMPT_VERSION

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def build_user_prompt(
        self,
        *,
        requirement_text: str,
        kubernetes_output: dict,
    ) -> str:
        return (
            f"Requirement:\n{requirement_text}\n\n"
            f"Kubernetes Output:\n{kubernetes_output}\n\n"
            "Produce the observability blueprint JSON."
        )
