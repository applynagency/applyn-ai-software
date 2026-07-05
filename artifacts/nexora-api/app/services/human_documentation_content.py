"""Sprint 56D.5 — Human-Written Documentation: authored content seeds.

Pure data (no imports from other services) consumed by ``human_documentation``.

For every customer-facing module this provides genuinely human, business-first
content that the engine composes into a 10-section, >=2000-word guide that a
non-technical manager can read:

* ``problem``         — Business Problem, framed as Without / With.
* ``outcomes``        — measurable Business Outcomes.
* ``scenarios``       — "When should I use this?" real situations.
* ``example``         — a realistic worked example (alert → postmortem).
* ``success_metrics`` — how a customer measures success (metric/target/how).

``SCORE_SCALES`` holds the platform's shared interpretation scales (scores,
risk, confidence, status, health, SLO, cost, capacity) that the engine selects
from per module for the Results Interpretation section.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Shared interpretation scales (Section 6 source).                            #
# --------------------------------------------------------------------------- #
SCORE_SCALES: dict[str, list[tuple[str, str]]] = {
    "Reliability & maturity scores (0–100)": [
        ("90–100 (Excellent)", "Best-in-class. Sustain and use headroom for innovation."),
        ("75–89 (Good)", "Healthy with minor gaps. Address the top one or two findings."),
        ("60–74 (Fair)", "Real risk is accumulating. Plan focused remediation this quarter."),
        ("0–59 (At risk)", "Urgent. Reliability is materially threatened — act now."),
    ],
    "Risk levels": [
        ("Critical", "Customer-facing failure is likely or already happening; stop and fix first."),
        ("High", "Significant chance of impact; schedule remediation before new work."),
        ("Medium", "Worth fixing soon; monitor and plan."),
        ("Low", "Acceptable for now; review periodically."),
    ],
    "Confidence levels": [
        ("High (≥85%)", "Strong evidence; safe to act, including automation where allowed."),
        ("Medium (60–84%)", "Reasonable evidence; a human should confirm before acting."),
        ("Low (<60%)", "Weak or conflicting signal; treat as a hint and investigate."),
    ],
    "Status values": [
        ("Open", "Detected and unworked — needs an owner."),
        ("Acknowledged / In progress", "Someone owns it and is actively working it."),
        ("Resolved / Closed", "Fixed and verified; captured for learning."),
    ],
    "Health scores": [
        ("Healthy (green)", "Within objectives; no action needed."),
        ("Degraded (amber)", "Trending the wrong way or breaching a soft threshold; investigate."),
        ("Unhealthy (red)", "Breaching objectives or failing; prioritize immediately."),
    ],
    "SLO & error-budget scores": [
        ("Budget healthy (>50% left)", "Room to ship; normal change pace is safe."),
        ("Budget tight (10–50% left)", "Slow down risky changes; protect the budget."),
        ("Budget exhausted (≤0%)", "Freeze risky changes; focus on reliability until it recovers."),
    ],
    "Cost scores": [
        ("Optimized", "Spend is efficient for the value delivered."),
        ("Some waste", "Identified savings worth capturing without risk."),
        ("Significant waste", "Large, safe savings available — prioritize the top items."),
    ],
    "Capacity scores": [
        ("Ample headroom (>40%)", "Comfortable for normal growth and spikes."),
        ("Limited headroom (15–40%)", "Plan scaling ahead of the next growth or event."),
        ("Constrained (<15%)", "At risk of saturation; scale now to avoid outages."),
    ],
}

# Which scales matter most per module category (others are appended generically).
CATEGORY_SCALES: dict[str, list[str]] = {
    "onboarding": ["Reliability & maturity scores (0–100)", "Status values", "Confidence levels"],
    "monitoring": ["Risk levels", "Status values", "Health scores", "Confidence levels"],
    "incident": ["Risk levels", "Confidence levels", "Status values", "Health scores"],
    "reliability": ["Health scores", "SLO & error-budget scores", "Reliability & maturity scores (0–100)", "Risk levels"],
    "deployment": ["Risk levels", "Confidence levels", "SLO & error-budget scores", "Status values"],
    "reporting": ["Reliability & maturity scores (0–100)", "Cost scores", "Capacity scores", "SLO & error-budget scores"],
}


def _ex(title, narrative, alert, incident, timeline, root_cause, recommendation, postmortem):
    return {
        "title": title, "narrative": narrative, "alert": alert, "incident": incident,
        "timeline": timeline, "root_cause": root_cause,
        "recommendation": recommendation, "postmortem": postmortem,
    }


# --------------------------------------------------------------------------- #
# Per-module authored seeds.                                                   #
# --------------------------------------------------------------------------- #
HUMAN: dict[str, dict] = {
    "monitoring": {
        "problem": {
            "without": "Without Monitoring, teams discover outages from angry customers, support tickets, or social media — long after revenue and trust have already been lost.",
            "with": "With Monitoring, every provider's signal lands in one prioritized stream, so on-call is alerted and acting before customers ever notice.",
            "summary": "Monitoring turns scattered, noisy provider consoles into a single, deduplicated, owner-attributed alert stream your team can actually act on.",
        },
        "outcomes": [
            {"metric": "Reduce detection time (MTTD)", "detail": "Catch problems in seconds from a unified stream instead of waiting for customer reports."},
            {"metric": "Fewer missed alerts", "detail": "Deduplicated, attributed signal means nothing important slips through the cracks at 3am."},
            {"metric": "Faster, cleaner escalation", "detail": "One click turns an alert into an incident that already carries its context."},
        ],
        "scenarios": [
            "You are on-call and need a single place to watch everything that is firing right now.",
            "An executive asks 'are we okay?' and you need an instant, credible answer.",
            "A noisy service keeps paging and you want to escalate it into a tracked investigation.",
        ],
        "example": _ex(
            "Checkout latency spike",
            "At 14:02 the checkout service starts slowing down. Monitoring surfaces three High alerts clustered within five minutes, on-call filters by 'checkout', and escalates — all before the first customer complaint.",
            "3× High latency alerts on checkout-api within 5 minutes, deduplicated from two providers.",
            "On-call escalates the cluster into an incident; alert context is carried in automatically.",
            "Timeline shows the latency climb beginning two minutes after a config push.",
            "A database connection-pool exhaustion triggered by the config change.",
            "Roll back the config change and raise the pool ceiling; confidence High.",
            "Postmortem records the config-push gap and adds a pre-deploy pool check.",
        ),
        "success_metrics": [
            {"metric": "Mean time to detect", "target": "< 2 minutes", "how": "Compare alert timestamp to the true incident start."},
            {"metric": "Unacknowledged alerts during a shift", "target": "≈ 0", "how": "Watch the Unacknowledged counter on the Monitoring header."},
            {"metric": "Alerts attributed to a service", "target": "> 95%", "how": "Review the share of alerts with an owning service in Service Mapping."},
        ],
    },
    "incidents": {
        "problem": {
            "without": "Without Incident Intelligence, every incident is a frantic, manual scramble across dashboards, chat, and tribal knowledge — and the same fires keep coming back.",
            "with": "With Incident Intelligence, each incident opens with AI-assembled context, a likely root cause, and recommended fixes, so responders act instead of hunting.",
            "summary": "Incident Intelligence compresses the time from 'something is wrong' to 'we know what and why' from hours to minutes.",
        },
        "outcomes": [
            {"metric": "Reduce MTTR", "detail": "Responders start from an investigated incident, not a blank page."},
            {"metric": "Reduce repeat incidents", "detail": "Captured root cause and actions stop the same failure recurring."},
            {"metric": "Improve responder confidence", "detail": "Junior engineers can run an incident with AI guidance."},
        ],
        "scenarios": [
            "A customer-facing service is failing and you need to coordinate a response fast.",
            "You want one source of truth for what is happening, who owns it, and what changed.",
            "You need to hand off an incident at shift change without losing context.",
        ],
        "example": _ex(
            "Checkout failure",
            "Checkout starts returning 500s. An incident opens automatically from the alert cluster, the AI assembles the timeline, proposes a root cause, and surfaces a ranked fix.",
            "Spike in 5xx errors on checkout-api.",
            "Incident auto-created with severity High and the alerting context attached.",
            "Timeline correlates the error spike with a deployment 90 seconds earlier.",
            "A regression in the new checkout build.",
            "Roll back to the previous build; blast radius limited to checkout.",
            "Postmortem adds a canary gate for checkout deploys.",
        ),
        "success_metrics": [
            {"metric": "Mean time to resolve", "target": "↓ 40% in 2 quarters", "how": "Track MTTR trend on the incident dashboard."},
            {"metric": "Repeat-incident rate", "target": "< 10%", "how": "Count incidents sharing a root-cause signature."},
            {"metric": "Incidents with a recorded root cause", "target": "100%", "how": "Audit closed incidents for a root-cause entry."},
        ],
    },
    "timeline": {
        "problem": {
            "without": "Without the Incident Timeline, responders argue from memory about what happened when, and postmortems are reconstructed from scattered screenshots.",
            "with": "With the Incident Timeline, every alert, deployment, and change is laid on one ordered axis so cause and effect are obvious at a glance.",
            "summary": "The Timeline is the single, trustworthy story of an incident — what changed, when, and what it caused.",
        },
        "outcomes": [
            {"metric": "Faster root-cause isolation", "detail": "Seeing changes next to symptoms makes the trigger obvious."},
            {"metric": "Higher-quality postmortems", "detail": "The timeline becomes the factual spine of the writeup."},
            {"metric": "Less disagreement during response", "detail": "Everyone reasons from the same ordered facts."},
        ],
        "scenarios": [
            "You suspect a recent change caused an incident and need to prove it.",
            "You are writing a postmortem and need an accurate sequence of events.",
            "An exec asks 'what actually happened' and you need a clear narrative.",
        ],
        "example": _ex(
            "Checkout regression",
            "The timeline shows a deploy at 14:00, error rate climbing at 14:02, the incident opening at 14:05, and recovery after rollback at 14:18 — a clean cause-and-effect story.",
            "Error-rate alert on checkout at 14:02.",
            "Incident opened at 14:05, linked to the timeline.",
            "Deploy 14:00 → errors 14:02 → incident 14:05 → rollback 14:15 → recovery 14:18.",
            "The 14:00 deploy introduced the regression.",
            "Roll back; add a canary stage.",
            "Postmortem references the timeline directly as evidence.",
        ),
        "success_metrics": [
            {"metric": "Time to identify the trigger", "target": "< 5 minutes", "how": "Measure from incident open to trigger identified on the timeline."},
            {"metric": "Postmortems citing the timeline", "target": "100%", "how": "Check writeups link the timeline as evidence."},
            {"metric": "Change-to-incident correlation found", "target": "> 80%", "how": "Track how often a change is linked on the timeline."},
        ],
    },
    "recommendations": {
        "problem": {
            "without": "Without Recommendations, teams know something is wrong but waste precious minutes debating what to actually do — often choosing the riskiest option under pressure.",
            "with": "With Recommendations, the platform proposes ranked, risk-scored fixes with a confidence level, so responders pick the safest effective action quickly.",
            "summary": "Recommendations turn raw diagnosis into a clear, ranked menu of safe next actions.",
        },
        "outcomes": [
            {"metric": "Faster decisions under pressure", "detail": "A ranked list removes debate during the worst moments."},
            {"metric": "Safer remediations", "detail": "Risk and blast-radius scoring steers teams away from dangerous fixes."},
            {"metric": "More consistent response quality", "detail": "Every responder gets expert-grade options."},
        ],
        "scenarios": [
            "You have a diagnosis but several possible fixes and limited time.",
            "A junior engineer is on-call and needs trustworthy options.",
            "You want to know the risk of an action before you take it.",
        ],
        "example": _ex(
            "Checkout fix options",
            "For the checkout incident, the platform ranks three fixes: roll back (High confidence, Low risk), raise the connection pool (Medium), and restart pods (Low). The responder picks the rollback.",
            "Checkout 5xx incident in progress.",
            "Incident shows a Recommendations tab with three ranked actions.",
            "Recommendations appear within a minute of incident open.",
            "Regression from the latest deploy.",
            "Roll back — Low risk, High confidence.",
            "Postmortem notes the recommendation was correct and fast.",
        ),
        "success_metrics": [
            {"metric": "Recommendation acceptance rate", "target": "> 70%", "how": "Track how often the top recommendation is chosen."},
            {"metric": "Time to first action", "target": "↓ 50%", "how": "Measure incident-open to first action taken."},
            {"metric": "Risk-related missteps", "target": "↓", "how": "Review actions flagged High risk that were taken anyway."},
        ],
    },
    "remediation": {
        "problem": {
            "without": "Without governed Remediation, fixes are applied by hand or by unchecked automation — with no record of who approved what, inviting both delay and dangerous surprises.",
            "with": "With Remediation, every action is approval-gated, bound to a specific target, and fully audited, so you act fast and safely with humans in the loop.",
            "summary": "Remediation is the safe execution layer: approve, bind, run, and record every incident action.",
        },
        "outcomes": [
            {"metric": "Safe time-to-fix", "detail": "Approved actions execute quickly without risky free-handing."},
            {"metric": "Full auditability", "detail": "Every approval and execution is recorded for compliance and learning."},
            {"metric": "Fewer self-inflicted outages", "detail": "Approval gates and binding stop wrong-target mistakes."},
        ],
        "scenarios": [
            "You chose a fix and need to execute it safely with a record.",
            "A high-risk action needs an explicit human approval before it runs.",
            "An auditor asks who approved a production change and when.",
        ],
        "example": _ex(
            "Approved checkout rollback",
            "The rollback for checkout is promoted to a remediation action, bound to checkout-api, approved by the incident commander, executed, and its success recorded — all in the incident.",
            "Checkout 5xx incident.",
            "Rollback action pending approval in the Remediation tab.",
            "Recommended 14:06 → approved 14:07 → executed 14:08 → success 14:10.",
            "Deploy regression.",
            "Approve and execute the bound rollback.",
            "Postmortem shows the approval trail and clean execution.",
        ),
        "success_metrics": [
            {"metric": "Actions with recorded approval", "target": "100%", "how": "Audit executed actions for an approver and timestamp."},
            {"metric": "Time from approval to execution", "target": "< 2 minutes", "how": "Measure the approval-to-run gap."},
            {"metric": "Wrong-target executions", "target": "0", "how": "Review binding mismatches; should never occur."},
        ],
    },
    "postmortems": {
        "problem": {
            "without": "Without Postmortems, the same incidents recur because nobody captures what was learned, and writeups take days of manual effort nobody enjoys.",
            "with": "With Postmortems, the platform drafts a blameless writeup from the real timeline and actions, so learning is captured in minutes and actually acted on.",
            "summary": "Postmortems convert every incident into durable, blameless organizational learning and tracked follow-ups.",
        },
        "outcomes": [
            {"metric": "Reduce repeat incidents", "detail": "Tracked action items close the gaps that caused the incident."},
            {"metric": "Less writeup effort", "detail": "Auto-drafting from the timeline turns days into minutes."},
            {"metric": "Stronger reliability culture", "detail": "Blameless, consistent writeups build trust and learning."},
        ],
        "scenarios": [
            "An incident just closed and you need a writeup while details are fresh.",
            "Leadership wants assurance that lessons are captured and acted on.",
            "You want a searchable history of what has failed and why.",
        ],
        "example": _ex(
            "Checkout incident postmortem",
            "Minutes after the checkout incident closes, a draft postmortem is generated from the timeline and actions; the team adds two action items and assigns owners.",
            "Closed checkout 5xx incident.",
            "Incident marked resolved; postmortem draft generated.",
            "Incident 14:05–14:18; postmortem drafted 14:25.",
            "Deploy regression with no canary.",
            "Add a canary gate and a pre-deploy pool check.",
            "Two tracked action items assigned with due dates.",
        ),
        "success_metrics": [
            {"metric": "Incidents with a postmortem", "target": "100% of High+", "how": "Audit High/Critical incidents for a writeup."},
            {"metric": "Action-item completion", "target": "> 90% by due date", "how": "Track open vs closed action items."},
            {"metric": "Repeat incidents", "target": "↓ quarter over quarter", "how": "Compare root-cause signatures over time."},
        ],
    },
    "service-health": {
        "problem": {
            "without": "Without Service Health, leaders cannot answer 'which services are at risk?' and teams find out a service is fragile only after it breaks.",
            "with": "With Service Health, every service carries a clear, trend-aware health score so risk is visible and addressed before it becomes an outage.",
            "summary": "Service Health is the at-a-glance reliability scorecard for every service you own.",
        },
        "outcomes": [
            {"metric": "Proactively reduce outages", "detail": "Declining health is fixed before it fails."},
            {"metric": "Clear ownership of risk", "detail": "Each service's health has an owner and a trend."},
            {"metric": "Better prioritization", "detail": "Engineering effort flows to the riskiest services first."},
        ],
        "scenarios": [
            "You need to know which services are degrading right now.",
            "You are planning the quarter and want to invest in the weakest services.",
            "An exec asks for a portfolio view of reliability risk.",
        ],
        "example": _ex(
            "Checkout health decline",
            "Checkout's health score drifts from 88 to 71 over a week as error rate and latency creep up; the team investigates before it becomes an incident.",
            "Health score dropping with rising latency.",
            "No incident yet — caught proactively from the health trend.",
            "Gradual 7-day decline in the health trend.",
            "A slow memory leak after a recent release.",
            "Patch the leak and add a memory alert.",
            "Captured as a near-miss with a preventive action.",
        ),
        "success_metrics": [
            {"metric": "Services in healthy band", "target": "> 90%", "how": "Track the share of services scoring Healthy."},
            {"metric": "Issues caught before incident", "target": "↑", "how": "Count near-misses found from health trends."},
            {"metric": "Time at-risk", "target": "↓", "how": "Measure how long services stay in the red/amber bands."},
        ],
    },
    "slos": {
        "problem": {
            "without": "Without SLOs and error budgets, 'reliable enough' is an argument, and teams either over-invest in gold-plating or ship recklessly until something breaks.",
            "with": "With SLOs and error budgets, reliability becomes a shared number that tells you exactly when to ship faster and when to slow down.",
            "summary": "SLOs turn reliability into an objective budget that aligns product speed with customer trust.",
        },
        "outcomes": [
            {"metric": "Balance speed and reliability", "detail": "Error budgets make the trade-off explicit and data-driven."},
            {"metric": "Fewer reliability surprises", "detail": "Burning budget warns you before customers feel it."},
            {"metric": "Aligned engineering and product", "detail": "One number replaces endless 'is it reliable enough' debates."},
        ],
        "scenarios": [
            "You need to decide whether it is safe to ship a risky change this week.",
            "You want to set a clear reliability target customers can trust.",
            "Leadership wants to track reliability as a first-class metric.",
        ],
        "example": _ex(
            "Checkout error budget",
            "Checkout's 99.9% SLO has burned 60% of its monthly budget after the incident; the team pauses risky changes until the budget recovers.",
            "Error-budget burn alert at 60%.",
            "Linked to the recent checkout incident.",
            "Budget healthy → incident → 60% burned in one event.",
            "A single deploy regression consumed most of the budget.",
            "Freeze risky checkout changes; focus on reliability.",
            "Postmortem ties the burn to the deploy gap.",
        ),
        "success_metrics": [
            {"metric": "Critical services with an SLO", "target": "100%", "how": "Audit tier-1 services for a defined SLO."},
            {"metric": "SLOs met", "target": "> 95% of months", "how": "Track monthly SLO attainment."},
            {"metric": "Budget-driven decisions", "target": "↑", "how": "Count change decisions made from budget state."},
        ],
    },
    "dependencies": {
        "problem": {
            "without": "Without a Dependency Graph, a failure in one service cascades into a mystery outage, and nobody knows the blast radius of a change until it is too late.",
            "with": "With the Dependency Graph, you see how services connect, so you can predict blast radius and trace failures to their source instantly.",
            "summary": "The Dependency Graph is the live map of how your system actually fits together.",
        },
        "outcomes": [
            {"metric": "Faster blast-radius analysis", "detail": "See instantly what a change or failure can affect."},
            {"metric": "Quicker root-cause tracing", "detail": "Follow the graph from symptom to source."},
            {"metric": "Safer architecture decisions", "detail": "Understand coupling before you change it."},
        ],
        "scenarios": [
            "You are about to change a shared service and need its blast radius.",
            "An outage is cascading and you need to find the origin.",
            "You are onboarding and want to understand how the system connects.",
        ],
        "example": _ex(
            "Checkout dependency cascade",
            "When the database degrades, the graph shows checkout, cart, and orders all depend on it — explaining the multi-service symptoms from a single root.",
            "Multiple services alerting at once.",
            "One incident grouping the related service alerts.",
            "DB degraded → checkout, cart, orders alert within a minute.",
            "Shared database connection saturation.",
            "Stabilize the database; the dependents recover.",
            "Postmortem flags the shared-DB coupling as a risk.",
        ),
        "success_metrics": [
            {"metric": "Services mapped in the graph", "target": "> 95%", "how": "Compare graph coverage to your service inventory."},
            {"metric": "Blast-radius checks before changes", "target": "↑", "how": "Track pre-change graph reviews."},
            {"metric": "Cascade incidents", "target": "↓", "how": "Count multi-service incidents traced to shared coupling."},
        ],
    },
    "capacity": {
        "problem": {
            "without": "Without Capacity Planning, teams either over-provision and burn cash, or under-provision and fall over during the next launch or seasonal spike.",
            "with": "With Capacity Planning, forecasts show exactly when you will run out of headroom, so you scale ahead of demand instead of during an outage.",
            "summary": "Capacity Planning forecasts demand so you scale on schedule, not in a panic.",
        },
        "outcomes": [
            {"metric": "Prevent saturation outages", "detail": "Scale before headroom runs out."},
            {"metric": "Avoid over-provisioning waste", "detail": "Right-size to forecasted demand."},
            {"metric": "Confident event readiness", "detail": "Enter launches and peak seasons with proven headroom."},
        ],
        "scenarios": [
            "A major launch or seasonal peak is coming and you must be ready.",
            "You want to right-size infrastructure to cut waste safely.",
            "You need to justify a scaling investment with a forecast.",
        ],
        "example": _ex(
            "Black Friday checkout capacity",
            "The forecast shows checkout will exceed 85% CPU two days before Black Friday; the team scales out a week early and sails through the peak.",
            "Forecast crossing the 85% utilization threshold.",
            "No incident — risk handled by planning.",
            "Forecast made 3 weeks out → scale 1 week out → smooth peak.",
            "Projected demand exceeding current headroom.",
            "Add capacity ahead of the event.",
            "Captured as a successful proactive scaling.",
        ),
        "success_metrics": [
            {"metric": "Capacity-related outages", "target": "0", "how": "Count incidents caused by saturation."},
            {"metric": "Utilization at peak", "target": "60–80%", "how": "Measure peak utilization against headroom targets."},
            {"metric": "Forecast accuracy", "target": "> 85%", "how": "Compare forecast to actual demand."},
        ],
    },
    "cost": {
        "problem": {
            "without": "Without Cost Optimization, cloud spend quietly balloons from idle resources and over-provisioning, and finance only notices on the invoice.",
            "with": "With Cost Optimization, safe, ranked savings are surfaced continuously, so you cut waste without risking reliability.",
            "summary": "Cost Optimization finds the money you are wasting and shows how to recover it safely.",
        },
        "outcomes": [
            {"metric": "Reduce cloud spend", "detail": "Capture ranked, low-risk savings every month."},
            {"metric": "No reliability trade-off", "detail": "Savings are risk-scored so you never cut into resilience."},
            {"metric": "Finance-engineering alignment", "detail": "One shared view of spend and savings."},
        ],
        "scenarios": [
            "Finance asks engineering to reduce cloud spend without breaking things.",
            "You suspect idle or oversized resources but cannot find them quickly.",
            "You want a monthly, repeatable cost-review ritual.",
        ],
        "example": _ex(
            "Idle checkout staging fleet",
            "Cost Optimization flags an oversized, mostly idle staging fleet behind checkout; right-sizing it saves 22% with no production risk.",
            "Idle-resource savings opportunity flagged.",
            "No incident — pure savings.",
            "Detected → reviewed → right-sized within a week.",
            "Staging fleet provisioned for a peak that never recurs.",
            "Right-size the staging fleet; Low risk.",
            "Logged as realized savings in the cost review.",
        ),
        "success_metrics": [
            {"metric": "Monthly savings captured", "target": "↑", "how": "Track realized savings from accepted recommendations."},
            {"metric": "Idle-resource spend", "target": "↓", "how": "Measure spend on low-utilization resources."},
            {"metric": "Savings without incidents", "target": "100%", "how": "Confirm no reliability impact from cost actions."},
        ],
    },
    "deployment-safety": {
        "problem": {
            "without": "Without Deployment Safety, every release is a gamble — risky changes ship straight to production and you learn they were bad from the resulting incident.",
            "with": "With Deployment Safety, each change gets a pre-deploy risk score and canary guidance, so risky releases are caught before customers are.",
            "summary": "Deployment Safety scores and gates releases so bad changes are stopped at the door.",
        },
        "outcomes": [
            {"metric": "Reduce change-failure rate", "detail": "Risky deploys are flagged and gated before release."},
            {"metric": "Smaller blast radius", "detail": "Canary guidance limits exposure of risky changes."},
            {"metric": "Faster safe delivery", "detail": "Low-risk changes ship confidently without ceremony."},
        ],
        "scenarios": [
            "You are about to ship a change and want to know how risky it is.",
            "You want to gate risky deploys automatically during budget burn.",
            "You need canary guidance for a sensitive service.",
        ],
        "example": _ex(
            "Risky checkout deploy gated",
            "A checkout change scores High risk due to a schema migration and low test coverage; Deployment Safety recommends a canary, catching a regression at 5% traffic.",
            "High deploy-risk score on the checkout change.",
            "No full incident — caught at canary.",
            "Risk scored pre-deploy → canary 5% → regression caught → halt.",
            "Schema migration regression.",
            "Canary first; fix forward before full rollout.",
            "Near-miss logged; coverage gap added as an action.",
        ),
        "success_metrics": [
            {"metric": "Change-failure rate", "target": "< 10%", "how": "Track deploys causing incidents."},
            {"metric": "Risky deploys caught at canary", "target": "↑", "how": "Count regressions stopped before full rollout."},
            {"metric": "Lead time for low-risk changes", "target": "↓", "how": "Measure delivery time for safe changes."},
        ],
    },
    "change-failure": {
        "problem": {
            "without": "Without Change Failure Prediction, you cannot tell a safe change from a dangerous one until it is already in production causing damage.",
            "with": "With Change Failure Prediction, each change carries a failure-likelihood score from history and context, so you focus review where it matters.",
            "summary": "Change Failure Prediction tells you which changes are likely to break before you ship them.",
        },
        "outcomes": [
            {"metric": "Reduce change-failure rate", "detail": "Predicted-risky changes get extra scrutiny."},
            {"metric": "Smarter review effort", "detail": "Reviewers focus on the changes most likely to fail."},
            {"metric": "Fewer deploy-caused incidents", "detail": "Risky changes are caught before release."},
        ],
        "scenarios": [
            "You want to prioritize code review on the riskiest changes.",
            "You need an objective risk signal for a change-approval gate.",
            "You are trending change-failure rate as a DORA metric.",
        ],
        "example": _ex(
            "High failure-likelihood change",
            "A checkout change scores 78% failure likelihood from past regressions in that module; the team adds tests and a canary, avoiding an incident.",
            "High predicted failure likelihood on the change.",
            "No incident — risk handled pre-merge.",
            "Predicted at PR → tests added → canary → safe rollout.",
            "Historically fragile module touched without coverage.",
            "Add tests and canary before merging.",
            "Captured as a prevented failure.",
        ),
        "success_metrics": [
            {"metric": "Change-failure rate (DORA)", "target": "Elite (< 15%)", "how": "Track the DORA change-failure metric."},
            {"metric": "Prediction accuracy", "target": "> 75%", "how": "Compare predicted vs actual failures."},
            {"metric": "Prevented failures", "target": "↑", "how": "Count high-risk changes fixed before release."},
        ],
    },
    "executive-reports": {
        "problem": {
            "without": "Without Executive Reports, leadership gets reliability updates as hand-built slide decks that are out of date the moment they are made — and never quite comparable.",
            "with": "With Executive Reports, a consistent, data-backed reliability narrative is generated on demand, so leaders make decisions from current facts.",
            "summary": "Executive Reports turn raw reliability data into a board-ready story in one click.",
        },
        "outcomes": [
            {"metric": "Save leadership prep time", "detail": "Reports generate in seconds instead of hours of slide-making."},
            {"metric": "Consistent, comparable reporting", "detail": "Every period uses the same trusted metrics."},
            {"metric": "Faster executive decisions", "detail": "Leaders act on current, credible reliability data."},
        ],
        "scenarios": [
            "A board or leadership meeting needs a reliability update.",
            "You want weekly, monthly, and quarterly reports without manual work.",
            "You need to show reliability, cost, and risk trends together.",
        ],
        "example": _ex(
            "Quarterly reliability report",
            "Ahead of the QBR, a quarterly report is generated showing reliability up 6 points, the checkout incident's impact, cost savings captured, and capacity readiness — exported to PDF.",
            "No alert — a scheduled reporting need.",
            "Summarizes the quarter's incidents including checkout.",
            "Quarter trend with the checkout incident annotated.",
            "Reliability gains tied to deploy-safety adoption.",
            "Continue canary rollout; invest in the weakest services.",
            "Incident learnings rolled into the executive narrative.",
        ),
        "success_metrics": [
            {"metric": "Report prep time", "target": "< 5 minutes", "how": "Compare to hours of manual slide-building."},
            {"metric": "Reporting cadence met", "target": "100%", "how": "Confirm each period's report is produced."},
            {"metric": "Decisions informed by reports", "target": "↑", "how": "Track leadership actions citing the report."},
        ],
    },
    "discovery": {
        "problem": {
            "without": "Without Infrastructure Discovery, your service inventory is a stale spreadsheet, and you cannot protect or reason about systems you do not even know exist.",
            "with": "With Infrastructure Discovery, connecting a provider automatically maps your services, resources, and topology, so everything else can build on an accurate picture.",
            "summary": "Infrastructure Discovery builds and maintains the accurate inventory every other capability depends on.",
        },
        "outcomes": [
            {"metric": "Eliminate inventory blind spots", "detail": "Auto-discovery finds services no spreadsheet tracked."},
            {"metric": "Faster onboarding to value", "detail": "Connect once and the platform maps everything."},
            {"metric": "Trustworthy foundation", "detail": "Accurate topology makes every other feature reliable."},
        ],
        "scenarios": [
            "You are setting up the platform and need your systems mapped.",
            "You suspect undocumented services and want a true inventory.",
            "You added a new cloud account and need it reflected automatically.",
        ],
        "example": _ex(
            "Discovering the checkout stack",
            "Connecting the cloud account discovers checkout-api, its database, cache, and queue, and maps their relationships — instantly revealing the real checkout topology.",
            "No alert — an onboarding discovery run.",
            "No incident — foundational setup.",
            "Connect → discover → map within minutes.",
            "Previously untracked cache and queue found.",
            "Map the new resources to the checkout service.",
            "Inventory accuracy improved for future incidents.",
        ),
        "success_metrics": [
            {"metric": "Inventory coverage", "target": "> 95%", "how": "Compare discovered vs known systems."},
            {"metric": "Time to first map", "target": "< 15 minutes", "how": "Measure connect-to-topology time."},
            {"metric": "Undocumented services found", "target": "↑ initially", "how": "Count newly discovered services."},
        ],
    },
    "ai-teams": {
        "problem": {
            "without": "Without AI Teams, every investigation and routine reliability task waits on scarce human experts, creating bottlenecks and burnout.",
            "with": "With AI Teams, specialized AI agents handle investigation, analysis, and routine reliability work under human oversight, multiplying your team's capacity.",
            "summary": "AI Teams give every engineer a squad of specialized agents that do the heavy lifting safely.",
        },
        "outcomes": [
            {"metric": "Multiply team capacity", "detail": "Agents handle routine analysis so humans focus on judgment."},
            {"metric": "Faster investigations", "detail": "Agents assemble context and hypotheses in parallel."},
            {"metric": "Reduce on-call burnout", "detail": "Less manual toil during incidents and reviews."},
        ],
        "scenarios": [
            "You want investigations accelerated without hiring more SREs.",
            "Routine reliability analysis is eating your team's time.",
            "You need expert-grade help available 24/7.",
        ],
        "example": _ex(
            "AI-assisted checkout investigation",
            "During the checkout incident, an investigation agent correlates alerts, deploys, and logs, proposes a root cause, and drafts the timeline while the human commander coordinates.",
            "Checkout 5xx incident.",
            "Agent attached to the incident for investigation.",
            "Agent works in parallel with the human responder.",
            "Deploy regression identified by the agent.",
            "Agent suggests rollback; human approves.",
            "Agent drafts the postmortem timeline.",
        ),
        "success_metrics": [
            {"metric": "Investigation time", "target": "↓ 40%", "how": "Compare agent-assisted vs manual investigations."},
            {"metric": "Toil hours saved", "target": "↑", "how": "Track routine tasks handled by agents."},
            {"metric": "Human-approved agent actions", "target": "100%", "how": "Confirm oversight on every agent action."},
        ],
    },
    "workflows": {
        "problem": {
            "without": "Without Workflows, response and reliability processes live in people's heads, so quality depends on who happens to be on-call that night.",
            "with": "With Workflows, your best processes are codified and automated with human checkpoints, so every response is consistent and high quality.",
            "summary": "Workflows turn tribal know-how into repeatable, governed automation.",
        },
        "outcomes": [
            {"metric": "Consistent response quality", "detail": "Every incident follows your proven process."},
            {"metric": "Faster routine operations", "detail": "Automation handles the repeatable steps."},
            {"metric": "Lower key-person risk", "detail": "Process no longer depends on one expert."},
        ],
        "scenarios": [
            "You want every incident handled with the same proven steps.",
            "Repetitive operational tasks should be automated safely.",
            "You need governed automation with human approval gates.",
        ],
        "example": _ex(
            "Checkout incident workflow",
            "A checkout incident triggers a workflow that pages on-call, opens the incident, attaches context, and requests rollback approval — consistent every time.",
            "Checkout 5xx alert triggers the workflow.",
            "Workflow opens and routes the incident automatically.",
            "Alert → page → incident → approval request in seconds.",
            "Deploy regression (handled by the standard path).",
            "Workflow proposes the standard rollback for approval.",
            "Postmortem confirms the process ran as designed.",
        ),
        "success_metrics": [
            {"metric": "Process adherence", "target": "> 95%", "how": "Track incidents handled via the workflow."},
            {"metric": "Manual steps automated", "target": "↑", "how": "Count steps moved into workflows."},
            {"metric": "Response-time variance", "target": "↓", "how": "Measure consistency across responders."},
        ],
    },
    "onboarding": {
        "problem": {
            "without": "Without guided Onboarding, new customers stall on setup, never connect their systems, and never reach the value they bought the platform for.",
            "with": "With Onboarding, a guided path connects your providers, discovers your systems, and produces first value in minutes — without contacting support.",
            "summary": "Onboarding is the guided on-ramp that gets a new customer from signup to first value fast.",
        },
        "outcomes": [
            {"metric": "Faster time to value", "detail": "Customers reach first insight in minutes, not weeks."},
            {"metric": "Higher activation", "detail": "More accounts complete setup and stay."},
            {"metric": "Fewer support tickets", "detail": "Self-service setup reduces onboarding friction."},
        ],
        "scenarios": [
            "You just signed up and want a clear path to first value.",
            "You are rolling the platform out to a new team.",
            "You want to connect providers without reading a manual.",
        ],
        "example": _ex(
            "First 15 minutes",
            "A new admin connects a cloud and a monitoring provider, discovery maps the checkout stack, and the first reliability score appears — all inside 15 minutes.",
            "No alert — initial setup.",
            "No incident — first-value setup.",
            "Connect → discover → first score within 15 minutes.",
            "Previously no inventory or baseline existed.",
            "Continue to monitoring and your first incident drill.",
            "Baseline captured for future comparison.",
        ),
        "success_metrics": [
            {"metric": "Time to first value", "target": "< 15 minutes", "how": "Measure signup to first reliability insight."},
            {"metric": "Setup completion rate", "target": "> 90%", "how": "Track accounts that finish onboarding."},
            {"metric": "Onboarding support tickets", "target": "↓", "how": "Count setup-related tickets per new account."},
        ],
    },
}
