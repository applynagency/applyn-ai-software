"""Sprint 56D.2 - Customer Success Documentation Rewrite: training-grade content.

Turns feature descriptions into first-time-customer training material. Provides,
per module: a 10+ step walkthrough (each step has an action, expected result and
"what happens internally" note), results interpretation, common mistakes,
troubleshooting, best practices, >=10 FAQs, and next steps.

This module is pure data with tiny self-contained helpers. It imports nothing
from ``customer_success_content`` (which imports *this* module and applies it),
so there is no circular import.

Tuples used below:
* step:           (action, expected_result, what_happens_internally)
* interpretation: (term, meaning)
* faq:            (question, answer)
* troubleshoot:   (problem, cause, resolution)
"""

from __future__ import annotations

from typing import Any

# Steps for existing modules (rewritten to >=10 detailed steps).
TRAINING_STEPS: dict[str, list[tuple[str, str, str]]] = {}
# >=10 FAQs per module.
TRAINING_FAQ: dict[str, list[tuple[str, str]]] = {}
# Results interpretation (term -> meaning).
TRAINING_INTERPRETATION: dict[str, list[tuple[str, str]]] = {}
# Common mistakes first-time customers make.
COMMON_MISTAKES: dict[str, list[str]] = {}
# What to do after finishing the guide.
NEXT_STEPS: dict[str, list[str]] = {}

# Full definitions for brand-new module guides.
NEW_MODULE_DEFS: list[dict[str, Any]] = []

TRAINING_STEPS["monitoring"] = [
    ("Open Operations -> Monitoring from the sidebar.",
     "The alert list loads with Severity, Service, Status, and Time columns.",
     "The view subscribes to the unified alert stream; provider collectors normalize and deduplicate raw signals before they are shown."),
    ("Read the Active Alerts and Unacknowledged counters at the top.",
     "You see how many alerts are firing and how many no responder has claimed.",
     "The header aggregates counts from the live alert index, grouped by status."),
    ("Sort by Severity so Critical and High alerts rise to the top.",
     "The table reorders with the most urgent alerts first.",
     "The severity router maps each provider's native severity onto Nexora's Critical/High/Medium/Low scale."),
    ("Type a service name into the search box.",
     "The list narrows to alerts attributed to that service in real time.",
     "Search matches against the service attribution computed during service mapping."),
    ("Click an alert row to open its detail panel.",
     "Alert metadata, affected service, provider, and first/last-seen timestamps appear.",
     "The detail view joins the raw alert payload with its mapped service owner."),
    ("Open the Notifications bell in the top bar.",
     "A popover lists the six most recent alerts from anywhere in the app.",
     "The bell reads the same alert index, limited to the newest six by timestamp."),
    ("Acknowledge an alert you are actively handling.",
     "Its status changes to acknowledged and it drops out of the Unacknowledged count.",
     "Acknowledgement writes a status transition that the header counters immediately reflect."),
    ("Spot a cluster of related alerts firing on one service within minutes.",
     "You can visually group repeated alerts pointing at the same root problem.",
     "Full correlation across the cluster is finalized later during incident investigation."),
    ("Escalate a recurring or critical alert into an incident.",
     "An AI-assisted incident investigation opens under Operations -> Incidents.",
     "Escalation seeds a new incident with the alert context and triggers the default SRE team."),
    ("Return to Monitoring and confirm the noise has dropped.",
     "The escalated alert is now linked to its incident and the stream is calmer.",
     "The alert is tagged with the incident id so it no longer counts toward the unacknowledged backlog."),
]
TRAINING_INTERPRETATION["monitoring"] = [
    ("Severity", "Critical/High/Medium/Low - drives ordering and on-call routing."),
    ("Status", "open, acknowledged, or resolved."),
    ("Active alerts", "Count of currently firing alerts across all connected providers."),
    ("Unacknowledged", "Alerts no responder has claimed yet - keep this near zero on shift."),
    ("Service attribution", "The owning service inferred for an alert; blank means the source is unmapped."),
    ("Alert age", "Time since first seen; old unacknowledged alerts are a triage smell."),
]
COMMON_MISTAKES["monitoring"] = [
    "Letting the Unacknowledged counter climb during a shift instead of triaging continuously.",
    "Leaving alert sources unmapped, so alerts arrive without a service owner.",
    "Treating every duplicate as a separate problem instead of escalating one incident.",
    "Filtering so narrowly that you miss a broader cluster on a related service.",
    "Silencing noisy alerts instead of escalating them so the root cause is captured.",
]
NEXT_STEPS["monitoring"] = [
    "Investigate the incident you escalated and walk its Timeline.",
    "Open Service Health for the affected service to see burn rate and budget.",
    "Tune monitoring rules and thresholds for sources that are too noisy.",
    "Confirm every alert source is mapped to a service for clean ownership.",
]
TRAINING_FAQ["monitoring"] = [
    ("Where do alerts come from?", "From the observability and cloud providers you connected during onboarding (Datadog, Prometheus, Grafana, cloud, etc.)."),
    ("Can I see alerts without opening the Monitoring page?", "Yes - the notifications bell in the top bar shows the latest six alerts on any page."),
    ("How do alerts become incidents?", "Escalate an alert to open an AI-assisted incident investigation that carries the alert context."),
    ("Why is an alert missing a service?", "Its source is not mapped yet; add the mapping in Service Mapping so attribution works."),
    ("Is the alert list real-time?", "It reflects the latest polled provider state and refreshes on load and on new signals."),
    ("What does acknowledging an alert do?", "It records that a responder has taken ownership and removes it from the Unacknowledged count."),
    ("Why do I see duplicate-looking alerts?", "Multiple providers can report the same condition; correlation is finalized during investigation."),
    ("Can I filter by more than one field?", "Yes - combine the search term with severity sorting to focus on what matters."),
    ("Do resolved alerts disappear?", "They move to resolved status and drop out of the active counts but remain searchable."),
    ("How is severity decided?", "Each provider's native severity is mapped onto Nexora's four-level scale by the severity router."),
]

TRAINING_STEPS["incidents"] = [
    ("Open Operations -> Incidents from the sidebar.",
     "The incident list loads with severity, status, source, and created date.",
     "The list reads the incident index for your organization, newest first."),
    ("Click an incident row to open its detail page.",
     "The incident summary header shows severity, status, confidence, and suspected provider.",
     "Opening the incident loads its investigation record produced by the AI team."),
    ("Read the root-cause summary and suspected trigger.",
     "A plain-language root cause and the most likely triggering change are shown.",
     "The RCA engine ranks candidate causes and surfaces the highest-confidence one."),
    ("Open the Timeline tab.",
     "A chronological list of events with provider and severity badges appears.",
     "The timeline engine merges alerts, metrics, and changes into one ordered narrative."),
    ("Open the Change Intelligence tab.",
     "Recent deployments, commits, releases, and authors are correlated to the incident.",
     "The change-correlation engine joins source-provider activity to the incident window."),
    ("Open the Recommendations tab.",
     "Ranked recommendations show confidence, risk, estimated recovery, and rationale.",
     "The recommendation engine scores candidate actions against the inferred root cause."),
    ("Open the Remediation Actions tab.",
     "Pending approvals, approved actions, and execution results are listed.",
     "The remediation engine prepares actions and enforces approval before any execution."),
    ("Approve a low-risk recommended action.",
     "The action moves from pending to approved and records who approved it.",
     "Approval writes an auditable decision and unlocks the action for execution."),
    ("Open the Postmortem tab and generate a postmortem.",
     "A draft postmortem is created with timeline, root cause, and action items.",
     "The postmortem generator synthesizes the investigation record into a shareable document."),
    ("Resolve the incident once mitigation is confirmed.",
     "The incident status changes to resolved and feeds your MTTR metrics.",
     "Resolution timestamps the lifecycle so reliability reports can compute MTTR and MTTA."),
]
TRAINING_INTERPRETATION["incidents"] = [
    ("Confidence score", "0-100 - how sure the AI is about the identified root cause."),
    ("Severity", "Business impact of the incident; drives routing and escalation."),
    ("Status", "open, investigating, mitigated, or resolved."),
    ("Suspected trigger", "The change or event most likely to have caused the incident."),
    ("Risk (on actions)", "How dangerous an action is to run; higher risk needs approval."),
    ("Estimated recovery", "Predicted time for a recommendation to restore service."),
]
COMMON_MISTAKES["incidents"] = [
    "Jumping to remediation before reading the Timeline and Change Intelligence.",
    "Approving high-risk actions without checking the blast radius.",
    "Ignoring the confidence score and treating every root cause as certain.",
    "Forgetting to generate a postmortem after resolving the incident.",
    "Resolving an incident before the mitigation is actually confirmed.",
]
NEXT_STEPS["incidents"] = [
    "Walk the Timeline guide to understand event reconstruction in depth.",
    "Review the Recommendations guide to learn how actions are ranked.",
    "Generate and export a postmortem for stakeholders.",
    "Check Service Health for the affected service to verify recovery.",
]
TRAINING_FAQ["incidents"] = [
    ("How does an incident get created?", "By escalating an alert from Monitoring, by a rule, or from a generated sample incident during onboarding."),
    ("What is the confidence score?", "A 0-100 measure of how certain the AI is about the identified root cause."),
    ("Can I investigate without an AI team?", "A default SRE team with investigator and RCA agents is provisioned automatically during onboarding."),
    ("Do recommended actions run automatically?", "No - actions require explicit approval before execution, and high-risk actions are flagged."),
    ("Where does change intelligence data come from?", "From the source providers you connected (GitHub/GitLab) correlated to the incident window."),
    ("Can I move through the whole workflow without leaving the page?", "Yes - Timeline, Change, Recommendations, Actions, and Postmortem are tabs on the incident detail page."),
    ("What if the root cause looks wrong?", "Use the Timeline and Change tabs to verify; you can still proceed with the recommendation you trust."),
    ("How is MTTR calculated?", "From the incident lifecycle timestamps captured between creation and resolution."),
    ("Are postmortems blameless?", "Yes - they focus on systemic causes and action items, not individuals."),
    ("Can I export an incident's postmortem?", "Yes - export to PDF, HTML, or Markdown from the Postmortem tab."),
]

