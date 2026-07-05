"""Coverage tests — all 35 marketplace integrations have live-data paths."""

import pytest

from app.services.integration_capabilities import (
    PIPELINE_INTEGRATION_KEYS,
    enrichment_for,
    supports_pipeline_sync,
)
from app.services.integration_definitions import INTEGRATION_DEFINITIONS
from app.services.monitoring_ingestion import INGEST_POLLERS
from app.services.universal_discovery_adapters import supports_universal_discovery

ALL_KEYS = set(INTEGRATION_DEFINITIONS.keys())


def test_all_35_integrations_defined():
    assert len(ALL_KEYS) == 35


@pytest.mark.parametrize("key", sorted(ALL_KEYS))
def test_every_integration_has_enrichment(key):
    e = enrichment_for(key)
    assert e["integration_key"] == key
    assert e["unlocks_now"]
    assert e["unlocks_live"]


@pytest.mark.parametrize("key", sorted(ALL_KEYS))
def test_every_integration_has_live_data_path(key):
    e = enrichment_for(key)
    assert e["live_data"] is True, f"{key} has no discovery, ingest, or pipeline sync"


def test_pipeline_sync_keys():
    for key in ("JENKINS", "CIRCLECI", "AZURE_DEVOPS", "GITHUB", "GITLAB", "BITBUCKET", "BUILDKITE", "HARNESS"):
        assert supports_pipeline_sync(key)


def test_gitops_sync_keys():
    from app.services.integration_capabilities import supports_gitops_sync
    for key in ("ARGOCD", "FLUX"):
        assert supports_gitops_sync(key)


def test_discovery_coverage():
    discovered = {k for k in ALL_KEYS if enrichment_for(k)["discovery"]}
    assert "GCP" in discovered or supports_universal_discovery("GCP")
    assert "BITBUCKET" in discovered
    assert "SONARQUBE" in discovered
    assert "HASHICORP_VAULT" in discovered


def test_ingest_coverage():
    ingested = set(INGEST_POLLERS.keys())
    for key in (
        "AWS", "AZURE", "CLOUDWATCH", "PROMETHEUS", "ALERTMANAGER", "KUBERNETES", "GITHUB", "GITLAB",
        "BITBUCKET", "JENKINS", "CIRCLECI", "DATADOG", "PAGERDUTY", "OPSGENIE",
        "GRAFANA", "NEW_RELIC", "LOKI", "ELASTIC", "SONARQUBE", "GCP",
        "SPLUNK", "SERVICENOW", "OPENTELEMETRY",
        "SENTRY", "DYNATRACE", "BUILDKITE", "HARNESS",
    ):
        assert key in ingested


def test_gcp_in_ingest_pollers():
    assert "GCP" in INGEST_POLLERS


def test_bitbucket_enrichment():
    e = enrichment_for("BITBUCKET")
    assert e["pipeline_sync"] is True
    assert e["discovery"] is True
    assert e["alert_ingest"] is True


def test_enterprise_mutation_keys():
    for key in ("SERVICENOW", "SENTRY", "SPLUNK"):
        e = enrichment_for(key)
        assert e["enterprise_mutations"] is True
    assert enrichment_for("GITHUB")["enterprise_mutations"] is False


def test_all_integrations_have_credential_schema():
    from app.security.secrets.service import REQUIRED_FIELDS

    missing = [k for k in ALL_KEYS if k not in REQUIRED_FIELDS]
    assert not missing, f"REQUIRED_FIELDS missing: {missing}"
