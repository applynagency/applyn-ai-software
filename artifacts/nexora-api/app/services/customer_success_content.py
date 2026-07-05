"""Sprint 56A — Customer Success Documentation Platform: content catalog.

Deterministic, in-memory, read-only customer-success content:

* MODULES          — maturity-complete guides for every customer-facing module
* JOURNEYS         — end-to-end customer journey guides
* PLAYBOOKS        — integration playbooks (AWS, Azure, K8s, GitHub, ...)
* SUCCESS_CENTER   — beginner-friendly "first X" guides

Every module guide contains the full documentation-maturity section set:
overview, navigation, prerequisites, step-by-step (>=5), results interpretation,
real-world example, troubleshooting, best practices, and FAQ (>=5).

No DB models, no migrations, no binary images — screenshots are tracked as
metadata placeholders only. Strictly additive.
"""

from __future__ import annotations

from typing import Any

# Screenshot categories (Sprint 56A deliverable 2).
SCREENSHOT_CATEGORIES = [
    "onboarding",
    "monitoring",
    "incident",
    "deployment",
    "reporting",
    "admin",
    "integrations",
]


# --------------------------------------------------------------------------- #
# Small builders to keep authored content specific but DRY.                    #
# --------------------------------------------------------------------------- #
def _step(action: str, expected: str) -> dict[str, str]:
    return {"action": action, "expected": expected}


def _faq(question: str, answer: str) -> dict[str, str]:
    return {"question": question, "answer": answer}


def _tip(problem: str, cause: str, resolution: str) -> dict[str, str]:
    return {"problem": problem, "cause": cause, "resolution": resolution}


def _term(term: str, meaning: str) -> dict[str, str]:
    return {"term": term, "meaning": meaning}


def _module(
    *,
    key: str,
    name: str,
    category: str,
    route: str,
    nav_path: list[str],
    overview: dict[str, str],
    prerequisites: list[str],
    steps: list[dict[str, str]],
    interpretation: list[dict[str, str]],
    example: dict[str, str],
    troubleshooting: list[dict[str, str]],
    best_practices: list[str],
    faq: list[dict[str, str]],
    reading_time_minutes: int,
    difficulty: str,
    role: str,
    business_value: str,
    expected_outcomes: list[str],
    related: list[str],
) -> dict[str, Any]:
    """Assemble a maturity-complete module guide and attach screenshot placeholders."""
    enriched_steps: list[dict[str, str]] = []
    for i, s in enumerate(steps, start=1):
        enriched_steps.append(
            {
                "order": i,
                "action": s["action"],
                "expected": s["expected"],
                "screenshot": f"{key}-step-{i}.png",
            }
        )
    screenshots = [
        {"name": f"{key}-overview.png", "caption": f"{name} overview", "category": category},
        *[
            {"name": st["screenshot"], "caption": f"{name} — step {st['order']}", "category": category}
            for st in enriched_steps
        ],
        {"name": f"{key}-results.png", "caption": f"{name} results interpretation", "category": category},
    ]
    return {
        "key": key,
        "name": name,
        "category": category,
        "route": route,
        "navigation": {"path": nav_path, "route": route},
        "overview": overview,
        "prerequisites": prerequisites,
        "steps": enriched_steps,
        "interpretation": interpretation,
        "example": example,
        "troubleshooting": troubleshooting,
        "best_practices": best_practices,
        "faq": faq,
        "screenshots": screenshots,
        "metadata": {
            "reading_time_minutes": reading_time_minutes,
            "difficulty": difficulty,
            "role": role,
            "business_value": business_value,
            "expected_outcomes": expected_outcomes,
            "related": related,
        },
    }