TRAINING_STEPS["postmortems"] = [
    ("Open Reports -> Postmortems (or the Postmortem tab on an incident).",
     "A list of generated postmortems with date, version, and status appears.",
     "The list reads postmortem records linked to resolved incidents."),
    ("Select the incident you want to retrospect.",
     "The incident's investigation record is loaded as the postmortem source.",
     "The generator pulls the timeline, root cause, and actions from the incident."),
    ("Click Generate Postmortem.",
     "A structured draft is produced with summary, timeline, root cause, and impact.",
     "The timeline aggregator and root-cause synthesizer assemble the narrative automatically."),
    ("Review the incident summary section.",
     "A concise description of what happened and the customer impact is shown.",
     "The summary is synthesized from the incident metadata and severity."),
    ("Review the reconstructed timeline.",
     "Key events appear in order with timestamps and provider context.",
     "Timeline entries are deduplicated and ordered from alerts, metrics, and changes."),
    ("Review the root-cause and contributing factors.",
     "The primary cause plus contributing factors are clearly separated.",
     "The synthesizer distinguishes the trigger from systemic contributing factors."),
    ("Review the extracted action items.",
     "Concrete, assignable follow-ups are listed to prevent recurrence.",
     "The action-item extractor turns findings into trackable, owned tasks."),
    ("Edit or annotate any section as needed.",
     "Your edits are preserved in the postmortem version.",
     "Edits create a new version while keeping the generated baseline."),
    ("Export the postmortem to PDF, HTML, or Markdown.",
     "A downloadable document is produced in the chosen format.",
     "The document renderer formats the postmortem dependency-free for sharing."),
    ("Share the postmortem with stakeholders and track action items.",
     "Stakeholders receive a blameless retrospective with clear next steps.",
     "Action items remain linked to the incident so completion can be tracked."),
]
TRAINING_INTERPRETATION["postmortems"] = [
    ("Status", "draft, final, or published."),
    ("Version", "Each edit increments the version; the generated baseline is version 1."),
    ("Root cause", "The primary trigger of the incident."),
    ("Contributing factors", "Systemic conditions that made the incident worse or possible."),
    ("Action item", "An owned, trackable task to prevent recurrence."),
    ("Impact", "The measured customer or business effect of the incident."),
]
COMMON_MISTAKES["postmortems"] = [
    "Writing postmortems from memory instead of the reconstructed timeline.",
    "Listing a single root cause and ignoring contributing factors.",
    "Creating action items with no owner, so nothing gets done.",
    "Assigning blame to people rather than fixing systemic causes.",
    "Never exporting or sharing the postmortem with stakeholders.",
]
NEXT_STEPS["postmortems"] = [
    "Assign owners and due dates to every action item.",
    "Export the postmortem and circulate it to stakeholders.",
    "Feed recurring action items into Deployment Safety and Change Failure prevention.",
    "Review trends across postmortems in your executive reports.",
]
TRAINING_FAQ["postmortems"] = [
    ("Are postmortems generated automatically?", "Yes - a draft is generated from the incident's investigation record, then you can edit it."),
    ("Is the process blameless?", "Yes - it focuses on systemic causes and action items, not individuals."),
    ("What formats can I export?", "PDF, HTML, and Markdown."),
    ("Can I edit a generated postmortem?", "Yes - edits create a new version while preserving the generated baseline."),
    ("Where do action items go?", "They stay linked to the incident so completion can be tracked over time."),
    ("Do I need to write the timeline myself?", "No - the timeline is reconstructed automatically from the incident."),
    ("Can I retrospect any incident?", "Any incident with an investigation record can be turned into a postmortem."),
    ("What is the difference between root cause and contributing factors?", "Root cause is the trigger; contributing factors are systemic conditions that worsened it."),
    ("How do versions work?", "The generated draft is version 1; each save increments the version."),
    ("Can stakeholders view postmortems without an account?", "Export to PDF/HTML and share the file with anyone."),
]

TRAINING_STEPS["service-health"] = [
    ("Open Reliability -> Service Health and pick a service.",
     "The service's Health Overview tab loads with a health score.",
     "The health scorer combines metrics, SLOs, and recent incidents into one score."),
    ("Read the health score and its color band.",
     "A 0-100 score with a status color tells you the service's current state.",
     "The score is recomputed from the latest availability, burn rate, and incident signals."),
    ("Check availability and error-budget remaining.",
     "Current availability and the percentage of error budget left are shown.",
     "The SLO evaluator computes budget consumed versus the target window."),
    ("Inspect the burn rate.",
     "You see how fast the service is consuming its error budget.",
     "Burn rate compares recent failure rate against the budget's sustainable pace."),
    ("Open the SLOs tab.",
     "Each objective shows target, current value, compliance, and trend.",
     "The evaluator reads metrics against each objective's target and window."),
    ("Open the Dependencies tab.",
     "Upstream and downstream services plus blast radius are shown.",
     "The dependency mapper renders edges and computes blast radius from the graph."),
    ("Open the Incidents tab for this service.",
     "Incidents affecting the service are listed with status.",
     "The incident correlator filters incidents attributed to this service."),
    ("Open the Deployments tab.",
     "Recent deployment safety analyses for the service appear.",
     "Deployment records are joined to the service via change attribution."),
    ("Open the Capacity and Cost tabs.",
     "Forecasts and cost optimization findings for the service are shown.",
     "Capacity forecasts and cost analyses are filtered to this service."),
    ("Read the prediction for near-term health.",
     "A forward-looking risk indicator suggests whether health may degrade.",
     "The predictor projects current burn and saturation trends forward."),
]
TRAINING_INTERPRETATION["service-health"] = [
    ("Health score", "0-100 composite of availability, burn rate, budget, and incidents."),
    ("Availability", "Share of successful requests/uptime over the window."),
    ("Error budget", "Allowed failure under the SLO; remaining budget is what you can still spend."),
    ("Burn rate", "Speed of error-budget consumption; >1x means you will exhaust early."),
    ("Blast radius", "How many services are affected if this one fails."),
    ("Prediction", "Forward-looking risk that health will degrade soon."),
]
COMMON_MISTAKES["service-health"] = [
    "Reading the health score without checking burn rate and budget remaining.",
    "Ignoring downstream dependencies and underestimating blast radius.",
    "Tuning SLO targets before establishing a baseline.",
    "Treating a green score as permission to deploy risky changes.",
    "Not correlating recent incidents with the current health drop.",
]
NEXT_STEPS["service-health"] = [
    "Open the dependency graph to understand blast radius before changes.",
    "Review SLOs and adjust targets once you have a baseline.",
    "Run a Deployment Safety analysis before your next release.",
    "Check Capacity Planning if burn rate is rising due to saturation.",
]
TRAINING_FAQ["service-health"] = [
    ("What makes up the health score?", "A composite of availability, burn rate, error budget remaining, and recent incidents."),
    ("What is a good burn rate?", "At or below 1x is sustainable; above 1x means you will exhaust your budget early."),
    ("How is blast radius computed?", "From the dependency graph - the count and criticality of services affected if this one fails."),
    ("Can I see all signals for a service in one place?", "Yes - Health, SLOs, Dependencies, Incidents, Deployments, Capacity, and Cost are tabs on the service page."),
    ("What does the prediction mean?", "It projects current burn and saturation forward to flag likely near-term degradation."),
    ("Why is my budget remaining low but availability high?", "Short, severe spikes can burn budget quickly even if overall availability looks high."),
    ("How often does the score update?", "It recomputes from the latest polled metrics and incident state."),
    ("What if a service has no SLOs?", "Generate SLOs during onboarding or in the SLOs tab so the evaluator has targets."),
    ("Do incidents lower the score?", "Yes - recent and active incidents reduce the composite health score."),
    ("Can I compare services?", "Use the service list to scan scores, then drill into any service for detail."),
]

TRAINING_STEPS["deployment-safety"] = [
    ("Open Deployments -> Deployment Safety.",
     "The list of recent safety analyses with scores and statuses loads.",
     "Each analysis is produced by the safety engine for a specific change."),
    ("Start a new safety analysis for an upcoming change.",
     "A form collects the change, target service, and timing.",
     "The change analyzer parses the change and links it to the target service."),
    ("Submit the change details.",
     "A safety score and status (Safe / Caution / Block) are returned.",
     "The safety scorer weighs change size, history, and current service health."),
    ("Read the overall safety score.",
     "A 0-100 score summarizes how risky the deployment is right now.",
     "The score combines weighted risk factors into a single number."),
    ("Review the contributing risk factors.",
     "Factors like change size, recent failures, and SLO burn are listed.",
     "The history analyzer and service-health reader supply each factor."),
    ("Check current service health for the target.",
     "The target service's health and burn rate are shown inline.",
     "The reader pulls live health so timing risk is reflected."),
    ("Review recommended guardrails.",
     "Suggestions such as canary, off-peak timing, or feature flags appear.",
     "Guardrails are selected based on which risk factors dominate the score."),
    ("Decide go / hold based on the status.",
     "A clear recommendation tells you whether to proceed.",
     "The decision threshold maps the score onto Safe/Caution/Block."),
    ("If blocked, mitigate the top risk factor and re-run.",
     "A new analysis reflects your mitigation and an updated score.",
     "Re-running recomputes the score with the changed inputs."),
    ("Proceed with the deployment and record the outcome.",
     "The deployment and its result are captured for future analyses.",
     "Outcomes feed the history analyzer to improve future scoring."),
]
TRAINING_INTERPRETATION["deployment-safety"] = [
    ("Safety score", "0-100 - higher is safer to deploy now."),
    ("Status", "Safe, Caution, or Block based on the score thresholds."),
    ("Risk factor", "A weighted contributor such as change size or SLO burn."),
    ("Guardrail", "A recommended mitigation like canary or off-peak timing."),
    ("Change size", "How large the change is; larger changes carry more risk."),
    ("Timing risk", "Risk added by deploying while the service is already strained."),
]
COMMON_MISTAKES["deployment-safety"] = [
    "Deploying during an active incident or high SLO burn.",
    "Ignoring a Caution status because the change feels small.",
    "Shipping a large change without canary or feature flags.",
    "Not re-running the analysis after mitigating a risk factor.",
    "Skipping outcome recording, which weakens future scoring.",
]
NEXT_STEPS["deployment-safety"] = [
    "Check Change Failure Prediction for the same change.",
    "Apply recommended guardrails (canary, off-peak, flags) before shipping.",
    "Record the deployment outcome to improve future analyses.",
    "Review Service Health after deploy to confirm stability.",
]
TRAINING_FAQ["deployment-safety"] = [
    ("What does the safety score mean?", "A 0-100 measure of how risky it is to deploy this change right now; higher is safer."),
    ("What are the statuses?", "Safe, Caution, and Block, mapped from the score thresholds."),
    ("Which factors affect the score?", "Change size, recent failure history, current service health, and SLO burn rate."),
    ("Does a Block stop my pipeline?", "It is a strong recommendation to hold; you mitigate the top factor and re-run."),
    ("How do guardrails help?", "They reduce blast radius and detection time - canary, off-peak timing, and feature flags."),
    ("Does timing matter?", "Yes - deploying while a service is strained adds timing risk."),
    ("How is history used?", "Past deployment outcomes train the scorer to weigh risk factors."),
    ("Can I analyze any change?", "Yes - provide the change and target service to get a score."),
    ("What if service health is unknown?", "Connect monitoring and SLOs so the reader can supply live health."),
    ("Should I record outcomes?", "Yes - recorded outcomes improve the accuracy of future analyses."),
]

