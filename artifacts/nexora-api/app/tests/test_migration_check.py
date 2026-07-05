"""Tests for the Alembic migration checker (app.database.migration_check).

Covers head detection from the real migration scripts, the version-comparison
logic, the fail-fast verifier, and a real database read of ``alembic_version``.
"""

import pytest

from app.database import migration_check as mc

HEAD = "0039_customer_pilot_operations"
SUPPORTED_DOWNGRADE_FLOOR = "0013_converge_graph"


def test_get_head_revision_matches_repo_head():
    assert mc.get_head_revision() == HEAD


def test_no_multiple_heads():
    # Branching (>1 head) would mean an un-merged migration branch.
    assert len(mc.get_heads()) == 1


async def test_check_migrations_ok(monkeypatch):
    async def _current():
        return HEAD

    monkeypatch.setattr(mc, "get_current_revision", _current)
    status = await mc.check_migrations()
    assert status.ok is True
    assert status.current == HEAD
    assert status.head == HEAD


async def test_check_migrations_behind(monkeypatch):
    async def _current():
        return "001_organizations"

    monkeypatch.setattr(mc, "get_current_revision", _current)
    status = await mc.check_migrations()
    assert status.ok is False
    assert status.current == "001_organizations"
    assert HEAD in status.detail
    assert "upgrade head" in status.detail


async def test_check_migrations_unmigrated(monkeypatch):
    async def _current():
        return None

    monkeypatch.setattr(mc, "get_current_revision", _current)
    status = await mc.check_migrations()
    assert status.ok is False
    assert "no alembic_version" in status.detail


async def test_check_migrations_db_error(monkeypatch):
    async def _current():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(mc, "get_current_revision", _current)
    status = await mc.check_migrations()
    assert status.ok is False
    assert "could not read database revision" in status.detail


async def test_verify_raises_when_not_ok(monkeypatch):
    async def _status():
        return mc.MigrationStatus(False, "001", HEAD, "behind")

    monkeypatch.setattr(mc, "check_migrations", _status)
    with pytest.raises(RuntimeError, match="migration check failed"):
        await mc.verify_migrations_or_raise()


async def test_verify_passes_when_ok(monkeypatch):
    async def _status():
        return mc.MigrationStatus(True, HEAD, HEAD, "ok")

    monkeypatch.setattr(mc, "check_migrations", _status)
    await mc.verify_migrations_or_raise()  # must not raise


def test_supported_downgrade_floor_is_documented():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(mc._ALEMBIC_INI))
    script = ScriptDirectory.from_config(cfg)
    rev = script.get_revision(SUPPORTED_DOWNGRADE_FLOOR)
    assert rev is not None
    with pytest.raises(NotImplementedError):
        rev.module.downgrade()


async def test_get_current_revision_reads_alembic_version(monkeypatch, tmp_path):
    # Real read path: a file-backed sqlite DB stamped with an alembic_version row.
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    db_path = tmp_path / "rev.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with test_engine.begin() as conn:
        await conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(64) NOT NULL)"))
        await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": HEAD})

    import app.database.session as session_mod

    monkeypatch.setattr(session_mod, "engine", test_engine)
    try:
        current = await mc.get_current_revision()
        assert current == HEAD
    finally:
        await test_engine.dispose()