# --------------------------------------------------------------------------- #
# MODULES — every customer-facing module.                                      #
# --------------------------------------------------------------------------- #
MODULES: list[dict[str, Any]] = [
    _module(
        key="onboarding",
        name="Infrastructure Onboarding",
        category="onboarding",
        route="/onboarding",
        nav_path=["Sidebar", "Get started", "Onboarding"],
        overview={
            "what": "A guided wizard that connects your providers, discovers your infrastructure, maps services and dependencies, and turns on SLOs and monitoring.",
            "why": "It replaces weeks of manual setup with a ~15 minute self-service flow so you reach first value fast.",
            "business_value": "Time-to-value under 15 minutes with zero manual identifiers and no hidden prerequisites.",
            "who": "New customers, platform admins, and SREs standing up a new organization.",
            "when": "Immediately after signup, or whenever you add a new environment or organization.",
        },
        prerequisites=[
            "A Nexora account and a newly created organization (the wizard can create one for you).",
            "Read-only access to at least one provider (AWS, Kubernetes, GitHub, etc.) — credentials are validated, never stored.",
        ],
        steps=[
            _step("Open Get started → Onboarding and name your organization.", "The organization is created and your session auto-switches into it."),
            _step("Select your providers (AWS, Azure, GCP, Kubernetes, GitHub, Datadog, Prometheus, Grafana).", "Selected providers are highlighted and saved to the wizard."),
            _step("Run credential validation.", "Each provider shows a connectivity status; secrets are validated read-only and discarded."),
            _step("Run discovery, then map services and dependencies.", "Discovered assets, services, and dependency edges are summarized with counts."),
            _step("Generate SLOs and enable monitoring, then generate a sample incident.", "Default SLOs and monitoring rules are created and a realistic incident is produced for you to investigate."),
        ],
        interpretation=[
            _term("Assets discovered", "Count of raw infrastructure resources found across connected providers."),
            _term("Services mapped", "Logical services grouped from discovered assets."),
            _term("SLO coverage %", "Share of services that now have at least one objective."),
            _term("Monitoring coverage %", "Share of services covered by at least one monitoring rule."),
        ],
        example={
            "scenario": "A fintech team connects AWS + Kubernetes + GitHub on day one.",
            "walkthrough": "They name the org 'Acme', select three providers, validate, discover 142 assets, map 18 services, find 31 dependencies, generate 36 SLOs at 92% coverage, enable monitoring at 88%, and produce a Checkout Outage sample incident.",
            "outcome": "Within 12 minutes the team investigates the sample incident and views their first executive dashboard.",
        },
        troubleshooting=[
            _tip("Credential validation shows 'missing fields'.", "Required provider fields were left blank.", "Provide the listed fields, or continue — validation is informational and never blocks the guided setup."),
            _tip("Discovery returns 0 assets.", "The provider scope had no read permission or no resources.", "Re-run with a read-only role attached to at least one account/cluster."),
            _tip("Wizard lost its place after a refresh.", "Browser storage was cleared.", "Re-open Onboarding — progress resumes from the persisted wizard id and step."),
        ],
        best_practices=[
            "Start with read-only credentials; you can deepen access later.",
            "Connect at least one source provider (GitHub/GitLab) so change intelligence works on incidents.",
            "Accept the generated SLOs first, then tune targets once you have a baseline.",
            "Use the sample incident to train new on-call engineers before real traffic.",
        ],
        faq=[
            _faq("Does onboarding store my cloud credentials?", "No. Credentials are validated read-only during the wizard and are never persisted."),
            _faq("How long does onboarding take?", "Most teams complete it in under 15 minutes."),
            _faq("Can I resume if I get interrupted?", "Yes. Progress is saved; re-open Onboarding to continue where you left off."),
            _faq("Do I need to set up an AI team first?", "No. A default SRE team with investigator and RCA agents is provisioned automatically on completion."),
            _faq("Can I onboard multiple environments?", "Yes. Run the wizard again per organization or environment."),
        ],
        reading_time_minutes=6,
        difficulty="Beginner",
        role="Platform Admin / SRE",
        business_value="Fast time-to-value",
        expected_outcomes=["Connected providers", "Discovered and mapped services", "Live SLOs and monitoring", "A sample incident to investigate"],
        related=["monitoring", "slos", "incidents"],
    ),
    _module(
        key="monitoring",
        name="Monitoring",
        category="monitoring",
        route="/monitoring",
        nav_path=["Sidebar", "Operations", "Monitoring"],
        overview={
            "what": "A live view of alerts streaming from your connected observability and cloud providers.",
            "why": "It centralizes signal from every provider so on-call sees one prioritized stream instead of many consoles.",
            "business_value": "Faster detection and fewer missed alerts through unified, deduplicated signal.",
            "who": "On-call engineers and SREs.",
            "when": "Continuously during on-call shifts and triage.",
        },
        prerequisites=[
            "At least one monitoring provider connected during onboarding.",
            "Services mapped so alerts can be attributed to an owner.",
        ],
        steps=[
            _step("Open Operations → Monitoring.", "The alert list loads with severity, service, and status."),
            _step("Use the search box to filter by service or severity.", "The table narrows to matching alerts in real time."),
            _step("Click the bell (Notifications) in the top bar for the latest six alerts.", "A popover shows the most recent alerts with service and status."),
            _step("Select an alert to read its details.", "Alert metadata, affected service, and timestamps are shown."),
            _step("Escalate a recurring alert into an incident investigation.", "An incident is opened and appears under Operations → Incidents."),
        ],
        interpretation=[
            _term("Severity", "Critical/High/Medium/Low — drives ordering and on-call routing."),
            _term("Status", "open, acknowledged, or resolved."),
            _term("Active alerts", "Count of currently firing alerts across providers."),
            _term("Unacknowledged", "Alerts no responder has claimed yet — watch this number during a shift."),
        ],
        example={
            "scenario": "Latency spikes on the checkout service.",
            "walkthrough": "An on-call engineer filters Monitoring by 'checkout', sees three High alerts clustered in five minutes, and escalates to an incident.",
            "outcome": "The incident carries the alert context into investigation, saving manual copy-paste.",
        },
        troubleshooting=[
            _tip("No alerts appear.", "No monitoring provider is connected or no rules exist.", "Re-run onboarding's monitoring step or connect a provider under Integrations."),
            _tip("Alerts lack a service.", "The alert source isn't mapped to a service.", "Map the source in Service Mapping so attribution works."),
            _tip("Duplicate-looking alerts.", "Multiple providers report the same condition.", "Use search to group by service; correlation happens during incident investigation."),
        ],
        best_practices=[
            "Keep the Unacknowledged count near zero during a shift.",
            "Attribute every alert source to a service for clean ownership.",
            "Escalate noisy repeat alerts into incidents to capture root cause.",
            "Review recent alerts at shift handoff.",
        ],
        faq=[
            _faq("Where do alerts come from?", "From the observability and cloud providers you connected (Datadog, Prometheus, Grafana, cloud, etc.)."),
            _faq("Can I see alerts from the top bar?", "Yes — the notifications bell shows the latest six alerts on any page."),
            _faq("How do alerts become incidents?", "Escalate an alert to open an AI-assisted incident investigation."),
            _faq("Why is an alert missing a service?", "Its source isn't mapped yet; add it in Service Mapping."),
            _faq("Is the list real-time?", "It reflects the latest polled state and refreshes on load."),
        ],
        reading_time_minutes=4,
        difficulty="Beginner",
        role="On-call Engineer / SRE",
        business_value="Faster detection",
        expected_outcomes=["Unified alert stream", "Attributed alerts", "One-click escalation to incidents"],
        related=["incidents", "service-health"],
    ),
    _module(
        key="incidents",
        name="Incident Intelligence",
        category="incident",
        route="/incidents",
        nav_path=["Sidebar", "Operations", "Incidents"],
        overview={
            "what": "AI-investigated incidents with timeline, change intelligence, recommendations, remediation actions, and postmortems.",
            "why": "It compresses root-cause analysis from hours of manual correlation to minutes.",
            "business_value": "Lower MTTR and consistent, blameless postmortems.",
            "who": "On-call engineers, incident commanders, and SREs.",
            "when": "Whenever an incident is declared or escalated from an alert.",
        },
        prerequisites=[
            "A default AI team (auto-provisioned during onboarding).",
            "Source provider connected for change intelligence (GitHub/GitLab).",
        ],
        steps=[
            _step("Open Operations → Incidents and click a row.", "You land on the Incident Detail page with a summary header."),
            _step("Open the Timeline tab.", "Chronological events show with provider and severity badges and a confidence score."),
            _step("Open the Change Intelligence tab.", "Recent deployments, commits, releases, and the suspected change are listed."),
            _step("Open the Recommendations tab.", "Ranked recommendations show confidence, risk, estimated recovery, and rationale."),
            _step("Open Remediation Actions, then Postmortem.", "Pending/approved actions and the generated postmortem (with export) are available."),
        ],
        interpretation=[
            _term("Confidence score", "0–100 likelihood the identified root cause is correct; higher means more corroborating signal."),
            _term("Risk", "Estimated blast radius / impact of applying a recommendation."),
            _term("Status", "open, investigating, mitigated, or resolved."),
            _term("Suspected trigger", "The change or event most correlated with the incident onset."),
            _term("Recommendation rationale", "Why the action is suggested, with the evidence used."),
        ],
        example={
            "scenario": "Checkout error rate jumps after a release.",
            "walkthrough": "The timeline pins the spike to 14:02; change intelligence flags release v1.42; the top recommendation (confidence 86) is 'roll back v1.42' with ~6 min estimated recovery.",
            "outcome": "On-call approves the remediation, recovers in minutes, and exports the postmortem.",
        },
        troubleshooting=[
            _tip("Change Intelligence is empty.", "No source provider is connected.", "Connect GitHub/GitLab so deployments and commits correlate."),
            _tip("Low confidence score.", "Sparse signal or no recent changes.", "Add more providers; confidence rises with corroborating evidence."),
            _tip("No postmortem yet.", "It hasn't been generated.", "Generate the postmortem from the incident; then export to PDF/HTML/Markdown."),
        ],
        best_practices=[
            "Always review Change Intelligence before applying a fix.",
            "Prefer high-confidence, low-risk recommendations first.",
            "Capture a postmortem for every Sev1/Sev2.",
            "Use remediation approvals to keep an auditable trail.",
        ],
        faq=[
            _faq("Do I need to pick a team to investigate?", "No. If you omit a team, your organization's default team is used."),
            _faq("How is the confidence score computed?", "From the strength and agreement of correlated signals across providers and changes."),
            _faq("Can I export the postmortem?", "Yes — PDF, HTML, and Markdown."),
            _faq("Where do recommendations come from?", "AI analysis of the timeline, changes, and historical patterns."),
            _faq("Can I drill from an alert to an incident?", "Yes — escalate from Monitoring to open an investigation."),
        ],
        reading_time_minutes=7,
        difficulty="Intermediate",
        role="Incident Commander / SRE",
        business_value="Lower MTTR",
        expected_outcomes=["Root cause identified", "Safe remediation applied", "Exportable postmortem"],
        related=["monitoring", "postmortems", "change-failure"],
    ),
    _module(
        key="postmortems",
        name="Postmortems",
        category="incident",
        route="/postmortems",
        nav_path=["Sidebar", "Operations", "Postmortems"],
        overview={
            "what": "Blameless retrospectives generated from incident investigations.",
            "why": "It standardizes learning so the same failure doesn't recur.",
            "business_value": "Institutional memory and measurable reliability improvement.",
            "who": "Incident commanders, SREs, and engineering leadership.",
            "when": "After every significant incident.",
        },
        prerequisites=[
            "A resolved or investigated incident.",
            "Permission to read incident data in the organization.",
        ],
        steps=[
            _step("Open Operations → Postmortems.", "The list of generated postmortems loads."),
            _step("Open an incident and switch to its Postmortem tab.", "The postmortem for that incident is shown with version and status."),
            _step("Generate a postmortem if none exists.", "A structured document (summary, timeline, root cause, actions) is created."),
            _step("Review the contributing factors and action items.", "Each action item has an owner-ready description."),
            _step("Export to PDF, HTML, or Markdown.", "A file downloads for sharing or archival."),
        ],
        interpretation=[
            _term("Version", "Increments when the postmortem is regenerated or edited."),
            _term("Status", "draft or published."),
            _term("Action items", "Follow-ups intended to prevent recurrence."),
            _term("Contributing factors", "Conditions that allowed the incident to occur or persist."),
        ],
        example={
            "scenario": "Recurring memory leak.",
            "walkthrough": "The postmortem links three incidents to the same service and proposes a memory limit plus an alert threshold change.",
            "outcome": "The action items are tracked and the pattern stops recurring.",
        },
        troubleshooting=[
            _tip("Postmortem tab is empty.", "None generated for the incident.", "Click generate on the incident; it appears in the list and tab."),
            _tip("Export downloads an empty file.", "The incident had little captured data.", "Ensure timeline and changes loaded before generating."),
            _tip("Cannot find a postmortem.", "Filtered out by status.", "Clear filters or open the incident's Postmortem tab directly."),
        ],
        best_practices=[
            "Keep postmortems blameless — focus on systems, not people.",
            "Assign every action item an owner and due date.",
            "Link related incidents to reveal patterns.",
            "Publish and circulate within 48 hours.",
        ],
        faq=[
            _faq("Are postmortems generated automatically?", "They're generated on demand from an incident and can be regenerated."),
            _faq("What formats can I export?", "PDF, HTML, and Markdown."),
            _faq("Can I edit a postmortem?", "Yes; edits create a new version."),
            _faq("Who can see postmortems?", "Members of the organization with read access."),
            _faq("How do I find a specific one?", "Use the Postmortems list search or open the incident's Postmortem tab."),
        ],
        reading_time_minutes=4,
        difficulty="Beginner",
        role="Incident Commander",
        business_value="Prevent recurrence",
        expected_outcomes=["Standardized retrospective", "Tracked action items", "Shareable export"],
        related=["incidents"],
    ),
    _module(
        key="service-health",
        name="Service Health",
        category="monitoring",
        route="/service-health",
        nav_path=["Sidebar", "Reliability", "Service Health"],
        overview={
            "what": "A real-time health rollup per service: score, availability, error budget, and predictions.",
            "why": "It tells you which services are healthy and which are trending toward trouble.",
            "business_value": "Proactive reliability management before customers feel pain.",
            "who": "Service owners and SREs.",
            "when": "During reviews, on-call, and capacity planning.",
        },
        prerequisites=[
            "Services mapped during onboarding.",
            "SLOs defined so compliance can be computed.",
        ],
        steps=[
            _step("Open Reliability → Service Health.", "A health rollup across all services loads."),
            _step("Click a service to open Service Detail.", "The Health Overview tab shows score, availability, burn rate, and budget remaining."),
            _step("Open the SLOs tab.", "Target, current, compliance, and trend per objective are shown."),
            _step("Open the Dependencies tab.", "Upstream/downstream dependencies and blast radius are listed."),
            _step("Open the Incidents tab.", "Incidents affecting this service are correlated for context."),
        ],
        interpretation=[
            _term("Health score", "0–100 composite of availability, error budget, and incident load."),
            _term("Burn rate", "How fast the error budget is being consumed; >1 means faster than sustainable."),
            _term("Budget remaining", "Share of the error budget left in the current window."),
            _term("Prediction", "Projected trajectory of the service's reliability."),
        ],
        example={
            "scenario": "A service shows a falling health score.",
            "walkthrough": "The owner sees burn rate 2.3 and 18% budget left, checks dependencies, and finds an upstream cache degrading.",
            "outcome": "They act before the budget is exhausted, avoiding an SLA breach.",
        },
        troubleshooting=[
            _tip("Health score is blank.", "No SLOs or metrics for the service.", "Define SLOs and ensure monitoring covers the service."),
            _tip("Compliance looks wrong.", "Window or target misconfigured.", "Review the SLO target and window on the SLOs tab."),
            _tip("No dependencies shown.", "Dependency mapping hasn't run.", "Run dependency mapping in onboarding or Discovery."),
        ],
        best_practices=[
            "Review burn rate weekly for tier-1 services.",
            "Investigate any service under 70 health.",
            "Use dependencies to find hidden upstream risk.",
            "Pair health review with capacity forecasts.",
        ],
        faq=[
            _faq("What is a good health score?", "85+ is healthy; under 70 warrants investigation."),
            _faq("How is burn rate useful?", "It warns when you'll exhaust the error budget before the window ends."),
            _faq("Can I see incidents per service?", "Yes — the Incidents tab on Service Detail."),
            _faq("Where do SLO numbers come from?", "From the objectives you defined and live metrics."),
            _faq("Does this cover dependencies?", "Yes — the Dependencies tab shows blast radius."),
        ],
        reading_time_minutes=5,
        difficulty="Intermediate",
        role="Service Owner / SRE",
        business_value="Proactive reliability",
        expected_outcomes=["Per-service health visibility", "Early budget-burn warnings", "Dependency-aware risk"],
        related=["slos", "dependencies", "capacity"],
    ),
    _module(
        key="slos",
        name="SLOs & Error Budgets",
        category="reporting",
        route="/slos",
        nav_path=["Sidebar", "Reliability", "SLOs"],
        overview={
            "what": "Service level objectives and the error budgets derived from them.",
            "why": "SLOs turn 'is it reliable?' into a measurable, agreed target.",
            "business_value": "Objective reliability targets that align engineering and the business.",
            "who": "Service owners, SREs, and engineering leadership.",
            "when": "At service launch and during quarterly reliability reviews.",
        },
        prerequisites=[
            "Services mapped.",
            "Monitoring enabled so current performance can be measured.",
        ],
        steps=[
            _step("Open Reliability → SLOs.", "Objectives load with target, current, and status."),
            _step("Open a service's SLOs tab to see per-objective detail.", "Target, current, compliance, and trend are shown."),
            _step("Compare current vs target.", "You can see whether the objective is met and the margin."),
            _step("Check error budget remaining.", "The remaining budget for the window is displayed."),
            _step("Adjust a target after establishing a baseline.", "The compliance recomputes against the new target."),
        ],
        interpretation=[
            _term("Target", "The objective, e.g. 99.9% availability over 30 days."),
            _term("Current", "Measured performance in the active window."),
            _term("Compliance", "Whether current meets target, with margin."),
            _term("Error budget", "Allowed failure (100% − target); when exhausted, slow down risky changes."),
        ],
        example={
            "scenario": "A new API service.",
            "walkthrough": "The team accepts a generated 99.9% target, watches a week, sees 99.95% current with 60% budget left, and keeps the target.",
            "outcome": "A defensible reliability target with room for safe iteration.",
        },
        troubleshooting=[
            _tip("Current shows no data.", "Monitoring doesn't cover the service.", "Enable monitoring so metrics flow."),
            _tip("Compliance always failing.", "Target set unrealistically high.", "Baseline first, then set an achievable target."),
            _tip("No SLOs listed.", "None generated or created.", "Run the onboarding SLO step or add objectives per service."),
        ],
        best_practices=[
            "Start from generated defaults, then tune to reality.",
            "Tie deploy freezes to error-budget exhaustion.",
            "Review SLOs quarterly with stakeholders.",
            "Keep targets meaningful — not 100%.",
        ],
        faq=[
            _faq("What's a sensible starting target?", "99.9% availability is a common baseline for tier-1 services."),
            _faq("What is an error budget?", "The allowed amount of failure; it's 100% minus your target."),
            _faq("What happens when the budget is exhausted?", "Slow down risky changes and prioritize reliability work."),
            _faq("Where are SLOs created?", "Generated during onboarding and viewable per service."),
            _faq("Can I change a target?", "Yes; compliance recomputes immediately."),
        ],
        reading_time_minutes=5,
        difficulty="Intermediate",
        role="Service Owner / Eng Leadership",
        business_value="Aligned reliability targets",
        expected_outcomes=["Defined objectives", "Visible error budgets", "Data-driven deploy decisions"],
        related=["service-health", "executive-reports"],
    ),
    _module(
        key="dependencies",
        name="Dependency Graph",
        category="monitoring",
        route="/dependencies",
        nav_path=["Sidebar", "Reliability", "Dependency Graph"],
        overview={
            "what": "Service-to-service dependency edges and blast-radius analysis.",
            "why": "It shows how failure propagates so you can prioritize the right fixes.",
            "business_value": "Smarter prioritization and fewer surprise cascading failures.",
            "who": "SREs and architects.",
            "when": "During design reviews, incident triage, and capacity planning.",
        },
        prerequisites=[
            "Dependency mapping completed during onboarding.",
            "Services mapped with names.",
        ],
        steps=[
            _step("Open Reliability → Dependency Graph.", "Dependency edges load with source, target, and type."),
            _step("Open a Service Detail → Dependencies tab.", "Upstream and downstream dependencies are listed."),
            _step("Read the blast radius for the service.", "The set of services impacted by its failure is shown."),
            _step("Click a dependency to drill into that service.", "You navigate to the dependent service's detail page."),
            _step("Use the graph during an incident to scope impact.", "You identify which downstreams are at risk."),
        ],
        interpretation=[
            _term("Upstream", "Services this service depends on."),
            _term("Downstream", "Services that depend on this service."),
            _term("Blast radius", "Everything affected if this service fails."),
            _term("Dependency type", "The nature of the edge (sync call, async, data, etc.)."),
        ],
        example={
            "scenario": "Planning a risky migration.",
            "walkthrough": "The team checks the payments service blast radius and sees seven downstreams, so they schedule a maintenance window.",
            "outcome": "The migration proceeds with stakeholders pre-notified.",
        },
        troubleshooting=[
            _tip("Graph is empty.", "Dependency mapping didn't run.", "Run dependency mapping in onboarding/Discovery."),
            _tip("Missing edges.", "Low-traffic paths weren't observed.", "Allow more observation time or add edges via mapping."),
            _tip("Edge points the wrong way.", "Direction inferred incorrectly.", "Verify with service owners and correct the mapping."),
        ],
        best_practices=[
            "Review blast radius before risky changes.",
            "Keep critical paths documented and minimal.",
            "Use the graph during incidents to scope impact fast.",
            "Re-map after major architecture changes.",
        ],
        faq=[
            _faq("How are dependencies discovered?", "Inferred during onboarding's dependency mapping step."),
            _faq("What is blast radius?", "The set of services impacted if a given service fails."),
            _faq("Can I drill across services?", "Yes — click a dependency to open that service's detail."),
            _faq("Why is an edge missing?", "Low-traffic paths may not be observed; re-map to refresh."),
            _faq("Does this help during incidents?", "Yes — it scopes downstream impact quickly."),
        ],
        reading_time_minutes=4,
        difficulty="Intermediate",
        role="SRE / Architect",
        business_value="Prevent cascading failures",
        expected_outcomes=["Visible dependencies", "Blast-radius awareness", "Cross-service drill-down"],
        related=["service-health", "incidents"],
    ),
    _module(
        key="capacity",
        name="Capacity Planning",
        category="monitoring",
        route="/capacity",
        nav_path=["Sidebar", "Infrastructure", "Capacity Planning"],
        overview={
            "what": "Forecasts of resource utilization and exhaustion risk.",
            "why": "It warns you before you run out of capacity.",
            "business_value": "Avoided outages and right-sized spend.",
            "who": "SREs and infrastructure owners.",
            "when": "During planning cycles and ahead of demand events.",
        },
        prerequisites=[
            "Discovery completed so resources are known.",
            "Metrics flowing for utilization.",
        ],
        steps=[
            _step("Open Infrastructure → Capacity Planning.", "Forecasts load with resource, status, and projection."),
            _step("Open a service's Capacity tab.", "Per-service forecasts are filtered for context."),
            _step("Review the soonest exhaustion date.", "The earliest at-risk resource is highlighted."),
            _step("Read critical vs warning counts.", "You see how many resources are at each risk tier."),
            _step("Plan a scale-up or optimization from the findings.", "You have the data to justify the change."),
        ],
        interpretation=[
            _term("Critical", "Resource will be exhausted soon — act now."),
            _term("Warning", "Trending toward exhaustion — plan ahead."),
            _term("Healthy", "Comfortable headroom."),
            _term("Exhaustion date", "Projected date a resource hits its limit."),
        ],
        example={
            "scenario": "A database nearing storage limits.",
            "walkthrough": "Capacity flags it Critical with a 9-day exhaustion date; the team provisions storage in advance.",
            "outcome": "No outage, no fire drill.",
        },
        troubleshooting=[
            _tip("No forecasts.", "Insufficient metric history.", "Allow more data to accumulate, then revisit."),
            _tip("Forecast looks off.", "A demand spike skewed the trend.", "Cross-check with recent events; forecasts adapt over time."),
            _tip("Resource missing.", "Not discovered.", "Re-run Discovery to include it."),
        ],
        best_practices=[
            "Act on Critical immediately; schedule Warning.",
            "Pair capacity with cost to right-size, not just scale up.",
            "Re-forecast before known demand events.",
            "Track exhaustion dates for tier-1 resources.",
        ],
        faq=[
            _faq("How far ahead do forecasts look?", "They project utilization toward the exhaustion date based on trend."),
            _faq("What does Critical mean?", "The resource is close to exhaustion and needs action now."),
            _faq("Can I see capacity per service?", "Yes — the Capacity tab on Service Detail."),
            _faq("Why is a resource missing?", "It wasn't discovered; re-run Discovery."),
            _faq("How accurate are forecasts?", "They improve as more metric history accumulates."),
        ],
        reading_time_minutes=4,
        difficulty="Intermediate",
        role="SRE / Infra Owner",
        business_value="Avoid capacity outages",
        expected_outcomes=["Exhaustion warnings", "Right-sized capacity", "Planned scale-ups"],
        related=["cost", "service-health"],
    ),
    _module(
        key="cost",
        name="Cost Optimization",
        category="reporting",
        route="/cost",
        nav_path=["Sidebar", "Infrastructure", "Cost Optimization"],
        overview={
            "what": "Cost analyses that surface waste and savings opportunities.",
            "why": "It turns cloud spend into prioritized, actionable savings.",
            "business_value": "Lower cloud bills without sacrificing reliability.",
            "who": "FinOps, SREs, and engineering leadership.",
            "when": "Monthly cost reviews and before budget planning.",
        },
        prerequisites=[
            "Discovery completed so resources and cost can be attributed.",
            "Cost data available from the connected provider.",
        ],
        steps=[
            _step("Open Infrastructure → Cost Optimization.", "Analyses load with current cost and savings."),
            _step("Review estimated waste and idle resources.", "Idle and overprovisioned counts are shown."),
            _step("Read the top recommendations.", "Each recommendation shows monthly savings and an action."),
            _step("Check potential and annualized savings.", "The financial upside is quantified."),
            _step("Assign owners to act on the top recommendations.", "Savings move from potential to realized."),
        ],
        interpretation=[
            _term("Estimated waste", "Spend attributable to idle/overprovisioned resources."),
            _term("Potential savings", "Monthly savings if recommendations are applied."),
            _term("Annual savings", "Potential savings annualized."),
            _term("Optimization score", "0–100 how optimized your spend is."),
        ],
        example={
            "scenario": "A monthly FinOps review.",
            "walkthrough": "The report shows $4,200/mo waste, 11 idle resources, and a top action to downsize three instances saving $1,800/mo.",
            "outcome": "The team applies the top three and realizes most of the savings.",
        },
        troubleshooting=[
            _tip("No cost data.", "Provider cost access isn't connected.", "Connect billing/cost access for the provider."),
            _tip("Savings look low.", "Already well-optimized, or limited scope.", "Expand provider scope to analyze more resources."),
            _tip("Recommendation seems risky.", "Resource is bursty, not idle.", "Validate utilization patterns before downsizing."),
        ],
        best_practices=[
            "Tackle idle resources first — lowest risk, quick wins.",
            "Validate utilization before downsizing bursty workloads.",
            "Pair cost with capacity to right-size safely.",
            "Review monthly and track realized savings.",
        ],
        faq=[
            _faq("Where does cost data come from?", "From the cost/billing access of your connected providers."),
            _faq("Is it safe to apply recommendations?", "Idle cleanups are low risk; validate bursty workloads first."),
            _faq("Can I see savings annually?", "Yes — both monthly and annualized figures are shown."),
            _faq("Does the Command Center surface savings?", "Yes — the Savings Opportunity widget."),
            _faq("How often should I review?", "Monthly, aligned with budget cycles."),
        ],
        reading_time_minutes=5,
        difficulty="Intermediate",
        role="FinOps / Eng Leadership",
        business_value="Reduce cloud spend",
        expected_outcomes=["Identified waste", "Prioritized savings", "Realized cost reduction"],
        related=["capacity", "executive-reports"],
    ),
    _module(
        key="deployment-safety",
        name="Deployment Safety",
        category="deployment",
        route="/deployment-safety",
        nav_path=["Sidebar", "Deployments", "Deployment Safety"],
        overview={
            "what": "Pre-deployment safety analyses that score a release before it ships.",
            "why": "It catches risky deploys before they cause incidents.",
            "business_value": "Fewer change-induced outages and safer release velocity.",
            "who": "Release engineers, SREs, and developers.",
            "when": "Before promoting a release to a sensitive environment.",
        },
        prerequisites=[
            "Source provider connected (GitHub/GitLab).",
            "Services mapped so analyses attribute to the right owner.",
        ],
        steps=[
            _step("Open Deployments → Deployment Safety.", "Analyses load with application, environment, and status."),
            _step("Open a service's Deployments tab.", "Safety analyses filtered to that service are shown."),
            _step("Read the safety score and status.", "Ready / At risk / Not ready is shown per analysis."),
            _step("Review the contributing risk factors.", "Factors lowering the score are listed."),
            _step("Decide to ship, gate, or roll back based on the score.", "You make an evidence-based release decision."),
        ],
        interpretation=[
            _term("Safety score", "0–100 confidence the deploy is safe; higher is safer."),
            _term("Ready", "Safe to proceed."),
            _term("At risk", "Proceed with caution and mitigations."),
            _term("Not ready", "Hold — address the flagged factors first."),
        ],
        example={
            "scenario": "Friday afternoon release.",
            "walkthrough": "The analysis returns 'At risk' (score 64) citing a recent rollback and high change size; the team splits the change and re-checks.",
            "outcome": "The smaller change scores 'Ready' and ships safely.",
        },
        troubleshooting=[
            _tip("No analyses.", "No deployments analyzed yet.", "Trigger an analysis or connect your CI/source provider."),
            _tip("Score unexpectedly low.", "Large change size or recent failures.", "Reduce change size and address recent rollbacks."),
            _tip("Wrong service attributed.", "Mapping mismatch.", "Correct service mapping for the application."),
        ],
        best_practices=[
            "Gate sensitive environments on a minimum safety score.",
            "Keep change sizes small to raise scores.",
            "Avoid deploys during error-budget exhaustion.",
            "Pair safety with change-failure prediction.",
        ],
        faq=[
            _faq("What is a safe score?", "Treat 80+ as Ready; define your own gate threshold."),
            _faq("Where does the score come from?", "Change size, recent history, and service health signals."),
            _faq("Can I see it per service?", "Yes — the Deployments tab on Service Detail."),
            _faq("Does it integrate with CI?", "It analyzes deployments from connected source/CI providers."),
            _faq("Should I block deploys automatically?", "You can gate on the score in your release process."),
        ],
        reading_time_minutes=5,
        difficulty="Intermediate",
        role="Release Engineer / SRE",
        business_value="Safer releases",
        expected_outcomes=["Pre-deploy risk scoring", "Evidence-based gates", "Fewer change-induced incidents"],
        related=["change-failure", "incidents"],
    ),
    _module(
        key="change-failure",
        name="Change Failure Prediction",
        category="deployment",
        route="/change-failure",
        nav_path=["Sidebar", "Deployments", "Change Failure Prediction"],
        overview={
            "what": "Predicted failure probability and risk level for upcoming changes.",
            "why": "It flags the riskiest changes so you can add review or mitigation.",
            "business_value": "Lower change failure rate — a core DORA metric.",
            "who": "Developers, release engineers, and SREs.",
            "when": "Before and during the review of a change.",
        },
        prerequisites=[
            "Source provider connected for change history.",
            "Services mapped.",
        ],
        steps=[
            _step("Open Deployments → Change Failure Prediction.", "Predictions load with application and risk level."),
            _step("Sort or filter by risk level.", "The highest-risk changes surface first."),
            _step("Open a prediction to read its probability.", "Failure probability and expected blast radius are shown."),
            _step("Add review or mitigation for high-risk changes.", "Risky changes get extra scrutiny."),
            _step("Track the change-failure trend over time.", "You can see whether risk is improving."),
        ],
        interpretation=[
            _term("Failure probability", "Estimated chance the change causes a failure (0–100%)."),
            _term("Risk level", "Low / Medium / High / Critical bucketing of probability."),
            _term("Expected blast radius", "Services likely affected if the change fails."),
            _term("Confidence", "How much signal supports the prediction."),
        ],
        example={
            "scenario": "A large refactor PR.",
            "walkthrough": "Prediction flags it High (38% failure) with a 4-service blast radius; the team adds an extra reviewer and a canary.",
            "outcome": "The change ships behind a canary and is caught early when metrics dip.",
        },
        troubleshooting=[
            _tip("No predictions.", "No change history connected.", "Connect GitHub/GitLab to feed change data."),
            _tip("Probability seems high for a small change.", "History shows prior failures in that area.", "Add a canary; the model reflects past risk."),
            _tip("Missing blast radius.", "Dependencies not mapped.", "Run dependency mapping."),
        ],
        best_practices=[
            "Require review for High/Critical changes.",
            "Canary high-risk changes.",
            "Keep changes small and frequent.",
            "Watch the trend, not just single predictions.",
        ],
        faq=[
            _faq("How is probability computed?", "From historical change outcomes, size, and service signals."),
            _faq("What should I do with a High risk?", "Add review, reduce scope, or canary the change."),
            _faq("Does it predict blast radius?", "Yes — using the dependency graph."),
            _faq("Where do I see overall risk?", "The Executive Command Center's Change Failure Risks widget."),
            _faq("Why no predictions?", "Connect a source provider so change history is available."),
        ],
        reading_time_minutes=4,
        difficulty="Advanced",
        role="Developer / Release Engineer",
        business_value="Lower change failure rate",
        expected_outcomes=["Risk-ranked changes", "Targeted review/canary", "Improving DORA metrics"],
        related=["deployment-safety", "incidents"],
    ),
    _module(
        key="executive-reports",
        name="Executive Reports",
        category="reporting",
        route="/reports",
        nav_path=["Sidebar", "Reports", "Executive Reports"],
        overview={
            "what": "Automated leadership reports summarizing reliability, incidents, SLOs, capacity, cost, and risk.",
            "why": "It gives leadership a single, consistent reliability narrative.",
            "business_value": "Executive alignment and demonstrable reliability ROI.",
            "who": "Engineering leadership, SRE leads, and executives.",
            "when": "Weekly/monthly leadership reviews.",
        },
        prerequisites=[
            "Operational data present (incidents, SLOs, cost, capacity).",
            "Read access to the organization's reporting.",
        ],
        steps=[
            _step("Open Reports → Executive Reports.", "Generated reports load with type and status."),
            _step("Open the Executive Command Center for the live view.", "Twelve widgets summarize health, risk, cost, and focus."),
            _step("Review reliability score, MTTR, and SLO compliance.", "Top-line reliability KPIs are shown."),
            _step("Review capacity, cost, deployment, and change-failure risks.", "Risk areas are quantified together."),
            _step("Export the report to PDF, HTML, or Markdown.", "A shareable file downloads for the leadership pack."),
        ],
        interpretation=[
            _term("Reliability score", "0–100 composite reliability posture with a letter grade."),
            _term("MTTR", "Mean time to resolve incidents — lower is better."),
            _term("SLO compliance", "Share of objectives currently met."),
            _term("Top risk services", "Services contributing most risk, with a basis."),
        ],
        example={
            "scenario": "Monthly board update.",
            "walkthrough": "Leadership exports the reliability report (PDF), highlighting a reliability score of 88 (B+), MTTR down 22%, and $50k/yr potential savings.",
            "outcome": "A crisp, data-backed reliability story for the board.",
        },
        troubleshooting=[
            _tip("Widgets show dashes.", "Underlying data is sparse.", "Generate incidents/SLOs/analyses to populate metrics."),
            _tip("Export fails.", "Transient issue or auth expiry.", "Retry; if it persists, re-authenticate and export again."),
            _tip("Numbers seem stale.", "Cached view.", "Reload the page to refresh the metrics."),
        ],
        best_practices=[
            "Export monthly and keep a trend archive.",
            "Pair the score with the top risk services for context.",
            "Use the Command Center live for ad-hoc questions.",
            "Share the same report format every cycle for comparability.",
        ],
        faq=[
            _faq("What formats can I export?", "PDF, HTML, and Markdown."),
            _faq("Where is the live view?", "The Executive Command Center page."),
            _faq("What does the reliability grade mean?", "A letter grade summarizing the 0–100 reliability score."),
            _faq("Can the CTO answer health/risk/cost from one screen?", "Yes — that's the Command Center's purpose."),
            _faq("How often are reports generated?", "On demand and on weekly/monthly schedules."),
        ],
        reading_time_minutes=5,
        difficulty="Beginner",
        role="Eng Leadership / Executive",
        business_value="Executive alignment & ROI",
        expected_outcomes=["One-screen executive view", "Exportable leadership reports", "Quantified reliability ROI"],
        related=["slos", "cost", "capacity"],
    ),
]