TRAINING_STEPS["capacity"] = [
    ("Open Infrastructure -> Capacity Planning.",
     "A list of capacity forecasts per service or resource loads.",
     "The forecaster reads historical utilization metrics for each resource."),
    ("Select a resource or service to forecast.",
     "Its utilization trend and projected curve are shown.",
     "The forecaster fits a trend to recent usage and projects it forward."),
    ("Read the current utilization.",
     "You see how much of the resource is in use right now.",
     "Utilization is computed from the latest collected metrics."),
    ("Read the projected exhaustion date.",
     "An estimated date when the resource runs out of headroom appears.",
     "The exhaustion estimator extrapolates the trend to the saturation threshold."),
    ("Check the risk tier.",
     "A tier (Low/Medium/High/Critical) summarizes urgency.",
     "The risk classifier maps time-to-exhaustion onto a tier."),
    ("Adjust the forecast horizon.",
     "The projection updates for the chosen window (e.g., 30/60/90 days).",
     "Changing the horizon re-runs the projection over the new window."),
    ("Compare multiple resources.",
     "You can see which resources will saturate first.",
     "Forecasts are ranked by time-to-exhaustion and risk tier."),
    ("Review the recommended action.",
     "Guidance such as scale-up, rebalance, or optimize is shown.",
     "Recommendations are selected from the dominant saturation driver."),
    ("Plan the capacity change.",
     "You schedule scaling ahead of the exhaustion date.",
     "Planning uses the exhaustion date to set a safe lead time."),
    ("Re-check the forecast after changes land.",
     "Utilization flattens and the exhaustion date moves out.",
     "New metrics shift the projection, confirming the change worked."),
]
TRAINING_INTERPRETATION["capacity"] = [
    ("Utilization", "Current share of a resource in use."),
    ("Exhaustion date", "Projected date the resource saturates if the trend holds."),
    ("Risk tier", "Low/Medium/High/Critical urgency based on time-to-exhaustion."),
    ("Forecast horizon", "The window over which the projection is made."),
    ("Headroom", "Remaining capacity before saturation."),
    ("Saturation driver", "The trend (growth, leak, seasonality) pushing toward exhaustion."),
]
COMMON_MISTAKES["capacity"] = [
    "Reacting only after a resource is already saturated.",
    "Forecasting a single resource and missing the one that saturates first.",
    "Using too short a horizon to catch slow growth.",
    "Scaling reactively instead of planning ahead of the exhaustion date.",
    "Ignoring the saturation driver and scaling the wrong dimension.",
]
NEXT_STEPS["capacity"] = [
    "Schedule scaling well before the exhaustion date.",
    "Cross-check Cost Optimization so scaling does not waste spend.",
    "Watch Service Health burn rate for capacity-driven degradation.",
    "Re-run the forecast after changes to confirm headroom improved.",
]
TRAINING_FAQ["capacity"] = [
    ("What is the exhaustion date?", "The projected date a resource saturates if the current usage trend continues."),
    ("How is the forecast made?", "By fitting a trend to historical utilization and projecting it over your chosen horizon."),
    ("What does the risk tier mean?", "It maps time-to-exhaustion onto Low/Medium/High/Critical urgency."),
    ("Can I change the horizon?", "Yes - choose windows like 30/60/90 days and the projection updates."),
    ("Which resource should I fix first?", "The one with the soonest exhaustion date and highest risk tier."),
    ("Does capacity relate to cost?", "Yes - overscaling wastes spend, so cross-check Cost Optimization."),
    ("What is a saturation driver?", "The underlying trend (growth, leak, seasonality) pushing toward exhaustion."),
    ("How do I confirm a fix worked?", "Re-run the forecast; utilization should flatten and the exhaustion date should move out."),
    ("Can I forecast many resources at once?", "Yes - the list ranks resources by time-to-exhaustion."),
    ("What if there is not enough history?", "Connect metrics and let data accumulate; projections improve with more history."),
]

TRAINING_STEPS["cost"] = [
    ("Open Infrastructure -> Cost Optimization.",
     "A list of cost analyses and a savings opportunity total load.",
     "The cost engine ingests billing and usage data per resource."),
    ("Read the total estimated savings opportunity.",
     "A headline figure shows how much you could save.",
     "Savings are summed across all detected waste recommendations."),
    ("Open a specific cost analysis.",
     "Spend breakdown and waste findings for that scope appear.",
     "The waste detector flags idle, oversized, and orphaned resources."),
    ("Review the top recommendations.",
     "Ranked actions show estimated savings and effort.",
     "The recommendation engine scores actions by savings per unit of effort."),
    ("Inspect a single recommendation's rationale.",
     "Why the resource is wasteful and the suggested fix are explained.",
     "Each recommendation cites the usage signal that triggered it."),
    ("Filter findings by service or resource type.",
     "The list narrows to the scope you care about.",
     "Findings are tagged by service and resource type for filtering."),
    ("Estimate the impact of applying a recommendation.",
     "Projected monthly and annual savings are shown.",
     "The savings estimator annualizes the per-resource delta."),
    ("Prioritize quick wins versus structural changes.",
     "You can separate low-effort, high-savings actions from larger ones.",
     "Effort and savings scores let you sort for quick wins first."),
    ("Hand off recommendations to the owning team.",
     "Owners receive the rationale and expected savings.",
     "Findings stay attributed to a service so the right team acts."),
    ("Re-run the analysis after changes.",
     "Applied savings drop out and the opportunity total updates.",
     "New billing/usage data refreshes waste detection and totals."),
]
TRAINING_INTERPRETATION["cost"] = [
    ("Savings opportunity", "Total estimated spend you could remove without impact."),
    ("Waste", "Idle, oversized, or orphaned resources costing money for no value."),
    ("Estimated savings", "Projected monthly/annual reduction from a recommendation."),
    ("Effort", "Relative work to apply a recommendation."),
    ("Quick win", "A low-effort, high-savings action to do first."),
    ("Attribution", "The service/team that owns the wasteful resource."),
]
COMMON_MISTAKES["cost"] = [
    "Chasing large structural changes before banking quick wins.",
    "Applying recommendations without notifying the owning team.",
    "Cutting capacity so aggressively that you create saturation risk.",
    "Ignoring orphaned resources because they look small individually.",
    "Never re-running the analysis, so the savings total goes stale.",
]
NEXT_STEPS["cost"] = [
    "Apply the highest savings-per-effort quick wins first.",
    "Cross-check Capacity Planning so cuts do not cause saturation.",
    "Route findings to owning teams with rationale attached.",
    "Re-run the analysis monthly and track realized savings.",
]
TRAINING_FAQ["cost"] = [
    ("Where does cost data come from?", "From the billing and usage data of your connected providers."),
    ("What counts as waste?", "Idle, oversized, or orphaned resources that cost money without delivering value."),
    ("How are recommendations ranked?", "By estimated savings relative to the effort required to apply them."),
    ("Are savings monthly or annual?", "Both - the estimator shows projected monthly and annualized savings."),
    ("Will cost cuts hurt reliability?", "They can if overdone - cross-check Capacity Planning before cutting."),
    ("Can I filter by team or service?", "Yes - findings are tagged by service and resource type."),
    ("What is a quick win?", "A low-effort, high-savings action you should do first."),
    ("How do I track realized savings?", "Re-run the analysis; applied items drop out and the total updates."),
    ("Who should act on a finding?", "The team that owns the attributed service or resource."),
    ("Does Nexora change my resources?", "No - it recommends; your team applies the changes."),
]

TRAINING_STEPS["change-failure"] = [
    ("Open Deployments -> Change Failure Prediction.",
     "A list of changes with failure probabilities and risk levels loads.",
     "The model scores each change from historical change-failure patterns."),
    ("Select a change to inspect.",
     "Its failure probability and contributing factors appear.",
     "The risk scorer breaks the probability into weighted factors."),
    ("Read the failure probability.",
     "A percentage estimates the chance this change causes an incident.",
     "Probability is produced by the change-history model for this change profile."),
    ("Check the risk level.",
     "A Low/Medium/High/Critical label summarizes the probability.",
     "Thresholds map probability onto the risk level."),
    ("Review the contributing factors.",
     "Factors such as rollback frequency, success rate, and active incidents are listed.",
     "Each factor contributes capped points to the overall score."),
    ("Inspect the predicted blast radius.",
     "The services likely affected if the change fails are shown.",
     "Blast radius is computed from the dependency graph for the target."),
    ("Compare against recent similar changes.",
     "You can see how comparable changes fared.",
     "The model surfaces nearest-neighbor change outcomes."),
    ("Apply mitigations to lower the risk.",
     "Splitting the change or adding tests reduces predicted probability.",
     "Re-scoring reflects the reduced change size and improved signals."),
    ("Coordinate timing with deployment safety.",
     "You align the change with a safe deployment window.",
     "Change-failure risk and deployment-safety timing are evaluated together."),
    ("Ship and record the outcome.",
     "The actual result feeds back into the model.",
     "Recorded outcomes retrain the model to improve future predictions."),
]
TRAINING_INTERPRETATION["change-failure"] = [
    ("Failure probability", "Estimated chance (0-100%) the change causes an incident."),
    ("Risk level", "Low/Medium/High/Critical mapped from the probability."),
    ("Rollback frequency", "How often similar changes were rolled back."),
    ("Deployment success rate", "Share of comparable deployments that succeeded."),
    ("Active incidents", "Open incidents that raise risk if you deploy now."),
    ("Blast radius", "Services likely affected if the change fails."),
]
COMMON_MISTAKES["change-failure"] = [
    "Treating a low probability as a guarantee of success.",
    "Ignoring active incidents that inflate deployment risk.",
    "Shipping one huge change instead of several small ones.",
    "Not recording outcomes, so the model never improves.",
    "Evaluating change-failure risk without checking deployment timing.",
]
NEXT_STEPS["change-failure"] = [
    "Run a Deployment Safety analysis for the same change.",
    "Split high-risk changes into smaller, safer increments.",
    "Resolve active incidents before deploying risky changes.",
    "Record the deployment outcome to retrain the model.",
]
TRAINING_FAQ["change-failure"] = [
    ("What is failure probability?", "An estimated 0-100% chance that a change causes an incident."),
    ("How is it predicted?", "A model trained on historical change outcomes scores the change profile."),
    ("What raises the risk?", "Large change size, high rollback frequency, low success rate, and active incidents."),
    ("What is blast radius here?", "The set of services likely affected if the change fails."),
    ("Can I lower a change's risk?", "Yes - split it, add tests, or deploy when no incidents are open, then re-score."),
    ("How does this differ from Deployment Safety?", "This predicts failure likelihood; Deployment Safety judges whether it is safe to deploy now."),
    ("Do active incidents matter?", "Yes - they add risk and should usually be resolved first."),
    ("Why record outcomes?", "Outcomes retrain the model so predictions get more accurate."),
    ("Is the percentage exact?", "It is an estimate; use it as a relative risk signal, not a certainty."),
    ("Can I compare to past changes?", "Yes - the model surfaces how similar recent changes fared."),
]

