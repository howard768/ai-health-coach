import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger("meld.database")

engine = create_async_engine(settings.database_url, echo=settings.app_env == "development")
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


def _run_alembic_migrations() -> None:
    """Run any pending Alembic migrations synchronously.

    Called at app startup to ensure schema is always up-to-date before
    requests are served. Idempotent — no-op if already at head.
    """
    from alembic.config import Config
    from alembic import command

    alembic_ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    if not alembic_ini.exists():
        logger.warning("alembic.ini not found — skipping migrations")
        return

    alembic_cfg = Config(str(alembic_ini))
    # Ensure Alembic uses the same DB as the app, with sync driver
    db_url = settings.database_url
    if db_url.startswith("sqlite+aiosqlite://"):
        db_url = db_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    elif db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    alembic_cfg.set_main_option("script_location", str(alembic_ini.parent / "alembic"))

    print("alembic: pre-upgrade (acquiring advisory lock + checking head)", flush=True)
    logger.info("Running Alembic migrations...")
    command.upgrade(alembic_cfg, "head")
    print("alembic: upgrade returned", flush=True)
    logger.info("Alembic migrations complete")


async def init_db():
    """Initialize the database — runs migrations to bring schema to head."""
    import asyncio
    # Alembic is synchronous; offload to a thread so we don't block the event loop.
    await asyncio.to_thread(_run_alembic_migrations)