# --------------------------------------------------------------------------- #
# JOURNEYS — end-to-end customer journey guides.                              #
# --------------------------------------------------------------------------- #
def _journey(
    *, key: str, name: str, category: str, summary: str, stages: list[dict[str, str]],
    expected_outcomes: list[str],
) -> dict[str, Any]:
    enriched = []
    for i, st in enumerate(stages, start=1):
        enriched.append(
            {
                "order": i,
                "title": st["title"],
                "description": st["description"],
                "module": st.get("module", ""),
                "screenshot": f"journey-{key}-stage-{i}.png",
                "expected_outcome": st["expected_outcome"],
            }
        )
    return {
        "key": key,
        "name": name,
        "category": category,
        "summary": summary,
        "stages": enriched,
        "expected_outcomes": expected_outcomes,
        "screenshots": [
            {"name": s["screenshot"], "caption": f"{name} — {s['title']}", "category": category}
            for s in enriched
        ],
    }


JOURNEYS: list[dict[str, Any]] = [
    _journey(
        key="infrastructure-onboarding",
        name="Infrastructure Onboarding",
        category="onboarding",
        summary="Go from a connected provider to live SLOs and monitoring.",
        stages=[
            {"title": "Connect Provider", "description": "Select and validate your providers in the onboarding wizard.", "module": "onboarding", "expected_outcome": "Providers connected (read-only)."},
            {"title": "Discovery", "description": "Scan providers to inventory assets.", "module": "onboarding", "expected_outcome": "Assets discovered and counted."},
            {"title": "Service Mapping", "description": "Group assets into logical services.", "module": "service-health", "expected_outcome": "Services created."},
            {"title": "Dependency Discovery", "description": "Infer service-to-service dependencies.", "module": "dependencies", "expected_outcome": "Dependency edges mapped."},
            {"title": "SLO Creation", "description": "Generate default objectives per service.", "module": "slos", "expected_outcome": "SLOs created with coverage."},
            {"title": "Monitoring Setup", "description": "Enable monitoring rules and finalize.", "module": "monitoring", "expected_outcome": "Monitoring live; org ready."},
        ],
        expected_outcomes=["Connected providers", "Mapped services & dependencies", "Live SLOs and monitoring"],
    ),
    _journey(
        key="incident-management",
        name="Incident Investigation",
        category="incident",
        summary="From an alert to a published postmortem.",
        stages=[
            {"title": "Alert", "description": "An alert fires in Monitoring.", "module": "monitoring", "expected_outcome": "Alert visible and attributed."},
            {"title": "Incident", "description": "Escalate the alert into an investigation.", "module": "incidents", "expected_outcome": "Incident opened with context."},
            {"title": "Timeline", "description": "Review chronological events.", "module": "incidents", "expected_outcome": "Onset pinpointed with confidence."},
            {"title": "Change Intelligence", "description": "Correlate recent changes.", "module": "incidents", "expected_outcome": "Suspected change identified."},
            {"title": "Recommendations", "description": "Review ranked remediations.", "module": "incidents", "expected_outcome": "A high-confidence fix selected."},
            {"title": "Remediation", "description": "Approve and apply the action.", "module": "incidents", "expected_outcome": "Incident mitigated."},
            {"title": "Postmortem", "description": "Generate and export the retrospective.", "module": "postmortems", "expected_outcome": "Postmortem published."},
        ],
        expected_outcomes=["Root cause found fast", "Safe remediation", "Published postmortem"],
    ),
    _journey(
        key="safe-deployment",
        name="Safe Deployment",
        category="deployment",
        summary="Ship changes with confidence using risk and safety signals.",
        stages=[
            {"title": "Deployment Risk", "description": "Check the deployment risk view.", "module": "change-failure", "expected_outcome": "Risk understood up front."},
            {"title": "Deployment Safety", "description": "Run a pre-deploy safety analysis.", "module": "deployment-safety", "expected_outcome": "Safety score and status."},
            {"title": "Change Failure Prediction", "description": "Read predicted failure probability.", "module": "change-failure", "expected_outcome": "High-risk changes flagged."},
            {"title": "Deployment Review", "description": "Decide to ship, gate, or canary.", "module": "deployment-safety", "expected_outcome": "Evidence-based release decision."},
        ],
        expected_outcomes=["Pre-deploy risk visibility", "Gated risky changes", "Fewer change-induced incidents"],
    ),
    _journey(
        key="executive-reporting",
        name="Executive Reporting",
        category="reporting",
        summary="Turn operational data into a leadership-ready reliability story.",
        stages=[
            {"title": "SLO", "description": "Confirm objectives and compliance.", "module": "slos", "expected_outcome": "SLO posture understood."},
            {"title": "Capacity", "description": "Review capacity risk.", "module": "capacity", "expected_outcome": "Capacity risks quantified."},
            {"title": "Cost", "description": "Review savings opportunities.", "module": "cost", "expected_outcome": "Savings quantified."},
            {"title": "Reliability Dashboard", "description": "Open the Executive Command Center.", "module": "executive-reports", "expected_outcome": "One-screen executive view."},
            {"title": "Executive Report", "description": "Export the report.", "module": "executive-reports", "expected_outcome": "Shareable leadership pack."},
        ],
        expected_outcomes=["Unified executive view", "Quantified risk and savings", "Exportable report"],
    ),
]


