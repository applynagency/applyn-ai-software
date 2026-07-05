# Service Unification Architecture

This document describes the shared abstractions introduced to remove large-scale
duplication across the backend service layer, and the rules for extending them.

The refactor is a **pure de-duplication**: every public class name, constructor
signature, method signature, audit action, error string, HTTP behaviour and
workflow-dispatch contract is preserved. No migrations, no API changes. The
existing per-family test suites (≈90 files for the staged agents alone) act as
the regression guarantee and continue to pass unchanged.

## Overview

| Area (as requested)        | Before                                              | After                                                                 |
| -------------------------- | --------------------------------------------------- | --------------------------------------------------------------------- |
| Backend V1/V2/V3 services  | 3 × ~313 lines, ~95% identical                      | 3 thin configs over `StagedAgentService`                              |
| Frontend V1/V2/V3 services | 3 × ~312 lines, ~95% identical                      | 3 thin configs over `StagedAgentService`                             |
| Shared CRUD                | run/artifact query bodies copied per family         | `StagedRunRepository` / `StagedArtifactRepository` mixins             |
| Reports                    | exec + leadership repeat RBAC / export / validation | single Executive reporting engine (Leadership removed, see note)      |
| Copilots                   | reliability + SRE + grounded ran in parallel        | single Copilot at `/v1/copilot` (see note)                           |
| Generic workflow engine    | ~31 near-identical `_dispatch_*` methods            | `AgentDispatcher._dispatch_via_execute_internal()` + thin wrappers    |

Net effect: ~1,600 lines of copy-paste collapsed into ~600 lines of shared,
single-source-of-truth code, with the per-family files reduced to declarations.

> **Sprint 60B convergence note.** The earlier de-duplication kept parallel
> implementations behind shared base classes. Sprint 60B retired those parallels
> outright:
> - **Reporting** — Leadership Reports (service, model, repository, schema,
>   router, scheduled job) was deleted. Executive Reports is the single reporting engine.
> - **Copilot** — SRE Copilot and the standalone Reliability Copilot session
>   stores were deleted. There is now one Copilot exposed at `/v1/copilot`
>   (Grounded engine); `app/services/grounded_copilot/evidence.py` is an internal
>   `EvidenceProvider` consumed by it. `COPILOT_ENABLED` was removed.
> - **Onboarding** — Infrastructure Onboarding (wizard model/service/routes/
>   schema/tests) was folded into the main onboarding
>   wizard, which now provisions a default SRE team and can generate a sample
>   incident.
> - **Discovery** — the legacy infrastructure-discovery system
>   (`InfrastructureDiscoveryService`, `DiscoveryPipelineService`,
>   `DiscoveryResource`/`InfrastructureDiscovery`/`DiscoveryChangeEvent` models,
>   their repositories/schemas/routes/tests, the `run_discovery`/`cron_discovery`
>   jobs, the `discovery_loop`, and `DISCOVERY_PIPELINE_ENABLED`) was deleted.
>   **Universal Discovery** (`UniversalDiscoveryService`) is the single discovery
>   engine: the inventory is `DiscoveredAsset` and the graph is
>   `KnowledgeGraphNode`/`KnowledgeGraphEdge`. The API is one family at
>   `/v1/discovery/*` (no `/universal` segment). Migration
>   `0012_converge_discovery` migrates legacy `discovery_resources` into
>   `discovered_assets` and drops the obsolete tables.
> - **Graph (Sprint 60D)** — the legacy service-dependency graph
>   (`ServiceDependency` model + repository and the bespoke in-memory `_Graph`
>   traversal that ~7 services each rebuilt) was deleted. There is now exactly
>   **one graph**: the Platform Knowledge Graph
>   (`KnowledgeGraphNode`/`KnowledgeGraphEdge`). Service-topology edges live in it
>   keyed by `service:<id>` node keys with the dependency type on
>   `relationship_type`. All traversal (BFS/DFS, upstream/downstream, shortest
>   path, impact/blast radius, critical path) is centralized in one engine,
>   `app/services/graph.py` (`GraphService` + `GraphAdjacency`); every consumer
>   (dependency API, blast-radius, war room, reliability dashboard, change
>   failure, architecture, copilot evidence + KG grounder, onboarding detection,
>   demo seeding) reads through it. **Universal Discovery is the sole graph
>   writer** (`add_service_dependency`/`remove_service_dependency`/
>   `_ensure_service_node`); its inventory rebuild preserves the curated
>   `service:` layer. Migration `0013_converge_graph` converts every
>   `ServiceDependency` edge into a `KnowledgeGraphEdge` (preserving ids),
>   projects the service nodes, and drops `service_dependencies`.
>
> Sections 3 and 4 below describe the current single-engine state after this
> convergence.

