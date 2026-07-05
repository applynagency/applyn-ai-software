"""Contract tests for the unified service abstractions.

These verify that the de-duplication refactor wired every formerly-duplicated
service family onto its shared base, and that the shared pure helpers behave as
the per-service copies used to. They are fast, import-only / pure-function tests;
the deep behavioural guarantees are covered by each family's existing suite
(test_backend_v1.py, test_executive_report.py, test_copilot.py, ...).
"""

import inspect

import pytest

from app.core.exceptions import NexoraException


# --------------------------------------------------------------------------- #
# Staged agent services (Backend / Frontend V1/V2/V3)                          #
# --------------------------------------------------------------------------- #
def test_staged_services_share_base_and_declare_config():
    from app.services._staged_agent import StagedAgentService
    from app.services.backend_v1 import BackendDeveloperV1Service
    from app.services.backend_v2 import BackendDeveloperV2Service
    from app.services.backend_v3 import BackendDeveloperV3Service
    from app.services.frontend_v1 import FrontendDeveloperV1Service
    from app.services.frontend_v2 import FrontendDeveloperV2Service
    from app.services.frontend_v3 import FrontendDeveloperV3Service

    expected = {
        BackendDeveloperV1Service: ("backend_v1", "backend_architect_run_id"),
        BackendDeveloperV2Service: ("backend_v2", "backend_v1_run_id"),
        BackendDeveloperV3Service: ("backend_v3", "backend_v2_run_id"),
        FrontendDeveloperV1Service: ("frontend_v1", "frontend_architect_run_id"),
        FrontendDeveloperV2Service: ("frontend_v2", "frontend_v1_run_id"),
        FrontendDeveloperV3Service: ("frontend_v3", "frontend_v2_run_id"),
    }
    for service_cls, (stage, prev_field) in expected.items():
        assert issubclass(service_cls, StagedAgentService)
        cfg = service_cls.config
        assert cfg.stage == stage
        assert cfg.resource_type == f"{stage}_run"
        assert cfg.previous.run_id_field == prev_field
        # The class name (a public contract used by routes/tests) is preserved.
        assert service_cls.__name__.endswith("Service")


def test_staged_service_logic_lives_only_in_the_base():
    """The concrete modules must not re-declare the shared orchestration."""
    import app.services.backend_v1 as mod

    # execute_internal / run / get_run etc. are inherited, not redefined.
    assert "def execute_internal" not in inspect.getsource(mod)
    assert "def _resolve_previous_output" not in inspect.getsource(mod)


# --------------------------------------------------------------------------- #
# Shared CRUD repositories                                                     #
# --------------------------------------------------------------------------- #
def test_staged_repositories_share_crud_mixins():
    from app.repositories._staged import StagedArtifactRepository, StagedRunRepository
    from app.repositories.backend_v1 import (
        BackendV1ArtifactRepository,
        BackendV1RunRepository,
    )
    from app.repositories.frontend_v3 import (
        FrontendV3ArtifactRepository,
        FrontendV3RunRepository,
    )

    for run_repo in (BackendV1RunRepository, FrontendV3RunRepository):
        assert issubclass(run_repo, StagedRunRepository)
        for method in ("get_with_artifact", "list_by_requirement", "list_by_organization"):
            assert hasattr(run_repo, method)

    for art_repo in (BackendV1ArtifactRepository, FrontendV3ArtifactRepository):
        assert issubclass(art_repo, StagedArtifactRepository)
        assert art_repo.run_model is not None
        # get_run_for_org is now available on every staged artifact repo.
        assert hasattr(art_repo, "get_run_for_org")


# --------------------------------------------------------------------------- #
# Reporting services                                                          #
# --------------------------------------------------------------------------- #
def test_report_services_share_base():
    from app.services._reporting import ReportingServiceBase
    from app.services.executive_report import ExecutiveReportingService

    assert issubclass(ExecutiveReportingService, ReportingServiceBase)


def test_build_export_formats():
    from app.services._reporting import build_export

    md = "# Title\n\nbody"
    # PDF (default)
    content, media_type, filename = build_export(
        md, None, title="T", filename_prefix="rep", tag="monthly-20260101"
    )
    assert isinstance(content, bytes)
    assert media_type == "application/pdf"
    assert filename == "rep-monthly-20260101.pdf"

    # HTML
    content, media_type, filename = build_export(
        md, "html", title="T", filename_prefix="rep", tag="t"
    )
    assert media_type == "text/html"
    assert filename == "rep-t.html"
    assert isinstance(content, bytes)

    # Markdown (both aliases)
    for fmt in ("markdown", "md"):
        content, media_type, filename = build_export(
            md, fmt, title="T", filename_prefix="rep", tag="t"
        )
        assert media_type == "text/markdown"
        assert content == md.encode("utf-8")

    # Unsupported
    with pytest.raises(NexoraException):
        build_export(md, "xlsx", title="T", filename_prefix="rep", tag="t")


# --------------------------------------------------------------------------- #
# Copilot — one unified surface                                               #
# --------------------------------------------------------------------------- #
def test_single_copilot_surface():
    # Reliability + SRE + Grounded copilots converged into one engine. The
    # deterministic retrieval engine is an internal evidence provider inside the
    # grounded_copilot package, reused via gather_evidence; it has no API or
    # persistence of its own and no legacy service names remain.
    from app.services.grounded_copilot.engine import GroundedCopilotEngine
    from app.services.grounded_copilot.evidence import EvidenceProvider

    assert hasattr(EvidenceProvider, "gather_evidence")
    assert hasattr(GroundedCopilotEngine, "chat")


# --------------------------------------------------------------------------- #
# Generic workflow engine dispatch                                            #
# --------------------------------------------------------------------------- #
def test_dispatcher_uses_generic_helper():
    from app.workflows.dispatcher import AgentDispatcher

    assert hasattr(AgentDispatcher, "_dispatch_via_execute_internal")

    # Each migrated wrapper delegates to the generic helper instead of carrying
    # its own copy of the load/execute/translate flow.
    for name in (
        "_dispatch_business_analyst",
        "_dispatch_backend_architect",
        "_dispatch_backend_v1",
        "_dispatch_backend_v2",
        "_dispatch_backend_v3",
        "_dispatch_frontend_architect",
        "_dispatch_frontend_v1",
        "_dispatch_frontend_v2",
        "_dispatch_frontend_v3",
        "_dispatch_uiux_designer",
    ):
        src = inspect.getsource(getattr(AgentDispatcher, name))
        assert "_dispatch_via_execute_internal" in src
        # The duplicated bodies are gone (no inline requirement/project lookups).
        assert "workspace_repo = WorkspaceRepository(session)" not in src