NEW_MODULE_DEFS.append({
    "key": "timeline",
    "name": "Incident Timeline",
    "category": "incident",
    "route": "/incidents/:id",
    "nav_path": ["Sidebar", "Operations", "Incidents", "Incident", "Timeline"],
    "overview": {
        "what": "A chronological, provider-aware reconstruction of everything that happened before and during an incident.",
        "why": "It removes the manual work of stitching together logs, metrics, alerts, and deploys so you can see cause and effect at a glance.",
        "business_value": "Faster root-cause confirmation and a defensible, shareable record of the incident.",
        "who": "On-call engineers, incident commanders, and SREs investigating an incident.",
        "when": "As the first step of any incident investigation and when writing the postmortem.",
    },
    "prerequisites": [
        "An incident that has been investigated by the AI team.",
        "At least one observability provider connected so events have signal.",
        "A source provider (GitHub/GitLab) connected so deploys appear on the timeline.",
    ],
    "steps": [
        ("Open an incident and select the Timeline tab.",
         "A vertical, time-ordered list of events appears.",
         "The timeline engine merges alerts, metrics, and changes into one ordered narrative."),
        ("Read the earliest events at the top.",
         "You see the first signals that preceded the incident.",
         "Events are sorted ascending by timestamp from the incident window."),
        ("Identify provider badges on each event.",
         "Each event shows which provider (cloud, observability, source) produced it.",
         "Badges are derived from the event source recorded during ingestion."),
        ("Spot the suspected trigger event.",
         "The most likely triggering change or signal is highlighted.",
         "The change-correlation engine flags the event closest to the onset with the highest weight."),
        ("Read the confidence score for the trigger.",
         "A 0-100 score shows how sure the system is about the trigger.",
         "Confidence reflects how cleanly the trigger correlates with the onset."),
        ("Expand a metric event to see the spike.",
         "The metric and its anomalous window are shown in context.",
         "Metric events carry the series and the detected anomaly boundaries."),
        ("Expand a deployment event to see the change.",
         "Commit, author, version, and service for the deploy appear.",
         "Deploy events are joined from the connected source provider."),
        ("Trace the sequence from trigger to impact.",
         "You can follow the causal chain from change to alert to impact.",
         "Ordering plus correlation links each downstream effect to its cause."),
        ("Filter the timeline by severity or provider.",
         "The list narrows to the events you care about.",
         "Filters apply over the event index without losing ordering."),
        ("Use the timeline to seed the postmortem.",
         "The reconstructed timeline is reused in the postmortem document.",
         "The postmortem generator reads the same timeline so the record stays consistent."),
    ],
    "interpretation": [
        ("Event", "A single signal: an alert, metric anomaly, or change."),
        ("Provider badge", "The system that produced the event."),
        ("Suspected trigger", "The event most likely to have started the incident."),
        ("Confidence score", "0-100 certainty that the trigger is correct."),
        ("Onset", "The moment impact began, used as the correlation anchor."),
        ("Causal chain", "The ordered path from trigger to customer impact."),
    ],
    "example": {
        "scenario": "Checkout latency spikes ten minutes after a deploy.",
        "walkthrough": "The timeline shows a 14:02 deploy to checkout, a 14:05 latency anomaly, and 14:07 alerts, with the deploy flagged as the suspected trigger at 88% confidence.",
        "outcome": "The responder confirms the deploy as root cause in under two minutes and rolls it back.",
    },
    "troubleshooting": [
        ("Deploys are missing from the timeline.", "No source provider is connected.", "Connect GitHub/GitLab so change events appear."),
        ("The timeline looks empty.", "No observability provider feeds this service.", "Connect monitoring and map the service so events have signal."),
        ("The trigger seems wrong.", "Multiple changes landed in the same window.", "Use Change Intelligence to compare candidates and pick the right one."),
    ],
    "best_practices": [
        "Always read the timeline before approving remediation.",
        "Connect a source provider so deploys appear alongside alerts.",
        "Use provider filters to cut noise during a busy incident.",
        "Reuse the timeline in the postmortem for a consistent record.",
    ],
    "faq": [
        ("What is on the timeline?", "Alerts, metric anomalies, and changes (deploys/commits) ordered by time."),
        ("How is the trigger chosen?", "The change-correlation engine flags the event nearest the onset with the strongest weight."),
        ("What does confidence mean?", "How cleanly the suspected trigger correlates with the incident onset."),
        ("Why are deploys missing?", "No source provider is connected; connect GitHub/GitLab."),
        ("Can I filter the timeline?", "Yes - by severity and provider, while keeping chronological order."),
        ("Is the timeline reused later?", "Yes - the postmortem uses the same reconstructed timeline."),
        ("Does the timeline update live?", "It reflects ingested events for the incident window."),
        ("What is the onset?", "The moment customer impact began; it anchors correlation."),
        ("Can I see metric detail?", "Yes - expand a metric event to view the anomalous window."),
        ("What if two changes are suspect?", "Open Change Intelligence to compare candidates side by side."),
    ],
    "reading_time_minutes": 5,
    "difficulty": "Beginner",
    "role": "On-call Engineer / SRE",
    "business_value": "Faster root-cause confirmation",
    "expected_outcomes": ["A clear causal chain", "A confirmed trigger", "A reusable timeline for the postmortem"],
    "related": ["incidents", "recommendations", "postmortems"],
    "common_mistakes": [
        "Approving remediation before reading the timeline.",
        "Ignoring provider badges and missing the deploy that caused the incident.",
        "Trusting the suspected trigger without checking competing changes.",
        "Investigating without a source provider, so deploys are invisible.",
        "Rewriting the timeline by hand in the postmortem instead of reusing it.",
    ],
    "next_steps": [
        "Open Change Intelligence to confirm the suspected change.",
        "Move to Recommendations to choose a remediation.",
        "Generate the postmortem using the reconstructed timeline.",
    ],
    "arch": "graph TD\n  Alerts --> TimelineEngine\n  Metrics --> TimelineEngine\n  Changes --> TimelineEngine\n  TimelineEngine --> Ordered[Ordered Events]\n  Ordered --> Trigger[Suspected Trigger]",
    "internal": {"customer_action": "Open the Timeline tab", "engines": ["Event Ingestion", "Timeline Engine", "Change Correlation Engine", "Confidence Scorer"], "outputs": ["Ordered events", "Suspected trigger", "Confidence score"]},
    "expected_screens": ["Timeline tab", "Provider badges", "Suspected trigger highlight", "Confidence score"],
})

NEW_MODULE_DEFS.append({
    "key": "recommendations",
    "name": "Incident Recommendations",
    "category": "incident",
    "route": "/incidents/:id",
    "nav_path": ["Sidebar", "Operations", "Incidents", "Incident", "Recommendations"],
    "overview": {
        "what": "Ranked, AI-generated remediation options for an incident, each with confidence, risk, estimated recovery, and rationale.",
        "why": "It tells you what to do next - and why - so you act decisively instead of guessing under pressure.",
        "business_value": "Lower MTTR and more consistent, defensible response decisions.",
        "who": "On-call engineers and incident commanders deciding how to respond.",
        "when": "After the root cause is identified and before executing remediation.",
    },
    "prerequisites": [
        "An incident with an identified or suspected root cause.",
        "A default AI team (auto-provisioned during onboarding).",
    ],
    "steps": [
        ("Open an incident and select the Recommendations tab.",
         "A ranked list of recommended actions appears.",
         "The recommendation engine scores candidate actions against the inferred root cause."),
        ("Read the top recommendation first.",
         "The highest-ranked action is shown with a confidence score.",
         "Ranking sorts by a blend of confidence and expected recovery."),
        ("Check each recommendation's confidence.",
         "A 0-100 score shows how strongly the AI backs the action.",
         "Confidence reflects how well the action fits the root cause and history."),
        ("Check each recommendation's risk.",
         "A risk level tells you how dangerous the action is to run.",
         "Risk is derived from blast radius and reversibility of the action."),
        ("Read the estimated recovery time.",
         "You see how long the action should take to restore service.",
         "Recovery estimates come from comparable past remediations."),
        ("Read the rationale.",
         "A plain-language explanation of why the action is recommended appears.",
         "The rationale cites the root cause and supporting signals."),
        ("Compare the top alternatives.",
         "You weigh trade-offs between speed and risk across options.",
         "Alternatives are scored consistently so they are comparable."),
        ("Pick the action that best fits your risk tolerance.",
         "You select a recommendation to act on.",
         "Selection links the chosen recommendation to the incident record."),
        ("Hand the chosen action to Remediation.",
         "The action moves to the Remediation tab for approval.",
         "The recommendation becomes a proposed remediation action pending approval."),
        ("Record which recommendation you chose.",
         "The decision is captured for the postmortem and learning.",
         "The choice feeds back to improve future ranking."),
    ],
    "interpretation": [
        ("Confidence", "0-100 - how strongly the AI backs the recommendation."),
        ("Risk", "How dangerous the action is to execute (blast radius, reversibility)."),
        ("Estimated recovery", "Predicted time for the action to restore service."),
        ("Rationale", "Why the action is recommended, tied to the root cause."),
        ("Rank", "Position in the list, blending confidence and recovery."),
        ("Reversibility", "Whether the action can be safely undone."),
    ],
    "example": {
        "scenario": "A bad deploy caused a checkout outage.",
        "walkthrough": "The top recommendation is 'roll back checkout to v1.42' at 91% confidence, Low risk, ~4 min recovery, because the v1.43 deploy correlates with the onset.",
        "outcome": "The commander approves the rollback and service recovers in five minutes.",
    },
    "troubleshooting": [
        ("No recommendations appear.", "The root cause is not yet identified.", "Complete the timeline/RCA so the engine has a target."),
        ("Confidence is low across the board.", "Signals are sparse or conflicting.", "Connect more providers or verify the root cause before acting."),
        ("A recommendation seems risky.", "It has a large blast radius.", "Prefer a reversible, lower-risk option even if recovery is slightly slower."),
    ],
    "best_practices": [
        "Balance confidence and risk, not just speed.",
        "Prefer reversible actions when uncertainty is high.",
        "Record the chosen recommendation for the postmortem.",
        "Re-check recommendations if new evidence changes the root cause.",
    ],
    "faq": [
        ("How are recommendations ranked?", "By a blend of confidence and estimated recovery time."),
        ("What does risk mean?", "How dangerous the action is, based on blast radius and reversibility."),
        ("Do recommendations execute themselves?", "No - they move to Remediation and require approval first."),
        ("Why is confidence low?", "Signals may be sparse or conflicting; verify the root cause or connect more providers."),
        ("Can I pick a lower-ranked option?", "Yes - choose the action that best fits your risk tolerance."),
        ("Where does recovery time come from?", "Estimates from comparable past remediations."),
        ("What is rationale?", "A plain-language explanation tying the action to the root cause."),
        ("Does my choice matter later?", "Yes - it is recorded for the postmortem and improves future ranking."),
        ("What if no recommendations show?", "Finish the timeline/RCA so the engine has a root cause to target."),
        ("Can I compare options?", "Yes - all options are scored consistently for easy comparison."),
    ],
    "reading_time_minutes": 5,
    "difficulty": "Beginner",
    "role": "Incident Commander / SRE",
    "business_value": "Decisive, lower-MTTR response",
    "expected_outcomes": ["A ranked set of actions", "A chosen remediation", "A recorded decision"],
    "related": ["incidents", "remediation", "timeline"],
    "common_mistakes": [
        "Picking the fastest action without weighing its risk.",
        "Acting on low-confidence recommendations without verifying the cause.",
        "Choosing an irreversible action when uncertainty is high.",
        "Not recording which recommendation was chosen.",
        "Ignoring new evidence that changes the root cause.",
    ],
    "next_steps": [
        "Send the chosen action to Remediation for approval.",
        "Confirm recovery in Service Health after the action runs.",
        "Capture the decision in the postmortem.",
    ],
    "arch": "graph TD\n  RootCause --> RecEngine\n  History --> RecEngine\n  RecEngine --> Ranked[Ranked Recommendations]\n  Ranked --> Remediation",
    "internal": {"customer_action": "Open the Recommendations tab", "engines": ["Recommendation Engine", "Risk Scorer", "Recovery Estimator"], "outputs": ["Ranked recommendations", "Confidence", "Risk", "Estimated recovery"]},
    "expected_screens": ["Recommendations tab", "Confidence and risk badges", "Rationale panel"],
})

