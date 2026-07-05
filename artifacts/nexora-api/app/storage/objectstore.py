"""Object-storage abstraction (Sprint 62B).

A single interface for binary/blob storage (uploads, exports, support bundles,
backups) so call sites do not hardcode the local filesystem. The backend is
chosen by ``OBJECT_STORE_BACKEND``:

* ``local`` (default) — filesystem under ``OBJECT_STORE_LOCAL_DIR`` (dev/single
  node + tests; no extra dependencies)
* ``s3``              — S3-compatible bucket (lazy ``boto3``), for multi-region
  deployments where every region reads the same object store / replicated bucket

No active-active write coordination — this is purely a storage seam.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ObjectStore:
    """Minimal blob store interface."""

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        raise NotImplementedError

    async def get(self, key: str) -> bytes | None:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError

    async def exists(self, key: str) -> bool:
        raise NotImplementedError

    def url(self, key: str) -> str:
        raise NotImplementedError


class LocalObjectStore(ObjectStore):
    def __init__(self, base_dir: str | None = None) -> None:
        self.base = Path(base_dir or settings.OBJECT_STORE_LOCAL_DIR)

    def _path(self, key: str) -> Path:
        # Prevent path traversal: keys are treated as relative POSIX paths.
        safe = os.path.normpath(key).lstrip("/").replace("..", "")
        return self.base / safe

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.url(key)

    async def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.exists() else None

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    async def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def url(self, key: str) -> str:
        base = settings.CDN_BASE_URL
        if base:
            return f"{base.rstrip('/')}/{key.lstrip('/')}"
        return f"file://{self._path(key)}"


class S3ObjectStore(ObjectStore):
    def __init__(self, bucket: str | None = None) -> None:
        self.bucket = bucket or settings.OBJECT_STORE_BUCKET
        if not self.bucket:
            raise ValueError("OBJECT_STORE_BUCKET is required for the s3 backend")
        self._client = None

    def _s3(self):
        if self._client is None:
            import boto3  # lazy: only required for the s3 backend

            self._client = boto3.client(
                "s3", region_name=settings.AWS_BEDROCK_REGION or settings.AZURE_REGION)
        return self._client

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        import asyncio

        def _do():
            extra = {"ContentType": content_type} if content_type else {}
            self._s3().put_object(Bucket=self.bucket, Key=key, Body=data, **extra)
        await asyncio.to_thread(_do)
        return self.url(key)

    async def get(self, key: str) -> bytes | None:
        import asyncio

        def _do():
            try:
                resp = self._s3().get_object(Bucket=self.bucket, Key=key)
                return resp["Body"].read()
            except Exception:
                return None
        return await asyncio.to_thread(_do)

    async def delete(self, key: str) -> None:
        import asyncio

        await asyncio.to_thread(
            lambda: self._s3().delete_object(Bucket=self.bucket, Key=key))

    async def exists(self, key: str) -> bool:
        import asyncio

        def _do():
            try:
                self._s3().head_object(Bucket=self.bucket, Key=key)
                return True
            except Exception:
                return False
        return await asyncio.to_thread(_do)

    def url(self, key: str) -> str:
        base = settings.CDN_BASE_URL
        if base:
            return f"{base.rstrip('/')}/{key.lstrip('/')}"
        return f"s3://{self.bucket}/{key}"


_STORE: ObjectStore | None = None


def get_object_store() -> ObjectStore:
    """Return the process-wide object store for the configured backend."""
    global _STORE
    if _STORE is not None:
        return _STORE
    backend = (settings.OBJECT_STORE_BACKEND or "local").lower()
    if backend == "s3":
        _STORE = S3ObjectStore()
    else:
        _STORE = LocalObjectStore()
    return _STORE


def reset_object_store() -> None:  # test helper
    global _STORE
    _STORE = None
