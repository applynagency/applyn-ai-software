"""Tests for live Argo CD GitOps listing."""

from app.delivery.gitops.argocd_live import list_applications


def test_argocd_live_returns_empty_without_credentials():
    assert list_applications({}) == []
    assert list_applications({"endpoint": "https://argocd.example.com"}) == []


def test_argocd_live_maps_applications(monkeypatch):
    def fake_get_json(url, *, headers=None, auth=None, timeout=20.0):
        assert "/api/v1/applications" in url
        return {
            "items": [{
                "metadata": {"name": "checkout", "namespace": "prod"},
                "spec": {"project": "default", "syncPolicy": {"automated": {}}},
                "status": {
                    "health": {"status": "Healthy"},
                    "sync": {"status": "Synced", "revision": "abc123"},
                    "history": [{"id": 1, "revision": "abc123"}],
                },
            }],
        }

    monkeypatch.setattr("app.delivery.gitops.argocd_live.get_json", fake_get_json)
    apps = list_applications({"endpoint": "https://argocd.example.com", "token": "tok"})
    assert len(apps) == 1
    assert apps[0].name == "checkout"
    assert apps[0].engine == "ArgoCD"
    assert apps[0].sync_status == "Synced"
    assert apps[0].auto_sync is True