NEW_MODULE_DEFS.append({
    "key": "remediation",
    "name": "Incident Remediation",
    "category": "incident",
    "route": "/incidents/:id",
    "nav_path": ["Sidebar", "Operations", "Incidents", "Incident", "Remediation"],
    "overview": {
        "what": "The approval-gated execution surface for incident actions, showing pending approvals, approved actions, and execution results.",
        "why": "It lets you act safely with humans in the loop, capturing who approved what and what happened.",
        "business_value": "Safe, auditable response with no surprise automated changes.",
        "who": "Incident commanders and approvers responsible for executing changes.",
        "when": "After choosing a recommendation and before/while applying the fix.",
    },
    "prerequisites": [
        "A chosen recommendation promoted to a remediation action.",
        "Approval permission for the action being executed.",
    ],
    "steps": [
        ("Open an incident and select the Remediation Actions tab.",
         "Pending approvals, approved actions, and results are listed.",
         "The remediation engine prepares actions and enforces approval before execution."),
        ("Review a pending action's details.",
         "The action, target, risk, and rationale are shown.",
         "Pending actions carry the recommendation context they came from."),
        ("Check the action's risk and blast radius.",
         "You see how dangerous and far-reaching the action is.",
         "Risk and blast radius are inherited from the recommendation scoring."),
        ("Confirm the bind/target is correct.",
         "The exact service/resource the action affects is shown.",
         "Binding ties the action to a specific target to prevent mistakes."),
        ("Approve a low-risk action.",
         "The action moves from pending to approved with your identity recorded.",
         "Approval writes an auditable decision and unlocks execution."),
        ("Hold or reject a high-risk action.",
         "The action is not executed and the reason is recorded.",
         "Rejection records a decision and keeps the action out of execution."),
        ("Execute the approved action.",
         "Execution begins and a result status is tracked.",
         "The engine runs the bound action and streams status back."),
        ("Read the execution result.",
         "Success or failure with detail is shown.",
         "Results are captured against the action for audit and learning."),
        ("Verify recovery in Service Health.",
         "You confirm the action actually restored the service.",
         "Service-health signals confirm the fix beyond the action's own status."),
        ("Record the outcome for the postmortem.",
         "The remediation and its result are linked to the incident.",
         "Outcomes feed the postmortem and improve future recommendations."),
    ],
    "interpretation": [
        ("Pending approval", "An action waiting for a human to approve before it can run."),
        ("Approved", "An action a responder authorized; ready to execute."),
        ("Execution result", "Success or failure of running the action."),
        ("Bind status", "Whether the action is correctly tied to its target."),
        ("Risk", "How dangerous the action is to execute."),
        ("Blast radius", "Services affected if the action goes wrong."),
    ],
    "example": {
        "scenario": "A rollback was recommended for the checkout service.",
        "walkthrough": "The commander reviews the bound rollback action (Low risk, target: checkout), approves it, executes, and sees a success result.",
        "outcome": "Service Health turns green within minutes and the outcome is recorded in the postmortem.",
    },
    "troubleshooting": [
        ("The action will not execute.", "It is still pending approval.", "Approve the action first; high-risk actions need an authorized approver."),
        ("Bind status is invalid.", "The target service/resource is ambiguous.", "Confirm the correct target before approving."),
        ("Execution failed.", "The environment changed since the recommendation.", "Re-investigate, pick an updated recommendation, and retry."),
    ],
    "best_practices": [
        "Always confirm bind/target before approving.",
        "Require approval for high-risk actions - never bypass the gate.",
        "Verify recovery in Service Health, not just the action status.",
        "Record every outcome for the postmortem and learning loop.",
    ],
    "faq": [
        ("Do actions run automatically?", "No - they require explicit approval, and high-risk actions are flagged."),
        ("Who can approve?", "Users with approval permission for the action."),
        ("What is bind status?", "Whether the action is correctly tied to its intended target."),
        ("What happens after execution?", "A result status (success/failure) is captured against the action."),
        ("How do I know it worked?", "Verify recovery in Service Health, not just the action status."),
        ("Can I reject an action?", "Yes - hold or reject it and the reason is recorded."),
        ("Where do actions come from?", "From recommendations you promoted on the Recommendations tab."),
        ("Is execution auditable?", "Yes - approver identity and results are recorded."),
        ("What if execution fails?", "Re-investigate, choose an updated recommendation, and retry."),
        ("Do outcomes matter later?", "Yes - they feed the postmortem and improve future recommendations."),
    ],
    "reading_time_minutes": 5,
    "difficulty": "Intermediate",
    "role": "Incident Commander / Approver",
    "business_value": "Safe, auditable remediation",
    "expected_outcomes": ["Approved actions", "Captured execution results", "A recorded outcome"],
    "related": ["incidents", "recommendations", "postmortems"],
    "common_mistakes": [
        "Approving an action without confirming the bind/target.",
        "Bypassing approval for high-risk actions.",
        "Trusting the action status instead of verifying recovery.",
        "Not recording the outcome for the postmortem.",
        "Retrying a failed action without re-investigating.",
    ],
    "next_steps": [
        "Confirm recovery in Service Health.",
        "Generate the postmortem with the remediation outcome.",
        "Feed recurring fixes into Deployment Safety guardrails.",
    ],
    "arch": "graph TD\n  Recommendation --> RemediationEngine\n  RemediationEngine --> Pending[Pending Approval]\n  Pending --> Approved\n  Approved --> Execution\n  Execution --> Result",
    "internal": {"customer_action": "Approve and execute an action", "engines": ["Remediation Engine", "Approval Gate", "Executor", "Result Recorder"], "outputs": ["Approval decision", "Execution result", "Recorded outcome"]},
    "expected_screens": ["Remediation Actions tab", "Pending approvals", "Execution results", "Bind status"],
})

NEW_MODULE_DEFS.append({
    "key": "discovery",
    "name": "Infrastructure Discovery",
    "category": "onboarding",
    "route": "/discovery",
    "nav_path": ["Sidebar", "Infrastructure", "Discovery"],
    "overview": {
        "what": "Automatic discovery of your infrastructure across connected providers - assets, services, and the relationships between them.",
        "why": "It builds an accurate, current map of what you run so every other feature (SLOs, incidents, capacity) has ground truth.",
        "business_value": "An always-current inventory with zero manual cataloging.",
        "who": "Platform admins and SREs setting up or maintaining an environment.",
        "when": "During onboarding and whenever infrastructure changes or a new provider is added.",
    },
    "prerequisites": [
        "At least one provider connected with read-only access.",
        "Provider credentials validated (validated read-only, never stored).",
    ],
    "steps": [
        ("Open Infrastructure -> Discovery.",
         "The discovery view shows connected providers and a Run control.",
         "The view reads which providers are connected and their last scan time."),
        ("Click Run Discovery.",
         "A scan starts and progress is shown per provider.",
         "The discovery engine enumerates resources using read-only provider APIs."),
        ("Watch the asset counts populate.",
         "Counts of discovered assets per provider appear.",
         "Each provider's resources are normalized into a common asset model."),
        ("Review the discovered assets list.",
         "Raw resources (instances, clusters, repos, etc.) are listed.",
         "Assets are deduplicated and tagged with provider and type."),
        ("Open the service mapping summary.",
         "Assets are grouped into logical services.",
         "The service mapper clusters related assets into services."),
        ("Review the inferred dependencies.",
         "Edges between services are shown with direction.",
         "The dependency mapper infers edges from network, naming, and traffic signals."),
        ("Spot any unmapped or orphaned assets.",
         "Assets without a service are highlighted.",
         "Unmapped assets are flagged so attribution can be completed."),
        ("Map an orphaned asset to a service.",
         "The asset gains an owner and appears in that service.",
         "Manual mapping updates the service model used everywhere."),
        ("Confirm coverage looks complete.",
         "Asset, service, and dependency counts match expectations.",
         "Coverage metrics summarize how much of your estate is mapped."),
        ("Re-run discovery after infrastructure changes.",
         "New assets appear and stale ones are reconciled.",
         "Re-scanning reconciles the live estate against the stored map."),
    ],
    "interpretation": [
        ("Asset", "A single raw infrastructure resource found by a provider."),
        ("Service", "A logical grouping of related assets."),
        ("Dependency edge", "A directed relationship between two services."),
        ("Orphaned asset", "A discovered asset not yet attributed to a service."),
        ("Coverage", "Share of assets that are mapped into services."),
        ("Reconciliation", "Updating the map to match the live estate on re-scan."),
    ],
    "example": {
        "scenario": "A team connects AWS and Kubernetes for the first time.",
        "walkthrough": "Discovery finds 142 assets, maps 18 services, infers 31 dependency edges, and flags 4 orphaned assets the team quickly maps.",
        "outcome": "Within minutes the team has an accurate map powering SLOs, incidents, and capacity.",
    },
    "troubleshooting": [
        ("Discovery returns 0 assets.", "The provider scope lacks read permission or has no resources.", "Re-run with a read-only role attached to at least one account/cluster."),
        ("Services look wrong.", "Naming or tagging is inconsistent.", "Adjust mappings; consistent tags improve future grouping."),
        ("Dependencies are missing.", "Traffic/naming signals are sparse.", "Connect more providers and re-run so inference has more signal."),
    ],
    "best_practices": [
        "Start with read-only credentials and broaden later.",
        "Keep tagging consistent so service grouping stays clean.",
        "Map orphaned assets promptly so attribution is complete.",
        "Re-run discovery after major infrastructure changes.",
    ],
    "faq": [
        ("Does discovery store my credentials?", "No - credentials are validated read-only and never persisted."),
        ("What does discovery find?", "Assets (raw resources), services (logical groups), and dependencies (edges)."),
        ("How are services formed?", "The service mapper clusters related assets using naming, tags, and signals."),
        ("How are dependencies inferred?", "From network, naming, and traffic signals between services."),
        ("What is an orphaned asset?", "A discovered asset not yet attributed to a service."),
        ("How do I fix coverage gaps?", "Map orphaned assets to services so attribution is complete."),
        ("Do I need to re-run discovery?", "Yes - after infrastructure changes or adding a provider."),
        ("Why does discovery power other features?", "SLOs, incidents, and capacity all rely on the discovered service map."),
        ("Can I discover multiple providers?", "Yes - all connected providers are scanned and normalized together."),
        ("Is discovery safe to run?", "Yes - it uses read-only APIs and makes no changes to your infrastructure."),
    ],
    "reading_time_minutes": 5,
    "difficulty": "Beginner",
    "role": "Platform Admin / SRE",
    "business_value": "Always-current inventory",
    "expected_outcomes": ["Discovered assets", "Mapped services", "Inferred dependencies", "Complete coverage"],
    "related": ["onboarding", "dependencies", "service-health"],
    "common_mistakes": [
        "Running discovery with credentials that lack read access.",
        "Leaving orphaned assets unmapped, breaking attribution.",
        "Using inconsistent tags that scramble service grouping.",
        "Never re-running discovery after infrastructure changes.",
        "Assuming discovery changes infrastructure (it is read-only).",
    ],
    "next_steps": [
        "Open the Dependency Graph to review blast radius.",
        "Generate SLOs for newly mapped services.",
        "Enable monitoring so discovered services emit alerts.",
    ],
    "arch": "graph TD\n  Providers --> DiscoveryEngine\n  DiscoveryEngine --> Assets\n  Assets --> ServiceMapper\n  ServiceMapper --> Services\n  Services --> DependencyMapper\n  DependencyMapper --> Graph",
    "internal": {"customer_action": "Run discovery", "engines": ["Discovery Engine", "Asset Normalizer", "Service Mapper", "Dependency Mapper"], "outputs": ["Assets", "Services", "Dependency edges", "Coverage metrics"]},
    "expected_screens": ["Discovery run controls", "Discovered assets list", "Service mapping summary", "Dependency edges"],
})

