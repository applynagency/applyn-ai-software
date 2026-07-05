"""Object storage abstraction (Sprint 62B)."""

from app.storage.objectstore import (
    LocalObjectStore,
    ObjectStore,
    S3ObjectStore,
    get_object_store,
)

__all__ = ["ObjectStore", "LocalObjectStore", "S3ObjectStore", "get_object_store"]