# --------------------------------------------------------------------------- #
# PLAYBOOKS — integration playbooks.                                          #
# --------------------------------------------------------------------------- #
def _playbook(
    *, key: str, name: str, overview: str, architecture_diagram: str,
    prerequisites: list[str], required_permissions: list[str], credential_setup: list[str],
    validation_steps: list[str], expected_results: list[str], common_errors: list[dict[str, str]],
    troubleshooting: list[str], security_notes: list[str], best_practices: list[str],
) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "category": "integrations",
        "overview": overview,
        "architecture_diagram": architecture_diagram,
        "prerequisites": prerequisites,
        "required_permissions": required_permissions,
        "credential_setup": credential_setup,
        "validation_steps": validation_steps,
        "expected_results": expected_results,
        "common_errors": common_errors,
        "troubleshooting": troubleshooting,
        "security_notes": security_notes,
        "best_practices": best_practices,
        "screenshots": [
            {"name": f"playbook-{key}-credentials.png", "caption": f"{name} credential setup", "category": "integrations"},
            {"name": f"playbook-{key}-validation.png", "caption": f"{name} validation", "category": "integrations"},
        ],
    }


def _err(error: str, fix: str) -> dict[str, str]:
    return {"error": error, "fix": fix}


_DIAGRAM = "[ {name} ] --read-only--> [ Nexora Collector ] --> [ Nexora Platform ]"