NEW_MODULE_DEFS.append({
    "key": "ai-teams",
    "name": "AI Teams",
    "category": "admin",
    "route": "/ai-teams",
    "nav_path": ["Sidebar", "AI Teams", "Teams"],
    "overview": {
        "what": "Configurable teams of AI agents (investigator, RCA, and more) that do the heavy lifting of incident response and analysis.",
        "why": "They automate investigation and analysis so your humans focus on decisions, not data gathering.",
        "business_value": "Scales SRE expertise without scaling headcount.",
        "who": "SRE leads and platform admins who configure automation.",
        "when": "After onboarding (a default team is created) and whenever you tune automation.",
    },
    "prerequisites": [
        "A completed onboarding (a default SRE team is auto-provisioned).",
        "Admin permission to create or edit teams and agents.",
    ],
    "steps": [
        ("Open AI Teams -> Teams.",
         "Your teams, including the default SRE team, are listed.",
         "The view reads the teams configured for your organization."),
        ("Open the default SRE team.",
         "Its member agents (investigator, RCA, etc.) are shown.",
         "The team record lists each agent and its role."),
        ("Inspect the Incident Investigator agent.",
         "Its purpose, inputs, and outputs are described.",
         "Each agent declares the signals it consumes and the artifacts it produces."),
        ("Inspect the RCA agent.",
         "You see how it derives root cause and confidence.",
         "The RCA agent consumes the timeline and changes to rank causes."),
        ("Create a new team.",
         "A new team is created and ready for agents.",
         "Team creation writes a new team record scoped to your organization."),
        ("Add an agent to the team and choose its role.",
         "The agent appears as a team member with that role.",
         "Agent assignment links the agent's capabilities to the team."),
        ("Set the team as default (optional).",
         "New incidents will use this team automatically.",
         "The default flag routes new investigations to this team."),
        ("Review what each agent is allowed to do.",
         "Capabilities and any approval requirements are shown.",
         "Capabilities define which actions an agent can propose versus execute."),
        ("Run the team against a sample incident.",
         "The team investigates and produces findings.",
         "Agents execute in sequence, passing artifacts down the pipeline."),
        ("Review the team's outputs and adjust.",
         "Root cause, confidence, and recommendations are produced.",
         "Outputs feed the incident workflow and can be tuned by editing agents."),
    ],
    "interpretation": [
        ("Team", "A named group of agents that work an incident together."),
        ("Agent", "A specialized AI worker with a role, inputs, and outputs."),
        ("Default team", "The team automatically used for new incidents."),
        ("Capability", "What an agent may propose or execute."),
        ("Pipeline", "The ordered sequence in which agents run."),
        ("Output artifact", "A finding (root cause, recommendation) an agent produces."),
    ],
    "example": {
        "scenario": "A team wants faster first-response on incidents.",
        "walkthrough": "They keep the default SRE team, confirm the Investigator and RCA agents, and run it on a sample incident to validate the outputs.",
        "outcome": "New incidents are automatically investigated, producing a root cause and recommendations in minutes.",
    },
    "troubleshooting": [
        ("No team runs on new incidents.", "No team is set as default.", "Mark a team as default so investigations route to it."),
        ("Agent outputs look thin.", "Required signals are not connected.", "Connect observability and source providers so agents have inputs."),
        ("An agent should not auto-execute.", "Its capability is too broad.", "Restrict the capability so it proposes actions for approval instead."),
    ],
    "best_practices": [
        "Keep one clearly marked default team.",
        "Give agents only the capabilities they need.",
        "Validate changes against a sample incident before relying on them.",
        "Connect all relevant providers so agents have rich inputs.",
    ],
    "faq": [
        ("Do I have to build a team from scratch?", "No - a default SRE team with investigator and RCA agents is created during onboarding."),
        ("What is an agent?", "A specialized AI worker with a defined role, inputs, and outputs."),
        ("What is the default team?", "The team automatically used to investigate new incidents."),
        ("Can agents execute changes?", "Only within their capabilities, and risky actions still require human approval."),
        ("How do agents get their data?", "From the providers you connected and from the incident's signals."),
        ("Can I create multiple teams?", "Yes - create teams for different domains or environments."),
        ("How do I test a team?", "Run it against a sample incident and review the outputs."),
        ("What is the pipeline?", "The ordered sequence in which a team's agents run."),
        ("Why are agent outputs thin?", "Likely missing inputs - connect the relevant providers."),
        ("Are teams organization-scoped?", "Yes - teams and agents belong to your organization."),
    ],
    "reading_time_minutes": 6,
    "difficulty": "Intermediate",
    "role": "SRE Lead / Platform Admin",
    "business_value": "Scales SRE expertise",
    "expected_outcomes": ["A configured team", "Agents with right-sized capabilities", "Automated investigations"],
    "related": ["incidents", "workflows", "recommendations"],
    "common_mistakes": [
        "Having no default team, so new incidents are not auto-investigated.",
        "Granting agents broad execute capabilities without approval gates.",
        "Relying on a team without testing it on a sample incident.",
        "Forgetting to connect providers, starving agents of inputs.",
        "Creating many overlapping teams with no clear default.",
    ],
    "next_steps": [
        "Run the team on a real incident and review outputs.",
        "Wire the team into a Workflow for end-to-end automation.",
        "Tighten agent capabilities to match your approval policy.",
    ],
    "arch": "graph TD\n  Team --> Investigator\n  Investigator --> RCA\n  RCA --> Recommender\n  Recommender --> Outputs[Findings]",
    "internal": {"customer_action": "Configure and run an AI team", "engines": ["Team Orchestrator", "Investigator Agent", "RCA Agent", "Recommendation Agent"], "outputs": ["Root cause", "Confidence", "Recommendations"]},
    "expected_screens": ["Teams list", "Team detail", "Agent capabilities", "Sample run outputs"],
})

NEW_MODULE_DEFS.append({
    "key": "workflows",
    "name": "Workflows",
    "category": "admin",
    "route": "/workflows",
    "nav_path": ["Sidebar", "AI Teams", "Workflows"],
    "overview": {
        "what": "Automated, multi-stage processes that chain AI teams and actions into a repeatable response - with approvals where you want them.",
        "why": "They turn your best incident playbook into a consistent, auditable automation that runs the same way every time.",
        "business_value": "Consistent response, less toil, and a clear audit trail.",
        "who": "SRE leads and platform admins who codify operational processes.",
        "when": "After you have a team configured and a process worth standardizing.",
    },
    "prerequisites": [
        "At least one configured AI team.",
        "Admin permission to create and edit workflows.",
    ],
    "steps": [
        ("Open AI Teams -> Workflows.",
         "Existing workflows with their stages are listed.",
         "The view reads workflow definitions scoped to your organization."),
        ("Create a new workflow.",
         "An empty workflow is created, ready for stages.",
         "Creation writes a workflow record you can add stages to."),
        ("Add the first stage and assign a team.",
         "The stage appears with its assigned team.",
         "Stage assignment links a team to a step in the process."),
        ("Add an approval gate where human sign-off is required.",
         "The workflow pauses at that stage until approved.",
         "Approval gates insert a wait-for-approval state into the run."),
        ("Add subsequent stages (investigate, recommend, remediate).",
         "The workflow shows the full ordered process.",
         "Stages run in sequence, passing outputs forward."),
        ("Define triggers for the workflow.",
         "You choose what starts the workflow (e.g., a new incident).",
         "Triggers bind events to an automatic workflow start."),
        ("Validate the workflow on a sample incident.",
         "The workflow runs end to end and records each stage.",
         "The execution engine runs stages and logs status transitions."),
        ("Approve at the gate during the run.",
         "The run resumes after your approval.",
         "Approval resolves the wait state and continues execution."),
        ("Review the execution results per stage.",
         "Each stage shows started/completed/failed and its outputs.",
         "Execution records capture stage and agent results for audit."),
        ("Publish the workflow for real incidents.",
         "The workflow is active and runs on its trigger.",
         "Publishing marks the workflow live so triggers fire it."),
    ],
    "interpretation": [
        ("Workflow", "An ordered, multi-stage automation."),
        ("Stage", "A single step, usually assigned to a team."),
        ("Approval gate", "A stage that waits for human sign-off."),
        ("Trigger", "The event that starts the workflow."),
        ("Execution", "A single run of the workflow with per-stage status."),
        ("Status transition", "Started/completed/failed events recorded for audit."),
    ],
    "example": {
        "scenario": "A team wants consistent handling of checkout incidents.",
        "walkthrough": "They build investigate -> recommend -> (approval) -> remediate, trigger it on new checkout incidents, and validate on a sample.",
        "outcome": "Every checkout incident now follows the same auditable, approval-gated process automatically.",
    },
    "troubleshooting": [
        ("The workflow never starts.", "No trigger is defined or it is unpublished.", "Define a trigger and publish the workflow."),
        ("A run is stuck.", "It is waiting at an approval gate.", "Approve the gate so the run resumes."),
        ("A stage fails.", "Its team lacks inputs or capability.", "Fix the team's inputs/capabilities and re-run."),
    ],
    "best_practices": [
        "Put approval gates before any high-risk action.",
        "Validate on a sample incident before publishing.",
        "Keep stages small and single-purpose.",
        "Review execution records to refine the process over time.",
    ],
    "faq": [
        ("What is a workflow?", "An ordered, multi-stage automation that chains teams and actions."),
        ("What is a stage?", "A single step in the workflow, usually assigned to a team."),
        ("What is an approval gate?", "A stage that pauses the run until a human approves."),
        ("How does a workflow start?", "Via a trigger you define, such as a new incident."),
        ("Can I test before going live?", "Yes - validate on a sample incident, then publish."),
        ("What if a run gets stuck?", "It is likely at an approval gate - approve to resume."),
        ("Why did a stage fail?", "Its team may lack inputs or capability; fix and re-run."),
        ("Are runs auditable?", "Yes - per-stage status transitions and outputs are recorded."),
        ("Can I require approvals?", "Yes - insert approval gates before risky stages."),
        ("Are workflows organization-scoped?", "Yes - definitions and runs belong to your organization."),
    ],
    "reading_time_minutes": 6,
    "difficulty": "Intermediate",
    "role": "SRE Lead / Platform Admin",
    "business_value": "Consistent, auditable response",
    "expected_outcomes": ["A published workflow", "Approval gates where needed", "Auditable executions"],
    "related": ["ai-teams", "incidents", "remediation"],
    "common_mistakes": [
        "Automating risky actions with no approval gate.",
        "Publishing without validating on a sample incident.",
        "Building giant multi-purpose stages that are hard to debug.",
        "Forgetting to define a trigger, so the workflow never runs.",
        "Never reviewing execution records to improve the process.",
    ],
    "next_steps": [
        "Publish the workflow and monitor its first real executions.",
        "Tune stages and gates based on execution records.",
        "Connect outcomes back into postmortems and prevention.",
    ],
    "arch": "graph TD\n  Trigger --> Stage1[Investigate]\n  Stage1 --> Stage2[Recommend]\n  Stage2 --> Gate[Approval Gate]\n  Gate --> Stage3[Remediate]\n  Stage3 --> Records[Execution Records]",
    "internal": {"customer_action": "Build and run a workflow", "engines": ["Workflow Builder", "Execution Engine", "Approval Gate", "Audit Recorder"], "outputs": ["Workflow definition", "Per-stage execution status", "Audit trail"]},
    "expected_screens": ["Workflows list", "Stage builder", "Approval gate", "Execution records"],
})

# Long-form training narrative per module (keeps each guide >=1000 words and
# teaches the mental model, not just the clicks).
DEEP_DIVE: dict[str, str] = {}

DEEP_DIVE["monitoring"] = (
    "Think of Monitoring as the single front door for every signal your systems produce. "
    "Before Nexora, on-call engineers typically juggle several consoles - one for cloud metrics, "
    "one for the APM tool, another for logs - and they mentally stitch those views together while "
    "the clock is running. Monitoring collapses that into one prioritized, deduplicated stream so the "
    "first question on a shift ('what is on fire and who is on it?') is answered in seconds. The two "
    "numbers to anchor on are Active Alerts and Unacknowledged. Active Alerts tells you the size of the "
    "current storm; Unacknowledged tells you how much of that storm nobody owns yet. A healthy shift "
    "keeps Unacknowledged close to zero, because every unowned alert is a potential blind spot. "
    "Severity is the second lens. Nexora maps each provider's native severity onto a consistent "
    "Critical/High/Medium/Low scale so a 'P1' in one tool and a 'sev-1' in another line up correctly. "
    "Sort by severity first, then narrow by service using the search box - this is the fastest path "
    "from a wall of alerts to the handful that matter. When you see several alerts clustering on one "
    "service within a few minutes, resist the urge to treat each as a separate ticket. That cluster is "
    "almost always one underlying problem, and the right move is to escalate a single incident rather "
    "than chase symptoms. Escalation is where Monitoring hands off to Incident Intelligence: the alert "
    "context travels with the incident, so the investigation starts with evidence instead of a blank "
    "page. A common anti-pattern is silencing noisy alerts to make the board look calm. Silencing hides "
    "the symptom but loses the root cause; escalating captures it. Finally, remember that attribution is "
    "everything. An alert with no service owner cannot be routed, scored, or correlated well, so part of "
    "operating Monitoring well is closing mapping gaps in Service Mapping so every source has a home. "
    "Used this way, Monitoring is not just a list - it is the triage surface that decides how fast the "
    "rest of your incident response can move."
)

