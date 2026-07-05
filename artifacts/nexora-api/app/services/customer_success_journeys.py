"""Sprint 56D.3 - End-to-End Customer Journey Documentation.

Per-stage training detail for the four end-to-end customer journeys, plus a
Mermaid diagram per journey. Pure data with no imports from
``customer_success_content`` (which imports this module and applies it), so there
is no circular import.

For every stage we provide:
* navigation     - the click path to reach the screen
* route          - the app route (used to render the stage screenshot)
* expected_screen- what the customer should see on screen
* internal       - what happens internally
* common_issues  - what can go wrong
* recovery_steps - how to recover

``expected_outcome`` already lives on the base stage in customer_success_content.
Lists are ordered to match the journey's stages by position.
"""

from __future__ import annotations

# Mermaid diagram per journey.
JOURNEY_DIAGRAMS: dict[str, str] = {
    "infrastructure-onboarding": (
        "graph LR\n"
        "  A[Connect Provider] --> B[Discovery]\n"
        "  B --> C[Service Mapping]\n"
        "  C --> D[Dependency Discovery]\n"
        "  D --> E[SLO Creation]\n"
        "  E --> F[Monitoring Setup]\n"
        "  F --> G[Org Ready]"
    ),
    "incident-management": (
        "graph LR\n"
        "  A[Alert] --> B[Incident]\n"
        "  B --> C[Timeline]\n"
        "  C --> D[Change Intelligence]\n"
        "  D --> E[Recommendations]\n"
        "  E --> F[Remediation]\n"
        "  F --> G[Postmortem]"
    ),
    "safe-deployment": (
        "graph LR\n"
        "  A[Deployment Risk] --> B[Deployment Safety]\n"
        "  B --> C[Change Failure Prediction]\n"
        "  C --> D[Deployment Review]\n"
        "  D --> E[Ship / Gate / Canary]"
    ),
    "executive-reporting": (
        "graph LR\n"
        "  A[SLO] --> B[Capacity]\n"
        "  B --> C[Cost]\n"
        "  C --> D[Reliability Dashboard]\n"
        "  D --> E[Executive Report]"
    ),
}

# Per-stage detail, ordered to match the stages in customer_success_content.
STAGE_DETAIL: dict[str, list[dict[str, object]]] = {}

STAGE_DETAIL["infrastructure-onboarding"] = [
    {
        "navigation": ["Sidebar", "Get started", "Onboarding", "Connect Provider"],
        "route": "/onboarding",
        "expected_screen": ["Provider selection grid", "Per-provider connectivity status", "Validate button"],
        "internal": "Selected provider credentials are validated read-only against each provider's API and then discarded; nothing is stored.",
        "common_issues": [
            "Validation shows 'missing fields' for a provider.",
            "Validation fails with an authentication error.",
        ],
        "recovery_steps": [
            "Fill in the listed fields, or continue - validation is informational and never blocks setup.",
            "Re-enter credentials using a read-only role/token and validate again.",
        ],
    },
    {
        "navigation": ["Get started", "Onboarding", "Discovery"],
        "route": "/discovery",
        "expected_screen": ["Discovery progress per provider", "Discovered asset counts", "Run discovery control"],
        "internal": "The discovery engine enumerates resources through read-only provider APIs and normalizes them into a common asset model.",
        "common_issues": [
            "Discovery returns 0 assets.",
            "Discovery is slow or appears stuck.",
        ],
        "recovery_steps": [
            "Re-run with a read-only role attached to at least one account/cluster.",
            "Confirm provider connectivity, then re-run discovery from the Discovery page.",
        ],
    },
    {
        "navigation": ["Sidebar", "Reliability", "Services"],
        "route": "/services",
        "expected_screen": ["Service mapping summary", "Grouped services list", "Unmapped assets flag"],
        "internal": "The service mapper clusters related assets into logical services using naming, tags, and signals.",
        "common_issues": [
            "Services look wrong or over-merged.",
            "Some assets are not grouped into any service.",
        ],
        "recovery_steps": [
            "Adjust mappings; consistent tagging improves automatic grouping.",
            "Map orphaned assets to a service so attribution is complete.",
        ],
    },
    {
        "navigation": ["Sidebar", "Reliability", "Dependency Graph"],
        "route": "/dependencies",
        "expected_screen": ["Dependency edges list", "Directed dependency graph", "Blast radius"],
        "internal": "The dependency mapper infers directed edges between services from network, naming, and traffic signals.",
        "common_issues": [
            "Dependencies are missing or sparse.",
            "An unexpected dependency edge appears.",
        ],
        "recovery_steps": [
            "Connect more providers and re-run discovery so inference has more signal.",
            "Verify the edge in the graph; re-run discovery after the topology stabilizes.",
        ],
    },
    {
        "navigation": ["Sidebar", "Reliability", "SLOs"],
        "route": "/slos",
        "expected_screen": ["Generated SLO list", "Target vs current", "SLO coverage tiles"],
        "internal": "The SLO generator creates default objectives per service and the evaluator computes initial compliance and coverage.",
        "common_issues": [
            "SLO coverage is lower than expected.",
            "A service has no SLOs.",
        ],
        "recovery_steps": [
            "Ensure services were mapped first, then regenerate SLOs.",
            "Generate an SLO for the service from the SLOs page.",
        ],
    },
    {
        "navigation": ["Sidebar", "Operations", "Monitoring"],
        "route": "/monitoring",
        "expected_screen": ["Active alerts list", "Monitoring summary", "Sample incident banner"],
        "internal": "Monitoring rules are provisioned, provider collectors begin streaming alerts, and a sample incident is generated for practice.",
        "common_issues": [
            "No alerts appear after enabling monitoring.",
            "The sample incident did not generate.",
        ],
        "recovery_steps": [
            "Confirm a monitoring provider is connected, then re-run the monitoring step.",
            "Re-open onboarding and re-run the final step to generate the sample incident.",
        ],
    },
]

