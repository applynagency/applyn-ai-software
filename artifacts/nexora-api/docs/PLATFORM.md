# Nexora — Engineering Operations Platform

Nexora is a **single, unified Engineering Operations Platform**. It brings the
full software lifecycle — from idea to production to incident response — under
one product, one brand, one navigation model, and one set of terms.

There is no separate consumer product and no second brand. Everything described
below runs on the same projects, services, organizations, and data.

> **Brand:** Nexora · **Positioning:** Engineering Operations Platform
> (defined once in code as `BRAND` in `static/app.js`).

---

## The seven modules

The platform is organized into seven product **modules**. Each module is a group
in the left navigation and maps to a coherent set of capabilities. The modules
are the canonical top-level vocabulary — features live *inside* a module, never
floating on their own.

The module catalog is defined once in `static/app.js` as `PLATFORM_MODULES` and
is reused by navigation, onboarding, and this document so terminology never
drifts.

| Module | What it does | Key destinations |
| --- | --- | --- |
| **AI Software Factory** | Describe an idea and let AI teams generate, test, and ship production software. | Applications (incl. Builds, Deployments, Releases, Change Requests), AI Tools |
| **AI Teams** | Compose and orchestrate the AI agents and workflows that build your software. | AI Teams, Workflows |
| **DevOps** | Ship safely and plan ahead. | Deployment Safety, Change Failure Prediction, Capacity Planning, Cost Optimization |
| **Observability** | See system state in real time. | Monitoring, Service Health |
| **Reliability** | Track reliability posture and reporting. | Reliability Dashboard, Maturity Score, Runbooks, Copilot, Executive Reports |
| **Incidents** | Detect, collaborate on, and resolve incidents. | Incidents, War Room |
| **Knowledge Graph** | Map services, dependencies, and architecture. | Architecture Map, Service Dependencies, Discovery |

Two non-module groups round out the navigation:

- **Platform** — cross-cutting setup and account: Integrations, Setup Wizard,
  Organization, Settings.
- **Help** — the Help Center.

Owner-role users additionally see a **Developer Tools** group (Teams, Workflows,
Execution Logs, AI Agents, Approvals, Admin: Organizations). This is unchanged.

---

## Unified navigation

Navigation is driven by a single declarative structure, `NAV_GROUPS` in
`static/app.js`. Each group carries a `module` id linking it to
`PLATFORM_MODULES`. The unification **only regrouped and relabeled** items — no
route was added or removed, so every page that was reachable before is still
reachable. See the migration guide for the full before/after map.

---

## Unified onboarding

First-time users land on a dashboard that:

1. Pitches the platform with one hero ("Nexora · Engineering Operations Platform").
2. Walks the **Get Started in 4 Steps** checklist (idea → live, maintained app).
3. Introduces the platform with **"One platform, seven modules"**
   (`renderPlatformModules()`), so newcomers immediately learn the vocabulary.

The Setup Wizard (`/onboarding`, under the **Platform** group) handles deeper
configuration (integrations, discovery).

---

## Consistent terminology

Use these terms consistently in UI copy, docs, and support content:

| Term | Meaning |
| --- | --- |
| **Platform** | The whole product: Nexora. |
| **Module** | One of the seven top-level product areas (e.g. "Reliability"). |
| **Application** | A customer software project built and run on the platform. |
| **AI Team** | A composed set of AI agents that build software. |
| **Workflow** | An orchestrated sequence executed by an AI Team. |
| **Service** | A running component tracked for health, dependencies, and reliability. |
| **Incident** | A tracked disruption, coordinated in the War Room. |
| **War Room** | The collaborative incident-response space (previously "AI War Room"). |
| **Reliability Dashboard** | The reliability posture overview (previously "Executive Dashboard"). |
| **Copilot** | The single grounded AI assistant (`/v1/copilot`). |

Avoid: "APPYLN", "customer platform", "software lifecycle platform" as a product
name. These referred to the old separately-branded surface and have been retired.

---

## Where things live in code

| Concern | Location |
| --- | --- |
| Brand (name, tagline, logo) | `BRAND` in `static/app.js` |
| Module catalog | `PLATFORM_MODULES` in `static/app.js` |
| Navigation | `NAV_GROUPS` in `static/app.js` |
| Onboarding modules panel | `renderPlatformModules()` in `static/app.js` |
| Page title / meta | `static/index.html` |

See [`MIGRATION_UNIFIED_PLATFORM.md`](./MIGRATION_UNIFIED_PLATFORM.md) for how the
previous experience maps onto the unified platform.
