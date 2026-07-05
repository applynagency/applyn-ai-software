# Migration Guide — Unified Engineering Operations Platform

This release unifies the product into **one** Engineering Operations Platform:
**Nexora**. The previously separate **APPYLN** consumer brand is retired, and the
navigation is reorganized around seven product modules.

**Nothing was removed.** Every route, page, API, and capability that existed
before still exists. This is a branding + information-architecture change, not a
functional one.

---

## 1. Branding: APPYLN → Nexora

| Before | After |
| --- | --- |
| Product name "APPYLN" | **Nexora** |
| Tagline "Build software with AI" | **Engineering Operations Platform** |
| Auth screen "APPYLN Platform / Customer software lifecycle platform" | **Nexora / Engineering Operations Platform** |
| Page title `APPYLN Platform` | `Nexora — Engineering Operations Platform` |
| Logo glyph `A` | `N` |

All brand text now comes from a single `BRAND` constant in `static/app.js`, so
there is one source of truth and no duplicate branding.

**Action for you:** none. The change is cosmetic. If you have external links to
`/` or any page, they continue to work.

---

## 2. Navigation: grouped into seven modules

The sidebar is now organized by product module. **All destinations are the same
URLs**; only their grouping and a few labels changed.

| Page / Route | Before (group) | After (module) | Label change |
| --- | --- | --- | --- |
| `/` Dashboard | (top) | (top) | — |
| `/applications` | Software Delivery | **AI Software Factory** | — |
| `/ai-tools` | Software Delivery | **AI Software Factory** | — |
| `/ai-teams` | Software Delivery | **AI Teams** | — |
| `/ai-team-workflows` | Software Delivery | **AI Teams** | — |
| `/deployment-safety` | Reliability & SRE | **DevOps** | — |
| `/change-failure` | Reliability & SRE | **DevOps** | — |
| `/capacity` | Planning | **DevOps** | — |
| `/cost-optimization` | Planning | **DevOps** | — |
| `/monitoring` | Reliability & SRE | **Observability** | — |
| `/services` | Reliability & SRE | **Observability** | — |
| `/reliability-dashboard` | Executive | **Reliability** | "Executive Dashboard" → "Reliability Dashboard" |
| `/reliability-maturity` | Executive | **Reliability** | — |
| `/runbooks` | Reliability & SRE | **Reliability** | — |
| `/copilot` | AI Copilots | **Reliability** | single unified Copilot (`/v1/copilot`) |
| `/executive-reports` | Executive | **Reliability** | — |
| `/incidents` | Reliability & SRE | **Incidents** | — |
| `/war-rooms` | Executive | **Incidents** | "AI War Room" → "War Room" |
| `/sre-copilot` | AI Copilots | **Reliability** | merged into the unified Copilot (`/copilot`) |
| `/architecture` | Executive | **Knowledge Graph** | — |
| `/dependencies` | Reliability & SRE | **Knowledge Graph** | — |
| `/discovery` | Setup | **Knowledge Graph** | — |
| `/integrations` | Setup | **Platform** | — |
| `/onboarding` | Setup | **Platform** | — |
| `/organization` | Account | **Platform** | — |
| `/settings` | Account | **Platform** | — |
| `/help` | Help | **Help** | — |

Retired group names: **Software Delivery, Reliability & SRE, Planning, AI
Copilots, Executive, Setup, Account**. Their items moved into the modules above.

The **Developer Tools** group (Owner-only: `/teams`, `/workflows`,
`/workflow-executions`, `/agents`, `/approvals`, `/organizations`) is unchanged.

> **Lifecycle pages** (`/builds`, `/deployments`, `/releases`,
> `/change-requests`) remain deep-link routes surfaced under **Applications**, as
> before — they are not separate top-level nav items.

---

## 3. Terminology updates

| Old term | New term |
| --- | --- |
| APPYLN | Nexora |
| "Executive Dashboard" | "Reliability Dashboard" |
| "AI War Room" | "War Room" |
| "customer platform" / "software lifecycle platform" (as a name) | "Engineering Operations Platform" |

The full glossary lives in [`PLATFORM.md`](./PLATFORM.md#consistent-terminology).

---

## 4. What did NOT change

- Every URL/route resolves exactly as before (command palette, search, deep
  links, bookmarks).
- All APIs, data models, permissions, and Owner-only Developer Tools.
- Asset cache version bumped (`?v=88`) so clients pick up the new bundle.

---

## 5. Rollout checklist

- [x] Single `BRAND` source of truth; APPYLN removed from app shell.
- [x] `NAV_GROUPS` regrouped into seven modules + Platform/Help.
- [x] `PLATFORM_MODULES` catalog added and surfaced in onboarding.
- [x] Platform overview (`PLATFORM.md`) and this migration guide published.
- [x] Asset version bumped in `index.html`.
- [ ] Update any external screenshots / marketing that still show "APPYLN".