DEEP_DIVE["incidents"] = (
    "Incident Intelligence is the workspace where a noisy signal becomes an understood, resolved, and "
    "documented event. The mental model is a pipeline you can walk without ever leaving the page: "
    "summary, timeline, change intelligence, recommendations, remediation, and postmortem. Each tab "
    "answers a specific question. The summary answers 'what and how bad?' with severity, status, and a "
    "confidence-scored root cause. The timeline answers 'what happened, in what order?' by merging "
    "alerts, metrics, and deploys into one narrative. Change Intelligence answers 'what changed?' by "
    "correlating recent commits, releases, and authors to the incident window - which is why connecting "
    "a source provider during onboarding pays off so heavily here. Recommendations answer 'what should "
    "we do?' with ranked actions, each carrying confidence, risk, estimated recovery, and a plain-language "
    "rationale. Remediation answers 'do it safely', enforcing human approval before anything executes and "
    "recording who approved what. The postmortem answers 'how do we prevent this?' by turning the whole "
    "record into a blameless document with trackable action items. The single most important number here "
    "is the confidence score. High confidence means the evidence converges cleanly on one cause; low "
    "confidence is a signal to slow down, read the timeline, and verify before acting. The discipline that "
    "separates fast teams from slow ones is resisting the urge to jump straight to remediation. Two minutes "
    "spent confirming the trigger on the timeline routinely saves an hour of chasing the wrong fix. Risk is "
    "the second number that matters: prefer reversible, low-blast-radius actions when uncertainty is high, "
    "even if they recover slightly slower. Because the entire workflow lives on one page, an incident "
    "commander can run an event end to end - detect, understand, decide, act, and retrospect - while keeping "
    "the team aligned. Every step also feeds your reliability metrics: lifecycle timestamps produce MTTR and "
    "MTTA, and resolved incidents roll up into the executive reports leadership watches."
)

DEEP_DIVE["timeline"] = (
    "The Timeline exists to kill the most expensive part of incident response: manually reconstructing what "
    "happened. In a traditional war room, someone scrolls logs, someone else pulls a metrics dashboard, and a "
    "third person checks the deploy history, and the group slowly assembles a shared story under pressure. "
    "Nexora's timeline does that assembly automatically, merging alerts, metric anomalies, and changes into a "
    "single, chronological narrative with provider badges so you can see at a glance whether a given event came "
    "from the cloud, the observability stack, or a source repository. Read it top to bottom: the earliest events "
    "are the leading indicators, and the goal is to find the moment of onset - when customer impact actually "
    "began - and then look just before it for the suspected trigger. The trigger is highlighted and carries a "
    "confidence score, which expresses how cleanly that event correlates with the onset. A deploy at 14:02 "
    "followed by a latency anomaly at 14:05 and alerts at 14:07 is a textbook causal chain, and the timeline "
    "makes that chain obvious. The discipline to build here is to always read the timeline before approving any "
    "remediation; the timeline is your evidence, and acting without it is guessing. Provider badges are not "
    "decoration - they tell you whether deploys are even present, and if they are missing it usually means a "
    "source provider was never connected, which blinds change correlation. When two changes land in the same "
    "window and both look suspicious, the timeline hands off to Change Intelligence, where you can compare "
    "candidates side by side. A subtle but important property is consistency: the same reconstructed timeline is "
    "reused when you generate the postmortem, so the record stakeholders read matches exactly what the responders "
    "saw during the incident. That consistency is what makes postmortems trustworthy. Treated well, the timeline "
    "turns a chaotic, memory-based reconstruction into a defensible, shareable, and fast confirmation of cause "
    "and effect - usually in the first two minutes of an investigation."
)

DEEP_DIVE["recommendations"] = (
    "Recommendations turn 'we think we know the cause' into 'here is exactly what to do about it, ranked.' Under "
    "pressure, the hardest part of incident response is often not finding the cause but deciding the response - "
    "and deciding well when the room is tense and the clock is loud. The recommendation engine scores candidate "
    "actions against the inferred root cause and presents them ranked, each with four numbers that you should "
    "read together rather than in isolation. Confidence tells you how strongly the system backs the action. Risk "
    "tells you how dangerous it is to run, derived from blast radius and reversibility. Estimated recovery tells "
    "you how long it should take to restore service, based on comparable past remediations. And the rationale "
    "explains, in plain language, why the action fits the cause. The novice mistake is to grab the fastest action "
    "and run; the experienced move is to balance speed against risk and to prefer reversible actions whenever "
    "uncertainty is high. A rollback that you can instantly undo is almost always a better first move than an "
    "irreversible data migration that recovers a minute faster. Recommendations are deliberately decoupled from "
    "execution: choosing one does not run it. Instead, the chosen action is promoted to the Remediation tab, where "
    "it waits for human approval. This separation is a safety feature - it means the AI proposes and a human "
    "disposes. If confidence is low across every option, that is itself information: your signals are sparse or "
    "conflicting, and you should connect more providers or verify the root cause before committing. Recording which "
    "recommendation you chose matters beyond the current incident; it lands in the postmortem and feeds back to "
    "improve future ranking, so the system gets better at your environment over time. Used well, this tab compresses "
    "the decision phase of an incident from anxious debate into a structured, defensible choice."
)

DEEP_DIVE["remediation"] = (
    "Remediation is the safety-critical surface of incident response, and its entire design philosophy is 'AI "
    "proposes, humans dispose.' Nothing here runs by surprise. Actions arrive from the Recommendations tab as "
    "pending proposals, each carrying the context it came from: the action itself, the target it is bound to, its "
    "risk, and its rationale. The single most important habit to build is to confirm the bind - the exact service "
    "or resource the action will touch - before you approve anything. Most remediation accidents are not wrong "
    "actions; they are right actions pointed at the wrong target. Risk and blast radius travel with each action so "
    "you can see how far a mistake would reach, and high-risk actions are explicitly flagged so they cannot be "
    "rubber-stamped. Approval is auditable: when you approve, your identity and the decision are recorded, which "
    "matters both for trust during the incident and for the postmortem afterward. Execution streams a result back - "
    "success or failure with detail - but the discipline that separates mature teams is to never trust the action's "
    "own status as proof of recovery. Verify in Service Health: did availability return, did burn rate fall, did "
    "the incident actually stop? An action can report success while the service stays degraded for a different "
    "reason. If execution fails, resist the urge to blindly retry; the environment may have shifted since the "
    "recommendation was generated, so re-investigate, pick an updated recommendation, and try again. Every outcome "
    "is recorded and linked to the incident, which does double duty: it populates the postmortem and it sharpens "
    "future recommendations. The approval gate may feel like friction in the moment, but it is precisely what lets "
    "you adopt automation without fear - you get the speed of AI-prepared actions with the judgment of a human in "
    "the loop. That combination is what makes remediation both fast and safe, and it is why bypassing the gate for "
    "'just this once' is the one habit you should never form."
)

DEEP_DIVE["postmortems"] = (
    "A postmortem is how an incident becomes organizational learning instead of a story that fades by Friday. "
    "Nexora generates the first draft for you from the incident's own investigation record, so you start from a "
    "structured document - summary, reconstructed timeline, root cause, contributing factors, impact, and action "
    "items - rather than a blank page and a fading memory. This matters because memory-based postmortems are both "
    "slow to write and quietly inaccurate; the generated timeline is the same one responders saw, which keeps the "
    "record honest. The most important conceptual distinction to internalize is root cause versus contributing "
    "factors. The root cause is the trigger - the change or event that started the incident. Contributing factors "
    "are the systemic conditions that made the incident possible or worse: the missing alert, the absent canary, "
    "the dependency nobody documented. Good postmortems name both, because fixing only the trigger leaves the "
    "system just as fragile for the next, different trigger. The second principle is blamelessness. The document "
    "focuses on systems and processes, not individuals, because the moment people fear blame they stop sharing the "
    "details that make postmortems valuable. The output that actually changes your reliability is the action item, "
    "and the single most common failure is creating action items with no owner and no due date - those simply never "
    "happen. Assign every action to a person, give it a date, and track it; many of those items will become "
    "Deployment Safety guardrails or Change Failure prevention rules. Versioning lets you edit the generated draft "
    "while preserving the baseline, and export to PDF, HTML, or Markdown means you can circulate the retrospective "
    "to anyone, including stakeholders without an account. Over time, patterns across many postmortems - the same "
    "contributing factor showing up again and again - become some of the most valuable signals leadership can act "
    "on, which is why these documents feed directly into your executive reporting."
)

DEEP_DIVE["service-health"] = (
    "Service Health is the one screen that answers 'is this service okay, and will it stay okay?' for any service "
    "you run. The headline is a 0-100 health score, but the score is a summary, not the story - the skill is "
    "reading the signals beneath it. Availability tells you how often the service is succeeding. Error budget tells "
    "you how much failure your SLO still allows, and burn rate tells you how fast you are spending that budget. "
    "Burn rate is the number experienced SREs watch most closely: a service can show high availability over a long "
    "window while a short, severe spike burns most of the month's budget in an afternoon, so a green-looking score "
    "can hide a service that is one bad hour from breaching. That is why a green score is never, by itself, "
    "permission to ship a risky change. The page is deliberately a single investigation surface: from one service "
    "you can move through Health, SLOs, Dependencies, Incidents, Deployments, Capacity, and Cost without losing "
    "context. The Dependencies tab is where blast radius lives - how many services, and how critical, would be hurt "
    "if this one failed - and underestimating blast radius is one of the most expensive mistakes teams make, "
    "because it turns a small change into a wide outage. The prediction indicator projects current burn and "
    "saturation trends forward, giving you an early warning that health may degrade before it actually does, which "
    "is the difference between a planned intervention and a 3 a.m. page. When a score drops, the discipline is to "
    "correlate: check the Incidents tab for active events and the Deployments tab for a recent change before "
    "concluding anything. And when targets feel wrong, resist tuning SLOs before you have a baseline - early "
    "targets set without data tend to be either meaninglessly loose or constantly breaching. Used well, Service "
    "Health is both a real-time gauge and a planning tool: it tells you the current state and gives you the lead "
    "time to act before that state becomes an incident."
)

