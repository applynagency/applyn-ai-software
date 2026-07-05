"""Alembic migration verification.

The application no longer creates tables at runtime (``Base.metadata.create_all``
is gone from startup). The database schema is owned exclusively by Alembic
migrations, and startup *verifies* that the connected database has been migrated
to the latest revision — failing fast otherwise.

This module provides:

* :func:`get_head_revision` — the latest revision defined by the migration
  scripts (no database needed).
* :func:`get_current_revision` — the revision currently stamped in the database
  (``alembic_version``).
* :func:`check_migrations` / :func:`verify_migrations_or_raise` — compare the two.

It is also runnable as a CLI for CI:

    python -m app.database.migration_check          # report status, exit 1 if behind
    python -m app.database.migration_check --head   # just print the head revision
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _script_directory():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(Config(str(_ALEMBIC_INI)))


def get_heads() -> list[str]:
    """All head revisions defined by the migration scripts (>1 means branching)."""
    return list(_script_directory().get_heads())


def get_head_revision() -> str | None:
    """The single latest migration revision, or ``None`` if there are none."""
    heads = get_heads()
    if not heads:
        return None
    if len(heads) > 1:
        # Multiple heads indicate an un-merged branch — surface it explicitly.
        raise RuntimeError(f"Multiple Alembic heads detected: {sorted(heads)}")
    return heads[0]


async def get_current_revision() -> str | None:
    """The revision currently applied to the database (None if never migrated)."""
    from app.database.session import engine

    def _read(sync_conn) -> str | None:
        from alembic.runtime.migration import MigrationContext

        return MigrationContext.configure(sync_conn).get_current_revision()

    async with engine.connect() as conn:
        return await conn.run_sync(_read)


@dataclass
class MigrationStatus:
    ok: bool
    current: str | None
    head: str | None
    detail: str


async def check_migrations() -> MigrationStatus:
    """Compare the database revision with the migration head."""
    try:
        head = get_head_revision()
    except Exception as exc:
        return MigrationStatus(False, None, None, f"could not read migration scripts: {exc}")

    try:
        current = await get_current_revision()
    except Exception as exc:
        return MigrationStatus(False, None, head, f"could not read database revision: {exc}")

    if current is None:
        return MigrationStatus(
            False,
            None,
            head,
            "database has no alembic_version row — no migrations applied. "
            "Run 'alembic upgrade head'.",
        )
    if current != head:
        return MigrationStatus(
            False,
            current,
            head,
            f"database is at revision {current!r} but head is {head!r}. "
            "Run 'alembic upgrade head'.",
        )
    return MigrationStatus(True, current, head, f"database is up to date at {head!r}.")


async def verify_migrations_or_raise() -> None:
    """Raise ``RuntimeError`` unless the database is migrated to head."""
    status = await check_migrations()
    if not status.ok:
        raise RuntimeError(f"Database migration check failed: {status.detail}")
    logger.info("migration_check_passed", extra={"revision": status.current})


def _main() -> int:
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Nexora Alembic migration checker")
    parser.add_argument("--head", action="store_true", help="print the head revision and exit")
    args = parser.parse_args()

    if args.head:
        print(get_head_revision() or "")
        return 0

    status = asyncio.run(check_migrations())
    print(
        f"current={status.current} head={status.head} ok={status.ok}\n{status.detail}"
    )
    return 0 if status.ok else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(_main())
