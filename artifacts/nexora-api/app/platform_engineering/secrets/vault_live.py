"""Live HashiCorp Vault KV metadata reads (no secret values exposed)."""

from __future__ import annotations

from app.delivery.pipelines.ci_http import bearer_header, get_json


def read_kv_metadata(secret: dict, path: str) -> dict:
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    token = secret.get("token")
    if not endpoint or not token or not path:
        return {"reachable": False, "reason": "missing_credentials_or_path"}
    clean = path.strip("/")
    if clean.startswith("secret/data/"):
        clean = clean[len("secret/data/"):]
    elif clean.startswith("secret/"):
        clean = clean[len("secret/"):]
    url = f"{endpoint}/v1/secret/metadata/{clean}"
    try:
        data = get_json(url, headers=bearer_header(token))
    except RuntimeError as exc:
        return {"reachable": False, "error": str(exc)[:200]}
    meta = (data.get("data") or {}) if isinstance(data, dict) else {}
    versions = meta.get("versions") or {}
    return {
        "reachable": True,
        "path": clean,
        "current_version": meta.get("current_version"),
        "max_versions": meta.get("max_versions"),
        "version_count": len(versions) if isinstance(versions, dict) else 0,
        "created_time": meta.get("created_time"),
        "updated_time": meta.get("updated_time"),
        "custom_metadata": meta.get("custom_metadata") or {},
    }