DEEP_DIVE["deployment-safety"] = (
    "Deployment Safety answers a deceptively simple question with real rigor: 'is it safe to ship this change right "
    "now?' The 'right now' is the part teams underestimate. A change that is perfectly safe at 10 a.m. on a quiet "
    "Tuesday can be reckless during an active incident or while a service is already burning its error budget, and "
    "the safety score captures exactly that timing-aware judgment. The score is a 0-100 number that maps onto three "
    "statuses - Safe, Caution, and Block - and it is computed by weighing several risk factors together: how large "
    "the change is, how often similar changes have failed or been rolled back, the current health of the target "
    "service, and its SLO burn rate. Reading the score without reading the factors is the classic mistake; the "
    "factors tell you what to fix. If change size dominates, split the change. If recent failure history dominates, "
    "add tests or a canary. If timing dominates because the service is strained, wait for a calmer window. The "
    "engine also recommends guardrails - canary releases, off-peak timing, feature flags - chosen based on which "
    "risk factors are loudest, and these guardrails work by shrinking blast radius and shortening detection time so "
    "that even a bad change is survivable. A Block status is not a bureaucratic wall; it is a strong recommendation "
    "to mitigate the top factor and re-run, and re-running with the change addressed should visibly move the score. "
    "The most damaging anti-pattern is dismissing a Caution because the change 'feels small' - small changes cause "
    "plenty of outages, especially when shipped at the wrong moment. Deployment Safety is most powerful when used "
    "alongside Change Failure Prediction: one judges whether now is a safe moment, the other predicts how likely "
    "this specific change is to fail, and together they let you choose both the right change and the right time. "
    "Finally, recording the actual outcome of each deployment closes the loop - those outcomes train the history "
    "analyzer, so the more honestly you record results, the smarter your future safety scores become."
)

DEEP_DIVE["capacity"] = (
    "Capacity Planning exists to move you from reacting to saturation to anticipating it. The core artifact is a "
    "forecast: for each resource or service, Nexora fits a trend to your historical utilization and projects it "
    "forward to estimate an exhaustion date - the point at which the resource runs out of headroom if nothing "
    "changes. That single date reframes capacity work from a fire drill into a scheduling problem. Around it sit a "
    "few signals you need to read together. Current utilization is where you are now; headroom is what is left; the "
    "risk tier (Low/Medium/High/Critical) translates time-to-exhaustion into urgency so you know what to handle "
    "first. The forecast horizon lets you zoom the projection - a 30-day window catches imminent problems while a "
    "90-day window surfaces slow, creeping growth that short windows miss, which is exactly the kind of trend that "
    "causes 'surprise' outages. Perhaps the most useful concept is the saturation driver: the underlying reason a "
    "resource is heading toward exhaustion, whether steady organic growth, a memory leak, or predictable seasonal "
    "load. The driver tells you not just that you need more capacity but which dimension to scale and whether scaling "
    "even fixes the problem - a leak is a bug, not a capacity shortfall. The discipline to build is to plan changes "
    "with lead time ahead of the exhaustion date rather than scrambling once a resource is already saturated, and to "
    "forecast across resources rather than fixating on one, because the resource that saturates first is the one that "
    "takes you down. Capacity is also intertwined with cost: overscaling to be safe quietly wastes spend, so the "
    "right move is to cross-check Cost Optimization and right-size rather than over-provision. After you make a "
    "change, re-run the forecast to confirm it worked - utilization should flatten and the exhaustion date should "
    "move out. Done consistently, Capacity Planning turns capacity from a recurring emergency into a quiet, "
    "scheduled, and cost-aware part of operations."
)

DEEP_DIVE["cost"] = (
    "Cost Optimization reframes cloud spend from a monthly surprise into a managed, prioritized backlog of "
    "improvements. The engine ingests your billing and usage data and detects waste - resources that cost money "
    "without delivering proportional value, typically idle, oversized, or orphaned. The headline figure is the total "
    "savings opportunity, but the real value is in how findings are ranked. Each recommendation carries an estimated "
    "savings (shown both monthly and annualized) and an effort level, and the engine sorts by savings relative to "
    "effort so that quick wins - low effort, high savings - rise to the top. The disciplined approach is to bank "
    "those quick wins first; they build momentum and free up budget without large projects, while structural changes "
    "that require architectural work can be scheduled deliberately. Every finding includes a rationale that cites the "
    "usage signal that triggered it, so you are never asked to cut something blindly, and findings are attributed to "
    "the owning service or team so the right people can act. That attribution matters: the most common failure mode "
    "is applying cost changes without telling the team that owns the resource, which erodes trust and occasionally "
    "breaks things. The second pitfall is treating cost in isolation from reliability. Cutting capacity too "
    "aggressively to save money can create saturation risk, which is why Cost Optimization is meant to be used "
    "alongside Capacity Planning - you want to right-size, not starve. Orphaned resources deserve special attention: "
    "individually they look trivial, but in aggregate forgotten volumes, idle load balancers, and unattached "
    "addresses add up to real money, and because nobody owns them they linger indefinitely. Nexora never changes "
    "your infrastructure for you; it recommends, and your teams apply, which keeps you in control. After changes "
    "land, re-running the analysis is essential - applied items drop out and the opportunity total updates, giving "
    "you a clear, ongoing measure of realized savings rather than a one-time snapshot that goes stale."
)

DEEP_DIVE["change-failure"] = (
    "Change Failure Prediction puts a number on a question every team asks before shipping: 'how likely is this "
    "change to cause an incident?' The engine learns from your historical change outcomes and produces a failure "
    "probability - a 0-100% estimate for the specific change in front of you - along with a risk level that maps "
    "that probability onto Low/Medium/High/Critical. The crucial mindset is that this is a probability, not a "
    "prophecy. A 10% prediction does not guarantee success, and treating a low number as a green light is exactly "
    "the overconfidence that precedes outages; use the percentage as a relative risk signal that informs how much "
    "care a change deserves. The prediction decomposes into contributing factors you can actually act on: change "
    "size, the rollback frequency of similar changes, the deployment success rate of comparable work, and the "
    "presence of active incidents. Each factor contributes capped points, which means no single factor can quietly "
    "dominate the score and the breakdown stays interpretable. Those factors are also your levers. A large change "
    "can be split into smaller, safer increments - smaller changes are easier to reason about, review, and roll "
    "back. Active incidents inflate risk because the system is already stressed, so resolving them first is often "
    "the cheapest way to lower a change's predicted failure. The engine also estimates blast radius from the "
    "dependency graph, telling you which services would be affected if the change fails, so you can weigh not just "
    "the odds of failure but its potential reach. Change Failure Prediction and Deployment Safety are complementary: "
    "this feature judges how risky the change itself is, while Deployment Safety judges whether now is a safe moment "
    "to ship it, and the strongest workflow consults both. As with safety scoring, recording the real outcome of "
    "each deployment is what makes the model better - every honest result retrains it to understand your environment, "
    "so the predictions you rely on get steadily more accurate the more you use them."
)

DEEP_DIVE["discovery"] = (
    "Infrastructure Discovery is the foundation everything else stands on: an accurate, automatically maintained map "
    "of what you actually run. Manual inventories rot the moment they are written, and stale maps quietly poison "
    "every downstream feature - you cannot set good SLOs, attribute incidents, or forecast capacity for services you "
    "do not know exist. Discovery solves this by scanning your connected providers using read-only APIs and producing "
    "three layers of truth. Assets are the raw resources - instances, clusters, repositories, databases - normalized "
    "into a common model regardless of which provider they came from. Services are logical groupings of related "
    "assets, clustered by naming, tags, and signals, because humans reason about 'the checkout service,' not about "
    "forty individual resources. Dependencies are the directed relationships between services, inferred from network, "
    "naming, and traffic signals, and they are what make blast-radius analysis possible. A key reassurance for "
    "first-time users is that discovery is strictly read-only: it observes, it never changes your infrastructure, and "
    "credentials are validated read-only and never stored. The metric to watch is coverage - the share of discovered "
    "assets that are mapped into services - because orphaned assets, those not yet attributed to any service, are "
    "holes in your map that break attribution for incidents, cost, and capacity. Closing those gaps by mapping "
    "orphans is part of operating discovery well, and consistent tagging is the cheapest way to keep automatic "
    "grouping accurate over time. Discovery is not a one-time event; infrastructure changes constantly, so re-running "
    "it after significant changes or after adding a provider lets the engine reconcile the live estate against the "
    "stored map, surfacing new assets and retiring stale ones. The payoff is large and compounding: a current, "
    "trustworthy service map means SLOs target real services, incidents attribute to real owners, dependency graphs "
    "reflect reality, and capacity forecasts cover everything you run. In short, the quality of every reliability "
    "feature is capped by the quality of your discovery, which is why it is the right place to start and the right "
    "place to revisit whenever your environment shifts."
)

DEEP_DIVE["ai-teams"] = (
    "AI Teams are how Nexora scales scarce SRE expertise without scaling headcount. Instead of a single monolithic "
    "'AI,' the platform organizes work into teams of specialized agents, each with a defined role, a set of inputs it "
    "consumes, and the artifacts it produces. The default SRE team created during onboarding already contains the "
    "essentials - an Incident Investigator that gathers and structures evidence, and an RCA agent that consumes the "
    "timeline and changes to rank candidate root causes with a confidence score - so most teams get value immediately "
    "without configuring anything. Understanding the pipeline is the key mental model: agents run in sequence, each "
    "passing its outputs to the next, so the investigator's evidence feeds the RCA agent, whose root cause feeds the "
    "recommender. This composability is what lets you tune behavior precisely. You can create new teams for different "
    "domains or environments, add agents and assign their roles, and - critically - control each agent's capabilities, "
    "which define what it may merely propose versus what it may execute. The safety principle mirrors the rest of the "
    "platform: give agents the narrowest capability that does the job, and keep risky actions behind human approval "
    "rather than granting broad auto-execute powers. Two configuration habits prevent most problems. First, always "
    "maintain one clearly marked default team, because the default is what new incidents route to automatically; "
    "without it, investigations simply do not start. Second, validate any team against a sample incident before "
    "relying on it in production, so you can see its outputs and adjust before a real event depends on it. Agents are "
    "only as good as their inputs, so thin or vague outputs almost always trace back to missing provider connections - "
    "connect observability and source providers so the agents have rich signals to reason over. Teams and agents are "
    "organization-scoped, keeping your automation isolated and governable. Used well, AI Teams turn the expertise of "
    "your best responders into a repeatable capability that works every incident, at any hour, freeing your humans to "
    "make the judgment calls that genuinely need them while the agents handle the heavy, repetitive work of gathering "
    "and structuring evidence."
)

DEEP_DIVE["workflows"] = (
    "Workflows are where your best operational playbook stops living in someone's head and becomes a consistent, "
    "auditable automation that runs the same way every time. A workflow is an ordered set of stages, and each stage "
    "is usually backed by an AI team - investigate, then recommend, then remediate, for example. Between stages you "
    "place the control that makes automation trustworthy: the approval gate, a stage that pauses the entire run until "
    "a human signs off. The design principle is straightforward and worth internalizing - automate the toil, gate the "
    "risk. Investigation and analysis can run automatically because they are read-only and reversible; anything that "
    "changes production should sit behind an approval gate so a human stays in the loop at the exact moment it matters. "
    "Workflows start from triggers you define, such as the creation of a new incident on a particular service, which "
    "is what turns a manual procedure into an automatic response. The lifecycle is deliberate: build the stages, place "
    "your gates, define the trigger, validate the whole thing on a sample incident, and only then publish it so it goes "
    "live. Skipping validation is the most common and most painful mistake, because a workflow that misbehaves does so "
    "consistently and at scale. Every run produces execution records - per-stage started/completed/failed status and "
    "the outputs each stage generated - which give you a complete audit trail and, just as importantly, the raw "
    "material to refine the process over time. When a run appears stuck, it is almost always waiting at an approval "
    "gate, and when a stage fails it usually means its team lacks the inputs or capabilities it needs, both of which "
    "are quick to diagnose from the records. Keep stages small and single-purpose so failures are easy to localize, "
    "and put a gate before any high-risk action without exception. Workflows tie the whole platform together: they "
    "orchestrate AI Teams, feed Remediation through controlled gates, and close the loop back into postmortems and "
    "prevention, so that consistent, well-governed response becomes the default rather than something that depends on "
    "who happens to be on call."
)

# === APPEND BELOW ===
