"""Kubernetes API client — shared by discovery and operations (no duplicate SDK wiring)."""

from __future__ import annotations

import os
import tempfile
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class K8sApiBundle:
    """Lazy-loaded Kubernetes Python SDK handles."""

    def __init__(self, kubeconfig: str) -> None:
        import yaml
        from kubernetes import client, config

        fd, self._path = tempfile.mkstemp(suffix=".kubeconfig")
        with os.fdopen(fd, "w") as handle:
            handle.write(kubeconfig)
        cfg = yaml.safe_load(kubeconfig)
        loader = config.kube_config.KubeConfigLoader(config_dict=cfg)
        configuration = client.Configuration()
        loader.load_and_set(configuration)
        api_client = client.ApiClient(configuration)
        self.core = client.CoreV1Api(api_client)
        self.apps = client.AppsV1Api(api_client)
        self.batch = client.BatchV1Api(api_client)
        self.net = client.NetworkingV1Api(api_client)
        self.autoscaling = client.AutoscalingV2Api(api_client)
        self.rbac = client.RbacAuthorizationV1Api(api_client)
        self.apiextensions = client.ApiextensionsV1Api(api_client)
        self.storage = client.StorageV1Api(api_client)
        self.version = client.VersionApi(api_client)
        self._context_cluster = ""
        current = cfg.get("current-context")
        for ctx in cfg.get("contexts", []):
            if ctx.get("name") == current:
                self._context_cluster = ctx.get("context", {}).get("cluster", "")

    def cleanup(self) -> None:
        try:
            os.unlink(self._path)
        except OSError:
            pass

    @property
    def cluster_name(self) -> str:
        return self._context_cluster or "kubernetes"


def open_client(secret: dict) -> K8sApiBundle:
    raw = secret.get("kubeconfig")
    if not raw:
        raise ValueError("kubeconfig required")
    return K8sApiBundle(raw)