## 1. Staged agent services

**Module:** `app/services/_staged_agent.py`

Every "run an agent against the previous stage's artifact" service (Backend and
Frontend Developer V1/V2/V3) shared an identical orchestration:

1. resolve the previous stage's latest *completed* artifact,
2. create a run row + audit `*_started`,
3. flip to `RUNNING`,
4. invoke the agent,
5. validate; on failure audit `*_validated` (failure) + `*_failed` and commit,
6. persist the artifact, mark `COMPLETED`, audit `*_completed`.

Only **names and labels** differ between stages. They are captured declaratively:

```python
class StageConfig:        # what this stage is
    stage, self_label, run_status_enum, run_repo_cls, artifact_repo_cls,
    response_cls, artifact_response_cls, list_response_cls, artifact_model_name,
    agent_cls, validator_cls, prompt_builder_cls, to_markdown, get_run_for_org,
    previous: PreviousStageConfig

class PreviousStageConfig: # what feeds this stage
    label, model_name, repo_cls, status_enum, run_id_field, agent_output_kwarg
```

`StagedAgentService` implements `run`, `execute_internal`, `get_run`,
`get_artifact`, `list_by_requirement`, `list_for_organization`,
`_to_response`, `_resolve_previous_output` and `_ensure_write` once. A concrete
service is now:

```python
class BackendDeveloperV1Service(StagedAgentService):
    config = BACKEND_V1_CONFIG
```

### Why the module-level symbols are kept

Tests patch the agent on the **service module**, e.g.
`patch("app.services.backend_v1.BackendDeveloperV1Agent.run", ...)`. Because the
agent class is still imported into `app/services/backend_v1.py` (and referenced
via `config.agent_cls`, which *is* that same class object), the patch resolves
and applies exactly as before. This is why each thin module re-imports its
agent/validator/prompt-builder/markdown symbols rather than hiding them in the
base.

### Behavioural fidelity

`execute_internal` is reproduced line-for-line: same audit-action ordering, the
same single `session.commit()` in the validation-failure path (and *not* in the
`AgentError` path), the same f-string error messages
(`"Backend Developer V1 output failed validation (score: N)"`), and the same
return shape `(run, artifact_payload)`.

### Adding a new staged stage

1. Build a `StageConfig` (+`PreviousStageConfig`) in a new
   `app/services/<stage>.py`, importing the stage's agent/validator/etc.
2. `class XxxService(StagedAgentService): config = XXX_CONFIG`.
3. Add a thin dispatcher wrapper (see §5).

## 2. Shared CRUD

**Module:** `app/repositories/_staged.py`

`StagedRunRepository[Model]` provides `get_with_artifact`,
`list_by_requirement`, `list_by_organization` (artifact eager-loading + the
standard ordering/counting). `StagedArtifactRepository[Model]` provides
`get_for_org` and `get_run_for_org` (org-scoping joined through the owning run;
set `run_model` on the subclass).

These build on the existing generic `BaseRepository` and assume the project's
conventional schema (`artifacts` relationship; `requirement_id`,
`organization_id`, `created_at` columns; artifact `run_id` FK). The six V-stage
repositories are now five-line subclasses:

```python
class BackendV1RunRepository(StagedRunRepository[BackendV1Run]):
    def __init__(self, session): super().__init__(BackendV1Run, session)

class BackendV1ArtifactRepository(StagedArtifactRepository[BackendV1Artifact]):
    run_model = BackendV1Run
    def __init__(self, session): super().__init__(BackendV1Artifact, session)
```

> Note: `get_run_for_org` is now available on *every* staged artifact repo
> (previously only some defined it). Adding a method is backward-compatible.

## 3. Reports