STAGE_DETAIL["incident-management"] = [
    {
        "navigation": ["Sidebar", "Operations", "Monitoring"],
        "route": "/monitoring",
        "expected_screen": ["Active alerts list", "Severity and service columns", "Unacknowledged counter"],
        "internal": "Provider collectors normalize and deduplicate incoming signals into a unified, attributed alert stream.",
        "common_issues": [
            "The alert has no service attribution.",
            "Duplicate-looking alerts from multiple providers.",
        ],
        "recovery_steps": [
            "Map the alert source to a service in Service Mapping.",
            "Group by service via search; correlation is finalized during investigation.",
        ],
    },
    {
        "navigation": ["Sidebar", "Operations", "Incidents"],
        "route": "/incidents",
        "expected_screen": ["Incident list", "New incident with severity and status", "Suspected provider"],
        "internal": "Escalation seeds a new incident with the alert context and triggers the default AI team to begin investigating.",
        "common_issues": [
            "No incident is created after escalation.",
            "The incident has no investigation yet.",
        ],
        "recovery_steps": [
            "Re-escalate from the alert in Monitoring.",
            "Confirm a default AI team exists; one is auto-provisioned during onboarding.",
        ],
    },
    {
        "navigation": ["Operations", "Incidents", "Incident", "Timeline"],
        "route": "/incidents/:id",
        "expected_screen": ["Chronological event list", "Provider badges", "Suspected trigger with confidence"],
        "internal": "The timeline engine merges alerts, metrics, and changes into one ordered narrative and flags the suspected trigger.",
        "common_issues": [
            "Deploys are missing from the timeline.",
            "The suspected trigger looks wrong.",
        ],
        "recovery_steps": [
            "Connect a source provider (GitHub/GitLab) so change events appear.",
            "Open Change Intelligence to compare candidate changes.",
        ],
    },
    {
        "navigation": ["Operations", "Incidents", "Incident", "Change Intelligence"],
        "route": "/incidents/:id",
        "expected_screen": ["Recent deploys and commits", "Authors and versions", "Correlation to the incident window"],
        "internal": "The change-correlation engine joins source-provider activity to the incident window to identify the suspected change.",
        "common_issues": [
            "No changes are correlated.",
            "Multiple changes look suspicious.",
        ],
        "recovery_steps": [
            "Connect and re-validate the source provider, then re-open the incident.",
            "Compare candidates by timestamp and proximity to onset.",
        ],
    },
    {
        "navigation": ["Operations", "Incidents", "Incident", "Recommendations"],
        "route": "/incidents/:id",
        "expected_screen": ["Ranked recommendations", "Confidence and risk badges", "Estimated recovery and rationale"],
        "internal": "The recommendation engine scores candidate actions against the inferred root cause and ranks them.",
        "common_issues": [
            "No recommendations appear.",
            "Confidence is low across all options.",
        ],
        "recovery_steps": [
            "Finish the timeline/RCA so the engine has a root cause to target.",
            "Connect more providers or verify the root cause before acting.",
        ],
    },
    {
        "navigation": ["Operations", "Incidents", "Incident", "Remediation Actions"],
        "route": "/incidents/:id",
        "expected_screen": ["Pending approvals", "Approved actions", "Execution results and bind status"],
        "internal": "The chosen recommendation becomes a remediation action that requires human approval before the executor runs it.",
        "common_issues": [
            "The action will not execute.",
            "Execution failed.",
        ],
        "recovery_steps": [
            "Approve the action first; confirm the bind/target is correct.",
            "Re-investigate, pick an updated recommendation, and retry.",
        ],
    },
    {
        "navigation": ["Sidebar", "Reports", "Postmortems"],
        "route": "/postmortems",
        "expected_screen": ["Generated postmortem", "Timeline, root cause, action items", "Export buttons"],
        "internal": "The postmortem generator synthesizes the investigation record into a blameless, exportable document.",
        "common_issues": [
            "Action items have no owner.",
            "The export does not download.",
        ],
        "recovery_steps": [
            "Assign an owner and due date to every action item.",
            "Re-try the export in PDF, HTML, or Markdown.",
        ],
    },
]

