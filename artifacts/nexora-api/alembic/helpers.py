"""Shared helpers for idempotent Alembic migrations.

Import from new migrations to avoid duplicating inspector utilities across
revision files. Existing applied revisions are frozen; this module is for
forward-looking migrations only.
"""

from __future__ import annotations

from sqlalchemy import inspect


def has_table(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def has_column(bind, table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(bind).get_columns(table)}


def has_index(bind, table: str, index: str) -> bool:
    return index in {i["name"] for i in inspect(bind).get_indexes(table)}