PLAYBOOKS: list[dict[str, Any]] = [
    _playbook(
        key="aws",
        name="AWS",
        overview="Connect AWS to discover resources, ingest CloudWatch signals, and attribute cost.",
        architecture_diagram=_DIAGRAM.format(name="AWS Account"),
        prerequisites=["An AWS account", "Ability to create an IAM role or access keys"],
        required_permissions=["ReadOnlyAccess (or scoped read for EC2, RDS, CloudWatch, Cost Explorer)"],
        credential_setup=[
            "Create an IAM role/user with read-only access.",
            "In Onboarding → Provider Selection, choose AWS.",
            "Provide the role ARN or access keys in Credential Validation.",
        ],
        validation_steps=["Run Credential Validation for AWS.", "Confirm a 'valid' status and run Discovery."],
        expected_results=["EC2/RDS and related resources discovered.", "CloudWatch alerts visible in Monitoring.", "Cost attributed in Cost Optimization."],
        common_errors=[_err("AccessDenied during discovery", "Attach read-only permissions to the role/user."), _err("No cost data", "Enable Cost Explorer read access.")],
        troubleshooting=["If discovery is empty, confirm the region scope and read permissions.", "If cost is missing, verify Cost Explorer access."],
        security_notes=["Use read-only credentials.", "Prefer a scoped IAM role over long-lived keys.", "Credentials are validated read-only and not stored."],
        best_practices=["Start with ReadOnlyAccess, then scope down.", "Use an assumable role per environment."],
    ),
    _playbook(
        key="azure",
        name="Azure",
        overview="Connect Azure to discover resources and ingest Monitor metrics.",
        architecture_diagram=_DIAGRAM.format(name="Azure Subscription"),
        prerequisites=["An Azure subscription", "Permission to register an app or assign a role"],
        required_permissions=["Reader role on the subscription/resource group"],
        credential_setup=[
            "Register an app (service principal) or use a managed identity.",
            "Assign the Reader role.",
            "Provide tenant/client/subscription details in Credential Validation.",
        ],
        validation_steps=["Run Credential Validation for Azure.", "Confirm 'valid' and run Discovery."],
        expected_results=["Azure resources discovered.", "Azure Monitor signals visible in Monitoring."],
        common_errors=[_err("AuthorizationFailed", "Assign the Reader role at the right scope."), _err("Invalid client secret", "Regenerate the secret and re-validate.")],
        troubleshooting=["If empty, check the Reader scope.", "If auth fails, verify tenant/client IDs."],
        security_notes=["Use the Reader role only.", "Rotate client secrets regularly.", "Secrets are not stored by Nexora."],
        best_practices=["Prefer managed identities where possible.", "Scope to the smallest subscription/RG needed."],
    ),
    _playbook(
        key="kubernetes",
        name="Kubernetes",
        overview="Connect a cluster to discover workloads and watch service health.",
        architecture_diagram=_DIAGRAM.format(name="Kubernetes Cluster"),
        prerequisites=["A reachable cluster", "Ability to create a read-only ServiceAccount"],
        required_permissions=["Read-only RBAC (get/list/watch on core + apps)"],
        credential_setup=[
            "Create a read-only ServiceAccount and ClusterRoleBinding.",
            "Select Kubernetes in Provider Selection.",
            "Provide the kubeconfig/token in Credential Validation.",
        ],
        validation_steps=["Run Credential Validation.", "Confirm 'valid' and run Discovery."],
        expected_results=["Deployments/pods/services discovered.", "Workload health reflected in Service Health."],
        common_errors=[_err("Forbidden (RBAC)", "Bind the read-only ClusterRole to the ServiceAccount."), _err("Connection timeout", "Ensure the API server is reachable from the collector.")],
        troubleshooting=["If forbidden, verify RBAC.", "If unreachable, check network/firewall to the API server."],
        security_notes=["Use read-only RBAC (get/list/watch).", "Avoid cluster-admin.", "Tokens are validated read-only, not stored."],
        best_practices=["Scope to namespaces you need.", "Rotate ServiceAccount tokens."],
    ),
    _playbook(
        key="github",
        name="GitHub",
        overview="Connect GitHub to power change intelligence and change-failure prediction.",
        architecture_diagram=_DIAGRAM.format(name="GitHub Org"),
        prerequisites=["A GitHub org/repo", "Ability to install an app or create a token"],
        required_permissions=["Read access to repository contents, commits, and deployments"],
        credential_setup=[
            "Install the GitHub App or create a fine-grained PAT (read-only).",
            "Select GitHub in Provider Selection.",
            "Provide the token in Credential Validation.",
        ],
        validation_steps=["Run Credential Validation.", "Open an incident and confirm Change Intelligence is populated."],
        expected_results=["Commits/releases appear in incident Change Intelligence.", "Change-failure predictions use change history."],
        common_errors=[_err("404 on repo", "Grant the app/token access to the repository."), _err("Rate limited", "Use a GitHub App for higher limits.")],
        troubleshooting=["If Change Intelligence is empty, verify repo access.", "If rate-limited, switch to a GitHub App."],
        security_notes=["Use read-only scopes.", "Prefer fine-grained tokens or a GitHub App.", "Tokens are not stored."],
        best_practices=["Install at the org level for full coverage.", "Limit to the repos you need."],
    ),
    _playbook(
        key="gitlab",
        name="GitLab",
        overview="Connect GitLab to power change intelligence from merge requests and pipelines.",
        architecture_diagram=_DIAGRAM.format(name="GitLab Group"),
        prerequisites=["A GitLab group/project", "Ability to create a read-only access token"],
        required_permissions=["read_api / read_repository scope"],
        credential_setup=[
            "Create a project/group access token with read scopes.",
            "Select GitLab in Provider Selection.",
            "Provide the token in Credential Validation.",
        ],
        validation_steps=["Run Credential Validation.", "Confirm commits/pipelines appear in Change Intelligence."],
        expected_results=["MRs/commits/pipelines feed change intelligence.", "Predictions use change history."],
        common_errors=[_err("401 Unauthorized", "Recreate the token with read scopes."), _err("403 on project", "Grant the token access to the group/project.")],
        troubleshooting=["If empty, verify token scopes.", "If 403, check project membership of the token."],
        security_notes=["Use read_api/read_repository only.", "Set an expiry on tokens.", "Tokens are not stored."],
        best_practices=["Use a group token for multi-project coverage.", "Rotate tokens periodically."],
    ),
    _playbook(
        key="slack",
        name="Slack",
        overview="Connect Slack to deliver alert and incident notifications to channels.",
        architecture_diagram="[ Nexora Platform ] --notify--> [ Slack Workspace ]",
        prerequisites=["A Slack workspace", "Permission to install an app"],
        required_permissions=["chat:write to the target channel(s)"],
        credential_setup=[
            "Create/install a Slack app and add it to channels.",
            "Provide the bot token / webhook in the integration settings.",
            "Choose target channels for notifications.",
        ],
        validation_steps=["Send a test notification.", "Confirm it arrives in the chosen channel."],
        expected_results=["Alerts/incidents post to Slack.", "Responders are notified in-channel."],
        common_errors=[_err("not_in_channel", "Invite the app to the channel."), _err("invalid_auth", "Reinstall the app and refresh the token.")],
        troubleshooting=["If nothing posts, confirm the app is in the channel.", "If auth fails, reinstall the app."],
        security_notes=["Grant only chat:write.", "Restrict to specific channels.", "Tokens are stored encrypted server-side for delivery."],
        best_practices=["Route by severity to different channels.", "Avoid noisy channels for Sev1 only."],
    ),
    _playbook(
        key="microsoft-teams",
        name="Microsoft Teams",
        overview="Connect Microsoft Teams to deliver notifications via an incoming webhook.",
        architecture_diagram="[ Nexora Platform ] --notify--> [ MS Teams Channel ]",
        prerequisites=["A Teams channel", "Permission to add a connector"],
        required_permissions=["Incoming Webhook connector on the channel"],
        credential_setup=[
            "Add an Incoming Webhook connector to the channel.",
            "Copy the webhook URL.",
            "Paste it into the integration settings.",
        ],
        validation_steps=["Send a test message.", "Confirm it appears in the Teams channel."],
        expected_results=["Alerts/incidents post to Teams.", "Responders notified in-channel."],
        common_errors=[_err("404 on webhook", "Recreate the connector and update the URL."), _err("Message not delivered", "Verify the channel still has the connector.")],
        troubleshooting=["If undelivered, recreate the webhook.", "If formatting breaks, check the connector status."],
        security_notes=["Webhook URLs are secrets — store securely.", "Rotate if exposed.", "Stored encrypted for delivery."],
        best_practices=["Use separate channels per severity.", "Document the webhook owner."],
    ),
    _playbook(
        key="jira",
        name="Jira",
        overview="Connect Jira to create tickets from incidents and postmortem action items.",
        architecture_diagram="[ Nexora Platform ] --create issues--> [ Jira Project ]",
        prerequisites=["A Jira project", "An account that can create issues"],
        required_permissions=["Create Issues in the target project"],
        credential_setup=[
            "Create an API token for a service account.",
            "Provide the site URL, email, and token in integration settings.",
            "Select the default project and issue type.",
        ],
        validation_steps=["Create a test issue from an action item.", "Confirm it appears in the Jira project."],
        expected_results=["Action items become Jira issues.", "Incidents can link to tickets."],
        common_errors=[_err("401 Unauthorized", "Regenerate the API token and re-enter credentials."), _err("Project not found", "Check the project key and permissions.")],
        troubleshooting=["If creation fails, verify Create Issues permission.", "If project missing, confirm the project key."],
        security_notes=["Use a dedicated service account.", "Grant least privilege (create only).", "Token stored encrypted server-side."],
        best_practices=["Map severities to issue priorities.", "Auto-create issues for postmortem actions."],
    ),
]


