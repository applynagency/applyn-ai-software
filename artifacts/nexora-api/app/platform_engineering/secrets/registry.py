"""Secret backend registry — references only, never values."""

from __future__ import annotations

from app.platform_engineering.types import SecretBackendType

_BACKENDS = {
    SecretBackendType.VAULT: {"path_prefix": "secret/data/", "rotation_supported": True},
    SecretBackendType.AWS_SECRETS_MANAGER: {"path_prefix": "arn:aws:secretsmanager:", "rotation_supported": True},
    SecretBackendType.AZURE_KEY_VAULT: {"path_prefix": "https://vault.azure.net/secrets/", "rotation_supported": True},
    SecretBackendType.GCP_SECRET_MANAGER: {"path_prefix": "projects/", "rotation_supported": True},
    SecretBackendType.KUBERNETES: {"path_prefix": "namespace/", "rotation_supported": False},
}


def supported_secret_backends() -> list[str]:
    return [b.value for b in SecretBackendType]


def resolve_secret_ref(backend: str, path: str, *, vault_config: dict | None = None) -> dict:
    """Return metadata about a secret reference — never the secret value."""
    meta = _BACKENDS.get(SecretBackendType(backend), {})
    result = {
        "backend": backend,
        "path": path,
        "path_prefix": meta.get("path_prefix", ""),
        "rotation_supported": meta.get("rotation_supported", False),
        "value": None,
        "note": "Secret values are never exposed via API",
    }
    if vault_config and str(backend).upper() == SecretBackendType.VAULT.value:
        from app.platform_engineering.secrets import vault_live

        live = vault_live.read_kv_metadata(vault_config, path)
        result["live"] = live
        result["reachable"] = live.get("reachable", False)
    return result