STAGE_DETAIL["safe-deployment"] = [
    {
        "navigation": ["Sidebar", "Deployments", "Deployment Risk"],
        "route": "/deployment-risk",
        "expected_screen": ["Deployment risk overview", "Risk level badges", "Recent changes at risk"],
        "internal": "The risk model surfaces the failure-risk profile for upcoming changes from historical change-failure patterns.",
        "common_issues": [
            "No changes appear in the risk view.",
            "Risk levels look uniformly low.",
        ],
        "recovery_steps": [
            "Connect a source provider so changes flow into the model.",
            "Record deployment outcomes so the model learns your environment.",
        ],
    },
    {
        "navigation": ["Sidebar", "Deployments", "Deployment Safety"],
        "route": "/deployment-safety",
        "expected_screen": ["Safety analyses list", "Safety score", "Safe / Caution / Block status"],
        "internal": "The safety engine weighs change size, history, current service health, and SLO burn into a single safety score.",
        "common_issues": [
            "Service health is unknown in the analysis.",
            "A Block status seems too strict.",
        ],
        "recovery_steps": [
            "Connect monitoring and SLOs so the engine can read live health.",
            "Mitigate the top risk factor and re-run the analysis.",
        ],
    },
    {
        "navigation": ["Sidebar", "Deployments", "Change Failure Prediction"],
        "route": "/change-failure",
        "expected_screen": ["Failure probability", "Risk level", "Contributing factors and blast radius"],
        "internal": "The change-history model produces a failure probability and decomposes it into capped, interpretable factors.",
        "common_issues": [
            "Probability seems implausibly low or high.",
            "Active incidents are inflating the risk.",
        ],
        "recovery_steps": [
            "Treat the percentage as a relative signal; split large changes to lower it.",
            "Resolve open incidents before deploying, then re-score.",
        ],
    },
    {
        "navigation": ["Deployments", "Deployment Safety", "Review"],
        "route": "/deployment-safety",
        "expected_screen": ["Combined risk and safety verdict", "Recommended guardrails", "Ship / gate / canary decision"],
        "internal": "The decision threshold combines the safety score and predicted failure risk into a clear go/hold recommendation.",
        "common_issues": [
            "Safety and failure signals disagree.",
            "Unsure which guardrail to apply.",
        ],
        "recovery_steps": [
            "Default to the more conservative signal; prefer a reversible rollout.",
            "Apply the recommended guardrail (canary, off-peak, feature flag) and proceed.",
        ],
    },
]

STAGE_DETAIL["executive-reporting"] = [
    {
        "navigation": ["Sidebar", "Reliability", "SLOs"],
        "route": "/slos",
        "expected_screen": ["SLO list", "Compliance and error budget", "Trend"],
        "internal": "The SLO evaluator reads metrics against each objective's target and window to compute compliance.",
        "common_issues": [
            "SLO compliance looks incomplete.",
            "A service has no objective.",
        ],
        "recovery_steps": [
            "Confirm services are mapped and SLOs were generated.",
            "Create an objective for the service from the SLOs page.",
        ],
    },
    {
        "navigation": ["Sidebar", "Infrastructure", "Capacity Planning"],
        "route": "/capacity",
        "expected_screen": ["Capacity forecasts", "Exhaustion dates", "Risk tiers"],
        "internal": "The forecaster fits trends to historical utilization and estimates exhaustion dates and risk tiers.",
        "common_issues": [
            "Forecasts lack enough history.",
            "An exhaustion date looks alarming.",
        ],
        "recovery_steps": [
            "Connect metrics and let data accumulate for better projections.",
            "Cross-check the saturation driver before scaling.",
        ],
    },
    {
        "navigation": ["Sidebar", "Infrastructure", "Cost Optimization"],
        "route": "/cost",
        "expected_screen": ["Savings opportunity total", "Top recommendations", "Estimated savings"],
        "internal": "The cost engine ingests billing and usage data, detects waste, and ranks recommendations by savings per effort.",
        "common_issues": [
            "Savings total looks stale.",
            "A recommendation lacks an owner.",
        ],
        "recovery_steps": [
            "Re-run the analysis so applied items drop out and totals update.",
            "Route findings to the owning service/team via attribution.",
        ],
    },
    {
        "navigation": ["Sidebar", "Executive Command Center"],
        "route": "/executive-command-center",
        "expected_screen": ["Executive widgets", "Reliability score", "Risk and savings summary"],
        "internal": "The reliability aggregator rolls SLOs, capacity, cost, and incidents into a single executive view.",
        "common_issues": [
            "A widget shows no data.",
            "Numbers differ from a module view.",
        ],
        "recovery_steps": [
            "Confirm the underlying module has data, then refresh the dashboard.",
            "Allow aggregation to reflect the latest module state.",
        ],
    },
    {
        "navigation": ["Sidebar", "Reports", "Executive Reports"],
        "route": "/reports",
        "expected_screen": ["Report preview", "Executive summary", "Export buttons"],
        "internal": "The report renderer formats the aggregated reliability story into a shareable, dependency-free export.",
        "common_issues": [
            "The export does not download.",
            "The report is missing a section.",
        ],
        "recovery_steps": [
            "Re-try the export in PDF, HTML, or Markdown.",
            "Ensure each source module has data before generating the report.",
        ],
    },
]

# === APPEND BELOW ===