# --------------------------------------------------------------------------- #
# CUSTOMER SUCCESS CENTER — beginner "first X" guides.                        #
# --------------------------------------------------------------------------- #
def _success(
    *, key: str, name: str, category: str, summary: str, est_minutes: int,
    steps: list[dict[str, str]], expected_outcome: str, related: list[str],
) -> dict[str, Any]:
    enriched = []
    for i, st in enumerate(steps, start=1):
        enriched.append(
            {
                "order": i,
                "action": st["action"],
                "expected": st["expected"],
                "screenshot": f"success-{key}-step-{i}.png",
            }
        )
    return {
        "key": key,
        "name": name,
        "category": category,
        "summary": summary,
        "difficulty": "Beginner",
        "estimated_minutes": est_minutes,
        "steps": enriched,
        "expected_outcome": expected_outcome,
        "related": related,
        "screenshots": [
            {"name": s["screenshot"], "caption": f"{name} — step {s['order']}", "category": category}
            for s in enriched
        ],
    }


SUCCESS_CENTER: list[dict[str, Any]] = [
    _success(
        key="first-15-minutes", name="Your First 15 Minutes", category="onboarding",
        summary="Get from signup to first value fast.", est_minutes=15,
        steps=[
            _step("Sign up and open Get started → Onboarding.", "The wizard opens at Organization Setup."),
            _step("Create your organization.", "Context auto-switches into the new org."),
            _step("Select and validate at least one provider.", "Connectivity is confirmed."),
            _step("Run discovery, mapping, SLOs, and monitoring.", "Your infrastructure is set up."),
            _step("Generate a sample incident and investigate it.", "You complete a full workflow end-to-end."),
        ],
        expected_outcome="A working organization with SLOs, monitoring, and a completed sample investigation.",
        related=["onboarding", "incidents"],
    ),
    _success(
        key="first-incident", name="Your First Incident", category="incident",
        summary="Investigate an incident from alert to fix.", est_minutes=10,
        steps=[
            _step("Open Operations → Incidents and select one.", "Incident Detail opens."),
            _step("Read the Timeline.", "You see when and how it started."),
            _step("Open Change Intelligence.", "You see the suspected change."),
            _step("Review Recommendations.", "You pick a high-confidence fix."),
            _step("Apply remediation and confirm recovery.", "The incident is mitigated."),
        ],
        expected_outcome="A mitigated incident with a clear root cause.",
        related=["incidents", "monitoring"],
    ),
    _success(
        key="first-deployment", name="Your First Safe Deployment", category="deployment",
        summary="Ship a change using safety signals.", est_minutes=8,
        steps=[
            _step("Open Deployments → Deployment Safety.", "Analyses load."),
            _step("Find your application's analysis.", "You see its safety score."),
            _step("Check Change Failure Prediction.", "You see failure probability."),
            _step("Decide ship/gate/canary.", "You make an evidence-based call."),
            _step("Deploy and watch service health.", "You confirm a healthy rollout."),
        ],
        expected_outcome="A change shipped with risk understood and verified.",
        related=["deployment-safety", "change-failure"],
    ),
    _success(
        key="first-postmortem", name="Your First Postmortem", category="incident",
        summary="Capture a blameless retrospective.", est_minutes=7,
        steps=[
            _step("Open a resolved incident.", "Incident Detail opens."),
            _step("Go to the Postmortem tab.", "The postmortem (or a generate option) is shown."),
            _step("Generate the postmortem.", "A structured document is created."),
            _step("Assign owners to action items.", "Follow-ups are actionable."),
            _step("Export to PDF and share.", "Leadership receives the retrospective."),
        ],
        expected_outcome="A published, shareable postmortem with action items.",
        related=["postmortems", "incidents"],
    ),
    _success(
        key="first-executive-report", name="Your First Executive Report", category="reporting",
        summary="Produce a leadership-ready reliability report.", est_minutes=6,
        steps=[
            _step("Open the Executive Command Center.", "Twelve widgets load."),
            _step("Review reliability, MTTR, and SLO compliance.", "You see top-line health."),
            _step("Review cost and risk widgets.", "You see savings and risks."),
            _step("Read the Executive Summary.", "You get the narrative and focus areas."),
            _step("Export to PDF.", "A shareable report downloads."),
        ],
        expected_outcome="An exported executive report covering health, risk, and cost.",
        related=["executive-reports", "cost"],
    ),
    _success(
        key="first-slo", name="Your First SLO", category="reporting",
        summary="Set a meaningful reliability target.", est_minutes=6,
        steps=[
            _step("Open Reliability → SLOs.", "Objectives load."),
            _step("Open a service's SLOs tab.", "You see target vs current."),
            _step("Accept a generated default target.", "A baseline objective exists."),
            _step("Watch for a week.", "You learn the real baseline."),
            _step("Tune the target.", "Compliance recomputes."),
        ],
        expected_outcome="A defensible SLO with a visible error budget.",
        related=["slos", "service-health"],
    ),
    _success(
        key="first-cost-review", name="Your First Cost Optimization Review", category="reporting",
        summary="Find and act on quick savings.", est_minutes=8,
        steps=[
            _step("Open Infrastructure → Cost Optimization.", "Analyses load."),
            _step("Read estimated waste and idle resources.", "You see the opportunity."),
            _step("Open the top recommendations.", "Each shows monthly savings."),
            _step("Validate the lowest-risk items.", "You confirm they're safe."),
            _step("Assign owners and apply.", "Savings start to realize."),
        ],
        expected_outcome="A prioritized savings plan with the first wins applied.",
        related=["cost", "capacity"],
    ),
]


# --------------------------------------------------------------------------- #
# Sprint 56A.1 enrichment — architecture, "What Happens Internally",          #
# expected screens, playbook validation, and learning paths.                  #
# --------------------------------------------------------------------------- #
LAST_UPDATED = "2026-06-23"

# Per-module Mermaid architecture diagrams.
MODULE_ARCH: dict[str, str] = {
    "onboarding": "graph TD\n  Providers --> Discovery\n  Discovery --> ServiceMap\n  ServiceMap --> Dependencies\n  Dependencies --> SLOs\n  SLOs --> Monitoring\n  Monitoring --> Ready[Org Ready]",
    "monitoring": "graph TD\n  Providers --> Collector\n  Collector --> AlertStream\n  AlertStream --> Dedup\n  Dedup --> Monitoring[Monitoring View]\n  Monitoring --> Incidents",
    "incidents": "graph TD\n  Alert --> Incident\n  Incident --> Timeline\n  Timeline --> ChangeCorrelation\n  ChangeCorrelation --> RCA\n  RCA --> Recommendations\n  Recommendations --> Remediation",
    "postmortems": "graph TD\n  Incident --> Timeline\n  Timeline --> RootCause\n  RootCause --> Postmortem\n  Postmortem --> ActionItems\n  Postmortem --> Export",
    "service-health": "graph TD\n  Metrics --> HealthEngine\n  SLOs --> HealthEngine\n  Incidents --> HealthEngine\n  HealthEngine --> HealthScore\n  HealthScore --> Predictions",
    "slos": "graph TD\n  Metrics --> SLOEngine\n  Targets --> SLOEngine\n  SLOEngine --> Compliance\n  SLOEngine --> ErrorBudget",
    "dependencies": "graph TD\n  Discovery --> ServiceMap\n  ServiceMap --> DependencyGraph\n  DependencyGraph --> BlastRadius",
    "capacity": "graph TD\n  Metrics --> Forecaster\n  Forecaster --> Utilization\n  Utilization --> ExhaustionDate\n  Forecaster --> RiskTier",
    "cost": "graph TD\n  BillingData --> CostEngine\n  Usage --> CostEngine\n  CostEngine --> Waste\n  CostEngine --> Recommendations\n  CostEngine --> Savings",
    "deployment-safety": "graph TD\n  Change --> SafetyEngine\n  History --> SafetyEngine\n  ServiceHealth --> SafetyEngine\n  SafetyEngine --> SafetyScore\n  SafetyScore --> Decision",
    "change-failure": "graph TD\n  ChangeHistory --> Model\n  Change --> Model\n  Model --> FailureProbability\n  Model --> BlastRadius",
    "executive-reports": "graph TD\n  SLOs --> Aggregator\n  Capacity --> Aggregator\n  Cost --> Aggregator\n  Incidents --> Aggregator\n  Aggregator --> CommandCenter\n  CommandCenter --> Export",
}

