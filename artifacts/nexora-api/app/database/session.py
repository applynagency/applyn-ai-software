from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_engine_kwargs: dict = {"echo": settings.DEBUG}
if "sqlite" in settings.DATABASE_URL:
    # Single shared connection for in-memory sqlite (tests + local dev).
    from sqlalchemy.pool import StaticPool

    _engine_kwargs["poolclass"] = StaticPool
elif "sqlite" not in settings.DATABASE_URL:
    _engine_kwargs.update(
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_recycle=settings.DATABASE_POOL_RECYCLE,
        # Liveness-check each pooled connection before use so a connection
        # broken by a DB failover/restart is transparently discarded and
        # replaced instead of raising on the next query.
        pool_pre_ping=True,
    )

engine = create_async_engine(
    settings.DATABASE_URL,
    **_engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """Create all tables directly from the ORM metadata.

    NOTE: This is for the **test suite and local sqlite development only**. The
    production schema is owned exclusively by Alembic migrations — the
    application no longer calls this at startup (see
    ``app.database.migration_check``). Do not use this at runtime.
    """
    import app.models  # noqa: F401 — registers all models
    from app.database.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


async def drop_tables() -> None:
    from app.database.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.info("Database tables dropped")
