"""PostgreSQL Alembic chain validation (Sprint 66B).

Requires a running PostgreSQL instance (Docker Compose ``db`` service).
Set ``NEXORA_POSTGRES_MIGRATION_TEST=1`` and a PostgreSQL ``DATABASE_URL``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import migration_check as mc

HEAD = "0039_customer_pilot_operations"
SUPPORTED_DOWNGRADE_FLOOR = "0013_converge_graph"

OPERATIONS_TABLES = (
    "pilot_notification_deliveries",
    "pilot_scheduler_health_snapshots",
)

COMMUNICATIONS_TABLES = (
    "pilot_customer_communications",
    "pilot_communication_comments",
    "pilot_notification_preferences",
    "pilot_approval_reminder_deliveries",
)

CUSTOMER_PILOT_TABLES = ("pilot_approval_packages", "pilot_closeout_requests")

ONBOARDING_TABLES = ("int_onboarding_sessions",)

PILOT_TABLES = (
    "pilot_enrollments",
    "pilot_checklist_items",
    "pilot_assessments",
    "pilot_scorecards",
    "pilot_live_operations",
    "pilot_stages",
    "pilot_approvals",
)

KEY_TABLES_FROM_0026 = ("op_policies", "op_goals")

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _async_postgres_url() -> str | None:
    if os.environ.get("NEXORA_POSTGRES_MIGRATION_TEST") != "1":
        return None
    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        return None
    if raw.startswith("postgres://"):
        raw = raw.replace("postgres://", "postgresql+asyncpg://", 1)
    elif raw.startswith("postgresql://") and "+asyncpg" not in raw:
        raw = raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    if "postgresql" not in raw:
        return None
    return raw


def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    db_url = env.get("DATABASE_URL", "")
    if db_url and "+asyncpg" not in db_url:
        if db_url.startswith("postgresql://"):
            env["DATABASE_URL"] = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif db_url.startswith("postgres://"):
            env["DATABASE_URL"] = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


async def _reset_public_schema(async_url: str) -> None:
    engine = create_async_engine(async_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    await engine.dispose()


async def _tables_exist(async_url: str, names: tuple[str, ...]) -> dict[str, bool]:
    engine = create_async_engine(async_url)
    try:
        async with engine.connect() as conn:
            existing = await conn.run_sync(lambda sync: set(inspect(sync).get_table_names()))
        return {name: name in existing for name in names}
    finally:
        await engine.dispose()


def test_single_head():
    assert mc.get_head_revision() == HEAD
    assert len(mc.get_heads()) == 1


def test_irreversible_boundary_documented():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(_REPO_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    rev = script.get_revision(SUPPORTED_DOWNGRADE_FLOOR)
    assert rev is not None
    with pytest.raises(NotImplementedError):
        rev.module.downgrade()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_migration_chain_full(monkeypatch):
    async_url = _async_postgres_url()
    if not async_url:
        pytest.skip("Set NEXORA_POSTGRES_MIGRATION_TEST=1 with a PostgreSQL DATABASE_URL")

    await _reset_public_schema(async_url)

    upgrade = _run_alembic("upgrade", "head")
    assert upgrade.returncode == 0, upgrade.stderr or upgrade.stdout

    current = _run_alembic("current")
    assert current.returncode == 0
    assert HEAD in current.stdout

    heads = _run_alembic("heads")
    assert heads.returncode == 0
    assert HEAD in heads.stdout
    assert heads.stdout.count("(head)") == 1

    pilot = await _tables_exist(async_url, PILOT_TABLES)
    assert all(pilot.values()), f"missing pilot tables: {pilot}"

    onboarding = await _tables_exist(async_url, ONBOARDING_TABLES)
    assert all(onboarding.values()), f"missing onboarding tables: {onboarding}"

    customer_pilot = await _tables_exist(async_url, CUSTOMER_PILOT_TABLES)
    assert all(customer_pilot.values()), f"missing customer pilot tables: {customer_pilot}"

    communications = await _tables_exist(async_url, COMMUNICATIONS_TABLES)
    assert all(communications.values()), f"missing communications tables: {communications}"

    operations = await _tables_exist(async_url, OPERATIONS_TABLES)
    assert all(operations.values()), f"missing operations tables: {operations}"

    key = await _tables_exist(async_url, KEY_TABLES_FROM_0026)
    assert all(key.values()), f"missing 0026 tables: {key}"

    down = _run_alembic("downgrade", SUPPORTED_DOWNGRADE_FLOOR)
    assert down.returncode == 0, down.stderr or down.stdout

    current_floor = _run_alembic("current")
    assert SUPPORTED_DOWNGRADE_FLOOR in current_floor.stdout

    down_below_floor = _run_alembic("downgrade", "0012_converge_discovery")
    assert down_below_floor.returncode != 0
    assert "NotImplementedError" in (down_below_floor.stderr + down_below_floor.stdout)

    reup = _run_alembic("upgrade", "head")
    assert reup.returncode == 0, reup.stderr or reup.stdout

    pilot_after = await _tables_exist(async_url, PILOT_TABLES)
    assert all(pilot_after.values()), f"pilot tables missing after re-upgrade: {pilot_after}"

    onboarding_after = await _tables_exist(async_url, ONBOARDING_TABLES)
    assert all(onboarding_after.values()), f"onboarding tables missing after re-upgrade: {onboarding_after}"

    customer_pilot_after = await _tables_exist(async_url, CUSTOMER_PILOT_TABLES)
    assert all(customer_pilot_after.values()), f"customer pilot tables missing after re-upgrade: {customer_pilot_after}"

    communications_after = await _tables_exist(async_url, COMMUNICATIONS_TABLES)
    assert all(communications_after.values()), f"communications tables missing after re-upgrade: {communications_after}"

    operations_after = await _tables_exist(async_url, OPERATIONS_TABLES)
    assert all(operations_after.values()), f"operations tables missing after re-upgrade: {operations_after}"

    monkeypatch.setenv("DATABASE_URL", async_url)
    from app.database import session as session_mod

    test_engine = create_async_engine(async_url)
    monkeypatch.setattr(session_mod, "engine", test_engine)
    try:
        status = await mc.check_migrations()
        assert status.ok is True
        assert status.current == HEAD
        assert status.head == HEAD
        await mc.verify_migrations_or_raise()
    finally:
        await test_engine.dispose()