# Per-module "What Happens Internally".
MODULE_INTERNAL: dict[str, dict[str, Any]] = {
    "onboarding": {"customer_action": "Run the onboarding wizard", "engines": ["Discovery Engine", "Service Mapper", "Dependency Mapper", "SLO Generator", "Monitoring Provisioner", "Default Team Provisioner"], "outputs": ["Connected providers", "Mapped services", "Generated SLOs", "Monitoring rules", "Sample incident"]},
    "monitoring": {"customer_action": "Open Monitoring", "engines": ["Provider Collectors", "Alert Normalizer", "Deduplication", "Severity Router"], "outputs": ["Unified alert stream", "Service attribution"]},
    "incidents": {"customer_action": "Click Investigate", "engines": ["Timeline Engine", "Change Correlation Engine", "RCA Engine", "Recommendation Engine", "Remediation Engine"], "outputs": ["Root cause", "Confidence score", "Recommendations", "Remediation actions"]},
    "postmortems": {"customer_action": "Generate postmortem", "engines": ["Timeline Aggregator", "Root Cause Synthesizer", "Action Item Extractor", "Document Renderer"], "outputs": ["Postmortem document", "Action items", "Export (PDF/HTML/MD)"]},
    "service-health": {"customer_action": "Open Service Health", "engines": ["Metric Aggregator", "SLO Evaluator", "Incident Correlator", "Health Scorer", "Predictor"], "outputs": ["Health score", "Burn rate", "Budget remaining", "Prediction"]},
    "slos": {"customer_action": "Open SLOs", "engines": ["Metric Aggregator", "SLO Evaluator", "Error Budget Calculator"], "outputs": ["Compliance", "Error budget"]},
    "dependencies": {"customer_action": "Open Dependency Graph", "engines": ["Discovery", "Service Mapper", "Dependency Inference", "Blast Radius Calculator"], "outputs": ["Dependency edges", "Blast radius"]},
    "capacity": {"customer_action": "Open Capacity Planning", "engines": ["Metric Collector", "Forecaster", "Exhaustion Estimator", "Risk Classifier"], "outputs": ["Forecasts", "Exhaustion date", "Risk tier"]},
    "cost": {"customer_action": "Open Cost Optimization", "engines": ["Cost Ingestion", "Waste Detector", "Recommendation Engine", "Savings Estimator"], "outputs": ["Estimated waste", "Recommendations", "Savings"]},
    "deployment-safety": {"customer_action": "Run a safety analysis", "engines": ["Change Analyzer", "History Analyzer", "Service Health Reader", "Safety Scorer"], "outputs": ["Safety score", "Status", "Risk factors"]},
    "change-failure": {"customer_action": "Open Change Failure Prediction", "engines": ["Change History Model", "Risk Scorer", "Blast Radius Calculator"], "outputs": ["Failure probability", "Risk level", "Blast radius"]},
    "executive-reports": {"customer_action": "Open the Command Center / generate a report", "engines": ["Reliability Aggregator", "Risk Aggregator", "Cost Aggregator", "Summary Generator", "Report Renderer"], "outputs": ["Reliability score", "Risk summary", "Exportable report"]},
}

# Per-module expected screens (validate success without screenshots).
MODULE_EXPECTED_SCREENS: dict[str, list[str]] = {
    "onboarding": ["Provider Selection grid", "Discovery summary", "SLO coverage tiles", "Monitoring summary", "Sample incident banner"],
    "monitoring": ["Active Alerts list", "Notifications popover", "Service status"],
    "incidents": ["Incident summary header", "Timeline tab", "Change Intelligence tab", "Recommendations tab", "Postmortem tab"],
    "postmortems": ["Postmortems list", "Postmortem tab", "Export buttons"],
    "service-health": ["Health Overview tab", "SLOs tab", "Dependencies tab", "Incidents tab"],
    "slos": ["SLO list", "Target vs current", "Error budget"],
    "dependencies": ["Dependency edges list", "Dependencies tab", "Blast radius"],
    "capacity": ["Capacity forecasts list", "Capacity tab", "Exhaustion date"],
    "cost": ["Cost analyses", "Savings Opportunity widget", "Top recommendations"],
    "deployment-safety": ["Deployment Safety analyses", "Safety score", "Deployments tab"],
    "change-failure": ["Change Failure list", "Risk level badges", "Change Failure Risks widget"],
    "executive-reports": ["Executive Command Center widgets", "Executive Summary", "Export buttons"],
}

# --------------------------------------------------------------------------- #
# Sprint 56D.2 — Customer Success Documentation Rewrite.                        #
# Append brand-new training-grade module guides and rewrite existing ones with #
# 10+ steps (each with "what happens internally"), >=10 FAQs, results          #
# interpretation, common mistakes, and next steps. Applied BEFORE the          #
# screenshot/expected-screen enrichment loop so new content is enriched too.   #
# --------------------------------------------------------------------------- #
from app.services.customer_success_training import (  # noqa: E402
    COMMON_MISTAKES as _TRAIN_MISTAKES,
)
from app.services.customer_success_training import (  # noqa: E402
    DEEP_DIVE as _TRAIN_DEEP,
)
from app.services.customer_success_training import (  # noqa: E402
    NEW_MODULE_DEFS as _TRAIN_NEW,
)
from app.services.customer_success_training import (  # noqa: E402
    NEXT_STEPS as _TRAIN_NEXT,
)
from app.services.customer_success_training import (  # noqa: E402
    TRAINING_FAQ as _TRAIN_FAQ,
)
from app.services.customer_success_training import (  # noqa: E402
    TRAINING_INTERPRETATION as _TRAIN_INTERP,
)
from app.services.customer_success_training import (  # noqa: E402
    TRAINING_STEPS as _TRAIN_STEPS,
)


def _rebuild_screenshots(_m: dict[str, Any]) -> list[dict[str, str]]:
    _key, _name, _cat = _m["key"], _m["name"], _m["category"]
    return [
        {"name": f"{_key}-overview.png", "caption": f"{_name} overview", "category": _cat},
        *[
            {"name": s["screenshot"], "caption": f"{_name} — step {s['order']}", "category": _cat}
            for s in _m["steps"]
        ],
        {"name": f"{_key}-results.png", "caption": f"{_name} results interpretation", "category": _cat},
    ]


# 1) Append brand-new module guides.
for _d in _TRAIN_NEW:
    _new = _module(
        key=_d["key"], name=_d["name"], category=_d["category"], route=_d["route"],
        nav_path=_d["nav_path"], overview=_d["overview"], prerequisites=_d["prerequisites"],
        steps=[_step(_a, _e) for (_a, _e, _i) in _d["steps"]],
        interpretation=[_term(_t, _mm) for (_t, _mm) in _d["interpretation"]],
        example=_d["example"],
        troubleshooting=[_tip(*_x) for _x in _d["troubleshooting"]],
        best_practices=_d["best_practices"],
        faq=[_faq(_q, _ans) for (_q, _ans) in _d["faq"]],
        reading_time_minutes=_d["reading_time_minutes"], difficulty=_d["difficulty"],
        role=_d["role"], business_value=_d["business_value"],
        expected_outcomes=_d["expected_outcomes"], related=_d["related"],
    )
    for _st, (_a, _e, _i) in zip(_new["steps"], _d["steps"], strict=True):
        _st["internal"] = _i
    _new["common_mistakes"] = _d["common_mistakes"]
    _new["next_steps"] = _d["next_steps"]
    MODULES.append(_new)
    MODULE_ARCH[_d["key"]] = _d["arch"]
    MODULE_INTERNAL[_d["key"]] = _d["internal"]
    MODULE_EXPECTED_SCREENS[_d["key"]] = _d["expected_screens"]

# 2) Rewrite existing modules with the training-grade content.
_by_key = {_m["key"]: _m for _m in MODULES}
for _key, _steps in _TRAIN_STEPS.items():
    _m = _by_key.get(_key)
    if not _m:
        continue
    _m["steps"] = [
        {"order": _i, "action": _a, "expected": _e,
         "screenshot": f"{_key}-step-{_i}.png", "internal": _internal}
        for _i, (_a, _e, _internal) in enumerate(_steps, start=1)
    ]
    _m["screenshots"] = _rebuild_screenshots(_m)
for _key, _faqs in _TRAIN_FAQ.items():
    if _key in _by_key:
        _by_key[_key]["faq"] = [{"question": _q, "answer": _ans} for (_q, _ans) in _faqs]
for _key, _interp in _TRAIN_INTERP.items():
    if _key in _by_key:
        _by_key[_key]["interpretation"] = [{"term": _t, "meaning": _mm} for (_t, _mm) in _interp]
for _key, _cm in _TRAIN_MISTAKES.items():
    if _key in _by_key:
        _by_key[_key]["common_mistakes"] = _cm
for _key, _ns in _TRAIN_NEXT.items():
    if _key in _by_key:
        _by_key[_key]["next_steps"] = _ns


# --------------------------------------------------------------------------- #
# Sprint 56D.3 — End-to-End Customer Journey Documentation.                     #
# Enrich every journey stage with navigation, expected screen, "what happens   #
# internally", common issues, recovery steps, and a per-stage screenshot route #
# plus a Mermaid diagram per journey.                                          #
# --------------------------------------------------------------------------- #
from app.services.customer_success_journeys import (  # noqa: E402
    JOURNEY_DIAGRAMS as _J_DIAGRAMS,
)
from app.services.customer_success_journeys import (  # noqa: E402
    STAGE_DETAIL as _J_DETAIL,
)

_MODULE_ROUTES = {_m["key"]: _m["route"] for _m in MODULES}
for _j in JOURNEYS:
    _jk = _j["key"]
    _j["diagram"] = _J_DIAGRAMS.get(_jk, "")
    _details = _J_DETAIL.get(_jk, [])
    for _st in _j["stages"]:
        _d = _details[_st["order"] - 1] if _st["order"] - 1 < len(_details) else {}
        _route = str(_d.get("route", "")) or _MODULE_ROUTES.get(_st["module"], "")
        _st["navigation"] = list(_d.get("navigation", []))
        _st["route"] = _route
        _st["expected_screen"] = list(_d.get("expected_screen", []))
        _st["internal"] = str(_d.get("internal", ""))
        _st["common_issues"] = list(_d.get("common_issues", []))
        _st["recovery_steps"] = list(_d.get("recovery_steps", []))