**Module:** `app/services/_reporting.py`

- `ReportingServiceBase` — shared `_ensure_read` / `_ensure_write` RBAC, the
  read-only `ReliabilityDashboardService` wiring, the audit repo, and a
  `_normalize_choice(value, default, allowed, error_message)` validator that
  backs both `_normalize_type` (executive: WEEKLY/MONTHLY/QUARTERLY) and
  `_normalize_cadence` (leadership: WEEKLY/MONTHLY).
- `build_export(markdown, fmt, *, title, filename_prefix, tag)` — the identical
  PDF / HTML / Markdown switch both services used, returning
  `(content, media_type, filename)` and raising `NexoraException` on unsupported
  formats.

`ExecutiveReportingService` is the single reporting engine; it owns report
section building, trend analysis, action plans and markdown rendering on top of
the shared export boilerplate. (Leadership Reports was removed in Sprint 60B.)

## 4. Copilot

**Module:** `app/services/grounded_copilot/`

There is exactly one Copilot, exposed at `/v1/copilot` by
`GroundedCopilotEngine`. It composes an LLM, RAG retrieval, the knowledge graph,
and a deterministic, read-only `EvidenceProvider`
(`app/services/grounded_copilot/evidence.py`) used as a grounded tool and as the
War Room's evidence source via `gather_evidence`. The former Reliability Copilot
and SRE Copilot — including their separate routers, services, models,
repositories, schemas and session stores — were deleted in Sprint 60B; no
legacy copilot service names remain.

## 5. Generic workflow engine

**Module:** `app/workflows/dispatcher.py`

`AgentDispatcher._dispatch_via_execute_internal(*, service_cls, label, ...)`
holds the once-per-agent flow that ~30 `_dispatch_*` methods duplicated:

1. resolve requirement → project → workspace (with the standard not-found
   results),
2. `service.execute_internal(organization_id, project_id, requirement_id,
   requirement_content, user)`,
3. translate to `AgentDispatchResult` (`completed` with tokens/score log,
   `AgentError` → failed, `ValidationError` → failed), using `label` for the log
   strings.

The ten staged-agent dispatchers (Business Analyst, Backend & Frontend
Architects, Backend & Frontend Developer V1/V2/V3, UI/UX Designer) are now thin
wrappers:

```python
async def _dispatch_backend_v1(self, *, requirement_content, session, requirement_id, user):
    from app.services.backend_v1 import BackendDeveloperV1Service
    return await self._dispatch_via_execute_internal(
        requirement_content=requirement_content, session=session,
        requirement_id=requirement_id, user=user,
        service_cls=BackendDeveloperV1Service, label="Backend Developer V1",
    )
```

The lazy in-method import (to avoid import cycles) and the public method
name/signature are preserved, so `dispatch_internal`'s routing table is
unchanged. Dispatchers that deviate from the template (code-review, execution,
QA/infra/SRE approvals, product owner, deployment, fullstack assembly) were
intentionally **not** migrated, because their success-log wording or persistence
differs; forcing them through the generic helper would change behaviour.

The dispatcher shrank from 2,485 to 2,056 lines.

## Testing

- **Contract tests:** `app/tests/test_service_unification.py` asserts the
  inheritance wiring, config values, the `build_export` matrix, and that the
  duplicated bodies are gone (delegation only).
- **Regression:** the pre-existing per-family suites are the real guarantee and
  pass unchanged — backend V1/V2/V3 + frontend V1/V2/V3 (384), copilots (31),
  reports (20/21¹), dispatcher/workflow (144).

¹ `test_leadership_report.py::test_run_due_generates_and_advances` fails in the
local Python 3.12 environment due to SQLite not round-tripping
`DateTime(timezone=True)` as timezone-aware (the test compares a naive vs aware
datetime). This is pre-existing and independent of the refactor — it fails
identically with the original `_now()` implementation.

## Design principles

- **Declarative over imperative:** stages/reports/copilots describe *what* they
  are; the shared base decides *how*.
- **Preserve patch surfaces:** keep module-level symbols where tests or callers
  reach for them.
- **Behaviour-identical or don't migrate:** anything whose strings, ordering or
  side effects differ stays hand-written rather than being shoe-horned into a
  generic path.
