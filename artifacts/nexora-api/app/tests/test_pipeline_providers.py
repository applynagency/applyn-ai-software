"""Unit tests for Buildkite, Harness, and Flux pipeline/GitOps providers."""

from app.delivery.gitops import flux_live
from app.delivery.pipelines.buildkite_live import BuildkiteProvider
from app.delivery.pipelines.harness_live import HarnessProvider
from app.delivery.pipelines.registry import get_pipeline_provider
from app.delivery.types import PipelineProviderType
from app.services.enterprise_enrichment import mutate_provider, summarize_provider


def test_buildkite_provider_empty_secret():
    impl = BuildkiteProvider()
    assert impl.list_pipelines({}) == []
    assert impl.list_runs({}, "my-pipeline") == []


def test_harness_provider_empty_secret():
    impl = HarnessProvider()
    assert impl.list_pipelines({}) == []
    assert impl.list_runs({}, "deploy") == []


def test_registry_has_buildkite_harness():
    assert get_pipeline_provider(PipelineProviderType.BUILDKITE).provider == "BUILDKITE"
    assert get_pipeline_provider(PipelineProviderType.HARNESS).provider == "HARNESS"


def test_flux_live_no_kubeconfig():
    assert flux_live.list_applications({}) == []


def test_enterprise_summarize_unavailable():
    row = summarize_provider("SERVICENOW", {})
    assert row["available"] is False


def test_enterprise_mutate_unsupported():
    result = mutate_provider("SPLUNK", {}, "acknowledge_incident", "x")
    assert result["status"] == "failed"


def test_enterprise_mutate_trigger_search_missing_creds():
    result = mutate_provider("SPLUNK", {}, "trigger_search", "my-search")
    assert result["status"] == "failed"
    assert "missing" in result["reason"]