for _m in MODULES:
    _k = _m["key"]
    _m["architecture_diagram"] = MODULE_ARCH[_k]
    _m["internal"] = MODULE_INTERNAL[_k]
    _m["expected_screens"] = MODULE_EXPECTED_SCREENS[_k]
    _m["updated_at"] = LAST_UPDATED
    _m.setdefault("common_mistakes", [])
    _m.setdefault("next_steps", [])
    _m["deep_dive"] = _TRAIN_DEEP.get(_k, "")
    for _s in _m["steps"]:
        _s["expected_screens"] = MODULE_EXPECTED_SCREENS[_k]
        # Sprint 56B — embedded screenshot metadata (replaces bare placeholder).
        _s["screenshot_id"] = _s["screenshot"].rsplit(".", 1)[0]
        _s["caption"] = f"{_m['name']} — step {_s['order']}"
        _s["alt_text"] = f"{_m['name']} screen: {_s['action']}"
        _s.setdefault("internal", "")

# Playbook validation checklists, recovery steps, and expected outputs.
PLAYBOOK_CHECKLIST: dict[str, list[str]] = {
    "aws": ["Credentials added", "Validation passed", "Discovery completed", "Resources found", "Services created", "Dependencies mapped"],
    "azure": ["Credentials added", "Validation passed", "Discovery completed", "Resources found", "Services created", "Dependencies mapped"],
    "kubernetes": ["ServiceAccount created", "Validation passed", "Workloads discovered", "Services created", "Health reporting"],
    "github": ["Token/App added", "Validation passed", "Repositories accessible", "Change intelligence populated"],
    "gitlab": ["Token added", "Validation passed", "Projects accessible", "Change intelligence populated"],
    "slack": ["App installed", "Token/webhook added", "Test notification sent", "Delivery confirmed"],
    "microsoft-teams": ["Connector added", "Webhook URL saved", "Test message sent", "Delivery confirmed"],
    "jira": ["API token added", "Project selected", "Test issue created", "Issue visible in Jira"],
}
PLAYBOOK_RECOVERY: dict[str, list[str]] = {
    "aws": ["Re-attach read-only permissions", "Confirm region scope", "Re-run discovery"],
    "azure": ["Assign Reader role at correct scope", "Regenerate client secret", "Re-validate"],
    "kubernetes": ["Bind read-only ClusterRole", "Verify API server reachability", "Re-validate token"],
    "github": ["Grant repo access to the app/token", "Switch to a GitHub App for rate limits", "Re-validate"],
    "gitlab": ["Recreate token with read scopes", "Add token to the group/project", "Re-validate"],
    "slack": ["Invite the app to the channel", "Reinstall the app", "Resend test notification"],
    "microsoft-teams": ["Recreate the incoming webhook", "Update the webhook URL", "Resend test message"],
    "jira": ["Regenerate the API token", "Confirm Create Issues permission", "Re-test issue creation"],
}

# --------------------------------------------------------------------------- #
# Sprint 56D.4 — Integration Success Playbooks (enterprise-grade detail).       #
# Adds business value, use cases, step-by-step configuration, expected screens, #
# >=10 FAQs, a Mermaid architecture diagram, and a full visual set (actual,     #
# architecture, annotated, validation, success).                               #
# --------------------------------------------------------------------------- #
from app.services.customer_success_playbooks import (  # noqa: E402
    ANNOTATIONS as _PB_ANN,
)
from app.services.customer_success_playbooks import (  # noqa: E402
    ARCH_MERMAID as _PB_ARCH,
)
from app.services.customer_success_playbooks import (  # noqa: E402
    BUSINESS_VALUE as _PB_VALUE,
)
from app.services.customer_success_playbooks import (  # noqa: E402
    CONFIG_STEPS as _PB_CONFIG,
)
from app.services.customer_success_playbooks import (  # noqa: E402
    EXPECTED_SCREENS as _PB_SCREENS,
)
from app.services.customer_success_playbooks import (  # noqa: E402
    PLAYBOOK_FAQ as _PB_FAQ,
)
from app.services.customer_success_playbooks import (  # noqa: E402
    PLAYBOOK_ROUTE as _PB_ROUTE,
)
from app.services.customer_success_playbooks import (  # noqa: E402
    USE_CASES as _PB_USECASES,
)

_PB_SHOTS = ["overview", "detail", "workflow"]

for _p in PLAYBOOKS:
    _pk = _p["key"]
    _p["validation_checklist"] = PLAYBOOK_CHECKLIST[_pk]
    _p["recovery_steps"] = PLAYBOOK_RECOVERY[_pk]
    _p["expected_outputs"] = list(_p["expected_results"])
    _p["business_value"] = _PB_VALUE.get(_pk, "")
    _p["use_cases"] = list(_PB_USECASES.get(_pk, []))
    _p["route"] = _PB_ROUTE
    _p["expected_screens"] = list(_PB_SCREENS.get(_pk, []))
    _p["architecture_mermaid"] = _PB_ARCH.get(_pk, "")
    _p["faq"] = [{"question": _q, "answer": _a} for (_q, _a) in _PB_FAQ.get(_pk, [])]
    _p["annotations"] = [{"target": _t, "note": _n} for (_t, _n) in _PB_ANN.get(_pk, [])]
    # Step-by-step configuration with per-step screenshot metadata.
    _cfg = []
    for _i, (_title, _action, _expected) in enumerate(_PB_CONFIG.get(_pk, []), start=1):
        _sid = f"playbook-{_pk}-config-{_i}"
        _cfg.append({
            "order": _i, "title": _title, "action": _action, "expected": _expected,
            "screenshot": f"{_sid}.png", "screenshot_id": _sid,
            "caption": f"{_p['name']} configuration — {_title}",
            "alt_text": f"{_p['name']} setup screen: {_action}",
            "route": _PB_ROUTE, "shot": _PB_SHOTS[(_i - 1) % len(_PB_SHOTS)],
        })
    _p["configuration_steps"] = _cfg
    # Full visual set: actual, architecture, annotated, validation, success.
    _ann_targets = [a["target"] for a in _p["annotations"]]
    _p["visuals"] = [
        {"kind": "actual", "title": f"{_p['name']} integration screen", "route": _PB_ROUTE,
         "shot": "overview", "screenshot_id": f"playbook-{_pk}-actual",
         "caption": f"{_p['name']} — integration settings", "annotations": [], "diagram": ""},
        {"kind": "architecture", "title": f"{_p['name']} architecture", "route": "",
         "shot": "", "screenshot_id": "", "caption": f"{_p['name']} architecture diagram",
         "annotations": [], "diagram": _PB_ARCH.get(_pk, "")},
        {"kind": "annotated", "title": f"{_p['name']} annotated setup", "route": _PB_ROUTE,
         "shot": "overview", "screenshot_id": f"playbook-{_pk}-annotated",
         "caption": f"{_p['name']} — annotated credential setup", "annotations": _ann_targets, "diagram": ""},
        {"kind": "validation", "title": f"{_p['name']} validation", "route": _PB_ROUTE,
         "shot": "detail", "screenshot_id": f"playbook-{_pk}-validation",
         "caption": f"{_p['name']} — validation passed", "annotations": [], "diagram": ""},
        {"kind": "success", "title": f"{_p['name']} success", "route": _PB_ROUTE,
         "shot": "workflow", "screenshot_id": f"playbook-{_pk}-success",
         "caption": f"{_p['name']} — connected successfully", "annotations": [], "diagram": ""},
    ]


# --------------------------------------------------------------------------- #
# LEARNING PATHS — guided learning tracks.                                     #
# --------------------------------------------------------------------------- #
def _path(*, key: str, name: str, summary: str, steps: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "summary": summary,
        "steps": [{"label": label, "module": module} for label, module in steps],
    }


LEARNING_PATHS: list[dict[str, Any]] = [
    _path(
        key="platform-fundamentals", name="Platform Fundamentals",
        summary="Learn the basics: get set up, watch alerts, and handle incidents.",
        steps=[("Overview", "onboarding"), ("Infrastructure Discovery", "onboarding"), ("Monitoring", "monitoring"), ("Incidents", "incidents")],
    ),
    _path(
        key="sre-operations", name="SRE Operations",
        summary="Operate reliably: investigate, recommend, remediate, and retrospect.",
        steps=[("Incident Investigation", "incidents"), ("Recommendations", "incidents"), ("Remediation", "incidents"), ("Postmortems", "postmortems")],
    ),
    _path(
        key="safe-deployments", name="Safe Deployments",
        summary="Ship safely with risk and safety signals.",
        steps=[("Deployment Risk", "change-failure"), ("Deployment Safety", "deployment-safety"), ("Change Failure Prediction", "change-failure")],
    ),
    _path(
        key="reliability-leadership", name="Reliability Leadership",
        summary="Lead reliability: objectives, capacity, cost, and executive reporting.",
        steps=[("SLOs", "slos"), ("Capacity", "capacity"), ("Cost", "cost"), ("Executive Reports", "executive-reports")],
    ),
]


def learning_path_progress(path: dict[str, Any], completed: set[str]) -> dict[str, Any]:
    steps = path["steps"]
    total = len(steps)
    done = sum(1 for s in steps if s["module"] in completed)
    return {
        "key": path["key"],
        "name": path["name"],
        "summary": path["summary"],
        "steps": [{**s, "completed": s["module"] in completed} for s in steps],
        "total_guides": total,
        "completed_guides": done,
        "remaining_guides": total - done,
        "completion_percent": round(done / total * 100) if total else 0,
    }


# --------------------------------------------------------------------------- #
# Accessors                                                                    #
# --------------------------------------------------------------------------- #
def _index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["key"]: item for item in items}


_MODULE_INDEX = _index(MODULES)
_JOURNEY_INDEX = _index(JOURNEYS)
_PLAYBOOK_INDEX = _index(PLAYBOOKS)
_SUCCESS_INDEX = _index(SUCCESS_CENTER)


def get_module(key: str) -> dict[str, Any] | None:
    return _MODULE_INDEX.get(key)


def get_journey(key: str) -> dict[str, Any] | None:
    return _JOURNEY_INDEX.get(key)


def get_playbook(key: str) -> dict[str, Any] | None:
    return _PLAYBOOK_INDEX.get(key)


def get_success_guide(key: str) -> dict[str, Any] | None:
    return _SUCCESS_INDEX.get(key)


_PATH_INDEX = _index(LEARNING_PATHS)


def get_learning_path(key: str) -> dict[str, Any] | None:
    return _PATH_INDEX.get(key)
